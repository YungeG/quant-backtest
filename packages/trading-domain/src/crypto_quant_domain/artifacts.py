from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .canonical import CanonicalSchema, canonical_bytes, canonical_sha256

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ENVELOPE_FIELDS = frozenset(
    {"artifact_type", "schema_version", "payload", "content_hash"}
)


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_type: str
    schema_version: int
    content_hash: str

    def __post_init__(self) -> None:
        if type(self.artifact_type) is not str:
            raise TypeError("artifact_type must be str")
        if type(self.schema_version) is not int:
            raise TypeError("schema_version must be int")
        CanonicalSchema(self.artifact_type, self.schema_version)
        if type(self.content_hash) is not str or _SHA256.fullmatch(
            self.content_hash
        ) is None:
            raise ValueError("content hash must be sha256:<64 lowercase hex>")

    @classmethod
    def from_envelope(cls, envelope: ArtifactEnvelope) -> ArtifactRef:
        if type(envelope) is not ArtifactEnvelope:
            raise TypeError("envelope must be ArtifactEnvelope")
        return cls(
            artifact_type=envelope.artifact_type,
            schema_version=envelope.schema_version,
            content_hash=envelope.content_hash,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "artifact_ref",
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "content_hash": self.content_hash,
        }


class ArtifactCatalogError(ValueError):
    pass


class UnknownArtifactTypeError(ArtifactCatalogError):
    pass


class UnsupportedSchemaVersionError(ArtifactCatalogError):
    pass


class ArtifactIntegrityError(ArtifactCatalogError):
    pass


class ArtifactDecodeError(ArtifactCatalogError):
    pass


def _source_hash(source_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(source_bytes).hexdigest()}"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _canonical_payload(value: Any) -> Any:
    encoded = canonical_bytes(value)
    try:
        decoded = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:  # pragma: no cover
        raise ArtifactIntegrityError("canonical payload could not be decoded") from error
    return _freeze(decoded)


def _artifact_body(
    artifact_type: str, schema_version: int, payload: Any
) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "schema_version": schema_version,
        "payload": payload,
    }


@dataclass(frozen=True, slots=True)
class ArtifactEnvelope:
    artifact_type: str
    schema_version: int
    payload: Any
    content_hash: str

    def __post_init__(self) -> None:
        CanonicalSchema(self.artifact_type, self.schema_version)
        if not isinstance(self.content_hash, str) or _SHA256.fullmatch(
            self.content_hash
        ) is None:
            raise ValueError("content hash must be sha256:<64 lowercase hex>")
        canonical_payload = _canonical_payload(self.payload)
        object.__setattr__(self, "payload", canonical_payload)
        expected = canonical_sha256(
            _artifact_body(
                self.artifact_type, self.schema_version, canonical_payload
            )
        )
        if self.content_hash != expected:
            raise ValueError("content hash does not match artifact body")

    @classmethod
    def create(
        cls, artifact_type: str, schema_version: int, payload: Any
    ) -> ArtifactEnvelope:
        canonical_payload = _canonical_payload(payload)
        return cls(
            artifact_type=artifact_type,
            schema_version=schema_version,
            payload=canonical_payload,
            content_hash=canonical_sha256(
                _artifact_body(artifact_type, schema_version, canonical_payload)
            ),
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "payload": self.payload,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class ArtifactSchemaRegistration:
    artifact_type: str
    schema_version: int
    payload_reader: Callable[[Any], Any]

    def __post_init__(self) -> None:
        CanonicalSchema(self.artifact_type, self.schema_version)
        if not callable(self.payload_reader):
            raise TypeError("payload_reader must be callable")


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    envelope: ArtifactEnvelope
    source_bytes: bytes
    source_hash: str

    def __post_init__(self) -> None:
        _validate_source_result(self.envelope, self.source_bytes, self.source_hash)


@dataclass(frozen=True, slots=True)
class ArtifactReadResult:
    envelope: ArtifactEnvelope
    artifact: Any
    source_bytes: bytes
    source_hash: str

    def __post_init__(self) -> None:
        _validate_source_result(self.envelope, self.source_bytes, self.source_hash)


def _validate_source_result(
    envelope: ArtifactEnvelope, source_bytes: bytes, source_hash: str
) -> None:
    if not isinstance(envelope, ArtifactEnvelope):
        raise TypeError("envelope must be ArtifactEnvelope")
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if source_bytes != canonical_bytes(envelope):
        raise ValueError("source_bytes must be the canonical envelope bytes")
    if not isinstance(source_hash, str) or _SHA256.fullmatch(source_hash) is None:
        raise ValueError("source hash must be sha256:<64 lowercase hex>")
    if source_hash != _source_hash(source_bytes):
        raise ValueError("source hash does not match source bytes")


@dataclass(frozen=True, slots=True, init=False)
class SchemaCatalog:
    registrations: tuple[ArtifactSchemaRegistration, ...]

    def __init__(
        self, registrations: Iterable[ArtifactSchemaRegistration]
    ) -> None:
        by_schema: dict[tuple[str, int], ArtifactSchemaRegistration] = {}
        for registration in registrations:
            if not isinstance(registration, ArtifactSchemaRegistration):
                raise TypeError("registrations must contain ArtifactSchemaRegistration")
            key = (registration.artifact_type, registration.schema_version)
            if key in by_schema:
                raise ValueError(
                    "duplicate artifact type/version registration: "
                    f"{registration.artifact_type}@{registration.schema_version}"
                )
            by_schema[key] = registration
        object.__setattr__(
            self,
            "registrations",
            tuple(by_schema[key] for key in sorted(by_schema)),
        )

    def write_current(self, artifact_type: str, artifact: Any) -> ArtifactWriteResult:
        return self._write(self._registration(artifact_type), artifact)

    @staticmethod
    def _write(
        registration: ArtifactSchemaRegistration, artifact: Any
    ) -> ArtifactWriteResult:
        envelope = ArtifactEnvelope.create(
            registration.artifact_type,
            registration.schema_version,
            artifact,
        )
        source_bytes = canonical_bytes(envelope)
        return ArtifactWriteResult(
            envelope=envelope,
            source_bytes=source_bytes,
            source_hash=_source_hash(source_bytes),
        )

    def read(self, source_bytes: bytes) -> ArtifactReadResult:
        if not isinstance(source_bytes, bytes):
            raise TypeError("source_bytes must be bytes")
        decoded = _decode_source(source_bytes)
        envelope = _read_envelope(decoded)
        if source_bytes != canonical_bytes(envelope):
            raise ArtifactIntegrityError("artifact must use canonical source bytes")
        registration = self._registration(
            envelope.artifact_type, envelope.schema_version
        )
        try:
            artifact = registration.payload_reader(envelope.payload)
        except Exception as error:
            raise ArtifactDecodeError(
                f"payload reader failed for {envelope.artifact_type} "
                f"version {envelope.schema_version}"
            ) from error
        return ArtifactReadResult(
            envelope=envelope,
            artifact=artifact,
            source_bytes=source_bytes,
            source_hash=_source_hash(source_bytes),
        )

    def _registration(
        self, artifact_type: str, schema_version: int | None = None
    ) -> ArtifactSchemaRegistration:
        matches = tuple(
            registration
            for registration in self.registrations
            if registration.artifact_type == artifact_type
        )
        if not matches:
            raise UnknownArtifactTypeError(f"unknown artifact type: {artifact_type}")
        if schema_version is None:
            return max(matches, key=lambda registration: registration.schema_version)
        for registration in matches:
            if registration.schema_version == schema_version:
                return registration
        current = max(matches, key=lambda registration: registration.schema_version)
        raise UnsupportedSchemaVersionError(
            f"unsupported {artifact_type} schema version {schema_version}; "
            f"current version is {current.schema_version}"
        )


def _decode_source(source_bytes: bytes) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ArtifactIntegrityError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_float(value: str) -> Any:
        raise ArtifactIntegrityError(f"non-integer JSON number is forbidden: {value}")

    def reject_constant(value: str) -> Any:
        raise ArtifactIntegrityError(f"non-finite JSON number is forbidden: {value}")

    try:
        text = source_bytes.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except ArtifactIntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ArtifactDecodeError("artifact source is not valid canonical JSON") from error


def _read_envelope(decoded: Any) -> ArtifactEnvelope:
    if not isinstance(decoded, Mapping) or set(decoded) != _ENVELOPE_FIELDS:
        raise ArtifactIntegrityError(
            "artifact envelope must contain exactly artifact_type, schema_version, "
            "payload, and content_hash"
        )
    try:
        return ArtifactEnvelope(
            artifact_type=decoded["artifact_type"],
            schema_version=decoded["schema_version"],
            payload=decoded["payload"],
            content_hash=decoded["content_hash"],
        )
    except (TypeError, ValueError) as error:
        raise ArtifactIntegrityError(f"invalid artifact envelope: {error}") from error
