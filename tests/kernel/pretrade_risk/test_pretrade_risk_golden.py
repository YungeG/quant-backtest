from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading import PreTradeRiskEvaluator

from ._fixtures import availability_state, evaluation_input, reservation_state


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/exact-pretrade-risk-decision-v1.json"


def canonical_json(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid canonical PreTrade Risk evidence: {error}")


def test_pretrade_risk_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen PreTrade Risk fixture: {error}")

    approved = PreTradeRiskEvaluator().evaluate(evaluation_input())
    state = reservation_state()
    rejected = PreTradeRiskEvaluator().evaluate(
        evaluation_input(
            state=state,
            availability=availability_state(
                state,
                usd_tradable_units=6_007_599,
                include_eur=True,
            ),
        )
    )
    assert approved.approval is not None
    assert rejected.rejection is not None

    actual = {
        "fixture_id": "exact-pretrade-risk-decision-v1",
        "policy_hash": approved.approval.evaluation_input.account_risk_policy.policy_hash,
        "requirement_hash": (
            approved.approval.evaluation_input.resource_requirement.requirement_hash
        ),
        "approval_input_hash": approved.approval.evaluation_input.input_hash,
        "approval_checks": [
            canonical_json(check) for check in approved.approval.checks
        ],
        "approval_decision_id": approved.approval.decision_id,
        "approval_decision_hash": approved.approval.decision_hash,
        "approval_outcome_hash": approved.outcome_hash,
        "rejection_input_hash": rejected.rejection.evaluation_input.input_hash,
        "rejection_checks": [
            canonical_json(check) for check in rejected.rejection.checks
        ],
        "rejection_decision_id": rejected.rejection.decision_id,
        "rejection_decision_hash": rejected.rejection.decision_hash,
        "rejection_outcome_hash": rejected.outcome_hash,
    }
    assert actual == expected
