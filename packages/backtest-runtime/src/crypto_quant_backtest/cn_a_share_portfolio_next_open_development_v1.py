"""Backtest-owned CN portfolio REAL next-open development Fill port.

Separate from the frozen single-venue BarOpenCandidate/FullFillBuilder. It
requires source-bound pooled Kernel risk and native explicit zero-slippage.
NO economic publication, fee assessment, terminal Engine or trade authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from crypto_quant_domain import (
    DomainId, DomainIdKind, Fill, Money, OrderStatus, PricePurpose,
    TimeInForce, canonical_sha256,
)
from crypto_quant_trading.orders import OrderEventStream
from crypto_quant_trading.profiles.cn_a_share.portfolio_order_plan_v1 import CnASharePortfolioOrderPlanV1
from crypto_quant_trading.profiles.cn_a_share.portfolio_open_risk_development_v1 import (
    CnASharePortfolioOpenRiskApprovalDevelopmentV1,
)

from .execution import (
    BarIneligibilityReason, BarLiquidityEvidence, BarOpenCandidate, BarOpenKind,
    BarOpenObservation, NextBarOpenRequest, NextEligibleBarOpenModel,
    NoEligibleBarAction, _reference_mark,  # pyright: ignore[reportPrivateUsage]
)
from .slippage import (
    DeterministicBpsSlippageModel, ExecutionReferencePrice,
    SlippageLimitation, SlippageMarketState, SlippageRequest,
)

_NO_BAR = NextEligibleBarOpenModel.create(actions=(
    (TimeInForce.DAY, NoEligibleBarAction.EXPIRE),
    (TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE),
    (TimeInForce.IOC, NoEligibleBarAction.EXPIRE),
    (TimeInForce.FOK, NoEligibleBarAction.EXPIRE),
    (TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE),
))


@dataclass(frozen=True, slots=True)
class CnASharePortfolioNextOpenDevelopmentOutcomeV1:
    plan_hash: str
    order_stream_hash: str
    observation_hash: str | None
    risk_approval_hash: str | None
    action: NoEligibleBarAction
    reason: str | None
    fill: Fill | None
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.action) is not NoEligibleBarAction
                or (self.action is NoEligibleBarAction.FULL_FILL) != (type(self.fill) is Fill)
                or (self.fill is not None and self.reason is not None)
                or (self.fill is None and self.reason is None)):
            raise ValueError("CN portfolio open action/fill/reason mismatch")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_next_open_development_outcome",
                "schema_version": 1, "plan_hash": self.plan_hash,
                "order_stream_hash": self.order_stream_hash,
                "observation_hash": self.observation_hash,
                "risk_approval_hash": self.risk_approval_hash,
                "action": self.action.value, "reason": self.reason, "fill": self.fill,
                "synthetic_development_only": True, "trade_authorized": False}


def evaluate_cn_a_share_portfolio_next_open_development_v1(
    *, plan: CnASharePortfolioOrderPlanV1, stream: OrderEventStream,
    observation: BarOpenObservation | None,
    risk: CnASharePortfolioOpenRiskApprovalDevelopmentV1 | None,
    liquidity: BarLiquidityEvidence | None, market_state: SlippageMarketState | None,
    slippage_model: DeterministicBpsSlippageModel | None,
    eligibility_window_exhausted: bool,
) -> CnASharePortfolioNextOpenDevelopmentOutcomeV1:
    """One accepted Order and one source-observed next open, never final PnL."""
    if (type(plan) is not CnASharePortfolioOrderPlanV1
            or type(stream) is not OrderEventStream or type(eligibility_window_exhausted) is not bool
            or (observation is not None and type(observation) is not BarOpenObservation)):
        raise TypeError("next open needs exact Order stream, observation and window evidence")
    state = stream.state
    if (stream.order.account_id != plan.account_id
            or all(p.intent != stream.order.intent for p in plan.proposed)
            or stream.order.intent.time_in_force is not plan.policy.time_in_force_for(stream.order.intent.side)):
        raise ValueError("next open Order not bound to versioned portfolio plan")
    if state is None or state.status not in {OrderStatus.ACCEPTED, OrderStatus.ACTIVE}:
        raise ValueError("next open requires accepted non-partial Order")
    if observation is None:
        raise ValueError("missing BarOpen source is not no-eligible-open evidence")
    if (observation.event.instrument_id != stream.order.intent.instrument_id
            or observation.event.event_time <= state.updated_at.instant
            or observation.event.event_time < plan.as_of):
        raise ValueError("CN portfolio BarOpen precedes plan or Order source")
    if observation.kind is not BarOpenKind.REAL:
        if any(value is not None for value in (risk, liquidity, market_state, slippage_model)):
            raise ValueError("non-real opening cannot carry fill approval")
        candidate = BarOpenCandidate(observation, None, None, None, None)
        native = _NO_BAR.simulate_execution(NextBarOpenRequest(
            stream, candidate, eligibility_window_exhausted))
        if native.result is None:
            raise ValueError("native non-real Bar failed")
        reason = observation.kind.value
        return CnASharePortfolioNextOpenDevelopmentOutcomeV1(
            plan.plan_hash,
            stream.stream_hash, observation.observation_hash,
            None, native.result.action, reason, None)
    event = observation.event
    if (event.instrument_id != stream.order.intent.instrument_id
            or event.event_time <= state.updated_at.instant
            or event.event_time != event.available_time
            or observation.open_price is None or observation.open_price.quote_currency != "CNY"):
        raise ValueError("CN portfolio real open is stale or wrong instrument/currency")
    return _evaluate_cn_portfolio_real_open_v1(
        plan=plan, stream=stream, observation=observation, risk=risk,
        liquidity=liquidity, market_state=market_state, slippage_model=slippage_model,
        eligibility_window_exhausted=eligibility_window_exhausted)


def _evaluate_cn_portfolio_real_open_v1(
    *, plan: CnASharePortfolioOrderPlanV1, stream: OrderEventStream,
    observation: BarOpenObservation,
    risk: CnASharePortfolioOpenRiskApprovalDevelopmentV1 | None,
    liquidity: BarLiquidityEvidence | None, market_state: SlippageMarketState | None,
    slippage_model: DeterministicBpsSlippageModel | None,
    eligibility_window_exhausted: bool,
) -> CnASharePortfolioNextOpenDevelopmentOutcomeV1:
    """Native real-Fill core; each versioned caller checks its own admission clock."""
    state = stream.state
    if state is None:
        raise ValueError("real opening needs an Order state")
    event = observation.event
    if (type(risk) is not CnASharePortfolioOpenRiskApprovalDevelopmentV1
            or type(liquidity) is not BarLiquidityEvidence
            or type(market_state) is not SlippageMarketState):
        raise ValueError("CN portfolio real Bar lacks independent market/pooled risk/liquidity state")
    if (risk.plan != plan or risk.order != stream.order
            or risk.open_event_hash != event.event_hash
            or risk.open_price != observation.open_price
            or risk.evaluated_at != event.available_time
            or liquidity.market_event_id != event.event_id
            or liquidity.market_event_hash != event.event_hash
            or liquidity.evaluated_at != event.available_time
            or market_state.source_event_id != event.event_id
            or market_state.evidence_hash != event.event_hash
            or market_state.revision_id != event.revision_id
            or market_state.observed_at > event.event_time
            or market_state.available_at > event.available_time):
        raise ValueError("CN portfolio real Bar gate evidence is stale or substituted")
    if not liquidity.approved:
        native = _NO_BAR.simulate_execution(NextBarOpenRequest(
            stream, None, eligibility_window_exhausted))
        if native.result is None:
            raise ValueError("native liquidity no-fill failed")
        return CnASharePortfolioNextOpenDevelopmentOutcomeV1(
            risk.plan.plan_hash, stream.stream_hash, observation.observation_hash,
            risk.approval_hash, native.result.action,
            BarIneligibilityReason.LIQUIDITY_BLOCKED.value, None)
    if (type(slippage_model) is not DeterministicBpsSlippageModel
            or slippage_model.basis_points_units != 0
            or slippage_model.limitations != (SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,)):
        raise ValueError("unfunded slippage is forbidden; require explicit development-zero model")
    fill = _native_cn_portfolio_zero_slippage_fill_v1(
        stream=stream, observation=observation, market_state=market_state,
        slippage_model=slippage_model, approval_hash=risk.approval_hash)
    return CnASharePortfolioNextOpenDevelopmentOutcomeV1(
        risk.plan.plan_hash, stream.stream_hash, observation.observation_hash,
        risk.approval_hash, NoEligibleBarAction.FULL_FILL, None, fill)


def _native_cn_portfolio_zero_slippage_fill_v1(
    *, stream: OrderEventStream, observation: BarOpenObservation,
    market_state: SlippageMarketState, slippage_model: DeterministicBpsSlippageModel,
    approval_hash: str,
) -> Fill:
    """Shared native full Fill only; versioned callers own risk/clock/liquidity gates."""
    state = stream.state
    if (state is None or type(slippage_model) is not DeterministicBpsSlippageModel
            or slippage_model.basis_points_units != 0
            or slippage_model.limitations != (SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,)):
        raise ValueError("native full Fill needs working state and explicit development-zero model")
    event = observation.event
    reference = ExecutionReferencePrice(_reference_mark(observation))
    slip = slippage_model.decide_slippage(SlippageRequest(
        reference, stream.order.intent.side, state.remaining_quantity, market_state))
    if slip.result is None or slip.result.execution_price != observation.open_price:
        raise ValueError("native development slippage not applicable to this Bar/order")
    decision = slip.result
    fill_id = DomainId(DomainIdKind.FILL,
        f"{DomainIdKind.FILL.prefix}_" + canonical_sha256({
            "type": "cn_a_share_portfolio_development_open_fill_identity",
            "order_id": stream.order.order_id,
            "open_event_hash": event.event_hash,
            "risk_approval_hash": approval_hash,
            "slippage_decision_id": decision.decision_id,
        })[7:])
    return Fill(
        fill_id=fill_id, order_id=stream.order.order_id, account_id=stream.order.account_id,
        venue_id=stream.order.intent.instrument_id.venue,
        instrument_id=stream.order.intent.instrument_id, side=stream.order.intent.side,
        quantity=state.remaining_quantity, reference_price=reference.mark.price,
        reference_price_purpose=PricePurpose.EXECUTION_REFERENCE, price=decision.execution_price,
        slippage_amount=Money(decision.slippage_amount.units, decision.slippage_amount.scale,
                              decision.slippage_amount.quote_currency),
        slippage_decision_id=decision.decision_id,
        slippage_model_key=decision.component_ref.component_key,
        slippage_calibration_id=canonical_sha256(decision.calibration_ref),
        liquidity="full", execution_time=event.event_time,
    )


def evaluate_cn_a_share_portfolio_observed_open_admission_development_v2(
    *, plan: CnASharePortfolioOrderPlanV1, stream: OrderEventStream,
    observation: BarOpenObservation | None,
    risk: CnASharePortfolioOpenRiskApprovalDevelopmentV1 | None,
    liquidity: BarLiquidityEvidence | None, market_state: SlippageMarketState | None,
    slippage_model: DeterministicBpsSlippageModel | None,
    eligibility_window_exhausted: bool,
) -> CnASharePortfolioNextOpenDevelopmentOutcomeV1:
    """Conditional observed-open admission, NOT an auction/queue fill guarantee.

    Estimates before the open are uncommitted. Actual market/fee/budget approval
    and acceptance follow the raw observation within its modeled UTC instant.
    This independent DEVELOPMENT operation never relaxes the V1 time gate.
    """
    from crypto_quant_domain import OrderEventType

    if (type(plan) is not CnASharePortfolioOrderPlanV1
            or type(stream) is not OrderEventStream
            or type(observation) is not BarOpenObservation
            or type(eligibility_window_exhausted) is not bool):
        raise TypeError("observed-open admission requires exact native source values")
    event, state = observation.event, stream.state
    if (observation.kind is not BarOpenKind.REAL or observation.open_price is None
            or event.event_time != event.available_time or plan.as_of != event.event_time
            or state is None or state.status is not OrderStatus.ACCEPTED
            or state.updated_at.instant != event.event_time
            or state.updated_at.phase.rank <= event.phase.rank
            or stream.order.created_at.instant >= event.event_time
            or stream.order.account_id != plan.account_id
            or event.instrument_id != stream.order.intent.instrument_id
            or all(p.intent != stream.order.intent for p in plan.proposed)
            or stream.order.intent.time_in_force is not plan.policy.time_in_force_for(stream.order.intent.side)):
        raise ValueError("observed-open admission clock, Order or plan mismatch")
    if type(risk) is not CnASharePortfolioOpenRiskApprovalDevelopmentV1:
        raise ValueError("observed-open admission lacks native pooled risk")
    kinds = (OrderEventType.ORDER_INTENT_CREATED, OrderEventType.ORDER_CAPABILITY_APPROVED,
             OrderEventType.ORDER_TRANSLATED, OrderEventType.MARKET_RULE_APPROVED,
             OrderEventType.FEE_RESERVATION_ESTIMATED, OrderEventType.PRE_TRADE_RISK_APPROVED,
             OrderEventType.ORDER_SUBMITTED, OrderEventType.ORDER_ACCEPTED)
    events = tuple(r.event for r in stream.records)
    spec = risk.market.evaluation_input.executable_order_spec
    evidence = (spec.capability_approval.decision_id, spec.spec_id, risk.market.decision_id,
                risk.fee.proposal_hash, plan.plan_hash, event.event_hash, event.event_hash)
    if (tuple(e.event_type for e in events) != kinds
            or tuple(e.evidence_id for e in events[1:]) != evidence
            or any(e.occurred_at.instant != stream.order.created_at.instant for e in events[:3])
            or any(e.occurred_at.instant != event.event_time
                   or e.occurred_at.phase.rank <= event.phase.rank for e in events[3:])):
        raise ValueError("observed-open approval history is stale, backdated or substituted")
    cursors = tuple(c for c in risk.reservation_state.cursors if c.order_id == stream.order.order_id)
    active = tuple(c for c in risk.reservation_state.active_reservations
                   if c.order_id == stream.order.order_id)
    if (len(cursors) != 1 or cursors[0].stream_hash != stream.stream_hash
            or cursors[0].event_count != len(stream.records)
            or len(active) != 1 or active[0].last_update_event_id != state.last_event_id):
        raise ValueError("observed-open reservation does not bind the accepted stream prefix")
    return _evaluate_cn_portfolio_real_open_v1(
        plan=plan, stream=stream, observation=observation, risk=risk,
        liquidity=liquidity, market_state=market_state, slippage_model=slippage_model,
        eligibility_window_exhausted=eligibility_window_exhausted)
