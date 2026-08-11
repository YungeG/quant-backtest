from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import InstrumentId, canonical_sha256
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
