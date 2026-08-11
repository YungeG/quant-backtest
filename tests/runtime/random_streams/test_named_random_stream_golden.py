from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import NamedRandomStream
from crypto_quant_domain import StrategySleeveId

from tests.runtime.random_streams._fixtures import STRATEGY_ID, stream


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/random-streams/named-random-stream-isolation-v1.json"
)


def _failure_controls() -> dict[str, bool]:
    current = stream()
    attempts = {
        "negative_seed": lambda: replace(current, master_random_seed=-1),
        "noncanonical_key": lambda: replace(current, stream_key=" padded "),
        "unsupported_algorithm": lambda: replace(current, algorithm="current"),
        "unsupported_version": lambda: replace(current, algorithm_version=2),
        "negative_counter": lambda: replace(current, counter=-1),
        "wrong_strategy_type": lambda: NamedRandomStream(
            master_random_seed=42,
            strategy_id="portfolio.momentum",
            stream_key="signal-selection",
        ),
    }
    controls: dict[str, bool] = {}
    for name, attempt in attempts.items():
        try:
            attempt()
        except (TypeError, ValueError):
            controls[name] = True
        else:
            controls[name] = False
    return controls


def _draws(count: int) -> tuple[list[int], list[str]]:
    current = stream()
    values: list[int] = []
    hashes = [current.stream_hash]
    for _ in range(count):
        value, current = current.draw_u64()
        values.append(value)
        hashes.append(current.stream_hash)
    return values, hashes


def _payload() -> dict[str, object]:
    values, hashes = _draws(3)
    replay_value, replay_next = stream(counter=1).draw_u64()
    initial = stream()
    repeated_value, repeated_next = initial.draw_u64()
    unrelated = stream(stream_key="tie-break")
    unrelated_value, unrelated_next = unrelated.draw_u64()
    variants = {
        "different_seed": stream(master_random_seed=43),
        "different_strategy": stream(
            strategy_id=StrategySleeveId("portfolio.value")
        ),
        "different_key": unrelated,
        "different_counter": stream(counter=1),
    }
    return {
        "schema_version": 1,
        "fixture_id": "named-random-stream-isolation-v1",
        "initial_stream": initial.to_canonical_dict(),
        "draw_values": values,
        "stream_hashes": hashes,
        "counter_replay": {
            "value_matches": replay_value == values[1],
            "next_hash_matches": replay_next.stream_hash == hashes[2],
        },
        "repeat_parity": {
            "value_matches": repeated_value == values[0],
            "next_hash_matches": repeated_next.stream_hash == hashes[1],
        },
        "unrelated_stream_noninterference": {
            "unrelated_value": unrelated_value,
            "unrelated_next_hash": unrelated_next.stream_hash,
            "original_hash_unchanged": initial.stream_hash == hashes[0],
            "original_next_value_unchanged": initial.draw_u64()[0] == values[0],
        },
        "identity_separation": {
            name: {
                "stream_hash": variant.stream_hash,
                "first_value": variant.draw_u64()[0],
            }
            for name, variant in variants.items()
        },
        "failure_controls": _failure_controls(),
        "limitations": [
            "raw_u64_only",
            "no_distribution_contract",
            "no_statistical-certification",
            "no-security-or-entropy-claim",
            "no-global-rng",
        ],
    }


def test_named_random_stream_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11G golden fixture: {error}") from error
    assert _payload() == expected
