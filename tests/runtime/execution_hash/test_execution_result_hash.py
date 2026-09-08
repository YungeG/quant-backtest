from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    AttemptEvidenceWriter,
    CanonicalExecutionSummary,
    ExecutionHashEvidenceError,
    ExecutionHashEvidenceErrorCode,
    ExecutionHashMismatch,
    ExecutionResultHasher,
    ExecutionTrace,
)
from crypto_quant_domain import ArtifactEnvelope, canonical_sha256
from tests.runtime.evidence._fixtures import attempt_record
from tests.runtime.execution_hash._fixtures import publish_ready, ready_branch


def _changed_result(record):
    ready = ready_branch(record)
    result = ready.engine_result
    first_entry = result.trace.entries[0]
    changed_entry = replace(
        first_entry,
        evidence_hash=canonical_sha256({"changed": "authoritative_trace"}),
    )
    return replace(
        result,
        trace=ExecutionTrace((changed_entry, *result.trace.entries[1:])),
    )


def test_summary_exactly_covers_authoritative_engine_result() -> None:
    record = attempt_record("ready")
    result = ready_branch(record).engine_result

    summary = CanonicalExecutionSummary.from_result(result)

    assert summary.trace is result.trace
    assert summary.decision_batches is result.decision_batches
    assert summary.allocations is result.allocations
    assert summary.approved_targets is result.approved_targets
    assert summary.normalized_targets is result.normalized_targets
    assert summary.order_plans is result.order_plans
    assert summary.order_streams is result.order_streams
    assert summary.fills is result.fills
    assert summary.slippage_decisions is result.slippage_decisions
    assert summary.fee_assessments is result.fee_assessments
    assert summary.final_journal is result.final_journal
    assert summary.final_ledger_state is result.final_ledger_state
    assert summary.final_portfolio_snapshot is result.final_portfolio_snapshot
    assert summary.run_end_report is result.run_end_report
    encoded = summary.to_canonical_dict()
    assert "attempt" not in str(encoded)
    assert "evidence_manifest" not in str(encoded)
    assert "metrics" not in str(encoded)


def test_attempt_and_evidence_location_do_not_change_execution_hash(tmp_path) -> None:
    first_record, first_publication = publish_ready(tmp_path / "first", ordinal=1)
    second_record, second_publication = publish_ready(tmp_path / "second", ordinal=2)
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None

    hasher = ExecutionResultHasher()
    first = hasher.bind(
        ready_branch(first_record), first_publication.finalized
    )
    second = hasher.bind(
        ready_branch(second_record), second_publication.finalized
    )

    assert first.attempt != second.attempt
    assert first.evidence_manifest_hash != second.evidence_manifest_hash
    assert first.execution_result_hash == second.execution_result_hash
    assert first.summary == second.summary
    assert first.engine_result is ready_branch(first_record).engine_result
    assert second.engine_result is ready_branch(second_record).engine_result

    check = hasher.check_same_semantic_run((second, first))
    assert check.consistency is not None
    assert check.mismatch is None
    assert check.consistency.execution_result_hash == first.execution_result_hash
    assert tuple(ref.attempt_id for ref in check.consistency.attempts) == tuple(
        sorted((first.attempt.attempt_id, second.attempt.attempt_id))
    )
    assert hasher.check_same_semantic_run((first, second)) == check


def test_authoritative_trace_change_changes_hash_and_fails_same_run_check(
    tmp_path,
) -> None:
    first_record, first_publication = publish_ready(tmp_path / "first", ordinal=1)
    changed_result = _changed_result(first_record)
    changed_record, changed_publication = publish_ready(
        tmp_path / "changed", ordinal=2, result=changed_result
    )
    assert first_publication.finalized is not None
    assert changed_publication.finalized is not None

    hasher = ExecutionResultHasher()
    first = hasher.bind(ready_branch(first_record), first_publication.finalized)
    changed = hasher.bind(
        ready_branch(changed_record), changed_publication.finalized
    )

    assert first.execution_result_hash != changed.execution_result_hash
    check = hasher.check_same_semantic_run((changed, first))
    assert check.consistency is None
    assert isinstance(check.mismatch, ExecutionHashMismatch)
    assert len({ref.execution_result_hash for ref in check.mismatch.attempts}) == 2
    assert hasher.check_same_semantic_run((first, changed)) == check


def test_bind_rejects_non_ready_or_mismatched_evidence(tmp_path) -> None:
    ready_record, ready_publication = publish_ready(tmp_path / "ready", ordinal=1)
    blocked_record = attempt_record("blocked")
    blocked_publication = AttemptEvidenceWriter(root=tmp_path / "blocked").publish(
        blocked_record
    )
    second_record, second_publication = publish_ready(tmp_path / "second", ordinal=2)
    assert ready_publication.finalized is not None
    assert blocked_publication.finalized is not None
    assert second_publication.finalized is not None
    hasher = ExecutionResultHasher()

    with pytest.raises(ExecutionHashEvidenceError) as non_ready:
        hasher.bind(ready_branch(ready_record), blocked_publication.finalized)
    assert non_ready.value.code is ExecutionHashEvidenceErrorCode.EVIDENCE_NOT_READY

    with pytest.raises(ExecutionHashEvidenceError) as mismatch:
        hasher.bind(ready_branch(ready_record), second_publication.finalized)
    assert mismatch.value.code is ExecutionHashEvidenceErrorCode.ATTEMPT_MISMATCH


def test_bind_rejects_engine_result_artifact_tampering(tmp_path) -> None:
    record, publication = publish_ready(tmp_path / "ready")
    assert publication.finalized is not None
    finalized = publication.finalized
    engine_entry = next(
        entry
        for entry in finalized.manifest.artifacts
        if entry.relative_path == "engine-execution-result.json"
    )
    wrong_hash = canonical_sha256({"wrong": "engine_result"})
    tampered_entry = replace(engine_entry, content_hash=wrong_hash)
    tampered_manifest = replace(
        finalized.manifest,
        artifacts=tuple(
            tampered_entry if entry is engine_entry else entry
            for entry in finalized.manifest.artifacts
        ),
    )
    tampered = replace(finalized, manifest=tampered_manifest)

    with pytest.raises(ExecutionHashEvidenceError) as error:
        ExecutionResultHasher().bind(ready_branch(record), tampered)
    assert error.value.code is ExecutionHashEvidenceErrorCode.ENGINE_ARTIFACT_MISMATCH

    expected_content_hash = ArtifactEnvelope.create(
        "engine_execution_result", 1, ready_branch(record).engine_result
    ).content_hash
    assert engine_entry.content_hash == expected_content_hash


def test_same_run_checker_rejects_mixed_semantic_runs(tmp_path) -> None:
    record, publication = publish_ready(tmp_path / "ready")
    assert publication.finalized is not None
    attempt_hash = ExecutionResultHasher().bind(
        ready_branch(record), publication.finalized
    )
    other_ref = replace(
        attempt_hash.to_ref(),
        semantic_run_id="run_" + "0" * 64,
    )

    with pytest.raises(ExecutionHashEvidenceError) as error:
        ExecutionResultHasher().check_same_semantic_run(
            (attempt_hash.to_ref(), other_ref)
        )
    assert error.value.code is ExecutionHashEvidenceErrorCode.SEMANTIC_RUN_MISMATCH
