from __future__ import annotations

import inspect
from pathlib import Path

from crypto_quant_backtest import PointInTimeObservationView

from tests.runtime.observations._causality_fixtures import (
    DECISION_BEFORE_CORRECTION,
    point_in_time_view,
)


ROOT = Path(__file__).resolve().parents[2]
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)


def test_point_in_time_view_exposes_only_hash_and_query_behavior() -> None:
    observation_view = point_in_time_view(DECISION_BEFORE_CORRECTION)
    public = {name for name in dir(observation_view) if not name.startswith("_")}
    assert public == {"query", "view_hash"}
    assert list(inspect.signature(PointInTimeObservationView.query).parameters) == [
        "self",
        "query",
    ]


def test_generic_runtime_modules_do_not_gain_observation_revision_branches() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "PointInTimeObservationView" not in source
        assert "RevisionedObservationRecord" not in source
        assert "ObservationCausalityTrace" not in source


def test_observation_causality_remains_offline_and_callback_free() -> None:
    source = (
        ROOT
        / "packages/backtest-runtime/src/crypto_quant_backtest/observations.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "Callable",
        "Protocol",
        "MarketBundleReader",
        "DeterministicTimeline",
        "datetime",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
    ):
        assert forbidden not in source
