"""N distinct A-shares through one native DEVELOPMENT Fill/Fee/Journal/Book core.

Synthetic tariff and Bar sources only. Not an N-stock Engine Result or NAV.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest.cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialStepDevelopmentV1, CnASharePortfolioNoFillDevelopmentV1,
    book_cn_a_share_portfolio_financial_batch_development_v2,
)
from crypto_quant_backtest.cn_a_share_portfolio_funding_development_v1 import (
    build_synthetic_cross_venue_funding_candidate_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_next_open_development_v1 import (
    evaluate_cn_a_share_portfolio_next_open_development_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_settlement_development_v1 import (
    build_cn_a_share_portfolio_settlement_development_v2,
)
from crypto_quant_backtest.execution import BarOpenObservation, NoEligibleBarAction
from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, BalanceChange, CashBalanceKey,
    CurrencyId, DomainId, DomainIdKind, Money, OrderEventType, OrderSide,
    PositionBalanceKey, Quantity, Scale, SimulationInstant, SourceSequence,
    TimelinePhase, UtcInstant, VenueId, canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal, CashAvailabilityRule, CashReservationUse,
    FeeReservationEstimator, MarketSettlementRules, OrderEventRecord,
    OrderEventStream, OrderReservationSchedule, OrderReservationUpdate,
    PositionAvailabilityRule, ReservationCommitment, ResourceReservationBook,
    SettlementBook,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_order_plan_v1 import CnASharePortfolioOrderPlanV1
from crypto_quant_trading.profiles.cn_a_share.portfolio_sellability_v1 import project_cn_a_share_portfolio_sellability_v1
from crypto_quant_trading.profiles.cn_a_share.shared_cny_cash_v1 import project_cn_a_share_shared_cny_cash_v1
from tests.kernel.orders._fixtures import event, full_lifecycle_records, order
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    QUANTIZATION, fee_query, final_fill_rule_set, final_order_rule_set,
    local_instant, market_rule_approval, policies, reservation_rule_set,
)
from tests.kernel.profiles.cn_a_share.test_portfolio_order_plan_v1 import POLICY, TARGET_W, TARGET_W1, _proposal
from tests.runtime.execution._fixtures import bar_event
from tests.runtime.providers.test_cn_a_share_portfolio_fill_fee_journal_development_v1 import POLICY as COST_BASIS
from tests.runtime.providers.test_cn_a_share_portfolio_next_open_development_v1 import _open_source
from tests.runtime.providers.test_cn_a_share_portfolio_preparation_inputs_v1 import _CODES, _inputs
from tests.runtime.providers.test_cn_a_share_portfolio_settlement_development_v1 import _week_calendar


def _native_n(count: int, *, omit_last_open=False, capital=1_000_000,
              account_id="pharma.cash.account", instrument_codes=None, price_units_by_code=None,
              at_override=None, calendars_override=None, quantity_units_by_code=None, scope_codes=None):
    codes = ((_CODES[0], _CODES[4]) if count == 2 else
             (_CODES[0], _CODES[1], _CODES[4]) if count == 3 else _CODES)
    if instrument_codes is not None:
        assert len(instrument_codes) == count
        codes = instrument_codes
    prices = price_units_by_code or {}
    scope, _, _ = _inputs(codes if scope_codes is None else scope_codes, account_id=account_id)
    account, schema = scope.account_id, scope.ledger_schema
    cash_keys = tuple(reg.key for reg in schema.cash_registrations
                      if isinstance(reg.key, CashBalanceKey))
    sh = next(key for key in cash_keys if key.venue_id.value == "xshg")
    sz = next(key for key in cash_keys if key.venue_id.value == "xshe")
    entry = AccountingJournalEntry(
        DomainId(DomainIdKind.JOURNAL, "jnl_" + "1" * 64),
        AccountingEntryType.CAPITAL_DEPOSITED, account, sh.venue_id,
        UtcInstant(9), SimulationInstant(UtcInstant(10), TimelinePhase(40, "accounting"), SourceSequence(1)),
        ("synthetic-variable-n-capital",), (BalanceChange(sh, Money(capital, Scale(2), "CNY")),),
        (), (), (),
    )
    journal = AccountingJournal.from_entries((entry,))
    rules = MarketSettlementRules.create(
        policy_key="cn.synthetic.variable-n.venue-cash.v1", policy_version=1, account_id=account,
        cash_rules=tuple(CashAvailabilityRule(
            key=key, pending_receivable_tradable=False, pending_receivable_withdrawable=False,
            pending_receivable_margin_eligible=False,
            tradable_reservation_uses=(CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            withdrawable_reservation_uses=(CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            available_margin_reservation_uses=(),
        ) for key in cash_keys),
        position_rules=tuple(PositionAvailabilityRule(reg.key, False)
            for reg in schema.registrations if isinstance(reg.key, PositionBalanceKey)),
    )
    from tests.runtime.providers.test_cn_a_share_portfolio_funding_development_v1 import AT
    funding = build_synthetic_cross_venue_funding_candidate_v1(
        prior_journal=journal, ledger_schema=schema, settlement_book=SettlementBook(account),
        reservation_streams=(), reservation_schedules=(), settlement_rules=rules,
        source_key=sh, destination_key=sz, amount=Money(capital // 2, Scale(2), "CNY"),
        transfer_key="n-stocks-initial", at=AT, expected_prior_hash=journal.journal_hash)
    journal = funding.journal
    at = at_override or local_instant(25, 10)
    before = UtcInstant(at.epoch_nanoseconds - 1)

    def snapshots(when, streams=(), schedules=()):
        book = SettlementBook(account)
        return (
            project_cn_a_share_shared_cny_cash_v1(
                journal=journal, ledger_schema=schema, settlement_book=book,
                order_streams=streams, reservation_schedules=schedules,
                market_rules=rules, as_of=when),
            project_cn_a_share_portfolio_sellability_v1(
                journal=journal, ledger_schema=schema, settlement_book=book,
                order_streams=streams, reservation_schedules=schedules,
                market_rules=rules, as_of=when),
        )

    cash, sellable = snapshots(before)
    prepared = []
    selected = tuple(i for i in scope.instrument_ids if i.stable_key + (
        ".SH" if i.venue.value == "xshg" else ".SZ") in codes)
    for index, instrument in enumerate(selected, 1):
        digit = f"{index:x}"
        key = PositionBalanceKey(account, instrument.venue, instrument)
        definition = scope.instrument_catalog.instrument(instrument)
        fee_rules = reservation_rule_set(
            side=OrderSide.BUY, effective_at=at, venue=instrument.venue.value,
            instrument_definition=definition)
        price_units = prices.get(instrument.stable_key, 400)
        units = (quantity_units_by_code or {}).get(instrument.stable_key, 100)
        prop = replace(_proposal(digit, key, TARGET_W, OrderSide.BUY, units * price_units, 506),
                       fee_authority_hash=fee_rules.rule_set_hash)
        if units != 100:
            prop = replace(prop, intent=replace(prop.intent,
                quantity=Quantity(units, prop.intent.quantity.scale, str(instrument))))
        if price_units_by_code is not None:
            subject = replace(order(digit), account_id=account, intent=prop.intent)
            approval = market_rule_approval(
                quantity_units=prop.intent.quantity.units, side=OrderSide.BUY, effective_at=at,
                venue=key.venue_id.value, account_id=account, subject=subject,
                reference_price_units=price_units, observed_at_open=True, session_day=25,
                instrument_definition=definition,
                session_date=at.to_datetime().date().isoformat() if at_override is not None else None)
            estimate = FeeReservationEstimator().estimate(approval, fee_rules, at)
            assert estimate.proposal is not None and estimate.failure is None
            prop = replace(prop, estimated_fee=estimate.proposal.fee_estimate.total_fee)
        prepared.append((digit, key, definition, fee_rules, prop))
    plan = CnASharePortfolioOrderPlanV1.create(
        account_id=account, target_id=TARGET_W, target_hash="sha256:" + "7" * 64,
        as_of=before, policy=POLICY, cash=cash, sellability=sellable,
        working_orders=(), reservation_schedules=(),
        proposed=tuple(item[4] for item in prepared))
    streams = []
    schedules = []
    evidence = []
    for index, (digit, key, definition, fee_rules, prop) in enumerate(prepared, 1):
        base = order(digit)
        subject = replace(base, account_id=account, intent=prop.intent)
        records = full_lifecycle_records(subject)[:8]
        stream = OrderEventStream.from_records(subject, records)
        commitment = ReservationCommitment(
            cash=(prop.principal,), fee_reserve=(prop.estimated_fee,), order_capacity_units=1)
        schedule = OrderReservationSchedule(subject.order_id, "sha256:" + "a" * 64,
            (OrderReservationUpdate(subject.order_id, records[-1].event.event_id,
                                    OrderEventType.ORDER_ACCEPTED, subject.intent.quantity,
                                    commitment, "sha256:" + "b" * 64),))
        market = market_rule_approval(
            quantity_units=prop.intent.quantity.units, side=OrderSide.BUY, effective_at=at,
            venue=key.venue_id.value, account_id=account, subject=subject,
            reference_price_units=prices.get(key.instrument_id.stable_key, 400),
            observed_at_open=True, session_day=25, instrument_definition=definition,
            session_date=at.to_datetime().date().isoformat() if at_override is not None else None)
        fee = FeeReservationEstimator().estimate(market, fee_rules, at)
        assert fee.failure is None and fee.proposal is not None
        assert fee.proposal.fee_estimate.total_fee == prop.estimated_fee
        schedule = replace(schedule, source_proposal_hash=fee.proposal.proposal_hash)
        price_units = prices.get(key.instrument_id.stable_key, 400)
        bar = bar_event(instant=at.epoch_nanoseconds, sequence=index, kind="real", price_units=price_units)
        bar = replace(bar, instrument_id=key.instrument_id,
                      payload={"schema_version": 1, "bar_kind": "real",
                               "open_price": {"units": price_units, "scale": 2, "quote_currency": "CNY"}})
        streams.append(stream)
        schedules.append(schedule)
        evidence.append((digit, definition, prop, subject, records, market, fee.proposal, bar))
    open_cash, open_pos = snapshots(at, tuple(streams), tuple(schedules))
    reservations = ResourceReservationBook(account).project(tuple(streams), tuple(schedules))
    steps = []
    witnesses = []
    for digit, definition, prop, subject, records, market, fee, bar in evidence[:count - int(omit_last_open)]:
        item = (prop, subject, market, fee, BarOpenObservation.from_event(bar))
        risk, liquidity, state, zero = _open_source(
            item, plan, open_cash, open_pos, reservations, at)
        witnesses.append((liquidity, state, zero))
        stream = next(s for s in streams if s.order == subject)
        opened = evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=item[4], risk=risk,
            liquidity=liquidity, market_state=state, slippage_model=zero,
            eligibility_window_exhausted=True)
        fill = opened.fill
        assert fill is not None
        activated = OrderEventRecord(full_lifecycle_records(subject)[8].event)
        terminal = OrderEventStream.from_records(subject, records + (activated,
            OrderEventRecord(event(subject, "native-n-fill-" + digit,
                                   OrderEventType.ORDER_FILLED, at.epoch_nanoseconds,
                                   activated.event.event_id, fill_id=fill.fill_id), fill)))
        market_policy, tax_policy = policies()
        q = fee_query(OrderSide.BUY, at, venue=definition.instrument_id.venue.value,
                      instrument_definition=definition)
        market_res = market_policy.assess_fees(q).result
        tax_res = tax_policy.assess_taxes(q).result
        assert market_res is not None and tax_res is not None
        steps.append(CnASharePortfolioFinancialStepDevelopmentV1(
            opened, risk, terminal, final_fill_rule_set(fill),
            final_order_rule_set(side=OrderSide.BUY, effective_at=at,
                                 venue=definition.instrument_id.venue.value,
                                 instrument_definition=definition),
            market_res, tax_res))
    calendars = calendars_override or (_week_calendar(VenueId("xshg")), _week_calendar(VenueId("xshe")))
    return scope, journal, schema, at, tuple(steps), calendars, (
        tuple(item[7] for item in evidence[:count - int(omit_last_open)])), tuple(witnesses), rules


def _two_week_n(count: int, *, account_id="pharma.cash.account.arm_b", gap_index=None,
                capital=1_000_000, instrument_codes=None, first_prices=None, second_prices=None,
                first_at=None, second_at=None, calendars_override=None, quantity_units_by_code=None):
    scope, opening, schema, _, first_steps, calendars, first_bars, first_witnesses, rules = _native_n(
        count, account_id=account_id, capital=capital, instrument_codes=instrument_codes,
        price_units_by_code=first_prices, at_override=first_at, calendars_override=calendars_override,
        quantity_units_by_code=quantity_units_by_code)
    prices = second_prices or {}
    first = book_cn_a_share_portfolio_financial_batch_development_v2(
        universe=scope.instrument_ids, prior_journal=opening, ledger_schema=schema,
        cost_basis_policy=COST_BASIS, notional_quantization=QUANTIZATION, steps=first_steps)
    friday = build_cn_a_share_portfolio_settlement_development_v2(
        batch=first, calendars=calendars)
    pending = friday.book.project().pending_obligations
    assert len(pending) == count
    due = max(item.obligation.settlement_time for item in pending)
    matured = friday.apply_due(due)
    monday = second_at or local_instant(28, 10)
    before = UtcInstant(monday.epoch_nanoseconds - 1)
    assert due <= before
    def snapshots(when, streams=(), schedules=()):
        return (
            project_cn_a_share_shared_cny_cash_v1(
                journal=first.journal, ledger_schema=schema, settlement_book=matured.book,
                order_streams=streams, reservation_schedules=schedules,
                market_rules=rules, as_of=when),
            project_cn_a_share_portfolio_sellability_v1(
                journal=first.journal, ledger_schema=schema, settlement_book=matured.book,
                order_streams=streams, reservation_schedules=schedules,
                market_rules=rules, as_of=when),
        )
    cash, positions = snapshots(before)
    prepared = []
    for index, instrument in enumerate(scope.instrument_ids, 1):
        definition = scope.instrument_catalog.instrument(instrument)
        key = PositionBalanceKey(account_id, instrument.venue, instrument)
        fee_rules = reservation_rule_set(
            side=OrderSide.SELL, effective_at=monday,
            venue=instrument.venue.value, instrument_definition=definition)
        prop = replace(_proposal(f"{index:x}", key, TARGET_W1, OrderSide.SELL, 0, 526),
                       fee_authority_hash=fee_rules.rule_set_hash)
        units = (quantity_units_by_code or {}).get(instrument.stable_key, 100)
        if units != 100:
            prop = replace(prop, intent=replace(prop.intent,
                quantity=Quantity(units, prop.intent.quantity.scale, str(instrument))))
        if second_prices is not None:
            subject = replace(order(f"{index:x}"), account_id=account_id, intent=prop.intent)
            approval = market_rule_approval(
                quantity_units=prop.intent.quantity.units, side=OrderSide.SELL, effective_at=monday,
                venue=instrument.venue.value, account_id=account_id, subject=subject,
                reference_price_units=prices[instrument.stable_key], observed_at_open=True,
                instrument_definition=definition, session_date=monday.to_datetime().date().isoformat())
            estimate = FeeReservationEstimator().estimate(approval, fee_rules, monday)
            assert estimate.proposal is not None and estimate.failure is None
            prop = replace(prop, estimated_fee=estimate.proposal.fee_estimate.total_fee)
        prepared.append((index, definition, fee_rules, prop))
    plan = CnASharePortfolioOrderPlanV1.create(
        account_id=account_id, target_id=TARGET_W1, target_hash="sha256:" + "7" * 64,
        as_of=before, policy=POLICY, cash=cash, sellability=positions,
        working_orders=(), reservation_schedules=(),
        proposed=tuple(item[3] for item in prepared))
    streams = []
    schedules = []
    evidence = []
    for index, definition, fee_rules, prop in prepared:
        digit = f"{index:x}"
        base = order(digit)
        oid = DomainId(DomainIdKind.ORDER, "ord_" + canonical_sha256(
            {"type": "synthetic_week2_order", "instrument": definition.instrument_id})[7:])
        subject = replace(base, order_id=oid, account_id=account_id, intent=prop.intent)
        records = full_lifecycle_records(subject)[:8]
        stream = OrderEventStream.from_records(subject, records)
        schedule = OrderReservationSchedule(subject.order_id, "sha256:" + "a" * 64,
            (OrderReservationUpdate(subject.order_id, records[-1].event.event_id,
                                    OrderEventType.ORDER_ACCEPTED, subject.intent.quantity,
                                    ReservationCommitment(sellable_quantities=(subject.intent.quantity,),
                                        fee_reserve=(prop.estimated_fee,), order_capacity_units=1),
                                    "sha256:" + "b" * 64),))
        market = market_rule_approval(
            quantity_units=prop.intent.quantity.units, side=OrderSide.SELL, effective_at=monday,
            venue=definition.instrument_id.venue.value, account_id=account_id,
            subject=subject, reference_price_units=prices.get(definition.instrument_id.stable_key, 400), observed_at_open=True,
            session_day=28, instrument_definition=definition,
            session_date=monday.to_datetime().date().isoformat() if second_at is not None else None)
        fee = FeeReservationEstimator().estimate(market, fee_rules, monday)
        assert fee.failure is None and fee.proposal is not None
        assert fee.proposal.fee_estimate.total_fee == prop.estimated_fee
        schedule = replace(schedule, source_proposal_hash=fee.proposal.proposal_hash)
        kind = "gap_placeholder" if index == gap_index else "real"
        price_units = prices.get(definition.instrument_id.stable_key, 400)
        bar = bar_event(instant=monday.epoch_nanoseconds, sequence=index,
                        kind=kind, price_units=price_units)
        bar = replace(bar, instrument_id=definition.instrument_id,
                      payload={"schema_version": 1, "bar_kind": kind,
                               "open_price": None if kind != "real" else {
                                   "units": price_units, "scale": 2, "quote_currency": "CNY"}})
        streams.append(stream)
        schedules.append(schedule)
        evidence.append((index, definition, prop, subject, records, market, fee.proposal, bar))
    open_cash, open_pos = snapshots(monday, tuple(streams), tuple(schedules))
    reservations = ResourceReservationBook(account_id).project(tuple(streams), tuple(schedules))
    steps = []
    blocked = []
    witnesses = []
    for index, definition, prop, subject, records, market, fee, bar in evidence:
        stream = streams[index - 1]
        observation = BarOpenObservation.from_event(bar)
        if index == gap_index:
            outcome = evaluate_cn_a_share_portfolio_next_open_development_v1(
                plan=plan, stream=stream, observation=observation,
                risk=None, liquidity=None, market_state=None, slippage_model=None,
                eligibility_window_exhausted=True)
            assert outcome.action is NoEligibleBarAction.KEEP_ACTIVE and outcome.fill is None
            blocked.append(CnASharePortfolioNoFillDevelopmentV1(stream, outcome))
            continue
        item = (prop, subject, market, fee, observation)
        risk, liquidity, state, zero = _open_source(
            item, plan, open_cash, open_pos, reservations, monday)
        outcome = evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=observation, risk=risk,
            liquidity=liquidity, market_state=state, slippage_model=zero,
            eligibility_window_exhausted=True)
        fill = outcome.fill
        assert fill is not None and fill.side is OrderSide.SELL
        activated = OrderEventRecord(full_lifecycle_records(subject)[8].event)
        terminal = OrderEventStream.from_records(subject, records + (activated,
            OrderEventRecord(event(subject, "native-n-sell-" + f"{index:x}",
                                   OrderEventType.ORDER_FILLED, monday.epoch_nanoseconds,
                                   activated.event.event_id, fill_id=fill.fill_id), fill)))
        q = fee_query(OrderSide.SELL, monday, venue=definition.instrument_id.venue.value,
                      instrument_definition=definition)
        market_policy, tax_policy = policies()
        market_res = market_policy.assess_fees(q).result
        tax_res = tax_policy.assess_taxes(q).result
        assert market_res is not None and tax_res is not None
        steps.append(CnASharePortfolioFinancialStepDevelopmentV1(
            outcome, risk, terminal, final_fill_rule_set(fill),
            final_order_rule_set(side=OrderSide.SELL, effective_at=monday,
                                 venue=definition.instrument_id.venue.value,
                                 instrument_definition=definition),
            market_res, tax_res))
        witnesses.append((liquidity, state, zero))
    return scope, opening, first, friday, matured, tuple(first_steps), first_bars, first_witnesses, (
        tuple(steps), tuple(bar for *_, bar in evidence), tuple(witnesses), tuple(blocked), calendars), rules


@pytest.mark.parametrize("count", (3, 10))
def test_native_variable_n_week2_sell_and_t_plus_one_prefix(count):
    scope, opening, first, friday, matured, _, _, _, second, _ = _two_week_n(count)
    steps, bars, witnesses, blocked, calendars = second
    assert len(steps) == count and not blocked
    assert first.journal.journal_hash == steps[0].risk.plan.cash.journal_hash
    assert matured.book.project().pending_obligations == ()
    second_batch = book_cn_a_share_portfolio_financial_batch_development_v2(
        universe=scope.instrument_ids, prior_journal=first.journal, ledger_schema=scope.ledger_schema,
        cost_basis_policy=COST_BASIS, notional_quantization=QUANTIZATION, steps=steps)
    assert len(second_batch.fills) == count and len(second_batch.fee_assessments) == 2 * count
    assert second_batch.journal.cursor_at(first.journal.entry_count).prefix_hash == first.journal.journal_hash
    assert len(build_cn_a_share_portfolio_settlement_development_v2(
        batch=second_batch, calendars=calendars).book.project().pending_obligations) == count

def test_three_then_ten_distinct_native_buy_fills_fees_and_pending_t_plus_one():
    for count in (3, 10):
        scope, journal, schema, at, steps, calendars, _, _, _ = _native_n(count)
        batch = book_cn_a_share_portfolio_financial_batch_development_v2(
            universe=scope.instrument_ids, prior_journal=journal, ledger_schema=schema,
            cost_basis_policy=COST_BASIS, notional_quantization=QUANTIZATION, steps=steps)
        assert len(batch.fills) == count and len(batch.fee_assessments) == 2 * count
        assert len({fill.instrument_id for fill in batch.fills}) == count
        assert {entry.account_id for entry in batch.journal.entries} == {scope.account_id}
        assert not batch.trade_authorized
        book = build_cn_a_share_portfolio_settlement_development_v2(
            batch=batch, calendars=calendars)
        assert len(book.book.project().pending_obligations) == count
        assert all(item.obligation.settlement_time > at
                   for item in book.book.project().pending_obligations)


@pytest.mark.parametrize("count", (3, 10))
def test_native_variable_n_gtc_gap_keeps_old_stock_and_charges_only_filled_sells(count):
    scope, _, first, _, matured, _, _, _, second, rules = _two_week_n(count, gap_index=1)
    steps, bars, witnesses, blocked, calendars = second
    assert len(steps) == count - 1 and len(blocked) == 1
    assert blocked[0].outcome.action is NoEligibleBarAction.KEEP_ACTIVE
    assert blocked[0].outcome.fill is None
    batch = book_cn_a_share_portfolio_financial_batch_development_v2(
        universe=scope.instrument_ids, prior_journal=first.journal,
        ledger_schema=scope.ledger_schema, cost_basis_policy=COST_BASIS,
        notional_quantization=QUANTIZATION, steps=steps, blocked=blocked)
    assert len(batch.fills) == count - 1 and len(batch.fee_assessments) == 2 * (count - 1)
    held = blocked[0].stream.order.intent.instrument_id
    assert batch.ledger_state.position_quantity(
        PositionBalanceKey(scope.account_id, held.venue, held)).units == 100
    assert len(build_cn_a_share_portfolio_settlement_development_v2(
        batch=batch, calendars=calendars).book.project().pending_obligations) == count - 1

def test_missing_tenth_open_and_overcash_never_produce_n_stock_batch():
    scope, journal, schema, at, steps, calendars, _, _, _ = _native_n(10, omit_last_open=True)
    with pytest.raises(ValueError, match="incomplete or duplicate scope"):
        book_cn_a_share_portfolio_financial_batch_development_v2(
            universe=scope.instrument_ids, prior_journal=journal, ledger_schema=schema,
            cost_basis_policy=COST_BASIS, notional_quantization=QUANTIZATION, steps=steps)
    with pytest.raises(ValueError, match="prefinance"):
        _native_n(10, capital=300_000)
