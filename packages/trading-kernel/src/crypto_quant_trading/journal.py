"""Immutable accounting journal ordering, identity, and replay."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from crypto_quant_domain import AccountingJournalEntry, SimulationInstant, canonical_sha256


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_GENESIS_HASH = canonical_sha256(
    {"type": "accounting_journal_genesis", "schema_version": 1}
)


class JournalError(Exception):
    """Base class for deterministic journal contract failures."""


class JournalEntryConflictError(JournalError):
    """Raised when one journal entry identity names different content."""

    def __init__(
        self,
        journal_entry_id: str,
        existing_entry_hash: str,
        conflicting_entry_hash: str,
    ) -> None:
        self.journal_entry_id = journal_entry_id
        self.existing_entry_hash = existing_entry_hash
        self.conflicting_entry_hash = conflicting_entry_hash
        super().__init__(f"conflicting content for journal entry {journal_entry_id}")


class JournalOrderingError(JournalError):
    """Raised when an append would rewrite an already-published prefix."""


class JournalCursorError(JournalError):
    """Raised when a replay cursor does not identify a valid prefix."""


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 digest")


def _entry_hash(entry: AccountingJournalEntry) -> str:
    return canonical_sha256(entry)


def _order_key(entry: AccountingJournalEntry) -> tuple[SimulationInstant, str]:
    return entry.recorded_at, entry.journal_entry_id.value


def _next_prefix_hash(previous_hash: str, entry_hash: str) -> str:
    return canonical_sha256(
        {
            "type": "accounting_journal_link",
            "schema_version": 1,
            "previous_hash": previous_hash,
            "entry_hash": entry_hash,
        }
    )


@dataclass(frozen=True, slots=True)
class JournalReplayCursor:
    """A verified position in one immutable journal prefix."""

    position: int
    prefix_hash: str

    def __post_init__(self) -> None:
        if isinstance(self.position, bool) or not isinstance(self.position, int):
            raise TypeError("JournalReplayCursor position must be an integer")
        if self.position < 0:
            raise ValueError("JournalReplayCursor position must be non-negative")
        _require_hash("JournalReplayCursor prefix_hash", self.prefix_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "journal_replay_cursor",
            "position": self.position,
            "prefix_hash": self.prefix_hash,
        }


@dataclass(frozen=True, slots=True)
class JournalReplay:
    """An immutable half-open replay slice and its verified boundaries."""

    start_cursor: JournalReplayCursor
    end_cursor: JournalReplayCursor
    entries: tuple[AccountingJournalEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.start_cursor, JournalReplayCursor):
            raise TypeError("start_cursor must be JournalReplayCursor")
        if not isinstance(self.end_cursor, JournalReplayCursor):
            raise TypeError("end_cursor must be JournalReplayCursor")
        if not isinstance(self.entries, tuple) or not all(
            isinstance(entry, AccountingJournalEntry) for entry in self.entries
        ):
            raise TypeError("entries must be a tuple of AccountingJournalEntry")
        if self.end_cursor.position - self.start_cursor.position != len(self.entries):
            raise ValueError("JournalReplay cursor range must match entry count")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "journal_replay",
            "start_cursor": self.start_cursor,
            "end_cursor": self.end_cursor,
            "entries": self.entries,
        }


@dataclass(frozen=True, slots=True)
class AccountingJournal:
    """An immutable append-only sequence of accounting facts."""

    entries: tuple[AccountingJournalEntry, ...] = ()
    _entry_hashes: tuple[str, ...] = field(init=False, repr=False)
    _prefix_hashes: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple) or not all(
            isinstance(entry, AccountingJournalEntry) for entry in self.entries
        ):
            raise TypeError("entries must be a tuple of AccountingJournalEntry")

        entry_hashes: list[str] = []
        prefix_hashes = [_GENESIS_HASH]
        seen_ids: dict[str, str] = {}
        previous_key: tuple[SimulationInstant, str] | None = None

        for entry in self.entries:
            key = _order_key(entry)
            if previous_key is not None and key <= previous_key:
                raise JournalOrderingError(
                    "AccountingJournal entries must use strict stable order"
                )
            previous_key = key

            entry_id = entry.journal_entry_id.value
            content_hash = _entry_hash(entry)
            existing_hash = seen_ids.get(entry_id)
            if existing_hash is not None:
                if existing_hash != content_hash:
                    raise JournalEntryConflictError(
                        entry_id, existing_hash, content_hash
                    )
                raise JournalOrderingError(
                    "AccountingJournal cannot contain duplicate entry identities"
                )
            seen_ids[entry_id] = content_hash
            entry_hashes.append(content_hash)
            prefix_hashes.append(_next_prefix_hash(prefix_hashes[-1], content_hash))

        object.__setattr__(self, "_entry_hashes", tuple(entry_hashes))
        object.__setattr__(self, "_prefix_hashes", tuple(prefix_hashes))

    @classmethod
    def empty(cls) -> AccountingJournal:
        return cls()

    @classmethod
    def from_entries(
        cls, entries: Iterable[AccountingJournalEntry]
    ) -> AccountingJournal:
        return cls.empty().append_many(entries)

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def entry_hashes(self) -> tuple[str, ...]:
        return self._entry_hashes

    @property
    def journal_hash(self) -> str:
        return self._prefix_hashes[-1]

    def append(self, entry: AccountingJournalEntry) -> AccountingJournal:
        if not isinstance(entry, AccountingJournalEntry):
            raise TypeError("entry must be AccountingJournalEntry")
        return self.append_many((entry,))

    def append_many(
        self, entries: Iterable[AccountingJournalEntry]
    ) -> AccountingJournal:
        try:
            candidates = tuple(entries)
        except TypeError as error:
            raise TypeError("entries must be an iterable of AccountingJournalEntry") from error
        if not all(isinstance(entry, AccountingJournalEntry) for entry in candidates):
            raise TypeError("entries must contain only AccountingJournalEntry")
        if not candidates:
            return self

        existing = {
            entry.journal_entry_id.value: content_hash
            for entry, content_hash in zip(
                self.entries, self._entry_hashes, strict=True
            )
        }
        pending: dict[str, tuple[str, AccountingJournalEntry]] = {}
        for entry in candidates:
            entry_id = entry.journal_entry_id.value
            content_hash = _entry_hash(entry)
            known_hash = existing.get(entry_id)
            if known_hash is not None:
                if known_hash != content_hash:
                    raise JournalEntryConflictError(
                        entry_id, known_hash, content_hash
                    )
                continue
            pending_value = pending.get(entry_id)
            if pending_value is not None:
                if pending_value[0] != content_hash:
                    raise JournalEntryConflictError(
                        entry_id, pending_value[0], content_hash
                    )
                continue
            pending[entry_id] = content_hash, entry

        if not pending:
            return self

        ordered = tuple(sorted((value[1] for value in pending.values()), key=_order_key))
        if self.entries and _order_key(ordered[0]) <= _order_key(self.entries[-1]):
            raise JournalOrderingError(
                "append would insert before the published prefix boundary"
            )
        return AccountingJournal(self.entries + ordered)

    def cursor_at(self, position: int) -> JournalReplayCursor:
        if isinstance(position, bool) or not isinstance(position, int):
            raise TypeError("cursor position must be an integer")
        if not 0 <= position <= self.entry_count:
            raise JournalCursorError(
                f"cursor position {position} is outside journal range"
            )
        return JournalReplayCursor(position, self._prefix_hashes[position])

    def _validate_cursor(self, cursor: JournalReplayCursor) -> None:
        if not isinstance(cursor, JournalReplayCursor):
            raise TypeError("replay cursor must be JournalReplayCursor")
        if cursor.position > self.entry_count:
            raise JournalCursorError(
                f"cursor position {cursor.position} is outside journal range"
            )
        expected_hash = self._prefix_hashes[cursor.position]
        if cursor.prefix_hash != expected_hash:
            raise JournalCursorError(
                f"cursor prefix hash does not match position {cursor.position}"
            )

    def replay(
        self,
        *,
        start: JournalReplayCursor | None = None,
        stop: JournalReplayCursor | None = None,
    ) -> JournalReplay:
        start_cursor = self.cursor_at(0) if start is None else start
        stop_cursor = self.cursor_at(self.entry_count) if stop is None else stop
        self._validate_cursor(start_cursor)
        self._validate_cursor(stop_cursor)
        if start_cursor.position > stop_cursor.position:
            raise JournalCursorError("replay start cursor cannot be after stop cursor")
        return JournalReplay(
            start_cursor=start_cursor,
            end_cursor=stop_cursor,
            entries=self.entries[start_cursor.position : stop_cursor.position],
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "accounting_journal",
            "schema_version": 1,
            "entries": self.entries,
            "journal_hash": self.journal_hash,
        }
