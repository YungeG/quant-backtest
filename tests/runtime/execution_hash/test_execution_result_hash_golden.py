from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_backtest import ExecutionResultHasher, ExecutionTrace
from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.runtime.execution_hash._fixtures import publish_ready, ready_branch


FIXTURE = Path("tests/fixtures/runtime/canonical-execution-result-hash-v1.json")


def _canonical_value(value) -> dict[str, object]:
    return json.loads(canonical_bytes(value))


def build_actual(root: Path) -> dict[str, object]:
    first_record, first_publication = publish_ready(root / "first", ordinal=1)
    second_record, second_publication = publish_ready(root / "second", ordinal=2)
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None

    original_result = ready_branch(first_record).engine_result
    first_trace = original_result.trace.entries[0]
    changed_result = replace(
        original_result,
        trace=ExecutionTrace(
            (
                replace(
                    first_trace,
                    evidence_hash=canonical_sha256({"changed": "golden_trace"}),
                ),
                *original_result.trace.entries[1:],
            )
        ),
    )
    changed_record, changed_publication = publish_ready(
        root / "changed", ordinal=3, result=changed_result
    )
    assert changed_publication.finalized is not None

    hasher = ExecutionResultHasher()
    first = hasher.bind(ready_branch(first_record), first_publication.finalized)
    second = hasher.bind(ready_branch(second_record), second_publication.finalized)
    changed = hasher.bind(
        ready_branch(changed_record), changed_publication.finalized
    )
    consistency = hasher.check_same_semantic_run((second, first))
    mismatch = hasher.check_same_semantic_run((changed, first))

    return {
        "schema_version": 1,
        "execution_result_hash": first.execution_result_hash,
        "canonical_summary_component_hashes": {
            "trace": canonical_sha256(first.summary.trace),
            "decision_batches": [
                canonical_sha256(value) for value in first.summary.decision_batches
            ],
            "allocations": [
                canonical_sha256(value) for value in first.summary.allocations
            ],
            "approved_targets": [
                canonical_sha256(value) for value in first.summary.approved_targets
            ],
            "normalized_targets": [
                canonical_sha256(value) for value in first.summary.normalized_targets
            ],
            "order_plans": [
                canonical_sha256(value) for value in first.summary.order_plans
            ],
            "order_streams": [
                canonical_sha256(value) for value in first.summary.order_streams
            ],
            "fills": [canonical_sha256(value) for value in first.summary.fills],
            "slippage_decisions": [
                canonical_sha256(value)
                for value in first.summary.slippage_decisions
            ],
            "fee_assessments": [
                canonical_sha256(value) for value in first.summary.fee_assessments
            ],
            "final_journal": canonical_sha256(first.summary.final_journal),
            "final_ledger_state": canonical_sha256(
                first.summary.final_ledger_state
            ),
            "final_portfolio_snapshot": canonical_sha256(
                first.summary.final_portfolio_snapshot
            ),
            "run_end_report": canonical_sha256(first.summary.run_end_report),
        },
        "attempt_independence": {
            "first_attempt_id": first.attempt.attempt_id,
            "second_attempt_id": second.attempt.attempt_id,
            "manifest_hashes_differ": (
                first.evidence_manifest_hash != second.evidence_manifest_hash
            ),
            "execution_hashes_equal": (
                first.execution_result_hash == second.execution_result_hash
            ),
        },
        "consistent_attempts": _canonical_value(consistency.consistency),
        "authoritative_mutation": {
            "changed_execution_result_hash": changed.execution_result_hash,
            "hash_changed": changed.execution_result_hash != first.execution_result_hash,
            "mismatch": _canonical_value(mismatch.mismatch),
        },
        "excluded_from_execution_hash": [
            "attempt_id",
            "semantic_run_id",
            "evidence_manifest_hash",
            "evidence_relative_directory",
            "logs",
            "charts",
            "derived_metrics",
            "presentation",
        ],
        "no_integrity_or_completed_result": True,
        "deployment_authorized": False,
    }


def test_execution_result_hash_matches_static_golden(tmp_path: Path) -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert build_actual(tmp_path) == expected
