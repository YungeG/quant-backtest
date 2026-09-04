from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from crypto_quant_domain import (
    InstrumentId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class MarketBundleError(ValueError):
    """Base error for invalid market-bundle read evidence."""


class MarketBundleIntegrityError(MarketBundleError):
    """The bundle content does not match its immutable manifest."""


class MarketBundleStreamError(MarketBundleError):
    """A cursor or stream operation violates the read contract."""


def _canonical_text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise MarketBundleIntegrityError(f"{name} must be text")
    if not value or value != value.strip() or unicodedata.normalize("NFC", value) != value:
        raise MarketBundleIntegrityError(f"{name} must be nonempty canonical NFC text")
    return value


def _content_hash(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise MarketBundleIntegrityError(f"{name} must be a canonical sha256 digest")
    return value


def _freeze_payload(value: object, path: str = "payload") -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise MarketBundleIntegrityError(f"{path} text must be NFC normalized")
        return value
    if isinstance(value, Mapping):
        keys = tuple(value)
        if any(not isinstance(key, str) for key in keys):
            raise MarketBundleIntegrityError(f"{path} keys must be text")
        frozen: dict[str, object] = {}
        for key in sorted(keys):
            if unicodedata.normalize("NFC", key) != key:
                raise MarketBundleIntegrityError(f"{path} keys must be NFC normalized")
            frozen[key] = _freeze_payload(value[key], f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_payload(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise MarketBundleIntegrityError(f"{path} must contain canonical data only")


@dataclass(frozen=True, slots=True, order=True)
class MarketBundleCapability:
    key: str
    version: int

    def __post_init__(self) -> None:
        _canonical_text("capability key", self.key)
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise MarketBundleIntegrityError("capability version must be an integer")
        if self.version <= 0:
            raise MarketBundleIntegrityError("capability version must be positive")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_bundle_capability",
            "key": self.key,
            "version": self.version,
        }

    @property
    def identity(self) -> str:
        return f"{self.key}@{self.version}"


@dataclass(frozen=True, slots=True)
class MarketEvent:
    event_id: str
    stream_key: str
    event_type: str
    capability: MarketBundleCapability
    instrument_id: InstrumentId | None
    event_time: UtcInstant
    available_time: UtcInstant
    phase: TimelinePhase
    source_sequence: SourceSequence
    revision_id: str
    supersedes_revision_id: str | None
    source_key: str
    source_hash: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        _canonical_text("event_id", self.event_id)
        _canonical_text("stream_key", self.stream_key)
        _canonical_text("event_type", self.event_type)
        if not isinstance(self.capability, MarketBundleCapability):
            raise MarketBundleIntegrityError("capability must be MarketBundleCapability")
        if self.instrument_id is not None and not isinstance(
            self.instrument_id, InstrumentId
        ):
            raise MarketBundleIntegrityError("instrument_id must be InstrumentId or None")
        if not isinstance(self.event_time, UtcInstant) or not isinstance(
            self.available_time, UtcInstant
        ):
            raise MarketBundleIntegrityError("event and available time must be UtcInstant")
        if self.available_time.epoch_nanoseconds < self.event_time.epoch_nanoseconds:
            raise MarketBundleIntegrityError("available_time cannot precede event_time")
        if not isinstance(self.phase, TimelinePhase):
            raise MarketBundleIntegrityError("phase must be TimelinePhase")
        if not isinstance(self.source_sequence, SourceSequence):
            raise MarketBundleIntegrityError("source_sequence must be SourceSequence")
        _canonical_text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _canonical_text("supersedes_revision_id", self.supersedes_revision_id)
            if self.supersedes_revision_id == self.revision_id:
                raise MarketBundleIntegrityError("a revision cannot supersede itself")
        _canonical_text("source_key", self.source_key)
        _content_hash("source_hash", self.source_hash)
        if not isinstance(self.payload, Mapping):
            raise MarketBundleIntegrityError("payload must be a mapping")
        try:
            frozen_payload = _freeze_payload(self.payload)
            canonical_bytes(frozen_payload)
        except MarketBundleIntegrityError:
            raise
        except (TypeError, ValueError) as error:
            raise MarketBundleIntegrityError(
                "payload must contain canonical data only"
            ) from error
        object.__setattr__(self, "payload", frozen_payload)

    @property
    def timeline_instant(self) -> SimulationInstant:
        return SimulationInstant(
            instant=self.available_time,
            phase=self.phase,
            source_sequence=self.source_sequence,
        )

    @property
    def ordering_key(self) -> tuple[int, int, str, int]:
        return (
            self.available_time.epoch_nanoseconds,
            self.phase.rank,
            self.phase.code,
            self.source_sequence.value,
        )

    @property
    def event_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_event",
            "event_id": self.event_id,
            "stream_key": self.stream_key,
            "event_type": self.event_type,
            "capability": self.capability.to_canonical_dict(),
            "instrument_id": (
                None
                if self.instrument_id is None
                else self.instrument_id.to_canonical_dict()
            ),
            "event_time": self.event_time.to_canonical_dict(),
            "available_time": self.available_time.to_canonical_dict(),
            "phase": self.phase.to_canonical_dict(),
            "source_sequence": self.source_sequence.to_canonical_dict(),
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class MarketStreamManifest:
    stream_key: str
    event_type: str
    capability: MarketBundleCapability
    event_count: int
    content_hash: str

    def __post_init__(self) -> None:
        _canonical_text("stream_key", self.stream_key)
        _canonical_text("event_type", self.event_type)
        if not isinstance(self.capability, MarketBundleCapability):
            raise MarketBundleIntegrityError("stream capability is invalid")
        if isinstance(self.event_count, bool) or not isinstance(self.event_count, int):
            raise MarketBundleIntegrityError("event_count must be an integer")
        if self.event_count < 0:
            raise MarketBundleIntegrityError("event_count must be non-negative")
        _content_hash("stream content_hash", self.content_hash)

    @classmethod
    def from_events(
        cls, stream_key: str, events: tuple[MarketEvent, ...]
    ) -> MarketStreamManifest:
        if not events:
            raise MarketBundleIntegrityError("a declared stream must contain events")
        event_types = {event.event_type for event in events}
        capabilities = {event.capability for event in events}
        if len(event_types) != 1 or len(capabilities) != 1:
            raise MarketBundleIntegrityError(
                "a stream must have one event type and capability"
            )
        return cls(
            stream_key=stream_key,
            event_type=next(iter(event_types)),
            capability=next(iter(capabilities)),
            event_count=len(events),
            content_hash=canonical_sha256(events),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_stream_manifest",
            "stream_key": self.stream_key,
            "event_type": self.event_type,
            "capability": self.capability.to_canonical_dict(),
            "event_count": self.event_count,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class MarketBundleManifest:
    bundle_key: str
    schema_version: int
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    instrument_catalog_hash: str
    capabilities: tuple[MarketBundleCapability, ...]
    streams: tuple[MarketStreamManifest, ...]
    content_hash: str

    def __post_init__(self) -> None:
        _canonical_text("bundle_key", self.bundle_key)
        if isinstance(self.schema_version, bool) or not isinstance(
            self.schema_version, int
        ):
            raise MarketBundleIntegrityError("schema_version must be an integer")
        if self.schema_version <= 0:
            raise MarketBundleIntegrityError("schema_version must be positive")
        if not isinstance(self.coverage_start, UtcInstant) or not isinstance(
            self.coverage_end_exclusive, UtcInstant
        ):
            raise MarketBundleIntegrityError("coverage bounds must be UtcInstant")
        if (
            self.coverage_end_exclusive.epoch_nanoseconds
            <= self.coverage_start.epoch_nanoseconds
        ):
            raise MarketBundleIntegrityError("coverage must be a nonempty half-open range")
        _content_hash("instrument_catalog_hash", self.instrument_catalog_hash)
        capabilities = tuple(sorted(self.capabilities))
        if len(set(capabilities)) != len(capabilities):
            raise MarketBundleIntegrityError("capabilities must be unique")
        streams = tuple(sorted(self.streams, key=lambda stream: stream.stream_key))
        if len({stream.stream_key for stream in streams}) != len(streams):
            raise MarketBundleIntegrityError("stream keys must be unique")
        declared = set(capabilities)
        if any(stream.capability not in declared for stream in streams):
            raise MarketBundleIntegrityError("stream capability must be declared")
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "streams", streams)
        _content_hash("manifest content_hash", self.content_hash)
        if self.content_hash != canonical_sha256(self._body()):
            raise MarketBundleIntegrityError("manifest content hash does not match body")

    @classmethod
    def build(
        cls,
        *,
        bundle_key: str,
        schema_version: int,
        coverage_start: UtcInstant,
        coverage_end_exclusive: UtcInstant,
        instrument_catalog_hash: str,
        capabilities: Iterable[MarketBundleCapability],
        streams: Iterable[MarketStreamManifest],
    ) -> MarketBundleManifest:
        capability_tuple = tuple(sorted(capabilities))
        stream_tuple = tuple(sorted(streams, key=lambda stream: stream.stream_key))
        body = cls._canonical_body(
            bundle_key=bundle_key,
            schema_version=schema_version,
            coverage_start=coverage_start,
            coverage_end_exclusive=coverage_end_exclusive,
            instrument_catalog_hash=instrument_catalog_hash,
            capabilities=capability_tuple,
            streams=stream_tuple,
        )
        return cls(
            bundle_key=bundle_key,
            schema_version=schema_version,
            coverage_start=coverage_start,
            coverage_end_exclusive=coverage_end_exclusive,
            instrument_catalog_hash=instrument_catalog_hash,
            capabilities=capability_tuple,
            streams=stream_tuple,
            content_hash=canonical_sha256(body),
        )

    @staticmethod
    def _canonical_body(
        *,
        bundle_key: str,
        schema_version: int,
        coverage_start: UtcInstant,
        coverage_end_exclusive: UtcInstant,
        instrument_catalog_hash: str,
        capabilities: tuple[MarketBundleCapability, ...],
        streams: tuple[MarketStreamManifest, ...],
    ) -> dict[str, object]:
        return {
            "type": "market_bundle_manifest_body",
            "bundle_key": bundle_key,
            "schema_version": schema_version,
            "coverage_start": coverage_start.to_canonical_dict(),
            "coverage_end_exclusive": coverage_end_exclusive.to_canonical_dict(),
            "instrument_catalog_hash": instrument_catalog_hash,
            "capabilities": tuple(item.to_canonical_dict() for item in capabilities),
            "streams": tuple(item.to_canonical_dict() for item in streams),
        }

    def _body(self) -> dict[str, object]:
        return self._canonical_body(
            bundle_key=self.bundle_key,
            schema_version=self.schema_version,
            coverage_start=self.coverage_start,
            coverage_end_exclusive=self.coverage_end_exclusive,
            instrument_catalog_hash=self.instrument_catalog_hash,
            capabilities=self.capabilities,
            streams=self.streams,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            **self._body(),
            "type": "market_bundle_manifest",
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class MarketBundleRef:
    bundle_key: str
    manifest_hash: str

    def __post_init__(self) -> None:
        _canonical_text("bundle_key", self.bundle_key)
        _content_hash("manifest_hash", self.manifest_hash)

    @classmethod
    def from_manifest(cls, manifest: MarketBundleManifest) -> MarketBundleRef:
        return cls(
            bundle_key=manifest.bundle_key,
            manifest_hash=canonical_sha256(manifest),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_bundle_ref",
            "bundle_key": self.bundle_key,
            "manifest_hash": self.manifest_hash,
        }


class InputValidationIssueCode(str, Enum):
    MISSING_REQUIRED_CAPABILITY = "missing_required_capability"
    UNKNOWN_STREAM = "unknown_stream"


@dataclass(frozen=True, slots=True)
class InputValidationIssue:
    code: InputValidationIssueCode
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, InputValidationIssueCode):
            raise MarketBundleIntegrityError("input validation code is invalid")
        _canonical_text("input validation subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "input_validation_issue",
            "code": self.code.value,
            "subject_key": self.subject_key,
        }


@dataclass(frozen=True, slots=True)
class InputValidationFailure:
    bundle_ref: MarketBundleRef
    issues: tuple[InputValidationIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_ref, MarketBundleRef):
            raise MarketBundleIntegrityError("bundle_ref is invalid")
        issues = tuple(
            sorted(self.issues, key=lambda issue: (issue.code.value, issue.subject_key))
        )
        if not issues or len(set(issues)) != len(issues):
            raise MarketBundleIntegrityError(
                "input validation issues must be nonempty and unique"
            )
        object.__setattr__(self, "issues", issues)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_bundle_input_validation_failure",
            "bundle_ref": self.bundle_ref.to_canonical_dict(),
            "issues": tuple(issue.to_canonical_dict() for issue in self.issues),
        }


@dataclass(frozen=True, slots=True)
class EventCursor:
    bundle_ref: MarketBundleRef
    stream_manifest: MarketStreamManifest
    position: int
    batch_size: int

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_ref, MarketBundleRef):
            raise MarketBundleStreamError("cursor bundle_ref is invalid")
        if not isinstance(self.stream_manifest, MarketStreamManifest):
            raise MarketBundleStreamError("cursor stream manifest is invalid")
        if isinstance(self.position, bool) or not isinstance(self.position, int):
            raise MarketBundleStreamError("cursor position must be an integer")
        if self.position < 0 or self.position > self.stream_manifest.event_count:
            raise MarketBundleStreamError("cursor position is out of range")
        if isinstance(self.batch_size, bool) or not isinstance(self.batch_size, int):
            raise MarketBundleStreamError("cursor batch_size must be an integer")
        if self.batch_size <= 0:
            raise MarketBundleStreamError("cursor batch_size must be positive")

    @property
    def exhausted(self) -> bool:
        return self.position == self.stream_manifest.event_count

    @property
    def cursor_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "event_cursor",
            "bundle_ref": self.bundle_ref.to_canonical_dict(),
            "stream_key": self.stream_manifest.stream_key,
            "stream_content_hash": self.stream_manifest.content_hash,
            "position": self.position,
            "batch_size": self.batch_size,
        }


@runtime_checkable
class MarketBundleReader(Protocol):
    @property
    def bundle_ref(self) -> MarketBundleRef: ...

    @property
    def manifest(self) -> MarketBundleManifest: ...

    def validate_requirements(
        self,
        *,
        required_capabilities: Iterable[MarketBundleCapability] = (),
        required_streams: Iterable[str] = (),
    ) -> InputValidationFailure | None: ...

    def open_cursor(
        self, stream_key: str, *, batch_size: int
    ) -> EventCursor | InputValidationFailure: ...

    def read_batch(
        self, cursor: EventCursor
    ) -> tuple[tuple[MarketEvent, ...], EventCursor]: ...

    def resume_cursor(
        self, cursor: EventCursor, *, batch_size: int | None = None
    ) -> EventCursor: ...


@dataclass(frozen=True, slots=True)
class InMemoryMarketBundleReader:
    bundle_ref: MarketBundleRef
    manifest: MarketBundleManifest
    streams: Mapping[str, tuple[MarketEvent, ...]]

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_ref, MarketBundleRef):
            raise MarketBundleIntegrityError("bundle_ref is invalid")
        if not isinstance(self.manifest, MarketBundleManifest):
            raise MarketBundleIntegrityError("manifest is invalid")
        if self.bundle_ref.bundle_key != self.manifest.bundle_key:
            raise MarketBundleIntegrityError("bundle reference key does not match manifest")
        if self.bundle_ref.manifest_hash != canonical_sha256(self.manifest):
            raise MarketBundleIntegrityError("bundle reference manifest hash does not match")
        if not isinstance(self.streams, Mapping):
            raise MarketBundleIntegrityError("streams must be a mapping")

        normalized: dict[str, tuple[MarketEvent, ...]] = {}
        event_ids: set[str] = set()
        for stream_key in sorted(self.streams):
            _canonical_text("stream key", stream_key)
            events = tuple(sorted(tuple(self.streams[stream_key]), key=lambda event: event.ordering_key))
            ordering_keys: set[tuple[int, int, str, int]] = set()
            for event in events:
                if not isinstance(event, MarketEvent):
                    raise MarketBundleIntegrityError("stream contains a non-MarketEvent")
                if event.stream_key != stream_key:
                    raise MarketBundleIntegrityError("event stream identity does not match")
                if event.event_id in event_ids:
                    raise MarketBundleIntegrityError("event IDs must be unique in a bundle")
                if event.ordering_key in ordering_keys:
                    raise MarketBundleIntegrityError(
                        "stream ordering key must be unique"
                    )
                if not (
                    self.manifest.coverage_start.epoch_nanoseconds
                    <= event.event_time.epoch_nanoseconds
                    < self.manifest.coverage_end_exclusive.epoch_nanoseconds
                ):
                    raise MarketBundleIntegrityError(
                        "event time lies outside manifest coverage"
                    )
                event_ids.add(event.event_id)
                ordering_keys.add(event.ordering_key)
            normalized[stream_key] = events

        manifests = {stream.stream_key: stream for stream in self.manifest.streams}
        if set(normalized) != set(manifests):
            raise MarketBundleIntegrityError("manifest stream set does not match content")
        for stream_key, events in normalized.items():
            stream_manifest = manifests[stream_key]
            if len(events) != stream_manifest.event_count:
                raise MarketBundleIntegrityError("manifest stream event count does not match")
            if canonical_sha256(events) != stream_manifest.content_hash:
                raise MarketBundleIntegrityError("manifest stream content hash does not match")
            if any(
                event.event_type != stream_manifest.event_type
                or event.capability != stream_manifest.capability
                for event in events
            ):
                raise MarketBundleIntegrityError("manifest stream declaration does not match")
        object.__setattr__(self, "streams", MappingProxyType(normalized))

    @classmethod
    def build(
        cls,
        *,
        bundle_key: str,
        schema_version: int,
        coverage_start: UtcInstant,
        coverage_end_exclusive: UtcInstant,
        instrument_catalog_hash: str,
        capabilities: Iterable[MarketBundleCapability],
        streams: Mapping[str, Iterable[MarketEvent]],
    ) -> InMemoryMarketBundleReader:
        normalized = {
            stream_key: tuple(sorted(events, key=lambda event: event.ordering_key))
            for stream_key, events in streams.items()
        }
        stream_manifests = tuple(
            MarketStreamManifest.from_events(stream_key, events)
            for stream_key, events in normalized.items()
        )
        manifest = MarketBundleManifest.build(
            bundle_key=bundle_key,
            schema_version=schema_version,
            coverage_start=coverage_start,
            coverage_end_exclusive=coverage_end_exclusive,
            instrument_catalog_hash=instrument_catalog_hash,
            capabilities=capabilities,
            streams=stream_manifests,
        )
        return cls(
            bundle_ref=MarketBundleRef.from_manifest(manifest),
            manifest=manifest,
            streams=normalized,
        )

    def validate_requirements(
        self,
        *,
        required_capabilities: Iterable[MarketBundleCapability] = (),
        required_streams: Iterable[str] = (),
    ) -> InputValidationFailure | None:
        declared = set(self.manifest.capabilities)
        issues = [
            InputValidationIssue(
                code=InputValidationIssueCode.MISSING_REQUIRED_CAPABILITY,
                subject_key=capability.identity,
            )
            for capability in set(required_capabilities)
            if capability not in declared
        ]
        issues.extend(
            InputValidationIssue(
                code=InputValidationIssueCode.UNKNOWN_STREAM,
                subject_key=stream_key,
            )
            for stream_key in set(required_streams)
            if stream_key not in self.streams
        )
        if not issues:
            return None
        return InputValidationFailure(bundle_ref=self.bundle_ref, issues=tuple(issues))

    def open_cursor(
        self, stream_key: str, *, batch_size: int
    ) -> EventCursor | InputValidationFailure:
        _canonical_text("stream_key", stream_key)
        if stream_key not in self.streams:
            return InputValidationFailure(
                bundle_ref=self.bundle_ref,
                issues=(
                    InputValidationIssue(
                        code=InputValidationIssueCode.UNKNOWN_STREAM,
                        subject_key=stream_key,
                    ),
                ),
            )
        stream_manifest = next(
            stream for stream in self.manifest.streams if stream.stream_key == stream_key
        )
        return EventCursor(
            bundle_ref=self.bundle_ref,
            stream_manifest=stream_manifest,
            position=0,
            batch_size=batch_size,
        )

    def read_batch(
        self, cursor: EventCursor
    ) -> tuple[tuple[MarketEvent, ...], EventCursor]:
        verified = self.resume_cursor(cursor)
        events = self.streams[verified.stream_manifest.stream_key]
        stop = min(verified.position + verified.batch_size, len(events))
        batch = events[verified.position : stop]
        if stop == verified.position:
            return batch, verified
        return batch, EventCursor(
            bundle_ref=self.bundle_ref,
            stream_manifest=verified.stream_manifest,
            position=stop,
            batch_size=verified.batch_size,
        )

    def resume_cursor(
        self, cursor: EventCursor, *, batch_size: int | None = None
    ) -> EventCursor:
        if not isinstance(cursor, EventCursor):
            raise MarketBundleStreamError("resume cursor must be EventCursor")
        if cursor.bundle_ref != self.bundle_ref:
            raise MarketBundleStreamError("cursor belongs to another bundle")
        stream_key = cursor.stream_manifest.stream_key
        if stream_key not in self.streams:
            raise MarketBundleStreamError("cursor stream is not in this bundle")
        manifest = next(
            stream for stream in self.manifest.streams if stream.stream_key == stream_key
        )
        if cursor.stream_manifest != manifest:
            raise MarketBundleStreamError("cursor stream evidence does not match bundle")
        return EventCursor(
            bundle_ref=self.bundle_ref,
            stream_manifest=manifest,
            position=cursor.position,
            batch_size=cursor.batch_size if batch_size is None else batch_size,
        )
