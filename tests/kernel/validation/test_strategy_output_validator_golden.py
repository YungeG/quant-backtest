from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import (
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    canonical_sha256,
)
from crypto_quant_trading import StrategyOutputValidator

from ._fixtures import context


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/strategy-output-validation-v1.json"


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid strategy validation fixture: {FIXTURE}") from error


def validate(payload: dict[str, Any]):
    return StrategyOutputValidator().validate(
        StrategyDecisionCandidate(StrategyDecisionPayload(payload)), context()
    )


def test_valid_candidate_matches_canonical_decision_golden() -> None:
    fixture = load_fixture()

    result = validate(fixture["valid_candidate"])

    assert result.failure is None
    assert result.decision is not None
    assert result.decision.to_canonical_dict() == fixture["expected_decision"]
    assert canonical_sha256(result.decision) == fixture["expected_decision_sha256"]


def test_invalid_candidate_matches_structured_failure_golden() -> None:
    fixture = load_fixture()

    result = validate(fixture["invalid_candidate"])

    assert result.decision is None
    assert result.failure is not None
    assert result.failure.to_canonical_dict() == fixture["expected_failure"]
