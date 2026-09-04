from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    InstrumentId,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent


_SCHEMA_VERSION = 1


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    digest = text.removeprefix("sha256:")
    if (
        len(text) != 71
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{name} must be a sha256 content hash")
    return text


@dataclass(frozen=True, slots=True)
class ObservationPurposeRef:
    key: str
    version: int

    def __post_init__(self) -> None:
        _text("observation purpose key", self.key)
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("observation purpose version must be an integer")
        if self.version <= 0:
            raise ValueError("observation purpose version must be positive")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_purpose_ref",
            "schema_version": _SCHEMA_VERSION,
            "key": self.key,
            "version": self.version,
        }

    @property
    def purpose_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "purpose_hash": self.purpose_hash}


@dataclass(frozen=True, slots=True)
class ObservationQuery:
    dataset_key: str
    instrument_id: InstrumentId
    purpose: ObservationPurposeRef
    capability: MarketBundleCapability

    def __post_init__(self) -> None:
        _text("observation dataset key", self.dataset_key)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be InstrumentId")
        if type(self.purpose) is not ObservationPurposeRef:
            raise TypeError("purpose must be ObservationPurposeRef")
        if type(self.capability) is not MarketBundleCapability:
            raise TypeError("capability must be MarketBundleCapability")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_query",
            "schema_version": _SCHEMA_VERSION,
            "dataset_key": self.dataset_key,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "purpose": self.purpose.to_canonical_dict(),
            "capability": self.capability.to_canonical_dict(),
        }

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "query_hash": self.query_hash}


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    purpose: ObservationPurposeRef
    event: MarketEvent

    def __post_init__(self) -> None:
        if type(self.purpose) is not ObservationPurposeRef:
            raise TypeError("purpose must be ObservationPurposeRef")
        if type(self.event) is not MarketEvent:
            raise TypeError("event must be MarketEvent")
        if self.event.instrument_id is None:
            raise ValueError("G11A observation records require one Instrument")

    def _query(self) -> ObservationQuery:
        instrument_id = self.event.instrument_id
        if instrument_id is None:
            raise ValueError("G11A observation records require one Instrument")
        return ObservationQuery(
            dataset_key=self.event.stream_key,
            instrument_id=instrument_id,
            purpose=self.purpose,
            capability=self.event.capability,
        )

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_record",
            "schema_version": _SCHEMA_VERSION,
            "purpose": self.purpose.to_canonical_dict(),
            "event": self.event.to_canonical_dict(),
        }

    @property
    def record_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "record_hash": self.record_hash}


class ObservationQueryFailureCode(str, Enum):
    DATASET_NOT_AUTHORIZED = "dataset_not_authorized"
    INSTRUMENT_NOT_AUTHORIZED = "instrument_not_authorized"
    PURPOSE_NOT_AUTHORIZED = "purpose_not_authorized"
    CAPABILITY_NOT_AUTHORIZED = "capability_not_authorized"


@dataclass(frozen=True, slots=True)
class ObservationQueryFailure:
    view_hash: str
    query: ObservationQuery
    code: ObservationQueryFailureCode

    def __post_init__(self) -> None:
        _hash("view_hash", self.view_hash)
        if type(self.query) is not ObservationQuery:
            raise TypeError("query must be ObservationQuery")
        if not isinstance(self.code, ObservationQueryFailureCode):
            raise TypeError("code must be ObservationQueryFailureCode")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_query_failure",
            "schema_version": _SCHEMA_VERSION,
            "view_hash": self.view_hash,
            "query": self.query.to_canonical_dict(),
            "code": self.code.value,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class ObservationQueryResult:
    view_hash: str
    query: ObservationQuery
    events: tuple[MarketEvent, ...]

    def __post_init__(self) -> None:
        _hash("view_hash", self.view_hash)
        if type(self.query) is not ObservationQuery:
            raise TypeError("query must be ObservationQuery")
        if type(self.events) is not tuple or any(type(event) is not MarketEvent for event in self.events):
            raise TypeError("events must be a tuple of MarketEvent")
        if any(
            event.stream_key != self.query.dataset_key
            or event.instrument_id != self.query.instrument_id
            or event.capability != self.query.capability
            for event in self.events
        ):
            raise ValueError("result event context must match query")
        identities = tuple(event.event_id for event in self.events)
        if len(identities) != len(set(identities)):
            raise ValueError("result event identities must be unique")
        order = tuple(
            (event.ordering_key, event.event_id, event.revision_id, event.event_hash)
            for event in self.events
        )
        if order != tuple(sorted(order)):
            raise ValueError("result events must use canonical order")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_query_result",
            "schema_version": _SCHEMA_VERSION,
            "view_hash": self.view_hash,
            "query": self.query.to_canonical_dict(),
            "events": [event.to_canonical_dict() for event in self.events],
        }

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "result_hash": self.result_hash}


@dataclass(frozen=True, slots=True)
class ObservationQueryOutcome:
    result: ObservationQueryResult | None
    failure: ObservationQueryFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("exactly one result or failure is required")
        if self.result is not None and type(self.result) is not ObservationQueryResult:
            raise TypeError("result must be ObservationQueryResult")
        if self.failure is not None and type(self.failure) is not ObservationQueryFailure:
            raise TypeError("failure must be ObservationQueryFailure")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_query_outcome",
            "schema_version": _SCHEMA_VERSION,
            "result": None if self.result is None else self.result.to_canonical_dict(),
            "failure": None if self.failure is None else self.failure.to_canonical_dict(),
        }

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "outcome_hash": self.outcome_hash}


class ObservationView:
    __slots__ = ("_allowed", "_records", "_view_hash")

    def __init__(
        self,
        *,
        allowed_queries: Iterable[ObservationQuery],
        records: Iterable[ObservationRecord],
    ) -> None:
        allowed_by_hash: dict[str, ObservationQuery] = {}
        for allowed_query in allowed_queries:
            if type(allowed_query) is not ObservationQuery:
                raise TypeError("allowed_queries must contain ObservationQuery")
            allowed_by_hash[allowed_query.query_hash] = allowed_query
        allowed = tuple(sorted(allowed_by_hash.values(), key=lambda item: item.query_hash))
        allowed_hashes = set(allowed_by_hash)

        retained: dict[tuple[str, int, str], ObservationRecord] = {}
        for record in records:
            if type(record) is not ObservationRecord:
                raise TypeError("records must contain ObservationRecord")
            if record._query().query_hash not in allowed_hashes:
                continue
            identity = (record.purpose.key, record.purpose.version, record.event.event_id)
            previous = retained.get(identity)
            if previous is not None and previous.record_hash != record.record_hash:
                raise ValueError("conflicting authorized observation record")
            retained[identity] = record

        ordered_records = tuple(
            sorted(
                retained.values(),
                key=lambda item: (
                    item.event.ordering_key,
                    item.event.event_id,
                    item.event.revision_id,
                    item.record_hash,
                ),
            )
        )
        body = {
            "type": "observation_view",
            "schema_version": _SCHEMA_VERSION,
            "allowed_queries": [item.to_canonical_dict() for item in allowed],
            "records": [item.to_canonical_dict() for item in ordered_records],
        }
        self._allowed = allowed
        self._records = ordered_records
        self._view_hash = canonical_sha256(body)

    @property
    def view_hash(self) -> str:
        return self._view_hash

    def query(self, query: ObservationQuery) -> ObservationQueryOutcome:
        if type(query) is not ObservationQuery:
            raise TypeError("query must be ObservationQuery")
        code = self._authorization_failure(query)
        if code is not None:
            return ObservationQueryOutcome(
                result=None,
                failure=ObservationQueryFailure(
                    view_hash=self.view_hash,
                    query=query,
                    code=code,
                ),
            )
        events = tuple(
            record.event
            for record in self._records
            if record._query() == query
        )
        return ObservationQueryOutcome(
            result=ObservationQueryResult(
                view_hash=self.view_hash,
                query=query,
                events=events,
            ),
            failure=None,
        )

    def _authorization_failure(
        self, query: ObservationQuery
    ) -> ObservationQueryFailureCode | None:
        dataset = tuple(
            allowed for allowed in self._allowed if allowed.dataset_key == query.dataset_key
        )
        if not dataset:
            return ObservationQueryFailureCode.DATASET_NOT_AUTHORIZED
        instrument = tuple(
            allowed for allowed in dataset if allowed.instrument_id == query.instrument_id
        )
        if not instrument:
            return ObservationQueryFailureCode.INSTRUMENT_NOT_AUTHORIZED
        purpose = tuple(
            allowed for allowed in instrument if allowed.purpose == query.purpose
        )
        if not purpose:
            return ObservationQueryFailureCode.PURPOSE_NOT_AUTHORIZED
        if not any(allowed.capability == query.capability for allowed in purpose):
            return ObservationQueryFailureCode.CAPABILITY_NOT_AUTHORIZED
        return None


@dataclass(frozen=True, slots=True)
class RevisionedObservationRecord:
    observation_key: str
    record: ObservationRecord

    def __post_init__(self) -> None:
        _text("observation_key", self.observation_key)
        if type(self.record) is not ObservationRecord:
            raise TypeError("record must be ObservationRecord")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "revisioned_observation_record",
            "schema_version": _SCHEMA_VERSION,
            "observation_key": self.observation_key,
            "record": self.record.to_canonical_dict(),
        }

    @property
    def revisioned_record_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            **self._canonical_body(),
            "revisioned_record_hash": self.revisioned_record_hash,
        }


class ObservationCausalityFailureCode(str, Enum):
    REVISION_ID_CONFLICT = "revision_id_conflict"
    REVISION_PARENT_MISSING = "revision_parent_missing"
    REVISION_CHAIN_CONFLICT = "revision_chain_conflict"
    REVISION_CONTEXT_MISMATCH = "revision_context_mismatch"
    REVISION_AVAILABILITY_REGRESSION = "revision_availability_regression"


@dataclass(frozen=True, slots=True)
class ObservationCausalityFailure:
    view_hash: str
    query: ObservationQuery
    decision_instant: SimulationInstant
    code: ObservationCausalityFailureCode
    observation_keys: tuple[str, ...]
    revision_ids: tuple[str, ...]
    candidate_record_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        _hash("view_hash", self.view_hash)
        if type(self.query) is not ObservationQuery:
            raise TypeError("query must be ObservationQuery")
        if type(self.decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")
        if not isinstance(self.code, ObservationCausalityFailureCode):
            raise TypeError("code must be ObservationCausalityFailureCode")
        if self.observation_keys != tuple(sorted(set(self.observation_keys))):
            raise ValueError("observation_keys must be sorted and unique")
        if any(not isinstance(value, str) or not value for value in self.revision_ids):
            raise ValueError("revision_ids must be non-empty strings")
        if self.revision_ids != tuple(sorted(self.revision_ids)):
            raise ValueError("revision_ids must be sorted")
        if self.candidate_record_hashes != tuple(
            sorted(set(self.candidate_record_hashes))
        ):
            raise ValueError("candidate_record_hashes must be sorted and unique")
        for value in self.candidate_record_hashes:
            _hash("candidate_record_hash", value)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_causality_failure",
            "schema_version": _SCHEMA_VERSION,
            "view_hash": self.view_hash,
            "query": self.query.to_canonical_dict(),
            "decision_instant": self.decision_instant.to_canonical_dict(),
            "code": self.code.value,
            "observation_keys": list(self.observation_keys),
            "revision_ids": list(self.revision_ids),
            "candidate_record_hashes": list(self.candidate_record_hashes),
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "failure_hash": self.failure_hash}


def _revision_set_hash(
    query: ObservationQuery, candidate_record_hashes: tuple[str, ...]
) -> str:
    return canonical_sha256(
        {
            "type": "observation_revision_set",
            "schema_version": _SCHEMA_VERSION,
            "query": query.to_canonical_dict(),
            "candidate_record_hashes": list(candidate_record_hashes),
        }
    )


def _selected_dataset_hash(
    query: ObservationQuery,
    observation_keys: tuple[str, ...],
    events: tuple[MarketEvent, ...],
) -> str:
    return canonical_sha256(
        {
            "type": "point_in_time_observation_dataset",
            "schema_version": _SCHEMA_VERSION,
            "query": query.to_canonical_dict(),
            "observation_keys": list(observation_keys),
            "events": [event.to_canonical_dict() for event in events],
        }
    )


@dataclass(frozen=True, slots=True)
class ObservationCausalityTrace:
    view_hash: str
    query: ObservationQuery
    decision_instant: SimulationInstant
    candidate_record_hashes: tuple[str, ...]
    revision_set_hash: str
    selected_observation_keys: tuple[str, ...]
    selected_event_hashes: tuple[str, ...]
    selected_revision_ids: tuple[str, ...]
    selected_source_hashes: tuple[str, ...]
    dataset_hash: str
    max_event_time: UtcInstant | None
    max_available_instant: SimulationInstant | None
    event_count: int

    def __post_init__(self) -> None:
        _hash("view_hash", self.view_hash)
        if type(self.query) is not ObservationQuery:
            raise TypeError("query must be ObservationQuery")
        if type(self.decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")
        if self.candidate_record_hashes != tuple(
            sorted(set(self.candidate_record_hashes))
        ):
            raise ValueError("candidate_record_hashes must be sorted and unique")
        for value in self.candidate_record_hashes:
            _hash("candidate_record_hash", value)
        _hash("revision_set_hash", self.revision_set_hash)
        if self.revision_set_hash != _revision_set_hash(
            self.query, self.candidate_record_hashes
        ):
            raise ValueError("revision_set_hash does not match candidates")
        if isinstance(self.event_count, bool) or not isinstance(self.event_count, int):
            raise TypeError("event_count must be an integer")
        if self.event_count < 0:
            raise ValueError("event_count must be non-negative")
        selected = (
            self.selected_observation_keys,
            self.selected_event_hashes,
            self.selected_revision_ids,
            self.selected_source_hashes,
        )
        if any(type(values) is not tuple for values in selected) or any(
            len(values) != self.event_count for values in selected
        ):
            raise ValueError("selected trace fields must align with event_count")
        for value in (*self.selected_event_hashes, *self.selected_source_hashes):
            _hash("selected_hash", value)
        if any(not isinstance(value, str) or not value for value in self.selected_observation_keys):
            raise ValueError("selected observation keys must be non-empty strings")
        if len(self.selected_observation_keys) != len(
            set(self.selected_observation_keys)
        ):
            raise ValueError("selected observation keys must be unique")
        if any(not isinstance(value, str) or not value for value in self.selected_revision_ids):
            raise ValueError("selected revision IDs must be non-empty strings")
        _hash("dataset_hash", self.dataset_hash)
        if self.max_event_time is not None and type(self.max_event_time) is not UtcInstant:
            raise TypeError("max_event_time must be UtcInstant or None")
        if (
            self.max_available_instant is not None
            and type(self.max_available_instant) is not SimulationInstant
        ):
            raise TypeError("max_available_instant must be SimulationInstant or None")
        if self.event_count == 0:
            if self.max_event_time is not None or self.max_available_instant is not None:
                raise ValueError("empty trace maxima must be None")
        elif self.max_event_time is None or self.max_available_instant is None:
            raise ValueError("non-empty trace maxima are required")
        if (
            self.max_available_instant is not None
            and self.max_available_instant > self.decision_instant
        ):
            raise ValueError("trace cannot contain future availability")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "observation_causality_trace",
            "schema_version": _SCHEMA_VERSION,
            "view_hash": self.view_hash,
            "query": self.query.to_canonical_dict(),
            "decision_instant": self.decision_instant.to_canonical_dict(),
            "candidate_record_hashes": list(self.candidate_record_hashes),
            "revision_set_hash": self.revision_set_hash,
            "selected_observation_keys": list(self.selected_observation_keys),
            "selected_event_hashes": list(self.selected_event_hashes),
            "selected_revision_ids": list(self.selected_revision_ids),
            "selected_source_hashes": list(self.selected_source_hashes),
            "dataset_hash": self.dataset_hash,
            "max_event_time": (
                None if self.max_event_time is None else self.max_event_time.to_canonical_dict()
            ),
            "max_available_instant": (
                None
                if self.max_available_instant is None
                else self.max_available_instant.to_canonical_dict()
            ),
            "event_count": self.event_count,
        }

    @property
    def trace_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "trace_hash": self.trace_hash}


@dataclass(frozen=True, slots=True)
class PointInTimeObservationQueryResult:
    view_hash: str
    query: ObservationQuery
    decision_instant: SimulationInstant
    events: tuple[MarketEvent, ...]
    trace: ObservationCausalityTrace

    def __post_init__(self) -> None:
        _hash("view_hash", self.view_hash)
        if type(self.query) is not ObservationQuery:
            raise TypeError("query must be ObservationQuery")
        if type(self.decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")
        if type(self.events) is not tuple or any(
            type(event) is not MarketEvent for event in self.events
        ):
            raise TypeError("events must be a tuple of MarketEvent")
        if type(self.trace) is not ObservationCausalityTrace:
            raise TypeError("trace must be ObservationCausalityTrace")
        if any(
            event.stream_key != self.query.dataset_key
            or event.instrument_id != self.query.instrument_id
            or event.capability != self.query.capability
            for event in self.events
        ):
            raise ValueError("result event context must match query")
        if any(event.timeline_instant > self.decision_instant for event in self.events):
            raise ValueError("result cannot contain future events")
        identities = tuple(event.event_id for event in self.events)
        if len(identities) != len(set(identities)):
            raise ValueError("result event identities must be unique")
        order = tuple(
            (event.ordering_key, event.event_id, event.revision_id, event.event_hash)
            for event in self.events
        )
        if order != tuple(sorted(order)):
            raise ValueError("result events must use canonical order")
        if (
            self.trace.view_hash != self.view_hash
            or self.trace.query != self.query
            or self.trace.decision_instant != self.decision_instant
        ):
            raise ValueError("trace context must match result")
        expected_event_hashes = tuple(event.event_hash for event in self.events)
        expected_revision_ids = tuple(event.revision_id for event in self.events)
        expected_source_hashes = tuple(event.source_hash for event in self.events)
        if (
            self.trace.selected_event_hashes != expected_event_hashes
            or self.trace.selected_revision_ids != expected_revision_ids
            or self.trace.selected_source_hashes != expected_source_hashes
            or self.trace.event_count != len(self.events)
        ):
            raise ValueError("trace selected fields must match result events")
        if self.trace.dataset_hash != _selected_dataset_hash(
            self.query, self.trace.selected_observation_keys, self.events
        ):
            raise ValueError("trace dataset_hash must match result events")
        expected_event_time = max(
            (event.event_time for event in self.events), default=None
        )
        expected_available = max(
            (event.timeline_instant for event in self.events), default=None
        )
        if (
            self.trace.max_event_time != expected_event_time
            or self.trace.max_available_instant != expected_available
        ):
            raise ValueError("trace maxima must match result events")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "point_in_time_observation_query_result",
            "schema_version": _SCHEMA_VERSION,
            "view_hash": self.view_hash,
            "query": self.query.to_canonical_dict(),
            "decision_instant": self.decision_instant.to_canonical_dict(),
            "events": [event.to_canonical_dict() for event in self.events],
            "trace": self.trace.to_canonical_dict(),
        }

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "result_hash": self.result_hash}


PointInTimeObservationFailure = ObservationQueryFailure | ObservationCausalityFailure


@dataclass(frozen=True, slots=True)
class PointInTimeObservationQueryOutcome:
    result: PointInTimeObservationQueryResult | None
    failure: PointInTimeObservationFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("exactly one result or failure is required")
        if (
            self.result is not None
            and type(self.result) is not PointInTimeObservationQueryResult
        ):
            raise TypeError("result must be PointInTimeObservationQueryResult")
        if self.failure is not None and type(self.failure) not in (
            ObservationQueryFailure,
            ObservationCausalityFailure,
        ):
            raise TypeError("failure must be an observation failure")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "point_in_time_observation_query_outcome",
            "schema_version": _SCHEMA_VERSION,
            "result": None if self.result is None else self.result.to_canonical_dict(),
            "failure": None if self.failure is None else self.failure.to_canonical_dict(),
        }

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "outcome_hash": self.outcome_hash}


class PointInTimeObservationView:
    __slots__ = ("_allowed", "_decision_instant", "_records", "_view_hash")

    def __init__(
        self,
        *,
        allowed_queries: Iterable[ObservationQuery],
        records: Iterable[RevisionedObservationRecord],
        decision_instant: SimulationInstant,
    ) -> None:
        if type(decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")
        allowed_by_hash: dict[str, ObservationQuery] = {}
        for allowed_query in allowed_queries:
            if type(allowed_query) is not ObservationQuery:
                raise TypeError("allowed_queries must contain ObservationQuery")
            allowed_by_hash[allowed_query.query_hash] = allowed_query
        allowed = tuple(sorted(allowed_by_hash.values(), key=lambda item: item.query_hash))
        allowed_hashes = set(allowed_by_hash)

        visible_by_hash: dict[str, RevisionedObservationRecord] = {}
        for record in records:
            if type(record) is not RevisionedObservationRecord:
                raise TypeError("records must contain RevisionedObservationRecord")
            if record.record._query().query_hash not in allowed_hashes:
                continue
            if record.record.event.timeline_instant > decision_instant:
                continue
            visible_by_hash[record.revisioned_record_hash] = record
        visible = tuple(
            sorted(
                visible_by_hash.values(),
                key=lambda item: (
                    item.record._query().query_hash,
                    item.observation_key,
                    item.record.event.ordering_key,
                    item.record.event.event_id,
                    item.record.event.revision_id,
                    item.revisioned_record_hash,
                ),
            )
        )
        body = {
            "type": "point_in_time_observation_view",
            "schema_version": _SCHEMA_VERSION,
            "decision_instant": decision_instant.to_canonical_dict(),
            "allowed_queries": [item.to_canonical_dict() for item in allowed],
            "records": [item.to_canonical_dict() for item in visible],
        }
        self._allowed = allowed
        self._decision_instant = decision_instant
        self._records = visible
        self._view_hash = canonical_sha256(body)

    @property
    def view_hash(self) -> str:
        return self._view_hash

    def query(self, query: ObservationQuery) -> PointInTimeObservationQueryOutcome:
        if type(query) is not ObservationQuery:
            raise TypeError("query must be ObservationQuery")
        authorization = self._authorization_failure(query)
        if authorization is not None:
            return PointInTimeObservationQueryOutcome(
                result=None,
                failure=ObservationQueryFailure(
                    view_hash=self.view_hash,
                    query=query,
                    code=authorization,
                ),
            )
        candidates = tuple(
            record for record in self._records if record.record._query() == query
        )
        failure_code = self._revision_failure(candidates)
        if failure_code is not None:
            return PointInTimeObservationQueryOutcome(
                result=None,
                failure=self._causality_failure(query, candidates, failure_code),
            )
        selected = self._select(candidates)
        events = tuple(record.record.event for record in selected)
        observation_keys = tuple(record.observation_key for record in selected)
        candidate_hashes = tuple(
            sorted(record.revisioned_record_hash for record in candidates)
        )
        trace = ObservationCausalityTrace(
            view_hash=self.view_hash,
            query=query,
            decision_instant=self._decision_instant,
            candidate_record_hashes=candidate_hashes,
            revision_set_hash=_revision_set_hash(query, candidate_hashes),
            selected_observation_keys=observation_keys,
            selected_event_hashes=tuple(event.event_hash for event in events),
            selected_revision_ids=tuple(event.revision_id for event in events),
            selected_source_hashes=tuple(event.source_hash for event in events),
            dataset_hash=_selected_dataset_hash(query, observation_keys, events),
            max_event_time=max((event.event_time for event in events), default=None),
            max_available_instant=max(
                (event.timeline_instant for event in events), default=None
            ),
            event_count=len(events),
        )
        return PointInTimeObservationQueryOutcome(
            result=PointInTimeObservationQueryResult(
                view_hash=self.view_hash,
                query=query,
                decision_instant=self._decision_instant,
                events=events,
                trace=trace,
            ),
            failure=None,
        )

    def _authorization_failure(
        self, query: ObservationQuery
    ) -> ObservationQueryFailureCode | None:
        dataset = tuple(
            allowed for allowed in self._allowed if allowed.dataset_key == query.dataset_key
        )
        if not dataset:
            return ObservationQueryFailureCode.DATASET_NOT_AUTHORIZED
        instrument = tuple(
            allowed for allowed in dataset if allowed.instrument_id == query.instrument_id
        )
        if not instrument:
            return ObservationQueryFailureCode.INSTRUMENT_NOT_AUTHORIZED
        purpose = tuple(
            allowed for allowed in instrument if allowed.purpose == query.purpose
        )
        if not purpose:
            return ObservationQueryFailureCode.PURPOSE_NOT_AUTHORIZED
        if not any(allowed.capability == query.capability for allowed in purpose):
            return ObservationQueryFailureCode.CAPABILITY_NOT_AUTHORIZED
        return None

    @staticmethod
    def _revision_failure(
        candidates: tuple[RevisionedObservationRecord, ...],
    ) -> ObservationCausalityFailureCode | None:
        identities: dict[tuple[str, str], set[str]] = {}
        for record in candidates:
            identity = (record.observation_key, record.record.event.revision_id)
            identities.setdefault(identity, set()).add(record.revisioned_record_hash)
        if any(len(hashes) > 1 for hashes in identities.values()):
            return ObservationCausalityFailureCode.REVISION_ID_CONFLICT

        groups = PointInTimeObservationView._groups(candidates)
        for records in groups.values():
            revision_ids = {record.record.event.revision_id for record in records}
            if any(
                record.record.event.supersedes_revision_id is not None
                and record.record.event.supersedes_revision_id not in revision_ids
                for record in records
            ):
                return ObservationCausalityFailureCode.REVISION_PARENT_MISSING

        terminals: list[str] = []
        for records in groups.values():
            by_revision = {
                record.record.event.revision_id: record for record in records
            }
            children: dict[str, list[str]] = {}
            roots = []
            for record in records:
                parent = record.record.event.supersedes_revision_id
                if parent is None:
                    roots.append(record.record.event.revision_id)
                else:
                    children.setdefault(parent, []).append(
                        record.record.event.revision_id
                    )
            if len(roots) != 1 or any(len(values) != 1 for values in children.values()):
                return ObservationCausalityFailureCode.REVISION_CHAIN_CONFLICT
            visited: set[str] = set()
            current = roots[0]
            while current not in visited:
                visited.add(current)
                next_values = children.get(current, [])
                if not next_values:
                    break
                current = next_values[0]
            if len(visited) != len(by_revision) or current in children:
                return ObservationCausalityFailureCode.REVISION_CHAIN_CONFLICT
            terminals.append(by_revision[current].record.event.event_id)
        if len(terminals) != len(set(terminals)):
            return ObservationCausalityFailureCode.REVISION_CHAIN_CONFLICT

        for records in groups.values():
            first = records[0].record.event
            if any(
                record.record._query() != records[0].record._query()
                or record.record.event.event_type != first.event_type
                or record.record.event.event_time != first.event_time
                for record in records[1:]
            ):
                return ObservationCausalityFailureCode.REVISION_CONTEXT_MISMATCH

        for records in groups.values():
            events_by_revision = {
                record.record.event.revision_id: record.record.event
                for record in records
            }
            if any(
                event.supersedes_revision_id is not None
                and event.timeline_instant
                <= events_by_revision[event.supersedes_revision_id].timeline_instant
                for event in events_by_revision.values()
            ):
                return ObservationCausalityFailureCode.REVISION_AVAILABILITY_REGRESSION
        return None

    @staticmethod
    def _groups(
        candidates: tuple[RevisionedObservationRecord, ...],
    ) -> dict[str, tuple[RevisionedObservationRecord, ...]]:
        groups: dict[str, list[RevisionedObservationRecord]] = {}
        for record in candidates:
            groups.setdefault(record.observation_key, []).append(record)
        return {
            key: tuple(sorted(values, key=lambda value: value.revisioned_record_hash))
            for key, values in groups.items()
        }

    @staticmethod
    def _select(
        candidates: tuple[RevisionedObservationRecord, ...],
    ) -> tuple[RevisionedObservationRecord, ...]:
        selected: list[RevisionedObservationRecord] = []
        for records in PointInTimeObservationView._groups(candidates).values():
            parent_ids = {
                record.record.event.supersedes_revision_id
                for record in records
                if record.record.event.supersedes_revision_id is not None
            }
            selected.append(
                next(
                    record
                    for record in records
                    if record.record.event.revision_id not in parent_ids
                )
            )
        return tuple(
            sorted(
                selected,
                key=lambda item: (
                    item.record.event.ordering_key,
                    item.record.event.event_id,
                    item.record.event.revision_id,
                    item.revisioned_record_hash,
                ),
            )
        )

    def _causality_failure(
        self,
        query: ObservationQuery,
        candidates: tuple[RevisionedObservationRecord, ...],
        code: ObservationCausalityFailureCode,
    ) -> ObservationCausalityFailure:
        return ObservationCausalityFailure(
            view_hash=self.view_hash,
            query=query,
            decision_instant=self._decision_instant,
            code=code,
            observation_keys=tuple(
                sorted({record.observation_key for record in candidates})
            ),
            revision_ids=tuple(
                sorted(record.record.event.revision_id for record in candidates)
            ),
            candidate_record_hashes=tuple(
                sorted({record.revisioned_record_hash for record in candidates})
            ),
        )
