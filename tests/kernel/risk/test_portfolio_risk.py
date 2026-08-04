from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import CurrencyId, InstrumentId, Money, Scale
from crypto_quant_trading import (
    PortfolioRiskAction,
    PortfolioRiskContractIssueCode,
    PortfolioRiskDecision,
    PortfolioRiskEvaluator,
    PortfolioRiskLimit,
    PortfolioRiskPolicy,
    PortfolioRiskPolicyRef,
    PortfolioRiskReasonCode,
    PortfolioRiskScope,
)

from ._fixtures import (
    NOTIONAL_SCALE,
    allocated_targets,
    expected_policy_config_hash,
    notional,
    policy,
)


def issue_codes(outcome: object) -> set[PortfolioRiskContractIssueCode]:
    failure = getattr(outcome, "failure")
    assert failure is not None
    return {issue.code for issue in failure.issues}


def decisions_by_scope(
    outcome: object,
) -> dict[tuple[PortfolioRiskScope, InstrumentId | None], PortfolioRiskDecision]:
    approved = getattr(outcome, "approved_target")
    assert approved is not None
    return {
        (decision.scope, decision.instrument_id): decision
        for decision in approved.decisions
    }


def test_target_limits_approve_clamp_and_reject_as_economic_decisions() -> None:
    allocation = allocated_targets()
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocation,
        policy=policy(
            btc_max=25_000_000_000_000_000,
            btc_action=PortfolioRiskAction.CLAMP,
            eth_max=20_000_000_000_000_000,
            eth_action=PortfolioRiskAction.REJECT,
        ),
    )

    assert outcome.failure is None
    assert outcome.approved_target is not None
    targets = {
        target.source_target.instrument_id: target
        for target in outcome.approved_target.targets
    }
    long_target = next(
        target.instrument_id
        for target in allocation.net_targets
        if target.target_notional.units > 0
    )
    short_target = next(
        target.instrument_id
        for target in allocation.net_targets
        if target.target_notional.units < 0
    )
    assert targets[long_target].approved_notional.units == 25_000_000_000_000_000
    assert targets[short_target].approved_notional.units == 0
    assert all(target.source_target.sleeve_attributions for target in targets.values())

    decisions = decisions_by_scope(outcome)
    target_decisions = [
        decision
        for (scope, _), decision in decisions.items()
        if scope is PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL
    ]
    assert {decision.action for decision in target_decisions} == {
        PortfolioRiskAction.CLAMP,
        PortfolioRiskAction.REJECT,
    }
    assert {decision.reason_code for decision in target_decisions} == {
        PortfolioRiskReasonCode.TARGET_LIMIT_EXCEEDED
    }
    assert outcome.approved_target.gross_exposure.units == 25_000_000_000_000_000
    assert outcome.approved_target.net_exposure.units == 25_000_000_000_000_000
    assert outcome.approved_target.economic_rejected


def test_within_limits_produce_approve_decisions() -> None:
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(),
        policy=policy(),
    )

    assert outcome.failure is None
    assert outcome.approved_target is not None
    assert all(
        decision.action is PortfolioRiskAction.APPROVE
        for decision in outcome.approved_target.decisions
    )
    assert all(
        decision.reason_code is PortfolioRiskReasonCode.WITHIN_LIMIT
        for decision in outcome.approved_target.decisions
    )
    assert outcome.approved_target.gross_exposure.units == 60_000_000_000_000_000
    assert outcome.approved_target.net_exposure.units == 0
    assert not outcome.approved_target.economic_rejected


def test_gross_limit_rejects_the_whole_target_set_without_contract_failure() -> None:
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(),
        policy=policy(gross_max=50_000_000_000_000_000),
    )

    assert outcome.failure is None
    assert outcome.approved_target is not None
    assert all(target.approved_notional.units == 0 for target in outcome.approved_target.targets)
    assert outcome.approved_target.gross_exposure.units == 0
    assert outcome.approved_target.net_exposure.units == 0
    gross = decisions_by_scope(outcome)[(PortfolioRiskScope.GROSS_EXPOSURE, None)]
    assert gross.action is PortfolioRiskAction.REJECT
    assert gross.before_notional.units == 60_000_000_000_000_000
    assert gross.after_notional.units == 0
    assert gross.reason_code is PortfolioRiskReasonCode.GROSS_LIMIT_EXCEEDED


def test_absolute_net_limit_rejects_the_whole_target_set() -> None:
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(carry_units=500_000_000_000),
        policy=policy(
            gross_max=60_000_000_000_000_000,
            net_max=40_000_000_000_000_000,
        ),
    )

    assert outcome.failure is None
    assert outcome.approved_target is not None
    assert all(target.approved_notional.units == 0 for target in outcome.approved_target.targets)
    net = decisions_by_scope(outcome)[
        (PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE, None)
    ]
    assert net.action is PortfolioRiskAction.REJECT
    assert net.before_notional.units == 50_000_000_000_000_000
    assert net.reason_code is PortfolioRiskReasonCode.ABSOLUTE_NET_LIMIT_EXCEEDED


def test_policy_and_input_order_do_not_change_approved_target_identity() -> None:
    allocation = allocated_targets()
    reversed_allocation = replace(
        allocation,
        net_targets=tuple(reversed(allocation.net_targets)),
    )

    first = PortfolioRiskEvaluator().evaluate(
        allocation=allocation,
        policy=policy(),
    )
    reordered = PortfolioRiskEvaluator().evaluate(
        allocation=reversed_allocation,
        policy=policy(reverse=True),
    )

    assert first.approved_target is not None
    assert reordered.approved_target is not None
    assert first.approved_target == reordered.approved_target
    assert (
        first.approved_target.approved_target_hash
        == reordered.approved_target.approved_target_hash
    )


def test_missing_policy_and_policy_context_or_coverage_fail_structurally() -> None:
    allocation = allocated_targets()
    evaluator = PortfolioRiskEvaluator()

    missing = evaluator.evaluate(allocation=allocation, policy=None)
    wrong_context = evaluator.evaluate(
        allocation=allocation,
        policy=policy(currency=CurrencyId("EUR"), scale=Scale(13)),
    )
    incomplete = evaluator.evaluate(
        allocation=allocation,
        policy=policy(include_eth=False, extra_instrument=True),
    )

    assert missing.approved_target is None
    assert issue_codes(missing) == {PortfolioRiskContractIssueCode.MISSING_POLICY}
    assert issue_codes(wrong_context) == {
        PortfolioRiskContractIssueCode.VALUATION_CURRENCY_MISMATCH,
        PortfolioRiskContractIssueCode.NOTIONAL_SCALE_MISMATCH,
    }
    assert issue_codes(incomplete) == {
        PortfolioRiskContractIssueCode.MISSING_INSTRUMENT_LIMIT,
        PortfolioRiskContractIssueCode.UNEXPECTED_INSTRUMENT_LIMIT,
    }


def test_policy_definition_fails_closed_for_bad_hash_or_aggregate_clamp() -> None:
    valid = policy()
    assert valid.policy_ref.config_hash == expected_policy_config_hash(valid)

    with pytest.raises(ValueError, match="config_hash"):
        replace(
            valid,
            policy_ref=PortfolioRiskPolicyRef(
                policy_key=valid.policy_ref.policy_key,
                policy_version=valid.policy_ref.policy_version,
                config_hash="sha256:" + "0" * 64,
            ),
        )

    with pytest.raises(ValueError, match="aggregate"):
        PortfolioRiskLimit(
            limit_id="aggregate.invalid-clamp.v1",
            scope=PortfolioRiskScope.GROSS_EXPOSURE,
            maximum=Money(1, NOTIONAL_SCALE, "USD"),
            breach_action=PortfolioRiskAction.CLAMP,
            instrument_id=None,
        )


def test_risk_decision_invariants_reject_noncanonical_transformations() -> None:
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(),
        policy=policy(btc_max=25_000_000_000_000_000),
    )
    assert outcome.approved_target is not None
    clamp = next(
        decision
        for decision in outcome.approved_target.decisions
        if decision.action is PortfolioRiskAction.CLAMP
    )

    with pytest.raises(ValueError, match="clamp"):
        replace(clamp, after_notional=notional(26_000_000_000_000_000))

    with pytest.raises(ValueError, match="duplicate risk decision"):
        replace(
            outcome.approved_target,
            decisions=(
                *outcome.approved_target.decisions,
                outcome.approved_target.decisions[0],
            ),
        )
