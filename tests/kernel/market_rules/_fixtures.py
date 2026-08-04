from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import (
    ExecutionStyle,
    Order,
    OrderIntent,
    OrderSide,
    PositionEffect,
    Price,
    PriceConstraint,
    RoundingPolicy,
    Scale,
    SessionId,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    ExecutableOrderSpec,
    MarketSessionState,
    NotionalPriceBasis,
    OrderRuleEvaluationInput,
    OrderRuleInterval,
    OrderRuleNotionalEvidence,
    OrderRuleSnapshot,
    OrderRuleTimeline,
    OrderTranslator,
    ProfileComponentRef,
    ProfilePortType,
    QuantityLattice,
    SupplementalOrderRuleDecision,
)
from tests.kernel.capabilities._fixtures import INSTRUMENT, PRICE_SCALE, intent
from tests.kernel.translation._fixtures import approval, mapping, order


def translated_spec(subject: Order | None = None) -> ExecutableOrderSpec:
    subject = order() if subject is None else subject
    result = OrderTranslator().translate(
        subject,
        approval(subject),
        mapping(),
        UtcInstant(110),
    )
    assert result.executable_spec is not None
    return result.executable_spec


def order_with_intent(source_intent: OrderIntent) -> Order:
    return replace(order(), intent=source_intent)


def limit_intent(*, price_units: int = 3_000_000) -> OrderIntent:
    return intent(
        style=ExecutionStyle.LIMIT,
        constraint=PriceConstraint(
            limit_price=Price(price_units, PRICE_SCALE, str(INSTRUMENT), "USD")
        ),
        tif=TimeInForce.DAY,
    )


def component_ref() -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=ProfilePortType.ORDER_RULE_MODEL,
        component_key="synthetic.cash.order-rules.v1",
        component_version=1,
        component_digest="sha256:" + "7" * 64,
    )


def lattice(*, step_units: int = 1, min_quantity_units: int = 1) -> QuantityLattice:
    from crypto_quant_domain import Money

    return QuantityLattice.create(
        instrument_id=INSTRUMENT,
        lattice_key="synthetic.cash.btc-usd.quantity-lattice.v1",
        lattice_version=1,
        atomic_scale=Scale(3),
        step_units=step_units,
        buy_lot_units=step_units,
        sell_lot_units=step_units,
        min_quantity_units=min_quantity_units,
        min_notional=Money(1_000, Scale(2), "USD"),
        odd_lot_close_permitted=False,
    )


def supplemental_decisions(
    *, reject: bool = False, reverse: bool = False
) -> tuple[SupplementalOrderRuleDecision, ...]:
    values = (
        SupplementalOrderRuleDecision(
            rule_key="account_permission",
            approved=not reject,
            reason_code="allowed" if not reject else "account_blocked",
        ),
        SupplementalOrderRuleDecision(
            rule_key="instrument_trading_status",
            approved=True,
            reason_code="tradable",
        ),
    )
    return tuple(reversed(values)) if reverse else values


def snapshot(
    *,
    session_state: MarketSessionState = MarketSessionState.OPEN,
    quantity_lattice: QuantityLattice | None = None,
    price_tick_units: int = 5,
    lower_price_units: int | None = 2_000_000,
    upper_price_units: int | None = 4_000_000,
    permitted_sides: tuple[OrderSide, ...] = (OrderSide.BUY, OrderSide.SELL),
    permitted_position_effects: tuple[PositionEffect, ...] = (
        PositionEffect.AUTO,
        PositionEffect.OPEN,
        PositionEffect.CLOSE,
    ),
    reduce_only_required: bool = False,
    supplemental: tuple[SupplementalOrderRuleDecision, ...] | None = None,
) -> OrderRuleSnapshot:
    return OrderRuleSnapshot.create(
        component_ref=component_ref(),
        instrument_id=INSTRUMENT,
        session_id=SessionId("synthetic.cash", "2026-01-02.regular"),
        session_state=session_state,
        quantity_lattice=lattice() if quantity_lattice is None else quantity_lattice,
        price_scale=PRICE_SCALE,
        price_tick_units=price_tick_units,
        lower_price_limit=(
            None
            if lower_price_units is None
            else Price(lower_price_units, PRICE_SCALE, str(INSTRUMENT), "USD")
        ),
        upper_price_limit=(
            None
            if upper_price_units is None
            else Price(upper_price_units, PRICE_SCALE, str(INSTRUMENT), "USD")
        ),
        permitted_sides=permitted_sides,
        permitted_position_effects=permitted_position_effects,
        reduce_only_required=reduce_only_required,
        notional_rounding=RoundingPolicy.TOWARD_ZERO,
        supplemental_decisions=(
            supplemental_decisions() if supplemental is None else supplemental
        ),
    )


def interval(
    *,
    start: int = 0,
    stop: int | None = 200,
    rule_snapshot: OrderRuleSnapshot | None = None,
) -> OrderRuleInterval:
    return OrderRuleInterval.create(
        effective_from=UtcInstant(start),
        effective_to_exclusive=None if stop is None else UtcInstant(stop),
        snapshot=snapshot() if rule_snapshot is None else rule_snapshot,
    )


def timeline(
    *, intervals: tuple[OrderRuleInterval, ...] | None = None
) -> OrderRuleTimeline:
    return OrderRuleTimeline.create(
        timeline_key="synthetic.cash.btc-usd.order-rule-timeline.v1",
        timeline_version=1,
        instrument_id=INSTRUMENT,
        intervals=(interval(),) if intervals is None else intervals,
    )


def reference_notional_evidence(
    *, price_units: int = 3_000_000, available_at: int = 100
) -> OrderRuleNotionalEvidence:
    price = Price(price_units, PRICE_SCALE, str(INSTRUMENT), "USD")
    return OrderRuleNotionalEvidence(
        basis=NotionalPriceBasis.SUPPLIED_REFERENCE,
        price=price,
        source_hash=canonical_sha256(
            {
                "type": "synthetic_order_rule_reference_price",
                "price": price,
                "available_at": UtcInstant(available_at),
            }
        ),
        available_at=UtcInstant(available_at),
    )


def limit_notional_evidence(source_intent: OrderIntent) -> OrderRuleNotionalEvidence:
    assert source_intent.price_constraint is not None
    assert source_intent.price_constraint.limit_price is not None
    price = source_intent.price_constraint.limit_price
    return OrderRuleNotionalEvidence(
        basis=NotionalPriceBasis.LIMIT_CONSTRAINT,
        price=price,
        source_hash=canonical_sha256(price),
        available_at=None,
    )


def evaluation_input(
    *,
    spec: ExecutableOrderSpec | None = None,
    evaluated_at: int = 150,
    notional_evidence: OrderRuleNotionalEvidence | None = None,
) -> OrderRuleEvaluationInput:
    return OrderRuleEvaluationInput(
        executable_order_spec=translated_spec() if spec is None else spec,
        evaluated_at=UtcInstant(evaluated_at),
        notional_evidence=(
            reference_notional_evidence()
            if notional_evidence is None
            else notional_evidence
        ),
    )
