from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import crypto_quant_bundle_builder as builder

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_koru_funding_rate_history_source_bounded_v1.py"
)
ROOT_EXPORTS = {
    "BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1",
    "BinanceUsdmKoruFundingRateHistoryTransportResponseV1",
    "capture_binance_usdm_koru_funding_rate_history_source_bounded_v1",
    "normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1",
}
KORU_FIXTURE_ROOT = (
    ROOT / "tests/fixtures/market_data/providers/binance_usdm/koru-funding-history-v1"
)
KORU_FIXTURE_SHA256 = {
    KORU_FIXTURE_ROOT
    / "acquisition-receipt.json": "74ea246da8d5b6aaf84ffce983cdb1f01a69533707683816dccc838f06b9d053",
    KORU_FIXTURE_ROOT
    / "funding-history.json": "ace9f779682989befac94ffd1c835e7a6e97b2b8103e6ad347ec8dc38fa6c960",
}
PROTECTED_SHA256 = {
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_funding_history_source_bounded_v2.py": "552b67cd8b62a3a5b4d782f7cd5ab4041cd1910514ae451932cef3c57b917bc3",
    ROOT
    / "tests/bundle_builder/providers/binance_usdm/test_funding_history_source_bounded_v2.py": "e5ffb6bc41c03c7f23dd1b0f122bceee92ba2451279c561e3ec50574de82a733",
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_funding_rate_archive.py": "2f42f796ed947dbe24f025e5e3612437c52704faaac5a12c60514685ceee0754",
    ROOT
    / "tests/bundle_builder/providers/binance_usdm/test_funding_history_response_evidence.py": "bd2ad74940e3c49024bfea66be7b2f44735dba01823e980f39a2e0d93f754f7c",
}


def test_koru_funding_history_root_exports_retained_construction_values() -> None:
    assert ROOT_EXPORTS <= set(builder.__all__)
    assert all(getattr(builder, name) is not None for name in ROOT_EXPORTS)
    assert all(not name.startswith("_") for name in builder.__all__)


def test_koru_funding_history_is_offline_rule_neutral_and_preparation_free() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
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
    assert "LocalMarketBundleRepository" not in source


def test_actual_koru_receipt_and_response_bytes_are_pinned() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in KORU_FIXTURE_SHA256
    } == KORU_FIXTURE_SHA256


def test_existing_btc_funding_sources_and_root_hashes_are_unchanged() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256
    } == PROTECTED_SHA256


def test_runtime_and_kernel_do_not_import_koru_funding_history_source() -> None:
    package_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("backtest-runtime", "trading-kernel")
        for path in (ROOT / "packages" / package / "src").rglob("*.py")
    )
    assert (
        "binance_usdm_koru_funding_rate_history_source_bounded_v1"
        not in package_sources
    )
