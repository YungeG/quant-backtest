"""Two venue Feb-8/Feb-19 synthetic T+1 positions; no executable orders."""
from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, BalanceChange, DomainId, DomainIdKind,
    InstrumentId, Money, OrderSide, PositionBalanceKey, Quantity, Scale,
    SettlementObligation, SimulationInstant, SourceSequence, TimelinePhase, UtcInstant,
)
from crypto_quant_trading import (
    AccountSettlementObligation, CashAvailabilityRule, LedgerBalanceRegistration,
    LedgerSchema, MarketSettlementRules, PositionAvailabilityRule,
    SettlementBook, SettlementEvent, SettlementEventType,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_sellability_v1 import (
    project_cn_a_share_portfolio_sellability_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_funding_development_v1 import (
    build_synthetic_cross_venue_funding_candidate_v1,
)
from tests.runtime.providers.test_cn_a_share_portfolio_funding_development_v1 import (
    ACCOUNT, AT, SCALE, SH, SZ, fixture,
)
from tests.kernel.profiles.cn_a_share._fixtures import settlement_model, settlement_query


def _two_week_sources():
    args = fixture()
    opening = build_synthetic_cross_venue_funding_candidate_v1(**args).journal
    keys = tuple(PositionBalanceKey(
        ACCOUNT, venue.venue_id,
        InstrumentId(venue.venue_id, "600000" if venue == SH else "000001")) for venue in (SH, SZ))
    schema = LedgerSchema((*args["ledger_schema"].registrations,
                           *(LedgerBalanceRegistration(key, Scale(0)) for key in keys)))
    rules = MarketSettlementRules.create(
        policy_key="cn.synthetic.shsz.cash-and-positions.v1", policy_version=1,
        account_id=ACCOUNT, cash_rules=args["settlement_rules"].cash_rules,
        position_rules=tuple(PositionAvailabilityRule(key, False) for key in keys))
    journal = opening
    obligations = []
    events = []
    times = []
    for digit, venue, key in (("a", SH, keys[0]), ("b", SZ, keys[1])):
        query = settlement_query(OrderSide.BUY, venue=venue.venue_id.value)
        resolution = settlement_model(venue.venue_id.value).resolve_settlement(query)
        assert resolution.failure is None and resolution.result is not None
        trade = query.fill.execution_time
        maturity = resolution.result.position_availability_time
        times.append((trade, maturity, resolution.result.next_trading_date.value.isoformat()))
        fill_id = DomainId(DomainIdKind.FILL, f"{DomainIdKind.FILL.prefix}_" + digit * 64)
        journal = journal.append(AccountingJournalEntry(
            DomainId(DomainIdKind.JOURNAL, f"{DomainIdKind.JOURNAL.prefix}_" + digit * 64),
            AccountingEntryType.FILL_BOOKED, ACCOUNT, venue.venue_id,
            trade, SimulationInstant(trade, AT.phase, SourceSequence(1 if venue == SH else 2)),
            (fill_id.value,),
            (BalanceChange(venue, Money(-10_000, SCALE, "CNY")),
             BalanceChange(key, Quantity(100, Scale(0), str(key.instrument_id)))),
            (), (), ()))
        ob = AccountSettlementObligation(
            SettlementObligation(
                DomainId(DomainIdKind.SETTLEMENT, f"{DomainIdKind.SETTLEMENT.prefix}_" + digit * 64), fill_id,
                trade, maturity, key.instrument_id, Quantity(100, Scale(0), str(key.instrument_id)),
                None, None), key)
        obligations.append(ob)
        recorded = SettlementEvent(
            f"settlement-recorded:{digit}", ob.obligation.settlement_obligation_id,
            SettlementEventType.OBLIGATION_RECORDED,
            SimulationInstant(trade, TimelinePhase(60, "settlement"), SourceSequence(1 if venue == SH else 2)),
            fill_id.value, "sha256:" + digit * 64)
        events.append(recorded)
        events.append(SettlementEvent(
            f"settlement-applied:{digit}", ob.obligation.settlement_obligation_id,
            SettlementEventType.SETTLEMENT_APPLIED,
            SimulationInstant(maturity, TimelinePhase(60, "settlement"), SourceSequence(1 if venue == SH else 2)),
            recorded.event_id, "sha256:" + digit * 64))
    return (journal, schema, rules,
            SettlementBook.from_events(ACCOUNT, tuple(obligations), tuple(events)),
            keys, times)


def test_two_week_two_stock_t_plus_one_sellability_uses_both_venue_calendars():
    journal, schema, rules, book, keys, times = _two_week_sources()
    assert [item[2] for item in times] == ["2024-02-19", "2024-02-19"]
    trade, maturity, _ = times[0]
    def project(at):
        return project_cn_a_share_portfolio_sellability_v1(
            journal=journal, ledger_schema=schema, settlement_book=book,
            order_streams=(), reservation_schedules=(), market_rules=rules, as_of=at)
    w = project(UtcInstant(trade.epoch_nanoseconds + 1))
    before_open = project(UtcInstant(maturity.epoch_nanoseconds - 1))
    w_plus_one = project(maturity)
    assert [w.sellable_for(key.instrument_id).units for key in keys] == [0, 0]
    assert [before_open.sellable_for(key.instrument_id).units for key in keys] == [0, 0]
    assert [w_plus_one.sellable_for(key.instrument_id).units for key in keys] == [100, 100]
    assert all(p.total.units == 100 for p in w.positions)
    assert w.snapshot_hash != w_plus_one.snapshot_hash
    assert not w.trade_authorized and not w_plus_one.trade_authorized
    with pytest.raises(ValueError, match="missing unique"):
        w.sellable_for(InstrumentId(SH.venue_id, "other"))


@pytest.mark.parametrize("scale,units", [(Scale(2), 100), (Scale(0), 100)])
def test_pending_quantity_scale_cannot_release_unsettled_integer_shares(scale, units):
    journal, schema, rules, book, keys, times = _two_week_sources()
    obligations = tuple(replace(item, obligation=replace(
        item.obligation, quantity=Quantity(units, scale, str(item.balance_key.instrument_id))))
        for item in book.obligations)
    book = SettlementBook.from_events(ACCOUNT, obligations, book.events)
    kwargs = dict(journal=journal, ledger_schema=schema, settlement_book=book,
                  order_streams=(), reservation_schedules=(), market_rules=rules,
                  as_of=UtcInstant(times[0][0].epoch_nanoseconds + 1))
    if scale == Scale(0):
        assert all(p.sellable.units == 0 for p in project_cn_a_share_portfolio_sellability_v1(**kwargs).positions)
    else:
        with pytest.raises(ValueError):
            project_cn_a_share_portfolio_sellability_v1(**kwargs)


def test_non_integer_registered_position_rejected_even_with_zero_balance():
    journal, schema, rules, book, keys, times = _two_week_sources()
    schema = LedgerSchema(tuple(replace(r, scale=Scale(2)) if r.key in keys else r
                                for r in schema.registrations))
    opening = type(journal).from_entries(journal.entries[:-2])
    with pytest.raises(ValueError):
        project_cn_a_share_portfolio_sellability_v1(
            journal=opening, ledger_schema=schema, settlement_book=book,
            order_streams=(), reservation_schedules=(), market_rules=rules,
            as_of=UtcInstant(times[0][0].epoch_nanoseconds - 1))


def test_direct_snapshot_rejects_non_integer_position():
    journal, schema, rules, book, keys, times = _two_week_sources()
    valid = project_cn_a_share_portfolio_sellability_v1(
        journal=journal, ledger_schema=schema, settlement_book=book,
        order_streams=(), reservation_schedules=(), market_rules=rules, as_of=times[0][1])
    positions = tuple(replace(p, total=Quantity(10000, Scale(2), str(p.key.instrument_id)),
                             sellable=Quantity(10000, Scale(2), str(p.key.instrument_id)))
                      for p in valid.positions)
    with pytest.raises(ValueError):
        replace(valid, positions=positions)



def test_audit_scale_2_position_cannot_make_t_plus_one_sellable_shares():
    journal, schema, rules, book, keys, times = _two_week_sources()
    # Same economic 100 shares, but incompatible integer-unit dimensions.
    schema = LedgerSchema(tuple(replace(r, scale=Scale(2)) if r.key in keys else r
                                for r in schema.registrations))
    journal = type(journal).from_entries(tuple(replace(entry, balance_changes=tuple(
        replace(change, value=Quantity(10000, Scale(2), str(change.key.instrument_id)))
        if isinstance(change.key, PositionBalanceKey) else change
        for change in entry.balance_changes)) for entry in journal.entries))
    with pytest.raises(ValueError):
        project_cn_a_share_portfolio_sellability_v1(
            journal=journal, ledger_schema=schema, settlement_book=book,
            order_streams=(), reservation_schedules=(), market_rules=rules,
            as_of=UtcInstant(times[0][0].epoch_nanoseconds + 1))


def test_pending_and_direct_position_reject_matching_scale_wrong_instrument():
    from crypto_quant_trading import PositionAvailability
    from crypto_quant_trading.settlement import AvailabilityEvidenceError

    journal, schema, rules, book, keys, times = _two_week_sources()
    first = book.obligations[0]
    wrong = next(key for key in keys if key != first.balance_key)
    with pytest.raises(ValueError):
        replace(first, obligation=replace(first.obligation, quantity=Quantity(
            100, Scale(0), str(wrong.instrument_id))))
    with pytest.raises(AvailabilityEvidenceError):
        PositionAvailability(keys[0], Quantity(100, Scale(0), str(keys[1].instrument_id)),
                             Quantity(0, Scale(0), str(keys[0].instrument_id)))
