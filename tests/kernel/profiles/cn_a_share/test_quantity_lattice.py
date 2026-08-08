from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    InstrumentType,
    Money,
    OrderSide,
    PortfolioSnapshot,
    PositionBalance,
    PositionEffect,
    PositionBalanceKey,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    StrategySleeveId,
    TargetExposureFraction,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    ApprovedInstrumentTarget,
    ApprovedPortfolioTarget,
    InstrumentModel,
    InstrumentSizingInput,
    MarketRuleDataIntegrityCode,
    MarketRuleEvaluator,
    NetInstrumentTarget,
    PortfolioRiskAction,
    PortfolioRiskDecision,
    PortfolioRiskReasonCode,
    PlanningOmissionCode,
    PortfolioRiskScope,
    PositionSizer,
    PositionSizingAction,
    PositionSizingReasonCode,
    QuantityLattice,
    RebalanceCoordinator,
    ResidualPositionPolicy,
    SleeveTargetNotional,
    TargetValidity,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashQuantityLatticeModel,
    CnAShareQuantityLatticeFailure,
    CnAShareQuantityLatticeFailureCode,
    CnAShareQuantityLatticeQuery,
    CnAShareQuantityLatticeResolution,
)
from tests.kernel.allocation._fixtures import BTC
from tests.kernel.capabilities._fixtures import (
    INSTRUMENT as RULE_INSTRUMENT,
    intent as rule_intent,
)
from tests.kernel.market_rules._fixtures import (
    evaluation_input as rule_evaluation_input,
    interval as rule_interval,
    order_with_intent,
    snapshot as rule_snapshot,
    timeline as rule_timeline,
    translated_spec,
)
from tests.kernel.profiles.cn_a_share._fixtures import settlement_query
from tests.kernel.profiles.cn_a_share._quantity_lattice_fixtures import (
    coordinate_quantity_case,
    quantity_sizing_case,
)
from tests.kernel.rebalance._fixtures import (
    ACCOUNT,
    availability,
    policy as rebalance_policy,
    reservation_state,
    working_order,
    working_stream,
)
from tests.kernel.risk._fixtures import allocated_targets
from tests.kernel.sizing._fixtures import (
    BATCH_ID,
    approved_targets,
    resolved_mark,
    sizing_inputs,
    sizing_policy,
)


_NOTIONAL_SCALE = Scale(14)


def _approved_target(
    raw_units: int,
    quantity_scale: Scale = Scale(0),
) -> ApprovedPortfolioTarget:
    allocation = allocated_targets()
    risk_ref = approved_targets().policy_ref
    target_units = raw_units * 10 ** (15 - quantity_scale.places)
    target_notional = Money(target_units, _NOTIONAL_SCALE, "USD")
    allocation_nav = Money(abs(target_units) or 1, _NOTIONAL_SCALE, "USD")
    fraction = TargetExposureFraction(
        BTC,
        0 if raw_units == 0 else (1 if raw_units > 0 else -1) * 10**12,
        Scale(12),
    )
    sleeve = SleeveTargetNotional(
        strategy_id="g08c-fixture",
        sleeve_id=StrategySleeveId("g08c.primary"),
        instrument_id=BTC,
        target_fraction=fraction,
        allocation_nav=allocation_nav,
        target_notional=target_notional,
    )
    source_target = NetInstrumentTarget(
        instrument_id=BTC,
        valuation_currency=allocation.valuation_currency,
        target_notional=target_notional,
        sleeve_attributions=(sleeve,),
    )
    approved = ApprovedInstrumentTarget(source_target, target_notional)
    limit = Money(abs(target_units) + 1, _NOTIONAL_SCALE, "USD")
    gross = Money(abs(target_units), _NOTIONAL_SCALE, "USD")
    decisions = (
        PortfolioRiskDecision(
            PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
            PortfolioRiskAction.APPROVE,
            PortfolioRiskReasonCode.WITHIN_LIMIT,
            "g08c.target",
            risk_ref,
            target_notional,
            target_notional,
            limit,
            BTC,
        ),
        PortfolioRiskDecision(
            PortfolioRiskScope.GROSS_EXPOSURE,
            PortfolioRiskAction.APPROVE,
            PortfolioRiskReasonCode.WITHIN_LIMIT,
            "g08c.gross",
            risk_ref,
            gross,
            gross,
            limit,
            None,
        ),
        PortfolioRiskDecision(
            PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
            PortfolioRiskAction.APPROVE,
            PortfolioRiskReasonCode.WITHIN_LIMIT,
            "g08c.net",
            risk_ref,
            target_notional,
            target_notional,
            limit,
            None,
        ),
    )
    return ApprovedPortfolioTarget.create(
        approved_at=allocation.valuation_time,
        source_allocation=allocation,
        policy_ref=risk_ref,
        targets=(approved,),
        decisions=decisions,
    )


def _sizing_outcome(
    current_units: int,
    raw_units: int,
    *,
    buy_lot_units: int = 100,
    sell_lot_units: int = 100,
    whole_sell_residual_permitted: bool = True,
    residual_policy: ResidualPositionPolicy = ResidualPositionPolicy.CLOSE_IF_PERMITTED,
    atomic_scale: Scale = Scale(0),
):
    lattice = QuantityLattice.create(
        instrument_id=BTC,
        lattice_key="g08c.position-relative.v1",
        lattice_version=1,
        atomic_scale=atomic_scale,
        step_units=1,
        buy_lot_units=buy_lot_units,
        sell_lot_units=sell_lot_units,
        min_quantity_units=0,
        min_notional=Money(0, _NOTIONAL_SCALE, "USD"),
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=whole_sell_residual_permitted,
    )
    outcome = PositionSizer().materialize(
        approved_target=_approved_target(raw_units, atomic_scale),
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(
            residual=residual_policy,
            rounding=RoundingPolicy.TOWARD_ZERO,
            price_purpose=PricePurpose.VALUATION,
        ),
        inputs=(
            InstrumentSizingInput(
                instrument_id=BTC,
                mark=resolved_mark(BTC, price_units=1_000),
                current_quantity=Quantity(current_units, atomic_scale, str(BTC)),
                lattice=lattice,
            ),
        ),
    )
    return outcome


def _sizing_decision(current_units: int, raw_units: int, **kwargs):
    outcome = _sizing_outcome(current_units, raw_units, **kwargs)
    assert outcome.failure is None
    assert outcome.normalized_target is not None
    return outcome.normalized_target.targets[0].decision


def _snapshot(
    current_units: int,
    quantity_scale: Scale,
    *,
    timestamp: int = 200,
) -> PortfolioSnapshot:
    zero = Money(0, Scale(2), "USD")
    positions = (
        (
            PositionBalance(
                PositionBalanceKey(ACCOUNT, BTC.venue, BTC),
                Quantity(current_units, quantity_scale, str(BTC)),
                (),
            ),
        )
        if current_units
        else ()
    )
    return PortfolioSnapshot(
        account_id=ACCOUNT,
        timestamp=UtcInstant(timestamp),
        reporting_currency=CurrencyId("USD"),
        cash=(),
        positions=positions,
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=Money(100_000, Scale(2), "USD"),
        valuation_marks=(),
        journal_state_hash="sha256:" + "1" * 64,
        valuation_mark_set_hash=canonical_sha256(()),
        valuation_staleness_report_hash="sha256:" + "2" * 64,
        currency_valuation_graph_hash="sha256:" + "3" * 64,
    )


def _coordinate(
    target,
    current_units: int,
    *,
    prior_plan=None,
    streams=(),
    as_of: int = 200,
    valid_until: int = 300,
):
    quantity_scale = target.targets[0].decision.final_quantity.scale
    snapshot = _snapshot(current_units, quantity_scale)
    reservations = reservation_state(streams)
    return RebalanceCoordinator().coordinate(
        target=target,
        target_validity=TargetValidity(
            normalized_target_id=target.normalized_target_id,
            normalized_target_hash=target.normalized_target_hash,
            valid_from=target.materialized_at,
            valid_until=UtcInstant(valid_until),
        ),
        portfolio_snapshot=snapshot,
        working_orders=streams,
        reservations=reservations,
        availability=availability(snapshot, reservations),
        policy=rebalance_policy(),
        as_of=UtcInstant(as_of),
        prior_plan=prior_plan,
    )


def test_quantity_lattice_schema_v1_bytes_and_hash_remain_unchanged() -> None:
    instrument = settlement_query(OrderSide.BUY).instrument
    lattice = QuantityLattice.create(
        instrument_id=instrument.instrument_id,
        lattice_key="compat.quantity-lattice.v1",
        lattice_version=1,
        atomic_scale=Scale(0),
        step_units=1,
        buy_lot_units=100,
        sell_lot_units=100,
        min_quantity_units=0,
        min_notional=Money(0, Scale(2), "CNY"),
        odd_lot_close_permitted=True,
    )

    assert canonical_bytes(lattice) == (
        b'{"atomic_scale":0,"buy_lot_units":100,"config_hash":"sha256:'
        b'274d2b47f2cdd2e0830e6c5b08a6a42000b01851e56dcde16e879bb87eb24873",'
        b'"instrument_id":{"stable_key":"600000","type":"instrument_id",'
        b'"venue":"xshg"},"lattice_key":"compat.quantity-lattice.v1",'
        b'"lattice_version":1,"min_notional":{"currency":"CNY","scale":2,'
        b'"type":"money","units":0},"min_quantity_units":0,'
        b'"odd_lot_close_permitted":true,"schema_version":1,'
        b'"sell_lot_units":100,"step_units":1,"type":"quantity_lattice"}'
    )
    assert lattice.config_hash == (
        "sha256:274d2b47f2cdd2e0830e6c5b08a6a42000b01851e56dcde16e879bb87eb24873"
    )
    assert lattice.lattice_hash == (
        "sha256:7529cc271e5252bfb31ff0b8bf1b2c8bf9ca65dc96e2acc73adcdfe44c89a759"
    )


@pytest.mark.parametrize(
    ("current", "raw", "final", "applied_lot", "residual_sale", "odd_close"),
    (
        (0, 0, 0, 1, False, False),
        (0, 251, 200, 100, False, False),
        (55, 251, 155, 100, False, False),
        (500, 451, 400, 100, False, False),
        (299, 200, 200, 100, True, False),
        (299, 100, 100, 100, True, False),
        (299, 199, 199, 100, False, False),
        (299, 298, 200, 100, True, False),
        (299, 198, 100, 100, True, False),
        (299, 98, 0, 100, False, True),
        (101, 100, 100, 100, True, False),
        (200, 199, 100, 100, False, False),
        (200, 0, 0, 100, False, False),
        (55, 0, 0, 100, False, True),
    ),
)
def test_position_relative_sizing_preserves_whole_sell_residual(
    current: int,
    raw: int,
    final: int,
    applied_lot: int,
    residual_sale: bool,
    odd_close: bool,
) -> None:
    decision = _sizing_decision(current, raw)

    assert decision.current_quantity.units == current
    assert decision.raw_quantity.units == raw
    assert decision.final_quantity.units == final
    assert decision.residual_quantity.units == raw - final
    assert decision.applied_lot_units == applied_lot
    assert (
        PositionSizingAction.SELL_RESIDUAL_COMPONENT in decision.actions
    ) is residual_sale
    assert (
        PositionSizingReasonCode.SELL_RESIDUAL_COMPONENT_PERMITTED
        in decision.reason_codes
    ) is residual_sale
    assert (PositionSizingAction.ODD_LOT_CLOSE in decision.actions) is odd_close


@pytest.mark.parametrize(
    ("current", "raw", "expected", "residual_sale"),
    (
        (55, 251, 155, False),
        (500, 451, 450, False),
        (55, 49, 45, False),
        (55, 50, 50, True),
        (55, 5, 5, False),
        (55, 55, 55, False),
        (55, 56, 55, False),
    ),
)
def test_unequal_buy_sell_lots_choose_delta_side_reachability(
    current: int,
    raw: int,
    expected: int,
    residual_sale: bool,
) -> None:
    decision = _sizing_decision(
        current,
        raw,
        buy_lot_units=100,
        sell_lot_units=10,
    )

    assert decision.final_quantity.units == expected
    assert (
        PositionSizingAction.SELL_RESIDUAL_COMPONENT in decision.actions
    ) is residual_sale


@pytest.mark.parametrize(
    ("current", "raw", "expected"),
    (
        (-55, -251, -250),
        (-251, -55, -50),
        (55, -251, -250),
        (-55, 251, 200),
        (55, 251, 200),
    ),
)
def test_negative_cross_zero_and_disabled_capability_keep_legacy_static_path(
    current: int,
    raw: int,
    expected: int,
) -> None:
    decision = _sizing_decision(
        current,
        raw,
        buy_lot_units=100,
        sell_lot_units=10,
        whole_sell_residual_permitted=(current != 55 or raw != 251),
    )

    assert decision.final_quantity.units == expected
    assert PositionSizingAction.SELL_RESIDUAL_COMPONENT not in decision.actions


def test_lot_reason_uses_raw_direction_without_changing_legacy_evidence() -> None:
    sub_lot_buy = _sizing_decision(
        55,
        56,
        buy_lot_units=100,
        sell_lot_units=10,
    )
    legacy_negative = _sizing_decision(
        -251,
        -55,
        buy_lot_units=100,
        sell_lot_units=10,
    )
    legacy_positive = _sizing_decision(
        500,
        451,
        buy_lot_units=100,
        sell_lot_units=10,
        whole_sell_residual_permitted=False,
    )

    assert PositionSizingReasonCode.BUY_LOT in sub_lot_buy.reason_codes
    assert PositionSizingReasonCode.SELL_LOT in legacy_negative.reason_codes
    assert PositionSizingReasonCode.BUY_LOT in legacy_positive.reason_codes


def test_hold_dust_preserves_quantity_but_changes_policy_and_target_identity() -> None:
    close = _sizing_outcome(
        55,
        251,
        residual_policy=ResidualPositionPolicy.CLOSE_IF_PERMITTED,
    )
    hold = _sizing_outcome(
        55,
        251,
        residual_policy=ResidualPositionPolicy.HOLD_DUST,
    )

    assert close.normalized_target is not None
    assert hold.normalized_target is not None
    close_decision = close.normalized_target.targets[0].decision
    hold_decision = hold.normalized_target.targets[0].decision
    assert close_decision.final_quantity == hold_decision.final_quantity
    assert close_decision.final_quantity.units == 155
    assert close_decision.policy_hash != hold_decision.policy_hash
    assert (
        close.normalized_target.normalized_target_id
        != hold.normalized_target.normalized_target_id
    )


def test_position_relative_materialization_is_input_order_invariant() -> None:
    approved = approved_targets()
    reversed_approved = replace(
        approved,
        targets=tuple(reversed(approved.targets)),
    )
    inputs = tuple(
        replace(
            value,
            lattice=QuantityLattice.create(
                instrument_id=value.instrument_id,
                lattice_key=f"g08c.parity:{value.instrument_id}",
                lattice_version=1,
                atomic_scale=value.current_quantity.scale,
                step_units=1,
                buy_lot_units=100,
                sell_lot_units=100,
                min_quantity_units=0,
                min_notional=Money(0, _NOTIONAL_SCALE, "USD"),
                odd_lot_close_permitted=True,
                whole_sell_residual_permitted=True,
            ),
        )
        for value in sizing_inputs()
    )
    policy = sizing_policy(
        residual=ResidualPositionPolicy.HOLD_DUST,
        rounding=RoundingPolicy.TOWARD_ZERO,
    )

    forward = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=policy,
        inputs=inputs,
    )
    reversed_result = PositionSizer().materialize(
        approved_target=reversed_approved,
        source_decision_batch_id=BATCH_ID,
        policy=policy,
        inputs=tuple(reversed(inputs)),
    )

    assert forward.normalized_target is not None
    assert reversed_result.normalized_target is not None
    assert forward.normalized_target == reversed_result.normalized_target


def test_residual_fail_is_atomic_for_unreachable_position_relative_target() -> None:
    legal = _sizing_outcome(
        299,
        200,
        residual_policy=ResidualPositionPolicy.FAIL,
    )
    unreachable = _sizing_outcome(
        299,
        298,
        residual_policy=ResidualPositionPolicy.FAIL,
    )

    assert legal.failure is None
    assert legal.normalized_target is not None
    assert unreachable.normalized_target is None
    assert unreachable.failure is not None
    assert unreachable.failure.code.value == "residual_not_permitted"


@pytest.mark.parametrize(
    "overrides",
    (
        {"sell_lot_units": None},
        {"odd_lot_close_permitted": False},
        {"min_quantity_units": 1},
        {"min_notional": Money(1, Scale(2), "CNY")},
    ),
)
def test_schema_v2_requires_explicit_sell_lot_odd_close_and_zero_minimums(
    overrides: dict[str, object],
) -> None:
    instrument = settlement_query(OrderSide.BUY).instrument
    values: dict[str, object] = {
        "instrument_id": instrument.instrument_id,
        "lattice_key": "invalid.position-relative.v1",
        "lattice_version": 1,
        "atomic_scale": Scale(0),
        "step_units": 1,
        "buy_lot_units": 100,
        "sell_lot_units": 100,
        "min_quantity_units": 0,
        "min_notional": Money(0, Scale(2), "CNY"),
        "odd_lot_close_permitted": True,
        "whole_sell_residual_permitted": True,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match="whole sell residual"):
        QuantityLattice.create(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("current", "raw", "side", "quantity", "position_effect"),
    (
        (0, 251, OrderSide.BUY, 200, PositionEffect.OPEN),
        (55, 251, OrderSide.BUY, 100, PositionEffect.OPEN),
        (299, 200, OrderSide.SELL, 99, PositionEffect.CLOSE),
        (299, 100, OrderSide.SELL, 199, PositionEffect.CLOSE),
        (101, 100, OrderSide.SELL, 1, PositionEffect.CLOSE),
        (55, 0, OrderSide.SELL, 55, PositionEffect.CLOSE),
    ),
)
def test_rebalance_consumes_normalized_quantity_without_second_rounding(
    current: int,
    raw: int,
    side: OrderSide,
    quantity: int,
    position_effect: PositionEffect,
) -> None:
    outcome = _sizing_outcome(current, raw)
    assert outcome.normalized_target is not None

    coordinated = _coordinate(outcome.normalized_target, current)

    assert coordinated.decision is not None
    assert len(coordinated.decision.plan.planned_orders) == 1
    planned = coordinated.decision.plan.planned_orders[0]
    assert planned.intent.side is side
    assert planned.intent.quantity.units == quantity
    assert planned.intent.position_effect is position_effect
    assert planned.intent.reduce_only is (side is OrderSide.SELL)
    assert planned.planned_delta.units == (
        quantity if side is OrderSide.BUY else -quantity
    )


@pytest.mark.parametrize(
    ("sizing_current", "raw", "changed_current"),
    (
        (299, 199, 298),
        (55, 251, 56),
    ),
)
def test_rebalance_does_not_replan_after_position_relative_evidence_changes(
    sizing_current: int,
    raw: int,
    changed_current: int,
) -> None:
    outcome = _sizing_outcome(sizing_current, raw)
    assert outcome.normalized_target is not None
    target = outcome.normalized_target
    baseline = _coordinate(target, sizing_current)
    assert baseline.decision is not None
    assert len(baseline.decision.plan.planned_orders) == 1

    changed = _coordinate(
        target,
        changed_current,
        prior_plan=baseline.decision.plan,
    )
    changed_without_prior = _coordinate(target, changed_current)

    assert changed.decision is not None
    assert not changed.decision.plan.planned_orders
    assert len(changed.decision.plan.omissions) == 1
    assert (
        changed.decision.plan.omissions[0].code
        is PlanningOmissionCode.POSITION_RELATIVE_REACHABILITY_STALE
    )
    assert changed_without_prior.decision is not None
    assert not changed_without_prior.decision.plan.planned_orders
    assert len(changed_without_prior.decision.plan.omissions) == 1
    assert (
        changed_without_prior.decision.plan.omissions[0].code
        is PlanningOmissionCode.POSITION_RELATIVE_REACHABILITY_STALE
    )


def test_legacy_signed_targets_do_not_enter_position_relative_stale_guard() -> None:
    cross_zero = _sizing_outcome(
        55,
        -251,
        buy_lot_units=100,
        sell_lot_units=10,
    )
    negative = _sizing_outcome(
        -55,
        -251,
        buy_lot_units=100,
        sell_lot_units=10,
    )
    assert cross_zero.normalized_target is not None
    assert negative.normalized_target is not None

    opened = _coordinate(cross_zero.normalized_target, 0)
    expanded = _coordinate(negative.normalized_target, -56)

    assert opened.decision is not None
    assert len(opened.decision.plan.planned_orders) == 1
    assert opened.decision.plan.planned_orders[0].planned_delta.units == -250
    assert expanded.decision is not None
    assert len(expanded.decision.plan.planned_orders) == 1
    assert expanded.decision.plan.planned_orders[0].planned_delta.units == -194


def test_position_relative_lifecycle_distinguishes_coverage_cancel_and_stale() -> None:
    outcome = _sizing_outcome(299, 199, atomic_scale=Scale(3))
    assert outcome.normalized_target is not None
    target = outcome.normalized_target
    order = working_order(
        "8",
        instrument_id=BTC,
        side=OrderSide.SELL,
        quantity_units=100,
        parent_id=target.normalized_target_id,
    )
    active_stream = working_stream(order)
    partial_stream = working_stream(order, partial_fill_units=1)
    cancel_stream = working_stream(
        order,
        partial_fill_units=1,
        cancel_requested=True,
    )
    unrelated_order = working_order(
        "9",
        instrument_id=BTC,
        side=OrderSide.SELL,
        quantity_units=98,
    )
    unrelated_stream = working_stream(unrelated_order)

    active = _coordinate(target, 299, streams=(active_stream,))
    partial = _coordinate(target, 298, streams=(partial_stream,))
    cancelling = _coordinate(target, 298, streams=(cancel_stream,))
    expired = _coordinate(
        target,
        299,
        streams=(active_stream,),
        as_of=301,
        valid_until=300,
    )
    unrelated = _coordinate(target, 298, streams=(unrelated_stream,))

    assert active.decision is not None
    assert active.decision.plan.omissions[0].code is PlanningOmissionCode.ALREADY_COVERED
    assert partial.decision is not None
    assert partial.decision.plan.omissions[0].code is PlanningOmissionCode.ALREADY_COVERED
    assert cancelling.decision is not None
    assert (
        cancelling.decision.plan.omissions[0].code
        is PlanningOmissionCode.CANCELLATION_PENDING
    )
    assert expired.decision is not None
    assert expired.decision.plan.omissions[0].code is PlanningOmissionCode.TARGET_EXPIRED
    assert unrelated.decision is not None
    assert (
        unrelated.decision.plan.omissions[0].code
        is PlanningOmissionCode.POSITION_RELATIVE_REACHABILITY_STALE
    )
    assert not unrelated.decision.plan.planned_orders


def test_unchanged_or_reached_position_relative_target_is_not_stale() -> None:
    outcome = _sizing_outcome(299, 199)
    assert outcome.normalized_target is not None
    target = outcome.normalized_target
    baseline = _coordinate(target, 299)
    assert baseline.decision is not None

    unchanged = _coordinate(target, 299, prior_plan=baseline.decision.plan)
    reached = _coordinate(target, 199, prior_plan=baseline.decision.plan)

    assert unchanged.decision is not None
    assert len(unchanged.decision.plan.planned_orders) == 1
    assert reached.decision is not None
    assert not reached.decision.plan.planned_orders
    assert len(reached.decision.plan.omissions) == 1
    assert reached.decision.plan.omissions[0].code is PlanningOmissionCode.ALREADY_COVERED


@pytest.mark.parametrize(
    ("quantity_units", "approved"),
    ((100, True), (99, False), (199, False), (1, False), (55, False)),
)
def test_market_rule_evaluator_requires_g08d_position_evidence_for_odd_sell(
    quantity_units: int,
    approved: bool,
) -> None:
    lattice = QuantityLattice.create(
        instrument_id=RULE_INSTRUMENT,
        lattice_key="g08c.market-rule-limit.v1",
        lattice_version=1,
        atomic_scale=Scale(3),
        step_units=1,
        buy_lot_units=100,
        sell_lot_units=100,
        min_quantity_units=0,
        min_notional=Money(0, Scale(2), "USD"),
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=True,
    )
    source_intent = replace(
        rule_intent(),
        side=OrderSide.SELL,
        quantity=Quantity(quantity_units, Scale(3), str(RULE_INSTRUMENT)),
        reduce_only=True,
        position_effect=PositionEffect.CLOSE,
    )
    request = rule_evaluation_input(
        spec=translated_spec(order_with_intent(source_intent))
    )
    rules = rule_timeline(
        intervals=(
            rule_interval(
                rule_snapshot=rule_snapshot(quantity_lattice=lattice)
            ),
        )
    )

    decision = MarketRuleEvaluator().evaluate(request, rules)

    assert (decision.approval is not None) is approved
    if approved:
        assert decision.rejection is None
    else:
        assert decision.data_integrity_failure is not None
        assert (
            decision.data_integrity_failure.code
            is MarketRuleDataIntegrityCode.MISSING_POSITION_EVIDENCE
        )


def test_public_resolution_and_failure_reject_substituted_template_metadata() -> None:
    instrument = settlement_query(OrderSide.BUY).instrument
    model = CnAShareCashQuantityLatticeModel(VenueId("xshg"), Scale(2))
    outcome = model.resolve_instrument(CnAShareQuantityLatticeQuery(instrument))
    assert outcome.result is not None
    substituted = QuantityLattice.create(
        instrument_id=instrument.instrument_id,
        lattice_key="substituted.v1",
        lattice_version=1,
        atomic_scale=Scale(0),
        step_units=1,
        buy_lot_units=7,
        sell_lot_units=7,
        min_quantity_units=0,
        min_notional=Money(0, Scale(2), "USD"),
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=True,
    )

    with pytest.raises(ValueError, match="A-share cash template"):
        CnAShareQuantityLatticeResolution(
            VenueId("xshg"),
            instrument.instrument_id,
            substituted,
        )
    with pytest.raises(ValueError, match="subject_key"):
        CnAShareQuantityLatticeFailure(
            CnAShareQuantityLatticeFailureCode.UNSUPPORTED_CURRENCY,
            VenueId("xshg"),
            instrument.instrument_id,
            "venue:xshg",
        )


@pytest.mark.parametrize(
    ("current", "raw", "final"),
    (
        (0, 0, 0),
        (0, 251, 200),
        (55, 251, 155),
        (500, 451, 400),
        (299, 200, 200),
        (299, 100, 100),
        (299, 199, 199),
        (299, 298, 200),
        (299, 198, 100),
        (299, 98, 0),
        (101, 100, 100),
        (200, 199, 100),
        (200, 0, 0),
        (55, 0, 0),
    ),
)
def test_concrete_cny_fixture_exact_covers_position_relative_arithmetic(
    current: int,
    raw: int,
    final: int,
) -> None:
    case = quantity_sizing_case(current_units=current, raw_units=raw)

    assert case.outcome.failure is None
    assert case.outcome.normalized_target is not None
    decision = case.outcome.normalized_target.targets[0].decision
    assert decision.current_quantity.units == current
    assert decision.raw_quantity.units == raw
    assert decision.final_quantity.units == final


def test_xshg_xshe_share_economics_but_not_component_or_result_identity() -> None:
    xshg = quantity_sizing_case(venue="xshg", current_units=299, raw_units=200)
    xshe = quantity_sizing_case(venue="xshe", current_units=299, raw_units=200)
    assert xshg.outcome.normalized_target is not None
    assert xshe.outcome.normalized_target is not None
    xshg_decision = xshg.outcome.normalized_target.targets[0].decision
    xshe_decision = xshe.outcome.normalized_target.targets[0].decision
    xshg_plan = coordinate_quantity_case(xshg)
    xshe_plan = coordinate_quantity_case(xshe)
    assert xshg_plan.decision is not None
    assert xshe_plan.decision is not None

    assert xshg_decision.final_quantity.units == xshe_decision.final_quantity.units
    assert xshg_decision.final_quantity.units == 200
    assert xshg.model.component_ref.component_digest == (
        "sha256:fab920b0ad96ead710bfe34de9a5dd5c1167bf34c60046bf7d305650d4f24412"
    )
    assert xshe.model.component_ref.component_digest == (
        "sha256:03902ce5aa70e65560a5ea4049402cf67024d1a5d8c3eae72f5bdc21bd7e6c86"
    )
    assert xshg.resolution.quantity_lattice.lattice_hash == (
        "sha256:5035652be70b3e10e9d59aac126eaecdd0b091be44e3e1ee3258c2aca35777b5"
    )
    assert xshe.resolution.quantity_lattice.lattice_hash == (
        "sha256:f470c21d0d8392c70ee28f0057cfeab12d991263da9a215509447b54fc10c34c"
    )
    assert xshg_decision.decision_hash != xshe_decision.decision_hash
    assert (
        xshg.outcome.normalized_target.normalized_target_id
        != xshe.outcome.normalized_target.normalized_target_id
    )
    assert xshg_plan.decision.plan.plan_hash != xshe_plan.decision.plan.plan_hash
    assert xshg_plan.decision.plan.planned_orders[0].intent.quantity.units == 99
    assert xshe_plan.decision.plan.planned_orders[0].intent.quantity.units == 99


def test_model_failure_precedence_and_subject_keys_are_stable() -> None:
    instrument = settlement_query(OrderSide.BUY).instrument
    model = CnAShareCashQuantityLatticeModel(VenueId("xshg"), Scale(2))
    cross_venue = replace(
        instrument,
        instrument_id=InstrumentId(VenueId("xshe"), "opaque"),
        instrument_type=InstrumentType.SPOT,
        quote_currency=CurrencyId("USD"),
        settlement_currency=CurrencyId("USD"),
    )
    wrong_type = replace(instrument, instrument_type=InstrumentType.SPOT)
    wrong_currency = replace(
        instrument,
        quote_currency=CurrencyId("USD"),
    )

    venue = model.resolve_instrument(CnAShareQuantityLatticeQuery(cross_venue))
    instrument_failure = model.resolve_instrument(
        CnAShareQuantityLatticeQuery(wrong_type)
    )
    currency = model.resolve_instrument(
        CnAShareQuantityLatticeQuery(wrong_currency)
    )

    assert venue.failure is not None
    assert venue.failure.code is CnAShareQuantityLatticeFailureCode.UNSUPPORTED_VENUE
    assert venue.failure.subject_key == "venue:xshe"
    assert instrument_failure.failure is not None
    assert (
        instrument_failure.failure.code
        is CnAShareQuantityLatticeFailureCode.UNSUPPORTED_INSTRUMENT
    )
    assert instrument_failure.failure.subject_key == "instrument:xshg:600000"
    assert currency.failure is not None
    assert (
        currency.failure.code
        is CnAShareQuantityLatticeFailureCode.UNSUPPORTED_CURRENCY
    )
    assert currency.failure.subject_key == "instrument:xshg:600000"
    assert venue.component_ref == model.component_ref


def test_model_uses_opaque_instrument_identity_not_symbol_allowlists() -> None:
    base = settlement_query(OrderSide.BUY).instrument
    xshg = CnAShareCashQuantityLatticeModel(VenueId("xshg"), Scale(2))
    xshe = CnAShareCashQuantityLatticeModel(VenueId("xshe"), Scale(2))
    xshg_values = (
        replace(base, instrument_id=InstrumentId(VenueId("xshg"), "opaque-a")),
        replace(base, instrument_id=InstrumentId(VenueId("xshg"), "000001")),
    )
    xshe_values = (
        replace(base, instrument_id=InstrumentId(VenueId("xshe"), "opaque-b")),
        replace(base, instrument_id=InstrumentId(VenueId("xshe"), "600000")),
    )

    xshg_results = (
        xshg.resolve_instrument(CnAShareQuantityLatticeQuery(xshg_values[0])).result,
        xshg.resolve_instrument(CnAShareQuantityLatticeQuery(xshg_values[1])).result,
    )
    xshe_results = (
        xshe.resolve_instrument(CnAShareQuantityLatticeQuery(xshe_values[0])).result,
        xshe.resolve_instrument(CnAShareQuantityLatticeQuery(xshe_values[1])).result,
    )

    assert xshg_results[0] is not None
    assert xshg_results[1] is not None
    assert xshe_results[0] is not None
    assert xshe_results[1] is not None
    assert xshg.component_ref.component_digest != xshe.component_ref.component_digest
    assert xshg_results[0] is not None
    assert xshe_results[0] is not None
    assert (
        xshg_results[0].quantity_lattice.lattice_hash
        != xshe_results[0].quantity_lattice.lattice_hash
    )


def test_concrete_model_returns_position_relative_schema_v2_lattice() -> None:
    instrument = settlement_query(OrderSide.BUY).instrument
    model = CnAShareCashQuantityLatticeModel(VenueId("xshg"), Scale(2))

    outcome = model.resolve_instrument(CnAShareQuantityLatticeQuery(instrument))

    assert isinstance(model, InstrumentModel)
    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.instrument_id == instrument.instrument_id
    lattice = outcome.result.quantity_lattice
    assert lattice.whole_sell_residual_permitted
    assert lattice.config_payload()["schema_version"] == 2
    assert lattice.buy_lot_units == 100
    assert lattice.sell_lot_units == 100
    assert lattice.atomic_scale == Scale(0)
    assert lattice.min_quantity_units == 0
    assert lattice.min_notional == Money(0, Scale(2), "CNY")
    failure_codes = (
        CnAShareQuantityLatticeFailureCode.UNSUPPORTED_VENUE.value,
        CnAShareQuantityLatticeFailureCode.UNSUPPORTED_INSTRUMENT.value,
        CnAShareQuantityLatticeFailureCode.UNSUPPORTED_CURRENCY.value,
    )
    assert failure_codes == (
        "unsupported_venue",
        "unsupported_instrument",
        "unsupported_currency",
    )
