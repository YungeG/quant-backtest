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
    PositionBalanceKey,
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
