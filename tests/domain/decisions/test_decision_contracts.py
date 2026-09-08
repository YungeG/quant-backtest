from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    ActivePortfolioTarget,
    CanonicalizationError,
    DecisionBatch,
    InstrumentId,
    Quantity,
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    StrategyDecision,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    StrategySleeveId,
    TargetExposureFraction,
    TargetSnapshot,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)


def instrument(stable_key: str = "linear_perpetual:btc-usdt") -> InstrumentId:
    return InstrumentId(VenueId("binance_usdm"), stable_key)


def target(stable_key: str = "linear_perpetual:btc-usdt") -> TargetExposureFraction:
    return TargetExposureFraction(instrument(stable_key), 500_000_000_000)


def snapshot(*targets: TargetExposureFraction) -> TargetSnapshot:
    return TargetSnapshot(
        sleeve_id=StrategySleeveId("trend.primary"),
        effective_time=UtcInstant(110),
        expires_at=UtcInstant(200),
        targets=targets,
    )


def simulation_instant(decision_time: int = 100, sequence: int = 1) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(decision_time),
        TimelinePhase(60, "decision"),
        SourceSequence(sequence),
    )


def decision(
    *,
    decision_time: int = 100,
    target_snapshot: TargetSnapshot | None = None,
    decision_instant: SimulationInstant | None = None,
) -> StrategyDecision:
    return StrategyDecision(
        strategy_id="trend-v1",
        decision_time=UtcInstant(decision_time),
        observed_through=UtcInstant(90),
        target_snapshot=target_snapshot or snapshot(target()),
        confidence=Rate(
            units=875_000_000_000,
            scale=Scale(12),
            basis="confidence",
        ),
        reason="scheduled rebalance",
        evidence={"model": {"revision": "sha256:model-v1"}, "features": ["a", "b"]},
        decision_instant=decision_instant,
    )


def test_candidate_preserves_invalid_decoded_data_without_becoming_authoritative() -> None:
    raw: dict[str, Any] = {
        "decision_time": "not-an-instant",
        "targets": [
            {"instrument_id": "unknown:asset", "value": 0.1},
            {"instrument_id": "unknown:asset", "value": Decimal("0.1")},
        ],
    }

    candidate = StrategyDecisionCandidate(StrategyDecisionPayload(raw))
    raw["decision_time"] = 100
    cast(list[Any], raw["targets"]).clear()
    frozen_targets = cast(tuple[Any, ...], candidate.payload.fields["targets"])

    assert candidate.payload.fields["decision_time"] == "not-an-instant"
    assert len(frozen_targets) == 2
    assert frozen_targets[0]["instrument_id"] == "unknown:asset"
    assert frozen_targets[0]["value"] == 0.1
    assert frozen_targets[1]["value"] == Decimal("0.1")
    with pytest.raises(TypeError):
        candidate.payload.fields["decision_time"] = 100  # type: ignore[index]
    with pytest.raises(CanonicalizationError, match="unsupported"):
        canonical_bytes(candidate)


def test_candidate_rejects_non_data_objects_and_non_string_keys() -> None:
    class EngineReference:
        pass

    with pytest.raises(TypeError, match="unsupported candidate payload"):
        StrategyDecisionPayload({"engine": EngineReference()})
    with pytest.raises(TypeError, match="string keys"):
        StrategyDecisionPayload(cast(Any, {1: "bad"}))


def test_strategy_sleeve_and_target_scale_fail_closed() -> None:
    with pytest.raises(ValueError, match="StrategySleeveId"):
        StrategySleeveId(" trend.primary ")
    with pytest.raises(CanonicalizationError, match="NFC"):
        StrategySleeveId("e\u0301")
    with pytest.raises(TypeError, match="integer"):
        TargetExposureFraction(instrument(), True)
    with pytest.raises(ValueError, match="scale 12"):
        TargetExposureFraction(instrument(), 1, Scale(11))


def test_snapshot_is_complete_atomic_and_rejects_duplicate_instruments() -> None:
    flattened = snapshot()
    assert not flattened.targets

    duplicate = target()
    with pytest.raises(ValueError, match="duplicate InstrumentId"):
        snapshot(duplicate, duplicate)
    with pytest.raises(ValueError, match="expires_at"):
        TargetSnapshot(
            sleeve_id=StrategySleeveId("trend.primary"),
            effective_time=UtcInstant(110),
            expires_at=UtcInstant(110),
            targets=(),
        )


def test_validated_decision_enforces_time_confidence_and_canonical_evidence() -> None:
    valid = decision()
    features = cast(tuple[str, ...], valid.evidence["features"])
    assert list(features) == ["a", "b"]
    model = cast(dict[str, str], valid.evidence["model"])
    with pytest.raises(TypeError):
        valid.evidence["new"] = 1  # type: ignore[index]
    with pytest.raises(TypeError):
        model["revision"] = "changed"

    with pytest.raises(ValueError, match="observed_through"):
        replace(valid, observed_through=UtcInstant(101))
    with pytest.raises(ValueError, match="effective_time"):
        decision(
            target_snapshot=TargetSnapshot(
                sleeve_id=StrategySleeveId("trend.primary"),
                effective_time=UtcInstant(99),
                expires_at=None,
                targets=(),
            )
        )
    with pytest.raises(ValueError, match="confidence basis"):
        replace(valid, confidence=Rate(1, Scale(12), "fraction"))
    with pytest.raises(ValueError, match="confidence scale"):
        replace(valid, confidence=Rate(1, Scale(11), "confidence"))
    with pytest.raises(ValueError, match="confidence range"):
        replace(valid, confidence=Rate(1_000_000_000_001, Scale(12), "confidence"))
    with pytest.raises(CanonicalizationError, match="float"):
        replace(valid, evidence={"score": 0.5})


def test_exact_decision_and_batch_bind_full_simulation_instant() -> None:
    legacy = decision()
    first_instant = simulation_instant(sequence=1)
    later_instant = simulation_instant(sequence=2)
    exact = decision(decision_instant=first_instant)

    assert "decision_instant" not in legacy.to_canonical_dict()
    assert exact.to_canonical_dict()["decision_instant"] == first_instant.to_canonical_dict()
    assert canonical_sha256(legacy) != canonical_sha256(exact)

    batch = DecisionBatch(
        "decision-batch-v2:fixture",
        UtcInstant(100),
        (exact,),
        decision_instant=first_instant,
    )
    assert batch.decision_instant == first_instant
    assert batch.to_canonical_dict()["decision_instant"] == first_instant.to_canonical_dict()

    with pytest.raises(ValueError, match="decision_instant instant"):
        decision(decision_instant=SimulationInstant(
            UtcInstant(101), first_instant.phase, first_instant.source_sequence
        ))
    with pytest.raises(ValueError, match="share decision_instant"):
        DecisionBatch("batch:legacy", UtcInstant(100), (exact,))
    with pytest.raises(ValueError, match="share decision_instant"):
        DecisionBatch(
            "batch:exact",
            UtcInstant(100),
            (exact,),
            decision_instant=later_instant,
        )


def test_decision_batch_requires_one_time_and_unique_sleeves() -> None:
    first = decision()
    batch = DecisionBatch("batch:100", UtcInstant(100), (first,))
    assert len(batch.decisions) == 1
    assert batch.decisions[0] is first

    with pytest.raises(ValueError, match="decision_time"):
        DecisionBatch(
            "batch:100",
            UtcInstant(100),
            (first, decision(decision_time=101)),
        )
    with pytest.raises(ValueError, match="duplicate StrategySleeveId"):
        DecisionBatch(
            "batch:100",
            UtcInstant(100),
            (first, replace(first, strategy_id="other-strategy")),
        )
    with pytest.raises(ValueError, match="non-empty"):
        DecisionBatch("batch:100", UtcInstant(100), ())


def test_active_target_binds_typed_instrument_to_exact_quantity() -> None:
    btc = instrument()
    quantity = Quantity(125_000_000, Scale(8), str(btc))
    active = ActivePortfolioTarget(
        source_decision_batch_id="batch:100",
        materialized_at=UtcInstant(110),
        quantities=((btc, quantity),),
    )
    assert len(active.quantities) == 1
    assert active.quantities[0][0] == btc
    assert active.quantities[0][1] == quantity

    with pytest.raises(ValueError, match="identity mismatch"):
        ActivePortfolioTarget(
            "batch:100",
            UtcInstant(110),
            ((btc, Quantity(1, Scale(8), "wrong:instrument")),),
        )
    with pytest.raises(ValueError, match="duplicate InstrumentId"):
        ActivePortfolioTarget(
            "batch:100",
            UtcInstant(110),
            ((btc, quantity), (btc, quantity)),
        )
