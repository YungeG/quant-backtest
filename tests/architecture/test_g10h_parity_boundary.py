from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARITY = ROOT / "tools/parity/binance_usdm.py"
RUNNER = ROOT / "tools/parity/run_binance_usdm_parity.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/composition.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/financial_dispatch.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "argparse",
    "binance_usdm",
    "dataclasses",
    "enum",
    "hashlib",
    "json",
    "legacy_migration.parity",
    "legacy_migration.snapshots",
    "pathlib",
    "sys",
    "tempfile",
    "typing",
}


def _imports(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
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


def test_g10h_tool_is_isolated_to_stdlib_and_existing_parity_helpers() -> None:
    assert PARITY.is_file()
    assert RUNNER.is_file()
    assert _imports(PARITY) <= ALLOWED_IMPORTS
    assert _imports(RUNNER) <= ALLOWED_IMPORTS
    source = PARITY.read_text(encoding="utf-8") + RUNNER.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "provider_sdk",
        "AuditableBacktestRunner",
        "DeterministicBarEngine",
        "deployment_authorized=True",
    ):
        assert forbidden not in source


def test_generic_runtime_remains_g10h_branchless() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "G10H" not in source
        assert "binance_usdm_parity" not in source
