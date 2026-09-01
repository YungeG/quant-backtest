from __future__ import annotations

from dataclasses import fields, replace

import pytest

from crypto_quant_backtest import (
    DeterministicBarEngine,
    EngineFailureCode,
    EngineStage,
    ExecutionCaseComposer,
    ExecutionCaseIdentityBinding,
    ExecutionCaseIdentityManifest,
    ExecutionCaseIdentityRule,
    ResolvedOrderCancellationPlanV1,
    ResolvedPortfolioReplacementAdmissionV1,
    TimelineEvent,
    TimelineSegment,
)
from crypto_quant_domain import (
    IdentityNamespace,
    Order,
    OrderEventType,
    OrderSide,
    OrderStatus,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    PortfolioCancelReplaceV1,
    PortfolioOrderPlanV2,
    PortfolioRebalanceCoordinatorV2,
    PortfolioSizingOmissionReason,
    ReservationCommitment,
)

from tests.kernel.portfolio.test_portfolio_order_sizing import _candidate, _size
from tests.runtime.engine._fixtures import (
    TARGET_TIME,
    bar_event,
    execution_case,
    target_event,
)
from tests.runtime.engine.test_order_terminal_lifecycle_v2 import (
    _expired_target_plan,
    _two_order_cancellation_context,
    _working_case,
)


def _single_replace_case(
    *,
    gtc_source: bool = False,
    reject_replacement: bool = False,
    replacement_side: OrderSide = OrderSide.SELL,
):
    case, stream, source_admission, schedule = _working_case()
    if gtc_source:
        order = replace(
            stream.order,
            intent=replace(stream.order.intent, time_in_force=TimeInForce.GTC),
        )
        stream = type(stream).from_records(order, stream.records)
        source_admission = replace(source_admission, order=order)
        case = replace(
            case,
            financial_state=replace(
                case.financial_state,
                order_streams=(stream,),
                order_admissions=(source_admission,),
            ),
        )
    target_plan = _expired_target_plan(case, stream, schedule)
    cancel_intent = target_plan.cancel_intents[0]
    cancellation = ResolvedOrderCancellationPlanV1(
        order_id=stream.order.order_id,
        cancel_requested_event_id="supersession:cancel-requested",
        cancel_requested_at=SimulationInstant(
            TARGET_TIME,
            TimelinePhase(90, "order_cancel_requested"),
            SourceSequence(1),
        ),
        cancelled_event_id="supersession:cancelled",
        cancelled_at=SimulationInstant(
            TARGET_TIME,
            TimelinePhase(91, "order_cancelled"),
            SourceSequence(1),
        ),
        reason_code=cancel_intent.reason_code,
        source_target_hash=target_plan.based_on_normalized_target_hash,
    )
    candidate = _candidate(
        side=replacement_side,
        current=0 if replacement_side is OrderSide.BUY else 5_000,
        target=5_000 if replacement_side is OrderSide.BUY else 0,
        sellable=0 if replacement_side is OrderSide.BUY else 5_000,
        order_digit="8",
        source_hash=target_plan.based_on_normalized_target_hash,
    )
    capped = _size(candidate)
    rebalance = PortfolioRebalanceCoordinatorV2().coordinate(
        capped_target=capped,
        policy=case.decision_cycles[0].portfolio_rebalance_policy,
        created_at=UtcInstant(260),
        cancellations=(cancel_intent,),
    )
    planned = rebalance.planned_orders[0]
    link = PortfolioCancelReplaceV1.create(
        instrument_id=planned.instrument_id,
        cancelled_order_id=stream.order.order_id,
        cancel_intent_id=cancel_intent.cancel_intent_id,
        prior_working_order_stream_hash=stream.stream_hash,
        replacement_identity=planned.sizing_evidence.identity,
        source_target_hash=target_plan.based_on_normalized_target_hash,
    )
    order_plan = PortfolioOrderPlanV2.create(
        source_normalized_target_id=case.decision_cycles[0].target_validity.normalized_target_id,
        source_normalized_target_hash=target_plan.based_on_normalized_target_hash,
        decision_time=case.decision_cycles[0].schedule.decision_time,
        policy_hash=case.decision_cycles[0].portfolio_rebalance_policy.policy_hash,
        sizing_evidence_hash=canonical_sha256(capped.sizing_evidence),
        cancellation_intents=(cancel_intent,),
        planned_orders=(planned,),
        cancel_replacements=(link,),
        omission_evidence_hashes=tuple(canonical_sha256(value) for value in capped.omissions),
    )
    first_at = SimulationInstant(
        TARGET_TIME,
        TimelinePhase(100, "portfolio_replacement"),
        SourceSequence(1),
    )
    replacement_order = Order(
        planned.sizing_evidence.identity.preallocated_order_id,
        stream.order.account_id,
        planned.intent,
        first_at,
    )
    event_plan = tuple(
        replace(
            value,
            event_id=f"supersession:replacement:{index}",
            occurred_at=SimulationInstant(
                TARGET_TIME,
                TimelinePhase(100, "portfolio_replacement"),
                SourceSequence(index + 1),
            ),
        )
        for index, value in enumerate(source_admission.event_plan)
    )
    admission = replace(
        source_admission,
        order=replacement_order,
        capability_set=(
            type(candidate.capability_set).create(
                capability_set_key=candidate.capability_set.capability_set_key,
                capability_set_version=candidate.capability_set.capability_set_version,
                style_capabilities=(),
                supports_reduce_only=candidate.capability_set.supports_reduce_only,
                supported_position_effects=candidate.capability_set.supported_position_effects,
                declared_capability_keys=candidate.capability_set.declared_capability_keys,
            )
            if reject_replacement
            else candidate.capability_set
        ),
        event_plan=event_plan,
    )
    wrapper = ResolvedPortfolioReplacementAdmissionV1(
        schema_version=1,
        admission=admission,
        cancel_replace_hash=link.link_hash,
        cancelled_order_id=stream.order.order_id,
        cancelled_event_id=cancellation.cancelled_event_id,
        replacement_order_id=replacement_order.order_id,
        replacement_intent_created_event_id=event_plan[0].event_id,
        occurred_at=event_plan[0].occurred_at,
        source_sequence=event_plan[0].occurred_at.source_sequence,
        source_target_hash=target_plan.based_on_normalized_target_hash,
        plan_hash=order_plan.plan_hash,
    )
    cycle = replace(
        case.decision_cycles[0],
        planning_at=UtcInstant(260),
        cancellation_plans=(cancellation,),
        replacement_admissions=(wrapper,),
        portfolio_sizing_candidates=(candidate,),
        portfolio_order_plan=order_plan,
    )
    state = DeterministicBarEngine()._initial_state(case)
    return case, state, cycle, capped, rebalance, stream, replacement_order


@pytest.mark.parametrize("gtc_source", (False, True))
def test_same_instrument_cancel_replace_has_exact_causation(gtc_source: bool) -> None:
    case, state, cycle, capped, rebalance, source, replacement = _single_replace_case(
        gtc_source=gtc_source
    )

    failure = DeterministicBarEngine()._apply_portfolio_order_plan_v2(
        case,
        state,
        cycle,
        capped,
        rebalance,
        target_event().timeline_instant,
    )

    assert failure is None
    cancelled = state.order_streams[source.order.order_id.value]
    admitted = state.order_streams[replacement.order_id.value]
    assert cancelled.state is not None and cancelled.state.status is OrderStatus.CANCELLED
    assert admitted.records[0].event.causation_id == cancelled.records[-1].event.event_id
    assert admitted.records[0].event.event_type is OrderEventType.ORDER_INTENT_CREATED
    stages = tuple(value.stage for value in state.trace_entries)
    assert stages.index(EngineStage.ORDER_CANCELLED) < stages.index(
        EngineStage.ORDER_ACCEPTED
    )
    assert not any(
        value.reason is PortfolioSizingOmissionReason.TARGET_SUPERSEDED
        for value in capped.omissions
    )


def test_cycle_replacement_admissions_are_exact_cover_and_disjoint() -> None:
    _, _, cycle, _, _, _, _ = _single_replace_case()
    wrapper = cycle.replacement_admissions[0]

    with pytest.raises(ValueError, match="exact-cover"):
        replace(cycle, replacement_admissions=())
    with pytest.raises(ValueError, match="disjoint"):
        replace(cycle, admissions=(wrapper.admission,))
    with pytest.raises(ValueError, match="duplicate replacement"):
        replace(cycle, replacement_admissions=(wrapper, wrapper))


def test_phase4_field_and_canonical_key_order_is_frozen() -> None:
    _, _, cycle, _, _, _, _ = _single_replace_case()
    link = cycle.portfolio_order_plan.cancel_replacements[0]
    plan = cycle.portfolio_order_plan

    assert tuple(value.name for value in fields(type(link))) == (
        "schema_version", "instrument_id", "cancelled_order_id", "cancel_intent_id",
        "prior_working_order_stream_hash", "replacement_order_id",
        "replacement_sizing_identity", "source_target_hash", "link_hash",
    )
    assert tuple(link.to_canonical_dict()) == (
        "type", "schema_version", "instrument_id", "cancelled_order_id",
        "cancel_intent_id", "prior_working_order_stream_hash", "replacement_order_id",
        "replacement_sizing_identity", "source_target_hash", "link_hash",
    )
    assert tuple(value.name for value in fields(type(plan))) == (
        "schema_version", "source_normalized_target_id", "source_normalized_target_hash",
        "decision_time", "policy_hash", "sizing_evidence_hash",
        "cancellation_intents", "planned_orders", "cancel_replacements",
        "omission_evidence_hashes", "plan_hash",
    )
    assert tuple(plan.to_canonical_dict()) == (
        "type", "schema_version", "source_normalized_target_id",
        "source_normalized_target_hash", "decision_time", "policy_hash",
        "sizing_evidence_hash", "cancellation_intents", "planned_orders",
        "cancel_replacements", "omission_evidence_hashes", "plan_hash",
    )


def test_direct_constructor_rejects_invalid_exact_cover() -> None:
    _, _, cycle, _, _, _, _ = _single_replace_case()
    plan = cycle.portfolio_order_plan
    link = plan.cancel_replacements[0]
    forged_order_id = replace(link.replacement_order_id, value="ord_" + "4" * 64)
    with pytest.raises(ValueError, match="replacement sizing identity context"):
        type(link)(
            1,
            link.instrument_id,
            link.cancelled_order_id,
            link.cancel_intent_id,
            link.prior_working_order_stream_hash,
            forged_order_id,
            link.replacement_sizing_identity,
            link.source_target_hash,
        )

    _, _, _, cycle2, _, _ = _two_order_cancellation_context()
    plan2 = cycle2.portfolio_order_plan
    reversed_cancellations = tuple(reversed(plan2.cancellation_intents))
    reversed_body = {
        "schema_version": 1,
        "source_normalized_target_id": plan2.source_normalized_target_id,
        "source_normalized_target_hash": plan2.source_normalized_target_hash,
        "decision_time": plan2.decision_time,
        "policy_hash": plan2.policy_hash,
        "sizing_evidence_hash": plan2.sizing_evidence_hash,
        "cancellation_intents": reversed_cancellations,
        "planned_orders": (),
        "cancel_replacements": (),
        "omission_evidence_hashes": (),
    }
    with pytest.raises(ValueError, match="canonical order"):
        type(plan2)(
            1, plan2.source_normalized_target_id, plan2.source_normalized_target_hash,
            plan2.decision_time, plan2.policy_hash, plan2.sizing_evidence_hash,
            reversed_cancellations, (), (), (), canonical_sha256(reversed_body),
        )


def test_replacement_identity_collisions_are_rejected_globally() -> None:
    case, _, cycle, _, _, source, replacement = _single_replace_case()
    wrapper = cycle.replacement_admissions[0]
    with pytest.raises(ValueError, match="disjoint"):
        replace(cycle, admissions=(wrapper.admission,))

    collided_order = replace(source.order, order_id=replacement.order_id)
    collided_records = tuple(
        replace(record, event=replace(record.event, order_id=replacement.order_id))
        for record in source.records
    )
    collided_stream = type(source).from_records(collided_order, collided_records)
    initial_admission = replace(
        case.financial_state.order_admissions[0], order=collided_order
    )
    with pytest.raises(ValueError, match="globally unique"):
        replace(
            case,
            decision_cycles=(cycle,),
            financial_state=replace(
                case.financial_state,
                order_streams=(collided_stream,),
                order_admissions=(initial_admission,),
            ),
        )


def test_replacement_identities_participate_in_manifest_verification() -> None:
    case, _, cycle, _, _, _, _ = _single_replace_case()
    case = replace(case, decision_cycles=(cycle,))
    expected = case._expected_identity_bindings()
    rules = tuple(
        ExecutionCaseIdentityRule(key, f"phase4.{index}", index, kind)
        for index, (key, (_, kind)) in enumerate(sorted(expected.items()))
    )
    spec = ExecutionCaseComposer.semantic_spec_from_case(
        case,
        spec_key="phase4.replacement.identity-test.v1",
        spec_version=1,
        identity_namespace=IdentityNamespace("phase4-test", "1"),
        identity_plan=rules,
    )
    bindings = tuple(
        ExecutionCaseIdentityBinding(
            rule.binding_key,
            rule.semantic_key,
            rule.ordinal,
            expected[rule.binding_key][0],
            rule.domain_kind,
        )
        for rule in rules
    )
    manifest = object.__new__(ExecutionCaseIdentityManifest)
    object.__setattr__(manifest, "semantic_run_id", "phase4-semantic-run")
    object.__setattr__(manifest, "namespace", spec.identity_namespace)
    object.__setattr__(manifest, "bindings", bindings)
    bound = replace(
        case,
        semantic_spec_hash=spec.semantic_spec_hash,
        semantic_spec=spec,
        identity_manifest=manifest,
    )

    assert bound.verify_identity_manifest("phase4-semantic-run")
    assert any(key.startswith("order.replacement.") for key in expected)
    assert any(key.startswith("order-event.replacement.") for key in expected)


def test_failed_replacement_rolls_back_every_mutation() -> None:
    case, state, cycle, capped, rebalance, _, _ = _single_replace_case(
        reject_replacement=True
    )
    streams = {key: value.stream_hash for key, value in state.order_streams.items()}
    trace = tuple(state.trace_entries)
    reservation_hash = state.reservation_state.state_hash
    settlement_hash = state.settlement_state.state_hash
    availability_hash = state.availability.state_hash

    outcome = DeterministicBarEngine()._apply_portfolio_order_plan_v2(
        case, state, cycle, capped, rebalance, target_event().timeline_instant
    )

    assert outcome is not None and outcome.engine_failure is not None
    assert {key: value.stream_hash for key, value in state.order_streams.items()} == streams
    assert tuple(state.trace_entries) == trace
    assert state.reservation_state.state_hash == reservation_hash
    assert state.settlement_state.state_hash == settlement_hash
    assert state.availability.state_hash == availability_hash


def test_second_admission_cash_exhaustion_rolls_back_first_admission() -> None:
    base_case, _, source_admission, _ = _working_case()
    empty_financial = execution_case().financial_state
    base_cycle = base_case.decision_cycles[0]
    source_hash = base_cycle.target_validity.normalized_target_hash
    eth = replace(_candidate(side=OrderSide.BUY, current=0, target=5_000).identity.instrument_id, stable_key="cash:eth-usd")
    candidates = (
        _candidate(side=OrderSide.BUY, current=0, target=5_000, source_hash=source_hash, order_digit="7"),
        _candidate(side=OrderSide.BUY, current=0, target=5_000, source_hash=source_hash, order_digit="5", instrument_id=eth),
    )
    capped = _size(*candidates)
    rebalance = PortfolioRebalanceCoordinatorV2().coordinate(
        capped_target=capped,
        policy=base_cycle.portfolio_rebalance_policy,
        created_at=base_cycle.planning_at,
    )
    order_plan = PortfolioOrderPlanV2.create(
        source_normalized_target_id=base_cycle.target_validity.normalized_target_id,
        source_normalized_target_hash=source_hash,
        decision_time=base_cycle.schedule.decision_time,
        policy_hash=base_cycle.portfolio_rebalance_policy.policy_hash,
        sizing_evidence_hash=canonical_sha256(capped.sizing_evidence),
        cancellation_intents=(),
        planned_orders=rebalance.planned_orders,
        cancel_replacements=(),
        omission_evidence_hashes=tuple(canonical_sha256(value) for value in capped.omissions),
    )
    admissions = []
    for index, (candidate, planned) in enumerate(zip(candidates, rebalance.planned_orders, strict=True)):
        order = Order(
            planned.sizing_evidence.identity.preallocated_order_id,
            source_admission.order.account_id,
            planned.intent,
            source_admission.order.created_at,
        )
        admissions.append(
            replace(
                source_admission,
                order=order,
                capability_set=candidate.capability_set,
                pretrade_plan=replace(
                    source_admission.pretrade_plan,
                    order_rule_timeline=candidate.order_rule_timeline,
                    notional_evidence=candidate.notional_evidence,
                    fee_reservation_rule_set=candidate.fee_rule_set,
                ),
                event_plan=tuple(
                    replace(value, event_id=f"cumulative:{index}:{event_index}")
                    for event_index, value in enumerate(source_admission.event_plan)
                ),
            )
        )
    cycle = replace(
        base_cycle,
        admissions=tuple(admissions),
        portfolio_sizing_candidates=candidates,
        portfolio_order_plan=order_plan,
    )
    case = replace(
        base_case,
        decision_cycles=(cycle,),
        bar_executions=(),
        financial_state=empty_financial,
    )
    engine = DeterministicBarEngine()
    control_state = engine._initial_state(case)
    assert engine._admit_order(case, control_state, admissions[0]) is None
    assert admissions[0].order.order_id.value in control_state.order_streams

    state = engine._initial_state(case)
    streams = dict(state.order_streams)
    trace = tuple(state.trace_entries)

    outcome = engine._apply_portfolio_order_plan_v2(
        case, state, cycle, capped, rebalance, target_event().timeline_instant
    )

    assert outcome is not None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.PRETRADE_REJECTED
    assert outcome.engine_failure.subject_keys == (
        admissions[1].order.order_id.value,
        "tradable_cash:USD",
    )
    assert state.order_streams == streams
    assert tuple(state.trace_entries) == trace
    assert state.reservation_state.active_reservations == ()


def test_multi_instrument_cancellation_commits_atomically() -> None:
    engine, case, state, cycle, _, ordered_intents = _two_order_cancellation_context()
    cash = state.availability.cash[0]
    zero = replace(cash.tradable, units=0)
    capped, rebalance, order_plan = cycle.materialize_portfolio_plans(
        cash_availability=cash,
        active_cash_reservations=zero,
        active_fee_reservations=zero,
        working_orders=tuple(state.order_streams.values()),
    )
    cycle = replace(cycle, portfolio_order_plan=order_plan)

    failure = engine._apply_portfolio_order_plan_v2(
        case, state, cycle, capped, rebalance, target_event().timeline_instant
    )

    assert failure is None
    assert all(
        state.order_streams[value.order_id.value].state.status is OrderStatus.CANCELLED
        for value in ordered_intents
    )


def test_full_run_replacement_is_followed_by_scheduled_bar_fill() -> None:
    case, _, cycle, _, _, _, replacement = _single_replace_case(
        replacement_side=OrderSide.BUY
    )
    baseline = execution_case()
    bar = replace(baseline.bar_executions[0], order_id=replacement.order_id)
    schedule = case.financial_state.reservation_schedules[0]
    update = schedule.updates[0]
    fee_only = ReservationCommitment(fee_reserve=update.commitment.fee_reserve)
    financial_state = replace(
        case.financial_state,
        reservation_schedules=(
            replace(schedule, updates=(replace(update, commitment=fee_only),)),
        ),
    )
    staged_case = replace(case, financial_state=financial_state)
    staged_state = DeterministicBarEngine()._initial_state(staged_case)
    cash = staged_state.availability.cash[0]
    active_cash = replace(cash.tradable, units=0)
    active_fee = replace(
        cash.tradable,
        units=sum(
            value.units for value in staged_state.reservation_state.totals.fee_reserve
        ),
    )
    _, _, resolved_plan = cycle.materialize_portfolio_plans(
        cash_availability=cash,
        active_cash_reservations=active_cash,
        active_fee_reservations=active_fee,
        working_orders=tuple(staged_state.order_streams.values()),
    )
    cycle = replace(
        cycle,
        portfolio_order_plan=resolved_plan,
        replacement_admissions=(
            replace(cycle.replacement_admissions[0], plan_hash=resolved_plan.plan_hash),
        ),
    )
    case = replace(
        staged_case,
        decision_cycles=(cycle,),
        bar_executions=(bar,),
        snapshot_plan=baseline.snapshot_plan,
        financial_dispatch_plan=baseline.financial_dispatch_plan,
    )

    outcome = DeterministicBarEngine().run(case)

    assert outcome.result is not None
    result = outcome.result
    replacement_stream = next(
        value for value in result.order_streams if value.order.order_id == replacement.order_id
    )
    assert replacement_stream.state is not None
    assert replacement_stream.state.status is OrderStatus.FILLED
    assert result.fills[0].order_id == replacement.order_id


def test_exact_cover_working_order_is_retained() -> None:
    case, state, cycle, _, stream = _single_replace_case()[:5]
    cycle = replace(
        cycle,
        cancellation_plans=(),
        replacement_admissions=(),
        portfolio_sizing_candidates=(),
        portfolio_order_plan=replace(
            cycle.portfolio_order_plan,
            cancellation_intents=(),
            planned_orders=(),
            cancel_replacements=(),
            omission_evidence_hashes=(),
            sizing_evidence_hash=canonical_sha256(()),
            plan_hash=PortfolioOrderPlanV2.create(
                source_normalized_target_id=cycle.target_validity.normalized_target_id,
                source_normalized_target_hash=cycle.target_validity.normalized_target_hash,
                decision_time=cycle.schedule.decision_time,
                policy_hash=cycle.portfolio_rebalance_policy.policy_hash,
                sizing_evidence_hash=canonical_sha256(()),
                cancellation_intents=(),
                planned_orders=(),
                cancel_replacements=(),
                omission_evidence_hashes=(),
            ).plan_hash,
        ),
    )
    cash = state.availability.cash[0]
    zero = replace(cash.tradable, units=0)
    capped, rebalance, _ = cycle.materialize_portfolio_plans(
        cash_availability=cash,
        active_cash_reservations=zero,
        active_fee_reservations=zero,
        working_orders=tuple(state.order_streams.values()),
    )
    before = state.order_streams.copy()

    assert DeterministicBarEngine()._apply_portfolio_order_plan_v2(
        case, state, cycle, capped, rebalance, target_event().timeline_instant
    ) is None
    assert state.order_streams == before
