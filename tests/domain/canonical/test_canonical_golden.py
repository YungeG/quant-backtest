from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import (
    CanonicalEnvelope,
    CanonicalSchema,
    canonical_bytes,
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/canonical-envelope-v1.json"


def test_canonical_envelope_matches_controlled_bytes_and_hash() -> None:
    fixture = cast(
        dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    envelope = CanonicalEnvelope(
        schema=CanonicalSchema(
            fixture["schema_name"], fixture["envelope_schema_version"]
        ),
        payload=fixture["payload"],
    )

    assert canonical_bytes(envelope) == fixture["expected_utf8"].encode("utf-8")
    assert canonical_sha256(envelope) == fixture["expected_sha256"]
