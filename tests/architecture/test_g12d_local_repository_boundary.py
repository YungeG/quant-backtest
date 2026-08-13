from __future__ import annotations

import ast
from pathlib import Path

from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    LocalMarketBundleRetentionProof,
    MarketBundlePublicationFailure,
    MarketBundlePublicationFailureCode,
    MarketBundlePublicationOutcome,
    MarketBundlePublicationResult,
    MarketBundleRepositoryPath,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/local_market_bundle_repository.py"
ALLOWED_IMPORTS = {
    "__future__",
    "contextlib",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "dataclasses",
    "enum",
    "hashlib",
    "json",
    "os",
    "pathlib",
    "re",
    "stat",
    "collections",
    "collections.abc",
}
G12D_EXPORTS = {
    "LocalMarketBundleRepository",
    "LocalMarketBundleRepositoryConfig",
    "MarketBundlePublicationFailureCode",
    "MarketBundlePublicationFailure",
    "MarketBundlePublicationOutcome",
    "MarketBundlePublicationResult",
    "MarketBundleRepositoryPath",
    "LocalMarketBundleRetentionProof",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def test_local_market_bundle_repository_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "socket",
        "requests",
        "urllib",
        "subprocess",
        "httpx",
        "aiohttp",
        "binance",
        "ccxt",
        "hummingbot",
        "websockets",
        "datetime.now",
        "time.time",
        "typing.Protocol",
        "class Reader",
        "class Cursor",
        "open_cursor",
        "read_batch",
        "callback",
        "registry",
        "wall_clock",
        "wall-clock",
        "datetime.now",
        "time.time",
    ):
        assert forbidden not in source


def test_builder_root_enforces_exact_g12d_surface() -> None:
    import crypto_quant_bundle_builder as builder

    assert G12D_EXPORTS <= set(builder.__all__)
    assert len(set(builder.__all__)) == 29
    assert builder.LocalMarketBundleRepository is LocalMarketBundleRepository
    assert builder.LocalMarketBundleRepositoryConfig is LocalMarketBundleRepositoryConfig
    assert builder.LocalMarketBundleRetentionProof is LocalMarketBundleRetentionProof
    assert builder.MarketBundlePublicationFailureCode is MarketBundlePublicationFailureCode
    assert builder.MarketBundlePublicationFailure is MarketBundlePublicationFailure
    assert builder.MarketBundlePublicationOutcome is MarketBundlePublicationOutcome
    assert builder.MarketBundlePublicationResult is MarketBundlePublicationResult
    assert builder.MarketBundleRepositoryPath is MarketBundleRepositoryPath


def test_runtime_and_kernel_do_not_import_local_market_bundle_repository() -> None:
    for directory in (
        ROOT / "packages/backtest-runtime/src/crypto_quant_backtest",
        ROOT / "packages/trading-kernel/src/crypto_quant_trading",
    ):
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "crypto_quant_bundle_builder.local_market_bundle_repository" not in source
            assert "LocalMarketBundleRepository" not in source
