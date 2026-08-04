from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crypto_quant_domain import ArtifactSchemaRegistration, SchemaCatalog


FIXTURE = Path("tests/fixtures/domain/artifact-envelope-catalog-v1.json")


@dataclass(frozen=True, slots=True)
class ExampleArtifact:
    identifier: str
    count: int

    def to_canonical_dict(self) -> dict[str, object]:
        return {"identifier": self.identifier, "count": self.count}


def read_example(payload: Any) -> ExampleArtifact:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    return ExampleArtifact(identifier=payload["identifier"], count=payload["count"])


def load_fixture() -> dict[str, Any]:
    try:
        decoded = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError("golden fixture must be valid JSON") from error
    if not isinstance(decoded, dict):
        raise AssertionError("golden fixture must be a JSON object")
    return decoded


def test_current_artifact_envelope_matches_the_independent_golden_fixture() -> None:
    fixture = load_fixture()
    catalog = SchemaCatalog(
        (
            ArtifactSchemaRegistration(
                fixture["artifact_type"], fixture["schema_version"], read_example
            ),
        )
    )
    value = ExampleArtifact(**fixture["payload"])

    written = catalog.write_current(fixture["artifact_type"], value)
    read = catalog.read(written.source_bytes)

    assert written.envelope.content_hash == fixture["expected_content_hash"]
    assert written.source_bytes == fixture["expected_source_utf8"].encode("utf-8")
    assert written.source_hash == fixture["expected_source_hash"]
    assert read.artifact == value
    assert read.source_bytes == written.source_bytes
    assert read.source_hash == written.source_hash
