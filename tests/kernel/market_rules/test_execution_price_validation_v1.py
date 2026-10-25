from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from crypto_quant_domain import Price, Scale, canonical_bytes
from crypto_quant_trading import MarketRuleApproval, MarketRuleEvaluator, MarketRuleIssueCode

from ._fixtures import (
    evaluation_input,
    limit_intent,
    limit_notional_evidence,
    order_with_intent,
    reference_notional_evidence,
    timeline,
    translated_spec,
)


def _approval(price: Price | None = None) -> MarketRuleApproval:
    evidence = reference_notional_evidence()
    if price is not None:
        evidence = replace(evidence, price=price)
    decision = MarketRuleEvaluator().evaluate(
        evaluation_input(notional_evidence=evidence), timeline()
    )
    assert decision.approval is not None
    return decision.approval


def test_execution_price_validation_is_static_and_preserves_approval_bytes() -> None:
    approval = _approval()
    price = approval.evaluation_input.notional_evidence.price
    before = canonical_bytes(approval)
    assert MarketRuleEvaluator.validate_execution_price(approval, price) == ()
    assert MarketRuleEvaluator().validate_execution_price(approval, price) == ()
    assert canonical_bytes(approval) == before
    assert canonical_bytes(_approval()) == before


@pytest.mark.parametrize(
    ("units", "expected"),
    (
        (3_000_003, (MarketRuleIssueCode.PRICE_TICK,)),
        (4_000_005, (MarketRuleIssueCode.PRICE_LIMIT,)),
        (1_999_995, (MarketRuleIssueCode.PRICE_LIMIT,)),
        (4_000_003, (MarketRuleIssueCode.PRICE_TICK, MarketRuleIssueCode.PRICE_LIMIT)),
    ),
)
def test_supplied_execution_price_checks_tick_and_limits_without_clipping(
    units: int, expected: tuple[MarketRuleIssueCode, ...]
) -> None:
    price = replace(reference_notional_evidence().price, units=units)
    approval = _approval(price)
    before = canonical_bytes(approval)
    issues = MarketRuleEvaluator.validate_execution_price(approval, price)
    assert tuple(issue.code for issue in issues) == expected
    assert all(issue.subject_key == "execution_price" for issue in issues)
    assert approval.evaluation_input.notional_evidence.price == price
    assert canonical_bytes(approval) == before


def test_supplied_execution_price_checks_scale_without_conversion() -> None:
    price = replace(reference_notional_evidence().price, units=30_000_000, scale=Scale(3))
    approval = _approval(price)
    issues = MarketRuleEvaluator.validate_execution_price(approval, price)
    assert tuple(issue.code for issue in issues) == (MarketRuleIssueCode.PRICE_SCALE,)
    assert issues[0].subject_key == "execution_price"


def test_price_must_match_this_approval_not_another_quote() -> None:
    approval = _approval()
    other = _approval(replace(reference_notional_evidence().price, units=3_000_005))
    with pytest.raises(ValueError, match="equal approval"):
        MarketRuleEvaluator.validate_execution_price(
            approval, other.evaluation_input.notional_evidence.price
        )
    with pytest.raises(ValueError, match="equal approval"):
        MarketRuleEvaluator.validate_execution_price(
            approval, replace(approval.evaluation_input.notional_evidence.price, instrument_id="foreign:instrument")
        )


def test_constraint_approval_is_not_execution_reference_authority() -> None:
    intent = limit_intent()
    decision = MarketRuleEvaluator().evaluate(
        evaluation_input(
            spec=translated_spec(order_with_intent(intent)),
            notional_evidence=limit_notional_evidence(intent),
        ),
        timeline(),
    )
    assert decision.approval is not None
    with pytest.raises(ValueError, match="SUPPLIED_REFERENCE"):
        MarketRuleEvaluator.validate_execution_price(
            decision.approval, decision.approval.evaluation_input.notional_evidence.price
        )


def test_execution_price_validation_requires_exact_types() -> None:
    approval = _approval()
    price = approval.evaluation_input.notional_evidence.price
    with pytest.raises(TypeError, match="exact MarketRuleApproval"):
        MarketRuleEvaluator.validate_execution_price(cast(Any, object()), price)
    with pytest.raises(TypeError, match="exact Price"):
        MarketRuleEvaluator.validate_execution_price(approval, cast(Any, price.units))

    class DerivedPrice(Price):
        pass

    class DerivedApproval(MarketRuleApproval):
        pass

    with pytest.raises(TypeError, match="exact Price"):
        MarketRuleEvaluator.validate_execution_price(
            approval, DerivedPrice(price.units, price.scale, price.instrument_id, price.quote_currency)
        )
    with pytest.raises(TypeError, match="exact MarketRuleApproval"):
        MarketRuleEvaluator.validate_execution_price(
            DerivedApproval(
                approval.decision_id, approval.evaluation_input, approval.rule_timeline,
                approval.resolved_interval, approval.calculated_notional,
            ),
            price,
        )
