from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_bundle_builder import normalize_synthetic_jsonl_v1
from crypto_quant_domain import canonical_bytes

from tests.bundle_builder.normalization._fixtures import JSONL, config, snapshot


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests/fixtures/market_data/normalization"
JSONL_FIXTURE = FIXTURES / "synthetic-jsonl-v1.jsonl"
EXPECTED = FIXTURES / "synthetic-jsonl-v1.expected.json"


def _payload() -> dict[str, object]:
    result = normalize_synthetic_jsonl_v1(snapshot(JSONL), config()).result
    assert result is not None
    repeated = normalize_synthetic_jsonl_v1(snapshot(JSONL), config()).result
    empty = normalize_synthetic_jsonl_v1(snapshot(b""), config()).result
    assert repeated is not None and empty is not None
    return {
        "schema_version": 1,
        "fixture_id": "synthetic-jsonl-v1",
        "result": result.to_canonical_dict(),
        "lookups": {
            "line_2_event_id": result.events[1].event_id,
            "line_2_trace_hash": result.traces[1].event_hash,
            "missing_event": result.trace_for_event("missing") is None,
        },
        "empty_member": empty.to_canonical_dict(),
        "repeat_parity": {
            "config_hash_matches": result.config.config_hash
            == repeated.config.config_hash,
            "normalization_hash_matches": result.normalization_hash
            == repeated.normalization_hash,
            "event_hashes_match": [event.event_hash for event in result.events]
            == [event.event_hash for event in repeated.events],
        },
        "limitations": [
            "synthetic-only-source-grammar",
            "physical-line-order-not-certified-stream-order",
            "revision-fields-preserved-not-chain-validated",
            "no-rule-corporate-action-or-bar-semantics",
            "no-manifest-coverage-publication-reader-or-provider-acquisition",
            "no-decision-grade-or-deployment-authorization",
        ],
    }


def test_synthetic_jsonl_matches_static_golden() -> None:
    try:
        raw = JSONL_FIXTURE.read_bytes()
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G12B golden fixture: {error}") from error
    assert raw == JSONL
    assert json.loads(canonical_bytes(_payload())) == expected
