from __future__ import annotations

import json
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
    BacktestEvidenceError,
    BacktestEvidenceFailureCode,
    BacktestEvidenceRepository,
    BacktestRuntime,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)

from tests.runtime.test_durable_rebuild_facade import (
    _journey_values,
    _local_reader,
    _seed_attempt_graph,
    _Store,
)


def _completed(tmp_path: Path):
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    ref = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    ).run(request)
    assert type(ref) is BacktestCanonicalPublicationRefV2
    return store, ref


def _entry(payload: dict[str, object], path: str) -> dict[str, object]:
    return next(
        value
        for value in payload["artifacts"]  # type: ignore[union-attr]
        if value["relative_path"] == path
    )


def _rewrite_completed_integrity_outcome(store: _Store, ref, outcome: str):
    manifest_envelope = json.loads(store.values[ref.artifact_ref].source_bytes)
    manifest_payload = manifest_envelope["payload"]
    integrity_entry = _entry(manifest_payload, "integrity.json")
    integrity_ref = ArtifactRef(
        integrity_entry["artifact_type"],
        integrity_entry["schema_version"],
        integrity_entry["content_hash"],
    )
    integrity_envelope = json.loads(store.values[integrity_ref].source_bytes)
    integrity_payload = integrity_envelope["payload"]
    integrity_payload["context"]["comparison_outcome"] = outcome
    integrity_payload["context_hash"] = canonical_sha256(
        integrity_payload["context"]
    )
    new_integrity_envelope = ArtifactEnvelope.create(
        "integrity_report", 2, integrity_payload
    )
    new_integrity_ref = store.put(envelope=new_integrity_envelope)

    result_entry = _entry(manifest_payload, "result.json")
    result_ref = ArtifactRef(
        result_entry["artifact_type"],
        result_entry["schema_version"],
        result_entry["content_hash"],
    )
    result_envelope = json.loads(store.values[result_ref].source_bytes)
    result_payload = result_envelope["payload"]
    result_payload["integrity_report_hash"] = canonical_sha256(integrity_payload)
    new_result_envelope = ArtifactEnvelope.create(
        "completed_backtest_result", 3, result_payload
    )
    new_result_ref = store.put(envelope=new_result_envelope)

    for entry, envelope, child_ref in (
        (integrity_entry, new_integrity_envelope, new_integrity_ref),
        (result_entry, new_result_envelope, new_result_ref),
    ):
        source = canonical_bytes(envelope)
        entry["content_hash"] = child_ref.content_hash
        entry["source_hash"] = canonical_sha256(envelope)
        entry["byte_count"] = len(source)
    new_manifest_envelope = ArtifactEnvelope.create(
        "canonical_publication_manifest", 2, manifest_payload
    )
    return BacktestCanonicalPublicationRefV2.from_artifact_ref(
        store.put(envelope=new_manifest_envelope)
    )


def test_completed_v3_rejects_mismatch_context_with_decision_grade(
    tmp_path: Path,
) -> None:
    store, ref = _completed(tmp_path)
    tampered = _rewrite_completed_integrity_outcome(store, ref, "mismatch")

    with pytest.raises(BacktestEvidenceError) as error:
        BacktestEvidenceRepository(store).load_completed_v3(tampered)

    assert error.value.code is BacktestEvidenceFailureCode.PORT_STATIC_PROOF_MISMATCH


def test_completed_v3_requires_exact_nominal_version(tmp_path: Path) -> None:
    store, ref = _completed(tmp_path)
    repository = BacktestEvidenceRepository(store)
    completed = repository.load_completed_v3(ref)
    assert completed.source_publication_ref == ref

    with pytest.raises(BacktestEvidenceError) as raw_error:
        repository.load_completed_v3(ref.to_artifact_ref())
    assert raw_error.value.code is BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH

    v1_ref = BacktestCanonicalPublicationRef.from_artifact_ref(
        ArtifactRef(
            "canonical_publication_manifest",
            1,
            ref.artifact_ref.content_hash,
        )
    )
    with pytest.raises(BacktestEvidenceError) as v1_error:
        repository.load_completed_v3(v1_ref)
    assert v1_error.value.code is BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH

    with pytest.raises(BacktestEvidenceError) as cross_error:
        repository.load_completed(ref)
    assert cross_error.value.code is BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH
