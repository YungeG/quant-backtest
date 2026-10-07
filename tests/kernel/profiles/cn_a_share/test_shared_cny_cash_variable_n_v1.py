"""Ten-instrument shared-CNY reservation guard; NOT ten-stock Engine execution."""
from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, BalanceChange, CashBalanceKey,
    CurrencyId, DomainId, DomainIdKind, Money, Quantity, Scale,
    SimulationInstant, SourceSequence, TimelinePhase, UtcInstant, VenueId,
    OrderEventType,
)
from crypto_quant_trading import (
    AccountingJournal, CashAvailabilityRule, CashReservationUse,
    MarketSettlementRules, OrderEventStream, OrderReservationSchedule,
    OrderReservationUpdate, PositionAvailabilityRule, ReservationCommitment, SettlementBook,
)
from crypto_quant_trading.profiles.cn_a_share.shared_cny_cash_v1 import (
    project_cn_a_share_shared_cny_cash_v1,
)
from tests.kernel.orders._fixtures import full_lifecycle_records, order
from tests.runtime.providers.test_cn_a_share_portfolio_preparation_inputs_v1 import _CODES, _inputs


def _ten_inputs(*, last_principal=9_000):
    scope, _, _ = _inputs(_CODES)
    account = scope.account_id
    cash_keys = tuple(r.key for r in scope.ledger_schema.cash_registrations
                      if isinstance(r.key, CashBalanceKey))
    sh_cash = next(key for key in cash_keys if key.venue_id.value == "xshg")
    deposit = AccountingJournalEntry(
        DomainId(DomainIdKind.JOURNAL, "jnl_" + "1" * 64),
        AccountingEntryType.CAPITAL_DEPOSITED, account, VenueId("xshg"),
        UtcInstant(9), SimulationInstant(UtcInstant(10), TimelinePhase(40, "accounting"), SourceSequence(1)),
        ("synthetic-ten-stock-initial-cash",),
        (BalanceChange(sh_cash, Money(100_000, Scale(2), "CNY")),),
        (), (), (),
    )
    journal = AccountingJournal.from_entries((deposit,))
    rules = MarketSettlementRules.create(
        policy_key="cn.synthetic.variable-n.cash.v1", policy_version=1, account_id=account,
        cash_rules=tuple(CashAvailabilityRule(
            key=key, pending_receivable_tradable=False, pending_receivable_withdrawable=False,
            pending_receivable_margin_eligible=False,
            tradable_reservation_uses=(CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            withdrawable_reservation_uses=(CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            available_margin_reservation_uses=(),
        ) for key in cash_keys),
        position_rules=tuple(PositionAvailabilityRule(r.key, False)
            for r in scope.ledger_schema.registrations if not isinstance(r.key, CashBalanceKey)),
    )
    streams = []
    schedules = []
    for index, instrument in enumerate(scope.instrument_ids, 1):
        digit = f"{index:x}"
        original = order(digit)
        subject = replace(original, account_id=account,
                          intent=replace(original.intent, instrument_id=instrument,
                                         quantity=Quantity(100, Scale(0), str(instrument))))
        records = full_lifecycle_records(subject)[:8]
        stream = OrderEventStream.from_records(subject, records)
        principal = last_principal if index == 10 else 9_000
        commitment = ReservationCommitment(
            cash=(Money(principal, Scale(2), "CNY"),),
            fee_reserve=(Money(5, Scale(2), "CNY"),), order_capacity_units=1)
        schedule = OrderReservationSchedule(subject.order_id, "sha256:" + "a" * 64,
            (OrderReservationUpdate(subject.order_id, records[-1].event.event_id,
                                    OrderEventType.ORDER_ACCEPTED, subject.intent.quantity,
                                    commitment, "sha256:" + "b" * 64),))
        streams.append(stream)
        schedules.append(schedule)
    at = UtcInstant(max(stream.state.updated_at.instant.epoch_nanoseconds
                        for stream in streams if stream.state is not None) + 1)
    return scope, journal, rules, tuple(streams), tuple(schedules), at


def test_ten_native_order_reservations_share_one_cny_pool_without_fill_or_nav():
    scope, journal, rules, streams, schedules, at = _ten_inputs()
    snapshot = project_cn_a_share_shared_cny_cash_v1(
        journal=journal, ledger_schema=scope.ledger_schema, settlement_book=SettlementBook(scope.account_id),
        order_streams=streams, reservation_schedules=schedules, market_rules=rules, as_of=at)
    assert snapshot.total.units == 100_000
    assert snapshot.reserved_principal.units == 90_000
    assert snapshot.reserved_fees.units == 50
    assert snapshot.spendable.units == 9_950
    assert not snapshot.trade_authorized
    scope, journal, rules, streams, schedules, at = _ten_inputs(last_principal=20_000)
    with pytest.raises(ValueError, match="overcommitted"):
        project_cn_a_share_shared_cny_cash_v1(
            journal=journal, ledger_schema=scope.ledger_schema, settlement_book=SettlementBook(scope.account_id),
            order_streams=streams, reservation_schedules=schedules, market_rules=rules, as_of=at)
