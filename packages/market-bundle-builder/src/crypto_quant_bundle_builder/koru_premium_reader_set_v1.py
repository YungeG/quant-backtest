"""Build the fixed target-free KORU premium reader set."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    InstrumentId,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import KoruPremiumReaderBindingV1, KoruPremiumReaderSetV1

from .binance_usdm_koru_directional_target_compiler_v1 import (
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetCompileRequestV1,
    KoruDirectionalTargetRecipeV1,
    KoruMarkIndexPremiumParametersV1,
    compile_binance_usdm_koru_directional_targets_v1,
)
from .koru_tradifi_economics_bundle_v3 import KoruTradifiEconomicsBundleV3
from .koru_tradifi_target_overlay_v3 import (
    KoruTradifiTargetOverlayRequestV3,
    publish_koru_tradifi_target_overlay_v3,
)

_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_IDS = tuple(f"KORU-PRM-{number:02d}" for number in range(1, 5))
_ENTRIES = ("20", "30", "40", "60")


def _same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def canonical_koru_premium_payload_v1(
    recipe: KoruDirectionalTargetRecipeV1, *, artifact_type: str
) -> dict[str, object]:
    """The only accepted strategy or parameter envelope body for a premium row."""
    if type(recipe) is not KoruDirectionalTargetRecipeV1:
        raise TypeError("recipe")
    if artifact_type not in {"strategy_definition", "strategy_parameter_set"}:
        raise ValueError("artifact_type")
    if recipe.family != "mark_index_premium" or type(recipe.parameters) is not KoruMarkIndexPremiumParametersV1:
        raise ValueError("premium recipe")
    return {
        "type": f"koru_premium_{artifact_type}_v1",
        "schema_version": 1,
        "premium_id": recipe.recipe_id,
        "premium_key": recipe.target_stream_key,
        "family": recipe.family,
        "strategy_id": recipe.strategy_id,
        "sleeve_id": recipe.sleeve_id,
        "instrument_id": {"venue": _INSTRUMENT.venue.value, "stable_key": _INSTRUMENT.stable_key},
        "bar_interval": recipe.bar_interval,
        "target_exposure": recipe.target_exposure,
        "entry_premium_bps": recipe.parameters.entry_premium_bps,
        "exit_premium_bps": recipe.parameters.exit_premium_bps,
        "max_hold_hours": recipe.parameters.max_hold_hours,
        "flat_when_inside_band": recipe.parameters.flat_when_inside_band,
    }


@dataclass(frozen=True, slots=True)
class KoruPremiumRecipeAuthorityV1:
    """Sealed recipe and strategy/parameter envelopes; no V2 economics input exists."""

    recipe: KoruDirectionalTargetRecipeV1
    strategy_definition_envelope: ArtifactEnvelope
    strategy_parameter_set_envelope: ArtifactEnvelope
    strategy_ref: ArtifactRef = field(init=False)
    parameter_ref: ArtifactRef = field(init=False)
    premium_id: str = field(init=False)
    premium_key: str = field(init=False)
    authority_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.recipe) is not KoruDirectionalTargetRecipeV1
            or type(self.strategy_definition_envelope) is not ArtifactEnvelope
            or type(self.strategy_parameter_set_envelope) is not ArtifactEnvelope
            or self.strategy_definition_envelope.artifact_type != "strategy_definition"
            or self.strategy_definition_envelope.schema_version != 1
            or self.strategy_parameter_set_envelope.artifact_type != "strategy_parameter_set"
            or self.strategy_parameter_set_envelope.schema_version != 1
        ):
            raise ValueError("premium envelopes")
        recipe = self.recipe
        if (
            recipe.recipe_id not in _IDS
            or recipe.target_stream_key != recipe.recipe_id
            or recipe.family != "mark_index_premium"
            or recipe.instrument_id != _INSTRUMENT
            or recipe.bar_interval != "1h"
            or recipe.target_exposure != "0.25"
            or type(recipe.parameters) is not KoruMarkIndexPremiumParametersV1
            or recipe.parameters.exit_premium_bps != "5"
            or recipe.parameters.max_hold_hours != 12
            or not recipe.parameters.flat_when_inside_band
            or recipe.parameters.entry_premium_bps != _ENTRIES[_IDS.index(recipe.recipe_id)]
        ):
            raise ValueError("frozen KORU premium scope")
        strategy_ref = ArtifactRef.from_envelope(self.strategy_definition_envelope)
        parameter_ref = ArtifactRef.from_envelope(self.strategy_parameter_set_envelope)
        if (
            recipe.strategy_ref != strategy_ref
            or recipe.parameter_ref != parameter_ref
            or not _same(self.strategy_definition_envelope.payload, canonical_koru_premium_payload_v1(recipe, artifact_type="strategy_definition"))
            or not _same(self.strategy_parameter_set_envelope.payload, canonical_koru_premium_payload_v1(recipe, artifact_type="strategy_parameter_set"))
        ):
            raise ValueError("premium envelope binding")
        object.__setattr__(self, "strategy_ref", strategy_ref)
        object.__setattr__(self, "parameter_ref", parameter_ref)
        object.__setattr__(self, "premium_id", recipe.recipe_id)
        object.__setattr__(self, "premium_key", recipe.target_stream_key)
        object.__setattr__(self, "authority_digest", canonical_sha256(self.to_canonical_dict()))

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_premium_recipe_authority_v1",
            "recipe": self.recipe,
            "recipe_digest": self.recipe.recipe_digest,
            "strategy_definition_envelope": self.strategy_definition_envelope,
            "strategy_parameter_set_envelope": self.strategy_parameter_set_envelope,
            "strategy_ref": self.strategy_ref,
            "parameter_ref": self.parameter_ref,
            "premium_id": self.premium_id,
            "premium_key": self.premium_key,
        }


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderSetBuildRequestV1:
    economics_bundle: KoruTradifiEconomicsBundleV3
    recipe_authorities: tuple[KoruPremiumRecipeAuthorityV1, ...]
    repository_root: Path

    def __post_init__(self) -> None:
        if type(self.economics_bundle) is not KoruTradifiEconomicsBundleV3:
            raise TypeError("economics_bundle")
        if type(self.recipe_authorities) is not tuple or any(type(row) is not KoruPremiumRecipeAuthorityV1 for row in self.recipe_authorities):
            raise TypeError("recipe_authorities")
        if not isinstance(self.repository_root, Path) or not self.repository_root.is_absolute():
            raise ValueError("repository_root")


class KoruPremiumReaderSetFailureCodeV1(str, Enum):
    INVALID_REQUEST = "invalid_request"
    COMPILATION_FAILED = "compilation_failed"
    OVERLAY_FAILED = "overlay_failed"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderSetFailureV1:
    code: KoruPremiumReaderSetFailureCodeV1
    subject: str


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderSetOutcomeV1:
    result: KoruPremiumReaderSetV1 | None = None
    failure: KoruPremiumReaderSetFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome")


def _failure(code: KoruPremiumReaderSetFailureCodeV1, subject: str) -> KoruPremiumReaderSetOutcomeV1:
    return KoruPremiumReaderSetOutcomeV1(failure=KoruPremiumReaderSetFailureV1(code, subject))


def build_koru_premium_recipe_authority_v1(
    recipe: KoruDirectionalTargetRecipeV1,
    strategy_definition_envelope: ArtifactEnvelope,
    strategy_parameter_set_envelope: ArtifactEnvelope,
) -> KoruPremiumRecipeAuthorityV1:
    return KoruPremiumRecipeAuthorityV1(recipe, strategy_definition_envelope, strategy_parameter_set_envelope)


def build_koru_premium_reader_set_v1(
    request: KoruPremiumReaderSetBuildRequestV1,
) -> KoruPremiumReaderSetOutcomeV1:
    """Compile the four sealed recipes once, then publish and reopen one overlay per row."""
    if type(request) is not KoruPremiumReaderSetBuildRequestV1:
        return _failure(KoruPremiumReaderSetFailureCodeV1.INVALID_REQUEST, "request")
    rows = request.recipe_authorities
    if (
        len(rows) != 4
        or tuple(row.premium_id for row in rows) != _IDS
        or tuple(row.premium_key for row in rows) != _IDS
        or len({row.strategy_ref for row in rows}) != 4
        or len({row.parameter_ref for row in rows}) != 4
    ):
        return _failure(KoruPremiumReaderSetFailureCodeV1.INVALID_REQUEST, "premium_rows")
    economics = request.economics_bundle
    try:
        source = economics.request.source_projection
        scope = KoruDirectionalDiscoveryScopeV1()
        source_ref = ArtifactRef("binance_usdm_koru_source_projection", 2, source.fragment_digest)
        compiled = compile_binance_usdm_koru_directional_targets_v1(
            KoruDirectionalTargetCompileRequestV1(
                source, source_ref, source.fragment_digest, scope, tuple(row.recipe for row in rows)
            )
        )
    except (AttributeError, TypeError, ValueError):
        return _failure(KoruPremiumReaderSetFailureCodeV1.COMPILATION_FAILED, "source")
    if compiled.result is None:
        return _failure(KoruPremiumReaderSetFailureCodeV1.COMPILATION_FAILED, "premium_recipes")
    result = compiled.result
    compiler_ref = ArtifactRef("koru_directional_target_compile_result", 1, result.result_digest)
    scope_ref = ArtifactRef("koru_directional_discovery_scope", 1, scope.scope_digest)
    bindings: list[KoruPremiumReaderBindingV1] = []
    for row in rows:
        try:
            overlay = publish_koru_tradifi_target_overlay_v3(
                KoruTradifiTargetOverlayRequestV3(
                    economics, result, compiler_ref, scope_ref, row.premium_key,
                    request.repository_root / row.premium_id,
                )
            )
            if overlay.result is None:
                raise ValueError("overlay")
            published = overlay.result
            stream = published.selected_stream
            if (
                not _same(published.request.selected_recipe, row.recipe)
                or stream.recipe_ref != row.parameter_ref
                or stream.target_stream_key != row.premium_key
                or stream.source_fragment_digest != source.fragment_digest
            ):
                raise ValueError("overlay binding")
            bindings.append(KoruPremiumReaderBindingV1(
                row.premium_id, row.premium_key, row.strategy_definition_envelope,
                row.strategy_parameter_set_envelope, row.strategy_ref, row.parameter_ref,
                row.recipe.recipe_digest, compiler_ref, result.result_digest, scope_ref,
                scope.scope_digest, source_ref, source.fragment_digest, stream.target_stream_key,
                stream.target_stream_digest, published.bundle_ref, published.bundle_ref.manifest_hash,
                economics.bundle_ref, economics.bundle_ref.manifest_hash, economics.authority_digest,
                published.reader,
            ))
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            return _failure(KoruPremiumReaderSetFailureCodeV1.OVERLAY_FAILED, row.premium_id)
    try:
        return KoruPremiumReaderSetOutcomeV1(result=KoruPremiumReaderSetV1(tuple(bindings)))
    except (TypeError, ValueError):
        return _failure(KoruPremiumReaderSetFailureCodeV1.RESULT_INVALID, "reader_set")


__all__ = [
    "KoruPremiumReaderSetBuildRequestV1",
    "KoruPremiumReaderSetFailureCodeV1",
    "KoruPremiumReaderSetFailureV1",
    "KoruPremiumReaderSetOutcomeV1",
    "KoruPremiumRecipeAuthorityV1",
    "build_koru_premium_reader_set_v1",
    "build_koru_premium_recipe_authority_v1",
    "canonical_koru_premium_payload_v1",
]
