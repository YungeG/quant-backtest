from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import AttemptEvidenceWriter
from tests.runtime.evidence._fixtures import attempt_record


FIXTURE = Path(
    "tests/fixtures/runtime/atomic-attempt-evidence-publication-v1.json"
)


def build_actual(root: Path) -> dict[str, object]:
    publications: dict[str, object] = {}
    for branch in ("ready", "blocked", "failed", "cancelled"):
        outcome = AttemptEvidenceWriter(root=root / branch).publish(
            attempt_record(branch)
        )
        assert outcome.finalized is not None
        finalized = outcome.finalized
        publications[branch] = {
            "status": finalized.status.value,
            "terminal_outcome": (
                finalized.terminal_outcome.value
                if finalized.terminal_outcome is not None
                else None
            ),
            "relative_directory": finalized.relative_directory,
            "manifest_hash": finalized.manifest.manifest_hash,
            "manifest_source_hash": finalized.manifest_source_hash,
            "publication_hash": finalized.publication_hash,
            "artifacts": [
                {
                    "path": entry.relative_path,
                    "role": entry.role.value,
                    "artifact_type": entry.artifact_type,
                    "schema_version": entry.schema_version,
                    "content_hash": entry.content_hash,
                    "source_hash": entry.source_hash,
                    "byte_count": entry.byte_count,
                }
                for entry in finalized.manifest.artifacts
            ],
            "market_bundle_ref_hash": finalized.manifest.market_bundle_ref_hash,
            "attempt_record_hash": finalized.manifest.attempt_record_hash,
            "deployment_authorized": finalized.deployment_authorized,
        }

    invalid_root = root / "writer-failure"
    invalid_root.write_text("not a directory", encoding="utf-8")
    failed = AttemptEvidenceWriter(root=invalid_root).publish(attempt_record("ready"))
    assert failed.failure is not None

    return {
        "schema_version": 1,
        "publications": publications,
        "writer_failure": {
            "code": failed.failure.code.value,
            "outcome": failed.failure.outcome.value,
            "relative_subject": failed.failure.relative_subject,
            "exception_type": failed.failure.exception_type,
            "failure_hash": failed.failure.failure_hash,
            "deployment_authorized": failed.failure.deployment_authorized,
        },
        "no_execution_summary_hash": True,
        "no_integrity_or_result_grade": True,
        "no_completed_publication": True,
    }


def test_atomic_attempt_evidence_publication_matches_static_golden(
    tmp_path: Path,
) -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert build_actual(tmp_path) == expected
