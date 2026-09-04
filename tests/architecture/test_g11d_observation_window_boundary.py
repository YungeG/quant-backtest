from __future__ import annotations

import ast
import inspect
from pathlib import Path

from crypto_quant_backtest import NamedBarWindowResult, NamedBarWindowView

from tests.runtime.observation_windows._fixtures import backing_result, named_query, window


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/observation_windows.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/universe.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "dataclasses",
    "observations",
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


def test_observation_window_module_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Callable",
        "Protocol",
        "MarketBundleReader",
        "DeterministicTimeline",
        "pandas",
        "numpy",
        "resample",
        "forward_fill",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "open(",
    ):
        assert forbidden not in source


def test_named_window_view_exposes_only_hash_and_argument_free_window() -> None:
    current = NamedBarWindowView(
        query=named_query(),
        backing_result=backing_result(),
    )
    public = {name for name in dir(current) if not name.startswith("_")}

    assert public == {"view_hash", "window"}
    assert list(inspect.signature(NamedBarWindowView.window).parameters) == ["self"]
    assert type(window(current)) is NamedBarWindowResult


def test_generic_runtime_modules_do_not_gain_g11d_branches() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "NamedBarWindowView" not in source
        assert "BarDefinitionRef" not in source
