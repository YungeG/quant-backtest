"""Two synthetic SH/SZ open-time risk approvals, not an executed portfolio."""
from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import Money, OrderSide, UtcInstant
from crypto_quant_trading import (
    AccountingJournal, FeeReservationEstimator, ResourceReservationBook, SettlementBook,
)
from crypto_quant_backtest.cn_a_share_portfolio_funding_development_v1 import (
    build_synthetic_cross_venue_funding_candidate_v1,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_open_risk_development_v1 import (
    CnASharePortfolioOpenRiskApprovalDevelopmentV1,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    local_instant, market_rule_approval, reservation_rule_set,
)
from tests.kernel.profiles.cn_a_share.test_portfolio_order_plan_v1 import (
    ACCOUNT, POLICY, TARGET_W, _accepted, _plan, _proposal, _sources,
)
from tests.kernel.profiles.cn_a_share.test_portfolio_sellability_v1 import _two_week_sources
from tests.runtime.providers.test_cn_a_share_portfolio_funding_development_v1 import fixture as funding_fixture
from tests.runtime.execution._fixtures import bar_event
from crypto_quant_backtest.execution import BarOpenObservation


def _opening_case(day: int = 28):
    _, schema, rules, _, keys, _ = _two_week_sources()
    args = funding_fixture()
    opening = build_synthetic_cross_venue_funding_candidate_v1(
        **{**args, "ledger_schema": schema, "settlement_rules": rules,
           "amount": Money(50_000, args["amount"].scale, "CNY")}).journal
    book = SettlementBook(ACCOUNT)
    t = local_instant(day, 10)
    fee_budget = 506 if day == 25 else 505
    before = UtcInstant(t.epoch_nanoseconds - 1)
    cash, positions = _sources(opening, schema, rules, book, before)
    # Freeze synthetic tariff identities and a conservative fee budget BEFORE
    # the opening event; the actual price/Kernel estimate is evaluated at t.
    rule_sets = tuple(reservation_rule_set(
        side=OrderSide.BUY, effective_at=t, venue=venue)
        for venue in ("xshg", "xshe"))
    proposals = tuple(replace(_proposal(digit, key, TARGET_W, OrderSide.BUY, 40_000, fee_budget),
                              fee_authority_hash=rule_set.rule_set_hash)
                      for digit, key, rule_set in (("6", keys[0], rule_sets[0]),
                                                  ("7", keys[1], rule_sets[1])))
    plan = _plan(TARGET_W, before, cash, positions, proposals)
    streams = []
    schedules = []
    evidence = []
    for seq, prop, venue, rule_set in ((1, proposals[0], "xshg", rule_sets[0]),
                                        (2, proposals[1], "xshe", rule_sets[1])):
        stream, schedule, _, order = _accepted(prop, str(seq + 5), fee=fee_budget)
        market = market_rule_approval(
            quantity_units=100, side=OrderSide.BUY, effective_at=t, venue=venue,
            account_id=ACCOUNT, subject=order, reference_price_units=400,
            observed_at_open=True, session_day=day)
        outcome = FeeReservationEstimator().estimate(market, rule_set, t)
        assert outcome.failure is None and outcome.proposal is not None
        assert outcome.proposal.fee_estimate.total_fee.units == fee_budget
        assert prop.fee_authority_hash == outcome.proposal.fee_estimate.rule_set.rule_set_hash
        schedule = replace(schedule, source_proposal_hash=outcome.proposal.proposal_hash)
        event = bar_event(instant=t.epoch_nanoseconds, sequence=seq, kind="real", price_units=400)
        event = replace(event, instrument_id=order.intent.instrument_id,
                        payload={"schema_version": 1, "bar_kind": "real",
                                 "open_price": {"units": 400, "scale": 2, "quote_currency": "CNY"}})
        observation = BarOpenObservation.from_event(event)
        assert observation.open_price == market.evaluation_input.notional_evidence.price
        streams.append(stream)
        schedules.append(schedule)
        evidence.append((prop, order, market, outcome.proposal, observation))
    open_cash, open_positions = _sources(opening, schema, rules, book, t,
                                         tuple(streams), tuple(schedules))
    reservations = ResourceReservationBook(ACCOUNT).project(tuple(streams), tuple(schedules))
    return plan, open_cash, open_positions, reservations, evidence, t


def test_two_venue_real_open_market_fee_and_shared_cash_risk_bind_without_old_approval():
    plan, cash, positions, reservations, evidence, at = _opening_case()
    assert cash.total.units == 100_000
    assert cash.reserved_principal.units == 80_000
    assert cash.reserved_fees.units == 1_010
    assert cash.spendable.units == 18_990
    approvals = []
    for prop, order, market, fee, observation in evidence:
        approved = CnASharePortfolioOpenRiskApprovalDevelopmentV1.create(
            plan=plan, proposal=prop, order=order, market=market, fee=fee,
            open_price=observation.open_price, open_event_hash=observation.event.event_hash,
            evaluated_at=at, open_cash=cash, open_sellability=positions,
            reservation_state=reservations)
        assert approved.approval_id.startswith("cn-a-share-portfolio-open-risk-development-v1:")
        assert not approved.trade_authorized and approved.development_only
        approvals.append(approved)
    assert approvals[0].approval_hash != approvals[1].approval_hash
    p, order, market, fee, obs = evidence[0]
    with pytest.raises(ValueError, match="fee proposal"):
        CnASharePortfolioOpenRiskApprovalDevelopmentV1.create(
            plan=plan, proposal=p, order=order, market=market, fee=evidence[1][3],
            open_price=obs.open_price, open_event_hash=obs.event.event_hash,
            evaluated_at=at, open_cash=cash, open_sellability=positions,
            reservation_state=reservations)
    with pytest.raises(ValueError, match="market/Order/price"):
        CnASharePortfolioOpenRiskApprovalDevelopmentV1.create(
            plan=plan, proposal=p, order=order, market=market, fee=fee,
            open_price=evidence[1][4].open_price, open_event_hash=obs.event.event_hash,
            evaluated_at=at, open_cash=cash, open_sellability=positions,
            reservation_state=reservations)
    with pytest.raises(ValueError, match="source prefix"):
        CnASharePortfolioOpenRiskApprovalDevelopmentV1.create(
            plan=plan, proposal=p, order=order, market=market, fee=fee,
            open_price=obs.open_price, open_event_hash=obs.event.event_hash,
            evaluated_at=at, open_cash=plan.cash, open_sellability=positions,
            reservation_state=reservations)
