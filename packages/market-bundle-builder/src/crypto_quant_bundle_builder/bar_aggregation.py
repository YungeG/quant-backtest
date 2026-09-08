from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    Scale,
    SessionId,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .bundle_validation import validate_market_bundle_v1

_SCHEMA_VERSION = 1
_AGGREGATION_ID = "canonical_bar_aggregation@1"
_SOURCE_EVENT_TYPE = "synthetic_price_point.v1"
_AGGREGATION_KIND = "explicit_bucket_price_ohlc"
_VOLUME_SEMANTICS = "none"
_EMPTY_INTERVAL_POLICY = "omit"
_BAR_CAPABILITY = MarketBundleCapability("price_bars", 1)


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


def _nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _validate_utc(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be UtcInstant")
    UtcInstant(cast(UtcInstant, value).epoch_nanoseconds)
    return value


def _validate_session(value: object) -> SessionId:
    if type(value) is not SessionId:
        raise TypeError("session_id must be SessionId")
    SessionId(cast(SessionId, value).calendar_id, cast(SessionId, value).value)
    return value


def _validate_trading_date(value: object) -> TradingDate:
    if type(value) is not TradingDate:
        raise TypeError("trading_date must be TradingDate")
    TradingDate(cast(TradingDate, value).calendar_id, cast(TradingDate, value).value)
    return value


def _validate_capability(value: object) -> MarketBundleCapability:
    if type(value) is not MarketBundleCapability:
        raise TypeError("source_capability must be MarketBundleCapability")
    MarketBundleCapability(
        cast(MarketBundleCapability, value).key,
        cast(MarketBundleCapability, value).version,
    )
    return value


def _validate_phase(value: object) -> TimelinePhase:
    if type(value) is not TimelinePhase:
        raise TypeError("output_phase must be TimelinePhase")
    TimelinePhase(cast(TimelinePhase, value).rank, cast(TimelinePhase, value).code)
    return value


def _aggregation_spec_hash() -> str:
    return canonical_sha256(
        {
            "type": "bar_aggregation_spec",
            "schema_version": _SCHEMA_VERSION,
            "aggregation_id": _AGGREGATION_ID,
        }
    )


@dataclass(frozen=True, slots=True)
class BarBucket:
    session_id: SessionId
    trading_date: TradingDate
    included_spans: tuple[tuple[UtcInstant, UtcInstant], ...]
    interval_start: UtcInstant
    interval_end_exclusive: UtcInstant

    def __post_init__(self) -> None:
        session_id = _validate_session(self.session_id)
        trading_date = _validate_trading_date(self.trading_date)
        if session_id.calendar_id != trading_date.calendar_id:
            raise ValueError("SessionId and TradingDate calendar_id must match")
        if type(self.included_spans) is not tuple or not self.included_spans:
            raise ValueError("included_spans must be a non-empty tuple")
        previous_end: int | None = None
        for span in self.included_spans:
            if type(span) is not tuple or len(span) != 2:
                raise TypeError(
                    "included_spans entries must be (start, end_exclusive) tuples"
                )
            start = _validate_utc("included span start", span[0])
            end = _validate_utc("included span end_exclusive", span[1])
            if end.epoch_nanoseconds <= start.epoch_nanoseconds:
                raise ValueError("included spans must be non-empty half-open ranges")
            if previous_end is not None and start.epoch_nanoseconds < previous_end:
                raise ValueError("included spans must be ordered and disjoint")
            previous_end = end.epoch_nanoseconds
        interval_start = _validate_utc("interval_start", self.interval_start)
        interval_end = _validate_utc(
            "interval_end_exclusive", self.interval_end_exclusive
        )
        if interval_start != self.included_spans[0][0]:
            raise ValueError("interval_start must equal the first span start")
        if interval_end != self.included_spans[-1][1]:
            raise ValueError("interval_end_exclusive must equal the final span end")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "bar_bucket",
            "schema_version": _SCHEMA_VERSION,
            "session_id": self.session_id.to_canonical_dict(),
            "trading_date": self.trading_date.to_canonical_dict(),
            "included_spans": [
                {
                    "start": start.to_canonical_dict(),
                    "end_exclusive": end.to_canonical_dict(),
                }
                for start, end in self.included_spans
            ],
            "interval_start": self.interval_start.to_canonical_dict(),
            "interval_end_exclusive": self.interval_end_exclusive.to_canonical_dict(),
        }

    @property
    def bucket_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "bucket_hash": self.bucket_hash}


@dataclass(frozen=True, slots=True)
class BarBucketPlan:
    plan_key: str
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    bar_definition_key: str
    bar_definition_version: int
    bar_definition_hash: str
    buckets: tuple[BarBucket, ...]

    def __post_init__(self) -> None:
        _text("plan_key", self.plan_key)
        coverage_start = _validate_utc("coverage_start", self.coverage_start)
        coverage_end = _validate_utc(
            "coverage_end_exclusive", self.coverage_end_exclusive
        )
        if coverage_end.epoch_nanoseconds <= coverage_start.epoch_nanoseconds:
            raise ValueError("coverage must be a non-empty half-open range")
        _text("bar_definition_key", self.bar_definition_key)
        _positive_int("bar_definition_version", self.bar_definition_version)
        _hash("bar_definition_hash", self.bar_definition_hash)
        if type(self.buckets) is not tuple or any(
            type(bucket) is not BarBucket for bucket in self.buckets
        ):
            raise TypeError("buckets must be a tuple of BarBucket")
        previous_end: int | None = None
        for bucket in self.buckets:
            BarBucket(
                session_id=bucket.session_id,
                trading_date=bucket.trading_date,
                included_spans=bucket.included_spans,
                interval_start=bucket.interval_start,
                interval_end_exclusive=bucket.interval_end_exclusive,
            )
            for start, end in bucket.included_spans:
                if (
                    start.epoch_nanoseconds < coverage_start.epoch_nanoseconds
                    or end.epoch_nanoseconds > coverage_end.epoch_nanoseconds
                ):
                    raise ValueError("bucket spans must lie inside plan coverage")
                if previous_end is not None and start.epoch_nanoseconds < previous_end:
                    raise ValueError(
                        "flattened bucket spans must be ordered and non-overlapping"
                    )
                previous_end = end.epoch_nanoseconds

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "bar_bucket_plan",
            "schema_version": _SCHEMA_VERSION,
            "plan_key": self.plan_key,
            "coverage_start": self.coverage_start.to_canonical_dict(),
            "coverage_end_exclusive": self.coverage_end_exclusive.to_canonical_dict(),
            "bar_definition_key": self.bar_definition_key,
            "bar_definition_version": self.bar_definition_version,
            "bar_definition_hash": self.bar_definition_hash,
            "buckets": [bucket._canonical_body() for bucket in self.buckets],
        }

    @property
    def bucket_plan_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "bucket_plan_hash": self.bucket_plan_hash}


@dataclass(frozen=True, slots=True)
class BarDefinition:
    key: str
    version: int
    output_stream_key: str
    aggregation_kind: str
    source_stream_key: str
    source_event_type: str
    source_capability: MarketBundleCapability
    price_purpose: PricePurpose
    price_scale: Scale
    volume_semantics: str
    empty_interval_policy: str
    output_phase: TimelinePhase

    def __post_init__(self) -> None:
        _text("key", self.key)
        _positive_int("version", self.version)
        _text("output_stream_key", self.output_stream_key)
        _text("source_stream_key", self.source_stream_key)
        if self.output_stream_key == self.source_stream_key:
            raise ValueError("source and output stream keys must differ")
        if self.aggregation_kind != _AGGREGATION_KIND:
            raise ValueError(f"aggregation_kind must be {_AGGREGATION_KIND}")
        if self.source_event_type != _SOURCE_EVENT_TYPE:
            raise ValueError(f"source_event_type must be {_SOURCE_EVENT_TYPE}")
        _validate_capability(self.source_capability)
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be PricePurpose")
        if type(self.price_scale) is not Scale:
            raise TypeError("price_scale must be Scale")
        Scale(self.price_scale.places)
        if self.volume_semantics != _VOLUME_SEMANTICS:
            raise ValueError(f"volume_semantics must be {_VOLUME_SEMANTICS}")
        if self.empty_interval_policy != _EMPTY_INTERVAL_POLICY:
            raise ValueError(f"empty_interval_policy must be {_EMPTY_INTERVAL_POLICY}")
        _validate_phase(self.output_phase)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "bar_definition",
            "schema_version": _SCHEMA_VERSION,
            "key": self.key,
            "version": self.version,
            "output_stream_key": self.output_stream_key,
            "aggregation_kind": self.aggregation_kind,
            "source_stream_key": self.source_stream_key,
            "source_event_type": self.source_event_type,
            "source_capability": self.source_capability.to_canonical_dict(),
            "price_purpose": self.price_purpose.value,
            "price_scale": self.price_scale.places,
            "volume_semantics": self.volume_semantics,
            "empty_interval_policy": self.empty_interval_policy,
            "output_phase": self.output_phase.to_canonical_dict(),
        }

    @property
    def definition_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "definition_hash": self.definition_hash}


class BarAggregationFailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    SOURCE_BUNDLE_MISMATCH = "source_bundle_mismatch"
    DEFINITION_BUCKET_PLAN_MISMATCH = "definition_bucket_plan_mismatch"
    SOURCE_STREAM_MISMATCH = "source_stream_mismatch"
    SOURCE_COVERAGE_UNALIGNED = "source_coverage_unaligned"
    SOURCE_EVENT_INVALID = "source_event_invalid"
    REVISION_CHAIN_INVALID = "revision_chain_invalid"
    OUTPUT_CAUSALITY_INVALID = "output_causality_invalid"
    OUTPUT_VALIDATION_FAILED = "output_validation_failed"


@dataclass(frozen=True, slots=True)
class BarAggregationFailure:
    code: BarAggregationFailureCode
    stream_key: str | None
    input_position: int | None
    interval_hash: str | None

    def __post_init__(self) -> None:
        if type(self.code) is not BarAggregationFailureCode:
            raise TypeError("code must be BarAggregationFailureCode")
        if self.stream_key is not None:
            _text("stream_key", self.stream_key)
        if self.input_position is not None:
            _nonnegative_int("input_position", self.input_position)
        if self.interval_hash is not None:
            _hash("interval_hash", self.interval_hash)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "bar_aggregation_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "stream_key": self.stream_key,
            "input_position": self.input_position,
            "interval_hash": self.interval_hash,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return self._canonical_body()


@dataclass(frozen=True, slots=True)
class BarAggregationManifest:
    source_bundle_ref: MarketBundleRef
    source_stream_manifest: MarketStreamManifest
    source_stream_hash: str
    bar_definition: BarDefinition
    bucket_plan_key: str
    bucket_plan_hash: str
    aggregation_spec_hash: str
    aggregation_code_hash: str
    aggregation_input_hash: str
    input_event_count: int
    source_stream_event_count: int
    selected_source_revision_count: int
    assigned_source_revision_count: int
    out_of_plan_source_revision_count: int
    nonselected_source_event_count: int
    candidate_instrument_count: int
    planned_bucket_count: int
    empty_bucket_instrument_count: int
    output_root_count: int
    output_revision_count: int
    output_stream_manifest: MarketStreamManifest | None
    output_bundle_ref: MarketBundleRef
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.source_bundle_ref) is not MarketBundleRef:
            raise TypeError("source_bundle_ref must be MarketBundleRef")
        MarketBundleRef(
            self.source_bundle_ref.bundle_key, self.source_bundle_ref.manifest_hash
        )
        if type(self.source_stream_manifest) is not MarketStreamManifest:
            raise TypeError("source_stream_manifest must be MarketStreamManifest")
        MarketStreamManifest(
            stream_key=self.source_stream_manifest.stream_key,
            event_type=self.source_stream_manifest.event_type,
            capability=self.source_stream_manifest.capability,
            event_count=self.source_stream_manifest.event_count,
            content_hash=self.source_stream_manifest.content_hash,
        )
        _hash("source_stream_hash", self.source_stream_hash)
        if self.source_stream_hash != self.source_stream_manifest.content_hash:
            raise ValueError("source_stream_hash must match source stream manifest")
        if type(self.bar_definition) is not BarDefinition:
            raise TypeError("bar_definition must be BarDefinition")
        BarDefinition(
            key=self.bar_definition.key,
            version=self.bar_definition.version,
            output_stream_key=self.bar_definition.output_stream_key,
            aggregation_kind=self.bar_definition.aggregation_kind,
            source_stream_key=self.bar_definition.source_stream_key,
            source_event_type=self.bar_definition.source_event_type,
            source_capability=self.bar_definition.source_capability,
            price_purpose=self.bar_definition.price_purpose,
            price_scale=self.bar_definition.price_scale,
            volume_semantics=self.bar_definition.volume_semantics,
            empty_interval_policy=self.bar_definition.empty_interval_policy,
            output_phase=self.bar_definition.output_phase,
        )
        if (
            self.source_stream_manifest.stream_key
            != self.bar_definition.source_stream_key
            or self.source_stream_manifest.event_type
            != self.bar_definition.source_event_type
            or self.source_stream_manifest.capability
            != self.bar_definition.source_capability
        ):
            raise ValueError("source stream manifest must match BarDefinition")
        _text("bucket_plan_key", self.bucket_plan_key)
        for name, value in (
            ("bucket_plan_hash", self.bucket_plan_hash),
            ("aggregation_spec_hash", self.aggregation_spec_hash),
            ("aggregation_code_hash", self.aggregation_code_hash),
            ("aggregation_input_hash", self.aggregation_input_hash),
        ):
            _hash(name, value)
        if self.aggregation_spec_hash != _aggregation_spec_hash():
            raise ValueError(
                "aggregation_spec_hash must match canonical_bar_aggregation@1"
            )
        expected_input_hash = _aggregation_input_hash(
            source_bundle_ref=self.source_bundle_ref,
            source_stream_manifest=self.source_stream_manifest,
            definition=self.bar_definition,
            bucket_plan_hash=self.bucket_plan_hash,
            aggregation_spec_hash=self.aggregation_spec_hash,
            aggregation_code_hash=self.aggregation_code_hash,
        )
        if self.aggregation_input_hash != expected_input_hash:
            raise ValueError("aggregation_input_hash does not match aggregation inputs")
        count_names = (
            "input_event_count",
            "source_stream_event_count",
            "selected_source_revision_count",
            "assigned_source_revision_count",
            "out_of_plan_source_revision_count",
            "nonselected_source_event_count",
            "candidate_instrument_count",
            "planned_bucket_count",
            "empty_bucket_instrument_count",
            "output_root_count",
            "output_revision_count",
        )
        for name in count_names:
            _nonnegative_int(name, getattr(self, name))
        if self.input_event_count < self.source_stream_event_count:
            raise ValueError("input_event_count must cover the source stream")
        if self.source_stream_event_count != (
            self.selected_source_revision_count + self.nonselected_source_event_count
        ):
            raise ValueError("source stream counts do not reconcile")
        if self.selected_source_revision_count != (
            self.assigned_source_revision_count + self.out_of_plan_source_revision_count
        ):
            raise ValueError("selected source counts do not reconcile")
        if self.output_root_count > self.output_revision_count:
            raise ValueError("output roots cannot exceed output revisions")
        if self.output_stream_manifest is None:
            if self.output_revision_count != 0:
                raise ValueError("non-empty output requires an output stream manifest")
        else:
            if type(self.output_stream_manifest) is not MarketStreamManifest:
                raise TypeError(
                    "output_stream_manifest must be MarketStreamManifest or None"
                )
            MarketStreamManifest(
                stream_key=self.output_stream_manifest.stream_key,
                event_type=self.output_stream_manifest.event_type,
                capability=self.output_stream_manifest.capability,
                event_count=self.output_stream_manifest.event_count,
                content_hash=self.output_stream_manifest.content_hash,
            )
            if (
                self.output_stream_manifest.stream_key
                != self.bar_definition.output_stream_key
                or self.output_stream_manifest.event_type != "bar"
                or self.output_stream_manifest.capability != _BAR_CAPABILITY
                or self.output_stream_manifest.event_count != self.output_revision_count
                or self.output_revision_count == 0
            ):
                raise ValueError("output stream manifest does not match generated Bars")
        if type(self.output_bundle_ref) is not MarketBundleRef:
            raise TypeError("output_bundle_ref must be MarketBundleRef")
        MarketBundleRef(
            self.output_bundle_ref.bundle_key, self.output_bundle_ref.manifest_hash
        )
        expected_output_key = (
            self.source_bundle_ref.bundle_key
            + ".bar-aggregation-v1."
            + self.aggregation_input_hash.removeprefix("sha256:")
        )
        if self.output_bundle_ref.bundle_key != expected_output_key:
            raise ValueError(
                "output Bundle key does not match aggregation input identity"
            )
        if (
            type(self.decision_grade_eligible) is not bool
            or type(self.deployment_authorized) is not bool
        ):
            raise TypeError("qualification flags must be bool")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G12G qualification flags must remain false")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "bar_aggregation_manifest",
            "schema_version": _SCHEMA_VERSION,
            "source_bundle_ref": self.source_bundle_ref.to_canonical_dict(),
            "source_stream_manifest": self.source_stream_manifest.to_canonical_dict(),
            "source_stream_hash": self.source_stream_hash,
            "bar_definition": self.bar_definition.to_canonical_dict(),
            "bucket_plan_key": self.bucket_plan_key,
            "bucket_plan_hash": self.bucket_plan_hash,
            "aggregation_spec_hash": self.aggregation_spec_hash,
            "aggregation_code_hash": self.aggregation_code_hash,
            "aggregation_input_hash": self.aggregation_input_hash,
            "input_event_count": self.input_event_count,
            "source_stream_event_count": self.source_stream_event_count,
            "selected_source_revision_count": self.selected_source_revision_count,
            "assigned_source_revision_count": self.assigned_source_revision_count,
            "out_of_plan_source_revision_count": self.out_of_plan_source_revision_count,
            "nonselected_source_event_count": self.nonselected_source_event_count,
            "candidate_instrument_count": self.candidate_instrument_count,
            "planned_bucket_count": self.planned_bucket_count,
            "empty_bucket_instrument_count": self.empty_bucket_instrument_count,
            "output_root_count": self.output_root_count,
            "output_revision_count": self.output_revision_count,
            "output_stream_manifest": (
                None
                if self.output_stream_manifest is None
                else self.output_stream_manifest.to_canonical_dict()
            ),
            "output_bundle_ref": self.output_bundle_ref.to_canonical_dict(),
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "manifest_hash": self.manifest_hash}


@dataclass(frozen=True, slots=True)
class BarAggregationResult:
    generated_events: tuple[MarketEvent, ...]
    output_manifest: MarketBundleManifest
    aggregation_manifest: BarAggregationManifest

    def __post_init__(self) -> None:
        if type(self.generated_events) is not tuple or any(
            type(event) is not MarketEvent for event in self.generated_events
        ):
            raise TypeError("generated_events must be a tuple of MarketEvent")
        for event in self.generated_events:
            _copy_event(event)
        if type(self.output_manifest) is not MarketBundleManifest:
            raise TypeError("output_manifest must be MarketBundleManifest")
        MarketBundleManifest(
            bundle_key=self.output_manifest.bundle_key,
            schema_version=self.output_manifest.schema_version,
            coverage_start=self.output_manifest.coverage_start,
            coverage_end_exclusive=self.output_manifest.coverage_end_exclusive,
            instrument_catalog_hash=self.output_manifest.instrument_catalog_hash,
            capabilities=self.output_manifest.capabilities,
            streams=self.output_manifest.streams,
            content_hash=self.output_manifest.content_hash,
        )
        if type(self.aggregation_manifest) is not BarAggregationManifest:
            raise TypeError("aggregation_manifest must be BarAggregationManifest")
        if MarketBundleRef.from_manifest(self.output_manifest) != (
            self.aggregation_manifest.output_bundle_ref
        ):
            raise ValueError("output manifest must match aggregation output Bundle ref")
        if (
            len(self.generated_events)
            != self.aggregation_manifest.output_revision_count
        ):
            raise ValueError("generated Event count must match aggregation manifest")
        if (
            sum(event.supersedes_revision_id is None for event in self.generated_events)
            != self.aggregation_manifest.output_root_count
        ):
            raise ValueError("generated root count must match aggregation manifest")
        if any(
            event.event_type != "bar"
            or event.stream_key
            != self.aggregation_manifest.bar_definition.output_stream_key
            or event.capability != _BAR_CAPABILITY
            for event in self.generated_events
        ):
            raise ValueError("generated Events must be the declared Bar stream")
        declared = next(
            (
                stream
                for stream in self.output_manifest.streams
                if stream.stream_key
                == self.aggregation_manifest.bar_definition.output_stream_key
            ),
            None,
        )
        if declared != self.aggregation_manifest.output_stream_manifest:
            raise ValueError(
                "output manifest Bar stream must match aggregation manifest"
            )
        if declared is not None and declared.content_hash != canonical_sha256(
            self.generated_events
        ):
            raise ValueError("generated Events must match output stream content hash")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "bar_aggregation_result",
            "schema_version": _SCHEMA_VERSION,
            "generated_events": [
                event.to_canonical_dict() for event in self.generated_events
            ],
            "output_manifest": self.output_manifest.to_canonical_dict(),
            "aggregation_manifest": self.aggregation_manifest.to_canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class BarAggregationOutcome:
    result: BarAggregationResult | None
    failure: BarAggregationFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and type(self.result) is not BarAggregationResult:
            raise TypeError("result must be BarAggregationResult or None")
        if self.failure is not None and type(self.failure) is not BarAggregationFailure:
            raise TypeError("failure must be BarAggregationFailure or None")


@dataclass(frozen=True, slots=True)
class _SelectedObservation:
    input_position: int
    event: MarketEvent
    instrument_id: InstrumentId
    record_key: str
    price_units: int
    bucket_index: int | None


@dataclass(frozen=True, slots=True)
class _ObservationChain:
    observations: tuple[_SelectedObservation, ...]


@dataclass(frozen=True, slots=True)
class _BarCandidate:
    available_time: UtcInstant
    instrument_id: InstrumentId
    bucket_index: int
    bucket: BarBucket
    observations: tuple[_SelectedObservation, ...]
    source_event_hashes: tuple[str, ...]
    selected_source_set_hash: str
    revision_identity_hash: str
    supersedes_revision_id: str | None


def _failed(
    code: BarAggregationFailureCode,
    *,
    stream_key: str | None = None,
    input_position: int | None = None,
    interval_hash: str | None = None,
) -> BarAggregationOutcome:
    return BarAggregationOutcome(
        result=None,
        failure=BarAggregationFailure(
            code=code,
            stream_key=stream_key,
            input_position=input_position,
            interval_hash=interval_hash,
        ),
    )


def _copy_event(event: MarketEvent) -> None:
    MarketEvent(
        event_id=event.event_id,
        stream_key=event.stream_key,
        event_type=event.event_type,
        capability=event.capability,
        instrument_id=event.instrument_id,
        event_time=event.event_time,
        available_time=event.available_time,
        phase=event.phase,
        source_sequence=event.source_sequence,
        revision_id=event.revision_id,
        supersedes_revision_id=event.supersedes_revision_id,
        source_key=event.source_key,
        source_hash=event.source_hash,
        payload=event.payload,
    )


def _validate_aggregation_inputs(
    source_manifest: object,
    source_events: object,
    bucket_plan: object,
    definition: object,
    aggregation_code_hash: object,
) -> bool:
    if (
        type(source_manifest) is not MarketBundleManifest
        or type(source_events) is not tuple
        or any(type(event) is not MarketEvent for event in source_events)
        or type(bucket_plan) is not BarBucketPlan
        or type(definition) is not BarDefinition
    ):
        return False
    try:
        _hash("aggregation_code_hash", aggregation_code_hash)
        manifest = cast(MarketBundleManifest, source_manifest)
        MarketBundleManifest(
            bundle_key=manifest.bundle_key,
            schema_version=manifest.schema_version,
            coverage_start=manifest.coverage_start,
            coverage_end_exclusive=manifest.coverage_end_exclusive,
            instrument_catalog_hash=manifest.instrument_catalog_hash,
            capabilities=manifest.capabilities,
            streams=manifest.streams,
            content_hash=manifest.content_hash,
        )
        for event in cast(tuple[MarketEvent, ...], source_events):
            _copy_event(event)
        dfn = cast(BarDefinition, definition)
        BarDefinition(
            key=dfn.key,
            version=dfn.version,
            output_stream_key=dfn.output_stream_key,
            aggregation_kind=dfn.aggregation_kind,
            source_stream_key=dfn.source_stream_key,
            source_event_type=dfn.source_event_type,
            source_capability=dfn.source_capability,
            price_purpose=dfn.price_purpose,
            price_scale=dfn.price_scale,
            volume_semantics=dfn.volume_semantics,
            empty_interval_policy=dfn.empty_interval_policy,
            output_phase=dfn.output_phase,
        )
        plan = cast(BarBucketPlan, bucket_plan)
        BarBucketPlan(
            plan_key=plan.plan_key,
            coverage_start=plan.coverage_start,
            coverage_end_exclusive=plan.coverage_end_exclusive,
            bar_definition_key=plan.bar_definition_key,
            bar_definition_version=plan.bar_definition_version,
            bar_definition_hash=plan.bar_definition_hash,
            buckets=plan.buckets,
        )
    except (TypeError, ValueError):
        return False
    return True


def _aggregation_input_hash(
    *,
    source_bundle_ref: MarketBundleRef,
    source_stream_manifest: MarketStreamManifest,
    definition: BarDefinition,
    bucket_plan_hash: str,
    aggregation_spec_hash: str,
    aggregation_code_hash: str,
) -> str:
    return canonical_sha256(
        {
            "type": "bar_aggregation_input",
            "schema_version": _SCHEMA_VERSION,
            "source_bundle_ref": source_bundle_ref.to_canonical_dict(),
            "source_stream_manifest": source_stream_manifest.to_canonical_dict(),
            "source_stream_hash": source_stream_manifest.content_hash,
            "definition_hash": definition.definition_hash,
            "bucket_plan_hash": bucket_plan_hash,
            "aggregation_spec_hash": aggregation_spec_hash,
            "aggregation_code_hash": aggregation_code_hash,
        }
    )


def _assigned_bucket(event_time: UtcInstant, plan: BarBucketPlan) -> int | None:
    instant = event_time.epoch_nanoseconds
    for index, bucket in enumerate(plan.buckets):
        if any(
            start.epoch_nanoseconds <= instant < end.epoch_nanoseconds
            for start, end in bucket.included_spans
        ):
            return index
    return None


def _source_observations(
    *,
    source_events: tuple[MarketEvent, ...],
    source_stream_key: str,
    definition: BarDefinition,
    bucket_plan: BarBucketPlan,
) -> tuple[
    tuple[_SelectedObservation, ...] | None,
    int,
    BarAggregationOutcome | None,
]:
    expected_fields = {
        "synthetic_record_key",
        "price_units",
        "price_scale",
        "price_purpose",
    }
    selected: list[_SelectedObservation] = []
    nonselected: list[tuple[int, MarketEvent]] = []
    nonselected_count = 0
    root_economic_keys: dict[tuple[InstrumentId, int], str] = {}

    for input_position, event in enumerate(source_events):
        if event.stream_key != source_stream_key:
            continue
        payload = event.payload
        if set(payload) != expected_fields:
            return (
                None,
                0,
                _failed(
                    BarAggregationFailureCode.SOURCE_EVENT_INVALID,
                    stream_key=source_stream_key,
                    input_position=input_position,
                ),
            )
        record_key = payload["synthetic_record_key"]
        price_units = payload["price_units"]
        price_scale = payload["price_scale"]
        purpose_value = payload["price_purpose"]
        try:
            _text("synthetic_record_key", record_key)
            if type(price_units) is not int or price_units <= 0:
                raise ValueError("price_units must be positive integer")
            if type(price_scale) is not int:
                raise TypeError("price_scale must be integer")
            scale = Scale(price_scale)
            if type(purpose_value) is not str:
                raise TypeError("price_purpose must be text")
            purpose = PricePurpose(purpose_value)
        except (TypeError, ValueError):
            return (
                None,
                0,
                _failed(
                    BarAggregationFailureCode.SOURCE_EVENT_INVALID,
                    stream_key=source_stream_key,
                    input_position=input_position,
                ),
            )
        if purpose is not definition.price_purpose:
            nonselected.append((input_position, event))
            nonselected_count += 1
            continue

        bucket_index = _assigned_bucket(event.event_time, bucket_plan)
        if (
            type(event.instrument_id) is not InstrumentId
            or scale != definition.price_scale
        ):
            return (
                None,
                0,
                _failed(
                    BarAggregationFailureCode.SOURCE_EVENT_INVALID,
                    stream_key=source_stream_key,
                    input_position=input_position,
                    interval_hash=(
                        None
                        if bucket_index is None
                        else bucket_plan.buckets[bucket_index].bucket_hash
                    ),
                ),
            )
        observation = _SelectedObservation(
            input_position=input_position,
            event=event,
            instrument_id=event.instrument_id,
            record_key=cast(str, record_key),
            price_units=cast(int, price_units),
            bucket_index=bucket_index,
        )
        if event.supersedes_revision_id is None:
            economic_key = (
                observation.instrument_id,
                event.event_time.epoch_nanoseconds,
            )
            previous_record = root_economic_keys.get(economic_key)
            if (
                previous_record is not None
                and previous_record != observation.record_key
            ):
                return (
                    None,
                    0,
                    _failed(
                        BarAggregationFailureCode.SOURCE_EVENT_INVALID,
                        stream_key=source_stream_key,
                        input_position=input_position,
                        interval_hash=(
                            None
                            if bucket_index is None
                            else bucket_plan.buckets[bucket_index].bucket_hash
                        ),
                    ),
                )
            root_economic_keys[economic_key] = observation.record_key
        selected.append(observation)

    selected_by_revision = {
        observation.event.revision_id: observation for observation in selected
    }
    for input_position, event in nonselected:
        parent = selected_by_revision.get(event.supersedes_revision_id or "")
        if parent is not None:
            return (
                None,
                0,
                _failed(
                    BarAggregationFailureCode.REVISION_CHAIN_INVALID,
                    stream_key=source_stream_key,
                    input_position=input_position,
                    interval_hash=(
                        None
                        if parent.bucket_index is None
                        else bucket_plan.buckets[parent.bucket_index].bucket_hash
                    ),
                ),
            )

    return tuple(selected), nonselected_count, None


def _revision_chains(
    *,
    selected: tuple[_SelectedObservation, ...],
    source_stream_key: str,
    bucket_plan: BarBucketPlan,
) -> tuple[tuple[_ObservationChain, ...] | None, BarAggregationOutcome | None]:
    by_revision: dict[str, _SelectedObservation] = {}
    invalid: list[_SelectedObservation] = []
    for observation in selected:
        if observation.event.revision_id in by_revision:
            invalid.append(observation)
        else:
            by_revision[observation.event.revision_id] = observation

    children: dict[str, list[_SelectedObservation]] = {}
    roots: dict[tuple[InstrumentId, str], list[_SelectedObservation]] = {}
    for observation in selected:
        parent_id = observation.event.supersedes_revision_id
        if parent_id is None:
            roots.setdefault(
                (observation.instrument_id, observation.record_key), []
            ).append(observation)
            continue
        parent = by_revision.get(parent_id)
        if parent is None:
            invalid.append(observation)
            continue
        children.setdefault(parent_id, []).append(observation)
        if (
            observation.instrument_id != parent.instrument_id
            or observation.record_key != parent.record_key
            or observation.event.event_time != parent.event.event_time
            or observation.bucket_index != parent.bucket_index
            or observation.event.timeline_instant <= parent.event.timeline_instant
        ):
            invalid.append(observation)

    for values in children.values():
        if len(values) > 1:
            invalid.extend(values)
    for values in roots.values():
        if len(values) > 1:
            invalid.extend(values[1:])

    chains: list[_ObservationChain] = []
    visited: set[str] = set()
    if not invalid:
        for values in roots.values():
            current = values[0]
            observations: list[_SelectedObservation] = []
            while current.event.revision_id not in visited:
                observations.append(current)
                visited.add(current.event.revision_id)
                next_values = children.get(current.event.revision_id, [])
                if not next_values:
                    break
                current = next_values[0]
            chains.append(_ObservationChain(tuple(observations)))
        invalid.extend(
            observation
            for observation in selected
            if observation.event.revision_id not in visited
        )

    if invalid:
        observation = min(invalid, key=lambda item: item.input_position)
        return None, _failed(
            BarAggregationFailureCode.REVISION_CHAIN_INVALID,
            stream_key=source_stream_key,
            input_position=observation.input_position,
            interval_hash=(
                None
                if observation.bucket_index is None
                else bucket_plan.buckets[observation.bucket_index].bucket_hash
            ),
        )
    return tuple(
        sorted(chains, key=lambda chain: chain.observations[0].input_position)
    ), None


def _bar_candidates(
    *,
    chains: tuple[_ObservationChain, ...],
    bucket_plan: BarBucketPlan,
    definition: BarDefinition,
    aggregation_spec_hash: str,
    aggregation_input_hash: str,
) -> tuple[tuple[_BarCandidate, ...] | None, BarAggregationOutcome | None]:
    grouped: dict[tuple[InstrumentId, int], list[_ObservationChain]] = {}
    for chain in chains:
        observation = chain.observations[0]
        if observation.bucket_index is not None:
            grouped.setdefault(
                (observation.instrument_id, observation.bucket_index), []
            ).append(chain)

    all_candidates: list[_BarCandidate] = []
    causality_failures: list[tuple[int, str]] = []

    for (instrument_id, bucket_index), instrument_chains in grouped.items():
        bucket = bucket_plan.buckets[bucket_index]
        close_ns = bucket.interval_end_exclusive.epoch_nanoseconds

        # Collect all availability timestamps from all revisions in these chains
        timestamps: set[int] = set()
        for chain in instrument_chains:
            for obs in chain.observations:
                timestamps.add(
                    max(close_ns, obs.event.available_time.epoch_nanoseconds)
                )

        sorted_times = sorted(timestamps)
        previous_source_set_hash: str | None = None
        previous_revision_id: str | None = None

        for available_ns in sorted_times:
            # Find the active revision for each chain at this time
            active_observations: list[_SelectedObservation] = []
            invalid_positions = [
                observation.input_position
                for chain in instrument_chains
                for observation in chain.observations
                if observation.event.available_time.epoch_nanoseconds == available_ns
                and not observation.event.phase < definition.output_phase
            ]
            for chain in instrument_chains:
                active: _SelectedObservation | None = None
                for observation in chain.observations:
                    if (
                        observation.event.available_time.epoch_nanoseconds
                        <= available_ns
                    ):
                        active = observation
                if active is not None:
                    active_observations.append(active)

            if not active_observations:
                continue

            if invalid_positions:
                causality_failures.append((min(invalid_positions), bucket.bucket_hash))
                continue

            active_observations.sort(
                key=lambda item: item.event.event_time.epoch_nanoseconds
            )
            source_event_hashes = tuple(
                item.event.event_hash for item in active_observations
            )
            selected_source_set_hash = canonical_sha256(source_event_hashes)

            if selected_source_set_hash == previous_source_set_hash:
                continue

            revision_identity_hash = canonical_sha256(
                {
                    "type": "bar_revision_identity",
                    "schema_version": _SCHEMA_VERSION,
                    "aggregation_spec_hash": aggregation_spec_hash,
                    "aggregation_input_hash": aggregation_input_hash,
                    "instrument_id": instrument_id.to_canonical_dict(),
                    "bucket_hash": bucket.bucket_hash,
                    "selected_source_set_hash": selected_source_set_hash,
                }
            )

            all_candidates.append(
                _BarCandidate(
                    available_time=UtcInstant(available_ns),
                    instrument_id=instrument_id,
                    bucket_index=bucket_index,
                    bucket=bucket,
                    observations=tuple(active_observations),
                    source_event_hashes=source_event_hashes,
                    selected_source_set_hash=selected_source_set_hash,
                    revision_identity_hash=revision_identity_hash,
                    supersedes_revision_id=previous_revision_id,
                )
            )
            previous_source_set_hash = selected_source_set_hash
            previous_revision_id = "bar-revision-v1:" + revision_identity_hash

    if causality_failures:
        position, interval_hash = min(causality_failures)
        return None, _failed(
            BarAggregationFailureCode.OUTPUT_CAUSALITY_INVALID,
            stream_key=definition.output_stream_key,
            input_position=position,
            interval_hash=interval_hash,
        )

    return tuple(
        sorted(
            all_candidates,
            key=lambda item: (
                item.available_time.epoch_nanoseconds,
                canonical_bytes(item.instrument_id),
                item.bucket_index,
                item.bucket.bucket_hash,
                item.revision_identity_hash,
            ),
        )
    ), None


def _bar_event(
    *,
    candidate: _BarCandidate,
    source_sequence: int,
    definition: BarDefinition,
    source_stream_hash: str,
    bucket_plan_hash: str,
    aggregation_spec_hash: str,
    aggregation_code_hash: str,
    aggregation_input_hash: str,
) -> MarketEvent:
    units = tuple(item.price_units for item in candidate.observations)
    scale = definition.price_scale.places
    bucket = candidate.bucket
    identity = candidate.revision_identity_hash
    return MarketEvent(
        event_id="bar-event-v1:" + identity,
        stream_key=definition.output_stream_key,
        event_type="bar",
        capability=_BAR_CAPABILITY,
        instrument_id=candidate.instrument_id,
        event_time=bucket.interval_start,
        available_time=candidate.available_time,
        phase=definition.output_phase,
        source_sequence=SourceSequence(source_sequence),
        revision_id="bar-revision-v1:" + identity,
        supersedes_revision_id=candidate.supersedes_revision_id,
        source_key="canonical-bar-aggregation-v1",
        source_hash=aggregation_input_hash,
        payload={
            "schema_version": _SCHEMA_VERSION,
            "bar_definition_key": definition.key,
            "bar_definition_version": definition.version,
            "bar_definition_hash": definition.definition_hash,
            "source_stream_hash": source_stream_hash,
            "bucket_plan_hash": bucket_plan_hash,
            "aggregation_spec_hash": aggregation_spec_hash,
            "aggregation_code_hash": aggregation_code_hash,
            "aggregation_input_hash": aggregation_input_hash,
            "bucket_hash": bucket.bucket_hash,
            "session_id": bucket.session_id.to_canonical_dict(),
            "trading_date": bucket.trading_date.to_canonical_dict(),
            "included_spans": [
                {
                    "start": start.to_canonical_dict(),
                    "end_exclusive": end.to_canonical_dict(),
                }
                for start, end in bucket.included_spans
            ],
            "interval_start": bucket.interval_start.to_canonical_dict(),
            "interval_end_exclusive": bucket.interval_end_exclusive.to_canonical_dict(),
            "price_purpose": definition.price_purpose.value,
            "price_scale": scale,
            "open": {"units": units[0], "scale": scale},
            "high": {"units": max(units), "scale": scale},
            "low": {"units": min(units), "scale": scale},
            "close": {"units": units[-1], "scale": scale},
            "volume": None,
            "observation_count": len(candidate.observations),
            "source_event_hashes": candidate.source_event_hashes,
            "selected_source_set_hash": candidate.selected_source_set_hash,
        },
    )


def aggregate_bars_v1(
    *,
    source_manifest: MarketBundleManifest,
    source_events: tuple[MarketEvent, ...],
    bucket_plan: BarBucketPlan,
    definition: BarDefinition,
    aggregation_code_hash: str,
) -> BarAggregationOutcome:
    if not _validate_aggregation_inputs(
        source_manifest,
        source_events,
        bucket_plan,
        definition,
        aggregation_code_hash,
    ):
        return _failed(BarAggregationFailureCode.INVALID_INPUT)

    source_validation = validate_market_bundle_v1(
        bundle_key=source_manifest.bundle_key,
        schema_version=source_manifest.schema_version,
        coverage_start=source_manifest.coverage_start,
        coverage_end_exclusive=source_manifest.coverage_end_exclusive,
        instrument_catalog_hash=source_manifest.instrument_catalog_hash,
        events=source_events,
    )
    if source_validation.manifest != source_manifest:
        failure = source_validation.failure
        return _failed(
            BarAggregationFailureCode.SOURCE_BUNDLE_MISMATCH,
            stream_key=None if failure is None else failure.stream_key,
            input_position=None if failure is None else failure.input_position,
        )

    if (
        bucket_plan.bar_definition_key != definition.key
        or bucket_plan.bar_definition_version != definition.version
        or bucket_plan.bar_definition_hash != definition.definition_hash
    ):
        return _failed(BarAggregationFailureCode.DEFINITION_BUCKET_PLAN_MISMATCH)

    source_stream = next(
        (
            stream
            for stream in source_manifest.streams
            if stream.stream_key == definition.source_stream_key
        ),
        None,
    )
    stream_keys = {stream.stream_key for stream in source_manifest.streams}
    if (
        source_stream is None
        or source_stream.event_type != definition.source_event_type
        or source_stream.capability != definition.source_capability
        or definition.output_stream_key in stream_keys
    ):
        return _failed(
            BarAggregationFailureCode.SOURCE_STREAM_MISMATCH,
            stream_key=(
                definition.output_stream_key
                if definition.output_stream_key in stream_keys
                else definition.source_stream_key
            ),
        )

    if (
        source_manifest.coverage_start != bucket_plan.coverage_start
        or source_manifest.coverage_end_exclusive != bucket_plan.coverage_end_exclusive
    ):
        return _failed(BarAggregationFailureCode.SOURCE_COVERAGE_UNALIGNED)

    selected, nonselected_count, selection_failure = _source_observations(
        source_events=source_events,
        source_stream_key=source_stream.stream_key,
        definition=definition,
        bucket_plan=bucket_plan,
    )
    if selection_failure is not None:
        return selection_failure
    assert selected is not None

    chains, revision_failure = _revision_chains(
        selected=selected,
        source_stream_key=source_stream.stream_key,
        bucket_plan=bucket_plan,
    )
    if revision_failure is not None:
        return revision_failure
    assert chains is not None

    aggregation_spec_hash = _aggregation_spec_hash()
    source_bundle_ref = MarketBundleRef.from_manifest(source_manifest)
    aggregation_input_hash = _aggregation_input_hash(
        source_bundle_ref=source_bundle_ref,
        source_stream_manifest=source_stream,
        definition=definition,
        bucket_plan_hash=bucket_plan.bucket_plan_hash,
        aggregation_spec_hash=aggregation_spec_hash,
        aggregation_code_hash=aggregation_code_hash,
    )
    candidates, causality_failure = _bar_candidates(
        chains=chains,
        bucket_plan=bucket_plan,
        definition=definition,
        aggregation_spec_hash=aggregation_spec_hash,
        aggregation_input_hash=aggregation_input_hash,
    )
    if causality_failure is not None:
        return causality_failure
    assert candidates is not None

    try:
        generated_events = tuple(
            _bar_event(
                candidate=candidate,
                source_sequence=index,
                definition=definition,
                source_stream_hash=source_stream.content_hash,
                bucket_plan_hash=bucket_plan.bucket_plan_hash,
                aggregation_spec_hash=aggregation_spec_hash,
                aggregation_code_hash=aggregation_code_hash,
                aggregation_input_hash=aggregation_input_hash,
            )
            for index, candidate in enumerate(candidates)
        )
    except (TypeError, ValueError):
        return _failed(BarAggregationFailureCode.OUTPUT_VALIDATION_FAILED)

    output_bundle_key = (
        source_manifest.bundle_key
        + ".bar-aggregation-v1."
        + aggregation_input_hash.removeprefix("sha256:")
    )
    output_validation = validate_market_bundle_v1(
        bundle_key=output_bundle_key,
        schema_version=source_manifest.schema_version,
        coverage_start=source_manifest.coverage_start,
        coverage_end_exclusive=source_manifest.coverage_end_exclusive,
        instrument_catalog_hash=source_manifest.instrument_catalog_hash,
        events=source_events + generated_events,
    )
    if output_validation.manifest is None:
        failure = output_validation.failure
        return _failed(
            BarAggregationFailureCode.OUTPUT_VALIDATION_FAILED,
            stream_key=None if failure is None else failure.stream_key,
            input_position=None if failure is None else failure.input_position,
        )
    output_manifest = output_validation.manifest
    output_stream = next(
        (
            stream
            for stream in output_manifest.streams
            if stream.stream_key == definition.output_stream_key
        ),
        None,
    )
    candidate_instruments = tuple(
        sorted({item.instrument_id for item in selected}, key=canonical_bytes)
    )
    assigned_count = sum(item.bucket_index is not None for item in selected)
    populated_pairs = {
        (item.instrument_id, item.bucket_index)
        for item in selected
        if item.bucket_index is not None
    }
    empty_count = sum(
        (instrument_id, bucket_index) not in populated_pairs
        for instrument_id in candidate_instruments
        for bucket_index in range(len(bucket_plan.buckets))
    )
    try:
        aggregation_manifest = BarAggregationManifest(
            source_bundle_ref=source_bundle_ref,
            source_stream_manifest=source_stream,
            source_stream_hash=source_stream.content_hash,
            bar_definition=definition,
            bucket_plan_key=bucket_plan.plan_key,
            bucket_plan_hash=bucket_plan.bucket_plan_hash,
            aggregation_spec_hash=aggregation_spec_hash,
            aggregation_code_hash=aggregation_code_hash,
            aggregation_input_hash=aggregation_input_hash,
            input_event_count=len(source_events),
            source_stream_event_count=source_stream.event_count,
            selected_source_revision_count=len(selected),
            assigned_source_revision_count=assigned_count,
            out_of_plan_source_revision_count=len(selected) - assigned_count,
            nonselected_source_event_count=nonselected_count,
            candidate_instrument_count=len(candidate_instruments),
            planned_bucket_count=len(bucket_plan.buckets),
            empty_bucket_instrument_count=empty_count,
            output_root_count=sum(
                event.supersedes_revision_id is None for event in generated_events
            ),
            output_revision_count=len(generated_events),
            output_stream_manifest=output_stream,
            output_bundle_ref=MarketBundleRef.from_manifest(output_manifest),
            decision_grade_eligible=False,
            deployment_authorized=False,
        )
        result = BarAggregationResult(
            generated_events=generated_events,
            output_manifest=output_manifest,
            aggregation_manifest=aggregation_manifest,
        )
    except (TypeError, ValueError):
        return _failed(BarAggregationFailureCode.OUTPUT_VALIDATION_FAILED)
    return BarAggregationOutcome(result=result, failure=None)
