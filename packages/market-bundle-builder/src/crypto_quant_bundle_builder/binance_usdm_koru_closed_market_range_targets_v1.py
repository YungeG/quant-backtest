"""Sealed eight-target generator for the KORU closed-market range strategy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from enum import Enum
from typing import Protocol, cast

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketEvent,
    MarketStreamManifest,
)

from .binance_usdm_koru_tradifi_source_projection_v1 import (
    BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1,
    BinanceUsdmKoruTradifiSourceProjectionResultV1,
)
from .binance_usdm_koru_tradifi_source_projection_v1 import (
    _trusted_result as _trusted_source_result,
)

_SCHEMA_VERSION = 1
_HOUR_NS = 3_600_000_000_000
_STRATEGY_ID = "koruusdt_closed_market_range_v1"
_SLEEVE_ID = "koruusdt-closed-market-range"
_INSTRUMENT = {
    "venue": "binance_usdm",
    "stable_key": "koru-usdt-tradifi-perpetual",
}
_CAPABILITY = MarketBundleCapability("precomputed_target_stream", 1)
_EVENT_TYPE = "strategy_decision_candidate"
_PHASE = TimelinePhase(30, "strategy_decision")
_SOURCE_KEY = "binance_usdm.koru.closed_market_range.targets.v1"
_STREAM_PREFIX = "binance_usdm.tradifi.target.koruusdt.closed_market_range.p"
_STRATEGY_ARTIFACT_TYPE = "strategy_definition"
_PARAMETER_ARTIFACT_TYPE = "strategy_parameter_set"
_PREMIUM_LIMIT = Decimal("0.02")
_ENTRY_FRACTION = Decimal("0.25")
_STOP_WIDTHS = Decimal(1)
_REQUIRED_SYNTHETIC_EQUITY_USDT = Decimal(10000)
_REQUIRED_SLEEVE_ALLOCATION_FRACTION = Decimal(1)
_TARGET_EXPOSURE_FRACTION = Decimal("0.1")
_TARGET_NOTIONAL = Decimal(1000)
_EVIDENCE_PLACES = Decimal("0.000000000001")
_PARAMETER_GRID = tuple(
    (formation, maximum, hold)
    for formation in (2, 3)
    for maximum in (Decimal("0.03"), Decimal("0.05"))
    for hold in (2, 4)
)


def _canonical_equal(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _instant_ns(value: object) -> int:
    if type(value) is not str or not value.endswith("Z"):
        raise ValueError("calendar instant must be exact UTC text")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("calendar instant must be UTC")
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    delta = parsed - epoch
    return (
        delta.days * 86_400_000_000_000
        + delta.seconds * 1_000_000_000
        + delta.microseconds * 1_000
    )


def _decimal_text(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 50
        quantized = value.quantize(_EVIDENCE_PLACES, rounding=ROUND_HALF_EVEN)
    text = format(quantized, "f").rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _formation_range_text(high: int, low: int) -> str:
    with localcontext() as context:
        context.prec = 50
        value = Decimal(2 * (high - low)) / Decimal(high + low)
    return _decimal_text(value)


def _formation_range_exceeds(high: int, low: int, maximum: Decimal) -> bool:
    numerator, denominator = maximum.as_integer_ratio()
    return 2 * (high - low) * denominator > numerator * (high + low)


def _artifact_ref_value(value: ArtifactRef) -> dict[str, object]:
    return value.to_canonical_dict()


class _SourceProjectionRequest(Protocol):
    @property
    def timeline_window_start(self) -> UtcInstant: ...

    @property
    def timeline_window_end_exclusive(self) -> UtcInstant: ...


class _SourceProjection(Protocol):
    @property
    def request(self) -> _SourceProjectionRequest: ...

    @property
    def source_events(self) -> tuple[MarketEvent, ...]: ...

    @property
    def xkrx_calendar(self) -> ArtifactEnvelope: ...

    @property
    def arcx_calendar(self) -> ArtifactEnvelope: ...

    @property
    def xkrx_calendar_ref(self) -> ArtifactRef: ...

    @property
    def arcx_calendar_ref(self) -> ArtifactRef: ...

    @property
    def post_adjustment_unit_regime_ref(self) -> ArtifactRef: ...

    @property
    def fragment_digest(self) -> str: ...


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetsRequestV1:
    source_projection: BinanceUsdmKoruTradifiSourceProjectionResultV1

    def __post_init__(self) -> None:
        trusted = _trusted_source_result(self.source_projection)
        if trusted is None:
            raise ValueError("source_projection must be an exact accepted result")
        object.__setattr__(self, "source_projection", trusted)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_closed_market_range_targets_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_projection": self.source_projection,
            "source_fragment_digest": self.source_projection.fragment_digest,
        }


class BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_FRAGMENT_INVALID = "source_fragment_invalid"
    TARGET_GENERATION_INVALID = "target_generation_invalid"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetsFailureV1:
    code: BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1
    subject: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1:
            raise TypeError("code must be an exact target-generation failure code")
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
            "type": "binance_usdm_koru_closed_market_range_targets_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1:
    envelope: ArtifactEnvelope
    ref: ArtifactRef

    def __post_init__(self) -> None:
        if (
            type(self.envelope) is not ArtifactEnvelope
            or type(self.ref) is not ArtifactRef
        ):
            raise TypeError("strategy artifact binding requires exact domain values")
        if (
            self.envelope.artifact_type != _STRATEGY_ARTIFACT_TYPE
            or self.envelope.schema_version != _SCHEMA_VERSION
            or self.ref != ArtifactRef.from_envelope(self.envelope)
        ):
            raise ValueError("strategy artifact binding mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_closed_market_range_strategy_artifact_binding_v1",
            "envelope": self.envelope,
            "ref": self.ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1:
    parameter_id: str
    formation_hours: int
    max_formation_range: Decimal
    max_hold_hours: int
    envelope: ArtifactEnvelope
    ref: ArtifactRef

    def __post_init__(self) -> None:
        if (
            type(self.parameter_id) is not str
            or self.parameter_id not in {f"p{index:02d}" for index in range(1, 9)}
            or type(self.formation_hours) is not int
            or type(self.max_formation_range) is not Decimal
            or type(self.max_hold_hours) is not int
            or (self.formation_hours, self.max_formation_range, self.max_hold_hours)
            not in _PARAMETER_GRID
        ):
            raise ValueError("parameter binding is outside the sealed grid")
        if (
            type(self.envelope) is not ArtifactEnvelope
            or type(self.ref) is not ArtifactRef
        ):
            raise TypeError("parameter artifact binding requires exact domain values")
        if (
            self.envelope.artifact_type != _PARAMETER_ARTIFACT_TYPE
            or self.envelope.schema_version != _SCHEMA_VERSION
            or self.ref != ArtifactRef.from_envelope(self.envelope)
        ):
            raise ValueError("parameter artifact binding mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_closed_market_range_parameter_artifact_binding_v1",
            "parameter_id": self.parameter_id,
            "formation_hours": self.formation_hours,
            "max_formation_range": str(self.max_formation_range),
            "max_hold_hours": self.max_hold_hours,
            "envelope": self.envelope,
            "ref": self.ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetStreamResultV1:
    parameter_ref: ArtifactRef
    stream_key: str
    events: tuple[MarketEvent, ...]
    manifest: MarketStreamManifest
    target_stream_digest: str

    def __post_init__(self) -> None:
        if type(self.parameter_ref) is not ArtifactRef:
            raise TypeError("parameter_ref must be exact ArtifactRef")
        if type(self.stream_key) is not str or not self.stream_key.startswith(
            _STREAM_PREFIX
        ):
            raise ValueError("stream_key must be a sealed target stream key")
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
            "type": "binance_usdm_koru_closed_market_range_target_stream_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "parameter_ref": self.parameter_ref,
            "stream_key": self.stream_key,
            "events": self.events,
            "manifest": self.manifest,
            "target_stream_digest": self.target_stream_digest,
        }


class _TargetError(ValueError):
    def __init__(
        self,
        code: BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1,
        subject: str,
    ) -> None:
        super().__init__(subject)
        self.code = code
        self.subject = subject


@dataclass(frozen=True, slots=True)
class _BarPair:
    completed_ns: int
    mark: MarketEvent
    index: MarketEvent

    @property
    def high(self) -> int:
        return cast(int, self.mark.payload["high_units"])

    @property
    def low(self) -> int:
        return cast(int, self.mark.payload["low_units"])

    @property
    def close(self) -> int:
        return cast(int, self.mark.payload["close_units"])

    @property
    def index_close(self) -> int:
        return cast(int, self.index.payload["close_units"])


@dataclass(frozen=True, slots=True)
class _Projection:
    boundary_ns: int
    cutoff_ns: int
    event: MarketEvent


@dataclass(frozen=True, slots=True)
class _Assembled:
    strategy: BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1
    parameters: tuple[BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1, ...]
    streams: tuple[BinanceUsdmKoruClosedMarketRangeTargetStreamResultV1, ...]


def _strategy_binding() -> BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1:
    payload = {
        "strategy_id": _STRATEGY_ID,
        "sleeve_id": _SLEEVE_ID,
        "instrument_id": _INSTRUMENT,
        "required_synthetic_equity_usdt": str(_REQUIRED_SYNTHETIC_EQUITY_USDT),
        "required_sleeve_allocation_fraction": str(
            _REQUIRED_SLEEVE_ALLOCATION_FRACTION
        ),
        "target_exposure_fraction": str(_TARGET_EXPOSURE_FRACTION),
        "position_notional_usdt": str(_TARGET_NOTIONAL),
        "future_preparation_binding": {
            "required_synthetic_equity_usdt": str(
                _REQUIRED_SYNTHETIC_EQUITY_USDT
            ),
            "required_sleeve_allocation_fraction": str(
                _REQUIRED_SLEEVE_ALLOCATION_FRACTION
            ),
            "mismatch_action": "reject",
        },
        "rules": {
            "cash_session_union": "XKRX_regular_union_ARCX_core",
            "closed_intervals": "complement_inside_source_fragment_window",
            "eligible_bar": "fully_closed_completed_1h_exact_strategy_mark_index_pair",
            "formation": "first_formation_hours_eligible_bars_per_closed_interval",
            "first_entry_evaluation_bar": "formation_hours_plus_one",
            "formation_range": "2*(high-low)/(high+low)",
            "formation_range_width_must_be_positive": True,
            "entry_premium": "ln(mark_close/index_close)",
            "entry_premium_absolute_max": "0.02",
            "long_entry": "formation_low<=mark_close<=formation_high_and_4*(mark_close-formation_low)<=formation_width",
            "short_entry": "formation_low<=mark_close<=formation_high_and_4*(formation_high-mark_close)<=formation_width",
            "entry_fraction": "0.25",
            "midpoint_exit": "formation_midpoint",
            "stop_distance_formation_widths": "1",
            "decision_projection_boundary": "decision_time_plus_1h",
            "source_bar_self_fill": False,
            "projection_must_be_present_and_safe": True,
            "entry_requires_later_safe_exit": True,
            "exit_bars_must_complete_after_actual_entry_fill": True,
            "boundary_exit": "last_safe_next_boundary_projection_before_cash_open",
            "maximum_trades_per_closed_interval": 1,
            "every_stream_ends_flat": True,
            "confidence": "1",
            "target_notional_usdt": str(_TARGET_NOTIONAL),
            "preparation_requires_exact_synthetic_equity_and_sleeve_allocation": True,
            "numeric_policy": "Decimal_and_integer_only",
            "premium_evidence_decimal_places": 12,
        },
        "parameter_schema": (
            "formation_hours",
            "max_formation_range",
            "max_hold_hours",
            "entry_zone_fraction",
            "stop_range_multiple",
            "max_abs_premium",
            "max_trades_per_closed_interval",
            "position_notional_usdt",
        ),
        "parameter_grid": {
            "formation_hours": (2, 3),
            "max_formation_range": ("0.03", "0.05"),
            "max_hold_hours": (2, 4),
            "cardinality": 8,
            "caller_expansion_allowed": False,
        },
        "development_authorized": False,
        "deployment_authorized": False,
    }
    envelope = ArtifactEnvelope.create(_STRATEGY_ARTIFACT_TYPE, 1, payload)
    return BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1(
        envelope, ArtifactRef.from_envelope(envelope)
    )


def _parameter_bindings(
    strategy_ref: ArtifactRef,
) -> tuple[BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1, ...]:
    bindings = []
    for index, (formation, maximum, hold) in enumerate(_PARAMETER_GRID, 1):
        parameter_id = f"p{index:02d}"
        payload = {
            "strategy_definition_ref": _artifact_ref_value(strategy_ref),
            "strategy_id": _STRATEGY_ID,
            "parameter_set_id": parameter_id,
            "formation_hours": str(formation),
            "max_formation_range": str(maximum),
            "max_hold_hours": str(hold),
            "entry_zone_fraction": str(_ENTRY_FRACTION),
            "stop_range_multiple": str(_STOP_WIDTHS),
            "max_abs_premium": str(_PREMIUM_LIMIT),
            "max_trades_per_closed_interval": "1",
            "position_notional_usdt": str(_TARGET_NOTIONAL),
            "development_authorized": False,
            "deployment_authorized": False,
        }
        envelope = ArtifactEnvelope.create(_PARAMETER_ARTIFACT_TYPE, 1, payload)
        bindings.append(
            BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1(
                parameter_id=parameter_id,
                formation_hours=formation,
                max_formation_range=maximum,
                max_hold_hours=hold,
                envelope=envelope,
                ref=ArtifactRef.from_envelope(envelope),
            )
        )
    return tuple(bindings)


def _sessions(source: _SourceProjection) -> tuple[tuple[int, int], ...]:
    start = source.request.timeline_window_start.epoch_nanoseconds
    end = source.request.timeline_window_end_exclusive.epoch_nanoseconds
    rows: list[tuple[int, int]] = []
    for envelope in (source.xkrx_calendar, source.arcx_calendar):
        payload = cast(Mapping[str, object], envelope.payload)
        sessions = payload.get("sessions")
        if not isinstance(sessions, tuple):
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
                "calendar_sessions",
            )
        for row in sessions:
            if not isinstance(row, Mapping):
                raise _TargetError(
                    BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
                    "calendar_session_row",
                )
            opened = max(_instant_ns(row.get("open_utc")), start)
            closed = min(_instant_ns(row.get("close_utc")), end)
            if opened < closed:
                rows.append((opened, closed))
    merged: list[tuple[int, int]] = []
    for opened, closed in sorted(rows):
        if merged and opened <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], closed))
        else:
            merged.append((opened, closed))
    return tuple(merged)


def _closed_intervals(
    source: _SourceProjection,
) -> tuple[tuple[int, int], ...]:
    cursor = source.request.timeline_window_start.epoch_nanoseconds
    end = source.request.timeline_window_end_exclusive.epoch_nanoseconds
    result: list[tuple[int, int]] = []
    for opened, closed in _sessions(source):
        if cursor < opened:
            result.append((cursor, opened))
        cursor = max(cursor, closed)
    if cursor < end:
        result.append((cursor, end))
    return tuple(result)


def _strategy_pairs(source: _SourceProjection) -> dict[int, _BarPair]:
    grouped: dict[int, dict[str, MarketEvent]] = {}
    for event in source.source_events:
        kind = event.payload.get("source_kind")
        if event.payload.get("price_purpose") != "strategy" or kind not in {
            "mark_price",
            "index_price",
        }:
            continue
        completed = event.event_time.epoch_nanoseconds
        by_kind = grouped.setdefault(completed, {})
        if kind in by_kind:
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
                f"duplicate_{kind}_bar:{completed}",
            )
        if (
            event.available_time != event.event_time
            or event.payload.get("interval") != "1h"
            or event.payload.get("price_scale") != 8
        ):
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
                f"invalid_strategy_bar:{event.event_id}",
            )
        by_kind[cast(str, kind)] = event
    return {
        completed: _BarPair(completed, values["mark_price"], values["index_price"])
        for completed, values in grouped.items()
        if set(values) == {"mark_price", "index_price"}
    }


def _projections(
    source: BinanceUsdmKoruTradifiSourceProjectionResultV1,
) -> dict[int, _Projection]:
    events = {event.event_id: event for event in source.projection_events}
    result: dict[int, _Projection] = {}
    for lineage in source.projection_lineage:
        if type(lineage) is not BinanceUsdmKoruFirstRetainedTradeProjectionLineageV1:
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
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
        ):
            raise _TargetError(
                BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
                f"unsafe_projection:{boundary}",
            )
        result[boundary] = _Projection(boundary, cutoff, event)
    return result


def _premium(pair: _BarPair) -> Decimal:
    if pair.close <= 0 or pair.index_close <= 0:
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
            f"nonpositive_close:{pair.completed_ns}",
        )
    with localcontext() as context:
        context.prec = 50
        return (Decimal(pair.close) / Decimal(pair.index_close)).ln()


def _evidence(
    *,
    source: _SourceProjection,
    strategy_ref: ArtifactRef,
    parameter_ref: ArtifactRef,
    pair: _BarPair,
    formation: tuple[_BarPair, ...],
    high: int,
    low: int,
    width: int,
    entry_premium: Decimal,
    decision_premium: Decimal,
    projection: _Projection,
) -> dict[str, object]:
    return {
        "source_fragment_digest": source.fragment_digest,
        "strategy_definition_ref": _artifact_ref_value(strategy_ref),
        "strategy_parameter_set_ref": _artifact_ref_value(parameter_ref),
        "xkrx_calendar_ref": _artifact_ref_value(source.xkrx_calendar_ref),
        "arcx_calendar_ref": _artifact_ref_value(source.arcx_calendar_ref),
        "post_adjustment_unit_regime_ref": _artifact_ref_value(
            source.post_adjustment_unit_regime_ref
        ),
        "mark_event_id": pair.mark.event_id,
        "mark_event_hash": pair.mark.event_hash,
        "index_event_id": pair.index.event_id,
        "index_event_hash": pair.index.event_hash,
        "formation_mark_event_hashes": tuple(
            item.mark.event_hash for item in formation
        ),
        "price_scale": 8,
        "formation_high_units": high,
        "formation_low_units": low,
        "formation_width_units": width,
        "formation_midpoint_numerator_units": high + low,
        "formation_range": _formation_range_text(high, low),
        "entry_premium": _decimal_text(entry_premium),
        "decision_premium": _decimal_text(decision_premium),
        "projection_boundary": projection.boundary_ns,
        "projection_event_id": projection.event.event_id,
        "projection_event_hash": projection.event.event_hash,
        "projection_actual_event_time": projection.event.event_time.epoch_nanoseconds,
        "projection_cutoff": projection.cutoff_ns,
    }


def _candidate(
    *,
    source: _SourceProjection,
    strategy_ref: ArtifactRef,
    parameter_ref: ArtifactRef,
    pair: _BarPair,
    formation: tuple[_BarPair, ...],
    high: int,
    low: int,
    width: int,
    projection: _Projection,
    entry_premium: Decimal,
    target: str,
    reason: str,
) -> dict[str, object]:
    decision_premium = _premium(pair)
    return {
        "schema_version": 1,
        "strategy_id": _STRATEGY_ID,
        "sleeve_id": _SLEEVE_ID,
        "decision_time": pair.completed_ns,
        "observed_through": pair.completed_ns,
        "effective_time": pair.completed_ns,
        "expires_at": projection.cutoff_ns,
        "targets": ({"instrument_id": _INSTRUMENT, "value": target},),
        "confidence": 1,
        "reason": reason,
        "evidence": _evidence(
            source=source,
            strategy_ref=strategy_ref,
            parameter_ref=parameter_ref,
            pair=pair,
            formation=formation,
            high=high,
            low=low,
            width=width,
            entry_premium=entry_premium,
            decision_premium=decision_premium,
            projection=projection,
        ),
    }


def _event(stream_key: str, sequence: int, candidate: dict[str, object]) -> MarketEvent:
    preimage = {
        "type": "binance_usdm_koru_closed_market_range_target_preimage_v1",
        "schema_version": 1,
        "stream_key": stream_key,
        "candidate": candidate,
    }
    event_identity = canonical_sha256({"identity": "event", "preimage": preimage})
    revision_identity = canonical_sha256({"identity": "revision", "preimage": preimage})
    source_identity = canonical_sha256({"identity": "source", "preimage": preimage})
    decision_time = UtcInstant(cast(int, candidate["decision_time"]))
    return MarketEvent(
        event_id="binance-usdm-koru-closed-market-range-target-v1:" + event_identity,
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


def _target_stream_digest(stream_key: str, events: tuple[MarketEvent, ...]) -> str:
    return canonical_sha256(
        {
            "type": "precomputed_target_stream",
            "schema_version": 1,
            "stream_key": stream_key,
            "events": events,
        }
    )


def _manifest(stream_key: str, events: tuple[MarketEvent, ...]) -> MarketStreamManifest:
    if events:
        return MarketStreamManifest.from_events(stream_key, events)
    return MarketStreamManifest(
        stream_key,
        _EVENT_TYPE,
        _CAPABILITY,
        0,
        canonical_sha256(()),
    )


def _exit(
    *,
    parameter: BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1,
    interval_pairs: tuple[_BarPair, ...],
    entry_index: int,
    entry_projection: _Projection,
    side: int,
    high: int,
    low: int,
    width: int,
    projections: dict[int, _Projection],
) -> tuple[_BarPair, _Projection, str] | None:
    eligible: list[tuple[int, _BarPair, _Projection]] = []
    for index in range(entry_index + 1, len(interval_pairs)):
        pair = interval_pairs[index]
        projection = projections.get(pair.completed_ns + _HOUR_NS)
        if (
            pair.completed_ns > entry_projection.event.event_time.epoch_nanoseconds
            and projection is not None
        ):
            eligible.append((index, pair, projection))
    for position, (_, pair, projection) in enumerate(eligible):
        if side == 1 and pair.close <= low - width:
            reason = "closed_market_range_long_stop_exit"
        elif side == -1 and pair.close >= high + width:
            reason = "closed_market_range_short_stop_exit"
        elif side == 1 and 2 * pair.close >= high + low:
            reason = "closed_market_range_long_midpoint_exit"
        elif side == -1 and 2 * pair.close <= high + low:
            reason = "closed_market_range_short_midpoint_exit"
        elif pair.completed_ns >= (
            entry_projection.event.event_time.epoch_nanoseconds
            + parameter.max_hold_hours * _HOUR_NS
        ):
            reason = "closed_market_range_max_hold_exit"
        elif position == len(eligible) - 1:
            reason = "closed_market_range_boundary_exit"
        else:
            continue
        return pair, projection, reason
    return None


def _stream_candidates(
    *,
    source: _SourceProjection,
    strategy_ref: ArtifactRef,
    parameter: BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1,
    closed: tuple[tuple[int, int], ...],
    pairs: dict[int, _BarPair],
    projections: dict[int, _Projection],
) -> tuple[dict[str, object], ...]:
    candidates: list[dict[str, object]] = []
    for interval_start, interval_end in closed:
        interval_pairs = tuple(
            pairs[completed]
            for completed in sorted(pairs)
            if completed - _HOUR_NS >= interval_start and completed <= interval_end
        )
        if len(interval_pairs) <= parameter.formation_hours:
            continue
        formation = interval_pairs[: parameter.formation_hours]
        high = max(pair.high for pair in formation)
        low = min(pair.low for pair in formation)
        width = high - low
        if width <= 0 or _formation_range_exceeds(
            high, low, parameter.max_formation_range
        ):
            continue
        for entry_index in range(parameter.formation_hours, len(interval_pairs)):
            pair = interval_pairs[entry_index]
            projection = projections.get(pair.completed_ns + _HOUR_NS)
            if projection is None:
                continue
            premium = _premium(pair)
            if premium.copy_abs() > _PREMIUM_LIMIT:
                continue
            if low <= pair.close <= high and 4 * (pair.close - low) <= width:
                side = 1
                entry_reason = "closed_market_range_long_entry"
            elif low <= pair.close <= high and 4 * (high - pair.close) <= width:
                side = -1
                entry_reason = "closed_market_range_short_entry"
            else:
                continue
            exit_value = _exit(
                parameter=parameter,
                interval_pairs=interval_pairs,
                entry_index=entry_index,
                entry_projection=projection,
                side=side,
                high=high,
                low=low,
                width=width,
                projections=projections,
            )
            if exit_value is None:
                continue
            exit_pair, exit_projection, exit_reason = exit_value
            entry_candidate = _candidate(
                source=source,
                strategy_ref=strategy_ref,
                parameter_ref=parameter.ref,
                pair=pair,
                formation=formation,
                high=high,
                low=low,
                width=width,
                projection=projection,
                entry_premium=premium,
                target=str(
                    _TARGET_EXPOSURE_FRACTION
                    if side == 1
                    else -_TARGET_EXPOSURE_FRACTION
                ),
                reason=entry_reason,
            )
            exit_candidate = _candidate(
                source=source,
                strategy_ref=strategy_ref,
                parameter_ref=parameter.ref,
                pair=exit_pair,
                formation=formation,
                high=high,
                low=low,
                width=width,
                projection=exit_projection,
                entry_premium=premium,
                target="0",
                reason=exit_reason,
            )
            candidates.extend((entry_candidate, exit_candidate))
            break
    return tuple(candidates)


def _stream_events(
    *,
    source: _SourceProjection,
    strategy_ref: ArtifactRef,
    parameter: BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1,
    closed: tuple[tuple[int, int], ...],
    pairs: dict[int, _BarPair],
    projections: dict[int, _Projection],
) -> tuple[MarketEvent, ...]:
    stream_key = _STREAM_PREFIX + parameter.parameter_id[1:] + ".v1"
    return tuple(
        _event(stream_key, sequence, candidate)
        for sequence, candidate in enumerate(
            _stream_candidates(
                source=source,
                strategy_ref=strategy_ref,
                parameter=parameter,
                closed=closed,
                pairs=pairs,
                projections=projections,
            )
        )
    )


def _assemble(value: object) -> _Assembled:
    if type(value) is not BinanceUsdmKoruClosedMarketRangeTargetsRequestV1:
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.INVALID_REQUEST,
            "request_type",
        )
    trusted_source = _trusted_source_result(value.source_projection)
    if trusted_source is None:
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.SOURCE_FRAGMENT_INVALID,
            "source_projection",
        )
    request = BinanceUsdmKoruClosedMarketRangeTargetsRequestV1(trusted_source)
    if not _canonical_equal(request, value):
        raise _TargetError(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.INVALID_REQUEST,
            "request_binding",
        )
    strategy = _strategy_binding()
    parameters = _parameter_bindings(strategy.ref)
    closed = _closed_intervals(trusted_source)
    pairs = _strategy_pairs(trusted_source)
    projections = _projections(trusted_source)
    streams = []
    for parameter in parameters:
        stream_key = _STREAM_PREFIX + parameter.parameter_id[1:] + ".v1"
        events = _stream_events(
            source=trusted_source,
            strategy_ref=strategy.ref,
            parameter=parameter,
            closed=closed,
            pairs=pairs,
            projections=projections,
        )
        streams.append(
            BinanceUsdmKoruClosedMarketRangeTargetStreamResultV1(
                parameter_ref=parameter.ref,
                stream_key=stream_key,
                events=events,
                manifest=_manifest(stream_key, events),
                target_stream_digest=_target_stream_digest(stream_key, events),
            )
        )
    return _Assembled(strategy, parameters, tuple(streams))


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruClosedMarketRangeTargetsResultV1:
    request: BinanceUsdmKoruClosedMarketRangeTargetsRequestV1
    strategy: BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1
    parameters: tuple[BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1, ...]
    streams: tuple[BinanceUsdmKoruClosedMarketRangeTargetStreamResultV1, ...]
    development_authorized: bool = False
    deployment_authorized: bool = False
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        assembled = _assemble(self.request)
        if (
            type(self.strategy)
            is not BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1
            or not _canonical_equal(self.strategy, assembled.strategy)
            or type(self.parameters) is not tuple
            or not _canonical_equal(self.parameters, assembled.parameters)
            or type(self.streams) is not tuple
            or not _canonical_equal(self.streams, assembled.streams)
            or type(self.development_authorized) is not bool
            or self.development_authorized
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("target-generation result binding mismatch")
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
            "type": "binance_usdm_koru_closed_market_range_targets_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_hash": self.request.request_hash,
            "strategy": self.strategy,
            "parameters": self.parameters,
            "streams": self.streams,
            "development_authorized": self.development_authorized,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_result(
    value: object,
) -> BinanceUsdmKoruClosedMarketRangeTargetsResultV1 | None:
    if type(value) is not BinanceUsdmKoruClosedMarketRangeTargetsResultV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruClosedMarketRangeTargetsResultV1(
            request=value.request,
            strategy=value.strategy,
            parameters=value.parameters,
            streams=value.streams,
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
class BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1:
    result: BinanceUsdmKoruClosedMarketRangeTargetsResultV1 | None = None
    failure: BinanceUsdmKoruClosedMarketRangeTargetsFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result must be an exact canonical target result")
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruClosedMarketRangeTargetsFailureV1
        ):
            raise TypeError("failure must be exact target-generation failure")


def _failed(
    code: BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1,
    subject: str,
) -> BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1:
    return BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1(
        failure=BinanceUsdmKoruClosedMarketRangeTargetsFailureV1(code, subject)
    )


def build_binance_usdm_koru_closed_market_range_targets_v1(
    request: BinanceUsdmKoruClosedMarketRangeTargetsRequestV1,
) -> BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1:
    try:
        assembled = _assemble(request)
        result = BinanceUsdmKoruClosedMarketRangeTargetsResultV1(
            request=request,
            strategy=assembled.strategy,
            parameters=assembled.parameters,
            streams=assembled.streams,
        )
    except _TargetError as error:
        return _failed(error.code, error.subject)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruClosedMarketRangeTargetsFailureCodeV1.RESULT_INVALID,
            type(error).__name__,
        )
    return BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1(result=result)
