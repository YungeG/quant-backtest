from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    DeterministicBarEngine,
    EngineFailureCode,
    EngineStage,
    PrecomputedTargetStream,
    ResolvedDecisionSnapshotRefreshPlanV1,
    ResolvedPortfolioDecisionCycleV2,
    TimelineEvent,
    TimelineSegment,
)
from crypto_quant_domain import (
    OrderSide,
    PricePurpose,
    QuantizationPolicy,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    CurrencyValuationGraph,
    PortfolioOrderPlanV2,
    PortfolioOrderSizerV1,
    PortfolioRebalanceCoordinatorV2,
    PortfolioRebalanceExecutionPolicyV1,
    PortfolioSnapshotRefreshInputV1,
    PortfolioSnapshotRefresherV1,
    PortfolioSnapshotRefreshPolicyV1,
    ResourceReservationBook,
)

from tests.kernel.portfolio.test_portfolio_order_sizing import _candidate
from tests.runtime.engine._fixtures import (
    MONEY_SCALE,
    TARGET_TIME,
    bar_event,
    execution_case,
    target_event,
    target_payload,
    valuation_mark,
)


def _portfolio_policy() -> PortfolioRebalanceExecutionPolicyV1:
    return PortfolioRebalanceExecutionPolicyV1(
        "equity.cn_a_share.portfolio.rebalance-execution.v1", 1
    )


def _empty_order_plan(cycle, policy):
    return PortfolioOrderPlanV2.create(
        source_normalized_target_id=cycle.target_validity.normalized_target_id,
        source_normalized_target_hash=cycle.target_validity.normalized_target_hash,
        decision_time=cycle.schedule.decision_time,
        policy_hash=policy.policy_hash,
        sizing_evidence_hash=canonical_sha256(()),
        cancellation_intents=(),
        planned_orders=(),
        cancel_replacements=(),
        omission_evidence_hashes=(),
    )


def _refresh_plan(*, marks=(), decision_time=TARGET_TIME, ordinal=0):
    case = execution_case()
    position_quantization = next(
        value.quantization_policy
        for value in case.snapshot_plan.valuations
        if value.quantization_policy is not None
    )
    return ResolvedDecisionSnapshotRefreshPlanV1(
        decision_ordinal=ordinal,
        occurred_at=SimulationInstant(
            decision_time,
            TimelinePhase(30, "decision_snapshot"),
            SourceSequence(0),
        ),
        policy=PortfolioSnapshotRefreshPolicyV1(
            policy_key="equity.cn_a_share.portfolio.snapshot-refresh.v1",
            policy_version=1,
            price_purpose=PricePurpose.VALUATION,
        ),
        resolved_marks=marks,
        currency_valuation_graph=CurrencyValuationGraph(
            valuation_at=decision_time,
            price_purpose=PricePurpose.VALUATION,
            edges=(),
        ),
        reporting_currency=case.snapshot_plan.reporting_currency,
        quantization_policy=QuantizationPolicy(
            version="decision-snapshot.validation-fixture.v1",
            target_scale=MONEY_SCALE,
            rounding=position_quantization.rounding,
        ),
    )


def test_v2_cycle_requires_snapshot_refresh_plan() -> None:
    cycle = execution_case().decision_cycles[0]

    phase3_policy = _portfolio_policy()
    with pytest.raises(TypeError, match="snapshot_refresh_plan"):
        ResolvedPortfolioDecisionCycleV2(
            schedule=cycle.schedule,
            allocations=cycle.allocations,
            target_notional_scale=cycle.target_notional_scale,
            risk_policy=cycle.risk_policy,
            sizing_policy=cycle.sizing_policy,
            sizing_inputs=cycle.sizing_inputs,
            target_validity=cycle.target_validity,
            rebalance_policy=cycle.rebalance_policy,
            planning_at=cycle.planning_at,
            admissions=cycle.admissions,
            snapshot_refresh_plan=None,
            portfolio_rebalance_policy=phase3_policy,
            portfolio_order_plan=_empty_order_plan(cycle, phase3_policy),
        )


@pytest.mark.parametrize(
    "marks",
    (
        (valuation_mark(resolved_at=UtcInstant(99)),),
        (
            replace(
                valuation_mark(),
                price_purpose=PricePurpose.EXECUTION_REFERENCE,
            ),
        ),
        (valuation_mark(), valuation_mark()),
    ),
)
def test_refresh_plan_rejects_non_authoritative_mark_sets(marks) -> None:
    with pytest.raises(ValueError, match="resolved marks"):
        _refresh_plan(marks=marks)


def test_input_construction_failure_is_structured_and_atomic() -> None:
    case = execution_case()
    cycle = case.decision_cycles[0]
    phase3_policy = _portfolio_policy()
    portfolio_cycle = ResolvedPortfolioDecisionCycleV2(
        schedule=cycle.schedule,
        allocations=cycle.allocations,
        target_notional_scale=cycle.target_notional_scale,
        risk_policy=cycle.risk_policy,
        sizing_policy=cycle.sizing_policy,
        sizing_inputs=cycle.sizing_inputs,
        target_validity=cycle.target_validity,
        rebalance_policy=cycle.rebalance_policy,
        planning_at=cycle.planning_at,
        admissions=cycle.admissions,
        snapshot_refresh_plan=_refresh_plan(),
        portfolio_rebalance_policy=phase3_policy,
        portfolio_order_plan=_empty_order_plan(cycle, phase3_policy),
    )
    engine = DeterministicBarEngine()
    state = engine._initial_state(case)
    state.reservation_state = ResourceReservationBook("account:wrong").project((), ())
    snapshot = state.snapshot
    artifacts = tuple(state.financial_artifacts)

    outcome = engine._refresh_decision_snapshot(
        case, state, portfolio_cycle, decision_ordinal=0
    )

    assert outcome is not None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.SNAPSHOT_PROJECTION_FAILURE
    assert state.snapshot is snapshot
    assert tuple(state.financial_artifacts) == artifacts


def test_second_decision_refreshes_current_financial_and_resource_state() -> None:
    base_case = execution_case()
    engine = DeterministicBarEngine()
    state = engine._initial_state(base_case)
    first_cycle = base_case.decision_cycles[0]

    assert engine._decision_cycle(
        base_case,
        state,
        first_cycle,
        (TimelineEvent(TimelineSegment.ACTIVE_TRADING, target_event()),),
        0,
    ) is None
    assert engine._bar_execution(
        base_case,
        state,
        base_case.bar_executions[0],
        TimelineEvent(TimelineSegment.ACTIVE_TRADING, bar_event()),
    ) is None
    stale_snapshot_hash = canonical_sha256(state.snapshot)

    second_time = UtcInstant(250)
    candidate = target_payload(decision_time=250)
    candidate["expires_at"] = 290
    second_event = replace(
        target_event(),
        event_id="engine-target-250",
        event_time=second_time,
        available_time=second_time,
        source_sequence=SourceSequence(3),
        revision_id="rev-2",
        payload={"schema_version": 1, "candidate": candidate},
    )
    first_entry = first_cycle.schedule.entries[0]
    second_schedule = replace(
        first_cycle.schedule,
        decision_time=second_time,
        entries=(
            replace(
                first_entry,
                event_id=second_event.event_id,
                validation_context=replace(
                    first_entry.validation_context,
                    decision_time=second_time,
                ),
            ),
        ),
    )
    mark = valuation_mark(price_units=11_000, resolved_at=second_time)
    graph = CurrencyValuationGraph(
        valuation_at=second_time,
        price_purpose=PricePurpose.VALUATION,
        edges=(),
    )
    position_quantization = next(
        value.quantization_policy
        for value in base_case.snapshot_plan.valuations
        if value.quantization_policy is not None
    )
    quantization = QuantizationPolicy(
        version="decision-snapshot.engine-fixture.v1",
        target_scale=MONEY_SCALE,
        rounding=position_quantization.rounding,
    )
    policy = PortfolioSnapshotRefreshPolicyV1(
        policy_key="equity.cn_a_share.portfolio.snapshot-refresh.v1",
        policy_version=1,
        price_purpose=PricePurpose.VALUATION,
    )
    refresh_plan = ResolvedDecisionSnapshotRefreshPlanV1(
        decision_ordinal=1,
        occurred_at=SimulationInstant(
            second_time,
            TimelinePhase(30, "decision_snapshot"),
            SourceSequence(0),
        ),
        policy=policy,
        resolved_marks=(mark,),
        currency_valuation_graph=graph,
        reporting_currency=base_case.snapshot_plan.reporting_currency,
        quantization_policy=quantization,
    )
    refresh_input = PortfolioSnapshotRefreshInputV1(
        ledger_state=state.ledger_state,
        position_lot_books=tuple(state.lot_books.items()),
        settlement_state=state.settlement_state,
        reservation_state=state.reservation_state,
        working_orders=(),
        resolved_marks=(mark,),
        currency_valuation_graph=graph,
        reporting_currency=refresh_plan.reporting_currency,
        quantization_policy=quantization,
        timestamp=second_time,
    )
    expected_snapshot = PortfolioSnapshotRefresherV1(policy).refresh(refresh_input)
    allocation = replace(
        first_cycle.allocations[0],
        valuation_time=second_time,
        allocation_nav=expected_snapshot.equity,
        source_portfolio_snapshot_hash=canonical_sha256(expected_snapshot),
    )
    phase3_policy = _portfolio_policy()
    sizing_candidates = ()
    resolved_order_plan = _empty_order_plan(first_cycle, phase3_policy)
    resolved_order_plan = replace(
        resolved_order_plan,
        decision_time=second_schedule.decision_time,
        plan_hash=canonical_sha256(
            {
                "schema_version": 1,
                "source_normalized_target_id": resolved_order_plan.source_normalized_target_id,
                "source_normalized_target_hash": resolved_order_plan.source_normalized_target_hash,
                "decision_time": second_schedule.decision_time,
                "policy_hash": resolved_order_plan.policy_hash,
                "sizing_evidence_hash": resolved_order_plan.sizing_evidence_hash,
                "cancellation_intents": (),
                "planned_orders": (),
                "cancel_replacements": (),
                "omission_evidence_hashes": (),
            }
        ),
    )
    second_cycle = ResolvedPortfolioDecisionCycleV2(
        schedule=second_schedule,
        allocations=(allocation,),
        target_notional_scale=first_cycle.target_notional_scale,
        risk_policy=first_cycle.risk_policy,
        sizing_policy=first_cycle.sizing_policy,
        sizing_inputs=tuple(
            replace(
                value,
                mark=mark,
                current_quantity=next(
                    position.quantity
                    for position in state.ledger_state.position_balances
                    if position.key.instrument_id == value.instrument_id
                ),
            )
            for value in first_cycle.sizing_inputs
        ),
        target_validity=first_cycle.target_validity,
        rebalance_policy=first_cycle.rebalance_policy,
        planning_at=UtcInstant(260),
        admissions=(),
        cancellation_plans=(),
        snapshot_refresh_plan=refresh_plan,
        portfolio_rebalance_policy=phase3_policy,
        portfolio_order_plan=resolved_order_plan,
        portfolio_sizing_candidates=sizing_candidates,
    )
    case = replace(
        base_case,
        target_stream=PrecomputedTargetStream(
            "targets", (target_event(), second_event)
        ),
        decision_cycles=(first_cycle, second_cycle),
    )

    failure = engine._decision_cycle(
        case,
        state,
        second_cycle,
        (TimelineEvent(TimelineSegment.ACTIVE_TRADING, second_event),),
        1,
    )

    assert failure is None
    assert canonical_sha256(state.snapshot) != stale_snapshot_hash
    assert state.snapshot == expected_snapshot
    assert state.allocations[-1].source_portfolio_snapshot_hash == canonical_sha256(
        expected_snapshot
    )
    assert state.snapshot.cash == state.ledger_state.cash_balances
    assert state.snapshot.positions == state.ledger_state.position_balances
    assert state.snapshot.fees.units == state.ledger_state.fee_amount(
        state.ledger_state.cash_balances[0].key
    ).units
    artifact = next(
        value
        for value in state.financial_artifacts
        if value.source_event_id == "decision-snapshot:1"
    )
    assert artifact.role == "decision_snapshot"
    assert artifact.payload.snapshot == expected_snapshot
    assert artifact.payload.lot_book_hash == refresh_input.lot_book_hash
    assert artifact.payload.reservation_state_hash == state.reservation_state.state_hash
    assert artifact.payload.settlement_state_hash == state.settlement_state.state_hash
    assert artifact.payload.decision_mark_set_hash == refresh_input.decision_mark_set_hash
    stages = tuple(entry.stage for entry in state.trace_entries)
    refresh_index = max(
        index for index, stage in enumerate(stages) if stage is EngineStage.DECISION_SNAPSHOT
    )
    allocation_index = max(
        index for index, stage in enumerate(stages) if stage is EngineStage.CAPITAL_ALLOCATION
    )
    assert refresh_index < allocation_index
    portfolio_plan = state.portfolio_rebalance_plans[-1]
    assert portfolio_plan.planned_orders == ()
    raw_sizing_index = max(
        index for index, stage in enumerate(stages) if stage is EngineStage.POSITION_SIZING
    )
    capped_index = max(
        index
        for index, stage in enumerate(stages)
        if stage is EngineStage.PORTFOLIO_ORDER_SIZING
    )
    plan_index = max(
        index
        for index, stage in enumerate(stages)
        if stage is EngineStage.PORTFOLIO_REBALANCE_PLAN
    )
    assert raw_sizing_index < capped_index < plan_index
