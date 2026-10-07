"""Development-only T+1 smoke for the actual new SH/SZ Fill IDs.

No published settlement owner-log, full two-week executor or OOS run.
"""
from __future__ import annotations

from datetime import date
import json

import pytest

from crypto_quant_domain import (
    AccountingEntryType, CashBalanceKey, CurrencyId, DomainId, DomainIdKind,
    InstrumentDefinition, InstrumentType, PositionBalanceKey, canonical_bytes, canonical_sha256,
    RoundingPolicy, SimulationInstant, SourceSequence, TimelinePhase, UtcInstant,
)
from crypto_quant_trading import CashInstrumentAccounting, CostBasisMethod, CostBasisPolicy, SettlementBook
from crypto_quant_trading.settlement import SettlementLifecycleError
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCalendarDayKind, CnAShareCashSettlementModel,
    CnAShareFrozenCalendar, CnAShareFrozenCalendarDay, CnAShareSettlementQuery,
)
from crypto_quant_backtest.cn_a_share_portfolio_settlement_development_v1 import (
    _book_body, build_cn_a_share_portfolio_settlement_development_v1,
    read_cn_a_share_portfolio_settlement_book_source_v1,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_sellability_v1 import (
    project_cn_a_share_portfolio_sellability_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_next_open_development_v1 import (
    evaluate_cn_a_share_portfolio_next_open_development_v1,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    QUANTIZATION, domain_id, instrument,
)
from tests.kernel.profiles.cn_a_share.test_portfolio_open_risk_development_v1 import _opening_case
from tests.kernel.profiles.cn_a_share.test_portfolio_sellability_v1 import _two_week_sources
from tests.kernel.profiles.cn_a_share.test_portfolio_order_plan_v1 import _accepted
from tests.runtime.providers.test_cn_a_share_portfolio_next_open_development_v1 import _open_source
from tests.runtime.providers.test_cn_a_share_portfolio_fill_fee_journal_development_v1 import _financial_batch


def _calendar(venue):
    days = tuple(CnAShareFrozenCalendarDay(date(2023, 8, day), CnAShareCalendarDayKind.TRADING)
                 for day in (28, 29))
    return CnAShareFrozenCalendar(
        venue_id=venue, calendar_id="CN.XSHG" if venue.value == "xshg" else "CN.XSHE",
        coverage_start=date(2023, 8, 28), coverage_end_exclusive=date(2023, 8, 30), days=days)


def _week_calendar(venue):
    kinds = {25: CnAShareCalendarDayKind.TRADING,
             26: CnAShareCalendarDayKind.WEEKEND,
             27: CnAShareCalendarDayKind.WEEKEND,
             28: CnAShareCalendarDayKind.TRADING,
             29: CnAShareCalendarDayKind.TRADING}
    return CnAShareFrozenCalendar(
        venue_id=venue, calendar_id="CN.XSHG" if venue.value == "xshg" else "CN.XSHE",
        coverage_start=date(2023, 8, 25), coverage_end_exclusive=date(2023, 8, 30),
        days=tuple(CnAShareFrozenCalendarDay(date(2023, 8, day), kind)
                   for day, kind in kinds.items()))


def test_local_book_prefix_holds_two_stock_friday_inventory_until_monday_due():
    batch = _financial_batch(25)
    _, schema, rules, _, keys, _ = _two_week_sources()
    calendars = (_week_calendar(batch.fills[0].venue_id),
                 _week_calendar(batch.fills[1].venue_id))
    first = build_cn_a_share_portfolio_settlement_development_v1(
        batch=batch, calendars=calendars)
    assert not first.trade_authorized and first.synthetic_development_only
    pending = first.book.project().pending_obligations
    assert len(pending) == 2
    assert all(isinstance(ob.balance_key, PositionBalanceKey) for ob in pending)
    assert {ob.balance_key.instrument_id for ob in pending
            if isinstance(ob.balance_key, PositionBalanceKey)} == {key.instrument_id for key in keys}
    maturity = pending[0].obligation.settlement_time
    assert all(ob.obligation.settlement_time == maturity for ob in pending)
    before = UtcInstant(maturity.epoch_nanoseconds - 1)
    assert first.apply_due(before) == first
    sell_before = project_cn_a_share_portfolio_sellability_v1(
        journal=batch.journal, ledger_schema=schema, settlement_book=first.book,
        order_streams=(), reservation_schedules=(), market_rules=rules, as_of=before)
    assert [sell_before.sellable_for(key.instrument_id).units for key in keys] == [0, 0]
    mature = first.apply_due(maturity)
    assert mature.book != first.book
    assert mature.book.cursor_at(first.book.event_count).prefix_hash == first.book.book_hash
    assert not mature.book.project().pending_obligations
    assert mature.apply_due(maturity) == mature
    sell_after = project_cn_a_share_portfolio_sellability_v1(
        journal=batch.journal, ledger_schema=schema, settlement_book=mature.book,
        order_streams=(), reservation_schedules=(), market_rules=rules, as_of=maturity)
    assert [sell_after.sellable_for(key.instrument_id).units for key in keys] == [100, 100]
    assert first.financial_batch_hash == batch.batch_hash
    assert first.settlement_hash != mature.settlement_hash



def test_friday_two_stock_native_fill_fee_to_monday_t_plus_one_obligations():
    batch = _financial_batch(25)
    assert {f.venue_id.value for f in batch.fills} == {"xshg", "xshe"}
    for fill in batch.fills:
        sources = tuple(entry for entry in batch.journal.entries
                        if entry.entry_type is AccountingEntryType.FILL_BOOKED
                        and fill.fill_id.value in entry.source_ids)
        assert len(sources) == 1
        instrument = InstrumentDefinition(fill.instrument_id, InstrumentType.EQUITY,
                                          None, CurrencyId("CNY"), CurrencyId("CNY"))
        def settlement_id(leg):
            digest = canonical_sha256({"fill": fill.fill_id, "leg": leg})
            return DomainId(DomainIdKind.SETTLEMENT,
                            f"{DomainIdKind.SETTLEMENT.prefix}_" + digest[7:])
        out = CnAShareCashSettlementModel(_week_calendar(fill.venue_id)).resolve_settlement(
            CnAShareSettlementQuery(
                fill, instrument, sources[0], settlement_id("cash"), settlement_id("position")))
        assert out.failure is None and out.result is not None
        assert out.result.trade_date.value == date(2023, 8, 25)
        assert out.result.next_trading_date.value == date(2023, 8, 28)
        assert out.result.position_availability_time > fill.execution_time



def test_native_two_venue_fill_settlement_defers_newly_bought_shares_to_next_session():
    plan, cash, positions, reservations, evidence, t = _opening_case()
    policy = CostBasisPolicy("cn.synthetic.portfolio.fifo.v2", 2, CostBasisMethod.FIFO,
                             RoundingPolicy.HALF_EVEN)
    for seq, (digit, item) in enumerate((("6", evidence[0]), ("7", evidence[1])), start=1):
        prop, order, _, _, obs = item
        stream, _, _, _ = _accepted(prop, digit, fee=505)
        risk, liquidity, market_state, zero = _open_source(
            item, plan, cash, positions, reservations, t)
        opening = evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=obs, risk=risk, liquidity=liquidity,
            market_state=market_state, slippage_model=zero,
            eligibility_window_exhausted=True)
        fill = opening.fill
        assert fill is not None
        booked = CashInstrumentAccounting().book_fill(
            fill=fill, cash_key=CashBalanceKey(fill.account_id, fill.venue_id, CurrencyId("CNY")),
            position_key=PositionBalanceKey(fill.account_id, fill.venue_id, fill.instrument_id),
            open_lots=(), cost_basis_policy=policy, notional_quantization=QUANTIZATION,
            journal_entry_id=domain_id(DomainIdKind.JOURNAL, "a" if seq == 1 else "b"),
            recorded_at=SimulationInstant(t, TimelinePhase(70, "accounting"), SourceSequence(seq)))
        assert booked.failure is None and booked.result is not None
        settlement = CnAShareCashSettlementModel(_calendar(fill.venue_id)).resolve_settlement(
            CnAShareSettlementQuery(
                fill=fill, instrument=instrument(fill.venue_id.value),
                fill_accounting_entry=booked.result.journal_entry,
                cash_obligation_id=domain_id(DomainIdKind.SETTLEMENT, "c" if seq == 1 else "d"),
                position_obligation_id=domain_id(DomainIdKind.SETTLEMENT, "e" if seq == 1 else "f")))
        assert settlement.failure is None and settlement.result is not None
        assert settlement.result.trade_date.value == date(2023, 8, 28)
        assert settlement.result.next_trading_date.value == date(2023, 8, 29)
        assert sorted(value.units for value in settlement.result.obligations) == [-40_000, 100]
        assert settlement.result.position_availability_time > fill.execution_time


def test_source_only_book_replay_preserves_two_venue_t_plus_one_prefix():
    initial = SettlementBook("account:synthetic-portfolio")
    assert read_cn_a_share_portfolio_settlement_book_source_v1(
        json.loads(canonical_bytes(_book_body(initial)))) == initial
    batch = _financial_batch(25)
    calendars = (_week_calendar(batch.fills[0].venue_id),
                 _week_calendar(batch.fills[1].venue_id))
    friday = build_cn_a_share_portfolio_settlement_development_v1(
        batch=batch, calendars=calendars)
    source = json.loads(canonical_bytes(_book_body(friday.book)))
    assert read_cn_a_share_portfolio_settlement_book_source_v1(source) == friday.book
    due = friday.book.project().pending_obligations[0].obligation.settlement_time
    monday = friday.apply_due(due).book
    assert read_cn_a_share_portfolio_settlement_book_source_v1(
        json.loads(canonical_bytes(_book_body(monday)))) == monday
    assert monday.project().pending_obligations == ()


def test_source_only_book_rejects_hash_and_extra_field_tamper():
    batch = _financial_batch(25)
    friday = build_cn_a_share_portfolio_settlement_development_v1(
        batch=batch, calendars=(_week_calendar(batch.fills[0].venue_id),
                                _week_calendar(batch.fills[1].venue_id)))
    source = json.loads(canonical_bytes(_book_body(friday.book)))
    with pytest.raises(ValueError, match="Book hash"):
        read_cn_a_share_portfolio_settlement_book_source_v1(
            {**source, "book_hash": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="source fields mismatch"):
        read_cn_a_share_portfolio_settlement_book_source_v1({**source, "secret_extra": 1})
    changed = json.loads(canonical_bytes(_book_body(friday.book)))
    position = next(row for row in changed["obligations"] if row["obligation"]["quantity"] is not None)
    position["obligation"]["quantity"]["units"] += 1
    with pytest.raises(ValueError, match="Book hash"):
        read_cn_a_share_portfolio_settlement_book_source_v1(changed)


def test_source_only_book_rejects_foreign_account_and_missing_recorded_event():
    batch = _financial_batch(25)
    friday = build_cn_a_share_portfolio_settlement_development_v1(
        batch=batch, calendars=(_week_calendar(batch.fills[0].venue_id),
                                _week_calendar(batch.fills[1].venue_id)))
    source = json.loads(canonical_bytes(_book_body(friday.book)))
    with pytest.raises(SettlementLifecycleError, match="account mismatch"):
        read_cn_a_share_portfolio_settlement_book_source_v1({**source, "account_id": "foreign"})
    with pytest.raises(SettlementLifecycleError, match="requires one recorded event"):
        read_cn_a_share_portfolio_settlement_book_source_v1({**source, "events": []})
