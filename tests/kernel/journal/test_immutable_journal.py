from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import Money, canonical_sha256
from crypto_quant_trading import (
    AccountingJournal,
    JournalCursorError,
    JournalEntryConflictError,
    JournalOrderingError,
    JournalReplayCursor,
)

from ._fixtures import journal_entry


def reducer_hash(entries: tuple[object, ...]) -> str:
    return canonical_sha256(
        {"type": "journal_test_reducer", "entries": [canonical_sha256(e) for e in entries]}
    )


def test_empty_journal_has_fixed_genesis_cursor_and_is_immutable() -> None:
    journal = AccountingJournal.empty()

    assert not journal.entries
    assert journal.entry_count == 0
    assert journal.cursor_at(0) == JournalReplayCursor(0, journal.journal_hash)
    assert AccountingJournal.empty().journal_hash == journal.journal_hash

    with pytest.raises(FrozenInstanceError):
        cast(Any, journal).entries = ()


def test_unordered_batch_has_stable_recorded_time_and_identity_order() -> None:
    entries = (
        journal_entry("3", recorded_nanoseconds=30),
        journal_entry("1", recorded_nanoseconds=10),
        journal_entry("2", recorded_nanoseconds=20),
    )

    forward = AccountingJournal.from_entries(entries)
    reverse = AccountingJournal.from_entries(tuple(reversed(entries)))
    unordered = AccountingJournal.from_entries(set(entries))

    expected_ids = tuple(f"jnl_{digit * 64}" for digit in ("1", "2", "3"))
    assert tuple(str(entry.journal_entry_id) for entry in forward.entries) == expected_ids
    assert reverse.entries == forward.entries
    assert unordered.entries == forward.entries
    assert reverse.journal_hash == forward.journal_hash
    assert unordered.journal_hash == forward.journal_hash


def test_identical_entry_is_idempotent_and_conflicting_identity_fails() -> None:
    entry = journal_entry("1", recorded_nanoseconds=10)
    journal = AccountingJournal.empty().append(entry)

    assert journal.append(entry) is journal
    duplicate_entries = (entry, entry)
    assert journal.append_many(duplicate_entries) is journal

    amount = cast(Money, entry.balance_changes[0].value)
    conflict = replace(
        entry,
        balance_changes=(
            replace(entry.balance_changes[0], value=replace(amount, units=amount.units + 1)),
        ),
    )
    with pytest.raises(JournalEntryConflictError, match=str(entry.journal_entry_id)):
        journal.append(conflict)


def test_append_rejects_non_entry_and_late_insertion() -> None:
    later = journal_entry("2", recorded_nanoseconds=20)
    journal = AccountingJournal.empty().append(later)

    with pytest.raises(TypeError, match="AccountingJournalEntry"):
        cast(Any, journal).append("not-an-entry")
    with pytest.raises(JournalOrderingError, match="published prefix"):
        journal.append(journal_entry("1", recorded_nanoseconds=10))


def test_replay_cursor_supports_exact_prefix_resume_parity() -> None:
    journal = AccountingJournal.from_entries(
        tuple(
            journal_entry(str(index), recorded_nanoseconds=index * 10)
            for index in range(1, 4)
        )
    )
    middle = journal.cursor_at(1)
    first = journal.replay(stop=middle)
    remaining = journal.replay(start=middle)
    full = journal.replay()

    combined_entries = first.entries + remaining.entries
    assert combined_entries == full.entries
    assert full.entries == journal.entries
    assert first.start_cursor == journal.cursor_at(0)
    assert first.end_cursor == remaining.start_cursor == middle
    assert remaining.end_cursor == full.end_cursor == journal.cursor_at(3)
    assert reducer_hash(first.entries + remaining.entries) == reducer_hash(full.entries)


def test_replay_rejects_forged_or_reversed_cursors() -> None:
    journal = AccountingJournal.from_entries(
        (
            journal_entry("1", recorded_nanoseconds=10),
            journal_entry("2", recorded_nanoseconds=20),
        )
    )

    with pytest.raises(JournalCursorError, match="position"):
        journal.replay(start=JournalReplayCursor(3, journal.journal_hash))
    with pytest.raises(JournalCursorError, match="prefix hash"):
        journal.replay(start=JournalReplayCursor(1, "sha256:" + "0" * 64))
    with pytest.raises(JournalCursorError, match="start.*stop"):
        journal.replay(start=journal.cursor_at(2), stop=journal.cursor_at(1))


def test_same_recorded_time_uses_journal_identity_as_tie_breaker() -> None:
    high = journal_entry("2", recorded_nanoseconds=10, source_sequence=1)
    low = journal_entry("1", recorded_nanoseconds=10, source_sequence=1)

    journal = AccountingJournal.from_entries((high, low))
    expected_entries = (low, high)
    assert journal.entries == expected_entries
