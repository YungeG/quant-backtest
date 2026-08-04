from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalance,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    Fill,
    InstrumentId,
    Money,
    OrderSide,
    PortfolioSnapshot,
    PositionBalance,
    PositionBalanceKey,
    PositionLot,
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


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def venue() -> VenueId:
    return VenueId("sse")


def instrument() -> InstrumentId:
    return InstrumentId(venue(), "equity:600000")


def cash_key(currency: str = "CNY") -> CashBalanceKey:
    return CashBalanceKey("account:primary", venue(), CurrencyId(currency))


def position_key() -> PositionBalanceKey:
    return PositionBalanceKey("account:primary", venue(), instrument())


def quantity(units: int = 10_000, places: int = 0) -> Quantity:
    return Quantity(units, Scale(places), str(instrument()))


def money(units: int, currency: str = "CNY", places: int = 2) -> Money:
    return Money(units, Scale(places), currency)


def price(units: int = 1_025, places: int = 2) -> Price:
    return Price(units, Scale(places), str(instrument()), "CNY")


def recorded_at(nanoseconds: int = 120, sequence: int = 1) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds),
        TimelinePhase(40, "accounting"),
        SourceSequence(sequence),
    )


def lot(lot_id: str = "lot:fill-1", units: int = 10_000) -> PositionLot:
    return PositionLot(
        lot_id=lot_id,
        position_key=position_key(),
        source_id="fill:1",
        quantity=quantity(units),
        unit_cost=price(),
        allocated_fees=(money(500),),
        opened_at=UtcInstant(100),
    )


def journal_entry() -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id="account:primary",
        venue_id=venue(),
        effective_time=UtcInstant(110),
        recorded_at=recorded_at(),
        source_ids=("fill:1",),
        balance_changes=(
            BalanceChange(cash_key(), money(-10_250_000)),
            BalanceChange(position_key(), quantity()),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )


def mark(mark_id: str = "mark:valuation-1") -> ValuationMarkReference:
    return ValuationMarkReference(
        mark_id=mark_id,
        instrument_id=instrument(),
        price_purpose=PricePurpose.VALUATION,
        observed_at=UtcInstant(190),
    )


def snapshot() -> PortfolioSnapshot:
    valuation_marks = (mark(),)
    reporting = CurrencyId("CNY")
    return PortfolioSnapshot(
        account_id="account:primary",
        timestamp=UtcInstant(200),
        reporting_currency=reporting,
        cash=(CashBalance(cash_key(), money(89_750_000)),),
        positions=(PositionBalance(position_key(), quantity(), (lot(),)),),
        realized_pnl=money(0),
        unrealized_pnl=money(750_000),
        fees=money(500),
        financing=money(0),
        equity=money(100_007_500),
        valuation_marks=valuation_marks,
        journal_state_hash="sha256:" + "a" * 64,
        valuation_mark_set_hash=canonical_sha256(valuation_marks),
        valuation_staleness_report_hash="sha256:" + "b" * 64,
        currency_valuation_graph_hash="sha256:" + "c" * 64,
    )


def test_price_purpose_is_typed_and_fill_rejects_raw_strings() -> None:
    assert [purpose.value for purpose in PricePurpose] == [
        "execution_reference",
        "valuation",
        "margin",
        "liquidation",
        "settlement",
        "funding",
    ]

    with pytest.raises(TypeError, match="PricePurpose"):
        cast(Any, Fill)(
            fill_id=domain_id(DomainIdKind.FILL, "2"),
            order_id=domain_id(DomainIdKind.ORDER, "3"),
            account_id="account:primary",
            venue_id=venue(),
            instrument_id=instrument(),
            side=OrderSide.BUY,
            quantity=quantity(1),
            reference_price=price(),
            reference_price_purpose="execution_reference",
            price=price(),
            slippage_amount=money(0),
            slippage_decision_id="slippage:1",
            slippage_model_key="slippage:none.v1",
            slippage_calibration_id=None,
            liquidity=None,
            execution_time=UtcInstant(100),
        )


def test_balance_keys_and_changes_enforce_native_identity() -> None:
    cash_change = BalanceChange(cash_key(), money(-1_000))
    position_change = BalanceChange(position_key(), quantity(100))
    assert isinstance(cash_change.value, Money)
    assert isinstance(position_change.value, Quantity)
    assert cash_change.value.currency == "CNY"
    assert position_change.value.instrument_id == str(instrument())

    with pytest.raises(ValueError, match="Venue"):
        PositionBalanceKey(
            "account:primary",
            VenueId("szse"),
            instrument(),
        )
    with pytest.raises(TypeError, match="CashBalanceKey.*Money"):
        BalanceChange(cash_key(), cast(Any, quantity(1)))
    with pytest.raises(ValueError, match="currency identity"):
        BalanceChange(cash_key(), money(1, "USD"))
    with pytest.raises(ValueError, match="instrument identity"):
        BalanceChange(
            position_key(),
            Quantity(1, Scale(0), "sse:equity:other"),
        )
    with pytest.raises(ValueError, match="non-zero"):
        BalanceChange(cash_key(), money(0))


def test_journal_entry_has_stable_identity_sources_time_and_typed_changes() -> None:
    entry = journal_entry()
    assert entry.journal_entry_id.kind is DomainIdKind.JOURNAL
    assert all(field.name != "snapshot" for field in fields(AccountingJournalEntry))

    with pytest.raises(ValueError, match="JOURNAL"):
        replace(entry, journal_entry_id=domain_id(DomainIdKind.FILL, "2"))
    with pytest.raises(ValueError, match="source_ids"):
        replace(entry, source_ids=())
    with pytest.raises(ValueError, match="duplicate source"):
        replace(entry, source_ids=("fill:1", "fill:1"))
    with pytest.raises(ValueError, match="effective_time"):
        replace(entry, effective_time=UtcInstant(121))
    with pytest.raises(ValueError, match="account"):
        replace(
            entry,
            balance_changes=(
                BalanceChange(
                    CashBalanceKey("account:other", venue(), CurrencyId("CNY")),
                    money(1),
                ),
            ),
        )
    with pytest.raises(ValueError, match="duplicate balance"):
        replace(
            entry,
            balance_changes=(
                BalanceChange(cash_key(), money(-1)),
                BalanceChange(cash_key(), money(1)),
            ),
        )

    with pytest.raises(FrozenInstanceError):
        cast(Any, entry).account_id = "account:other"


def test_position_lot_and_position_balance_preserve_lot_provenance() -> None:
    value = lot()
    balance = PositionBalance(position_key(), quantity(), (value,))
    assert balance.lots[0].source_id == "fill:1"

    with pytest.raises(ValueError, match="non-zero"):
        replace(value, quantity=quantity(0))
    with pytest.raises(ValueError, match="instrument identity"):
        replace(
            value,
            quantity=Quantity(1, Scale(0), "sse:equity:other"),
        )
    with pytest.raises(ValueError, match="positive"):
        replace(value, unit_cost=price(0))
    with pytest.raises(ValueError, match="duplicate allocated fee currency"):
        replace(value, allocated_fees=(money(1), money(2)))
    with pytest.raises(ValueError, match="exact lot total"):
        replace(balance, quantity=quantity(9_999))
    with pytest.raises(ValueError, match="duplicate lot"):
        replace(balance, lots=(value, value))


def test_cash_and_position_balances_are_typed_immutable_state_values() -> None:
    cash = CashBalance(cash_key(), money(100))
    position = PositionBalance(position_key(), quantity(), ())
    assert cash.amount.currency == str(cash.key.currency_id)
    assert not position.lots

    with pytest.raises(ValueError, match="currency identity"):
        replace(cash, amount=money(100, "USD"))
    with pytest.raises(ValueError, match="non-zero"):
        replace(position, quantity=quantity(0))


def test_valuation_mark_reference_is_typed() -> None:
    value = mark()
    assert value.price_purpose is PricePurpose.VALUATION

    with pytest.raises(TypeError, match="PricePurpose"):
        replace(value, price_purpose=cast(Any, "valuation"))
    with pytest.raises(ValueError, match="mark_id"):
        replace(value, mark_id=" mark:valuation-1 ")


def test_snapshot_enforces_reporting_currency_marks_and_content_hashes() -> None:
    value = snapshot()
    assert value.equity.currency == str(value.reporting_currency)

    with pytest.raises(ValueError, match="Reporting Currency"):
        replace(value, equity=money(value.equity.units, "USD"))
    with pytest.raises(ValueError, match="future valuation mark"):
        replace(
            value,
            valuation_marks=(replace(mark(), observed_at=UtcInstant(201)),),
            valuation_mark_set_hash=canonical_sha256(
                (replace(mark(), observed_at=UtcInstant(201)),)
            ),
        )
    with pytest.raises(ValueError, match="duplicate valuation mark"):
        replace(
            value,
            valuation_marks=(mark(), mark()),
            valuation_mark_set_hash=canonical_sha256((mark(), mark())),
        )
    with pytest.raises(ValueError, match="mark-set hash"):
        replace(value, valuation_mark_set_hash="sha256:" + "d" * 64)
    with pytest.raises(ValueError, match="sha256"):
        replace(value, journal_state_hash="not-a-hash")
    with pytest.raises(ValueError, match="duplicate CashBalance"):
        replace(value, cash=(value.cash[0], value.cash[0]))


def test_set_like_inputs_have_order_independent_canonical_hashes() -> None:
    second_cash_key = CashBalanceKey(
        "account:primary", venue(), CurrencyId("USD")
    )
    entry = replace(
        journal_entry(),
        source_ids=("fill:2", "fill:1"),
        balance_changes=(
            BalanceChange(second_cash_key, money(100, "USD")),
            *journal_entry().balance_changes,
        ),
        fees=(money(25, "USD"), money(500)),
    )
    reversed_entry = replace(
        entry,
        source_ids=tuple(reversed(entry.source_ids)),
        balance_changes=tuple(reversed(entry.balance_changes)),
        fees=tuple(reversed(entry.fees)),
    )
    assert canonical_sha256(entry) == canonical_sha256(reversed_entry)

    first_mark = mark("mark:valuation-1")
    second_mark = ValuationMarkReference(
        "mark:valuation-2",
        InstrumentId(venue(), "equity:600001"),
        PricePurpose.VALUATION,
        UtcInstant(191),
    )
    base = snapshot()
    marks = (first_mark, second_mark)
    reversed_marks = tuple(reversed(marks))
    first = replace(
        base,
        valuation_marks=marks,
        valuation_mark_set_hash=canonical_sha256(marks),
    )
    second = replace(
        base,
        valuation_marks=reversed_marks,
        valuation_mark_set_hash=canonical_sha256(marks),
    )
    assert canonical_sha256(first) == canonical_sha256(second)
