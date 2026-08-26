from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    ArtifactDecodeError,
    ArtifactEnvelope,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactReadResult,
    ArtifactRef,
    ArtifactRetentionUnavailableError,
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .target_stream import PrecomputedTargetStream

_ARTIFACT_TYPE = "backtest_target_stream"
_SCHEMA_VERSION = 1
_PAYLOAD_FIELDS = frozenset({"producer_context_ref", "target_stream"})
_STREAM_FIELDS = frozenset({"type", "schema_version", "stream_key", "events"})
_EVENT_FIELDS = frozenset(
    {
        "type",
        "event_id",
        "stream_key",
        "event_type",
        "capability",
        "instrument_id",
        "event_time",
        "available_time",
        "phase",
        "source_sequence",
        "revision_id",
        "supersedes_revision_id",
        "source_key",
        "source_hash",
        "payload",
    }
)


class BacktestTargetStreamFailureCode(str, Enum):
    REF_TYPE_MISMATCH = "ref_type_mismatch"
    NOT_FOUND = "not_found"
    TAMPERED = "tampered"
    RETENTION_UNAVAILABLE = "retention_unavailable"
    CONTEXT_MISMATCH = "context_mismatch"
    DIGEST_MISMATCH = "digest_mismatch"


class BacktestTargetStreamError(Exception):
    def __init__(self, code: BacktestTargetStreamFailureCode) -> None:
        if type(code) is not BacktestTargetStreamFailureCode:
            raise TypeError("code must be exact BacktestTargetStreamFailureCode")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class BacktestTargetStreamRef:
    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.artifact_ref) is not ArtifactRef:
            raise TypeError("artifact_ref must be exact ArtifactRef")
        rebuilt = ArtifactRef(
            self.artifact_ref.artifact_type,
            self.artifact_ref.schema_version,
            self.artifact_ref.content_hash,
        )
        if (
            rebuilt != self.artifact_ref
            or rebuilt.artifact_type != _ARTIFACT_TYPE
            or rebuilt.schema_version != _SCHEMA_VERSION
        ):
            raise ValueError("artifact_ref must reference backtest_target_stream@1")

    @classmethod
    def from_artifact_ref(cls, artifact_ref: ArtifactRef) -> BacktestTargetStreamRef:
        return cls(artifact_ref)

    def to_artifact_ref(self) -> ArtifactRef:
        return self.artifact_ref

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_target_stream_ref",
            "artifact_ref": self.artifact_ref,
        }


@dataclass(frozen=True, slots=True)
class VerifiedBacktestTargetStream:
    ref: BacktestTargetStreamRef
    producer_context_ref: ArtifactRef
    target_stream: PrecomputedTargetStream
    digest: str

    def __post_init__(self) -> None:
        if type(self.ref) is not BacktestTargetStreamRef:
            raise TypeError("ref must be exact BacktestTargetStreamRef")
        if type(self.producer_context_ref) is not ArtifactRef:
            raise TypeError("producer_context_ref must be exact ArtifactRef")
        if type(self.target_stream) is not PrecomputedTargetStream:
            raise TypeError("target_stream must be exact PrecomputedTargetStream")
        if self.digest != self.target_stream.target_stream_digest:
            raise ValueError("digest does not bind target_stream")
        envelope = ArtifactEnvelope.create(
            _ARTIFACT_TYPE,
            _SCHEMA_VERSION,
            {
                "producer_context_ref": self.producer_context_ref,
                "target_stream": self.target_stream,
            },
        )
        if self.ref.artifact_ref != ArtifactRef.from_envelope(envelope):
            raise ValueError("ref does not bind producer context and target stream")


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(type(key) is str for key in value):
        raise TypeError(f"{name} must be a string-keyed mapping")
    return value


def _exact(name: str, value: Mapping[str, Any], fields: frozenset[str]) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} fields do not match the canonical schema")


def _artifact_ref(value: object) -> ArtifactRef:
    data = _mapping("producer_context_ref", value)
    _exact(
        "producer_context_ref",
        data,
        frozenset(
            {"type", "artifact_type", "schema_version", "content_hash"}
        ),
    )
    if data["type"] != "artifact_ref":
        raise ValueError("producer_context_ref must be ArtifactRef")
    return ArtifactRef(
        data["artifact_type"], data["schema_version"], data["content_hash"]
    )


def _instant(value: object) -> UtcInstant:
    data = _mapping("utc_instant", value)
    _exact("utc_instant", data, frozenset({"type", "epoch_nanoseconds"}))
    if data["type"] != "utc_instant":
        raise ValueError("invalid UtcInstant type")
    return UtcInstant(data["epoch_nanoseconds"])


def _instrument(value: object) -> InstrumentId | None:
    if value is None:
        return None
    data = _mapping("instrument_id", value)
    _exact("instrument_id", data, frozenset({"type", "venue", "stable_key"}))
    if data["type"] != "instrument_id":
        raise ValueError("invalid InstrumentId type")
    venue = data["venue"]
    if isinstance(venue, Mapping):
        venue_data = _mapping("venue", venue)
        if venue_data.get("type") != "venue_id" or set(venue_data) != {"type", "value"}:
            raise ValueError("invalid VenueId")
        venue = venue_data["value"]
    return InstrumentId(VenueId(venue), data["stable_key"])


def _event(value: object) -> MarketEvent:
    data = _mapping("target event", value)
    _exact("target event", data, _EVENT_FIELDS)
    if data["type"] != "market_event":
        raise ValueError("target event must be MarketEvent")
    capability = _mapping("capability", data["capability"])
    if set(capability) != {"type", "key", "version"} or capability["type"] != "market_bundle_capability":
        raise ValueError("invalid target event capability")
    phase = _mapping("phase", data["phase"])
    if set(phase) != {"type", "rank", "code"} or phase["type"] != "timeline_phase":
        raise ValueError("invalid target event phase")
    sequence = _mapping("source_sequence", data["source_sequence"])
    if set(sequence) != {"type", "value"} or sequence["type"] != "source_sequence":
        raise ValueError("invalid target event source sequence")
    return MarketEvent(
        event_id=data["event_id"],
        stream_key=data["stream_key"],
        event_type=data["event_type"],
        capability=MarketBundleCapability(capability["key"], capability["version"]),
        instrument_id=_instrument(data["instrument_id"]),
        event_time=_instant(data["event_time"]),
        available_time=_instant(data["available_time"]),
        phase=TimelinePhase(phase["rank"], phase["code"]),
        source_sequence=SourceSequence(sequence["value"]),
        revision_id=data["revision_id"],
        supersedes_revision_id=data["supersedes_revision_id"],
        source_key=data["source_key"],
        source_hash=data["source_hash"],
        payload=_mapping("target event payload", data["payload"]),
    )


def _read_precomputed_target_stream(value: object) -> PrecomputedTargetStream:
    data = _mapping("target_stream", value)
    _exact("target_stream", data, _STREAM_FIELDS)
    if data["type"] != "precomputed_target_stream" or data["schema_version"] != 1:
        raise ValueError("target_stream must be precomputed_target_stream@1")
    events = data["events"]
    if not isinstance(events, (tuple, list)):
        raise TypeError("target_stream.events must be a sequence")
    stream = PrecomputedTargetStream(data["stream_key"], tuple(_event(item) for item in events))
    if canonical_bytes(stream) != canonical_bytes(data):
        raise ValueError("target_stream did not reconstruct exactly")
    return stream


class BacktestTargetStreamRepository:
    def __init__(
        self,
        *,
        reader: ArtifactEnvelopeReader,
        publisher: ArtifactEnvelopePublisher | None = None,
    ) -> None:
        if not callable(getattr(reader, "read", None)):
            raise TypeError("reader must provide read")
        if publisher is not None and not callable(getattr(publisher, "put", None)):
            raise TypeError("publisher must provide put")
        self._reader = reader
        self._publisher = publisher

    def publish(
        self,
        producer_context_ref: ArtifactRef,
        target_stream: PrecomputedTargetStream,
    ) -> BacktestTargetStreamRef:
        if type(producer_context_ref) is not ArtifactRef:
            raise TypeError("producer_context_ref must be exact ArtifactRef")
        if type(target_stream) is not PrecomputedTargetStream:
            raise TypeError("target_stream must be exact PrecomputedTargetStream")
        if self._publisher is None:
            raise RuntimeError("target stream publisher is unavailable")
        envelope = ArtifactEnvelope.create(
            _ARTIFACT_TYPE,
            _SCHEMA_VERSION,
            {
                "producer_context_ref": producer_context_ref,
                "target_stream": target_stream,
            },
        )
        expected = ArtifactRef.from_envelope(envelope)
        try:
            actual = self._publisher.put(envelope=envelope)
        except Exception as error:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.RETENTION_UNAVAILABLE
            ) from error
        if type(actual) is not ArtifactRef or actual != expected:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.CONTEXT_MISMATCH
            )
        return BacktestTargetStreamRef(actual)

    def load(self, ref: BacktestTargetStreamRef) -> VerifiedBacktestTargetStream:
        if type(ref) is not BacktestTargetStreamRef:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.REF_TYPE_MISMATCH
            )
        try:
            artifact_ref = BacktestTargetStreamRef(
                ArtifactRef(
                    ref.artifact_ref.artifact_type,
                    ref.artifact_ref.schema_version,
                    ref.artifact_ref.content_hash,
                )
            ).artifact_ref
        except Exception as error:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.REF_TYPE_MISMATCH
            ) from error
        try:
            result = self._reader.read(ref=artifact_ref)
        except ArtifactNotFoundError as error:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.NOT_FOUND
            ) from error
        except ArtifactRetentionUnavailableError as error:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.RETENTION_UNAVAILABLE
            ) from error
        except (ArtifactIntegrityError, ArtifactDecodeError) as error:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.TAMPERED
            ) from error
        except Exception as error:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.RETENTION_UNAVAILABLE
            ) from error
        if type(result) is not ArtifactReadResult:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.TAMPERED
            )
        try:
            if (
                result.envelope.artifact_type != _ARTIFACT_TYPE
                or result.envelope.schema_version != _SCHEMA_VERSION
                or ArtifactRef.from_envelope(result.envelope) != artifact_ref
                or result.source_bytes != canonical_bytes(result.envelope)
                or result.source_hash != canonical_sha256(result.envelope)
            ):
                raise ValueError("artifact identity mismatch")
            payload = _mapping("backtest_target_stream payload", result.envelope.payload)
            _exact("backtest_target_stream payload", payload, _PAYLOAD_FIELDS)
            producer_context_ref = _artifact_ref(payload["producer_context_ref"])
            target_stream_digest = canonical_sha256(payload["target_stream"])
            target_stream = _read_precomputed_target_stream(payload["target_stream"])
        except Exception as error:
            raise BacktestTargetStreamError(
                BacktestTargetStreamFailureCode.TAMPERED
            ) from error
        try:
            return VerifiedBacktestTargetStream(
                ref, producer_context_ref, target_stream, target_stream_digest
            )
        except ValueError as error:
            code = (
                BacktestTargetStreamFailureCode.DIGEST_MISMATCH
                if "digest" in str(error)
                else BacktestTargetStreamFailureCode.CONTEXT_MISMATCH
            )
            raise BacktestTargetStreamError(code) from error
