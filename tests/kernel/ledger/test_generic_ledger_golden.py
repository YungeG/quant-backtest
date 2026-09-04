from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading import GenericLedger

from .test_generic_ledger import fixture_journal, schema


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures/kernel/generic-ledger-projection-v1.json"
)


def test_generic_ledger_projection_matches_golden_fixture() -> None:
    journal = fixture_journal()
    ledger = GenericLedger(schema(reverse=True))
    prefix = ledger.project(journal, stop=journal.cursor_at(3))
    final = ledger.resume(journal, prefix)
    actual = {
        "fixture_id": "generic-ledger-projection-v1",
        "schema_hash": ledger.schema.schema_hash,
        "prefix_state_hash": prefix.state_hash,
        "final_state_hash": final.state_hash,
        "final_state": json.loads(canonical_bytes(final)),
    }

    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid generic ledger golden fixture: {error}")
    assert actual == expected
