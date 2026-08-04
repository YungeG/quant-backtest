from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_trading import PortfolioSnapshotProjector

from ._fixtures import snapshot_inputs


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures/kernel/portfolio-snapshot-projection-v1.json"
)


def test_portfolio_snapshot_projection_matches_golden_fixture() -> None:
    outcome = PortfolioSnapshotProjector().project(**snapshot_inputs())  # type: ignore[arg-type]
    assert outcome.snapshot is not None
    assert outcome.failure is None
    actual = {
        "fixture_id": "portfolio-snapshot-projection-v1",
        "snapshot": json.loads(canonical_bytes(outcome.snapshot)),
        "snapshot_hash": canonical_sha256(outcome.snapshot),
        "outcome": json.loads(canonical_bytes(outcome)),
    }

    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid portfolio snapshot golden fixture: {error}")
    assert actual == expected
