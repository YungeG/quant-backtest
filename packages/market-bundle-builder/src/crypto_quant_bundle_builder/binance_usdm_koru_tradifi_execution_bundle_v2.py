"""Final immutable in-memory streaming KORU TradFi execution bundle assembly."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    Money,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .binance_usdm_koru_closed_market_range_targets_v1 import (
    BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1,
    BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1,
)
from .binance_usdm_koru_closed_market_range_targets_v2 import (
    BinanceUsdmKoruClosedMarketRangeTargetsResultV2,
)
from .binance_usdm_koru_closed_market_range_targets_v2 import (
    _trusted_result as _trusted_target_result,
)
from .binance_usdm_koru_tradifi_execution_bundle_v1 import (
    _BOUND_PRICE_PURPOSES,
    _INSTRUMENT,
    _INSTRUMENT_WIRE,
    _PRICE_PURPOSE_SOURCE_STREAMS,
    _REQUIRED_ALLOCATION,
    _REQUIRED_EQUITY,
    _REQUIRED_POSITION_NOTIONAL,
    _canonical_equal,
    _canonical_hash,
    _canonical_text,
    _freeze_json,
    _parameter_target_bindings,
    _validate_profile_wire,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruTradifiSourceProjectionResultV2,
    build_binance_usdm_koru_source_profile_authority_v2,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    _trusted_result as _trusted_source_result,
)

_SCHEMA_VERSION = 2
_PREPARATION_STREAM = "binance_usdm.tradifi.preparation_authority.v2"
_PREPARATION_EVENT_TYPE = "binance_usdm_tradifi_preparation_authority_v2"
_PREPARATION_CAPABILITY = MarketBundleCapability(
    "binance_usdm.tradifi.preparation-authority", 1
)
_ACCOUNT_STREAM = "binance_usdm.tradifi.account.authority.koruusdt.v2"
_ACCOUNT_EVENT_TYPE = "account_financial_event"
_ACCOUNT_CAPABILITY = MarketBundleCapability("account.financial-event", 1)
_PRICE_PURPOSE_STREAM = "binance_usdm.tradifi.price_purpose.authority.koruusdt.v2"
_PRICE_PURPOSE_EVENT_TYPE = "binance_usdm_tradifi_price_purpose_binding_v2"
_PRICE_PURPOSE_CAPABILITY = MarketBundleCapability(
    "binance_usdm.price-purpose-streams", 1
)
_FUNDING_STREAM = "binance_usdm.funding_history.publications.koruusdt.v1"
def _canonical_wire(value: object) -> object:
    return json.loads(canonical_bytes(value))


_LIMITATIONS = (
    "selected_source_events_form_the_executable_stream",
    "full_raw_data_is_retained_transitively_in_source_snapshots",
    "v2_projection_target_and_authority_identities",
    "development_only",
)


def _source_snapshot_bindings(
    source: BinanceUsdmKoruTradifiSourceProjectionResultV2,
) -> tuple[dict[str, object], ...]:
    bindings: list[dict[str, object]] = []
    boundary = source.request.aggregate_trade_boundary_index_result
    for capture in boundary.request.captures:
        bindings.append(
            {
                "source_kind": "aggregate_trades",
                "source_snapshot_id": capture.snapshot.snapshot_id,
                "source_snapshot_hash": canonical_sha256(
                    capture.snapshot.to_canonical_dict()
                ),
                "source_evidence_hash": capture.capture_hash,
            }
        )
    for source_kind, results in (
        ("mark_price", source.request.mark_price_results),
        ("index_price", source.request.index_price_results),
        ("funding_history", (source.request.funding_result,)),
    ):
        for result in results:
            bindings.append(
                {
                    "source_kind": source_kind,
                    "source_snapshot_id": result.source_snapshot_id,
                    "source_snapshot_hash": result.source_snapshot_hash,
                    "source_evidence_hash": result.normalization_hash,
                }
            )
    authority = source.request.authority_result
    snapshot = authority.source_snapshot
    bindings.append(
        {
            "source_kind": "calendar_unit",
            "source_snapshot_id": snapshot.snapshot_id,
            "source_snapshot_hash": canonical_sha256(snapshot.to_canonical_dict()),
            "source_evidence_hash": canonical_sha256(authority),
        }
    )
    return tuple(
        sorted(
            bindings,
            key=lambda value: (
                _canonical_text("source_kind", value["source_kind"]),
                _canonical_text("source_snapshot_id", value["source_snapshot_id"]),
                _canonical_text("source_evidence_hash", value["source_evidence_hash"]),
            ),
        )
    )


def _streaming_authority_bindings(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV2,
) -> dict[str, object]:
    source = request.source_projection
    target = request.target_result
    return {
        "source_fragment_digest": source.fragment_digest,
        "target_result_digest": target.result_digest,
        "aggregate_trade_boundary_index_request_hash": (
            source.aggregate_trade_boundary_index_request_hash
        ),
        "aggregate_trade_boundary_index_result_digest": (
            source.aggregate_trade_boundary_index_result_digest
        ),
        "aggregate_trade_streamed_reconstruction_digest": (
            source.aggregate_trade_streamed_reconstruction_digest
        ),
        "aggregate_trade_intra_day_raw_id_gap_stream": (
            source.aggregate_trade_intra_day_raw_id_gap_stream.to_canonical_dict()
        ),
        "aggregate_trade_cross_date_raw_id_gap_stream": (
            source.aggregate_trade_cross_date_raw_id_gap_stream.to_canonical_dict()
        ),
        "aggregate_trade_coverage_gaps": tuple(
            _canonical_wire(value) for value in source.aggregate_trade_coverage_gaps
        ),
        "missing_boundaries": tuple(
            _canonical_wire(value) for value in source.missing_boundaries
        ),
        "source_profile_authority_ref": (
            request.source_profile_authority_ref.to_canonical_dict()
        ),
        "source_profile_authority_hash": (
            request.source_profile_authority_envelope.content_hash
        ),
        "profile_composition_request_hash": request.profile_composition_request_hash,
    }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleRequestV2:
    source_projection: BinanceUsdmKoruTradifiSourceProjectionResultV2
    target_result: BinanceUsdmKoruClosedMarketRangeTargetsResultV2
    source_profile_authority_envelope: ArtifactEnvelope
    source_profile_authority_ref: ArtifactRef
    profile_composition_request_wire: Mapping[str, object]
    profile_composition_request_hash: str
    execution_account_id: str
    initial_equity: Money
    sleeve_allocation_fraction: str
    _price_purpose_bindings: tuple[Mapping[str, object], ...] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        source = _trusted_source_result(self.source_projection)
        target = _trusted_target_result(self.target_result)
        if source is None:
            raise ValueError("source_projection must be an exact accepted V2 result")
        if target is None:
            raise ValueError("target_result must be an exact accepted V2 result")
        if not _canonical_equal(target.request.source_projection, source):
            raise ValueError(
                "target result must be generated from the accepted V2 source fragment"
            )
        derived_envelope, derived_ref = (
            build_binance_usdm_koru_source_profile_authority_v2(source)
        )
        if (
            type(self.source_profile_authority_envelope) is not ArtifactEnvelope
            or not _canonical_equal(
                self.source_profile_authority_envelope, derived_envelope
            )
            or type(self.source_profile_authority_ref) is not ArtifactRef
            or self.source_profile_authority_ref != derived_ref
        ):
            raise ValueError(
                "source profile authority must be exactly derived from source projection"
            )
        request_hash = _canonical_hash(
            "profile_composition_request_hash", self.profile_composition_request_hash
        )
        account_id = _canonical_text("execution_account_id", self.execution_account_id)
        if type(self.initial_equity) is not Money or self.initial_equity != _REQUIRED_EQUITY:
            raise ValueError("initial_equity must be exact 10000 USDT at scale 8")
        if self.sleeve_allocation_fraction != _REQUIRED_ALLOCATION:
            raise ValueError("sleeve_allocation_fraction must be exact full allocation 1")
        frozen_wire = _freeze_json(self.profile_composition_request_wire)
        profile, price_bindings = _validate_profile_wire(
            frozen_wire,
            request_hash,
            source,
            account_id,
            execution_source_manifest=next(
                value
                for value in source.stream_manifests
                if value.stream_key
                == "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1"
            ),
        )
        if profile.get("raw_exact_valuation") is not True:
            raise ValueError("V2 KORU profile must bind raw exact valuation")
        if profile.get("raw_exact_margin") is not True:
            raise ValueError("V2 KORU profile must bind raw exact margin")
        object.__setattr__(self, "source_projection", source)
        object.__setattr__(self, "target_result", target)
        object.__setattr__(
            self, "source_profile_authority_envelope", derived_envelope
        )
        object.__setattr__(self, "source_profile_authority_ref", derived_ref)
        object.__setattr__(self, "profile_composition_request_wire", profile)
        object.__setattr__(self, "_price_purpose_bindings", price_bindings)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    @property
    def bundle_key(self) -> str:
        digest = canonical_sha256(
            {
                "type": "binance_usdm_koru_tradifi_execution_bundle_key_v2",
                "source_fragment_digest": self.source_projection.fragment_digest,
                "target_result_digest": self.target_result.result_digest,
                "aggregate_trade_boundary_index_result_digest": (
                    self.source_projection.aggregate_trade_boundary_index_result_digest
                ),
                "source_profile_authority_ref": self.source_profile_authority_ref,
                "profile_composition_request_hash": self.profile_composition_request_hash,
                "execution_account_id": self.execution_account_id,
                "initial_equity": self.initial_equity,
                "sleeve_allocation_fraction": self.sleeve_allocation_fraction,
            }
        )
        return "binance-usdm-koru-tradifi-execution-development-v2-" + digest[7:]

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_execution_bundle_request_v2",
            "schema_version": _SCHEMA_VERSION,
            "source_projection": self.source_projection,
            "source_fragment_digest": self.source_projection.fragment_digest,
            "target_result": self.target_result,
            "target_result_digest": self.target_result.result_digest,
            "source_profile_authority_envelope": self.source_profile_authority_envelope,
            "source_profile_authority_ref": self.source_profile_authority_ref,
            "profile_composition_request_wire": self.profile_composition_request_wire,
            "profile_composition_request_hash": self.profile_composition_request_hash,
            "execution_account_id": self.execution_account_id,
            "initial_equity": self.initial_equity,
            "sleeve_allocation_fraction": self.sleeve_allocation_fraction,
            "bundle_key": self.bundle_key,
            "bundle_schema_version": _SCHEMA_VERSION,
            "limitations": _LIMITATIONS,
            "development_only": True,
        }


class BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_FRAGMENT_INVALID = "source_fragment_invalid"
    TARGET_RESULT_INVALID = "target_result_invalid"
    PROFILE_REQUEST_INVALID = "profile_request_invalid"
    AUTHORITY_ASSEMBLY_INVALID = "authority_assembly_invalid"
    STREAM_ASSEMBLY_INVALID = "stream_assembly_invalid"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleFailureV2:
    code: BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2:
            raise TypeError("code must be exact V2 execution-bundle failure code")
        _canonical_text("subject", self.subject)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_execution_bundle_failure_v2",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


def _price_purpose_payload(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV2,
) -> dict[str, object]:
    manifests = {
        manifest.stream_key: manifest
        for manifest in request.source_projection.stream_manifests
    }
    if len(manifests) != len(request.source_projection.stream_manifests):
        raise ValueError("accepted V2 source manifests must have disjoint stream keys")
    if (
        tuple(
            binding.get("price_purpose") for binding in request._price_purpose_bindings
        )
        != _BOUND_PRICE_PURPOSES
    ):
        raise ValueError("validated profile price bindings are incomplete")
    bindings = []
    bound_keys: set[str] = set()
    for profile_binding in request._price_purpose_bindings:
        purpose = profile_binding["price_purpose"]
        if type(purpose) is not str:
            raise ValueError("validated profile purpose must be text")
        stream_key = _PRICE_PURPOSE_SOURCE_STREAMS[purpose]
        manifest = manifests.get(stream_key)
        if manifest is None or stream_key in bound_keys:
            raise ValueError("price purpose source manifest binding is incomplete")
        bound_keys.add(stream_key)
        bindings.append(
            {
                **profile_binding,
                "source_stream_manifest": {
                    "stream_key": manifest.stream_key,
                    "event_type": manifest.event_type,
                    "original_capability": manifest.capability.to_canonical_dict(),
                    "event_count": manifest.event_count,
                    "content_hash": manifest.content_hash,
                },
            }
        )
    if len(bound_keys) != 4:
        raise ValueError("price purpose authority must exact-cover four purposes")
    return {
        "schema_version": _SCHEMA_VERSION,
        "instrument_id": _INSTRUMENT_WIRE,
        "price_purpose_bindings": tuple(bindings),
        **_streaming_authority_bindings(request),
    }


def _authority_event_binding(event: MarketEvent) -> dict[str, object]:
    return {
        "stream_key": event.stream_key,
        "event_type": event.event_type,
        "event_id": event.event_id,
        "event_hash": event.event_hash,
    }


def _preparation_payload(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV2,
    price_purpose: MarketEvent,
) -> dict[str, object]:
    source = request.source_projection
    target = request.target_result
    return {
        "schema_version": _SCHEMA_VERSION,
        "profile_composition_request_wire": request.profile_composition_request_wire,
        "profile_composition_request_hash": request.profile_composition_request_hash,
        "strategy_definition_ref": target.strategy.ref.to_canonical_dict(),
        "parameter_target_bindings": _parameter_target_bindings(target),
        "xkrx_calendar_ref": source.xkrx_calendar_ref.to_canonical_dict(),
        "arcx_calendar_ref": source.arcx_calendar_ref.to_canonical_dict(),
        "post_adjustment_unit_regime_ref": (
            source.post_adjustment_unit_regime_ref.to_canonical_dict()
        ),
        "source_profile_authority_envelope": (
            request.source_profile_authority_envelope.to_canonical_dict()
        ),
        "source_profile_authority_ref": (
            request.source_profile_authority_ref.to_canonical_dict()
        ),
        "source_snapshot_bindings": _source_snapshot_bindings(source),
        **_streaming_authority_bindings(request),
        "price_purpose_authority_binding": _authority_event_binding(price_purpose),
        "required_initial_equity": request.initial_equity.to_canonical_dict(),
        "required_sleeve_allocation_fraction": request.sleeve_allocation_fraction,
        "required_position_notional_usdt": _REQUIRED_POSITION_NOTIONAL,
        "source_limitations": _LIMITATIONS,
    }


def _event(
    *,
    stream_key: str,
    event_type: str,
    capability: MarketBundleCapability,
    instrument_id: object,
    instant: UtcInstant,
    phase: TimelinePhase,
    payload: dict[str, object],
) -> MarketEvent:
    source_hash = canonical_sha256(
        {
            "type": event_type + "_source_v2",
            "stream_key": stream_key,
            "payload": payload,
        }
    )
    return MarketEvent(
        event_id=event_type + ":" + source_hash,
        stream_key=stream_key,
        event_type=event_type,
        capability=capability,
        instrument_id=instrument_id,
        event_time=instant,
        available_time=instant,
        phase=phase,
        source_sequence=SourceSequence(0),
        revision_id=canonical_sha256(
            {"type": event_type + "_revision_v2", "source_hash": source_hash}
        ),
        supersedes_revision_id=None,
        source_key=stream_key,
        source_hash=source_hash,
        payload=payload,
    )


def _authority_events(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV2,
) -> tuple[MarketEvent, MarketEvent, MarketEvent]:
    start = request.source_projection.request.timeline_window_start
    price_purpose = _event(
        stream_key=_PRICE_PURPOSE_STREAM,
        event_type=_PRICE_PURPOSE_EVENT_TYPE,
        capability=_PRICE_PURPOSE_CAPABILITY,
        instrument_id=_INSTRUMENT,
        instant=start,
        phase=TimelinePhase(0, "market_data"),
        payload=_price_purpose_payload(request),
    )
    preparation = _event(
        stream_key=_PREPARATION_STREAM,
        event_type=_PREPARATION_EVENT_TYPE,
        capability=_PREPARATION_CAPABILITY,
        instrument_id=None,
        instant=start,
        phase=TimelinePhase(0, "market_data"),
        payload=_preparation_payload(request, price_purpose),
    )
    strategy_ref = request.target_result.strategy.ref
    account = _event(
        stream_key=_ACCOUNT_STREAM,
        event_type=_ACCOUNT_EVENT_TYPE,
        capability=_ACCOUNT_CAPABILITY,
        instrument_id=_INSTRUMENT,
        instant=start,
        phase=TimelinePhase(110, "account_financial_dispatch"),
        payload={
            "schema_version": _SCHEMA_VERSION,
            "account_id": request.execution_account_id,
            "initial_equity": request.initial_equity.to_canonical_dict(),
            "sleeve_allocation_fraction": request.sleeve_allocation_fraction,
            "position_notional_usdt": _REQUIRED_POSITION_NOTIONAL,
            "profile_composition_request_hash": request.profile_composition_request_hash,
            "strategy_definition_ref": strategy_ref.to_canonical_dict(),
            "strategy_definition_hash": strategy_ref.content_hash,
            "operation_authorized": False,
            "order_authorized": False,
            "deployment_authorized": False,
        },
    )
    return preparation, price_purpose, account


def _validate_selected_lineage(
    source: BinanceUsdmKoruTradifiSourceProjectionResultV2,
) -> None:
    boundary = source.request.aggregate_trade_boundary_index_result
    selected = {event.event_id: event for event in boundary.selected_source_events}
    retained = {
        event.event_id: event for event in source.source_events if event.event_id in selected
    }
    if set(retained) != set(selected) or any(
        not _canonical_equal(retained[event_id], event)
        for event_id, event in selected.items()
    ):
        raise ValueError("selected aggregate source lineage is not exact")
    if {value.source_event_id for value in source.projection_lineage} != set(selected):
        raise ValueError("selected aggregate source events must exact-cover lineage")
    projections = {event.event_id: event for event in source.projection_events}
    if {value.projection_event_id for value in source.projection_lineage} != set(
        projections
    ) or any(
        projections[value.projection_event_id].event_hash
        != value.projection_event_hash
        for value in source.projection_lineage
    ):
        raise ValueError("projection lineage must exact-cover V2 bar-open events")


def _accepted_streams(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV2,
    preparation: MarketEvent,
    price_purpose: MarketEvent,
    account: MarketEvent,
) -> tuple[dict[str, tuple[MarketEvent, ...]], tuple[MarketStreamManifest, ...]]:
    source = request.source_projection
    _validate_selected_lineage(source)
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in (*source.source_events, *source.projection_events):
        grouped[event.stream_key].append(event)
    streams: dict[str, tuple[MarketEvent, ...]] = {
        manifest.stream_key: tuple(grouped.get(manifest.stream_key, ()))
        for manifest in source.stream_manifests
    }
    manifests = list(source.stream_manifests)
    funding_events = source.request.funding_result.events
    funding_identities = {
        (event.stream_key, event.event_type, event.capability) for event in funding_events
    }
    if len(funding_identities) != 1:
        raise ValueError("accepted funding authority must have one stream identity")
    funding_key, funding_type, funding_capability = next(iter(funding_identities))
    if funding_key != _FUNDING_STREAM:
        raise ValueError("accepted funding authority stream identity mismatch")
    if funding_key not in streams:
        streams[funding_key] = ()
        manifests.append(
            MarketStreamManifest(
                funding_key,
                funding_type,
                funding_capability,
                0,
                canonical_sha256(()),
            )
        )
    if len(request.target_result.streams) != 8:
        raise ValueError("V2 target result must exact-cover eight streams")
    for target_stream in request.target_result.streams:
        if target_stream.stream_key in streams:
            raise ValueError("target stream collides with accepted source stream")
        streams[target_stream.stream_key] = target_stream.events
        manifests.append(target_stream.manifest)
    for event in (preparation, price_purpose, account):
        if event.stream_key in streams:
            raise ValueError("authority stream collides with accepted stream")
        streams[event.stream_key] = (event,)
        manifests.append(MarketStreamManifest.from_events(event.stream_key, (event,)))
    if len(streams) != len(manifests) or len(
        {event.event_id for events in streams.values() for event in events}
    ) != sum(len(events) for events in streams.values()):
        raise ValueError("bundle streams must exact-cover globally unique events")
    for manifest in manifests:
        events = streams[manifest.stream_key]
        if len({event.ordering_key for event in events}) != len(events):
            raise ValueError("stream ordering keys must be unique")
        expected = (
            MarketStreamManifest.from_events(manifest.stream_key, events)
            if events
            else MarketStreamManifest(
                manifest.stream_key,
                manifest.event_type,
                manifest.capability,
                0,
                canonical_sha256(()),
            )
        )
        if not _canonical_equal(manifest, expected):
            raise ValueError("accepted stream manifest does not match exact events")
    return streams, tuple(manifests)


@dataclass(frozen=True, slots=True)
class _Assembled:
    preparation_authority_event: MarketEvent
    price_purpose_authority_event: MarketEvent
    account_authority_event: MarketEvent
    streams: Mapping[str, tuple[MarketEvent, ...]]
    events: tuple[MarketEvent, ...]
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    reader: InMemoryMarketBundleReader


def _assemble(request: BinanceUsdmKoruTradifiExecutionBundleRequestV2) -> _Assembled:
    preparation, price_purpose, account = _authority_events(request)
    streams, stream_manifests = _accepted_streams(
        request, preparation, price_purpose, account
    )
    source_request = request.source_projection.request
    manifest = MarketBundleManifest.build(
        bundle_key=request.bundle_key,
        schema_version=_SCHEMA_VERSION,
        coverage_start=source_request.timeline_window_start,
        coverage_end_exclusive=source_request.timeline_window_end_exclusive,
        instrument_catalog_hash=source_request.instrument_catalog_hash,
        capabilities=tuple(sorted({value.capability for value in stream_manifests})),
        streams=stream_manifests,
    )
    bundle_ref = MarketBundleRef.from_manifest(manifest)
    reader = InMemoryMarketBundleReader(bundle_ref, manifest, streams)
    events = tuple(
        event
        for stream_key in sorted(reader.streams)
        for event in reader.streams[stream_key]
    )
    return _Assembled(
        preparation,
        price_purpose,
        account,
        reader.streams,
        events,
        manifest,
        bundle_ref,
        reader,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleResultV2:
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV2
    preparation_authority_event: MarketEvent
    price_purpose_authority_event: MarketEvent
    account_authority_event: MarketEvent
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    reader: InMemoryMarketBundleReader
    events: tuple[MarketEvent, ...]
    development_only: bool = True
    deployment_authorized: bool = False
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        trusted_request = _trusted_request(self.request)
        if trusted_request is None:
            raise TypeError("request must be exact V2 execution-bundle request")
        assembled = _assemble(trusted_request)
        if (
            type(self.preparation_authority_event) is not MarketEvent
            or not _canonical_equal(
                self.preparation_authority_event, assembled.preparation_authority_event
            )
            or type(self.price_purpose_authority_event) is not MarketEvent
            or not _canonical_equal(
                self.price_purpose_authority_event,
                assembled.price_purpose_authority_event,
            )
            or type(self.account_authority_event) is not MarketEvent
            or not _canonical_equal(
                self.account_authority_event, assembled.account_authority_event
            )
            or type(self.manifest) is not MarketBundleManifest
            or not _canonical_equal(self.manifest, assembled.manifest)
            or type(self.bundle_ref) is not MarketBundleRef
            or self.bundle_ref != assembled.bundle_ref
            or type(self.reader) is not InMemoryMarketBundleReader
            or self.reader.bundle_ref != assembled.reader.bundle_ref
            or not _canonical_equal(self.reader.manifest, assembled.reader.manifest)
            or not _canonical_equal(self.reader.streams, assembled.reader.streams)
            or type(self.events) is not tuple
            or not _canonical_equal(self.events, assembled.events)
            or type(self.development_only) is not bool
            or not self.development_only
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("V2 execution-bundle result binding mismatch")
        object.__setattr__(self, "request", trusted_request)
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    @property
    def source_projection(self) -> BinanceUsdmKoruTradifiSourceProjectionResultV2:
        return self.request.source_projection

    @property
    def target_result(self) -> BinanceUsdmKoruClosedMarketRangeTargetsResultV2:
        return self.request.target_result

    @property
    def authority_artifacts(self) -> tuple[ArtifactEnvelope, ...]:
        source = self.source_projection
        return (
            source.xkrx_calendar,
            source.arcx_calendar,
            source.post_adjustment_unit_regime,
            self.request.source_profile_authority_envelope,
        )

    @property
    def authority_refs(self) -> tuple[ArtifactRef, ...]:
        source = self.source_projection
        return (
            source.xkrx_calendar_ref,
            source.arcx_calendar_ref,
            source.post_adjustment_unit_regime_ref,
            self.request.source_profile_authority_ref,
        )

    @property
    def strategy(self) -> BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1:
        return self.target_result.strategy

    @property
    def strategy_artifact(self) -> ArtifactEnvelope:
        return self.strategy.envelope

    @property
    def strategy_ref(self) -> ArtifactRef:
        return self.strategy.ref

    @property
    def parameters(
        self,
    ) -> tuple[BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1, ...]:
        return self.target_result.parameters

    @property
    def parameter_artifacts(self) -> tuple[ArtifactEnvelope, ...]:
        return tuple(value.envelope for value in self.parameters)

    @property
    def parameter_refs(self) -> tuple[ArtifactRef, ...]:
        return tuple(value.ref for value in self.parameters)

    @property
    def streams(self) -> Mapping[str, tuple[MarketEvent, ...]]:
        return self.reader.streams

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_execution_bundle_result_v2",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "authority_artifacts": self.authority_artifacts,
            "authority_refs": self.authority_refs,
            "strategy_artifact": self.strategy_artifact,
            "strategy_ref": self.strategy_ref,
            "parameter_artifacts": self.parameter_artifacts,
            "parameter_refs": self.parameter_refs,
            "preparation_authority_event": self.preparation_authority_event,
            "price_purpose_authority_event": self.price_purpose_authority_event,
            "account_authority_event": self.account_authority_event,
            "manifest": self.manifest,
            "bundle_ref": self.bundle_ref,
            "events": self.events,
            "limitations": _LIMITATIONS,
            "development_only": self.development_only,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_request(
    value: object,
) -> BinanceUsdmKoruTradifiExecutionBundleRequestV2 | None:
    if type(value) is not BinanceUsdmKoruTradifiExecutionBundleRequestV2:
        return None
    try:
        rebuilt = BinanceUsdmKoruTradifiExecutionBundleRequestV2(
            source_projection=value.source_projection,
            target_result=value.target_result,
            source_profile_authority_envelope=(
                value.source_profile_authority_envelope
            ),
            source_profile_authority_ref=value.source_profile_authority_ref,
            profile_composition_request_wire=value.profile_composition_request_wire,
            profile_composition_request_hash=value.profile_composition_request_hash,
            execution_account_id=value.execution_account_id,
            initial_equity=value.initial_equity,
            sleeve_allocation_fraction=value.sleeve_allocation_fraction,
        )
        if not _canonical_equal(rebuilt, value):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


def _trusted_result(
    value: object,
) -> BinanceUsdmKoruTradifiExecutionBundleResultV2 | None:
    if type(value) is not BinanceUsdmKoruTradifiExecutionBundleResultV2:
        return None
    try:
        rebuilt = BinanceUsdmKoruTradifiExecutionBundleResultV2(
            request=value.request,
            preparation_authority_event=value.preparation_authority_event,
            price_purpose_authority_event=value.price_purpose_authority_event,
            account_authority_event=value.account_authority_event,
            manifest=value.manifest,
            bundle_ref=value.bundle_ref,
            reader=value.reader,
            events=value.events,
            development_only=value.development_only,
            deployment_authorized=value.deployment_authorized,
        )
        if not _canonical_equal(rebuilt, value) or value.result_digest != canonical_sha256(
            value._body()
        ):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleOutcomeV2:
    result: BinanceUsdmKoruTradifiExecutionBundleResultV2 | None = None
    failure: BinanceUsdmKoruTradifiExecutionBundleFailureV2 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result must be an exact canonical V2 execution-bundle result")
        if self.failure is not None and type(
            self.failure
        ) is not BinanceUsdmKoruTradifiExecutionBundleFailureV2:
            raise TypeError("failure must be exact V2 execution-bundle failure")


def _failed(
    code: BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2,
    subject: str,
) -> BinanceUsdmKoruTradifiExecutionBundleOutcomeV2:
    return BinanceUsdmKoruTradifiExecutionBundleOutcomeV2(
        failure=BinanceUsdmKoruTradifiExecutionBundleFailureV2(code, subject)
    )


def build_binance_usdm_koru_tradifi_execution_bundle_v2(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV2,
) -> BinanceUsdmKoruTradifiExecutionBundleOutcomeV2:
    trusted = _trusted_request(request)
    if trusted is None:
        return _failed(
            BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2.INVALID_REQUEST,
            "request",
        )
    try:
        assembled = _assemble(trusted)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2.STREAM_ASSEMBLY_INVALID,
            f"{type(error).__name__}:{error}"[:500],
        )
    try:
        result = BinanceUsdmKoruTradifiExecutionBundleResultV2(
            request=trusted,
            preparation_authority_event=assembled.preparation_authority_event,
            price_purpose_authority_event=assembled.price_purpose_authority_event,
            account_authority_event=assembled.account_authority_event,
            manifest=assembled.manifest,
            bundle_ref=assembled.bundle_ref,
            reader=assembled.reader,
            events=assembled.events,
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2.RESULT_INVALID,
            f"{type(error).__name__}:{error}"[:500],
        )
    return BinanceUsdmKoruTradifiExecutionBundleOutcomeV2(result=result)
