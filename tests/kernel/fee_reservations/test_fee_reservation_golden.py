from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading import FeeReservationEstimator

from ._fixtures import estimate_time, market_rule_approval, rule_set


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/worst-case-fee-reservation-v1.json"


def canonical_json(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid canonical Fee Reservation evidence: {error}")


def test_fee_reservation_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Fee Reservation fixture: {error}")

    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), rule_set(), estimate_time()
    )
    assert outcome.estimate is not None
    assert outcome.proposal is not None

    actual = {
        "fixture_id": "worst-case-fee-reservation-v1",
        "rule_set_hash": outcome.estimate.rule_set.rule_set_hash,
        "market_rule_decision_id": outcome.estimate.market_rule_approval.decision_id,
        "lines": [canonical_json(line) for line in outcome.estimate.lines],
        "total_fee": canonical_json(outcome.estimate.total_fee),
        "estimate_id": outcome.estimate.estimate_id,
        "estimate_hash": outcome.estimate.estimate_hash,
        "proposal_id": outcome.proposal.proposal_id,
        "proposal_hash": outcome.proposal.proposal_hash,
        "outcome_hash": outcome.outcome_hash,
    }
    assert actual == expected
