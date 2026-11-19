"""Pure native economic state, complete checkpoints and allocation consumers."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from crypto_quant_domain import (
    CurrencyId, DecisionBatch, ExecutionStyle, Money, PortfolioSnapshot, PositionBalanceKey,
    OrderStatus, PricePurpose, RoundingPolicy, Scale, SimulationInstant, TimeInForce,
    canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading import (
    AccountingJournal, ApprovedPortfolioTarget, AtomicDecisionBatchCollector, AtomicDecisionBatchResult,
    AvailabilityProjection, CapitalAllocationPolicyRef, CurrencyValuationGraph,
    DecisionBatchExpectation, DecisionBatchSubmission, GenericLedger,
    InstrumentSizingInput, LatestSleeveDecisionState, MarketSettlementRules, NormalizedPortfolioTarget,
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

from .cn_a_share_portfolio_economic_definition_v1 import (
    CnASharePortfolioEconomicDevelopmentInputsV1,
)
from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2
from .target_stream import PrecomputedTargetStreamAdapter

from crypto_quant_domain import AccountingEntryType, CashBalanceKey, AccountingJournalEntry
from crypto_quant_trading import ResourceReservationState
from crypto_quant_trading.profiles.cn_a_share.portfolio_v1 import (
    CnASharePortfolioSellabilitySnapshotV1, project_cn_a_share_portfolio_sellability_v1,
    CnAShareSharedCnyCashSnapshotV1, project_cn_a_share_shared_cny_cash_v1,
)
import crypto_quant_domain as d
import crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 as e
from .cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioMarkBatchDevelopmentV1
from .cn_a_share_portfolio_standard_native_state_v1 import _NativeSignalTargetV1
from .cn_a_share_portfolio_settlement_development_v1 import _build_cn_a_share_portfolio_settlement_facts_v1, _book_body
from .engine import EngineFailureCode
from .profile_portfolio_execution import (
    _ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION, _ECONOMIC_SEGMENTED_SPECS,
)

_CNY = CurrencyId("CNY")
_CENT = Scale(2)
_NOTIONAL = Scale(14)


class _EconomicNativeFailureV1(Exception):
    def __init__(self, code: EngineFailureCode, evidence: object, *, operation=None, native_inputs=None, original_claim=None):
        self.operation,self.native_inputs,self.original_claim=operation,native_inputs,original_claim
        self.code, self.evidence = code, evidence
        self.evidence_hash = canonical_sha256(evidence)
        super().__init__(code.value)


def _advance_economic_settlement_v1(*, case, inputs, journal, book, consumer):
    """Expose complete native due batches at their own full clock, never at now."""
    from .cn_a_share_portfolio_settlement_development_v1 import CnASharePortfolioSettlementDevelopmentV1
    from crypto_quant_trading import SettlementEventType
    if (type(inputs) not in (CnASharePortfolioEconomicDevelopmentInputsV1, CnASharePortfolioEconomicDevelopmentInputsV2) or type(journal) is not AccountingJournal
            or type(book) is not SettlementBook or type(consumer) is not SimulationInstant):
        raise TypeError("economic settlement advance requires exact immutable source values")
    if book.account_id != inputs.scope.account_id or any(event.occurred_at > consumer for event in book.events):
        raise ValueError("economic settlement Book has foreign account or future committed facts")
    # Historical specs retain their original closing behavior.
    version = case.semantic_spec.spec_version
    exclusive = (version in _ECONOMIC_SEGMENTED_SPECS or
        (type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2
         and version == _ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION))
    end = case.timeline.window.end_exclusive if exclusive else None
    while True:
        pending = book.project().pending_obligations
        if not pending:
            return book
        due = min(row.obligation.settlement_time for row in pending)
        if due > consumer.instant or (end is not None and due >= end):
            return book
        group = tuple(row for row in pending if row.obligation.settlement_time == due)
        clocks = tuple(SimulationInstant(due, d.TimelinePhase(20, "settlement_due"), d.SourceSequence(index))
                       for index in range(1, len(group) + 1))
        if book.events and book.events[-1].occurred_at >= clocks[0]:
            raise ValueError("missed native settlement due boundary behind committed prefix")
        if clocks[0] > consumer:
            return book
        if clocks[-1] > consumer:
            raise ValueError("consumer splits an atomic native settlement batch")
        advanced = CnASharePortfolioSettlementDevelopmentV1(canonical_sha256(journal),
            tuple(c.calendar_hash for c in inputs.calendars), book).apply_due(due).book
        delta = advanced.events[len(book.events):]
        if (advanced.obligations != book.obligations or advanced.events[:len(book.events)] != book.events
                or tuple(event.occurred_at for event in delta) != clocks
                or tuple(event.settlement_obligation_id for event in delta) != tuple(row.obligation.settlement_obligation_id for row in group)
                or any(event.event_type is not SettlementEventType.SETTLEMENT_APPLIED for event in delta)):
            raise ValueError("native settlement batch changed shape/order/clock or failed to advance")
        book = advanced


def _economic_marks_at_v1(inputs, at):
    if type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2:
        from .cn_a_share_portfolio_economic_activation_v2 import (
            _economic_activation_at_v2, _economic_financial_checkpoints_v2, _resolve_retained_economic_marks_v2,
        )
        batches = (inputs.initial_marks, _resolve_retained_economic_marks_v2(inputs, _economic_activation_at_v2(inputs)),
            *inputs.daily_marks, *_economic_financial_checkpoints_v2(inputs))
    else:
        batches = (inputs.initial_marks, *inputs.signal_marks, *inputs.daily_marks, *inputs.checkpoint_marks)
    rows = tuple(b for b in batches if b.at == at)
    if len(rows) != 1:
        raise d.ArtifactIntegrityError("economic consumer lacks one exact retained mark batch")
    return rows[0]


def _economic_projection_at_v1(*, inputs, journal, settlement_book, order_streams,
    reservation_schedules, market_rules, dividend_state, marks):
    outcome = e.project_cn_a_share_portfolio_economic_state_v1(e.CnASharePortfolioEconomicProjectionInputsV1(
        journal, inputs.scope.ledger_schema, settlement_book, order_streams, reservation_schedules,
        market_rules, inputs.scope.instrument_catalog, marks.marks,
        CurrencyValuationGraph(marks.at.instant, PricePurpose.VALUATION, ()), inputs.notional_quantization,
        dividend_state, marks.at))
    if outcome.projection is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.SNAPSHOT_PROJECTION_FAILURE, outcome.failure,
            operation="economic_projection",native_inputs={"inputs":e.CnASharePortfolioEconomicProjectionInputsV1(
                journal,inputs.scope.ledger_schema,settlement_book,order_streams,reservation_schedules,market_rules,
                inputs.scope.instrument_catalog,marks.marks,CurrencyValuationGraph(marks.at.instant,PricePurpose.VALUATION,()),
                inputs.notional_quantization,dividend_state,marks.at)},original_claim={"marks":marks})
    return outcome.projection


@dataclass(frozen=True, slots=True)
class _EconomicOpenSourcesV1:
    inputs: CnASharePortfolioEconomicDevelopmentInputsV1 | CnASharePortfolioEconomicDevelopmentInputsV2
    journal: AccountingJournal
    settlement_book: SettlementBook
    order_streams: tuple[OrderEventStream, ...]
    reservation_schedules: tuple[OrderReservationSchedule, ...]
    market_rules: MarketSettlementRules
    dividend_state: e.CnAShareCashDividendStateV1
    journal_entry_ids: tuple[tuple[str, d.DomainId], ...]
    at: SimulationInstant
    economic_projection: e.CnASharePortfolioEconomicProjectionV1 = field(init=False)
    cash: CnAShareSharedCnyCashSnapshotV1 = field(init=False)
    sellability: CnASharePortfolioSellabilitySnapshotV1 = field(init=False)
    reservations: ResourceReservationState = field(init=False)
    available_by_venue: tuple[tuple[CashBalanceKey, Money], ...] = field(init=False)

    def __post_init__(self) -> None:
        if (type(self.inputs) not in (CnASharePortfolioEconomicDevelopmentInputsV1, CnASharePortfolioEconomicDevelopmentInputsV2)
                or type(self.journal) is not AccountingJournal
                or type(self.settlement_book) is not SettlementBook
                or type(self.market_rules) is not MarketSettlementRules
                or type(self.at) is not SimulationInstant
                or type(self.order_streams) is not tuple
                or any(type(s) is not OrderEventStream for s in self.order_streams)
                or type(self.reservation_schedules) is not tuple
                or any(type(s) is not OrderReservationSchedule for s in self.reservation_schedules)):
            raise TypeError("economic opening requires exact native full-clock source facts")
        scope = self.inputs.scope
        initial = self.inputs.initial_journal.entries
        if (self.journal.entries[:len(initial)] != initial
                or self.settlement_book.account_id != scope.account_id
                or self.market_rules.account_id != scope.account_id
                or any(e.account_id != scope.account_id or e.recorded_at > self.at for e in self.journal.entries)
                or any(e.occurred_at > self.at for e in self.settlement_book.events)
                or any(s.order.account_id != scope.account_id
                       or s.order.intent.instrument_id not in scope.instrument_ids or s.order.created_at > self.at
                       or s.state is None or s.state.updated_at > self.at for s in self.order_streams)):
            raise ValueError("economic opening source account, Journal prefix or full-clock mismatch")
        suffix = self.journal.entries[len(initial):]
        if any(e.entry_type not in {AccountingEntryType.FILL_BOOKED, AccountingEntryType.FEE_CHARGED,
                                   AccountingEntryType.CAPITAL_TRANSFERRED, AccountingEntryType.CORPORATE_ACTION_CASH_PAID,
                                   AccountingEntryType.CORPORATE_ACTION_TAX_PAID} for e in suffix):
            raise ValueError("economic runtime cannot create new capital or unrelated economic attribution")
        transfers: dict[tuple[str, ...], list[AccountingJournalEntry]] = {}
        for entry in suffix:
            if entry.entry_type is AccountingEntryType.CAPITAL_TRANSFERRED:
                transfers.setdefault(entry.source_ids, []).append(entry)
        for pair in transfers.values():
            changes = tuple(c for e in pair for c in e.balance_changes)
            if (len(pair) != 2 or len(changes) != 2
                    or {e.venue_id.value for e in pair} != {"xshg", "xshe"}
                    or pair[0].recorded_at.instant != pair[1].recorded_at.instant
                    or any(e.position_lot_changes or e.realized_pnl or e.fees or e.financing for e in pair)
                    or any(type(c.key) is not CashBalanceKey or type(c.value) is not Money
                           or c.value.currency != "CNY" or c.value.scale != _CENT for c in changes)
                    or changes[0].value.units == 0
                    or any(e.venue_id != c.key.venue_id for e in pair for c in e.balance_changes)
                    or changes[0].value.units + changes[1].value.units != 0):
                raise ValueError("economic funding must retain the WHOLE native equal-CNY two-leg pair")
        fills = tuple(r.fill for s in self.order_streams for r in s.records if r.fill is not None)
        entries = tuple(e for e in suffix if e.entry_type is AccountingEntryType.FILL_BOOKED)
        if len(fills) != len(entries) or len({f.fill_id for f in fills}) != len(fills):
            raise ValueError("economic current sources lost historical native Fill/Journal facts")
        for fill in fills:
            linked = tuple(e for e in entries if fill.fill_id.value in e.source_ids)
            obligations = tuple(ob for ob in self.settlement_book.obligations
                                if ob.obligation.source_fill_id == fill.fill_id)
            if (len(linked) != 1 or len(obligations) != 2
                    or linked[0].account_id != fill.account_id or linked[0].venue_id != fill.venue_id):
                raise ValueError("economic current sources lost native Fill/Journal/T+1 obligation cover")
        if {ob.obligation.source_fill_id for ob in self.settlement_book.obligations} != {f.fill_id for f in fills}:
            raise ValueError("economic current Book contains foreign or missing Fill sources")
        if fills:
            expected = _build_cn_a_share_portfolio_settlement_facts_v1(fills=fills,
                journal=self.journal, source_hash=canonical_sha256(fills), calendars=self.inputs.calendars).book
            if self.settlement_book.obligations != expected.obligations:
                raise ValueError("economic current Book differs from exact native T+1 amount/key/time resolution")
        if type(self.dividend_state) is not e.CnAShareCashDividendStateV1 or self.dividend_state.as_of > self.at:
            raise ValueError("economic source state is invalid or future")
        history = e.CnAShareCashDividendHistoryInputsV1(self.journal, scope.ledger_schema,
            self.settlement_book, self.order_streams, self.reservation_schedules, self.market_rules,
            scope.instrument_catalog, self.dividend_state, self.inputs.dividend_actions, self.journal_entry_ids, self.at)
        rejected = e.verify_cn_a_share_cash_dividend_history_v1(history)
        if rejected is not None:
            raise d.ArtifactIntegrityError("economic dividend history mismatch: " + d.canonical_sha256(rejected))
        state = replace(self.dividend_state, as_of=self.at)
        rejected = e.verify_cn_a_share_cash_dividend_history_v1(replace(history, dividend_state=state))
        if rejected is not None:
            raise d.ArtifactIntegrityError("economic checkpoint crosses an unapplied model boundary")
        marks = _economic_marks_at_v1(self.inputs, self.at)
        projection = _economic_projection_at_v1(inputs=self.inputs, journal=self.journal,
            settlement_book=self.settlement_book, order_streams=self.order_streams,
            reservation_schedules=self.reservation_schedules, market_rules=self.market_rules,
            dividend_state=state, marks=marks)
        cash = project_cn_a_share_shared_cny_cash_v1(journal=self.journal, ledger_schema=scope.ledger_schema,
            settlement_book=self.settlement_book, order_streams=self.order_streams,
            reservation_schedules=self.reservation_schedules, market_rules=self.market_rules, as_of=self.at.instant)
        sellability = project_cn_a_share_portfolio_sellability_v1(journal=self.journal,
            ledger_schema=scope.ledger_schema, settlement_book=self.settlement_book,
            order_streams=self.order_streams, reservation_schedules=self.reservation_schedules,
            market_rules=self.market_rules, as_of=self.at.instant)
        reservations = ResourceReservationBook(scope.account_id).project(self.order_streams, self.reservation_schedules)
        object.__setattr__(self, "dividend_state", state)
        object.__setattr__(self, "economic_projection", projection)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "sellability", sellability)
        object.__setattr__(self, "reservations", reservations)
        object.__setattr__(self, "available_by_venue", tuple((r.key, r.spendable) for r in projection.cash_rows))

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_sources", "schema_version": 1,
            "definition_hash": self.inputs._definition_source_hash, "at": self.at,
            "journal_count": self.journal.entry_count, "journal_hash": self.journal.journal_hash,
            "ledger_hash": GenericLedger(self.inputs.scope.ledger_schema).project(self.journal).state_hash,
            "book": _book_body(self.settlement_book),
            "order_stream_hashes": tuple(s.stream_hash for s in self.order_streams),
            "schedule_hashes": tuple(s.schedule_hash for s in self.reservation_schedules),
            "market_rules_hash": self.market_rules.rules_hash, "dividend_state": self.dividend_state,
            "journal_entry_ids": self.journal_entry_ids, "economic_projection": self.economic_projection,
            "sellability": self.sellability, "reservations": self.reservations}


def _economic_signal_target_v1(*, sources: _EconomicOpenSourcesV1, event: MarketEvent):
    inputs = sources.inputs
    if type(event) is not MarketEvent or event.event_time != event.available_time:
        raise d.ArtifactIntegrityError("economic target source is not currently available")
    at = SimulationInstant(event.event_time, event.phase, event.source_sequence)
    if sources.at != at:
        raise ValueError("economic signal must consume its exact source-clock projection")
    # Preserve V1 mark/equity rejection precedence before decoding the source.
    _economic_marks_at_v1(inputs, at)
    _require_economic_equity_v1(sources, event)
    collected = _collect_economic_decision_v1(inputs=inputs, event=event,
        original_claim={"source": sources, "event": event})
    return _economic_signal_from_batch_v1(sources=sources, event=event, collected=collected,
        allocation_state=collected.state, valid_from=collected.batch.decisions[0].target_snapshot.effective_time)


def _require_economic_equity_v1(sources: _EconomicOpenSourcesV1, event: MarketEvent) -> None:
    projection = sources.economic_projection
    if projection.snapshot.equity.units <= 0:
        raise _EconomicNativeFailureV1(EngineFailureCode.ALLOCATION, projection, operation='economic_equity_allocation', native_inputs={"projection":projection}, original_claim={"source":sources,"event":event})


def _collect_economic_decision_v1(*, inputs, event, original_claim) -> AtomicDecisionBatchResult:
    at = SimulationInstant(event.event_time, event.phase, event.source_sequence)
    candidate, issues = PrecomputedTargetStreamAdapter()._decode(event)
    if candidate is None or issues:
        raise _EconomicNativeFailureV1(EngineFailureCode.TARGET_INPUT_DECODE, issues, operation='target_decode', native_inputs={"event":event}, original_claim=original_claim)
    payload = candidate.payload.fields
    from crypto_quant_domain import StrategySleeveId
    validated = StrategyOutputValidator().validate(candidate, StrategyOutputValidationContext(
        expected_strategy_id=payload["strategy_id"],
        expected_sleeve_id=StrategySleeveId(payload["sleeve_id"]), decision_time=at.instant,
        instrument_catalog=inputs.scope.instrument_catalog,
        universe=inputs.scope.instrument_ids, decision_instant=at))
    if validated.decision is None:
        from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2
        from crypto_quant_trading import StrategyValidationFailure
        evidence = validated
        if type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2:
            if type(validated.failure) is not StrategyValidationFailure:
                raise TypeError("economic V2 validation rejection requires exact native failure")
            evidence = validated.failure
        raise _EconomicNativeFailureV1(EngineFailureCode.TARGET_VALIDATION, evidence, operation='target_validation', native_inputs={'candidate': candidate, 'context': StrategyOutputValidationContext(expected_strategy_id=payload['strategy_id'], expected_sleeve_id=StrategySleeveId(payload['sleeve_id']), decision_time=at.instant, instrument_catalog=inputs.scope.instrument_catalog, universe=inputs.scope.instrument_ids, decision_instant=at)}, original_claim=original_claim)
    decision = validated.decision
    weights = tuple(t for t in decision.target_snapshot.targets if t.units)
    if any(t.units < 0 or t.units * len(weights) != t.scale.factor for t in weights):
        raise ValueError("native standard policy requires long equal-weight or cash intent")
    expectation = DecisionBatchExpectation(decision.strategy_id, decision.target_snapshot.sleeve_id)
    collected = AtomicDecisionBatchCollector().collect(decision_time=at.instant, decision_instant=at,
        expected=(expectation,), submissions=(DecisionBatchSubmission(expectation, validated),))
    if collected.batch is None or collected.state is None:
        from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2
        from crypto_quant_trading import DecisionBatchFailure
        evidence = collected
        if type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2:
            if type(collected.failure) is not DecisionBatchFailure:
                raise TypeError("economic V2 collection rejection requires exact native failure")
            evidence = collected.failure
        raise _EconomicNativeFailureV1(EngineFailureCode.DECISION_BATCH, evidence, operation='decision_batch_collection', native_inputs={'decision_time': at.instant, 'decision_instant': at, 'expected': (expectation,), 'submissions': (DecisionBatchSubmission(expectation, validated),)}, original_claim=original_claim)
    return collected


def _economic_signal_from_batch_v1(*, sources: _EconomicOpenSourcesV1, event: MarketEvent,
    collected: AtomicDecisionBatchResult, allocation_state: LatestSleeveDecisionState,
    valid_from: d.UtcInstant,
) -> tuple[_NativeSignalTargetV1, e.CnASharePortfolioEconomicProjectionV1]:
    inputs, journal, at = sources.inputs, sources.journal, sources.at
    marks = _economic_marks_at_v1(inputs, at)
    projection = sources.economic_projection
    snapshot = projection.snapshot
    decision = collected.batch.decisions[0]
    allocation_input = StrategyAllocation(
        decision.strategy_id, decision.target_snapshot.sleeve_id, at.instant, _CNY, snapshot.equity,
        CapitalAllocationPolicyRef("cn.portfolio.economic-equity.equal-weight.development", 1,
            canonical_sha256({"basis": "current_economic_projection", "projection_hash": projection.projection_hash, "exposure": "1"})),
        canonical_sha256(snapshot), valuation_instant=at)
    allocated = PortfolioAllocator().allocate(sleeve_state=allocation_state,
        portfolio_snapshot=snapshot, allocations=(allocation_input,), target_notional_scale=_NOTIONAL)
    if allocated.allocation is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.ALLOCATION, allocated, operation='portfolio_allocation', native_inputs={'sleeve_state': allocation_state, 'portfolio_snapshot': snapshot, 'allocations': (allocation_input,), 'target_notional_scale': _NOTIONAL}, original_claim={"source":sources,"event":event})
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
        raise _EconomicNativeFailureV1(EngineFailureCode.PORTFOLIO_RISK, risk, operation='portfolio_risk', native_inputs={'allocation': allocated.allocation, 'policy': PortfolioRiskPolicy.create(policy_key='cn.portfolio.live-long-equity.development', policy_version=1, valuation_currency=_CNY, notional_scale=_NOTIONAL, limits=limits)}, original_claim={"source":sources,"event":event})
    ledger = GenericLedger(inputs.scope.ledger_schema).project(journal)
    by_mark = {m.instrument_id: m for m in marks.marks}
    sizing_inputs = []
    for target in risk.approved_target.targets:
        instrument = target.source_target.instrument_id
        lattice = CnAShareCashQuantityLatticeModel(instrument.venue, _NOTIONAL).resolve_instrument(
            CnAShareQuantityLatticeQuery(inputs.scope.instrument_catalog.instrument(instrument)))
        if lattice.result is None:
            raise _EconomicNativeFailureV1(EngineFailureCode.POSITION_SIZING, lattice, operation='quantity_lattice', native_inputs={'query': CnAShareQuantityLatticeQuery(inputs.scope.instrument_catalog.instrument(instrument))}, original_claim={"source":sources,"event":event})
        key = PositionBalanceKey(inputs.scope.account_id, instrument.venue, instrument)
        sizing_inputs.append(InstrumentSizingInput(instrument, by_mark[instrument],
            ledger.position_quantity(key), lattice.result.quantity_lattice))
    sized = PositionSizer().materialize(approved_target=risk.approved_target,
        source_decision_batch_id=collected.batch.decision_batch_id,
        policy=PositionSizingPolicy.create(policy_key="cn.portfolio.live-signal-close.development",
            policy_version=1, price_purpose=PricePurpose.VALUATION, rounding=RoundingPolicy.TOWARD_ZERO,
            residual_policy=ResidualPositionPolicy.CLOSE_IF_PERMITTED), inputs=tuple(sizing_inputs))
    if sized.normalized_target is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.POSITION_SIZING, sized, operation='position_sizing', native_inputs={'approved_target': risk.approved_target, 'source_decision_batch_id': collected.batch.decision_batch_id, 'policy': PositionSizingPolicy.create(policy_key='cn.portfolio.live-signal-close.development', policy_version=1, price_purpose=PricePurpose.VALUATION, rounding=RoundingPolicy.TOWARD_ZERO, residual_policy=ResidualPositionPolicy.CLOSE_IF_PERMITTED), 'inputs': tuple(sizing_inputs)}, original_claim={"source":sources,"event":event})
    normalized = sized.normalized_target
    validity = TargetValidity(normalized.normalized_target_id, normalized.normalized_target_hash,
        valid_from, decision.target_snapshot.expires_at)
    return _NativeSignalTargetV1(snapshot, collected.batch, allocated.allocation,
        risk.approved_target, normalized, validity), projection



from .engine import EngineFailure, ExecutionTrace, ExecutionCaseSemanticSpec, ExecutionCaseIdentityManifest
from .financial_dispatch import FinancialDispatchArtifact


@dataclass(frozen=True, slots=True)
class _EconomicFailureContextV1:
    case_hash: str
    definition_hash: str
    target_stream_digest: str
    failed_event_id: str
    failed_at: SimulationInstant
    base_failure: EngineFailure
    prefix_checkpoint: _EconomicOpenSourcesV1
    journal: AccountingJournal
    order_streams: tuple[OrderEventStream, ...]
    reservation_schedules: tuple[OrderReservationSchedule, ...]
    financial_artifacts: tuple[FinancialDispatchArtifact, ...]
    trace: ExecutionTrace
    pending_intentions: tuple[d.Order, ...]
    admissions: tuple
    journal_entry_ids: tuple[tuple[str, d.DomainId], ...]
    used_identity_keys: tuple[str, ...]
    ca_transition_inputs: e.CnAShareCashDividendTransitionInputsV1 | None
    ca_failure: e.CnAShareCashDividendTransitionFailureV1 | None
    semantic_spec: ExecutionCaseSemanticSpec
    identity_manifest: ExecutionCaseIdentityManifest
    source_refs: tuple[tuple[str, d.ArtifactRef], ...]
    timeline_stream_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("case_hash", "definition_hash", "target_stream_digest"):
            value = getattr(self, name)
            if type(value) is not str or len(value) != 71 or not value.startswith("sha256:") or any(c not in "0123456789abcdef" for c in value[7:]):
                raise ValueError("economic context hash is not canonical: " + name)
        if type(self.failed_event_id) is not str or not self.failed_event_id or self.failed_event_id.strip() != self.failed_event_id:
            raise ValueError("economic failed event identity must be canonical")
        for name, expected in (("failed_at", SimulationInstant), ("base_failure", EngineFailure),
                ("prefix_checkpoint", _EconomicOpenSourcesV1), ("journal", AccountingJournal),
                ("trace", ExecutionTrace), ("semantic_spec", ExecutionCaseSemanticSpec),
                ("identity_manifest", ExecutionCaseIdentityManifest)):
            if type(getattr(self, name)) is not expected:
                raise TypeError("economic context requires exact " + name)
        for name, expected in (("order_streams", OrderEventStream), ("reservation_schedules", OrderReservationSchedule),
                ("financial_artifacts", FinancialDispatchArtifact), ("pending_intentions", d.Order),
                ("used_identity_keys", str), ("timeline_stream_keys", str)):
            values = getattr(self, name)
            if type(values) is not tuple or any(type(v) is not expected for v in values):
                raise TypeError("economic context requires exact tuple " + name)
        if type(self.admissions) is not tuple or type(self.source_refs) is not tuple or type(self.journal_entry_ids) is not tuple:
            raise TypeError("economic context requires immutable source/identity/admission tuples")
        prefix = self.prefix_checkpoint
        if (self.base_failure.economic_failure_context is not None or self.base_failure.case_hash != self.case_hash
                or self.base_failure.trace_hash != self.trace.trace_hash or prefix.at > self.failed_at
                or prefix.inputs._definition_source_hash != self.definition_hash
                or canonical_bytes(prefix.journal) != canonical_bytes(self.journal)
                or canonical_bytes(prefix.order_streams) != canonical_bytes(self.order_streams)
                or canonical_bytes(prefix.reservation_schedules) != canonical_bytes(self.reservation_schedules)
                or prefix.journal_entry_ids != self.journal_entry_ids):
            raise ValueError("economic failure context does not preserve its actual committed prefix")
        if any(a.occurred_at > self.failed_at or a.role == "economic_attempt_witness" for a in self.financial_artifacts):
            raise ValueError("economic failure cannot carry future artifacts or a completion witness")
        if self.used_identity_keys != tuple(sorted(set(self.used_identity_keys))) or not set(self.used_identity_keys) <= {r.binding_key for r in self.semantic_spec.identity_plan}:
            raise ValueError("economic failure used identity keys are not sealed coordinates")
        if (self.ca_transition_inputs is None) != (self.ca_failure is None):
            raise ValueError("economic failure must retain both C-A input and failure or neither")
        if self.ca_failure is not None:
            if (type(self.ca_transition_inputs) is not e.CnAShareCashDividendTransitionInputsV1
                    or type(self.ca_failure) is not e.CnAShareCashDividendTransitionFailureV1
                    or self.ca_failure.code is not e.CnAShareCashDividendTransitionFailureCodeV1.TAX_CASH_SHORTFALL
                    or self.base_failure.code is not EngineFailureCode.FINANCIAL_DISPATCH_FAILURE):
                raise ValueError("economic C-A failure must be the actual TAX cash shortfall")
            request = self.ca_transition_inputs
            h = request.history
            if (request.kind != "TAX" or h.as_of != self.failed_at
                    or canonical_bytes(h.journal) != canonical_bytes(self.journal)
                    or canonical_bytes(h.dividend_state) != canonical_bytes(prefix.dividend_state)
                    or h.journal_entry_ids != self.journal_entry_ids
                    or h.settlement_book != prefix.settlement_book
                    or h.order_streams != self.order_streams or h.reservation_schedules != self.reservation_schedules):
                raise ValueError("economic C-A failure inputs differ from committed prefix")
        canonical_bytes(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_failure_context", "schema_version": 1,
            "case_hash": self.case_hash, "definition_hash": self.definition_hash,
            "target_stream_digest": self.target_stream_digest, "failed_event_id": self.failed_event_id,
            "failed_at": self.failed_at, "base_failure": self.base_failure, "prefix_checkpoint": self.prefix_checkpoint,
            "journal": self.journal, "order_streams": self.order_streams,
            "reservation_schedules": self.reservation_schedules, "financial_artifacts": self.financial_artifacts,
            "trace": self.trace, "pending_intentions": self.pending_intentions, "admissions": self.admissions,
            "journal_entry_ids": self.journal_entry_ids, "used_identity_keys": self.used_identity_keys,
            "ca_transition_inputs": self.ca_transition_inputs, "ca_failure": self.ca_failure,
            "semantic_spec": self.semantic_spec, "identity_manifest": self.identity_manifest,
            "source_refs": self.source_refs, "timeline_stream_keys": self.timeline_stream_keys}
