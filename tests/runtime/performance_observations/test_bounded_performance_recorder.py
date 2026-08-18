from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from crypto_quant_backtest.performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
    PerformanceOutcome,
    _PerformanceObservation,
)
from crypto_quant_domain import CanonicalizationError, canonical_bytes


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/runtime/performance/perf-obs-01-mrmd-v1.expected.json"
MAX = 2**63 - 1


def test_runtime_v1_taxonomy_and_static_fixture() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert [value.name for value in PerformanceOperation] == expected["operations"]
    assert [value.name for value in PerformanceOutcome] == expected["outcomes"]
    assert expected["maximum_cells"] == 19
    assert expected["saturation_limit"] == MAX


def test_observation_requires_exact_enums_valid_pair_and_exact_integers() -> None:
    value = _PerformanceObservation(
        PerformanceOperation.CONSTRUCT_BINDINGS,
        PerformanceOutcome.SUCCEEDED,
        1,
        2,
        3,
        4,
    )
    assert tuple(field.name for field in fields(_PerformanceObservation)) == (
        "operation", "outcome", "call_count", "total_duration_ns", "input_count", "output_count"
    )
    assert value.call_count == 1

    with pytest.raises(TypeError):
        _PerformanceObservation("CONSTRUCT_BINDINGS", PerformanceOutcome.SUCCEEDED, 1, 2, 3, 4)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="INELIGIBLE"):
        _PerformanceObservation(
            PerformanceOperation.CONSTRUCT_BINDINGS,
            PerformanceOutcome.INELIGIBLE,
            1,
            2,
            3,
            4,
        )
    for invalid in (True, -1, MAX + 1):
        with pytest.raises((TypeError, ValueError)):
            _PerformanceObservation(
                PerformanceOperation.CONSTRUCT_BINDINGS,
                PerformanceOutcome.SUCCEEDED,
                invalid,  # type: ignore[arg-type]
                0,
                0,
                0,
            )


def test_recorder_aggregates_saturates_and_snapshot_is_sorted() -> None:
    recorder = BoundedPerformanceRecorder()
    recorder.record(
        operation=PerformanceOperation.VERIFY_SIGNAL_BAR,
        outcome=PerformanceOutcome.FAILED,
        duration_ns=MAX,
        input_count=MAX,
        output_count=MAX,
    )
    recorder.record(
        operation="VERIFY_SIGNAL_BAR",
        outcome="FAILED",
        duration_ns=10,
        input_count=10,
        output_count=10,
    )
    recorder.record(
        operation=PerformanceOperation.CONSTRUCT_BINDINGS,
        outcome=PerformanceOutcome.SUCCEEDED,
        duration_ns=3,
        input_count=4,
        output_count=5,
    )

    snapshot = recorder.snapshot()
    assert tuple((item.operation.value, item.outcome.value) for item in snapshot) == tuple(
        sorted((item.operation.value, item.outcome.value) for item in snapshot)
    )
    saturated = next(item for item in snapshot if item.operation is PerformanceOperation.VERIFY_SIGNAL_BAR)
    assert saturated == _PerformanceObservation(
        PerformanceOperation.VERIFY_SIGNAL_BAR,
        PerformanceOutcome.FAILED,
        2,
        MAX,
        MAX,
        MAX,
    )
    recorder._cells[(PerformanceOperation.CONSTRUCT_BINDINGS, PerformanceOutcome.SUCCEEDED)] = _PerformanceObservation(
        PerformanceOperation.CONSTRUCT_BINDINGS, PerformanceOutcome.SUCCEEDED, MAX, MAX, MAX, MAX
    )
    recorder.record(
        operation=PerformanceOperation.CONSTRUCT_BINDINGS,
        outcome=PerformanceOutcome.SUCCEEDED,
        duration_ns=1,
        input_count=1,
        output_count=1,
    )
    fully_saturated = next(item for item in recorder.snapshot() if item.operation is PerformanceOperation.CONSTRUCT_BINDINGS)
    assert (fully_saturated.call_count, fully_saturated.total_duration_ns, fully_saturated.input_count, fully_saturated.output_count) == (MAX, MAX, MAX, MAX)


def test_fixed_keyspace_is_bounded_to_nineteen_cells() -> None:
    recorder = BoundedPerformanceRecorder()
    for operation in PerformanceOperation:
        for outcome in PerformanceOutcome:
            if outcome is PerformanceOutcome.INELIGIBLE and operation is not PerformanceOperation.EVALUATE_LOOKBACK:
                with pytest.raises(ValueError):
                    recorder.record(operation=operation, outcome=outcome, duration_ns=0, input_count=0, output_count=0)
                continue
            recorder.record(operation=operation, outcome=outcome, duration_ns=0, input_count=0, output_count=0)

    assert len(recorder.snapshot()) == 19


def test_observations_are_not_canonical_values() -> None:
    recorder = BoundedPerformanceRecorder()
    recorder.record(operation=PerformanceOperation.CONSTRUCT_BINDINGS, outcome=PerformanceOutcome.SUCCEEDED, duration_ns=0, input_count=0, output_count=0)

    with pytest.raises(CanonicalizationError):
        canonical_bytes(recorder.snapshot()[0])
    with pytest.raises(CanonicalizationError):
        canonical_bytes(recorder.snapshot())
