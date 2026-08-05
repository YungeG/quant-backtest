from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crypto_quant_backtest import (
    CanonicalResultPublisher,
    IntegrityTraceLevel,
)
from crypto_quant_domain import canonical_bytes
from tests.runtime.integrity._fixtures import (
    decision_grade_attempts,
    mismatched_attempts,
    one_attempt,
    rebuild_evidence,
    two_attempts,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/runtime/integrity-canonical-result-publication-v1.json"


def _read_json(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(decoded, dict)
    return decoded


def _source_hashes(directory: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        paths = sorted(directory.iterdir())
        for path in paths:
            values[path.name] = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    except OSError as error:
        raise AssertionError("cannot hash publication directory") from error
    return values


def build_actual(root: Path) -> dict[str, object]:
    development, development_hashes, development_evidence = two_attempts(
        root / "development"
    )
    development_outcome = CanonicalResultPublisher(
        root=root / "development"
    ).publish(
        resolved_request=development.resolved_request,
        attempt_hashes=development_hashes,
        finalized_attempts=development_evidence,
        rebuild_evidence=rebuild_evidence(development),
    )
    assert development_outcome.finalized_result is not None
    development_result = development_outcome.finalized_result
    development_directory = root / "development" / development_result.relative_directory

    blocked = one_attempt(root / "blocked")
    blocked_outcome = CanonicalResultPublisher(root=root / "blocked").publish(
        resolved_request=blocked.resolved_request,
        attempt_hashes=blocked.attempt_hashes,
        finalized_attempts=blocked.finalized_attempts,
        rebuild_evidence=rebuild_evidence(blocked),
    )
    assert blocked_outcome.finalized_evaluation is not None
    blocked_evaluation = blocked_outcome.finalized_evaluation
    blocked_directory = root / "blocked" / blocked_evaluation.relative_directory

    mismatch = mismatched_attempts(root / "mismatch")
    mismatch_outcome = CanonicalResultPublisher(root=root / "mismatch").publish(
        resolved_request=mismatch.resolved_request,
        attempt_hashes=mismatch.attempt_hashes,
        finalized_attempts=mismatch.finalized_attempts,
        rebuild_evidence=rebuild_evidence(mismatch),
    )
    assert mismatch_outcome.finalized_evaluation is not None
    mismatch_evaluation = mismatch_outcome.finalized_evaluation
    mismatch_directory = root / "mismatch" / mismatch_evaluation.relative_directory

    decision = decision_grade_attempts(root / "decision")
    decision_outcome = CanonicalResultPublisher(root=root / "decision").publish(
        resolved_request=decision.resolved_request,
        attempt_hashes=decision.attempt_hashes,
        finalized_attempts=decision.finalized_attempts,
        rebuild_evidence=rebuild_evidence(
            decision,
            trace_level=IntegrityTraceLevel.FULL_TRACE,
            bundle_retained=True,
            deterministic_rebuild=True,
        ),
    )
    assert decision_outcome.finalized_result is not None
    decision_result = decision_outcome.finalized_result
    decision_directory = root / "decision" / decision_result.relative_directory

    try:
        decoded = json.loads(
            canonical_bytes(
                {
                "fixture_id": "integrity-canonical-result-publication-v1",
                "development": {
                    "finalized": development_result,
                    "canonical_attempt_ref": development_result.canonical_attempt_ref,
                    "integrity_report": development_result.integrity_report,
                    "result": development_result.result,
                    "publication_manifest": development_result.manifest,
                    "source_hashes": _source_hashes(development_directory),
                },
                "blocked": {
                    "finalized": blocked_evaluation,
                    "integrity_report": blocked_evaluation.report,
                    "evaluation_record": blocked_evaluation.record,
                    "publication_manifest": blocked_evaluation.manifest,
                    "source_hashes": _source_hashes(blocked_directory),
                },
                "mismatch": {
                    "finalized": mismatch_evaluation,
                    "integrity_report": mismatch_evaluation.report,
                    "evaluation_record": mismatch_evaluation.record,
                    "publication_manifest": mismatch_evaluation.manifest,
                    "source_hashes": _source_hashes(mismatch_directory),
                },
                "decision_grade": {
                    "finalized": decision_result,
                    "canonical_attempt_ref": decision_result.canonical_attempt_ref,
                    "integrity_report": decision_result.integrity_report,
                    "result": decision_result.result,
                    "publication_manifest": decision_result.manifest,
                    "source_hashes": _source_hashes(decision_directory),
                },
                }
            )
        )
    except json.JSONDecodeError as error:
        raise AssertionError("canonical fixture did not decode") from error
    assert isinstance(decoded, dict)
    return decoded


def test_integrity_and_canonical_publication_match_static_golden(
    tmp_path: Path,
) -> None:
    expected = _read_json(FIXTURE)
    assert build_actual(tmp_path) == expected
