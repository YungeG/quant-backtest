from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crypto_quant_backtest import (
    AttemptExecutionRecord,
    AttemptExecutionStatus,
    AttemptIdentity,
    AuditableBacktestRunner,
    BacktestRunOutcome,
    DeterministicBarEngine,
    EngineCancellation,
    EngineCancellationRequest,
    EngineExecutionOutcome,
    EngineFailure,
    EngineFailureCode,
    ExecutionTrace,
    InputOrigin,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.runtime.engine._fixtures import input_validation_failure
from tests.runtime.runner._fixtures import RecordingEngine, execution_case, resolved_request


BLOCKED_ENGINE_CODES = {
    EngineFailureCode.TIMELINE_FAILURE,
    EngineFailureCode.POSITION_SIZING,
    EngineFailureCode.CAPABILITY_REJECTED,
    EngineFailureCode.TRANSLATION_REJECTED,
    EngineFailureCode.MARKET_RULE_REJECTED,
    EngineFailureCode.MARKET_RULE_DATA_FAILURE,
    EngineFailureCode.FEE_RESERVATION,
    EngineFailureCode.PRETRADE_REJECTED,
    EngineFailureCode.EXECUTION_FAILURE,
    EngineFailureCode.SLIPPAGE_FAILURE,
    EngineFailureCode.FEE_ASSESSMENT_FAILURE,
    EngineFailureCode.SNAPSHOT_PROJECTION_FAILURE,
    EngineFailureCode.RUN_END_TERMINATED,
    EngineFailureCode.MISSING_SCHEDULED_EVENT,
}
FAILED_ENGINE_CODES = {
    EngineFailureCode.ALLOCATION,
    EngineFailureCode.PORTFOLIO_RISK,
    EngineFailureCode.REBALANCE,
    EngineFailureCode.ORDER_PLAN_MISMATCH,
    EngineFailureCode.PRETRADE_CONTRACT_FAILURE,
    EngineFailureCode.FILL_CONSTRUCTION,
    EngineFailureCode.ACCOUNTING_FAILURE,
    EngineFailureCode.FEE_ACCOUNTING_FAILURE,
    EngineFailureCode.CASE_EVIDENCE_MISMATCH,
}
ORIGIN_SENSITIVE_CODES = {
    EngineFailureCode.TARGET_INPUT_DECODE,
    EngineFailureCode.TARGET_VALIDATION,
    EngineFailureCode.DECISION_BATCH,
}


def engine_failure(code: EngineFailureCode) -> EngineFailure:
    case = execution_case()
    return EngineFailure(
        code=code,
        case_hash=case.case_hash,
        trace_hash=ExecutionTrace().trace_hash,
        subject_keys=(code.value,),
        evidence_hashes=(canonical_sha256({"code": code.value}),),
    )


def test_success_is_ready_to_finalize_and_preserves_exact_engine_result() -> None:
    resolved = resolved_request()
    case = execution_case()
    engine_result = DeterministicBarEngine().run(case).result
    assert engine_result is not None
    engine = RecordingEngine(outcome=EngineExecutionOutcome(result=engine_result))
    runner = AuditableBacktestRunner(engine=engine)
    attempt = AttemptIdentity.first(resolved.semantic_run_id)

    record = runner.execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.status is AttemptExecutionStatus.READY_TO_FINALIZE
    assert record.terminal_outcome is None
    assert record.ready_to_finalize is not None
    assert record.ready_to_finalize.engine_result is engine_result
    assert record.ready_to_finalize.engine_result.result_hash == engine_result.result_hash
    assert record.ready_to_finalize.attempt == attempt
    assert not hasattr(record.ready_to_finalize, "evidence_manifest_hash")
    assert record.terminal_outcome is not BacktestRunOutcome.COMPLETED
    assert len(engine.calls) == 1
    assert engine.calls[0][0] is case
    assert engine.calls[0][1] is None
    with pytest.raises(FrozenInstanceError):
        setattr(
            record.ready_to_finalize,
            "input_origin",
            InputOrigin.RUNTIME_STRATEGY,
        )


def test_engine_failure_mapping_is_explicit_exhaustive_and_origin_aware() -> None:
    runner = AuditableBacktestRunner()
    assert (
        BLOCKED_ENGINE_CODES | FAILED_ENGINE_CODES | ORIGIN_SENSITIVE_CODES
        == set(EngineFailureCode)
    )

    for code in BLOCKED_ENGINE_CODES:
        assert (
            runner.classify_engine_failure(
                code, InputOrigin.PRECOMPUTED_TARGET_STREAM
            )
            is BacktestRunOutcome.BLOCKED
        )
    for code in FAILED_ENGINE_CODES:
        assert (
            runner.classify_engine_failure(
                code, InputOrigin.PRECOMPUTED_TARGET_STREAM
            )
            is BacktestRunOutcome.FAILED
        )
    for code in ORIGIN_SENSITIVE_CODES:
        assert (
            runner.classify_engine_failure(
                code, InputOrigin.PRECOMPUTED_TARGET_STREAM
            )
            is BacktestRunOutcome.BLOCKED
        )
        assert (
            runner.classify_engine_failure(code, InputOrigin.RUNTIME_STRATEGY)
            is BacktestRunOutcome.FAILED
        )


def test_input_validation_engine_failure_and_cancellation_are_nominally_distinct() -> None:
    resolved = resolved_request()
    case = execution_case()
    attempt = AttemptIdentity.first(resolved.semantic_run_id)

    blocked_input = AuditableBacktestRunner(
        engine=RecordingEngine(
            outcome=EngineExecutionOutcome(
                input_validation_failure=input_validation_failure()
            )
        )
    ).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    assert blocked_input.status is AttemptExecutionStatus.BLOCKED
    assert blocked_input.blocked_report is not None
    assert blocked_input.blocked_report.issue.code == "market_bundle_input_validation"

    blocked_target = AuditableBacktestRunner(
        engine=RecordingEngine(
            outcome=EngineExecutionOutcome(
                engine_failure=engine_failure(EngineFailureCode.TARGET_VALIDATION)
            )
        )
    ).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    assert blocked_target.status is AttemptExecutionStatus.BLOCKED
    assert blocked_target.blocked_report is not None
    assert blocked_target.blocked_report.issue.code == "target_validation"

    request = EngineCancellationRequest("bar-open-1", "operator_cancelled")
    cancellation = EngineCancellation(
        case_hash=case.case_hash,
        request=request,
        processed_timeline_events=1,
        trace_hash=ExecutionTrace().trace_hash,
    )
    cancelled = AuditableBacktestRunner(
        engine=RecordingEngine(
            outcome=EngineExecutionOutcome(cancellation=cancellation)
        )
    ).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        cancellation=request,
    )
    assert cancelled.status is AttemptExecutionStatus.CANCELLED
    assert cancelled.cancelled_report is not None
    assert cancelled.cancelled_report.cancellation is cancellation
    assert cancelled.terminal_outcome is BacktestRunOutcome.CANCELLED


def test_origin_mismatch_fails_before_engine_and_exception_message_is_not_canonical() -> None:
    resolved = resolved_request()
    case = execution_case()
    attempt = AttemptIdentity.first(resolved.semantic_run_id)
    engine = RecordingEngine(outcome=DeterministicBarEngine().run(case))

    mismatch = AuditableBacktestRunner(engine=engine).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.RUNTIME_STRATEGY,
    )
    assert mismatch.status is AttemptExecutionStatus.FAILED
    assert mismatch.failed_report is not None
    assert mismatch.failed_report.issue.code == "input_origin_mismatch"
    assert not engine.calls

    exploding = RecordingEngine(error=RuntimeError("secret host/path/detail"))
    failed = AuditableBacktestRunner(engine=exploding).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    assert failed.status is AttemptExecutionStatus.FAILED
    assert failed.failed_report is not None
    assert failed.failed_report.issue.code == "unhandled_engine_exception"
    assert b"secret host/path/detail" not in canonical_bytes(failed)
    assert b"builtins.RuntimeError" in canonical_bytes(failed)

    ready = AuditableBacktestRunner(
        engine=RecordingEngine(outcome=DeterministicBarEngine().run(case))
    ).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    assert ready.ready_to_finalize is not None
    with pytest.raises(ValueError, match="exactly one branch"):
        AttemptExecutionRecord(
            ready_to_finalize=ready.ready_to_finalize,
            failed_report=failed.failed_report,
        )


def test_retry_creates_child_attempt_and_reinvokes_the_same_initial_case() -> None:
    resolved = resolved_request()
    case = execution_case()
    engine_outcome = DeterministicBarEngine().run(case)
    assert engine_outcome.result is not None
    engine = RecordingEngine(outcome=engine_outcome)
    runner = AuditableBacktestRunner(engine=engine)
    first = runner.execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    second = runner.retry_from_start(
        previous=first,
        resolved_request=resolved,
        execution_case=case,
        next_attempt_ordinal=2,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert second.attempt.attempt_id != first.attempt.attempt_id
    assert second.attempt.parent_attempt_id == first.attempt.attempt_id
    assert second.attempt.semantic_run_id == first.attempt.semantic_run_id
    assert second.ready_to_finalize is not None
    assert first.ready_to_finalize is not None
    assert second.ready_to_finalize.engine_result.result_hash == (
        first.ready_to_finalize.engine_result.result_hash
    )
    assert len(engine.calls) == 2
    assert all(call[0] is case and call[1] is None for call in engine.calls)
    assert first.attempt.ordinal == 1
    with pytest.raises(ValueError, match="greater than previous"):
        runner.retry_from_start(
            previous=first,
            resolved_request=resolved,
            execution_case=case,
            next_attempt_ordinal=1,
            input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        )


def test_attempt_identity_rejects_wrong_semantic_run() -> None:
    resolved = resolved_request()
    attempt = AttemptIdentity.first(resolved.semantic_run_id)
    with pytest.raises(ValueError, match="semantic run"):
        replace(attempt, semantic_run_id="run_" + "f" * 64)

    wrong_attempt = AttemptIdentity.first("run_" + "e" * 64)
    with pytest.raises(ValueError, match="Attempt semantic run"):
        AuditableBacktestRunner().execute(
            resolved_request=resolved,
            execution_case=execution_case(),
            attempt=wrong_attempt,
            input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        )
