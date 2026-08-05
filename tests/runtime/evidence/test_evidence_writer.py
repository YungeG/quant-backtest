from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from crypto_quant_backtest import (
    BacktestRunOutcome,
    EvidencePublicationOutcome,
    EvidencePublicationStatus,
    EvidenceWriteFailureCode,
    AttemptEvidenceWriter,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.runtime.evidence._fixtures import attempt_record


COMMON_PATHS = {
    "request.json",
    "environment.json",
    "build-artifact-manifest.json",
    "market-bundle-ref.json",
    "environment-compatibility-report.json",
    "attempt-execution-record.json",
}
BRANCH_PATHS = {
    "ready": "engine-execution-result.json",
    "blocked": "blocked-run-report.json",
    "failed": "failure-report.json",
    "cancelled": "cancellation-report.json",
}
BRANCH_STATUS = {
    "ready": EvidencePublicationStatus.READY_FOR_INTEGRITY,
    "blocked": EvidencePublicationStatus.BLOCKED,
    "failed": EvidencePublicationStatus.FAILED,
    "cancelled": EvidencePublicationStatus.CANCELLED,
}
BRANCH_OUTCOME = {
    "ready": None,
    "blocked": BacktestRunOutcome.BLOCKED,
    "failed": BacktestRunOutcome.FAILED,
    "cancelled": BacktestRunOutcome.CANCELLED,
}


def _final_directory(root: Path, record) -> Path:
    return (
        root
        / "runs"
        / record.attempt.semantic_run_id
        / "attempts"
        / record.attempt.attempt_id
    )


def test_ready_attempt_is_atomically_finalized_without_completed_result(
    tmp_path: Path,
) -> None:
    record = attempt_record("ready")
    writer = AttemptEvidenceWriter(root=tmp_path)

    outcome = writer.publish(record)

    assert outcome.finalized is not None
    assert outcome.failure is None
    finalized = outcome.finalized
    assert finalized.status is EvidencePublicationStatus.READY_FOR_INTEGRITY
    assert finalized.terminal_outcome is None
    assert finalized.deployment_authorized is False
    assert finalized.attempt == record.attempt
    assert finalized.manifest.attempt_record_hash == canonical_sha256(record)

    final_directory = _final_directory(tmp_path, record)
    staging_directory = final_directory.parent / ".staging" / record.attempt.attempt_id
    assert final_directory.is_dir()
    assert not staging_directory.exists()
    assert {path.name for path in final_directory.iterdir()} == (
        COMMON_PATHS | {BRANCH_PATHS["ready"], "evidence-manifest.json"}
    )
    assert not (final_directory / "result.json").exists()
    assert not (final_directory / "integrity.json").exists()
    assert not (tmp_path / "runs" / record.attempt.semantic_run_id / "canonical").exists()

    verification = writer.verify(finalized)
    assert verification.finalized == finalized
    assert verification.failure is None

    for path in final_directory.iterdir():
        assert path.stat().st_mode & 0o222 == 0
        decoded = json.loads(path.read_bytes())
        assert path.read_bytes() == canonical_bytes(decoded)

    bundle_envelope = json.loads((final_directory / "market-bundle-ref.json").read_bytes())
    assert set(bundle_envelope["payload"]) == {"type", "bundle_key", "manifest_hash"}
    assert "streams" not in bundle_envelope["payload"]
    assert "events" not in bundle_envelope["payload"]


def test_all_runner_branches_publish_exact_common_and_branch_evidence(
    tmp_path: Path,
) -> None:
    for branch in ("ready", "blocked", "failed", "cancelled"):
        root = tmp_path / branch
        record = attempt_record(branch)
        outcome = AttemptEvidenceWriter(root=root).publish(record)

        assert outcome.finalized is not None
        finalized = outcome.finalized
        assert finalized.status is BRANCH_STATUS[branch]
        assert finalized.terminal_outcome is BRANCH_OUTCOME[branch]
        assert {entry.relative_path for entry in finalized.manifest.artifacts} == (
            COMMON_PATHS | {BRANCH_PATHS[branch]}
        )
        assert finalized.manifest.market_bundle_ref_hash == canonical_sha256(
            record.resolved_request.environment.market_bundle_ref
        )
        assert finalized.manifest.deployment_authorized is False


def test_existing_final_attempt_and_stale_staging_fail_without_overwrite(
    tmp_path: Path,
) -> None:
    record = attempt_record("ready")
    writer = AttemptEvidenceWriter(root=tmp_path)
    first = writer.publish(record)
    assert first.finalized is not None
    final_directory = _final_directory(tmp_path, record)
    before = {
        path.name: path.read_bytes() for path in sorted(final_directory.iterdir())
    }

    duplicate = writer.publish(record)

    assert duplicate.finalized is None
    assert duplicate.failure is not None
    assert duplicate.failure.code is EvidenceWriteFailureCode.FINAL_DESTINATION_EXISTS
    assert duplicate.failure.outcome is BacktestRunOutcome.FAILED
    assert {
        path.name: path.read_bytes() for path in sorted(final_directory.iterdir())
    } == before

    other_root = tmp_path / "stale"
    stale_record = attempt_record("blocked")
    stale = (
        other_root
        / "runs"
        / stale_record.attempt.semantic_run_id
        / "attempts"
        / ".staging"
        / stale_record.attempt.attempt_id
    )
    stale.mkdir(parents=True)
    (stale / "partial.tmp").write_text("unfinished", encoding="utf-8")

    stale_outcome = AttemptEvidenceWriter(root=other_root).publish(stale_record)

    assert stale_outcome.finalized is None
    assert stale_outcome.failure is not None
    assert stale_outcome.failure.code is EvidenceWriteFailureCode.STAGING_EXISTS
    assert not _final_directory(other_root, stale_record).exists()

    symlink_root = tmp_path / "dangling-final"
    symlink_record = attempt_record("failed")
    final_link = _final_directory(symlink_root, symlink_record)
    final_link.parent.mkdir(parents=True)
    final_link.symlink_to(symlink_root / "missing-target", target_is_directory=True)

    symlink_outcome = AttemptEvidenceWriter(root=symlink_root).publish(
        symlink_record
    )

    assert symlink_outcome.finalized is None
    assert symlink_outcome.failure is not None
    assert (
        symlink_outcome.failure.code
        is EvidenceWriteFailureCode.FINAL_DESTINATION_EXISTS
    )
    assert final_link.is_symlink()


def test_writer_failure_is_failed_evidence_and_never_exposes_absolute_path(
    tmp_path: Path,
) -> None:
    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_text("file", encoding="utf-8")
    record = attempt_record("ready")

    outcome = AttemptEvidenceWriter(root=invalid_root).publish(record)

    assert outcome.finalized is None
    assert outcome.failure is not None
    failure = outcome.failure
    assert failure.code is EvidenceWriteFailureCode.STAGING_PREPARE_FAILED
    assert failure.outcome is BacktestRunOutcome.FAILED
    assert failure.deployment_authorized is False
    encoded = canonical_bytes(failure)
    assert os.fsencode(str(tmp_path)) not in encoded
    assert b"NotADirectoryError" in encoded
    assert not _final_directory(invalid_root, record).exists()


def test_evidence_contracts_reject_forged_paths_coverage_and_branches(
    tmp_path: Path,
) -> None:
    record = attempt_record("ready")
    published = AttemptEvidenceWriter(root=tmp_path).publish(record)
    assert published.finalized is not None
    finalized = published.finalized
    entry = finalized.manifest.artifacts[0]

    with pytest.raises(ValueError, match="relative path"):
        replace(entry, relative_path="../request.json")
    with pytest.raises(ValueError, match="exactly cover"):
        replace(
            finalized.manifest,
            artifacts=finalized.manifest.artifacts[:-1],
        )
    with pytest.raises(ValueError, match="exactly one branch"):
        EvidencePublicationOutcome(
            finalized=finalized,
            failure=AttemptEvidenceWriter(root=tmp_path).publish(record).failure,
        )
    with pytest.raises(ValueError, match="never authorizes deployment"):
        replace(finalized, deployment_authorized=True)


def test_manifest_verification_fails_closed_on_extra_or_changed_file(
    tmp_path: Path,
) -> None:
    record = attempt_record("ready")
    writer = AttemptEvidenceWriter(root=tmp_path)
    published = writer.publish(record)
    assert published.finalized is not None
    finalized = published.finalized
    final_directory = _final_directory(tmp_path, record)

    os.chmod(final_directory, 0o755)
    extra = final_directory / "unlisted.json"
    extra.write_text("{}", encoding="utf-8")
    extra_verification = writer.verify(finalized)
    assert extra_verification.finalized is None
    assert extra_verification.failure is not None
    assert (
        extra_verification.failure.code
        is EvidenceWriteFailureCode.EVIDENCE_VERIFICATION_FAILED
    )

    extra.unlink()
    request_path = final_directory / "request.json"
    os.chmod(request_path, 0o644)
    request_path.write_bytes(request_path.read_bytes() + b"\n")
    changed_verification = writer.verify(finalized)
    assert changed_verification.finalized is None
    assert changed_verification.failure is not None
    assert (
        changed_verification.failure.code
        is EvidenceWriteFailureCode.EVIDENCE_VERIFICATION_FAILED
    )
