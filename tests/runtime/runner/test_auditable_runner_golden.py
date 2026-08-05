from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import (
    AttemptIdentity,
    AuditableBacktestRunner,
    DeterministicBarEngine,
    EngineCancellation,
    EngineCancellationRequest,
    EngineExecutionOutcome,
    EngineFailureCode,
    ExecutionTrace,
    InputOrigin,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.runtime.runner._fixtures import RecordingEngine, execution_case, resolved_request
from tests.runtime.runner.test_auditable_runner import engine_failure


FIXTURE = Path("tests/fixtures/runtime/auditable-runner-outcome-mapping-v1.json")


def build_actual() -> dict[str, object]:
    resolved = resolved_request()
    case = execution_case()
    engine_outcome = DeterministicBarEngine().run(case)
    assert engine_outcome.result is not None
    runner = AuditableBacktestRunner(engine=RecordingEngine(outcome=engine_outcome))
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

    blocked = AuditableBacktestRunner(
        engine=RecordingEngine(
            outcome=EngineExecutionOutcome(
                engine_failure=engine_failure(EngineFailureCode.TARGET_INPUT_DECODE)
            )
        )
    ).execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    cancel_request = EngineCancellationRequest("bar-open-1", "operator_cancelled")
    cancellation = EngineCancellation(
        case_hash=case.case_hash,
        request=cancel_request,
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
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        cancellation=cancel_request,
    )

    assert first.ready_to_finalize is not None
    assert second.ready_to_finalize is not None
    assert blocked.blocked_report is not None
    assert blocked.terminal_outcome is not None
    assert cancelled.cancelled_report is not None
    assert cancelled.terminal_outcome is not None
    classifier = AuditableBacktestRunner()
    actual = {
        "schema_version": 1,
        "semantic_run_id": resolved.semantic_run_id,
        "engine_result_hash": engine_outcome.result.result_hash,
        "first": {
            "attempt": first.attempt.to_canonical_dict(),
            "status": first.status.value,
            "terminal_outcome": None,
            "ready_hash": first.ready_to_finalize.ready_hash,
            "record_hash": canonical_sha256(first),
        },
        "retry": {
            "attempt": second.attempt.to_canonical_dict(),
            "status": second.status.value,
            "terminal_outcome": None,
            "ready_hash": second.ready_to_finalize.ready_hash,
            "record_hash": canonical_sha256(second),
        },
        "blocked": {
            "status": blocked.status.value,
            "terminal_outcome": blocked.terminal_outcome.value,
            "issue": json.loads(canonical_bytes(blocked.blocked_report.issue)),
            "report_hash": blocked.blocked_report.report_hash,
            "record_hash": canonical_sha256(blocked),
        },
        "cancelled": {
            "status": cancelled.status.value,
            "terminal_outcome": cancelled.terminal_outcome.value,
            "cancellation_hash": cancellation.cancellation_hash,
            "report_hash": cancelled.cancelled_report.report_hash,
            "record_hash": canonical_sha256(cancelled),
        },
        "precomputed_target_failure_outcome": classifier.classify_engine_failure(
            EngineFailureCode.TARGET_VALIDATION,
            InputOrigin.PRECOMPUTED_TARGET_STREAM,
        ).value,
        "runtime_strategy_target_failure_outcome": classifier.classify_engine_failure(
            EngineFailureCode.TARGET_VALIDATION,
            InputOrigin.RUNTIME_STRATEGY,
        ).value,
        "engine_failure_mapping": {
            code.value: classifier.classify_engine_failure(
                code, InputOrigin.PRECOMPUTED_TARGET_STREAM
            ).value
            for code in EngineFailureCode
        },
    }
    return actual


def test_auditable_runner_outcome_mapping_matches_static_golden() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert build_actual() == expected
