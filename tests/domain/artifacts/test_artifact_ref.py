from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid fixture: {path}") from error
    if not isinstance(decoded, dict):
        raise AssertionError(f"fixture must be object: {path}")
    return decoded


def test_artifact_ref_wire_format_is_exact() -> None:
    fixture = load_fixture(Path("tests/fixtures/domain/artifact-ref-v1.json"))

    value = ArtifactRef(
        artifact_type=fixture["artifact_type"],
        schema_version=fixture["schema_version"],
        content_hash=fixture["content_hash"],
    )

    assert value.to_canonical_dict() == {
        "type": "artifact_ref",
        "artifact_type": fixture["artifact_type"],
        "schema_version": fixture["schema_version"],
        "content_hash": fixture["content_hash"],
    }
    assert canonical_bytes(value) == fixture["expected_canonical_utf8"].encode()
    assert canonical_sha256(value) == fixture["expected_canonical_sha256"]


def test_artifact_ref_rejects_type_schema_and_hash_forgery() -> None:
    class Text(str):
        pass

    with pytest.raises(TypeError, match="artifact_type"):
        ArtifactRef(True, 1, "sha256:" + "0" * 64)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="schema_version"):
        ArtifactRef("engine_execution_result", True, "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="at least 1"):
        ArtifactRef("engine_execution_result", 0, "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="sha256"):
        ArtifactRef("engine_execution_result", 1, "sha256:" + "Z" * 64)
    with pytest.raises(ValueError, match="sha256"):
        ArtifactRef("engine_execution_result", 1, Text("sha256:" + "0" * 64))


def test_artifact_ref_reconstructs_from_exact_envelope_and_is_frozen() -> None:
    class EnvelopeSubclass(ArtifactEnvelope):
        pass

    envelope = ArtifactEnvelope.create(
        "engine_execution_result", 1, {"status": "ok", "details": [1, 2, 3]}
    )
    value = ArtifactRef.from_envelope(envelope)

    assert value == ArtifactRef(
        artifact_type=envelope.artifact_type,
        schema_version=envelope.schema_version,
        content_hash=envelope.content_hash,
    )
    with pytest.raises(TypeError, match="ArtifactEnvelope"):
        ArtifactRef.from_envelope({})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ArtifactEnvelope"):
        ArtifactRef.from_envelope(
            EnvelopeSubclass(
                envelope.artifact_type,
                envelope.schema_version,
                envelope.payload,
                envelope.content_hash,
            )
        )
    with pytest.raises(FrozenInstanceError):
        value.artifact_type = "other"  # type: ignore[misc]
    assert not hasattr(value, "__dict__")


def test_artifact_envelope_catalog_v1_bytes_remain_bit_for_bit_unchanged() -> None:
    fixture = load_fixture(
        Path("tests/fixtures/domain/artifact-envelope-catalog-v1.json")
    )
    envelope = ArtifactEnvelope.create(
        fixture["artifact_type"], fixture["schema_version"], fixture["payload"]
    )

    assert envelope.content_hash == fixture["expected_content_hash"]
    assert canonical_bytes(envelope) == fixture["expected_source_utf8"].encode()
    assert canonical_sha256(envelope) == fixture["expected_source_hash"]
