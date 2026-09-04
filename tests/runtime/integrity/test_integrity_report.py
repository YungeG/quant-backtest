from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

import crypto_quant_backtest._publication as publication_helpers
from crypto_quant_domain import ArtifactEnvelope, canonical_bytes, canonical_sha256
from crypto_quant_backtest import (
    AttemptConsistencySet,
    AttemptEvidenceWriter,
    AttemptIdentity,
    AuditableBacktestRunner,
    BacktestRunOutcome,
    CanonicalExecutionSummary,
    CanonicalPublicationFailureCode,
    CanonicalResultPublisher,
    CompletedBacktestResult,
    DeterministicBarEngine,
    EvidenceWriteFailureCode,
    ExecutionResultHasher,
    IntegrityEvaluationContext,
    IntegrityEvaluationRecord,
    IntegrityEvaluator,
    IntegrityIssueCode,
    IntegrityIssueSeverity,
    IntegrityTraceLevel,
    ResultGrade,
)
from tests.runtime.execution_hash._fixtures import ready_record
from tests.runtime.runner._fixtures import RecordingEngine, execution_case
from tests.runtime.integrity._fixtures import (
    decision_grade_attempts,
    editable_build_attempts,
    mismatched_attempts,
    one_attempt,
    rebuild_evidence,
    two_attempts,
)


def _directory_bytes(directory: Path) -> dict[str, bytes]:
    try:
        return {
            path.name: path.read_bytes()
            for path in sorted(directory.iterdir())
        }
    except OSError as error:
        pytest.fail(f"cannot read publication directory: {error}")


def _json_object(path: Path) -> dict[str, Any]:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid JSON artifact: {error}")
    assert isinstance(decoded, dict)
    return decoded


def _canonical_object(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        pytest.fail(f"invalid canonical JSON: {error}")


def _artifact_payload(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_bytes())
        payload = decoded["payload"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        pytest.fail(f"invalid canonical artifact: {error}")
    assert isinstance(payload, dict)
    return payload


def test_equal_attempt_ordinals_use_attempt_id_tie_break(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    parent_attempt_id = "attempt_" + "a" * 64
    alternate_attempt = AttemptIdentity(
        semantic_run_id=attempts.semantic_run_id,
        ordinal=2,
        parent_attempt_id=parent_attempt_id,
        attempt_id=(
            "attempt_"
            + canonical_sha256(
                {
                    "type": "attempt_identity_v1",
                    "semantic_run_id": attempts.semantic_run_id,
                    "ordinal": 2,
                    "parent_attempt_id": parent_attempt_id,
                }
            ).removeprefix("sha256:")
        ),
    )
    alternate_manifest = replace(
        finalized[0].manifest,
        attempt_id=alternate_attempt.attempt_id,
    )
    alternate_finalized = replace(
        finalized[0],
        attempt=alternate_attempt,
        manifest=alternate_manifest,
        manifest_source_hash="sha256:" + "a" * 64,
        relative_directory=(
            f"runs/{attempts.semantic_run_id}/attempts/"
            f"{alternate_attempt.attempt_id}"
        ),
    )
    alternate_hash = replace(
        hashes[0],
        attempt=alternate_attempt,
        evidence_manifest_hash=alternate_manifest.manifest_hash,
    )
    values = (alternate_hash, hashes[1])
    evidence = (alternate_finalized, finalized[1])

    first = AttemptConsistencySet(attempts.resolved_request, values, evidence)
    second = AttemptConsistencySet(
        attempts.resolved_request,
        tuple(reversed(values)),
        tuple(reversed(evidence)),
    )

    expected = min(value.attempt.attempt_id for value in values)
    assert first.canonical_attempt.attempt.attempt_id == expected
    assert second == first


def test_development_integrity_preserves_limitations_without_blocking(
    tmp_path: Path,
) -> None:
    attempts, hashes, _ = two_attempts(tmp_path)
    context = IntegrityEvaluationContext(
        resolved_request=attempts.resolved_request,
        attempts=attempts,
        execution_hash_check=ExecutionResultHasher.check_same_semantic_run(hashes),
        rebuild_evidence=rebuild_evidence(attempts),
    )

    report = IntegrityEvaluator().evaluate(context)

    assert report.result_grade is ResultGrade.DEVELOPMENT
    assert report.context == context
    assert not report.blocking_issues
    assert {issue.code for issue in report.limitations} >= {
        IntegrityIssueCode.DEVELOPMENT_PROFILE,
        IntegrityIssueCode.ENVIRONMENT_LIMITATION,
        IntegrityIssueCode.SUMMARY_TRACE,
        IntegrityIssueCode.BUNDLE_RETENTION_UNPROVEN,
        IntegrityIssueCode.DETERMINISTIC_REBUILD_UNPROVEN,
    }
    assert all(
        issue.severity is IntegrityIssueSeverity.LIMITATION
        for issue in report.limitations
    )
    assert report.canonical_attempt_ref is not None
    assert not report.deployment_authorized


def test_decision_grade_requires_full_trace_retention_and_rebuild_proofs(
    tmp_path: Path,
) -> None:
    attempts = decision_grade_attempts(tmp_path)
    rebuild = rebuild_evidence(
        attempts,
        trace_level=IntegrityTraceLevel.FULL_TRACE,
        bundle_retained=True,
        deterministic_rebuild=True,
    )
    context = IntegrityEvaluationContext(
        resolved_request=attempts.resolved_request,
        attempts=attempts,
        execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
            attempts.attempt_hashes
        ),
        rebuild_evidence=rebuild,
    )

    report = IntegrityEvaluator().evaluate(context)

    assert report.result_grade is ResultGrade.DECISION_GRADE
    assert not report.issues
    assert report.canonical_attempt_ref is not None
    assert (
        report.canonical_attempt_ref.deterministic_rebuild_evidence_hash
        == rebuild.evidence_hash
    )
    assert report.canonical_attempt_ref.trace_level is IntegrityTraceLevel.FULL_TRACE
    assert (
        report.canonical_attempt_ref.market_bundle_retention_proof_hash
        == rebuild.market_bundle_retention_proof_hash
    )

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=rebuild,
    )
    assert outcome.finalized_result is not None
    assert outcome.finalized_result.result.result_grade is ResultGrade.DECISION_GRADE


def test_decision_grade_accepts_microstructure_trace(
    tmp_path: Path,
) -> None:
    attempts = decision_grade_attempts(tmp_path)
    report = IntegrityEvaluator().evaluate(
        IntegrityEvaluationContext(
            resolved_request=attempts.resolved_request,
            attempts=attempts,
            execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
                attempts.attempt_hashes
            ),
            rebuild_evidence=rebuild_evidence(
                attempts,
                trace_level=IntegrityTraceLevel.MICROSTRUCTURE_TRACE,
                bundle_retained=True,
                deterministic_rebuild=True,
            ),
        )
    )

    assert report.result_grade is ResultGrade.DECISION_GRADE
    assert not report.issues


def test_decision_grade_deficits_are_blocking_not_hidden_limitations(
    tmp_path: Path,
) -> None:
    attempts = decision_grade_attempts(tmp_path)
    context = IntegrityEvaluationContext(
        resolved_request=attempts.resolved_request,
        attempts=attempts,
        execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
            attempts.attempt_hashes
        ),
        rebuild_evidence=rebuild_evidence(attempts),
    )

    report = IntegrityEvaluator().evaluate(context)

    assert report.result_grade is None
    assert report.canonical_attempt_ref is None
    assert {issue.code for issue in report.blocking_issues} == {
        IntegrityIssueCode.SUMMARY_TRACE,
        IntegrityIssueCode.BUNDLE_RETENTION_UNPROVEN,
        IntegrityIssueCode.DETERMINISTIC_REBUILD_UNPROVEN,
    }
    assert not report.limitations

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert outcome.finalized_evaluation is not None
    assert outcome.finalized_evaluation.record.outcome is BacktestRunOutcome.BLOCKED
    assert outcome.finalized_result is None


def test_development_editable_build_limitation_is_preserved(
    tmp_path: Path,
) -> None:
    attempts = editable_build_attempts(tmp_path)
    report = IntegrityEvaluator().evaluate(
        IntegrityEvaluationContext(
            resolved_request=attempts.resolved_request,
            attempts=attempts,
            execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
                attempts.attempt_hashes
            ),
            rebuild_evidence=rebuild_evidence(attempts),
        )
    )

    build_issue = next(
        issue
        for issue in report.limitations
        if issue.code is IntegrityIssueCode.DEVELOPMENT_BUILD
    )
    assert build_issue.severity is IntegrityIssueSeverity.LIMITATION
    assert any(
        subject.startswith("editable_build_artifact:")
        for subject in build_issue.subject_keys
    )


def test_fewer_than_two_attempts_is_blocking_and_has_no_canonical_ref(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    single = AttemptConsistencySet(
        attempts.resolved_request,
        hashes[:1],
        finalized[:1],
    )
    context = IntegrityEvaluationContext(
        resolved_request=single.resolved_request,
        attempts=single,
        execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
            single.attempt_hashes
        ),
        rebuild_evidence=rebuild_evidence(single),
    )

    report = IntegrityEvaluator().evaluate(context)

    assert report.result_grade is None
    assert report.canonical_attempt_ref is None
    assert {issue.code for issue in report.blocking_issues} == {
        IntegrityIssueCode.INSUFFICIENT_ATTEMPTS
    }

    complete_attempts, complete_hashes, _ = two_attempts(tmp_path / "complete")
    complete_report = IntegrityEvaluator().evaluate(
        IntegrityEvaluationContext(
            resolved_request=complete_attempts.resolved_request,
            attempts=complete_attempts,
            execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
                complete_hashes
            ),
            rebuild_evidence=rebuild_evidence(complete_attempts),
        )
    )
    assert complete_report.canonical_attempt_ref is not None
    with pytest.raises(ValueError, match="blocking Integrity"):
        CompletedBacktestResult(
            context=report.context,
            canonical_attempt_ref=complete_report.canonical_attempt_ref,
            integrity_report=report,
        )


def test_execution_hash_mismatch_is_blocking_and_cannot_select_attempt(
    tmp_path: Path,
) -> None:
    attempts = mismatched_attempts(tmp_path)
    context = IntegrityEvaluationContext(
        resolved_request=attempts.resolved_request,
        attempts=attempts,
        execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
            attempts.attempt_hashes
        ),
        rebuild_evidence=rebuild_evidence(attempts),
    )

    report = IntegrityEvaluator().evaluate(context)

    assert report.result_grade is None
    assert report.canonical_attempt_ref is None
    assert IntegrityIssueCode.EXECUTION_HASH_MISMATCH in {
        issue.code for issue in report.blocking_issues
    }


def test_two_consistent_attempts_publish_atomic_completed_result(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    attempt_directories = tuple(
        tmp_path / value.relative_directory for value in finalized
    )
    attempt_bytes = tuple(
        _directory_bytes(value) for value in attempt_directories
    )

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=tuple(reversed(hashes)),
        finalized_attempts=tuple(reversed(finalized)),
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.finalized_result is not None
    assert outcome.finalized_evaluation is None
    assert outcome.failure is None
    publication = outcome.finalized_result
    assert publication.result.result_grade is ResultGrade.DEVELOPMENT
    assert not publication.result.deployment_authorized
    assert publication.canonical_attempt_ref.attempt.ordinal == 1
    canonical = (
        tmp_path
        / "runs"
        / attempts.semantic_run_id
        / "canonical"
    )
    assert {path.name for path in canonical.iterdir()} == {
        "canonical-attempt-ref.json",
        "integrity.json",
        "result.json",
        "publication-manifest.json",
    }
    assert not (
        tmp_path / "runs" / attempts.semantic_run_id / "integrity-evaluations"
    ).exists()
    assert tuple(_directory_bytes(value) for value in attempt_directories) == attempt_bytes
    assert canonical.stat().st_mode & 0o222 == 0
    assert all(path.stat().st_mode & 0o222 == 0 for path in canonical.iterdir())


def test_completed_result_rejects_context_not_bound_by_integrity_report(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    published = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert published.finalized_result is not None
    result = published.finalized_result.result
    changed_context = replace(
        result.context,
        rebuild_evidence=replace(
            result.context.rebuild_evidence,
            trace_level=IntegrityTraceLevel.FULL_TRACE,
        ),
    )

    with pytest.raises(ValueError, match="does not bind Result context"):
        replace(result, context=changed_context)


def test_insufficient_attempts_publish_durable_blocked_evaluation_only(
    tmp_path: Path,
) -> None:
    attempts = one_attempt(tmp_path)

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.finalized_result is None
    assert outcome.finalized_evaluation is not None
    assert outcome.failure is None
    evaluation = outcome.finalized_evaluation
    assert evaluation.record.outcome is BacktestRunOutcome.BLOCKED
    directory = tmp_path / evaluation.relative_directory
    assert {path.name for path in directory.iterdir()} == {
        "integrity.json",
        "evaluation-outcome.json",
        "publication-manifest.json",
    }
    run_directory = tmp_path / "runs" / attempts.semantic_run_id
    assert not (run_directory / "canonical").exists()
    assert not (directory / "result.json").exists()
    assert not (directory / "canonical-attempt-ref.json").exists()


@pytest.mark.parametrize(
    "attempt_factory",
    (one_attempt, mismatched_attempts),
)
def test_integrity_evaluation_is_never_overwritten(
    tmp_path: Path,
    attempt_factory,
) -> None:
    attempts = attempt_factory(tmp_path)
    publisher = CanonicalResultPublisher(root=tmp_path)
    arguments = {
        "resolved_request": attempts.resolved_request,
        "attempt_hashes": attempts.attempt_hashes,
        "finalized_attempts": attempts.finalized_attempts,
        "rebuild_evidence": rebuild_evidence(attempts),
    }
    first = publisher.publish(**arguments)
    assert first.finalized_evaluation is not None
    directory = tmp_path / first.finalized_evaluation.relative_directory
    before = _directory_bytes(directory)

    second = publisher.publish(**arguments)

    assert second.failure is not None
    assert second.failure.code is CanonicalPublicationFailureCode.FINAL_DESTINATION_EXISTS
    assert _directory_bytes(directory) == before


def test_preexisting_evaluation_symlink_is_never_overwritten(
    tmp_path: Path,
) -> None:
    attempts = one_attempt(tmp_path)
    context = IntegrityEvaluationContext(
        resolved_request=attempts.resolved_request,
        attempts=attempts,
        execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
            attempts.attempt_hashes
        ),
        rebuild_evidence=rebuild_evidence(attempts),
    )
    report = IntegrityEvaluator().evaluate(context)
    record = IntegrityEvaluationRecord(report, BacktestRunOutcome.BLOCKED)
    parent = (
        tmp_path
        / "runs"
        / attempts.semantic_run_id
        / "integrity-evaluations"
    )
    parent.mkdir(parents=True)
    destination = parent / record.evaluation_id
    destination.symlink_to(tmp_path / "symlink-target", target_is_directory=True)

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.FINAL_DESTINATION_EXISTS
    assert destination.is_symlink()


def test_existing_canonical_result_is_never_overwritten(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    publisher = CanonicalResultPublisher(root=tmp_path)
    first = publisher.publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert first.finalized_result is not None
    canonical = tmp_path / first.finalized_result.relative_directory
    before = {path.name: path.read_bytes() for path in canonical.iterdir()}

    second = publisher.publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert second.failure is not None
    assert second.failure.code is CanonicalPublicationFailureCode.SEMANTIC_RUN_CLOSED
    assert {path.name: path.read_bytes() for path in canonical.iterdir()} == before


def test_execution_hash_mismatch_publishes_durable_failed_evaluation(
    tmp_path: Path,
) -> None:
    attempts = mismatched_attempts(tmp_path)

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.finalized_result is None
    assert outcome.finalized_evaluation is not None
    assert outcome.failure is None
    evaluation = outcome.finalized_evaluation
    assert evaluation.record.outcome is BacktestRunOutcome.FAILED
    assert IntegrityIssueCode.EXECUTION_HASH_MISMATCH in {
        issue.code for issue in evaluation.report.blocking_issues
    }
    run_directory = tmp_path / "runs" / attempts.semantic_run_id
    assert not (run_directory / "canonical").exists()
    assert not (run_directory / ".publication.lock").exists()


def test_execution_hash_mismatch_publishes_failed_evaluation_for_any_bound_attempt(
    tmp_path: Path,
) -> None:
    attempts = mismatched_attempts(tmp_path)
    second = attempts.attempt_hashes[1]
    second_bound_rebuild = replace(
        rebuild_evidence(attempts),
        execution_case_hash=second.engine_result.case_hash,
        trace_hash=second.engine_result.trace.trace_hash,
        execution_result_hash=second.execution_result_hash,
    )

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=second_bound_rebuild,
    )

    assert outcome.failure is None
    assert outcome.finalized_evaluation is not None
    assert outcome.finalized_evaluation.record.outcome is BacktestRunOutcome.FAILED
    assert IntegrityIssueCode.EXECUTION_HASH_MISMATCH in {
        issue.code for issue in outcome.finalized_evaluation.report.blocking_issues
    }


def test_publisher_rejects_non_exact_eligible_attempt_set_under_lock(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes[:1],
        finalized_attempts=finalized[:1],
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.finalized_result is None
    assert outcome.finalized_evaluation is None
    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.ATTEMPT_SET_MISMATCH
    run_directory = tmp_path / "runs" / attempts.semantic_run_id
    assert not (run_directory / "canonical").exists()
    assert not (run_directory / "integrity-evaluations").exists()


def test_publisher_rebinds_attempt_hash_to_finalized_engine_artifact(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    forged = replace(
        hashes[0],
        engine_result_artifact_content_hash=(
            "sha256:" + "0" * 64
        ),
    )

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=(forged, hashes[1]),
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.ATTEMPT_EVIDENCE_INVALID
    assert outcome.finalized_result is None


def test_publisher_rejects_attempt_engine_result_not_bound_to_disk_evidence(
    tmp_path: Path,
) -> None:
    attempts = mismatched_attempts(tmp_path)
    first, second = attempts.attempt_hashes
    forged = replace(
        first,
        engine_result=second.engine_result,
        summary=CanonicalExecutionSummary.from_result(second.engine_result),
    )

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=(forged, second),
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=replace(
            rebuild_evidence(attempts),
            execution_case_hash=second.engine_result.case_hash,
            trace_hash=second.engine_result.trace.trace_hash,
            execution_result_hash=second.execution_result_hash,
        ),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.ATTEMPT_EVIDENCE_INVALID
    assert outcome.finalized_result is None


def test_publisher_rejects_writable_finalized_attempt_evidence(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    writable = tmp_path / finalized[0].relative_directory / "request.json"
    writable.chmod(0o644)

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.ATTEMPT_EVIDENCE_INVALID


def test_publisher_rejects_tampered_finalized_attempt_evidence(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    first_directory = tmp_path / finalized[0].relative_directory
    request_path = first_directory / "request.json"
    request_path.chmod(0o644)
    request_path.write_bytes(request_path.read_bytes() + b"\n")

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.ATTEMPT_EVIDENCE_INVALID
    run_directory = tmp_path / "runs" / attempts.semantic_run_id
    assert not (run_directory / "canonical").exists()
    assert not (run_directory / "integrity-evaluations").exists()


def test_canonical_publication_closes_run_before_runner_invokes_engine(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    published = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert published.finalized_result is not None
    recording = RecordingEngine(
        outcome=DeterministicBarEngine().run(execution_case())
    )
    third_attempt = AttemptIdentity.retry(
        finalized[1].attempt,
        next_ordinal=3,
    )

    record = AuditableBacktestRunner(
        engine=recording,
        publication_root=tmp_path,
    ).execute(
        resolved_request=attempts.resolved_request,
        execution_case=execution_case(),
        attempt=third_attempt,
        input_origin=ready_record().input_origin,
    )

    assert record.cache_hit is not None
    assert record.cache_hit.outcome is BacktestRunOutcome.COMPLETED
    assert (
        record.cache_hit.canonical_attempt.attempt_id
        == published.finalized_result.canonical_attempt_ref.attempt.attempt_id
    )
    assert recording.calls == []


def test_runner_rejects_invalid_canonical_cache_without_engine(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    published = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert published.finalized_result is not None
    canonical = tmp_path / published.finalized_result.relative_directory
    result_path = canonical / "result.json"
    canonical.chmod(0o755)
    result_path.chmod(0o644)
    result_path.write_bytes(b"{}")
    result_path.chmod(0o444)
    canonical.chmod(0o555)
    recording = RecordingEngine(
        outcome=DeterministicBarEngine().run(execution_case())
    )

    record = AuditableBacktestRunner(
        engine=recording,
        publication_root=tmp_path,
    ).execute(
        resolved_request=attempts.resolved_request,
        execution_case=execution_case(),
        attempt=AttemptIdentity.retry(finalized[1].attempt, next_ordinal=3),
        input_origin=ready_record().input_origin,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "canonical_cache_invalid"
    assert recording.calls == []


def test_runner_rejects_duplicate_canonical_manifest_paths_without_engine(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    published = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert published.finalized_result is not None
    canonical = tmp_path / published.finalized_result.relative_directory
    manifest_path = canonical / "publication-manifest.json"
    canonical.chmod(0o755)
    manifest_path.chmod(0o644)
    manifest_source = _json_object(manifest_path)
    manifest_payload = manifest_source["payload"]
    manifest_payload["artifacts"].append(
        dict(manifest_payload["artifacts"][0])
    )
    manifest_path.write_bytes(
        canonical_bytes(
            ArtifactEnvelope.create(
                "canonical_publication_manifest", 1, manifest_payload
            )
        )
    )
    manifest_path.chmod(0o444)
    canonical.chmod(0o555)
    recording = RecordingEngine(
        outcome=DeterministicBarEngine().run(execution_case())
    )

    record = AuditableBacktestRunner(
        engine=recording,
        publication_root=tmp_path,
    ).execute(
        resolved_request=attempts.resolved_request,
        execution_case=execution_case(),
        attempt=AttemptIdentity.retry(finalized[1].attempt, next_ordinal=3),
        input_origin=ready_record().input_origin,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "canonical_cache_invalid"
    assert recording.calls == []


def test_runner_rejects_cache_grade_escalation_without_engine(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    published = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert published.finalized_result is not None
    canonical = tmp_path / published.finalized_result.relative_directory
    integrity_path = canonical / "integrity.json"
    result_path = canonical / "result.json"
    manifest_path = canonical / "publication-manifest.json"
    canonical.chmod(0o755)
    integrity_path.chmod(0o644)
    result_path.chmod(0o644)
    manifest_path.chmod(0o644)

    integrity_source = _json_object(integrity_path)
    integrity_payload = integrity_source["payload"]
    integrity_payload["requested_grade"] = "decision_grade"
    integrity_payload["result_grade"] = "decision_grade"
    integrity_envelope = ArtifactEnvelope.create(
        "integrity_report", 1, integrity_payload
    )
    integrity_bytes = canonical_bytes(integrity_envelope)
    integrity_path.write_bytes(integrity_bytes)

    result_source = _json_object(result_path)
    result_payload = result_source["payload"]
    result_payload["result_grade"] = "decision_grade"
    result_payload["integrity_report_hash"] = canonical_sha256(
        integrity_payload
    )
    result_envelope = ArtifactEnvelope.create(
        "completed_backtest_result", 1, result_payload
    )
    result_bytes = canonical_bytes(result_envelope)
    result_path.write_bytes(result_bytes)

    manifest_source = _json_object(manifest_path)
    manifest_payload = manifest_source["payload"]
    rewritten = {
        "integrity.json": (integrity_envelope, integrity_bytes),
        "result.json": (result_envelope, result_bytes),
    }
    for entry in manifest_payload["artifacts"]:
        replacement = rewritten.get(entry["relative_path"])
        if replacement is None:
            continue
        envelope, source_bytes = replacement
        entry["content_hash"] = envelope.content_hash
        entry["source_hash"] = (
            f"sha256:{hashlib.sha256(source_bytes).hexdigest()}"
        )
        entry["byte_count"] = len(source_bytes)
    manifest_path.write_bytes(
        canonical_bytes(
            ArtifactEnvelope.create(
                "canonical_publication_manifest", 1, manifest_payload
            )
        )
    )
    integrity_path.chmod(0o444)
    result_path.chmod(0o444)
    manifest_path.chmod(0o444)
    canonical.chmod(0o555)
    recording = RecordingEngine(
        outcome=DeterministicBarEngine().run(execution_case())
    )

    record = AuditableBacktestRunner(
        engine=recording,
        publication_root=tmp_path,
    ).execute(
        resolved_request=attempts.resolved_request,
        execution_case=execution_case(),
        attempt=AttemptIdentity.retry(finalized[1].attempt, next_ordinal=3),
        input_origin=ready_record().input_origin,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "canonical_cache_invalid"
    assert recording.calls == []


def test_runner_without_publication_root_fails_closed_before_engine(
    tmp_path: Path,
) -> None:
    attempts, hashes, _ = two_attempts(tmp_path)
    recording = RecordingEngine(
        outcome=DeterministicBarEngine().run(execution_case())
    )

    record = AuditableBacktestRunner(engine=recording).execute(
        resolved_request=attempts.resolved_request,
        execution_case=execution_case(),
        attempt=AttemptIdentity.retry(
            hashes[-1].attempt,
            next_ordinal=3,
        ),
        input_origin=ready_record().input_origin,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "publication_root_required"
    assert recording.calls == []


def test_canonical_publication_closes_run_to_new_attempt_evidence(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    published = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert published.finalized_result is not None
    third = ready_record(ordinal=3)

    outcome = AttemptEvidenceWriter(root=tmp_path).publish(third)

    assert outcome.finalized is None
    assert outcome.failure is not None
    assert outcome.failure.code is EvidenceWriteFailureCode.SEMANTIC_RUN_CLOSED
    assert not (
        tmp_path
        / "runs"
        / attempts.semantic_run_id
        / "attempts"
        / third.attempt.attempt_id
    ).exists()


@pytest.mark.parametrize(
    "filesystem_model",
    ("shared_adversarial", "nfs", "object_store", "trusted-local", ""),
)
def test_shared_or_adversarial_filesystem_model_is_rejected(
    filesystem_model: str,
) -> None:
    with pytest.raises(ValueError, match="trusted cooperative single-writer"):
        CanonicalResultPublisher(
            root=Path("publication-root"),
            filesystem_model=filesystem_model,
        )


def test_attempt_writer_cannot_enter_publisher_critical_section(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    third = ready_record(ordinal=3)

    with publication_helpers.RunPublicationLock(
        root=tmp_path,
        semantic_run_id=attempts.semantic_run_id,
    ):
        blocked = AttemptEvidenceWriter(root=tmp_path).publish(third)

    assert blocked.failure is not None
    assert blocked.failure.code is EvidenceWriteFailureCode.RUN_LOCK_UNAVAILABLE
    published = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert published.finalized_result is not None


def test_existing_run_lock_is_never_broken_by_wall_clock_age(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    lock = (
        tmp_path
        / "runs"
        / attempts.semantic_run_id
        / ".publication.lock"
    )
    lock.write_text("old-but-authoritative-lock\n", encoding="utf-8")
    os.utime(lock, (1, 1))

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.RUN_LOCK_UNAVAILABLE
    assert lock.read_text(encoding="utf-8") == "old-but-authoritative-lock\n"
    assert not (lock.parent / "canonical").exists()


def test_canonical_write_failure_leaves_no_visible_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    original = CanonicalResultPublisher._write_file

    def fail_result(path: Path, source_bytes: bytes) -> None:
        if path.name == "result.json":
            raise OSError("forced result write failure")
        original(path, source_bytes)

    monkeypatch.setattr(
        CanonicalResultPublisher,
        "_write_file",
        staticmethod(fail_result),
    )

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is CanonicalPublicationFailureCode.ARTIFACT_WRITE_FAILED
    run_directory = tmp_path / "runs" / attempts.semantic_run_id
    assert not (run_directory / "canonical").exists()
    assert not (run_directory / ".canonical.staging").exists()


def test_lock_prepare_failure_removes_partial_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)

    def fail_fsync(_descriptor: int) -> None:
        raise OSError("forced lock fsync failure")

    monkeypatch.setattr(publication_helpers.os, "fsync", fail_fsync)
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is not None
    assert not (
        tmp_path
        / "runs"
        / attempts.semantic_run_id
        / ".publication.lock"
    ).exists()


def test_lock_release_failure_does_not_turn_visible_result_into_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    original_unlink = Path.unlink

    def fail_lock_unlink(path: Path, *args, **kwargs) -> None:
        if path.name == ".publication.lock":
            raise OSError("forced lock release failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_lock_unlink)
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.failure is None
    assert outcome.finalized_result is not None
    assert (tmp_path / outcome.finalized_result.relative_directory).is_dir()


def test_publication_files_are_read_only_before_atomic_rename(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    original_rename = Path.rename
    observed_files_read_only = False

    def inspect_rename(source: Path, target: Path) -> Path:
        nonlocal observed_files_read_only
        if source.name == ".canonical.staging":
            observed_files_read_only = all(
                path.stat().st_mode & 0o222 == 0
                for path in source.iterdir()
            )
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", inspect_rename)
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    assert outcome.finalized_result is not None
    assert observed_files_read_only
    directory = tmp_path / outcome.finalized_result.relative_directory
    assert directory.stat().st_mode & 0o222 == 0


def test_post_rename_verification_failure_hides_final_destination(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)

    def fail_final(directory: Path) -> None:
        if directory.name == "canonical":
            raise PermissionError("forced final verification failure")
        publication_helpers.verify_read_only(directory)

    monkeypatch.setattr(
        CanonicalResultPublisher,
        "_verify_read_only",
        staticmethod(fail_final),
    )
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    canonical = tmp_path / "runs" / attempts.semantic_run_id / "canonical"
    assert outcome.failure is not None
    assert not canonical.exists()


def test_failed_primary_rollback_rename_uses_fallback_and_hides_canonical(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    original_replace = publication_helpers.os.replace
    verification_calls = 0

    def fail_first_final_verification(directory: Path) -> None:
        nonlocal verification_calls
        verification_calls += 1
        if directory.name == "canonical" and verification_calls == 1:
            raise PermissionError("forced final verification failure")
        publication_helpers.verify_read_only(directory)

    def fail_rollback_replace(source, target) -> None:
        if Path(source).name == "canonical":
            raise OSError("forced rollback rename failure")
        original_replace(source, target)

    monkeypatch.setattr(
        CanonicalResultPublisher,
        "_verify_read_only",
        staticmethod(fail_first_final_verification),
    )
    monkeypatch.setattr(publication_helpers.os, "replace", fail_rollback_replace)
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    canonical = tmp_path / "runs" / attempts.semantic_run_id / "canonical"
    assert outcome.failure is not None
    assert not canonical.exists()


def test_first_integrity_evaluation_syncs_new_parent_entry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts = one_attempt(tmp_path)
    hashes = attempts.attempt_hashes
    finalized = attempts.finalized_attempts
    synced: list[Path] = []
    original_fsync = publication_helpers.fsync_directory

    def record_fsync(directory: Path) -> None:
        synced.append(directory)
        original_fsync(directory)

    monkeypatch.setattr(
        publication_helpers,
        "fsync_directory",
        record_fsync,
    )
    monkeypatch.setattr(
        CanonicalResultPublisher,
        "_fsync_directory",
        staticmethod(record_fsync),
    )
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    run_directory = tmp_path / "runs" / attempts.semantic_run_id
    assert outcome.finalized_evaluation is not None
    assert run_directory in synced
    assert run_directory / "integrity-evaluations" in synced


def test_parent_fsync_and_partial_rollback_delete_leave_no_visible_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    original_fsync = CanonicalResultPublisher._fsync_directory

    def fail_parent(directory: Path) -> None:
        if directory.name == attempts.semantic_run_id:
            raise OSError("forced parent fsync failure")
        original_fsync(directory)

    monkeypatch.setattr(
        CanonicalResultPublisher,
        "_fsync_directory",
        staticmethod(fail_parent),
    )
    def fail_remove(directory: Path) -> None:
        (directory / "publication-manifest.json").unlink()
        raise OSError("forced partial rollback deletion failure")

    monkeypatch.setattr(publication_helpers.shutil, "rmtree", fail_remove)

    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    canonical = tmp_path / "runs" / attempts.semantic_run_id / "canonical"
    assert outcome.failure is not None
    assert not canonical.exists()


def test_evaluation_parent_fsync_and_partial_rollback_leave_no_visible_evaluation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts = one_attempt(tmp_path)
    original_fsync = CanonicalResultPublisher._fsync_directory

    def fail_parent(directory: Path) -> None:
        if directory.name == "integrity-evaluations":
            raise OSError("forced evaluation parent fsync failure")
        original_fsync(directory)

    def fail_remove(directory: Path) -> None:
        (directory / "publication-manifest.json").unlink()
        raise OSError("forced partial rollback deletion failure")

    monkeypatch.setattr(
        CanonicalResultPublisher,
        "_fsync_directory",
        staticmethod(fail_parent),
    )
    monkeypatch.setattr(publication_helpers.shutil, "rmtree", fail_remove)
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=rebuild_evidence(attempts),
    )

    evaluations = (
        tmp_path
        / "runs"
        / attempts.semantic_run_id
        / "integrity-evaluations"
    )
    assert outcome.failure is not None
    assert all(path.name.startswith(".") for path in evaluations.iterdir())


def test_canonical_publication_hash_dag_is_acyclic_and_exact_covered(
    tmp_path: Path,
) -> None:
    attempts, hashes, finalized = two_attempts(tmp_path)
    outcome = CanonicalResultPublisher(root=tmp_path).publish(
        resolved_request=attempts.resolved_request,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert outcome.finalized_result is not None
    publication = outcome.finalized_result
    directory = tmp_path / publication.relative_directory

    attempt_ref = _artifact_payload(directory / "canonical-attempt-ref.json")
    integrity = _artifact_payload(directory / "integrity.json")
    result = _artifact_payload(directory / "result.json")
    manifest = _artifact_payload(directory / "publication-manifest.json")

    assert attempt_ref["engine_result_artifact_content_hash"] == (
        publication.canonical_attempt_ref.engine_result_artifact_content_hash
    )
    assert "integrity_report_hash" not in attempt_ref
    assert "result_hash" not in attempt_ref
    assert "publication_manifest_hash" not in attempt_ref
    assert integrity["canonical_attempt_ref_hash"] == publication.canonical_attempt_ref.reference_hash
    context = integrity["context"]
    assert isinstance(context, dict)
    assert context["attempt_consistency_set"] == _canonical_object(
        publication.integrity_report.context.attempts
    )
    assert context["execution_hash_check"] == _canonical_object(
        publication.integrity_report.context.execution_hash_check
    )
    assert context["rebuild_evidence"] == _canonical_object(
        publication.integrity_report.context.rebuild_evidence
    )
    assert "result_hash" not in integrity
    assert "publication_manifest_hash" not in integrity
    assert result["canonical_attempt_ref_hash"] == publication.canonical_attempt_ref.reference_hash
    assert result["integrity_report_hash"] == publication.integrity_report.report_hash
    assert result["attempt_id"] == publication.canonical_attempt_ref.attempt.attempt_id
    assert result["evidence_manifest_hash"] == (
        publication.canonical_attempt_ref.evidence_manifest_hash
    )
    assert result["integrity"] == {
        "blocking": [],
        "limitations": _canonical_object(
            publication.integrity_report.limitations
        ),
    }
    assert "publication_manifest_hash" not in result
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    assert all(isinstance(entry, dict) for entry in artifacts)
    entries = cast(list[dict[str, object]], artifacts)
    assert {entry["relative_path"] for entry in entries} == {
        "canonical-attempt-ref.json",
        "integrity.json",
        "result.json",
    }

    first_entry = publication.manifest.artifacts[0]
    forged_manifest = replace(
        publication.manifest,
        artifacts=(
            replace(first_entry, source_hash="sha256:" + "cd" * 32),
            *publication.manifest.artifacts[1:],
        ),
    )
    with pytest.raises(ValueError, match="source hashes do not bind"):
        replace(publication, manifest=forged_manifest)


def test_rebuild_evidence_must_exact_bind_attempt_trace_and_execution(
    tmp_path: Path,
) -> None:
    attempts, hashes, _ = two_attempts(tmp_path)
    rebuild = rebuild_evidence(attempts)
    changed = replace(
        rebuild,
        trace_hash="sha256:" + "ab" * 32,
    )

    with pytest.raises(ValueError, match="execution binding mismatch"):
        IntegrityEvaluationContext(
            resolved_request=attempts.resolved_request,
            attempts=attempts,
            execution_hash_check=ExecutionResultHasher.check_same_semantic_run(
                hashes
            ),
            rebuild_evidence=changed,
        )
