from __future__ import annotations

from functools import lru_cache

from crypto_quant_backtest import (
    BAR_OPEN_CAPABILITY,
    BAR_OPEN_EVENT_TYPE,
    BarLiquidityEvidence,
    BarOpenCandidate,
    BarOpenObservation,
    NextBarOpenRequest,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageMarketState,
    SlippageRequest,
    DeterministicBpsSlippageModel,
    SimulationComponentRef,
    SimulationPortType,
)
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    OrderSide,
    Quantity,
    RoundingPolicy,
    Scale,
    SourceSequence,
    TimelinePhase,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading import (
    FeeReservationEstimator,
    MarketRuleApproval,
    MarketRuleEvaluator,
    OrderRuleEvaluationInput,
    PreTradeResourceRequirement,
    PreTradeRiskApproval,
    PreTradeRiskEvaluationInput,
    PreTradeRiskEvaluator,
)
from tests.kernel.fee_reservations._fixtures import rule_set as fee_rule_set
from tests.kernel.integration.test_order_acceptance_journey import run_journey
from tests.kernel.market_rules._fixtures import reference_notional_evidence


BAR_PHASE = TimelinePhase(60, "bar_open")


@lru_cache(maxsize=1)
def accepted_journey():
    return run_journey()


@lru_cache(maxsize=1)
def execution_approvals() -> tuple[MarketRuleApproval, PreTradeRiskApproval]:
    instant = UtcInstant(300)
    journey = accepted_journey()
    old_pretrade = journey["pretrade"]
    old_input = old_pretrade.evaluation_input
    old_market = old_input.market_rule_approval
    market_source = OrderRuleEvaluationInput(
        executable_order_spec=old_market.evaluation_input.executable_order_spec,
        evaluated_at=instant,
        notional_evidence=reference_notional_evidence(
            price_units=3_000_000,
            available_at=300,
        ),
    )
    market_outcome = MarketRuleEvaluator().evaluate(
        market_source,
        old_market.rule_timeline,
    )
    assert market_outcome.approval is not None
    market = market_outcome.approval
    reservation = FeeReservationEstimator().estimate(
        market,
        fee_rule_set(),
        instant,
    )
    assert reservation.proposal is not None
    requirement = PreTradeResourceRequirement.create(
        requirement_source_key="synthetic.cash.wp06e-resource.v1",
        requirement_source_version=1,
        requirement_source_hash=canonical_sha256(
            {
                "market_rule_decision_id": market.decision_id,
                "fee_proposal_id": reservation.proposal.proposal_id,
                "account_profile": "synthetic.cash.wp06e.v1",
            }
        ),
        market_rule_approval=market,
        fee_reservation_proposal=reservation.proposal,
        commitment=old_input.resource_requirement.commitment,
    )
    source = PreTradeRiskEvaluationInput(
        market_rule_approval=market,
        fee_reservation_proposal=reservation.proposal,
        resource_requirement=requirement,
        reservation_state=old_input.reservation_state,
        availability_state=old_input.availability_state,
        account_risk_policy=old_input.account_risk_policy,
        evaluated_at=instant,
    )
    pretrade_outcome = PreTradeRiskEvaluator().evaluate(source)
    assert pretrade_outcome.approval is not None
    return market, pretrade_outcome.approval


def bar_event(
    *,
    instant: int = 300,
    sequence: int = 1,
    kind: str = "real",
    price_units: int = 3_100_000,
    extra_payload: dict[str, object] | None = None,
) -> MarketEvent:
    order = accepted_journey()["order"]
    payload: dict[str, object] = {
        "schema_version": 1,
        "bar_kind": kind,
        "open_price": (
            {
                "units": price_units,
                "scale": 2,
                "quote_currency": "USD",
            }
            if kind == "real"
            else None
        ),
    }
    if extra_payload:
        payload.update(extra_payload)
    return MarketEvent(
        event_id=f"bar-open:{instant}:{sequence}:{kind}",
        stream_key="bars.open",
        event_type=BAR_OPEN_EVENT_TYPE,
        capability=BAR_OPEN_CAPABILITY,
        instrument_id=order.intent.instrument_id,
        event_time=UtcInstant(instant),
        available_time=UtcInstant(instant),
        phase=BAR_PHASE,
        source_sequence=SourceSequence(sequence),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key="synthetic.bar-open.v1",
        source_hash="sha256:" + "71" * 32,
        payload=payload,
    )


def liquidity_evidence(
    event: MarketEvent,
    *,
    approved: bool = True,
    reason_code: str | None = None,
) -> BarLiquidityEvidence:
    return BarLiquidityEvidence.create(
        evidence_key="synthetic.bar-liquidity.v1",
        evidence_version=1,
        market_event=event,
        evaluated_at=event.available_time,
        approved=approved,
        reason_code=reason_code,
        source_hash="sha256:" + "72" * 32,
    )


def candidate(
    *,
    instant: int = 300,
    kind: str = "real",
    liquidity_approved: bool = True,
    reason_code: str | None = None,
    extra_payload: dict[str, object] | None = None,
) -> BarOpenCandidate:
    event = bar_event(
        instant=instant,
        kind=kind,
        extra_payload=extra_payload,
    )
    observation = BarOpenObservation.from_event(event)
    if kind != "real":
        return BarOpenCandidate(
            observation=observation,
            market_rule_approval=None,
            pretrade_risk_approval=None,
            liquidity_evidence=None,
            market_state=None,
        )
    market, pretrade = execution_approvals()
    return BarOpenCandidate(
        observation=observation,
        market_rule_approval=market,
        pretrade_risk_approval=pretrade,
        liquidity_evidence=liquidity_evidence(
            event,
            approved=liquidity_approved,
            reason_code=reason_code,
        ),
        market_state=SlippageMarketState(
            state_key="normal",
            observed_at=event.event_time,
            available_at=event.available_time,
            source_event_id=event.event_id,
            revision_id=event.revision_id,
            evidence_hash=event.event_hash,
        ),
    )


def model(
    *,
    day_action: NoEligibleBarAction = NoEligibleBarAction.EXPIRE,
) -> NextEligibleBarOpenModel:
    actions = {
        TimeInForce.DAY: day_action,
        TimeInForce.GTC: NoEligibleBarAction.KEEP_ACTIVE,
        TimeInForce.IOC: NoEligibleBarAction.EXPIRE,
        TimeInForce.FOK: NoEligibleBarAction.EXPIRE,
        TimeInForce.GTX: NoEligibleBarAction.KEEP_ACTIVE,
    }
    return NextEligibleBarOpenModel.create(
        actions=tuple(actions.items()),
    )


def request(
    *,
    bar_candidate: BarOpenCandidate | None = None,
    eligibility_window_exhausted: bool = False,
) -> NextBarOpenRequest:
    return NextBarOpenRequest(
        order_stream=accepted_journey()["accepted_stream"],
        candidate=bar_candidate,
        eligibility_window_exhausted=eligibility_window_exhausted,
    )


def slippage_model(decision) -> DeterministicBpsSlippageModel:
    assert decision.reference_price is not None
    assert decision.fill_quantity is not None
    instrument = decision.reference_price.mark.instrument_id
    reference_time = decision.reference_price.mark.resolved_at
    envelope = SlippageApplicabilityEnvelope.create(
        envelope_key="synthetic.next-open.bps.v1",
        envelope_version=1,
        instrument_id=instrument,
        valid_from=UtcInstant(reference_time.epoch_nanoseconds - 1),
        valid_to_exclusive=UtcInstant(reference_time.epoch_nanoseconds + 1),
        maximum_quantity=Quantity(
            decision.fill_quantity.units,
            decision.fill_quantity.scale,
            str(instrument),
        ),
        allowed_market_state_keys=("normal",),
    )
    component = SimulationComponentRef(
        port_type=SimulationPortType.SLIPPAGE_MODEL,
        component_key="deterministic_bps.v1",
        component_version=1,
        component_digest="sha256:" + "73" * 32,
    )
    return DeterministicBpsSlippageModel(
        component_ref=component,
        calibration_ref=SlippageCalibrationRef(
            calibration_key="synthetic.next-open.calibration.v1",
            calibration_version=1,
            calibration_digest="sha256:" + "74" * 32,
        ),
        applicability_envelope=envelope,
        basis_points_units=10,
        basis_points_scale=Scale(0),
        rounding=RoundingPolicy.HALF_UP,
        limitations=(),
    )


def slippage_request(decision) -> SlippageRequest:
    assert decision.reference_price is not None
    assert decision.fill_quantity is not None
    assert decision.candidate is not None
    assert decision.candidate.market_state is not None
    return SlippageRequest(
        reference_price=decision.reference_price,
        side=decision.request.order_stream.order.intent.side,
        quantity=decision.fill_quantity,
        market_state=decision.candidate.market_state,
    )


def fill_id() -> DomainId:
    return DomainId(DomainIdKind.FILL, "fil_" + "9" * 64)


def altered_quantity(quantity: Quantity) -> Quantity:
    return Quantity(quantity.units - 1, quantity.scale, quantity.instrument_id)
