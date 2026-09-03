"""Sealed V3 KORU target authority reconstructed from a target overlay."""

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

_SCHEMA_VERSION = 3
_AUTHORITY_STREAM = "binance_usdm.tradifi.target_overlay_authority.koruusdt.v3"
_AUTHORITY_EVENT = "koru_tradifi_target_overlay_authority_v3"
_OVERLAY_PREFIX = "koru-tradifi-target-overlay-development-v3-"
_ECONOMICS_PREFIX = "koru-tradifi-economics-development-v3-"
_V2_TARGET_PREFIX = "binance_usdm.tradifi.target.koruusdt.closed_market_range."
_FORBIDDEN_STREAMS = frozenset({
    "binance_usdm.tradifi.preparation_authority.v2",
    "binance_usdm.tradifi.directional_hybrid_authority.koruusdt.v3",
})
_FIXED_SCOPE_WIRE = {
    "type": "koru_directional_discovery_scope_v1",
    "schema_version": 1,
    "discovery_start": {"type": "utc_instant", "epoch_nanoseconds": 1_784_109_600_000_000_000},
    "discovery_end_exclusive": {"type": "utc_instant", "epoch_nanoseconds": 1_787_569_200_000_000_000},
    "holdout_start": {"type": "utc_instant", "epoch_nanoseconds": 1_787_569_200_000_000_000},
}


def _failure(subject: str) -> BinanceUsdmTradifiBarBacktestFailure:
    return BinanceUsdmTradifiBarBacktestFailure(BinanceUsdmTradifiBarBacktestFailureCode.PREPARATION_AUTHORITY_INVALID, subject)


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
    if not isinstance(value, Mapping) or set(value) != {"type", "artifact_type", "schema_version", "content_hash"} or value.get("type") != "artifact_ref":
        raise ValueError("artifact_ref")
    return domain.ArtifactRef(_text(value["artifact_type"], "artifact_type"), value["schema_version"], _digest(value["content_hash"], "content_hash"))


def _market_ref(value: object) -> MarketBundleRef:
    if not isinstance(value, Mapping) or set(value) != {"type", "bundle_key", "manifest_hash"} or value.get("type") != "market_bundle_ref":
        raise ValueError("market_bundle_ref")
    return MarketBundleRef(_text(value["bundle_key"], "bundle_key"), _digest(value["manifest_hash"], "manifest_hash"))


def _envelope(value: object) -> domain.ArtifactEnvelope:
    if not isinstance(value, Mapping) or set(value) != {"artifact_type", "schema_version", "payload", "content_hash"}:
        raise ValueError("artifact_envelope")
    envelope = domain.ArtifactEnvelope.create(value["artifact_type"], value["schema_version"], value["payload"])
    if envelope.to_canonical_dict() != value:
        raise ValueError("artifact_envelope")
    return envelope


@dataclass(frozen=True, slots=True)
class KoruDirectionalV3StrategyAuthority:
    """The sole V3 strategy identity admitted from a target overlay."""

    bundle_ref: MarketBundleRef
    bundle_digest: str
    economics_bundle_ref: MarketBundleRef
    economics_bundle_digest: str
    economics_authority_digest: str
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
        refs = (self.compiler_result_ref, self.strategy_ref, self.parameter_ref, self.scope_ref, self.source_profile_authority_ref)
        if type(self.bundle_ref) is not MarketBundleRef or type(self.economics_bundle_ref) is not MarketBundleRef or any(type(value) is not domain.ArtifactRef for value in refs):
            raise TypeError("authority_refs")
        if (
            self.bundle_digest != self.bundle_ref.manifest_hash
            or self.economics_bundle_digest != self.economics_bundle_ref.manifest_hash
            or (self.compiler_result_ref.artifact_type, self.compiler_result_ref.schema_version) != ("koru_directional_target_compile_result", 1)
            or (self.strategy_ref.artifact_type, self.strategy_ref.schema_version) != ("strategy_definition", 1)
            or (self.parameter_ref.artifact_type, self.parameter_ref.schema_version) != ("strategy_parameter_set", 1)
            or (self.scope_ref.artifact_type, self.scope_ref.schema_version) != ("koru_directional_discovery_scope", 1)
            or (self.source_profile_authority_ref.artifact_type, self.source_profile_authority_ref.schema_version) != ("binance_usdm_koru_source_profile_authority", 2)
        ):
            raise ValueError("authority_refs")
        for name in ("selected_recipe_id", "strategy_id", "sleeve_id", "target_stream_key", "target_exposure"):
            _text(getattr(self, name), name)
        _digest(self.economics_authority_digest, "economics_authority_digest")
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
                or "fills" in candidate or "pnl" in candidate
                or not isinstance(targets, tuple) or len(targets) != 1 or not isinstance(targets[0], Mapping)
                or targets[0].get("value") not in {"0", self.target_exposure, "-" + self.target_exposure}
            ):
                raise ValueError("target_event")


class BinanceUsdmKoruDirectionalPlannerV3:
    @staticmethod
    def target(authority: KoruDirectionalV3StrategyAuthority) -> BinanceUsdmKoruDirectionalTargetConsumptionV3:
        if type(authority) is not KoruDirectionalV3StrategyAuthority:
            raise TypeError("authority")
        return BinanceUsdmKoruDirectionalTargetConsumptionV3(
            authority.strategy_ref, authority.parameter_ref, authority.strategy_id, authority.sleeve_id,
            authority.target_exposure, authority.target_stream, authority.target_stream_digest,
            authority.source_fragment_digest, authority.scope_ref,
        )


def _overlay_payload(reader: MarketBundleReader, manifest: MarketBundleManifest, bundle_ref: MarketBundleRef) -> Mapping[str, object]:
    events = _read(reader, _AUTHORITY_STREAM)
    required = {
        "schema_version", "economics_bundle_ref", "economics_bundle_digest", "economics_authority_digest",
        "economics_bundle_manifest", "economics_stream_manifests", "coverage_start", "coverage_end_exclusive",
        "instrument_catalog_hash", "source_fragment_digest", "source_profile_authority_envelope",
        "source_profile_authority_ref", "compiler_result_ref", "compiler_result_digest", "scope_ref", "scope_digest",
        "scope", "source_projection_ref", "recipe", "recipe_ref", "recipe_digest", "strategy_ref", "strategy_id",
        "sleeve_id", "target_stream_key", "target_stream_digest", "target_stream_manifest", "target_events", "target_events_digest",
    }
    if len(events) != 1:
        raise ValueError("overlay_authority_count")
    event = events[0]
    payload = event.payload
    if (
        event.event_type != _AUTHORITY_EVENT
        or event.stream_key != _AUTHORITY_STREAM
        or event.event_id != _AUTHORITY_EVENT + ":" + event.source_hash
        or event.source_hash != domain.canonical_sha256({"type": _AUTHORITY_EVENT, "payload": payload})
        or not isinstance(payload, Mapping) or set(payload) != required or payload.get("schema_version") != _SCHEMA_VERSION
    ):
        raise ValueError("overlay_authority_schema")
    economics_ref = _market_ref(payload["economics_bundle_ref"])
    economics_manifest = payload["economics_bundle_manifest"]
    if (
        not isinstance(economics_manifest, Mapping)
        or economics_manifest.get("type") != "market_bundle_manifest"
        or economics_manifest.get("schema_version") != _SCHEMA_VERSION
        or economics_manifest.get("bundle_key") != economics_ref.bundle_key
        or not economics_ref.bundle_key.startswith(_ECONOMICS_PREFIX)
        or domain.canonical_sha256(economics_manifest) != economics_ref.manifest_hash
        or payload["economics_bundle_digest"] != economics_ref.manifest_hash
        or payload["coverage_start"] != manifest.coverage_start.to_canonical_dict()
        or payload["coverage_end_exclusive"] != manifest.coverage_end_exclusive.to_canonical_dict()
        or payload["instrument_catalog_hash"] != manifest.instrument_catalog_hash
        or economics_manifest.get("coverage_start") != payload["coverage_start"]
        or economics_manifest.get("coverage_end_exclusive") != payload["coverage_end_exclusive"]
        or economics_manifest.get("instrument_catalog_hash") != payload["instrument_catalog_hash"]
    ):
        raise ValueError("economics_bundle_binding")
    actual = {stream.stream_key: stream.to_canonical_dict() for stream in manifest.streams}
    economics_streams = payload["economics_stream_manifests"]
    if not isinstance(economics_streams, tuple) or not economics_streams:
        raise ValueError("economics_streams")
    if economics_manifest.get("streams") != economics_streams:
        raise ValueError("economics_manifest_streams")
    for stream in economics_streams:
        if not isinstance(stream, Mapping) or stream.get("stream_key") not in actual or actual[stream["stream_key"]] != stream:
            raise ValueError("economics_stream_binding")
    if {stream["stream_key"] for stream in economics_streams} | {_AUTHORITY_STREAM, payload["target_stream_key"]} != set(actual):
        raise ValueError("overlay_stream_cover")
    if any(key.startswith(_V2_TARGET_PREFIX) or key in _FORBIDDEN_STREAMS for key in actual):
        raise ValueError("legacy_stream")
    if bundle_ref != MarketBundleRef.from_manifest(manifest):
        raise ValueError("overlay_bundle_ref")
    return payload


def verify_binance_usdm_koru_directional_strategy_authority_v3(
    *, market_reader: MarketBundleReader
) -> KoruDirectionalV3StrategyAuthority | BinanceUsdmTradifiBarBacktestFailure:
    try:
        manifest, bundle_ref = market_reader.manifest, market_reader.bundle_ref
        if (
            type(manifest) is not MarketBundleManifest or type(bundle_ref) is not MarketBundleRef
            or manifest.schema_version != _SCHEMA_VERSION or not manifest.bundle_key.startswith(_OVERLAY_PREFIX)
            or MarketBundleRef.from_manifest(manifest) != bundle_ref
        ):
            return _failure("overlay_bundle_ref")
        payload = _overlay_payload(market_reader, manifest, bundle_ref)
        compiler_ref, scope_ref, source_ref = (_artifact_ref(payload[key]) for key in ("compiler_result_ref", "scope_ref", "source_projection_ref"))
        recipe_ref, strategy_ref, source_authority_ref = (_artifact_ref(payload[key]) for key in ("recipe_ref", "strategy_ref", "source_profile_authority_ref"))
        compiler_digest = _digest(payload["compiler_result_digest"], "compiler_result_digest")
        scope_digest = _digest(payload["scope_digest"], "scope_digest")
        source_fragment = _digest(payload["source_fragment_digest"], "source_fragment_digest")
        economics_ref = _market_ref(payload["economics_bundle_ref"])
        if (
            domain.canonical_bytes(payload["scope"]) != domain.canonical_bytes(_FIXED_SCOPE_WIRE)
            or scope_digest != domain.canonical_sha256(_FIXED_SCOPE_WIRE)
            or compiler_ref != domain.ArtifactRef("koru_directional_target_compile_result", 1, compiler_digest)
            or scope_ref != domain.ArtifactRef("koru_directional_discovery_scope", 1, scope_digest)
            or source_ref != domain.ArtifactRef("binance_usdm_koru_source_projection", 2, source_fragment)
            or recipe_ref.artifact_type != "strategy_parameter_set" or recipe_ref.schema_version != 1
            or strategy_ref.artifact_type != "strategy_definition" or strategy_ref.schema_version != 1
        ):
            return _failure("compiler_scope_recipe_binding")
        recipe = payload["recipe"]
        if (
            not isinstance(recipe, Mapping) or domain.canonical_sha256(recipe) != _digest(payload["recipe_digest"], "recipe_digest")
            or recipe.get("family") != "mark_index_premium" or recipe.get("recipe_id") != _text(recipe.get("recipe_id"), "recipe_id")
            or recipe.get("strategy_ref") != strategy_ref.to_canonical_dict() or recipe.get("parameter_ref") != recipe_ref.to_canonical_dict()
            or recipe.get("strategy_id") != _text(payload["strategy_id"], "strategy_id")
            or recipe.get("sleeve_id") != _text(payload["sleeve_id"], "sleeve_id")
            or recipe.get("target_stream_key") != _text(payload["target_stream_key"], "target_stream_key")
            or type(recipe.get("target_exposure")) is not str
        ):
            return _failure("recipe_binding")
        source_authority = _envelope(payload["source_profile_authority_envelope"])
        source_payload = source_authority.payload
        if (
            source_authority_ref != domain.ArtifactRef.from_envelope(source_authority)
            or source_authority.artifact_type != "binance_usdm_koru_source_profile_authority" or source_authority.schema_version != 2
            or not isinstance(source_payload, Mapping) or source_payload.get("source_fragment_digest") != source_fragment
        ):
            return _failure("source_binding")
        target_key = _text(payload["target_stream_key"], "target_stream_key")
        target_events = _read(market_reader, target_key)
        stream_manifest = next((stream for stream in manifest.streams if stream.stream_key == target_key), None)
        if (
            stream_manifest is None or stream_manifest.event_type != TARGET_STREAM_EVENT_TYPE or stream_manifest.capability != TARGET_STREAM_CAPABILITY
            or tuple(event.to_canonical_dict() for event in target_events) != payload["target_events"]
            or domain.canonical_sha256(target_events) != _digest(payload["target_events_digest"], "target_events_digest")
            or stream_manifest.to_canonical_dict() != payload["target_stream_manifest"]
            or stream_manifest.content_hash != domain.canonical_sha256(target_events)
        ):
            return _failure("target_events")
        target = PrecomputedTargetStream(target_key, target_events)
        digest = _digest(payload["target_stream_digest"], "target_stream_digest")
        if target.target_stream_digest != digest:
            return _failure("target_stream_digest")
        return KoruDirectionalV3StrategyAuthority(
            bundle_ref, bundle_ref.manifest_hash, economics_ref, _digest(payload["economics_bundle_digest"], "economics_bundle_digest"),
            _digest(payload["economics_authority_digest"], "economics_authority_digest"), compiler_ref,
            _text(recipe["recipe_id"], "recipe_id"), strategy_ref, recipe_ref, _text(payload["strategy_id"], "strategy_id"),
            _text(payload["sleeve_id"], "sleeve_id"), target_key, digest, _text(recipe["target_exposure"], "target_exposure"),
            scope_ref, source_fragment, source_authority, source_authority_ref, target,
        )
    except (AttributeError, KeyError, StopIteration, TypeError, ValueError):
        return _failure("unexpected_input")


__all__ = [
    "BinanceUsdmKoruDirectionalPlannerV3",
    "BinanceUsdmKoruDirectionalTargetConsumptionV3",
    "KoruDirectionalV3StrategyAuthority",
    "verify_binance_usdm_koru_directional_strategy_authority_v3",
]
