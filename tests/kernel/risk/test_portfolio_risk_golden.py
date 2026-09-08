from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading import PortfolioRiskAction, PortfolioRiskEvaluator

from ._fixtures import allocated_targets, policy


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/portfolio-risk-decisions-v1.json"


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid portfolio risk fixture: {FIXTURE}") from error


def canonical_value(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise AssertionError("canonical value is not valid JSON") from error


def test_mixed_target_risk_decisions_match_golden() -> None:
    fixture = load_fixture()
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(),
        policy=policy(
            btc_max=25_000_000_000_000_000,
            btc_action=PortfolioRiskAction.CLAMP,
            eth_max=20_000_000_000_000_000,
            eth_action=PortfolioRiskAction.REJECT,
        ),
    )

    assert outcome.failure is None
    assert outcome.approved_target is not None
    assert canonical_value(outcome.approved_target) == fixture["expected_approved_target"]
    assert (
        outcome.approved_target.approved_target_hash
        == fixture["expected_approved_target_sha256"]
    )


def test_missing_policy_failure_matches_golden() -> None:
    fixture = load_fixture()
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(),
        policy=None,
    )

    assert outcome.approved_target is None
    assert outcome.failure is not None
    assert canonical_value(outcome.failure) == fixture["expected_missing_policy_failure"]
    assert outcome.failure.failure_hash == fixture["expected_missing_policy_sha256"]
