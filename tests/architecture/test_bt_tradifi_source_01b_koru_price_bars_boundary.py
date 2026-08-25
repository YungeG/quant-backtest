from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import crypto_quant_bundle_builder as builder

ROOT = Path(__file__).resolve().parents[2]
BUILDER_ROOT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_koru_price_bars_source_bounded_v1.py"
)
INTERNAL_NAMES = {
    "BinanceUsdmKoruPriceBarsSourceKindV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedFailureV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedRequestV1",
    "capture_binance_usdm_koru_price_bars_source_bounded_v1",
    "normalize_binance_usdm_koru_price_bars_source_bounded_v1",
}
KORU_FIXTURE_ROOT = (
    ROOT / "tests/fixtures/market_data/providers/binance_usdm/koru-price-bars-v1"
)
KORU_PROVIDER_FIXTURE_SHA256 = {
    KORU_FIXTURE_ROOT
    / "acquisition-receipt.json": "a352d9307aacee8136f7580bea6d82bda817f5a1f7eea70e2d55679f5995a535",
    KORU_FIXTURE_ROOT
    / "mark/KORUUSDT-1h-2026-07-16.zip": "1d24171e3eeeda02f6114da802bb6ed60d655b6b5c19c56825b3d2539f88cf0b",
    KORU_FIXTURE_ROOT
    / "mark/KORUUSDT-1h-2026-07-16.zip.CHECKSUM": "629977ec493c028e4095f4dbdbc60388d57eaee44976df511f8649aebac24e70",
    KORU_FIXTURE_ROOT
    / "index/KORUUSDT-1h-2026-07-16.zip": "75ed044992cea272cc807526f489ec5879c43a8a828a72811dec2528d11b0606",
    KORU_FIXTURE_ROOT
    / "index/KORUUSDT-1h-2026-07-16.zip.CHECKSUM": "153e5ad46b80a217d849a26355d17935296108ce6a6203b9a982da34a9a59e5b",
}
PROTECTED_SHA256 = {
    BUILDER_ROOT: "ce723694c39feeb0f70976065f8e513a1a2277d93cc35401bbaf046520acc40e",
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_mark_price_archive.py": "34c8767a8d094a2f3bef0af702f17c6b9ab39a2fbe3717b34967e3458fc760b2",
    ROOT
    / "tests/bundle_builder/providers/binance_usdm/test_mark_price_archive_contract.py": "559f0de880ac1ad25a710231d4de0770bdd4bf2fd06d7180c4cc505ed2c9b87f",
    ROOT
    / "tests/bundle_builder/providers/binance_usdm/test_mark_price_archive_evidence.py": "399dba4aa512866d688b1ce9e5b89d31af29de7b53f42e6b5b078f41075f7f75",
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/mark-price-klines-v1/evidence.expected.json": "4814ad89aeadf2aeb10a8c63f9b4ea1218d04890043f7887a98fea362f84ac3c",
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/mark-price-klines-v1/BTCUSDT-1m-2024-01-01.zip": "660efeefdc875f052051b94c2976babd013f64c6633bf58ba030764771747b90",
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/mark-price-klines-v1/BTCUSDT-1m-2024-01-01.zip.CHECKSUM": "ea5548dadd83fad69bbc9db3a24560b7d3f988e54299d2c6aa87e85351e05215",
}


def test_koru_price_bars_v1_is_package_internal_and_root_stays_frozen() -> None:
    assert INTERNAL_NAMES.isdisjoint(builder.__all__)
    assert len(set(builder.__all__)) == 45
    assert all(not hasattr(builder, name) for name in INTERNAL_NAMES)
    assert (
        hashlib.sha256(BUILDER_ROOT.read_bytes()).hexdigest()
        == PROTECTED_SHA256[BUILDER_ROOT]
    )


def test_koru_price_bars_v1_is_offline_rule_neutral_and_scope_bounded() -> None:
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
    assert "funding" not in source.lower()


def test_existing_btc_official_mark_archive_and_root_hashes_are_unchanged() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256
    } == PROTECTED_SHA256


def test_actual_koru_provider_receipt_archive_and_checksum_bytes_are_pinned() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in KORU_PROVIDER_FIXTURE_SHA256
    } == KORU_PROVIDER_FIXTURE_SHA256


def test_runtime_and_kernel_do_not_import_the_koru_price_bar_source_module() -> None:
    package_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("backtest-runtime", "trading-kernel")
        for path in (ROOT / "packages" / package / "src").rglob("*.py")
    )
    assert "binance_usdm_koru_price_bars_source_bounded_v1" not in package_sources
