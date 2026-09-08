from __future__ import annotations

import ast
import inspect
from pathlib import Path

from crypto_quant_backtest import PointInTimeUniverseView, UniverseSelection

from tests.runtime.universe._fixtures import DECISION_BEFORE_CORRECTION, select_universe, view


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/universe.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/observations.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "collections.abc",
    "crypto_quant_domain",
    "dataclasses",
    "enum",
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


def test_universe_module_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Callable",
        "Protocol",
        "ObservationView",
        "MarketBundle",
        "MarketBundleReader",
        "InstrumentCatalog",
        "StrategyOutputValidationContext",
        "DeterministicTimeline",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "glob",
        "scandir",
        "open(",
    ):
        assert forbidden not in source


def test_universe_view_exposes_only_hash_and_selection() -> None:
    current = view(DECISION_BEFORE_CORRECTION)
    public = {name for name in dir(current) if not name.startswith("_")}

    assert public == {"select", "view_hash"}
    assert list(inspect.signature(PointInTimeUniverseView.select).parameters) == [
        "self"
    ]
    assert type(select_universe(current)) is UniverseSelection


def test_generic_runtime_modules_do_not_gain_g11c_branches() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "PointInTimeUniverseView" not in source
        assert "UniverseMembershipRevision" not in source
