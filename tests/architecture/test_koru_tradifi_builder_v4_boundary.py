from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_bundle_builder as builder

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder"
MODULES = (
    PACKAGE / "binance_usdm_koru_directional_target_compiler_v2.py",
    PACKAGE / "koru_tradifi_economics_bundle_v4.py",
    PACKAGE / "koru_tradifi_target_overlay_v4.py",
)
EXPORTS = {
    "KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_ARTIFACT_TYPE_V2",
    "KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_SCHEMA_VERSION_V2",
    "KoruDirectionalTargetCompileFailureCodeV2",
    "KoruDirectionalTargetCompileFailureV2",
    "KoruDirectionalTargetCompileOutcomeV2",
    "KoruDirectionalTargetCompileRequestV2",
    "KoruDirectionalTargetCompileResultV2",
    "KoruDirectionalTargetStreamV2",
    "KoruTradifiEconomicsBundleFailureCodeV4",
    "KoruTradifiEconomicsBundleFailureV4",
    "KoruTradifiEconomicsBundleOutcomeV4",
    "KoruTradifiEconomicsBundleRequestV4",
    "KoruTradifiEconomicsBundleV4",
    "KoruTradifiEconomicsTermsV4",
    "KoruTradifiSourceProjectionContentIdentityV3",
    "KoruTradifiTargetOverlayFailureCodeV4",
    "KoruTradifiTargetOverlayFailureV4",
    "KoruTradifiTargetOverlayOutcomeV4",
    "KoruTradifiTargetOverlayRequestV4",
    "KoruTradifiTargetOverlayV4",
    "build_binance_usdm_koru_source_profile_authority_v3",
    "compile_binance_usdm_koru_directional_targets_v2",
    "publish_koru_tradifi_economics_bundle_v4",
    "publish_koru_tradifi_target_overlay_v4",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add("." * node.level + node.module)
    return names


def test_v4_builder_chain_is_public_and_has_no_runtime_or_research_dependency() -> None:
    assert EXPORTS <= set(builder.__all__)
    assert all(getattr(builder, name) is not None for name in EXPORTS)
    imports = set().union(*(_imports(module) for module in MODULES))
    assert not any("crypto_quant_backtest" in name or "research" in name.lower() for name in imports)
    compiler_source = MODULES[0].read_text(encoding="utf-8")
    assert "binance_usdm_koru_tradifi_source_projection_v2" not in compiler_source
    assert "BinanceUsdmKoruTradifiSourceProjectionResultV2" not in compiler_source
    for module in MODULES[1:]:
        source = module.read_text(encoding="utf-8")
        assert "koru_tradifi_economics_bundle_v3" not in source
        assert "koru_tradifi_target_overlay_v3" not in source
