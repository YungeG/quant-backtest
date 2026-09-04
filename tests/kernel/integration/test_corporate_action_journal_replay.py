from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    Money,
    PositionLotChange,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
)
from crypto_quant_trading import (
    AccountingJournal,
    GenericLedger,
    JournalEntryConflictError,
    LedgerBalanceRegistration,
    LedgerFinancialInvariantError,
    LedgerSchema,
)
from crypto_quant_trading.profiles.cn_a_share import (
    translate_corporate_action_cash_payment,
    translate_corporate_action_share_delivery,
)
from tests.kernel.profiles.cn_a_share._corporate_action_accounting_fixtures import (
    CNY_SCALE,
    SHARE_SCALE,
    cash_request,
    journal_id,
    share_request,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/integration/corporate-action-journal-replay-v1.json"


def _entries() -> tuple[AccountingJournalEntry, AccountingJournalEntry, AccountingJournalEntry]:
    share = share_request()
    cash = cash_request()
    lot = share.open_lots[0]
    opening = AccountingJournalEntry(
        journal_entry_id=journal_id("6"),
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id=share.entitlement.account_id,
        venue_id=share.entitlement.position_key.venue_id,
        effective_time=lot.opened_at,
        recorded_at=SimulationInstant(
            lot.opened_at,
            TimelinePhase(40, "accounting"),
            SourceSequence(0),
        ),
        source_ids=(lot.source_id,),
        balance_changes=(BalanceChange(lot.position_key, lot.quantity),),
        realized_pnl=(),
        fees=(),
        financing=(),
        position_lot_changes=(PositionLotChange(None, lot),),
    )
    share_outcome = translate_corporate_action_share_delivery(share)
    cash_outcome = translate_corporate_action_cash_payment(cash)
    assert share_outcome.failure is cash_outcome.failure is None
    assert share_outcome.journal_entry is not None
    assert cash_outcome.journal_entry is not None
    return opening, share_outcome.journal_entry, cash_outcome.journal_entry


def _schema() -> LedgerSchema:
    share = share_request()
    cash = cash_request()
    return LedgerSchema(
        (
            LedgerBalanceRegistration(cash.cash_key, CNY_SCALE),
            LedgerBalanceRegistration(share.entitlement.position_key, SHARE_SCALE),
        )
    )


def test_full_prefix_resume_journal_and_ledger_replay_are_exact() -> None:
    opening, share_entry, cash_entry = _entries()
    journal = AccountingJournal.from_entries((opening, share_entry, cash_entry))
    assert tuple(str(entry.journal_entry_id) for entry in journal.entries) == (
        "jnl_" + "6" * 64,
        "jnl_" + "7" * 64,
        "jnl_" + "8" * 64,
    )

    prefix_cursor = journal.cursor_at(2)
    prefix_replay = journal.replay(stop=prefix_cursor)
    resumed_replay = journal.replay(start=prefix_cursor)
    assert prefix_replay.entries + resumed_replay.entries == journal.replay().entries

    ledger = GenericLedger(_schema())
    full = ledger.project(journal)
    prefix = ledger.project(journal, stop=prefix_cursor)
    resumed = ledger.resume(journal, prefix)
    assert resumed == full
    assert resumed.state_hash == full.state_hash

    share = share_request()
    cash = cash_request()
    position = full.position_balances[0]
    assert position.quantity == Quantity(
        710, Scale(0), str(share.entitlement.position_key.instrument_id)
    )
    assert len(position.lots) == 1
    assert position.lots[0].total_cost_basis == Money(750_000, CNY_SCALE, "CNY")
    assert full.cash_amount(cash.cash_key) == Money(7_000, CNY_SCALE, "CNY")


def test_duplicate_and_conflict_ownership_remains_in_journal_and_ledger() -> None:
    opening, share_entry, cash_entry = _entries()
    journal = AccountingJournal.from_entries((opening, share_entry, cash_entry))
    assert journal.append(cash_entry) is journal

    cash_change = cash_entry.balance_changes[0]
    assert isinstance(cash_change.value, Money)
    conflict = replace(
        cash_entry,
        balance_changes=(
            replace(cash_change, value=replace(cash_change.value, units=cash_change.value.units + 1)),
        ),
    )
    with pytest.raises(JournalEntryConflictError, match=str(cash_entry.journal_entry_id)):
        journal.append(conflict)

    lot_change = share_entry.position_lot_changes[0]
    assert lot_change.before is not None
    stale_before = replace(
        lot_change.before,
        quantity=replace(lot_change.before.quantity, units=499),
    )
    stale_share = replace(
        share_entry,
        position_lot_changes=(replace(lot_change, before=stale_before),),
    )
    stale_journal = AccountingJournal.from_entries((opening, stale_share, cash_entry))
    with pytest.raises(LedgerFinancialInvariantError, match="before mismatch"):
        GenericLedger(_schema()).project(stale_journal)


def test_replay_static_fixture_freezes_ids_controls_and_false_qualification_flags() -> None:
    fixture = json.loads(FIXTURE.read_bytes())
    assert fixture == {
        "fixture_id": "cn-a-share-corporate-action-journal-replay-v1",
        "qualification": {
            "allowed_grade": "development",
            "decision_grade_eligible": False,
            "profile_qualified": False,
            "deployment_authorized": False,
        },
        "replay_controls": {
            "journal_ids": [
                "jnl_" + "6" * 64,
                "jnl_" + "7" * 64,
                "jnl_" + "8" * 64,
            ],
            "full_prefix_resume_replay": True,
            "duplicate_idempotency": True,
            "conflict_rejection": True,
        },
    }
