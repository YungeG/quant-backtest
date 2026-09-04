from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, cast

from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    Scale,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent

from .source_snapshots import SourceSnapshot, SourceSnapshotMember, verify_source_snapshot


_SCHEMA_VERSION = 1
_NORMALIZER_ID = "synthetic_jsonl@1"
_INSTRUMENT_ALIAS = re.compile(r"[A-Z][A-Z0-9._-]{0,63}\Z")
_PURPOSE_ALIAS = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_FIELDS = (
    "available_time_epoch_nanoseconds",
    "event_time_epoch_nanoseconds",
    "instrument",
    "price_scale",
    "price_units",
    "purpose",
    "record_key",
    "revision_id",
    "schema_version",
    "supersedes_revision_id",
    "type",
)


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", text) is None:
        raise ValueError(f"{name} must be sha256 content hash")
    return text


def _alias_bindings(
    name: str,
    bindings: object,
    pattern: re.Pattern[str],
    value_type: type[object],
) -> tuple[tuple[str, object], ...]:
    if type(bindings) is not tuple or not bindings:
        raise ValueError(f"{name} must be nonempty tuple")
    values: list[tuple[str, object]] = []
    for binding in cast(tuple[object, ...], bindings):
        if type(binding) is not tuple or len(binding) != 2:
            raise TypeError(f"{name} entries must be alias/value tuples")
        alias, value = cast(tuple[object, object], binding)
        if type(alias) is not str or pattern.fullmatch(alias) is None:
            raise ValueError(f"{name} alias is invalid")
        if type(value) is not value_type:
            raise TypeError(f"{name} value has invalid type")
        values.append((alias, value))
    ordered = tuple(sorted(values, key=lambda item: item[0]))
    if len({alias for alias, _ in ordered}) != len(ordered):
        raise ValueError(f"{name} aliases must be unique")
    return ordered


@dataclass(frozen=True, slots=True)
class SyntheticJsonlV1Config:
    member_key: str
    stream_key: str
    capability: MarketBundleCapability
    phase: TimelinePhase
    instrument_bindings: tuple[tuple[str, InstrumentId], ...]
    price_purpose_bindings: tuple[tuple[str, PricePurpose], ...]

    def __post_init__(self) -> None:
        _text("member_key", self.member_key)
        _text("stream_key", self.stream_key)
        if type(self.capability) is not MarketBundleCapability:
            raise TypeError("capability must be MarketBundleCapability")
        if type(self.phase) is not TimelinePhase:
            raise TypeError("phase must be TimelinePhase")
        object.__setattr__(
            self,
            "instrument_bindings",
            _alias_bindings(
                "instrument_bindings",
                self.instrument_bindings,
                _INSTRUMENT_ALIAS,
                InstrumentId,
            ),
        )
        object.__setattr__(
            self,
            "price_purpose_bindings",
            _alias_bindings(
                "price_purpose_bindings",
                self.price_purpose_bindings,
                _PURPOSE_ALIAS,
                PricePurpose,
            ),
        )

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "synthetic_jsonl_v1_config",
            "schema_version": _SCHEMA_VERSION,
            "member_key": self.member_key,
            "stream_key": self.stream_key,
            "capability": self.capability.to_canonical_dict(),
            "phase": self.phase.to_canonical_dict(),
            "instrument_bindings": [
                {"alias": alias, "instrument_id": value.to_canonical_dict()}
                for alias, value in self.instrument_bindings
            ],
            "price_purpose_bindings": [
                {"alias": alias, "price_purpose": value.value}
                for alias, value in self.price_purpose_bindings
            ],
        }

    @property
    def config_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "config_hash": self.config_hash}


@dataclass(frozen=True, slots=True, order=True)
class SyntheticJsonlV1RecordLocator:
    member_key: str
    line_number: int

    def __post_init__(self) -> None:
        _text("member_key", self.member_key)
        if type(self.line_number) is not int or self.line_number <= 0:
            raise ValueError("line_number must be positive integer")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_jsonl_line_locator",
            "schema_version": _SCHEMA_VERSION,
            "member_key": self.member_key,
            "line_number": self.line_number,
        }


@dataclass(frozen=True, slots=True)
class SyntheticJsonlV1SourceTrace:
    snapshot_id: str
    provenance_hash: str
    source_key: str
    member_content_hash: str
    locator: SyntheticJsonlV1RecordLocator
    event_id: str
    event_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("snapshot_id", self.snapshot_id),
            ("provenance_hash", self.provenance_hash),
            ("member_content_hash", self.member_content_hash),
            ("event_hash", self.event_hash),
        ):
            _hash(name, value)
        _text("source_key", self.source_key)
        _text("event_id", self.event_id)
        if type(self.locator) is not SyntheticJsonlV1RecordLocator:
            raise TypeError("locator must be SyntheticJsonlV1RecordLocator")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_jsonl_v1_source_trace",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "provenance_hash": self.provenance_hash,
            "source_key": self.source_key,
            "member_content_hash": self.member_content_hash,
            "locator": self.locator.to_canonical_dict(),
            "event_id": self.event_id,
            "event_hash": self.event_hash,
        }


class SyntheticJsonlV1NormalizationFailureCode(str, Enum):
    INVALID_NORMALIZATION_INPUT = "invalid_normalization_input"
    SOURCE_SNAPSHOT_INVALID = "source_snapshot_invalid"
    SELECTED_MEMBER_MISSING = "selected_member_missing"
    MEMBER_ENCODING_INVALID = "member_encoding_invalid"
    JSONL_LAYOUT_INVALID = "jsonl_layout_invalid"
    JSON_INVALID = "json_invalid"
    NONCANONICAL_JSON = "noncanonical_json"
    RECORD_SHAPE_INVALID = "record_shape_invalid"
    UNSUPPORTED_RECORD_SCHEMA = "unsupported_record_schema"
    RECORD_FIELD_INVALID = "record_field_invalid"
    INSTRUMENT_UNMAPPED = "instrument_unmapped"
    PRICE_PURPOSE_UNMAPPED = "price_purpose_unmapped"
    EVENT_ENVELOPE_INVALID = "event_envelope_invalid"


@dataclass(frozen=True, slots=True)
class SyntheticJsonlV1NormalizationFailure:
    code: SyntheticJsonlV1NormalizationFailureCode
    member_key: str | None
    locator: SyntheticJsonlV1RecordLocator | None
    field: str | None

    def __post_init__(self) -> None:
        if type(self.code) is not SyntheticJsonlV1NormalizationFailureCode:
            raise TypeError("code must be normalization failure code")
        if self.member_key is not None:
            _text("member_key", self.member_key)
        if self.locator is not None and type(
            self.locator
        ) is not SyntheticJsonlV1RecordLocator:
            raise TypeError("locator must be record locator or None")
        if self.field is not None:
            _text("field", self.field)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_jsonl_v1_normalization_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "member_key": self.member_key,
            "locator": None if self.locator is None else self.locator.to_canonical_dict(),
            "field": self.field,
        }


@dataclass(frozen=True, slots=True)
class SyntheticJsonlV1NormalizationResult:
    config: SyntheticJsonlV1Config
    normalizer_spec_hash: str
    snapshot_id: str
    provenance_hash: str
    source_key: str
    member_content_hash: str
    events: tuple[MarketEvent, ...]
    traces: tuple[SyntheticJsonlV1SourceTrace, ...]
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.config) is not SyntheticJsonlV1Config:
            raise TypeError("config must be SyntheticJsonlV1Config")
        for name, value in (
            ("normalizer_spec_hash", self.normalizer_spec_hash),
            ("snapshot_id", self.snapshot_id),
            ("provenance_hash", self.provenance_hash),
            ("member_content_hash", self.member_content_hash),
        ):
            _hash(name, value)
        _text("source_key", self.source_key)
        if type(self.events) is not tuple or any(type(event) is not MarketEvent for event in self.events):
            raise TypeError("events must be tuple of MarketEvent")
        if type(self.traces) is not tuple or any(
            type(trace) is not SyntheticJsonlV1SourceTrace for trace in self.traces
        ):
            raise TypeError("traces must be tuple of source trace")
        if len(self.events) != len(self.traces):
            raise ValueError("events and traces must exact-cover")
        for index, (event, trace) in enumerate(zip(self.events, self.traces, strict=True)):
            if (
                trace.locator.member_key != self.config.member_key
                or trace.locator.line_number != index + 1
                or event.source_sequence != SourceSequence(index)
                or trace.event_id != event.event_id
                or trace.event_hash != event.event_hash
                or trace.snapshot_id != self.snapshot_id
                or trace.provenance_hash != self.provenance_hash
                or trace.source_key != self.source_key
                or trace.member_content_hash != self.member_content_hash
                or event.source_key != self.source_key
                or event.source_hash != self.member_content_hash
            ):
                raise ValueError("result trace does not match Event evidence")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G12B qualification flags must remain false")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "synthetic_jsonl_v1_normalization_result",
            "schema_version": _SCHEMA_VERSION,
            "config": self.config.to_canonical_dict(),
            "normalizer_spec_hash": self.normalizer_spec_hash,
            "snapshot_id": self.snapshot_id,
            "provenance_hash": self.provenance_hash,
            "source_key": self.source_key,
            "member_content_hash": self.member_content_hash,
            "events": [event.to_canonical_dict() for event in self.events],
            "traces": [trace.to_canonical_dict() for trace in self.traces],
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "normalization_hash": self.normalization_hash}

    def event_for_source_record(
        self, locator: SyntheticJsonlV1RecordLocator
    ) -> MarketEvent | None:
        for event, trace in zip(self.events, self.traces, strict=True):
            if trace.locator == locator:
                return event
        return None

    def trace_for_event(self, event_id: str) -> SyntheticJsonlV1SourceTrace | None:
        return next((trace for trace in self.traces if trace.event_id == event_id), None)


@dataclass(frozen=True, slots=True)
class SyntheticJsonlV1NormalizationOutcome:
    result: SyntheticJsonlV1NormalizationResult | None
    failure: SyntheticJsonlV1NormalizationFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")


def _failed(
    code: SyntheticJsonlV1NormalizationFailureCode,
    member_key: str | None = None,
    locator: SyntheticJsonlV1RecordLocator | None = None,
    field: str | None = None,
) -> SyntheticJsonlV1NormalizationOutcome:
    return SyntheticJsonlV1NormalizationOutcome(
        None, SyntheticJsonlV1NormalizationFailure(code, member_key, locator, field)
    )


def _duplicate_free_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json_integer(value: str) -> int:
    digits = value.lstrip("-")
    if len(digits) > 4300 or not digits.isdigit():
        raise ValueError("integer token is invalid")
    try:
        return int(value)
    except ValueError as error:
        raise ValueError("integer token is invalid") from error


def _spec_hash() -> str:
    return canonical_sha256(
        {
            "type": "synthetic_jsonl_v1_normalizer_spec",
            "schema_version": _SCHEMA_VERSION,
            "normalizer_id": _NORMALIZER_ID,
        }
    )


def _selected_member(snapshot: SourceSnapshot, key: str) -> SourceSnapshotMember | None:
    return next((member for member in snapshot.members if member.member_key == key), None)


def _parse_line(
    line: bytes, locator: SyntheticJsonlV1RecordLocator
) -> tuple[dict[str, object] | None, SyntheticJsonlV1NormalizationOutcome | None]:
    try:
        parsed = json.loads(
            line,
            object_pairs_hook=_duplicate_free_object,
            parse_int=_json_integer,
            parse_float=lambda value: (_ for _ in ()).throw(ValueError("float forbidden")),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError("constant forbidden")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, _failed(
            SyntheticJsonlV1NormalizationFailureCode.JSON_INVALID,
            locator.member_key,
            locator,
        )
    if type(parsed) is not dict:
        return None, _failed(
            SyntheticJsonlV1NormalizationFailureCode.RECORD_SHAPE_INVALID,
            locator.member_key,
            locator,
        )
    record = cast(dict[str, object], parsed)
    try:
        if canonical_bytes(record) != line:
            return None, _failed(
                SyntheticJsonlV1NormalizationFailureCode.NONCANONICAL_JSON,
                locator.member_key,
                locator,
            )
    except (TypeError, ValueError):
        return None, _failed(
            SyntheticJsonlV1NormalizationFailureCode.NONCANONICAL_JSON,
            locator.member_key,
            locator,
        )
    if tuple(record) != _FIELDS or set(record) != set(_FIELDS):
        return None, _failed(
            SyntheticJsonlV1NormalizationFailureCode.RECORD_SHAPE_INVALID,
            locator.member_key,
            locator,
        )
    return record, None


def normalize_synthetic_jsonl_v1(
    snapshot: SourceSnapshot, config: SyntheticJsonlV1Config
) -> SyntheticJsonlV1NormalizationOutcome:
    if type(snapshot) is not SourceSnapshot or type(config) is not SyntheticJsonlV1Config:
        return _failed(SyntheticJsonlV1NormalizationFailureCode.INVALID_NORMALIZATION_INPUT)
    if verify_source_snapshot(snapshot).snapshot is None:
        return _failed(SyntheticJsonlV1NormalizationFailureCode.SOURCE_SNAPSHOT_INVALID)
    member = _selected_member(snapshot, config.member_key)
    if member is None:
        return _failed(
            SyntheticJsonlV1NormalizationFailureCode.SELECTED_MEMBER_MISSING,
            config.member_key,
        )
    try:
        value = snapshot.member_bytes(config.member_key)
    except ValueError:
        return _failed(SyntheticJsonlV1NormalizationFailureCode.SOURCE_SNAPSHOT_INVALID)
    if not value:
        return SyntheticJsonlV1NormalizationOutcome(
            SyntheticJsonlV1NormalizationResult(
                config,
                _spec_hash(),
                snapshot.snapshot_id,
                snapshot.provenance_hash,
                snapshot.provenance.source_key,
                member.content_hash,
                (),
                (),
                False,
                False,
            ),
            None,
        )
    if value.startswith(b"\xef\xbb\xbf") or b"\r" in value:
        return _failed(
            SyntheticJsonlV1NormalizationFailureCode.MEMBER_ENCODING_INVALID,
            config.member_key,
        )
    try:
        value.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return _failed(
            SyntheticJsonlV1NormalizationFailureCode.MEMBER_ENCODING_INVALID,
            config.member_key,
        )
    if not value.endswith(b"\n") or value.endswith(b"\n\n"):
        return _failed(
            SyntheticJsonlV1NormalizationFailureCode.JSONL_LAYOUT_INVALID,
            config.member_key,
        )
    lines = value[:-1].split(b"\n")
    if any(not line for line in lines):
        return _failed(
            SyntheticJsonlV1NormalizationFailureCode.JSONL_LAYOUT_INVALID,
            config.member_key,
        )
    instruments = dict(config.instrument_bindings)
    purposes = dict(config.price_purpose_bindings)
    events: list[MarketEvent] = []
    traces: list[SyntheticJsonlV1SourceTrace] = []
    for line_number, line in enumerate(lines, 1):
        locator = SyntheticJsonlV1RecordLocator(config.member_key, line_number)
        record, failure = _parse_line(line, locator)
        if failure is not None:
            return failure
        assert record is not None
        if record["type"] != "synthetic_price_point" or record["schema_version"] != 1:
            return _failed(
                SyntheticJsonlV1NormalizationFailureCode.UNSUPPORTED_RECORD_SCHEMA,
                config.member_key,
                locator,
                "schema_version",
            )
        field_error: str | None = None
        for field in _FIELDS:
            value_field = record[field]
            if field in ("available_time_epoch_nanoseconds", "event_time_epoch_nanoseconds"):
                if type(value_field) is not int:
                    field_error = field
                    break
            elif field == "instrument":
                if type(value_field) is not str or _INSTRUMENT_ALIAS.fullmatch(value_field) is None:
                    field_error = field
                    break
            elif field == "price_scale":
                try:
                    Scale(cast(int, value_field))
                except (TypeError, ValueError):
                    field_error = field
                    break
            elif field == "price_units":
                if type(value_field) is not int or value_field <= 0:
                    field_error = field
                    break
            elif field == "purpose":
                if type(value_field) is not str or _PURPOSE_ALIAS.fullmatch(value_field) is None:
                    field_error = field
                    break
            elif field in ("record_key", "revision_id"):
                if type(value_field) is not str or _RECORD_ID.fullmatch(value_field) is None:
                    field_error = field
                    break
            elif field == "supersedes_revision_id" and value_field is not None:
                if (
                    type(value_field) is not str
                    or _RECORD_ID.fullmatch(value_field) is None
                    or value_field == record["revision_id"]
                ):
                    field_error = field
                    break
        if field_error is None and cast(int, record["available_time_epoch_nanoseconds"]) < cast(
            int, record["event_time_epoch_nanoseconds"]
        ):
            field_error = "available_time_epoch_nanoseconds"
        if field_error is not None:
            return _failed(
                SyntheticJsonlV1NormalizationFailureCode.RECORD_FIELD_INVALID,
                config.member_key,
                locator,
                field_error,
            )
        instrument_alias = cast(str, record["instrument"])
        purpose_alias = cast(str, record["purpose"])
        instrument = instruments.get(instrument_alias)
        if instrument is None:
            return _failed(
                SyntheticJsonlV1NormalizationFailureCode.INSTRUMENT_UNMAPPED,
                config.member_key,
                locator,
                "instrument",
            )
        purpose = purposes.get(purpose_alias)
        if purpose is None:
            return _failed(
                SyntheticJsonlV1NormalizationFailureCode.PRICE_PURPOSE_UNMAPPED,
                config.member_key,
                locator,
                "purpose",
            )
        identity = {
            "type": "synthetic_jsonl_v1_event_identity",
            "schema_version": _SCHEMA_VERSION,
            "normalizer_spec_hash": _spec_hash(),
            "config_hash": config.config_hash,
            "snapshot_id": snapshot.snapshot_id,
            "source_key": snapshot.provenance.source_key,
            "locator": locator.to_canonical_dict(),
        }
        event_id = "synthetic-jsonl-v1:" + canonical_sha256(identity)
        try:
            event = MarketEvent(
                event_id=event_id,
                stream_key=config.stream_key,
                event_type="synthetic_price_point.v1",
                capability=config.capability,
                instrument_id=instrument,
                event_time=UtcInstant(cast(int, record["event_time_epoch_nanoseconds"])),
                available_time=UtcInstant(cast(int, record["available_time_epoch_nanoseconds"])),
                phase=config.phase,
                source_sequence=SourceSequence(line_number - 1),
                revision_id=cast(str, record["revision_id"]),
                supersedes_revision_id=cast(str | None, record["supersedes_revision_id"]),
                source_key=snapshot.provenance.source_key,
                source_hash=member.content_hash,
                payload={
                    "synthetic_record_key": cast(str, record["record_key"]),
                    "price_units": cast(int, record["price_units"]),
                    "price_scale": Scale(cast(int, record["price_scale"])).places,
                    "price_purpose": purpose.value,
                },
            )
        except (TypeError, ValueError):
            return _failed(
                SyntheticJsonlV1NormalizationFailureCode.EVENT_ENVELOPE_INVALID,
                config.member_key,
                locator,
            )
        trace = SyntheticJsonlV1SourceTrace(
            snapshot.snapshot_id,
            snapshot.provenance_hash,
            snapshot.provenance.source_key,
            member.content_hash,
            locator,
            event.event_id,
            event.event_hash,
        )
        events.append(event)
        traces.append(trace)
    return SyntheticJsonlV1NormalizationOutcome(
        SyntheticJsonlV1NormalizationResult(
            config,
            _spec_hash(),
            snapshot.snapshot_id,
            snapshot.provenance_hash,
            snapshot.provenance.source_key,
            member.content_hash,
            tuple(events),
            tuple(traces),
            False,
            False,
        ),
        None,
    )
