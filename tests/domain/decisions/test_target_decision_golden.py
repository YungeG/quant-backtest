from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import (
    ActivePortfolioTarget,
    DecisionBatch,
    InstrumentId,
    Quantity,
    Rate,
    Scale,
    StrategyDecision,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    StrategySleeveId,
    TargetExposureFraction,
    TargetSnapshot,
    UtcInstant,
    VenueId,
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/target-decision-contracts-v1.json"


def load_fixture() -> dict[str, Any]:
    try:
        return cast(
            dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid target decision fixture: {FIXTURE}") from error


def build_decision(fixture: dict[str, Any]) -> StrategyDecision:
    value = fixture["validated"]
    targets = tuple(
        TargetExposureFraction(
            InstrumentId(VenueId(row["venue"]), row["stable_key"]),
            row["units"],
        )
        for row in value["targets"]
    )
    return StrategyDecision(
        strategy_id=value["strategy_id"],
        decision_time=UtcInstant(value["decision_time"]),
        observed_through=UtcInstant(value["observed_through"]),
        target_snapshot=TargetSnapshot(
            sleeve_id=StrategySleeveId(value["sleeve_id"]),
            effective_time=UtcInstant(value["effective_time"]),
            expires_at=UtcInstant(value["expires_at"]),
            targets=targets,
        ),
        confidence=Rate(
            value["confidence_units"], Scale(12), basis="confidence"
        ),
        reason=value["reason"],
        evidence=value["evidence"],
    )


def test_candidate_fixture_preserves_duplicates_and_invalid_time() -> None:
    fixture = load_fixture()
    candidate = StrategyDecisionCandidate(
        StrategyDecisionPayload(fixture["candidate_payload"])
    )
    targets = cast(tuple[Any, ...], candidate.payload.fields["targets"])

    assert candidate.payload.fields["decision_time"] == "not-an-instant"
    assert len(targets) == 2
    assert targets[0] == targets[1]


def test_validated_decision_batch_and_active_target_match_golden_contract() -> None:
    fixture = load_fixture()
    decision = build_decision(fixture)
    batch = DecisionBatch("batch:100", UtcInstant(100), (decision,))

    btc = InstrumentId(VenueId("binance_usdm"), "linear_perpetual:btc-usdt")
    eth = InstrumentId(VenueId("binance_usdm"), "linear_perpetual:eth-usdt")
    active = ActivePortfolioTarget(
        source_decision_batch_id="batch:100",
        materialized_at=UtcInstant(110),
        quantities=(
            (eth, Quantity(-200_000_000, Scale(8), str(eth))),
            (btc, Quantity(125_000_000, Scale(8), str(btc))),
        ),
    )

    expected_batch = {
        **fixture["expected_batch_header"],
        "decisions": [fixture["expected_decision"]],
    }
    assert decision.to_canonical_dict() == fixture["expected_decision"]
    assert canonical_sha256(decision) == fixture["expected_decision_sha256"]
    assert batch.to_canonical_dict() == expected_batch
    assert canonical_sha256(batch) == fixture["expected_batch_sha256"]
    assert active.to_canonical_dict() == fixture["expected_active_target"]
    assert canonical_sha256(active) == fixture["expected_active_target_sha256"]
