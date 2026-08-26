"""Sealed KORU source verification and first-retained-trade projection fragment."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
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

from .binance_usdm_koru_aggtrades_source_bounded_v1 import (
    BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1,
    BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1,
    normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1,
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

_SCHEMA_VERSION = 1
_HOUR_NS = 3_600_000_000_000
_DAY_NS = 86_400_000_000_000
_ALLOWED_START = 1_784_109_600_000_000_000
_FIRST_PRICE_COMPLETION = _ALLOWED_START + _HOUR_NS
_ALLOWED_END_EXCLUSIVE = 1_791_158_400_000_000_000
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_AGG_STREAM = "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1"
_AGG_EVENT_TYPE = "binance_usdm_koru_aggregate_trade.v1"
_AGG_CAPABILITY = MarketBundleCapability(
    "price.aggregate_trade.koru-usdt-tradifi-perpetual", 1
)
_FUNDING_STREAM = "binance_usdm.funding_history.publications.koruusdt.v1"
_FUNDING_EVENT_TYPE = "binance_usdm_koru_funding_history_publication_v1"
_FUNDING_CAPABILITY = MarketBundleCapability("binance_usdm.funding-publications", 1)
_PROJECTION_STREAM = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v1"
)
_PROJECTION_EVENT_TYPE = "bar_open"
_PROJECTION_CAPABILITY = MarketBundleCapability("bar_open", 1)
_PROJECTION_PHASE = TimelinePhase(20, "bar_open")
_PROJECTION_SOURCE_KEY = (
    "binance_usdm.tradifi.first_retained_aggregate_trade_projection.koruusdt.1h.v1"
)
_MARK_PURPOSES = frozenset({"strategy", "valuation", "margin", "liquidation"})
_INDEX_PURPOSES = frozenset({"strategy"})
_EPOCH_DATE = date(1970, 1, 1)


def _hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(digit not in "0123456789abcdef" for digit in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


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


def _requested_dates(start: UtcInstant, end: UtcInstant) -> tuple[str, ...]:
    first = start.epoch_nanoseconds // _DAY_NS
    last = (end.epoch_nanoseconds - 1) // _DAY_NS
    return tuple(
        (_EPOCH_DATE + timedelta(days=value)).isoformat()
        for value in range(first, last + 1)
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


def _canonical_equal(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionRequestV1:
    timeline_window_start: UtcInstant
    timeline_window_end_exclusive: UtcInstant
    instrument_catalog_hash: str
    projection_scale: Scale
    aggregate_trade_results: tuple[
        BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1, ...
    ]
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
            type(self.aggregate_trade_results) is not tuple
            or not self.aggregate_trade_results
            or any(
                type(value)
                is not BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1
                for value in self.aggregate_trade_results
            )
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
        ):
            raise TypeError("daily normalization results must be exact tuples")
        if (
            type(self.funding_result)
            is not BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1
            or type(self.authority_result)
            is not KoruTradifiCalendarUnitAuthorityResultV1
        ):
            raise TypeError(
                "funding and authority results must be exact accepted results"
            )

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_source_projection_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "timeline_window_start": self.timeline_window_start,
            "timeline_window_end_exclusive": self.timeline_window_end_exclusive,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "projection_scale": self.projection_scale.places,
            "aggregate_trade_results": self.aggregate_trade_results,
            "mark_price_results": self.mark_price_results,
            "index_price_results": self.index_price_results,
            "funding_result": self.funding_result,
            "authority_result": self.authority_result,
        }


class BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1(str, Enum):
    INVALID_REQUEST = "invalid_request"
    AUTHORITY_INVALID = "authority_invalid"
    AGGREGATE_TRADES_INVALID = "aggregate_trades_invalid"
    PRICE_BARS_INVALID = "price_bars_invalid"
    FUNDING_INVALID = "funding_invalid"
    SOURCE_CONTEXT_INVALID = "source_context_invalid"
    PROJECTION_INVALID = "projection_invalid"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionFailureV1:
    code: BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1
    subject: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1:
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
            "type": "binance_usdm_koru_tradifi_source_projection_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1:
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
    source_normalization_hash: str
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
            "source_normalization_hash",
            "projection_event_hash",
            "projection_source_hash",
        ):
            _hash(name, getattr(self, name))
        object.__setattr__(self, "lineage_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_first_retained_trade_projection_lineage_v1",
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
            "source_normalization_hash": self.source_normalization_hash,
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
class BinanceUsdmKoruMissingBoundaryProjectionV1:
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
            "type": "binance_usdm_koru_missing_boundary_projection_v1",
            "schema_version": _SCHEMA_VERSION,
            "hourly_boundary": self.hourly_boundary,
            "next_cash_market_open_or_window_end": self.next_cash_market_open_or_window_end,
            "reason": self.reason,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "missing_hash": self.missing_hash}


@dataclass(frozen=True, slots=True)
class _ValidatedInputs:
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV1
    source_events: tuple[MarketEvent, ...]
    aggregate_events: tuple[MarketEvent, ...]
    aggregate_lineage: Mapping[
        str, BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1
    ]
    aggregate_trade_cross_date_raw_id_gaps: tuple[
        BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1, ...
    ]
    aggregate_trade_missing_prefixes: tuple[tuple[int, int], ...]
    sessions: tuple[tuple[int, int], ...]
    cash_opens: tuple[int, ...]
    unit_admission_start: int


@dataclass(frozen=True, slots=True)
class _Assembled:
    source_events: tuple[MarketEvent, ...]
    projection_events: tuple[MarketEvent, ...]
    projection_lineage: tuple[BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1, ...]
    missing_boundaries: tuple[BinanceUsdmKoruMissingBoundaryProjectionV1, ...]
    stream_manifests: tuple[MarketStreamManifest, ...]
    aggregate_trade_cross_date_raw_id_gaps: tuple[
        BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1, ...
    ]


class _ProjectionError(ValueError):
    def __init__(
        self, code: BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1, subject: str
    ) -> None:
        self.code = code
        self.subject = subject
        super().__init__(subject)


def _trusted_request(value: object) -> BinanceUsdmKoruTradifiSourceProjectionRequestV1:
    if type(value) is not BinanceUsdmKoruTradifiSourceProjectionRequestV1:
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.INVALID_REQUEST,
            "request",
        )
    request = value
    try:
        rebuilt = BinanceUsdmKoruTradifiSourceProjectionRequestV1(
            request.timeline_window_start,
            request.timeline_window_end_exclusive,
            request.instrument_catalog_hash,
            request.projection_scale,
            request.aggregate_trade_results,
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
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.INVALID_REQUEST,
            "request",
        ) from error


def _verified_authority(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV1,
) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...], int]:
    outcome = verify_koru_tradifi_calendar_unit_authority_v1(
        result=request.authority_result,
        expected_hashes=APPROVED_MEMBER_HASHES,
    )
    if outcome.result is None or not _canonical_equal(
        outcome.result, request.authority_result
    ):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AUTHORITY_INVALID,
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
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AUTHORITY_INVALID,
            "authority_coverage",
        ) from error


def _verified_aggregate_results(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV1,
) -> tuple[
    tuple[MarketEvent, ...],
    Mapping[str, BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1],
    tuple[BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1, ...],
    tuple[tuple[int, int], ...],
]:
    expected_dates = _requested_dates(
        request.timeline_window_start, request.timeline_window_end_exclusive
    )
    if (
        tuple(
            value.capture.request.utc_date for value in request.aggregate_trade_results
        )
        != expected_dates
    ):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AGGREGATE_TRADES_INVALID,
            "aggregate_trade_dates",
        )
    all_events: list[MarketEvent] = []
    by_event: dict[
        str, BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1
    ] = {}
    previous: (
        BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1 | None
    ) = None
    cross_date_raw_id_gaps: list[
        BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1
    ] = []
    missing_prefixes: list[tuple[int, int]] = []
    for result in request.aggregate_trade_results:
        replay = normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
            result.capture
        )
        if replay.result is None or not _canonical_equal(replay.result, result):
            raise _ProjectionError(
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AGGREGATE_TRADES_INVALID,
                result.capture.request.utc_date,
            )
        if (
            result.prefix_gap_classification != "unknown_unproven"
            or result.suffix_gap_classification != "unknown_unproven"
            or result.internal_gap_classification
            not in {
                "none_observed_by_contiguous_ids",
                "provider_raw_id_gaps_observed_with_contiguous_aggregate_ids",
            }
        ):
            raise _ProjectionError(
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AGGREGATE_TRADES_INVALID,
                "aggregate_trade_gap_evidence",
            )
        retained_authority = result.capture.request.authority
        if retained_authority is not None:
            missing_prefixes.append(
                (
                    retained_authority.declared_missing_prefix_start.epoch_nanoseconds,
                    retained_authority.declared_missing_prefix_end_exclusive.epoch_nanoseconds,
                )
            )
        if previous is not None:
            first_event = result.events[0]
            last_event = previous.events[-1]
            first = first_event.payload
            last = last_event.payload
            previous_last_trade_id = cast(int, last["last_trade_id"])
            current_first_trade_id = cast(int, first["first_trade_id"])
            aggregate_ids_contiguous = (
                result.first_aggregate_trade_id
                == previous.last_aggregate_trade_id + 1
            )
            if not aggregate_ids_contiguous and (
                retained_authority is None
                or result.first_aggregate_trade_id
                <= previous.last_aggregate_trade_id
                or current_first_trade_id <= previous_last_trade_id
            ):
                raise _ProjectionError(
                    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AGGREGATE_TRADES_INVALID,
                    "aggregate_trade_cross_date_contiguity",
                )
            if aggregate_ids_contiguous and current_first_trade_id <= previous_last_trade_id:
                raise _ProjectionError(
                    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AGGREGATE_TRADES_INVALID,
                    "aggregate_trade_cross_date_raw_id_overlap",
                )
            if (
                aggregate_ids_contiguous
                and current_first_trade_id > previous_last_trade_id + 1
            ):
                cross_date_raw_id_gaps.append(
                    BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1(
                        previous_aggregate_trade_id=cast(
                            int, last["aggregate_trade_id"]
                        ),
                        current_aggregate_trade_id=cast(
                            int, first["aggregate_trade_id"]
                        ),
                        previous_last_trade_id=previous_last_trade_id,
                        current_first_trade_id=current_first_trade_id,
                        missing_first_trade_id=previous_last_trade_id + 1,
                        missing_last_trade_id=current_first_trade_id - 1,
                        missing_trade_count=(
                            current_first_trade_id - previous_last_trade_id - 1
                        ),
                        previous_transaction_time_milliseconds=cast(
                            int, last["transaction_time_milliseconds"]
                        ),
                        current_transaction_time_milliseconds=cast(
                            int, first["transaction_time_milliseconds"]
                        ),
                    )
                )
        previous = result
        for event in result.events:
            if (
                event.stream_key != _AGG_STREAM
                or event.event_type != _AGG_EVENT_TYPE
                or event.capability != _AGG_CAPABILITY
                or event.instrument_id != _INSTRUMENT
                or event.phase != TimelinePhase(0, "market_data")
            ):
                raise _ProjectionError(
                    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.SOURCE_CONTEXT_INVALID,
                    event.event_id,
                )
            if (
                request.timeline_window_start
                <= event.event_time
                < request.timeline_window_end_exclusive
            ):
                all_events.append(event)
                by_event[event.event_id] = result
    ordered = tuple(
        sorted(
            all_events,
            key=lambda value: (
                value.event_time.epoch_nanoseconds,
                cast(int, value.payload["aggregate_trade_id"]),
                value.event_id,
            ),
        )
    )
    return (
        ordered,
        by_event,
        tuple(cross_date_raw_id_gaps),
        tuple(missing_prefixes),
    )


def _verified_price_results(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV1,
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
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.PRICE_BARS_INVALID,
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
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.PRICE_BARS_INVALID,
                source_kind.value,
            )
        for event in result.events:
            if event.instrument_id != _INSTRUMENT or event.phase != TimelinePhase(
                0, "market_data"
            ):
                raise _ProjectionError(
                    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.SOURCE_CONTEXT_INVALID,
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
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.PRICE_BARS_INVALID,
                f"{source_kind.value}:{opened}",
            )
        selected.extend(events)
    return tuple(completed for completed, _ in required_grid), tuple(selected)


def _verified_funding_result(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV1,
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
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.FUNDING_INVALID,
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
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.SOURCE_CONTEXT_INVALID,
            "funding_events",
        )
    return events


def _validate_inputs(
    value: object,
) -> _ValidatedInputs:
    request = _trusted_request(value)
    sessions, cash_opens, admission_start = _verified_authority(request)
    (
        aggregate_events,
        aggregate_lineage,
        aggregate_trade_cross_date_raw_id_gaps,
        aggregate_trade_missing_prefixes,
    ) = _verified_aggregate_results(request)
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
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.PRICE_BARS_INVALID,
            "mark_index_grid",
        )
    funding_events = _verified_funding_result(request)
    source_events = tuple(
        sorted(
            (*aggregate_events, *mark_events, *index_events, *funding_events),
            key=lambda event: (event.stream_key, event.ordering_key, event.event_id),
        )
    )
    if len({event.event_id for event in source_events}) != len(source_events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.SOURCE_CONTEXT_INVALID,
            "duplicate_source_event_id",
        )
    return _ValidatedInputs(
        request,
        source_events,
        aggregate_events,
        aggregate_lineage,
        aggregate_trade_cross_date_raw_id_gaps,
        aggregate_trade_missing_prefixes,
        sessions,
        cash_opens,
        admission_start,
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
    try:
        whole_units = int(whole)
        fractional_units = int(fraction.ljust(8, "0"))
    except ValueError as error:
        raise ValueError("aggregate trade price cannot project exactly to scale 8") from error
    units = whole_units * 100_000_000 + fractional_units
    if units <= 0:
        raise ValueError("aggregate trade price must be positive")
    return units


def _contains(sessions: tuple[tuple[int, int], ...], instant: int) -> bool:
    return any(start <= instant < end for start, end in sessions)


def _cash_cutoff(cash_opens: tuple[int, ...], boundary: int, window_end: int) -> int:
    index = bisect_left(cash_opens, boundary + 1)
    return min(cash_opens[index] if index < len(cash_opens) else window_end, window_end)


def _project(
    boundary: UtcInstant,
    cutoff: UtcInstant,
    source: MarketEvent,
    normalization: BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1,
    source_sequence: int,
) -> tuple[MarketEvent, BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1]:
    payload = source.payload
    units = _price_units(payload["price"])
    preimage = {
        "type": "binance_usdm_koru_first_retained_trade_projection_preimage_v1",
        "schema_version": _SCHEMA_VERSION,
        "hourly_boundary": boundary,
        "next_cash_market_open_or_window_end": cutoff,
        "source_event_id": source.event_id,
        "source_event_hash": source.event_hash,
        "source_revision_id": source.revision_id,
        "source_event_time": source.event_time,
        "source_available_time": source.available_time,
        "source_key": source.source_key,
        "source_hash": source.source_hash,
        "source_record_hash": payload["source_record_hash"],
        "source_snapshot_id": normalization.source_snapshot_id,
        "source_snapshot_hash": normalization.source_snapshot_hash,
        "source_normalization_hash": normalization.normalization_hash,
        "open_price": {"units": units, "scale": 8, "quote_currency": "USDT"},
    }
    event_identity = canonical_sha256(
        {
            "type": "binance_usdm_koru_first_retained_trade_projection_event_identity_v1",
            "projection": preimage,
        }
    )
    revision_identity = canonical_sha256(
        {
            "type": "binance_usdm_koru_first_retained_trade_projection_revision_identity_v1",
            "projection": preimage,
        }
    )
    source_identity = canonical_sha256(
        {
            "type": "binance_usdm_koru_first_retained_trade_projection_source_identity_v1",
            "projection": preimage,
        }
    )
    event = MarketEvent(
        event_id="binance-usdm-koru-first-retained-trade-bar-open-v1:" + event_identity,
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
    lineage = BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1(
        hourly_boundary=boundary,
        next_cash_market_open_or_window_end=cutoff,
        source_event_id=source.event_id,
        source_event_hash=source.event_hash,
        source_revision_id=source.revision_id,
        source_event_time=source.event_time,
        source_available_time=source.available_time,
        source_key=source.source_key,
        source_hash=source.source_hash,
        aggregate_trade_id=cast(int, payload["aggregate_trade_id"]),
        first_trade_id=cast(int, payload["first_trade_id"]),
        last_trade_id=cast(int, payload["last_trade_id"]),
        source_record_hash=cast(str, payload["source_record_hash"]),
        source_snapshot_id=normalization.source_snapshot_id,
        source_snapshot_hash=normalization.source_snapshot_hash,
        source_provenance_hash=cast(str, payload["source_provenance_hash"]),
        source_member_hash=normalization.source_member_hash,
        source_request_hash=normalization.request_hash,
        source_capture_hash=normalization.capture_hash,
        source_normalization_hash=normalization.normalization_hash,
        open_price_units=units,
        open_price_scale=8,
        projection_event_id=event.event_id,
        projection_event_hash=event.event_hash,
        projection_revision_id=event.revision_id,
        projection_source_key=event.source_key,
        projection_source_hash=event.source_hash,
    )
    return event, lineage


def _manifest_from_group(
    stream_key: str, events: tuple[MarketEvent, ...]
) -> MarketStreamManifest:
    if len({event.event_id for event in events}) != len(events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.SOURCE_CONTEXT_INVALID,
            f"duplicate_event_id:{stream_key}",
        )
    if len({event.ordering_key for event in events}) != len(events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.SOURCE_CONTEXT_INVALID,
            f"duplicate_ordering_key:{stream_key}",
        )
    return MarketStreamManifest.from_events(stream_key, events)


def _stream_manifests(
    source_events: tuple[MarketEvent, ...], projection_events: tuple[MarketEvent, ...]
) -> tuple[MarketStreamManifest, ...]:
    events = (*source_events, *projection_events)
    if len({event.event_id for event in events}) != len(events):
        raise _ProjectionError(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.SOURCE_CONTEXT_INVALID,
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


def _assemble(value: object) -> _Assembled:
    validated = _validate_inputs(value)
    request = validated.request
    start = request.timeline_window_start.epoch_nanoseconds
    end = request.timeline_window_end_exclusive.epoch_nanoseconds
    first_boundary = ((start + _HOUR_NS - 1) // _HOUR_NS) * _HOUR_NS
    aggregate_times = tuple(
        event.event_time.epoch_nanoseconds for event in validated.aggregate_events
    )
    projections: list[MarketEvent] = []
    lineages: list[BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1] = []
    missing: list[BinanceUsdmKoruMissingBoundaryProjectionV1] = []
    for boundary_ns in range(first_boundary, end, _HOUR_NS):
        if boundary_ns < validated.unit_admission_start:
            continue
        cutoff_ns = _cash_cutoff(validated.cash_opens, boundary_ns, end)
        boundary = UtcInstant(boundary_ns)
        cutoff = UtcInstant(cutoff_ns)
        if any(
            start <= boundary_ns < end_exclusive
            for start, end_exclusive in validated.aggregate_trade_missing_prefixes
        ):
            missing.append(
                BinanceUsdmKoruMissingBoundaryProjectionV1(
                    boundary, cutoff, "missing_retained_aggregate_trade"
                )
            )
            continue
        if _contains(validated.sessions, boundary_ns):
            continue
        index = bisect_left(aggregate_times, boundary_ns)
        if index >= len(validated.aggregate_events):
            missing.append(
                BinanceUsdmKoruMissingBoundaryProjectionV1(
                    boundary, cutoff, "missing_retained_aggregate_trade"
                )
            )
            continue
        source = validated.aggregate_events[index]
        if source.event_time.epoch_nanoseconds >= cutoff_ns:
            missing.append(
                BinanceUsdmKoruMissingBoundaryProjectionV1(
                    boundary, cutoff, "no_safe_fill_before_cash_market_open"
                )
            )
            continue
        event, lineage = _project(
            boundary,
            cutoff,
            source,
            validated.aggregate_lineage[source.event_id],
            len(projections),
        )
        if event.event_time != event.available_time:
            raise _ProjectionError(
                BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.PROJECTION_INVALID,
                event.event_id,
            )
        projections.append(event)
        lineages.append(lineage)
    projection_events = tuple(projections)
    return _Assembled(
        source_events=validated.source_events,
        projection_events=projection_events,
        projection_lineage=tuple(lineages),
        missing_boundaries=tuple(missing),
        stream_manifests=_stream_manifests(validated.source_events, projection_events),
        aggregate_trade_cross_date_raw_id_gaps=(
            validated.aggregate_trade_cross_date_raw_id_gaps
        ),
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionResultV1:
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV1
    source_events: tuple[MarketEvent, ...]
    projection_events: tuple[MarketEvent, ...]
    projection_lineage: tuple[BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1, ...]
    missing_boundaries: tuple[BinanceUsdmKoruMissingBoundaryProjectionV1, ...]
    stream_manifests: tuple[MarketStreamManifest, ...]
    xkrx_calendar: ArtifactEnvelope
    arcx_calendar: ArtifactEnvelope
    post_adjustment_unit_regime: ArtifactEnvelope
    xkrx_calendar_ref: ArtifactRef
    arcx_calendar_ref: ArtifactRef
    post_adjustment_unit_regime_ref: ArtifactRef
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False
    aggregate_trade_cross_date_raw_id_gaps: tuple[
        BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1, ...
    ] = ()
    fragment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        try:
            assembled = _assemble(self.request)
            authority = self.request.authority_result
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
                or type(self.aggregate_trade_cross_date_raw_id_gaps) is not tuple
                or any(
                    type(gap)
                    is not BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1
                    for gap in self.aggregate_trade_cross_date_raw_id_gaps
                )
                or not _canonical_equal(
                    self.aggregate_trade_cross_date_raw_id_gaps,
                    assembled.aggregate_trade_cross_date_raw_id_gaps,
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
        value: dict[str, object] = {
            "type": "binance_usdm_koru_tradifi_source_projection_result_v1",
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
            "source_normalization_hashes": (
                tuple(
                    value.normalization_hash
                    for value in self.request.aggregate_trade_results
                )
                + tuple(
                    value.normalization_hash
                    for value in self.request.mark_price_results
                )
                + tuple(
                    value.normalization_hash
                    for value in self.request.index_price_results
                )
                + (self.request.funding_result.normalization_hash,)
            ),
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }
        if self.aggregate_trade_cross_date_raw_id_gaps:
            value["aggregate_trade_cross_date_raw_id_gaps"] = (
                self.aggregate_trade_cross_date_raw_id_gaps
            )
        return value

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "fragment_digest": self.fragment_digest}


def _trusted_result(
    value: object,
) -> BinanceUsdmKoruTradifiSourceProjectionResultV1 | None:
    if type(value) is not BinanceUsdmKoruTradifiSourceProjectionResultV1:
        return None
    result = value
    try:
        rebuilt = BinanceUsdmKoruTradifiSourceProjectionResultV1(
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
            decision_grade_eligible=result.decision_grade_eligible,
            deployment_authorized=result.deployment_authorized,
            aggregate_trade_cross_date_raw_id_gaps=(
                result.aggregate_trade_cross_date_raw_id_gaps
            ),
        )
        if not _canonical_equal(
            rebuilt, result
        ) or result.fragment_digest != canonical_sha256(result._body()):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiSourceProjectionOutcomeV1:
    result: BinanceUsdmKoruTradifiSourceProjectionResultV1 | None = None
    failure: BinanceUsdmKoruTradifiSourceProjectionFailureV1 | None = None

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
            is not BinanceUsdmKoruTradifiSourceProjectionFailureV1
        ):
            raise TypeError("failure must be exact source-projection failure")


def _failed(
    code: BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1, subject: str
) -> BinanceUsdmKoruTradifiSourceProjectionOutcomeV1:
    return BinanceUsdmKoruTradifiSourceProjectionOutcomeV1(
        failure=BinanceUsdmKoruTradifiSourceProjectionFailureV1(code, subject)
    )


def build_binance_usdm_koru_tradifi_source_projection_v1(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV1,
) -> BinanceUsdmKoruTradifiSourceProjectionOutcomeV1:
    try:
        trusted = _trusted_request(request)
        assembled = _assemble(trusted)
        authority = trusted.authority_result
        result = BinanceUsdmKoruTradifiSourceProjectionResultV1(
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
            aggregate_trade_cross_date_raw_id_gaps=(
                assembled.aggregate_trade_cross_date_raw_id_gaps
            ),
        )
    except _ProjectionError as error:
        return _failed(error.code, error.subject)
    except (KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.RESULT_INVALID,
            type(error).__name__,
        )
    return BinanceUsdmKoruTradifiSourceProjectionOutcomeV1(result=result)
