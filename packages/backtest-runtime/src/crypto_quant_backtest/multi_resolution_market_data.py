from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from time import perf_counter_ns as _perf_counter_ns
from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    SessionId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent, MarketStreamManifest

from .decision_schedule import DecisionSchedule, LookbackRequirement
from .observations import (
    ObservationCausalityTrace,
    ObservationPurposeRef,
    ObservationQuery,
    PointInTimeObservationQueryResult,
)
from .performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
    PerformanceOutcome,
)


_SCHEMA_VERSION = 1
_MAX_OBSERVATION_VALUE = 2**63 - 1
_AGGREGATION_SPEC_HASH = "sha256:324439214b2cb2fa64300c470a65e322de3c3dd7056381a73672db00677dbccb"
_BAR_CAPABILITY = MarketBundleCapability("price_bars", 1)
_PAYLOAD_FIELDS = {
    "schema_version",
    "bar_definition_key",
    "bar_definition_version",
    "bar_definition_hash",
    "source_stream_hash",
    "bucket_plan_hash",
    "aggregation_spec_hash",
    "aggregation_code_hash",
    "aggregation_input_hash",
    "bucket_hash",
    "session_id",
    "trading_date",
    "included_spans",
    "interval_start",
    "interval_end_exclusive",
    "price_purpose",
    "price_scale",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "observation_count",
    "source_event_hashes",
    "selected_source_set_hash",
}


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if (
        len(text) != 71
        or not text.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in text[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 hash")
    return text


def _instrument(value: object) -> InstrumentId:
    if type(value) is not InstrumentId:
        raise TypeError("instrument_id must be exact InstrumentId")
    try:
        if type(value.venue) is not VenueId:
            raise TypeError("instrument_id venue must be exact VenueId")
        return InstrumentId(VenueId(value.venue.value), value.stable_key)
    except AttributeError as error:
        raise ValueError("instrument_id authority is invalid") from error


def _utc(value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError("instant must be exact UtcInstant")
    return UtcInstant(value.epoch_nanoseconds)


def _phase(value: object) -> TimelinePhase:
    if type(value) is not TimelinePhase:
        raise TypeError("phase must be exact TimelinePhase")
    return TimelinePhase(value.rank, value.code)


def _source_sequence(value: object) -> SourceSequence:
    if type(value) is not SourceSequence:
        raise TypeError("source_sequence must be exact SourceSequence")
    return SourceSequence(value.value)


def _simulation_instant(value: object) -> SimulationInstant:
    if type(value) is not SimulationInstant:
        raise TypeError("decision instant must be exact SimulationInstant")
    return SimulationInstant(
        _utc(value.instant),
        _phase(value.phase),
        _source_sequence(value.source_sequence),
    )


def _capability(value: object) -> MarketBundleCapability:
    if type(value) is not MarketBundleCapability:
        raise TypeError("capability must be exact MarketBundleCapability")
    return MarketBundleCapability(value.key, value.version)


def _purpose(value: object) -> ObservationPurposeRef:
    if type(value) is not ObservationPurposeRef:
        raise TypeError("purpose must be exact ObservationPurposeRef")
    return ObservationPurposeRef(value.key, value.version)


def _query(value: object) -> ObservationQuery:
    if type(value) is not ObservationQuery:
        raise TypeError("query must be exact ObservationQuery")
    return ObservationQuery(
        value.dataset_key,
        _instrument(value.instrument_id),
        _purpose(value.purpose),
        _capability(value.capability),
    )


def _event(value: object) -> MarketEvent:
    if type(value) is not MarketEvent:
        raise TypeError("events must contain exact MarketEvent")
    return MarketEvent(
        event_id=value.event_id,
        stream_key=value.stream_key,
        event_type=value.event_type,
        capability=_capability(value.capability),
        instrument_id=None if value.instrument_id is None else _instrument(value.instrument_id),
        event_time=_utc(value.event_time),
        available_time=_utc(value.available_time),
        phase=_phase(value.phase),
        source_sequence=_source_sequence(value.source_sequence),
        revision_id=value.revision_id,
        supersedes_revision_id=value.supersedes_revision_id,
        source_key=value.source_key,
        source_hash=value.source_hash,
        payload=value.payload,
    )


def _trace(value: object) -> ObservationCausalityTrace:
    if type(value) is not ObservationCausalityTrace:
        raise TypeError("trace must be exact ObservationCausalityTrace")
    for name in (
        "candidate_record_hashes",
        "selected_observation_keys",
        "selected_event_hashes",
        "selected_revision_ids",
        "selected_source_hashes",
    ):
        if type(getattr(value, name)) is not tuple:
            raise TypeError(f"trace {name} must be an exact tuple")
    return ObservationCausalityTrace(
        view_hash=value.view_hash,
        query=_query(value.query),
        decision_instant=_simulation_instant(value.decision_instant),
        candidate_record_hashes=value.candidate_record_hashes,
        revision_set_hash=value.revision_set_hash,
        selected_observation_keys=value.selected_observation_keys,
        selected_event_hashes=value.selected_event_hashes,
        selected_revision_ids=value.selected_revision_ids,
        selected_source_hashes=value.selected_source_hashes,
        dataset_hash=value.dataset_hash,
        max_event_time=None if value.max_event_time is None else _utc(value.max_event_time),
        max_available_instant=(
            None
            if value.max_available_instant is None
            else _simulation_instant(value.max_available_instant)
        ),
        event_count=value.event_count,
    )


def _visible_result(value: object) -> PointInTimeObservationQueryResult:
    if type(value) is not PointInTimeObservationQueryResult:
        raise TypeError("visible_result must be exact PointInTimeObservationQueryResult")
    if type(value.events) is not tuple:
        raise TypeError("visible result events must be a tuple")
    return PointInTimeObservationQueryResult(
        view_hash=value.view_hash,
        query=_query(value.query),
        decision_instant=_simulation_instant(value.decision_instant),
        events=tuple(_event(event) for event in value.events),
        trace=_trace(value.trace),
    )


def _signal(value: object) -> SignalBarBinding:
    if type(value) is not SignalBarBinding:
        raise TypeError("signal_bindings must contain exact SignalBarBinding")
    try:
        return SignalBarBinding(
            value.requirement_hash,
            value.stream_key,
            value.price_purpose,
            value.aggregation_input_hash,
        )
    except AttributeError as error:
        raise ValueError("SignalBarBinding authority is invalid") from error


def _execution(value: object) -> ExecutionDataBinding:
    if type(value) is not ExecutionDataBinding:
        raise TypeError("execution_bindings must contain exact ExecutionDataBinding")
    try:
        return ExecutionDataBinding(value.profile_binding_key, value.stream_key)
    except AttributeError as error:
        raise ValueError("ExecutionDataBinding authority is invalid") from error


def _valuation(value: object) -> ValuationDataBinding:
    if type(value) is not ValuationDataBinding:
        raise TypeError("valuation_bindings must contain exact ValuationDataBinding")
    try:
        return ValuationDataBinding(value.instrument_id, value.stream_key)
    except AttributeError as error:
        raise ValueError("ValuationDataBinding authority is invalid") from error


@dataclass(frozen=True, slots=True)
class SignalBarBinding:
    requirement_hash: str
    stream_key: str
    price_purpose: PricePurpose
    aggregation_input_hash: str

    def __post_init__(self) -> None:
        _hash("requirement_hash", self.requirement_hash)
        _text("stream_key", self.stream_key)
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be exact PricePurpose")
        _hash("aggregation_input_hash", self.aggregation_input_hash)

    def _canonical_body(self) -> dict[str, object]:
        _hash("requirement_hash", self.requirement_hash)
        _text("stream_key", self.stream_key)
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be exact PricePurpose")
        _hash("aggregation_input_hash", self.aggregation_input_hash)
        return {
            "type": "signal_bar_binding",
            "schema_version": _SCHEMA_VERSION,
            "requirement_hash": self.requirement_hash,
            "stream_key": self.stream_key,
            "price_purpose": self.price_purpose.value,
            "aggregation_input_hash": self.aggregation_input_hash,
        }

    @property
    def signal_binding_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "signal_binding_hash": self.signal_binding_hash}


@dataclass(frozen=True, slots=True)
class ExecutionDataBinding:
    profile_binding_key: str
    stream_key: str

    def __post_init__(self) -> None:
        _text("profile_binding_key", self.profile_binding_key)
        _text("stream_key", self.stream_key)

    def _canonical_body(self) -> dict[str, object]:
        _text("profile_binding_key", self.profile_binding_key)
        _text("stream_key", self.stream_key)
        return {
            "type": "execution_data_binding",
            "schema_version": _SCHEMA_VERSION,
            "profile_binding_key": self.profile_binding_key,
            "stream_key": self.stream_key,
        }

    @property
    def execution_binding_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "execution_binding_hash": self.execution_binding_hash}


@dataclass(frozen=True, slots=True)
class ValuationDataBinding:
    instrument_id: InstrumentId
    stream_key: str

    def __post_init__(self) -> None:
        _instrument(self.instrument_id)
        _text("stream_key", self.stream_key)

    def _canonical_body(self) -> dict[str, object]:
        instrument_id = _instrument(self.instrument_id)
        _text("stream_key", self.stream_key)
        return {
            "type": "valuation_data_binding",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": instrument_id.to_canonical_dict(),
            "stream_key": self.stream_key,
        }

    @property
    def valuation_binding_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "valuation_binding_hash": self.valuation_binding_hash}


@dataclass(frozen=True, slots=True)
class MultiResolutionMarketDataBindings:
    signal_bindings: tuple[SignalBarBinding, ...]
    execution_bindings: tuple[ExecutionDataBinding, ...]
    valuation_bindings: tuple[ValuationDataBinding, ...]

    def __post_init__(self) -> None:
        if type(self.signal_bindings) is not tuple:
            raise TypeError("signal_bindings must be a tuple")
        if type(self.execution_bindings) is not tuple:
            raise TypeError("execution_bindings must be a tuple")
        if type(self.valuation_bindings) is not tuple:
            raise TypeError("valuation_bindings must be a tuple")
        signals = tuple(sorted((_signal(value) for value in self.signal_bindings), key=lambda value: (value.requirement_hash, value.stream_key, value.price_purpose.value, value.aggregation_input_hash)))
        executions = tuple(sorted((_execution(value) for value in self.execution_bindings), key=lambda value: (value.profile_binding_key, value.stream_key)))
        valuations = tuple(sorted((_valuation(value) for value in self.valuation_bindings), key=lambda value: (canonical_bytes(value.instrument_id), value.stream_key)))
        if len({value.requirement_hash for value in signals}) != len(signals):
            raise ValueError("duplicate signal binding identity")
        if len({value.profile_binding_key for value in executions}) != len(executions):
            raise ValueError("duplicate execution binding identity")
        if len({value.instrument_id for value in valuations}) != len(valuations):
            raise ValueError("duplicate valuation binding identity")
        object.__setattr__(self, "signal_bindings", signals)
        object.__setattr__(self, "execution_bindings", executions)
        object.__setattr__(self, "valuation_bindings", valuations)

    def _validated_values(self) -> tuple[tuple[SignalBarBinding, ...], tuple[ExecutionDataBinding, ...], tuple[ValuationDataBinding, ...]]:
        rebuilt = MultiResolutionMarketDataBindings(self.signal_bindings, self.execution_bindings, self.valuation_bindings)
        return rebuilt.signal_bindings, rebuilt.execution_bindings, rebuilt.valuation_bindings

    def _canonical_body(self) -> dict[str, object]:
        signals, executions, valuations = self._validated_values()
        return {
            "type": "multi_resolution_market_data_bindings",
            "schema_version": _SCHEMA_VERSION,
            "signal_bindings": [value.to_canonical_dict() for value in signals],
            "execution_bindings": [value.to_canonical_dict() for value in executions],
            "valuation_bindings": [value.to_canonical_dict() for value in valuations],
        }

    @property
    def bindings_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "bindings_hash": self.bindings_hash}


class SignalBarVerificationFailureCode(str, Enum):
    MALFORMED_G12G_PAYLOAD = "malformed_g12g_payload"
    BAR_DEFINITION_MISMATCH = "bar_definition_mismatch"
    AGGREGATION_LINEAGE_MISMATCH = "aggregation_lineage_mismatch"


@dataclass(frozen=True, slots=True)
class SignalBarVerificationFailure:
    code: SignalBarVerificationFailureCode
    event_position: int

    def __post_init__(self) -> None:
        if type(self.code) is not SignalBarVerificationFailureCode:
            raise TypeError("code must be exact SignalBarVerificationFailureCode")
        if type(self.event_position) is not int or self.event_position < 0:
            raise ValueError("event_position must be a non-negative exact integer")


@dataclass(frozen=True, slots=True)
class VerifiedSignalBarResult:
    requirement_hash: str
    events: tuple[MarketEvent, ...]

    def __post_init__(self) -> None:
        _hash("requirement_hash", self.requirement_hash)
        if type(self.events) is not tuple or any(type(value) is not MarketEvent for value in self.events):
            raise TypeError("events must be a tuple of exact MarketEvent")


@dataclass(frozen=True, slots=True)
class SignalBarVerificationOutcome:
    result: VerifiedSignalBarResult | None
    failure: SignalBarVerificationFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("exactly one result or failure is required")
        if self.result is not None and type(self.result) is not VerifiedSignalBarResult:
            raise TypeError("result must be exact VerifiedSignalBarResult or None")
        if self.failure is not None and type(self.failure) is not SignalBarVerificationFailure:
            raise TypeError("failure must be exact SignalBarVerificationFailure or None")


def _clock() -> int | None:
    try:
        value = _perf_counter_ns()
        return value if type(value) is int else None
    except BaseException:
        return None


def _record_observation(
    recorder: BoundedPerformanceRecorder,
    operation: PerformanceOperation,
    outcome: PerformanceOutcome,
    duration_ns: int,
    input_count: int,
    output_count: int,
) -> None:
    try:
        measurements = (duration_ns, input_count, output_count)
        if any(type(value) is not int or value < 0 for value in measurements):
            return
        duration_ns, input_count, output_count = (
            min(value, _MAX_OBSERVATION_VALUE) for value in measurements
        )
        recorder.record(
            operation=operation,
            outcome=outcome,
            duration_ns=duration_ns,
            input_count=input_count,
            output_count=output_count,
        )
    except BaseException:
        return


def _candidate_count(signal_bindings, execution_bindings, valuation_bindings) -> int:
    return len(signal_bindings) + len(execution_bindings) + len(valuation_bindings)


def _binding_count(bindings: MultiResolutionMarketDataBindings) -> int:
    return (
        len(bindings.signal_bindings)
        + len(bindings.execution_bindings)
        + len(bindings.valuation_bindings)
    )


def _event_count(events: tuple[MarketEvent, ...]) -> int:
    return len(events)


def construct_multi_resolution_market_data_bindings(
    *,
    signal_bindings: tuple[SignalBarBinding, ...],
    execution_bindings: tuple[ExecutionDataBinding, ...],
    valuation_bindings: tuple[ValuationDataBinding, ...],
    recorder: BoundedPerformanceRecorder | None = None,
) -> MultiResolutionMarketDataBindings:
    if recorder is None:
        return MultiResolutionMarketDataBindings(
            signal_bindings, execution_bindings, valuation_bindings
        )
    start = _clock()
    try:
        result = MultiResolutionMarketDataBindings(
            signal_bindings, execution_bindings, valuation_bindings
        )
    except BaseException:
        end = _clock()
        try:
            if start is not None and end is not None and end >= start:
                _record_observation(
                    recorder,
                    PerformanceOperation.CONSTRUCT_BINDINGS,
                    PerformanceOutcome.FAILED,
                    end - start,
                    _candidate_count(
                        signal_bindings, execution_bindings, valuation_bindings
                    ),
                    0,
                )
        except BaseException:
            pass
        raise
    end = _clock()
    try:
        if start is not None and end is not None and end >= start:
            _record_observation(
                recorder,
                PerformanceOperation.CONSTRUCT_BINDINGS,
                PerformanceOutcome.SUCCEEDED,
                end - start,
                _candidate_count(
                    signal_bindings, execution_bindings, valuation_bindings
                ),
                _binding_count(result),
            )
    except BaseException:
        pass
    return result


def validate_schedule_signal_exact_cover(
    schedule: DecisionSchedule,
    bindings: MultiResolutionMarketDataBindings,
    recorder: BoundedPerformanceRecorder | None = None,
) -> MultiResolutionMarketDataBindings:
    start = None if recorder is None else _clock()
    try:
        if type(schedule) is not DecisionSchedule:
            raise TypeError("schedule must be exact DecisionSchedule")
        if type(bindings) is not MultiResolutionMarketDataBindings:
            raise TypeError("bindings must be exact MultiResolutionMarketDataBindings")
        MultiResolutionMarketDataBindings(
            bindings.signal_bindings,
            bindings.execution_bindings,
            bindings.valuation_bindings,
        )
        expected = tuple(value.requirement_hash for value in schedule.requirements)
        actual = tuple(value.requirement_hash for value in bindings.signal_bindings)
        if set(actual) != set(expected) or len(actual) != len(expected):
            raise ValueError("signal bindings must exact-cover schedule requirements")
        by_hash = {value.requirement_hash: value for value in bindings.signal_bindings}
        for requirement in schedule.requirements:
            if (
                by_hash[requirement.requirement_hash].stream_key
                != requirement.observation_query.dataset_key
            ):
                raise ValueError(
                    "signal binding stream must match requirement observation stream"
                )
        result = bindings
    except BaseException:
        if recorder is not None:
            end = _clock()
            try:
                if start is not None and end is not None and end >= start:
                    _record_observation(
                        recorder,
                        PerformanceOperation.VALIDATE_BINDINGS,
                        PerformanceOutcome.FAILED,
                        end - start,
                        len(bindings.signal_bindings),
                        0,
                    )
            except BaseException:
                pass
        raise
    if recorder is not None:
        end = _clock()
        try:
            if start is not None and end is not None and end >= start:
                _record_observation(
                    recorder,
                    PerformanceOperation.VALIDATE_BINDINGS,
                    PerformanceOutcome.SUCCEEDED,
                    end - start,
                    len(bindings.signal_bindings),
                    len(result.signal_bindings),
                )
        except BaseException:
            pass
    return result


def _keys(value: object, expected: set[str]) -> bool:
    try:
        return set(value) == expected  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _utc_payload(value: object) -> int:
    if not _keys(value, {"type", "epoch_nanoseconds"}):
        raise ValueError("invalid UtcInstant payload")
    if value["type"] != "utc_instant" or type(value["epoch_nanoseconds"]) is not int:  # type: ignore[index]
        raise ValueError("invalid UtcInstant payload")
    instant = UtcInstant(value["epoch_nanoseconds"])  # type: ignore[index]
    if instant.to_canonical_dict() != dict(value):  # type: ignore[arg-type]
        raise ValueError("noncanonical UtcInstant payload")
    return instant.epoch_nanoseconds


def _session_payload(value: object) -> SessionId:
    if not _keys(value, {"type", "calendar_id", "value"}):
        raise ValueError("invalid SessionId payload")
    if value["type"] != "session_id":  # type: ignore[index]
        raise ValueError("invalid SessionId payload")
    result = SessionId(value["calendar_id"], value["value"])  # type: ignore[index]
    if result.to_canonical_dict() != dict(value):  # type: ignore[arg-type]
        raise ValueError("noncanonical SessionId payload")
    return result


def _trading_date_payload(value: object) -> TradingDate:
    if not _keys(value, {"type", "calendar_id", "date"}):
        raise ValueError("invalid TradingDate payload")
    if value["type"] != "trading_date" or type(value["date"]) is not str:  # type: ignore[index]
        raise ValueError("invalid TradingDate payload")
    parsed = date.fromisoformat(value["date"])  # type: ignore[index]
    if parsed.isoformat() != value["date"]:  # type: ignore[index]
        raise ValueError("noncanonical TradingDate payload")
    result = TradingDate(value["calendar_id"], parsed)  # type: ignore[index]
    if result.to_canonical_dict() != dict(value):  # type: ignore[arg-type]
        raise ValueError("noncanonical TradingDate payload")
    return result


def _price_payload(value: object, scale: int) -> int:
    if not _keys(value, {"units", "scale"}):
        raise ValueError("invalid price payload")
    units = value["units"]  # type: ignore[index]
    item_scale = value["scale"]  # type: ignore[index]
    if type(units) is not int or type(item_scale) is not int or item_scale != scale:
        raise ValueError("invalid price payload")
    return units


def _bucket_hash(payload) -> str:
    session_id = _session_payload(payload["session_id"])
    trading_date = _trading_date_payload(payload["trading_date"])
    if session_id.calendar_id != trading_date.calendar_id:
        raise ValueError("bucket calendar mismatch")
    spans = payload["included_spans"]
    if type(spans) is not tuple or not spans:
        raise ValueError("included_spans must be nonempty canonical list")
    normalized: list[dict[str, object]] = []
    previous_end: int | None = None
    for span in spans:
        if not _keys(span, {"start", "end_exclusive"}):
            raise ValueError("invalid included span")
        start = _utc_payload(span["start"])
        end = _utc_payload(span["end_exclusive"])
        if end <= start or (previous_end is not None and start < previous_end):
            raise ValueError("included spans must be ordered nonempty and disjoint")
        previous_end = end
        normalized.append({"start": dict(span["start"]), "end_exclusive": dict(span["end_exclusive"])})
    interval_start = _utc_payload(payload["interval_start"])
    interval_end = _utc_payload(payload["interval_end_exclusive"])
    if interval_start != _utc_payload(spans[0]["start"]) or interval_end != _utc_payload(spans[-1]["end_exclusive"]):
        raise ValueError("included spans must cover interval boundaries")
    body = {
        "type": "bar_bucket",
        "schema_version": _SCHEMA_VERSION,
        "session_id": session_id.to_canonical_dict(),
        "trading_date": trading_date.to_canonical_dict(),
        "included_spans": normalized,
        "interval_start": dict(payload["interval_start"]),
        "interval_end_exclusive": dict(payload["interval_end_exclusive"]),
    }
    return canonical_sha256(body)


def _malformed(requirement: LookbackRequirement, binding: SignalBarBinding, stream_manifest: MarketStreamManifest, event: MarketEvent) -> bool:
    try:
        payload = event.payload
        if (
            type(event) is not MarketEvent
            or event.event_type != "bar"
            or event.source_key != "canonical-bar-aggregation-v1"
            or event.stream_key != binding.stream_key
            or event.stream_key != requirement.observation_query.dataset_key
            or event.instrument_id != requirement.observation_query.instrument_id
            or type(event.capability) is not MarketBundleCapability
            or event.capability != _BAR_CAPABILITY
            or event.capability != requirement.observation_query.capability
            or event.stream_key != stream_manifest.stream_key
            or event.event_type != stream_manifest.event_type
            or event.capability != stream_manifest.capability
            or not _keys(payload, _PAYLOAD_FIELDS)
        ):
            return True
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            return True
        if payload["aggregation_spec_hash"] != _AGGREGATION_SPEC_HASH:
            return True
        for name in (
            "bar_definition_hash", "source_stream_hash", "bucket_plan_hash",
            "aggregation_spec_hash", "aggregation_code_hash", "aggregation_input_hash",
            "bucket_hash", "selected_source_set_hash",
        ):
            _hash(name, payload[name])
        _text("bar_definition_key", payload["bar_definition_key"])
        if type(payload["bar_definition_version"]) is not int or payload["bar_definition_version"] <= 0:
            return True
        if type(payload["price_purpose"]) is not str:
            return True
        PricePurpose(payload["price_purpose"])
        scale = payload["price_scale"]
        if type(scale) is not int or scale < 0:
            return True
        open_units = _price_payload(payload["open"], scale)
        high_units = _price_payload(payload["high"], scale)
        low_units = _price_payload(payload["low"], scale)
        close_units = _price_payload(payload["close"], scale)
        if not low_units <= open_units <= high_units or not low_units <= close_units <= high_units:
            return True
        if payload["volume"] is not None:
            return True
        source_hashes = payload["source_event_hashes"]
        if type(source_hashes) is not tuple or not source_hashes:
            return True
        for value in source_hashes:
            _hash("source_event_hash", value)
        count = payload["observation_count"]
        if type(count) is not int or count <= 0 or count != len(source_hashes):
            return True
        if payload["selected_source_set_hash"] != canonical_sha256(source_hashes):
            return True
        if payload["bucket_hash"] != _bucket_hash(payload):
            return True
        interval_start = _utc_payload(payload["interval_start"])
        interval_end = _utc_payload(payload["interval_end_exclusive"])
        if event.event_time.epoch_nanoseconds != interval_start or event.available_time.epoch_nanoseconds < interval_end:
            return True
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return True
    return False


def verify_visible_signal_bars(
    requirement: LookbackRequirement,
    binding: SignalBarBinding,
    stream_manifest: MarketStreamManifest,
    visible_result: PointInTimeObservationQueryResult,
    recorder: BoundedPerformanceRecorder | None = None,
) -> SignalBarVerificationOutcome:
    start = None if recorder is None else _clock()
    try:
        if type(requirement) is not LookbackRequirement:
            raise TypeError("requirement must be exact LookbackRequirement")
        if type(binding) is not SignalBarBinding:
            raise TypeError("binding must be exact SignalBarBinding")
        binding_copy = _signal(binding)
        if type(stream_manifest) is not MarketStreamManifest:
            raise TypeError("stream_manifest must be exact MarketStreamManifest")
        try:
            manifest = MarketStreamManifest(
                stream_manifest.stream_key,
                stream_manifest.event_type,
                _capability(stream_manifest.capability),
                stream_manifest.event_count,
                stream_manifest.content_hash,
            )
        except AttributeError as error:
            raise ValueError("stream_manifest authority is invalid") from error
        if (
            manifest.stream_key != binding_copy.stream_key
            or manifest.event_type != "bar"
            or manifest.capability != _BAR_CAPABILITY
            or manifest.capability != requirement.observation_query.capability
        ):
            raise ValueError("stream_manifest must match signal binding and requirement")
        rebuilt = _visible_result(visible_result)
        if binding_copy.requirement_hash != requirement.requirement_hash:
            raise ValueError("binding requirement_hash must match requirement")
        if rebuilt.query != requirement.observation_query:
            raise ValueError("visible result Query must match requirement")
        failures: list[tuple[int, int, SignalBarVerificationFailureCode]] = []
        for position, event in enumerate(rebuilt.events):
            if _malformed(requirement, binding_copy, manifest, event):
                failures.append(
                    (
                        0,
                        position,
                        SignalBarVerificationFailureCode.MALFORMED_G12G_PAYLOAD,
                    )
                )
                continue
            payload = event.payload
            if (
                payload["bar_definition_key"] != requirement.bar_definition.key
                or payload["bar_definition_version"]
                != requirement.bar_definition.version
                or payload["bar_definition_hash"]
                != requirement.bar_definition.definition_hash
                or payload["price_purpose"] != binding_copy.price_purpose.value
            ):
                failures.append(
                    (
                        1,
                        position,
                        SignalBarVerificationFailureCode.BAR_DEFINITION_MISMATCH,
                    )
                )
            elif (
                payload["aggregation_input_hash"]
                != binding_copy.aggregation_input_hash
                or event.source_hash != binding_copy.aggregation_input_hash
            ):
                failures.append(
                    (
                        2,
                        position,
                        SignalBarVerificationFailureCode.AGGREGATION_LINEAGE_MISMATCH,
                    )
                )
        if failures:
            _, position, code = min(failures)
            outcome = SignalBarVerificationOutcome(
                None, SignalBarVerificationFailure(code, position)
            )
        else:
            outcome = SignalBarVerificationOutcome(
                VerifiedSignalBarResult(
                    requirement.requirement_hash, rebuilt.events
                ),
                None,
            )
    except BaseException:
        if recorder is not None:
            end = _clock()
            try:
                if start is not None and end is not None and end >= start:
                    _record_observation(
                        recorder,
                        PerformanceOperation.VERIFY_SIGNAL_BAR,
                        PerformanceOutcome.FAILED,
                        end - start,
                        _event_count(visible_result.events),
                        0,
                    )
            except BaseException:
                pass
        raise
    if recorder is not None:
        end = _clock()
        try:
            performance_outcome = (
                PerformanceOutcome.FAILED
                if outcome.failure is not None
                else PerformanceOutcome.SUCCEEDED
            )
            output_count = (
                0
                if outcome.result is None
                else _event_count(outcome.result.events)
            )
            if start is not None and end is not None and end >= start:
                _record_observation(
                    recorder,
                    PerformanceOperation.VERIFY_SIGNAL_BAR,
                    performance_outcome,
                    end - start,
                    _event_count(rebuilt.events),
                    output_count,
                )
        except BaseException:
            pass
    return outcome
