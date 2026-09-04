from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from crypto_quant_domain import (
    DecisionBatch,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent
from crypto_quant_trading import (
    AtomicDecisionBatchCollector,
    DecisionBatchExpectation,
    DecisionBatchFailure,
    DecisionBatchSubmission,
    LatestSleeveDecisionState,
    StrategyOutputValidationContext,
    StrategyOutputValidator,
    StrategyValidationFailure,
)

from .timeline import TimelineEvent, TimelineSegment


TARGET_STREAM_CAPABILITY = MarketBundleCapability("precomputed_target_stream", 1)
TARGET_STREAM_EVENT_TYPE = "strategy_decision_candidate"
_TARGET_STREAM_SCHEMA_VERSION = 1
_TARGET_ENVELOPE_FIELDS = frozenset({"schema_version", "candidate"})


def _canonical_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be nonempty trimmed text")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be NFC normalized")
    return value


def _hash_text(name: str, value: object) -> str:
    text = _canonical_text(name, value)
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{name} must be a canonical sha256 digest")
    try:
        int(text[7:], 16)
    except ValueError as error:
        raise ValueError(f"{name} must be a canonical sha256 digest") from error
    return text


@dataclass(frozen=True, slots=True)
class PrecomputedTargetStream:
    stream_key: str
    events: tuple[MarketEvent, ...]
    schema_version: int = _TARGET_STREAM_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _canonical_text("stream_key", self.stream_key)
        if type(self.schema_version) is not int or self.schema_version not in {1, 2}:
            raise ValueError("schema_version")
        if not isinstance(self.events, tuple) or not all(
            isinstance(event, MarketEvent) for event in self.events
        ):
            raise TypeError("events must be a tuple of MarketEvent")
        if any(event.stream_key != self.stream_key for event in self.events):
            raise ValueError("all target events must match stream_key")
        ordered = tuple(
            sorted(self.events, key=lambda event: (event.ordering_key, event.event_id))
        )
        event_ids = tuple(event.event_id for event in ordered)
        ordering_keys = tuple(event.ordering_key for event in ordered)
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("target stream event IDs must be unique")
        if len(set(ordering_keys)) != len(ordering_keys):
            raise ValueError("target stream ordering keys must be unique")
        object.__setattr__(self, "events", ordered)

    @property
    def target_stream_digest(self) -> str:
        return canonical_sha256(self)

    def events_at(self, decision_time: UtcInstant) -> tuple[MarketEvent, ...]:
        if not isinstance(decision_time, UtcInstant):
            raise TypeError("decision_time must be UtcInstant")
        return tuple(
            event
            for event in self.events
            if event.event_time == decision_time
            and event.available_time == decision_time
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "precomputed_target_stream",
            "schema_version": self.schema_version,
            "stream_key": self.stream_key,
            "events": self.events,
        }


@dataclass(frozen=True, slots=True)
class TargetStreamScheduleEntry:
    event_id: str
    expectation: DecisionBatchExpectation
    validation_context: StrategyOutputValidationContext

    def __post_init__(self) -> None:
        _canonical_text("event_id", self.event_id)
        if not isinstance(self.expectation, DecisionBatchExpectation):
            raise TypeError("expectation must be DecisionBatchExpectation")
        if not isinstance(self.validation_context, StrategyOutputValidationContext):
            raise TypeError("validation_context must be StrategyOutputValidationContext")
        context = self.validation_context
        if (
            context.expected_strategy_id != self.expectation.strategy_id
            or context.expected_sleeve_id != self.expectation.sleeve_id
        ):
            raise ValueError("validation context identity must match expectation")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "target_stream_schedule_entry",
            "event_id": self.event_id,
            "expectation": self.expectation,
            "validation_context": {
                "expected_strategy_id": self.validation_context.expected_strategy_id,
                "expected_sleeve_id": self.validation_context.expected_sleeve_id,
                "decision_time": self.validation_context.decision_time,
                "instrument_catalog_hash": canonical_sha256(
                    self.validation_context.instrument_catalog
                ),
                "universe": self.validation_context.universe,
            },
        }


@dataclass(frozen=True, slots=True)
class TargetStreamDecisionSchedule:
    decision_time: UtcInstant
    segment: TimelineSegment
    entries: tuple[TargetStreamScheduleEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.decision_time, UtcInstant):
            raise TypeError("decision_time must be UtcInstant")
        if not isinstance(self.segment, TimelineSegment):
            raise TypeError("segment must be TimelineSegment")
        if not isinstance(self.entries, tuple) or not self.entries:
            raise ValueError("entries must be a nonempty tuple")
        if not all(isinstance(entry, TargetStreamScheduleEntry) for entry in self.entries):
            raise TypeError("entries must contain TargetStreamScheduleEntry")
        ordered = tuple(
            sorted(
                self.entries,
                key=lambda entry: (
                    entry.expectation.strategy_id,
                    entry.expectation.sleeve_id.value,
                    entry.event_id,
                ),
            )
        )
        if len({entry.event_id for entry in ordered}) != len(ordered):
            raise ValueError("schedule event IDs must be unique")
        identities = {
            (entry.expectation.strategy_id, entry.expectation.sleeve_id)
            for entry in ordered
        }
        if len(identities) != len(ordered):
            raise ValueError("schedule expectations must be unique")
        if any(
            entry.validation_context.decision_time != self.decision_time
            for entry in ordered
        ):
            raise ValueError("validation context decision time must match schedule")
        object.__setattr__(self, "entries", ordered)

    @property
    def schedule_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "target_stream_decision_schedule",
            "decision_time": self.decision_time,
            "segment": self.segment.value,
            "entries": self.entries,
        }


class InputDecodeIssueCode(str, Enum):
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    UNSUPPORTED_EVENT_TYPE = "unsupported_event_type"
    EVENT_INSTRUMENT_NOT_EMPTY = "event_instrument_not_empty"
    EVENT_TIME_MISMATCH = "event_time_mismatch"
    MISSING_ENVELOPE_FIELD = "missing_envelope_field"
    UNKNOWN_ENVELOPE_FIELD = "unknown_envelope_field"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    CANDIDATE_NOT_MAPPING = "candidate_not_mapping"
    DUPLICATE_EVENT = "duplicate_event"
    UNEXPECTED_EVENT = "unexpected_event"
    MISSING_SOURCE_EVENT = "missing_source_event"
    SOURCE_EVENT_HASH_MISMATCH = "source_event_hash_mismatch"
    TIMELINE_SEGMENT_MISMATCH = "timeline_segment_mismatch"
    MISSING_WARMUP_EVENT = "missing_warmup_event"


@dataclass(frozen=True, slots=True)
class InputDecodeIssue:
    code: InputDecodeIssueCode
    event_id: str
    path: str
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, InputDecodeIssueCode):
            raise TypeError("code must be InputDecodeIssueCode")
        _canonical_text("event_id", self.event_id)
        _canonical_text("path", self.path)
        _canonical_text("subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "input_decode_issue",
            "code": self.code.value,
            "event_id": self.event_id,
            "path": self.path,
            "subject_key": self.subject_key,
        }


def _issue_key(issue: InputDecodeIssue) -> tuple[str, str, str, str]:
    return (issue.event_id, issue.path, issue.code.value, issue.subject_key)


@dataclass(frozen=True, slots=True)
class InputDecodeFailure:
    target_stream_digest: str
    schedule_hash: str
    issues: tuple[InputDecodeIssue, ...]
    source_event_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        _hash_text("target_stream_digest", self.target_stream_digest)
        _hash_text("schedule_hash", self.schedule_hash)
        if not isinstance(self.issues, tuple) or not self.issues:
            raise ValueError("issues must be a nonempty tuple")
        if not all(isinstance(issue, InputDecodeIssue) for issue in self.issues):
            raise TypeError("issues must contain InputDecodeIssue")
        ordered = tuple(sorted(self.issues, key=_issue_key))
        if len(set(ordered)) != len(ordered):
            raise ValueError("decode issues must be unique")
        hashes = tuple(sorted(self.source_event_hashes))
        for value in hashes:
            _hash_text("source_event_hash", value)
        if len(set(hashes)) != len(hashes):
            raise ValueError("source event hashes must be unique")
        object.__setattr__(self, "issues", ordered)
        object.__setattr__(self, "source_event_hashes", hashes)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "input_decode_failure",
            "target_stream_digest": self.target_stream_digest,
            "schedule_hash": self.schedule_hash,
            "issues": self.issues,
            "source_event_hashes": self.source_event_hashes,
        }


@dataclass(frozen=True, slots=True)
class TargetCandidateValidationFailure:
    event_id: str
    event_hash: str
    validation_failure: StrategyValidationFailure

    def __post_init__(self) -> None:
        _canonical_text("event_id", self.event_id)
        _hash_text("event_hash", self.event_hash)
        if not isinstance(self.validation_failure, StrategyValidationFailure):
            raise TypeError("validation_failure must be StrategyValidationFailure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "target_candidate_validation_failure",
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "validation_failure": self.validation_failure,
        }


def _validate_source_evidence(
    source_event_ids: tuple[str, ...], source_event_hashes: tuple[str, ...]
) -> None:
    if not source_event_ids:
        raise ValueError("source_event_ids must be nonempty")
    if len(source_event_ids) != len(source_event_hashes):
        raise ValueError("source event identities and hashes must align")
    for value in source_event_ids:
        _canonical_text("source_event_id", value)
    for value in source_event_hashes:
        _hash_text("source_event_hash", value)
    if len(set(source_event_ids)) != len(source_event_ids):
        raise ValueError("source event identities must be unique")
    if len(set(source_event_hashes)) != len(source_event_hashes):
        raise ValueError("source event hashes must be unique")


@dataclass(frozen=True, slots=True)
class TargetStreamWarmupSuppression:
    target_stream_digest: str
    schedule_hash: str
    source_event_ids: tuple[str, ...]
    source_event_hashes: tuple[str, ...]
    prior_state_hash: str | None

    def __post_init__(self) -> None:
        _hash_text("target_stream_digest", self.target_stream_digest)
        _hash_text("schedule_hash", self.schedule_hash)
        _validate_source_evidence(self.source_event_ids, self.source_event_hashes)
        if self.prior_state_hash is not None:
            _hash_text("prior_state_hash", self.prior_state_hash)

    @property
    def suppression_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "target_stream_warmup_suppression",
            "target_stream_digest": self.target_stream_digest,
            "schedule_hash": self.schedule_hash,
            "source_event_ids": self.source_event_ids,
            "source_event_hashes": self.source_event_hashes,
            "prior_state_hash": self.prior_state_hash,
        }


@dataclass(frozen=True, slots=True)
class TargetStreamBatchInjection:
    target_stream_digest: str
    schedule_hash: str
    source_event_ids: tuple[str, ...]
    source_event_hashes: tuple[str, ...]
    batch: DecisionBatch
    state: LatestSleeveDecisionState

    def __post_init__(self) -> None:
        _hash_text("target_stream_digest", self.target_stream_digest)
        _hash_text("schedule_hash", self.schedule_hash)
        _validate_source_evidence(self.source_event_ids, self.source_event_hashes)
        if not isinstance(self.batch, DecisionBatch):
            raise TypeError("batch must be DecisionBatch")
        if not isinstance(self.state, LatestSleeveDecisionState):
            raise TypeError("state must be LatestSleeveDecisionState")
        if self.batch.decision_time != self.state.as_of:
            raise ValueError("batch and state decision time must match")

    @property
    def batch_hash(self) -> str:
        return canonical_sha256(self.batch)

    @property
    def state_hash(self) -> str:
        return self.state.state_hash

    @property
    def injection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "target_stream_batch_injection",
            "target_stream_digest": self.target_stream_digest,
            "schedule_hash": self.schedule_hash,
            "source_event_ids": self.source_event_ids,
            "source_event_hashes": self.source_event_hashes,
            "batch": self.batch,
            "state": self.state,
        }


@dataclass(frozen=True, slots=True)
class TargetStreamInjectionOutcome:
    injection: TargetStreamBatchInjection | None = None
    suppression: TargetStreamWarmupSuppression | None = None
    decode_failure: InputDecodeFailure | None = None
    validation_failures: tuple[TargetCandidateValidationFailure, ...] = ()
    batch_failure: DecisionBatchFailure | None = None

    def __post_init__(self) -> None:
        branches = (
            self.injection is not None,
            self.suppression is not None,
            self.decode_failure is not None,
            bool(self.validation_failures),
            self.batch_failure is not None,
        )
        if sum(branches) != 1:
            raise ValueError("outcome requires exactly one result branch")
        if self.injection is not None and not isinstance(
            self.injection, TargetStreamBatchInjection
        ):
            raise TypeError("injection must be TargetStreamBatchInjection")
        if self.suppression is not None and not isinstance(
            self.suppression, TargetStreamWarmupSuppression
        ):
            raise TypeError("suppression must be TargetStreamWarmupSuppression")
        if self.decode_failure is not None and not isinstance(
            self.decode_failure, InputDecodeFailure
        ):
            raise TypeError("decode_failure must be InputDecodeFailure")
        if self.batch_failure is not None and not isinstance(
            self.batch_failure, DecisionBatchFailure
        ):
            raise TypeError("batch_failure must be DecisionBatchFailure")
        if not isinstance(self.validation_failures, tuple) or not all(
            isinstance(failure, TargetCandidateValidationFailure)
            for failure in self.validation_failures
        ):
            raise TypeError(
                "validation_failures must contain TargetCandidateValidationFailure"
            )
        ordered = tuple(
            sorted(
                self.validation_failures,
                key=lambda failure: (failure.event_id, failure.event_hash),
            )
        )
        if len({failure.event_id for failure in ordered}) != len(ordered):
            raise ValueError("validation failure event IDs must be unique")
        object.__setattr__(self, "validation_failures", ordered)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "target_stream_injection_outcome",
            "injection": self.injection,
            "suppression": self.suppression,
            "decode_failure": self.decode_failure,
            "validation_failures": self.validation_failures,
            "batch_failure": self.batch_failure,
        }


class PrecomputedTargetStreamAdapter:
    def __init__(
        self,
        *,
        validator: StrategyOutputValidator | None = None,
        collector: AtomicDecisionBatchCollector | None = None,
    ) -> None:
        self._validator = validator or StrategyOutputValidator()
        self._collector = collector or AtomicDecisionBatchCollector()

    def inject(
        self,
        *,
        stream: PrecomputedTargetStream,
        timeline_events: tuple[TimelineEvent, ...],
        schedule: TargetStreamDecisionSchedule,
        prior_state: LatestSleeveDecisionState | None = None,
    ) -> TargetStreamInjectionOutcome:
        if not isinstance(stream, PrecomputedTargetStream):
            raise TypeError("stream must be PrecomputedTargetStream")
        if not isinstance(timeline_events, tuple) or not all(
            isinstance(event, TimelineEvent) for event in timeline_events
        ):
            raise TypeError("timeline_events must be a tuple of TimelineEvent")
        if not isinstance(schedule, TargetStreamDecisionSchedule):
            raise TypeError("schedule must be TargetStreamDecisionSchedule")
        if prior_state is not None and not isinstance(
            prior_state, LatestSleeveDecisionState
        ):
            raise TypeError("prior_state must be LatestSleeveDecisionState or None")

        issues = self._structural_issues(stream, timeline_events, schedule)
        decoded: dict[str, StrategyDecisionCandidate] = {}
        for timeline_event in timeline_events:
            event = timeline_event.event
            candidate, event_issues = self._decode(event)
            issues.extend(event_issues)
            if candidate is not None:
                decoded[event.event_id] = candidate
        if schedule.segment is TimelineSegment.WARMUP:
            present = {event.event.event_id for event in timeline_events}
            for entry in schedule.entries:
                if entry.event_id not in present:
                    issues.append(
                        InputDecodeIssue(
                            InputDecodeIssueCode.MISSING_WARMUP_EVENT,
                            entry.event_id,
                            "schedule.entries",
                            entry.event_id,
                        )
                    )
        if issues:
            return TargetStreamInjectionOutcome(
                decode_failure=InputDecodeFailure(
                    target_stream_digest=stream.target_stream_digest,
                    schedule_hash=schedule.schedule_hash,
                    issues=tuple(issues),
                    source_event_hashes=tuple(
                        event.event.event_hash for event in timeline_events
                    ),
                )
            )

        entries_by_event = {entry.event_id: entry for entry in schedule.entries}
        submissions: list[DecisionBatchSubmission] = []
        validation_failures: list[TargetCandidateValidationFailure] = []
        for timeline_event in sorted(
            timeline_events,
            key=lambda item: (item.event.ordering_key, item.event.event_id),
        ):
            event = timeline_event.event
            entry = entries_by_event[event.event_id]
            result = self._validator.validate(decoded[event.event_id], entry.validation_context)
            if result.failure is not None:
                validation_failures.append(
                    TargetCandidateValidationFailure(
                        event_id=event.event_id,
                        event_hash=event.event_hash,
                        validation_failure=result.failure,
                    )
                )
            else:
                submissions.append(
                    DecisionBatchSubmission(expectation=entry.expectation, result=result)
                )
        if validation_failures:
            return TargetStreamInjectionOutcome(
                validation_failures=tuple(validation_failures)
            )

        ordered_timeline_events = tuple(
            sorted(
                timeline_events,
                key=lambda item: (item.event.ordering_key, item.event.event_id),
            )
        )
        source_ids = tuple(item.event.event_id for item in ordered_timeline_events)
        source_hashes = tuple(item.event.event_hash for item in ordered_timeline_events)
        if schedule.segment is TimelineSegment.WARMUP:
            return TargetStreamInjectionOutcome(
                suppression=TargetStreamWarmupSuppression(
                    target_stream_digest=stream.target_stream_digest,
                    schedule_hash=schedule.schedule_hash,
                    source_event_ids=source_ids,
                    source_event_hashes=source_hashes,
                    prior_state_hash=(
                        prior_state.state_hash if prior_state is not None else None
                    ),
                )
            )

        batch_result = self._collector.collect(
            decision_time=schedule.decision_time,
            expected=tuple(entry.expectation for entry in schedule.entries),
            submissions=tuple(submissions),
            prior_state=prior_state,
        )
        if batch_result.failure is not None:
            return TargetStreamInjectionOutcome(batch_failure=batch_result.failure)
        if batch_result.batch is None or batch_result.state is None:
            raise RuntimeError("collector returned an invalid success result")
        return TargetStreamInjectionOutcome(
            injection=TargetStreamBatchInjection(
                target_stream_digest=stream.target_stream_digest,
                schedule_hash=schedule.schedule_hash,
                source_event_ids=source_ids,
                source_event_hashes=source_hashes,
                batch=batch_result.batch,
                state=batch_result.state,
            )
        )

    def _structural_issues(
        self,
        stream: PrecomputedTargetStream,
        timeline_events: tuple[TimelineEvent, ...],
        schedule: TargetStreamDecisionSchedule,
    ) -> list[InputDecodeIssue]:
        issues: list[InputDecodeIssue] = []
        source_by_id = {event.event_id: event for event in stream.events}
        scheduled_ids = {entry.event_id for entry in schedule.entries}
        source_ids_at_time = {
            event.event_id for event in stream.events_at(schedule.decision_time)
        }
        for event_id in sorted(scheduled_ids - set(source_by_id)):
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.MISSING_SOURCE_EVENT,
                    event_id,
                    "stream.events",
                    event_id,
                )
            )
        for event_id in sorted(source_ids_at_time - scheduled_ids):
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.UNEXPECTED_EVENT,
                    event_id,
                    "stream.events",
                    event_id,
                )
            )

        counts = Counter(item.event.event_id for item in timeline_events)
        for event_id, count in sorted(counts.items()):
            if count > 1:
                issues.append(
                    InputDecodeIssue(
                        InputDecodeIssueCode.DUPLICATE_EVENT,
                        event_id,
                        "timeline_events",
                        str(count),
                    )
                )
        for timeline_event in timeline_events:
            event = timeline_event.event
            if event.event_id not in scheduled_ids:
                issues.append(
                    InputDecodeIssue(
                        InputDecodeIssueCode.UNEXPECTED_EVENT,
                        event.event_id,
                        "timeline_events",
                        event.event_id,
                    )
                )
            source = source_by_id.get(event.event_id)
            if source is None:
                issues.append(
                    InputDecodeIssue(
                        InputDecodeIssueCode.MISSING_SOURCE_EVENT,
                        event.event_id,
                        "timeline_events",
                        event.event_id,
                    )
                )
            elif source.event_hash != event.event_hash:
                issues.append(
                    InputDecodeIssue(
                        InputDecodeIssueCode.SOURCE_EVENT_HASH_MISMATCH,
                        event.event_id,
                        "timeline_events",
                        event.event_hash,
                    )
                )
            if timeline_event.segment is not schedule.segment:
                issues.append(
                    InputDecodeIssue(
                        InputDecodeIssueCode.TIMELINE_SEGMENT_MISMATCH,
                        event.event_id,
                        "timeline_events.segment",
                        timeline_event.segment.value,
                    )
                )
            if (
                event.event_time != schedule.decision_time
                or event.available_time != schedule.decision_time
            ):
                issues.append(
                    InputDecodeIssue(
                        InputDecodeIssueCode.EVENT_TIME_MISMATCH,
                        event.event_id,
                        "timeline_events.event_time",
                        str(event.event_time.epoch_nanoseconds),
                    )
                )
        return issues

    def _decode(
        self, event: MarketEvent
    ) -> tuple[StrategyDecisionCandidate | None, list[InputDecodeIssue]]:
        issues: list[InputDecodeIssue] = []
        if event.capability != TARGET_STREAM_CAPABILITY:
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.UNSUPPORTED_CAPABILITY,
                    event.event_id,
                    "event.capability",
                    event.capability.identity,
                )
            )
        if event.event_type != TARGET_STREAM_EVENT_TYPE:
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.UNSUPPORTED_EVENT_TYPE,
                    event.event_id,
                    "event.event_type",
                    event.event_type,
                )
            )
        if event.instrument_id is not None:
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.EVENT_INSTRUMENT_NOT_EMPTY,
                    event.event_id,
                    "event.instrument_id",
                    str(event.instrument_id),
                )
            )

        fields = set(event.payload)
        for field in sorted(_TARGET_ENVELOPE_FIELDS - fields):
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.MISSING_ENVELOPE_FIELD,
                    event.event_id,
                    "event.payload",
                    field,
                )
            )
        for field in sorted(fields - _TARGET_ENVELOPE_FIELDS):
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.UNKNOWN_ENVELOPE_FIELD,
                    event.event_id,
                    "event.payload",
                    field,
                )
            )
        schema_version = event.payload.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != _TARGET_STREAM_SCHEMA_VERSION
        ):
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.UNSUPPORTED_SCHEMA_VERSION,
                    event.event_id,
                    "event.payload.schema_version",
                    str(schema_version),
                )
            )
        candidate_fields = event.payload.get("candidate")
        if "candidate" in event.payload and not isinstance(candidate_fields, Mapping):
            issues.append(
                InputDecodeIssue(
                    InputDecodeIssueCode.CANDIDATE_NOT_MAPPING,
                    event.event_id,
                    "event.payload.candidate",
                    type(candidate_fields).__name__,
                )
            )
        if issues:
            return None, issues
        try:
            payload = StrategyDecisionPayload(
                cast(Mapping[str, Any], candidate_fields)
            )
        except (TypeError, ValueError) as error:
            return None, [
                InputDecodeIssue(
                    InputDecodeIssueCode.CANDIDATE_NOT_MAPPING,
                    event.event_id,
                    "event.payload.candidate",
                    type(error).__name__,
                )
            ]
        return StrategyDecisionCandidate(payload), []
