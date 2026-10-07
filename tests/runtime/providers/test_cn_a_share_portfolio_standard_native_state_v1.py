"""Pure live native-state sentinels, NOT the public October two-week A/B gate."""
from dataclasses import replace
from collections.abc import Mapping

import pytest
import crypto_quant_domain as d
from crypto_quant_trading import (GenericLedger, OrderReservationSchedule,
    OrderReservationUpdate, ReservationCommitment)
from crypto_quant_trading.decisions import DecisionBatchExpectation
from crypto_quant_backtest.cn_a_share_portfolio_standard_native_state_v1 import (
    _native_snapshot_at_v1, _native_signal_target_v1, _native_rebalance_plan_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_financial_development_v1 import (
    book_cn_a_share_portfolio_financial_batch_development_v3,
)
from crypto_quant_backtest.cn_a_share_portfolio_settlement_development_v1 import (
    _build_cn_a_share_portfolio_settlement_native,
)
from tests.runtime.providers.test_cn_a_share_portfolio_standard_definition_v1 import source_definition
from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import _native_n
from tests.runtime.target_stream._fixtures import event as source_event


def _target(source, index, *, selected=None):
    marks = source.signal_marks[index]
    selected = source.scope.instrument_ids if selected is None else selected
    fraction = "0.5" if len(selected) == 2 else "1"
    candidate = {"schema_version": 1, "strategy_id": "cn.native.live", "sleeve_id": "pharma",
        "decision_time": marks.at.instant.epoch_nanoseconds,
        "observed_through": marks.at.instant.epoch_nanoseconds,
        "effective_time": marks.at.instant.epoch_nanoseconds,
        "expires_at": None,
        "targets": [{"instrument_id": {"venue": i.venue.value, "stable_key": i.stable_key},
                     "value": fraction} for i in selected],
        "confidence": "0.9", "reason": "source-frozen development target",
        "evidence": {"source": "synthetic.only"}}
    event = source_event("native-target-" + str(index),
        DecisionBatchExpectation("cn.native.live", d.StrategySleeveId("pharma")),
        instrument_id=source.scope.instrument_ids[0], value="0.5", source_sequence=1,
        payload_override={"schema_version": 1, "candidate": candidate})
    return replace(event, event_time=marks.at.instant, available_time=marks.at.instant,
        phase=marks.at.phase, source_sequence=marks.at.source_sequence)


def _live_prefix():
    source = source_definition()
    scope, journal, schema, at, steps, calendars, bars, witnesses, rules = _native_n(
        2, capital=10_000_000, price_units_by_code={"600000": 1137, "000001": 2231})
    assert journal == source.initial_journal
    batch = book_cn_a_share_portfolio_financial_batch_development_v3(
        portfolio_scope=scope.instrument_ids, prior_journal=journal, ledger_schema=schema,
        cost_basis_policy=source.cost_basis_policy, notional_quantization=source.notional_quantization,
        steps=steps)
    # Friday -> Monday due events precede the second signal phase. No sale cash
    # is made spendable by the snapshot helper; availability is native below.
    clock = d.SimulationInstant(d.UtcInstant(at.epoch_nanoseconds + 3 * 86_400_000_000_000),
        source.signal_marks[0].at.phase, d.SourceSequence(1))
    marks = replace(source.signal_marks[0], at=clock, marks=tuple(replace(m,
        price=replace(m.price, units=m.price.units + 100), observed_at=clock.instant,
        available_at=clock.instant, resolved_at=clock.instant,
        available_at_instant=clock, resolved_at_instant=clock) for m in source.signal_marks[0].marks))
    source = replace(source, signal_marks=(source.signal_marks[0], marks))
    settlement = _build_cn_a_share_portfolio_settlement_native(batch=batch, calendars=calendars)
    settled = settlement.apply_due(clock.instant)
    streams = tuple(step.terminal_order for step in steps)
    schedules = []
    for step in steps:
        stream, fee = step.terminal_order, step.risk.fee
        accepted = next(r.event for r in stream.records if r.event.event_type is d.OrderEventType.ORDER_ACCEPTED)
        proposal = step.risk.proposal
        commitment = ReservationCommitment(cash=(proposal.principal,), fee_reserve=fee.commitment.fee_reserve)
        schedules.append(OrderReservationSchedule(stream.order.order_id, fee.proposal_hash,
            (OrderReservationUpdate(stream.order.order_id, accepted.event_id, accepted.event_type,
                stream.order.intent.quantity, commitment, fee.proposal_hash),)))
    return source, batch, settled.book, streams, tuple(schedules), rules


def test_current_native_equity_and_inventory_feed_w2_sizing_not_initial_zero():
    source, batch, book, streams, schedules, rules = _live_prefix()
    signal = _native_signal_target_v1(inputs=source, journal=batch.journal, event=_target(source, 1))
    assert signal.snapshot.equity != source.scope.initial_cash
    assert signal.snapshot.fees.units > 0
    assert signal.allocation.total_allocation_nav == signal.snapshot.equity
    ledger = GenericLedger(source.scope.ledger_schema).project(batch.journal)
    for target in signal.normalized_target.targets:
        key = d.PositionBalanceKey(source.scope.account_id, target.instrument_id.venue, target.instrument_id)
        assert target.decision.current_quantity == ledger.position_quantity(key)
        assert target.decision.current_quantity.units == 100
    plan = _native_rebalance_plan_v1(inputs=source, signal=signal, journal=batch.journal,
        settlement_book=book, order_streams=streams, reservation_schedules=schedules,
        market_rules=rules, at=source.signal_marks[1].at)
    assert len(plan.planned_orders) == 2
    for order in plan.planned_orders:
        target = next(t for t in signal.normalized_target.targets if t.instrument_id == order.intent.instrument_id)
        assert order.intent.side is d.OrderSide.BUY
        assert order.intent.quantity.units == target.decision.final_quantity.units - 100


def test_native_cash_intent_generates_held_close_orders_but_not_fills():
    source, batch, book, streams, schedules, rules = _live_prefix()
    signal = _native_signal_target_v1(inputs=source, journal=batch.journal, event=_target(source, 1, selected=()))
    assert signal.normalized_target.targets == ()
    plan = _native_rebalance_plan_v1(inputs=source, signal=signal, journal=batch.journal,
        settlement_book=book, order_streams=streams, reservation_schedules=schedules,
        market_rules=rules, at=source.signal_marks[1].at)
    assert len(plan.planned_orders) == 2
    assert all(p.intent.side is d.OrderSide.SELL and p.intent.quantity.units == 100
               and p.intent.reduce_only and p.intent.position_effect is d.PositionEffect.CLOSE
               for p in plan.planned_orders)
    assert len(batch.fills) == 2  # Native planner did NOT sell or change prior Fill facts.


def test_native_cohort_change_closes_absent_holding_and_resizes_intersection():
    source, batch, book, streams, schedules, rules = _live_prefix()
    selected = source.scope.instrument_ids[:1]
    signal = _native_signal_target_v1(inputs=source, journal=batch.journal,
        event=_target(source, 1, selected=selected))
    plan = _native_rebalance_plan_v1(inputs=source, signal=signal, journal=batch.journal,
        settlement_book=book, order_streams=streams, reservation_schedules=schedules,
        market_rules=rules, at=source.signal_marks[1].at)
    held_exit = next(p for p in plan.planned_orders if p.intent.instrument_id not in selected)
    assert held_exit.intent.side is d.OrderSide.SELL
    assert held_exit.intent.quantity.units == 100
    held_resize = next(p for p in plan.planned_orders if p.intent.instrument_id in selected)
    assert held_resize.intent.side is d.OrderSide.BUY
    assert held_resize.intent.quantity.units == signal.normalized_target.targets[0].decision.final_quantity.units - 100


def test_native_target_expiry_is_preserved_and_exclusive_for_later_rebalance():
    source, batch, book, streams, schedules, rules = _live_prefix()
    event = _target(source, 1)
    expires = d.UtcInstant(event.event_time.epoch_nanoseconds + 1)
    payload = event.payload["candidate"]
    assert isinstance(payload, Mapping)
    candidate = dict(payload)
    candidate["expires_at"] = expires.epoch_nanoseconds
    event = replace(event, payload={"schema_version": 1, "candidate": candidate})
    signal = _native_signal_target_v1(inputs=source, journal=batch.journal, event=event)
    at_expiry = d.SimulationInstant(expires, event.phase, event.source_sequence)
    try:
        plan = _native_rebalance_plan_v1(inputs=source, signal=signal, journal=batch.journal,
            settlement_book=book, order_streams=streams, reservation_schedules=schedules,
            market_rules=rules, at=at_expiry)
    except ValueError as error:
        assert "expired" in str(error) or "inactive" in str(error)
    else:
        assert not plan.planned_orders, "accepted target expiry must not be erased into None"

@pytest.mark.parametrize("part", ["prefix", "future_phase", "missing_signal_clock"])
def test_live_signal_rejects_foreign_prefix_future_finance_and_missing_exact_clock(part):
    source, batch, book, streams, schedules, rules = _live_prefix()
    journal = batch.journal
    if part == "prefix":
        journal = replace(journal, entries=journal.entries[1:])
    elif part == "future_phase":
        mark = source.signal_marks[1].at
        late = d.SimulationInstant(mark.instant, d.TimelinePhase(mark.phase.rank + 1, "late_finance"), mark.source_sequence)
        journal = type(journal).from_entries((*journal.entries[:-1], replace(journal.entries[-1], recorded_at=late)))
    else:
        source = replace(source, signal_marks=(source.signal_marks[0],))
    when = _target(source, 1) if part != "missing_signal_clock" else _target(_live_prefix()[0], 1)
    with pytest.raises(ValueError, match="prefix|full-clock"):
        _native_signal_target_v1(inputs=source, journal=journal, event=when)
