from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_sha256
from crypto_quant_trading import AccountingJournal

from ._fixtures import journal_entry


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/immutable-journal-replay-v1.json"


def test_immutable_journal_replay_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen journal fixture: {error}")
    journal = AccountingJournal.from_entries(
        (
            journal_entry("3", recorded_nanoseconds=30),
            journal_entry("1", recorded_nanoseconds=10),
            journal_entry("2", recorded_nanoseconds=20),
        )
    )

    actual = {
        "fixture_id": "immutable-journal-replay-v1",
        "genesis_hash": AccountingJournal.empty().journal_hash,
        "ordered_entry_ids": [
            str(entry.journal_entry_id) for entry in journal.entries
        ],
        "entry_hashes": list(journal.entry_hashes),
        "cursor_prefix_hashes": [
            journal.cursor_at(position).prefix_hash
            for position in range(journal.entry_count + 1)
        ],
        "journal_hash": journal.journal_hash,
        "full_replay_hash": canonical_sha256(journal.replay()),
        "middle_replay_hash": canonical_sha256(
            journal.replay(start=journal.cursor_at(1), stop=journal.cursor_at(2))
        ),
    }

    assert actual == expected
