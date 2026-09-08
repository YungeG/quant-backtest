from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import Money, Order, OrderEventType, OrderSide, Quantity
from crypto_quant_trading import (
    OrderEventStream,
    OrderReservationSchedule,
    OrderReservationUpdate,
    ReservationCommitment,
)

from tests.kernel.orders._fixtures import (
    ACCOUNT,
    INSTRUMENT,
    PRICE_SCALE,
    QUANTITY_SCALE,
    USD,
    full_lifecycle_records,
    order,
)


def source_hash(digit: str) -> str:
    return f"sha256:{digit * 64}"


def subject_order(digit: str = "1", *, side: OrderSide = OrderSide.BUY) -> Order:
    base = order(digit)
    return replace(base, intent=replace(base.intent, side=side))


def stream(subject: Order, event_count: int = 11) -> OrderEventStream:
    records = full_lifecycle_records(subject)
    return OrderEventStream.from_records(subject, records[:event_count])


def buy_commitment(*, partial: bool = False) -> ReservationCommitment:
    if partial:
        return ReservationCommitment(
            cash=(Money(6_300, PRICE_SCALE, str(USD)),),
            sellable_quantities=(),
            margin=(Money(1_200, PRICE_SCALE, str(USD)),),
            fee_reserve=(Money(300, PRICE_SCALE, str(USD)),),
            order_capacity_units=1,
            exposure_capacity=(Money(6_000, PRICE_SCALE, str(USD)),),
        )
    return ReservationCommitment(
        cash=(Money(10_500, PRICE_SCALE, str(USD)),),
        sellable_quantities=(),
        margin=(Money(2_000, PRICE_SCALE, str(USD)),),
        fee_reserve=(Money(500, PRICE_SCALE, str(USD)),),
        order_capacity_units=1,
        exposure_capacity=(Money(10_000, PRICE_SCALE, str(USD)),),
    )


def sell_commitment(*, partial: bool = False) -> ReservationCommitment:
    quantity_units = 600 if partial else 1_000
    return ReservationCommitment(
        cash=(),
        sellable_quantities=(
            Quantity(quantity_units, QUANTITY_SCALE, str(INSTRUMENT)),
        ),
        margin=(),
        fee_reserve=(Money(200 if partial else 300, PRICE_SCALE, str(USD)),),
        order_capacity_units=1,
        exposure_capacity=(Money(
                6_000 if partial else 10_000,
                PRICE_SCALE,
                str(USD),
            ),),
    )


def schedule(subject: Order, *, sell: bool = False) -> OrderReservationSchedule:
    records = full_lifecycle_records(subject)
    initial = sell_commitment() if sell else buy_commitment()
    partial = sell_commitment(partial=True) if sell else buy_commitment(partial=True)
    return OrderReservationSchedule(
        order_id=subject.order_id,
        source_proposal_hash=source_hash(subject.order_id.value[-1]),
        updates=(
            OrderReservationUpdate(
                order_id=subject.order_id,
                event_id=records[7].event.event_id,
                event_type=OrderEventType.ORDER_ACCEPTED,
                remaining_quantity=subject.intent.quantity,
                commitment=initial,
                source_evidence_hash=source_hash("a"),
            ),
            OrderReservationUpdate(
                order_id=subject.order_id,
                event_id=records[9].event.event_id,
                event_type=OrderEventType.ORDER_PARTIALLY_FILLED,
                remaining_quantity=Quantity(
                    600,
                    QUANTITY_SCALE,
                    str(INSTRUMENT),
                ),
                commitment=partial,
                source_evidence_hash=source_hash("b"),
            ),
        ),
    )


__all__ = [
    "ACCOUNT",
    "buy_commitment",
    "schedule",
    "sell_commitment",
    "source_hash",
    "stream",
    "subject_order",
]
