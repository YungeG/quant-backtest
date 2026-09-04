from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    DomainIdKind,
    Money,
    OrderSide,
    PortfolioSnapshot,
    Price,
    PricePurpose,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    CashInstrumentAccounting,
    CurrencyValuationGraph,
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
    MarkObservation,
    MarkResolver,
    PortfolioSnapshotProjector,
    PortfolioValueKind,
    PortfolioValueRef,
    ReportingCurrencyValuation,
    ResolvedMark,
    StaleMarkPolicy,
)

from tests.kernel.accounting._fixtures import (
    ACCOUNT,
    CASH_KEY,
    COST_BASIS_POLICY,
    INSTRUMENT,
    MONEY_SCALE,
    NOTIONAL_POLICY,
    POSITION_KEY,
    QUANTITY_SCALE,
    USD,
    VENUE,
    domain_id,
    fee_assessment,
    fill,
    recorded_at,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/foundation-financial-journey-v1.json"
ACCOUNTING = CashInstrumentAccounting()
VALUATION_AT = UtcInstant(50)


def deposit() -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "0"),
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        account_id=ACCOUNT,
        venue_id=VENUE,
        effective_time=UtcInstant(0),
        recorded_at=SimulationInstant(
            UtcInstant(1), TimelinePhase(50, "accounting"), SourceSequence(1)
        ),
        source_ids=("capital:initial",),
        balance_changes=(
            BalanceChange(CASH_KEY, Money(100_000, MONEY_SCALE, str(USD))),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )


def valuation_mark() -> ResolvedMark:
    observation = MarkObservation(
        instrument_id=INSTRUMENT,
        quote_currency_id=USD,
        price_purpose=PricePurpose.VALUATION,
        price=Price(12_000, MONEY_SCALE, str(INSTRUMENT), str(USD)),
        observed_at=UtcInstant(45),
        available_at=UtcInstant(46),
        stream_id="stream:cash-asset-1:valuation",
        source_event_id="event:cash-asset-1:45",
        revision_id="revision:1",
    )
    outcome = MarkResolver().resolve(
        (observation,),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=VALUATION_AT,
        stale_policy=StaleMarkPolicy(
            policy_key="marks.valuation.foundation.v1",
            policy_version=1,
            price_purpose=PricePurpose.VALUATION,
            max_age_nanoseconds=10,
            allow_forward_fill=True,
        ),
    )
    assert outcome.resolved_mark is not None
    return outcome.resolved_mark


def build_financial_evidence() -> tuple[
    AccountingJournal,
    LedgerState,
    tuple[ReportingCurrencyValuation, ...],
    ResolvedMark,
    str,
]:
    buy = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=20,
        price_units=10_000,
        execution_time=10,
    )
    bought = ACCOUNTING.book_fill(
        fill=buy,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        recorded_at=recorded_at(11),
    ).result
    assert bought is not None
    buy_fee = ACCOUNTING.charge_fee(
        assessment=fee_assessment(
            "3", buy, amount_units=100, assessment_time=12
        ),
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=bought.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "3"),
        recorded_at=recorded_at(13),
    ).result
    assert buy_fee is not None

    sell = fill(
        "2",
        side=OrderSide.SELL,
        quantity_units=10,
        price_units=13_000,
        execution_time=30,
    )
    sold = ACCOUNTING.book_fill(
        fill=sell,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=buy_fee.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "2"),
        recorded_at=recorded_at(31),
    ).result
    assert sold is not None
    sell_fee = ACCOUNTING.charge_fee(
        assessment=fee_assessment(
            "4", sell, amount_units=150, assessment_time=32
        ),
        related_fill=sell,
        cash_key=CASH_KEY,
        open_lots=sold.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(33),
    ).result
    assert sell_fee is not None

    journal = AccountingJournal.from_entries(
        (
            deposit(),
            bought.journal_entry,
            buy_fee.journal_entry,
            sold.journal_entry,
            sell_fee.journal_entry,
        )
    )
    ledger_state = GenericLedger(
        LedgerSchema(
            (
                LedgerBalanceRegistration(CASH_KEY, MONEY_SCALE),
                LedgerBalanceRegistration(POSITION_KEY, QUANTITY_SCALE),
            )
        )
    ).project(journal)

    mark = valuation_mark()
    graph = CurrencyValuationGraph(
        valuation_at=VALUATION_AT,
        price_purpose=PricePurpose.VALUATION,
        edges=(),
    )
    resolution = graph.resolve(USD, USD).resolution
    assert resolution is not None
    position_value = mark.price.notional(
        ledger_state.position_quantity(POSITION_KEY),
        result_scale=MONEY_SCALE,
        rounding=NOTIONAL_POLICY.rounding,
    )
    remaining_lot = sold.open_lots[0]
    assert remaining_lot.unit_cost is not None
    remaining_cost = remaining_lot.unit_cost.notional(
        remaining_lot.quantity,
        result_scale=MONEY_SCALE,
        rounding=NOTIONAL_POLICY.rounding,
    )
    unrealized = position_value - remaining_cost
    valuations = (
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.CASH, CASH_KEY),
            ledger_state.cash_amount(CASH_KEY),
            ledger_state.cash_amount(CASH_KEY),
            resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.POSITION_MARKET_VALUE, POSITION_KEY),
            position_value,
            position_value,
            resolution,
            graph.graph_hash,
            NOTIONAL_POLICY,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.UNREALIZED_PNL, POSITION_KEY),
            unrealized,
            unrealized,
            resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.REALIZED_PNL, CASH_KEY),
            ledger_state.realized_pnl_amount(CASH_KEY),
            ledger_state.realized_pnl_amount(CASH_KEY),
            resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.FEES, CASH_KEY),
            ledger_state.fee_amount(CASH_KEY),
            ledger_state.fee_amount(CASH_KEY),
            resolution,
            graph.graph_hash,
        ),
    )
    return journal, ledger_state, valuations, mark, graph.graph_hash


def project_snapshot(
    ledger_state: LedgerState,
    valuations: tuple[ReportingCurrencyValuation, ...],
    mark: ResolvedMark,
    graph_hash: str,
) -> PortfolioSnapshot:
    outcome = PortfolioSnapshotProjector().project(
        ledger_state=ledger_state,
        resolved_marks=(mark,),
        valuations=valuations,
        reporting_currency=USD,
        reporting_scale=MONEY_SCALE,
        timestamp=VALUATION_AT,
        currency_valuation_graph_hash=graph_hash,
    )
    assert outcome.snapshot is not None
    return outcome.snapshot


def test_foundation_financial_journey_replays_and_rebuilds_exactly() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen foundation financial fixture: {error}")

    journal, ledger_state, valuations, mark, graph_hash = build_financial_evidence()
    snapshot = project_snapshot(ledger_state, valuations, mark, graph_hash)

    assert ledger_state.cash_amount(CASH_KEY) == Money(92_750, MONEY_SCALE, str(USD))
    assert ledger_state.position_quantity(POSITION_KEY).units == 10
    assert ledger_state.realized_pnl_amount(CASH_KEY) == Money(
        3_000, MONEY_SCALE, str(USD)
    )
    assert ledger_state.fee_amount(CASH_KEY) == Money(250, MONEY_SCALE, str(USD))
    assert snapshot.realized_pnl == Money(3_000, MONEY_SCALE, str(USD))
    assert snapshot.unrealized_pnl == Money(2_000, MONEY_SCALE, str(USD))
    assert snapshot.fees == Money(250, MONEY_SCALE, str(USD))
    assert snapshot.equity == Money(104_750, MONEY_SCALE, str(USD))
    assert snapshot.equity.units - 100_000 == (
        snapshot.realized_pnl.units
        + snapshot.unrealized_pnl.units
        - snapshot.fees.units
    )

    snapshot_hash = canonical_sha256(snapshot)
    snapshot_bytes = canonical_bytes(snapshot)
    del snapshot
    rebuilt = project_snapshot(ledger_state, tuple(reversed(valuations)), mark, graph_hash)
    assert canonical_bytes(rebuilt) == snapshot_bytes
    assert canonical_sha256(rebuilt) == snapshot_hash

    actual = {
        "fixture_id": "foundation-financial-journey-v1",
        "journal_entry_count": journal.entry_count,
        "journal_hash": journal.journal_hash,
        "ledger_state_hash": ledger_state.state_hash,
        "cash_units": ledger_state.cash_amount(CASH_KEY).units,
        "position_units": ledger_state.position_quantity(POSITION_KEY).units,
        "gross_realized_pnl_units": rebuilt.realized_pnl.units,
        "unrealized_pnl_units": rebuilt.unrealized_pnl.units,
        "fee_units": rebuilt.fees.units,
        "net_economic_change_units": (
            rebuilt.realized_pnl.units
            + rebuilt.unrealized_pnl.units
            - rebuilt.fees.units
        ),
        "equity_units": rebuilt.equity.units,
        "mark_id": mark.mark_id,
        "currency_valuation_graph_hash": graph_hash,
        "snapshot_hash": snapshot_hash,
        "snapshot": json.loads(snapshot_bytes),
    }
    assert actual == expected
