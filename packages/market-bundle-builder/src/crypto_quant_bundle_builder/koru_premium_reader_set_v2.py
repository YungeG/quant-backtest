"""Build the fixed V2 KORU premium reader set from V3/V4 authorities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from crypto_quant_domain import ArtifactRef, canonical_bytes
from crypto_quant_market_data import (
    KoruPremiumReaderBindingV2,
    KoruPremiumReaderSetV2,
    LocalMarketBundleReader,
)

from .binance_usdm_koru_directional_target_compiler_v1 import (
    KoruDirectionalDiscoveryScopeV1,
)
from .binance_usdm_koru_directional_target_compiler_v2 import (
    KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_ARTIFACT_TYPE_V2,
    KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_SCHEMA_VERSION_V2,
    KoruDirectionalTargetCompileRequestV2,
    compile_binance_usdm_koru_directional_targets_v2,
)
from .koru_premium_reader_set_v1 import KoruPremiumRecipeAuthorityV1
from .koru_tradifi_economics_bundle_v4 import KoruTradifiEconomicsBundleV4
from .koru_tradifi_target_overlay_v4 import (
    KoruTradifiTargetOverlayRequestV4,
    publish_koru_tradifi_target_overlay_v4,
)

_IDS = tuple(f"KORU-PRM-{number:02d}" for number in range(1, 5))


def _same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderSetBuildRequestV2:
    economics_bundle: KoruTradifiEconomicsBundleV4
    recipe_authorities: tuple[KoruPremiumRecipeAuthorityV1, ...]
    repository_root: Path

    def __post_init__(self) -> None:
        if type(self.economics_bundle) is not KoruTradifiEconomicsBundleV4:
            raise TypeError("economics_bundle")
        if type(self.recipe_authorities) is not tuple or any(
            type(row) is not KoruPremiumRecipeAuthorityV1 for row in self.recipe_authorities
        ):
            raise TypeError("recipe_authorities")
        if not isinstance(self.repository_root, Path) or not self.repository_root.is_absolute():
            raise ValueError("repository_root")


class KoruPremiumReaderSetFailureCodeV2(str, Enum):
    INVALID_REQUEST = "invalid_request"
    COMPILATION_FAILED = "compilation_failed"
    OVERLAY_FAILED = "overlay_failed"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderSetFailureV2:
    code: KoruPremiumReaderSetFailureCodeV2
    subject: str


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderSetOutcomeV2:
    result: KoruPremiumReaderSetV2 | None = None
    failure: KoruPremiumReaderSetFailureV2 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome")


def _failure(code: KoruPremiumReaderSetFailureCodeV2, subject: str) -> KoruPremiumReaderSetOutcomeV2:
    return KoruPremiumReaderSetOutcomeV2(failure=KoruPremiumReaderSetFailureV2(code, subject))


def build_koru_premium_reader_set_v2(
    request: KoruPremiumReaderSetBuildRequestV2,
) -> KoruPremiumReaderSetOutcomeV2:
    """Compile four sealed recipes once, publish OverlayV4 rows, and reopen each reader."""
    if type(request) is not KoruPremiumReaderSetBuildRequestV2:
        return _failure(KoruPremiumReaderSetFailureCodeV2.INVALID_REQUEST, "request")
    rows = request.recipe_authorities
    if (
        len(rows) != 4
        or tuple(row.premium_id for row in rows) != _IDS
        or tuple(row.premium_key for row in rows) != _IDS
        or len({row.strategy_ref for row in rows}) != 4
        or len({row.parameter_ref for row in rows}) != 4
    ):
        return _failure(KoruPremiumReaderSetFailureCodeV2.INVALID_REQUEST, "premium_rows")
    economics = request.economics_bundle
    try:
        source = economics.request.source_projection
        source_identity = economics.request.source_projection_content_identity
        scope = KoruDirectionalDiscoveryScopeV1()
        compiled = compile_binance_usdm_koru_directional_targets_v2(
            KoruDirectionalTargetCompileRequestV2(
                source,
                source_identity.source_projection_authority_ref,
                source_identity.source_projection_authority_content_hash,
                scope,
                tuple(row.recipe for row in rows),
            )
        )
    except (AttributeError, TypeError, ValueError):
        return _failure(KoruPremiumReaderSetFailureCodeV2.COMPILATION_FAILED, "source")
    if compiled.result is None:
        return _failure(KoruPremiumReaderSetFailureCodeV2.COMPILATION_FAILED, "premium_recipes")
    result = compiled.result
    compiler_ref = ArtifactRef(
        KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_ARTIFACT_TYPE_V2,
        KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_SCHEMA_VERSION_V2,
        result.result_digest,
    )
    scope_ref = ArtifactRef("koru_directional_discovery_scope", 1, scope.scope_digest)
    bindings: list[KoruPremiumReaderBindingV2] = []
    for row in rows:
        try:
            overlay_root = request.repository_root / row.premium_id
            overlay = publish_koru_tradifi_target_overlay_v4(
                KoruTradifiTargetOverlayRequestV4(
                    economics, result, compiler_ref, scope_ref, row.premium_key, overlay_root
                )
            )
            if overlay.result is None:
                raise ValueError("overlay")
            published = overlay.result
            stream = published.selected_stream
            reader = LocalMarketBundleReader.open(
                repository_root=overlay_root, bundle_ref=published.bundle_ref
            )
            if (
                reader.manifest != published.manifest
                or not _same(published.request.selected_recipe, row.recipe)
                or stream.recipe_ref != row.parameter_ref
                or stream.target_stream_key != row.premium_key
                or stream.source_fragment_digest != source_identity.source_fragment_digest
                or result.request.source_projection_authority_ref
                != source_identity.source_projection_authority_ref
                or result.request.source_projection_authority_content_hash
                != source_identity.source_projection_authority_content_hash
            ):
                raise ValueError("overlay binding")
            bindings.append(KoruPremiumReaderBindingV2(
                row.premium_id,
                row.premium_key,
                row.strategy_definition_envelope,
                row.strategy_parameter_set_envelope,
                row.strategy_ref,
                row.parameter_ref,
                row.recipe.recipe_digest,
                compiler_ref,
                result.result_digest,
                scope_ref,
                scope.scope_digest,
                source_identity.source_projection_authority_ref,
                source_identity.source_projection_authority_content_hash,
                source_identity.source_fragment_digest,
                stream.target_stream_key,
                stream.target_stream_digest,
                published.bundle_ref,
                published.bundle_ref.manifest_hash,
                economics.bundle_ref,
                economics.bundle_ref.manifest_hash,
                economics.authority_digest,
                reader,
            ))
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            return _failure(KoruPremiumReaderSetFailureCodeV2.OVERLAY_FAILED, row.premium_id)
    try:
        return KoruPremiumReaderSetOutcomeV2(result=KoruPremiumReaderSetV2(tuple(bindings)))
    except (TypeError, ValueError):
        return _failure(KoruPremiumReaderSetFailureCodeV2.RESULT_INVALID, "reader_set")


__all__ = [
    "KoruPremiumReaderSetBuildRequestV2",
    "KoruPremiumReaderSetFailureCodeV2",
    "KoruPremiumReaderSetFailureV2",
    "KoruPremiumReaderSetOutcomeV2",
    "build_koru_premium_reader_set_v2",
]
