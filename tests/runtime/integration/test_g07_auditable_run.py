from __future__ import annotations

from pathlib import Path

import pytest

from crypto_quant_backtest import (
    AttemptEvidenceWriter,
    AttemptIdentity,
    AuditableBacktestRunner,
    BacktestRunOutcome,
    DeterministicBarEngine,
    EngineExecutionResult,
    InputOrigin,
    IntegrityIssueCode,
    ResultGrade,
)
from tests.runtime.integration._fixtures import completed_journey, mismatch_journey
from tests.runtime.runner._fixtures import RecordingEngine


def _tree_bytes(directory: Path) -> dict[str, bytes]:
    try:
        return {
            str(path.relative_to(directory)): path.read_bytes()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        }
    except OSError as error:
        pytest.fail(f"cannot read G07 run tree: {error}")


def _result_domain_ids(result: EngineExecutionResult) -> frozenset[str]:
    return frozenset(
        (
            *(stream.order.order_id.value for stream in result.order_streams),
            *(fill.fill_id.value for fill in result.fills),
            *(fee.fee_assessment_id.value for fee in result.fee_assessments),
            *(
                entry.journal_entry_id.value
                for entry in result.final_journal.entries
            ),
        )
    )


def test_two_attempts_publish_one_auditable_development_result(
    tmp_path: Path,
) -> None:
    journey = completed_journey(tmp_path)
    first, second = journey.attempts.attempt_hashes
    first_evidence, second_evidence = journey.attempts.finalized_attempts
    finalized = journey.publication.finalized_result

    assert finalized is not None
    assert journey.publication.failure is None
    assert not journey.canonical_existed_before
    assert len(journey.engine_calls) == 2
    assert all(call_case is journey.case for call_case in journey.engine_calls)
    assert first.attempt.attempt_id != second.attempt.attempt_id
    assert first.attempt.semantic_run_id == second.attempt.semantic_run_id
    assert first.execution_result_hash == second.execution_result_hash
    assert first.engine_result.case_hash == second.engine_result.case_hash
    manifest = journey.case.identity_manifest
    assert manifest is not None
    expected_domain_ids = frozenset(
        binding.value
        for binding in manifest.bindings
        if binding.domain_kind is not None
    )
    assert _result_domain_ids(first.engine_result) == expected_domain_ids
    assert _result_domain_ids(second.engine_result) == expected_domain_ids
    assert (
        first_evidence.manifest.manifest_hash
        != second_evidence.manifest.manifest_hash
    )
    assert first_evidence.relative_directory != second_evidence.relative_directory
    writer = AttemptEvidenceWriter(root=tmp_path)
    assert writer.verify(first_evidence).finalized == first_evidence
    assert writer.verify(second_evidence).finalized == second_evidence
    first_paths = {
        f"{first_evidence.relative_directory}/{entry.relative_path}"
        for entry in first_evidence.manifest.artifacts
    }
    second_paths = {
        f"{second_evidence.relative_directory}/{entry.relative_path}"
        for entry in second_evidence.manifest.artifacts
    }
    assert first_paths.isdisjoint(second_paths)
    assert journey.attempt_bytes_before == journey.attempt_bytes_after
    assert journey.input_hashes_before == journey.input_hashes_after
    assert finalized.result.outcome is BacktestRunOutcome.COMPLETED
    assert finalized.result.result_grade is ResultGrade.DEVELOPMENT
    assert (
        finalized.result.canonical_attempt_ref.attempt.attempt_id
        == first.attempt.attempt_id
    )
    assert not finalized.result.deployment_authorized
    assert finalized.result.canonical_attempt_ref == finalized.canonical_attempt_ref
    assert finalized.result.integrity_report == finalized.integrity_report
    assert (
        finalized.canonical_attempt_ref.evidence_manifest_hash
        == first.evidence_manifest_hash
    )
    assert (
        finalized.canonical_attempt_ref.execution_result_hash
        == first.execution_result_hash
    )
    assert {
        entry.relative_path for entry in finalized.manifest.artifacts
    } == {
        "canonical-attempt-ref.json",
        "integrity.json",
        "result.json",
    }
    assert {issue.code for issue in finalized.integrity_report.limitations} >= {
        IntegrityIssueCode.DEVELOPMENT_PROFILE,
        IntegrityIssueCode.ENVIRONMENT_LIMITATION,
        IntegrityIssueCode.SUMMARY_TRACE,
        IntegrityIssueCode.BUNDLE_RETENTION_UNPROVEN,
        IntegrityIssueCode.DETERMINISTIC_REBUILD_UNPROVEN,
    }


def test_closed_semantic_run_returns_verified_cache_without_rerunning_engine(
    tmp_path: Path,
) -> None:
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    engine = RecordingEngine(outcome=DeterministicBarEngine().run(journey.case))
    run_directory = (
        tmp_path / "runs" / journey.attempts.resolved_request.semantic_run_id
    )
    before = _tree_bytes(run_directory)
    third_attempt = AttemptIdentity.retry(
        journey.attempts.canonical_attempt.attempt,
        next_ordinal=3,
    )

    record = AuditableBacktestRunner(
        engine=engine,
        publication_root=tmp_path,
    ).execute(
        resolved_request=journey.attempts.resolved_request,
        execution_case=journey.case,
        attempt=third_attempt,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.cache_hit is not None
    assert record.cache_hit.result_hash == finalized.result.result_hash
    assert (
        record.cache_hit.execution_result_hash
        == finalized.result.execution_result_hash
    )
    assert (
        record.cache_hit.canonical_attempt
        == journey.attempts.canonical_attempt.attempt
    )
    assert not record.cache_hit.deployment_authorized
    assert engine.calls == []
    assert _tree_bytes(run_directory) == before
    assert not (
        run_directory / "attempts" / third_attempt.attempt_id
    ).exists()


def test_execution_hash_mismatch_publishes_failed_evaluation_without_winner(
    tmp_path: Path,
) -> None:
    journey = mismatch_journey(tmp_path)
    first, second = journey.attempts.attempt_hashes
    evaluation = journey.publication.finalized_evaluation

    assert first.execution_result_hash != second.execution_result_hash
    assert journey.publication.finalized_result is None
    assert journey.publication.failure is None
    assert evaluation is not None
    assert evaluation.record.outcome is BacktestRunOutcome.FAILED
    assert {issue.code for issue in evaluation.report.blocking_issues} == {
        IntegrityIssueCode.EXECUTION_HASH_MISMATCH
    }
    assert evaluation.report.canonical_attempt_ref is None
    assert not journey.canonical_directory.exists()
    assert journey.evaluation_directory.is_dir()
    assert journey.attempt_bytes_before == journey.attempt_bytes_after
    assert journey.input_hashes_before == journey.input_hashes_after
