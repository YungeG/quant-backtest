from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, BalanceChange, CashBalanceKey,
    CurrencyId, DomainId, DomainIdKind, Money, Scale, SimulationInstant,
    SourceSequence, TimelinePhase, UtcInstant, VenueId, canonical_bytes,
)


def cash_key() -> CashBalanceKey:
    return CashBalanceKey("account:primary", VenueId("xshg"), CurrencyId("CNY"))


def journal_entry() -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=DomainId(DomainIdKind.JOURNAL, "jnl_" + "1" * 64),
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id="account:primary",
        venue_id=VenueId("xshg"),
        effective_time=UtcInstant(110),
        recorded_at=SimulationInstant(UtcInstant(120), TimelinePhase(70, "accounting"), SourceSequence(1)),
        source_ids=("fill:1",),
        balance_changes=(BalanceChange(cash_key(), Money(-1000, Scale(2), "CNY")),),
        realized_pnl=(), fees=(), financing=(),
    )


def test_corporate_action_tax_paid_uses_native_cash_entry() -> None:
    entry = replace(
        journal_entry(),
        entry_type=AccountingEntryType.CORPORATE_ACTION_TAX_PAID,
        balance_changes=(BalanceChange(cash_key(), Money(-247, Scale(2), "CNY")),),
    )
    assert entry.entry_type.value == "corporate_action_tax_paid"
    assert entry.balance_changes[0].value == Money(-247, Scale(2), "CNY")
    assert b'"entry_type":"corporate_action_tax_paid"' in canonical_bytes(entry)
    assert entry.fees == entry.financing == entry.realized_pnl == ()


def test_old_entry_type_encoding_and_enum_values_are_preserved() -> None:
    entry = journal_entry()
    assert entry.entry_type is AccountingEntryType.FILL_BOOKED
    assert b'"entry_type":"fill_booked"' in canonical_bytes(entry)
    assert [item.value for item in AccountingEntryType if item is not AccountingEntryType.CORPORATE_ACTION_TAX_PAID] == [
        "capital_deposited", "capital_withdrawn", "capital_transferred", "fill_booked",
        "fee_charged", "funding_applied", "borrow_fee_charged", "settlement_applied",
        "corporate_action_entitlement_booked", "corporate_action_position_adjusted",
        "corporate_action_cash_paid", "liquidation_applied",
    ]


def test_tax_cash_changes_do_not_allow_zero_or_float_money() -> None:
    with pytest.raises(ValueError):
        BalanceChange(cash_key(), Money(0, Scale(2), "CNY"))
    with pytest.raises(TypeError):
        Money(2.47, Scale(2), "CNY")  # type: ignore[arg-type]
