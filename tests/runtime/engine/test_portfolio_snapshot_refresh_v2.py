from __future__ import annotations

from dataclasses import replace

from crypto_quant_backtest import (
    DeterministicBarEngine,
    EngineStage,
    PrecomputedTargetStream,
    ResolvedDecisionSnapshotRefreshPlanV1,
    ResolvedPortfolioDecisionCycleV2,
    TimelineEvent,
    TimelineSegment,
)
from crypto_quant_domain import (
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
    PortfolioSnapshotRefreshInputV1,
    PortfolioSnapshotRefresherV1,
    PortfolioSnapshotRefreshPolicyV1,
)

from tests.runtime.engine._fixtures import (
    MONEY_SCALE,
    bar_event,
    execution_case,
    target_event,
    target_payload,
    valuation_mark,
)


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

    assert failure is not None  # Later legacy rebalance evidence is intentionally absent.
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
