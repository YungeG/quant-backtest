from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


_MAX_VALUE = 2**63 - 1


class PerformanceOperation(str, Enum):
    CONSTRUCT_BINDINGS = "construct_bindings"
    VALIDATE_BINDINGS = "validate_bindings"
    LOOKUP_STREAMS = "lookup_streams"
    HYDRATE_INPUTS = "hydrate_inputs"
    VERIFY_REPLAY = "verify_replay"
    PROJECT_POINT_IN_TIME = "project_point_in_time"
    VERIFY_SIGNAL_BAR = "verify_signal_bar"
    BUILD_WINDOW = "build_window"
    EVALUATE_LOOKBACK = "evaluate_lookback"


class PerformanceOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INELIGIBLE = "ineligible"


def _pair(operation: object, outcome: object) -> tuple[PerformanceOperation, PerformanceOutcome]:
    if type(operation) is not PerformanceOperation:
        raise TypeError("operation must be exact PerformanceOperation")
    if type(outcome) is not PerformanceOutcome:
        raise TypeError("outcome must be exact PerformanceOutcome")
    if outcome is PerformanceOutcome.INELIGIBLE and operation is not PerformanceOperation.EVALUATE_LOOKBACK:
        raise ValueError("INELIGIBLE is valid only for EVALUATE_LOOKBACK")
    return operation, outcome


def _integer(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    if not 0 <= value <= _MAX_VALUE:
        raise ValueError(f"{name} must be between 0 and {_MAX_VALUE}")
    return value


@dataclass(frozen=True, slots=True)
class _PerformanceObservation:
    operation: PerformanceOperation
    outcome: PerformanceOutcome
    call_count: int
    total_duration_ns: int
    input_count: int
    output_count: int

    def __post_init__(self) -> None:
        _pair(self.operation, self.outcome)
        for name in ("call_count", "total_duration_ns", "input_count", "output_count"):
            _integer(name, getattr(self, name))


class BoundedPerformanceRecorder:
    __slots__ = ("_cells",)

    def __init__(self) -> None:
        self._cells: dict[tuple[PerformanceOperation, PerformanceOutcome], _PerformanceObservation] = {}

    def record(
        self,
        *,
        operation: PerformanceOperation,
        outcome: PerformanceOutcome,
        duration_ns: int,
        input_count: int,
        output_count: int,
    ) -> None:
        operation, outcome = _pair(operation, outcome)
        duration_ns = _integer("duration_ns", duration_ns)
        input_count = _integer("input_count", input_count)
        output_count = _integer("output_count", output_count)
        previous = self._cells.get((operation, outcome))
        if previous is None:
            value = _PerformanceObservation(
                operation=operation,
                outcome=outcome,
                call_count=1,
                total_duration_ns=duration_ns,
                input_count=input_count,
                output_count=output_count,
            )
        else:
            value = _PerformanceObservation(
                operation=operation,
                outcome=outcome,
                call_count=min(previous.call_count + 1, _MAX_VALUE),
                total_duration_ns=min(previous.total_duration_ns + duration_ns, _MAX_VALUE),
                input_count=min(previous.input_count + input_count, _MAX_VALUE),
                output_count=min(previous.output_count + output_count, _MAX_VALUE),
            )
        self._cells[(operation, outcome)] = value

    def snapshot(self) -> tuple[_PerformanceObservation, ...]:
        return tuple(
            sorted(
                self._cells.values(),
                key=lambda value: (value.operation.value, value.outcome.value),
            )
        )
