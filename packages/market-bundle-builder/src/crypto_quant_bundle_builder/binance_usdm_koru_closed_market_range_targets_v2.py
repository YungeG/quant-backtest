"""Frozen V2 target streams for the KORU closed-market range strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    SourceSequence,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import MarketEvent, MarketStreamManifest

from .binance_usdm_koru_aggtrade_boundary_index_v1 import (
    BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1,
    BinanceUsdmKoruRawIdGapStreamEvidenceV1,
)
from .binance_usdm_koru_closed_market_range_targets_v1 import (
    _CAPABILITY,
    _EVENT_TYPE,
    _PHASE,
    _STREAM_PREFIX,
    BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1,
    BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1,
    _canonical_equal,
    _closed_intervals,
    _manifest,
    _parameter_bindings,
    _Projection,
    _strategy_binding,
    _strategy_pairs,
    _stream_candidates,
    _target_stream_digest,
)
from .binance_usdm_koru_closed_market_range_targets_v1 import (
    _SOURCE_KEY as _V1_SOURCE_KEY,
)
from .binance_usdm_koru_closed_market_range_targets_v1 import (
    _TargetError as _V1TargetError,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruFirstRetainedTradeProjectionLineageV2,
    BinanceUsdmKoruMissingBoundaryProjectionV2,
    BinanceUsdmKoruTradifiSourceProjectionResultV2,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    _trusted_result as _trusted_source_result,
)

_SCHEMA_VERSION = 2
_SOURCE_KEY = _V1_SOURCE_KEY.removesuffix(".v1") + ".v2"
_STREAM_KEYS = tuple(f"{_STREAM_PREFIX}{index:02d}.v2" for index in range(1, 9))


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetsRequestV2:
    source_projection: BinanceUsdmKoruTradifiSourceProjectionResultV2

    def __post_init__(self) -> None:
        trusted = _trusted_source_result(self.source_projection)
        if trusted is None:
            raise ValueError("source_projection must be an exact accepted V2 result")
        object.__setattr__(self, "source_projection", trusted)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_closed_market_range_targets_request_v2",
            "schema_version": _SCHEMA_VERSION,
            "source_projection": self.source_projection,
            "source_fragment_digest": self.source_projection.fragment_digest,
        }


class BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_FRAGMENT_INVALID = "source_fragment_invalid"
    TARGET_GENERATION_INVALID = "target_generation_invalid"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetsFailureV2:
    code: BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2
    subject: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2:
            raise TypeError("code must be an exact V2 target-generation failure code")
        if self.subject is not None and (
            type(self.subject) is not str
            or not self.subject
            or self.subject != self.subject.strip()
        ):
            raise ValueError("subject must be canonical text or None")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_closed_market_range_targets_failure_v2",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetStreamResultV2:
    parameter_ref: ArtifactRef
    stream_key: str
    events: tuple[MarketEvent, ...]
    manifest: MarketStreamManifest
    target_stream_digest: str

    def __post_init__(self) -> None:
        if type(self.parameter_ref) is not ArtifactRef:
            raise TypeError("parameter_ref must be exact ArtifactRef")
        if type(self.stream_key) is not str or self.stream_key not in _STREAM_KEYS:
            raise ValueError("stream_key must be a sealed V2 target stream key")
        if type(self.events) is not tuple or any(
            type(event) is not MarketEvent for event in self.events
        ):
            raise TypeError("events must be an exact MarketEvent tuple")
        if any(event.stream_key != self.stream_key for event in self.events):
            raise ValueError("target event stream mismatch")
        expected_manifest = _manifest(self.stream_key, self.events)
        if type(self.manifest) is not MarketStreamManifest or not _canonical_equal(
            self.manifest, expected_manifest
        ):
            raise ValueError("target stream manifest mismatch")
        expected_digest = _target_stream_digest(self.stream_key, self.events)
        if self.target_stream_digest != expected_digest:
            raise ValueError("target stream digest mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_closed_market_range_target_stream_result_v2",
            "schema_version": _SCHEMA_VERSION,
            "parameter_ref": self.parameter_ref,
            "stream_key": self.stream_key,
            "events": self.events,
            "manifest": self.manifest,
            "target_stream_digest": self.target_stream_digest,
        }


class _TargetError(ValueError):
    def __init__(
        self, code: BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2, subject: str
    ) -> None:
        super().__init__(subject)
        self.code = code
        self.subject = subject


@dataclass(frozen=True, slots=True)
class _Assembled:
    strategy: BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1
    parameters: tuple[BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1, ...]
    streams: tuple[BinanceUsdmKoruClosedMarketRangeTargetStreamResultV2, ...]


def _projections(
    source: BinanceUsdmKoruTradifiSourceProjectionResultV2,
) -> dict[int, _Projection]:
    events = {event.event_id: event for event in source.projection_events}
    missing: set[int] = set()
    for value in source.missing_boundaries:
        if type(value) is not BinanceUsdmKoruMissingBoundaryProjectionV2:
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.SOURCE_FRAGMENT_INVALID,
                "missing_projection_type",
            )
        boundary = value.hourly_boundary.epoch_nanoseconds
        if boundary in missing:
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.SOURCE_FRAGMENT_INVALID,
                f"duplicate_missing_projection:{boundary}",
            )
        missing.add(boundary)

    result: dict[int, _Projection] = {}
    for lineage in source.projection_lineage:
        if type(lineage) is not BinanceUsdmKoruFirstRetainedTradeProjectionLineageV2:
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.SOURCE_FRAGMENT_INVALID,
                "projection_lineage_type",
            )
        event = events.get(lineage.projection_event_id)
        boundary = lineage.hourly_boundary.epoch_nanoseconds
        cutoff = lineage.next_cash_market_open_or_window_end.epoch_nanoseconds
        if (
            event is None
            or event.event_hash != lineage.projection_event_hash
            or event.event_time.epoch_nanoseconds >= cutoff
            or boundary in result
            or boundary in missing
        ):
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.SOURCE_FRAGMENT_INVALID,
                f"unsafe_projection:{boundary}",
            )
        result[boundary] = _Projection(boundary, cutoff, event)
    if len(result) != len(events):
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.SOURCE_FRAGMENT_INVALID,
            "unbound_projection_event",
        )
    return result


def _event(stream_key: str, sequence: int, candidate: dict[str, object]) -> MarketEvent:
    preimage = {
        "type": "binance_usdm_koru_closed_market_range_target_preimage_v2",
        "schema_version": _SCHEMA_VERSION,
        "stream_key": stream_key,
        "candidate": candidate,
    }
    event_identity = canonical_sha256({"identity": "event", "preimage": preimage})
    revision_identity = canonical_sha256({"identity": "revision", "preimage": preimage})
    source_identity = canonical_sha256({"identity": "source", "preimage": preimage})
    decision_time = UtcInstant(cast(int, candidate["decision_time"]))
    return MarketEvent(
        event_id="binance-usdm-koru-closed-market-range-target-v2:" + event_identity,
        stream_key=stream_key,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=None,
        event_time=decision_time,
        available_time=decision_time,
        phase=_PHASE,
        source_sequence=SourceSequence(sequence),
        revision_id=revision_identity,
        supersedes_revision_id=None,
        source_key=_SOURCE_KEY,
        source_hash=source_identity,
        payload={"schema_version": 1, "candidate": candidate},
    )


def _assemble(value: object) -> _Assembled:
    if type(value) is not BinanceUsdmKoruClosedMarketRangeTargetsRequestV2:
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.INVALID_REQUEST,
            "request_type",
        )
    trusted_source = _trusted_source_result(value.source_projection)
    if trusted_source is None:
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.SOURCE_FRAGMENT_INVALID,
            "source_projection",
        )
    request = BinanceUsdmKoruClosedMarketRangeTargetsRequestV2(trusted_source)
    if not _canonical_equal(request, value):
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.INVALID_REQUEST,
            "request_binding",
        )
    strategy = _strategy_binding()
    parameters = _parameter_bindings(strategy.ref)
    try:
        closed = _closed_intervals(trusted_source)
        pairs = _strategy_pairs(trusted_source)
        projections = _projections(trusted_source)
        streams = []
        for parameter, stream_key in zip(parameters, _STREAM_KEYS, strict=True):
            candidates = _stream_candidates(
                source=trusted_source,
                strategy_ref=strategy.ref,
                parameter=parameter,
                closed=closed,
                pairs=pairs,
                projections=projections,
            )
            events = tuple(
                _event(stream_key, sequence, candidate)
                for sequence, candidate in enumerate(candidates)
            )
            streams.append(
                BinanceUsdmKoruClosedMarketRangeTargetStreamResultV2(
                    parameter_ref=parameter.ref,
                    stream_key=stream_key,
                    events=events,
                    manifest=_manifest(stream_key, events),
                    target_stream_digest=_target_stream_digest(stream_key, events),
                )
            )
    except _V1TargetError as error:
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2(error.code.value),
            error.subject,
        ) from error
    return _Assembled(strategy, parameters, tuple(streams))


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetsResultV2:
    request: BinanceUsdmKoruClosedMarketRangeTargetsRequestV2
    strategy: BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1
    parameters: tuple[BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1, ...]
    streams: tuple[BinanceUsdmKoruClosedMarketRangeTargetStreamResultV2, ...]
    source_fragment_digest: str
    aggregate_trade_boundary_index_request_hash: str
    aggregate_trade_boundary_index_result_digest: str
    aggregate_trade_streamed_reconstruction_digest: str
    aggregate_trade_intra_day_raw_id_gap_stream: BinanceUsdmKoruRawIdGapStreamEvidenceV1
    aggregate_trade_cross_date_raw_id_gap_stream: (
        BinanceUsdmKoruRawIdGapStreamEvidenceV1
    )
    aggregate_trade_coverage_gaps: tuple[
        BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1, ...
    ]
    missing_boundaries: tuple[BinanceUsdmKoruMissingBoundaryProjectionV2, ...]
    development_authorized: bool = False
    deployment_authorized: bool = False
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        assembled = _assemble(self.request)
        source = self.request.source_projection
        if (
            type(self.strategy)
            is not BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1
            or not _canonical_equal(self.strategy, assembled.strategy)
            or type(self.parameters) is not tuple
            or not _canonical_equal(self.parameters, assembled.parameters)
            or type(self.streams) is not tuple
            or not _canonical_equal(self.streams, assembled.streams)
            or self.source_fragment_digest != source.fragment_digest
            or self.aggregate_trade_boundary_index_request_hash
            != source.aggregate_trade_boundary_index_request_hash
            or self.aggregate_trade_boundary_index_result_digest
            != source.aggregate_trade_boundary_index_result_digest
            or self.aggregate_trade_streamed_reconstruction_digest
            != source.aggregate_trade_streamed_reconstruction_digest
            or type(self.aggregate_trade_intra_day_raw_id_gap_stream)
            is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
            or not _canonical_equal(
                self.aggregate_trade_intra_day_raw_id_gap_stream,
                source.aggregate_trade_intra_day_raw_id_gap_stream,
            )
            or type(self.aggregate_trade_cross_date_raw_id_gap_stream)
            is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
            or not _canonical_equal(
                self.aggregate_trade_cross_date_raw_id_gap_stream,
                source.aggregate_trade_cross_date_raw_id_gap_stream,
            )
            or type(self.aggregate_trade_coverage_gaps) is not tuple
            or not _canonical_equal(
                self.aggregate_trade_coverage_gaps,
                source.aggregate_trade_coverage_gaps,
            )
            or type(self.missing_boundaries) is not tuple
            or not _canonical_equal(self.missing_boundaries, source.missing_boundaries)
            or type(self.development_authorized) is not bool
            or self.development_authorized
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("V2 target-generation result binding mismatch")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    @property
    def artifacts(self) -> tuple[ArtifactEnvelope, ...]:
        return (self.strategy.envelope,) + tuple(
            value.envelope for value in self.parameters
        )

    @property
    def refs(self) -> tuple[ArtifactRef, ...]:
        return (self.strategy.ref,) + tuple(value.ref for value in self.parameters)

    @property
    def stream_manifests(self) -> tuple[MarketStreamManifest, ...]:
        return tuple(value.manifest for value in self.streams)

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_closed_market_range_targets_result_v2",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_hash": self.request.request_hash,
            "strategy": self.strategy,
            "parameters": self.parameters,
            "streams": self.streams,
            "source_fragment_digest": self.source_fragment_digest,
            "aggregate_trade_boundary_index_request_hash": self.aggregate_trade_boundary_index_request_hash,
            "aggregate_trade_boundary_index_result_digest": self.aggregate_trade_boundary_index_result_digest,
            "aggregate_trade_streamed_reconstruction_digest": self.aggregate_trade_streamed_reconstruction_digest,
            "aggregate_trade_intra_day_raw_id_gap_stream": self.aggregate_trade_intra_day_raw_id_gap_stream,
            "aggregate_trade_cross_date_raw_id_gap_stream": self.aggregate_trade_cross_date_raw_id_gap_stream,
            "aggregate_trade_coverage_gaps": self.aggregate_trade_coverage_gaps,
            "missing_boundaries": self.missing_boundaries,
            "development_authorized": self.development_authorized,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_result(
    value: object,
) -> BinanceUsdmKoruClosedMarketRangeTargetsResultV2 | None:
    if type(value) is not BinanceUsdmKoruClosedMarketRangeTargetsResultV2:
        return None
    try:
        rebuilt = BinanceUsdmKoruClosedMarketRangeTargetsResultV2(
            request=value.request,
            strategy=value.strategy,
            parameters=value.parameters,
            streams=value.streams,
            source_fragment_digest=value.source_fragment_digest,
            aggregate_trade_boundary_index_request_hash=(
                value.aggregate_trade_boundary_index_request_hash
            ),
            aggregate_trade_boundary_index_result_digest=(
                value.aggregate_trade_boundary_index_result_digest
            ),
            aggregate_trade_streamed_reconstruction_digest=(
                value.aggregate_trade_streamed_reconstruction_digest
            ),
            aggregate_trade_intra_day_raw_id_gap_stream=(
                value.aggregate_trade_intra_day_raw_id_gap_stream
            ),
            aggregate_trade_cross_date_raw_id_gap_stream=(
                value.aggregate_trade_cross_date_raw_id_gap_stream
            ),
            aggregate_trade_coverage_gaps=value.aggregate_trade_coverage_gaps,
            missing_boundaries=value.missing_boundaries,
            development_authorized=value.development_authorized,
            deployment_authorized=value.deployment_authorized,
        )
        if not _canonical_equal(
            rebuilt, value
        ) or value.result_digest != canonical_sha256(value._body()):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2:
    result: BinanceUsdmKoruClosedMarketRangeTargetsResultV2 | None = None
    failure: BinanceUsdmKoruClosedMarketRangeTargetsFailureV2 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result must be an exact canonical V2 target result")
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruClosedMarketRangeTargetsFailureV2
        ):
            raise TypeError("failure must be exact V2 target-generation failure")


def _failed(
    code: BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2, subject: str
) -> BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2:
    return BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2(
        failure=BinanceUsdmKoruClosedMarketRangeTargetsFailureV2(code, subject)
    )


def build_binance_usdm_koru_closed_market_range_targets_v2(
    request: BinanceUsdmKoruClosedMarketRangeTargetsRequestV2,
) -> BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2:
    try:
        assembled = _assemble(request)
        source = request.source_projection
        result = BinanceUsdmKoruClosedMarketRangeTargetsResultV2(
            request=request,
            strategy=assembled.strategy,
            parameters=assembled.parameters,
            streams=assembled.streams,
            source_fragment_digest=source.fragment_digest,
            aggregate_trade_boundary_index_request_hash=(
                source.aggregate_trade_boundary_index_request_hash
            ),
            aggregate_trade_boundary_index_result_digest=(
                source.aggregate_trade_boundary_index_result_digest
            ),
            aggregate_trade_streamed_reconstruction_digest=(
                source.aggregate_trade_streamed_reconstruction_digest
            ),
            aggregate_trade_intra_day_raw_id_gap_stream=(
                source.aggregate_trade_intra_day_raw_id_gap_stream
            ),
            aggregate_trade_cross_date_raw_id_gap_stream=(
                source.aggregate_trade_cross_date_raw_id_gap_stream
            ),
            aggregate_trade_coverage_gaps=source.aggregate_trade_coverage_gaps,
            missing_boundaries=source.missing_boundaries,
        )
    except _TargetError as error:
        return _failed(error.code, error.subject)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV2.RESULT_INVALID,
            type(error).__name__,
        )
    return BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2(result=result)
