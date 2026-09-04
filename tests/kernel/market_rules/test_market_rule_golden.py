from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_trading import MarketRuleEvaluator

from ._fixtures import evaluation_input, timeline


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/point-in-time-market-rule-evaluation-v1.json"


def test_market_rule_evaluation_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Market Rule fixture: {error}")

    result = MarketRuleEvaluator().evaluate(evaluation_input(), timeline())
    assert result.approval is not None
    approval = result.approval

    actual = {
        "fixture_id": "point-in-time-market-rule-evaluation-v1",
        "timeline": {
            "config_hash": approval.rule_timeline.config_hash,
            "timeline_hash": approval.rule_timeline.timeline_hash,
        },
        "interval": {
            "interval_id": approval.resolved_interval.interval_id,
            "interval_hash": approval.resolved_interval.interval_hash,
            "snapshot_hash": approval.resolved_interval.snapshot.snapshot_hash,
        },
        "notional_evidence_hash": approval.evaluation_input.notional_evidence.evidence_hash,
        "calculated_notional": approval.calculated_notional.to_canonical_dict(),
        "decision_id": approval.decision_id,
        "decision_hash": result.decision_hash,
    }
    assert actual == expected
