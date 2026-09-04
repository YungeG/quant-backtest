"""Causal KORU directional target compilation from V3 source authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import cast

from crypto_quant_domain import ArtifactRef, canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketEvent, MarketStreamManifest

from . import binance_usdm_koru_directional_target_compiler_v1 as _v1
from .binance_usdm_koru_directional_target_compiler_v1 import (
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetEvidenceIdentityV1,
    KoruDirectionalTargetRecipeV1,
    KoruDirectionalUnsupportedParametersV1,
    KoruMarkIndexPremiumParametersV1,
)
from .binance_usdm_koru_tradifi_source_projection_v3 import (
    KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V3,
    KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V3,
    BinanceUsdmKoruTradifiSourceProjectionResultV3,
    create_binance_usdm_koru_tradifi_source_projection_authority_v3,
)
from .binance_usdm_koru_tradifi_source_projection_v3 import (
    _trusted_result as _trusted_source_result,
)

_SCHEMA_VERSION = 2
_REQUEST_SCHEMA_VERSION = "koru_directional_target_compile_v2"
KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_ARTIFACT_TYPE_V2 = "koru_directional_target_compile_result"
KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_SCHEMA_VERSION_V2 = 2

# Recipe parameters and target-event semantics are intentionally stable across the
# source-authority successor.
type SourceProjectionV3 = BinanceUsdmKoruTradifiSourceProjectionResultV3
type TargetV3 = MarketEvent


def _same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetStreamV2:
    recipe_ref: ArtifactRef
    source_fragment_digest: str
    target_stream_key: str
    events: tuple[TargetV3, ...]
    manifest: MarketStreamManifest
    target_stream_digest: str
    evidence: tuple[KoruDirectionalTargetEvidenceIdentityV1, ...]

    def __post_init__(self) -> None:
        if type(self.recipe_ref) is not ArtifactRef:
            raise TypeError("recipe_ref")
        _hash("source_fragment_digest", self.source_fragment_digest)
        if type(self.target_stream_key) is not str or not self.target_stream_key or self.target_stream_key != self.target_stream_key.strip():
            raise ValueError("target_stream_key")
        if type(self.events) is not tuple or any(type(event) is not MarketEvent for event in self.events):
            raise TypeError("events")
        if any(event.stream_key != self.target_stream_key for event in self.events):
            raise ValueError("target_stream_key")
        expected_manifest = _manifest(self.target_stream_key, self.events)
        if type(self.manifest) is not MarketStreamManifest or not _same(self.manifest, expected_manifest):
            raise ValueError("manifest")
        if self.target_stream_digest != _stream_digest(self.target_stream_key, self.events):
            raise ValueError("target_stream_digest")
        if type(self.evidence) is not tuple or any(type(value) is not KoruDirectionalTargetEvidenceIdentityV1 for value in self.evidence):
            raise TypeError("evidence")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_stream_v2",
            "schema_version": _SCHEMA_VERSION,
            "recipe_ref": self.recipe_ref,
            "source_fragment_digest": self.source_fragment_digest,
            "target_stream_key": self.target_stream_key,
            "events": self.events,
            "manifest": self.manifest,
            "target_stream_digest": self.target_stream_digest,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileRequestV2:
    source_projection: SourceProjectionV3
    source_projection_authority_ref: ArtifactRef
    source_projection_authority_content_hash: str
    scope: KoruDirectionalDiscoveryScopeV1
    recipes: tuple[KoruDirectionalTargetRecipeV1, ...]
    schema_version: str = _REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.source_projection) is not BinanceUsdmKoruTradifiSourceProjectionResultV3:
            raise TypeError("source_projection must be exact SourceProjectionV3")
        if type(self.source_projection_authority_ref) is not ArtifactRef:
            raise TypeError("source_projection_authority_ref")
        _hash("source_projection_authority_content_hash", self.source_projection_authority_content_hash)
        if (
            self.source_projection_authority_ref.artifact_type
            != KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V3
            or self.source_projection_authority_ref.schema_version
            != KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V3
            or self.source_projection_authority_ref.content_hash
            != self.source_projection_authority_content_hash
        ):
            raise ValueError("source_projection_authority")
        expected_authority, expected_ref = create_binance_usdm_koru_tradifi_source_projection_authority_v3(self.source_projection)
        if (
            self.source_projection_authority_ref != expected_ref
            or self.source_projection_authority_content_hash != expected_authority.content_hash
        ):
            raise ValueError("source_projection_authority")
        if type(self.scope) is not KoruDirectionalDiscoveryScopeV1:
            raise TypeError("scope")
        if (
            type(self.recipes) is not tuple
            or not self.recipes
            or any(type(recipe) is not KoruDirectionalTargetRecipeV1 for recipe in self.recipes)
        ):
            raise ValueError("recipes")
        if self.schema_version != _REQUEST_SCHEMA_VERSION:
            raise ValueError("schema_version")

    @property
    def request_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_compile_request_v2",
            "schema_version": self.schema_version,
            "source_projection": self.source_projection,
            "source_projection_authority_ref": self.source_projection_authority_ref,
            "source_projection_authority_content_hash": self.source_projection_authority_content_hash,
            "source_fragment_digest": self.source_projection.fragment_digest,
            "scope": self.scope,
            "recipes": self.recipes,
        }


class KoruDirectionalTargetCompileFailureCodeV2(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    SOURCE_PROJECTION_INVALID = "SOURCE_PROJECTION_INVALID"
    HOLDOUT_SOURCE_INPUT = "HOLDOUT_SOURCE_INPUT"
    SOURCE_OUT_OF_SCOPE = "SOURCE_OUT_OF_SCOPE"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    PAIRED_BAR_INVALID = "PAIRED_BAR_INVALID"
    REVISION_INVALID = "REVISION_INVALID"
    AVAILABILITY_INVALID = "AVAILABILITY_INVALID"
    CALENDAR_AVAILABILITY_UNPROVEN = "CALENDAR_AVAILABILITY_UNPROVEN"
    UNSUPPORTED_RECIPE_FAMILY = "UNSUPPORTED_RECIPE_FAMILY"
    NEXT_BOUNDARY_EVIDENCE_MISSING = "NEXT_BOUNDARY_EVIDENCE_MISSING"
    TARGET_RULE_INVALID = "TARGET_RULE_INVALID"
    RESULT_INVALID = "RESULT_INVALID"


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileFailureV2:
    code: KoruDirectionalTargetCompileFailureCodeV2
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not KoruDirectionalTargetCompileFailureCodeV2:
            raise TypeError("code")
        if type(self.subject) is not str or not self.subject or self.subject != self.subject.strip():
            raise ValueError("subject")

    @property
    def failure_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_compile_failure_v2",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


class _CompileError(ValueError):
    def __init__(self, code: KoruDirectionalTargetCompileFailureCodeV2, subject: str) -> None:
        super().__init__(subject)
        self.code = code
        self.subject = subject


def _manifest(stream_key: str, events: tuple[MarketEvent, ...]) -> MarketStreamManifest:
    if events:
        return MarketStreamManifest.from_events(stream_key, events)
    return MarketStreamManifest(stream_key, "strategy_decision_candidate", _v1._CAPABILITY, 0, canonical_sha256(()))


def _stream_digest(stream_key: str, events: tuple[MarketEvent, ...]) -> str:
    return canonical_sha256({"type": "precomputed_target_stream", "schema_version": _SCHEMA_VERSION, "stream_key": stream_key, "events": events})


def _rebuild_recipe(recipe: KoruDirectionalTargetRecipeV1) -> KoruDirectionalTargetRecipeV1:
    params = recipe.parameters
    if type(params) is KoruMarkIndexPremiumParametersV1:
        rebuilt_params = KoruMarkIndexPremiumParametersV1(
            params.entry_premium_bps, params.exit_premium_bps, params.max_hold_hours, params.flat_when_inside_band
        )
    elif type(params) is KoruDirectionalUnsupportedParametersV1:
        rebuilt_params = KoruDirectionalUnsupportedParametersV1(params.family)
    else:
        raise TypeError("parameters")
    return KoruDirectionalTargetRecipeV1(
        recipe.family, recipe.recipe_id, recipe.strategy_id, recipe.sleeve_id,
        ArtifactRef(recipe.strategy_ref.artifact_type, recipe.strategy_ref.schema_version, recipe.strategy_ref.content_hash),
        ArtifactRef(recipe.parameter_ref.artifact_type, recipe.parameter_ref.schema_version, recipe.parameter_ref.content_hash),
        recipe.target_stream_key, recipe.instrument_id, recipe.target_exposure, recipe.bar_interval, rebuilt_params,
    )


def _trusted_request(value: object) -> KoruDirectionalTargetCompileRequestV2:
    if type(value) is not KoruDirectionalTargetCompileRequestV2:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.INVALID_REQUEST, "request_type")
    try:
        scope = KoruDirectionalDiscoveryScopeV1(
            value.scope.discovery_start, value.scope.discovery_end_exclusive, value.scope.holdout_start
        )
        rebuilt = KoruDirectionalTargetCompileRequestV2(
            value.source_projection,
            ArtifactRef(
                value.source_projection_authority_ref.artifact_type,
                value.source_projection_authority_ref.schema_version,
                value.source_projection_authority_ref.content_hash,
            ),
            value.source_projection_authority_content_hash,
            scope,
            tuple(_rebuild_recipe(recipe) for recipe in value.recipes),
            value.schema_version,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.INVALID_REQUEST, "request") from error
    if not _same(rebuilt, value):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.INVALID_REQUEST, "request_binding")
    order = tuple((recipe.family, recipe.recipe_id, recipe.parameter_ref.content_hash, recipe.target_stream_key) for recipe in rebuilt.recipes)
    if order != tuple(sorted(order)):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.INVALID_REQUEST, "recipe_order")
    if (
        len({recipe.recipe_id for recipe in rebuilt.recipes}) != len(rebuilt.recipes)
        or len({(recipe.strategy_id, recipe.parameter_ref.content_hash) for recipe in rebuilt.recipes}) != len(rebuilt.recipes)
        or len({recipe.target_stream_key for recipe in rebuilt.recipes}) != len(rebuilt.recipes)
    ):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.INVALID_REQUEST, "recipe_identity")
    return rebuilt


def _trusted_source(request: KoruDirectionalTargetCompileRequestV2) -> SourceProjectionV3:
    source = _trusted_source_result(request.source_projection)
    if source is None:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.SOURCE_PROJECTION_INVALID, "source_projection")
    authority, ref = create_binance_usdm_koru_tradifi_source_projection_authority_v3(source)
    if (
        ref != request.source_projection_authority_ref
        or authority.content_hash != request.source_projection_authority_content_hash
    ):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.SOURCE_PROJECTION_INVALID, "source_projection_authority")
    if source.request.timeline_window_end_exclusive > request.scope.holdout_start:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.HOLDOUT_SOURCE_INPUT, "source_window")
    if (
        source.request.timeline_window_start < request.scope.discovery_start
        or source.request.timeline_window_end_exclusive > request.scope.discovery_end_exclusive
    ):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.SOURCE_OUT_OF_SCOPE, "source_window")
    if len({event.event_id for event in source.source_events}) != len(source.source_events):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.DUPLICATE_IDENTITY, "source_event_id")
    if any(
        event.event_time < request.scope.discovery_start or event.event_time >= request.scope.holdout_start
        for event in (*source.source_events, *source.projection_events)
    ):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.HOLDOUT_SOURCE_INPUT, "source_event")
    return source


def _premium_stream(
    source: SourceProjectionV3,
    recipe: KoruDirectionalTargetRecipeV1,
    scope: KoruDirectionalDiscoveryScopeV1,
) -> KoruDirectionalTargetStreamV2:
    try:
        stream = _v1._premium_stream(cast(_v1.SourceProjectionV2, source), recipe, scope)
    except _v1._CompileError as error:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2(error.code.value), error.subject) from error
    return KoruDirectionalTargetStreamV2(
        stream.recipe_ref,
        stream.source_fragment_digest,
        stream.target_stream_key,
        stream.events,
        _manifest(stream.target_stream_key, stream.events),
        _stream_digest(stream.target_stream_key, stream.events),
        stream.evidence,
    )


def _compile(request: KoruDirectionalTargetCompileRequestV2) -> tuple[KoruDirectionalTargetStreamV2, ...]:
    return _compile_trusted(_trusted_request(request))


def _compile_trusted(request: KoruDirectionalTargetCompileRequestV2) -> tuple[KoruDirectionalTargetStreamV2, ...]:
    source = _trusted_source(request)
    streams: list[KoruDirectionalTargetStreamV2] = []
    for recipe in request.recipes:
        if recipe.family == "breakout":
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.CALENDAR_AVAILABILITY_UNPROVEN, recipe.recipe_id)
        if recipe.family in {"funding_carry", "cash_open_momentum"}:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV2.UNSUPPORTED_RECIPE_FAMILY, recipe.recipe_id)
        streams.append(_premium_stream(source, recipe, request.scope))
    return tuple(sorted(streams, key=lambda stream: stream.target_stream_key))


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileResultV2:
    request: KoruDirectionalTargetCompileRequestV2
    streams: tuple[KoruDirectionalTargetStreamV2, ...]
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not KoruDirectionalTargetCompileRequestV2:
            raise TypeError("request")
        if type(self.streams) is not tuple or any(type(stream) is not KoruDirectionalTargetStreamV2 for stream in self.streams):
            raise TypeError("streams")
        try:
            trusted = _trusted_request(self.request)
            expected = _compile_trusted(trusted)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("result request cannot be compiled") from error
        if not _same(trusted, self.request) or not _same(self.streams, expected):
            raise ValueError("result must exactly replay the request")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_compile_result_v2",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_digest": self.request.request_digest,
            "streams": self.streams,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileOutcomeV2:
    result: KoruDirectionalTargetCompileResultV2 | None = None
    failure: KoruDirectionalTargetCompileFailureV2 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result")
        if self.failure is not None and type(self.failure) is not KoruDirectionalTargetCompileFailureV2:
            raise TypeError("failure")


def _trusted_result(value: object) -> KoruDirectionalTargetCompileResultV2 | None:
    if type(value) is not KoruDirectionalTargetCompileResultV2:
        return None
    try:
        trusted = _trusted_request(value.request)
        rebuilt = KoruDirectionalTargetCompileResultV2(trusted, _compile_trusted(trusted))
        if (
            not _same(trusted, value.request)
            or not _same(rebuilt, value)
            or value.result_digest != canonical_sha256(value._body())
        ):
            return None
    except (AttributeError, KeyError, TypeError, ValueError, _CompileError):
        return None
    return rebuilt


def compile_binance_usdm_koru_directional_targets_v2(
    request: KoruDirectionalTargetCompileRequestV2,
) -> KoruDirectionalTargetCompileOutcomeV2:
    """Compile V3-source observations into causally evidenced target streams."""
    try:
        trusted = _trusted_request(request)
        return KoruDirectionalTargetCompileOutcomeV2(
            result=KoruDirectionalTargetCompileResultV2(trusted, _compile_trusted(trusted))
        )
    except _CompileError as error:
        return KoruDirectionalTargetCompileOutcomeV2(
            failure=KoruDirectionalTargetCompileFailureV2(error.code, error.subject)
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return KoruDirectionalTargetCompileOutcomeV2(
            failure=KoruDirectionalTargetCompileFailureV2(
                KoruDirectionalTargetCompileFailureCodeV2.RESULT_INVALID, type(error).__name__
            )
        )


__all__ = [
    "KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_ARTIFACT_TYPE_V2",
    "KORU_DIRECTIONAL_TARGET_COMPILE_RESULT_SCHEMA_VERSION_V2",
    "KoruDirectionalTargetCompileFailureCodeV2",
    "KoruDirectionalTargetCompileFailureV2",
    "KoruDirectionalTargetCompileOutcomeV2",
    "KoruDirectionalTargetCompileRequestV2",
    "KoruDirectionalTargetCompileResultV2",
    "KoruDirectionalTargetStreamV2",
    "SourceProjectionV3",
    "TargetV3",
    "compile_binance_usdm_koru_directional_targets_v2",
]
