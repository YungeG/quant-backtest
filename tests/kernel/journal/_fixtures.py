from __future__ import annotations

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    Money,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)


def journal_id(digit: str) -> DomainId:
    return DomainId(DomainIdKind.JOURNAL, f"jnl_{digit * 64}")


def journal_entry(
    digit: str,
    *,
    recorded_nanoseconds: int,
    source_sequence: int = 1,
    amount_units: int = 10_000,
) -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=journal_id(digit),
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        account_id="account:primary",
        venue_id=VenueId("synthetic"),
        effective_time=UtcInstant(recorded_nanoseconds - 1),
        recorded_at=SimulationInstant(
            UtcInstant(recorded_nanoseconds),
            TimelinePhase(40, "accounting"),
            SourceSequence(source_sequence),
        ),
        source_ids=(f"capital:{digit}",),
        balance_changes=(
            BalanceChange(
                CashBalanceKey(
                    "account:primary", VenueId("synthetic"), CurrencyId("USD")
                ),
                Money(amount_units, Scale(2), "USD"),
            ),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
