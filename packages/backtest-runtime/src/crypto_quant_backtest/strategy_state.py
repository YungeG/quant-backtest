from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from crypto_quant_domain import (
    CanonicalSchema,
    SimulationInstant,
    StrategySleeveId,
    canonical_bytes,
    canonical_sha256,
)


_SCHEMA_VERSION = 1


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _freeze(value: object, location: str, active: set[int]) -> object:
    if value is None or type(value) in (bool, int, str):
        canonical_bytes(value)
        return value

    identity = id(value)
    if identity in active:
        raise ValueError(f"cyclic StrategyState value at {location}")

    if isinstance(value, Mapping):
        active.add(identity)
        try:
            keys = tuple(value)
            for key in keys:
                _text(f"StrategyState key at {location}", key)
            frozen = {
                key: _freeze(value[key], f"{location}/{key}", active)
                for key in sorted(keys)
            }
            return MappingProxyType(frozen)
        finally:
            active.remove(identity)

    if type(value) in (list, tuple):
        active.add(identity)
        try:
            sequence = cast(list[object] | tuple[object, ...], value)
            return tuple(
                _freeze(child, f"{location}/{index}", active)
                for index, child in enumerate(sequence)
            )
        finally:
            active.remove(identity)

    raise TypeError(
        f"unsupported StrategyState value {type(value).__name__} at {location}"
    )


@dataclass(frozen=True, slots=True)
class StrategyState:
    strategy_id: StrategySleeveId
    state_schema: CanonicalSchema
    values: Mapping[str, Any]

    def __post_init__(self) -> None:
        if type(self.strategy_id) is not StrategySleeveId:
            raise TypeError("strategy_id must be StrategySleeveId")
        if type(self.state_schema) is not CanonicalSchema:
            raise TypeError("state_schema must be CanonicalSchema")
        if not isinstance(self.values, Mapping):
            raise TypeError("values must be a Mapping")
        frozen = cast(Mapping[str, Any], _freeze(self.values, "values", set()))
        canonical_bytes(frozen)
        object.__setattr__(self, "values", frozen)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "strategy_state",
            "schema_version": _SCHEMA_VERSION,
            "strategy_id": self.strategy_id.to_canonical_dict(),
            "state_schema": self.state_schema.to_canonical_dict(),
            "values": self.values,
        }

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "state_hash": self.state_hash}


@dataclass(frozen=True, slots=True)
class StrategyStateTransition:
    transition_key: str
    occurred_at: SimulationInstant
    before_state: StrategyState
    after_state: StrategyState

    def __post_init__(self) -> None:
        _text("transition_key", self.transition_key)
        if type(self.occurred_at) is not SimulationInstant:
            raise TypeError("occurred_at must be SimulationInstant")
        if type(self.before_state) is not StrategyState:
            raise TypeError("before_state must be StrategyState")
        if type(self.after_state) is not StrategyState:
            raise TypeError("after_state must be StrategyState")
        if self.before_state.strategy_id != self.after_state.strategy_id:
            raise ValueError("transition states must share Strategy identity")
        if self.before_state.state_schema != self.after_state.state_schema:
            raise ValueError("transition states must share state schema")

    @property
    def before_state_hash(self) -> str:
        return self.before_state.state_hash

    @property
    def after_state_hash(self) -> str:
        return self.after_state.state_hash

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "strategy_state_transition",
            "schema_version": _SCHEMA_VERSION,
            "transition_key": self.transition_key,
            "occurred_at": self.occurred_at.to_canonical_dict(),
            "strategy_id": self.before_state.strategy_id.to_canonical_dict(),
            "state_schema": self.before_state.state_schema.to_canonical_dict(),
            "before_state_hash": self.before_state_hash,
            "after_state_hash": self.after_state_hash,
        }

    @property
    def transition_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "transition_hash": self.transition_hash}


@dataclass(frozen=True, slots=True)
class StrategyCheckpoint:
    checkpoint_key: str
    captured_at: SimulationInstant
    state: StrategyState

    def __post_init__(self) -> None:
        _text("checkpoint_key", self.checkpoint_key)
        if type(self.captured_at) is not SimulationInstant:
            raise TypeError("captured_at must be SimulationInstant")
        if type(self.state) is not StrategyState:
            raise TypeError("state must be StrategyState")

    @property
    def state_hash(self) -> str:
        return self.state.state_hash

    def restore(self) -> StrategyState:
        return self.state

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "strategy_checkpoint",
            "schema_version": _SCHEMA_VERSION,
            "checkpoint_key": self.checkpoint_key,
            "captured_at": self.captured_at.to_canonical_dict(),
            "state": self.state.to_canonical_dict(),
        }

    @property
    def checkpoint_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "checkpoint_hash": self.checkpoint_hash}
