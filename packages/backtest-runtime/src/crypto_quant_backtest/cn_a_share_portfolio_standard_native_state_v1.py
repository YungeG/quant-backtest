"""Pure native live-state operators for the standard CN portfolio Engine.

No preparation, diagnostic Case conversion, predicted quantities, PnL or I/O.
The profile caller owns order admission, source binding and atomic attempt proof.
"""
from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import (
    CurrencyId, DecisionBatch, ExecutionStyle, Money, PortfolioSnapshot, PositionBalanceKey,
    OrderStatus, PricePurpose, RoundingPolicy, Scale, SimulationInstant, TimeInForce,
    canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading import (
    AccountingJournal, ApprovedPortfolioTarget, AtomicDecisionBatchCollector,
    AvailabilityProjection, CapitalAllocationPolicyRef, CurrencyValuationGraph,
    DecisionBatchExpectation, DecisionBatchSubmission, GenericLedger,
    InstrumentSizingInput, MarketSettlementRules, NormalizedPortfolioTarget,
    OrderEventStream, OrderPlan, OrderReservationSchedule, PortfolioAllocation,
    PortfolioAllocator, PortfolioRiskAction, PortfolioRiskEvaluator, PortfolioRiskLimit,
    PortfolioRiskPolicy, PortfolioRiskScope, PortfolioSnapshotProjector, PositionSizer,
    PositionSizingPolicy, RebalanceCoordinator, RebalancePolicy, ResidualPositionPolicy,
    ResourceReservationBook, SettlementBook, StrategyAllocation,
    StrategyOutputValidationContext, StrategyOutputValidator, TargetValidity,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashQuantityLatticeModel, CnAShareQuantityLatticeQuery,
)

from .cn_a_share_portfolio_standard_definition_v1 import (
    CnASharePortfolioMarkBatchDevelopmentV1, CnASharePortfolioStandardDevelopmentInputsV1,
)
from .target_stream import PrecomputedTargetStreamAdapter

_CNY = CurrencyId("CNY")
_CENT = Scale(2)
_NOTIONAL = Scale(14)


def _native_snapshot_at_v1(
    inputs: CnASharePortfolioStandardDevelopmentInputsV1,
    journal: AccountingJournal, marks: CnASharePortfolioMarkBatchDevelopmentV1,
) -> PortfolioSnapshot:
    """Project current native cash, lots and fees exactly once at the source clock."""
    if (type(inputs) is not CnASharePortfolioStandardDevelopmentInputsV1
            or type(journal) is not AccountingJournal
            or type(marks) is not CnASharePortfolioMarkBatchDevelopmentV1):
        raise TypeError("native snapshot requires exact source DTO, Journal and marks")
    prefix = inputs.initial_journal.entries
    if (journal.entries[:len(prefix)] != prefix
            or any(e.account_id != inputs.scope.account_id or e.recorded_at > marks.at
                   for e in journal.entries)
            or {m.instrument_id for m in marks.marks} != set(inputs.scope.instrument_ids)):
        raise ValueError("native snapshot source prefix, account, scope or full-clock mismatch")
    projected = PortfolioSnapshotProjector().project_cash_ledger(
        ledger_state=GenericLedger(inputs.scope.ledger_schema).project(journal),
        resolved_marks=marks.marks, reporting_currency=_CNY, reporting_scale=_CENT,
        projection_at=marks.at, instrument_catalog=inputs.scope.instrument_catalog,
        currency_valuation_graph=CurrencyValuationGraph(marks.at.instant, PricePurpose.VALUATION, ()),
        notional_quantization=inputs.notional_quantization)
    if projected.snapshot is None:
        raise ValueError("native current snapshot rejected: " + str(projected.failure))
    return projected.snapshot


@dataclass(frozen=True, slots=True)
class _NativeSignalTargetV1:
    snapshot: PortfolioSnapshot
    decision_batch: DecisionBatch
    allocation: PortfolioAllocation
    approved_target: ApprovedPortfolioTarget
    normalized_target: NormalizedPortfolioTarget
    target_validity: TargetValidity

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_native_signal_target", "schema_version": 1,
                "snapshot": self.snapshot, "decision_batch": self.decision_batch,
                "allocation": self.allocation, "approved_target": self.approved_target,
                "normalized_target": self.normalized_target, "target_validity": self.target_validity}


def _native_signal_target_v1(
    *, inputs: CnASharePortfolioStandardDevelopmentInputsV1,
    journal: AccountingJournal, event: MarketEvent,
) -> _NativeSignalTargetV1:
    """Native equal-weight/cash intent from CURRENT equity and CURRENT quantities."""
    if type(event) is not MarketEvent or event.event_time != event.available_time:
        raise ValueError("native signal requires an exact currently available target event")
    at = SimulationInstant(event.event_time, event.phase, event.source_sequence)
    batches = tuple(b for b in inputs.signal_marks if b.at == at)
    if len(batches) != 1:
        raise ValueError("native signal lacks exact full-clock frozen mark cover")
    marks = batches[0]
    snapshot = _native_snapshot_at_v1(inputs, journal, marks)
    if snapshot.equity.units <= 0:
        raise ValueError("native signal has no positive live equity")
    candidate, issues = PrecomputedTargetStreamAdapter()._decode(event)
    if candidate is None or issues:
        raise ValueError("native target source decode rejected: " + str(issues))
    payload = candidate.payload.fields
    from crypto_quant_domain import StrategySleeveId
    validated = StrategyOutputValidator().validate(candidate, StrategyOutputValidationContext(
        expected_strategy_id=payload["strategy_id"],
        expected_sleeve_id=StrategySleeveId(payload["sleeve_id"]), decision_time=at.instant,
        instrument_catalog=inputs.scope.instrument_catalog,
        universe=inputs.scope.instrument_ids, decision_instant=at))
    if validated.decision is None:
        raise ValueError("native strategy target rejected: " + str(validated.failure))
    decision = validated.decision
    weights = tuple(t for t in decision.target_snapshot.targets if t.units)
    if any(t.units < 0 or t.units * len(weights) != t.scale.factor for t in weights):
        raise ValueError("native standard policy requires long equal-weight or cash intent")
    expectation = DecisionBatchExpectation(decision.strategy_id, decision.target_snapshot.sleeve_id)
    collected = AtomicDecisionBatchCollector().collect(decision_time=at.instant, decision_instant=at,
        expected=(expectation,), submissions=(DecisionBatchSubmission(expectation, validated),))
    if collected.batch is None or collected.state is None:
        raise ValueError("native signal decision batch rejected: " + str(collected.failure))
    allocation_input = StrategyAllocation(
        decision.strategy_id, decision.target_snapshot.sleeve_id, at.instant, _CNY, snapshot.equity,
        CapitalAllocationPolicyRef("cn.portfolio.live-equity.equal-weight.development", 1,
            canonical_sha256({"basis": "current_native_snapshot_equity", "exposure": "1"})),
        canonical_sha256(snapshot), valuation_instant=at)
    allocated = PortfolioAllocator().allocate(sleeve_state=collected.state,
        portfolio_snapshot=snapshot, allocations=(allocation_input,), target_notional_scale=_NOTIONAL)
    if allocated.allocation is None:
        raise ValueError("native live allocation rejected: " + str(allocated.failure))
    maximum = Money(snapshot.equity.units * 10 ** (_NOTIONAL.places - _CENT.places), _NOTIONAL, "CNY")
    limits = tuple(PortfolioRiskLimit("stock." + str(i), PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
        maximum, PortfolioRiskAction.REJECT, i)
        for i in (target.instrument_id for target in allocated.allocation.net_targets)) + tuple(
        PortfolioRiskLimit(s.value, s, maximum, PortfolioRiskAction.REJECT, None) for s in
        (PortfolioRiskScope.GROSS_EXPOSURE, PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE))
    risk = PortfolioRiskEvaluator().evaluate(allocation=allocated.allocation,
        policy=PortfolioRiskPolicy.create(policy_key="cn.portfolio.live-long-equity.development", policy_version=1,
            valuation_currency=_CNY, notional_scale=_NOTIONAL, limits=limits))
    if risk.approved_target is None:
        raise ValueError("native live portfolio risk rejected: " + str(risk.failure))
    ledger = GenericLedger(inputs.scope.ledger_schema).project(journal)
    by_mark = {m.instrument_id: m for m in marks.marks}
    sizing_inputs = []
    for target in risk.approved_target.targets:
        instrument = target.source_target.instrument_id
        lattice = CnAShareCashQuantityLatticeModel(instrument.venue, _NOTIONAL).resolve_instrument(
            CnAShareQuantityLatticeQuery(inputs.scope.instrument_catalog.instrument(instrument)))
        if lattice.result is None:
            raise ValueError("native CN quantity lattice rejected")
        key = PositionBalanceKey(inputs.scope.account_id, instrument.venue, instrument)
        sizing_inputs.append(InstrumentSizingInput(instrument, by_mark[instrument],
            ledger.position_quantity(key), lattice.result.quantity_lattice))
    sized = PositionSizer().materialize(approved_target=risk.approved_target,
        source_decision_batch_id=collected.batch.decision_batch_id,
        policy=PositionSizingPolicy.create(policy_key="cn.portfolio.live-signal-close.development",
            policy_version=1, price_purpose=PricePurpose.VALUATION, rounding=RoundingPolicy.TOWARD_ZERO,
            residual_policy=ResidualPositionPolicy.CLOSE_IF_PERMITTED), inputs=tuple(sizing_inputs))
    if sized.normalized_target is None:
        raise ValueError("native live position sizing rejected: " + str(sized.failure))
    normalized = sized.normalized_target
    validity = TargetValidity(normalized.normalized_target_id, normalized.normalized_target_hash,
        decision.target_snapshot.effective_time, decision.target_snapshot.expires_at)
    return _NativeSignalTargetV1(snapshot, collected.batch, allocated.allocation,
        risk.approved_target, normalized, validity)


def _native_rebalance_plan_v1(
    *, inputs: CnASharePortfolioStandardDevelopmentInputsV1,
    signal: _NativeSignalTargetV1, journal: AccountingJournal,
    settlement_book: SettlementBook, order_streams: tuple[OrderEventStream, ...],
    reservation_schedules: tuple[OrderReservationSchedule, ...],
    market_rules: MarketSettlementRules, at: SimulationInstant,
) -> OrderPlan:
    """Native deltas include absent held stocks/cash exits; they are NOT Fills.

    Superseded pooled working reservations must first be cancelled by the CN
    caller using its versioned plan. Never feed an invented venue-local cash
    allocation to legacy AvailabilityProjection to hide an ambiguous CNY hold.
    """
    normalized = signal.normalized_target
    if (type(signal) is not _NativeSignalTargetV1 or type(at) is not SimulationInstant
            or type(settlement_book) is not SettlementBook
            or type(market_rules) is not MarketSettlementRules
            or settlement_book.account_id != inputs.scope.account_id
            or market_rules.account_id != inputs.scope.account_id
            or normalized.materialized_instant is None or at < normalized.materialized_instant
            or any(e.recorded_at > at for e in journal.entries)
            or any(e.occurred_at > at for e in settlement_book.events)
            or any(s.state is None or s.state.updated_at > at for s in order_streams)):
        raise ValueError("native rebalance source account or full-clock mismatch")
    ledger = GenericLedger(inputs.scope.ledger_schema).project(journal)
    if ledger.state_hash != signal.snapshot.journal_state_hash:
        raise ValueError("native rebalance signal snapshot and current Journal prefix differ")
    reservations = ResourceReservationBook(inputs.scope.account_id).project(order_streams, reservation_schedules)
    availability = AvailabilityProjection().project(ledger, settlement_book.project(), reservations, market_rules)
    outcome = RebalanceCoordinator().coordinate(
        target=normalized,
        target_validity=signal.target_validity,
        portfolio_snapshot=signal.snapshot,
        working_orders=tuple(s for s in order_streams if s.state is not None and s.state.status in
            {OrderStatus.ACCEPTED, OrderStatus.ACTIVE, OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCEL_REQUESTED}),
        reservations=reservations, availability=availability,
        policy=RebalancePolicy.create(policy_key="cn.portfolio.native-deltas.development", policy_version=1,
            execution_style=ExecutionStyle.MARKET, time_in_force=TimeInForce.GTC,
            urgency="normal", plan_valid_for_nanoseconds=None), as_of=at.instant)
    if outcome.decision is None:
        raise ValueError("native portfolio rebalance rejected: " + str(outcome.failure))
    canonical_bytes(outcome.decision.plan)
    return outcome.decision.plan
