"""Explicit Aug2023 TEST sources; current-open seam, NOT public October A/B."""
from dataclasses import replace

import pytest
import crypto_quant_domain as d
from crypto_quant_trading import (
    GenericLedger, OrderEventRecord, OrderEventStream, OrderReservationSchedule,
    OrderReservationUpdate, ReservationCommitment, ResourceReservationBook, SettlementBook,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_order_plan_v1 import CnASharePortfolioOrderPlanV1
from crypto_quant_backtest.cn_a_share_portfolio_standard_opening_v1 import (
    _StandardOpenSourcesV1, _StandardCurrentOpenProofV1, _StandardFinancialStepV1,
    _standard_market_fee_v1, _standard_opening_v1, _standard_full_fill_budget_v1,
    _book_standard_full_fill_batch_v1,
)
from crypto_quant_backtest.execution import BarOpenObservation, NoEligibleBarAction
from tests.runtime.providers.test_cn_a_share_portfolio_standard_case_v1 import _sources
from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import _native_n


def _at(when, phase, sequence=1):
    return d.SimulationInstant(when, d.TimelinePhase(phase, "standard_test_stage"), d.SourceSequence(sequence))


def _accepted(order, market, fee, plan, terms, sequence):
    spec = market.evaluation_input.executable_order_spec
    kinds = (d.OrderEventType.ORDER_INTENT_CREATED, d.OrderEventType.ORDER_CAPABILITY_APPROVED,
        d.OrderEventType.ORDER_TRANSLATED, d.OrderEventType.MARKET_RULE_APPROVED,
        d.OrderEventType.FEE_RESERVATION_ESTIMATED, d.OrderEventType.PRE_TRADE_RISK_APPROVED,
        d.OrderEventType.ORDER_SUBMITTED, d.OrderEventType.ORDER_ACCEPTED)
    evidence = (plan.plan_hash, spec.capability_approval.decision_id, spec.spec_id,
        market.decision_id, fee.proposal_hash, plan.plan_hash, terms.bar_event_hash, terms.bar_event_hash)
    phases = (40, 41, 42, 60, 61, 62, 63, 66)
    records = []
    cause = order.intent.parent_id
    for index, (kind, value, phase) in enumerate(zip(kinds, evidence, phases, strict=True)):
        when = order.created_at.instant if index < 3 else terms.opening_at
        event = d.OrderEvent("event:standard.test." + order.order_id.value + "." + str(index),
            order.order_id, cause, kind, order.created_at if index == 0 else _at(when, phase, sequence),
            evidence_id=value)
        records.append(OrderEventRecord(event))
        cause = event.event_id
    stream = OrderEventStream.from_records(order, tuple(records))
    proposal = next(p for p in plan.proposed if p.intent == order.intent)
    commitment = ReservationCommitment(
        cash=(proposal.principal,) if order.intent.side is d.OrderSide.BUY else (),
        sellable_quantities=(order.intent.quantity,) if order.intent.side is d.OrderSide.SELL else (),
        fee_reserve=fee.commitment.fee_reserve, order_capacity_units=1)
    update = OrderReservationUpdate(order.order_id, records[-1].event.event_id,
        d.OrderEventType.ORDER_ACCEPTED, order.intent.quantity, commitment, d.canonical_sha256(plan))
    schedule = OrderReservationSchedule(order.order_id, fee.proposal_hash, (update,))
    return stream, schedule


def _terminal(opening, sequence):
    stream = opening.proof.stream
    fill = opening.fill
    assert fill is not None and stream.state is not None
    activated = d.OrderEvent("event:standard.test.activate." + stream.order.order_id.value,
        stream.order.order_id, stream.state.last_event_id, d.OrderEventType.ORDER_ACTIVATED,
        _at(fill.execution_time, 68, sequence), evidence_id=opening.outcome_hash)
    filled = d.OrderEvent("event:standard.test.fill." + stream.order.order_id.value,
        stream.order.order_id, activated.event_id, d.OrderEventType.ORDER_FILLED,
        _at(fill.execution_time, 69, sequence), fill_id=fill.fill_id, evidence_id=opening.outcome_hash)
    return stream.append(OrderEventRecord(activated)).append(OrderEventRecord(filled, fill))


def _smoke(inputs=None):
    source, bars, *_ = _sources()
    if inputs is not None:
        source = inputs
    native = _native_n(2, capital=10_000_000,
        price_units_by_code={"600000": 1137, "000001": 2231})
    rules = native[-1]
    before = _StandardOpenSourcesV1(source, source.initial_journal, SettlementBook(source.scope.account_id),
        (), (), rules, _at(bars[0].event_time, 55))
    orders, proposals, markets, fees, terms = [], [], [], [], []
    for index, step in enumerate(native[4]):
        original = step.risk
        order = replace(original.order, created_at=source.signal_marks[0].at)
        term = next(t for t in source.opening_terms if t.instrument_id == order.intent.instrument_id
            and t.side is order.intent.side and t.opening_at == bars[0].event_time)
        market, fee = _standard_market_fee_v1(order, term)
        proposal = replace(original.proposal, principal=market.calculated_notional,
            estimated_fee=fee.fee_estimate.total_fee, fee_authority_hash=term.reservation_rules.rule_set_hash)
        orders.append(order)
        proposals.append(proposal)
        markets.append(market)
        fees.append(fee)
        terms.append(term)
    plan = CnASharePortfolioOrderPlanV1.create(account_id=source.scope.account_id,
        target_id=orders[0].intent.parent_id, target_hash=d.canonical_sha256("fixture.target"),
        as_of=before.at.instant, policy=source.execution_policy, cash=before.cash,
        sellability=before.sellability, working_orders=(), reservation_schedules=(), proposed=tuple(proposals))
    paired = tuple(_accepted(o, m, f, plan, t, i) for i, (o, m, f, t) in
        enumerate(zip(orders, markets, fees, terms, strict=True), 1))
    streams, schedules = tuple(p[0] for p in paired), tuple(p[1] for p in paired)
    current = _StandardOpenSourcesV1(source, source.initial_journal, before.settlement_book,
        streams, schedules, rules, _at(bars[0].event_time, 67))
    proofs = tuple(_StandardCurrentOpenProofV1(plan, before, current, stream, fee,
        BarOpenObservation.from_event(next(b for b in bars if b.instrument_id == stream.order.intent.instrument_id)), term)
        for stream, fee, term in zip(streams, fees, terms, strict=True))
    return proofs


def _opening_batch(proofs):
    prefix, outcomes = [], []
    for proof in sorted(proofs, key=lambda p: (p.stream.order.intent.side is d.OrderSide.BUY,
                                              p.stream.order.intent.instrument_id)):
        opening = _standard_opening_v1(proof, budget_prefix=tuple(prefix))
        outcomes.append(opening)
        if opening.fill is not None:
            prefix.append(proof)
    return tuple(outcomes)

def _retry_case():
    from datetime import date
    from crypto_quant_trading.profiles.cn_a_share import (
        CnAShareFrozenCalendarDay, CnAShareCalendarDayKind,
    )
    from crypto_quant_backtest.cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioOpeningTermsDevelopmentV1
    from crypto_quant_backtest.cn_a_share_portfolio_settlement_development_v1 import (
        _build_cn_a_share_portfolio_settlement_facts_v1,
    )
    from crypto_quant_backtest.execution import BarLiquidityEvidence
    from crypto_quant_backtest.slippage import SlippageApplicabilityEnvelope
    from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
        market_rule_approval, reservation_rule_set, final_fill_rule_set, final_order_rule_set, policies, fee_query,
    )
    source, bars, *_ = _sources()
    native = _native_n(2, capital=10_000_000, price_units_by_code={"600000": 1137, "000001": 2231})
    prototype = {s.risk.order.intent.instrument_id: s for s in native[4]}
    sh = next(i for i in source.scope.instrument_ids if i.venue.value == "xshg")
    sz = next(i for i in source.scope.instrument_ids if i.venue.value == "xshe")
    monday = d.UtcInstant(bars[0].event_time.epoch_nanoseconds + 3 * 86_400_000_000_000)
    tuesday = d.UtcInstant(monday.epoch_nanoseconds + 86_400_000_000_000)
    target_id = "normalized-portfolio-target-v1:sha256:" + "9" * 64
    sell = replace(prototype[sh].risk.order, order_id=d.DomainId(d.DomainIdKind.ORDER, "ord_" + "9" * 64),
        intent=replace(prototype[sh].risk.order.intent, side=d.OrderSide.SELL, reduce_only=True,
            position_effect=d.PositionEffect.CLOSE, time_in_force=d.TimeInForce.GTC, parent_id=target_id),
        created_at=_at(d.UtcInstant(monday.epoch_nanoseconds - 1000), 40))
    buy = replace(prototype[sz].risk.order, order_id=d.DomainId(d.DomainIdKind.ORDER, "ord_" + "8" * 64),
        intent=replace(prototype[sz].risk.order.intent, parent_id=target_id),
        created_at=_at(d.UtcInstant(monday.epoch_nanoseconds - 1000), 40, 2))
    added, new_bars = [], {}
    for order, when, price, blocked in ((sell, monday, 1100, True), (buy, monday, 2231, False),
                                       (sell, tuesday, 1500, False)):
        instrument = order.intent.instrument_id
        definition = source.scope.instrument_catalog.instrument(instrument)
        base = next(t for t in source.opening_terms if t.instrument_id == instrument and t.side is d.OrderSide.BUY)
        old_bar = next(b for b in bars if b.instrument_id == instrument)
        raw = replace(old_bar, event_id=old_bar.event_id + ".later." + str(when.epoch_nanoseconds),
            event_time=when, available_time=when,
            payload={"schema_version": 1, "bar_kind": "real", "open_price":
                {"units": price, "scale": 2, "quote_currency": "CNY"}})
        market = market_rule_approval(quantity_units=100, side=order.intent.side, effective_at=when,
            venue=instrument.venue.value, account_id=source.scope.account_id, subject=order,
            reference_price_units=price, observed_at_open=True, instrument_definition=definition,
            session_date=when.to_datetime().date().isoformat())
        liquidity = BarLiquidityEvidence.create(evidence_key="standard.retry.synthetic", evidence_version=1,
            market_event=raw, evaluated_at=when, approved=not blocked,
            reason_code="synthetic_limit_lock" if blocked else None, source_hash=raw.event_hash)
        state = replace(base.market_state, source_event_id=raw.event_id, evidence_hash=raw.event_hash,
            revision_id=raw.revision_id, observed_at=when, available_at=when)
        mp, tp = policies()
        query = fee_query(order.intent.side, when, venue=instrument.venue.value, instrument_definition=definition)
        m, t = mp.assess_fees(query).result, tp.assess_taxes(query).result
        assert m is not None and t is not None
        envelope = base.slippage_model.applicability_envelope
        shifted = SlippageApplicabilityEnvelope.create(envelope_key=envelope.envelope_key,
            envelope_version=envelope.envelope_version, instrument_id=instrument,
            valid_from=d.UtcInstant(when.epoch_nanoseconds - 1),
            valid_to_exclusive=d.UtcInstant(when.epoch_nanoseconds + 1),
            maximum_quantity=envelope.maximum_quantity, allowed_market_state_keys=envelope.allowed_market_state_keys)
        zero = replace(base.slippage_model, applicability_envelope=shifted)
        terms = CnASharePortfolioOpeningTermsDevelopmentV1(raw.event_id, raw.event_hash, instrument,
            order.intent.side, market.evaluation_input.executable_order_spec.capability_approval.capability_set,
            base.translation_mapping, market.rule_timeline,
            market.evaluation_input.notional_evidence,
            reservation_rule_set(side=order.intent.side, effective_at=when, venue=instrument.venue.value,
                instrument_definition=definition),
            final_fill_rule_set(replace(prototype[instrument].opening.fill, side=order.intent.side,
                execution_time=when)),
            final_order_rule_set(side=order.intent.side, effective_at=when, venue=instrument.venue.value,
                instrument_definition=definition), m, t, liquidity, state, zero)
        added.append(terms)
        new_bars[(instrument, when)] = raw
    calendars = tuple(replace(c, coverage_end_exclusive=date(2023, 8, 31),
        days=(*c.days, CnAShareFrozenCalendarDay(date(2023, 8, 30), CnAShareCalendarDayKind.TRADING)))
        for c in source.calendars)
    assert len(calendars) == 2
    source = replace(source, calendars=(calendars[0], calendars[1]),
        opening_terms=tuple(sorted((*source.opening_terms, *added), key=lambda t: (t.opening_at, t.instrument_id, t.side.value))))
    friday_proofs = _smoke(source)
    friday_steps = tuple(_StandardFinancialStepV1(o, _terminal(o, i))
        for i, o in enumerate(_opening_batch(friday_proofs), 1))
    journal, _, fills, _ = _book_standard_full_fill_batch_v1(friday_steps)
    settlement = _build_cn_a_share_portfolio_settlement_facts_v1(fills=fills, journal=journal,
        source_hash=d.canonical_sha256(friday_steps), calendars=source.calendars).apply_due(monday)
    history = tuple(s.terminal_order for s in friday_steps)
    schedules = friday_proofs[0].sources.reservation_schedules
    before = _StandardOpenSourcesV1(source, journal, settlement.book, history, schedules,
        native[-1], _at(monday, 55))
    proposals, facts = [], []
    for order in (sell, buy):
        term = next(t for t in added if t.instrument_id == order.intent.instrument_id and t.opening_at == monday)
        market, fee = _standard_market_fee_v1(order, term)
        proto = prototype[order.intent.instrument_id].risk.proposal
        proposal = replace(proto, intent=order.intent,
            principal=market.calculated_notional if order.intent.side is d.OrderSide.BUY else d.Money(0, d.Scale(2), "CNY"),
            estimated_fee=fee.fee_estimate.total_fee, fee_authority_hash=term.reservation_rules.rule_set_hash)
        proposals.append(proposal)
        facts.append((order, term, market, fee))
    plan = CnASharePortfolioOrderPlanV1.create(account_id=source.scope.account_id, target_id=target_id,
        target_hash=d.canonical_sha256("retry.target"), as_of=monday, policy=source.execution_policy,
        cash=before.cash, sellability=before.sellability, working_orders=history,
        reservation_schedules=schedules, proposed=tuple(proposals))
    accepted = tuple(_accepted(o, m, f, plan, term, i) for i, (o, term, m, f) in enumerate(facts, 1))
    streams = (*history, *(p[0] for p in accepted))
    schedules = (*schedules, *(p[1] for p in accepted))
    current = _StandardOpenSourcesV1(source, journal, settlement.book, streams, schedules, native[-1], _at(monday, 67))
    monday_proofs = tuple(_StandardCurrentOpenProofV1(plan, before, current, accepted[i][0], facts[i][3],
        BarOpenObservation.from_event(new_bars[(o.intent.instrument_id, monday)]), term)
        for i, (o, term, _, _) in enumerate(facts))
    blocked = _standard_opening_v1(monday_proofs[0])
    assert blocked.fill is None and blocked.action is NoEligibleBarAction.KEEP_ACTIVE
    bought = _standard_opening_v1(monday_proofs[1])
    assert bought.fill is not None
    buy_step = _StandardFinancialStepV1(bought, _terminal(bought, 2))
    journal, _, fills, _ = _book_standard_full_fill_batch_v1((buy_step,))
    new_settlement = _build_cn_a_share_portfolio_settlement_facts_v1(fills=fills, journal=journal,
        source_hash=d.canonical_sha256(buy_step), calendars=source.calendars)
    combined_book = settlement.book.append(obligations=new_settlement.book.obligations, events=new_settlement.book.events)
    settlement = replace(new_settlement, book=combined_book).apply_due(tuesday)
    streams = (*history, accepted[0][0], buy_step.terminal_order)
    later = _StandardOpenSourcesV1(source, journal, settlement.book, streams, schedules,
        native[-1], _at(tuesday, 67))
    term = next(t for t in added if t.instrument_id == sh and t.opening_at == tuesday)
    retried = _StandardCurrentOpenProofV1(plan, before, later, accepted[0][0], facts[0][3],
        BarOpenObservation.from_event(new_bars[(sh, tuesday)]), term)
    return retried, blocked


def test_gtc_retry_after_intervening_native_buy_uses_current_price_fee_and_unchanged_schedule():
    proof, blocked = _retry_case()
    assert proof.sources.journal.journal_hash != proof.plan.cash.journal_hash
    assert proof.market.calculated_notional != proof.original_fee.fee_estimate.market_rule_approval.calculated_notional
    assert proof.fee.proposal_hash != proof.original_fee.proposal_hash
    assert proof.fee.fee_estimate.estimated_at == proof.observation.event.event_time
    assert proof.terms.market_fee_resolution.effective_at == proof.observation.event.event_time
    old_schedule = next(s for s in proof.sources.reservation_schedules if s.order_id == proof.stream.order.order_id)
    assert len(old_schedule.updates) == 1 and old_schedule.source_proposal_hash == proof.original_fee.proposal_hash
    assert blocked.proof.stream == proof.stream
    opening = _standard_opening_v1(proof)
    assert opening.fill is not None
    step = _StandardFinancialStepV1(opening, _terminal(opening, 1))
    journal, ledger, fills, fees = _book_standard_full_fill_batch_v1((step,))
    assert len(fills) == 1 and len(fees) == 2
    assert fills[0].side is d.OrderSide.SELL
    assert ledger == GenericLedger(proof.sources.inputs.scope.ledger_schema).project(journal)
    assert journal.entries[:len(proof.sources.journal.entries)] == proof.sources.journal.entries
    assert old_schedule in proof.sources.reservation_schedules


@pytest.mark.parametrize("part", ("book", "order", "journal", "future_phase"))
def test_retry_rejects_lost_current_graph_and_future_phases(part):
    proof, _ = _retry_case()
    source = proof.sources
    if part == "book":
        kwargs = {"settlement_book": SettlementBook(source.inputs.scope.account_id)}
    elif part == "order":
        kwargs = {"order_streams": source.order_streams[1:]}
    elif part == "journal":
        kwargs = {"journal": proof.plan_sources.journal}
    else:
        kwargs = {"at": _at(source.journal.entries[-1].recorded_at.instant, 67)}
    with pytest.raises(ValueError):
        replace(source, **kwargs)


def test_retry_cannot_substitute_the_fresh_fee_for_original_reservation():
    proof, _ = _retry_case()
    assert proof.original_fee != proof.fee
    with pytest.raises(ValueError, match="original market/fee/acceptance"):
        replace(proof, original_fee=proof.fee)


def test_current_open_rejects_wrong_native_bar_and_acceptance_evidence():
    proof = _smoke()[0]
    with pytest.raises(ValueError, match="source, clock, plan or Order"):
        replace(proof, observation=replace(proof.observation,
            event=replace(proof.observation.event, revision_id="foreign.revision")))
    record = proof.stream.records[4]
    changed = proof.stream.records[:4] + (replace(record,
        event=replace(record.event, evidence_id=d.canonical_sha256("wrong.original.fee"))),) + proof.stream.records[5:]
    stream = OrderEventStream.from_records(proof.stream.order, changed)
    source = replace(proof.sources, order_streams=(stream, *proof.sources.order_streams[1:]))
    with pytest.raises(ValueError, match="original market/fee/acceptance"):
        replace(proof, stream=stream, sources=source)


def test_atomic_native_batch_cannot_drop_cumulative_budget_prefix_or_duplicate_orders():
    proofs = _smoke()
    with pytest.raises(ValueError, match="duplicate"):
        _standard_full_fill_budget_v1((proofs[0], proofs[0]))
    independently_built = tuple(_standard_opening_v1(p) for p in proofs)
    steps = tuple(_StandardFinancialStepV1(o, _terminal(o, i)) for i, o in enumerate(independently_built, 1))
    with pytest.raises(ValueError, match="exact sell-first budget prefix"):
        _book_standard_full_fill_batch_v1(steps)


def test_native_actual_final_fee_over_reserved_worstcase_never_returns_batch():
    from crypto_quant_trading import FinalFeeRuleSet, FinalFeeRuleSource
    source, *_ = _sources()
    changed = []
    for term in source.opening_terms:
        if term.side is not d.OrderSide.BUY:
            changed.append(term)
            continue
        final = term.final_order_rules
        rules = tuple(replace(rule, rate=d.Rate(1, d.Scale(0), "fee_fraction"))
                      if rule.source is FinalFeeRuleSource.ACCOUNT_SCHEDULE and rule.rate is not None else rule
                      for rule in final.charge_rules)
        altered = FinalFeeRuleSet.create(market_fee_policy_ref=final.market_fee_policy_ref,
            tax_policy_ref=final.tax_policy_ref, account_fee_schedule_ref=final.account_fee_schedule_ref,
            assessment_currency=final.assessment_currency, assessment_scale=final.assessment_scale,
            charge_rules=rules, minimums=final.minimums)
        changed.append(replace(term, final_order_rules=altered))
    source = replace(source, opening_terms=tuple(changed))
    proofs = _smoke(source)
    openings = _opening_batch(proofs)
    steps = tuple(_StandardFinancialStepV1(o, _terminal(o, i)) for i, o in enumerate(openings, 1))
    with pytest.raises(ValueError, match="exceed reserved worst-case budget"):
        _book_standard_full_fill_batch_v1(steps)


def test_false_nofill_is_not_an_unproved_boolean_override():
    from crypto_quant_backtest.cn_a_share_portfolio_standard_opening_v1 import _StandardOpeningOutcomeV1
    proof = _smoke()[0]
    with pytest.raises(ValueError, match="native liquidity/batch budget"):
        _StandardOpeningOutcomeV1(proof, NoEligibleBarAction.EXPIRE,
            "settled_cash_or_t1_unavailable", None)


def test_current_sources_reject_native_book_with_same_fill_count_but_forged_settlement_time():
    proof, _ = _retry_case()
    source = proof.sources
    ob = next(o for o in source.settlement_book.obligations
              if isinstance(o.balance_key, d.PositionBalanceKey)
              and o.obligation.settlement_time > o.obligation.trade_time)
    forged = replace(ob, obligation=replace(ob.obligation, settlement_time=ob.obligation.trade_time))
    obligations = tuple(forged if old == ob else old for old in source.settlement_book.obligations)
    fake_book = SettlementBook.from_events(source.inputs.scope.account_id, obligations, source.settlement_book.events)
    assert len(fake_book.obligations) == len(source.settlement_book.obligations)
    with pytest.raises(ValueError, match="native.*T\\+1|native settlement"):
        replace(source, settlement_book=fake_book)


def test_whole_live_funding_pair_can_extend_retry_prefix_but_half_pair_is_rejected():
    from crypto_quant_backtest.cn_a_share_portfolio_venue_funding_development_v1 import plan_cn_portfolio_venue_funding_development_v1
    proof, _ = _retry_case()
    source = proof.sources
    destination = proof.stream.order.intent.instrument_id.venue
    required = tuple((key, d.Money(value.units + 1 if key.venue_id == destination else 0,
        d.Scale(2), "CNY")) for key, value in source.available_by_venue)
    pair = plan_cn_portfolio_venue_funding_development_v1(journal=source.journal,
        ledger_schema=source.inputs.scope.ledger_schema, settlement_book=source.settlement_book,
        order_streams=source.order_streams, reservation_schedules=source.reservation_schedules,
        market_rules=source.market_rules, required_by_venue=required,
        at=_at(proof.observation.event.event_time, 65), target_hash=proof.plan.target_hash)
    assert len(pair) == 2
    with pytest.raises(ValueError, match="WHOLE"):
        replace(source, journal=source.journal.append_many(pair[:1]))
    extended = replace(source, journal=source.journal.append_many(pair))
    assert extended.cash.total == source.cash.total
    assert extended.cash.spendable == source.cash.spendable
    funded_proof = replace(proof, sources=extended)
    assert funded_proof.proof_hash != proof.proof_hash
    assert _standard_opening_v1(funded_proof).fill is not None


def test_two_stock_current_prefix_full_fill_native_journal():
    proofs = _smoke()
    assert _standard_full_fill_budget_v1(proofs)
    openings = _opening_batch(proofs)
    assert all(o.action is NoEligibleBarAction.FULL_FILL for o in openings)
    steps = tuple(_StandardFinancialStepV1(o, _terminal(o, i)) for i, o in enumerate(openings, 1))
    journal, ledger, fills, fees = _book_standard_full_fill_batch_v1(steps)
    source = proofs[0].sources
    assert journal.entries[:len(source.journal.entries)] == source.journal.entries
    assert len(journal.entries) == len(source.journal.entries) + 6
    assert len(fills) == 2 and len(fees) == 4
    assert ledger == GenericLedger(source.inputs.scope.ledger_schema).project(journal)
    assert all(v.amount.units >= 0 for v in ledger.cash_balances)
    released = ResourceReservationBook(source.inputs.scope.account_id).project(
        tuple(s.terminal_order for s in steps), source.reservation_schedules)
    assert not released.active_reservations
    assert all(len(s.updates) == 1 for s in source.reservation_schedules)
