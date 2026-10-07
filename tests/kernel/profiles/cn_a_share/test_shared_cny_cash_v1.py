"""Two-stock synthetic XSHG/XSHE cash guard; no executed portfolio Backtest."""
from __future__ import annotations

from dataclasses import replace
import pytest

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, BalanceChange, DomainId, DomainIdKind,
    InstrumentId, Money, Quantity, Scale, SimulationInstant, SourceSequence, UtcInstant,
)
from crypto_quant_trading import (
    AvailabilityEvidenceError, AvailabilityProjection, GenericLedger,
    OrderEventStream, OrderReservationSchedule, OrderReservationUpdate,
    ReservationCommitment, ResourceReservationBook, SettlementBook,
)
from crypto_quant_domain import OrderEventType
from crypto_quant_trading.profiles.cn_a_share.shared_cny_cash_v1 import (
    project_cn_a_share_shared_cny_cash_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_funding_development_v1 import (
    build_synthetic_cross_venue_funding_candidate_v1,
)
from tests.runtime.providers.test_cn_a_share_portfolio_funding_development_v1 import (
    ACCOUNT, AT, SCALE, SH, SZ, fixture,
)
from tests.kernel.orders._fixtures import full_lifecycle_records, order
from tests.kernel.settlement._fixtures import applied_event, registered_obligation, recorded_event


def _accepted(digit: str, key, principal: int, fee: int):
    instrument = InstrumentId(key.venue_id, "600000" if key == SH else "000001")
    base = order(digit)
    subject = replace(base, account_id=ACCOUNT, intent=replace(
        base.intent, instrument_id=instrument, quantity=Quantity(100, Scale(0), str(instrument))))
    records = full_lifecycle_records(subject)[:8]
    commitment = ReservationCommitment(
        cash=(Money(principal, SCALE, "CNY"),),
        fee_reserve=(Money(fee, SCALE, "CNY"),), order_capacity_units=1)
    schedule = OrderReservationSchedule(
        subject.order_id, "sha256:" + "a" * 64, (
            OrderReservationUpdate(subject.order_id, records[-1].event.event_id,
                                   OrderEventType.ORDER_ACCEPTED, subject.intent.quantity,
                                   commitment, "sha256:" + "b" * 64),))
    return OrderEventStream.from_records(subject, records), schedule


def _project(args, journal, orders=(), schedules=(), book=None, at=None):
    chosen_book = book if book is not None else args["settlement_book"]
    if at is None:
        latest = [journal.entries[-1].recorded_at.instant.epoch_nanoseconds]
        latest.extend(e.occurred_at.instant.epoch_nanoseconds for e in chosen_book.events)
        latest.extend(s.state.updated_at.instant.epoch_nanoseconds
                      for s in orders if s.state is not None)
        at = UtcInstant(max(latest) + 1)
    return project_cn_a_share_shared_cny_cash_v1(
        journal=journal, ledger_schema=args["ledger_schema"],
        settlement_book=chosen_book, order_streams=orders,
        reservation_schedules=schedules, market_rules=args["settlement_rules"], as_of=at)


def test_two_stock_same_account_no_double_spend_and_pending_sale_not_prefinanced():
    args = fixture()
    journal = build_synthetic_cross_venue_funding_candidate_v1(**args).journal
    empty = _project(args, journal)
    assert empty.total.units == 100_000 and empty.spendable.units == 100_000
    assert not empty.trade_authorized
    sh, sh_schedule = _accepted("6", SH, 50_000, 1_000)
    reserved = _project(args, journal, (sh,), (sh_schedule,))
    # Legacy venue-local projection must not silently allocate currency-only reservations.
    with pytest.raises(AvailabilityEvidenceError, match="one unique Cash rule owner"):
        AvailabilityProjection().project(
            GenericLedger(args["ledger_schema"]).project(journal),
            args["settlement_book"].project(),
            ResourceReservationBook(ACCOUNT).project((sh,), (sh_schedule,)),
            args["settlement_rules"],
        )
    assert reserved.reserved_principal.units == 50_000
    assert reserved.reserved_fees.units == 1_000
    assert reserved.spendable.units == 49_000
    assert reserved.can_fund_buy(principal=Money(48_000, SCALE, "CNY"), estimated_fee=Money(1_000, SCALE, "CNY"))
    assert not reserved.can_fund_buy(principal=Money(49_000, SCALE, "CNY"), estimated_fee=Money(1, SCALE, "CNY"))
    sz, sz_schedule = _accepted("7", SZ, 50_000, 1_000)
    with pytest.raises(ValueError, match="overcommitted"):
        _project(args, journal, (sh, sz), (sh_schedule, sz_schedule))

    receipt = registered_obligation("2", key=SZ, units=20_000, settlement_time=200)
    recorded = recorded_event(receipt, "2", sequence=1)
    book = SettlementBook.from_events(ACCOUNT, (receipt,), (recorded,))
    booked_sale = AccountingJournalEntry(
        DomainId(DomainIdKind.JOURNAL, "jnl_" + "f" * 64), AccountingEntryType.FILL_BOOKED,
        ACCOUNT, SZ.venue_id, UtcInstant(100),
        SimulationInstant(UtcInstant(100), AT.phase, SourceSequence(1)),
        (receipt.obligation.source_fill_id.value,),
        (BalanceChange(SZ, Money(20_000, SCALE, "CNY")),), (), (), ())
    pending = _project(args, journal.append(booked_sale), (sh,), (sh_schedule,), book)
    assert pending.total.units == 120_000
    assert pending.unsettled_receivables.units == 20_000
    assert pending.spendable.units == 49_000
    assert not pending.can_fund_buy(principal=Money(50_000, SCALE, "CNY"), estimated_fee=Money(1, SCALE, "CNY"))
    settled = SettlementBook.from_events(
        ACCOUNT, (receipt,), (recorded, applied_event(receipt, recorded, "2", occurred_at=200)))
    after_settlement = _project(args, journal.append(booked_sale), (sh,), (sh_schedule,), settled)
    assert _project(args, journal.append(booked_sale), (sh,), (sh_schedule,), settled,
                    at=UtcInstant(101)).unsettled_receivables.units == 20_000
    assert after_settlement.unsettled_receivables.units == 0
    assert after_settlement.spendable.units == 69_000
    assert after_settlement.can_fund_buy(
        principal=Money(50_000, SCALE, "CNY"), estimated_fee=Money(1, SCALE, "CNY"))


def test_ledger_fee_charge_reduces_shared_pool_without_order_reservation():
    args = fixture()
    journal = build_synthetic_cross_venue_funding_candidate_v1(**args).journal
    fee = AccountingJournalEntry(
        DomainId(DomainIdKind.JOURNAL, "jnl_" + "e" * 64), AccountingEntryType.FEE_CHARGED,
        ACCOUNT, SH.venue_id, UtcInstant(100),
        SimulationInstant(UtcInstant(100), AT.phase, SourceSequence(1)),
        ("synthetic-fee-expense",),
        (BalanceChange(SH, Money(-1_000, SCALE, "CNY")),),
        (), (Money(1_000, SCALE, "CNY"),), ())
    snapshot = _project(args, journal.append(fee))
    assert snapshot.total.units == 99_000
    assert snapshot.spendable.units == 99_000
    with pytest.raises(ValueError, match="principal/fee"):
        snapshot.can_fund_buy(principal=Money(100, SCALE, "USD"), estimated_fee=Money(0, SCALE, "CNY"))
