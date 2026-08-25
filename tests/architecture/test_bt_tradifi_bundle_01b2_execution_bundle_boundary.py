from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_bundle_builder as builder

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/"
    "binance_usdm_koru_tradifi_execution_bundle_v1.py"
)
ROOT_EXPORT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
INTERNAL_NAMES = {
    "BinanceUsdmKoruTradifiExecutionBundleRequestV1",
    "BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1",
    "BinanceUsdmKoruTradifiExecutionBundleFailureV1",
    "BinanceUsdmKoruTradifiExecutionBundleResultV1",
    "BinanceUsdmKoruTradifiExecutionBundleOutcomeV1",
    "build_binance_usdm_koru_tradifi_execution_bundle_v1",
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


def test_execution_bundle_is_internal_in_memory_and_off_runtime_publication() -> None:
    assert MODULE.is_file()
    assert INTERNAL_NAMES.isdisjoint(builder.__all__)
    assert all(not hasattr(builder, name) for name in INTERNAL_NAMES)
    assert "binance_usdm_koru_tradifi_execution_bundle_v1" not in ROOT_EXPORT.read_text(
        encoding="utf-8"
    )
    assert _imports() <= {
        "__future__",
        "collections",
        "collections.abc",
        "dataclasses",
        "enum",
        "types",
        "crypto_quant_domain",
        "crypto_quant_market_data",
        "binance_usdm_koru_closed_market_range_targets_v1",
        "binance_usdm_koru_tradifi_source_projection_v1",
    }
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "LocalMarketBundleRepository",
        "runtime_case",
        "pathlib",
        "open(",
        "write_text",
        "write_bytes",
        "socket",
        "requests",
        "urllib",
    ):
        assert forbidden not in source


def test_execution_bundle_has_one_public_build_seam() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    functions = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert functions == ["build_binance_usdm_koru_tradifi_execution_bundle_v1"]
