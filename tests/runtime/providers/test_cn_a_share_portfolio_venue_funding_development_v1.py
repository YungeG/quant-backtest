"""In-memory live funding planner guards; no Engine or completed Backtest."""
from dataclasses import replace
from typing import Any

import pytest
from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, BalanceChange, DomainId, DomainIdKind,
    Money, SimulationInstant, SourceSequence, TimelinePhase, UtcInstant,
)
from crypto_quant_trading import AccountingJournal, GenericLedger, SettlementBook
from crypto_quant_backtest.cn_a_share_portfolio_funding_development_v1 import build_synthetic_cross_venue_funding_candidate_v1
from crypto_quant_backtest.cn_a_share_portfolio_venue_funding_development_v1 import plan_cn_portfolio_venue_funding_development_v1 as plan
from tests.runtime.providers.test_cn_a_share_portfolio_funding_development_v1 import ACCOUNT, SCALE, SH, SZ, fixture
from tests.kernel.profiles.cn_a_share.test_shared_cny_cash_v1 import _accepted
from tests.kernel.settlement._fixtures import applied_event, recorded_event, registered_obligation


def args(*, at=1000) -> dict[str, Any]:
    source = fixture()
    journal = build_synthetic_cross_venue_funding_candidate_v1(**source).journal
    return dict(journal=journal, ledger_schema=source["ledger_schema"], settlement_book=source["settlement_book"],
                order_streams=(), reservation_schedules=(), market_rules=source["settlement_rules"],
                at=SimulationInstant(UtcInstant(at), TimelinePhase(61, "venue_funding"), SourceSequence(0)),
                target_hash="sha256:" + "a" * 64)


def requirement(sh, sz):
    return ((SH, Money(sh, SCALE, "CNY")), (SZ, Money(sz, SCALE, "CNY")))


def test_planner_is_append_free_atomic_deterministic_and_protects_both_venues(monkeypatch):
    facts = args()
    def forbidden(*args, **kwargs):
        raise AssertionError("planner appended native facts")
    with monkeypatch.context() as m:
        m.setattr(AccountingJournal, "append_many", forbidden)
        entries = plan(**facts, required_by_venue=requirement(20_000, 70_000))
        assert plan(**facts, required_by_venue=requirement(20_000, 70_000)) == entries
    assert len(entries) == 2
    assert entries[0].source_ids == entries[1].source_ids
    assert sum(e.balance_changes[0].value.units for e in entries) == 0
    after = facts["journal"].append_many(entries)
    ledger = GenericLedger(facts["ledger_schema"]).project(after)
    assert (ledger.cash_amount(SH).units, ledger.cash_amount(SZ).units) == (30_000, 70_000)
    assert after.cursor_at(facts["journal"].entry_count).prefix_hash == facts["journal"].journal_hash
    assert plan(**{**facts, "journal": after, "at": replace(facts["at"], source_sequence=SourceSequence(3))},
                required_by_venue=requirement(20_000, 70_000)) == ()


def test_live_reservations_and_fee_commitments_cannot_be_transferred_away():
    facts = args()
    stream, schedule = _accepted("6", SH, 50_000, 1_000)
    facts.update(order_streams=(stream,), reservation_schedules=(schedule,))
    entries = plan(**facts, required_by_venue=requirement(0, 49_000))
    assert entries[0].balance_changes[0].value.units == -9_000
    with pytest.raises(ValueError, match="settled unreserved"):
        plan(**facts, required_by_venue=requirement(0, 50_000))


def test_pending_sale_is_unavailable_until_native_settlement_applies():
    facts = args(at=150)
    receipt = registered_obligation("2", key=SZ, units=20_000, settlement_time=200)
    recorded = recorded_event(receipt, "2", sequence=1)
    book = SettlementBook.from_events(ACCOUNT, (receipt,), (recorded,))
    sale = AccountingJournalEntry(DomainId(DomainIdKind.JOURNAL, "jnl_" + "f" * 64),
        AccountingEntryType.FILL_BOOKED, ACCOUNT, SZ.venue_id, UtcInstant(100),
        SimulationInstant(UtcInstant(100), facts["at"].phase, SourceSequence(1)),
        (receipt.obligation.source_fill_id.value,), (BalanceChange(SZ, Money(20_000, SCALE, "CNY")),), (), (), ())
    stream, schedule = _accepted("6", SH, 50_000, 1_000)
    facts.update(journal=facts["journal"].append(sale), settlement_book=book,
                 order_streams=(stream,), reservation_schedules=(schedule,))
    with pytest.raises(ValueError, match="settled unreserved"):
        plan(**facts, required_by_venue=requirement(0, 50_000))
    applied = SettlementBook.from_events(ACCOUNT, (receipt,),
        (recorded, applied_event(receipt, recorded, "2", occurred_at=200)))
    entries = plan(**{**facts, "settlement_book": applied, "at": replace(facts["at"], instant=UtcInstant(1000))},
                   required_by_venue=requirement(0, 68_000))
    assert entries[0].balance_changes[0].value.units == -8_000


def test_booked_fees_and_same_instant_future_phases_are_not_free_cash():
    facts = args()
    fee = AccountingJournalEntry(DomainId(DomainIdKind.JOURNAL, "jnl_" + "e" * 64),
        AccountingEntryType.FEE_CHARGED, ACCOUNT, SH.venue_id, UtcInstant(100),
        SimulationInstant(UtcInstant(100), facts["at"].phase, SourceSequence(1)), ("modeled-fee",),
        (BalanceChange(SH, Money(-1_000, SCALE, "CNY")),), (), (Money(1_000, SCALE, "CNY"),), ())
    with pytest.raises(ValueError, match="settled unreserved"):
        plan(**{**facts, "journal": facts["journal"].append(fee)}, required_by_venue=requirement(59_000, 41_000))
    future = replace(fee, recorded_at=replace(facts["at"], phase=TimelinePhase(90, "fee")))
    with pytest.raises(ValueError, match="future source facts"):
        plan(**{**facts, "journal": facts["journal"].append(future)}, required_by_venue=requirement(0, 1))


@pytest.mark.parametrize("required", [((SH, Money(1, SCALE, "CNY")),), requirement(-1, 0),
                                      ((SH, Money(1, SCALE, "CNY")), (SH, Money(1, SCALE, "CNY"))),
                                      ((SH, Money(1, SCALE, "USD")), (SZ, Money(1, SCALE, "CNY")))])
def test_funding_scope_or_money_mismatch_fails_closed(required):
    with pytest.raises(ValueError, match="requirements must exact-cover"):
        plan(**args(), required_by_venue=required)
