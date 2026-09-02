"""Immutable publication of one compiled KORU directional target stream."""

from __future__ import annotations

import json
from collections import defaultdict
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
    InMemoryMarketBundleReader,
    LocalMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .local_market_bundle_repository import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)

from .binance_usdm_koru_directional_target_compiler_v1 import (
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetCompileResultV1,
    KoruDirectionalTargetStreamV1,
)
from .binance_usdm_koru_directional_target_compiler_v1 import (
    _trusted_result as _trusted_compiler_result,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruTradifiSourceProjectionResultV2,
    build_binance_usdm_koru_source_profile_authority_v2,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    _trusted_result as _trusted_source_result,
)

_SCHEMA_VERSION = 3
_PREPARATION_STREAM = "binance_usdm.tradifi.preparation_authority.koruusdt.v3"
_PREPARATION_EVENT_TYPE = "binance_usdm_tradifi_preparation_authority_koruusdt_v3"
_PREPARATION_CAPABILITY = MarketBundleCapability("binance_usdm.tradifi.preparation-authority", 1)
_BUNDLE_PREFIX = "binance-usdm-koru-directional-execution-development-v3-"
_HYBRID_BUNDLE_PREFIX = "binance-usdm-koru-tradifi-directional-hybrid-development-v3-"
_HYBRID_AUTHORITY_STREAM = "binance_usdm.tradifi.directional_hybrid_authority.koruusdt.v3"
_HYBRID_AUTHORITY_EVENT_TYPE = "binance_usdm_tradifi_directional_hybrid_authority_koruusdt_v3"
_HYBRID_AUTHORITY_CAPABILITY = MarketBundleCapability("binance_usdm.tradifi.directional-hybrid-authority", 1)
_V2_PREPARATION_STREAM = "binance_usdm.tradifi.preparation_authority.v2"
_V2_TARGET_PREFIX = "binance_usdm.tradifi.target.koruusdt.closed_market_range."


def _same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _hash(value: object, name: str) -> str:
    if type(value) is not str or len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError(f"{name} must be canonical sha256")
    try:
        int(value[7:], 16)
    except ValueError as error:
        raise ValueError(f"{name} must be canonical sha256") from error
    return value


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical text")
    return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruDirectionalExecutionBundleRequestV3:
    """Publication request; a compiler result object is mandatory, not merely its CAS ref."""

    compiler_result: KoruDirectionalTargetCompileResultV1
    compiler_result_ref: ArtifactRef
    scope_ref: ArtifactRef
    target_stream_key: str

    def __post_init__(self) -> None:
        result = _trusted_compiler_result(self.compiler_result)
        if result is None:
            raise ValueError("compiler_result must be an exact successful canonical result")
        if type(self.compiler_result_ref) is not ArtifactRef or self.compiler_result_ref != ArtifactRef(
            "koru_directional_target_compile_result", 1, result.result_digest
        ):
            raise ValueError("compiler_result_ref must exactly bind compiler result")
        scope = result.request.scope
        fixed_scope = KoruDirectionalDiscoveryScopeV1()
        if (
            scope != fixed_scope
            or type(self.scope_ref) is not ArtifactRef
            or self.scope_ref != ArtifactRef(
                "koru_directional_discovery_scope", 1, fixed_scope.scope_digest
            )
        ):
            raise ValueError("scope_ref must exactly bind the fixed discovery scope")
        _text(self.target_stream_key, "target_stream_key")
        selected = tuple(value for value in result.streams if value.target_stream_key == self.target_stream_key)
        if len(selected) != 1:
            raise ValueError("target_stream_key must select exactly one compiled stream")
        recipe = next(value for value in result.request.recipes if value.parameter_ref == selected[0].recipe_ref)
        if recipe.family != "mark_index_premium":
            raise ValueError("only supported premium streams may be published")
        object.__setattr__(self, "compiler_result", result)

    @property
    def source_projection(self) -> BinanceUsdmKoruTradifiSourceProjectionResultV2:
        return self.compiler_result.request.source_projection

    @property
    def selected_stream(self) -> KoruDirectionalTargetStreamV1:
        return next(value for value in self.compiler_result.streams if value.target_stream_key == self.target_stream_key)

    @property
    def selected_recipe(self):
        return next(value for value in self.compiler_result.request.recipes if value.parameter_ref == self.selected_stream.recipe_ref)

    @property
    def bundle_key(self) -> str:
        return _BUNDLE_PREFIX + canonical_sha256({
            "compiler_result_ref": self.compiler_result_ref,
            "scope_ref": self.scope_ref,
            "target_stream_key": self.target_stream_key,
            "target_stream_digest": self.selected_stream.target_stream_digest,
        })[7:]

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_directional_execution_bundle_request_v3",
            "schema_version": _SCHEMA_VERSION,
            "compiler_result": self.compiler_result,
            "compiler_result_ref": self.compiler_result_ref,
            "compiler_result_digest": self.compiler_result.result_digest,
            "scope_ref": self.scope_ref,
            "scope_digest": self.compiler_result.request.scope.scope_digest,
            "target_stream_key": self.target_stream_key,
            "target_stream_digest": self.selected_stream.target_stream_digest,
            "bundle_key": self.bundle_key,
            "development_only": True,
        }


class BinanceUsdmKoruDirectionalExecutionBundleFailureCodeV3(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_FRAGMENT_INVALID = "source_fragment_invalid"
    COMPILER_RESULT_INVALID = "compiler_result_invalid"
    STREAM_ASSEMBLY_INVALID = "stream_assembly_invalid"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruDirectionalExecutionBundleFailureV3:
    code: BinanceUsdmKoruDirectionalExecutionBundleFailureCodeV3
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruDirectionalExecutionBundleFailureCodeV3:
            raise TypeError("code must be exact V3 bundle failure code")
        _text(self.subject, "subject")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "binance_usdm_koru_directional_execution_bundle_failure_v3", "schema_version": _SCHEMA_VERSION, "code": self.code.value, "subject": self.subject}


@dataclass(frozen=True, slots=True)
class _Assembled:
    preparation_authority_event: MarketEvent
    streams: dict[str, tuple[MarketEvent, ...]]
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    reader: InMemoryMarketBundleReader
    events: tuple[MarketEvent, ...]


def _authority_event(request: BinanceUsdmKoruDirectionalExecutionBundleRequestV3) -> MarketEvent:
    source = request.source_projection
    stream = request.selected_stream
    recipe = request.selected_recipe
    source_authority, source_authority_ref = build_binance_usdm_koru_source_profile_authority_v2(source)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "compiler_result_ref": request.compiler_result_ref.to_canonical_dict(),
        "compiler_result_digest": request.compiler_result.result_digest,
        "scope_ref": request.scope_ref.to_canonical_dict(),
        "scope_digest": request.compiler_result.request.scope.scope_digest,
        "scope": json.loads(canonical_bytes(request.compiler_result.request.scope)),
        "source_projection_ref": request.compiler_result.request.source_projection_ref.to_canonical_dict(),
        "source_fragment_digest": stream.source_fragment_digest,
        "source_profile_authority_envelope": source_authority.to_canonical_dict(),
        "source_profile_authority_ref": source_authority_ref.to_canonical_dict(),
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
    source_hash = canonical_sha256({"type": _PREPARATION_EVENT_TYPE, "payload": payload})
    start = source.request.timeline_window_start
    return MarketEvent(
        event_id=_PREPARATION_EVENT_TYPE + ":" + source_hash,
        stream_key=_PREPARATION_STREAM,
        event_type=_PREPARATION_EVENT_TYPE,
        capability=_PREPARATION_CAPABILITY,
        instrument_id=None,
        event_time=start,
        available_time=start,
        phase=TimelinePhase(0, "market_data"),
        source_sequence=SourceSequence(0),
        revision_id=canonical_sha256({"type": _PREPARATION_EVENT_TYPE + "_revision", "source_hash": source_hash}),
        supersedes_revision_id=None,
        source_key=_PREPARATION_STREAM,
        source_hash=source_hash,
        payload=payload,
    )


def _assemble(request: BinanceUsdmKoruDirectionalExecutionBundleRequestV3) -> _Assembled:
    source = _trusted_source_result(request.source_projection)
    if source is None or source != request.source_projection:
        raise ValueError("compiler source projection is not trusted")
    stream = request.selected_stream
    if stream.source_fragment_digest != source.fragment_digest:
        raise ValueError("compiler stream source fragment mismatch")
    if stream.manifest.content_hash != canonical_sha256(stream.events):
        raise ValueError("compiler stream manifest mismatch")
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in (*source.source_events, *source.projection_events):
        grouped[event.stream_key].append(event)
    streams = {manifest.stream_key: tuple(grouped.get(manifest.stream_key, ())) for manifest in source.stream_manifests}
    manifests = list(source.stream_manifests)
    if stream.target_stream_key in streams:
        raise ValueError("target stream collides with source stream")
    streams[stream.target_stream_key] = stream.events
    manifests.append(stream.manifest)
    authority = _authority_event(request)
    streams[authority.stream_key] = (authority,)
    manifests.append(MarketStreamManifest.from_events(authority.stream_key, (authority,)))
    for manifest in manifests:
        events = streams[manifest.stream_key]
        expected = MarketStreamManifest.from_events(manifest.stream_key, events) if events else MarketStreamManifest(manifest.stream_key, manifest.event_type, manifest.capability, 0, canonical_sha256(()))
        if not _same(manifest, expected):
            raise ValueError("stream manifest does not bind published events")
    manifest = MarketBundleManifest.build(
        bundle_key=request.bundle_key,
        schema_version=_SCHEMA_VERSION,
        coverage_start=source.request.timeline_window_start,
        coverage_end_exclusive=source.request.timeline_window_end_exclusive,
        instrument_catalog_hash=source.request.instrument_catalog_hash,
        capabilities=tuple(sorted({value.capability for value in manifests})),
        streams=manifests,
    )
    bundle_ref = MarketBundleRef.from_manifest(manifest)
    reader = InMemoryMarketBundleReader(bundle_ref, manifest, streams)
    events = tuple(event for key in sorted(reader.streams) for event in reader.streams[key])
    return _Assembled(authority, reader.streams, manifest, bundle_ref, reader, events)


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruDirectionalExecutionBundleV3:
    request: BinanceUsdmKoruDirectionalExecutionBundleRequestV3
    preparation_authority_event: MarketEvent
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    reader: InMemoryMarketBundleReader
    events: tuple[MarketEvent, ...]
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        request = _trusted_request(self.request)
        if request is None:
            raise ValueError("request must be an exact V3 bundle request")
        assembled = _assemble(request)
        if not (
            type(self.preparation_authority_event) is MarketEvent
            and _same(self.preparation_authority_event, assembled.preparation_authority_event)
            and type(self.manifest) is MarketBundleManifest and _same(self.manifest, assembled.manifest)
            and type(self.bundle_ref) is MarketBundleRef and self.bundle_ref == assembled.bundle_ref
            and type(self.reader) is InMemoryMarketBundleReader and _same(self.reader.streams, assembled.reader.streams)
            and type(self.events) is tuple and _same(self.events, assembled.events)
        ):
            raise ValueError("V3 bundle result binding mismatch")
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    @property
    def source_projection(self) -> BinanceUsdmKoruTradifiSourceProjectionResultV2:
        return self.request.source_projection

    @property
    def compiler_result(self) -> KoruDirectionalTargetCompileResultV1:
        return self.request.compiler_result

    @property
    def selected_stream(self) -> KoruDirectionalTargetStreamV1:
        return self.request.selected_stream

    @property
    def streams(self):
        return self.reader.streams

    def _body(self) -> dict[str, object]:
        return {"type": "binance_usdm_koru_directional_execution_bundle_v3", "schema_version": _SCHEMA_VERSION, "request": self.request, "preparation_authority_event": self.preparation_authority_event, "manifest": self.manifest, "bundle_ref": self.bundle_ref, "events": self.events, "development_only": True, "deployment_authorized": False}

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_request(value: object) -> BinanceUsdmKoruDirectionalExecutionBundleRequestV3 | None:
    if type(value) is not BinanceUsdmKoruDirectionalExecutionBundleRequestV3:
        return None
    try:
        rebuilt = BinanceUsdmKoruDirectionalExecutionBundleRequestV3(
            value.compiler_result, value.compiler_result_ref, value.scope_ref,
            value.target_stream_key,
        )
        return rebuilt if _same(rebuilt, value) else None
    except (AttributeError, TypeError, ValueError):
        return None


def _trusted_result(value: object) -> BinanceUsdmKoruDirectionalExecutionBundleV3 | None:
    if type(value) is not BinanceUsdmKoruDirectionalExecutionBundleV3:
        return None
    try:
        rebuilt = BinanceUsdmKoruDirectionalExecutionBundleV3(value.request, value.preparation_authority_event, value.manifest, value.bundle_ref, value.reader, value.events)
        if not _same(rebuilt, value) or value.result_digest != canonical_sha256(value._body()):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruDirectionalExecutionBundleOutcomeV3:
    result: BinanceUsdmKoruDirectionalExecutionBundleV3 | None = None
    failure: BinanceUsdmKoruDirectionalExecutionBundleFailureV3 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result must be exact trusted V3 bundle")
        if self.failure is not None and type(self.failure) is not BinanceUsdmKoruDirectionalExecutionBundleFailureV3:
            raise TypeError("failure must be exact V3 bundle failure")


def build_binance_usdm_koru_directional_execution_bundle_v3(request: BinanceUsdmKoruDirectionalExecutionBundleRequestV3) -> BinanceUsdmKoruDirectionalExecutionBundleOutcomeV3:
    trusted = _trusted_request(request)
    if trusted is None:
        return BinanceUsdmKoruDirectionalExecutionBundleOutcomeV3(failure=BinanceUsdmKoruDirectionalExecutionBundleFailureV3(BinanceUsdmKoruDirectionalExecutionBundleFailureCodeV3.INVALID_REQUEST, "request"))
    try:
        assembled = _assemble(trusted)
        return BinanceUsdmKoruDirectionalExecutionBundleOutcomeV3(result=BinanceUsdmKoruDirectionalExecutionBundleV3(trusted, assembled.preparation_authority_event, assembled.manifest, assembled.bundle_ref, assembled.reader, assembled.events))
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return BinanceUsdmKoruDirectionalExecutionBundleOutcomeV3(failure=BinanceUsdmKoruDirectionalExecutionBundleFailureV3(BinanceUsdmKoruDirectionalExecutionBundleFailureCodeV3.STREAM_ASSEMBLY_INVALID, type(error).__name__))


def _read(reader: MarketBundleReader, stream_key: str) -> tuple[MarketEvent, ...]:
    cursor = reader.open_cursor(stream_key, batch_size=64)
    events: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    if any(type(event) is not MarketEvent for event in events):
        raise ValueError("market_event")
    return tuple(events)


def _hybrid_authority_event(
    *,
    v2_reader: MarketBundleReader,
    v3: BinanceUsdmKoruDirectionalExecutionBundleV3,
) -> MarketEvent:
    authority = v3.preparation_authority_event
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "v2_bundle_ref": v2_reader.bundle_ref.to_canonical_dict(),
        "v2_bundle_digest": v2_reader.bundle_ref.manifest_hash,
        "v2_bundle_manifest": v2_reader.manifest.to_canonical_dict(),
        "v3_bundle_ref": v3.bundle_ref.to_canonical_dict(),
        "v3_bundle_digest": v3.bundle_ref.manifest_hash,
        "v3_bundle_manifest": v3.manifest.to_canonical_dict(),
        "v3_preparation_authority_event": authority.to_canonical_dict(),
        "v3_preparation_authority_digest": canonical_sha256(authority),
        "target_stream_key": v3.selected_stream.target_stream_key,
        "target_stream_digest": v3.selected_stream.target_stream_digest,
    }
    source_hash = canonical_sha256({"type": _HYBRID_AUTHORITY_EVENT_TYPE, "payload": payload})
    return MarketEvent(
        event_id=_HYBRID_AUTHORITY_EVENT_TYPE + ":" + source_hash,
        stream_key=_HYBRID_AUTHORITY_STREAM,
        event_type=_HYBRID_AUTHORITY_EVENT_TYPE,
        capability=_HYBRID_AUTHORITY_CAPABILITY,
        instrument_id=None,
        event_time=v2_reader.manifest.coverage_start,
        available_time=v2_reader.manifest.coverage_start,
        phase=TimelinePhase(0, "market_data"),
        source_sequence=SourceSequence(0),
        revision_id=canonical_sha256({"type": _HYBRID_AUTHORITY_EVENT_TYPE + "_revision", "source_hash": source_hash}),
        supersedes_revision_id=None,
        source_key=_HYBRID_AUTHORITY_STREAM,
        source_hash=source_hash,
        payload=payload,
    )


def _verify_v2_v3_source_binding(
    *,
    v2_reader: MarketBundleReader,
    v3: BinanceUsdmKoruDirectionalExecutionBundleV3,
) -> None:
    if (
        type(v2_reader.manifest) is not MarketBundleManifest
        or type(v2_reader.bundle_ref) is not MarketBundleRef
        or v2_reader.manifest.schema_version != 2
        or not v2_reader.manifest.bundle_key.startswith("binance-usdm-koru-tradifi-execution-development-v2-")
        or MarketBundleRef.from_manifest(v2_reader.manifest) != v2_reader.bundle_ref
    ):
        raise ValueError("v2_bundle")
    events = _read(v2_reader, _V2_PREPARATION_STREAM)
    if len(events) != 1:
        raise ValueError("v2_preparation")
    v2_payload = events[0].payload
    v3_payload = v3.preparation_authority_event.payload
    if not (
        isinstance(v2_payload, Mapping)
        and isinstance(v3_payload, Mapping)
        and v2_payload.get("source_profile_authority_envelope")
        == v3_payload.get("source_profile_authority_envelope")
        and v2_payload.get("source_profile_authority_ref")
        == v3_payload.get("source_profile_authority_ref")
    ):
        raise ValueError("v2_v3_source_binding")


def publish_binance_usdm_koru_directional_hybrid_bundle_v3(
    *,
    v2_market_reader: MarketBundleReader,
    v3_execution_bundle: BinanceUsdmKoruDirectionalExecutionBundleV3,
    publication_root: Path,
) -> LocalMarketBundleReader:
    """Publish and reopen the only V3 runtime market-bundle input."""
    trusted = _trusted_result(v3_execution_bundle)
    if trusted is None or not isinstance(publication_root, Path):
        raise ValueError("hybrid_publication_input")
    _verify_v2_v3_source_binding(v2_reader=v2_market_reader, v3=trusted)
    v2_manifest = v2_market_reader.manifest
    target_key = trusted.selected_stream.target_stream_key
    if target_key in {stream.stream_key for stream in v2_manifest.streams}:
        raise ValueError("target_stream_collision")
    streams = {
        stream.stream_key: _read(v2_market_reader, stream.stream_key)
        for stream in v2_manifest.streams
        if not stream.stream_key.startswith(_V2_TARGET_PREFIX)
    }
    authority = trusted.preparation_authority_event
    if authority.stream_key in streams or _HYBRID_AUTHORITY_STREAM in streams:
        raise ValueError("authority_stream_collision")
    streams[target_key] = trusted.selected_stream.events
    streams[authority.stream_key] = (authority,)
    hybrid_authority = _hybrid_authority_event(v2_reader=v2_market_reader, v3=trusted)
    streams[hybrid_authority.stream_key] = (hybrid_authority,)
    manifests = tuple(
        MarketStreamManifest.from_events(key, events)
        for key, events in sorted(streams.items())
    )
    manifest = MarketBundleManifest.build(
        bundle_key=_HYBRID_BUNDLE_PREFIX + canonical_sha256({
            "v2_bundle_ref": v2_market_reader.bundle_ref,
            "v3_bundle_ref": trusted.bundle_ref,
            "target_stream_digest": trusted.selected_stream.target_stream_digest,
        })[7:],
        schema_version=_SCHEMA_VERSION,
        coverage_start=v2_manifest.coverage_start,
        coverage_end_exclusive=v2_manifest.coverage_end_exclusive,
        instrument_catalog_hash=v2_manifest.instrument_catalog_hash,
        capabilities=tuple(sorted({stream.capability for stream in manifests})),
        streams=manifests,
    )
    bundle_ref = MarketBundleRef.from_manifest(manifest)
    root = publication_root / "directional-v3-market-bundles"
    outcome = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads={key: canonical_bytes(events) for key, events in streams.items()},
        retention_policy_ref="binance-usdm-tradifi-directional-v3",
    )
    if outcome.result is None or outcome.result.bundle_ref != bundle_ref:
        raise ValueError("hybrid_publication")
    reader = LocalMarketBundleReader.open(repository_root=root, bundle_ref=bundle_ref)
    if reader.manifest != manifest or reader.bundle_ref != bundle_ref:
        raise ValueError("hybrid_reopen")
    return reader


__all__ = [
    "BinanceUsdmKoruDirectionalExecutionBundleFailureCodeV3",
    "BinanceUsdmKoruDirectionalExecutionBundleFailureV3",
    "BinanceUsdmKoruDirectionalExecutionBundleOutcomeV3",
    "BinanceUsdmKoruDirectionalExecutionBundleRequestV3",
    "BinanceUsdmKoruDirectionalExecutionBundleV3",
    "build_binance_usdm_koru_directional_execution_bundle_v3",
    "publish_binance_usdm_koru_directional_hybrid_bundle_v3",
]
