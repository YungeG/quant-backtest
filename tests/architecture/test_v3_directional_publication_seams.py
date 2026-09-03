from __future__ import annotations

from pathlib import Path

import crypto_quant_bundle_builder as bundle_builder

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder"
PUBLICATION_TESTS = {
    "test_koru_tradifi_economics_bundle_v3.py": "publish_koru_tradifi_economics_bundle_v3",
    "test_koru_tradifi_target_overlay_v3.py": "publish_koru_tradifi_target_overlay_v3",
}
_PUBLICATION_EXPORTS = {
    "KoruTradifiEconomicsBundleFailureCodeV3",
    "KoruTradifiEconomicsBundleFailureV3",
    "KoruTradifiEconomicsBundleOutcomeV3",
    "KoruTradifiEconomicsBundleRequestV3",
    "KoruTradifiEconomicsBundleV3",
    "KoruTradifiEconomicsTermsV3",
    "KoruTradifiTargetOverlayFailureCodeV3",
    "KoruTradifiTargetOverlayFailureV3",
    "KoruTradifiTargetOverlayOutcomeV3",
    "KoruTradifiTargetOverlayRequestV3",
    "KoruTradifiTargetOverlayV3",
}
_LEGACY_NAMES = (
    "BinanceUsdmKoruDirectionalExecution" + "Bundle",
    "build_binance_usdm_koru_directional_execution" + "_bundle_v3",
    "binance_usdm_koru_directional_execution" + "_bundle_v3",
)


def test_v3_directional_publication_collection_has_only_economics_and_overlay_seams() -> None:
    provider_tests = ROOT / "tests/bundle_builder/providers/binance_usdm"
    assert {path.name for path in provider_tests.glob("test_*v3.py")} == set(PUBLICATION_TESTS)
    root_exports = set(bundle_builder.__all__)
    assert _PUBLICATION_EXPORTS == {
        name for name in root_exports if name.startswith("KoruTradifi") and name.endswith("V3")
    }
    assert set(PUBLICATION_TESTS.values()) <= root_exports

    for name, seam in PUBLICATION_TESTS.items():
        source = (provider_tests / name).read_text(encoding="utf-8")
        assert seam in source
        assert not any(legacy in source for legacy in _LEGACY_NAMES)

    assert not (BUILDER / (_LEGACY_NAMES[2] + ".py")).exists()
    for directory in (ROOT / "packages", ROOT / "tests"):
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert not any(legacy in source for legacy in _LEGACY_NAMES), path
