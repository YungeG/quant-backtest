from __future__ import annotations

import ast
import inspect
from pathlib import Path

from crypto_quant_backtest import ObservationView

from tests.runtime.observations._fixtures import view


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/observations.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "collections.abc",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "dataclasses",
    "enum",
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


def test_observation_module_uses_only_public_immutable_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "MarketBundleReader",
        "InMemoryMarketBundleReader",
        "EventCursor",
        "DeterministicTimeline",
        "DeterministicBarEngine",
        "AuditableBacktestRunner",
        "AccountingJournal",
        "GenericLedger",
        "PortfolioSnapshot",
        "datetime",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
    ):
        assert forbidden not in source


def test_observation_view_exposes_only_hash_and_query_behavior() -> None:
    observation_view = view()
    public = {name for name in dir(observation_view) if not name.startswith("_")}
    assert public == {"query", "view_hash"}
    assert tuple(inspect.signature(ObservationView.query).parameters) == (
        "self",
        "query",
    )


def test_existing_runtime_modules_do_not_gain_g11a_branches() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "ObservationView" not in source
        assert "ObservationQuery" not in source
