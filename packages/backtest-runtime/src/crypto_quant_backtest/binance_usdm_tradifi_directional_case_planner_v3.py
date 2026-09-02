"""V3 directional no-fill case planning over verified V2 economics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import crypto_quant_domain as domain
import crypto_quant_trading as trading

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
    _decision_mark,
    _events,
    _expected_artifact_roles,
    _funding_events,
    _initial_financial_state,
    _planning_snapshot,
    _snapshot_plan,
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
from .financial_dispatch import FinancialDispatchPlan
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


def _identity_plan_v3(values) -> tuple[ExecutionCaseIdentityRule, ...]:
    rules = [ExecutionCaseIdentityRule("journal.initial.0", "binance-usdm-tradifi.directional-v3.initial-deposit", 0, domain.DomainIdKind.JOURNAL)]
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
        rules.extend((
            ExecutionCaseIdentityRule(f"settlement.funding.{index}", key, ordinal(index), domain.DomainIdKind.SETTLEMENT),
            ExecutionCaseIdentityRule(f"journal.funding.{index}", key, ordinal(index), domain.DomainIdKind.JOURNAL),
        ))
    return tuple(rules)


def _preparation(values) -> MultiResolutionMarketDataPreparation:
    schedule = DecisionSchedule(
        "binance-usdm-tradifi.directional-v3.no-fill",
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


def _cycles(values) -> tuple[ResolvedDecisionCycle, ...]:
    """Consume exact V3 candidates but deliberately plan no orders, fills, or PNL."""
    contract = values.resolved_profile.linear_contract
    catalog = domain.InstrumentCatalog(
        currencies=(domain.CurrencyId("KORU"), _USDT),
        instruments=(contract.instrument,),
        symbol_timelines=(),
    )
    prior_state = None
    zero_quantity = domain.Quantity(0, contract.quantity_scale, str(contract.instrument.instrument_id))
    cycles = []
    for event in values.target_stream.events:
        sleeve = domain.StrategySleeveId(values.target.sleeve_id)
        expectation = trading.DecisionBatchExpectation(values.target.strategy_id, sleeve)
        schedule = TargetStreamDecisionSchedule(
            event.event_time,
            TimelineSegment.ACTIVE_TRADING,
            (TargetStreamScheduleEntry(
                event.event_id,
                expectation,
                trading.StrategyOutputValidationContext(
                    values.target.strategy_id,
                    sleeve,
                    event.event_time,
                    catalog,
                    (contract.instrument.instrument_id,),
                ),
            ),),
        )
        injected = PrecomputedTargetStreamAdapter().inject(
            stream=values.target_stream,
            timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, event),),
            schedule=schedule,
            prior_state=prior_state,
        )
        if injected.injection is None:
            raise ValueError("directional V3 target did not pass standard validation: " + str(injected))
        prior_state = injected.injection.state
        snapshot = _planning_snapshot(values, event, zero_quantity, ())
        allocation_ref = trading.CapitalAllocationPolicyRef(
            "binance-usdm-tradifi.directional-v3.full-sleeve",
            3,
            domain.canonical_sha256({"authority": values.authority_digest}),
        )
        allocations = (trading.StrategyAllocation(
            values.target.strategy_id,
            sleeve,
            event.event_time,
            _USDT,
            domain.Money(0, snapshot.equity.scale, "USDT"),
            allocation_ref,
            domain.canonical_sha256(snapshot),
        ),)
        risk = trading.PortfolioRiskPolicy.create(
            policy_key="binance-usdm-tradifi.directional-v3.target-risk",
            policy_version=3,
            valuation_currency=_USDT,
            notional_scale=_NOTIONAL_SCALE,
            limits=(
                trading.PortfolioRiskLimit("directional-v3-target", trading.PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL, _NOTIONAL_LIMIT, trading.PortfolioRiskAction.REJECT, contract.instrument.instrument_id),
                trading.PortfolioRiskLimit("directional-v3-gross", trading.PortfolioRiskScope.GROSS_EXPOSURE, _NOTIONAL_LIMIT, trading.PortfolioRiskAction.REJECT, None),
                trading.PortfolioRiskLimit("directional-v3-net", trading.PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE, _NOTIONAL_LIMIT, trading.PortfolioRiskAction.REJECT, None),
            ),
        )
        sizing = trading.PositionSizingPolicy.create(
            policy_key="binance-usdm-tradifi.directional-v3.fixed-exposure",
            policy_version=3,
            price_purpose=domain.PricePurpose.EXECUTION_REFERENCE,
            rounding=domain.RoundingPolicy.TOWARD_ZERO,
            residual_policy=trading.ResidualPositionPolicy.FAIL,
        )
        evidence = event.payload["candidate"].get("evidence")
        source_rows = evidence.get("source_events") if isinstance(evidence, Mapping) else None
        source_ids = {row.get("event_id") for row in source_rows} if isinstance(source_rows, tuple) and all(isinstance(row, Mapping) for row in source_rows) else set()
        mark_event = next((value for value in _events(values, _STRATEGY_STREAM) if value.event_id in source_ids), None)
        if mark_event is None:
            raise ValueError("directional V3 target has no retained strategy mark")
        mark = _decision_mark(values, mark_event, event)
        rules = values.profile_composition_request.order_rules
        if rules is None:
            raise ValueError("directional V3 economics lacks order lattice")
        inputs = (trading.InstrumentSizingInput(contract.instrument.instrument_id, mark, zero_quantity, rules.market_quantity_lattice),)
        allocated = trading.PortfolioAllocator().allocate(
            sleeve_state=prior_state,
            portfolio_snapshot=snapshot,
            allocations=allocations,
            target_notional_scale=_NOTIONAL_SCALE,
        )
        approved = trading.PortfolioRiskEvaluator().evaluate(allocation=allocated.allocation, policy=risk) if allocated.allocation is not None else None
        sized = trading.PositionSizer().materialize(
            approved_target=approved.approved_target,
            source_decision_batch_id=injected.injection.batch.decision_batch_id,
            policy=sizing,
            inputs=inputs,
        ) if approved is not None and approved.approved_target is not None else None
        if sized is None or sized.normalized_target is None:
            raise ValueError("directional V3 fixed exposure cannot normalize: " + str((allocated, approved, sized)))
        expires = event.payload["candidate"]["expires_at"]
        if type(expires) is not int:
            raise ValueError("directional V3 target expiry")
        validity = trading.TargetValidity(sized.normalized_target.normalized_target_id, sized.normalized_target.normalized_target_hash, event.event_time, domain.UtcInstant(expires))
        rebalance = trading.RebalancePolicy.create(
            policy_key="binance-usdm-tradifi.directional-v3.no-fill",
            policy_version=3,
            execution_style=domain.ExecutionStyle.MARKET,
            time_in_force=domain.TimeInForce.IOC,
            urgency="normal",
            plan_valid_for_nanoseconds=expires - event.event_time.epoch_nanoseconds,
        )
        cycles.append(ResolvedDecisionCycle(schedule, allocations, _NOTIONAL_SCALE, risk, sizing, inputs, validity, rebalance, event.event_time, (), snapshot))
    return tuple(cycles)


def _plan(values, semantic_run_id: str, journal_id: domain.DomainId) -> _ExecutionCasePlan:
    financial = _initial_financial_state(
        values, journal_id, values.intent.timeline_window.trading_start
    )
    snapshot = _snapshot_plan(values)
    funding = _funding_events(values, semantic_run_id)
    roles = _expected_artifact_roles(
        (
            "final_snapshot",
            "margin_projection.final",
            *(role for event in funding for role in event.expected_artifact_roles),
        )
    )
    return _ExecutionCasePlan(
        _cycles(values),
        (),
        financial,
        FinancialDispatchPlan(values.financial_dispatcher_spec, funding, snapshot, roles),
        values.resolved_profile.simulation.execution_model,
        snapshot,
        MarkToMarketCloseoutPolicy(),
    )


def plan_binance_usdm_tradifi_directional_case_v3(values) -> BinanceUsdmTradifiDirectionalCasePlanningResultV3:
    """Plan no fills/PNL; the V3 stream remains a durable target consumption input."""
    identity_plan = _identity_plan_v3(values)
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
    placeholder_plan = _plan(values, _PLACEHOLDER_RUN_ID, placeholder.domain_id("journal.initial.0"))
    base = _base_spec(values, timeline, identity_plan)
    base = type(base)(
        base.schema_version,
        "binance-usdm-tradifi.directional-v3.execution-case",
        3,
        "binance-usdm-tradifi.directional-v3.no-fill",
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
    actual_plan = _plan(values, resolved.semantic_run_id, identities.domain_id("journal.initial.0"))
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
