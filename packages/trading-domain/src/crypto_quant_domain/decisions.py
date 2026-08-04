from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, cast

from .canonical import canonical_bytes
from .identity import require_canonical_text
from .instruments import InstrumentId
from .numeric import Quantity, Rate, Scale
from .time import UtcInstant


TARGET_EXPOSURE_SCALE = Scale(12)


def _freeze_candidate_value(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (bool, int, float, str, Decimal)):
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"candidate payload mapping requires string keys at {path}")
            frozen[key] = _freeze_candidate_value(child, f"{path}/{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_candidate_value(child, f"{path}/{index}")
            for index, child in enumerate(value)
        )
    raise TypeError(
        f"unsupported candidate payload value {type(value).__name__} at {path}"
    )


def _freeze_canonical_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("evidence must be a mapping")
    frozen = cast(Mapping[str, Any], _freeze_candidate_value(value, "evidence"))
    canonical_bytes(frozen)
    return frozen


@dataclass(frozen=True, slots=True)
class StrategyDecisionPayload:
    fields: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.fields, Mapping):
            raise TypeError("StrategyDecisionPayload fields must be a mapping")
        frozen = cast(
            Mapping[str, Any], _freeze_candidate_value(self.fields, "payload")
        )
        object.__setattr__(self, "fields", frozen)


@dataclass(frozen=True, slots=True)
class StrategyDecisionCandidate:
    payload: StrategyDecisionPayload

    def __post_init__(self) -> None:
        if not isinstance(self.payload, StrategyDecisionPayload):
            raise TypeError("payload must be StrategyDecisionPayload")


@dataclass(frozen=True, slots=True, order=True)
class StrategySleeveId:
    value: str

    def __post_init__(self) -> None:
        require_canonical_text("StrategySleeveId", self.value)
        canonical_bytes(self.value)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "strategy_sleeve_id", "value": self.value}

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TargetExposureFraction:
    instrument_id: InstrumentId
    units: int
    scale: Scale = TARGET_EXPOSURE_SCALE

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if isinstance(self.units, bool) or not isinstance(self.units, int):
            raise TypeError("TargetExposureFraction units must be an integer")
        if not isinstance(self.scale, Scale):
            raise TypeError("scale must be a Scale")
        if self.scale != TARGET_EXPOSURE_SCALE:
            raise ValueError("TargetExposureFraction requires canonical scale 12")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "target_exposure_fraction",
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "units": self.units,
            "scale": self.scale.places,
        }


@dataclass(frozen=True, slots=True)
class TargetSnapshot:
    sleeve_id: StrategySleeveId
    effective_time: UtcInstant
    expires_at: UtcInstant | None
    targets: tuple[TargetExposureFraction, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sleeve_id, StrategySleeveId):
            raise TypeError("sleeve_id must be StrategySleeveId")
        if not isinstance(self.effective_time, UtcInstant):
            raise TypeError("effective_time must be UtcInstant")
        if self.expires_at is not None and not isinstance(self.expires_at, UtcInstant):
            raise TypeError("expires_at must be UtcInstant or None")
        if self.expires_at is not None and self.expires_at <= self.effective_time:
            raise ValueError("expires_at must be after effective_time")
        if not isinstance(self.targets, tuple):
            raise TypeError("targets must be a tuple")
        if not all(isinstance(target, TargetExposureFraction) for target in self.targets):
            raise TypeError("targets must contain TargetExposureFraction")
        instrument_ids = [target.instrument_id for target in self.targets]
        if len(set(instrument_ids)) != len(instrument_ids):
            raise ValueError("duplicate InstrumentId in TargetSnapshot")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "target_snapshot",
            "sleeve_id": self.sleeve_id.to_canonical_dict(),
            "effective_time": self.effective_time.to_canonical_dict(),
            "expires_at": (
                self.expires_at.to_canonical_dict()
                if self.expires_at is not None
                else None
            ),
            "targets": [
                target.to_canonical_dict()
                for target in sorted(
                    self.targets, key=lambda value: value.instrument_id
                )
            ],
        }


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    strategy_id: str
    decision_time: UtcInstant
    observed_through: UtcInstant
    target_snapshot: TargetSnapshot
    confidence: Rate | None
    reason: str
    evidence: Mapping[str, Any]

    def __post_init__(self) -> None:
        require_canonical_text("strategy_id", self.strategy_id)
        require_canonical_text("reason", self.reason)
        if not isinstance(self.decision_time, UtcInstant):
            raise TypeError("decision_time must be UtcInstant")
        if not isinstance(self.observed_through, UtcInstant):
            raise TypeError("observed_through must be UtcInstant")
        if not isinstance(self.target_snapshot, TargetSnapshot):
            raise TypeError("target_snapshot must be TargetSnapshot")
        if self.observed_through > self.decision_time:
            raise ValueError("observed_through must not be after decision_time")
        if self.target_snapshot.effective_time < self.decision_time:
            raise ValueError("target effective_time must not be before decision_time")
        if self.confidence is not None:
            if not isinstance(self.confidence, Rate):
                raise TypeError("confidence must be Rate or None")
            if self.confidence.basis != "confidence":
                raise ValueError("confidence basis must be confidence")
            if self.confidence.scale != TARGET_EXPOSURE_SCALE:
                raise ValueError("confidence scale must be 12")
            if not 0 <= self.confidence.units <= TARGET_EXPOSURE_SCALE.factor:
                raise ValueError("confidence range must be between 0 and 1")
        object.__setattr__(self, "evidence", _freeze_canonical_mapping(self.evidence))
        canonical_bytes({"strategy_id": self.strategy_id, "reason": self.reason})

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "strategy_decision",
            "strategy_id": self.strategy_id,
            "decision_time": self.decision_time.to_canonical_dict(),
            "observed_through": self.observed_through.to_canonical_dict(),
            "target_snapshot": self.target_snapshot.to_canonical_dict(),
            "confidence": (
                self.confidence.to_canonical_dict()
                if self.confidence is not None
                else None
            ),
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class DecisionBatch:
    decision_batch_id: str
    decision_time: UtcInstant
    decisions: tuple[StrategyDecision, ...]

    def __post_init__(self) -> None:
        require_canonical_text("decision_batch_id", self.decision_batch_id)
        if not isinstance(self.decision_time, UtcInstant):
            raise TypeError("decision_time must be UtcInstant")
        if not isinstance(self.decisions, tuple):
            raise TypeError("decisions must be a tuple")
        if not self.decisions:
            raise ValueError("DecisionBatch decisions must be non-empty")
        if not all(isinstance(decision, StrategyDecision) for decision in self.decisions):
            raise TypeError("decisions must contain StrategyDecision")
        if any(decision.decision_time != self.decision_time for decision in self.decisions):
            raise ValueError("DecisionBatch decisions must share decision_time")
        sleeve_ids = [decision.target_snapshot.sleeve_id for decision in self.decisions]
        if len(set(sleeve_ids)) != len(sleeve_ids):
            raise ValueError("duplicate StrategySleeveId in DecisionBatch")
        canonical_bytes(self.decision_batch_id)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "decision_batch",
            "decision_batch_id": self.decision_batch_id,
            "decision_time": self.decision_time.to_canonical_dict(),
            "decisions": [
                decision.to_canonical_dict()
                for decision in sorted(
                    self.decisions,
                    key=lambda value: (
                        value.target_snapshot.sleeve_id,
                        value.strategy_id,
                    ),
                )
            ],
        }


@dataclass(frozen=True, slots=True)
class ActivePortfolioTarget:
    source_decision_batch_id: str
    materialized_at: UtcInstant
    quantities: tuple[tuple[InstrumentId, Quantity], ...]

    def __post_init__(self) -> None:
        require_canonical_text(
            "source_decision_batch_id", self.source_decision_batch_id
        )
        if not isinstance(self.materialized_at, UtcInstant):
            raise TypeError("materialized_at must be UtcInstant")
        if not isinstance(self.quantities, tuple):
            raise TypeError("quantities must be a tuple")
        instrument_ids: list[InstrumentId] = []
        for item in self.quantities:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("quantities must contain InstrumentId/Quantity pairs")
            instrument_id, quantity = item
            if not isinstance(instrument_id, InstrumentId):
                raise TypeError("target quantity instrument_id must be InstrumentId")
            if not isinstance(quantity, Quantity):
                raise TypeError("target quantity must be Quantity")
            if quantity.instrument_id != str(instrument_id):
                raise ValueError("ActivePortfolioTarget quantity identity mismatch")
            instrument_ids.append(instrument_id)
        if len(set(instrument_ids)) != len(instrument_ids):
            raise ValueError("duplicate InstrumentId in ActivePortfolioTarget")
        canonical_bytes(self.source_decision_batch_id)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "active_portfolio_target",
            "source_decision_batch_id": self.source_decision_batch_id,
            "materialized_at": self.materialized_at.to_canonical_dict(),
            "quantities": [
                {
                    "instrument_id": instrument_id.to_canonical_dict(),
                    "quantity": quantity.to_canonical_dict(),
                }
                for instrument_id, quantity in sorted(
                    self.quantities, key=lambda value: value[0]
                )
            ],
        }
