from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_bundle_builder as builder

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/"
    "binance_usdm_koru_tradifi_source_projection_v2.py"
)
ROOT_EXPORTS = {
    "BinanceUsdmKoruTradifiSourceProjectionRequestV2",
    "BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2",
    "BinanceUsdmKoruTradifiSourceProjectionFailureV2",
    "BinanceUsdmKoruFirstRetainedTradeProjectionLineageV2",
    "BinanceUsdmKoruMissingBoundaryProjectionV2",
    "BinanceUsdmKoruTradifiSourceProjectionResultV2",
    "BinanceUsdmKoruTradifiSourceProjectionOutcomeV2",
    "KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V1",
    "KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V1",
    "build_binance_usdm_koru_source_profile_authority_v2",
    "build_binance_usdm_koru_tradifi_source_projection_v2",
    "create_binance_usdm_koru_tradifi_source_projection_authority_v1",
    "open_binance_usdm_koru_tradifi_source_projection_authority_v1",
    "serialize_binance_usdm_koru_tradifi_source_projection_authority_v1",
}
AUTHORITY_PUBLIC_SEAMS = {
    "create_binance_usdm_koru_tradifi_source_projection_authority_v1",
    "open_binance_usdm_koru_tradifi_source_projection_authority_v1",
    "serialize_binance_usdm_koru_tradifi_source_projection_authority_v1",
}


def _imports() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        prefix = "." * node.level
        if node.module is not None:
            imported.add(f"{prefix}{node.module}")
        else:
            imported.update(f"{prefix}{alias.name}" for alias in node.names)
    return imported


def _private_imports() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name.startswith("_")
    }


def _root_projection_exports() -> set[str]:
    tree = ast.parse(
        (
            ROOT
            / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
        ).read_text(encoding="utf-8")
    )
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "binance_usdm_koru_tradifi_source_projection_v2"
        ):
            return {alias.name for alias in node.names}
    raise AssertionError("source projection root export is absent")


def test_streaming_source_projection_is_root_exported_and_aggregate_bounded() -> None:
    assert MODULE.is_file()
    assert ROOT_EXPORTS <= set(builder.__all__)
    assert all(getattr(builder, name) is not None for name in ROOT_EXPORTS)
    assert all(not name.startswith("_") for name in builder.__all__)
    assert _root_projection_exports() == ROOT_EXPORTS
    assert _imports() <= {
        "__future__",
        "base64",
        "json",
        "bisect",
        "collections",
        "collections.abc",
        "dataclasses",
        "datetime",
        "enum",
        "typing",
        "crypto_quant_domain",
        "crypto_quant_domain.numeric",
        "crypto_quant_market_data",
        ".binance_usdm_koru_aggtrade_boundary_index_v1",
        ".binance_usdm_koru_aggtrades_source_bounded_v1",
        ".binance_usdm_koru_funding_rate_history_source_bounded_v1",
        ".binance_usdm_koru_price_bars_source_bounded_v1",
        ".koru_tradifi_calendar_unit_authority_v1",
        ".source_snapshots",
    }
    assert _private_imports() == {"_trusted_result"}
    source = MODULE.read_text(encoding="utf-8")
    assert (
        '"binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v2"'
        in source
    )
    for forbidden in (
        "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v1",
        "binance_usdm_koru_tradifi_source_projection_v1",
        "_verified_aggregate_results",
        "normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1",
        "aggregate_trade_results",
        "crypto_quant_backtest",
        "crypto_quant_foundation",
        "crypto_quant_trading",
        "BacktestRuntime",
        "Foundation",
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


def test_streaming_source_projection_has_only_build_and_authority_seams() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert AUTHORITY_PUBLIC_SEAMS <= ROOT_EXPORTS
    assert functions == AUTHORITY_PUBLIC_SEAMS | {
        "build_binance_usdm_koru_source_profile_authority_v2",
        "build_binance_usdm_koru_tradifi_source_projection_v2",
    }
