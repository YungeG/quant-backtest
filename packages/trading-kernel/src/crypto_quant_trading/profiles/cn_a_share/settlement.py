"""Mainland China cash-equity settlement and availability semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import cast
import unicodedata
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    Fill,
    InstrumentDefinition,
    InstrumentType,
    Money,
    OrderSide,
    PositionBalanceKey,
    Quantity,
    SettlementObligation,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading.ports import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)
from crypto_quant_trading.ledger import LedgerSchema
from crypto_quant_trading.settlement import (
    AccountSettlementObligation,
    AvailabilityEvidenceError,
    CashAvailabilityRule,
    CashReservationUse,
    MarketSettlementRules,
    PositionAvailabilityRule,
)

from .calendar import (
    CnAShareCalendarDayKind,
    CnAShareCashSessionModel,
    CnAShareFrozenCalendar,
    CnAShareSessionFailureCode,
    CnAShareSessionQuery,
)


_COMPONENT_KEY = "equity.cn_a_share.cash.settlement.v1"
_ALGORITHM_KEY = "cn-a-share-cash-settlement-availability-v1"
_APPLICABILITY_KEY = "ordinary-rmb-a-share-cny-cash-v1"
_POLICY_KEY = "equity.cn_a_share.cash.availability.v1"
_CNY = CurrencyId("CNY")
_TIMEZONE = ZoneInfo("Asia/Shanghai")
_CALENDAR_BY_VENUE = {"xshg": "CN.XSHG", "xshe": "CN.XSHE"}


class CnAShareSettlementFailureCode(Enum):
    UNSUPPORTED_VENUE = "unsupported_venue"
    UNSUPPORTED_INSTRUMENT = "unsupported_instrument"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    TRADE_TIME_NOT_OPEN = "trade_time_not_open"
    CALENDAR_COVERAGE_MISSING = "calendar_coverage_missing"
    ACCOUNTING_EFFECT_MISMATCH = "accounting_effect_mismatch"
    SETTLEMENT_IDENTITY_MISMATCH = "settlement_identity_mismatch"


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    text = _canonical_text(name, value)
    if (
        len(text) != 71
        or not text.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in text[7:])
    ):
        raise ValueError(f"{name} must be canonical sha256 identity")
    return text


def _availability_policy_payload() -> dict[str, object]:
    return {
        "policy_key": _POLICY_KEY,
        "policy_version": 1,
        "cash": {
            "pending_receivable_tradable": True,
            "pending_receivable_withdrawable": False,
            "pending_receivable_margin_eligible": False,
            "tradable_reservation_uses": ("cash", "fee_reserve"),
            "withdrawable_reservation_uses": ("cash", "fee_reserve"),
            "available_margin_reservation_uses": (),
        },
        "position": {"pending_receivable_sellable": False},
    }


@dataclass(frozen=True, slots=True)
class CnAShareSettlementQuery:
    fill: Fill
    instrument: InstrumentDefinition
    fill_accounting_entry: AccountingJournalEntry
    cash_obligation_id: DomainId
    position_obligation_id: DomainId

    def __post_init__(self) -> None:
        if not isinstance(self.fill, Fill):
            raise TypeError("fill must be Fill")
        if not isinstance(self.instrument, InstrumentDefinition):
            raise TypeError("instrument must be InstrumentDefinition")
        if not isinstance(self.fill_accounting_entry, AccountingJournalEntry):
            raise TypeError("fill_accounting_entry must be AccountingJournalEntry")
        if not isinstance(self.cash_obligation_id, DomainId):
            raise TypeError("cash_obligation_id must be DomainId")
        if not isinstance(self.position_obligation_id, DomainId):
            raise TypeError("position_obligation_id must be DomainId")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_settlement_query",
            "schema_version": 1,
            "fill": self.fill,
            "instrument": self.instrument,
            "fill_accounting_entry": self.fill_accounting_entry,
            "cash_obligation_id": self.cash_obligation_id,
            "position_obligation_id": self.position_obligation_id,
        }


@dataclass(frozen=True, slots=True)
class CnAShareSettlementResolution:
    venue_id: VenueId
    fill_id: DomainId
    trade_date: TradingDate
    next_trading_date: TradingDate
    position_availability_time: UtcInstant
    cash_withdrawal_time: UtcInstant
    fill_accounting_entry_hash: str
    obligations: tuple[AccountSettlementObligation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.fill_id, DomainId) or self.fill_id.kind is not DomainIdKind.FILL:
            raise ValueError("fill_id must be Fill DomainId")
        if not isinstance(self.trade_date, TradingDate) or not isinstance(
            self.next_trading_date, TradingDate
        ):
            raise TypeError("trade dates must be TradingDate")
        if self.trade_date.calendar_id != self.next_trading_date.calendar_id:
            raise ValueError("trade dates must share calendar identity")
        if self.next_trading_date.value <= self.trade_date.value:
            raise ValueError("next_trading_date must be after trade_date")
        if not isinstance(self.position_availability_time, UtcInstant) or not isinstance(
            self.cash_withdrawal_time, UtcInstant
        ):
            raise TypeError("availability times must be UtcInstant")
        if self.cash_withdrawal_time < self.position_availability_time:
            raise ValueError("cash withdrawal cannot precede position availability")
        _hash("fill_accounting_entry_hash", self.fill_accounting_entry_hash)
        if (
            not isinstance(self.obligations, tuple)
            or len(self.obligations) != 2
            or not all(
                isinstance(value, AccountSettlementObligation)
                for value in self.obligations
            )
        ):
            raise ValueError("obligations must contain Cash then Position legs")
        cash, position = self.obligations
        expected_calendar = _CALENDAR_BY_VENUE.get(self.venue_id.value)
        if (
            expected_calendar is None
            or self.trade_date.calendar_id != expected_calendar
            or self.next_trading_date.calendar_id != expected_calendar
            or not isinstance(cash.balance_key, CashBalanceKey)
            or not isinstance(position.balance_key, PositionBalanceKey)
            or cash.balance_key.account_id != position.balance_key.account_id
            or cash.balance_key.currency_id != _CNY
            or cash.obligation.currency_id != _CNY
            or cash.obligation.amount is None
            or cash.obligation.amount.currency != _CNY.value
            or cash.balance_key.venue_id != self.venue_id
            or position.balance_key.venue_id != self.venue_id
            or position.balance_key.instrument_id.venue != self.venue_id
            or cash.obligation.settlement_obligation_id
            == position.obligation.settlement_obligation_id
            or cash.obligation.currency_id is None
            or position.obligation.instrument_id is None
            or cash.obligation.source_fill_id != self.fill_id
            or position.obligation.source_fill_id != self.fill_id
            or cash.obligation.trade_time != position.obligation.trade_time
            or cash.units * position.units >= 0
        ):
            raise ValueError("obligations must be Cash then Position legs for fill")
        trade_time = cash.obligation.trade_time
        if _local_date_for(trade_time) != self.trade_date.value:
            raise ValueError("obligation trade_time does not match trade_date")
        expected_cash_time = (
            trade_time if cash.units < 0 else self.cash_withdrawal_time
        )
        expected_position_time = (
            trade_time if position.units < 0 else self.position_availability_time
        )
        if (
            self.position_availability_time
            != _local_boundary(self.next_trading_date.value, 0)
            or self.cash_withdrawal_time
            != _local_boundary(self.next_trading_date.value, 16)
            or self.position_availability_time <= trade_time
            or self.cash_withdrawal_time <= trade_time
            or cash.obligation.settlement_time != expected_cash_time
            or position.obligation.settlement_time != expected_position_time
        ):
            raise ValueError("obligation settlement times do not match resolution")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_settlement_resolution",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "fill_id": self.fill_id,
            "trade_date": self.trade_date,
            "next_trading_date": self.next_trading_date,
            "position_availability_time": self.position_availability_time,
            "cash_withdrawal_time": self.cash_withdrawal_time,
            "fill_accounting_entry_hash": self.fill_accounting_entry_hash,
            "obligations": self.obligations,
        }


@dataclass(frozen=True, slots=True)
class CnAShareSettlementFailure:
    code: CnAShareSettlementFailureCode
    fill_id: DomainId
    venue_id: VenueId
    calendar_id: str
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, CnAShareSettlementFailureCode):
            raise TypeError("code must be CnAShareSettlementFailureCode")
        if not isinstance(self.fill_id, DomainId) or self.fill_id.kind is not DomainIdKind.FILL:
            raise ValueError("fill_id must be Fill DomainId")
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        _canonical_text("calendar_id", self.calendar_id)
        _canonical_text("subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_settlement_failure",
            "schema_version": 1,
            "code": self.code.value,
            "fill_id": self.fill_id,
            "venue_id": self.venue_id,
            "calendar_id": self.calendar_id,
            "subject_key": self.subject_key,
        }


def _local_date_for(instant: UtcInstant) -> date:
    try:
        return instant.to_datetime().astimezone(_TIMEZONE).date()
    except (OverflowError, ValueError) as error:
        raise ValueError("trade_time is outside supported calendar range") from error


def _local_boundary(local_date: date, hour: int) -> UtcInstant:
    return UtcInstant.from_datetime(
        datetime.combine(local_date, time(hour=hour), tzinfo=_TIMEZONE)
    )


def _accounting_effects(
    query: CnAShareSettlementQuery,
) -> tuple[CashBalanceKey, Money, PositionBalanceKey, Quantity] | None:
    fill = query.fill
    entry = query.fill_accounting_entry
    if (
        entry.entry_type is not AccountingEntryType.FILL_BOOKED
        or entry.effective_time != fill.execution_time
        or entry.recorded_at.instant < fill.execution_time
        or entry.account_id != fill.account_id
        or entry.venue_id != fill.venue_id
        or len(entry.source_ids) != 2
        or set(entry.source_ids) != {fill.fill_id.value, fill.order_id.value}
        or entry.fees
        or entry.financing
        or len(entry.balance_changes) != 2
    ):
        return None
    cash_changes = tuple(
        value
        for value in entry.balance_changes
        if isinstance(value.key, CashBalanceKey)
    )
    position_changes = tuple(
        value
        for value in entry.balance_changes
        if isinstance(value.key, PositionBalanceKey)
    )
    if len(cash_changes) != 1 or len(position_changes) != 1:
        return None
    cash_change = cash_changes[0]
    position_change = position_changes[0]
    if not isinstance(cash_change.value, Money) or not isinstance(
        position_change.value, Quantity
    ):
        return None
    cash_key = cast(CashBalanceKey, cash_change.key)
    position_key = cast(PositionBalanceKey, position_change.key)
    cash_value = cast(Money, cash_change.value)
    position_value = cast(Quantity, position_change.value)
    expected_position_units = (
        fill.quantity.units
        if fill.side is OrderSide.BUY
        else -fill.quantity.units
    )
    expected_cash_sign = -1 if fill.side is OrderSide.BUY else 1
    if (
        cash_key.account_id != fill.account_id
        or cash_key.venue_id != fill.venue_id
        or cash_key.currency_id != _CNY
        or cash_value.currency != _CNY.value
        or cash_value.units * expected_cash_sign <= 0
        or position_key.account_id != fill.account_id
        or position_key.venue_id != fill.venue_id
        or position_key.instrument_id != fill.instrument_id
        or position_value.instrument_id != str(fill.instrument_id)
        or position_value.scale != fill.quantity.scale
        or position_value.units != expected_position_units
    ):
        return None
    return cash_key, cash_value, position_key, position_value


@dataclass(frozen=True, slots=True)
class CnAShareCashSettlementModel:
    calendar: CnAShareFrozenCalendar

    def __post_init__(self) -> None:
        if not isinstance(self.calendar, CnAShareFrozenCalendar):
            raise TypeError("calendar must be CnAShareFrozenCalendar")

    @property
    def component_ref(self) -> ProfileComponentRef:
        session_ref = CnAShareCashSessionModel(self.calendar).component_ref
        return ProfileComponentRef(
            port_type=ProfilePortType.SETTLEMENT_MODEL,
            component_key=_COMPONENT_KEY,
            component_version=1,
            component_digest=canonical_sha256(
                {
                    "type": "cn_a_share_cash_settlement_component",
                    "schema_version": 1,
                    "component_key": _COMPONENT_KEY,
                    "component_version": 1,
                    "algorithm_key": _ALGORITHM_KEY,
                    "session_component_ref": session_ref,
                    "applicability_key": _APPLICABILITY_KEY,
                    "leg_timing": {
                        "negative_delivery": "fill-execution-time",
                        "positive_position": "next-trading-date-local-00:00",
                        "positive_cash": "next-trading-date-local-16:00",
                    },
                    "availability_policy": _availability_policy_payload(),
                }
            ),
        )

    def resolve_settlement(
        self, query: CnAShareSettlementQuery, /
    ) -> ProfilePortOutcome[
        CnAShareSettlementResolution,
        CnAShareSettlementFailure,
    ]:
        if not isinstance(query, CnAShareSettlementQuery):
            raise TypeError("query must be CnAShareSettlementQuery")
        fill = query.fill
        failure: tuple[CnAShareSettlementFailureCode, str] | None = None
        if fill.venue_id != self.calendar.venue_id:
            failure = (
                CnAShareSettlementFailureCode.UNSUPPORTED_VENUE,
                fill.venue_id.value,
            )
        elif (
            query.instrument.instrument_id != fill.instrument_id
            or query.instrument.instrument_id.venue != fill.venue_id
            or query.instrument.instrument_type is not InstrumentType.EQUITY
        ):
            failure = (
                CnAShareSettlementFailureCode.UNSUPPORTED_INSTRUMENT,
                fill.fill_id.value,
            )
        elif (
            query.instrument.quote_currency != _CNY
            or query.instrument.settlement_currency != _CNY
            or fill.price.quote_currency != _CNY.value
        ):
            failure = (
                CnAShareSettlementFailureCode.UNSUPPORTED_CURRENCY,
                fill.fill_id.value,
            )
        elif (
            query.cash_obligation_id.kind is not DomainIdKind.SETTLEMENT
            or query.position_obligation_id.kind is not DomainIdKind.SETTLEMENT
            or query.cash_obligation_id == query.position_obligation_id
        ):
            failure = (
                CnAShareSettlementFailureCode.SETTLEMENT_IDENTITY_MISMATCH,
                fill.fill_id.value,
            )
        effects = _accounting_effects(query) if failure is None else None
        if failure is None and effects is None:
            failure = (
                CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH,
                query.fill_accounting_entry.journal_entry_id.value,
            )
        if failure is not None:
            return self._failure(query, *failure)

        session = CnAShareCashSessionModel(self.calendar).resolve_session(
            CnAShareSessionQuery(fill.venue_id, fill.execution_time)
        )
        if session.failure is not None:
            if session.failure.code is not CnAShareSessionFailureCode.CALENDAR_COVERAGE_MISSING:
                raise RuntimeError("validated settlement venue failed session lookup")
            return self._failure(
                query,
                CnAShareSettlementFailureCode.CALENDAR_COVERAGE_MISSING,
                fill.fill_id.value,
            )
        session_result = session.result
        if session_result is None:  # pragma: no cover - exactly-one port contract
            raise RuntimeError("session outcome has no branch")
        next_day = next(
            (
                value
                for value in self.calendar.days
                if value.local_date > session_result.local_date
                and value.kind is CnAShareCalendarDayKind.TRADING
            ),
            None,
        )
        if next_day is None:
            return self._failure(
                query,
                CnAShareSettlementFailureCode.CALENDAR_COVERAGE_MISSING,
                fill.fill_id.value,
            )
        if not session_result.is_open or session_result.trading_date is None:
            return self._failure(
                query,
                CnAShareSettlementFailureCode.TRADE_TIME_NOT_OPEN,
                fill.fill_id.value,
            )
        if effects is None:  # pragma: no cover - guarded above
            raise RuntimeError("validated accounting effects are missing")
        cash_key, cash_value, position_key, position_value = effects
        position_time = _local_boundary(next_day.local_date, 0)
        cash_time = _local_boundary(next_day.local_date, 16)
        cash_settlement_time = (
            fill.execution_time if cash_value.units < 0 else cash_time
        )
        position_settlement_time = (
            fill.execution_time if position_value.units < 0 else position_time
        )
        obligations = (
            AccountSettlementObligation(
                SettlementObligation(
                    settlement_obligation_id=query.cash_obligation_id,
                    source_fill_id=fill.fill_id,
                    trade_time=fill.execution_time,
                    settlement_time=cash_settlement_time,
                    instrument_id=None,
                    quantity=None,
                    currency_id=cash_key.currency_id,
                    amount=cash_value,
                ),
                cash_key,
            ),
            AccountSettlementObligation(
                SettlementObligation(
                    settlement_obligation_id=query.position_obligation_id,
                    source_fill_id=fill.fill_id,
                    trade_time=fill.execution_time,
                    settlement_time=position_settlement_time,
                    instrument_id=position_key.instrument_id,
                    quantity=position_value,
                    currency_id=None,
                    amount=None,
                ),
                position_key,
            ),
        )
        result = CnAShareSettlementResolution(
            venue_id=fill.venue_id,
            fill_id=fill.fill_id,
            trade_date=session_result.trading_date,
            next_trading_date=TradingDate(
                self.calendar.calendar_id,
                next_day.local_date,
            ),
            position_availability_time=position_time,
            cash_withdrawal_time=cash_time,
            fill_accounting_entry_hash=canonical_sha256(
                query.fill_accounting_entry
            ),
            obligations=obligations,
        )
        return ProfilePortOutcome.for_result(self.component_ref, query, result)

    def availability_rules(self, schema: LedgerSchema) -> MarketSettlementRules:
        if not isinstance(schema, LedgerSchema):
            raise TypeError("schema must be LedgerSchema")
        registrations = schema.registrations
        accounts = {value.key.account_id for value in registrations}
        if len(accounts) != 1:
            raise AvailabilityEvidenceError(
                "A-share cash availability requires exactly one Account"
            )
        if any(
            value.key.venue_id != self.calendar.venue_id
            for value in registrations
        ):
            raise AvailabilityEvidenceError(
                "A-share cash availability Venue mismatch"
            )
        cash_keys = tuple(
            cast(CashBalanceKey, value.key)
            for value in registrations
            if isinstance(value.key, CashBalanceKey)
        )
        position_keys = tuple(
            cast(PositionBalanceKey, value.key)
            for value in registrations
            if isinstance(value.key, PositionBalanceKey)
        )
        if (
            not cash_keys
            or not position_keys
            or any(value.currency_id != _CNY for value in cash_keys)
        ):
            raise AvailabilityEvidenceError(
                "A-share cash availability requires CNY Cash and Position"
            )
        account_id = next(iter(accounts))
        return MarketSettlementRules.create(
            policy_key=_POLICY_KEY,
            policy_version=1,
            account_id=account_id,
            cash_rules=tuple(
                CashAvailabilityRule(
                    key=value,
                    pending_receivable_tradable=True,
                    pending_receivable_withdrawable=False,
                    pending_receivable_margin_eligible=False,
                    tradable_reservation_uses=(
                        CashReservationUse.CASH,
                        CashReservationUse.FEE_RESERVE,
                    ),
                    withdrawable_reservation_uses=(
                        CashReservationUse.CASH,
                        CashReservationUse.FEE_RESERVE,
                    ),
                    available_margin_reservation_uses=(),
                )
                for value in cash_keys
            ),
            position_rules=tuple(
                PositionAvailabilityRule(
                    key=value,
                    pending_receivable_sellable=False,
                )
                for value in position_keys
            ),
        )

    def _failure(
        self,
        query: CnAShareSettlementQuery,
        code: CnAShareSettlementFailureCode,
        subject_key: str,
    ) -> ProfilePortOutcome[
        CnAShareSettlementResolution,
        CnAShareSettlementFailure,
    ]:
        return ProfilePortOutcome.for_failure(
            self.component_ref,
            query,
            CnAShareSettlementFailure(
                code=code,
                fill_id=query.fill.fill_id,
                venue_id=query.fill.venue_id,
                calendar_id=self.calendar.calendar_id,
                subject_key=subject_key,
            ),
        )
