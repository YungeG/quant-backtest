"""Two-phase Semantic Run and resolved ExecutionCase composition."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from crypto_quant_domain import (
    AccountingJournalEntry,
    IdentityNamespace,
    OrderIntent,
    PortfolioSnapshot,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InputValidationFailure, MarketBundleReader
from crypto_quant_trading import StrategyAllocation

from .engine import (
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    ResolvedBarExecution,
    ResolvedDecisionCycle,
    ResolvedExecutionCase,
    ResolvedFinancialState,
    ResolvedOrderAdmission,
    SnapshotProjectionPlan,
)
from .execution import NextEligibleBarOpenModel
from .financial_dispatch import (
    FillAccountingDispatchPlan,
    FinancialDispatchPlan,
    LinearFundingAccountEventPlan,
    LinearMarginLiquidationAuditPlan,
    ScheduledAccountEvent,
    default_cash_financial_dispatcher_spec,
)
from .multi_resolution_preparation import MultiResolutionMarketDataPreparation
from .ports import SimulationPortType
from .resolution import BacktestRequest, ResolvedBacktestRequest
from .run_end import MarkToMarketCloseoutPolicy
from .slippage import DeterministicBpsSlippageModel
from .target_stream import PrecomputedTargetStream
from .timeline import DeterministicTimeline


class _ExecutionCaseBuilder(Protocol):
    def semantic_spec(self) -> ExecutionCaseSemanticSpec: ...

    def build(
        self,
        identities: ExecutionCaseIdentityFactory,
        semantic_spec_hash: str,
    ) -> ResolvedExecutionCase: ...


@dataclass(frozen=True, slots=True)
class _ExecutionCasePlan:
    decision_cycles: tuple[ResolvedDecisionCycle, ...]
    bar_executions: tuple[ResolvedBarExecution, ...]
    financial_state: ResolvedFinancialState
    financial_dispatch_plan: FinancialDispatchPlan
    execution_model: NextEligibleBarOpenModel
    snapshot_plan: SnapshotProjectionPlan
    closeout_policy: MarkToMarketCloseoutPolicy

    def __post_init__(self) -> None:
        if type(self.decision_cycles) is not tuple or not all(
            type(value) is ResolvedDecisionCycle for value in self.decision_cycles
        ):
            raise TypeError("decision_cycles must contain exact ResolvedDecisionCycle")
        if type(self.bar_executions) is not tuple or not all(
            type(value) is ResolvedBarExecution for value in self.bar_executions
        ):
            raise TypeError("bar_executions must contain exact ResolvedBarExecution")
        if type(self.financial_state) is not ResolvedFinancialState:
            raise TypeError("financial_state must be exact ResolvedFinancialState")
        if type(self.financial_dispatch_plan) is not FinancialDispatchPlan:
            raise TypeError(
                "financial_dispatch_plan must be exact FinancialDispatchPlan"
            )
        if type(self.execution_model) is not NextEligibleBarOpenModel:
            raise TypeError("execution_model must be exact NextEligibleBarOpenModel")
        if type(self.snapshot_plan) is not SnapshotProjectionPlan:
            raise TypeError("snapshot_plan must be exact SnapshotProjectionPlan")
        if type(self.closeout_policy) is not MarkToMarketCloseoutPolicy:
            raise TypeError("closeout_policy must be exact MarkToMarketCloseoutPolicy")


@dataclass(frozen=True, slots=True)
class _HydratedExecutionCaseInputs:
    execution_case_semantic_spec: ExecutionCaseSemanticSpec
    timeline_stream_keys: tuple[str, ...]
    target_stream: PrecomputedTargetStream
    timeline_batch_size: int
    execution_case_plan: _ExecutionCasePlan

    def __post_init__(self) -> None:
        if type(self.execution_case_semantic_spec) is not ExecutionCaseSemanticSpec:
            raise TypeError(
                "execution_case_semantic_spec must be exact ExecutionCaseSemanticSpec"
            )
        if type(self.timeline_stream_keys) is not tuple or not all(
            type(value) is str and value for value in self.timeline_stream_keys
        ):
            raise TypeError("timeline_stream_keys must contain nonempty str")
        if tuple(sorted(set(self.timeline_stream_keys))) != self.timeline_stream_keys:
            raise ValueError("timeline_stream_keys must be sorted and unique")
        if type(self.target_stream) is not PrecomputedTargetStream:
            raise TypeError("target_stream must be exact PrecomputedTargetStream")
        if type(self.timeline_batch_size) is not int or self.timeline_batch_size < 1:
            raise ValueError("timeline_batch_size must be a positive integer")
        if type(self.execution_case_plan) is not _ExecutionCasePlan:
            raise TypeError("execution_case_plan must be exact _ExecutionCasePlan")


def _allocation_semantics(
    allocation: StrategyAllocation,
) -> dict[str, object]:
    return {
        "strategy_id": allocation.strategy_id,
        "sleeve_id": allocation.sleeve_id,
        "valuation_time": allocation.valuation_time,
        "valuation_currency": allocation.valuation_currency,
        "allocation_nav": allocation.allocation_nav,
        "policy_ref": allocation.policy_ref,
    }


def _order_intent_semantics(intent: OrderIntent) -> dict[str, object]:
    return {
        "instrument_id": intent.instrument_id,
        "side": intent.side.value,
        "quantity": intent.quantity,
        "execution_style": intent.execution_style.value,
        "price_constraint": intent.price_constraint,
        "time_in_force": intent.time_in_force.value,
        "reduce_only": intent.reduce_only,
        "position_effect": intent.position_effect.value,
        "urgency": intent.urgency,
        "reason": intent.reason,
        "parent_role": "normalized_portfolio_target",
    }


def _admission_semantics(
    admission: ResolvedOrderAdmission,
) -> dict[str, object]:
    return {
        "account_id": admission.order.account_id,
        "intent": _order_intent_semantics(admission.order.intent),
        "created_at": admission.order.created_at,
        "capability_set": admission.capability_set,
        "translation_mapping": admission.translation_mapping,
        "translation_time": admission.translation_time,
        "pretrade_plan": admission.pretrade_plan,
        "event_plan": tuple(
            {
                "event_type": event.event_type.value,
                "occurred_at": event.occurred_at,
                "external_evidence_id": event.external_evidence_id,
            }
            for event in admission.event_plan
        ),
    }


def _decision_semantics(case: ResolvedExecutionCase) -> tuple[dict[str, object], ...]:
    output = []
    for cycle in case.decision_cycles:
        payload: dict[str, object] = {
            "schedule": cycle.schedule,
            "allocations": tuple(
                _allocation_semantics(value) for value in cycle.allocations
            ),
            "target_notional_scale": cycle.target_notional_scale.places,
            "risk_policy": cycle.risk_policy,
            "sizing_policy": cycle.sizing_policy,
            "sizing_inputs": cycle.sizing_inputs,
            "target_validity": {
                "valid_from": cycle.target_validity.valid_from,
                "valid_until": cycle.target_validity.valid_until,
            },
            "rebalance_policy": cycle.rebalance_policy,
            "planning_at": cycle.planning_at,
        }
        if cycle.planning_snapshot is not None:
            payload["planning_snapshot"] = cycle.planning_snapshot
        output.append(payload)
    return tuple(output)


def _accounting_plan_semantics(
    plan: FillAccountingDispatchPlan,
) -> dict[str, object]:
    fee = plan.fee_plan
    return {
        "source_event_id": plan.source_event_id,
        "position_accounting_component": plan.position_accounting_component,
        "semantic_payload": plan.semantic_payload,
        "fill_recorded_at": plan.fill_recorded_at,
        "fee_cash_key": fee.cash_key,
        "final_fee_rule_set": fee.final_fee_rule_set,
        "fee_assessment_time": fee.fee_assessment_time,
        "fee_recorded_at": fee.fee_recorded_at,
        "expected_artifact_roles": plan.expected_artifact_roles,
    }


def _slippage_model_semantics(
    model: DeterministicBpsSlippageModel,
) -> dict[str, object]:
    return {
        "component_ref": model.component_ref,
        "calibration_ref": model.calibration_ref,
        "applicability_envelope": model.applicability_envelope,
        "basis_points_units": model.basis_points_units,
        "basis_points_scale": model.basis_points_scale.places,
        "rounding": model.rounding.value,
        "limitations": tuple(value.value for value in model.limitations),
    }


def _bar_execution_semantics(
    execution: ResolvedBarExecution,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_event_id": execution.event_id,
        "pretrade_plan": execution.pretrade_plan,
        "liquidity_evidence": execution.liquidity_evidence,
        "market_state": execution.market_state,
        "slippage_model": _slippage_model_semantics(execution.slippage_model),
        "fill_event_at": execution.fill_event_at,
        "accounting_plan": _accounting_plan_semantics(execution.accounting_plan),
    }
    if execution.fill_liquidity_role is not None:
        payload["fill_liquidity_role"] = execution.fill_liquidity_role
    return payload


def _execution_semantics(case: ResolvedExecutionCase) -> dict[str, object]:
    return {
        "admissions": tuple(
            _admission_semantics(admission)
            for cycle in case.decision_cycles
            for admission in cycle.admissions
        ),
        "bar_executions": tuple(
            _bar_execution_semantics(execution) for execution in case.bar_executions
        ),
        "execution_model_spec": case.execution_model.spec(),
    }


def _journal_entry_semantics(
    entry: AccountingJournalEntry,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "entry_type": entry.entry_type.value,
        "account_id": entry.account_id,
        "venue_id": entry.venue_id,
        "effective_time": entry.effective_time,
        "recorded_at": entry.recorded_at,
        "source_ids": entry.source_ids,
        "balance_changes": entry.balance_changes,
        "realized_pnl": entry.realized_pnl,
        "fees": entry.fees,
        "financing": entry.financing,
    }
    if entry.position_lot_changes:
        payload["position_lot_changes"] = entry.position_lot_changes
    return payload


def _snapshot_semantics(snapshot: PortfolioSnapshot) -> dict[str, object]:
    return {
        "account_id": snapshot.account_id,
        "timestamp": snapshot.timestamp,
        "reporting_currency": snapshot.reporting_currency,
        "cash": snapshot.cash,
        "positions": snapshot.positions,
        "realized_pnl": snapshot.realized_pnl,
        "unrealized_pnl": snapshot.unrealized_pnl,
        "fees": snapshot.fees,
        "financing": snapshot.financing,
        "equity": snapshot.equity,
        "valuation_marks": snapshot.valuation_marks,
        "valuation_mark_set_hash": snapshot.valuation_mark_set_hash,
        "valuation_staleness_report_hash": snapshot.valuation_staleness_report_hash,
        "currency_valuation_graph_hash": snapshot.currency_valuation_graph_hash,
    }


def _scheduled_event_semantics(value: ScheduledAccountEvent) -> dict[str, object]:
    payload = value.payload
    authority = None
    if isinstance(
        payload, (LinearFundingAccountEventPlan, LinearMarginLiquidationAuditPlan)
    ):
        authority = payload.production_semantic_authority()
    if authority is not None and canonical_bytes(
        value.semantic_payload
    ) != canonical_bytes(authority):
        raise ValueError(
            "scheduled event semantic payload does not match production authority"
        )
    return {
        "event_id": value.event_id,
        "event_at": value.event_at,
        "operation_key": value.operation_key,
        "component_keys": value.component_keys,
        "semantic_payload": (
            authority if authority is not None else value.semantic_payload
        ),
        "expected_artifact_roles": value.expected_artifact_roles,
    }


def _financial_dispatch_semantics(
    plan: FinancialDispatchPlan,
) -> dict[str, object]:
    return {
        "dispatcher_spec": plan.dispatcher_spec,
        "scheduled_account_events": tuple(
            _scheduled_event_semantics(value) for value in plan.scheduled_account_events
        ),
        "final_snapshot_payload": plan.final_snapshot_payload,
        "expected_artifact_roles": plan.expected_artifact_roles,
    }


def _financial_semantics(case: ResolvedExecutionCase) -> dict[str, object]:
    financial = case.financial_state
    if financial.settlement_book.obligations or financial.settlement_book.events:
        raise ValueError(
            "ExecutionCaseSemanticSpec v1 requires pristine initial settlement state"
        )
    return {
        "journal_entries": tuple(
            _journal_entry_semantics(entry) for entry in financial.journal.entries
        ),
        "ledger_schema": financial.ledger_schema,
        "initial_snapshot": _snapshot_semantics(financial.initial_snapshot),
        "lot_books": financial.lot_books,
        "initial_order_admissions": tuple(
            _admission_semantics(value)
            for value in sorted(
                financial.order_admissions,
                key=lambda admission: (
                    admission.order.created_at,
                    admission.order.intent.parent_id,
                ),
            )
        ),
        "initial_reservation_schedules": tuple(
            {
                "source_proposal_hash": value.source_proposal_hash,
                "updates": tuple(
                    {
                        "event_type": update.event_type.value,
                        "remaining_quantity": update.remaining_quantity,
                        "commitment": update.commitment,
                        "source_evidence_hash": update.source_evidence_hash,
                    }
                    for update in value.updates
                ),
            }
            for value in sorted(
                financial.reservation_schedules,
                key=lambda schedule: schedule.source_proposal_hash,
            )
        ),
        "settlement_account_id": financial.settlement_book.account_id,
        "settlement_rules": financial.settlement_rules,
        "financial_dispatch_plan": _financial_dispatch_semantics(
            case.financial_dispatch_plan
        ),
    }


def _execution_case_semantic_spec_v3(
    *,
    base_spec: ExecutionCaseSemanticSpec,
    execution_case_plan: _ExecutionCasePlan,
    market_data_preparation: MultiResolutionMarketDataPreparation,
) -> ExecutionCaseSemanticSpec:
    if type(base_spec) is not ExecutionCaseSemanticSpec:
        raise TypeError("base_spec must be exact ExecutionCaseSemanticSpec")
    if type(execution_case_plan) is not _ExecutionCasePlan:
        raise TypeError("execution_case_plan must be exact _ExecutionCasePlan")
    if type(market_data_preparation) is not MultiResolutionMarketDataPreparation:
        raise TypeError(
            "market_data_preparation must be exact MultiResolutionMarketDataPreparation"
        )
    preparation = MultiResolutionMarketDataPreparation(
        market_data_preparation.decision_schedule,
        market_data_preparation.bindings,
        market_data_preparation.signal_lineages,
    )
    return replace(
        base_spec,
        decision_inputs_hash=canonical_sha256(
            {
                "type": "execution_case_decision_inputs_mrmd_v1",
                "base": _decision_semantics(execution_case_plan),  # pyright: ignore[reportArgumentType]
                "decision_schedule": preparation.decision_schedule,
                "signal_bindings": preparation.bindings.signal_bindings,
                "signal_lineages": preparation.signal_lineages,
            }
        ),
        execution_inputs_hash=canonical_sha256(
            {
                "type": "execution_case_execution_inputs_mrmd_v1",
                "base": _execution_semantics(execution_case_plan),  # pyright: ignore[reportArgumentType]
                "execution_bindings": preparation.bindings.execution_bindings,
            }
        ),
        financial_inputs_hash=canonical_sha256(
            _financial_semantics(execution_case_plan)  # pyright: ignore[reportArgumentType]
        ),
        snapshot_inputs_hash=canonical_sha256(
            {
                "type": "execution_case_snapshot_inputs_mrmd_v1",
                "base": execution_case_plan.snapshot_plan,
                "valuation_bindings": preparation.bindings.valuation_bindings,
            }
        ),
        run_end_inputs_hash=canonical_sha256(
            execution_case_plan.closeout_policy.spec()
        ),
    )


def _execution_case_semantic_spec_from_case_v3(
    *,
    case: ResolvedExecutionCase,
    market_data_preparation: MultiResolutionMarketDataPreparation,
    spec_key: str,
    spec_version: int,
    identity_namespace: IdentityNamespace,
    identity_plan: tuple[ExecutionCaseIdentityRule, ...],
) -> ExecutionCaseSemanticSpec:
    base_spec = ExecutionCaseComposer.semantic_spec_from_case(
        case,
        spec_key=spec_key,
        spec_version=spec_version,
        identity_namespace=identity_namespace,
        identity_plan=identity_plan,
    )
    closeout_policy = case.closeout_policy
    if type(closeout_policy) is not MarkToMarketCloseoutPolicy:
        raise TypeError("closeout_policy must be exact MarkToMarketCloseoutPolicy")
    return _execution_case_semantic_spec_v3(
        base_spec=base_spec,
        execution_case_plan=_ExecutionCasePlan(
            decision_cycles=case.decision_cycles,
            bar_executions=case.bar_executions,
            financial_state=case.financial_state,
            financial_dispatch_plan=case.financial_dispatch_plan,
            execution_model=case.execution_model,
            snapshot_plan=case.snapshot_plan,
            closeout_policy=closeout_policy,
        ),
        market_data_preparation=market_data_preparation,
    )


def _compose_execution_case_from_authority(
    *,
    request: BacktestRequest,
    semantic_run_id: str,
    market_reader: MarketBundleReader,
    hydrated_inputs: _HydratedExecutionCaseInputs,
) -> ResolvedExecutionCase:
    if type(request) is not BacktestRequest:
        raise TypeError("request must be exact BacktestRequest")
    if type(semantic_run_id) is not str or not semantic_run_id:
        raise TypeError("semantic_run_id must be nonempty str")
    if type(hydrated_inputs) is not _HydratedExecutionCaseInputs:
        raise TypeError("hydrated_inputs must be exact _HydratedExecutionCaseInputs")
    spec = hydrated_inputs.execution_case_semantic_spec
    if spec.semantic_spec_hash != request.execution_case_semantic_hash:
        raise ValueError("execution case semantic spec does not bind the request")
    if (
        hydrated_inputs.target_stream.target_stream_digest
        != request.target_stream_digest
    ):
        raise ValueError("target stream does not bind the request")
    if market_reader.bundle_ref != request.market_bundle_ref:
        raise ValueError("market reader does not bind the request")

    timeline = DeterministicTimeline.open(
        reader=market_reader,
        stream_keys=hydrated_inputs.timeline_stream_keys,
        window=request.timeline_window,
    )
    if isinstance(timeline, InputValidationFailure):
        raise ValueError("execution timeline cannot be reconstructed")
    if (
        ExecutionCaseComposer.timeline_semantic_hash(timeline)
        != spec.timeline_semantic_hash
    ):
        raise ValueError("execution timeline semantic hash mismatch")

    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=semantic_run_id,
        namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    for rule in spec.identity_plan:
        if rule.domain_kind is None:
            identities.event_id(rule.binding_key)
        else:
            identities.domain_id(rule.binding_key)

    plan = hydrated_inputs.execution_case_plan
    result = ResolvedExecutionCase(
        case_key=spec.case_key,
        case_version=spec.case_version,
        semantic_spec_hash=spec.semantic_spec_hash,
        timeline=timeline,
        timeline_batch_size=hydrated_inputs.timeline_batch_size,
        target_stream=hydrated_inputs.target_stream,
        decision_cycles=plan.decision_cycles,
        bar_executions=plan.bar_executions,
        financial_state=plan.financial_state,
        financial_dispatch_plan=plan.financial_dispatch_plan,
        execution_model=plan.execution_model,
        snapshot_plan=plan.snapshot_plan,
        closeout_policy=plan.closeout_policy,
        identity_manifest=identities.manifest(),
        semantic_spec=spec,
    )
    recomputed_spec = ExecutionCaseComposer.semantic_spec_from_case(
        result,
        spec_key=spec.spec_key,
        spec_version=spec.spec_version,
        identity_namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    if recomputed_spec != spec:
        raise ValueError("execution case inputs do not match the semantic spec")
    if not result.verify_identity_manifest(semantic_run_id):
        raise ValueError("execution case identities do not match the semantic plan")
    return result


def _compose_execution_case_from_authority_v3(
    *,
    request: BacktestRequest,
    semantic_run_id: str,
    market_reader: MarketBundleReader,
    hydrated_inputs: _HydratedExecutionCaseInputs,
    market_data_preparation: MultiResolutionMarketDataPreparation,
) -> ResolvedExecutionCase:
    if type(request) is not BacktestRequest:
        raise TypeError("request must be exact BacktestRequest")
    if type(semantic_run_id) is not str or not semantic_run_id:
        raise TypeError("semantic_run_id must be nonempty str")
    if type(hydrated_inputs) is not _HydratedExecutionCaseInputs:
        raise TypeError("hydrated_inputs must be exact _HydratedExecutionCaseInputs")
    if type(market_data_preparation) is not MultiResolutionMarketDataPreparation:
        raise TypeError(
            "market_data_preparation must be exact MultiResolutionMarketDataPreparation"
        )
    spec = hydrated_inputs.execution_case_semantic_spec
    if spec.semantic_spec_hash != request.execution_case_semantic_hash:
        raise ValueError("execution case semantic spec does not bind the request")
    if (
        hydrated_inputs.target_stream.target_stream_digest
        != request.target_stream_digest
    ):
        raise ValueError("target stream does not bind the request")
    if market_reader.bundle_ref != request.market_bundle_ref:
        raise ValueError("market reader does not bind the request")

    timeline = DeterministicTimeline.open(
        reader=market_reader,
        stream_keys=hydrated_inputs.timeline_stream_keys,
        window=request.timeline_window,
    )
    if isinstance(timeline, InputValidationFailure):
        raise ValueError("execution timeline cannot be reconstructed")
    if (
        ExecutionCaseComposer.timeline_semantic_hash(timeline)
        != spec.timeline_semantic_hash
    ):
        raise ValueError("execution timeline semantic hash mismatch")

    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=semantic_run_id,
        namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    for rule in spec.identity_plan:
        if rule.domain_kind is None:
            identities.event_id(rule.binding_key)
        else:
            identities.domain_id(rule.binding_key)

    plan = hydrated_inputs.execution_case_plan
    result = ResolvedExecutionCase(
        case_key=spec.case_key,
        case_version=spec.case_version,
        semantic_spec_hash=spec.semantic_spec_hash,
        timeline=timeline,
        timeline_batch_size=hydrated_inputs.timeline_batch_size,
        target_stream=hydrated_inputs.target_stream,
        decision_cycles=plan.decision_cycles,
        bar_executions=plan.bar_executions,
        financial_state=plan.financial_state,
        financial_dispatch_plan=plan.financial_dispatch_plan,
        execution_model=plan.execution_model,
        snapshot_plan=plan.snapshot_plan,
        closeout_policy=plan.closeout_policy,
        identity_manifest=identities.manifest(),
        semantic_spec=spec,
    )
    recomputed_spec = _execution_case_semantic_spec_from_case_v3(
        case=result,
        market_data_preparation=market_data_preparation,
        spec_key=spec.spec_key,
        spec_version=spec.spec_version,
        identity_namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    if recomputed_spec != spec:
        raise ValueError("execution case inputs do not match the semantic spec")
    if not result.verify_identity_manifest(semantic_run_id):
        raise ValueError("execution case identities do not match the semantic plan")
    return result


def _validate_financial_component_bindings(
    resolved_request: ResolvedBacktestRequest,
    plan: _ExecutionCasePlan,
) -> None:
    spec = plan.financial_dispatch_plan.dispatcher_spec
    registered_spec = getattr(
        resolved_request.environment.market_semantics.implementation,
        "financial_dispatcher_spec",
        None,
    )
    if registered_spec is not None and registered_spec != spec:
        raise ValueError(
            "financial dispatcher spec does not bind the registered market profile"
        )
    # Legacy generic-cash plans predate profile-owned dispatcher refs.
    if spec == default_cash_financial_dispatcher_spec():
        return
    market = {
        value.port_type: value
        for value in resolved_request.environment.market_semantics.component_manifest
    }
    simulation = {
        value.port_type: value
        for value in resolved_request.environment.simulation.component_manifest
    }
    financial_refs = (
        spec.position_accounting_component,
        spec.financing_component,
        spec.margin_component,
    )
    if any(market.get(value.port_type) != value for value in financial_refs):
        raise ValueError(
            "financial dispatcher refs do not bind the resolved market profile"
        )
    if (
        simulation.get(SimulationPortType.LIQUIDATION_AUDIT_MODEL)
        != spec.liquidation_audit_component
    ):
        raise ValueError(
            "financial dispatcher liquidation ref does not bind the simulation profile"
        )


def _compose_execution_case(
    *,
    resolved_request: ResolvedBacktestRequest,
    market_reader: MarketBundleReader,
    hydrated_inputs: _HydratedExecutionCaseInputs,
) -> ResolvedExecutionCase:
    if type(resolved_request) is not ResolvedBacktestRequest:
        raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
    if type(hydrated_inputs) is not _HydratedExecutionCaseInputs:
        raise TypeError("hydrated_inputs must be exact _HydratedExecutionCaseInputs")
    request = resolved_request.request
    if (
        resolved_request.build_artifact_manifest.manifest_hash
        != request.build_artifact_manifest_hash
    ):
        raise ValueError("resolved build manifest does not bind the request")

    selected = {
        value.port_type: value
        for value in resolved_request.environment.simulation.component_manifest
    }
    plan = hydrated_inputs.execution_case_plan
    represented = (
        plan.execution_model.component_ref,
        plan.closeout_policy.spec().component_ref,
        *(value.slippage_model.component_ref for value in plan.bar_executions),
    )
    if any(selected.get(value.port_type) != value for value in represented):
        raise ValueError(
            "execution case component refs do not bind the resolved profile"
        )
    _validate_financial_component_bindings(resolved_request, plan)

    return _compose_execution_case_from_authority(
        request=request,
        semantic_run_id=resolved_request.semantic_run_id,
        market_reader=market_reader,
        hydrated_inputs=hydrated_inputs,
    )


def _compose_execution_case_v3(
    *,
    resolved_request: ResolvedBacktestRequest,
    market_reader: MarketBundleReader,
    hydrated_inputs: _HydratedExecutionCaseInputs,
    market_data_preparation: MultiResolutionMarketDataPreparation,
) -> ResolvedExecutionCase:
    if type(resolved_request) is not ResolvedBacktestRequest:
        raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
    if type(hydrated_inputs) is not _HydratedExecutionCaseInputs:
        raise TypeError("hydrated_inputs must be exact _HydratedExecutionCaseInputs")
    request = resolved_request.request
    if (
        resolved_request.build_artifact_manifest.manifest_hash
        != request.build_artifact_manifest_hash
    ):
        raise ValueError("resolved build manifest does not bind the request")

    selected = {
        value.port_type: value
        for value in resolved_request.environment.simulation.component_manifest
    }
    plan = hydrated_inputs.execution_case_plan
    represented = (
        plan.execution_model.component_ref,
        plan.closeout_policy.spec().component_ref,
        *(value.slippage_model.component_ref for value in plan.bar_executions),
    )
    if any(selected.get(value.port_type) != value for value in represented):
        raise ValueError(
            "execution case component refs do not bind the resolved profile"
        )
    _validate_financial_component_bindings(resolved_request, plan)

    return _compose_execution_case_from_authority_v3(
        request=request,
        semantic_run_id=resolved_request.semantic_run_id,
        market_reader=market_reader,
        hydrated_inputs=hydrated_inputs,
        market_data_preparation=market_data_preparation,
    )


class ExecutionCaseComposer:
    @staticmethod
    def timeline_semantic_hash(timeline: DeterministicTimeline) -> str:
        if not isinstance(timeline, DeterministicTimeline):
            raise TypeError("timeline must be DeterministicTimeline")
        return canonical_sha256(
            {
                "type": "execution_case_timeline_semantics_v1",
                "timeline_id": timeline.timeline_id,
                "bundle_ref": timeline.reader.bundle_ref,
                "stream_keys": timeline.stream_keys,
                "window": timeline.window,
            }
        )

    @classmethod
    def semantic_spec_from_case(
        cls,
        case: ResolvedExecutionCase,
        *,
        spec_key: str,
        spec_version: int,
        identity_namespace: IdentityNamespace,
        identity_plan: tuple[ExecutionCaseIdentityRule, ...],
    ) -> ExecutionCaseSemanticSpec:
        if not isinstance(case, ResolvedExecutionCase):
            raise TypeError("case must be ResolvedExecutionCase")
        for cycle in case.decision_cycles:
            for admission in cycle.admissions:
                if (
                    admission.order.intent.parent_id
                    != cycle.target_validity.normalized_target_id
                ):
                    raise ValueError(
                        "OrderIntent parent does not match normalized target"
                    )
        return ExecutionCaseSemanticSpec(
            schema_version=1,
            spec_key=spec_key,
            spec_version=spec_version,
            case_key=case.case_key,
            case_version=case.case_version,
            identity_namespace=identity_namespace,
            identity_plan=identity_plan,
            timeline_semantic_hash=cls.timeline_semantic_hash(case.timeline),
            target_stream_digest=case.target_stream.target_stream_digest,
            decision_inputs_hash=canonical_sha256(_decision_semantics(case)),
            execution_inputs_hash=canonical_sha256(_execution_semantics(case)),
            financial_inputs_hash=canonical_sha256(_financial_semantics(case)),
            snapshot_inputs_hash=canonical_sha256(case.snapshot_plan),
            run_end_inputs_hash=canonical_sha256(case.closeout_policy.spec()),
        )

    def compose(
        self,
        *,
        resolved_request: ResolvedBacktestRequest,
        builder: _ExecutionCaseBuilder,
    ) -> ResolvedExecutionCase:
        if not isinstance(resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        if not callable(getattr(builder, "semantic_spec", None)) or not callable(
            getattr(builder, "build", None)
        ):
            raise TypeError("builder must provide semantic_spec and build")
        spec = builder.semantic_spec()
        request = resolved_request.request
        if request.execution_case_semantic_hash != spec.semantic_spec_hash:
            raise ValueError("resolved Request does not bind builder semantic spec")
        if request.target_stream_digest != spec.target_stream_digest:
            raise ValueError("semantic spec target digest does not match Request")

        identities = ExecutionCaseIdentityFactory(
            semantic_run_id=resolved_request.semantic_run_id,
            namespace=spec.identity_namespace,
            identity_plan=spec.identity_plan,
        )
        case = builder.build(identities, spec.semantic_spec_hash)
        if not isinstance(case, ResolvedExecutionCase):
            raise TypeError("builder must return ResolvedExecutionCase")
        if case.identity_manifest is not None:
            raise ValueError("builder must not supply an identity manifest")
        recomputed = self.semantic_spec_from_case(
            case,
            spec_key=spec.spec_key,
            spec_version=spec.spec_version,
            identity_namespace=spec.identity_namespace,
            identity_plan=spec.identity_plan,
        )
        if recomputed != spec:
            raise ValueError("resolved Case inputs do not match semantic spec")
        if builder.semantic_spec() != spec:
            raise ValueError("builder semantic spec changed during composition")

        composed = replace(
            case,
            identity_manifest=identities.manifest(),
            semantic_spec=spec,
        )
        if not composed.verify_identity_manifest(resolved_request.semantic_run_id):
            raise ValueError(
                "resolved Case identity manifest does not exact-cover Case"
            )
        return composed


__all__ = ["ExecutionCaseComposer"]
