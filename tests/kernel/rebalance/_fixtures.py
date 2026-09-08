from __future__ import annotations

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    DomainIdKind,
    ExecutionStyle,
    Fill,
    InstrumentId,
    Money,
    Order,
    OrderEvent,
    OrderEventType,
    OrderIntent,
    OrderSide,
    PortfolioSnapshot,
    PositionBalance,
    PositionBalanceKey,
    PositionEffect,
    Price,
    PricePurpose,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    ActiveOrderReservation,
    AvailabilityState,
    OrderEventRecord,
    OrderEventStream,
    NormalizedPortfolioTarget,
    OrderReservationCursor,
    RebalancePolicy,
    ReservationCommitment,
    ResourceReservationState,
    TargetValidity,
)
from tests.kernel.integration.test_target_materialization_journey import run_journey


ACCOUNT = "account:primary"
USD = CurrencyId("USD")
QUANTITY_SCALE = Scale(3)
PRICE_SCALE = Scale(2)
PHASE = TimelinePhase(70, "plan_and_submit")


def normalized_target() -> NormalizedPortfolioTarget:
    return run_journey()["normalized"]


def policy(*, valid_for: int | None = 50) -> RebalancePolicy:
    return RebalancePolicy.create(
        policy_key="rebalance.market-day.v1",
        policy_version=1,
        execution_style=ExecutionStyle.MARKET,
        time_in_force=TimeInForce.DAY,
        urgency="normal",
        plan_valid_for_nanoseconds=valid_for,
    )


def validity(*, valid_until: int | None = 300) -> TargetValidity:
    target = normalized_target()
    return TargetValidity(
        normalized_target_id=target.normalized_target_id,
        normalized_target_hash=target.normalized_target_hash,
        valid_from=target.materialized_at,
        valid_until=UtcInstant(valid_until) if valid_until is not None else None,
    )


def snapshot(
    *,
    btc_units: int = 0,
    eth_units: int = 16_000,
    timestamp: int = 200,
) -> PortfolioSnapshot:
    target = normalized_target()
    btc, eth = (value.instrument_id for value in target.targets)
    positions = []
    for instrument_id, units in ((btc, btc_units), (eth, eth_units)):
        if units:
            positions.append(
                PositionBalance(
                    PositionBalanceKey(ACCOUNT, instrument_id.venue, instrument_id),
                    Quantity(units, QUANTITY_SCALE, str(instrument_id)),
                    (),
                )
            )
    base = run_journey()["allocation"].source_portfolio_snapshot_hash
    zero = Money(0, Scale(2), "USD")
    return PortfolioSnapshot(
        account_id=ACCOUNT,
        timestamp=UtcInstant(timestamp),
        reporting_currency=USD,
        cash=(),
        positions=tuple(positions),
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=Money(100_000, Scale(2), "USD"),
        valuation_marks=(),
        journal_state_hash=base,
        valuation_mark_set_hash=canonical_sha256(()),
        valuation_staleness_report_hash="sha256:" + "1" * 64,
        currency_valuation_graph_hash="sha256:" + "2" * 64,
    )


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def instant(nanoseconds: int, sequence: int = 1) -> SimulationInstant:
    return SimulationInstant(UtcInstant(nanoseconds), PHASE, SourceSequence(sequence))


def working_order(
    digit: str,
    *,
    instrument_id: InstrumentId,
    side: OrderSide,
    quantity_units: int,
    parent_id: str = "normalized-portfolio-target-v1:old",
) -> Order:
    return Order(
        order_id=domain_id(DomainIdKind.ORDER, digit),
        account_id=ACCOUNT,
        intent=OrderIntent(
            instrument_id=instrument_id,
            side=side,
            quantity=Quantity(quantity_units, QUANTITY_SCALE, str(instrument_id)),
            execution_style=ExecutionStyle.MARKET,
            price_constraint=None,
            time_in_force=TimeInForce.DAY,
            reduce_only=False,
            position_effect=PositionEffect.AUTO,
            urgency="normal",
            reason="prior rebalance",
            parent_id=parent_id,
        ),
        created_at=instant(110),
    )


def _event(
    order: Order,
    suffix: str,
    event_type: OrderEventType,
    at: int,
    cause: str,
    *,
    fill_id: DomainId | None = None,
) -> OrderEvent:
    return OrderEvent(
        event_id=f"event:{order.order_id.value[-4:]}:{suffix}",
        order_id=order.order_id,
        causation_id=cause,
        event_type=event_type,
        occurred_at=instant(at),
        fill_id=fill_id,
        evidence_id=f"evidence:{suffix}",
    )


def working_stream(
    order: Order,
    *,
    partial_fill_units: int = 0,
    cancel_requested: bool = False,
    cancelled: bool = False,
) -> OrderEventStream:
    types = (
        OrderEventType.ORDER_INTENT_CREATED,
        OrderEventType.ORDER_CAPABILITY_APPROVED,
        OrderEventType.ORDER_TRANSLATED,
        OrderEventType.MARKET_RULE_APPROVED,
        OrderEventType.FEE_RESERVATION_ESTIMATED,
        OrderEventType.PRE_TRADE_RISK_APPROVED,
        OrderEventType.ORDER_SUBMITTED,
        OrderEventType.ORDER_ACCEPTED,
        OrderEventType.ORDER_ACTIVATED,
    )
    records: list[OrderEventRecord] = []
    cause = order.intent.parent_id
    for offset, event_type in enumerate(types):
        event = _event(order, event_type.value, event_type, 110 + offset, cause)
        records.append(OrderEventRecord(event))
        cause = event.event_id

    if partial_fill_units:
        fill_id = domain_id(DomainIdKind.FILL, "a" if order.order_id.value[-1] != "a" else "b")
        price = Price(10_000, PRICE_SCALE, str(order.intent.instrument_id), "USD")
        fill = Fill(
            fill_id=fill_id,
            order_id=order.order_id,
            account_id=order.account_id,
            venue_id=order.intent.instrument_id.venue,
            instrument_id=order.intent.instrument_id,
            side=order.intent.side,
            quantity=Quantity(partial_fill_units, QUANTITY_SCALE, str(order.intent.instrument_id)),
            reference_price=price,
            reference_price_purpose=PricePurpose.EXECUTION_REFERENCE,
            price=price,
            slippage_amount=Money(0, PRICE_SCALE, "USD"),
            slippage_decision_id=f"slippage:{order.order_id.value[-4:]}",
            slippage_model_key="slippage.fixture.v1",
            slippage_calibration_id=None,
            liquidity="taker",
            execution_time=UtcInstant(119),
        )
        event = _event(
            order,
            "partial",
            OrderEventType.ORDER_PARTIALLY_FILLED,
            119,
            cause,
            fill_id=fill_id,
        )
        records.append(OrderEventRecord(event, fill))
        cause = event.event_id

    if cancel_requested or cancelled:
        event = _event(
            order,
            "cancel-requested",
            OrderEventType.ORDER_CANCEL_REQUESTED,
            120,
            cause,
        )
        records.append(OrderEventRecord(event))
        cause = event.event_id
    if cancelled:
        event = _event(
            order,
            "cancelled",
            OrderEventType.ORDER_CANCELLED,
            121,
            cause,
        )
        records.append(OrderEventRecord(event))

    return OrderEventStream.from_records(order, records)


def reservation_state(
    streams: tuple[OrderEventStream, ...] = (),
) -> ResourceReservationState:
    active = []
    cursors = []
    for stream in streams:
        state = stream.state
        if state is None or state.status.value in {"filled", "cancelled", "expired", "rejected"}:
            continue
        commitment = ReservationCommitment(order_capacity_units=1)
        cursors.append(
            OrderReservationCursor(
                stream.order.order_id,
                stream.event_count,
                stream.stream_hash,
                "sha256:" + "3" * 64,
            )
        )
        active.append(
            ActiveOrderReservation(
                account_id=ACCOUNT,
                order_id=stream.order.order_id,
                last_update_event_id=state.last_event_id,
                remaining_quantity=state.remaining_quantity,
                commitment=commitment,
                source_proposal_hash="sha256:" + "4" * 64,
            )
        )
    totals = ReservationCommitment(order_capacity_units=len(active))
    return ResourceReservationState(
        account_id=ACCOUNT,
        cursors=tuple(cursors),
        active_reservations=tuple(active),
        totals=totals,
    )


def availability(
    portfolio_snapshot: PortfolioSnapshot,
    reservations: ResourceReservationState,
) -> AvailabilityState:
    return AvailabilityState(
        account_id=ACCOUNT,
        ledger_state_hash=portfolio_snapshot.journal_state_hash,
        settlement_state_hash="sha256:" + "5" * 64,
        reservation_state_hash=reservations.state_hash,
        market_settlement_rules_hash="sha256:" + "6" * 64,
        cash=(),
        positions=(),
    )


__all__ = [
    "ACCOUNT",
    "QUANTITY_SCALE",
    "availability",
    "normalized_target",
    "policy",
    "reservation_state",
    "snapshot",
    "validity",
    "working_order",
    "working_stream",
]
