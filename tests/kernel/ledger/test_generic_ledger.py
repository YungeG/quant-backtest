from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    InstrumentId,
    Money,
    PositionBalance,
    PositionBalanceKey,
    PositionLot,
    PositionLotChange,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import (
    AccountingJournal,
    GenericLedger,
    JournalReplayCursor,
    LedgerBalanceRegistration,
    LedgerFinancialInvariantError,
    LedgerSchema,
    LedgerStateMismatchError,
    UnregisteredBalanceKeyError,
)


VENUE = VenueId("synthetic")
ACCOUNT = "account:primary"
USD_KEY = CashBalanceKey(ACCOUNT, VENUE, CurrencyId("USD"))
STOCK = InstrumentId(VENUE, "stock-1")
STOCK_KEY = PositionBalanceKey(ACCOUNT, VENUE, STOCK)
USD_SCALE = Scale(2)
QUANTITY_SCALE = Scale(0)


def schema(*, reverse: bool = False) -> LedgerSchema:
    registrations = (
        LedgerBalanceRegistration(USD_KEY, USD_SCALE),
        LedgerBalanceRegistration(STOCK_KEY, QUANTITY_SCALE),
    )
    return LedgerSchema(tuple(reversed(registrations)) if reverse else registrations)


def entry(
    digit: str,
    *,
    recorded_nanoseconds: int,
    entry_type: AccountingEntryType,
    changes: tuple[BalanceChange, ...],
    realized_pnl: tuple[Money, ...] = (),
    fees: tuple[Money, ...] = (),
    financing: tuple[Money, ...] = (),
    position_lot_changes: tuple[PositionLotChange, ...] = (),
) -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=DomainId(DomainIdKind.JOURNAL, f"jnl_{digit * 64}"),
        entry_type=entry_type,
        account_id=ACCOUNT,
        venue_id=VENUE,
        effective_time=UtcInstant(recorded_nanoseconds - 1),
        recorded_at=SimulationInstant(
            UtcInstant(recorded_nanoseconds),
            TimelinePhase(40, "accounting"),
            SourceSequence(1),
        ),
        source_ids=(f"source:{digit}",),
        balance_changes=changes,
        realized_pnl=realized_pnl,
        fees=fees,
        financing=financing,
        position_lot_changes=position_lot_changes,
    )


def lot(
    lot_id: str,
    units: int,
    *,
    total_cost: int = 0,
) -> PositionLot:
    return PositionLot(
        lot_id=lot_id,
        position_key=STOCK_KEY,
        source_id="fill:1",
        quantity=Quantity(units, QUANTITY_SCALE, str(STOCK)),
        unit_cost=None,
        allocated_fees=(),
        opened_at=UtcInstant(5),
        total_cost_basis=Money(total_cost, USD_SCALE, "USD") if total_cost else None,
    )


def fixture_entries() -> tuple[AccountingJournalEntry, ...]:
    return (
        entry(
            "1",
            recorded_nanoseconds=10,
            entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
            changes=(BalanceChange(USD_KEY, Money(100_000, USD_SCALE, "USD")),),
        ),
        entry(
            "2",
            recorded_nanoseconds=20,
            entry_type=AccountingEntryType.FILL_BOOKED,
            changes=(
                BalanceChange(USD_KEY, Money(-30_000, USD_SCALE, "USD")),
                BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),
            ),
        ),
        entry(
            "3",
            recorded_nanoseconds=30,
            entry_type=AccountingEntryType.FEE_CHARGED,
            changes=(BalanceChange(USD_KEY, Money(-100, USD_SCALE, "USD")),),
            fees=(Money(100, USD_SCALE, "USD"),),
        ),
        entry(
            "4",
            recorded_nanoseconds=40,
            entry_type=AccountingEntryType.FILL_BOOKED,
            changes=(
                BalanceChange(USD_KEY, Money(18_000, USD_SCALE, "USD")),
                BalanceChange(STOCK_KEY, Quantity(-4, QUANTITY_SCALE, str(STOCK))),
            ),
            realized_pnl=(Money(6_000, USD_SCALE, "USD"),),
        ),
        entry(
            "5",
            recorded_nanoseconds=50,
            entry_type=AccountingEntryType.FUNDING_APPLIED,
            changes=(BalanceChange(USD_KEY, Money(-50, USD_SCALE, "USD")),),
            financing=(Money(50, USD_SCALE, "USD"),),
        ),
    )


def fixture_journal() -> AccountingJournal:
    return AccountingJournal.from_entries(fixture_entries())


def test_schema_registration_is_order_independent_and_immutable() -> None:
    forward = schema()
    reverse = schema(reverse=True)

    expected_keys = (USD_KEY, STOCK_KEY)
    assert forward == reverse
    assert forward.schema_hash == reverse.schema_hash
    assert tuple(registration.key for registration in forward.registrations) == expected_keys

    with pytest.raises(ValueError, match="duplicate"):
        LedgerSchema((forward.registrations[0], forward.registrations[0]))
    with pytest.raises(FrozenInstanceError):
        cast(Any, forward).registrations = ()


def test_full_projection_rebuilds_cash_position_and_native_attributions() -> None:
    journal = fixture_journal()
    state = GenericLedger(schema()).project(journal)

    assert state.cursor == journal.cursor_at(journal.entry_count)
    assert state.cash_amount(USD_KEY) == Money(87_850, USD_SCALE, "USD")
    assert state.position_quantity(STOCK_KEY) == Quantity(
        6, QUANTITY_SCALE, str(STOCK)
    )
    assert state.realized_pnl_amount(USD_KEY) == Money(6_000, USD_SCALE, "USD")
    assert state.fee_amount(USD_KEY) == Money(100, USD_SCALE, "USD")
    assert state.financing_amount(USD_KEY) == Money(50, USD_SCALE, "USD")
    assert not hasattr(state, "unrealized_pnl")


def test_lot_projection_supports_full_and_prefix_resume() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),),
        position_lot_changes=(PositionLotChange(None, lot("lot-1", 10)),),
    )
    adjust = entry(
        "2",
        recorded_nanoseconds=20,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(),
        position_lot_changes=(
            PositionLotChange(before=lot("lot-1", 10), after=lot("lot-1", 5)),
            PositionLotChange(before=None, after=lot("lot-2", 5)),
        ),
    )
    close_half = entry(
        "3",
        recorded_nanoseconds=30,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(-5, QUANTITY_SCALE, str(STOCK))),),
        position_lot_changes=(
            PositionLotChange(before=lot("lot-1", 5), after=None),
        ),
    )

    journal = AccountingJournal.from_entries((open_position, adjust, close_half))
    ledger = GenericLedger(schema())
    full = ledger.project(journal)
    prefix = ledger.project(journal, stop=journal.cursor_at(2))
    resumed = ledger.resume(journal, prefix)

    assert resumed == full
    assert resumed.state_hash == full.state_hash
    assert ledger.resume(journal, full) is full
    assert full.position_quantity(STOCK_KEY) == Quantity(5, QUANTITY_SCALE, str(STOCK))


def test_prefix_resume_has_exact_full_replay_parity_and_is_idempotent() -> None:
    journal = fixture_journal()
    ledger = GenericLedger(schema())
    full = ledger.project(journal)
    prefix = ledger.project(journal, stop=journal.cursor_at(3))
    resumed = ledger.resume(journal, prefix)

    assert resumed == full
    assert resumed.state_hash == full.state_hash
    assert ledger.resume(journal, full) is full
    assert ledger.project(journal).state_hash == full.state_hash


def test_unregistered_key_and_attribution_currency_fail_closed() -> None:
    unknown_cash = CashBalanceKey(ACCOUNT, VENUE, CurrencyId("EUR"))
    unknown_change = entry(
        "6",
        recorded_nanoseconds=60,
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        changes=(BalanceChange(unknown_cash, Money(100, USD_SCALE, "EUR")),),
    )
    with pytest.raises(UnregisteredBalanceKeyError, match="cash_balance_key"):
        GenericLedger(schema()).project(AccountingJournal.from_entries((unknown_change,)))

    unknown_attribution = entry(
        "7",
        recorded_nanoseconds=70,
        entry_type=AccountingEntryType.FUNDING_APPLIED,
        changes=(BalanceChange(USD_KEY, Money(-10, USD_SCALE, "USD")),),
        financing=(Money(10, USD_SCALE, "EUR"),),
    )
    with pytest.raises(UnregisteredBalanceKeyError, match="EUR"):
        GenericLedger(schema()).project(
            AccountingJournal.from_entries((unknown_attribution,))
        )


def test_identity_and_scale_mismatch_fail_financial_invariant() -> None:
    wrong_scale = entry(
        "6",
        recorded_nanoseconds=60,
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        changes=(BalanceChange(USD_KEY, Money(1000, Scale(3), "USD")),),
    )
    with pytest.raises(LedgerFinancialInvariantError, match="scale"):
        GenericLedger(schema()).project(AccountingJournal.from_entries((wrong_scale,)))

    wrong_attribution_scale = entry(
        "7",
        recorded_nanoseconds=70,
        entry_type=AccountingEntryType.FEE_CHARGED,
        changes=(BalanceChange(USD_KEY, Money(-10, USD_SCALE, "USD")),),
        fees=(Money(100, Scale(3), "USD"),),
    )
    with pytest.raises(LedgerFinancialInvariantError, match="scale"):
        GenericLedger(schema()).project(
            AccountingJournal.from_entries((wrong_attribution_scale,))
        )


def test_resume_rejects_forged_cursor_and_forged_state() -> None:
    journal = fixture_journal()
    ledger = GenericLedger(schema())
    prefix = ledger.project(journal, stop=journal.cursor_at(2))

    forged_cursor = replace(
        prefix,
        cursor=JournalReplayCursor(prefix.cursor.position, "sha256:" + "0" * 64),
    )
    with pytest.raises(LedgerStateMismatchError, match="cursor"):
        ledger.resume(journal, forged_cursor)

    forged_cash = replace(
        prefix.cash_balances[0], amount=Money(999, USD_SCALE, "USD")
    )
    forged_state = replace(prefix, cash_balances=(forged_cash,))
    with pytest.raises(LedgerStateMismatchError, match="state"):
        ledger.resume(journal, forged_state)


def test_resume_rejects_forged_position_lot_state() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(
            BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),
        ),
        position_lot_changes=(PositionLotChange(None, lot("lot-1", 10)),),
    )
    later_cash = entry(
        "2",
        recorded_nanoseconds=20,
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        changes=(BalanceChange(USD_KEY, Money(100, USD_SCALE, "USD")),),
    )
    journal = AccountingJournal.from_entries((open_position, later_cash))
    ledger = GenericLedger(schema())
    prefix = ledger.project(journal, stop=journal.cursor_at(1))
    position = prefix.position_balances[0]
    forged_lot = replace(position.lots[0], source_id="fill:forged")
    forged_position = replace(position, lots=(forged_lot,))
    forged_state = replace(prefix, position_balances=(forged_position,))

    with pytest.raises(LedgerStateMismatchError, match="state"):
        ledger.resume(journal, forged_state)


def test_truthful_negative_cash_and_short_position_are_not_policy_rejected() -> None:
    short = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(
            BalanceChange(USD_KEY, Money(-500, USD_SCALE, "USD")),
            BalanceChange(STOCK_KEY, Quantity(-2, QUANTITY_SCALE, str(STOCK))),
        ),
    )

    state = GenericLedger(schema()).project(AccountingJournal.from_entries((short,)))

    assert state.cash_amount(USD_KEY).units == -500
    assert state.position_quantity(STOCK_KEY).units == -2


def test_zero_position_is_removed_but_registered_zero_cash_remains_explicit() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(2, QUANTITY_SCALE, str(STOCK))),),
    )
    close_position = entry(
        "2",
        recorded_nanoseconds=20,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(-2, QUANTITY_SCALE, str(STOCK))),),
    )

    state = GenericLedger(schema()).project(
        AccountingJournal.from_entries((open_position, close_position))
    )

    expected_zero_position = Quantity(0, QUANTITY_SCALE, str(STOCK))
    assert state.position_balances == ()
    assert state.position_quantity(STOCK_KEY) == expected_zero_position
    assert state.cash_amount(USD_KEY) == Money(0, USD_SCALE, "USD")
    assert len(state.cash_balances) == 1


def test_projection_tracks_position_lot_mutation_and_keeps_exact_quantities() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),),
        position_lot_changes=(PositionLotChange(None, lot("lot-1", 10)),),
    )
    adjust = entry(
        "2",
        recorded_nanoseconds=20,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(),
        position_lot_changes=(
            PositionLotChange(before=lot("lot-1", 10), after=lot("lot-1", 3)),
            PositionLotChange(before=None, after=lot("lot-2", 7)),
        ),
    )
    close_part = entry(
        "3",
        recorded_nanoseconds=30,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(-7, QUANTITY_SCALE, str(STOCK))),),
        position_lot_changes=(
            PositionLotChange(before=lot("lot-2", 7), after=None),
        ),
    )

    state = GenericLedger(schema()).project(
        AccountingJournal.from_entries((open_position, adjust, close_part))
    )

    expected = PositionBalance(STOCK_KEY, Quantity(3, QUANTITY_SCALE, str(STOCK)), (lot("lot-1", 3),))
    assert state.position_balances == (expected,)
    assert state.position_quantity(STOCK_KEY).units == 3


def test_ledger_rejects_lot_change_total_mismatch() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),),
        position_lot_changes=(PositionLotChange(None, lot("lot-1", 5)),),
    )

    with pytest.raises(LedgerFinancialInvariantError, match="position lot total"):
        GenericLedger(schema()).project(AccountingJournal.from_entries((open_position,)))


def test_ledger_rejects_position_lot_before_not_found_and_create_conflict() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),),
        position_lot_changes=(PositionLotChange(None, lot("lot-1", 10)),),
    )
    close_unknown = entry(
        "2",
        recorded_nanoseconds=20,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(),
        position_lot_changes=(PositionLotChange(before=lot("lot-2", 1), after=None),),
    )
    duplicate_create = entry(
        "3",
        recorded_nanoseconds=30,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(),
        position_lot_changes=(PositionLotChange(None, lot("lot-1", 1)),),
    )

    with pytest.raises(LedgerFinancialInvariantError, match="before state"):
        GenericLedger(schema()).project(
            AccountingJournal.from_entries((open_position, close_unknown))
        )
    with pytest.raises(LedgerFinancialInvariantError, match="create conflict"):
        GenericLedger(schema()).project(
            AccountingJournal.from_entries((open_position, duplicate_create))
        )


def test_ledger_rejects_position_lot_before_mismatch() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(
            BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),
        ),
        position_lot_changes=(PositionLotChange(None, lot("lot-1", 10)),),
    )
    mismatched_replace = entry(
        "2",
        recorded_nanoseconds=20,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(),
        position_lot_changes=(
            PositionLotChange(
                before=lot("lot-1", 5),
                after=lot("lot-1", 4),
            ),
        ),
    )

    with pytest.raises(LedgerFinancialInvariantError, match="before mismatch"):
        GenericLedger(schema()).project(
            AccountingJournal.from_entries((open_position, mismatched_replace))
        )


def test_ledger_rejects_position_lot_close_quantity_mismatch() -> None:
    open_position = entry(
        "1",
        recorded_nanoseconds=10,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(
            BalanceChange(STOCK_KEY, Quantity(10, QUANTITY_SCALE, str(STOCK))),
        ),
        position_lot_changes=(
            PositionLotChange(None, lot("lot-1", 5)),
            PositionLotChange(None, lot("lot-2", 5)),
        ),
    )
    mismatched_close = entry(
        "2",
        recorded_nanoseconds=20,
        entry_type=AccountingEntryType.FILL_BOOKED,
        changes=(
            BalanceChange(STOCK_KEY, Quantity(-7, QUANTITY_SCALE, str(STOCK))),
        ),
        position_lot_changes=(
            PositionLotChange(before=lot("lot-1", 5), after=None),
        ),
    )

    with pytest.raises(LedgerFinancialInvariantError, match="lot total"):
        GenericLedger(schema()).project(
            AccountingJournal.from_entries((open_position, mismatched_close))
        )
