from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import crypto_quant_bundle_builder as builder

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_koru_aggtrades_source_bounded_v1.py"
)
ROOT_EXPORTS = {
    "BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationOutcomeV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1",
    "BinanceUsdmKoruRetainedAggregateTradesAuthorityV1",
    "BinanceUsdmKoruRetainedAggregateTradesPageV1",
    "build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1",
    "capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1",
    "capture_binance_usdm_koru_aggregate_trades_source_bounded_v1",
    "normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1",
}
PROTECTED_SHA256 = {
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_aggtrades_archive.py": "e00d8b058e1152aed73d2fa5198a23241550d60756245adcc9d8a0b2a1dc1079",
    ROOT
    / "tests/bundle_builder/providers/binance_usdm/test_aggtrades_archive_contract.py": "f6095bd7e198a1ebf1c12f67261cbf3f0b133b9f888adaae2afd7a873395ae4d",
    ROOT
    / "tests/bundle_builder/providers/binance_usdm/test_aggtrades_archive_evidence.py": "761c663df3feda3fa7b021d5828e5d7d8a9d63c30a554a36246ce90acf35feef",
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/aggtrades-v1/evidence.expected.json": "54f183ea5e4d61f0d0c80a9a1ba3f7cfe4538a429338ea711d31d4c3d24935e0",
}


def test_koru_source_bounded_v1_root_exports_retained_construction_values() -> None:
    assert ROOT_EXPORTS <= set(builder.__all__)
    assert all(getattr(builder, name) is not None for name in ROOT_EXPORTS)
    assert all(not name.startswith("_") for name in builder.__all__)
    assert not hasattr(
        builder, "BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1"
    )


def test_koru_source_bounded_v1_is_offline_and_rule_neutral() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imports
    )
    assert not imports.intersection(
        {
            "aiohttp",
            "httpx",
            "requests",
            "socket",
            "urllib",
            "pathlib",
            "subprocess",
        }
    )
    assert "BTCUSDT" not in source
    assert "btc-usdt-perpetual" not in source
    assert "prepare" not in source.lower()
    assert "funding" not in source.lower()
    assert "mark_price" not in source.lower()
    assert "index_price" not in source.lower()


def test_existing_btc_official_fixture_goldens_and_archive_grammar_are_unchanged() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in PROTECTED_SHA256
    } == PROTECTED_SHA256


def test_runtime_and_kernel_do_not_import_the_koru_builder_source_module() -> None:
    package_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("backtest-runtime", "trading-kernel")
        for path in (ROOT / "packages" / package / "src").rglob("*.py")
    )
    assert "binance_usdm_koru_aggtrades_source_bounded_v1" not in package_sources
