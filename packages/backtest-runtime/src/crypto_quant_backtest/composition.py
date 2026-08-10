"""Two-phase Semantic Run and resolved ExecutionCase composition."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from crypto_quant_domain import (
    AccountingJournalEntry,
    IdentityNamespace,
    OrderIntent,
    PortfolioSnapshot,
    canonical_sha256,
)
from crypto_quant_trading import StrategyAllocation

from .slippage import DeterministicBpsSlippageModel
from .engine import (
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    ResolvedExecutionCase,
    ResolvedOrderAdmission,
)
from .financial_dispatch import FillAccountingDispatchPlan, FinancialDispatchPlan
from .resolution import ResolvedBacktestRequest
from .timeline import DeterministicTimeline


class _ExecutionCaseBuilder(Protocol):
    def semantic_spec(self) -> ExecutionCaseSemanticSpec:
        pass

    def build(
        self,
        identities: ExecutionCaseIdentityFactory,
        semantic_spec_hash: str,
    ) -> ResolvedExecutionCase:
        pass


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
    return tuple(
        {
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
        for cycle in case.decision_cycles
    )


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


def _execution_semantics(case: ResolvedExecutionCase) -> dict[str, object]:
    return {
        "admissions": tuple(
            _admission_semantics(admission)
            for cycle in case.decision_cycles
            for admission in cycle.admissions
        ),
        "bar_executions": tuple(
            {
                "source_event_id": execution.event_id,
                "pretrade_plan": execution.pretrade_plan,
                "liquidity_evidence": execution.liquidity_evidence,
                "market_state": execution.market_state,
                "slippage_model": _slippage_model_semantics(
                    execution.slippage_model
                ),
                "fill_event_at": execution.fill_event_at,
                "accounting_plan": _accounting_plan_semantics(
                    execution.accounting_plan
                ),
            }
            for execution in case.bar_executions
        ),
        "execution_model_spec": case.execution_model.spec(),
    }


def _journal_entry_semantics(
    entry: AccountingJournalEntry,
) -> dict[str, object]:
    return {
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


def _financial_dispatch_semantics(
    plan: FinancialDispatchPlan,
) -> dict[str, object]:
    return {
        "dispatcher_spec": plan.dispatcher_spec,
        "scheduled_account_events": tuple(
            {
                "event_id": value.event_id,
                "event_at": value.event_at,
                "operation_key": value.operation_key,
                "component_keys": value.component_keys,
                "semantic_payload": value.semantic_payload,
                "expected_artifact_roles": value.expected_artifact_roles,
            }
            for value in plan.scheduled_account_events
        ),
        "final_snapshot_payload": plan.final_snapshot_payload,
        "expected_artifact_roles": plan.expected_artifact_roles,
    }


def _financial_semantics(case: ResolvedExecutionCase) -> dict[str, object]:
    financial = case.financial_state
    if (
        financial.settlement_book.obligations
        or financial.settlement_book.events
    ):
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
            raise ValueError("resolved Case identity manifest does not exact-cover Case")
        return composed


__all__ = ["ExecutionCaseComposer"]
