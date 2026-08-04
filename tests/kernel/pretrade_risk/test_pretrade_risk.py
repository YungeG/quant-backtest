from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crypto_quant_domain import Money, OrderSide, Quantity, Scale, UtcInstant
from crypto_quant_trading import (
    AccountRiskPolicy,
    ExposureCapacityLimit,
    FeeReserveFundingSource,
    PreTradeRiskContractIssueCode,
    PreTradeRiskEvaluator,
    PreTradeRiskReasonCode,
    ReservationCommitment,
)

from ._fixtures import (
    EUR,
    MONEY_SCALE,
    USD,
    availability_state,
    evaluation_input,
    fee_proposal,
    policy,
    requirement,
    reservation_state,
)


def test_approves_unchanged_order_against_exact_available_resources() -> None:
    source = evaluation_input()

    outcome = PreTradeRiskEvaluator().evaluate(source)

    assert outcome.approval is not None
    assert outcome.rejection is None
    assert outcome.contract_failure is None
    assert outcome.approval.evaluation_input == source
    assert outcome.approval.order == (
        source.market_rule_approval.evaluation_input.executable_order_spec.source_order
    )
    assert all(check.approved for check in outcome.approval.checks)
    assert source.resource_requirement.commitment.fee_reserve == (
        source.fee_reservation_proposal.fee_estimate.total_fee,
    )


def test_insufficient_tradable_cash_is_economic_rejection_not_contract_failure() -> None:
    state = reservation_state()
    source = evaluation_input(
        state=state,
        availability=availability_state(
            state,
            usd_tradable_units=6_007_599,
            include_eur=True,
        ),
    )
    original_spec = source.market_rule_approval.evaluation_input.executable_order_spec

    outcome = PreTradeRiskEvaluator().evaluate(source)

    assert outcome.approval is None
    assert outcome.contract_failure is None
    assert outcome.rejection is not None
    assert outcome.rejection.order.intent == original_spec.source_order.intent
    assert PreTradeRiskReasonCode.TRADABLE_CASH in (
        check.reason_code
        for check in outcome.rejection.checks
        if not check.approved
    )


def test_account_permission_rejection_is_economic_and_does_not_replan() -> None:
    source = evaluation_input(
        risk_policy=policy(
            allowed_sides=(OrderSide.SELL,),
            exposure_limits=(
                ExposureCapacityLimit(Money(20_000_000, MONEY_SCALE, str(USD))),
                ExposureCapacityLimit(Money(100_000, MONEY_SCALE, str(EUR))),
            ),
        )
    )

    outcome = PreTradeRiskEvaluator().evaluate(source)

    assert outcome.contract_failure is None
    assert outcome.rejection is not None
    failed = tuple(check for check in outcome.rejection.checks if not check.approved)
    assert failed[0].reason_code is PreTradeRiskReasonCode.ACCOUNT_PERMISSION
    assert failed[0].subject_key == "side:buy"


def test_fee_reserve_can_explicitly_use_available_margin() -> None:
    fee = fee_proposal().commitment.fee_reserve
    commitment = ReservationCommitment(
        margin=(Money(7_999_000, MONEY_SCALE, str(USD)),),
        fee_reserve=fee,
        order_capacity_units=1,
        exposure_capacity=(Money(6_000_000, MONEY_SCALE, str(USD)),),
    )
    source = evaluation_input(
        resource_requirement=requirement(commitment=commitment),
        risk_policy=policy(
            funding_source=FeeReserveFundingSource.AVAILABLE_MARGIN,
        ),
    )

    outcome = PreTradeRiskEvaluator().evaluate(source)

    assert outcome.rejection is not None
    assert outcome.contract_failure is None
    assert PreTradeRiskReasonCode.AVAILABLE_MARGIN in (
        check.reason_code
        for check in outcome.rejection.checks
        if not check.approved
    )


def test_sellable_quantity_and_capacity_are_compared_without_cross_netting() -> None:
    proposal = fee_proposal()
    approval = proposal.fee_estimate.market_rule_approval
    instrument = approval.evaluation_input.executable_order_spec.source_order.intent.instrument_id
    commitment = ReservationCommitment(
        sellable_quantities=(Quantity(5_001, Scale(3), str(instrument)),),
        fee_reserve=proposal.commitment.fee_reserve,
        order_capacity_units=6,
        exposure_capacity=(Money(20_000_001, MONEY_SCALE, str(USD)),),
    )
    source = evaluation_input(resource_requirement=requirement(commitment=commitment))

    outcome = PreTradeRiskEvaluator().evaluate(source)

    assert outcome.rejection is not None
    failed_codes = {
        check.reason_code
        for check in outcome.rejection.checks
        if not check.approved
    }
    assert failed_codes == {
        PreTradeRiskReasonCode.SELLABLE_QUANTITY,
        PreTradeRiskReasonCode.ORDER_CAPACITY,
        PreTradeRiskReasonCode.EXPOSURE_CAPACITY,
    }


def test_stale_availability_and_fee_mismatch_are_contract_failures() -> None:
    source = evaluation_input()
    stale = replace(
        source,
        availability_state=replace(
            source.availability_state,
            reservation_state_hash="sha256:" + "9" * 64,
        ),
    )
    fee_mismatch = replace(
        source,
        resource_requirement=requirement(
            commitment=replace(
                source.resource_requirement.commitment,
                fee_reserve=(Money(1, MONEY_SCALE, str(USD)),),
            )
        ),
    )

    stale_outcome = PreTradeRiskEvaluator().evaluate(stale)
    fee_outcome = PreTradeRiskEvaluator().evaluate(fee_mismatch)

    assert stale_outcome.contract_failure is not None
    assert stale_outcome.contract_failure.codes == (
        PreTradeRiskContractIssueCode.RESERVATION_STATE_MISMATCH,
    )
    assert fee_outcome.contract_failure is not None
    assert fee_outcome.contract_failure.codes == (
        PreTradeRiskContractIssueCode.FEE_RESERVE_MISMATCH,
    )
    assert stale_outcome.approval is None and stale_outcome.rejection is None
    assert fee_outcome.approval is None and fee_outcome.rejection is None


def test_missing_availability_and_exposure_limit_fail_structurally() -> None:
    source = evaluation_input()
    no_cash = replace(source.availability_state, cash=())
    no_eur_limit = policy(
        exposure_limits=(
            ExposureCapacityLimit(Money(20_000_000, MONEY_SCALE, str(USD))),
        )
    )

    missing_cash = PreTradeRiskEvaluator().evaluate(
        replace(source, availability_state=no_cash)
    )
    missing_limit = PreTradeRiskEvaluator().evaluate(
        replace(source, account_risk_policy=no_eur_limit)
    )

    assert missing_cash.contract_failure is not None
    assert PreTradeRiskContractIssueCode.MISSING_CASH_AVAILABILITY in (
        missing_cash.contract_failure.codes
    )
    assert missing_limit.contract_failure is not None
    assert missing_limit.contract_failure.codes == (
        PreTradeRiskContractIssueCode.MISSING_EXPOSURE_LIMIT,
    )


def test_early_evaluation_and_account_context_mismatch_fail_structurally() -> None:
    source = evaluation_input()
    early = PreTradeRiskEvaluator().evaluate(
        replace(source, evaluated_at=UtcInstant(159))
    )
    foreign_policy = AccountRiskPolicy.create(
        policy_key=source.account_risk_policy.policy_key,
        policy_version=source.account_risk_policy.policy_version,
        account_id="account:other",
        venue_id=source.account_risk_policy.venue_id,
        allowed_sides=source.account_risk_policy.allowed_sides,
        allowed_position_effects=source.account_risk_policy.allowed_position_effects,
        allowed_reduce_only_values=(
            source.account_risk_policy.allowed_reduce_only_values
        ),
        fee_reserve_funding_source=(
            source.account_risk_policy.fee_reserve_funding_source
        ),
        order_capacity_limit=source.account_risk_policy.order_capacity_limit,
        exposure_capacity_limits=(
            source.account_risk_policy.exposure_capacity_limits
        ),
    )
    foreign = PreTradeRiskEvaluator().evaluate(
        replace(source, account_risk_policy=foreign_policy)
    )

    assert early.contract_failure is not None
    assert early.contract_failure.codes == (
        PreTradeRiskContractIssueCode.EVALUATION_BEFORE_FEE_ESTIMATION,
    )
    assert foreign.contract_failure is not None
    assert PreTradeRiskContractIssueCode.ACCOUNT_CONTEXT_MISMATCH in (
        foreign.contract_failure.codes
    )


def test_requirement_and_policy_tuple_order_do_not_change_decision_identity() -> None:
    first = evaluation_input()
    reversed_requirement = requirement(reverse=True)
    reversed_policy = AccountRiskPolicy.create(
        policy_key=first.account_risk_policy.policy_key,
        policy_version=first.account_risk_policy.policy_version,
        account_id=first.account_risk_policy.account_id,
        venue_id=first.account_risk_policy.venue_id,
        allowed_sides=tuple(reversed(first.account_risk_policy.allowed_sides)),
        allowed_position_effects=tuple(
            reversed(first.account_risk_policy.allowed_position_effects)
        ),
        allowed_reduce_only_values=tuple(
            reversed(first.account_risk_policy.allowed_reduce_only_values)
        ),
        fee_reserve_funding_source=(
            first.account_risk_policy.fee_reserve_funding_source
        ),
        order_capacity_limit=first.account_risk_policy.order_capacity_limit,
        exposure_capacity_limits=tuple(
            reversed(first.account_risk_policy.exposure_capacity_limits)
        ),
    )
    second = replace(
        first,
        resource_requirement=reversed_requirement,
        account_risk_policy=reversed_policy,
    )

    first_outcome = PreTradeRiskEvaluator().evaluate(first)
    second_outcome = PreTradeRiskEvaluator().evaluate(second)

    assert first_outcome == second_outcome
    assert first_outcome.outcome_hash == second_outcome.outcome_hash


def test_policy_and_contract_values_are_immutable_and_fail_closed() -> None:
    risk_policy = policy()
    with pytest.raises(FrozenInstanceError):
        risk_policy.order_capacity_limit = 99  # type: ignore[misc]
    with pytest.raises(ValueError, match="config_hash mismatch"):
        replace(risk_policy, config_hash="sha256:" + "0" * 64)

    with pytest.raises(ValueError, match="duplicate allowed OrderSide"):
        AccountRiskPolicy.create(
            policy_key=risk_policy.policy_key,
            policy_version=risk_policy.policy_version,
            account_id=risk_policy.account_id,
            venue_id=risk_policy.venue_id,
            allowed_sides=(OrderSide.BUY, OrderSide.BUY),
            allowed_position_effects=risk_policy.allowed_position_effects,
            allowed_reduce_only_values=risk_policy.allowed_reduce_only_values,
            fee_reserve_funding_source=risk_policy.fee_reserve_funding_source,
            order_capacity_limit=risk_policy.order_capacity_limit,
            exposure_capacity_limits=risk_policy.exposure_capacity_limits,
        )

    valid_requirement = requirement()
    with pytest.raises(ValueError, match="requirement_id mismatch"):
        replace(valid_requirement, requirement_id="pretrade-requirement-v1:bad")
