from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .canonical import canonical_bytes, canonical_sha256
from .identity import DomainId, DomainIdKind, require_canonical_text
from .instruments import CurrencyId, InstrumentId, VenueId
from .numeric import Money, Price, Quantity
from .time import SimulationInstant, UtcInstant


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _require_text(name: str, value: str) -> None:
    require_canonical_text(name, value)
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 content hash")


def _require_money_tuple(name: str, values: tuple[Money, ...]) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple")
    if not all(isinstance(value, Money) for value in values):
        raise TypeError(f"{name} must contain Money")
    currencies = [value.currency for value in values]
    if len(set(currencies)) != len(currencies):
        raise ValueError(f"duplicate {name} currency")
    if any(value.units == 0 for value in values):
        raise ValueError(f"{name} entries must be non-zero")


def _canonical_money(values: tuple[Money, ...]) -> list[Money]:
    return sorted(values, key=canonical_bytes)


class PricePurpose(str, Enum):
    EXECUTION_REFERENCE = "execution_reference"
    VALUATION = "valuation"
    MARGIN = "margin"
    LIQUIDATION = "liquidation"
    SETTLEMENT = "settlement"
    FUNDING = "funding"


class AccountingEntryType(str, Enum):
    CAPITAL_DEPOSITED = "capital_deposited"
    CAPITAL_WITHDRAWN = "capital_withdrawn"
    CAPITAL_TRANSFERRED = "capital_transferred"
    FILL_BOOKED = "fill_booked"
    FEE_CHARGED = "fee_charged"
    FUNDING_APPLIED = "funding_applied"
    BORROW_FEE_CHARGED = "borrow_fee_charged"
    SETTLEMENT_APPLIED = "settlement_applied"
    CORPORATE_ACTION_ENTITLEMENT_BOOKED = "corporate_action_entitlement_booked"
    CORPORATE_ACTION_POSITION_ADJUSTED = "corporate_action_position_adjusted"
    CORPORATE_ACTION_CASH_PAID = "corporate_action_cash_paid"
    LIQUIDATION_APPLIED = "liquidation_applied"


@dataclass(frozen=True, slots=True, order=True)
class CashBalanceKey:
    account_id: str
    venue_id: VenueId
    currency_id: CurrencyId

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.currency_id, CurrencyId):
            raise TypeError("currency_id must be CurrencyId")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cash_balance_key",
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "currency_id": self.currency_id,
        }


@dataclass(frozen=True, slots=True, order=True)
class PositionBalanceKey:
    account_id: str
    venue_id: VenueId
    instrument_id: InstrumentId

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if self.instrument_id.venue != self.venue_id:
            raise ValueError("PositionBalanceKey Instrument Venue mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_balance_key",
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
        }


@dataclass(frozen=True, slots=True)
class BalanceChange:
    key: CashBalanceKey | PositionBalanceKey
    value: Money | Quantity

    def __post_init__(self) -> None:
        if isinstance(self.key, CashBalanceKey):
            if not isinstance(self.value, Money):
                raise TypeError("CashBalanceKey requires Money value")
            if self.value.currency != str(self.key.currency_id):
                raise ValueError("Cash balance currency identity mismatch")
        elif isinstance(self.key, PositionBalanceKey):
            if not isinstance(self.value, Quantity):
                raise TypeError("PositionBalanceKey requires Quantity value")
            if self.value.instrument_id != str(self.key.instrument_id):
                raise ValueError("Position balance instrument identity mismatch")
        else:
            raise TypeError("key must be CashBalanceKey or PositionBalanceKey")
        if self.value.units == 0:
            raise ValueError("BalanceChange must be non-zero")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "balance_change", "key": self.key, "value": self.value}


@dataclass(frozen=True, slots=True)
class PositionLot:
    lot_id: str
    position_key: PositionBalanceKey
    source_id: str
    quantity: Quantity
    unit_cost: Price | None
    allocated_fees: tuple[Money, ...]
    opened_at: UtcInstant

    def __post_init__(self) -> None:
        _require_text("lot_id", self.lot_id)
        if not isinstance(self.position_key, PositionBalanceKey):
            raise TypeError("position_key must be PositionBalanceKey")
        _require_text("source_id", self.source_id)
        if not isinstance(self.quantity, Quantity):
            raise TypeError("quantity must be Quantity")
        if self.quantity.units == 0:
            raise ValueError("PositionLot quantity must be non-zero")
        if self.quantity.instrument_id != str(self.position_key.instrument_id):
            raise ValueError("PositionLot quantity instrument identity mismatch")
        if self.unit_cost is not None:
            if not isinstance(self.unit_cost, Price):
                raise TypeError("unit_cost must be Price or None")
            if self.unit_cost.units <= 0:
                raise ValueError("PositionLot unit cost must be positive")
            if self.unit_cost.instrument_id != str(self.position_key.instrument_id):
                raise ValueError("PositionLot unit cost instrument identity mismatch")
        _require_money_tuple("allocated fee", self.allocated_fees)
        if not isinstance(self.opened_at, UtcInstant):
            raise TypeError("opened_at must be UtcInstant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_lot",
            "lot_id": self.lot_id,
            "position_key": self.position_key,
            "source_id": self.source_id,
            "quantity": self.quantity,
            "unit_cost": self.unit_cost,
            "allocated_fees": _canonical_money(self.allocated_fees),
            "opened_at": self.opened_at,
        }


@dataclass(frozen=True, slots=True)
class CashBalance:
    key: CashBalanceKey
    amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.key, CashBalanceKey):
            raise TypeError("key must be CashBalanceKey")
        if not isinstance(self.amount, Money):
            raise TypeError("amount must be Money")
        if self.amount.currency != str(self.key.currency_id):
            raise ValueError("CashBalance currency identity mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "cash_balance", "key": self.key, "amount": self.amount}


@dataclass(frozen=True, slots=True)
class PositionBalance:
    key: PositionBalanceKey
    quantity: Quantity
    lots: tuple[PositionLot, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.key, PositionBalanceKey):
            raise TypeError("key must be PositionBalanceKey")
        if not isinstance(self.quantity, Quantity):
            raise TypeError("quantity must be Quantity")
        if self.quantity.units == 0:
            raise ValueError("PositionBalance quantity must be non-zero")
        if self.quantity.instrument_id != str(self.key.instrument_id):
            raise ValueError("PositionBalance quantity instrument identity mismatch")
        if not isinstance(self.lots, tuple):
            raise TypeError("lots must be a tuple")
        if not all(isinstance(value, PositionLot) for value in self.lots):
            raise TypeError("lots must contain PositionLot")
        lot_ids = [value.lot_id for value in self.lots]
        if len(set(lot_ids)) != len(lot_ids):
            raise ValueError("duplicate lot in PositionBalance")
        if self.lots:
            if any(value.position_key != self.key for value in self.lots):
                raise ValueError("PositionBalance lot key mismatch")
            if any(value.quantity.scale != self.quantity.scale for value in self.lots):
                raise ValueError("PositionBalance lot quantity scale mismatch")
            if sum(value.quantity.units for value in self.lots) != self.quantity.units:
                raise ValueError("PositionBalance requires exact lot total")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_balance",
            "key": self.key,
            "quantity": self.quantity,
            "lots": sorted(self.lots, key=canonical_bytes),
        }


@dataclass(frozen=True, slots=True)
class ValuationMarkReference:
    mark_id: str
    instrument_id: InstrumentId
    price_purpose: PricePurpose
    observed_at: UtcInstant

    def __post_init__(self) -> None:
        _require_text("mark_id", self.mark_id)
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.price_purpose, PricePurpose):
            raise TypeError("price_purpose must be PricePurpose")
        if not isinstance(self.observed_at, UtcInstant):
            raise TypeError("observed_at must be UtcInstant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "valuation_mark_reference",
            "mark_id": self.mark_id,
            "instrument_id": self.instrument_id,
            "price_purpose": self.price_purpose.value,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class AccountingJournalEntry:
    journal_entry_id: DomainId
    entry_type: AccountingEntryType
    account_id: str
    venue_id: VenueId
    effective_time: UtcInstant
    recorded_at: SimulationInstant
    source_ids: tuple[str, ...]
    balance_changes: tuple[BalanceChange, ...]
    realized_pnl: tuple[Money, ...]
    fees: tuple[Money, ...]
    financing: tuple[Money, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.journal_entry_id, DomainId):
            raise TypeError("journal_entry_id must be DomainId")
        if self.journal_entry_id.kind is not DomainIdKind.JOURNAL:
            raise ValueError("journal_entry_id must use DomainIdKind.JOURNAL")
        if not isinstance(self.entry_type, AccountingEntryType):
            raise TypeError("entry_type must be AccountingEntryType")
        _require_text("account_id", self.account_id)
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.effective_time, UtcInstant):
            raise TypeError("effective_time must be UtcInstant")
        if not isinstance(self.recorded_at, SimulationInstant):
            raise TypeError("recorded_at must be SimulationInstant")
        if self.effective_time > self.recorded_at.instant:
            raise ValueError("effective_time cannot be after recorded_at")
        if not isinstance(self.source_ids, tuple) or not self.source_ids:
            raise ValueError("source_ids must be a non-empty tuple")
        for source_id in self.source_ids:
            _require_text("source_id", source_id)
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("duplicate source identity")
        if not isinstance(self.balance_changes, tuple):
            raise TypeError("balance_changes must be a tuple")
        if not all(isinstance(value, BalanceChange) for value in self.balance_changes):
            raise TypeError("balance_changes must contain BalanceChange")
        keys = [canonical_bytes(value.key) for value in self.balance_changes]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate balance change")
        for change in self.balance_changes:
            if change.key.account_id != self.account_id:
                raise ValueError("Journal balance account mismatch")
            if change.key.venue_id != self.venue_id:
                raise ValueError("Journal balance Venue mismatch")
        _require_money_tuple("realized_pnl", self.realized_pnl)
        _require_money_tuple("fees", self.fees)
        _require_money_tuple("financing", self.financing)
        if (
            not self.balance_changes
            and not self.realized_pnl
            and not self.fees
            and not self.financing
            and self.entry_type
            is not AccountingEntryType.CORPORATE_ACTION_ENTITLEMENT_BOOKED
        ):
            raise ValueError("AccountingJournalEntry requires an economic effect")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "accounting_journal_entry",
            "journal_entry_id": self.journal_entry_id,
            "entry_type": self.entry_type.value,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "effective_time": self.effective_time,
            "recorded_at": self.recorded_at,
            "source_ids": sorted(self.source_ids),
            "balance_changes": sorted(self.balance_changes, key=canonical_bytes),
            "realized_pnl": _canonical_money(self.realized_pnl),
            "fees": _canonical_money(self.fees),
            "financing": _canonical_money(self.financing),
        }


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    account_id: str
    timestamp: UtcInstant
    reporting_currency: CurrencyId
    cash: tuple[CashBalance, ...]
    positions: tuple[PositionBalance, ...]
    realized_pnl: Money
    unrealized_pnl: Money
    fees: Money
    financing: Money
    equity: Money
    valuation_marks: tuple[ValuationMarkReference, ...]
    journal_state_hash: str
    valuation_mark_set_hash: str
    valuation_staleness_report_hash: str
    currency_valuation_graph_hash: str

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        if not isinstance(self.timestamp, UtcInstant):
            raise TypeError("timestamp must be UtcInstant")
        if not isinstance(self.reporting_currency, CurrencyId):
            raise TypeError("reporting_currency must be CurrencyId")
        if not isinstance(self.cash, tuple) or not all(
            isinstance(value, CashBalance) for value in self.cash
        ):
            raise TypeError("cash must be a tuple of CashBalance")
        if not isinstance(self.positions, tuple) or not all(
            isinstance(value, PositionBalance) for value in self.positions
        ):
            raise TypeError("positions must be a tuple of PositionBalance")
        cash_keys = [canonical_bytes(value.key) for value in self.cash]
        if len(set(cash_keys)) != len(cash_keys):
            raise ValueError("duplicate CashBalance")
        position_keys = [canonical_bytes(value.key) for value in self.positions]
        if len(set(position_keys)) != len(position_keys):
            raise ValueError("duplicate PositionBalance")
        if any(value.key.account_id != self.account_id for value in self.cash):
            raise ValueError("Snapshot CashBalance account mismatch")
        if any(value.key.account_id != self.account_id for value in self.positions):
            raise ValueError("Snapshot PositionBalance account mismatch")
        reporting_values = (
            self.realized_pnl,
            self.unrealized_pnl,
            self.fees,
            self.financing,
            self.equity,
        )
        if not all(isinstance(value, Money) for value in reporting_values):
            raise TypeError("Snapshot reporting values must be Money")
        reporting_currency = str(self.reporting_currency)
        if any(value.currency != reporting_currency for value in reporting_values):
            raise ValueError("Snapshot values must use Reporting Currency")
        if not isinstance(self.valuation_marks, tuple) or not all(
            isinstance(value, ValuationMarkReference)
            for value in self.valuation_marks
        ):
            raise TypeError(
                "valuation_marks must be a tuple of ValuationMarkReference"
            )
        mark_ids = [value.mark_id for value in self.valuation_marks]
        mark_keys = [
            (value.instrument_id, value.price_purpose)
            for value in self.valuation_marks
        ]
        if len(set(mark_ids)) != len(mark_ids) or len(set(mark_keys)) != len(mark_keys):
            raise ValueError("duplicate valuation mark")
        if any(value.observed_at > self.timestamp for value in self.valuation_marks):
            raise ValueError("future valuation mark is forbidden")
        for name, value in (
            ("journal_state_hash", self.journal_state_hash),
            ("valuation_mark_set_hash", self.valuation_mark_set_hash),
            (
                "valuation_staleness_report_hash",
                self.valuation_staleness_report_hash,
            ),
            ("currency_valuation_graph_hash", self.currency_valuation_graph_hash),
        ):
            _require_hash(name, value)
        sorted_marks = tuple(sorted(self.valuation_marks, key=canonical_bytes))
        if self.valuation_mark_set_hash != canonical_sha256(sorted_marks):
            raise ValueError("valuation mark-set hash mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_snapshot",
            "account_id": self.account_id,
            "timestamp": self.timestamp,
            "reporting_currency": self.reporting_currency,
            "cash": sorted(self.cash, key=canonical_bytes),
            "positions": sorted(self.positions, key=canonical_bytes),
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "fees": self.fees,
            "financing": self.financing,
            "equity": self.equity,
            "valuation_marks": sorted(self.valuation_marks, key=canonical_bytes),
            "journal_state_hash": self.journal_state_hash,
            "valuation_mark_set_hash": self.valuation_mark_set_hash,
            "valuation_staleness_report_hash": self.valuation_staleness_report_hash,
            "currency_valuation_graph_hash": self.currency_valuation_graph_hash,
        }
