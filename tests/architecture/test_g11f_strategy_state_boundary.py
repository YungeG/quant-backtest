from __future__ import annotations

import ast
import inspect
from pathlib import Path

from crypto_quant_backtest import StrategyCheckpoint, StrategyState

from tests.runtime.strategy_state._fixtures import FIRST_DECISION, checkpoint, state


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/strategy_state.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/observations.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "collections.abc",
    "crypto_quant_domain",
    "dataclasses",
    "types",
    "typing",
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


def test_strategy_state_module_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Callable",
        "Protocol",
        "MarketBundle",
        "ObservationView",
        "PortfolioSnapshot",
        "AccountingJournal",
        "GenericLedger",
        "DeterministicTimeline",
        "datetime",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "open(",
    ):
        assert forbidden not in source


def test_checkpoint_restore_is_argument_free_and_returns_strategy_state() -> None:
    initial = state({"count": 0, "history": []})
    saved = checkpoint(initial)

    assert type(saved.restore()) is StrategyState
    assert saved.restore() is initial
    assert list(inspect.signature(StrategyCheckpoint.restore).parameters) == ["self"]
    assert type(FIRST_DECISION).__name__ == "SimulationInstant"


def test_generic_runtime_modules_do_not_gain_g11f_branches() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "StrategyCheckpoint" not in source
        assert "StrategyStateTransition" not in source
