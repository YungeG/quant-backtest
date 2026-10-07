"""Retained October closes -> native daily account snapshots, diagnostic only.

No standard completion/owner-log publication, provider-time/revision, historical
status/fee authority or Validation eligibility is granted. Returned dividend
rows are an ex-post rejection guard, not proof of absence or entitlement.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    AccountingEntryType, ArtifactEnvelope, ArtifactReadResult, ArtifactRef, CurrencyId,
    Money, PortfolioSnapshot, PositionBalanceKey, Price, PricePurpose, Scale,
    SimulationInstant, SourceSequence, TimelinePhase, UtcInstant,
    canonical_bytes, canonical_sha256,
)
from crypto_quant_trading import (
    GenericLedger, PortfolioSnapshotProjector, ResolvedMark, SettlementBook,
    SettlementBookState, CurrencyValuationGraph,
)
from crypto_quant_trading.profiles.cn_a_share import CnAShareCalendarDayKind

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_daily_nav_draft_v0 import (
    DraftDailyCloseEquityV0, DraftPortfolioDailyNavMetricsV0,
    derive_draft_cn_portfolio_daily_nav_v0,
)
from .cn_a_share_portfolio_engine_case_v3 import CnASharePortfolioEngineDevelopmentResultV3
from .cn_a_share_portfolio_engine_diagnostic_prepare_v1 import _unique
from .cn_a_share_portfolio_engine_result_source_v3 import read_cn_a_share_portfolio_engine_development_result_source_v3
from .cn_a_share_portfolio_settlement_development_v1 import CnASharePortfolioSettlementDevelopmentV1
from .cn_a_share_portfolio_true_date_diagnostic_prepare_v1 import PreparedCnAShareTrueDateDiagnosticV1

_TZ = ZoneInfo("Asia/Shanghai")
_CENT = Scale(2)
_CNY = CurrencyId("CNY")
_DAILY = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"]
_DIVIDEND = ["ts_code", "end_date", "ann_date", "div_proc", "stk_div", "stk_bo_rate", "stk_co_rate",
             "cash_div", "cash_div_tax", "record_date", "ex_date", "pay_date", "div_listdate", "imp_ann_date"]


def _nonfinite(value: str):
    raise ValueError("retained observation cannot contain nonfinite JSON")


def _rows(raw: bytes, digest: str, fields: list[str]) -> tuple[list, ...]:
    if (type(raw) is not bytes or not raw or len(raw) > 2 * 1024 * 1024
            or digest != "sha256:" + hashlib.sha256(raw).hexdigest()):
        raise ValueError("retained observation bytes/hash mismatch")
    obj = json.loads(raw, parse_float=Decimal, parse_constant=_nonfinite, object_pairs_hook=_unique)
    if (type(obj) is not dict or type(obj.get("code")) is not int or obj["code"] != 0
            or type(obj.get("data")) is not dict or obj["data"].get("fields") != fields
            or type(obj["data"].get("items")) is not list or len(obj["data"]["items"]) > 6000):
        raise ValueError("retained observation business/schema mismatch")
    rows = obj["data"]["items"]
    if any(type(row) is not list or len(row) != len(fields) for row in rows):
        raise ValueError("retained observation malformed row")
    return tuple(rows)


def _date(value: str) -> date:
    if type(value) is not str or len(value) != 8 or not value.isascii() or not value.isdigit():
        raise ValueError("retained observation date must be YYYYMMDD")
    return date(int(value[:4]), int(value[4:6]), int(value[6:]))


def _eod(day: date) -> UtcInstant:
    return UtcInstant.from_datetime(datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=_TZ))


@dataclass(frozen=True, slots=True)
class CnAShareRetainedDailyCloseV1:
    response_bytes: bytes
    response_sha256: str
    trade_date: str

    def __post_init__(self) -> None:
        _date(self.trade_date)
        self.prices()

    def prices(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in _rows(self.response_bytes, self.response_sha256, _DAILY):
            code, day, close = row[0], row[1], row[5]
            if type(code) is not str or code in out or day != self.trade_date or type(close) not in (str, int, Decimal):
                raise ValueError("retained close duplicate/subject/date/price mismatch")
            value = Decimal(close) * 100
            if not value.is_finite() or value <= 0 or value != value.to_integral_value():
                raise ValueError("retained close requires positive exact CNY cents")
            out[code] = int(value)
        if not out:
            raise ValueError("retained daily close cannot be empty")
        return out

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_retained_daily_close", "schema_version": 1,
                "response_hex": self.response_bytes.hex(), "response_sha256": self.response_sha256,
                "trade_date": self.trade_date, "provider_available_at": None, "provider_revision_id": None}


@dataclass(frozen=True, slots=True)
class CnAShareRetainedDividendGuardV1:
    response_bytes: bytes
    response_sha256: str
    ts_code: str

    def __post_init__(self) -> None:
        if type(self.ts_code) is not str or len(self.ts_code) != 9 or self.ts_code[-3:] not in (".SH", ".SZ"):
            raise ValueError("retained dividend guard stock malformed")
        self.rows()

    def rows(self) -> tuple[list, ...]:
        rows = _rows(self.response_bytes, self.response_sha256, _DIVIDEND)
        for row in rows:
            if row[0] != self.ts_code:
                raise ValueError("retained dividend guard foreign stock")
            for value in row[9:13]:
                if value not in (None, ""):
                    _date(value)
        return rows

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_retained_dividend_guard", "schema_version": 1,
                "response_hex": self.response_bytes.hex(), "response_sha256": self.response_sha256,
                "ts_code": self.ts_code, "absence_verified": False,
                "provider_available_at": None, "provider_revision_id": None}


def _code(instrument) -> str:
    return instrument.stable_key + (".SH" if instrument.venue.value == "xshg" else ".SZ")


def _input(prepared: PreparedCnAShareTrueDateDiagnosticV1,
           closes: tuple[CnAShareRetainedDailyCloseV1, ...],
           dividends: tuple[CnAShareRetainedDividendGuardV1, ...],
           end_exclusive: date) -> ArtifactEnvelope:
    if type(prepared) is not PreparedCnAShareTrueDateDiagnosticV1 or type(end_exclusive) is not date:
        raise TypeError("daily NAV diagnostic requires exact true-date preparation and date")
    prepared._verify()
    if any(entry.recorded_at.instant >= prepared.case.target_events[0].event_time
           for entry in prepared.case.initial_journal.entries):
        raise ValueError("daily NAV initial funding must precede first decision")
    start = min(bar.event_time.to_datetime().astimezone(_TZ).date() for bar in prepared.case.first_bars)
    calendars = tuple(c.calendar() for c in prepared.calendar_conditions)
    if not start < end_exclusive <= min(c.coverage_end_exclusive for c in calendars):
        raise ValueError("daily NAV diagnostic window outside frozen calendar")
    sequences = tuple(tuple(day.local_date for day in c.days if start <= day.local_date < end_exclusive
                            and day.kind is CnAShareCalendarDayKind.TRADING) for c in calendars)
    if (not sequences[0] or sequences[0] != sequences[1] or type(closes) is not tuple
            or any(type(c) is not CnAShareRetainedDailyCloseV1 for c in closes)
            or tuple(_date(c.trade_date) for c in closes) != sequences[0]):
        raise ValueError("daily closes must exact-cover both venue calendars in order")
    codes = tuple(_code(i) for i in prepared.case.source.scope.instrument_ids)
    if (type(dividends) is not tuple or any(type(c) is not CnAShareRetainedDividendGuardV1 for c in dividends)
            or tuple(c.ts_code for c in dividends) != codes):
        raise ValueError("daily NAV dividend guard must exact-cover frozen stock order")
    for close in closes:
        prices = close.prices()
        if any(code not in prices for code in codes):
            raise ValueError("daily close missing frozen stock; no zero/forward fill")
        for opening in prepared.open_conditions:
            if opening.trade_date == close.trade_date and opening.response_bytes != close.response_bytes:
                raise ValueError("daily close/open must share exact retained response")
    for condition in dividends:
        condition.rows()
    return ArtifactEnvelope.create("cn_a_share_portfolio_daily_nav_diagnostic_input", 1,
        {"true_date_input_ref": prepared.input_ref, "closes": closes, "dividend_guards": dividends,
         "end_exclusive": end_exclusive.isoformat(), "modeled_close_at": "23:59:59 Asia/Shanghai",
         "diagnostic_only": True, "source_qualification_verified": False,
         "formal_publication_eligible": False, "validation_eligible": False, "trade_authorized": False})


def _read(ref: ArtifactRef, envelope: ArtifactEnvelope, reader: ArtifactEnvelopeReader) -> ArtifactReadResult:
    result = reader.read(ref=ref)
    if (type(result) is not ArtifactReadResult or ref != ArtifactRef.from_envelope(envelope)
            or result.envelope != envelope or result.source_bytes != canonical_bytes(envelope)
            or result.source_hash != canonical_sha256(envelope)):
        raise ValueError("daily NAV retained artifact exact readback mismatch")
    return result


def _reject_unmodeled_dividends_v1(*, journal, schema, account, instruments, guards,
                                    start: date, end_exclusive: date) -> None:
    """Pure native-journal entitlement guard; callers own later valuation/publication."""
    ledger = GenericLedger(schema)
    for instrument, guard in zip(instruments, guards, strict=True):
        key = PositionBalanceKey(account, instrument.venue, instrument)
        for row in guard.rows():
            dates = tuple(_date(value) for value in row[9:13] if value not in (None, ""))
            if not any(start <= day < end_exclusive for day in dates):
                continue
            record = _date(row[9]) if row[9] not in (None, "") else min(dates)
            if record >= end_exclusive:
                continue
            stop = sum(entry.recorded_at.instant <= _eod(record) for entry in journal.entries)
            state = ledger.project(journal, stop=journal.cursor_at(stop))
            if state.position_quantity(key).units:
                raise ValueError("daily NAV unmodeled corporate action on retained inventory")

@dataclass(frozen=True, slots=True)
class CnASharePortfolioCloseDayDiagnosticV1:
    trade_date: str
    snapshot: PortfolioSnapshot
    journal_prefix_hash: str
    settlement_state: SettlementBookState
    close_source_hash: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_close_day_diagnostic", "schema_version": 1,
                "trade_date": self.trade_date, "snapshot": self.snapshot,
                "journal_prefix_hash": self.journal_prefix_hash, "settlement_state": self.settlement_state,
                "close_source_hash": self.close_source_hash, "diagnostic_only": True,
                "provider_available_at": None, "provider_revision_id": None}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioDailyNavDiagnosticV1:
    input_ref: ArtifactRef
    native_result_ref: ArtifactRef
    account_id: str
    days: tuple[CnASharePortfolioCloseDayDiagnosticV1, ...]
    draft_metrics: DraftPortfolioDailyNavMetricsV0
    source_qualification_verified: bool = field(default=False, init=False)
    formal_publication_eligible: bool = field(default=False, init=False)
    validation_eligible: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_daily_nav_diagnostic", "schema_version": 1,
                "input_ref": self.input_ref, "native_result_ref": self.native_result_ref,
                "account_id": self.account_id, "days": self.days, "draft_metrics": self.draft_metrics,
                "source_qualification_verified": False, "formal_publication_eligible": False,
                "validation_eligible": False, "trade_authorized": False}


def _derive_native_daily_nav_diagnostic_v1(
    *, scope, initial_journal, journal, settlement, batches, notional_quantization,
    closes: tuple[CnAShareRetainedDailyCloseV1, ...],
    dividend_guards: tuple[CnAShareRetainedDividendGuardV1, ...], end_exclusive: date,
    input_ref: ArtifactRef, native_ref: ArtifactRef,
) -> CnASharePortfolioDailyNavDiagnosticV1:
    """Pure native daily projection; callers verify/retain their exact execution sources."""
    if any(entry.entry_type in (AccountingEntryType.CAPITAL_DEPOSITED, AccountingEntryType.CAPITAL_WITHDRAWN)
           for entry in journal.entries[initial_journal.entry_count:]):
        raise ValueError("daily NAV rejects external cash flows after initial funding")
    account = scope.account_id
    ledger = GenericLedger(scope.ledger_schema)
    start = _date(closes[0].trade_date)
    _reject_unmodeled_dividends_v1(journal=journal, schema=scope.ledger_schema, account=account,
        instruments=scope.instrument_ids, guards=dividend_guards,
        start=start, end_exclusive=end_exclusive)
    days = []
    observations = []
    for close in closes:
        day = _date(close.trade_date)
        at = _eod(day)
        instant = SimulationInstant(at, TimelinePhase(90, "conditional_daily_close"), SourceSequence(1))
        stop = sum(entry.recorded_at <= instant for entry in journal.entries)
        state = ledger.project(journal, stop=journal.cursor_at(stop))
        event_stop = sum(event.occurred_at <= instant for event in settlement.book.events)
        events = settlement.book.events[:event_stop]
        ids = {event.settlement_obligation_id for event in events}
        book = SettlementBook.from_events(account,
            tuple(ob for ob in settlement.book.obligations if ob.obligation.settlement_obligation_id in ids), events)
        due = CnASharePortfolioSettlementDevelopmentV1(
            settlement.financial_batch_hash, settlement.calendar_hashes, book).apply_due(at)
        prices = close.prices()
        marks = tuple(ResolvedMark(
            instrument_id=i, quote_currency_id=_CNY, price_purpose=PricePurpose.VALUATION,
            price=Price(prices[_code(i)], _CENT, str(i), "CNY"), observed_at=at,
            available_at=at, resolved_at=at, age_nanoseconds=0,
            stream_id="conditional.retained.daily.close", source_event_id=close.response_sha256 + "/" + _code(i),
            revision_id="modeled.not-provider:" + close.response_sha256,
            stale_policy_key="conditional.same-day.close", stale_policy_version=1,
            stale_policy_hash=canonical_sha256({"policy": "conditional.same-day.close", "schema_version": 1}),
            available_at_instant=instant, resolved_at_instant=instant)
            for i in scope.instrument_ids)
        projected = PortfolioSnapshotProjector().project_cash_ledger(
            ledger_state=state, resolved_marks=marks, reporting_currency=_CNY,
            reporting_scale=_CENT, projection_at=instant, instrument_catalog=scope.instrument_catalog,
            currency_valuation_graph=CurrencyValuationGraph(at, PricePurpose.VALUATION, ()),
            notional_quantization=notional_quantization)
        if projected.snapshot is None:
            raise ValueError("daily NAV native snapshot projection failed: " + str(projected.failure))
        snapshot = projected.snapshot
        fees = tuple(f for b in batches if b is not None
                     for f in b.fee_assessments if f.assessment_time <= at)
        days.append(CnASharePortfolioCloseDayDiagnosticV1(day.isoformat(), snapshot,
            state.cursor.prefix_hash, due.book.project(), close.response_sha256))
        observations.append(DraftDailyCloseEquityV0(day.isoformat(), snapshot.equity,
            Money(0, _CENT, "CNY"), state.state_hash, close.response_sha256,
            canonical_sha256(fees), canonical_sha256(dividend_guards),
            canonical_sha256({"diagnostic_native_result_ref": native_ref, "not_owner_log": True})))
    metrics = derive_draft_cn_portfolio_daily_nav_v0(
        initial_equity=scope.initial_cash,
        expected_trading_dates=tuple(day.trade_date for day in days), observations=tuple(observations))
    return CnASharePortfolioDailyNavDiagnosticV1(input_ref, native_ref, account, tuple(days), metrics)

@dataclass(frozen=True, slots=True)
class PreparedCnASharePortfolioDailyNavDiagnosticV1:
    prepared: PreparedCnAShareTrueDateDiagnosticV1
    closes: tuple[CnAShareRetainedDailyCloseV1, ...]
    dividend_guards: tuple[CnAShareRetainedDividendGuardV1, ...]
    end_exclusive: date
    input_ref: ArtifactRef
    artifact_reader: ArtifactEnvelopeReader
    artifact_publisher: ArtifactEnvelopePublisher

    def _verify(self) -> None:
        envelope = _input(self.prepared, self.closes, self.dividend_guards, self.end_exclusive)
        _read(self.input_ref, envelope, self.artifact_reader)

    def __post_init__(self) -> None:
        self._verify()

    def run(self) -> CnASharePortfolioDailyNavDiagnosticV1:
        self._verify()
        outcome = self.prepared.run()
        native = outcome.portfolio_result_v3
        if outcome.engine_failure is not None or type(native) is not CnASharePortfolioEngineDevelopmentResultV3:
            raise ValueError("daily NAV native execution did not return paired result")
        envelope = ArtifactEnvelope.create("cn_a_share_portfolio_daily_nav_native_source", 1, {"result": native})
        native_ref = ArtifactRef.from_envelope(envelope)
        if self.artifact_publisher.put(envelope=envelope) != native_ref:
            raise ValueError("daily NAV native publisher returned wrong ref")
        retained = _read(native_ref, envelope, self.artifact_reader)
        case = self.prepared.case
        result = read_cn_a_share_portfolio_engine_development_result_source_v3(
            retained.envelope.payload["result"], ledger_schema=case.ledger_schema)
        if result != native or result.case_hash != case.case_hash or result.source_ref != case.source_ref:
            raise ValueError("daily NAV native case/result mismatch")
        batch = result.second_batch or result.first_batch
        settlement = result.matured_first_settlement
        if result.second_settlement is not None:
            second = result.second_settlement
            settlement = CnASharePortfolioSettlementDevelopmentV1(
                second.financial_batch_hash, second.calendar_hashes,
                settlement.book.append(obligations=second.book.obligations, events=second.book.events))
        return _derive_native_daily_nav_diagnostic_v1(
            scope=case.source.scope, initial_journal=case.initial_journal,
            journal=batch.journal, settlement=settlement,
            batches=(result.first_batch, result.second_batch), notional_quantization=case.notional_quantization,
            closes=self.closes, dividend_guards=self.dividend_guards, end_exclusive=self.end_exclusive,
            input_ref=self.input_ref, native_ref=native_ref)


def prepare_cn_a_share_portfolio_daily_nav_diagnostic_v1(
    *, prepared: PreparedCnAShareTrueDateDiagnosticV1,
    closes: tuple[CnAShareRetainedDailyCloseV1, ...],
    dividend_guards: tuple[CnAShareRetainedDividendGuardV1, ...], end_exclusive: date,
    artifact_reader: ArtifactEnvelopeReader, artifact_publisher: ArtifactEnvelopePublisher,
) -> PreparedCnASharePortfolioDailyNavDiagnosticV1:
    """Retain complete daily sources, then derive only unqualified native diagnostics."""
    envelope = _input(prepared, closes, dividend_guards, end_exclusive)
    ref = ArtifactRef.from_envelope(envelope)
    if artifact_publisher.put(envelope=envelope) != ref:
        raise ValueError("daily NAV input publisher returned wrong ref")
    return PreparedCnASharePortfolioDailyNavDiagnosticV1(
        prepared, closes, dividend_guards, end_exclusive, ref, artifact_reader, artifact_publisher)
