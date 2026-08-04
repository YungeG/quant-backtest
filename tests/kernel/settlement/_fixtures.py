from __future__ import annotations

from crypto_quant_domain import (
    CashBalance,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    InstrumentId,
    Money,
    PositionBalance,
    PositionBalanceKey,
    Quantity,
    Scale,
    SettlementObligation,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import (
    AccountingJournal,
    AccountSettlementObligation,
    ActiveOrderReservation,
    CashAvailabilityRule,
    CashReservationUse,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
    MarketSettlementRules,
    OrderReservationCursor,
    PositionAvailabilityRule,
    ReservationCommitment,
    ResourceReservationState,
    SettlementBook,
    SettlementEvent,
    SettlementEventType,
)


ACCOUNT = "account:primary"
VENUE = VenueId("synthetic")
USD = CurrencyId("USD")
INSTRUMENT = InstrumentId(VENUE, "asset-1")
CASH_KEY = CashBalanceKey(ACCOUNT, VENUE, USD)
POSITION_KEY = PositionBalanceKey(ACCOUNT, VENUE, INSTRUMENT)
MONEY_SCALE = Scale(2)
QUANTITY_SCALE = Scale(0)


def digest(digit: str) -> str:
    return f"sha256:{digit * 64}"


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def instant(nanoseconds: int, sequence: int = 1) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds),
        TimelinePhase(60, "settlement"),
        SourceSequence(sequence),
    )


def registered_obligation(
    digit: str,
    *,
    key: CashBalanceKey | PositionBalanceKey,
    units: int,
    settlement_time: int,
) -> AccountSettlementObligation:
    if isinstance(key, CashBalanceKey):
        obligation = SettlementObligation(
            settlement_obligation_id=domain_id(DomainIdKind.SETTLEMENT, digit),
            source_fill_id=domain_id(DomainIdKind.FILL, digit),
            trade_time=UtcInstant(10),
            settlement_time=UtcInstant(settlement_time),
            instrument_id=None,
            quantity=None,
            currency_id=key.currency_id,
            amount=Money(units, MONEY_SCALE, str(key.currency_id)),
        )
    else:
        obligation = SettlementObligation(
            settlement_obligation_id=domain_id(DomainIdKind.SETTLEMENT, digit),
            source_fill_id=domain_id(DomainIdKind.FILL, digit),
            trade_time=UtcInstant(10),
            settlement_time=UtcInstant(settlement_time),
            instrument_id=key.instrument_id,
            quantity=Quantity(units, QUANTITY_SCALE, str(key.instrument_id)),
            currency_id=None,
            amount=None,
        )
    return AccountSettlementObligation(obligation=obligation, balance_key=key)


def recorded_event(
    registered: AccountSettlementObligation,
    digit: str,
    *,
    sequence: int,
) -> SettlementEvent:
    return SettlementEvent(
        event_id=f"settlement-event:recorded:{digit}",
        settlement_obligation_id=registered.obligation.settlement_obligation_id,
        event_type=SettlementEventType.OBLIGATION_RECORDED,
        occurred_at=instant(registered.obligation.trade_time.epoch_nanoseconds, sequence),
        causation_id=registered.obligation.source_fill_id.value,
        source_evidence_hash=digest(digit),
    )


def applied_event(
    registered: AccountSettlementObligation,
    recorded: SettlementEvent,
    digit: str,
    *,
    occurred_at: int | None = None,
    sequence: int = 1,
) -> SettlementEvent:
    return SettlementEvent(
        event_id=f"settlement-event:applied:{digit}",
        settlement_obligation_id=registered.obligation.settlement_obligation_id,
        event_type=SettlementEventType.SETTLEMENT_APPLIED,
        occurred_at=instant(
            occurred_at
            if occurred_at is not None
            else registered.obligation.settlement_time.epoch_nanoseconds,
            sequence,
        ),
        causation_id=recorded.event_id,
        source_evidence_hash=digest(digit.upper()),
    )


def settlement_evidence() -> tuple[
    tuple[AccountSettlementObligation, ...], tuple[SettlementEvent, ...]
]:
    position = registered_obligation(
        "1", key=POSITION_KEY, units=10, settlement_time=20
    )
    cash_receivable = registered_obligation(
        "2", key=CASH_KEY, units=5_000, settlement_time=30
    )
    cash_delivery = registered_obligation(
        "3", key=CASH_KEY, units=-10_000, settlement_time=40
    )
    position_recorded = recorded_event(position, "1", sequence=1)
    cash_receivable_recorded = recorded_event(cash_receivable, "2", sequence=2)
    cash_delivery_recorded = recorded_event(cash_delivery, "3", sequence=3)
    events = (
        position_recorded,
        cash_receivable_recorded,
        cash_delivery_recorded,
        applied_event(position, position_recorded, "1"),
        applied_event(cash_receivable, cash_receivable_recorded, "2"),
        applied_event(cash_delivery, cash_delivery_recorded, "3"),
    )
    return (position, cash_receivable, cash_delivery), events


def settlement_book() -> SettlementBook:
    obligations, events = settlement_evidence()
    return SettlementBook.from_events(ACCOUNT, obligations, events)


def ledger_state() -> LedgerState:
    schema = LedgerSchema(
        (
            LedgerBalanceRegistration(CASH_KEY, MONEY_SCALE),
            LedgerBalanceRegistration(POSITION_KEY, QUANTITY_SCALE),
        )
    )
    return LedgerState(
        schema=schema,
        cursor=AccountingJournal.empty().cursor_at(0),
        cash_balances=(CashBalance(CASH_KEY, Money(15_000, MONEY_SCALE, str(USD))),),
        position_balances=(
            PositionBalance(
                POSITION_KEY,
                Quantity(15, QUANTITY_SCALE, str(INSTRUMENT)),
                (),
            ),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )


def reservation_state() -> ResourceReservationState:
    order_id = domain_id(DomainIdKind.ORDER, "9")
    commitment = ReservationCommitment(
        cash=(Money(2_000, MONEY_SCALE, str(USD)),),
        sellable_quantities=(Quantity(2, QUANTITY_SCALE, str(INSTRUMENT)),),
        margin=(Money(1_500, MONEY_SCALE, str(USD)),),
        fee_reserve=(Money(100, MONEY_SCALE, str(USD)),),
    )
    cursor = OrderReservationCursor(order_id, 1, digest("8"), digest("7"))
    active = ActiveOrderReservation(
        account_id=ACCOUNT,
        order_id=order_id,
        last_update_event_id="order-event:accepted:9",
        remaining_quantity=Quantity(1, QUANTITY_SCALE, str(INSTRUMENT)),
        commitment=commitment,
        source_proposal_hash=digest("6"),
    )
    return ResourceReservationState(
        account_id=ACCOUNT,
        cursors=(cursor,),
        active_reservations=(active,),
        totals=commitment,
    )


def market_rules(*, reverse: bool = False) -> MarketSettlementRules:
    cash_rule = CashAvailabilityRule(
        key=CASH_KEY,
        pending_receivable_tradable=True,
        pending_receivable_withdrawable=False,
        pending_receivable_margin_eligible=True,
        tradable_reservation_uses=(
            CashReservationUse.CASH,
            CashReservationUse.FEE_RESERVE,
        ),
        withdrawable_reservation_uses=(
            CashReservationUse.CASH,
            CashReservationUse.MARGIN,
            CashReservationUse.FEE_RESERVE,
        ),
        available_margin_reservation_uses=(CashReservationUse.MARGIN,),
    )
    position_rule = PositionAvailabilityRule(
        key=POSITION_KEY,
        pending_receivable_sellable=False,
    )
    cash_rules: tuple[CashAvailabilityRule, ...] = (cash_rule,)
    position_rules: tuple[PositionAvailabilityRule, ...] = (position_rule,)
    if reverse:
        cash_rules = tuple(reversed(cash_rules))
        position_rules = tuple(reversed(position_rules))
    return MarketSettlementRules.create(
        policy_key="settlement.synthetic.explicit.v1",
        policy_version=1,
        account_id=ACCOUNT,
        cash_rules=cash_rules,
        position_rules=position_rules,
    )


__all__ = [
    "ACCOUNT",
    "CASH_KEY",
    "INSTRUMENT",
    "MONEY_SCALE",
    "POSITION_KEY",
    "QUANTITY_SCALE",
    "USD",
    "VENUE",
    "applied_event",
    "digest",
    "instant",
    "ledger_state",
    "market_rules",
    "recorded_event",
    "registered_obligation",
    "reservation_state",
    "settlement_book",
    "settlement_evidence",
]
