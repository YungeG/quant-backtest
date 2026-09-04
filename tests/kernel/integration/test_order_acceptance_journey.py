from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, TypedDict, cast

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Money,
    Order,
    OrderEvent,
    OrderEventType,
    OrderSide,
    OrderStatus,
    PositionEffect,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    AccountRiskPolicy,
    CapabilityRejection,
    ExposureCapacityLimit,
    FeeAssessmentEngine,
    FeeChargedJournalTranslator,
    FeeReservationBasis,
    FeeReserveFundingSource,
    FeeReservationEstimator,
    FeeReservationFailure,
    MarketRuleApproval,
    MarketRuleDataIntegrityFailure,
    MarketRuleEvaluator,
    MarketSessionState,
    MarketRuleRejection,
    OrderCapabilityApproval,
    OrderCapabilityValidator,
    OrderEventRecord,
    OrderEventStream,
    OrderPlan,
    OrderRuleEvaluationInput,
    OrderTranslationResult,
    OrderTranslator,
    PreTradeResourceRequirement,
    PreTradeRiskApproval,
    PreTradeRiskContractFailure,
    PreTradeRiskEvaluationInput,
    PreTradeRiskEvaluator,
    PreTradeRiskRejection,
    RebalanceCoordinator,
    ReservationCommitment,
    ResourceReservationProposal,
    ResourceReservationState,
)
from tests.kernel.capabilities._fixtures import capability_set
from tests.kernel.fee_reservations._fixtures import (
    account_rule as reservation_account_rule,
    market_rule as reservation_market_rule,
    rule_set as reservation_rule_set,
    tax_rule as reservation_tax_rule,
)
from tests.kernel.fees._fixtures import (
    assessment_time,
    cash_key,
    domain_id,
    fill_basis,
    recorded_at,
    rule_set as final_fee_rule_set,
)
from tests.kernel.market_rules._fixtures import (
    evaluation_input as market_rule_input,
    interval as market_rule_interval,
    reference_notional_evidence,
    snapshot as market_rule_snapshot,
    timeline as market_rule_timeline,
)
from tests.kernel.pretrade_risk._fixtures import availability_state
from tests.kernel.rebalance._fixtures import (
    availability as planning_availability,
    normalized_target,
    policy as rebalance_policy,
    reservation_state as planning_reservation_state,
    snapshot as planning_snapshot,
    validity,
)
from tests.kernel.translation._fixtures import field_rules, mapping


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/target-to-accepted-order-journey-v1.json"
ORDER_PHASE = TimelinePhase(80, "g05_order_acceptance")


class Journey(TypedDict):
    plan: OrderPlan
    order: Order
    capability: OrderCapabilityApproval
    translation_hash: str
    market_rule_id: str
    fee_estimate_id: str
    fee_proposal_hash: str
    pretrade: PreTradeRiskApproval
    accepted_stream: OrderEventStream
    fee_assessment_hash: str
    fee_journal_hash: str
    journal_hash: str


def instant(nanoseconds: int, sequence: int) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds), ORDER_PHASE, SourceSequence(sequence)
    )


def order_id(digit: str = "8") -> DomainId:
    return DomainId(DomainIdKind.ORDER, f"ord_{digit * 64}")


def plan_order() -> tuple[OrderPlan, Order]:
    target = normalized_target()
    portfolio_snapshot = planning_snapshot()
    reservations = planning_reservation_state()
    availability = planning_availability(portfolio_snapshot, reservations)
    coordinator = RebalanceCoordinator()
    first = coordinator.coordinate(
        target=target,
        target_validity=validity(),
        portfolio_snapshot=portfolio_snapshot,
        working_orders=(),
        reservations=reservations,
        availability=availability,
        policy=rebalance_policy(),
        as_of=UtcInstant(200),
    )
    assert first.decision is not None
    plan = first.decision.plan
    repeated = coordinator.coordinate(
        target=target,
        target_validity=validity(),
        portfolio_snapshot=portfolio_snapshot,
        working_orders=(),
        reservations=reservations,
        availability=availability,
        policy=rebalance_policy(),
        as_of=UtcInstant(200),
        prior_plan=plan,
    )
    assert repeated.decision is not None
    assert repeated.decision.plan is plan
    assert len(plan.planned_orders) == 1
    planned = plan.planned_orders[0]
    subject = Order(
        order_id=order_id(),
        account_id=plan.account_id,
        intent=planned.intent,
        created_at=instant(200, 1),
    )
    return plan, subject


def approved_market_rule(
    subject: Order, capability: OrderCapabilityApproval
) -> tuple[OrderTranslationResult, MarketRuleApproval]:
    translation = OrderTranslator().translate(
        subject, capability, mapping(), UtcInstant(210)
    )
    assert translation.executable_spec is not None
    source = OrderRuleEvaluationInput(
        executable_order_spec=translation.executable_spec,
        evaluated_at=UtcInstant(220),
        notional_evidence=reference_notional_evidence(
            price_units=3_000_000, available_at=205
        ),
    )
    decision = MarketRuleEvaluator().evaluate(
        source,
        market_rule_timeline(
            intervals=(market_rule_interval(stop=400),)
        ),
    )
    assert decision.approval is not None
    return translation, decision.approval


def approved_pretrade(
    market_approval: MarketRuleApproval,
    proposal: ResourceReservationProposal,
) -> tuple[PreTradeRiskEvaluationInput, PreTradeRiskApproval]:
    state = ResourceReservationState(
        account_id=market_approval.evaluation_input.executable_order_spec.source_order.account_id,
        cursors=(),
        active_reservations=(),
        totals=ReservationCommitment.empty(),
    )
    available = availability_state(
        state,
        usd_tradable_units=100_000_000,
        usd_margin_units=100_000_000,
    )
    commitment = ReservationCommitment(
        cash=(market_approval.calculated_notional,),
        fee_reserve=proposal.commitment.fee_reserve,
        order_capacity_units=1,
        exposure_capacity=(market_approval.calculated_notional,),
    )
    requirement = PreTradeResourceRequirement.create(
        requirement_source_key="synthetic.cash.g05-resource.v1",
        requirement_source_version=1,
        requirement_source_hash=canonical_sha256(
            {
                "market_rule_decision_id": market_approval.decision_id,
                "fee_proposal_id": proposal.proposal_id,
                "account_profile": "synthetic.cash.g05.v1",
            }
        ),
        market_rule_approval=market_approval,
        fee_reservation_proposal=proposal,
        commitment=commitment,
    )
    order = market_approval.evaluation_input.executable_order_spec.source_order
    policy = AccountRiskPolicy.create(
        policy_key="synthetic.cash.g05-account-risk.v1",
        policy_version=1,
        account_id=order.account_id,
        venue_id=order.intent.instrument_id.venue,
        allowed_sides=(OrderSide.BUY, OrderSide.SELL),
        allowed_position_effects=(
            PositionEffect.AUTO,
            PositionEffect.OPEN,
            PositionEffect.CLOSE,
        ),
        allowed_reduce_only_values=(False, True),
        fee_reserve_funding_source=FeeReserveFundingSource.TRADABLE_CASH,
        order_capacity_limit=10,
        exposure_capacity_limits=(
            ExposureCapacityLimit(Money(100_000_000, Scale(2), "USD")),
        ),
    )
    source = PreTradeRiskEvaluationInput(
        market_rule_approval=market_approval,
        fee_reservation_proposal=proposal,
        resource_requirement=requirement,
        reservation_state=state,
        availability_state=available,
        account_risk_policy=policy,
        evaluated_at=UtcInstant(240),
    )
    outcome = PreTradeRiskEvaluator().evaluate(source)
    assert outcome.approval is not None
    return source, outcome.approval


def accepted_stream(
    subject: Order,
    capability: OrderCapabilityApproval,
    translation_hash: str,
    market_rule_id: str,
    fee_estimate_id: str,
    pretrade_id: str,
) -> OrderEventStream:
    stages = (
        (
            OrderEventType.ORDER_INTENT_CREATED,
            subject.intent.parent_id,
            canonical_sha256(subject.intent),
        ),
        (
            OrderEventType.ORDER_CAPABILITY_APPROVED,
            "",
            capability.decision_id,
        ),
        (OrderEventType.ORDER_TRANSLATED, "", translation_hash),
        (OrderEventType.MARKET_RULE_APPROVED, "", market_rule_id),
        (OrderEventType.FEE_RESERVATION_ESTIMATED, "", fee_estimate_id),
        (OrderEventType.PRE_TRADE_RISK_APPROVED, "", pretrade_id),
        (OrderEventType.ORDER_SUBMITTED, "", "submission:synthetic:g05"),
        (OrderEventType.ORDER_ACCEPTED, "", "acceptance:synthetic:g05"),
    )
    records: list[OrderEventRecord] = []
    previous_event_id = subject.intent.parent_id
    for index, (event_type, explicit_cause, evidence_id) in enumerate(stages, start=1):
        cause = explicit_cause or previous_event_id
        event = OrderEvent(
            event_id=f"event:g05:{index}:{event_type.value}",
            order_id=subject.order_id,
            causation_id=cause,
            event_type=event_type,
            occurred_at=(
                subject.created_at if index == 1 else instant(200 + index, index)
            ),
            fill_id=None,
            evidence_id=evidence_id,
        )
        records.append(OrderEventRecord(event))
        previous_event_id = event.event_id
    return OrderEventStream.from_records(subject, tuple(records))


def run_journey() -> Journey:
    plan, subject = plan_order()
    capability_decision = OrderCapabilityValidator().validate(
        subject.intent, capability_set()
    )
    assert capability_decision.approval is not None
    capability = capability_decision.approval
    translation, market_approval = approved_market_rule(subject, capability)
    reservation = FeeReservationEstimator().estimate(
        market_approval,
        reservation_rule_set(),
        UtcInstant(230),
    )
    assert reservation.estimate is not None
    assert reservation.proposal is not None
    _, pretrade = approved_pretrade(market_approval, reservation.proposal)
    stream = accepted_stream(
        subject,
        capability,
        translation.result_hash,
        market_approval.decision_id,
        reservation.estimate.estimate_id,
        pretrade.decision_id,
    )
    assert stream.state is not None
    assert stream.state.status is OrderStatus.ACCEPTED

    final_fee = FeeAssessmentEngine().assess(
        basis=fill_basis(side=OrderSide.SELL),
        rule_set=final_fee_rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "5"),
        assessment_time=assessment_time(),
    )
    assert final_fee.result is not None
    fee_journal = FeeChargedJournalTranslator().translate(
        result=final_fee.result,
        cash_key=cash_key(),
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "e"),
        recorded_at=recorded_at(),
    )
    assert fee_journal.result is not None
    journal = AccountingJournal.empty().append(
        fee_journal.result.journal_entry
    )
    assert journal.append(fee_journal.result.journal_entry) is journal

    return {
        "plan": plan,
        "order": subject,
        "capability": capability,
        "translation_hash": translation.result_hash,
        "market_rule_id": market_approval.decision_id,
        "fee_estimate_id": reservation.estimate.estimate_id,
        "fee_proposal_hash": reservation.proposal.proposal_hash,
        "pretrade": pretrade,
        "accepted_stream": stream,
        "fee_assessment_hash": final_fee.result.result_hash,
        "fee_journal_hash": fee_journal.result.result_hash,
        "journal_hash": journal.journal_hash,
    }


def canonical_json(value: object) -> object:
    return json.loads(canonical_bytes(value))


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G05 fixture: {FIXTURE}") from error


def test_active_target_reaches_one_exact_accepted_order_and_final_fee_journal() -> None:
    fixture = load_fixture()
    journey = run_journey()
    plan = journey["plan"]
    subject = journey["order"]
    stream = journey["accepted_stream"]

    assert len(plan.planned_orders) == 1
    assert subject.intent.quantity == plan.planned_orders[0].intent.quantity
    assert stream.state is not None
    assert stream.state.status is OrderStatus.ACCEPTED
    actual = {
        "fixture_id": "target-to-accepted-order-journey-v1",
        "active_target_hash": canonical_sha256(normalized_target().active_target),
        "plan_id": plan.plan_id,
        "plan_hash": plan.plan_hash,
        "order": canonical_json(subject),
        "capability_id": journey["capability"].decision_id,
        "capability_hash": canonical_sha256(journey["capability"]),
        "translation_hash": journey["translation_hash"],
        "market_rule_id": journey["market_rule_id"],
        "fee_estimate_id": journey["fee_estimate_id"],
        "fee_proposal_hash": journey["fee_proposal_hash"],
        "pretrade_id": journey["pretrade"].decision_id,
        "pretrade_hash": journey["pretrade"].decision_hash,
        "accepted_order_state": canonical_json(stream.state),
        "accepted_stream_hash": stream.stream_hash,
        "fee_assessment_hash": journey["fee_assessment_hash"],
        "fee_journal_hash": journey["fee_journal_hash"],
        "journal_hash": journey["journal_hash"],
    }
    assert actual == fixture


def test_gate_failures_remain_nominally_distinct_and_cannot_reach_accepted() -> None:
    _, subject = plan_order()
    capability_rejected = OrderCapabilityValidator().validate(
        subject.intent, capability_set(styles=())
    )
    assert isinstance(capability_rejected.rejection, CapabilityRejection)
    assert capability_rejected.approval is None

    capability = OrderCapabilityValidator().validate(
        subject.intent, capability_set()
    ).approval
    assert capability is not None
    translation_rejected = OrderTranslator().translate(
        subject,
        capability,
        mapping(rules=field_rules()[:-1]),
        UtcInstant(210),
    )
    assert translation_rejected.executable_spec is None
    assert translation_rejected.report.status.value == "rejected"

    translation, _ = approved_market_rule(subject, capability)
    assert translation.executable_spec is not None
    rejected_market = MarketRuleEvaluator().evaluate(
        market_rule_input(
            spec=translation.executable_spec,
            evaluated_at=220,
            notional_evidence=reference_notional_evidence(
                price_units=3_000_000, available_at=205
            ),
        ),
        market_rule_timeline(
            intervals=(
                market_rule_interval(
                    stop=400,
                    rule_snapshot=market_rule_snapshot(
                        session_state=MarketSessionState.CLOSED
                    ),
                ),
            )
        ),
    )
    assert isinstance(rejected_market.rejection, MarketRuleRejection)
    missing_rule = MarketRuleEvaluator().evaluate(
        market_rule_input(
            spec=translation.executable_spec,
            evaluated_at=220,
            notional_evidence=reference_notional_evidence(
                price_units=3_000_000, available_at=205
            ),
        ),
        market_rule_timeline(),
    )
    assert isinstance(missing_rule.data_integrity_failure, MarketRuleDataIntegrityFailure)

    _, market_approval = approved_market_rule(subject, capability)
    unknown_market_fee = replace(
        reservation_market_rule(),
        basis=FeeReservationBasis.UNKNOWN,
        rate=None,
    )
    fee_failed = FeeReservationEstimator().estimate(
        market_approval,
        reservation_rule_set(
            rules=(
                unknown_market_fee,
                reservation_tax_rule(),
                reservation_account_rule(),
            ),
            minimums=(),
        ),
        UtcInstant(230),
    )
    assert isinstance(fee_failed.failure, FeeReservationFailure)
    assert fee_failed.proposal is None

    fee_ok = FeeReservationEstimator().estimate(
        market_approval, reservation_rule_set(), UtcInstant(230)
    )
    assert fee_ok.proposal is not None
    risk_input, _ = approved_pretrade(market_approval, fee_ok.proposal)
    low_cash = replace(
        risk_input,
        availability_state=availability_state(
            risk_input.reservation_state,
            usd_tradable_units=1,
            usd_margin_units=1,
        ),
    )
    risk_rejected = PreTradeRiskEvaluator().evaluate(low_cash)
    assert isinstance(risk_rejected.rejection, PreTradeRiskRejection)
    assert risk_rejected.contract_failure is None
    stale_availability = replace(
        risk_input.availability_state,
        reservation_state_hash="sha256:" + "0" * 64,
    )
    risk_contract_failed = PreTradeRiskEvaluator().evaluate(
        replace(risk_input, availability_state=stale_availability)
    )
    assert isinstance(
        risk_contract_failed.contract_failure, PreTradeRiskContractFailure
    )
    assert risk_contract_failed.rejection is None

    distinct = {
        type(capability_rejected.rejection).__name__,
        type(translation_rejected.report).__name__,
        type(rejected_market.rejection).__name__,
        type(missing_rule.data_integrity_failure).__name__,
        type(fee_failed.failure).__name__,
        type(risk_rejected.rejection).__name__,
        type(risk_contract_failed.contract_failure).__name__,
    }
    assert len(distinct) == 7


def test_journey_is_deterministic_and_has_no_runtime_or_market_data_dependency() -> None:
    first = run_journey()
    second = run_journey()
    first_values = (
        first["plan"],
        first["order"],
        first["capability"],
        first["pretrade"],
        first["accepted_stream"],
    )
    second_values = (
        second["plan"],
        second["order"],
        second["capability"],
        second["pretrade"],
        second["accepted_stream"],
    )
    for first_value, second_value in zip(
        first_values, second_values, strict=True
    ):
        assert canonical_sha256(first_value) == canonical_sha256(second_value)
    first_hashes = (
        first["translation_hash"],
        first["market_rule_id"],
        first["fee_estimate_id"],
        first["fee_proposal_hash"],
        first["fee_assessment_hash"],
        first["fee_journal_hash"],
        first["journal_hash"],
    )
    second_hashes = (
        second["translation_hash"],
        second["market_rule_id"],
        second["fee_estimate_id"],
        second["fee_proposal_hash"],
        second["fee_assessment_hash"],
        second["fee_journal_hash"],
        second["journal_hash"],
    )
    assert first_hashes == second_hashes
