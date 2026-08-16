from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from crypto_quant_domain import (
    ArtifactCatalogError,
    ArtifactDecodeError,
    ArtifactEnvelope,
    ArtifactIntegrityError,
    ArtifactSchemaRegistration,
    SchemaCatalog,
    UnknownArtifactTypeError,
    UnsupportedSchemaVersionError,
    canonical_bytes,
    canonical_sha256,
)

ARTIFACT_TYPE = "example.position-snapshot"


@dataclass(frozen=True, slots=True)
class ExampleArtifact:
    identifier: str
    count: int

    def to_canonical_dict(self) -> dict[str, object]:
        return {"identifier": self.identifier, "count": self.count}


def read_example(payload: Any) -> ExampleArtifact:
    if not isinstance(payload, Mapping) or set(payload) != {"identifier", "count"}:
        raise ValueError("invalid example payload")
    identifier = payload["identifier"]
    count = payload["count"]
    if not isinstance(identifier, str) or isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("invalid example payload values")
    return ExampleArtifact(identifier=identifier, count=count)


def catalog() -> SchemaCatalog:
    return SchemaCatalog(
        (
            ArtifactSchemaRegistration(
                artifact_type=ARTIFACT_TYPE,
                schema_version=1,
                payload_reader=read_example,
            ),
        )
    )


def source_hash(source_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(source_bytes).hexdigest()}"


def decode_json_object(source_bytes: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(source_bytes)
    except json.JSONDecodeError as error:
        raise AssertionError("writer output must be valid JSON") from error
    if not isinstance(decoded, dict):
        raise AssertionError("writer output must be a JSON object")
    return decoded


def test_current_writer_produces_a_verified_canonical_envelope() -> None:
    value = ExampleArtifact(identifier="alpha", count=7)

    result = catalog().write_current(ARTIFACT_TYPE, value)

    assert result.envelope.artifact_type == ARTIFACT_TYPE
    assert result.envelope.schema_version == 1
    assert result.envelope.payload == {"identifier": "alpha", "count": 7}
    assert result.envelope.content_hash == canonical_sha256(
        {
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": 1,
            "payload": value,
        }
    )
    assert result.source_bytes == canonical_bytes(result.envelope)
    assert result.source_hash == source_hash(result.source_bytes)


def test_reader_dispatches_only_after_integrity_checks_and_preserves_source() -> None:
    written = catalog().write_current(
        ARTIFACT_TYPE, ExampleArtifact(identifier="alpha", count=7)
    )

    read = catalog().read(written.source_bytes)

    assert read.envelope.content_hash == written.envelope.content_hash
    assert read.artifact == ExampleArtifact(identifier="alpha", count=7)
    assert read.source_bytes == written.source_bytes
    assert read.source_hash == written.source_hash


def test_catalog_selects_highest_writer_and_reads_each_registered_version() -> None:
    def read_v2(payload: Any) -> tuple[int, ExampleArtifact]:
        return (2, read_example(payload))

    current = SchemaCatalog(
        (
            ArtifactSchemaRegistration(ARTIFACT_TYPE, 2, read_v2),
            ArtifactSchemaRegistration(ARTIFACT_TYPE, 1, read_example),
        )
    )
    value = ExampleArtifact(identifier="alpha", count=7)

    written = current.write_current(ARTIFACT_TYPE, value)
    old = ArtifactEnvelope.create(ARTIFACT_TYPE, 1, value)

    assert written.envelope.schema_version == 2
    assert current.read(written.source_bytes).artifact == (2, value)
    assert current.read(canonical_bytes(old)).artifact == value
    assert tuple(
        (registration.artifact_type, registration.schema_version)
        for registration in current.registrations
    ) == ((ARTIFACT_TYPE, 1), (ARTIFACT_TYPE, 2))


def test_catalog_and_envelope_reject_invalid_registration_or_identity() -> None:
    registration = ArtifactSchemaRegistration(ARTIFACT_TYPE, 1, read_example)

    with pytest.raises(ValueError, match="canonical lowercase"):
        ArtifactSchemaRegistration("Example", 1, read_example)
    with pytest.raises(ValueError, match="at least 1"):
        ArtifactSchemaRegistration(ARTIFACT_TYPE, 0, read_example)
    with pytest.raises(TypeError, match="payload_reader must be callable"):
        ArtifactSchemaRegistration(ARTIFACT_TYPE, 1, None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="duplicate artifact type"):
        SchemaCatalog((registration, registration))
    with pytest.raises(ValueError, match="content hash"):
        ArtifactEnvelope(ARTIFACT_TYPE, 1, {"value": 1}, "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="sha256"):
        ArtifactEnvelope(ARTIFACT_TYPE, 1, {"value": 1}, "not-a-hash")


def test_unknown_type_and_noncurrent_version_fail_closed() -> None:
    current = catalog()
    unknown = ArtifactEnvelope.create("example.unknown", 1, {"value": 1})
    future = ArtifactEnvelope.create(ARTIFACT_TYPE, 2, {"identifier": "alpha", "count": 7})

    with pytest.raises(UnknownArtifactTypeError, match="example.unknown"):
        current.write_current("example.unknown", {"value": 1})
    with pytest.raises(UnknownArtifactTypeError, match="example.unknown"):
        current.read(canonical_bytes(unknown))
    with pytest.raises(UnsupportedSchemaVersionError, match="version 2"):
        current.read(canonical_bytes(future))
    with pytest.raises(TypeError):
        current.write_current(ARTIFACT_TYPE, {"value": 1}, schema_version=2)  # type: ignore[call-arg]


def test_reader_rejects_malformed_duplicate_or_noncanonical_json() -> None:
    written = catalog().write_current(
        ARTIFACT_TYPE, ExampleArtifact(identifier="alpha", count=7)
    )
    decoded = decode_json_object(written.source_bytes)
    duplicate = (
        b'{"artifact_type":"example.position-snapshot",'
        b'"artifact_type":"example.position-snapshot",'
        b'"content_hash":"sha256:' + b"0" * 64 + b'","payload":{},"schema_version":1}'
    )

    with pytest.raises(ArtifactDecodeError, match="JSON"):
        catalog().read(b"not json")
    with pytest.raises(ArtifactIntegrityError, match="duplicate JSON key"):
        catalog().read(duplicate)
    with pytest.raises(ArtifactIntegrityError, match="canonical source bytes"):
        catalog().read(json.dumps(decoded, indent=2, ensure_ascii=False).encode())


def test_reader_rejects_content_tampering_before_payload_dispatch() -> None:
    written = catalog().write_current(
        ARTIFACT_TYPE, ExampleArtifact(identifier="alpha", count=7)
    )
    decoded = decode_json_object(written.source_bytes)
    payload = decoded["payload"]
    assert isinstance(payload, dict)
    payload["count"] = 8
    tampered = json.dumps(
        decoded,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    with pytest.raises(ArtifactIntegrityError, match="content hash"):
        catalog().read(tampered)


def test_payload_reader_failure_is_wrapped_without_fallback() -> None:
    envelope = ArtifactEnvelope.create(ARTIFACT_TYPE, 1, {"unexpected": True})

    with pytest.raises(ArtifactDecodeError, match="payload reader failed") as raised:
        catalog().read(canonical_bytes(envelope))

    assert isinstance(raised.value.__cause__, ValueError)
    assert isinstance(raised.value, ArtifactCatalogError)
