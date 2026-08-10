from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crypto_quant_backtest import (
    DeterministicBarEngine,
    EngineCancellation,
    EngineCancellationRequest,
    EngineFailure,
    EngineFailureCode,
    EngineStage,
)
from crypto_quant_domain import Money, Quantity, Scale, canonical_sha256

from tests.runtime.engine._fixtures import (
    BAR_EVENT_ID,
    CASH_KEY,
    POSITION_KEY,
    execution_case,
    input_validation_failure,
)


def test_engine_runs_target_to_fill_accounting_snapshot_and_run_end() -> None:
    case = execution_case()
    outcome = DeterministicBarEngine().run(case)

    assert outcome.result is not None
    assert outcome.engine_failure is None
    result = outcome.result
    assert len(result.decision_batches) == 1
    assert len(result.allocations) == 1
    assert len(result.approved_targets) == 1
    assert len(result.normalized_targets) == 1
    assert len(result.order_plans) == 1
    assert len(result.order_streams) == 1
    assert len(result.fills) == 1
    assert len(result.slippage_decisions) == 1
    assert len(result.fee_assessments) == 1
    assert result.final_journal.entry_count == 3
    assert result.final_ledger_state.cash_amount(CASH_KEY) == Money(
        47_392, Scale(2), "USD"
    )
    assert result.final_ledger_state.position_quantity(POSITION_KEY) == Quantity(
        5_000, Scale(3), str(POSITION_KEY.instrument_id)
    )
    assert result.final_portfolio_snapshot.equity == Money(102_392, Scale(2), "USD")
    assert result.final_portfolio_snapshot.unrealized_pnl == Money(
        2_445, Scale(2), "USD"
    )
    assert result.final_portfolio_snapshot.fees == Money(53, Scale(2), "USD")
    assert result.run_end_report.open_positions == result.final_portfolio_snapshot.positions
    assert not result.run_end_report.terminated_orders
    assert not result.run_end_report.pending_fee_assessments
    assert EngineStage.DECISION_BATCH in {entry.stage for entry in result.trace.entries}
    assert EngineStage.FILL in {entry.stage for entry in result.trace.entries}
    assert EngineStage.RUN_END is result.trace.entries[-1].stage
    assert not hasattr(result, "semantic_run_id")
    assert not hasattr(result, "attempt_id")
    assert not hasattr(result, "outcome")


def test_same_case_is_exact_across_timeline_batch_size() -> None:
    first = DeterministicBarEngine().run(execution_case(batch_size=1)).result
    second = DeterministicBarEngine().run(execution_case(batch_size=3)).result

    assert first is not None and second is not None
    assert first.case_hash == second.case_hash
    assert first.trace.trace_hash == second.trace.trace_hash
    assert first.final_journal.journal_hash == second.final_journal.journal_hash
    assert first.final_ledger_state.state_hash == second.final_ledger_state.state_hash
    assert canonical_sha256(first.final_portfolio_snapshot) == canonical_sha256(
        second.final_portfolio_snapshot
    )
    assert first.run_end_report.report_hash == second.run_end_report.report_hash
    assert first.result_hash == second.result_hash


def test_warmup_target_is_suppressed_without_extra_trading_authority() -> None:
    result = DeterministicBarEngine().run(
        execution_case(include_warmup=True)
    ).result

    assert result is not None
    stages = tuple(entry.stage for entry in result.trace.entries)
    assert stages.count(EngineStage.TARGET_WARMUP_SUPPRESSED) == 1
    assert len(result.decision_batches) == 1
    assert len(result.order_plans) == 1
    assert len(result.order_streams) == 1
    assert len(result.fills) == 1
    assert len(result.slippage_decisions) == 1


def test_capability_rejection_is_engine_failure_with_no_partial_result() -> None:
    outcome = DeterministicBarEngine().run(
        execution_case(reject_capability=True)
    )

    assert outcome.result is None
    assert isinstance(outcome.engine_failure, EngineFailure)
    assert outcome.engine_failure.code is EngineFailureCode.CAPABILITY_REJECTED
    assert outcome.input_validation_failure is None
    assert outcome.cancellation is None


def test_final_snapshot_evidence_mismatch_fails_structurally() -> None:
    case = execution_case()
    cash = next(
        value
        for value in case.snapshot_plan.valuations
        if value.value_ref.kind.value == "cash"
    )
    wrong_cash = Money(cash.native_value.units + 1, cash.native_value.scale, "USD")
    bad_plan = replace(
        case.snapshot_plan,
        valuations=tuple(
            replace(value, native_value=wrong_cash, reporting_value=wrong_cash)
            if value is cash
            else value
            for value in case.snapshot_plan.valuations
        ),
    )
    outcome = DeterministicBarEngine().run(
        replace(
            case,
            snapshot_plan=bad_plan,
            financial_dispatch_plan=replace(
                case.financial_dispatch_plan,
                final_snapshot_payload=bad_plan,
            ),
        )
    )

    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert (
        outcome.engine_failure.code
        == EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    )


def test_market_input_validation_failure_is_not_engine_failure() -> None:
    failure = input_validation_failure()
    outcome = DeterministicBarEngine().run(failure)

    assert outcome.input_validation_failure is failure
    assert outcome.engine_failure is None
    assert outcome.cancellation is None
    assert outcome.result is None


def test_explicit_event_cancellation_is_nominal_and_deterministic() -> None:
    request = EngineCancellationRequest(
        cancel_before_event_id=BAR_EVENT_ID,
        reason_code="operator_requested_test_cancellation",
    )
    first = DeterministicBarEngine().run(
        execution_case(batch_size=1), cancellation=request
    )
    second = DeterministicBarEngine().run(
        execution_case(batch_size=3), cancellation=request
    )

    assert isinstance(first.cancellation, EngineCancellation)
    assert isinstance(second.cancellation, EngineCancellation)
    assert first.cancellation.cancellation_hash == second.cancellation.cancellation_hash
    assert first.cancellation.processed_timeline_events == 1
    assert first.result is None and first.engine_failure is None


def test_result_and_case_are_immutable() -> None:
    case = execution_case()
    result = DeterministicBarEngine().run(case).result
    assert result is not None

    with pytest.raises(FrozenInstanceError):
        setattr(case, "case_key", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(result, "case_hash", "sha256:" + "0" * 64)
