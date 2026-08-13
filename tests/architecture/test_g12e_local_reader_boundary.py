from __future__ import annotations

import ast
from pathlib import Path

from crypto_quant_market_data import LocalMarketBundleReader


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-data-contracts/src/crypto_quant_market_data/local_market_bundle_reader.py"
)
ALLOWED_IMPORTS = {
    "__future__",
    "collections",
    "collections.abc",
    "crypto_quant_domain",
    "hashlib",
    "json",
    "pathlib",
    "re",
    "stat",
    "bundles",
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


def test_local_reader_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_bundle_builder",
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "pandas",
        "pyarrow",
        "parquet",
        "socket",
        "requests",
        "urllib",
        "subprocess",
        "datetime.now",
        "time.time",
        "Protocol",
        "callback",
        "registry",
        "DataFrame",
    ):
        assert forbidden not in source


def test_market_data_root_exactly_adds_local_reader() -> None:
    import crypto_quant_market_data as market_data

    assert len(set(market_data.__all__)) == 15
    assert market_data.LocalMarketBundleReader is LocalMarketBundleReader


def test_runtime_kernel_and_builder_do_not_import_local_reader() -> None:
    for directory in (
        ROOT / "packages/backtest-runtime/src/crypto_quant_backtest",
        ROOT / "packages/trading-kernel/src/crypto_quant_trading",
        ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder",
    ):
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "local_market_bundle_reader" not in source
            assert "LocalMarketBundleReader" not in source
