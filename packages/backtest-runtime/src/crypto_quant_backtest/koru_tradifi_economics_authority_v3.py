"""Target-free V3 economics admission for the KORU TradFi directional runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import crypto_quant_domain as domain
from crypto_quant_market_data import (
    LocalMarketBundleReader,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .binance_usdm_koru_tradifi_development_profile_v1 import (
    BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
    build_binance_usdm_koru_tradifi_development_profile_v1,
)
from .binance_usdm_tradifi_preparation import BinanceUsdmTradifiProviderInputs
from .binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
    BinanceUsdmTradifiBarBacktestFailureCode,
)
from .profile_build_manifest import _provider_build_manifest
from .timeline import TimelineWindow

_SCHEMA_VERSION = 3
_ECONOMICS_STREAM = "binance_usdm.tradifi.economics_authority.koruusdt.v3"
_PRICE_STREAM = "binance_usdm.tradifi.price_purpose.authority.koruusdt.v3"
_ACCOUNT_STREAM = "binance_usdm.tradifi.account.authority.koruusdt.v3"
_ECONOMICS_EVENT = "koru_tradifi_economics_authority_v3"
_PRICE_EVENT = "binance_usdm_tradifi_price_purpose_binding_v3"
_ACCOUNT_EVENT = "account_financial_event"
_ECONOMICS_PREFIX = "koru-tradifi-economics-development-v3-"
_FORBIDDEN_ECONOMICS_STREAMS = frozenset({
    "binance_usdm.tradifi.preparation_authority.v2",
    "binance_usdm.tradifi.directional_hybrid_authority.koruusdt.v3",
})


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


def _ref(value: object) -> domain.ArtifactRef:
    if not isinstance(value, Mapping) or set(value) != {"type", "artifact_type", "schema_version", "content_hash"} or value.get("type") != "artifact_ref":
        raise ValueError("artifact_ref")
    return domain.ArtifactRef(value["artifact_type"], value["schema_version"], value["content_hash"])


def _verified_artifact(reader: ArtifactEnvelopeReader, ref: domain.ArtifactRef) -> domain.ArtifactEnvelope:
    result = reader.read(ref=ref)
    if (
        type(result) is not domain.ArtifactReadResult or result.envelope is None
        or result.source_bytes != domain.canonical_bytes(result.envelope)
        or result.source_hash != domain.canonical_sha256(result.envelope)
        or domain.ArtifactRef.from_envelope(result.envelope) != ref
    ):
        raise ValueError("artifact")
    return result.envelope


def _binding(event: MarketEvent) -> dict[str, object]:
    return {"stream_key": event.stream_key, "event_type": event.event_type, "event_id": event.event_id, "event_hash": event.event_hash}


@dataclass(frozen=True, slots=True)
class KoruTradifiEconomicsAuthorityV3:
    """Verified V3 market, funding, fee, and margin inputs with no target."""

    bundle_ref: MarketBundleRef
    authority_digest: str
    source_profile_authority_ref: domain.ArtifactRef
    source_fragment_digest: str
    resolved_profile: object
    financial_dispatcher_spec: object
    build_artifact_manifest: object
    market_manifest: MarketBundleManifest
    market_reader: LocalMarketBundleReader

    def __post_init__(self) -> None:
        if (
            type(self.bundle_ref) is not MarketBundleRef
            or type(self.source_profile_authority_ref) is not domain.ArtifactRef
            or type(self.market_manifest) is not MarketBundleManifest
            or type(self.market_reader) is not LocalMarketBundleReader
            or self.market_reader.bundle_ref != self.bundle_ref
            or self.market_reader.manifest != self.market_manifest
            or type(self.source_fragment_digest) is not str
            or type(self.authority_digest) is not str
        ):
            raise ValueError("economics_authority")


def _economics_payload(reader: LocalMarketBundleReader) -> tuple[Mapping[str, object], tuple[MarketEvent, ...], tuple[MarketEvent, ...]]:
    manifest = reader.manifest
    events_by_key = {stream.stream_key: _read(reader, stream.stream_key) for stream in manifest.streams}
    for stream in manifest.streams:
        if MarketStreamManifest.from_events(stream.stream_key, events_by_key[stream.stream_key]) != stream:
            raise ValueError("stream_manifest")
    events = events_by_key.get(_ECONOMICS_STREAM, ())
    if len(events) != 1 or not isinstance(events[0].payload, Mapping):
        raise ValueError("economics_event")
    event = events[0]
    payload = event.payload
    required = {
        "schema_version", "source_projection_content_identity", "source_fragment_digest", "full_scope", "terms", "artifact_refs",
        "stream_manifests", "price_purpose_authority_binding", "account_authority_binding", "development_only", "deployment_authorized", "authority_digest",
    }
    if (
        set(payload) != required or payload.get("schema_version") != _SCHEMA_VERSION
        or event.event_type != _ECONOMICS_EVENT
        or event.source_hash != domain.canonical_sha256({"type": _ECONOMICS_EVENT, "stream_key": _ECONOMICS_STREAM, "payload": payload})
        or payload.get("authority_digest") != domain.canonical_sha256({key: value for key, value in payload.items() if key != "authority_digest"})
        or payload.get("development_only") is not True or payload.get("deployment_authorized") is not False
    ):
        raise ValueError("economics_wire")
    if any(stream.stream_key in _FORBIDDEN_ECONOMICS_STREAMS or ".target." in stream.stream_key for stream in manifest.streams if stream.stream_key != "binance_usdm.tradifi.target_overlay_authority.koruusdt.v3"):
        raise ValueError("legacy_economics_stream")
    return payload, events_by_key.get(_PRICE_STREAM, ()), events_by_key.get(_ACCOUNT_STREAM, ())


def resolve_koru_tradifi_economics_authority_v3(
    *, market_reader: MarketBundleReader, artifact_reader: ArtifactEnvelopeReader,
    provider_inputs: BinanceUsdmTradifiProviderInputs, experiment_id: str,
) -> KoruTradifiEconomicsAuthorityV3 | BinanceUsdmTradifiBarBacktestFailure:
    """Validate only V3 economics bytes and build their profile; targets are ignored."""
    try:
        reader = LocalMarketBundleReader.validate_repository_open_reader_v1(market_reader)
    except (AttributeError, TypeError, ValueError):
        return _failure("local_reader")
    try:
        if (
            type(provider_inputs) is not BinanceUsdmTradifiProviderInputs
            or type(experiment_id) is not str or not experiment_id
            or reader.manifest.schema_version != _SCHEMA_VERSION
            or MarketBundleRef.from_manifest(reader.manifest) != reader.bundle_ref
        ):
            raise ValueError("input")
        payload, price_events, account_events = _economics_payload(reader)
        terms = payload["terms"]
        source_identity = payload["source_projection_content_identity"]
        if (
            not isinstance(terms, Mapping) or not isinstance(source_identity, Mapping)
            or source_identity.get("source_fragment_digest") != payload["source_fragment_digest"]
            or not isinstance(payload["artifact_refs"], tuple) or len(payload["artifact_refs"]) != 4
            or not isinstance(payload["stream_manifests"], tuple)
        ):
            raise ValueError("economics_terms")
        refs = tuple(_ref(value) for value in payload["artifact_refs"])
        artifacts = tuple(_verified_artifact(artifact_reader, ref) for ref in refs)
        source_profile = artifacts[0]
        if (
            source_profile.artifact_type != "binance_usdm_koru_source_profile_authority" or source_profile.schema_version != 2
            or not isinstance(source_profile.payload, Mapping)
            or source_profile.payload.get("source_fragment_digest") != payload["source_fragment_digest"]
            or tuple(terms.get(key) for key in ("xkrx_calendar_ref", "arcx_calendar_ref", "post_adjustment_unit_regime_ref"))
            != tuple(ref.to_canonical_dict() for ref in refs[1:])
        ):
            raise ValueError("artifact_bindings")
        actual = {stream.stream_key: stream.to_canonical_dict() for stream in reader.manifest.streams}
        source_manifests = payload["stream_manifests"]
        source_keys = tuple(
            stream.get("stream_key") if isinstance(stream, Mapping) else None
            for stream in source_manifests
        )
        expected = set(source_keys) | {_ECONOMICS_STREAM, _PRICE_STREAM, _ACCOUNT_STREAM}
        extras = set(actual) - expected
        if (
            None in expected or len(source_keys) != len(set(source_keys)) or not expected <= set(actual)
            or (extras and (len(extras) != 2 or "binance_usdm.tradifi.target_overlay_authority.koruusdt.v3" not in extras))
        ):
            raise ValueError("economics_cover")
        for stream in source_manifests:
            if not isinstance(stream, Mapping) or actual.get(stream.get("stream_key")) != stream:
                raise ValueError("source_manifest")
        if len(price_events) != 1 or len(account_events) != 1:
            raise ValueError("authority_event")
        price, account = price_events[0], account_events[0]
        expected_prices = tuple(
            {
                "price_purpose": binding["price_purpose"],
                "source_stream_manifest": binding["stream_manifest"],
                "event_bindings": binding["event_bindings"],
            }
            for binding in terms.get("price_purpose_authority", ())
        )
        if (
            price.event_type != _PRICE_EVENT or account.event_type != _ACCOUNT_EVENT
            or price.event_id != _PRICE_EVENT + ":" + price.source_hash
            or account.event_id != _ACCOUNT_EVENT + ":" + account.source_hash
            or payload["price_purpose_authority_binding"] != _binding(price)
            or payload["account_authority_binding"] != _binding(account)
            or price.payload.get("source_projection_content_identity") != source_identity
            or price.payload.get("price_purpose_bindings") != expected_prices
            or account.payload.get("account_id") != "account-1"
            or account.payload.get("initial_equity") != provider_inputs.initial_equity.to_canonical_dict()
            or account.payload.get("allocation_fraction") != provider_inputs.sleeve_allocation_fraction
            or account.payload.get("position_notional_usdt") != "1000"
        ):
            raise ValueError("authority_events")
        source_bindings = terms.get("source_event_bindings")
        if not isinstance(source_bindings, tuple):
            raise TypeError("source_bindings")
        source_keys = {stream["stream_key"] for stream in source_manifests}
        source_events = tuple(
            event for key in sorted(source_keys) if key != "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v2"
            for event in _read(reader, key)
        )
        if tuple(_binding(event) for event in source_events) != source_bindings:
            raise ValueError("source_events")
        profile_request = BinanceUsdmKoruTradifiDevelopmentProfileRequestV1(
            TimelineWindow(reader.manifest.coverage_start, reader.manifest.coverage_start, reader.manifest.coverage_end_exclusive),
            domain.SimulationInstant(
                domain.UtcInstant(max(
                    event.available_time.epoch_nanoseconds
                    if not isinstance(event.payload, Mapping)
                    else event.payload.get("acquired_at_epoch_nanoseconds", event.available_time.epoch_nanoseconds)
                    for event in source_events
                )),
                domain.TimelinePhase(200, "profile_composition"), domain.SourceSequence(0),
            ),
            "account-1", refs[1], refs[2], refs[3], source_profile, refs[0], source_events,
        )
        built = build_binance_usdm_koru_tradifi_development_profile_v1(profile_request)
        if built.result is None:
            raise ValueError("profile")
        result = built.result
        return KoruTradifiEconomicsAuthorityV3(
            reader.bundle_ref, payload["authority_digest"], refs[0], payload["source_fragment_digest"],
            result.resolved_profile, result.financial_dispatcher_spec,
            _provider_build_manifest(provider_inputs.build_artifact_manifest, result.profile_registry),
            reader.manifest, reader,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure("economics_v3")


__all__ = ["KoruTradifiEconomicsAuthorityV3", "resolve_koru_tradifi_economics_authority_v3"]
