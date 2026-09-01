from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    DeterministicBarEngine,
    EngineStage,
    ResolvedOrderCancellationPlanV1,
    ResolvedPortfolioReplacementAdmissionV1,
)
from crypto_quant_domain import (
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
)

from tests.kernel.portfolio.test_portfolio_order_sizing import _candidate, _size
from tests.runtime.engine._fixtures import TARGET_TIME, target_event
from tests.runtime.engine.test_order_terminal_lifecycle_v2 import (
    _expired_target_plan,
    _two_order_cancellation_context,
    _working_case,
)


def _single_replace_case(*, gtc_source: bool = False, reject_replacement: bool = False):
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
        side=OrderSide.SELL,
        current=5_000,
        target=0,
        sellable=5_000,
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
