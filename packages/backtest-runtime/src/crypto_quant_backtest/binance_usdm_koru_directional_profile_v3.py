"""Sealed V3 KORU directional authority reconstructed from published market bytes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import crypto_quant_domain as domain
from crypto_quant_market_data import (
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
)

from .binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
    BinanceUsdmTradifiBarBacktestFailureCode,
)
from .target_stream import (
    TARGET_STREAM_CAPABILITY,
    TARGET_STREAM_EVENT_TYPE,
    PrecomputedTargetStream,
)

_PREPARATION_STREAM = "binance_usdm.tradifi.preparation_authority.koruusdt.v3"
_PREPARATION_EVENT_TYPE = "binance_usdm_tradifi_preparation_authority_koruusdt_v3"
_HYBRID_AUTHORITY_STREAM = "binance_usdm.tradifi.directional_hybrid_authority.koruusdt.v3"
_HYBRID_AUTHORITY_EVENT_TYPE = "binance_usdm_tradifi_directional_hybrid_authority_koruusdt_v3"
_HYBRID_BUNDLE_PREFIX = "binance-usdm-koru-tradifi-directional-hybrid-development-v3-"
_V2_BUNDLE_PREFIX = "binance-usdm-koru-tradifi-execution-development-v2-"
_V2_TARGET_PREFIX = "binance_usdm.tradifi.target.koruusdt.closed_market_range."
_FIXED_SCOPE_WIRE = {
    "type": "koru_directional_discovery_scope_v1",
    "schema_version": 1,
    "discovery_start": {"type": "utc_instant", "epoch_nanoseconds": 1_784_109_600_000_000_000},
    "discovery_end_exclusive": {"type": "utc_instant", "epoch_nanoseconds": 1_787_569_200_000_000_000},
    "holdout_start": {"type": "utc_instant", "epoch_nanoseconds": 1_787_569_200_000_000_000},
}


def _failure(subject: str) -> BinanceUsdmTradifiBarBacktestFailure:
    return BinanceUsdmTradifiBarBacktestFailure(
        BinanceUsdmTradifiBarBacktestFailureCode.PREPARATION_AUTHORITY_INVALID, subject
    )


def _read(reader: MarketBundleReader, stream_key: str) -> tuple[MarketEvent, ...]:
    cursor = reader.open_cursor(stream_key, batch_size=64)
    events: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    if any(type(event) is not MarketEvent for event in events):
        raise ValueError("market_event")
    return tuple(events)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(name)
    return value


def _digest(value: object, name: str) -> str:
    if type(value) is not str or len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError(name)
    int(value[7:], 16)
    return value


def _artifact_ref(value: object) -> domain.ArtifactRef:
    if not isinstance(value, Mapping) or set(value) != {
        "type", "artifact_type", "schema_version", "content_hash"
    } or value.get("type") != "artifact_ref":
        raise ValueError("artifact_ref")
    return domain.ArtifactRef(
        _text(value["artifact_type"], "artifact_type"),
        value["schema_version"],
        _digest(value["content_hash"], "content_hash"),
    )


def _market_ref(value: object) -> MarketBundleRef:
    if not isinstance(value, Mapping) or set(value) != {
        "type", "bundle_key", "manifest_hash"
    } or value.get("type") != "market_bundle_ref":
        raise ValueError("market_bundle_ref")
    return MarketBundleRef(
        _text(value["bundle_key"], "bundle_key"),
        _digest(value["manifest_hash"], "manifest_hash"),
    )


def _manifest_wire(
    value: object, *, ref: MarketBundleRef, schema_version: int, prefix: str
) -> Mapping[str, object]:
    keys = {
        "type", "bundle_key", "schema_version", "coverage_start",
        "coverage_end_exclusive", "instrument_catalog_hash", "capabilities",
        "streams", "content_hash",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("bundle_manifest")
    body = dict(value)
    content_hash = body.pop("content_hash")
    body["type"] = "market_bundle_manifest_body"
    if (
        value.get("type") != "market_bundle_manifest"
        or value.get("schema_version") != schema_version
        or value.get("bundle_key") != ref.bundle_key
        or not ref.bundle_key.startswith(prefix)
        or _digest(content_hash, "manifest_content_hash") != domain.canonical_sha256(body)
        or domain.canonical_sha256(value) != ref.manifest_hash
    ):
        raise ValueError("bundle_manifest")
    return value


def _envelope(value: object) -> domain.ArtifactEnvelope:
    if not isinstance(value, Mapping) or set(value) != {
        "artifact_type", "schema_version", "payload", "content_hash"
    }:
        raise ValueError("artifact_envelope")
    envelope = domain.ArtifactEnvelope.create(
        value["artifact_type"], value["schema_version"], value["payload"]
    )
    if envelope.to_canonical_dict() != value:
        raise ValueError("artifact_envelope")
    return envelope


def _stream_wire(manifest: Mapping[str, object], stream_key: str) -> Mapping[str, object]:
    streams = manifest.get("streams")
    if not isinstance(streams, tuple):
        raise ValueError("manifest_streams")
    selected = tuple(
        value for value in streams
        if isinstance(value, Mapping) and value.get("stream_key") == stream_key
    )
    if len(selected) != 1:
        raise ValueError("manifest_stream")
    return selected[0]


@dataclass(frozen=True, slots=True)
class KoruDirectionalV3PublicationWire:
    """Exact builder-published V2/V3 lineage embedded in the hybrid bundle."""

    v2_bundle_ref: MarketBundleRef
    v2_bundle_digest: str
    v2_bundle_manifest: Mapping[str, object]
    v3_bundle_ref: MarketBundleRef
    v3_bundle_digest: str
    v3_bundle_manifest: Mapping[str, object]
    v3_preparation_authority_event: Mapping[str, object]
    v3_preparation_authority_digest: str
    target_stream_key: str
    target_stream_digest: str

    def __post_init__(self) -> None:
        if type(self.v2_bundle_ref) is not MarketBundleRef or type(self.v3_bundle_ref) is not MarketBundleRef:
            raise TypeError("bundle_refs")
        if self.v2_bundle_digest != self.v2_bundle_ref.manifest_hash or self.v3_bundle_digest != self.v3_bundle_ref.manifest_hash:
            raise ValueError("bundle_digests")
        _digest(self.v3_preparation_authority_digest, "v3_preparation_authority_digest")
        _text(self.target_stream_key, "target_stream_key")
        _digest(self.target_stream_digest, "target_stream_digest")


@dataclass(frozen=True, slots=True)
class KoruDirectionalV3StrategyAuthority:
    """The sole V3 strategy identity admitted to directional preparation."""

    bundle_ref: MarketBundleRef
    bundle_digest: str
    v2_bundle_ref: MarketBundleRef
    v2_bundle_digest: str
    v3_bundle_ref: MarketBundleRef
    v3_bundle_digest: str
    compiler_result_ref: domain.ArtifactRef
    selected_recipe_id: str
    strategy_ref: domain.ArtifactRef
    parameter_ref: domain.ArtifactRef
    strategy_id: str
    sleeve_id: str
    target_stream_key: str
    target_stream_digest: str
    target_exposure: str
    scope_ref: domain.ArtifactRef
    source_fragment_digest: str
    source_profile_authority_envelope: domain.ArtifactEnvelope
    source_profile_authority_ref: domain.ArtifactRef
    target_stream: PrecomputedTargetStream

    def __post_init__(self) -> None:
        refs = (
            self.compiler_result_ref, self.strategy_ref, self.parameter_ref,
            self.scope_ref, self.source_profile_authority_ref,
        )
        if (
            type(self.bundle_ref) is not MarketBundleRef
            or type(self.v2_bundle_ref) is not MarketBundleRef
            or type(self.v3_bundle_ref) is not MarketBundleRef
            or any(type(value) is not domain.ArtifactRef for value in refs)
        ):
            raise TypeError("authority_refs")
        if (
            self.bundle_digest != self.bundle_ref.manifest_hash
            or self.v2_bundle_digest != self.v2_bundle_ref.manifest_hash
            or self.v3_bundle_digest != self.v3_bundle_ref.manifest_hash
            or (self.compiler_result_ref.artifact_type, self.compiler_result_ref.schema_version) != ("koru_directional_target_compile_result", 1)
            or (self.strategy_ref.artifact_type, self.strategy_ref.schema_version) != ("strategy_definition", 1)
            or (self.parameter_ref.artifact_type, self.parameter_ref.schema_version) != ("strategy_parameter_set", 1)
            or (self.scope_ref.artifact_type, self.scope_ref.schema_version) != ("koru_directional_discovery_scope", 1)
            or (self.source_profile_authority_ref.artifact_type, self.source_profile_authority_ref.schema_version) != ("binance_usdm_koru_source_profile_authority", 2)
        ):
            raise ValueError("authority_refs")
        for name in ("selected_recipe_id", "strategy_id", "sleeve_id", "target_stream_key", "target_exposure"):
            _text(getattr(self, name), name)
        try:
            exposure = Decimal(self.target_exposure)
        except InvalidOperation as error:
            raise ValueError("target_exposure") from error
        if not exposure.is_finite() or exposure <= 0 or str(exposure) != self.target_exposure:
            raise ValueError("target_exposure")
        if (
            type(self.source_profile_authority_envelope) is not domain.ArtifactEnvelope
            or self.source_profile_authority_ref != domain.ArtifactRef.from_envelope(self.source_profile_authority_envelope)
            or type(self.target_stream) is not PrecomputedTargetStream
            or self.target_stream.stream_key != self.target_stream_key
            or self.target_stream.target_stream_digest != self.target_stream_digest
        ):
            raise ValueError("published_target_binding")

    @property
    def events(self) -> tuple[MarketEvent, ...]:
        return self.target_stream.events


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruDirectionalTargetConsumptionV3:
    """Durable V3 target identity; events remain exactly the published bytes."""

    strategy_ref: domain.ArtifactRef
    parameter_ref: domain.ArtifactRef
    strategy_id: str
    sleeve_id: str
    target_exposure: str
    target_stream: PrecomputedTargetStream
    target_stream_digest: str
    source_fragment_digest: str
    scope_ref: domain.ArtifactRef

    def __post_init__(self) -> None:
        if type(self.strategy_ref) is not domain.ArtifactRef or type(self.parameter_ref) is not domain.ArtifactRef or type(self.scope_ref) is not domain.ArtifactRef:
            raise TypeError("authority_refs")
        if type(self.target_stream) is not PrecomputedTargetStream or self.target_stream.target_stream_digest != self.target_stream_digest:
            raise ValueError("target_stream")
        for name in ("strategy_id", "sleeve_id", "target_exposure"):
            _text(getattr(self, name), name)
        try:
            exposure = Decimal(self.target_exposure)
        except InvalidOperation as error:
            raise ValueError("target_exposure") from error
        if not exposure.is_finite() or exposure <= 0 or str(exposure) != self.target_exposure:
            raise ValueError("target_exposure")
        for event in self.target_stream.events:
            candidate = event.payload.get("candidate") if isinstance(event.payload, Mapping) else None
            targets = candidate.get("targets") if isinstance(candidate, Mapping) else None
            if (
                event.event_type != TARGET_STREAM_EVENT_TYPE
                or event.capability != TARGET_STREAM_CAPABILITY
                or event.instrument_id is not None
                or event.available_time != event.event_time
                or not isinstance(candidate, Mapping)
                or candidate.get("strategy_id") != self.strategy_id
                or candidate.get("sleeve_id") != self.sleeve_id
                or "fills" in candidate
                or "pnl" in candidate
                or not isinstance(targets, tuple)
                or len(targets) != 1
                or not isinstance(targets[0], Mapping)
            ):
                raise ValueError("target_event")
            value = targets[0].get("value")
            if type(value) is not str or value not in {"0", self.target_exposure, "-" + self.target_exposure}:
                raise ValueError("target_exposure")


class BinanceUsdmKoruDirectionalPlannerV3:
    """Admits and normalizes published V3 bytes; it never compiler-imports."""

    @staticmethod
    def target(authority: KoruDirectionalV3StrategyAuthority) -> BinanceUsdmKoruDirectionalTargetConsumptionV3:
        if type(authority) is not KoruDirectionalV3StrategyAuthority:
            raise TypeError("authority")
        return BinanceUsdmKoruDirectionalTargetConsumptionV3(
            authority.strategy_ref, authority.parameter_ref, authority.strategy_id,
            authority.sleeve_id, authority.target_exposure, authority.target_stream,
            authority.target_stream_digest, authority.source_fragment_digest,
            authority.scope_ref,
        )


def _publication_wire(
    *, reader: MarketBundleReader, manifest: MarketBundleManifest, bundle_ref: MarketBundleRef
) -> KoruDirectionalV3PublicationWire:
    events = _read(reader, _HYBRID_AUTHORITY_STREAM)
    if len(events) != 1:
        raise ValueError("hybrid_authority_event_count")
    event = events[0]
    payload = event.payload
    required = {
        "schema_version", "v2_bundle_ref", "v2_bundle_digest", "v2_bundle_manifest",
        "v3_bundle_ref", "v3_bundle_digest", "v3_bundle_manifest",
        "v3_preparation_authority_event", "v3_preparation_authority_digest",
        "target_stream_key", "target_stream_digest",
    }
    if (
        event.stream_key != _HYBRID_AUTHORITY_STREAM
        or event.event_type != _HYBRID_AUTHORITY_EVENT_TYPE
        or event.source_hash != domain.canonical_sha256({"type": _HYBRID_AUTHORITY_EVENT_TYPE, "payload": payload})
        or not isinstance(payload, Mapping)
        or set(payload) != required
        or payload["schema_version"] != 3
    ):
        raise ValueError("hybrid_authority_schema")
    v2_ref = _market_ref(payload["v2_bundle_ref"])
    v3_ref = _market_ref(payload["v3_bundle_ref"])
    v2_manifest = _manifest_wire(payload["v2_bundle_manifest"], ref=v2_ref, schema_version=2, prefix=_V2_BUNDLE_PREFIX)
    v3_manifest = _manifest_wire(payload["v3_bundle_manifest"], ref=v3_ref, schema_version=3, prefix="binance-usdm-koru-directional-execution-development-v3-")
    wire = KoruDirectionalV3PublicationWire(
        v2_ref, _digest(payload["v2_bundle_digest"], "v2_bundle_digest"), v2_manifest,
        v3_ref, _digest(payload["v3_bundle_digest"], "v3_bundle_digest"), v3_manifest,
        payload["v3_preparation_authority_event"],
        _digest(payload["v3_preparation_authority_digest"], "v3_preparation_authority_digest"),
        _text(payload["target_stream_key"], "target_stream_key"),
        _digest(payload["target_stream_digest"], "target_stream_digest"),
    )
    if bundle_ref != MarketBundleRef.from_manifest(manifest):
        raise ValueError("hybrid_bundle_ref")
    actual_streams = {stream.stream_key: stream for stream in manifest.streams}
    for stream in wire.v2_bundle_manifest["streams"]:
        if not isinstance(stream, Mapping):
            raise ValueError("v2_manifest_stream")
        key = _text(stream.get("stream_key"), "v2_stream_key")
        if key.startswith(_V2_TARGET_PREFIX):
            if key in actual_streams:
                raise ValueError("v2_target_retained")
        elif key not in actual_streams or actual_streams[key].to_canonical_dict() != stream:
            raise ValueError("v2_economics_binding")
    return wire


def verify_binance_usdm_koru_directional_strategy_authority_v3(
    *, market_reader: MarketBundleReader
) -> KoruDirectionalV3StrategyAuthority | BinanceUsdmTradifiBarBacktestFailure:
    try:
        manifest = market_reader.manifest
        bundle_ref = market_reader.bundle_ref
        if (
            type(manifest) is not MarketBundleManifest
            or type(bundle_ref) is not MarketBundleRef
            or manifest.schema_version != 3
            or not manifest.bundle_key.startswith(_HYBRID_BUNDLE_PREFIX)
            or MarketBundleRef.from_manifest(manifest) != bundle_ref
        ):
            return _failure("hybrid_bundle_ref")
        wire = _publication_wire(reader=market_reader, manifest=manifest, bundle_ref=bundle_ref)
        events = _read(market_reader, _PREPARATION_STREAM)
        if len(events) != 1:
            return _failure("preparation_event_count")
        event = events[0]
        if (
            event.to_canonical_dict() != wire.v3_preparation_authority_event
            or domain.canonical_sha256(event) != wire.v3_preparation_authority_digest
            or _stream_wire(wire.v3_bundle_manifest, _PREPARATION_STREAM)
            != next(stream.to_canonical_dict() for stream in manifest.streams if stream.stream_key == _PREPARATION_STREAM)
        ):
            return _failure("v3_authority_binding")
        payload = event.payload
        required = {
            "schema_version", "compiler_result_ref", "compiler_result_digest", "scope_ref", "scope_digest", "scope",
            "source_projection_ref", "source_fragment_digest", "source_profile_authority_envelope",
            "source_profile_authority_ref", "recipe", "recipe_ref", "recipe_digest", "strategy_ref",
            "strategy_id", "sleeve_id", "target_stream_key", "target_stream_digest", "target_stream_manifest",
            "target_events", "target_events_digest",
        }
        if (
            event.event_type != _PREPARATION_EVENT_TYPE
            or event.source_hash != domain.canonical_sha256({"type": _PREPARATION_EVENT_TYPE, "payload": payload})
            or not isinstance(payload, Mapping)
            or set(payload) != required
            or payload["schema_version"] != 3
        ):
            return _failure("preparation_payload_schema")
        compiler_ref, scope_ref, source_ref = (_artifact_ref(payload[key]) for key in ("compiler_result_ref", "scope_ref", "source_projection_ref"))
        recipe_ref, strategy_ref, source_authority_ref = (_artifact_ref(payload[key]) for key in ("recipe_ref", "strategy_ref", "source_profile_authority_ref"))
        compiler_digest = _digest(payload["compiler_result_digest"], "compiler_result_digest")
        scope_digest = _digest(payload["scope_digest"], "scope_digest")
        source_fragment = _digest(payload["source_fragment_digest"], "source_fragment_digest")
        fixed_scope_digest = domain.canonical_sha256(_FIXED_SCOPE_WIRE)
        if (
            domain.canonical_bytes(payload["scope"]) != domain.canonical_bytes(_FIXED_SCOPE_WIRE)
            or scope_digest != fixed_scope_digest
            or compiler_ref != domain.ArtifactRef("koru_directional_target_compile_result", 1, compiler_digest)
            or scope_ref != domain.ArtifactRef("koru_directional_discovery_scope", 1, fixed_scope_digest)
            or source_ref != domain.ArtifactRef("binance_usdm_koru_source_projection", 2, source_fragment)
            or recipe_ref.artifact_type != "strategy_parameter_set"
            or recipe_ref.schema_version != 1
            or strategy_ref.artifact_type != "strategy_definition"
            or strategy_ref.schema_version != 1
        ):
            return _failure("compiler_scope_recipe_binding")
        recipe = payload["recipe"]
        if not isinstance(recipe, Mapping) or domain.canonical_sha256(recipe) != _digest(payload["recipe_digest"], "recipe_digest"):
            return _failure("recipe_digest")
        if (
            recipe.get("family") != "mark_index_premium"
            or recipe.get("recipe_id") != _text(recipe.get("recipe_id"), "recipe_id")
            or recipe.get("strategy_ref") != strategy_ref.to_canonical_dict()
            or recipe.get("parameter_ref") != recipe_ref.to_canonical_dict()
            or recipe.get("strategy_id") != _text(payload["strategy_id"], "strategy_id")
            or recipe.get("sleeve_id") != _text(payload["sleeve_id"], "sleeve_id")
            or recipe.get("target_stream_key") != wire.target_stream_key
            or type(recipe.get("target_exposure")) is not str
        ):
            return _failure("recipe_binding")
        source_authority = _envelope(payload["source_profile_authority_envelope"])
        if source_authority_ref != domain.ArtifactRef.from_envelope(source_authority):
            return _failure("source_profile_authority_ref")
        source_payload = source_authority.payload
        if (
            source_authority.artifact_type != "binance_usdm_koru_source_profile_authority"
            or source_authority.schema_version != 2
            or not isinstance(source_payload, Mapping)
            or source_payload.get("source_fragment_digest") != source_fragment
        ):
            return _failure("source_fragment")
        target_events = _read(market_reader, wire.target_stream_key)
        stream_manifest = next(
            (stream for stream in manifest.streams if stream.stream_key == wire.target_stream_key), None
        )
        if (
            stream_manifest is None
            or stream_manifest.event_type != TARGET_STREAM_EVENT_TYPE
            or stream_manifest.capability != TARGET_STREAM_CAPABILITY
            or tuple(value.to_canonical_dict() for value in target_events) != payload["target_events"]
            or domain.canonical_sha256(target_events) != _digest(payload["target_events_digest"], "target_events_digest")
            or stream_manifest.to_canonical_dict() != payload["target_stream_manifest"]
            or _stream_wire(wire.v3_bundle_manifest, wire.target_stream_key) != payload["target_stream_manifest"]
            or stream_manifest.content_hash != domain.canonical_sha256(target_events)
        ):
            return _failure("target_events")
        target = PrecomputedTargetStream(wire.target_stream_key, target_events)
        if target.target_stream_digest != wire.target_stream_digest or target.target_stream_digest != _digest(payload["target_stream_digest"], "target_stream_digest"):
            return _failure("target_stream_digest")
        return KoruDirectionalV3StrategyAuthority(
            bundle_ref, bundle_ref.manifest_hash, wire.v2_bundle_ref, wire.v2_bundle_digest,
            wire.v3_bundle_ref, wire.v3_bundle_digest, compiler_ref,
            _text(recipe["recipe_id"], "recipe_id"), strategy_ref, recipe_ref,
            _text(payload["strategy_id"], "strategy_id"), _text(payload["sleeve_id"], "sleeve_id"),
            wire.target_stream_key, target.target_stream_digest,
            _text(recipe["target_exposure"], "target_exposure"), scope_ref, source_fragment,
            source_authority, source_authority_ref, target,
        )
    except (AttributeError, KeyError, StopIteration, TypeError, ValueError):
        return _failure("unexpected_input")


__all__ = [
    "BinanceUsdmKoruDirectionalPlannerV3",
    "BinanceUsdmKoruDirectionalTargetConsumptionV3",
    "KoruDirectionalV3PublicationWire",
    "KoruDirectionalV3StrategyAuthority",
    "verify_binance_usdm_koru_directional_strategy_authority_v3",
]
