from __future__ import annotations

from dataclasses import fields, replace

import pytest

from crypto_quant_backtest import (
    BarIneligibilityReason,
    ExecutionModel,
    FullFillBuilder,
    FullFillConstructionFailure,
    FullFillResult,
    NextBarOpenDecision,
    NextBarOpenFailure,
    NextBarOpenFailureCode,
    NextBarOpenRequest,
    NoEligibleBarAction,
    SimulationPortType,
)
from crypto_quant_domain import (
    Money,
    OrderStatus,
    PricePurpose,
    Quantity,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from tests.runtime.execution._fixtures import (
    accepted_journey,
    altered_quantity,
    candidate,
    fill_id,
    model,
    request,
    slippage_model,
    slippage_request,
)


def eligible_decision() -> NextBarOpenDecision:
    outcome = model().simulate_execution(request(bar_candidate=candidate()))
    assert outcome.failure is None
    assert isinstance(outcome.result, NextBarOpenDecision)
    return outcome.result


def test_first_real_eligible_bar_produces_exact_full_reference_decision() -> None:
    execution = model()
    execution_port: ExecutionModel[
        NextBarOpenRequest, NextBarOpenDecision, NextBarOpenFailure
    ] = execution
    subject = request(bar_candidate=candidate())

    outcome = execution_port.simulate_execution(subject)

    assert execution.spec().component_ref == execution.component_ref
    assert execution.component_ref.port_type is SimulationPortType.EXECUTION_MODEL
    assert outcome.failure is None
    assert isinstance(outcome.result, NextBarOpenDecision)
    decision = outcome.result
    assert subject.order_stream.state is not None
    assert decision.action is NoEligibleBarAction.FULL_FILL
    assert decision.reference_price is not None
    assert decision.reference_price.mark.price_purpose is PricePurpose.EXECUTION_REFERENCE
    assert decision.reference_price.mark.price.units == 3_100_000
    assert decision.reference_price.mark.source_event_id == "bar-open:300:1:real"
    assert decision.fill_quantity == subject.order_stream.state.remaining_quantity
    assert decision.candidate == subject.candidate
    assert outcome.input_hash == canonical_sha256(subject)


def test_same_bar_and_missing_or_stale_gate_evidence_fail_structured() -> None:
    stream = accepted_journey()["accepted_stream"]
    assert stream.state is not None
    same_instant = stream.state.updated_at.instant.epoch_nanoseconds

    same_bar = model().simulate_execution(
        request(bar_candidate=candidate(instant=same_instant))
    )
    missing_gate = model().simulate_execution(
        request(
            bar_candidate=replace(
                candidate(),
                market_rule_approval=None,
                pretrade_risk_approval=None,
            )
        )
    )
    stale_gate = model().simulate_execution(
        request(bar_candidate=candidate(instant=301))
    )
    outside_rule_interval = model().simulate_execution(
        request(bar_candidate=candidate(instant=500))
    )

    assert isinstance(same_bar.failure, NextBarOpenFailure)
    assert same_bar.failure.code is NextBarOpenFailureCode.SAME_BAR_FORBIDDEN
    assert isinstance(missing_gate.failure, NextBarOpenFailure)
    assert missing_gate.failure.code is NextBarOpenFailureCode.MISSING_GATE_APPROVAL
    assert isinstance(stale_gate.failure, NextBarOpenFailure)
    assert stale_gate.failure.code is NextBarOpenFailureCode.MARKET_RULE_INTERVAL_MISMATCH
    assert isinstance(outside_rule_interval.failure, NextBarOpenFailure)
    assert outside_rule_interval.failure.code is NextBarOpenFailureCode.MARKET_RULE_INTERVAL_MISMATCH


def test_placeholder_forward_fill_and_liquidity_block_never_produce_reference() -> None:
    placeholder = model().simulate_execution(
        request(bar_candidate=candidate(kind="gap_placeholder"))
    ).result
    forward = model().simulate_execution(
        request(bar_candidate=candidate(kind="forward_filled"))
    ).result
    blocked = model().simulate_execution(
        request(
            bar_candidate=candidate(
                liquidity_approved=False,
                reason_code="liquidity_blocked_at_limit",
            )
        )
    ).result

    assert placeholder is not None and forward is not None and blocked is not None
    assert placeholder.action is NoEligibleBarAction.KEEP_ACTIVE
    assert placeholder.ineligibility_reason is BarIneligibilityReason.GAP_PLACEHOLDER
    assert placeholder.reference_price is None
    assert forward.ineligibility_reason is BarIneligibilityReason.FORWARD_FILLED
    assert forward.reference_price is None
    assert blocked.ineligibility_reason is BarIneligibilityReason.LIQUIDITY_BLOCKED
    assert blocked.reference_price is None


def test_eligibility_window_end_uses_explicit_tif_mapping() -> None:
    expired = model().simulate_execution(
        request(bar_candidate=None, eligibility_window_exhausted=True)
    ).result
    kept = model(day_action=NoEligibleBarAction.KEEP_ACTIVE).simulate_execution(
        request(bar_candidate=None, eligibility_window_exhausted=True)
    ).result

    assert expired is not None and kept is not None
    assert request().order_stream.order.intent.time_in_force is TimeInForce.DAY
    assert expired.action is NoEligibleBarAction.EXPIRE
    assert expired.ineligibility_reason is BarIneligibilityReason.NO_ELIGIBLE_BAR
    assert kept.action is NoEligibleBarAction.KEEP_ACTIVE
    with pytest.raises(ValueError, match="cover every TimeInForce"):
        replace(model().applicability, tif_actions=())


def test_fill_requires_independent_matching_successful_slippage() -> None:
    decision = eligible_decision()
    slippage = slippage_model(decision)
    slippage_outcome = slippage.decide_slippage(slippage_request(decision))

    built = FullFillBuilder().build(
        decision=decision,
        slippage_outcome=slippage_outcome,
        fill_id=fill_id(),
    )

    assert isinstance(built, FullFillResult)
    assert decision.reference_price is not None
    assert decision.candidate is not None
    assert slippage_outcome.result is not None
    assert built.fill.quantity == decision.fill_quantity
    assert built.fill.reference_price == decision.reference_price.mark.price
    assert built.fill.price == slippage_outcome.result.execution_price
    assert built.fill.slippage_amount == Money(
        slippage_outcome.result.slippage_amount.units,
        slippage_outcome.result.slippage_amount.scale,
        slippage_outcome.result.slippage_amount.quote_currency,
    )
    assert built.fill.execution_time == decision.candidate.observation.event.event_time
    assert built.fill.liquidity == "full"

    failed_slippage = slippage.decide_slippage(
        replace(
            slippage_request(decision),
            quantity=Quantity(
                decision.fill_quantity.units + 1,
                decision.fill_quantity.scale,
                decision.fill_quantity.instrument_id,
            ),
        )
    )
    failure = FullFillBuilder().build(
        decision=decision,
        slippage_outcome=failed_slippage,
        fill_id=fill_id(),
    )
    assert isinstance(failure, FullFillConstructionFailure)


def test_mismatched_slippage_request_cannot_construct_fill() -> None:
    decision = eligible_decision()
    request_value = slippage_request(decision)
    smaller = replace(
        request_value,
        quantity=altered_quantity(request_value.quantity),
    )
    mismatch = slippage_model(decision).decide_slippage(smaller)

    result = FullFillBuilder().build(
        decision=decision,
        slippage_outcome=mismatch,
        fill_id=fill_id(),
    )

    assert isinstance(result, FullFillConstructionFailure)
    assert result.code.value == "slippage_evidence_mismatch"

    valid = slippage_model(decision).decide_slippage(request_value)
    forged = replace(valid, input_hash="sha256:" + "00" * 32)
    forged_result = FullFillBuilder().build(
        decision=decision,
        slippage_outcome=forged,
        fill_id=fill_id(),
    )
    assert isinstance(forged_result, FullFillConstructionFailure)
    assert forged_result.code.value == "slippage_evidence_mismatch"


def test_missing_liquidity_and_future_market_state_fail_closed() -> None:
    missing_liquidity = model().simulate_execution(
        request(
            bar_candidate=replace(candidate(), liquidity_evidence=None)
        )
    )
    future_state = candidate()
    assert future_state.market_state is not None
    future_market_state = model().simulate_execution(
        request(
            bar_candidate=replace(
                future_state,
                market_state=replace(
                    future_state.market_state,
                    available_at=UtcInstant(301),
                ),
            )
        )
    )

    assert isinstance(missing_liquidity.failure, NextBarOpenFailure)
    assert missing_liquidity.failure.code is NextBarOpenFailureCode.LIQUIDITY_EVIDENCE_MISMATCH
    assert isinstance(future_market_state.failure, NextBarOpenFailure)
    assert future_market_state.failure.code is NextBarOpenFailureCode.FUTURE_MARKET_STATE


def test_order_state_and_candidate_context_fail_closed() -> None:
    stream = accepted_journey()["accepted_stream"]
    assert stream.state is not None
    created_only = type(stream).from_records(stream.order, stream.records[:1])
    invalid_state = model().simulate_execution(
        replace(request(bar_candidate=candidate()), order_stream=created_only)
    )
    assert isinstance(invalid_state.failure, NextBarOpenFailure)
    assert invalid_state.failure.code is NextBarOpenFailureCode.ORDER_STATE_INELIGIBLE
    observation = candidate().observation
    assert observation.open_price is not None
    with pytest.raises(ValueError, match="instrument"):
        replace(
            observation,
            open_price=replace(
                observation.open_price,
                instrument_id="synthetic:cash:eth-usd",
            ),
        )


def test_execution_contracts_have_no_future_bar_or_partial_fill_fields() -> None:
    forbidden = {"high", "low", "close", "volume", "partial_fill", "queue"}
    observed_fields = {field.name for field in fields(type(candidate().observation))}
    candidate_fields = {field.name for field in fields(type(candidate()))}
    request_fields = {field.name for field in fields(type(request()))}

    assert observed_fields.isdisjoint(forbidden)
    assert candidate_fields.isdisjoint(forbidden)
    assert request_fields.isdisjoint(forbidden)
    with pytest.raises(ValueError, match="exact fields"):
        candidate(extra_payload={"high": 3_200_000})
