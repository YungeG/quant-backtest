"""Streaming KORU source verification and first-retained-trade projection.

Selected aggregate source events retain their exact V1 identities. The derived V3
bar-open event, stream, revision, source, and manifest identities are versioned
projection identities and intentionally cannot equal their V1 counterparts.
"""

from __future__ import annotations

import base64
import json
from bisect import bisect_left
from collections import OrderedDict, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    InstrumentId,
    Scale,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketEvent,
    MarketStreamManifest,
)

from .binance_usdm_koru_aggtrade_boundary_index_v1 import (
    BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1,
    BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
    BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3,
    BinanceUsdmKoruExecutionBoundaryV1,
    BinanceUsdmKoruRawIdGapStreamEvidenceV1,
    BinanceUsdmKoruSelectedAggregateTradeLineageV1,
)
from .binance_usdm_koru_funding_rate_history_source_bounded_v1 import (
    BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1,
    normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1,
)
from .binance_usdm_koru_price_bars_source_bounded_v1 import (
    BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1,
    BinanceUsdmKoruPriceBarsSourceKindV1,
    normalize_binance_usdm_koru_price_bars_source_bounded_v1,
)
from .koru_tradifi_calendar_unit_authority_v1 import (
    APPROVED_MEMBER_HASHES,
    KoruTradifiCalendarUnitAuthorityResultV1,
    verify_koru_tradifi_calendar_unit_authority_v1,
)

_SCHEMA_VERSION = 3
_SOURCE_PROFILE_AUTHORITY_ARTIFACT_TYPE_V3 = "binance_usdm_koru_source_profile_authority"
_HOUR_NS = 3_600_000_000_000
_DAY_NS = 86_400_000_000_000
_ALLOWED_START = 1_784_109_600_000_000_000
_FIRST_PRICE_COMPLETION = _ALLOWED_START + _HOUR_NS
_ALLOWED_END_EXCLUSIVE = 1_791_158_400_000_000_000
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_FUNDING_STREAM = "binance_usdm.funding_history.publications.koruusdt.v1"
_FUNDING_EVENT_TYPE = "binance_usdm_koru_funding_history_publication_v1"
_FUNDING_CAPABILITY = MarketBundleCapability("binance_usdm.funding-publications", 1)
_PROJECTION_STREAM = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v3"
)
_PROJECTION_EVENT_TYPE = "bar_open"
_PROJECTION_CAPABILITY = MarketBundleCapability("bar_open", 1)
_PROJECTION_PHASE = TimelinePhase(20, "bar_open")
_PROJECTION_SOURCE_KEY = (
    "binance_usdm.tradifi.first_retained_aggregate_trade_projection.koruusdt.1h.v3"
)
_LIMITATIONS = (
    (
        "v3_bar_open_event_stream_revision_source_and_manifest_identities_are_versioned_"
        "and_intentionally_differ_from_v2"
    ),
)
_MARK_PURPOSES = frozenset({"strategy", "valuation", "margin", "liquidation"})
_INDEX_PURPOSES = frozenset({"strategy"})
_EPOCH_DATE = date(1970, 1, 1)

KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V3 = (
    "binance_usdm_koru_tradifi_source_projection_authority_v3"
)
KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V3 = 3
_AUTHORITY_BUILDER_ID_V3 = "binance_usdm_koru_tradifi_source_projection_v3"
_AUTHORITY_PAYLOAD_FIELDS_V3 = frozenset(
    {
        "type",
        "schema_version",
        "builder",
        "discovery_scope",
        "source_fragment_digest",
        "boundary_index_identity",
        "source_projection",
    }
)
_AUTHORITY_BUILDER_FIELDS_V3 = frozenset(
    {"id", "source_projection_type", "source_projection_schema_version"}
)
_AUTHORITY_SCOPE_FIELDS_V3 = frozenset(
    {"timeline_window_start", "timeline_window_end_exclusive"}
)


def _hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(digit not in "0123456789abcdef" for digit in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


def _canonical_equal(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _iso_ns(value: object) -> int:
    if type(value) is not str or not value.endswith("Z"):
        raise ValueError("authority time must be exact UTC text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("authority time must be exact UTC text") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("authority time must be UTC")
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    delta = parsed - epoch
    return (
        delta.days * _DAY_NS
        + delta.seconds * 1_000_000_000
        + delta.microseconds * 1_000
    )


def _required_price_grid(
    start: UtcInstant, end: UtcInstant
) -> tuple[tuple[int, int], ...]:
    first_completed = max(
        ((start.epoch_nanoseconds + _HOUR_NS - 1) // _HOUR_NS) * _HOUR_NS,
        _FIRST_PRICE_COMPLETION,
    )
    return tuple(
        (completed, (completed - _HOUR_NS) // 1_000_000)
        for completed in range(first_completed, end.epoch_nanoseconds, _HOUR_NS)
    )


def _price_result_dates(grid: tuple[tuple[int, int], ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (_EPOCH_DATE + timedelta(days=opened // (_DAY_NS // 1_000_000))).isoformat()
            for _, opened in grid
        )
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionRequestV3:
    timeline_window_start: UtcInstant
    timeline_window_end_exclusive: UtcInstant
    instrument_catalog_hash: str
    projection_scale: Scale
    aggregate_trade_boundary_index_result: (
        BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3
    )
    mark_price_results: tuple[
        BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1, ...
    ]
    index_price_results: tuple[
        BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1, ...
    ]
    funding_result: BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1
    authority_result: KoruTradifiCalendarUnitAuthorityResultV1

    def __post_init__(self) -> None:
        if (
            type(self.timeline_window_start) is not UtcInstant
            or type(self.timeline_window_end_exclusive) is not UtcInstant
            or not _ALLOWED_START
            <= self.timeline_window_start.epoch_nanoseconds
            < self.timeline_window_end_exclusive.epoch_nanoseconds
            <= _ALLOWED_END_EXCLUSIVE
        ):
            raise ValueError(
                "timeline window must be inside the admitted authority range"
            )
        _hash("instrument_catalog_hash", self.instrument_catalog_hash)
        if type(self.projection_scale) is not Scale or self.projection_scale != Scale(
            8
        ):
            raise ValueError("projection_scale must be exact Scale(8)")
        if (
            type(self.aggregate_trade_boundary_index_result)
            is not BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3
            or type(self.mark_price_results) is not tuple
            or any(
                type(value)
                is not BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1
                for value in self.mark_price_results
            )
            or type(self.index_price_results) is not tuple
            or any(
                type(value)
                is not BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1
                for value in self.index_price_results
            )
            or type(self.funding_result)
            is not BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1
            or type(self.authority_result)
            is not KoruTradifiCalendarUnitAuthorityResultV1
        ):
            raise TypeError("source results must use exact accepted types")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_source_projection_request_v3",
            "schema_version": _SCHEMA_VERSION,
            "timeline_window_start": self.timeline_window_start,
            "timeline_window_end_exclusive": self.timeline_window_end_exclusive,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "projection_scale": self.projection_scale.places,
            "aggregate_trade_boundary_index_result": self.aggregate_trade_boundary_index_result,
            "mark_price_results": self.mark_price_results,
            "index_price_results": self.index_price_results,
            "funding_result": self.funding_result,
            "authority_result": self.authority_result,
        }


class BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3(str, Enum):
    INVALID_REQUEST = "invalid_request"
    AUTHORITY_INVALID = "authority_invalid"
    AGGREGATE_TRADES_INVALID = "aggregate_trades_invalid"
    PRICE_BARS_INVALID = "price_bars_invalid"
    FUNDING_INVALID = "funding_invalid"
    SOURCE_CONTEXT_INVALID = "source_context_invalid"
    PROJECTION_INVALID = "projection_invalid"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionFailureV3:
    code: BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3
    subject: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3:
            raise TypeError("code must be an exact source-projection failure code")
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
            "type": "binance_usdm_koru_tradifi_source_projection_failure_v3",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFirstRetainedTradeProjectionLineageV3:
    hourly_boundary: UtcInstant
    next_cash_market_open_or_window_end: UtcInstant
    source_event_id: str
    source_event_hash: str
    source_revision_id: str
    source_event_time: UtcInstant
    source_available_time: UtcInstant
    source_key: str
    source_hash: str
    aggregate_trade_id: int
    first_trade_id: int
    last_trade_id: int
    source_record_hash: str
    source_snapshot_id: str
    source_snapshot_hash: str
    source_provenance_hash: str
    source_member_hash: str
    source_request_hash: str
    source_capture_hash: str
    boundary_index_request_hash: str
    boundary_index_result_digest: str
    boundary_index_lineage_hash: str
    open_price_units: int
    open_price_scale: int
    projection_event_id: str
    projection_event_hash: str
    projection_revision_id: str
    projection_source_key: str
    projection_source_hash: str
    lineage_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.hourly_boundary) is not UtcInstant
            or type(self.next_cash_market_open_or_window_end) is not UtcInstant
            or type(self.source_event_time) is not UtcInstant
            or type(self.source_available_time) is not UtcInstant
            or not self.hourly_boundary
            <= self.source_event_time
            < self.next_cash_market_open_or_window_end
            or type(self.aggregate_trade_id) is not int
            or type(self.first_trade_id) is not int
            or type(self.last_trade_id) is not int
            or self.aggregate_trade_id < 0
            or not 0 <= self.first_trade_id <= self.last_trade_id
            or type(self.open_price_units) is not int
            or self.open_price_units <= 0
            or self.open_price_scale != 8
        ):
            raise ValueError("projection lineage primitive binding mismatch")
        for name in (
            "source_event_id",
            "source_revision_id",
            "source_key",
            "source_snapshot_id",
            "projection_event_id",
            "projection_revision_id",
            "projection_source_key",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f"{name} must be canonical text")
        for name in (
            "source_event_hash",
            "source_hash",
            "source_record_hash",
            "source_snapshot_hash",
            "source_provenance_hash",
            "source_member_hash",
            "source_request_hash",
            "source_capture_hash",
            "boundary_index_request_hash",
            "boundary_index_result_digest",
            "boundary_index_lineage_hash",
            "projection_event_hash",
            "projection_source_hash",
        ):
            _hash(name, getattr(self, name))
        object.__setattr__(self, "lineage_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_first_retained_trade_projection_lineage_v3",
            "schema_version": _SCHEMA_VERSION,
            "hourly_boundary": self.hourly_boundary,
            "next_cash_market_open_or_window_end": self.next_cash_market_open_or_window_end,
            "source_event_id": self.source_event_id,
            "source_event_hash": self.source_event_hash,
            "source_revision_id": self.source_revision_id,
            "source_event_time": self.source_event_time,
            "source_available_time": self.source_available_time,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "source_ids": {
                "aggregate_trade_id": self.aggregate_trade_id,
                "first_trade_id": self.first_trade_id,
                "last_trade_id": self.last_trade_id,
            },
            "source_record_hash": self.source_record_hash,
            "source_snapshot_id": self.source_snapshot_id,
            "source_snapshot_hash": self.source_snapshot_hash,
            "source_provenance_hash": self.source_provenance_hash,
            "source_member_hash": self.source_member_hash,
            "source_request_hash": self.source_request_hash,
            "source_capture_hash": self.source_capture_hash,
            "boundary_index_request_hash": self.boundary_index_request_hash,
            "boundary_index_result_digest": self.boundary_index_result_digest,
            "boundary_index_lineage_hash": self.boundary_index_lineage_hash,
            "open_price": {
                "units": self.open_price_units,
                "scale": self.open_price_scale,
                "quote_currency": "USDT",
            },
            "projection_event_id": self.projection_event_id,
            "projection_event_hash": self.projection_event_hash,
            "projection_revision_id": self.projection_revision_id,
            "projection_source_key": self.projection_source_key,
            "projection_source_hash": self.projection_source_hash,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "lineage_hash": self.lineage_hash}


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruMissingBoundaryProjectionV3:
    hourly_boundary: UtcInstant
    next_cash_market_open_or_window_end: UtcInstant
    reason: str
    missing_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.hourly_boundary) is not UtcInstant
            or type(self.next_cash_market_open_or_window_end) is not UtcInstant
            or self.next_cash_market_open_or_window_end <= self.hourly_boundary
        ):
            raise ValueError("missing boundary interval is invalid")
        if self.reason not in {
            "missing_retained_aggregate_trade",
            "no_safe_fill_before_cash_market_open",
        }:
            raise ValueError("missing boundary reason is invalid")
        object.__setattr__(self, "missing_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_missing_boundary_projection_v3",
            "schema_version": _SCHEMA_VERSION,
            "hourly_boundary": self.hourly_boundary,
            "next_cash_market_open_or_window_end": self.next_cash_market_open_or_window_end,
            "reason": self.reason,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "missing_hash": self.missing_hash}


@dataclass(frozen=True, slots=True)
class _ValidatedInputs:
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3
    source_events: tuple[MarketEvent, ...]
    selected_lineage: tuple[BinanceUsdmKoruSelectedAggregateTradeLineageV1, ...]
    sessions: tuple[tuple[int, int], ...]
    cash_opens: tuple[int, ...]
    unit_admission_start: int
    missing_prefixes: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class _Assembled:
    source_events: tuple[MarketEvent, ...]
    projection_events: tuple[MarketEvent, ...]
    projection_lineage: tuple[BinanceUsdmKoruFirstRetainedTradeProjectionLineageV3, ...]
    missing_boundaries: tuple[BinanceUsdmKoruMissingBoundaryProjectionV3, ...]
    stream_manifests: tuple[MarketStreamManifest, ...]


class _ProjectionError(ValueError):
    def __init__(
        self, code: BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3, subject: str
    ) -> None:
        self.code = code
        self.subject = subject
        super().__init__(subject)


def _trusted_request(value: object) -> BinanceUsdmKoruTradifiSourceProjectionRequestV3:
    if type(value) is not BinanceUsdmKoruTradifiSourceProjectionRequestV3:
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.INVALID_REQUEST,
            "request",
        )
    request = value
    try:
        rebuilt = BinanceUsdmKoruTradifiSourceProjectionRequestV3(
            request.timeline_window_start,
            request.timeline_window_end_exclusive,
            request.instrument_catalog_hash,
            request.projection_scale,
            request.aggregate_trade_boundary_index_result,
            request.mark_price_results,
            request.index_price_results,
            request.funding_result,
            request.authority_result,
        )
        if not _canonical_equal(rebuilt, request):
            raise ValueError("request mismatch")
        return rebuilt
    except (AttributeError, TypeError, ValueError) as error:
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.INVALID_REQUEST,
            "request",
        ) from error


def _verified_authority(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3,
) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...], int]:
    outcome = verify_koru_tradifi_calendar_unit_authority_v1(
        result=request.authority_result,
        expected_hashes=APPROVED_MEMBER_HASHES,
    )
    if outcome.result is None or not _canonical_equal(
        outcome.result, request.authority_result
    ):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.AUTHORITY_INVALID,
            "authority_result",
        )
    try:
        calendars = (
            request.authority_result.xkrx_calendar.payload,
            request.authority_result.arcx_calendar.payload,
        )
        unit = request.authority_result.post_adjustment_unit_regime.payload
        sessions: list[tuple[int, int]] = []
        for calendar in calendars:
            if not isinstance(calendar, Mapping):
                raise TypeError("calendar payload")
            coverage = calendar["coverage"]
            if not isinstance(coverage, Mapping):
                raise TypeError("calendar coverage")
            if not (
                _iso_ns(coverage["start"])
                <= request.timeline_window_start.epoch_nanoseconds
                < request.timeline_window_end_exclusive.epoch_nanoseconds
                <= _iso_ns(coverage["end_exclusive"])
            ):
                raise ValueError("calendar coverage")
            values = calendar["sessions"]
            if not isinstance(values, tuple):
                raise TypeError("calendar sessions")
            for value in values:
                if not isinstance(value, Mapping):
                    raise TypeError("calendar session")
                sessions.append(
                    (_iso_ns(value["open_utc"]), _iso_ns(value["close_utc"]))
                )
        if not isinstance(unit, Mapping):
            raise TypeError("unit payload")
        admission = unit["authoritative_post_adjustment_admission"]
        if not isinstance(admission, Mapping):
            raise TypeError("unit admission")
        admission_start = _iso_ns(admission["start"])
        admission_end = _iso_ns(admission["end_exclusive"])
        if not (
            admission_start <= request.timeline_window_start.epoch_nanoseconds
            and request.timeline_window_end_exclusive.epoch_nanoseconds <= admission_end
            and type(admission["pre_adjustment_admission"]) is bool
            and not admission["pre_adjustment_admission"]
            and type(admission["cross_regime_admission"]) is bool
            and not admission["cross_regime_admission"]
        ):
            raise ValueError("unit coverage")
        ordered = tuple(sorted(sessions))
        return ordered, tuple(sorted({value[0] for value in ordered})), admission_start
    except (KeyError, TypeError, ValueError) as error:
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.AUTHORITY_INVALID,
            "authority_coverage",
        ) from error


def _contains(sessions: tuple[tuple[int, int], ...], instant: int) -> bool:
    return any(start <= instant < end for start, end in sessions)


def _cash_cutoff(cash_opens: tuple[int, ...], boundary: int, window_end: int) -> int:
    index = bisect_left(cash_opens, boundary + 1)
    return min(cash_opens[index] if index < len(cash_opens) else window_end, window_end)


def _eligible_boundaries(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3,
    sessions: tuple[tuple[int, int], ...],
    cash_opens: tuple[int, ...],
    admission_start: int,
) -> tuple[BinanceUsdmKoruExecutionBoundaryV1, ...]:
    start = request.timeline_window_start.epoch_nanoseconds
    end = request.timeline_window_end_exclusive.epoch_nanoseconds
    first = ((start + _HOUR_NS - 1) // _HOUR_NS) * _HOUR_NS
    missing_prefixes = _missing_prefixes(request.aggregate_trade_boundary_index_result)
    return tuple(
        BinanceUsdmKoruExecutionBoundaryV1(
            UtcInstant(boundary),
            UtcInstant(_cash_cutoff(cash_opens, boundary, end)),
        )
        for boundary in range(first, end, _HOUR_NS)
        if boundary >= admission_start
        and (
            any(
                prefix_start <= boundary < prefix_end
                for prefix_start, prefix_end in missing_prefixes
            )
            or not _contains(sessions, boundary)
        )
    )


def _verified_boundary_index(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3,
    expected_boundaries: tuple[BinanceUsdmKoruExecutionBoundaryV1, ...],
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3:
    result = request.aggregate_trade_boundary_index_result
    index_request = result.request
    if (
        index_request.timeline_window_start != request.timeline_window_start
        or index_request.timeline_window_end_exclusive
        != request.timeline_window_end_exclusive
        or not _canonical_equal(index_request.boundaries, expected_boundaries)
    ):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.AGGREGATE_TRADES_INVALID,
            "aggregate_trade_boundary_index_request",
        )
    try:
        if result.result_digest != canonical_sha256(result._body()):
            raise ValueError("result digest")
    except (AttributeError, TypeError, ValueError) as error:
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.AGGREGATE_TRADES_INVALID,
            "aggregate_trade_boundary_index_result",
        ) from error
    # Boundary V3 is opened/published authority.  Never rebuild or replay captures here.
    return result


def _verified_price_results(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3,
    results: tuple[BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1, ...],
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> tuple[tuple[int, ...], tuple[MarketEvent, ...]]:
    required_grid = _required_price_grid(
        request.timeline_window_start, request.timeline_window_end_exclusive
    )
    if tuple(
        value.capture.request.utc_date for value in results
    ) != _price_result_dates(required_grid):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.PRICE_BARS_INVALID,
            source_kind.value + "_dates",
        )
    grouped: dict[int, list[MarketEvent]] = defaultdict(list)
    for result in results:
        replay = normalize_binance_usdm_koru_price_bars_source_bounded_v1(
            result.capture
        )
        if (
            replay.result is None
            or not _canonical_equal(replay.result, result)
            or result.source_kind != source_kind
            or result.suffix_gap_classification != "unknown_unproven"
            or result.internal_gap_classification != "none_observed_by_contiguous_hours"
        ):
            raise _ProjectionError(
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.PRICE_BARS_INVALID,
                source_kind.value,
            )
        for event in result.events:
            if event.instrument_id != _INSTRUMENT or event.phase != TimelinePhase(
                0, "market_data"
            ):
                raise _ProjectionError(
                    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.SOURCE_CONTEXT_INVALID,
                    event.event_id,
                )
            grouped[cast(int, event.payload["open_time_milliseconds"])].append(event)
    purposes = (
        _MARK_PURPOSES
        if source_kind == BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
        else _INDEX_PURPOSES
    )
    selected: list[MarketEvent] = []
    for completed, opened in required_grid:
        events = grouped.get(opened, [])
        if (
            len(events) != len(purposes)
            or frozenset(event.payload["price_purpose"] for event in events) != purposes
            or any(
                event.payload["source_kind"] != source_kind.value
                or event.event_time.epoch_nanoseconds != completed
                or event.available_time != event.event_time
                or not (
                    request.timeline_window_start
                    <= event.event_time
                    < request.timeline_window_end_exclusive
                )
                for event in events
            )
        ):
            raise _ProjectionError(
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.PRICE_BARS_INVALID,
                f"{source_kind.value}:{opened}",
            )
        selected.extend(events)
    return tuple(completed for completed, _ in required_grid), tuple(selected)


def _verified_funding_result(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3,
) -> tuple[MarketEvent, ...]:
    result = request.funding_result
    replay = normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        result.capture
    )
    start_ns = request.timeline_window_start.epoch_nanoseconds
    end_ns = request.timeline_window_end_exclusive.epoch_nanoseconds
    source_request = result.capture.request
    if (
        replay.result is None
        or not _canonical_equal(replay.result, result)
        or source_request.start_time_milliseconds > start_ns // 1_000_000
        or source_request.end_time_milliseconds < (end_ns - 1) // 1_000_000
        or result.prefix_gap_classification != "unknown_unproven"
        or result.suffix_gap_classification != "unknown_unproven"
        or result.special_count != 0
        or result.missing_rate_type_count != 0
        or result.regular_count != result.row_count
    ):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.FUNDING_INVALID,
            "funding_result",
        )
    events = tuple(
        event
        for event in result.events
        if request.timeline_window_start
        <= event.event_time
        < request.timeline_window_end_exclusive
    )
    if any(
        event.stream_key != _FUNDING_STREAM
        or event.event_type != _FUNDING_EVENT_TYPE
        or event.capability != _FUNDING_CAPABILITY
        or event.instrument_id != _INSTRUMENT
        or event.event_time != event.available_time
        or event.payload["rate_type"] != "Regular"
        for event in events
    ):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.SOURCE_CONTEXT_INVALID,
            "funding_events",
        )
    return events


def _missing_prefixes(
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
) -> tuple[tuple[int, int], ...]:
    return tuple(
        (
            gap.declared_missing_interval_start.epoch_nanoseconds,
            gap.declared_missing_interval_end_exclusive.epoch_nanoseconds,
        )
        for gap in result.aggregate_id_coverage_gaps
    )


def _validate_inputs(value: object) -> _ValidatedInputs:
    request = _trusted_request(value)
    sessions, cash_opens, admission_start = _verified_authority(request)
    boundaries = _eligible_boundaries(request, sessions, cash_opens, admission_start)
    boundary_index = _verified_boundary_index(request, boundaries)
    mark_grid, mark_events = _verified_price_results(
        request,
        request.mark_price_results,
        BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE,
    )
    index_grid, index_events = _verified_price_results(
        request,
        request.index_price_results,
        BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
    )
    if mark_grid != index_grid:
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.PRICE_BARS_INVALID,
            "mark_index_grid",
        )
    funding_events = _verified_funding_result(request)
    source_events = tuple(
        sorted(
            (
                *boundary_index.selected_source_events,
                *mark_events,
                *index_events,
                *funding_events,
            ),
            key=lambda event: (event.stream_key, event.ordering_key, event.event_id),
        )
    )
    if len({event.event_id for event in source_events}) != len(source_events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.SOURCE_CONTEXT_INVALID,
            "duplicate_source_event_id",
        )
    return _ValidatedInputs(
        request,
        source_events,
        boundary_index.selected_lineage,
        sessions,
        cash_opens,
        admission_start,
        _missing_prefixes(boundary_index),
    )


def _price_units(value: object) -> int:
    if type(value) is not str or not value or value.startswith(("+", "-")):
        raise ValueError("aggregate trade price must be exact positive decimal text")
    whole, separator, fraction = value.partition(".")
    if (
        not separator
        or not whole.isdigit()
        or not fraction.isdigit()
        or len(fraction) > 8
        or (len(whole) > 1 and whole.startswith("0"))
    ):
        raise ValueError("aggregate trade price cannot project exactly to scale 8")
    units = int(whole) * 100_000_000 + int(fraction.ljust(8, "0"))
    if units <= 0:
        raise ValueError("aggregate trade price must be positive")
    return units


def _project(
    lineage: BinanceUsdmKoruSelectedAggregateTradeLineageV1,
    boundary_index: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
    source_sequence: int,
) -> tuple[MarketEvent, BinanceUsdmKoruFirstRetainedTradeProjectionLineageV3]:
    source = lineage.source_event
    payload = source.payload
    units = _price_units(lineage.price)
    preimage = {
        "type": "binance_usdm_koru_first_retained_trade_projection_preimage_v3",
        "schema_version": _SCHEMA_VERSION,
        "hourly_boundary": lineage.boundary,
        "next_cash_market_open_or_window_end": lineage.cutoff,
        "source_event_id": source.event_id,
        "source_event_hash": source.event_hash,
        "source_revision_id": source.revision_id,
        "source_event_time": source.event_time,
        "source_available_time": source.available_time,
        "source_key": source.source_key,
        "source_hash": source.source_hash,
        "source_record_hash": lineage.csv_row_hash,
        "source_snapshot_id": lineage.source_snapshot_id,
        "source_snapshot_hash": lineage.source_snapshot_hash,
        "boundary_index_request_hash": boundary_index.request.request_hash,
        "boundary_index_result_digest": boundary_index.result_digest,
        "boundary_index_lineage_hash": lineage.lineage_hash,
        "open_price": {"units": units, "scale": 8, "quote_currency": "USDT"},
    }
    event_identity = canonical_sha256(
        {
            "type": "binance_usdm_koru_first_retained_trade_projection_event_identity_v3",
            "projection": preimage,
        }
    )
    revision_identity = canonical_sha256(
        {
            "type": "binance_usdm_koru_first_retained_trade_projection_revision_identity_v3",
            "projection": preimage,
        }
    )
    source_identity = canonical_sha256(
        {
            "type": "binance_usdm_koru_first_retained_trade_projection_source_identity_v3",
            "projection": preimage,
        }
    )
    event = MarketEvent(
        event_id="binance-usdm-koru-first-retained-trade-bar-open-v3:" + event_identity,
        stream_key=_PROJECTION_STREAM,
        event_type=_PROJECTION_EVENT_TYPE,
        capability=_PROJECTION_CAPABILITY,
        instrument_id=_INSTRUMENT,
        event_time=source.event_time,
        available_time=source.event_time,
        phase=_PROJECTION_PHASE,
        source_sequence=SourceSequence(source_sequence),
        revision_id=revision_identity,
        supersedes_revision_id=None,
        source_key=_PROJECTION_SOURCE_KEY,
        source_hash=source_identity,
        payload={
            "schema_version": 1,
            "bar_kind": "real",
            "open_price": {
                "units": units,
                "scale": 8,
                "quote_currency": "USDT",
            },
        },
    )
    projected_lineage = BinanceUsdmKoruFirstRetainedTradeProjectionLineageV3(
        hourly_boundary=lineage.boundary,
        next_cash_market_open_or_window_end=lineage.cutoff,
        source_event_id=source.event_id,
        source_event_hash=source.event_hash,
        source_revision_id=source.revision_id,
        source_event_time=source.event_time,
        source_available_time=source.available_time,
        source_key=source.source_key,
        source_hash=source.source_hash,
        aggregate_trade_id=lineage.aggregate_trade_id,
        first_trade_id=lineage.first_trade_id,
        last_trade_id=lineage.last_trade_id,
        source_record_hash=lineage.csv_row_hash,
        source_snapshot_id=lineage.source_snapshot_id,
        source_snapshot_hash=lineage.source_snapshot_hash,
        source_provenance_hash=lineage.source_provenance_hash,
        source_member_hash=lineage.source_member_hash,
        source_request_hash=lineage.request_hash,
        source_capture_hash=lineage.capture_hash,
        boundary_index_request_hash=boundary_index.request.request_hash,
        boundary_index_result_digest=boundary_index.result_digest,
        boundary_index_lineage_hash=lineage.lineage_hash,
        open_price_units=units,
        open_price_scale=8,
        projection_event_id=event.event_id,
        projection_event_hash=event.event_hash,
        projection_revision_id=event.revision_id,
        projection_source_key=event.source_key,
        projection_source_hash=event.source_hash,
    )
    if payload["source_record_hash"] != lineage.csv_row_hash:
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.PROJECTION_INVALID,
            source.event_id,
        )
    return event, projected_lineage


def _manifest_from_group(
    stream_key: str, events: tuple[MarketEvent, ...]
) -> MarketStreamManifest:
    if len({event.event_id for event in events}) != len(events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.SOURCE_CONTEXT_INVALID,
            f"duplicate_event_id:{stream_key}",
        )
    if len({event.ordering_key for event in events}) != len(events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.SOURCE_CONTEXT_INVALID,
            f"duplicate_ordering_key:{stream_key}",
        )
    return MarketStreamManifest.from_events(stream_key, events)


def _stream_manifests(
    source_events: tuple[MarketEvent, ...], projection_events: tuple[MarketEvent, ...]
) -> tuple[MarketStreamManifest, ...]:
    events = (*source_events, *projection_events)
    if len({event.event_id for event in events}) != len(events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.SOURCE_CONTEXT_INVALID,
            "duplicate_event_id",
        )
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in events:
        grouped[event.stream_key].append(event)
    manifests = [
        _manifest_from_group(key, tuple(values)) for key, values in grouped.items()
    ]
    if not projection_events:
        manifests.append(
            MarketStreamManifest(
                _PROJECTION_STREAM,
                _PROJECTION_EVENT_TYPE,
                _PROJECTION_CAPABILITY,
                0,
                canonical_sha256(()),
            )
        )
    return tuple(sorted(manifests, key=lambda value: value.stream_key))


def _missing_reason(
    boundary: int,
    cutoff: int,
    window_end: int,
    missing_prefixes: tuple[tuple[int, int], ...],
) -> str:
    if any(start <= boundary < end for start, end in missing_prefixes):
        return "missing_retained_aggregate_trade"
    if cutoff < window_end:
        return "no_safe_fill_before_cash_market_open"
    return "missing_retained_aggregate_trade"


def _assemble(value: object) -> _Assembled:
    validated = _validate_inputs(value)
    request = validated.request
    boundary_index = request.aggregate_trade_boundary_index_result
    projections: list[MarketEvent] = []
    lineages: list[BinanceUsdmKoruFirstRetainedTradeProjectionLineageV3] = []
    for selected in validated.selected_lineage:
        event, lineage = _project(selected, boundary_index, len(projections))
        if event.event_time != event.available_time:
            raise _ProjectionError(
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.PROJECTION_INVALID,
                event.event_id,
            )
        projections.append(event)
        lineages.append(lineage)
    window_end = request.timeline_window_end_exclusive.epoch_nanoseconds
    missing = tuple(
        BinanceUsdmKoruMissingBoundaryProjectionV3(
            value.boundary,
            value.cutoff,
            _missing_reason(
                value.boundary.epoch_nanoseconds,
                value.cutoff.epoch_nanoseconds,
                window_end,
                validated.missing_prefixes,
            ),
        )
        for value in boundary_index.missing_boundaries
    )
    projection_events = tuple(projections)
    return _Assembled(
        source_events=validated.source_events,
        projection_events=projection_events,
        projection_lineage=tuple(lineages),
        missing_boundaries=missing,
        stream_manifests=_stream_manifests(validated.source_events, projection_events),
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionResultV3:
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3
    source_events: tuple[MarketEvent, ...]
    projection_events: tuple[MarketEvent, ...]
    projection_lineage: tuple[BinanceUsdmKoruFirstRetainedTradeProjectionLineageV3, ...]
    missing_boundaries: tuple[BinanceUsdmKoruMissingBoundaryProjectionV3, ...]
    stream_manifests: tuple[MarketStreamManifest, ...]
    xkrx_calendar: ArtifactEnvelope
    arcx_calendar: ArtifactEnvelope
    post_adjustment_unit_regime: ArtifactEnvelope
    xkrx_calendar_ref: ArtifactRef
    arcx_calendar_ref: ArtifactRef
    post_adjustment_unit_regime_ref: ArtifactRef
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
    aggregate_trade_capture_final_evidence: tuple[
        BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3, ...
    ]
    development_only: bool = True
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False
    fragment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        try:
            assembled = _assemble(self.request)
            authority = self.request.authority_result
            boundary_index = self.request.aggregate_trade_boundary_index_result
            if (
                type(self.source_events) is not tuple
                or not _canonical_equal(self.source_events, assembled.source_events)
                or type(self.projection_events) is not tuple
                or not _canonical_equal(
                    self.projection_events, assembled.projection_events
                )
                or type(self.projection_lineage) is not tuple
                or not _canonical_equal(
                    self.projection_lineage, assembled.projection_lineage
                )
                or type(self.missing_boundaries) is not tuple
                or not _canonical_equal(
                    self.missing_boundaries, assembled.missing_boundaries
                )
                or type(self.stream_manifests) is not tuple
                or not _canonical_equal(
                    self.stream_manifests, assembled.stream_manifests
                )
                or type(self.xkrx_calendar) is not ArtifactEnvelope
                or not _canonical_equal(self.xkrx_calendar, authority.xkrx_calendar)
                or type(self.arcx_calendar) is not ArtifactEnvelope
                or not _canonical_equal(self.arcx_calendar, authority.arcx_calendar)
                or type(self.post_adjustment_unit_regime) is not ArtifactEnvelope
                or not _canonical_equal(
                    self.post_adjustment_unit_regime,
                    authority.post_adjustment_unit_regime,
                )
                or type(self.xkrx_calendar_ref) is not ArtifactRef
                or not _canonical_equal(
                    self.xkrx_calendar_ref, authority.xkrx_calendar_ref
                )
                or type(self.arcx_calendar_ref) is not ArtifactRef
                or not _canonical_equal(
                    self.arcx_calendar_ref, authority.arcx_calendar_ref
                )
                or type(self.post_adjustment_unit_regime_ref) is not ArtifactRef
                or not _canonical_equal(
                    self.post_adjustment_unit_regime_ref,
                    authority.post_adjustment_unit_regime_ref,
                )
                or self.aggregate_trade_boundary_index_request_hash
                != boundary_index.request.request_hash
                or self.aggregate_trade_boundary_index_result_digest
                != boundary_index.result_digest
                or self.aggregate_trade_streamed_reconstruction_digest
                != boundary_index.streamed_reconstruction_digest
                or type(self.aggregate_trade_intra_day_raw_id_gap_stream)
                is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
                or not _canonical_equal(
                    self.aggregate_trade_intra_day_raw_id_gap_stream,
                    boundary_index.intra_day_raw_id_gap_stream,
                )
                or type(self.aggregate_trade_cross_date_raw_id_gap_stream)
                is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
                or not _canonical_equal(
                    self.aggregate_trade_cross_date_raw_id_gap_stream,
                    boundary_index.cross_date_raw_id_gap_stream,
                )
                or type(self.aggregate_trade_coverage_gaps) is not tuple
                or not _canonical_equal(
                    self.aggregate_trade_coverage_gaps,
                    boundary_index.aggregate_id_coverage_gaps,
                )
                or type(self.aggregate_trade_capture_final_evidence) is not tuple
                or any(
                    type(value) is not BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3
                    for value in self.aggregate_trade_capture_final_evidence
                )
                or not _canonical_equal(
                    self.aggregate_trade_capture_final_evidence,
                    boundary_index.capture_final_evidence,
                )
                or type(self.development_only) is not bool
                or not self.development_only
                or type(self.decision_grade_eligible) is not bool
                or self.decision_grade_eligible
                or type(self.deployment_authorized) is not bool
                or self.deployment_authorized
            ):
                raise ValueError("source-projection result binding mismatch")
        except _ProjectionError as error:
            raise ValueError(
                "source-projection result cannot replay request"
            ) from error
        object.__setattr__(self, "fragment_digest", canonical_sha256(self._body()))

    @property
    def projection_stream_manifest(self) -> MarketStreamManifest:
        return next(
            value
            for value in self.stream_manifests
            if value.stream_key == _PROJECTION_STREAM
        )

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_source_projection_result_v3",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_hash": self.request.request_hash,
            "source_events": self.source_events,
            "projection_events": self.projection_events,
            "projection_lineage": self.projection_lineage,
            "missing_boundaries": self.missing_boundaries,
            "stream_manifests": self.stream_manifests,
            "authority_envelopes": (
                self.xkrx_calendar,
                self.arcx_calendar,
                self.post_adjustment_unit_regime,
            ),
            "authority_refs": (
                self.xkrx_calendar_ref,
                self.arcx_calendar_ref,
                self.post_adjustment_unit_regime_ref,
            ),
            "aggregate_trade_boundary_index_request_hash": self.aggregate_trade_boundary_index_request_hash,
            "aggregate_trade_boundary_index_result_digest": self.aggregate_trade_boundary_index_result_digest,
            "aggregate_trade_streamed_reconstruction_digest": self.aggregate_trade_streamed_reconstruction_digest,
            "aggregate_trade_intra_day_raw_id_gap_stream": self.aggregate_trade_intra_day_raw_id_gap_stream,
            "aggregate_trade_cross_date_raw_id_gap_stream": self.aggregate_trade_cross_date_raw_id_gap_stream,
            "aggregate_trade_coverage_gaps": self.aggregate_trade_coverage_gaps,
            "aggregate_trade_capture_final_evidence": self.aggregate_trade_capture_final_evidence,
            "limitations": _LIMITATIONS,
            "source_normalization_hashes": (
                tuple(
                    value.normalization_hash
                    for value in self.request.mark_price_results
                )
                + tuple(
                    value.normalization_hash
                    for value in self.request.index_price_results
                )
                + (self.request.funding_result.normalization_hash,)
            ),
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "fragment_digest": self.fragment_digest}


def _authority_type_registry_v3() -> dict[str, type[object]]:
    """Whitelist the exact model types needed to replay a V3 result."""

    from crypto_quant_domain import artifacts, instruments, time
    from crypto_quant_domain.numeric import scales
    from crypto_quant_market_data import bundles

    from . import (
        binance_usdm_koru_aggtrade_boundary_index_v1,
        binance_usdm_koru_aggtrades_source_bounded_v1,
        binance_usdm_koru_funding_rate_history_source_bounded_v1,
        binance_usdm_koru_price_bars_source_bounded_v1,
        koru_tradifi_calendar_unit_authority_v1,
        source_snapshots,
    )

    registry: dict[str, type[object]] = {}
    for module in (
        artifacts,
        instruments,
        time,
        scales,
        bundles,
        binance_usdm_koru_aggtrade_boundary_index_v1,
        binance_usdm_koru_aggtrades_source_bounded_v1,
        binance_usdm_koru_funding_rate_history_source_bounded_v1,
        binance_usdm_koru_price_bars_source_bounded_v1,
        koru_tradifi_calendar_unit_authority_v1,
        source_snapshots,
    ):
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and value.__module__ == module.__name__
                and (is_dataclass(value) or issubclass(value, Enum))
            ):
                registry[f"{value.__module__}.{value.__qualname__}"] = value
    for value in (
        BinanceUsdmKoruTradifiSourceProjectionRequestV3,
        BinanceUsdmKoruTradifiSourceProjectionResultV3,
        BinanceUsdmKoruFirstRetainedTradeProjectionLineageV3,
        BinanceUsdmKoruMissingBoundaryProjectionV3,
    ):
        registry[f"{__name__}.{value.__qualname__}"] = value
    return registry


def _authority_encode_v3(value: object) -> dict[str, object]:
    registry = _authority_type_registry_v3()

    def encode(item: object) -> dict[str, object]:
        if item is None or type(item) in (bool, int, str):
            return {"kind": "scalar", "value": item}
        if type(item) is bytes:
            return {
                "kind": "bytes",
                "base64": base64.b64encode(item).decode("ascii"),
            }
        if isinstance(item, Enum):
            type_id = f"{type(item).__module__}.{type(item).__qualname__}"
            if registry.get(type_id) is not type(item):
                raise TypeError("source authority contains an unsupported enum")
            return {"kind": "enum", "type": type_id, "value": item.value}
        if type(item) is tuple:
            return {"kind": "tuple", "items": [encode(child) for child in item]}
        if isinstance(item, Mapping):
            keys = tuple(sorted(item))
            if any(type(key) is not str for key in keys):
                raise TypeError("source authority mappings must use string keys")
            return {
                "kind": "mapping",
                "items": [[key, encode(item[key])] for key in keys],
            }
        if is_dataclass(item) and not isinstance(item, type):
            type_id = f"{type(item).__module__}.{type(item).__qualname__}"
            if registry.get(type_id) is not type(item):
                raise TypeError("source authority contains an unsupported model")
            return {
                "kind": "model",
                "type": type_id,
                "fields": [
                    [item_field.name, encode(getattr(item, item_field.name))]
                    for item_field in fields(item)
                    if item_field.init
                ],
            }
        raise TypeError("source authority contains an unsupported value")

    return encode(value)


def _authority_decode_v3(value: object) -> object:
    registry = _authority_type_registry_v3()

    def exact(value: object, keys: frozenset[str]) -> dict[str, object]:
        if type(value) is not dict or set(value) != keys:
            raise ValueError("source authority serialization schema mismatch")
        return value

    def decode(item: object) -> object:
        if type(item) is not dict or type(item.get("kind")) is not str:
            raise ValueError("source authority serialization schema mismatch")
        kind = item["kind"]
        expected_keys = {
            "scalar": frozenset({"kind", "value"}),
            "bytes": frozenset({"kind", "base64"}),
            "enum": frozenset({"kind", "type", "value"}),
            "tuple": frozenset({"kind", "items"}),
            "mapping": frozenset({"kind", "items"}),
            "model": frozenset({"kind", "type", "fields"}),
        }.get(kind)
        if expected_keys is None:
            raise ValueError("source authority serialization schema mismatch")
        node = exact(item, expected_keys)
        if kind == "scalar":
            if node["value"] is None or type(node["value"]) in (bool, int, str):
                return node["value"]
        elif kind == "bytes":
            encoded = node["base64"]
            if type(encoded) is str:
                try:
                    decoded_bytes = base64.b64decode(encoded, validate=True)
                except ValueError as error:
                    raise ValueError("source authority bytes are invalid") from error
                if base64.b64encode(decoded_bytes).decode("ascii") == encoded:
                    return decoded_bytes
        elif kind == "enum":
            type_id, enum_value = node["type"], node["value"]
            enum_type = registry.get(type_id) if type(type_id) is str else None
            if enum_type is not None and issubclass(enum_type, Enum):
                return enum_type(enum_value)
        elif kind == "tuple":
            if type(node["items"]) is list:
                return tuple(decode(child) for child in node["items"])
        elif kind == "mapping":
            entries = node["items"]
            if type(entries) is list:
                decoded_mapping: dict[str, object] = {}
                previous = ""
                for entry in entries:
                    if (
                        type(entry) is not list
                        or len(entry) != 2
                        or type(entry[0]) is not str
                        or entry[0] <= previous
                    ):
                        raise ValueError("source authority mapping order is invalid")
                    previous = entry[0]
                    decoded_mapping[entry[0]] = decode(entry[1])
                return decoded_mapping
        elif kind == "model":
            type_id = node["type"]
            model_type = registry.get(type_id) if type(type_id) is str else None
            model_fields = node["fields"]
            if (
                model_type is not None
                and is_dataclass(model_type)
                and type(model_fields) is list
            ):
                expected = tuple(
                    item_field.name
                    for item_field in fields(model_type)
                    if item_field.init
                )
                if (
                    len(model_fields) != len(expected)
                    or any(
                        type(entry) is not list
                        or len(entry) != 2
                        or type(entry[0]) is not str
                        for entry in model_fields
                    )
                    or tuple(entry[0] for entry in model_fields) != expected
                ):
                    raise ValueError("source authority model field order is invalid")
                return model_type(
                    **{entry[0]: decode(entry[1]) for entry in model_fields}
                )
        raise ValueError("source authority serialization value is invalid")

    return decode(value)


def _discovery_scope_v3(
    result: BinanceUsdmKoruTradifiSourceProjectionResultV3,
) -> dict[str, object]:
    request = result.request
    return {
        "timeline_window_start": request.timeline_window_start.to_canonical_dict(),
        "timeline_window_end_exclusive": (
            request.timeline_window_end_exclusive.to_canonical_dict()
        ),
    }


def _boundary_index_identity_v3(
    result: BinanceUsdmKoruTradifiSourceProjectionResultV3,
) -> dict[str, object]:
    return json.loads(
        canonical_bytes(
            {
                "request_hash": result.aggregate_trade_boundary_index_request_hash,
                "result_digest": result.aggregate_trade_boundary_index_result_digest,
                "capture_final_evidence": tuple(
                    value.to_canonical_dict()
                    for value in result.aggregate_trade_capture_final_evidence
                ),
            }
        ).decode("utf-8")
    )


def _source_projection_authority_payload_v3(
    result: BinanceUsdmKoruTradifiSourceProjectionResultV3,
) -> dict[str, object]:
    trusted = _trusted_result(result)
    if trusted is None:
        raise ValueError("result must be an exact canonical source-projection result")
    return {
        "type": KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V3,
        "schema_version": KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V3,
        "builder": {
            "id": _AUTHORITY_BUILDER_ID_V3,
            "source_projection_type": (
                "binance_usdm_koru_tradifi_source_projection_result_v3"
            ),
            "source_projection_schema_version": _SCHEMA_VERSION,
        },
        "discovery_scope": _discovery_scope_v3(trusted),
        "source_fragment_digest": trusted.fragment_digest,
        "boundary_index_identity": _boundary_index_identity_v3(trusted),
        "source_projection": _authority_encode_v3(trusted),
    }


def create_binance_usdm_koru_tradifi_source_projection_authority_v3(
    result: BinanceUsdmKoruTradifiSourceProjectionResultV3,
) -> tuple[ArtifactEnvelope, ArtifactRef]:
    """Create the versioned, replayable authority envelope for an exact V3 result."""

    envelope = ArtifactEnvelope.create(
        KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V3,
        KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V3,
        _source_projection_authority_payload_v3(result),
    )
    ref = ArtifactRef.from_envelope(envelope)
    if ref.content_hash == result.fragment_digest:
        raise ValueError(
            "authority artifact identity must differ from fragment identity"
        )
    return envelope, ref


def serialize_binance_usdm_koru_tradifi_source_projection_authority_v3(
    result: BinanceUsdmKoruTradifiSourceProjectionResultV3,
) -> bytes:
    """Return the exact canonical authority envelope bytes for a V3 result."""

    envelope, _ = create_binance_usdm_koru_tradifi_source_projection_authority_v3(
        result
    )
    return canonical_bytes(envelope)


def _authority_envelope_from_bytes_v3(source: bytes) -> ArtifactEnvelope:
    if type(source) is not bytes:
        raise TypeError("source authority envelope must be bytes")
    try:
        value = json.loads(source.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("source authority envelope is not canonical JSON") from error
    if type(value) is not dict or canonical_bytes(value) != source:
        raise ValueError("source authority envelope must use exact canonical bytes")
    try:
        envelope = ArtifactEnvelope(
            artifact_type=value["artifact_type"],
            schema_version=value["schema_version"],
            payload=value["payload"],
            content_hash=value["content_hash"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("source authority envelope is invalid") from error
    if (
        set(value) != {"artifact_type", "schema_version", "payload", "content_hash"}
        or canonical_bytes(envelope) != source
    ):
        raise ValueError("source authority envelope is invalid")
    return envelope


def open_binance_usdm_koru_tradifi_source_projection_authority_v3(
    source: bytes,
) -> BinanceUsdmKoruTradifiSourceProjectionResultV3:
    """Open canonical authority bytes only after typed V3 replay and identity checks."""

    envelope = _authority_envelope_from_bytes_v3(source)
    if (
        envelope.artifact_type
        != KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V3
        or envelope.schema_version
        != KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V3
    ):
        raise ValueError("source authority envelope schema is unsupported")
    payload = json.loads(canonical_bytes(envelope.payload).decode("utf-8"))
    if type(payload) is not dict or set(payload) != _AUTHORITY_PAYLOAD_FIELDS_V3:
        raise ValueError("source authority payload schema is invalid")
    if (
        payload["type"]
        != KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_ARTIFACT_TYPE_V3
        or payload["schema_version"]
        != KORU_TRADIFI_SOURCE_PROJECTION_AUTHORITY_SCHEMA_VERSION_V3
        or type(payload["builder"]) is not dict
        or set(payload["builder"]) != _AUTHORITY_BUILDER_FIELDS_V3
        or payload["builder"]
        != {
            "id": _AUTHORITY_BUILDER_ID_V3,
            "source_projection_type": (
                "binance_usdm_koru_tradifi_source_projection_result_v3"
            ),
            "source_projection_schema_version": _SCHEMA_VERSION,
        }
        or type(payload["discovery_scope"]) is not dict
        or set(payload["discovery_scope"]) != _AUTHORITY_SCOPE_FIELDS_V3
    ):
        raise ValueError("source authority payload identity is invalid")
    try:
        rebuilt = _authority_decode_v3(payload["source_projection"])
    except (IndexError, RecursionError, TypeError, ValueError) as error:
        raise ValueError("source authority cannot reconstruct typed result") from error
    if type(rebuilt) is not BinanceUsdmKoruTradifiSourceProjectionResultV3:
        raise ValueError("source authority result type is invalid")
    trusted = _trusted_result(rebuilt)
    if trusted is None:
        raise ValueError("source authority result does not pass trusted V3 replay")
    if (
        type(payload["source_fragment_digest"]) is not str
        or payload["source_fragment_digest"] != trusted.fragment_digest
        or payload["discovery_scope"] != _discovery_scope_v3(trusted)
        or payload["boundary_index_identity"] != _boundary_index_identity_v3(trusted)
        or ArtifactRef.from_envelope(envelope).content_hash == trusted.fragment_digest
    ):
        raise ValueError("source authority identity binding is invalid")
    return trusted



_TRUSTED_RESULT_CACHE_CAPACITY = 8
_TRUSTED_RESULT_CACHE: OrderedDict[
    int,
    tuple[
        BinanceUsdmKoruTradifiSourceProjectionResultV3,
        BinanceUsdmKoruTradifiSourceProjectionResultV3,
        tuple[object, ...],
    ],
] = OrderedDict()
_TRUSTED_RESULT_CACHE_HITS = 0
_TRUSTED_RESULT_CACHE_MISSES = 0


def _reset_trusted_result_cache_for_test() -> None:
    global _TRUSTED_RESULT_CACHE_HITS, _TRUSTED_RESULT_CACHE_MISSES
    _TRUSTED_RESULT_CACHE.clear()
    _TRUSTED_RESULT_CACHE_HITS = 0
    _TRUSTED_RESULT_CACHE_MISSES = 0


def _trusted_result_cache_stats_for_test() -> tuple[int, int, int]:
    return (
        len(_TRUSTED_RESULT_CACHE),
        _TRUSTED_RESULT_CACHE_HITS,
        _TRUSTED_RESULT_CACHE_MISSES,
    )


def _trusted_result_state_guard(
    value: BinanceUsdmKoruTradifiSourceProjectionResultV3,
) -> tuple[object, ...]:
    guarded: list[object] = []
    seen: set[int] = set()

    def visit(item: object) -> None:
        if id(item) in seen:
            return
        seen.add(id(item))
        guarded.append(item)
        if is_dataclass(item) and not isinstance(item, type):
            for item_field in fields(item):
                visit(getattr(item, item_field.name))
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
        elif isinstance(item, (set, frozenset)):
            for child in sorted(item, key=_trusted_result_identity_order):
                visit(child)
        elif isinstance(item, Mapping):
            for key, child in sorted(
                item.items(), key=lambda entry: _trusted_result_identity_order(entry[0])
            ):
                visit(key)
                visit(child)
        elif type(item).__module__.startswith("crypto_quant_"):
            for slot in _trusted_result_slot_names(type(item)):
                try:
                    visit(getattr(item, slot))
                except AttributeError:
                    continue

    visit(value)
    return tuple(guarded)


def _trusted_result_identity_order(value: object) -> tuple[str, str, int]:
    value_type = type(value)
    return value_type.__module__, value_type.__qualname__, id(value)


def _trusted_result_slot_names(value_type: type[object]) -> tuple[str, ...]:
    return tuple(
        slot
        for base in reversed(value_type.__mro__)
        for slot in (
            (base.__dict__["__slots__"],)
            if isinstance(base.__dict__.get("__slots__"), str)
            else base.__dict__.get("__slots__", ())
        )
        if slot not in {"__dict__", "__weakref__"}
    )


def _trusted_result(
    value: object,
) -> BinanceUsdmKoruTradifiSourceProjectionResultV3 | None:
    global _TRUSTED_RESULT_CACHE_HITS, _TRUSTED_RESULT_CACHE_MISSES
    if type(value) is not BinanceUsdmKoruTradifiSourceProjectionResultV3:
        return None
    key = id(value)
    cached = _TRUSTED_RESULT_CACHE.get(key)
    if cached is not None:
        try:
            current_state = _trusted_result_state_guard(value)
        except AttributeError:
            current_state = ()
        if (
            cached[0] is value
            and len(current_state) == len(cached[2])
            and all(
                current is saved
                for current, saved in zip(current_state, cached[2], strict=True)
            )
        ):
            _TRUSTED_RESULT_CACHE.move_to_end(key)
            _TRUSTED_RESULT_CACHE_HITS += 1
            return cached[1]
        _TRUSTED_RESULT_CACHE.pop(key)
    _TRUSTED_RESULT_CACHE_MISSES += 1
    result = value
    try:
        rebuilt = BinanceUsdmKoruTradifiSourceProjectionResultV3(
            request=result.request,
            source_events=result.source_events,
            projection_events=result.projection_events,
            projection_lineage=result.projection_lineage,
            missing_boundaries=result.missing_boundaries,
            stream_manifests=result.stream_manifests,
            xkrx_calendar=result.xkrx_calendar,
            arcx_calendar=result.arcx_calendar,
            post_adjustment_unit_regime=result.post_adjustment_unit_regime,
            xkrx_calendar_ref=result.xkrx_calendar_ref,
            arcx_calendar_ref=result.arcx_calendar_ref,
            post_adjustment_unit_regime_ref=result.post_adjustment_unit_regime_ref,
            aggregate_trade_boundary_index_request_hash=(
                result.aggregate_trade_boundary_index_request_hash
            ),
            aggregate_trade_boundary_index_result_digest=(
                result.aggregate_trade_boundary_index_result_digest
            ),
            aggregate_trade_streamed_reconstruction_digest=(
                result.aggregate_trade_streamed_reconstruction_digest
            ),
            aggregate_trade_intra_day_raw_id_gap_stream=(
                result.aggregate_trade_intra_day_raw_id_gap_stream
            ),
            aggregate_trade_cross_date_raw_id_gap_stream=(
                result.aggregate_trade_cross_date_raw_id_gap_stream
            ),
            aggregate_trade_coverage_gaps=result.aggregate_trade_coverage_gaps,
            aggregate_trade_capture_final_evidence=(
                result.aggregate_trade_capture_final_evidence
            ),
            development_only=result.development_only,
            decision_grade_eligible=result.decision_grade_eligible,
            deployment_authorized=result.deployment_authorized,
        )
        if not _canonical_equal(
            rebuilt, result
        ) or result.fragment_digest != canonical_sha256(result._body()):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    _TRUSTED_RESULT_CACHE[key] = (
        result,
        rebuilt,
        _trusted_result_state_guard(result),
    )
    _TRUSTED_RESULT_CACHE.move_to_end(key)
    if len(_TRUSTED_RESULT_CACHE) > _TRUSTED_RESULT_CACHE_CAPACITY:
        _TRUSTED_RESULT_CACHE.popitem(last=False)
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionOutcomeV3:
    result: BinanceUsdmKoruTradifiSourceProjectionResultV3 | None = None
    failure: BinanceUsdmKoruTradifiSourceProjectionFailureV3 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError(
                "result must be an exact canonical source-projection result"
            )
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruTradifiSourceProjectionFailureV3
        ):
            raise TypeError("failure must be exact source-projection failure")


def _failed(
    code: BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3, subject: str
) -> BinanceUsdmKoruTradifiSourceProjectionOutcomeV3:
    return BinanceUsdmKoruTradifiSourceProjectionOutcomeV3(
        failure=BinanceUsdmKoruTradifiSourceProjectionFailureV3(code, subject)
    )


def build_binance_usdm_koru_tradifi_source_projection_v3(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV3,
) -> BinanceUsdmKoruTradifiSourceProjectionOutcomeV3:
    try:
        trusted = _trusted_request(request)
        assembled = _assemble(trusted)
        authority = trusted.authority_result
        boundary_index = trusted.aggregate_trade_boundary_index_result
        result = BinanceUsdmKoruTradifiSourceProjectionResultV3(
            request=trusted,
            source_events=assembled.source_events,
            projection_events=assembled.projection_events,
            projection_lineage=assembled.projection_lineage,
            missing_boundaries=assembled.missing_boundaries,
            stream_manifests=assembled.stream_manifests,
            xkrx_calendar=authority.xkrx_calendar,
            arcx_calendar=authority.arcx_calendar,
            post_adjustment_unit_regime=authority.post_adjustment_unit_regime,
            xkrx_calendar_ref=authority.xkrx_calendar_ref,
            arcx_calendar_ref=authority.arcx_calendar_ref,
            post_adjustment_unit_regime_ref=authority.post_adjustment_unit_regime_ref,
            aggregate_trade_boundary_index_request_hash=boundary_index.request.request_hash,
            aggregate_trade_boundary_index_result_digest=boundary_index.result_digest,
            aggregate_trade_streamed_reconstruction_digest=(
                boundary_index.streamed_reconstruction_digest
            ),
            aggregate_trade_intra_day_raw_id_gap_stream=(
                boundary_index.intra_day_raw_id_gap_stream
            ),
            aggregate_trade_cross_date_raw_id_gap_stream=(
                boundary_index.cross_date_raw_id_gap_stream
            ),
            aggregate_trade_coverage_gaps=boundary_index.aggregate_id_coverage_gaps,
            aggregate_trade_capture_final_evidence=(
                boundary_index.capture_final_evidence
            ),
        )
    except _ProjectionError as error:
        return _failed(error.code, error.subject)
    except (KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.RESULT_INVALID,
            type(error).__name__,
        )
    return BinanceUsdmKoruTradifiSourceProjectionOutcomeV3(result=result)


def build_binance_usdm_koru_source_profile_authority_v3(
    result: BinanceUsdmKoruTradifiSourceProjectionResultV3,
) -> tuple[ArtifactEnvelope, ArtifactRef]:
    """Derive the V3 source-profile authority from a replayed V3 source result."""
    trusted = _trusted_result(result)
    if trusted is None:
        raise ValueError("result must be an exact canonical source-projection result")
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in trusted.source_events:
        grouped[event.stream_key].append(event)
    source_manifests = tuple(
        MarketStreamManifest.from_events(stream_key, tuple(events))
        for stream_key, events in sorted(grouped.items())
    )
    payload = {
        "type": "binance_usdm_koru_source_profile_authority_v3",
        "schema_version": _SCHEMA_VERSION,
        "timeline_window": {
            "data_start": trusted.request.timeline_window_start,
            "trading_start": trusted.request.timeline_window_start,
            "end_exclusive": trusted.request.timeline_window_end_exclusive,
        },
        "source_projection_request_hash": trusted.request.request_hash,
        "source_fragment_digest": trusted.fragment_digest,
        "source_projection_authority_ref": create_binance_usdm_koru_tradifi_source_projection_authority_v3(trusted)[1],
        "aggregate_trade_boundary_index_request_hash": trusted.aggregate_trade_boundary_index_request_hash,
        "aggregate_trade_boundary_index_result_digest": trusted.aggregate_trade_boundary_index_result_digest,
        "aggregate_trade_streamed_reconstruction_digest": trusted.aggregate_trade_streamed_reconstruction_digest,
        "aggregate_trade_intra_day_raw_id_gap_stream": trusted.aggregate_trade_intra_day_raw_id_gap_stream.to_canonical_dict(),
        "aggregate_trade_cross_date_raw_id_gap_stream": trusted.aggregate_trade_cross_date_raw_id_gap_stream.to_canonical_dict(),
        "aggregate_trade_coverage_gaps": tuple(value.to_canonical_dict() for value in trusted.aggregate_trade_coverage_gaps),
        "aggregate_trade_capture_final_evidence": tuple(value.to_canonical_dict() for value in trusted.aggregate_trade_capture_final_evidence),
        "missing_boundaries": tuple(value.to_canonical_dict() for value in trusted.missing_boundaries),
        "source_stream_manifests": tuple(value.to_canonical_dict() for value in source_manifests),
        "source_event_bindings": tuple(
            {"stream_key": event.stream_key, "event_id": event.event_id, "event_hash": event.event_hash}
            for event in trusted.source_events
        ),
        "execution_projection_stream_manifest": trusted.projection_stream_manifest.to_canonical_dict(),
        "execution_projection_event_bindings": tuple(
            sorted(
                (
                    {"stream_key": event.stream_key, "event_id": event.event_id, "event_hash": event.event_hash}
                    for event in trusted.projection_events
                ),
                key=lambda value: (value["stream_key"], value["event_id"], value["event_hash"]),
            )
        ),
        "xkrx_calendar_ref": trusted.xkrx_calendar_ref,
        "arcx_calendar_ref": trusted.arcx_calendar_ref,
        "post_adjustment_unit_regime_ref": trusted.post_adjustment_unit_regime_ref,
        "development_only": trusted.development_only,
        "decision_grade_eligible": trusted.decision_grade_eligible,
        "deployment_authorized": trusted.deployment_authorized,
    }
    envelope = ArtifactEnvelope.create(
        _SOURCE_PROFILE_AUTHORITY_ARTIFACT_TYPE_V3, _SCHEMA_VERSION, payload
    )
    return envelope, ArtifactRef.from_envelope(envelope)
