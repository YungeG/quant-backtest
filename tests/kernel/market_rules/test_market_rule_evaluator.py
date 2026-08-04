from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    InstrumentId,
    OrderSide,
    PositionEffect,
    Price,
    Quantity,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    MarketRuleDataIntegrityCode,
    MarketRuleEvaluator,
    MarketRuleIssueCode,
    MarketSessionState,
    NotionalPriceBasis,
    OrderRuleInterval,
    OrderRuleNotionalEvidence,
    OrderRuleSnapshot,
    OrderRuleTimeline,
)
from tests.kernel.capabilities._fixtures import INSTRUMENT, PRICE_SCALE, intent

from ._fixtures import (
    evaluation_input,
    interval,
    lattice,
    limit_intent,
    limit_notional_evidence,
    order_with_intent,
    reference_notional_evidence,
    snapshot,
    supplemental_decisions,
    timeline,
    translated_spec,
)


def issue_codes(decision: object) -> tuple[MarketRuleIssueCode, ...]:
    rejection = getattr(decision, "rejection")
    assert rejection is not None
    return tuple(issue.code for issue in rejection.issues)


def test_approves_exact_rules_without_mutating_the_executable_spec() -> None:
    request = evaluation_input()
    rules = timeline()
    source_hash = request.executable_order_spec.spec_hash

    decision = MarketRuleEvaluator().evaluate(request, rules)

    assert decision.approval is not None
    assert decision.rejection is None
    assert decision.data_integrity_failure is None
    assert decision.approval.evaluation_input == request
    assert decision.approval.rule_timeline == rules
    assert decision.approval.resolved_interval == rules.intervals[0]
    assert decision.approval.calculated_notional.units == 6_000_000
    assert decision.approval.calculated_notional.scale == Scale(2)
    assert request.executable_order_spec.spec_hash == source_hash


def test_timeline_and_set_like_input_order_do_not_change_decision_identity() -> None:
    first_snapshot = snapshot()
    second_snapshot = snapshot(
        permitted_sides=(OrderSide.SELL, OrderSide.BUY),
        permitted_position_effects=(
            PositionEffect.CLOSE,
            PositionEffect.OPEN,
            PositionEffect.AUTO,
        ),
        supplemental=supplemental_decisions(reverse=True),
    )
    past = interval(start=0, stop=100, rule_snapshot=first_snapshot)
    active_first = interval(start=100, stop=200, rule_snapshot=first_snapshot)
    active_second = interval(start=100, stop=200, rule_snapshot=second_snapshot)
    request = evaluation_input(evaluated_at=150)

    first = MarketRuleEvaluator().evaluate(
        request, timeline(intervals=(past, active_first))
    )
    second = MarketRuleEvaluator().evaluate(
        request, timeline(intervals=(active_second, past))
    )

    assert first == second
    assert first.decision_id == second.decision_id
    assert first.decision_hash == second.decision_hash


def test_missing_and_overlapping_intervals_are_data_integrity_failures() -> None:
    request = evaluation_input(evaluated_at=250)
    missing = MarketRuleEvaluator().evaluate(request, timeline())

    assert missing.data_integrity_failure is not None
    assert (
        missing.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.MISSING_RULE_INTERVAL
    )
    assert missing.approval is None
    assert missing.rejection is None

    overlap = timeline(
        intervals=(interval(start=0, stop=300), interval(start=200, stop=400))
    )
    overlapping = MarketRuleEvaluator().evaluate(request, overlap)
    assert overlapping.data_integrity_failure is not None
    assert (
        overlapping.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.OVERLAPPING_RULE_INTERVALS
    )
    assert len(overlapping.data_integrity_failure.candidate_interval_ids) == 2


def test_quantity_scale_step_and_minimum_violations_are_structured() -> None:
    small_intent = replace(
        intent(),
        quantity=Quantity(3, Scale(3), str(INSTRUMENT)),
    )
    request = evaluation_input(spec=translated_spec(order_with_intent(small_intent)))
    rules = timeline(
        intervals=(
            interval(
                rule_snapshot=snapshot(
                    quantity_lattice=lattice(step_units=5, min_quantity_units=10)
                )
            ),
        )
    )

    decision = MarketRuleEvaluator().evaluate(request, rules)

    expected_codes = (
        MarketRuleIssueCode.MINIMUM_QUANTITY,
        MarketRuleIssueCode.QUANTITY_STEP,
    )
    assert issue_codes(decision) == expected_codes
    assert decision.rejection is not None
    assert decision.rejection.evaluation_input.executable_order_spec.intent.quantity.units == 3


def test_price_scale_tick_and_limit_violations_are_structured() -> None:
    source_intent = limit_intent(price_units=4_000_003)
    spec = translated_spec(order_with_intent(source_intent))
    request = evaluation_input(
        spec=spec,
        notional_evidence=limit_notional_evidence(source_intent),
    )

    decision = MarketRuleEvaluator().evaluate(request, timeline())

    expected_codes = (
        MarketRuleIssueCode.PRICE_LIMIT,
        MarketRuleIssueCode.PRICE_TICK,
    )
    assert issue_codes(decision) == expected_codes

    wrong_scale_price = Price(40_000_030, Scale(3), str(INSTRUMENT), "USD")
    source_constraint = source_intent.price_constraint
    assert source_constraint is not None
    wrong_scale_intent = replace(
        source_intent,
        price_constraint=replace(source_constraint, limit_price=wrong_scale_price),
    )
    wrong_scale = MarketRuleEvaluator().evaluate(
        evaluation_input(
            spec=translated_spec(order_with_intent(wrong_scale_intent)),
            notional_evidence=limit_notional_evidence(wrong_scale_intent),
        ),
        timeline(),
    )
    expected_scale_codes = (MarketRuleIssueCode.PRICE_SCALE,)
    assert issue_codes(wrong_scale) == expected_scale_codes


def test_session_permission_and_supplemental_rejections_are_distinct() -> None:
    rules = timeline(
        intervals=(
            interval(
                rule_snapshot=snapshot(
                    session_state=MarketSessionState.CLOSED,
                    permitted_sides=(OrderSide.SELL,),
                    permitted_position_effects=(PositionEffect.CLOSE,),
                    reduce_only_required=True,
                    supplemental=supplemental_decisions(reject=True),
                )
            ),
        )
    )

    decision = MarketRuleEvaluator().evaluate(evaluation_input(), rules)

    expected_codes = (
        MarketRuleIssueCode.POSITION_EFFECT_NOT_PERMITTED,
        MarketRuleIssueCode.REDUCE_ONLY_REQUIRED,
        MarketRuleIssueCode.SESSION_CLOSED,
        MarketRuleIssueCode.SIDE_NOT_PERMITTED,
        MarketRuleIssueCode.SUPPLEMENTAL_RULE_REJECTED,
    )
    assert issue_codes(decision) == expected_codes


def test_notional_evidence_is_explicit_and_minimum_notional_is_checked() -> None:
    low_reference = reference_notional_evidence(price_units=400)
    low_notional = MarketRuleEvaluator().evaluate(
        evaluation_input(notional_evidence=low_reference), timeline()
    )
    expected_codes = (MarketRuleIssueCode.MINIMUM_NOTIONAL,)
    assert issue_codes(low_notional) == expected_codes

    source_intent = limit_intent()
    source_spec = translated_spec(order_with_intent(source_intent))
    wrong_constraint_price = Price(
        2_999_999, PRICE_SCALE, str(INSTRUMENT), "USD"
    )
    invalid_constraint = OrderRuleNotionalEvidence(
        basis=NotionalPriceBasis.LIMIT_CONSTRAINT,
        price=wrong_constraint_price,
        source_hash=canonical_sha256(wrong_constraint_price),
        available_at=None,
    )
    invalid = MarketRuleEvaluator().evaluate(
        evaluation_input(spec=source_spec, notional_evidence=invalid_constraint),
        timeline(),
    )
    assert invalid.data_integrity_failure is not None
    assert (
        invalid.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.INVALID_NOTIONAL_EVIDENCE
    )

    future_reference = reference_notional_evidence(available_at=151)
    future = MarketRuleEvaluator().evaluate(
        evaluation_input(notional_evidence=future_reference), timeline()
    )
    assert future.data_integrity_failure is not None
    assert (
        future.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.INVALID_NOTIONAL_EVIDENCE
    )


def test_context_failures_and_forged_hashes_fail_closed() -> None:
    before_translation = MarketRuleEvaluator().evaluate(
        evaluation_input(evaluated_at=109), timeline()
    )
    assert before_translation.data_integrity_failure is not None
    assert (
        before_translation.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.EVALUATION_BEFORE_TRANSLATION
    )

    other_instrument = InstrumentId(VenueId("synthetic"), "cash:eth-usd")
    other_intent = replace(
        intent(),
        instrument_id=other_instrument,
        quantity=Quantity(2_000, Scale(3), str(other_instrument)),
    )
    wrong_instrument = MarketRuleEvaluator().evaluate(
        evaluation_input(spec=translated_spec(order_with_intent(other_intent))),
        timeline(),
    )
    assert wrong_instrument.data_integrity_failure is not None
    assert (
        wrong_instrument.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.INSTRUMENT_CONTEXT_MISMATCH
    )

    valid_snapshot = snapshot()
    with pytest.raises(ValueError, match="config_hash"):
        replace(valid_snapshot, config_hash="sha256:" + "0" * 64)

    valid_timeline = timeline()
    with pytest.raises(ValueError, match="config_hash"):
        replace(valid_timeline, config_hash="sha256:" + "0" * 64)

    with pytest.raises(TypeError, match="evaluation_input"):
        MarketRuleEvaluator().evaluate(object(), valid_timeline)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="rule_timeline"):
        MarketRuleEvaluator().evaluate(evaluation_input(), object())  # type: ignore[arg-type]


def test_interval_requires_a_nonempty_half_open_range() -> None:
    with pytest.raises(ValueError, match="effective interval"):
        OrderRuleInterval.create(
            effective_from=UtcInstant(100),
            effective_to_exclusive=UtcInstant(100),
            snapshot=snapshot(),
        )

    valid_snapshot = snapshot()
    wrong_component = replace(
        valid_snapshot.component_ref,
        port_type=next(
            value
            for value in type(valid_snapshot.component_ref.port_type)
            if value is not valid_snapshot.component_ref.port_type
        ),
    )
    with pytest.raises(ValueError, match="ORDER_RULE_MODEL"):
        replace(valid_snapshot, component_ref=wrong_component)
