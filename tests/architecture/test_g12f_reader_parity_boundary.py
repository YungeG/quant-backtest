from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARITY = ROOT / "tools/parity/market_bundle_reader.py"
RUNNER = ROOT / "tools/parity/run_market_bundle_reader_parity.py"
PRODUCTION = (
    ROOT / "packages/market-data-contracts/src/crypto_quant_market_data",
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading",
)
ALLOWED_IMPORTS = {
    "__future__",
    "argparse",
    "json",
    "legacy_migration.parity",
    "market_bundle_reader",
    "pathlib",
    "sys",
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


def test_g12f_tool_reuses_only_stdlib_and_existing_comparator() -> None:
    assert PARITY.is_file()
    assert RUNNER.is_file()
    assert _imports(PARITY) <= ALLOWED_IMPORTS
    assert _imports(RUNNER) <= ALLOWED_IMPORTS
    source = PARITY.read_text(encoding="utf-8") + RUNNER.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_market_data",
        "crypto_quant_bundle_builder",
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "pandas",
        "pyarrow",
        "parquet",
        "mmap",
        "DataFrame",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "datetime.now",
        "time.time",
        "approved_change",
        "explicit_tolerance",
    ):
        assert forbidden not in source


def test_production_packages_remain_g12f_branchless() -> None:
    for directory in PRODUCTION:
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "G12F" not in source
            assert "market_bundle_reader_g12f" not in source
            assert "run_market_bundle_reader_parity" not in source
