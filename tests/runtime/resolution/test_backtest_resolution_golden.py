from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    ProfileResolver,
    RequestedResultGrade,
    SourceTreeState,
)
from crypto_quant_domain import canonical_bytes
from crypto_quant_market_data import MarketBundleCapability
from tests.runtime.resolution._fixtures import (
    build_manifest,
    bundle_manifest,
    profile_registry,
    provenance_variant,
    request,
)


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/runtime/backtest-request-profile-resolution-v1.json"


def build_actual() -> dict[str, object]:
    resolver = ProfileResolver()
    bundle = bundle_manifest()
    build = build_manifest()
    backtest_request = request(build, bundle=bundle)
    resolved = resolver.resolve(
        request=backtest_request,
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=build,
    )
    provenance_build = provenance_variant(build)
    provenance_only = resolver.resolve(
        request=request(provenance_build, bundle=bundle),
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=provenance_build,
    )
    missing_profile = resolver.resolve(
        request=backtest_request,
        registry=BacktestProfileRegistry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=build,
    )
    missing_capability = resolver.resolve(
        request=backtest_request,
        registry=profile_registry(
            extra_market_capabilities=(
                MarketBundleCapability("order_book_l2", 1),
            )
        ),
        market_bundle_manifest=bundle,
        build_artifact_manifest=build,
    )
    editable_build = build_manifest(
        runtime_mode=ArtifactInstallMode.EDITABLE,
        runtime_content_hash=None,
        runtime_source_state=SourceTreeState.DIRTY,
    )
    editable_development = resolver.resolve(
        request=request(editable_build, bundle=bundle),
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=editable_build,
    )
    editable_decision_grade = resolver.resolve(
        request=request(
            editable_build,
            bundle=bundle,
            grade=RequestedResultGrade.DECISION_GRADE,
        ),
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=editable_build,
    )

    return json.loads(
        canonical_bytes(
            {
                "fixture_id": "backtest-request-profile-resolution-v1",
                "resolved": resolved,
                "provenance_only": provenance_only,
                "missing_profile": missing_profile,
                "missing_capability": missing_capability,
                "editable_development": editable_development,
                "editable_decision_grade": editable_decision_grade,
            }
        )
    )


def test_backtest_request_profile_resolution_matches_canonical_golden() -> None:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert build_actual() == expected
