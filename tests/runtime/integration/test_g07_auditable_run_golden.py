from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crypto_quant_backtest import (
    AttemptIdentity,
    AuditableBacktestRunner,
    DeterministicBarEngine,
    InputOrigin,
)
from crypto_quant_domain import canonical_bytes
from tests.runtime.integration._fixtures import completed_journey, mismatch_journey
from tests.runtime.runner._fixtures import RecordingEngine


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/runtime/g07-auditable-synthetic-run-v1.json"


def _read_json(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(decoded, dict)
    return decoded


def _source_hashes(directory: Path) -> dict[str, str]:
    try:
        return {
            path.name: f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
            for path in sorted(directory.iterdir())
            if path.is_file()
        }
    except OSError as error:
        raise AssertionError("cannot hash publication directory") from error


def build_actual(root: Path) -> dict[str, object]:
    completed = completed_journey(root / "completed")
    finalized = completed.publication.finalized_result
    assert finalized is not None
    manifest = completed.case.identity_manifest
    assert manifest is not None
    engine = RecordingEngine(outcome=DeterministicBarEngine().run(completed.case))
    cache_record = AuditableBacktestRunner(
        engine=engine,
        publication_root=root / "completed",
    ).execute(
        resolved_request=completed.attempts.resolved_request,
        execution_case=completed.case,
        attempt=AttemptIdentity.retry(
            completed.attempts.canonical_attempt.attempt,
            next_ordinal=3,
        ),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    assert cache_record.cache_hit is not None
    completed_directory = root / "completed" / finalized.relative_directory

    mismatch = mismatch_journey(root / "mismatch")
    evaluation = mismatch.publication.finalized_evaluation
    assert evaluation is not None

    payload = {
        "fixture_id": "g07-auditable-synthetic-run-v1",
        "completed": {
            "semantic_run_id": completed.attempts.semantic_run_id,
            "execution_case_hash": completed.case.case_hash,
            "identity_manifest_hash": manifest.manifest_hash,
            "derived_domain_ids": {
                binding.binding_key: binding.value
                for binding in manifest.bindings
                if binding.domain_kind is not None
            },
            "attempts": tuple(
                {
                    "attempt": value.attempt,
                    "evidence_manifest_hash": value.evidence_manifest_hash,
                    "engine_result_artifact_content_hash": (
                        value.engine_result_artifact_content_hash
                    ),
                    "execution_result_hash": value.execution_result_hash,
                    "relative_directory": evidence.relative_directory,
                }
                for value, evidence in zip(
                    completed.attempts.attempt_hashes,
                    completed.attempts.finalized_attempts,
                    strict=True,
                )
            ),
            "attempt_evidence_unchanged": (
                completed.attempt_bytes_before == completed.attempt_bytes_after
            ),
            "authoritative_objects_unchanged": (
                completed.input_hashes_before == completed.input_hashes_after
            ),
            "canonical_existed_before": completed.canonical_existed_before,
            "finalized_result": finalized,
            "canonical_source_hashes": _source_hashes(completed_directory),
            "cache_hit": cache_record.cache_hit,
            "cache_engine_calls": len(engine.calls),
        },
        "mismatch": {
            "semantic_run_id": mismatch.attempts.semantic_run_id,
            "attempt_execution_hashes": tuple(
                value.execution_result_hash
                for value in mismatch.attempts.attempt_hashes
            ),
            "attempt_evidence_unchanged": (
                mismatch.attempt_bytes_before == mismatch.attempt_bytes_after
            ),
            "authoritative_objects_unchanged": (
                mismatch.input_hashes_before == mismatch.input_hashes_after
            ),
            "canonical_exists": mismatch.canonical_directory.exists(),
            "finalized_evaluation": evaluation,
            "evaluation_source_hashes": _source_hashes(
                mismatch.evaluation_directory
            ),
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical fixture did not decode") from error
    assert isinstance(decoded, dict)
    return decoded


def test_g07_auditable_run_matches_static_golden(tmp_path: Path) -> None:
    assert build_actual(tmp_path) == _read_json(FIXTURE)
