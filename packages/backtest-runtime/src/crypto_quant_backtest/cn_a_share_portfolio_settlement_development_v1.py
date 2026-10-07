"""Development-only two-venue CN T+1 obligations from actual batch Fills.

No broker cash transfer, source-qualified calendar, published owner Journal,
public prepare or economic Backtest. SettlementBook is immutable and due
applications occur only at the requested real boundary, never backdated.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from crypto_quant_domain import (
    AccountingEntryType, CurrencyId, DomainId, DomainIdKind, Fill, SettlementObligation,
    InstrumentDefinition, InstrumentType, SimulationInstant, SourceSequence,
    TimelinePhase, UtcInstant, VenueId, canonical_bytes, canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal, AccountSettlementObligation, SettlementBook, SettlementEvent,
    SettlementEventType,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashSettlementModel, CnAShareFrozenCalendar,
    CnAShareSettlementQuery,
)
from .cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialBatchDevelopmentV1,
    CnASharePortfolioFinancialBatchDevelopmentV2, CnASharePortfolioFinancialBatchDevelopmentV3,
)


def _settlement_id(fill_id: DomainId, leg: str) -> DomainId:
    return DomainId(DomainIdKind.SETTLEMENT, f"{DomainIdKind.SETTLEMENT.prefix}_" +
                    canonical_sha256({"type": "cn_portfolio_development_settlement", "fill": fill_id,
                                      "leg": leg})[7:])


def _event_id(obligation: AccountSettlementObligation, phase: str) -> str:
    return "cn-portfolio-settlement-" + phase + ":" + canonical_sha256({
        "type": "cn_portfolio_development_settlement_event", "obligation": obligation,
        "phase": phase})


def _book_body(book: SettlementBook) -> dict[str, object]:
    return {"type": "cn_portfolio_development_settlement_book_source",
            "schema_version": 1, "account_id": book.account_id,
            "book_hash": book.book_hash,
            "obligations": book.obligations, "events": book.events}


def read_cn_a_share_portfolio_settlement_book_source_v1(source: object) -> SettlementBook:
    """Rebuild a native two-venue Book from its canonical source, never a balance hint."""
    from .execution_inputs import (
        _read_balance_key, _read_currency, _read_domain_id, _read_instrument_id,
        _read_money, _read_quantity, _read_simulation_instant, _read_utc,
    )

    def fields(value: object, expected: set[str], name: str) -> Mapping:
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError(f"portfolio settlement {name} source fields mismatch")
        return value

    data = fields(source, {"type", "schema_version", "account_id", "book_hash", "obligations", "events"}, "Book")
    if (data["type"] != "cn_portfolio_development_settlement_book_source"
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or not isinstance(data["obligations"], (tuple, list))
            or not isinstance(data["events"], (tuple, list))):
        raise ValueError("portfolio settlement source version or sequence mismatch")
    obligations: list[AccountSettlementObligation] = []
    for item in data["obligations"]:
        record = fields(item, {"type", "obligation", "balance_key"}, "account obligation")
        if record["type"] != "account_settlement_obligation":
            raise ValueError("portfolio account obligation tag mismatch")
        raw = fields(record["obligation"], {"type", "settlement_obligation_id", "source_fill_id",
                    "trade_time", "settlement_time", "instrument_id", "quantity", "currency_id", "amount"}, "obligation")
        if raw["type"] != "settlement_obligation":
            raise ValueError("portfolio settlement obligation tag mismatch")
        obligation = SettlementObligation(
            _read_domain_id(raw["settlement_obligation_id"]), _read_domain_id(raw["source_fill_id"]),
            _read_utc(raw["trade_time"]), _read_utc(raw["settlement_time"]),
            None if raw["instrument_id"] is None else _read_instrument_id(raw["instrument_id"]),
            None if raw["quantity"] is None else _read_quantity(raw["quantity"]),
            None if raw["currency_id"] is None else _read_currency(raw["currency_id"]),
            None if raw["amount"] is None else _read_money(raw["amount"]),
        )
        obligations.append(AccountSettlementObligation(obligation, _read_balance_key(record["balance_key"])))
    events: list[SettlementEvent] = []
    for item in data["events"]:
        raw = fields(item, {"type", "event_id", "settlement_obligation_id", "event_type",
                            "occurred_at", "causation_id", "source_evidence_hash"}, "event")
        if raw["type"] != "settlement_event":
            raise ValueError("portfolio settlement event tag mismatch")
        events.append(SettlementEvent(raw["event_id"], _read_domain_id(raw["settlement_obligation_id"]),
                                      SettlementEventType(raw["event_type"]),
                                      _read_simulation_instant(raw["occurred_at"]),
                                      raw["causation_id"], raw["source_evidence_hash"]))
    book = SettlementBook.from_events(data["account_id"], tuple(obligations), tuple(events))
    if data["book_hash"] != book.book_hash or canonical_bytes(data) != canonical_bytes(_book_body(book)):
        raise ValueError("portfolio settlement Book hash/source reconstruction mismatch")
    return book

@dataclass(frozen=True, slots=True)
class CnASharePortfolioSettlementDevelopmentV1:
    financial_batch_hash: str
    calendar_hashes: tuple[str, str]
    book: SettlementBook
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.book) is not SettlementBook or type(self.calendar_hashes) is not tuple
                or len(self.calendar_hashes) != 2
                or self.book != SettlementBook.from_events(
                    self.book.account_id, self.book.obligations, self.book.events)):
            raise ValueError("CN development settlement Book is not a replayable whole source")

    @property
    def settlement_hash(self) -> str:
        return canonical_sha256(self)

    def apply_due(self, at: UtcInstant) -> CnASharePortfolioSettlementDevelopmentV1:
        """Append only known due obligations at at; no future acceptance or backdating."""
        if type(at) is not UtcInstant:
            raise TypeError("due time must be UtcInstant")
        if self.book.events and at < self.book.events[-1].occurred_at.instant:
            raise ValueError("due application cannot precede published Settlement prefix")
        recorded = {event.settlement_obligation_id: event for event in self.book.events
                    if event.event_type is SettlementEventType.OBLIGATION_RECORDED}
        due = tuple(ob for ob in self.book.project().pending_obligations
                    if ob.obligation.settlement_time <= at)
        if not due:
            return self
        updates = tuple(SettlementEvent(
            event_id=_event_id(ob, "applied"),
            settlement_obligation_id=ob.obligation.settlement_obligation_id,
            event_type=SettlementEventType.SETTLEMENT_APPLIED,
            occurred_at=SimulationInstant(at, TimelinePhase(20, "settlement_due"),
                                          SourceSequence(index)),
            causation_id=recorded[ob.obligation.settlement_obligation_id].event_id,
            source_evidence_hash=canonical_sha256({"source": ob, "at": at}),
        ) for index, ob in enumerate(due, start=1))
        return CnASharePortfolioSettlementDevelopmentV1(
            self.financial_batch_hash, self.calendar_hashes,
            self.book.append(events=updates))

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_settlement_development",
                "schema_version": 1, "financial_batch_hash": self.financial_batch_hash,
                "calendar_hashes": self.calendar_hashes,
                "book": _book_body(self.book), "synthetic_development_only": True,
                "trade_authorized": False}


def build_cn_a_share_portfolio_settlement_development_v1(
    *, batch: CnASharePortfolioFinancialBatchDevelopmentV1,
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
) -> CnASharePortfolioSettlementDevelopmentV1:
    if (type(batch) is not CnASharePortfolioFinancialBatchDevelopmentV1
            or type(calendars) is not tuple or len(calendars) != 2
            or not all(type(c) is CnAShareFrozenCalendar for c in calendars)):
        raise TypeError("CN development settlement requires two typed venue calendars")
    return _build_cn_a_share_portfolio_settlement_native(batch=batch, calendars=calendars)


def _build_cn_a_share_portfolio_settlement_native(
    *, batch: CnASharePortfolioFinancialBatchDevelopmentV1 | CnASharePortfolioFinancialBatchDevelopmentV2 | CnASharePortfolioFinancialBatchDevelopmentV3,
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
) -> CnASharePortfolioSettlementDevelopmentV1:
    return _build_cn_a_share_portfolio_settlement_facts_v1(
        fills=batch.fills, journal=batch.journal, source_hash=batch.batch_hash, calendars=calendars)


def _build_cn_a_share_portfolio_settlement_facts_v1(
    *, fills: tuple[Fill, ...], journal: AccountingJournal, source_hash: str,
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
) -> CnASharePortfolioSettlementDevelopmentV1:
    """Shared native T+1 facts; no legacy/diagnostic Result conversion is needed."""
    if not fills or any(type(f) is not Fill for f in fills) or type(journal) is not AccountingJournal:
        raise TypeError("native CN settlement requires actual Fill/Journal facts")
    by_venue = {calendar.venue_id: calendar for calendar in calendars}
    if len(by_venue) != 2 or {v.value for v in by_venue} != {"xshg", "xshe"}:
        raise ValueError("CN settlement needs one exact calendar per SH/SZ venue")
    obligations: list[AccountSettlementObligation] = []
    recorded_events: list[SettlementEvent] = []
    immediate_events: list[SettlementEvent] = []
    for ordinal, fill in enumerate(sorted(fills, key=lambda f: str(f.instrument_id)), start=1):
        entries = tuple(entry for entry in journal.entries
                        if entry.entry_type is AccountingEntryType.FILL_BOOKED
                        and fill.fill_id.value in entry.source_ids)
        if len(entries) != 1 or entries[0].account_id != fill.account_id or entries[0].venue_id != fill.venue_id:
            raise ValueError("CN settlement Fill has no exact same-venue Journal evidence")
        instrument = InstrumentDefinition(fill.instrument_id, InstrumentType.EQUITY,
                                          None, CurrencyId("CNY"), CurrencyId("CNY"))
        outcome = CnAShareCashSettlementModel(by_venue[fill.venue_id]).resolve_settlement(
            CnAShareSettlementQuery(
                fill, instrument, entries[0],
                _settlement_id(fill.fill_id, "cash"),
                _settlement_id(fill.fill_id, "position")))
        if outcome.result is None:
            raise ValueError("native CN T+1 settlement rejected Fill or calendar")
        for leg, ob in enumerate(outcome.result.obligations, start=1):
            obligations.append(ob)
            record = SettlementEvent(
                event_id=_event_id(ob, "recorded"),
                settlement_obligation_id=ob.obligation.settlement_obligation_id,
                event_type=SettlementEventType.OBLIGATION_RECORDED,
                occurred_at=SimulationInstant(fill.execution_time,
                                              TimelinePhase(75, "settlement_recorded"),
                                              SourceSequence((ordinal - 1) * 2 + leg)),
                causation_id=fill.fill_id.value,
                source_evidence_hash=canonical_sha256({"fill": fill, "obligation": ob}),
            )
            recorded_events.append(record)
            if ob.obligation.settlement_time == fill.execution_time:
                immediate_events.append(SettlementEvent(
                    event_id=_event_id(ob, "applied"),
                    settlement_obligation_id=ob.obligation.settlement_obligation_id,
                    event_type=SettlementEventType.SETTLEMENT_APPLIED,
                    occurred_at=SimulationInstant(fill.execution_time,
                                                  TimelinePhase(80, "settlement_due"),
                                                  SourceSequence((ordinal - 1) * 2 + leg)),
                    causation_id=record.event_id,
                    source_evidence_hash=canonical_sha256({"source": ob, "at": fill.execution_time}),
                ))
    book = SettlementBook.from_events(fills[0].account_id, tuple(obligations),
                                      (*recorded_events, *immediate_events))
    return CnASharePortfolioSettlementDevelopmentV1(
        source_hash,
        (canonical_sha256(by_venue[VenueId("xshg")]),
         canonical_sha256(by_venue[VenueId("xshe")])),
        book)


def build_cn_a_share_portfolio_settlement_development_v2(
    *, batch: CnASharePortfolioFinancialBatchDevelopmentV2,
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
) -> CnASharePortfolioSettlementDevelopmentV1:
    """N Fill settlement using the same native two-venue calendar model as V1."""
    if type(batch) is not CnASharePortfolioFinancialBatchDevelopmentV2:
        raise TypeError("variable-N settlement requires exact financial BatchV2")
    return _build_cn_a_share_portfolio_settlement_native(batch=batch, calendars=calendars)
