from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_bundle_builder as builder

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/"
    "binance_usdm_koru_tradifi_source_projection_v1.py"
)
ROOT_EXPORT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
INTERNAL_NAMES = {
    "BinanceUsdmKoruTradifiSourceProjectionRequestV1",
    "BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1",
    "BinanceUsdmKoruTradifiSourceProjectionFailureV1",
    "BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1",
    "BinanceUsdmKoruMissingBoundaryProjectionV1",
    "BinanceUsdmKoruTradifiSourceProjectionResultV1",
    "BinanceUsdmKoruTradifiSourceProjectionOutcomeV1",
    "build_binance_usdm_koru_tradifi_source_projection_v1",
}


def _imports() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").lstrip(".")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_source_projection_is_package_internal_and_off_runtime_boundaries() -> None:
    assert MODULE.is_file()
    assert INTERNAL_NAMES.isdisjoint(builder.__all__)
    assert all(not hasattr(builder, name) for name in INTERNAL_NAMES)
    root = ROOT_EXPORT.read_text(encoding="utf-8")
    assert "binance_usdm_koru_tradifi_source_projection_v1" not in root
    assert _imports() <= {
        "__future__",
        "bisect",
        "collections",
        "collections.abc",
        "dataclasses",
        "datetime",
        "enum",
        "typing",
        "crypto_quant_domain",
        "crypto_quant_market_data",
        "binance_usdm_koru_aggtrades_source_bounded_v1",
        "binance_usdm_koru_funding_rate_history_source_bounded_v1",
        "binance_usdm_koru_price_bars_source_bounded_v1",
        "koru_tradifi_calendar_unit_authority_v1",
    }
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "MarketBundleRef",
        "LocalMarketBundleRepository",
        "target_events",
        "preparation_authority",
        "account.financial-event",
        "pathlib",
        "open(",
        "socket",
        "requests",
        "urllib",
    ):
        assert forbidden not in source


def test_source_projection_has_one_public_build_seam() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    functions = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert functions == ["build_binance_usdm_koru_tradifi_source_projection_v1"]
