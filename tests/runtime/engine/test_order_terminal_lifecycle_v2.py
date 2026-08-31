from __future__ import annotations

from dataclasses import replace

from crypto_quant_backtest import (
    BarLiquidityEvidence,
    DeterministicBarEngine,
    EngineFailureCode,
    EngineStage,
    NoEligibleBarAction,
    ResolvedOrderCancellationPlanV1,
    ResolvedOrderTerminalPlanV1,
    ResolvedPortfolioBarExecutionV2,
    ResolvedPortfolioDecisionCycleV2,
)
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    ExecutionStyle,
    InstrumentId,
    Money,
    OrderEventType,
    OrderStatus,
    Quantity,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TimeInForce,
    UtcInstant,
)
from crypto_quant_trading import (
    AvailabilityProjection,
    GenericLedger,
    OrderCapabilitySet,
    OrderReservationSchedule,
    OrderReservationUpdate,
    PortfolioAllocator,
    PortfolioRiskEvaluator,
    PortfolioValueKind,
    PositionSizer,
    RebalanceCoordinator,
    ResourceReservationBook,
)

from tests.runtime.engine._fixtures import (
    BAR_TIME,
    CASH_KEY,
    TARGET_TIME,
    allocations,
    bar_event,
    execution_case,
    initial_snapshot,
    risk_policy,
    sizing_inputs,
    sizing_policy,
)


def _unchanged_case():
    case = execution_case()
    cash = next(
        value
        for value in case.snapshot_plan.valuations
        if value.value_ref.kind is PortfolioValueKind.CASH
    )
    unchanged_cash = Money(100_000, cash.native_value.scale, "USD")
    snapshot_plan = replace(
        case.snapshot_plan,
        resolved_marks=(),
        valuations=(
            replace(
                cash,
                native_value=unchanged_cash,
                reporting_value=unchanged_cash,
            ),
        ),
    )
    return replace(
        case,
        bar_executions=(),
        snapshot_plan=snapshot_plan,
        financial_dispatch_plan=replace(
            case.financial_dispatch_plan,
            final_snapshot_payload=snapshot_plan,
            expected_artifact_roles=("final_snapshot",),
        ),
    )


def _working_case():
    admitted_case = _unchanged_case()
    admitted_result = DeterministicBarEngine().run(admitted_case).result
    assert admitted_result is not None
    stream = admitted_result.order_streams[0]
    early_records = tuple(
        replace(
            record,
            event=replace(
                record.event,
                occurred_at=SimulationInstant(
                    UtcInstant(10 + index),
                    record.event.occurred_at.phase,
                    record.event.occurred_at.source_sequence,
                ),
            ),
        )
        for index, record in enumerate(stream.records)
    )
    early_order = replace(stream.order, created_at=early_records[0].event.occurred_at)
    stream = type(stream).from_records(early_order, early_records)
    original_admission = admitted_case.decision_cycles[0].admissions[0]
    resolved_admission = replace(
        original_admission,
        order=early_order,
        event_plan=tuple(
            replace(plan, occurred_at=record.event.occurred_at)
            for plan, record in zip(
                original_admission.event_plan, early_records, strict=True
            )
        ),
    )
    accepted = stream.records[-1].event
    schedule = OrderReservationSchedule(
        order_id=stream.order.order_id,
        source_proposal_hash="sha256:" + "a" * 64,
        updates=(
            OrderReservationUpdate(
                order_id=stream.order.order_id,
                event_id=accepted.event_id,
                event_type=accepted.event_type,
                remaining_quantity=stream.order.intent.quantity,
                commitment=resolved_admission.pretrade_plan.resource_commitment,
                source_evidence_hash="sha256:" + "b" * 64,
            ),
        ),
    )
    financial_state = replace(
        admitted_case.financial_state,
        order_streams=(stream,),
        order_admissions=(resolved_admission,),
        reservation_schedules=(schedule,),
    )
    cycle = admitted_case.decision_cycles[0]
    portfolio_cycle = ResolvedPortfolioDecisionCycleV2(
        schedule=cycle.schedule,
        allocations=cycle.allocations,
        target_notional_scale=cycle.target_notional_scale,
        risk_policy=cycle.risk_policy,
        sizing_policy=cycle.sizing_policy,
        sizing_inputs=cycle.sizing_inputs,
        target_validity=cycle.target_validity,
        rebalance_policy=cycle.rebalance_policy,
        planning_at=UtcInstant(130),
        admissions=(),
        cancellation_plans=(),
    )
    return (
        replace(
            admitted_case,
            decision_cycles=(portfolio_cycle,),
            financial_state=financial_state,
        ),
        stream,
        resolved_admission,
        schedule,
    )


def _portfolio_bar(case, terminal_plan=None):
    base = execution_case().bar_executions[0]
    blocked = BarLiquidityEvidence.create(
        evidence_key=base.liquidity_evidence.evidence_key,
        evidence_version=base.liquidity_evidence.evidence_version,
        market_event=bar_event(),
        evaluated_at=BAR_TIME,
        approved=False,
        reason_code="upper_limit_blocked",
        source_hash=base.liquidity_evidence.source_hash,
    )
    return ResolvedPortfolioBarExecutionV2(
        event_id=base.event_id,
        order_id=base.order_id,
        pretrade_plan=base.pretrade_plan,
        liquidity_evidence=blocked,
        market_state=base.market_state,
        slippage_model=base.slippage_model,
        fill_id=base.fill_id,
        fill_event_id=base.fill_event_id,
        fill_event_at=base.fill_event_at,
        accounting_plan=base.accounting_plan,
        terminal_plan=terminal_plan,
    )


def _resolved_expiry_case():
    case, stream, _, schedule = _working_case()
    provisional = ResolvedOrderTerminalPlanV1(
        order_id=stream.order.order_id,
        trigger_action=NoEligibleBarAction.EXPIRE,
        terminal_event_type=OrderEventType.ORDER_EXPIRED,
        event_id="engine-order:expired",
        occurred_at=SimulationInstant(
            BAR_TIME,
            TimelinePhase(70, "order_expired"),
            SourceSequence(1),
        ),
        reason_code="day_eligibility_window_exhausted",
        source_evidence_hash="sha256:" + "f" * 64,
    )
    provisional_case = replace(
        case,
        bar_executions=(_portfolio_bar(case, provisional),),
    )
    mismatch = DeterministicBarEngine().run(provisional_case).engine_failure
    assert mismatch is not None
    assert mismatch.code is EngineFailureCode.CASE_EVIDENCE_MISMATCH
    decision_hashes = set(mismatch.evidence_hashes) - {provisional.plan_hash}
    assert len(decision_hashes) == 1
    resolved = replace(
        provisional,
        source_evidence_hash=decision_hashes.pop(),
    )
    return replace(
        case,
        bar_executions=(_portfolio_bar(case, resolved),),
    ), schedule


def _expired_target_plan(case, stream, schedule):
    cycle = case.decision_cycles[0]
    injected = case.target_stream
    from crypto_quant_backtest import PrecomputedTargetStreamAdapter
    from crypto_quant_backtest.timeline import TimelineEvent, TimelineSegment
    from tests.runtime.engine._fixtures import target_event

    target = target_event()
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=injected,
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, target),),
        schedule=cycle.schedule,
    )
    assert outcome.injection is not None
    allocated = PortfolioAllocator().allocate(
        sleeve_state=outcome.injection.state,
        portfolio_snapshot=initial_snapshot(),
        allocations=allocations(),
        target_notional_scale=cycle.target_notional_scale,
    )
    assert allocated.allocation is not None
    approved = PortfolioRiskEvaluator().evaluate(
        allocation=allocated.allocation,
        policy=risk_policy(),
    )
    assert approved.approved_target is not None
    sized = PositionSizer().materialize(
        approved_target=approved.approved_target,
        source_decision_batch_id=outcome.injection.batch.decision_batch_id,
        policy=sizing_policy(),
        inputs=sizing_inputs(),
    )
    assert sized.normalized_target is not None
    reservations = ResourceReservationBook(stream.order.account_id).project(
        (stream,), (schedule,)
    )
    settlement = case.financial_state.settlement_book.project()
    availability = AvailabilityProjection().project(
        GenericLedger(case.financial_state.ledger_schema).project(
            case.financial_state.journal
        ),
        settlement,
        reservations,
        case.financial_state.settlement_rules,
    )
    planned = RebalanceCoordinator().coordinate(
        target=sized.normalized_target,
        target_validity=cycle.target_validity,
        portfolio_snapshot=initial_snapshot(),
        working_orders=(stream,),
        reservations=reservations,
        availability=availability,
        policy=cycle.rebalance_policy,
        as_of=UtcInstant(260),
    )
    assert planned.decision is not None
    assert len(planned.decision.plan.cancel_intents) == 1
    return planned.decision.plan


def _two_order_cancellation_context(*, invalid_second: bool = False):
    case, first_stream, first_admission, first_schedule = _working_case()
    target_plan = _expired_target_plan(case, first_stream, first_schedule)
    first_intent = target_plan.cancel_intents[0]

    second_instrument = InstrumentId(
        first_stream.order.intent.instrument_id.venue, "cash:eth-usd"
    )
    second_order_id = DomainId(DomainIdKind.ORDER, "ord_" + "9" * 64)
    second_quantity = Quantity(
        first_stream.order.intent.quantity.units,
        first_stream.order.intent.quantity.scale,
        str(second_instrument),
    )
    second_order = replace(
        first_stream.order,
        order_id=second_order_id,
        intent=replace(
            first_stream.order.intent,
            instrument_id=second_instrument,
            quantity=second_quantity,
        ),
    )
    second_records = []
    causation_id = second_order.intent.parent_id
    for index, record in enumerate(first_stream.records):
        event = replace(
            record.event,
            event_id=f"engine-order:second:{index}",
            order_id=second_order_id,
            causation_id=causation_id,
        )
        second_records.append(replace(record, event=event))
        causation_id = event.event_id
    second_stream = type(first_stream).from_records(
        second_order, tuple(second_records)
    )
    second_admission = replace(
        first_admission,
        order=second_order,
        event_plan=tuple(
            replace(plan, event_id=record.event.event_id)
            for plan, record in zip(
                first_admission.event_plan, second_records, strict=True
            )
        ),
    )
    second_schedule = replace(
        first_schedule,
        order_id=second_order_id,
        updates=tuple(
            replace(
                update,
                order_id=second_order_id,
                event_id=second_records[-1].event.event_id,
                remaining_quantity=second_quantity,
            )
            for update in first_schedule.updates
        ),
    )
    case = replace(
        case,
        financial_state=replace(
            case.financial_state,
            order_streams=(first_stream, second_stream),
            order_admissions=(first_admission, second_admission),
            reservation_schedules=(first_schedule, second_schedule),
        ),
    )
    second_intent = replace(
        first_intent,
        cancel_intent_id="cancel-intent-v1:sha256:" + "c" * 64,
        order_id=second_order_id,
        instrument_id=second_instrument,
    )
    order_plan = type(target_plan).create(
        account_id=target_plan.account_id,
        created_at=target_plan.created_at,
        based_on_normalized_target_id=target_plan.based_on_normalized_target_id,
        based_on_normalized_target_hash=target_plan.based_on_normalized_target_hash,
        based_on_target_validity_hash=target_plan.based_on_target_validity_hash,
        based_on_portfolio_snapshot_hash=target_plan.based_on_portfolio_snapshot_hash,
        based_on_working_order_set_hash=target_plan.based_on_working_order_set_hash,
        based_on_reservation_state_hash=target_plan.based_on_reservation_state_hash,
        based_on_availability_state_hash=target_plan.based_on_availability_state_hash,
        policy=target_plan.policy,
        valid_until=target_plan.valid_until,
        planned_orders=target_plan.planned_orders,
        cancel_intents=(first_intent, second_intent),
        omissions=target_plan.omissions,
        supersedes_plan_id=target_plan.supersedes_plan_id,
    )
    ordered_intents = tuple(
        sorted(
            order_plan.cancel_intents,
            key=lambda value: (value.instrument_id, value.order_id.value),
        )
    )
    cancellation_plans = tuple(
        ResolvedOrderCancellationPlanV1(
            order_id=intent.order_id,
            cancel_requested_event_id=f"engine-order:{index}:cancel-requested",
            cancel_requested_at=SimulationInstant(
                TARGET_TIME,
                TimelinePhase(90, "order_cancel_requested"),
                SourceSequence(index),
            ),
            cancelled_event_id=f"engine-order:{index}:cancelled",
            cancelled_at=SimulationInstant(
                TARGET_TIME,
                TimelinePhase(91, "order_cancelled"),
                SourceSequence(index),
            ),
            reason_code=(
                "invalid_later_reason"
                if invalid_second and index == len(ordered_intents)
                else intent.reason_code
            ),
            source_target_hash=order_plan.based_on_normalized_target_hash,
        )
        for index, intent in enumerate(ordered_intents, start=1)
    )
    cycle = replace(
        case.decision_cycles[0],
        planning_at=UtcInstant(260),
        cancellation_plans=cancellation_plans,
    )
    engine = DeterministicBarEngine()
    state = engine._initial_state(case)
    return engine, case, state, cycle, order_plan, ordered_intents


def test_day_expiry_is_terminal_releases_reservation_and_preserves_cash() -> None:
    case, schedule = _resolved_expiry_case()
    outcome = DeterministicBarEngine().run(case)

    assert outcome.result is not None
    result = outcome.result
    stream = result.order_streams[0]
    assert stream.state is not None
    assert stream.state.status is OrderStatus.EXPIRED
    projected = ResourceReservationBook(stream.order.account_id).project(
        (stream,), (schedule,)
    )
    assert projected.active_reservations == ()
    cash = result.final_ledger_state.cash_amount(CASH_KEY)
    assert cash == Money(100_000, cash.scale, "USD")
    assert result.final_ledger_state.position_balances == ()
    stages = tuple(entry.stage for entry in result.trace.entries)
    assert EngineStage.ORDER_EXPIRED in stages
    assert EngineStage.RESOURCE_REFRESH in stages


def test_gtc_no_fill_remains_active_and_reserved() -> None:
    case, stream, resolved_admission, schedule = _working_case()
    gtc_order = replace(
        stream.order,
        intent=replace(stream.order.intent, time_in_force=TimeInForce.GTC),
    )
    gtc_stream = type(stream).from_records(gtc_order, stream.records)
    capabilities = resolved_admission.capability_set
    styles = capabilities.style_capabilities
    market = next(
        value for value in styles if value.execution_style is ExecutionStyle.MARKET
    )
    gtc_capabilities = OrderCapabilitySet.create(
        capability_set_key=capabilities.capability_set_key,
        capability_set_version=capabilities.capability_set_version,
        style_capabilities=tuple(
            replace(
                value,
                time_in_forces=(TimeInForce.DAY, TimeInForce.GTC),
            )
            if value is market
            else value
            for value in styles
        ),
        supports_reduce_only=capabilities.supports_reduce_only,
        supported_position_effects=capabilities.supported_position_effects,
        declared_capability_keys=capabilities.declared_capability_keys,
    )
    gtc_admission = replace(
        resolved_admission,
        order=gtc_order,
        capability_set=gtc_capabilities,
    )
    case = replace(
        case,
        financial_state=replace(
            case.financial_state,
            order_streams=(gtc_stream,),
            order_admissions=(gtc_admission,),
        ),
        bar_executions=(_portfolio_bar(case),),
    )
    result = DeterministicBarEngine().run(case).result

    assert result is not None
    final_stream = result.order_streams[0]
    assert final_stream.state is not None
    assert final_stream.state.status is OrderStatus.ACCEPTED
    projected = ResourceReservationBook(final_stream.order.account_id).project(
        (final_stream,), (schedule,)
    )
    assert len(projected.active_reservations) == 1
    assert EngineStage.ORDER_EXPIRED not in {
        entry.stage for entry in result.trace.entries
    }


def test_target_cancellation_emits_ordered_events_and_releases_resources() -> None:
    case, stream, _, schedule = _working_case()
    target_plan = _expired_target_plan(case, stream, schedule)
    cancel_intent = target_plan.cancel_intents[0]
    cancellation = ResolvedOrderCancellationPlanV1(
        order_id=stream.order.order_id,
        cancel_requested_event_id="engine-order:cancel-requested",
        cancel_requested_at=SimulationInstant(
            TARGET_TIME,
            TimelinePhase(90, "order_cancel_requested"),
            SourceSequence(1),
        ),
        cancelled_event_id="engine-order:cancelled",
        cancelled_at=SimulationInstant(
            TARGET_TIME,
            TimelinePhase(91, "order_cancelled"),
            SourceSequence(1),
        ),
        reason_code=cancel_intent.reason_code,
        source_target_hash=target_plan.based_on_normalized_target_hash,
    )
    cycle = case.decision_cycles[0]
    cancelling_cycle = replace(
        cycle,
        planning_at=UtcInstant(260),
        cancellation_plans=(cancellation,),
    )
    result = DeterministicBarEngine().run(
        replace(case, decision_cycles=(cancelling_cycle,))
    ).result

    assert result is not None
    final_stream = result.order_streams[0]
    assert final_stream.state is not None
    assert final_stream.state.status is OrderStatus.CANCELLED
    assert tuple(record.event.event_type for record in final_stream.records[-2:]) == (
        OrderEventType.ORDER_CANCEL_REQUESTED,
        OrderEventType.ORDER_CANCELLED,
    )
    assert final_stream.records[-2].event.occurred_at.phase.rank == 90
    assert final_stream.records[-1].event.occurred_at.phase.rank == 91
    projected = ResourceReservationBook(final_stream.order.account_id).project(
        (final_stream,), (schedule,)
    )
    assert projected.active_reservations == ()
    lifecycle_stages = tuple(
        entry.stage
        for entry in result.trace.entries
        if entry.stage
        in {
            EngineStage.ORDER_CANCEL_REQUESTED,
            EngineStage.ORDER_CANCELLED,
            EngineStage.RESOURCE_REFRESH,
        }
    )
    assert lifecycle_stages == (
        EngineStage.ORDER_CANCEL_REQUESTED,
        EngineStage.ORDER_CANCELLED,
        EngineStage.RESOURCE_REFRESH,
    )
    assert result.final_ledger_state.cash_amount(CASH_KEY).units == 100_000
    assert result.final_ledger_state.position_balances == ()


def test_two_order_cancellation_is_canonical_across_instruments() -> None:
    engine, case, state, cycle, order_plan, ordered_intents = (
        _two_order_cancellation_context()
    )

    failure = engine._apply_target_cancellations(case, state, cycle, order_plan)

    assert failure is None
    ordered_order_ids = tuple(value.order_id.value for value in ordered_intents)
    lifecycle = tuple(
        entry
        for entry in state.trace_entries
        if entry.stage
        in {
            EngineStage.ORDER_CANCEL_REQUESTED,
            EngineStage.ORDER_CANCELLED,
            EngineStage.RESOURCE_REFRESH,
        }
    )
    assert tuple(entry.stage for entry in lifecycle) == (
        EngineStage.ORDER_CANCEL_REQUESTED,
        EngineStage.ORDER_CANCEL_REQUESTED,
        EngineStage.ORDER_CANCELLED,
        EngineStage.ORDER_CANCELLED,
        EngineStage.RESOURCE_REFRESH,
    )
    assert tuple(entry.subject_id for entry in lifecycle[:2]) == ordered_order_ids
    assert tuple(entry.subject_id for entry in lifecycle[2:4]) == ordered_order_ids
    assert tuple(entry.instant.source_sequence.value for entry in lifecycle[:4]) == (
        1,
        2,
        1,
        2,
    )
    assert tuple(entry.instant.phase.rank for entry in lifecycle[:4]) == (
        90,
        90,
        91,
        91,
    )
    assert all(
        state.order_streams[order_id].state is not None
        and state.order_streams[order_id].state.status is OrderStatus.CANCELLED
        for order_id in ordered_order_ids
    )
    assert state.reservation_state.active_reservations == ()


def test_later_invalid_cancellation_plan_commits_nothing() -> None:
    engine, case, state, cycle, order_plan, _ = _two_order_cancellation_context(
        invalid_second=True
    )
    stream_hashes = {
        order_id: stream.stream_hash for order_id, stream in state.order_streams.items()
    }
    trace_entries = tuple(state.trace_entries)
    reservation_hash = state.reservation_state.state_hash
    availability_hash = state.availability.state_hash
    settlement_hash = state.settlement_state.state_hash

    outcome = engine._apply_target_cancellations(case, state, cycle, order_plan)

    assert outcome is not None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.CASE_EVIDENCE_MISMATCH
    assert {
        order_id: stream.stream_hash for order_id, stream in state.order_streams.items()
    } == stream_hashes
    assert tuple(state.trace_entries) == trace_entries
    assert state.reservation_state.state_hash == reservation_hash
    assert state.availability.state_hash == availability_hash
    assert state.settlement_state.state_hash == settlement_hash
    assert len(state.reservation_state.active_reservations) == 2
