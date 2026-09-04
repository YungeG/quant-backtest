from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    Fill,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    OrderSide,
    PositionBalanceKey,
    Price,
    PricePurpose,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    ActiveOrderReservation,
    AvailabilityProjection,
    AvailabilityState,
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
    MarketSettlementRules,
    OrderReservationCursor,
    ReservationCommitment,
    ResourceReservationState,
    SettlementBook,
    SettlementBookState,
    SettlementEvent,
    SettlementEventType,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCalendarDayKind,
    CnAShareCashSettlementModel,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareSessionQuery,
    CnAShareSettlementQuery,
    CnAShareSettlementResolution,
)


_TIMEZONE = ZoneInfo("Asia/Shanghai")
_ACCOUNT = "account:cn-a-primary"
_CNY = CurrencyId("CNY")
_MONEY_SCALE = Scale(2)
_QUANTITY_SCALE = Scale(0)


def frozen_calendar(venue: str = "xshg") -> CnAShareFrozenCalendar:
    calendar_id = {"xshg": "CN.XSHG", "xshe": "CN.XSHE"}[venue]
    days = []
    for day in range(8, 20):
        local_date = date(2024, 2, day)
        if day in {8, 19}:
            kind = CnAShareCalendarDayKind.TRADING
        elif day == 18:
            kind = CnAShareCalendarDayKind.WEEKEND
        else:
            kind = CnAShareCalendarDayKind.FROZEN_HOLIDAY
        days.append(CnAShareFrozenCalendarDay(local_date, kind))
    return CnAShareFrozenCalendar(
        venue_id=VenueId(venue),
        calendar_id=calendar_id,
        coverage_start=date(2024, 2, 8),
        coverage_end_exclusive=date(2024, 2, 20),
        days=tuple(reversed(days)),
    )


def _domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def local_query(
    local_date: date,
    hour: int,
    minute: int,
    *,
    venue: str = "xshg",
) -> CnAShareSessionQuery:
    return CnAShareSessionQuery(
        venue_id=VenueId(venue),
        instant=UtcInstant.from_datetime(
            datetime(
                local_date.year,
                local_date.month,
                local_date.day,
                hour,
                minute,
                tzinfo=_TIMEZONE,
            )
        ),
    )


def settlement_model(venue: str = "xshg") -> CnAShareCashSettlementModel:
    return CnAShareCashSettlementModel(frozen_calendar(venue))


def settlement_schema(venue: str = "xshg") -> LedgerSchema:
    venue_id = VenueId(venue)
    instrument_id = InstrumentId(
        venue_id,
        "600000" if venue == "xshg" else "000001",
    )
    return LedgerSchema(
        (
            LedgerBalanceRegistration(
                CashBalanceKey(_ACCOUNT, venue_id, _CNY),
                _MONEY_SCALE,
            ),
            LedgerBalanceRegistration(
                PositionBalanceKey(_ACCOUNT, venue_id, instrument_id),
                _QUANTITY_SCALE,
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class SettlementJourney:
    queries: tuple[CnAShareSettlementQuery, CnAShareSettlementQuery]
    resolutions: tuple[
        CnAShareSettlementResolution,
        CnAShareSettlementResolution,
    ]
    journal: AccountingJournal
    ledger: LedgerState
    rules: MarketSettlementRules
    reservations: ResourceReservationState
    forward_book: SettlementBook
    reversed_book: SettlementBook
    position_boundary_before: SettlementBookState
    position_boundary_after: SettlementBookState
    cash_boundary_before: SettlementBookState
    cash_boundary_after: SettlementBookState
    full_state: SettlementBookState
    resumed_state: SettlementBookState
    before_availability: AvailabilityState
    position_available: AvailabilityState
    cash_available: AvailabilityState


def settlement_query(
    side: OrderSide,
    *,
    venue: str = "xshg",
    local_date: date = date(2024, 2, 8),
    hour: int = 10,
    minute: int = 0,
) -> CnAShareSettlementQuery:
    venue_id = VenueId(venue)
    instrument_id = InstrumentId(
        venue_id,
        "600000" if venue == "xshg" else "000001",
    )
    instrument = InstrumentDefinition(
        instrument_id=instrument_id,
        instrument_type=InstrumentType.EQUITY,
        base_currency=None,
        quote_currency=_CNY,
        settlement_currency=_CNY,
    )
    execution_time = local_query(
        local_date,
        hour,
        minute,
        venue=venue,
    ).instant
    digit = "1" if side is OrderSide.BUY else "2"
    price_units = 1_000 if side is OrderSide.BUY else 1_200
    cash_units = -100_000 if side is OrderSide.BUY else 120_000
    position_units = 100 if side is OrderSide.BUY else -100
    price = Price(
        price_units,
        _MONEY_SCALE,
        str(instrument_id),
        str(_CNY),
    )
    fill = Fill(
        fill_id=_domain_id(DomainIdKind.FILL, digit),
        order_id=_domain_id(DomainIdKind.ORDER, digit),
        account_id=_ACCOUNT,
        venue_id=venue_id,
        instrument_id=instrument_id,
        side=side,
        quantity=Quantity(100, _QUANTITY_SCALE, str(instrument_id)),
        reference_price=price,
        reference_price_purpose=PricePurpose.EXECUTION_REFERENCE,
        price=price,
        slippage_amount=Money(0, _MONEY_SCALE, str(_CNY)),
        slippage_decision_id=f"slippage:{digit}",
        slippage_model_key="slippage.zero.fixture.v1",
        slippage_calibration_id=None,
        liquidity="taker",
        execution_time=execution_time,
    )
    cash_key = CashBalanceKey(_ACCOUNT, venue_id, _CNY)
    position_key = PositionBalanceKey(_ACCOUNT, venue_id, instrument_id)
    entry = AccountingJournalEntry(
        journal_entry_id=_domain_id(
            DomainIdKind.JOURNAL,
            "2" if side is OrderSide.BUY else "1",
        ),
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id=_ACCOUNT,
        venue_id=venue_id,
        effective_time=execution_time,
        recorded_at=SimulationInstant(
            execution_time,
            TimelinePhase(50, "accounting"),
            SourceSequence(1 if side is OrderSide.BUY else 2),
        ),
        source_ids=(fill.order_id.value, fill.fill_id.value),
        balance_changes=(
            BalanceChange(
                position_key,
                Quantity(position_units, _QUANTITY_SCALE, str(instrument_id)),
            ),
            BalanceChange(cash_key, Money(cash_units, _MONEY_SCALE, str(_CNY))),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    return CnAShareSettlementQuery(
        fill=fill,
        instrument=instrument,
        fill_accounting_entry=entry,
        cash_obligation_id=_domain_id(DomainIdKind.SETTLEMENT, digit),
        position_obligation_id=_domain_id(
            DomainIdKind.SETTLEMENT,
            "3" if side is OrderSide.BUY else "4",
        ),
    )


def _settlement_event_instant(
    instant: UtcInstant,
    phase_order: int,
    phase_key: str,
    sequence: int,
) -> SimulationInstant:
    return SimulationInstant(
        instant,
        TimelinePhase(phase_order, phase_key),
        SourceSequence(sequence),
    )


def _reservation_state(query: CnAShareSettlementQuery) -> ResourceReservationState:
    commitment = ReservationCommitment(
        cash=(Money(20_000, _MONEY_SCALE, str(_CNY)),),
        sellable_quantities=(
            Quantity(20, _QUANTITY_SCALE, str(query.fill.instrument_id)),
        ),
        margin=(),
        fee_reserve=(Money(1_000, _MONEY_SCALE, str(_CNY)),),
    )
    order_id = _domain_id(DomainIdKind.ORDER, "9")
    return ResourceReservationState(
        account_id=_ACCOUNT,
        cursors=(
            OrderReservationCursor(
                order_id,
                1,
                f"sha256:{'8' * 64}",
                f"sha256:{'7' * 64}",
            ),
        ),
        active_reservations=(
            ActiveOrderReservation(
                account_id=_ACCOUNT,
                order_id=order_id,
                last_update_event_id="order-event:accepted:9",
                remaining_quantity=Quantity(
                    20,
                    _QUANTITY_SCALE,
                    str(query.fill.instrument_id),
                ),
                commitment=commitment,
                source_proposal_hash=f"sha256:{'6' * 64}",
            ),
        ),
        totals=commitment,
    )


def settlement_journey(venue: str = "xshg") -> SettlementJourney:
    model = settlement_model(venue)
    buy_query = settlement_query(OrderSide.BUY, venue=venue)
    sell_query = settlement_query(OrderSide.SELL, venue=venue)
    schema = settlement_schema(venue)
    cash_change = next(
        value
        for value in buy_query.fill_accounting_entry.balance_changes
        if isinstance(value.key, CashBalanceKey)
    )
    position_change = next(
        value
        for value in buy_query.fill_accounting_entry.balance_changes
        if isinstance(value.key, PositionBalanceKey)
    )
    cash_key = cash_change.key
    position_key = position_change.key
    assert isinstance(cash_key, CashBalanceKey)
    assert isinstance(position_key, PositionBalanceKey)
    initial_time = local_query(date(2024, 2, 8), 9, 0, venue=venue).instant
    initial = AccountingJournalEntry(
        journal_entry_id=_domain_id(DomainIdKind.JOURNAL, "0"),
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        account_id=_ACCOUNT,
        venue_id=VenueId(venue),
        effective_time=initial_time,
        recorded_at=_settlement_event_instant(
            initial_time,
            50,
            "accounting",
            1,
        ),
        source_ids=("initial:cash-position",),
        balance_changes=(
            BalanceChange(cash_key, Money(1_000_000, _MONEY_SCALE, str(_CNY))),
            BalanceChange(
                position_key,
                Quantity(200, _QUANTITY_SCALE, str(position_key.instrument_id)),
            ),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    journal = AccountingJournal.from_entries(
        (
            sell_query.fill_accounting_entry,
            initial,
            buy_query.fill_accounting_entry,
        )
    )
    ledger = GenericLedger(schema).project(journal)
    assert ledger.cursor == journal.cursor_at(journal.entry_count)
    assert buy_query.fill_accounting_entry in journal.entries
    assert sell_query.fill_accounting_entry in journal.entries
    buy_outcome = model.resolve_settlement(buy_query)
    sell_outcome = model.resolve_settlement(sell_query)
    assert buy_outcome.result is not None
    assert sell_outcome.result is not None
    buy = buy_outcome.result
    sell = sell_outcome.result
    obligations = buy.obligations + sell.obligations
    resolution_by_fill = {
        buy.fill_id.value: buy,
        sell.fill_id.value: sell,
    }
    recorded_events = tuple(
        SettlementEvent(
            event_id=f"settlement-event:recorded:{5 - index}",
            settlement_obligation_id=value.obligation.settlement_obligation_id,
            event_type=SettlementEventType.OBLIGATION_RECORDED,
            occurred_at=_settlement_event_instant(
                value.obligation.trade_time,
                60,
                "settlement_recorded",
                index,
            ),
            causation_id=value.obligation.source_fill_id.value,
            source_evidence_hash=canonical_sha256(
                resolution_by_fill[value.obligation.source_fill_id.value]
            ),
        )
        for index, value in enumerate(obligations, start=1)
    )
    recorded_by_obligation = {
        event.settlement_obligation_id: event for event in recorded_events
    }
    immediate = tuple(
        value
        for value in obligations
        if value.obligation.settlement_time == value.obligation.trade_time
    )
    deferred = tuple(
        value
        for value in obligations
        if value.obligation.settlement_time > value.obligation.trade_time
    )
    applied_events = tuple(
        SettlementEvent(
            event_id=f"settlement-event:applied:{5 - index}",
            settlement_obligation_id=value.obligation.settlement_obligation_id,
            event_type=SettlementEventType.SETTLEMENT_APPLIED,
            occurred_at=_settlement_event_instant(
                value.obligation.settlement_time,
                61,
                "settlement_applied",
                index,
            ),
            causation_id=recorded_by_obligation[
                value.obligation.settlement_obligation_id
            ].event_id,
            source_evidence_hash=canonical_sha256(value),
        )
        for index, value in enumerate((*immediate, *deferred), start=1)
    )
    all_events = recorded_events + applied_events
    forward_book = SettlementBook.from_events(_ACCOUNT, obligations, all_events)
    reversed_book = SettlementBook.from_events(
        _ACCOUNT,
        tuple(reversed(obligations)),
        tuple(reversed(all_events)),
    )
    ordered_events = forward_book.events
    position_event_id = next(
        event.event_id
        for event in applied_events
        if event.settlement_obligation_id
        == buy.obligations[1].obligation.settlement_obligation_id
    )
    cash_event_id = next(
        event.event_id
        for event in applied_events
        if event.settlement_obligation_id
        == sell.obligations[0].obligation.settlement_obligation_id
    )
    position_index = next(
        index
        for index, event in enumerate(ordered_events)
        if event.event_id == position_event_id
    )
    cash_index = next(
        index
        for index, event in enumerate(ordered_events)
        if event.event_id == cash_event_id
    )
    position_before = forward_book.project(
        stop=forward_book.cursor_at(position_index)
    )
    position_after = forward_book.project(
        stop=forward_book.cursor_at(position_index + 1)
    )
    cash_before = forward_book.project(stop=forward_book.cursor_at(cash_index))
    cash_after = forward_book.project(stop=forward_book.cursor_at(cash_index + 1))
    full_state = forward_book.project()
    resumed_state = forward_book.resume(position_before)
    reservations = _reservation_state(buy_query)
    rules = model.availability_rules(schema)
    projection = AvailabilityProjection()
    return SettlementJourney(
        queries=(buy_query, sell_query),
        resolutions=(buy, sell),
        journal=journal,
        ledger=ledger,
        rules=rules,
        reservations=reservations,
        forward_book=forward_book,
        reversed_book=reversed_book,
        position_boundary_before=position_before,
        position_boundary_after=position_after,
        cash_boundary_before=cash_before,
        cash_boundary_after=cash_after,
        full_state=full_state,
        resumed_state=resumed_state,
        before_availability=projection.project(
            ledger,
            position_before,
            reservations,
            rules,
        ),
        position_available=projection.project(
            ledger,
            position_after,
            reservations,
            rules,
        ),
        cash_available=projection.project(
            ledger,
            cash_after,
            reservations,
            rules,
        ),
    )
