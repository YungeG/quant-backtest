"""Two native zero-slippage CNY open Fills; explicitly synthetic/development only."""
from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import Fill, OrderSide, Price, UtcInstant
from crypto_quant_backtest.cn_a_share_portfolio_next_open_development_v1 import (
    evaluate_cn_a_share_portfolio_next_open_development_v1,
)
from crypto_quant_backtest.execution import BarLiquidityEvidence, NoEligibleBarAction
from crypto_quant_backtest.slippage import (
    SlippageApplicabilityEnvelope, SlippageMarketState,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_open_risk_development_v1 import (
    CnASharePortfolioOpenRiskApprovalDevelopmentV1,
)
from tests.kernel.profiles.cn_a_share.test_portfolio_open_risk_development_v1 import _opening_case
from tests.kernel.profiles.cn_a_share.test_portfolio_order_plan_v1 import _accepted
from tests.runtime.slippage._fixtures import model as bps_model, zero_model


def _market_state(event):
    return SlippageMarketState(
        "normal", event.event_time, event.available_time, event.event_id,
        event.revision_id, event.event_hash)


def _zero_for(order, event):
    applicability = SlippageApplicabilityEnvelope.create(
        envelope_key="synthetic.cn.portfolio.open.development.v1", envelope_version=1,
        instrument_id=order.intent.instrument_id,
        valid_from=UtcInstant(event.event_time.epoch_nanoseconds - 1),
        valid_to_exclusive=UtcInstant(event.event_time.epoch_nanoseconds + 1),
        maximum_quantity=order.intent.quantity, allowed_market_state_keys=("normal",))
    return replace(zero_model(), applicability_envelope=applicability)


def _open_source(item, plan, cash, positions, reservations, at, *, approved=True):
    prop, order, market, fee, observation = item
    risk = CnASharePortfolioOpenRiskApprovalDevelopmentV1.create(
        plan=plan, proposal=prop, order=order, market=market, fee=fee,
        open_price=observation.open_price, open_event_hash=observation.event.event_hash,
        evaluated_at=at, open_cash=cash, open_sellability=positions,
        reservation_state=reservations)
    event = observation.event
    liquidity = BarLiquidityEvidence.create(
        evidence_key="synthetic.cn.open-liquidity", evidence_version=1,
        market_event=event, evaluated_at=event.available_time,
        approved=approved, reason_code=None if approved else "limit_blocked",
        source_hash="sha256:" + "7" * 64)
    return risk, liquidity, _market_state(event), _zero_for(order, event)


def test_two_stock_same_open_produces_development_fill_with_native_slippage():
    plan, cash, positions, reservations, evidence, at = _opening_case()
    results = []
    for digit, item in (("6", evidence[0]), ("7", evidence[1])):
        prop, order, _, _, observation = item
        stream, _, _, recreated = _accepted(prop, digit, fee=505)
        assert recreated == order
        risk, liquidity, market_state, zero = _open_source(
            item, plan, cash, positions, reservations, at)
        result = evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=observation,
            risk=risk, liquidity=liquidity, market_state=market_state,
            slippage_model=zero, eligibility_window_exhausted=True)
        assert result.action is NoEligibleBarAction.FULL_FILL
        assert isinstance(result.fill, Fill)
        assert result.fill.order_id == order.order_id
        assert result.fill.instrument_id == prop.intent.instrument_id
        assert result.fill.reference_price == observation.open_price
        assert result.fill.price == observation.open_price
        assert result.fill.slippage_amount.units == 0
        assert not result.trade_authorized and result.synthetic_development_only
        results.append(result)
    assert {r.fill.venue_id.value for r in results if r.fill} == {"xshg", "xshe"}
    assert len({r.fill.fill_id for r in results if r.fill}) == 2
    assert results[0].outcome_hash != results[1].outcome_hash


def test_open_block_and_substitution_never_yield_a_fill():
    plan, cash, positions, reservations, evidence, at = _opening_case()
    prop, order, _, _, observation = evidence[0]
    stream, _, _, _ = _accepted(prop, "6", fee=505)
    risk, liquidity, state, zero = _open_source(
        evidence[0], plan, cash, positions, reservations, at, approved=False)
    blocked = evaluate_cn_a_share_portfolio_next_open_development_v1(
        plan=plan, stream=stream, observation=observation,
        risk=risk, liquidity=liquidity, market_state=state,
        slippage_model=None, eligibility_window_exhausted=True)
    assert blocked.action is NoEligibleBarAction.EXPIRE and blocked.fill is None
    assert blocked.reason == "liquidity_blocked"
    with pytest.raises(ValueError, match="missing BarOpen source"):
        evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=None, risk=None, liquidity=None,
            market_state=None, slippage_model=None, eligibility_window_exhausted=True)
    with pytest.raises(ValueError, match="lacks independent"):
        evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=observation,
            risk=None, liquidity=liquidity, market_state=state,
            slippage_model=zero, eligibility_window_exhausted=True)
    other_event = evidence[1][4].event
    foreign_liquidity = BarLiquidityEvidence.create(
        evidence_key="synthetic.cn.open-liquidity", evidence_version=1,
        market_event=other_event, evaluated_at=other_event.available_time,
        approved=True, reason_code=None, source_hash="sha256:" + "7" * 64)
    with pytest.raises(ValueError, match="gate evidence"):
        evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=observation,
            risk=risk, liquidity=foreign_liquidity,
            market_state=state, slippage_model=zero, eligibility_window_exhausted=True)
    with pytest.raises(ValueError, match="unfunded slippage"):
        evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=observation,
            risk=risk, liquidity=_open_source(evidence[0], plan, cash, positions, reservations, at)[1],
            market_state=state, slippage_model=replace(
                bps_model(), applicability_envelope=zero.applicability_envelope),
            eligibility_window_exhausted=True)
