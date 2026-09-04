from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from crypto_quant_backtest import (
    CashFillAccountingPlan,
    DefaultCashFinancialDispatcher,
    DeterministicBarEngine,
    EngineFailureCode,
    FillAccountingDispatchPlan,
    FinancialDispatcherSpec,
    FinancialDispatchFailureCode,
    FinancialDispatchOutcome,
    FinancialDispatchPlan,
    FinancialStateView,
    ResolvedExecutionCase,
    ScheduledAccountEvent,
)
from crypto_quant_domain import (
    AccountingEntryType,
    Fill,
    Money,
)
from crypto_quant_trading import FinalFeeAssessmentResult, GenericLedger

from tests.kernel.accounting._fixtures import COST_BASIS_POLICY_V2
from tests.runtime.engine._fixtures import (
    CASH_KEY,
    MONEY_SCALE,
    POSITION_KEY,
    CashAccountingSemanticPayload,
    cash_accounting_plan,
    execution_case,
)


def _v2_cash_plan() -> FillAccountingDispatchPlan:
    plan = cash_accounting_plan()
    position_payload = replace(
        cast(CashFillAccountingPlan, plan.position_payload),
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        cost_basis_policy=COST_BASIS_POLICY_V2,
    )
    semantic_payload = replace(
        cast(CashAccountingSemanticPayload, plan.semantic_payload),
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        cost_basis_policy=COST_BASIS_POLICY_V2,
    )
    return replace(
        plan,
        position_payload=position_payload,
        semantic_payload=semantic_payload,
    )


class _TamperingDispatcher:
    def __init__(
        self,
        *,
        corrupt_evidence_at: str = "fill",
        corrupt_projection: bool = False,
        remove_lot_changes: bool = False,
    ) -> None:
        self._delegate = DefaultCashFinancialDispatcher()
        self._corrupt_evidence_at = corrupt_evidence_at
        self._corrupt_projection = corrupt_projection
        self._remove_lot_changes = remove_lot_changes

    @property
    def spec(self) -> FinancialDispatcherSpec:
        return self._delegate.spec

    def book_fill(
        self,
        plan: FillAccountingDispatchPlan,
        fill: Fill,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        outcome = self._delegate.book_fill(plan, fill, state_view)
        assert outcome.result is not None
        if self._remove_lot_changes:
            return replace(
                outcome,
                result=replace(
                    outcome.result,
                    journal_entries=tuple(
                        replace(entry, position_lot_changes=())
                        for entry in outcome.result.journal_entries
                    ),
                ),
            )
        if self._corrupt_evidence_at == "fill" and not self._corrupt_projection:
            return replace(
                outcome,
                result=replace(outcome.result, position_lot_books=()),
            )
        if not self._corrupt_projection:
            return outcome
        entry = outcome.result.journal_entries[0]
        lot_change = entry.position_lot_changes[0]
        invalid_entry = replace(
            entry,
            position_lot_changes=(
                replace(lot_change, before=lot_change.after, after=None),
            ),
        )
        return replace(
            outcome,
            result=replace(outcome.result, journal_entries=(invalid_entry,)),
        )

    def book_fee(
        self,
        plan: FillAccountingDispatchPlan,
        fill: Fill,
        assessment: FinalFeeAssessmentResult,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        outcome = self._delegate.book_fee(plan, fill, assessment, state_view)
        if self._corrupt_evidence_at != "fee" or outcome.result is None:
            return outcome
        return replace(
            outcome,
            result=replace(outcome.result, position_lot_books=()),
        )

    def dispatch_scheduled_event(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        return self._delegate.dispatch_scheduled_event(event, state_view)

    def project_final_snapshot(
        self,
        plan: FinancialDispatchPlan,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        outcome = self._delegate.project_final_snapshot(plan, state_view)
        if self._corrupt_evidence_at != "final" or outcome.result is None:
            return outcome
        return replace(
            outcome,
            result=replace(outcome.result, position_lot_books=()),
        )


def _v2_execution_case() -> ResolvedExecutionCase:
    baseline = execution_case()
    v2_plan = _v2_cash_plan()
    v2_bar_execution = replace(
        baseline.bar_executions[0],
        accounting_plan=v2_plan,
    )
    return replace(
        baseline,
        bar_executions=(v2_bar_execution,),
    )


def test_v2_engine_run_uses_ledger_authority_for_lots_and_replays_ledger() -> None:
    case = _v2_execution_case()

    outcome = DeterministicBarEngine().run(case)
    assert outcome.result is not None

    result = outcome.result
    assert result.final_ledger_state.position_balances
    final_position = result.final_ledger_state.position_balances[0]
    assert final_position.lots
    final_lot = final_position.lots[0]
    assert final_lot.total_cost_basis == Money(52_555, MONEY_SCALE, "USD")
    assert final_lot.allocated_fees == (Money(53, MONEY_SCALE, "USD"),)

    replay = GenericLedger(case.financial_state.ledger_schema).project(result.final_journal)
    assert replay == result.final_ledger_state

    fee_entries = tuple(
        entry
        for entry in result.final_journal.entries
        if entry.entry_type == AccountingEntryType.FEE_CHARGED
    )
    assert fee_entries
    assert fee_entries[0].position_lot_changes


@pytest.mark.parametrize("stage", ("fill", "fee", "final"))
def test_engine_rejects_tampered_v2_position_lot_evidence(stage: str) -> None:
    dispatcher = _TamperingDispatcher(corrupt_evidence_at=stage)
    outcome = DeterministicBarEngine(dispatcher).run(_v2_execution_case())

    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert outcome.engine_failure.subject_keys == (
        "position_lot_books",
        FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value,
    )


def test_engine_rejects_v2_dispatcher_that_removes_all_lot_changes() -> None:
    dispatcher = _TamperingDispatcher(remove_lot_changes=True)
    outcome = DeterministicBarEngine(dispatcher).run(_v2_execution_case())

    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert outcome.engine_failure.subject_keys == (
        "position_lot_books",
        FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value,
    )


def test_engine_structures_staged_ledger_projection_failure() -> None:
    dispatcher = _TamperingDispatcher(corrupt_projection=True)
    outcome = DeterministicBarEngine(dispatcher).run(_v2_execution_case())

    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert outcome.engine_failure.subject_keys == (
        "generic_ledger_projection",
        FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value,
    )
