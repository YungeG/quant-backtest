from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import (
    ExecutionStyle,
    Price,
    PriceConstraint,
    Quantity,
    Scale,
    canonical_bytes,
)
from crypto_quant_trading import (
    MarketRuleEvaluator,
    MarketRuleIssueCode,
    OrderRuleSnapshot,
    QuantityLattice,
)
from tests.kernel.capabilities._fixtures import INSTRUMENT, PRICE_SCALE, intent
from tests.kernel.market_rules._fixtures import (
    evaluation_input,
    interval,
    lattice,
    limit_intent,
    limit_notional_evidence,
    order_with_intent,
    reference_notional_evidence,
    snapshot,
    timeline,
    translated_spec,
)


def _named_lattice(
    key: str, *, step_units: int, min_quantity_units: int
) -> QuantityLattice:
    value = lattice(
        step_units=step_units,
        min_quantity_units=min_quantity_units,
    )
    return QuantityLattice.create(
        instrument_id=value.instrument_id,
        lattice_key=key,
        lattice_version=1,
        atomic_scale=value.atomic_scale,
        step_units=value.step_units,
        buy_lot_units=value.buy_lot_units,
        sell_lot_units=value.sell_lot_units,
        min_quantity_units=value.min_quantity_units,
        min_notional=value.min_notional,
        odd_lot_close_permitted=value.odd_lot_close_permitted,
    )


def _style_snapshot(
    *,
    primary: QuantityLattice,
    market: QuantityLattice,
    max_limit: int | None = None,
    max_market: int | None = None,
) -> OrderRuleSnapshot:
    base = snapshot(quantity_lattice=primary)
    return OrderRuleSnapshot.create(
        component_ref=base.component_ref,
        instrument_id=base.instrument_id,
        session_id=base.session_id,
        session_state=base.session_state,
        quantity_lattice=primary,
        market_quantity_lattice=market,
        price_scale=base.price_scale,
        price_tick_units=base.price_tick_units,
        lower_price_limit=base.lower_price_limit,
        upper_price_limit=base.upper_price_limit,
        permitted_sides=base.permitted_sides,
        permitted_position_effects=base.permitted_position_effects,
        reduce_only_required=base.reduce_only_required,
        notional_rounding=base.notional_rounding,
        supplemental_decisions=base.supplemental_decisions,
        max_limit_order_quantity_units=max_limit,
        max_market_order_quantity_units=max_market,
    )


def _decision(style: ExecutionStyle, rules: OrderRuleSnapshot, units: int):
    limit_price = Price(3_000_000, PRICE_SCALE, str(INSTRUMENT), "USD")
    trigger_price = Price(2_900_000, PRICE_SCALE, str(INSTRUMENT), "USD")
    if style is ExecutionStyle.STOP_LIMIT:
        source_intent = replace(
            limit_intent(),
            execution_style=style,
            price_constraint=PriceConstraint(
                limit_price=limit_price,
                trigger_price=trigger_price,
            ),
        )
    elif style is ExecutionStyle.STOP:
        source_intent = intent(
            style=style,
            constraint=PriceConstraint(trigger_price=trigger_price),
        )
    else:
        source_intent = limit_intent() if style is ExecutionStyle.LIMIT else intent(style=style)
    source_intent = replace(
        source_intent,
        quantity=Quantity(units, Scale(3), str(INSTRUMENT)),
    )
    evidence = (
        limit_notional_evidence(source_intent)
        if style in {ExecutionStyle.LIMIT, ExecutionStyle.STOP_LIMIT}
        else reference_notional_evidence()
    )
    return MarketRuleEvaluator().evaluate(
        evaluation_input(
            spec=translated_spec(order_with_intent(source_intent)),
            notional_evidence=evidence,
        ),
        timeline(intervals=(interval(rule_snapshot=rules),)),
    )


def test_legacy_snapshot_bytes_and_hashes_remain_exact() -> None:
    no_caps = snapshot()
    with_caps = snapshot(
        max_limit_order_quantity_units=10,
        max_market_order_quantity_units=20,
    )

    assert no_caps.config_hash == (
        "sha256:fa4273119a0b6c4b445eeb55b111b5354f51bcd30153ac9fc47fa0e0ba7c0edc"
    )
    assert no_caps.snapshot_hash == (
        "sha256:bb698906ddea161ac22b9e828d70107508070e60f574830194e241b43d8c1dcf"
    )
    assert with_caps.config_hash == (
        "sha256:9adde02b4aa84a2bb563fbdd45f80fff91a6f2522169c19f046772c16eb86775"
    )
    assert with_caps.snapshot_hash == (
        "sha256:1a21799fa05ab3eaa66b4e59c68aebf5c824f8704e63f3b27b3f1d409a2cb408"
    )
    assert b"market_quantity_lattice" not in canonical_bytes(no_caps)
    assert b"market_quantity_lattice" not in canonical_bytes(with_caps)


def test_schema_v3_preserves_an_independent_market_lattice() -> None:
    primary = _named_lattice("limit-lattice", step_units=2, min_quantity_units=2)
    market = _named_lattice("market-lattice", step_units=3, min_quantity_units=3)

    rules = _style_snapshot(
        primary=primary,
        market=market,
        max_limit=10,
        max_market=9,
    )

    assert rules.config_payload()["schema_version"] == 3
    assert rules.market_quantity_lattice == market
    assert rules.max_market_order_quantity_units == 9
    assert b'"market_quantity_lattice"' in canonical_bytes(rules)


def test_limit_and_market_orders_use_their_own_quantity_lattices() -> None:
    limit_friendly = _style_snapshot(
        primary=_named_lattice("limit-any", step_units=1, min_quantity_units=1),
        market=_named_lattice("market-fives", step_units=5, min_quantity_units=5),
    )
    market_friendly = _style_snapshot(
        primary=_named_lattice("limit-fives", step_units=5, min_quantity_units=5),
        market=_named_lattice("market-any", step_units=1, min_quantity_units=1),
    )

    limit_approved = _decision(ExecutionStyle.LIMIT, limit_friendly, 3)
    stop_limit_approved = _decision(ExecutionStyle.STOP_LIMIT, limit_friendly, 3)
    market_rejected = _decision(ExecutionStyle.MARKET, limit_friendly, 3)
    stop_rejected = _decision(ExecutionStyle.STOP, limit_friendly, 3)
    limit_rejected = _decision(ExecutionStyle.LIMIT, market_friendly, 3)
    stop_limit_rejected = _decision(ExecutionStyle.STOP_LIMIT, market_friendly, 3)
    market_approved = _decision(ExecutionStyle.MARKET, market_friendly, 3)
    stop_approved = _decision(ExecutionStyle.STOP, market_friendly, 3)

    assert limit_approved.approval is not None
    assert stop_limit_approved.approval is not None
    assert market_approved.approval is not None
    assert stop_approved.approval is not None
    assert market_rejected.rejection is not None
    assert stop_rejected.rejection is not None
    assert limit_rejected.rejection is not None
    assert stop_limit_rejected.rejection is not None
    expected = [
        MarketRuleIssueCode.MINIMUM_QUANTITY,
        MarketRuleIssueCode.QUANTITY_STEP,
    ]
    assert [issue.code for issue in market_rejected.rejection.issues] == expected
    assert [issue.code for issue in stop_rejected.rejection.issues] == expected
    assert [issue.code for issue in limit_rejected.rejection.issues] == expected
    assert [issue.code for issue in stop_limit_rejected.rejection.issues] == expected
