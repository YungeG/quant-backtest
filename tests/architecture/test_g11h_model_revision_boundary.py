from __future__ import annotations

import ast
import inspect
from pathlib import Path

from crypto_quant_backtest import ModelArtifactRef, ModelRevisionTimeline

from tests.runtime.model_revisions._fixtures import (
    DECISION_BEFORE_CORRECTION,
    select_model,
    timeline,
)


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/model_revisions.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/observations.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/strategy_state.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/random_streams.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "collections.abc",
    "crypto_quant_domain",
    "dataclasses",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def test_model_revision_module_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Callable",
        "Protocol",
        "StrategyState",
        "ObservationView",
        "DeterministicTimeline",
        "MarketBundle",
        "AccountingJournal",
        "GenericLedger",
        "pickle",
        "joblib",
        "torch",
        "tensorflow",
        "sklearn",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "open(",
    ):
        assert forbidden not in source


def test_point_in_time_timeline_exposes_only_hash_and_selection() -> None:
    current = timeline(DECISION_BEFORE_CORRECTION)
    public = {name for name in dir(current) if not name.startswith("_")}

    assert public == {"select", "timeline_hash"}
    assert list(inspect.signature(ModelRevisionTimeline.select).parameters) == ["self"]
    assert type(select_model(current)) is ModelArtifactRef


def test_generic_runtime_modules_do_not_gain_g11h_branches() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "ModelArtifactRef" not in source
        assert "ModelRevisionTimeline" not in source
