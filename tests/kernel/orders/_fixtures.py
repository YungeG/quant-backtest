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
    VenueId,
)
from crypto_quant_trading import OrderEventRecord


VENUE = VenueId("synthetic")
USD = CurrencyId("USD")
INSTRUMENT = InstrumentId(VENUE, "cash-asset-1")
ACCOUNT = "account:primary"
QUANTITY_SCALE = Scale(3)
PRICE_SCALE = Scale(2)
PHASE = TimelinePhase(60, "orders")


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def instant(nanoseconds: int, sequence: int = 1) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds),
        PHASE,
        SourceSequence(sequence),
    )


def order(digit: str = "1", *, parent_id: str = "target:active:1") -> Order:
    return Order(
        order_id=domain_id(DomainIdKind.ORDER, digit),
        account_id=ACCOUNT,
        intent=OrderIntent(
            instrument_id=INSTRUMENT,
            side=OrderSide.BUY,
            quantity=Quantity(1_000, QUANTITY_SCALE, str(INSTRUMENT)),
            execution_style=ExecutionStyle.MARKET,
            price_constraint=None,
            time_in_force=TimeInForce.DAY,
            reduce_only=False,
            position_effect=PositionEffect.AUTO,
            urgency="normal",
            reason="rebalance",
            parent_id=parent_id,
        ),
        created_at=instant(10),
    )


def event(
    subject: Order,
    name: str,
    event_type: OrderEventType,
    nanoseconds: int,
    causation_id: str,
    *,
    fill_id: DomainId | None = None,
    reason_code: str | None = None,
) -> OrderEvent:
    return OrderEvent(
        event_id=f"event:{name}",
        order_id=subject.order_id,
        causation_id=causation_id,
        event_type=event_type,
        occurred_at=instant(nanoseconds),
        fill_id=fill_id,
        evidence_id=f"evidence:{name}",
        reason_code=reason_code,
    )


def fill(
    subject: Order,
    digit: str,
    quantity_units: int,
    nanoseconds: int,
) -> Fill:
    price = Price(10_000, PRICE_SCALE, str(INSTRUMENT), str(USD))
    return Fill(
        fill_id=domain_id(DomainIdKind.FILL, digit),
        order_id=subject.order_id,
        account_id=subject.account_id,
        venue_id=VENUE,
        instrument_id=INSTRUMENT,
        side=subject.intent.side,
        quantity=Quantity(quantity_units, QUANTITY_SCALE, str(INSTRUMENT)),
        reference_price=price,
        reference_price_purpose=PricePurpose.EXECUTION_REFERENCE,
        price=price,
        slippage_amount=Money(0, PRICE_SCALE, str(USD)),
        slippage_decision_id=f"slippage:{digit}",
        slippage_model_key="slippage.fixture.v1",
        slippage_calibration_id=None,
        liquidity="taker",
        execution_time=UtcInstant(nanoseconds),
    )


def full_lifecycle_records(subject: Order | None = None) -> tuple[OrderEventRecord, ...]:
    subject = order() if subject is None else subject
    created = event(
        subject,
        "created",
        OrderEventType.ORDER_INTENT_CREATED,
        10,
        subject.intent.parent_id,
    )
    capability = event(
        subject,
        "capability",
        OrderEventType.ORDER_CAPABILITY_APPROVED,
        20,
        created.event_id,
    )
    translated = event(
        subject,
        "translated",
        OrderEventType.ORDER_TRANSLATED,
        30,
        capability.event_id,
    )
    market = event(
        subject,
        "market",
        OrderEventType.MARKET_RULE_APPROVED,
        40,
        translated.event_id,
    )
    fee = event(
        subject,
        "fee",
        OrderEventType.FEE_RESERVATION_ESTIMATED,
        50,
        market.event_id,
    )
    risk = event(
        subject,
        "risk",
        OrderEventType.PRE_TRADE_RISK_APPROVED,
        60,
        fee.event_id,
    )
    submitted = event(
        subject,
        "submitted",
        OrderEventType.ORDER_SUBMITTED,
        70,
        risk.event_id,
    )
    accepted = event(
        subject,
        "accepted",
        OrderEventType.ORDER_ACCEPTED,
        80,
        submitted.event_id,
    )
    activated = event(
        subject,
        "activated",
        OrderEventType.ORDER_ACTIVATED,
        90,
        accepted.event_id,
    )
    first_fill = fill(subject, "2", 400, 100)
    partial = event(
        subject,
        "partial",
        OrderEventType.ORDER_PARTIALLY_FILLED,
        100,
        activated.event_id,
        fill_id=first_fill.fill_id,
    )
    final_fill = fill(subject, "3", 600, 110)
    filled = event(
        subject,
        "filled",
        OrderEventType.ORDER_FILLED,
        110,
        partial.event_id,
        fill_id=final_fill.fill_id,
    )
    return (
        OrderEventRecord(created),
        OrderEventRecord(capability),
        OrderEventRecord(translated),
        OrderEventRecord(market),
        OrderEventRecord(fee),
        OrderEventRecord(risk),
        OrderEventRecord(submitted),
        OrderEventRecord(accepted),
        OrderEventRecord(activated),
        OrderEventRecord(partial, first_fill),
        OrderEventRecord(filled, final_fill),
    )
