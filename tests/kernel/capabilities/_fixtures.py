from __future__ import annotations

from crypto_quant_domain import (
    ExecutionStyle,
    InstrumentId,
    OrderIntent,
    OrderSide,
    PositionEffect,
    Price,
    PriceConstraint,
    Quantity,
    Scale,
    TimeInForce,
    VenueId,
)
from crypto_quant_trading import (
    OrderCapabilityKey,
    OrderCapabilitySet,
    OrderStyleCapability,
    PriceConstraintShape,
)


INSTRUMENT = InstrumentId(VenueId("synthetic"), "cash:btc-usd")
QUANTITY_SCALE = Scale(3)
PRICE_SCALE = Scale(2)
DECLARED_CAPABILITY_KEYS = tuple(value.value for value in OrderCapabilityKey)


def intent(
    *,
    style: ExecutionStyle = ExecutionStyle.MARKET,
    constraint: PriceConstraint | None = None,
    tif: TimeInForce = TimeInForce.DAY,
    reduce_only: bool = False,
    position_effect: PositionEffect = PositionEffect.AUTO,
) -> OrderIntent:
    return OrderIntent(
        instrument_id=INSTRUMENT,
        side=OrderSide.BUY,
        quantity=Quantity(2_000, QUANTITY_SCALE, str(INSTRUMENT)),
        execution_style=style,
        price_constraint=constraint,
        time_in_force=tif,
        reduce_only=reduce_only,
        position_effect=position_effect,
        urgency="normal",
        reason="rebalance",
        parent_id="order-plan-v1:sha256:" + "1" * 64,
    )


def limit_constraint() -> PriceConstraint:
    return PriceConstraint(
        limit_price=Price(3_000_000, PRICE_SCALE, str(INSTRUMENT), "USD")
    )


def trigger_constraint() -> PriceConstraint:
    return PriceConstraint(
        trigger_price=Price(2_900_000, PRICE_SCALE, str(INSTRUMENT), "USD")
    )


def stop_limit_constraint() -> PriceConstraint:
    return PriceConstraint(
        limit_price=Price(2_880_000, PRICE_SCALE, str(INSTRUMENT), "USD"),
        trigger_price=Price(2_900_000, PRICE_SCALE, str(INSTRUMENT), "USD"),
    )


def style_capabilities() -> tuple[OrderStyleCapability, ...]:
    return (
        OrderStyleCapability(
            ExecutionStyle.MARKET,
            (PriceConstraintShape.NONE,),
            (TimeInForce.DAY, TimeInForce.IOC),
        ),
        OrderStyleCapability(
            ExecutionStyle.LIMIT,
            (PriceConstraintShape.LIMIT,),
            (TimeInForce.DAY, TimeInForce.GTC, TimeInForce.GTX),
        ),
        OrderStyleCapability(
            ExecutionStyle.STOP,
            (PriceConstraintShape.TRIGGER,),
            (TimeInForce.DAY, TimeInForce.GTC),
        ),
        OrderStyleCapability(
            ExecutionStyle.STOP_LIMIT,
            (PriceConstraintShape.LIMIT_AND_TRIGGER,),
            (TimeInForce.DAY, TimeInForce.GTC),
        ),
    )


def capability_set(
    *,
    styles: tuple[OrderStyleCapability, ...] | None = None,
    supports_reduce_only: bool = True,
    position_effects: tuple[PositionEffect, ...] = (
        PositionEffect.AUTO,
        PositionEffect.OPEN,
        PositionEffect.CLOSE,
    ),
    declared_keys: tuple[str, ...] = DECLARED_CAPABILITY_KEYS,
) -> OrderCapabilitySet:
    return OrderCapabilitySet.create(
        capability_set_key="synthetic.order-capabilities.v1",
        capability_set_version=1,
        style_capabilities=style_capabilities() if styles is None else styles,
        supports_reduce_only=supports_reduce_only,
        supported_position_effects=position_effects,
        declared_capability_keys=declared_keys,
    )
