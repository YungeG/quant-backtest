from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import AttemptIdentity, InputOrigin
from crypto_quant_domain import canonical_bytes
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.runtime.resolution.test_execution_case_identity import resolved_for
from tests.runtime.runner._fixtures import auditable_runner


FIXTURE = Path("tests/fixtures/runtime/pre-id-execution-case-identity-v1.json")


def build_actual() -> dict[str, object]:
    builder = SyntheticExecutionCaseBuilder()
    spec = builder.semantic_spec()
    first_resolved, first_case = resolved_for(builder)
    second_resolved, second_case = resolved_for(builder)
    runner = auditable_runner()
    first = runner.execute(
        resolved_request=first_resolved,
        execution_case=first_case,
        attempt=AttemptIdentity.first(first_resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    second = runner.retry_from_start(
        previous=first,
        resolved_request=second_resolved,
        execution_case=second_case,
        next_attempt_ordinal=2,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    assert first.ready_to_finalize is not None
    assert second.ready_to_finalize is not None
    first_result = first.ready_to_finalize.engine_result
    second_result = second.ready_to_finalize.engine_result
    assert first_case.identity_manifest is not None
    changed, changed_case = resolved_for(
        SyntheticExecutionCaseBuilder(reject_capability=True)
    )

    return {
        "schema_version": 1,
        "semantic_spec": json.loads(canonical_bytes(spec)),
        "semantic_spec_hash": spec.semantic_spec_hash,
        "semantic_run_id": first_resolved.semantic_run_id,
        "identity_manifest": json.loads(
            canonical_bytes(first_case.identity_manifest)
        ),
        "identity_manifest_hash": first_case.identity_manifest.manifest_hash,
        "final_execution_case_hash": first_case.case_hash,
        "spec_and_final_case_hashes_differ": spec.semantic_spec_hash
        != first_case.case_hash,
        "derived_domain_ids": {
            "order_id": first_case.decision_cycles[0].admissions[0].order.order_id.value,
            "fill_id": first_result.fills[0].fill_id.value,
            "fee_assessment_id": first_result.fee_assessments[
                0
            ].fee_assessment_id.value,
            "journal_entry_ids": [
                entry.journal_entry_id.value
                for entry in first_result.final_journal.entries
            ],
        },
        "independent_composition_and_attempt_parity": {
            "first_attempt_id": first.attempt.attempt_id,
            "second_attempt_id": second.attempt.attempt_id,
            "attempt_ids_differ": first.attempt != second.attempt,
            "cases_are_distinct_objects": first_case is not second_case,
            "case_hashes_equal": first_result.case_hash == second_result.case_hash,
            "identity_manifests_equal": first_case.identity_manifest
            == second_case.identity_manifest,
            "fill_ids_equal": first_result.fills[0].fill_id
            == second_result.fills[0].fill_id,
            "journal_ids_equal": [
                entry.journal_entry_id for entry in first_result.final_journal.entries
            ]
            == [entry.journal_entry_id for entry in second_result.final_journal.entries],
        },
        "semantic_input_change": {
            "semantic_run_changed": changed.semantic_run_id
            != first_resolved.semantic_run_id,
            "semantic_spec_changed": changed_case.semantic_spec_hash
            != first_case.semantic_spec_hash,
            "final_case_changed": changed_case.case_hash != first_case.case_hash,
        },
        "operational_fields_absent_from_spec": [
            "attempt_id",
            "hostname",
            "absolute_path",
            "wall_clock",
            "final_execution_case_hash",
        ],
        "deployment_authorized": False,
    }


def test_pre_id_execution_case_identity_matches_static_golden() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert build_actual() == expected
