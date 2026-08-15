from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalance,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    InstrumentId,
    Money,
    PortfolioSnapshot,
    PositionBalance,
    PositionBalanceKey,
    PositionLot,
    PositionLotChange,
    Price,
    PricePurpose,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    ValuationMarkReference,
    VenueId,
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_V1 = ROOT / "tests/fixtures/domain/accounting-contracts-v1.json"
FIXTURE_V2 = ROOT / "tests/fixtures/domain/accounting-contracts-v2.json"


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid accounting fixture: {path}") from error


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def venue() -> VenueId:
    return VenueId("sse")


def instrument(stable_key: str = "equity:600000") -> InstrumentId:
    return InstrumentId(venue(), stable_key)


def cash_key(currency: str = "CNY") -> CashBalanceKey:
    return CashBalanceKey("account:primary", venue(), CurrencyId(currency))


def position_key(stable_key: str = "equity:600000") -> PositionBalanceKey:
    return PositionBalanceKey("account:primary", venue(), instrument(stable_key))


def money(units: int, currency: str = "CNY") -> Money:
    return Money(units, Scale(2), currency)


def quantity(units: int, stable_key: str = "equity:600000") -> Quantity:
    return Quantity(units, Scale(0), str(instrument(stable_key)))


def lot() -> PositionLot:
    return PositionLot(
        lot_id="lot:fill-1",
        position_key=position_key(),
        source_id="fill:1",
        quantity=quantity(10_000),
        unit_cost=Price(1_025, Scale(2), str(instrument()), "CNY"),
        allocated_fees=(money(500),),
        opened_at=UtcInstant(100),
    )


def lot_with_total_cost_basis() -> PositionLot:
    return PositionLot(
        lot_id="lot:fill-1",
        position_key=position_key(),
        source_id="fill:1",
        quantity=quantity(10_000),
        unit_cost=Price(1_025, Scale(2), str(instrument()), "CNY"),
        allocated_fees=(money(500),),
        opened_at=UtcInstant(100),
        total_cost_basis=money(10_250_000),
    )


def lot_with_replacement() -> PositionLot:
    return PositionLot(
        lot_id="lot:fill-1",
        position_key=position_key(),
        source_id="fill:1",
        quantity=quantity(5_000),
        unit_cost=Price(1_050, Scale(2), str(instrument()), "CNY"),
        allocated_fees=(money(500),),
        opened_at=UtcInstant(100),
        total_cost_basis=money(5_250_000),
    )


def journal() -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id="account:primary",
        venue_id=venue(),
        effective_time=UtcInstant(110),
        recorded_at=SimulationInstant(
            UtcInstant(120),
            TimelinePhase(40, "accounting"),
            SourceSequence(1),
        ),
        source_ids=("fill:2", "fill:1"),
        balance_changes=(
            BalanceChange(position_key(), quantity(10_000)),
            BalanceChange(cash_key(), money(-10_250_000)),
        ),
        realized_pnl=(),
        fees=(money(500),),
        financing=(),
    )


def journal_with_lots() -> AccountingJournalEntry:
    replacement = lot_with_replacement()
    change = PositionLotChange(
        before=PositionLot(
            lot_id="lot:fill-1",
            position_key=position_key(),
            source_id="fill:1",
            quantity=quantity(10_000),
            unit_cost=Price(1_025, Scale(2), str(instrument()), "CNY"),
            allocated_fees=(money(500),),
            opened_at=UtcInstant(100),
            total_cost_basis=money(10_250_000),
        ),
        after=replacement,
    )
    return AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "2"),
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id="account:primary",
        venue_id=venue(),
        effective_time=UtcInstant(130),
        recorded_at=SimulationInstant(
            UtcInstant(140),
            TimelinePhase(40, "accounting"),
            SourceSequence(1),
        ),
        source_ids=("fill:2",),
        balance_changes=(
            BalanceChange(position_key(), quantity(-5_000)),
            BalanceChange(cash_key(), money(5_250_000)),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
        position_lot_changes=(change,),
    )


def snapshot() -> PortfolioSnapshot:
    marks = (
        ValuationMarkReference(
            "mark:600001",
            instrument("equity:600001"),
            PricePurpose.VALUATION,
            UtcInstant(191),
        ),
        ValuationMarkReference(
            "mark:600000",
            instrument(),
            PricePurpose.VALUATION,
            UtcInstant(190),
        ),
    )
    return PortfolioSnapshot(
        account_id="account:primary",
        timestamp=UtcInstant(200),
        reporting_currency=CurrencyId("CNY"),
        cash=(
            CashBalance(cash_key("USD"), money(100_00, "USD")),
            CashBalance(cash_key(), money(89_750_000)),
        ),
        positions=(
            PositionBalance(position_key(), quantity(10_000), (lot(),)),
        ),
        realized_pnl=money(0),
        unrealized_pnl=money(750_000),
        fees=money(500),
        financing=money(0),
        equity=money(100_007_500),
        valuation_marks=marks,
        journal_state_hash="sha256:" + "a" * 64,
        valuation_mark_set_hash=canonical_sha256(
            tuple(sorted(marks, key=lambda value: value.mark_id))
        ),
        valuation_staleness_report_hash="sha256:" + "b" * 64,
        currency_valuation_graph_hash="sha256:" + "c" * 64,
    )


def build_objects() -> dict[str, object]:
    return {
        "cash_balance_key": cash_key(),
        "position_balance_key": position_key(),
        "position_lot": lot(),
        "journal_entry": journal(),
        "portfolio_snapshot": snapshot(),
    }


def build_v2_objects() -> dict[str, object]:
    return {
        "position_lot_v2": lot_with_total_cost_basis(),
        "position_lot_change_v2": PositionLotChange(
            before=lot(),
            after=lot_with_replacement(),
        ),
        "journal_entry_v2": journal_with_lots(),
    }


def test_accounting_contracts_match_golden_hashes() -> None:
    expected = load_fixture(FIXTURE_V1)["expected_sha256"]
    actual = {name: canonical_sha256(value) for name, value in build_objects().items()}
    assert actual == expected


def test_accounting_contracts_match_v2_golden_hashes() -> None:
    expected = load_fixture(FIXTURE_V2)["expected_sha256"]
    actual = {name: canonical_sha256(value) for name, value in build_v2_objects().items()}
    assert actual == expected



def test_set_like_accounting_inputs_have_order_independent_hashes() -> None:
    entry = journal()
    reversed_entry = replace(
        entry,
        source_ids=tuple(reversed(entry.source_ids)),
        balance_changes=tuple(reversed(entry.balance_changes)),
    )
    assert canonical_sha256(reversed_entry) == canonical_sha256(entry)

    value = snapshot()
    reversed_snapshot = replace(
        value,
        cash=tuple(reversed(value.cash)),
        valuation_marks=tuple(reversed(value.valuation_marks)),
    )
    assert canonical_sha256(reversed_snapshot) == canonical_sha256(value)
