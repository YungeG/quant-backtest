from __future__ import annotations

import hashlib
from dataclasses import dataclass

from crypto_quant_domain import (
    StrategySleeveId,
    canonical_bytes,
    canonical_sha256,
)


_SCHEMA_VERSION = 1
_ALGORITHM = "sha256-counter"
_ALGORITHM_VERSION = 1


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _nonnegative_integer(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


@dataclass(frozen=True, slots=True)
class NamedRandomStream:
    master_random_seed: int
    strategy_id: StrategySleeveId
    stream_key: str
    algorithm: str = _ALGORITHM
    algorithm_version: int = _ALGORITHM_VERSION
    counter: int = 0

    def __post_init__(self) -> None:
        _nonnegative_integer("master_random_seed", self.master_random_seed)
        if type(self.strategy_id) is not StrategySleeveId:
            raise TypeError("strategy_id must be StrategySleeveId")
        _text("stream_key", self.stream_key)
        if self.algorithm != _ALGORITHM:
            raise ValueError(f"algorithm must be {_ALGORITHM}")
        if type(self.algorithm_version) is not int:
            raise TypeError("algorithm_version must be an integer")
        if self.algorithm_version != _ALGORITHM_VERSION:
            raise ValueError(f"algorithm_version must be {_ALGORITHM_VERSION}")
        _nonnegative_integer("counter", self.counter)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "named_random_stream",
            "schema_version": _SCHEMA_VERSION,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "master_random_seed": self.master_random_seed,
            "strategy_id": self.strategy_id.to_canonical_dict(),
            "stream_key": self.stream_key,
            "counter": self.counter,
        }

    def _draw_body(self) -> dict[str, object]:
        return {
            "type": "named_random_stream_draw",
            "schema_version": _SCHEMA_VERSION,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "master_random_seed": self.master_random_seed,
            "strategy_id": self.strategy_id.to_canonical_dict(),
            "stream_key": self.stream_key,
            "counter": self.counter,
        }

    @property
    def stream_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def draw_u64(self) -> tuple[int, NamedRandomStream]:
        digest = hashlib.sha256(canonical_bytes(self._draw_body())).digest()
        value = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return (
            value,
            NamedRandomStream(
                master_random_seed=self.master_random_seed,
                strategy_id=self.strategy_id,
                stream_key=self.stream_key,
                algorithm=self.algorithm,
                algorithm_version=self.algorithm_version,
                counter=self.counter + 1,
            ),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "stream_hash": self.stream_hash}
