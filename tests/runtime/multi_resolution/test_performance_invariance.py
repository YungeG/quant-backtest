from __future__ import annotations

import pytest

from crypto_quant_backtest.multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
    SignalBarBinding,
    ValuationDataBinding,
    construct_multi_resolution_market_data_bindings,
)
from crypto_quant_backtest.performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
)
from crypto_quant_domain import InstrumentId, PricePurpose, VenueId


class RaisingRecorder(BoundedPerformanceRecorder):
    def record(self, **kwargs) -> None:  # type: ignore[override]
        raise RuntimeError("observation failed")


def candidates():
    return {
        "signal_bindings": (SignalBarBinding("sha256:" + "1" * 64, "bars", PricePurpose.VALUATION, "sha256:" + "2" * 64),),
        "execution_bindings": (ExecutionDataBinding("profile", "trades"),),
        "valuation_bindings": (ValuationDataBinding(InstrumentId(VenueId("test"), "asset"), "marks"),),
    }


def test_disabled_enabled_and_failing_recorder_preserve_exact_authority() -> None:
    disabled = construct_multi_resolution_market_data_bindings(**candidates())
    recorder = BoundedPerformanceRecorder()
    enabled = construct_multi_resolution_market_data_bindings(**candidates(), recorder=recorder)
    failed = construct_multi_resolution_market_data_bindings(**candidates(), recorder=RaisingRecorder())

    assert disabled == enabled == failed
    assert disabled.to_canonical_dict() == enabled.to_canonical_dict() == failed.to_canonical_dict()
    assert recorder.snapshot()[0].operation is PerformanceOperation.CONSTRUCT_BINDINGS


def test_clock_counter_and_authoritative_exception_identity_are_preserved(monkeypatch) -> None:
    import crypto_quant_backtest.multi_resolution_market_data as module

    def broken_clock() -> int:
        raise RuntimeError("clock failed")

    monkeypatch.setattr(module, "_perf_counter_ns", broken_clock)
    expected = MultiResolutionMarketDataBindings(**candidates())
    clock_recorder = BoundedPerformanceRecorder()
    assert construct_multi_resolution_market_data_bindings(
        **candidates(), recorder=clock_recorder
    ) == expected
    assert clock_recorder.snapshot() == ()

    monkeypatch.undo()

    def broken_counter(*args, **kwargs) -> int:
        raise RuntimeError("counter failed")

    monkeypatch.setattr(module, "_candidate_count", broken_counter)
    counter_recorder = BoundedPerformanceRecorder()
    assert construct_multi_resolution_market_data_bindings(
        **candidates(), recorder=counter_recorder
    ) == expected
    assert counter_recorder.snapshot() == ()

    bad = candidates()
    bad["signal_bindings"] = []
    with pytest.raises(TypeError) as disabled:
        construct_multi_resolution_market_data_bindings(**bad)
    with pytest.raises(TypeError) as enabled:
        construct_multi_resolution_market_data_bindings(**bad, recorder=RaisingRecorder())
    assert type(disabled.value) is type(enabled.value)
    assert str(disabled.value) == str(enabled.value)


def test_single_measurements_saturate_before_the_recorder(monkeypatch) -> None:
    import crypto_quant_backtest.multi_resolution_market_data as module

    maximum = 2**63 - 1
    ticks = iter((0, maximum + 100))
    monkeypatch.setattr(module, "_perf_counter_ns", lambda: next(ticks))
    monkeypatch.setattr(module, "_candidate_count", lambda *args: maximum + 1)
    monkeypatch.setattr(module, "_binding_count", lambda value: maximum + 2)
    recorder = BoundedPerformanceRecorder()

    construct_multi_resolution_market_data_bindings(**candidates(), recorder=recorder)

    observation = recorder.snapshot()[0]
    assert (
        observation.total_duration_ns,
        observation.input_count,
        observation.output_count,
    ) == (maximum, maximum, maximum)
