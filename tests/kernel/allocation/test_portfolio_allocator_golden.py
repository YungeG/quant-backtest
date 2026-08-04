from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import Scale, UtcInstant, canonical_bytes
from crypto_quant_trading import LatestSleeveDecisionState, PortfolioAllocator

from ._fixtures import (
    NOTIONAL_SCALE,
    TREND,
    allocations,
    decision,
    snapshot,
    state,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/capital-allocation-netting-v1.json"


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid capital allocation fixture: {FIXTURE}") from error


def canonical_value(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise AssertionError("canonical value is not valid JSON") from error


def test_net_allocation_matches_golden() -> None:
    fixture = load_fixture()
    portfolio_snapshot = snapshot()
    outcome = PortfolioAllocator().allocate(
        sleeve_state=state(),
        portfolio_snapshot=portfolio_snapshot,
        allocations=allocations(portfolio_snapshot),
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert outcome.failure is None
    assert outcome.allocation is not None
    assert canonical_value(outcome.allocation) == fixture["expected_allocation"]
    assert outcome.allocation.allocation_hash == fixture["expected_allocation_sha256"]


def test_inexact_allocation_failure_matches_golden() -> None:
    fixture = load_fixture()
    portfolio_snapshot = snapshot()
    inexact_state = LatestSleeveDecisionState(
        as_of=UtcInstant(100),
        decisions=(decision("trend-v1", TREND, 333_333_333_333),),
    )
    outcome = PortfolioAllocator().allocate(
        sleeve_state=inexact_state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=(allocations(portfolio_snapshot)[0],),
        target_notional_scale=Scale(2),
    )

    assert outcome.allocation is None
    assert outcome.failure is not None
    assert canonical_value(outcome.failure) == fixture["expected_failure"]
    assert outcome.failure.failure_hash == fixture["expected_failure_sha256"]
