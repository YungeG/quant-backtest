from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crypto_quant_domain import CurrencyId, Money, Scale, UtcInstant
from crypto_quant_trading import (
    FeeReservationApplicability,
    FeeReservationBasis,
    FeeReservationEstimator,
    FeeReservationFailureCode,
    FeeReservationRuleSet,
)

from ._fixtures import (
    account_ref,
    account_rule,
    estimate_time,
    market_fee_ref,
    market_rule,
    market_rule_approval,
    minimum,
    rule_set,
    tax_ref,
    tax_rule,
)


def test_estimates_worst_case_fee_and_only_proposes_fee_reserve() -> None:
    approval = market_rule_approval()
    rules = rule_set()

    outcome = FeeReservationEstimator().estimate(approval, rules, estimate_time())

    assert outcome.failure is None
    assert outcome.estimate is not None
    assert outcome.proposal is not None
    assert outcome.estimate.total_fee == Money(7_600, Scale(2), "USD")
    expected_amounts = (6_000, 1_500, 100)
    expected_rule_ids = (
        "market_taker_fee",
        "market_order_minimum",
        "account_order_charge",
    )
    assert tuple(
        line.amount.units for line in outcome.estimate.lines
    ) == expected_amounts
    assert tuple(
        line.rule_id for line in outcome.estimate.lines
    ) == expected_rule_ids
    commitment = outcome.proposal.commitment
    expected_fee_reserve = (outcome.estimate.total_fee,)
    assert commitment.fee_reserve == expected_fee_reserve
    assert not commitment.cash
    assert not commitment.sellable_quantities
    assert not commitment.margin
    assert commitment.order_capacity_units == 0
    assert not commitment.exposure_capacity


def test_per_order_minimum_is_applied_once_to_its_declared_scope() -> None:
    source_market_rule = market_rule()
    assert source_market_rule.rate is not None
    second_market_rule = replace(
        source_market_rule,
        rule_id="market_surcharge",
        rate=replace(source_market_rule.rate, units=5),
    )
    scoped_minimum = replace(
        minimum(),
        charge_rule_ids=("market_surcharge", "market_taker_fee"),
    )
    rules = rule_set(
        rules=(account_rule(), tax_rule(), second_market_rule, market_rule()),
        minimums=(scoped_minimum,),
    )

    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), rules, estimate_time()
    )

    assert outcome.estimate is not None
    minimum_lines = [
        line
        for line in outcome.estimate.lines
        if line.basis is FeeReservationBasis.PER_ORDER_MINIMUM
    ]
    assert len(minimum_lines) == 1
    assert minimum_lines[0].amount == Money(0, Scale(2), "USD")
    assert outcome.estimate.total_fee == Money(9_100, Scale(2), "USD")


def test_minimum_does_not_activate_when_its_charge_scope_is_not_applicable() -> None:
    rules = rule_set(
        rules=(
            replace(
                market_rule(),
                applicability=FeeReservationApplicability.NOT_APPLICABLE,
            ),
            tax_rule(),
            replace(
                account_rule(),
                applicability=FeeReservationApplicability.NOT_APPLICABLE,
            ),
        )
    )

    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), rules, estimate_time()
    )

    assert outcome.estimate is not None
    assert outcome.estimate.total_fee == Money(0, Scale(2), "USD")
    assert outcome.proposal is not None
    assert outcome.proposal.commitment.is_empty


def test_unknown_basis_and_applicability_fail_without_partial_output() -> None:
    unknown_basis = replace(
        market_rule(),
        basis=FeeReservationBasis.UNKNOWN,
        rate=None,
    )
    unknown_applicability = replace(
        tax_rule(),
        applicability=FeeReservationApplicability.UNKNOWN,
    )
    rules = rule_set(
        rules=(unknown_basis, unknown_applicability, account_rule()),
        minimums=(),
    )

    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), rules, estimate_time()
    )

    assert outcome.estimate is None
    assert outcome.proposal is None
    assert outcome.failure is not None
    expected_codes = (
        FeeReservationFailureCode.UNKNOWN_APPLICABILITY,
        FeeReservationFailureCode.UNKNOWN_BASIS,
    )
    expected_subjects = ("transaction_tax", "market_taker_fee")
    assert outcome.failure.codes == expected_codes
    assert outcome.failure.subject_rule_ids == expected_subjects


def test_estimation_before_market_rule_evaluation_is_structured_failure() -> None:
    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), rule_set(), UtcInstant(149)
    )

    assert outcome.failure is not None
    expected_codes = (
        FeeReservationFailureCode.ESTIMATION_BEFORE_MARKET_RULE_EVALUATION,
    )
    assert outcome.failure.codes == expected_codes
    assert outcome.estimate is None
    assert outcome.proposal is None


def test_reservation_currency_mismatch_is_structured_failure() -> None:
    eur_rules = FeeReservationRuleSet.create(
        market_fee_policy_ref=market_fee_ref(),
        tax_policy_ref=tax_ref(),
        account_fee_schedule_ref=account_ref(),
        reservation_currency=CurrencyId("EUR"),
        reservation_scale=Scale(2),
        charge_rules=(
            market_rule(),
            tax_rule(),
            replace(account_rule(), flat_amount=Money(100, Scale(2), "EUR")),
        ),
        minimums=(
            replace(minimum(), minimum_amount=Money(7_500, Scale(2), "EUR")),
        ),
    )

    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), eur_rules, estimate_time()
    )

    assert outcome.failure is not None
    expected_codes = (FeeReservationFailureCode.RESERVATION_CURRENCY_MISMATCH,)
    assert outcome.failure.codes == expected_codes
    assert outcome.estimate is None
    assert outcome.proposal is None


def test_rule_and_scope_input_order_do_not_change_identity() -> None:
    first_rules = rule_set()
    second_rules = rule_set(
        rules=tuple(reversed((market_rule(), tax_rule(), account_rule()))),
        minimums=(replace(minimum(), charge_rule_ids=("market_taker_fee",)),),
    )

    first = FeeReservationEstimator().estimate(
        market_rule_approval(), first_rules, estimate_time()
    )
    second = FeeReservationEstimator().estimate(
        market_rule_approval(), second_rules, estimate_time()
    )

    assert first == second
    assert first.outcome_hash == second.outcome_hash
    assert first_rules == second_rules


def test_rule_set_requires_explicit_source_coverage_and_valid_minimum_scope() -> None:
    with pytest.raises(ValueError, match="explicit rule coverage"):
        rule_set(rules=(market_rule(), account_rule()), minimums=())

    with pytest.raises(ValueError, match="unknown charge rule"):
        rule_set(minimums=(replace(minimum(), charge_rule_ids=("missing",)),))

    with pytest.raises(ValueError, match="same source"):
        rule_set(
            minimums=(
                replace(
                    minimum(),
                    charge_rule_ids=("market_taker_fee", "account_order_charge"),
                ),
            )
        )


def test_rule_set_rejects_forged_hash_currency_mismatch_and_overlapping_minima() -> None:
    valid = rule_set()
    with pytest.raises(ValueError, match="config_hash mismatch"):
        replace(valid, config_hash="sha256:" + "0" * 64)

    with pytest.raises(ValueError, match="currency or Scale"):
        rule_set(
            rules=(
                market_rule(),
                tax_rule(),
                replace(
                    account_rule(),
                    flat_amount=Money(100, Scale(2), "EUR"),
                ),
            )
        )

    duplicate_scope = replace(minimum(), minimum_id="second_minimum")
    with pytest.raises(ValueError, match="multiple minimums"):
        rule_set(minimums=(minimum(), duplicate_scope))


def test_contract_values_are_immutable() -> None:
    rules = rule_set()
    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), rules, estimate_time()
    )
    assert outcome.estimate is not None

    with pytest.raises(FrozenInstanceError):
        rules.reservation_scale = Scale(3)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        outcome.estimate.total_fee = Money(0, Scale(2), "USD")  # type: ignore[misc]
