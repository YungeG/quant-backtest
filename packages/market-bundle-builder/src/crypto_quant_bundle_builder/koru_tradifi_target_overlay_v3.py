"""Immutable one-target overlay over a published target-free economics bundle."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from crypto_quant_domain import (
    ArtifactRef,
    SourceSequence,
    TimelinePhase,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    LocalMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketEvent,
    MarketStreamManifest,
)

from .binance_usdm_koru_directional_target_compiler_v1 import (
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetCompileResultV1,
    KoruDirectionalTargetStreamV1,
)
from .binance_usdm_koru_directional_target_compiler_v1 import (
    _trusted_result as _trusted_compiler_result,
)
from .koru_tradifi_economics_bundle_v3 import KoruTradifiEconomicsBundleV3
from .local_market_bundle_repository import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)

_SCHEMA_VERSION = 3
_AUTHORITY_STREAM = "binance_usdm.tradifi.target_overlay_authority.koruusdt.v3"
_AUTHORITY_EVENT = "koru_tradifi_target_overlay_authority_v3"
_AUTHORITY_CAPABILITY = MarketBundleCapability("binance_usdm.tradifi.target-overlay-authority", 1)
_ECONOMICS_STREAM = "binance_usdm.tradifi.economics_authority.koruusdt.v3"
_V2_TARGET_PREFIX = "binance_usdm.tradifi.target.koruusdt.closed_market_range."
_FORBIDDEN_ECONOMICS_STREAMS = frozenset({
    "binance_usdm.tradifi.preparation_authority.v2",
    "binance_usdm.tradifi.directional_hybrid_authority.koruusdt.v3",
})
_BUNDLE_PREFIX = "koru-tradifi-target-overlay-development-v3-"


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(name)
    return value


def _read(reader: LocalMarketBundleReader, stream_key: str) -> tuple[MarketEvent, ...]:
    cursor = reader.open_cursor(stream_key, batch_size=64)
    events: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    if any(type(event) is not MarketEvent for event in events):
        raise ValueError("market_event")
    return tuple(events)


@dataclass(frozen=True, slots=True)
class KoruTradifiTargetOverlayRequestV3:
    """A trusted economics result and one trusted premium compiler stream."""

    economics_bundle: KoruTradifiEconomicsBundleV3
    compiler_result: KoruDirectionalTargetCompileResultV1
    compiler_result_ref: ArtifactRef
    scope_ref: ArtifactRef
    target_stream_key: str
    repository_root: Path

    def __post_init__(self) -> None:
        result = _trusted_compiler_result(self.compiler_result)
        if result is None:
            raise ValueError("compiler_result")
        if type(self.economics_bundle) is not KoruTradifiEconomicsBundleV3:
            raise TypeError("economics_bundle")
        reader = LocalMarketBundleReader.validate_repository_open_reader_v1(self.economics_bundle.reader)
        if reader.bundle_ref != self.economics_bundle.bundle_ref or reader.manifest != self.economics_bundle.manifest:
            raise ValueError("economics_reader")
        if (
            type(self.compiler_result_ref) is not ArtifactRef
            or self.compiler_result_ref != ArtifactRef("koru_directional_target_compile_result", 1, result.result_digest)
        ):
            raise ValueError("compiler_result_ref")
        fixed_scope = KoruDirectionalDiscoveryScopeV1()
        if (
            result.request.scope != fixed_scope
            or type(self.scope_ref) is not ArtifactRef
            or self.scope_ref != ArtifactRef("koru_directional_discovery_scope", 1, fixed_scope.scope_digest)
        ):
            raise ValueError("scope_ref")
        _text(self.target_stream_key, "target_stream_key")
        selected = tuple(stream for stream in result.streams if stream.target_stream_key == self.target_stream_key)
        if len(selected) != 1:
            raise ValueError("target_stream_key")
        recipe = next(recipe for recipe in result.request.recipes if recipe.parameter_ref == selected[0].recipe_ref)
        if recipe.family != "mark_index_premium" or self.target_stream_key.startswith(_V2_TARGET_PREFIX):
            raise ValueError("premium_recipe")
        if not isinstance(self.repository_root, Path) or not self.repository_root.is_absolute():
            raise ValueError("repository_root")
        object.__setattr__(self, "compiler_result", result)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_target_overlay_request_v3",
            "schema_version": _SCHEMA_VERSION,
            "economics_bundle": self.economics_bundle,
            "compiler_result": self.compiler_result,
            "compiler_result_ref": self.compiler_result_ref,
            "scope_ref": self.scope_ref,
            "target_stream_key": self.target_stream_key,
        }

    @property
    def selected_stream(self) -> KoruDirectionalTargetStreamV1:
        return next(stream for stream in self.compiler_result.streams if stream.target_stream_key == self.target_stream_key)

    @property
    def selected_recipe(self):
        return next(recipe for recipe in self.compiler_result.request.recipes if recipe.parameter_ref == self.selected_stream.recipe_ref)

    @property
    def overlay_key(self) -> str:
        return _BUNDLE_PREFIX + canonical_sha256({
            "economics_bundle_ref": self.economics_bundle.bundle_ref,
            "economics_authority_digest": self.economics_bundle.authority_digest,
            "compiler_result_ref": self.compiler_result_ref,
            "scope_ref": self.scope_ref,
            "target_stream_digest": self.selected_stream.target_stream_digest,
        })[7:]


class KoruTradifiTargetOverlayFailureCodeV3(str, Enum):
    INVALID_REQUEST = "invalid_request"
    ECONOMICS_INVALID = "economics_invalid"
    SOURCE_BINDING_INVALID = "source_binding_invalid"
    STREAM_ASSEMBLY_INVALID = "stream_assembly_invalid"
    MARKET_PUBLICATION_FAILED = "market_publication_failed"
    REOPEN_FAILED = "reopen_failed"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class KoruTradifiTargetOverlayFailureV3:
    code: KoruTradifiTargetOverlayFailureCodeV3
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not KoruTradifiTargetOverlayFailureCodeV3:
            raise TypeError("code")
        _text(self.subject, "subject")


@dataclass(frozen=True, slots=True)
class KoruTradifiTargetOverlayV3:
    request: KoruTradifiTargetOverlayRequestV3
    authority_event: MarketEvent
    manifest: MarketBundleManifest
    reader: LocalMarketBundleReader
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.request) is not KoruTradifiTargetOverlayRequestV3
            or type(self.authority_event) is not MarketEvent
            or type(self.manifest) is not MarketBundleManifest
            or type(self.reader) is not LocalMarketBundleReader
            or self.reader.manifest != self.manifest
        ):
            raise ValueError("overlay_binding")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    @property
    def bundle_ref(self):
        return self.reader.bundle_ref

    @property
    def selected_stream(self) -> KoruDirectionalTargetStreamV1:
        return self.request.selected_stream

    def _body(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_target_overlay_v3",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "authority_event": self.authority_event,
            "manifest": self.manifest,
            "bundle_ref": self.bundle_ref,
            "development_only": True,
            "deployment_authorized": False,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


@dataclass(frozen=True, slots=True)
class KoruTradifiTargetOverlayOutcomeV3:
    result: KoruTradifiTargetOverlayV3 | None = None
    failure: KoruTradifiTargetOverlayFailureV3 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome")


def _failure(code: KoruTradifiTargetOverlayFailureCodeV3, subject: str) -> KoruTradifiTargetOverlayOutcomeV3:
    return KoruTradifiTargetOverlayOutcomeV3(failure=KoruTradifiTargetOverlayFailureV3(code, subject))


def _economics_streams(request: KoruTradifiTargetOverlayRequestV3) -> dict[str, tuple[MarketEvent, ...]]:
    bundle = request.economics_bundle
    reader = LocalMarketBundleReader.validate_repository_open_reader_v1(bundle.reader)
    if reader.bundle_ref != bundle.bundle_ref or reader.manifest != bundle.manifest:
        raise ValueError("economics_reader")
    economics_events = _read(reader, _ECONOMICS_STREAM)
    if len(economics_events) != 1 or economics_events[0] != bundle.economics_authority_event:
        raise ValueError("economics_authority")
    payload = economics_events[0].payload
    if (
        not isinstance(payload, Mapping)
        or payload.get("authority_digest") != bundle.authority_digest
        or payload.get("source_fragment_digest") != request.selected_stream.source_fragment_digest
        or payload.get("artifact_refs", ())[0] != bundle.authority_refs[0].to_canonical_dict()
        or payload.get("stream_manifests") is None
    ):
        raise ValueError("source_binding")
    streams = {stream.stream_key: _read(reader, stream.stream_key) for stream in reader.manifest.streams}
    if any(key in _FORBIDDEN_ECONOMICS_STREAMS or ".target." in key for key in streams):
        raise ValueError("legacy_economics_stream")
    for stream in reader.manifest.streams:
        if MarketStreamManifest.from_events(stream.stream_key, streams[stream.stream_key]) != stream:
            raise ValueError("economics_stream_manifest")
    return streams


def _authority_event(request: KoruTradifiTargetOverlayRequestV3, economics_manifest: MarketBundleManifest) -> MarketEvent:
    stream = request.selected_stream
    recipe = request.selected_recipe
    bundle = request.economics_bundle
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "economics_bundle_ref": bundle.bundle_ref.to_canonical_dict(),
        "economics_bundle_digest": bundle.bundle_ref.manifest_hash,
        "economics_authority_digest": bundle.authority_digest,
        "economics_bundle_manifest": bundle.manifest.to_canonical_dict(),
        "economics_stream_manifests": tuple(value.to_canonical_dict() for value in economics_manifest.streams),
        "coverage_start": economics_manifest.coverage_start.to_canonical_dict(),
        "coverage_end_exclusive": economics_manifest.coverage_end_exclusive.to_canonical_dict(),
        "instrument_catalog_hash": economics_manifest.instrument_catalog_hash,
        "source_fragment_digest": stream.source_fragment_digest,
        "source_profile_authority_envelope": bundle.source_profile_authority.to_canonical_dict(),
        "source_profile_authority_ref": bundle.authority_refs[0].to_canonical_dict(),
        "compiler_result_ref": request.compiler_result_ref.to_canonical_dict(),
        "compiler_result_digest": request.compiler_result.result_digest,
        "scope_ref": request.scope_ref.to_canonical_dict(),
        "scope_digest": request.compiler_result.request.scope.scope_digest,
        "scope": json.loads(canonical_bytes(request.compiler_result.request.scope)),
        "source_projection_ref": request.compiler_result.request.source_projection_ref.to_canonical_dict(),
        "recipe": json.loads(canonical_bytes(recipe)),
        "recipe_ref": stream.recipe_ref.to_canonical_dict(),
        "recipe_digest": recipe.recipe_digest,
        "strategy_ref": recipe.strategy_ref.to_canonical_dict(),
        "strategy_id": recipe.strategy_id,
        "sleeve_id": recipe.sleeve_id,
        "target_stream_key": stream.target_stream_key,
        "target_stream_digest": stream.target_stream_digest,
        "target_stream_manifest": stream.manifest.to_canonical_dict(),
        "target_events": tuple(event.to_canonical_dict() for event in stream.events),
        "target_events_digest": canonical_sha256(stream.events),
    }
    source_hash = canonical_sha256({"type": _AUTHORITY_EVENT, "payload": payload})
    return MarketEvent(
        event_id=_AUTHORITY_EVENT + ":" + source_hash,
        stream_key=_AUTHORITY_STREAM,
        event_type=_AUTHORITY_EVENT,
        capability=_AUTHORITY_CAPABILITY,
        instrument_id=None,
        event_time=economics_manifest.coverage_start,
        available_time=economics_manifest.coverage_start,
        phase=TimelinePhase(0, "market_data"),
        source_sequence=SourceSequence(0),
        revision_id=canonical_sha256({"type": _AUTHORITY_EVENT + "_revision", "source_hash": source_hash}),
        supersedes_revision_id=None,
        source_key=_AUTHORITY_STREAM,
        source_hash=source_hash,
        payload=payload,
    )


def publish_koru_tradifi_target_overlay_v3(
    request: KoruTradifiTargetOverlayRequestV3,
) -> KoruTradifiTargetOverlayOutcomeV3:
    """Copy the sealed economics bytes and add exactly one compiler-selected target."""
    if type(request) is not KoruTradifiTargetOverlayRequestV3:
        return _failure(KoruTradifiTargetOverlayFailureCodeV3.INVALID_REQUEST, "request")
    try:
        streams = _economics_streams(request)
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return _failure(KoruTradifiTargetOverlayFailureCodeV3.ECONOMICS_INVALID, "economics")
    try:
        target = request.selected_stream
        if target.target_stream_key in streams or target.manifest.content_hash != canonical_sha256(target.events):
            raise ValueError("target_stream")
        authority = _authority_event(request, request.economics_bundle.manifest)
        if authority.stream_key in streams:
            raise ValueError("authority_stream")
        streams[target.target_stream_key] = target.events
        streams[authority.stream_key] = (authority,)
        manifests = tuple(MarketStreamManifest.from_events(key, events) for key, events in sorted(streams.items()))
        manifest = MarketBundleManifest.build(
            bundle_key=request.overlay_key,
            schema_version=_SCHEMA_VERSION,
            coverage_start=request.economics_bundle.manifest.coverage_start,
            coverage_end_exclusive=request.economics_bundle.manifest.coverage_end_exclusive,
            instrument_catalog_hash=request.economics_bundle.manifest.instrument_catalog_hash,
            capabilities=tuple(sorted({stream.capability for stream in manifests})),
            streams=manifests,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(KoruTradifiTargetOverlayFailureCodeV3.STREAM_ASSEMBLY_INVALID, "overlay")
    outcome = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=request.repository_root)
    ).publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads={key: canonical_bytes(events) for key, events in streams.items()},
        retention_policy_ref="koru-tradifi-target-overlay-v3",
    )
    if outcome.result is None:
        return _failure(KoruTradifiTargetOverlayFailureCodeV3.MARKET_PUBLICATION_FAILED, "overlay")
    try:
        reader = LocalMarketBundleReader.open(repository_root=request.repository_root, bundle_ref=outcome.result.bundle_ref)
        if reader.manifest != manifest:
            raise ValueError("readback")
    except (AttributeError, OSError, TypeError, ValueError):
        return _failure(KoruTradifiTargetOverlayFailureCodeV3.REOPEN_FAILED, "overlay")
    try:
        return KoruTradifiTargetOverlayOutcomeV3(result=KoruTradifiTargetOverlayV3(request, authority, manifest, reader))
    except (AttributeError, TypeError, ValueError):
        return _failure(KoruTradifiTargetOverlayFailureCodeV3.RESULT_INVALID, "overlay")


__all__ = [
    "KoruTradifiTargetOverlayFailureCodeV3",
    "KoruTradifiTargetOverlayFailureV3",
    "KoruTradifiTargetOverlayOutcomeV3",
    "KoruTradifiTargetOverlayRequestV3",
    "KoruTradifiTargetOverlayV3",
    "publish_koru_tradifi_target_overlay_v3",
]
