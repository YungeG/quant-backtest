"""Kernel-only versioned CN portfolio intents; NO Runtime admission or economic fills."""
from __future__ import annotations

from dataclasses import replace
import pytest

from crypto_quant_domain import (
    Money, OrderEventType, OrderSide, PositionEffect, Quantity, Scale, TimeInForce,
    UtcInstant,
)
from crypto_quant_trading import (
    AccountingJournal, OrderEventRecord, OrderEventStream, OrderReservationSchedule,
    OrderReservationUpdate, ReservationCommitment,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_order_plan_v1 import (
    CnASharePortfolioOrderPlanV1, CnASharePortfolioOrderProposalV1,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_rebalance_policy_v1 import CnAShareRebalanceExecutionPolicyV1
from crypto_quant_trading.profiles.cn_a_share.shared_cny_cash_v1 import project_cn_a_share_shared_cny_cash_v1
from crypto_quant_trading.profiles.cn_a_share.portfolio_sellability_v1 import project_cn_a_share_portfolio_sellability_v1
from tests.kernel.profiles.cn_a_share.test_portfolio_sellability_v1 import _two_week_sources
from tests.kernel.orders._fixtures import event, full_lifecycle_records, order
from tests.runtime.providers.test_cn_a_share_portfolio_funding_development_v1 import ACCOUNT, SCALE

POLICY = CnAShareRebalanceExecutionPolicyV1.create("cn.pharma.weekly")
FEE_HASH = "sha256:" + "f" * 64  # Clearly synthetic; not brokerage/route authority.
TARGET_W = "normalized-portfolio-target-v2:sha256:" + "1" * 64
TARGET_W1 = "normalized-portfolio-target-v2:sha256:" + "2" * 64


def _sources(journal, schema, rules, book, at, streams=(), schedules=()):
    return (
        project_cn_a_share_shared_cny_cash_v1(
            journal=journal, ledger_schema=schema, settlement_book=book,
            order_streams=streams, reservation_schedules=schedules,
            market_rules=rules, as_of=at),
        project_cn_a_share_portfolio_sellability_v1(
            journal=journal, ledger_schema=schema, settlement_book=book,
            order_streams=streams, reservation_schedules=schedules,
            market_rules=rules, as_of=at),
    )


def _proposal(digit, key, target, side, principal=0, fee=100):
    base = order(digit)
    intent = replace(
        base.intent, instrument_id=key.instrument_id,
        quantity=Quantity(100, Scale(0), str(key.instrument_id)),
        side=side, parent_id=target,
        time_in_force=TimeInForce.GTC if side is OrderSide.SELL else TimeInForce.DAY,
        reduce_only=side is OrderSide.SELL,
        position_effect=PositionEffect.CLOSE if side is OrderSide.SELL else PositionEffect.OPEN,
    )
    return CnASharePortfolioOrderProposalV1(
        intent, Money(principal, SCALE, "CNY"), Money(fee, SCALE, "CNY"), FEE_HASH)


def _plan(target, at, cash, sellability, proposals=(), streams=(), schedules=()):
    return CnASharePortfolioOrderPlanV1.create(
        account_id=ACCOUNT, target_id=target, target_hash="sha256:" + "7" * 64,
        as_of=at, policy=POLICY, cash=cash, sellability=sellability,
        working_orders=streams, reservation_schedules=schedules, proposed=proposals)


def _accepted(proposal, digit, fee=100):
    base = order(digit)
    subject = replace(base, account_id=ACCOUNT, intent=proposal.intent)
    records = full_lifecycle_records(subject)[:8]
    stream = OrderEventStream.from_records(subject, records)
    commitment = ReservationCommitment(
        cash=((proposal.principal,) if proposal.principal.units else ()),
        sellable_quantities=((proposal.intent.quantity,) if proposal.intent.side is OrderSide.SELL else ()),
        fee_reserve=(Money(fee, SCALE, "CNY"),), order_capacity_units=1)
    schedule = OrderReservationSchedule(
        subject.order_id, "sha256:" + "a" * 64,
        (OrderReservationUpdate(subject.order_id, records[-1].event.event_id,
                                OrderEventType.ORDER_ACCEPTED, subject.intent.quantity,
                                commitment, "sha256:" + "b" * 64),))
    return stream, schedule, records, subject


def test_two_week_two_stock_side_tif_t_plus_one_and_no_prefinance():
    journal, schema, rules, book, keys, times = _two_week_sources()
    trade, maturity, _ = times[0]
    opening = AccountingJournal.from_entries(journal.entries[:-2])
    w_at = UtcInstant(trade.epoch_nanoseconds - 1)
    cash_w, pos_w = _sources(opening, schema, rules, book, w_at)
    w_buys = (_proposal("1", keys[0], TARGET_W, OrderSide.BUY, 10_000),
              _proposal("2", keys[1], TARGET_W, OrderSide.BUY, 10_000))
    plan_w = _plan(TARGET_W, w_at, cash_w, pos_w, w_buys)
    assert [p.intent.time_in_force for p in plan_w.proposed] == [TimeInForce.DAY] * 2
    assert plan_w.plan_id.startswith("cn-a-share-portfolio-order-plan-v1:")
    assert not plan_w.trade_authorized and plan_w == _plan(TARGET_W, w_at, cash_w, pos_w, w_buys)

    w_plus_one = maturity
    sh_sell = _proposal("3", keys[0], TARGET_W1, OrderSide.SELL)
    sz_sell = _proposal("4", keys[1], TARGET_W1, OrderSide.SELL)
    before = UtcInstant(maturity.epoch_nanoseconds - 1)
    cash_before, pos_before = _sources(journal, schema, rules, book, before)
    with pytest.raises(ValueError, match="T\\+1"):
        _plan(TARGET_W1, before, cash_before, pos_before, (sh_sell, sz_sell))
    cash_after, pos_after = _sources(journal, schema, rules, book, w_plus_one)
    plan = _plan(TARGET_W1, w_plus_one, cash_after, pos_after, (sz_sell, sh_sell))
    assert [p.intent.side for p in plan.proposed] == [OrderSide.SELL] * 2
    assert [p.intent.time_in_force for p in plan.proposed] == [TimeInForce.GTC] * 2
    # Prospective sell proceeds are not included in spendable cash for the buy.
    unfunded = _proposal("5", keys[1], TARGET_W1, OrderSide.BUY, 80_001, 100)
    with pytest.raises(ValueError, match="prefinance"):
        _plan(TARGET_W1, w_plus_one, cash_after, pos_after, (sh_sell, unfunded))
    with pytest.raises(ValueError, match="TIF"):
        _plan(TARGET_W1, w_plus_one, cash_after, pos_after,
              (replace(sh_sell, intent=replace(sh_sell.intent, time_in_force=TimeInForce.DAY)),))


def test_new_target_cancels_blocked_gtc_sell_and_expired_day_buy_does_not_roll():
    journal, schema, rules, book, keys, times = _two_week_sources()
    at = times[0][1]
    old_sell = _proposal("6", keys[0], TARGET_W, OrderSide.SELL)
    gtc, sell_schedule, _, _ = _accepted(old_sell, "6")
    old_buy = _proposal("7", keys[1], TARGET_W, OrderSide.BUY, 10_000)
    active_buy, buy_schedule, records, subject = _accepted(old_buy, "7")
    expired = OrderEventRecord(event(subject, "expired-day", OrderEventType.ORDER_EXPIRED,
                                     90, records[-1].event.event_id))
    day_stream = OrderEventStream.from_records(subject, records + (expired,))
    streams = (gtc, day_stream)
    schedules = (sell_schedule, buy_schedule)
    cash, pos = _sources(journal, schema, rules, book, at, streams, schedules)
    assert pos.sellable_for(keys[0].instrument_id).units == 0
    assert cash.reserved_fees.units == 100  # Expired DAY fee reservation released.
    same = _plan(TARGET_W, at, cash, pos, streams=streams, schedules=schedules)
    assert same.retained_working_order_ids == (gtc.order.order_id,)
    assert not same.cancel_intents
    next_target = _plan(TARGET_W1, at, cash, pos, streams=streams, schedules=schedules)
    assert [c.order_id for c in next_target.cancel_intents] == [gtc.order.order_id]
    assert [c.reason_code for c in next_target.cancel_intents] == ["prior_target_superseded"]
    assert not next_target.retained_working_order_ids
    assert next_target.plan_id != same.plan_id
    # Cannot race a replacement sell until prior GTC cancellation is confirmed.
    with pytest.raises(ValueError, match="cannot replan"):
        _plan(TARGET_W1, at, cash, pos,
              (_proposal("8", keys[0], TARGET_W1, OrderSide.SELL),), streams, schedules)
    # Plan input cannot silently omit the active reservation evidence.
    cash_unbound, pos_unbound = _sources(journal, schema, rules, book, at)
    with pytest.raises(ValueError, match="reservation prefix"):
        _plan(TARGET_W1, at, cash_unbound, pos_unbound, streams=streams, schedules=schedules)
