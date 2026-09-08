from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import NamedRandomStream
from crypto_quant_domain import StrategySleeveId

from tests.runtime.random_streams._fixtures import STRATEGY_ID, stream


def test_named_counter_stream_replays_without_unrelated_stream_coupling() -> None:
    initial = stream()
    first_value, after_first = initial.draw_u64()
    second_value, after_second = after_first.draw_u64()

    replay_value, replay_after = stream(counter=1).draw_u64()
    unrelated_value, unrelated_after = stream(stream_key="tie-break").draw_u64()
    repeated_first, repeated_after = initial.draw_u64()

    assert first_value == 4_185_877_640_117_093_455
    assert second_value == 473_125_739_100_027_668
    assert initial.counter == 0
    assert after_first.counter == 1
    assert after_second.counter == 2
    assert replay_value == second_value
    assert replay_after.stream_hash == after_second.stream_hash
    assert repeated_first == first_value
    assert repeated_after.stream_hash == after_first.stream_hash
    assert unrelated_value != first_value
    assert unrelated_after.counter == 1
    assert initial.counter == 0


def test_stream_identity_separates_seed_strategy_key_and_counter() -> None:
    baseline = stream()
    variants = (
        stream(master_random_seed=43),
        stream(strategy_id=StrategySleeveId("portfolio.value")),
        stream(stream_key="tie-break"),
        stream(counter=1),
    )
    baseline_value, _ = baseline.draw_u64()

    assert len({baseline.stream_hash, *(item.stream_hash for item in variants)}) == 5
    assert all(item.draw_u64()[0] != baseline_value for item in variants)


def test_stream_canonical_identity_and_u64_range_are_explicit() -> None:
    current = stream()
    value, next_stream = current.draw_u64()

    assert 0 <= value < 2**64
    assert next_stream.master_random_seed == current.master_random_seed
    assert next_stream.strategy_id == current.strategy_id
    assert next_stream.stream_key == current.stream_key
    assert next_stream.algorithm == "sha256-counter"
    assert next_stream.algorithm_version == 1
    assert list(current.to_canonical_dict()) == [
        "type",
        "schema_version",
        "algorithm",
        "algorithm_version",
        "master_random_seed",
        "strategy_id",
        "stream_key",
        "counter",
        "stream_hash",
    ]


@pytest.mark.parametrize(
    ("field", "bad_value", "expected_error"),
    (
        ("master_random_seed", True, ValueError),
        ("master_random_seed", -1, ValueError),
        ("master_random_seed", 1.0, ValueError),
        ("strategy_id", "portfolio.momentum", TypeError),
        ("stream_key", "", ValueError),
        ("stream_key", " padded ", ValueError),
        ("stream_key", "e\u0301", ValueError),
        ("algorithm", "sha512-counter", ValueError),
        ("algorithm_version", True, TypeError),
        ("algorithm_version", 2, ValueError),
        ("counter", True, ValueError),
        ("counter", -1, ValueError),
        ("counter", 1.0, ValueError),
    ),
)
def test_stream_rejects_invalid_or_unfrozen_identity(
    field: str,
    bad_value: object,
    expected_error: type[Exception],
) -> None:
    values: dict[str, object] = {
        "master_random_seed": 42,
        "strategy_id": STRATEGY_ID,
        "stream_key": "signal-selection",
        "algorithm": "sha256-counter",
        "algorithm_version": 1,
        "counter": 0,
    }
    values[field] = bad_value

    with pytest.raises(expected_error):
        NamedRandomStream(**values)


def test_dataclass_replace_revalidates_identity() -> None:
    current = stream()

    with pytest.raises(ValueError, match="algorithm must"):
        replace(current, algorithm="current")
    with pytest.raises(ValueError, match="counter"):
        replace(current, counter=-1)
    with pytest.raises(ValueError, match="stream_key"):
        replace(current, stream_key=" ")
