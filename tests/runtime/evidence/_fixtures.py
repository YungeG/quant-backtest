from __future__ import annotations

from crypto_quant_backtest import (
    AttemptExecutionRecord,
    AttemptIdentity,
    AuditableBacktestRunner,
    DeterministicBarEngine,
    EngineCancellation,
    EngineCancellationRequest,
    EngineExecutionOutcome,
    EngineFailure,
    EngineFailureCode,
    ExecutionTrace,
    InputOrigin,
)
from crypto_quant_domain import canonical_sha256
from tests.runtime.runner._fixtures import RecordingEngine, execution_case, resolved_request


def _engine_failure(code: EngineFailureCode) -> EngineFailure:
    case = execution_case()
    return EngineFailure(
        code=code,
        case_hash=case.case_hash,
        trace_hash=ExecutionTrace().trace_hash,
        subject_keys=(code.value,),
        evidence_hashes=(canonical_sha256({"code": code.value}),),
    )


def attempt_record(branch: str) -> AttemptExecutionRecord:
    resolved = resolved_request()
    case = execution_case()
    attempt = AttemptIdentity.first(resolved.semantic_run_id)
    cancellation = None

    if branch == "ready":
        engine_outcome = DeterministicBarEngine().run(case)
    elif branch == "blocked":
        engine_outcome = EngineExecutionOutcome(
            engine_failure=_engine_failure(EngineFailureCode.TARGET_INPUT_DECODE)
        )
    elif branch == "failed":
        engine_outcome = EngineExecutionOutcome(
            engine_failure=_engine_failure(EngineFailureCode.ACCOUNTING_FAILURE)
        )
    elif branch == "cancelled":
        cancellation = EngineCancellationRequest("bar-open-1", "operator_cancelled")
        engine_outcome = EngineExecutionOutcome(
            cancellation=EngineCancellation(
                case_hash=case.case_hash,
                request=cancellation,
                processed_timeline_events=1,
                trace_hash=ExecutionTrace().trace_hash,
            )
        )
    else:
        raise ValueError(f"unknown branch: {branch}")

    return AuditableBacktestRunner(
        engine=RecordingEngine(outcome=engine_outcome)
    ).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        cancellation=cancellation,
    )


__all__ = ["attempt_record"]
