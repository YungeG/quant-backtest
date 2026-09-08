from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import SimulationInstant, UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketEvent

from .observations import (
    ObservationCausalityTrace,
    ObservationQuery,
    PointInTimeObservationQueryResult,
)


_SCHEMA_VERSION = 1
_MAX_LOOKBACK = 10_000


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
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
class BarDefinitionRef:
    key: str
    version: int
    definition_hash: str

    def __post_init__(self) -> None:
        _text("BarDefinition key", self.key)
        if type(self.version) is not int or self.version <= 0:
            raise ValueError("BarDefinition version must be a positive integer")
        _hash("definition_hash", self.definition_hash)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "bar_definition_ref",
            "schema_version": _SCHEMA_VERSION,
            "key": self.key,
            "version": self.version,
            "definition_hash": self.definition_hash,
        }

    @property
    def bar_definition_ref_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            **self._canonical_body(),
            "bar_definition_ref_hash": self.bar_definition_ref_hash,
        }


@dataclass(frozen=True, slots=True)
class NamedBarWindowQuery:
    observation_query: ObservationQuery
    bar_definition: BarDefinitionRef
    decision_instant: SimulationInstant
    lookback_count: int
    end_at_or_before: UtcInstant | None

    def __post_init__(self) -> None:
        if type(self.observation_query) is not ObservationQuery:
            raise TypeError("observation_query must be ObservationQuery")
        if type(self.bar_definition) is not BarDefinitionRef:
            raise TypeError("bar_definition must be BarDefinitionRef")
        if type(self.decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")
        if (
            type(self.lookback_count) is not int
            or not 1 <= self.lookback_count <= _MAX_LOOKBACK
        ):
            raise ValueError(f"lookback_count must be between 1 and {_MAX_LOOKBACK}")
        if self.end_at_or_before is not None and type(
            self.end_at_or_before
        ) is not UtcInstant:
            raise TypeError("end_at_or_before must be UtcInstant or None")
        if (
            self.end_at_or_before is not None
            and self.end_at_or_before > self.decision_instant.instant
        ):
            raise ValueError("end_at_or_before must not be after Decision Instant")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "named_bar_window_query",
            "schema_version": _SCHEMA_VERSION,
            "observation_query": self.observation_query.to_canonical_dict(),
            "bar_definition": self.bar_definition.to_canonical_dict(),
            "decision_instant": self.decision_instant.to_canonical_dict(),
            "lookback_count": self.lookback_count,
            "end_at_or_before": (
                None
                if self.end_at_or_before is None
                else self.end_at_or_before.to_canonical_dict()
            ),
        }

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "query_hash": self.query_hash}


@dataclass(frozen=True, slots=True)
class NamedBarWindowResult:
    query: NamedBarWindowQuery
    events: tuple[MarketEvent, ...]
    causality_trace: ObservationCausalityTrace
    available_count: int
    requested_count: int
    coverage_complete: bool
    shortfall_count: int
    max_event_time: UtcInstant | None
    max_available_instant: SimulationInstant | None
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.query) is not NamedBarWindowQuery:
            raise TypeError("query must be NamedBarWindowQuery")
        if type(self.events) is not tuple or any(
            type(event) is not MarketEvent for event in self.events
        ):
            raise TypeError("events must be a tuple of MarketEvent")
        if type(self.causality_trace) is not ObservationCausalityTrace:
            raise TypeError("causality_trace must be ObservationCausalityTrace")
        if self.causality_trace.query != self.query.observation_query:
            raise ValueError("causality trace Query must match named window")
        if self.causality_trace.decision_instant != self.query.decision_instant:
            raise ValueError("causality trace Decision Instant must match named window")
        selected_event_hashes = set(self.causality_trace.selected_event_hashes)
        if any(event.event_hash not in selected_event_hashes for event in self.events):
            raise ValueError("window Events must be selected by causality trace")
        if type(self.available_count) is not int or self.available_count < 0:
            raise ValueError("available_count must be nonnegative integer")
        if self.requested_count != self.query.lookback_count:
            raise ValueError("requested_count must match Query")
        expected_count = min(self.available_count, self.requested_count)
        if len(self.events) != expected_count:
            raise ValueError("returned Event count must match bounded lookback")
        expected_complete = self.available_count >= self.requested_count
        if self.coverage_complete is not expected_complete:
            raise ValueError("coverage_complete does not match counts")
        if self.shortfall_count != max(self.requested_count - self.available_count, 0):
            raise ValueError("shortfall_count does not match counts")
        order = tuple(
            (event.ordering_key, event.event_id, event.revision_id, event.event_hash)
            for event in self.events
        )
        if order != tuple(sorted(order)):
            raise ValueError("window Events must use canonical order")
        if len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("window Event identities must be unique")
        if any(
            event.event_type != "bar"
            or event.stream_key != self.query.observation_query.dataset_key
            or event.instrument_id != self.query.observation_query.instrument_id
            or event.capability != self.query.observation_query.capability
            or event.timeline_instant > self.query.decision_instant
            or (
                self.query.end_at_or_before is not None
                and event.event_time > self.query.end_at_or_before
            )
            for event in self.events
        ):
            raise ValueError("window Event context does not match Query")
        expected_event_time = max((event.event_time for event in self.events), default=None)
        expected_available = max(
            (event.timeline_instant for event in self.events), default=None
        )
        if (
            self.max_event_time != expected_event_time
            or self.max_available_instant != expected_available
        ):
            raise ValueError("window maxima do not match Events")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G11D result flags must remain false")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "named_bar_window_result",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query.to_canonical_dict(),
            "events": [event.to_canonical_dict() for event in self.events],
            "causality_trace": self.causality_trace.to_canonical_dict(),
            "available_count": self.available_count,
            "requested_count": self.requested_count,
            "coverage_complete": self.coverage_complete,
            "shortfall_count": self.shortfall_count,
            "max_event_time": (
                None if self.max_event_time is None else self.max_event_time.to_canonical_dict()
            ),
            "max_available_instant": (
                None
                if self.max_available_instant is None
                else self.max_available_instant.to_canonical_dict()
            ),
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "result_hash": self.result_hash}


class NamedBarWindowView:
    __slots__ = ("_backing_result", "_query", "_view_hash")

    def __init__(
        self,
        *,
        query: NamedBarWindowQuery,
        backing_result: PointInTimeObservationQueryResult,
    ) -> None:
        if type(query) is not NamedBarWindowQuery:
            raise TypeError("query must be NamedBarWindowQuery")
        if type(backing_result) is not PointInTimeObservationQueryResult:
            raise TypeError("backing_result must be PointInTimeObservationQueryResult")
        if backing_result.query != query.observation_query:
            raise ValueError("backing result Query must match named window")
        if backing_result.decision_instant != query.decision_instant:
            raise ValueError("backing result Decision Instant must match named window")
        if any(event.event_type != "bar" for event in backing_result.events):
            raise ValueError("backing result must contain only bar Events")
        body = {
            "type": "named_bar_window_view",
            "schema_version": _SCHEMA_VERSION,
            "query": query.to_canonical_dict(),
            "backing_result": backing_result.to_canonical_dict(),
        }
        self._query = query
        self._backing_result = backing_result
        self._view_hash = canonical_sha256(body)

    @property
    def view_hash(self) -> str:
        return self._view_hash

    def window(self) -> NamedBarWindowResult:
        eligible = tuple(
            event
            for event in self._backing_result.events
            if self._query.end_at_or_before is None
            or event.event_time <= self._query.end_at_or_before
        )
        events = eligible[-self._query.lookback_count :]
        return NamedBarWindowResult(
            query=self._query,
            events=events,
            causality_trace=self._backing_result.trace,
            available_count=len(eligible),
            requested_count=self._query.lookback_count,
            coverage_complete=len(eligible) >= self._query.lookback_count,
            shortfall_count=max(self._query.lookback_count - len(eligible), 0),
            max_event_time=max((event.event_time for event in events), default=None),
            max_available_instant=max(
                (event.timeline_instant for event in events), default=None
            ),
            decision_grade_eligible=False,
            deployment_authorized=False,
        )
