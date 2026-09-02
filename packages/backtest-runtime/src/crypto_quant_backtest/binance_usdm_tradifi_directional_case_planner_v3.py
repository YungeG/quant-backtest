"""V3 directional execution planning over verified V2 economics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

import crypto_quant_domain as domain
import crypto_quant_trading as trading
from crypto_quant_market_data import MarketEvent

from . import binance_usdm_tradifi_case_planner as _v2
from .binance_usdm_tradifi_case_planner import (
    _FUNDING_STREAM,
    _INSTRUMENT,
    _LIQUIDATION_STREAM,
    _NAMESPACE,
    _NOTIONAL_LIMIT,
    _NOTIONAL_SCALE,
    _PROJECTION_STREAM_PREFIX,
    _STRATEGY_STREAM,
    _USDT,
    _base_spec,
    _events,
)
from .composition import (
    _compose_execution_case_v3,
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from .decision_schedule import DecisionSchedule, DecisionScheduleEntry
from .engine import (
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ResolvedDecisionCycle,
    ResolvedExecutionCase,
)
from .financial_dispatch import (
    FeeAccountingDispatchPlan,
    FillAccountingDispatchPlan,
    FinancialDispatchPlan,
)
from .multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
)
from .multi_resolution_preparation import MultiResolutionMarketDataPreparation
from .resolution import (
    BacktestRequest,
    ProfileResolver,
    ResolvedBacktestRequest,
    StrategyFamily,
)
from .run_end import MarkToMarketCloseoutPolicy
from .slippage import SlippageMarketState
from .target_stream import (
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
)
from .timeline import DeterministicTimeline, TimelineEvent, TimelineSegment

_PLACEHOLDER_RUN_ID = "run_" + "0" * 64


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiDirectionalCasePlanningResultV3:
    request: BacktestRequest
    resolved_request: ResolvedBacktestRequest
    market_data_preparation: MultiResolutionMarketDataPreparation
    hydrated_inputs: _HydratedExecutionCaseInputs
    execution_case: ResolvedExecutionCase


@dataclass(frozen=True, slots=True)
class _V3CandidateRow:
    event: MarketEvent
    candidate: Mapping[str, object]
    target: int
    mark: MarketEvent
    projection: MarketEvent | None


def _identity_plan_v3(
    values, rows: tuple[_V3CandidateRow, ...]
) -> tuple[ExecutionCaseIdentityRule, ...]:
    rules = [
        ExecutionCaseIdentityRule(
            "journal.initial.0",
            "binance-usdm-tradifi.directional-v3.initial-deposit",
            0,
            domain.DomainIdKind.JOURNAL,
        )
    ]
    event_types = (
        domain.OrderEventType.ORDER_INTENT_CREATED,
        domain.OrderEventType.ORDER_CAPABILITY_APPROVED,
        domain.OrderEventType.ORDER_TRANSLATED,
        domain.OrderEventType.MARKET_RULE_APPROVED,
        domain.OrderEventType.FEE_RESERVATION_ESTIMATED,
        domain.OrderEventType.PRE_TRADE_RISK_APPROVED,
        domain.OrderEventType.ORDER_SUBMITTED,
        domain.OrderEventType.ORDER_ACCEPTED,
    )
    previous_target = 0
    execution_index = 0
    for cycle_index, row in enumerate(rows):
        if row.target == previous_target:
            continue
        previous_target = row.target
        rules.extend(
            (
                ExecutionCaseIdentityRule(
                    f"order.{cycle_index}.0",
                    "binance-usdm-tradifi.directional-v3.order",
                    cycle_index,
                    domain.DomainIdKind.ORDER,
                ),
                ExecutionCaseIdentityRule(
                    f"fill.{execution_index}",
                    "binance-usdm-tradifi.directional-v3.fill",
                    execution_index,
                    domain.DomainIdKind.FILL,
                ),
                ExecutionCaseIdentityRule(
                    f"journal.fill.{execution_index}",
                    "binance-usdm-tradifi.directional-v3.fill-journal",
                    execution_index,
                    domain.DomainIdKind.JOURNAL,
                ),
                ExecutionCaseIdentityRule(
                    f"fee.{execution_index}",
                    "binance-usdm-tradifi.directional-v3.fee",
                    execution_index,
                    domain.DomainIdKind.FEE,
                ),
                ExecutionCaseIdentityRule(
                    f"journal.fee.{execution_index}",
                    "binance-usdm-tradifi.directional-v3.fee-journal",
                    execution_index,
                    domain.DomainIdKind.JOURNAL,
                ),
                ExecutionCaseIdentityRule(
                    f"order-event.fill.{execution_index}",
                    "binance-usdm-tradifi.directional-v3.order-event.fill",
                    execution_index,
                ),
                *(
                    ExecutionCaseIdentityRule(
                        f"order-event.{cycle_index}.0.{event_index}",
                        f"binance-usdm-tradifi.directional-v3.order-event.{event_type.value}",
                        cycle_index * 10 + event_index,
                    )
                    for event_index, event_type in enumerate(event_types)
                ),
            )
        )
        execution_index += 1
    versions = {value.model_version for value in values.resolved_profile.request.funding_sources}
    if versions <= {1}:
        ordinal = lambda index: index
    elif versions == {2}:
        ordinal = lambda index: 0
    else:
        raise ValueError("directional V3 funding model version")
    for index, event in enumerate(_events(values, _FUNDING_STREAM)):
        key = trading.LinearFundingApplicationKey.derive(
            values.intent.execution_account_id,
            trading.FundingSlotId.derive(_INSTRUMENT, event.event_time),
        ).value
        rules.extend(
            (
                ExecutionCaseIdentityRule(
                    f"settlement.funding.{index}",
                    key,
                    ordinal(index),
                    domain.DomainIdKind.SETTLEMENT,
                ),
                ExecutionCaseIdentityRule(
                    f"journal.funding.{index}",
                    key,
                    ordinal(index),
                    domain.DomainIdKind.JOURNAL,
                ),
            )
        )
    return tuple(rules)


def _preparation(values) -> MultiResolutionMarketDataPreparation:
    schedule = DecisionSchedule(
        "binance-usdm-tradifi.directional-v3.execution",
        3,
        values.intent.timeline_window,
        tuple(DecisionScheduleEntry(event.timeline_instant, TimelineSegment.ACTIVE_TRADING) for event in values.target_stream.events),
        (),
    )
    return MultiResolutionMarketDataPreparation(
        schedule,
        MultiResolutionMarketDataBindings(
            (),
            (
                ExecutionDataBinding(
                    values.resolved_profile.simulation.execution_model.component_ref.component_key,
                    _PROJECTION_STREAM_PREFIX + "2",
                ),
            ),
            (),
        ),
        (),
    )


def _candidate_rows(values) -> tuple[_V3CandidateRow, ...]:
    """Bind each sealed V3 decision to its retained economics inputs."""
    strategy_events = {event.event_id: event for event in _events(values, _STRATEGY_STREAM)}
    projection_events = {
        event.event_id: event
        for event in _events(values, _PROJECTION_STREAM_PREFIX + "2")
    }
    rows: list[_V3CandidateRow] = []
    prior_target = 0
    for event in values.target_stream.events:
        candidate = event.payload.get("candidate")
        if not isinstance(candidate, Mapping):
            raise TypeError("directional V3 candidate")
        targets = candidate.get("targets")
        if not isinstance(targets, tuple) or len(targets) != 1 or not isinstance(targets[0], Mapping):
            raise ValueError("directional V3 candidate target")
        target_wire = targets[0]
        if target_wire.get("instrument_id") != {
            "venue": "binance_usdm", "stable_key": "koru-usdt-tradifi-perpetual"
        }:
            raise ValueError("directional V3 candidate instrument")
        raw_target = target_wire.get("value")
        target_values = {
            "0": 0,
            values.target.target_exposure: 1,
            "-" + values.target.target_exposure: -1,
        }
        target = target_values.get(raw_target) if type(raw_target) is str else None
        if target is None:
            raise ValueError("directional V3 target exposure")
        evidence = candidate.get("evidence")
        source_rows = evidence.get("source_events") if isinstance(evidence, Mapping) else None
        if not isinstance(source_rows, tuple) or not all(isinstance(value, Mapping) for value in source_rows):
            raise ValueError("directional V3 source evidence")

        def bound_event(
            events: Mapping[str, MarketEvent], *, required: bool, source_rows=source_rows
        ) -> MarketEvent | None:
            matches = []
            for source in source_rows:
                retained = events.get(source.get("event_id"))
                if retained is not None and (
                    source.get("event_hash") == retained.event_hash
                    and source.get("revision_id") == retained.revision_id
                    and source.get("event_time") == retained.event_time.epoch_nanoseconds
                    and source.get("available_time") == retained.available_time.epoch_nanoseconds
                ):
                    matches.append(retained)
            if len(matches) != 1:
                if not matches and not required:
                    return None
                raise ValueError("directional V3 source evidence binding")
            return matches[0]

        mark = bound_event(strategy_events, required=True)
        projection = bound_event(projection_events, required=False)
        if mark is None:
            raise ValueError("directional V3 strategy mark")
        expires = candidate.get("expires_at")
        if (
            candidate.get("strategy_id") != values.target.strategy_id
            or candidate.get("sleeve_id") != values.target.sleeve_id
            or candidate.get("decision_time") != event.event_time.epoch_nanoseconds
            or candidate.get("effective_time") != event.event_time.epoch_nanoseconds
            or mark.instrument_id != _INSTRUMENT
            or mark.payload.get("price_purpose") != "strategy"
            or not mark.timeline_instant < event.timeline_instant
            or mark.available_time > event.event_time
            or (projection is not None and not event.timeline_instant < projection.timeline_instant)
            or (projection is not None and not event.event_time < projection.event_time)
            or (projection is None and (target != 0 or target != prior_target))
            or type(expires) is not int
            or expires <= event.event_time.epoch_nanoseconds
        ):
            raise ValueError("directional V3 mark or next-boundary projection")
        _v2._decision_mark(values, mark, event)
        if projection is not None:
            _v2._execution_mark(values, projection)
        rows.append(_V3CandidateRow(event, candidate, target, mark, projection))
        prior_target = target
    if prior_target != 0:
        raise ValueError("directional V3 target stream must finish flat")
    if tuple((row.event.timeline_instant, row.event.event_id) for row in rows) != tuple(
        sorted((row.event.timeline_instant, row.event.event_id) for row in rows)
    ):
        raise ValueError("directional V3 target decisions")
    return tuple(rows)


def _changed_rows(rows: tuple[_V3CandidateRow, ...]) -> tuple[_V3CandidateRow, ...]:
    previous = 0
    changed = []
    for row in rows:
        if row.target != previous:
            changed.append(row)
        previous = row.target
    return tuple(changed)


@dataclass(frozen=True, slots=True)
class _V3EconomicExecutionAdapter:
    """V3 target authority paired with the established V2 execution economics."""

    values: object
    rows: tuple[_V3CandidateRow, ...]
    identity_plan: tuple[ExecutionCaseIdentityRule, ...]

    def plan(self, semantic_run_id: str, journal_id: domain.DomainId) -> _ExecutionCasePlan:
        values = self.values
        changed = _changed_rows(self.rows)
        snapshot_at = self.rows[0].event.event_time if self.rows else values.intent.timeline_window.trading_start
        financial = _v2._initial_financial_state(values, journal_id, snapshot_at)
        snapshot = _v2._snapshot_plan(values)
        funding = _v2._funding_events(values, semantic_run_id)
        audit_rows = tuple(
            (row.event, row.candidate, row.target, row.mark, row.projection)
            for row in self.rows
            if row.projection is not None
        )
        audits = _v2._margin_audits(values, audit_rows, funding)
        scheduled_events = (*funding, *audits)
        identities = ExecutionCaseIdentityFactory(
            semantic_run_id=semantic_run_id, namespace=_NAMESPACE, identity_plan=self.identity_plan
        )
        ledger = trading.GenericLedger(financial.ledger_schema).project(financial.journal)
        reservations = trading.ResourceReservationBook(values.intent.execution_account_id).project((), ())
        contract = values.resolved_profile.linear_contract
        catalog = domain.InstrumentCatalog(
            currencies=(domain.CurrencyId("KORU"), _USDT),
            instruments=(contract.instrument,), symbol_timelines=(),
        )
        prior_state = None
        current_quantity = domain.Quantity(0, contract.quantity_scale, str(_INSTRUMENT))
        current_lots: tuple[domain.PositionLot, ...] = ()
        pending: tuple[
            int, MarketEvent, domain.Quantity, tuple[domain.PositionLot, ...]
        ] | None = None
        cycles: list[ResolvedDecisionCycle] = []
        bars: list[_v2.ResolvedBarExecution] = []
        event_types = (
            domain.OrderEventType.ORDER_INTENT_CREATED,
            domain.OrderEventType.ORDER_CAPABILITY_APPROVED,
            domain.OrderEventType.ORDER_TRANSLATED,
            domain.OrderEventType.MARKET_RULE_APPROVED,
            domain.OrderEventType.FEE_RESERVATION_ESTIMATED,
            domain.OrderEventType.PRE_TRADE_RISK_APPROVED,
            domain.OrderEventType.ORDER_SUBMITTED,
            domain.OrderEventType.ORDER_ACCEPTED,
        )
        execution_index = 0
        for cycle_index, row in enumerate(self.rows):
            if pending is not None and pending[1].event_time < row.event.event_time:
                _, _, current_quantity, current_lots = pending
                pending = None
            if pending is not None and row.target != pending[0]:
                raise ValueError("directional V3 pending-target-conflict")
            sleeve = domain.StrategySleeveId(values.target.sleeve_id)
            expectation = trading.DecisionBatchExpectation(values.target.strategy_id, sleeve)
            schedule = TargetStreamDecisionSchedule(
                row.event.event_time, TimelineSegment.ACTIVE_TRADING,
                (TargetStreamScheduleEntry(
                    row.event.event_id, expectation,
                    trading.StrategyOutputValidationContext(
                        values.target.strategy_id, sleeve, row.event.event_time,
                        catalog, (_INSTRUMENT,),
                    ),
                ),),
            )
            injected = PrecomputedTargetStreamAdapter().inject(
                stream=values.target_stream,
                timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, row.event),),
                schedule=schedule, prior_state=prior_state,
            )
            if injected.injection is None:
                raise ValueError("directional V3 target did not pass standard validation")
            prior_state = injected.injection.state
            changed_this = (
                execution_index < len(changed) and row is changed[execution_index]
            )
            planning_snapshot = _v2._planning_snapshot(values, row.event, current_quantity, current_lots)
            allocation_ref = trading.CapitalAllocationPolicyRef(
                "binance-usdm-tradifi.full-sleeve.v1", 1,
                domain.canonical_sha256({"equity": _v2._INITIAL_EQUITY, "fraction": "1"}),
            )
            allocations = (trading.StrategyAllocation(
                values.target.strategy_id, sleeve, row.event.event_time, _USDT,
                _v2._INITIAL_EQUITY, allocation_ref, domain.canonical_sha256(planning_snapshot),
            ),)
            risk = trading.PortfolioRiskPolicy.create(
                policy_key="binance-usdm-tradifi.target-risk.v1", policy_version=1,
                valuation_currency=_USDT, notional_scale=_NOTIONAL_SCALE,
                limits=(
                    trading.PortfolioRiskLimit("tradifi-target", trading.PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL, _NOTIONAL_LIMIT, trading.PortfolioRiskAction.REJECT, _INSTRUMENT),
                    trading.PortfolioRiskLimit("tradifi-gross", trading.PortfolioRiskScope.GROSS_EXPOSURE, _NOTIONAL_LIMIT, trading.PortfolioRiskAction.REJECT, None),
                    trading.PortfolioRiskLimit("tradifi-net", trading.PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE, _NOTIONAL_LIMIT, trading.PortfolioRiskAction.REJECT, None),
                ),
            )
            sizing = trading.PositionSizingPolicy.create(
                policy_key="binance-usdm-tradifi.fixed-notional-sizing.v1", policy_version=1,
                price_purpose=domain.PricePurpose.EXECUTION_REFERENCE,
                rounding=domain.RoundingPolicy.TOWARD_ZERO,
                residual_policy=trading.ResidualPositionPolicy.FAIL,
            )
            rules = values.profile_composition_request.order_rules
            if rules is None:
                raise ValueError("directional V3 economics lacks order lattice")
            sizing_input = trading.InstrumentSizingInput(
                _INSTRUMENT, _v2._decision_mark(values, row.mark, row.event),
                current_quantity, rules.market_quantity_lattice,
            )
            allocated = trading.PortfolioAllocator().allocate(
                sleeve_state=prior_state, portfolio_snapshot=planning_snapshot,
                allocations=allocations, target_notional_scale=_NOTIONAL_SCALE,
            )
            if allocated.allocation is None:
                raise ValueError("directional V3 full-sleeve allocation failed")
            if values.target.target_exposure == ".25" and row.target:
                target_notional = allocated.allocation.sleeve_targets[0].target_notional
                if abs(target_notional.units) != 250_000_000 or target_notional.scale != _NOTIONAL_SCALE:
                    raise ValueError("directional V3 .25 target notional must be 2500.00000")
            approved = trading.PortfolioRiskEvaluator().evaluate(
                allocation=allocated.allocation, policy=risk
            )
            if approved.approved_target is None:
                raise ValueError("directional V3 target risk evaluation failed")
            sized = trading.PositionSizer().materialize(
                approved_target=approved.approved_target,
                source_decision_batch_id=injected.injection.batch.decision_batch_id,
                policy=sizing, inputs=(sizing_input,),
            )
            if sized.normalized_target is None:
                raise ValueError("directional V3 target sizing failed")
            expires = row.candidate["expires_at"]
            validity = trading.TargetValidity(
                sized.normalized_target.normalized_target_id,
                sized.normalized_target.normalized_target_hash,
                row.event.event_time, domain.UtcInstant(expires),
            )
            rebalance = trading.RebalancePolicy.create(
                policy_key="binance-usdm-tradifi.market-ioc.v1", policy_version=1,
                execution_style=domain.ExecutionStyle.MARKET, time_in_force=domain.TimeInForce.IOC,
                urgency="normal", plan_valid_for_nanoseconds=expires - row.event.event_time.epoch_nanoseconds,
            )
            if not changed_this:
                cycles.append(ResolvedDecisionCycle(
                    schedule, allocations, _NOTIONAL_SCALE, risk, sizing,
                    (sizing_input,), validity, rebalance, row.event.event_time,
                    (), planning_snapshot,
                ))
                continue
            availability = trading.AvailabilityProjection().project(
                ledger, trading.SettlementBook(values.intent.execution_account_id).project(),
                reservations, financial.settlement_rules,
            )
            coordinated = trading.RebalanceCoordinator().coordinate(
                target=sized.normalized_target, target_validity=validity,
                portfolio_snapshot=planning_snapshot, working_orders=(), reservations=reservations,
                availability=replace(availability, ledger_state_hash=planning_snapshot.journal_state_hash),
                policy=rebalance, as_of=row.event.event_time,
            )
            if coordinated.decision is None or len(coordinated.decision.plan.planned_orders) != 1:
                raise ValueError("each directional V3 target change must produce one order")
            intent = coordinated.decision.plan.planned_orders[0].intent
            order = domain.Order(
                identities.domain_id(f"order.{cycle_index}.0"), values.intent.execution_account_id,
                intent, domain.SimulationInstant(row.event.event_time, domain.TimelinePhase(80, "order_admission"), domain.SourceSequence(0)),
            )
            admission_events = tuple(
                _v2.OrderEventPlan(
                    event_type, identities.event_id(f"order-event.{cycle_index}.0.{event_index}"),
                    domain.SimulationInstant(row.event.event_time, domain.TimelinePhase(80, "order_admission"), domain.SourceSequence(event_index)),
                    f"{row.event.event_id}:{event_type.value}" if event_type in {domain.OrderEventType.ORDER_SUBMITTED, domain.OrderEventType.ORDER_ACCEPTED} else None,
                )
                for event_index, event_type in enumerate(event_types)
            )
            admission = _v2.ResolvedOrderAdmission(
                order, _v2._capabilities(values), _v2._translation_mapping(), row.event.event_time,
                _v2._pretrade(values, order, sizing_input.mark.price, row.event.event_time), admission_events,
            )
            cycles.append(ResolvedDecisionCycle(
                schedule, allocations, _NOTIONAL_SCALE, risk, sizing, (sizing_input,), validity,
                rebalance, row.event.event_time, (admission,), planning_snapshot,
            ))
            if row.projection is None:
                raise ValueError("directional V3 target change lacks next-boundary projection")
            execution_mark = _v2._execution_mark(values, row.projection)
            market_state = SlippageMarketState(
                "normal", row.projection.event_time, row.projection.available_time,
                row.projection.event_id, row.projection.revision_id, row.projection.event_hash,
            )
            cash_key, position_key = _v2._keys(values)
            account = values.profile_composition_request.account_profile
            if account is None:
                raise ValueError("directional V3 economics lacks fee authority")
            fill_recorded = domain.SimulationInstant(row.projection.event_time, domain.TimelinePhase(90, "accounting"), domain.SourceSequence(1))
            fee_recorded = domain.SimulationInstant(row.projection.event_time, domain.TimelinePhase(90, "accounting"), domain.SourceSequence(3))
            accounting = FillAccountingDispatchPlan(
                row.projection.event_id, identities.domain_id(f"fill.{execution_index}"),
                values.financial_dispatcher_spec.position_accounting_component,
                _v2.LinearDerivativeFillAccountingPlan(
                    position_key, contract, trading.LedgerBalanceRegistration(cash_key, _v2._MONEY_SCALE),
                    domain.QuantizationPolicy("binance-usdm-tradifi.realized-half-even.v1", _v2._MONEY_SCALE, domain.RoundingPolicy.HALF_EVEN),
                ),
                _v2._LinearFillSemantics(position_key, contract),
                identities.domain_id(f"journal.fill.{execution_index}"), fill_recorded,
                FeeAccountingDispatchPlan(
                    cash_key, account.final_fee_rule_set, identities.domain_id(f"fee.{execution_index}"),
                    row.projection.event_time, identities.domain_id(f"journal.fee.{execution_index}"), fee_recorded,
                ),
                (f"position_accounting.{execution_index + 1}",),
            )
            bars.append(_v2.ResolvedBarExecution(
                row.projection.event_id, order.order_id,
                _v2._pretrade(values, order, execution_mark.price, row.projection.available_time),
                _v2.BarLiquidityEvidence.create(
                    evidence_key=f"binance-usdm-tradifi.first-retained-trade.{execution_index + 1}",
                    evidence_version=1, market_event=row.projection,
                    evaluated_at=row.projection.available_time, approved=True,
                    reason_code=None, source_hash=row.projection.event_hash,
                ),
                market_state, values.resolved_profile.simulation.slippage_model,
                identities.domain_id(f"fill.{execution_index}"), identities.event_id(f"order-event.fill.{execution_index}"),
                domain.SimulationInstant(row.projection.event_time, domain.TimelinePhase(70, "fill"), domain.SourceSequence(1)),
                accounting, "taker",
            ))
            next_quantity = sized.normalized_target.targets[0].decision.final_quantity
            pending = (
                row.target,
                row.projection,
                next_quantity,
                _v2._planning_lots(
                    values, sized.normalized_target, sizing_input.mark, row.event.event_time
                ),
            )
            execution_index += 1

        roles = _v2._expected_artifact_roles(
            (
                "final_snapshot", "margin_projection.final",
                *(f"position_accounting.{index + 1}" for index in range(len(bars))),
                *(role for event in scheduled_events for role in event.expected_artifact_roles),
            )
        )
        return _ExecutionCasePlan(
            tuple(cycles), tuple(bars), financial,
            FinancialDispatchPlan(values.financial_dispatcher_spec, scheduled_events, snapshot, roles),
            values.resolved_profile.simulation.execution_model, snapshot,
            MarkToMarketCloseoutPolicy(),
        )


def _plan(
    values,
    semantic_run_id: str,
    journal_id: domain.DomainId,
    rows: tuple[_V3CandidateRow, ...],
    identity_plan: tuple[ExecutionCaseIdentityRule, ...],
) -> _ExecutionCasePlan:
    return _V3EconomicExecutionAdapter(values, rows, identity_plan).plan(
        semantic_run_id, journal_id
    )


def plan_binance_usdm_tradifi_directional_case_v3(values) -> BinanceUsdmTradifiDirectionalCasePlanningResultV3:
    """Plan V3 target changes with sealed V2 execution economics."""
    rows = _candidate_rows(values)
    identity_plan = _identity_plan_v3(values, rows)
    timeline_keys = tuple(sorted((values.target_stream_key, _PROJECTION_STREAM_PREFIX + "2", _FUNDING_STREAM, _LIQUIDATION_STREAM)))
    timeline = DeterministicTimeline.open(
        reader=values.market_reader,
        stream_keys=timeline_keys,
        window=values.intent.timeline_window,
    )
    if type(timeline) is not DeterministicTimeline:
        raise ValueError("directional V3 overlay did not open a timeline")
    preparation = _preparation(values)
    placeholder = ExecutionCaseIdentityFactory(
        semantic_run_id=_PLACEHOLDER_RUN_ID,
        namespace=_NAMESPACE,
        identity_plan=identity_plan,
    )
    placeholder_plan = _plan(
        values, _PLACEHOLDER_RUN_ID, placeholder.domain_id("journal.initial.0"),
        rows, identity_plan,
    )
    base = _base_spec(values, timeline, identity_plan)
    base = type(base)(
        base.schema_version,
        "binance-usdm-tradifi.directional-v3.execution-case",
        3,
        "binance-usdm-tradifi.directional-v3.execution",
        3,
        base.identity_namespace,
        base.identity_plan,
        base.timeline_semantic_hash,
        base.target_stream_digest,
        values.authority_digest,
        values.authority_digest,
        values.authority_digest,
        values.authority_digest,
        values.authority_digest,
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=base,
        execution_case_plan=placeholder_plan,
        market_data_preparation=preparation,
    )
    profile = values.resolved_profile
    request = BacktestRequest(
        1,
        values.intent.experiment_id,
        values.intent.timeline_window,
        profile.market_registration.profile_key,
        profile.simulation_registration.profile_key,
        profile.execution_account_registration.profile_key,
        values.intent.execution_account_id,
        domain.CurrencyId("USDT"),
        values.market_bundle_ref,
        values.target_stream.target_stream_digest,
        spec.semantic_spec_hash,
        values.intent.master_random_seed,
        values.build_artifact_manifest.manifest_hash,
        StrategyFamily.PRECOMPUTED_TARGET,
        profile.simulation_registration.engine_kind,
        values.intent.result_grade_requested,
    )
    outcome = ProfileResolver().resolve(
        request=request,
        registry=values.profile_registry,
        market_bundle_manifest=values.market_bundle_manifest,
        build_artifact_manifest=values.build_artifact_manifest,
    )
    if outcome.resolved is None:
        raise ValueError("directional V3 request did not resolve")
    resolved = outcome.resolved
    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=resolved.semantic_run_id,
        namespace=_NAMESPACE,
        identity_plan=identity_plan,
    )
    actual_plan = _plan(
        values, resolved.semantic_run_id, identities.domain_id("journal.initial.0"),
        rows, identity_plan,
    )
    if _execution_case_semantic_spec_v3(base_spec=spec, execution_case_plan=actual_plan, market_data_preparation=preparation) != spec:
        raise ValueError("directional V3 identities changed semantics")
    hydrated = _HydratedExecutionCaseInputs(spec, timeline_keys, values.target_stream, 64, actual_plan)
    case = _compose_execution_case_v3(
        resolved_request=resolved,
        market_reader=values.market_reader,
        hydrated_inputs=hydrated,
        market_data_preparation=preparation,
    )
    return BinanceUsdmTradifiDirectionalCasePlanningResultV3(request, resolved, preparation, hydrated, case)


__all__ = ["BinanceUsdmTradifiDirectionalCasePlanningResultV3", "plan_binance_usdm_tradifi_directional_case_v3"]
