from __future__ import annotations

import pytest

from crypto_quant_backtest.multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
    SignalBarBinding,
    ValuationDataBinding,
    construct_multi_resolution_market_data_bindings,
)
from crypto_quant_backtest.performance_observations import BoundedPerformanceRecorder, PerformanceOperation
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


def test_clock_and_authoritative_exception_identity_are_preserved(monkeypatch) -> None:
    import crypto_quant_backtest.multi_resolution_market_data as module

    def broken_clock() -> int:
        raise RuntimeError("clock failed")

    monkeypatch.setattr(module, "_perf_counter_ns", broken_clock)
    assert construct_multi_resolution_market_data_bindings(**candidates(), recorder=BoundedPerformanceRecorder()) == MultiResolutionMarketDataBindings(**candidates())

    bad = candidates()
    bad["signal_bindings"] = []
    with pytest.raises(TypeError) as disabled:
        construct_multi_resolution_market_data_bindings(**bad)
    with pytest.raises(TypeError) as enabled:
        construct_multi_resolution_market_data_bindings(**bad, recorder=RaisingRecorder())
    assert type(disabled.value) is type(enabled.value)
    assert str(disabled.value) == str(enabled.value)
