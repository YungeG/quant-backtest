from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading import PositionSizer, ResidualPositionPolicy

from ._fixtures import (
    BATCH_ID,
    approved_targets,
    sizing_inputs,
    sizing_policy,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/position-sizing-active-target-v1.json"


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid position sizing fixture: {FIXTURE}") from error


def canonical_value(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise AssertionError("canonical value is not valid JSON") from error


def test_position_sizing_materialization_matches_golden() -> None:
    fixture = load_fixture()
    outcome = PositionSizer().materialize(
        approved_target=approved_targets(),
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=sizing_inputs(),
    )

    assert outcome.failure is None
    assert outcome.normalized_target is not None
    assert canonical_value(outcome.normalized_target) == fixture["expected_normalized_target"]
    assert (
        outcome.normalized_target.normalized_target_hash
        == fixture["expected_normalized_target_sha256"]
    )


def test_residual_failure_matches_golden() -> None:
    fixture = load_fixture()
    outcome = PositionSizer().materialize(
        approved_target=approved_targets(),
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(residual=ResidualPositionPolicy.FAIL),
        inputs=sizing_inputs(),
    )

    assert outcome.normalized_target is None
    assert outcome.failure is not None
    assert canonical_value(outcome.failure) == fixture["expected_residual_failure"]
    assert outcome.failure.failure_hash == fixture["expected_residual_failure_sha256"]
