from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import UtcInstant, canonical_bytes
from crypto_quant_trading import AtomicDecisionBatchCollector

from ._fixtures import BTC, CARRY, ETH, TREND, submission


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/atomic-decision-batch-v1.json"


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid atomic decision batch fixture: {FIXTURE}") from error


def canonical_value(value: object) -> object:
    return json.loads(canonical_bytes(value))


def test_complete_batch_and_latest_state_match_golden() -> None:
    fixture = load_fixture()

    result = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(CARRY, TREND),
        submissions=(
            submission(TREND, instrument_id=BTC),
            submission(CARRY, instrument_id=ETH, units=-250_000_000_000),
        ),
    )

    assert result.failure is None
    assert result.batch is not None
    assert result.state is not None
    assert canonical_value(result.batch) == fixture["expected_batch"]
    assert result.batch_hash == fixture["expected_batch_sha256"]
    assert canonical_value(result.state) == fixture["expected_state"]
    assert result.state_hash == fixture["expected_state_sha256"]


def test_atomic_failure_matches_golden_without_partial_authority() -> None:
    fixture = load_fixture()

    result = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(TREND, CARRY),
        submissions=(submission(TREND),),
    )

    assert result.batch is None
    assert result.state is None
    assert result.failure is not None
    assert canonical_value(result.failure) == fixture["expected_failure"]
    assert result.failure.failure_hash == fixture["expected_failure_sha256"]
