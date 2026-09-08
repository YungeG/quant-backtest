from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, cast

import crypto_quant_backtest
import pytest
from crypto_quant_backtest import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
    BacktestEvidenceError,
    BacktestEvidenceFailureCode,
    BacktestEvidenceRepository,
    BacktestRuntime,
)
from crypto_quant_backtest.engine import ExecutionTraceEntry
from crypto_quant_backtest.runner import ReadyToFinalizeAttempt
from crypto_quant_backtest.verified_publications import _VerifiedCompletedEvidenceV3
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
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
    prepared, resolved, _, _, request, registry = values
    store = _Store()
    records, finalized = cast(
        Any, _seed_attempt_graph(store, tmp_path / "seed", values)
    )
    ref = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    ).run(request)
    assert type(ref) is BacktestCanonicalPublicationRefV2
    return store, ref, resolved, records, finalized


def _artifact_ref(value: dict[str, object]) -> ArtifactRef:
    return ArtifactRef(
        value["artifact_type"],  # type: ignore[arg-type]
        value["schema_version"],  # type: ignore[arg-type]
        value["content_hash"],  # type: ignore[arg-type]
    )


def _entry(payload: dict[str, object], path: str) -> dict[str, object]:
    return next(
        value
        for value in payload["artifacts"]  # type: ignore[union-attr]
        if value["relative_path"] == path
    )


def _payload(store: _Store, ref: ArtifactRef) -> dict[str, object]:
    return json.loads(store.values[ref].source_bytes)["payload"]


def _tamper_payload(store: _Store, ref: ArtifactRef, mutate) -> None:
    source = json.loads(store.values[ref].source_bytes)
    mutate(source["payload"])
    envelope = ArtifactEnvelope.create(
        source["artifact_type"],
        source["schema_version"],
        source["payload"],
    )
    store.values[ref] = ArtifactReadResult(
        envelope=envelope,
        artifact=object(),
        source_bytes=canonical_bytes(envelope),
        source_hash=canonical_sha256(envelope),
    )


def _tamper_source(store: _Store, ref: ArtifactRef) -> None:
    result = store.values[ref]
    bypassed = object.__new__(ArtifactReadResult)
    for name in ("envelope", "artifact", "source_hash"):
        object.__setattr__(bypassed, name, getattr(result, name))
    object.__setattr__(bypassed, "source_bytes", result.source_bytes + b" ")
    store.values[ref] = bypassed


def _root_child_ref(store: _Store, ref, path: str) -> ArtifactRef:
    return _artifact_ref(_entry(_payload(store, ref.artifact_ref), path))


def _first_evidence_ref(store: _Store, ref) -> ArtifactRef:
    verification_ref = _root_child_ref(store, ref, "rebuild-verification.json")
    value = _payload(store, verification_ref)["attempts"][0][  # type: ignore[index]
        "evidence_manifest_ref"
    ]
    return ArtifactRef(
        value["artifact_type"],  # type: ignore[arg-type]
        value["schema_version"],  # type: ignore[arg-type]
        value["content_hash"],  # type: ignore[arg-type]
    )


def test_load_completed_evidence_v3_projects_the_verified_graph(
    tmp_path: Path,
) -> None:
    store, ref, resolved, records, finalized = _completed(tmp_path)
    before = {key: value.source_bytes for key, value in store.values.items()}
    repository = BacktestEvidenceRepository(store)

    completed = repository.load_completed_v3(ref)
    rich = repository.load_completed_evidence_v3(ref)

    assert completed == rich.completed
    assert type(rich) is _VerifiedCompletedEvidenceV3
    assert rich.resolved_request == resolved
    assert rich.ready_attempts == tuple(value.ready_to_finalize for value in records)
    assert rich.finalized_attempts == finalized
    assert tuple(value.attempt for value in rich.attempt_hashes) == (
        rich.first_attempt,
        rich.retry_attempt,
    )
    assert rich.first_engine_result == records[0].ready_to_finalize.engine_result
    assert rich.first_trace == rich.first_engine_result.trace
    assert rich.market_bundle_ref == resolved.request.market_bundle_ref
    assert rich.execution_result_hash == completed.source_execution_result_hash
    assert rich.execution_case_semantic_hash == (
        resolved.request.execution_case_semantic_hash
    )
    assert rich.execution_case_hash == rich.first_engine_result.case_hash
    assert rich.trace_hash == rich.first_trace.trace_hash
    assert rich.completed.rebuild_verification_ref.artifact_type == (
        "deterministic_rebuild_verification"
    )
    assert rich.completed.proof_publication_manifest_ref.artifact_type == (
        "deterministic_rebuild_verification_publication_manifest"
    )
    identities = (
        rich.canonical_root,
        rich.canonical_attempt,
        rich.integrity.artifact,
        rich.completed_result,
        rich.rebuild_verification,
        rich.proof_publication_manifest,
        *rich.evidence_manifests,
    )
    assert all(value.body_hash == value.ref.content_hash for value in identities)
    assert rich.canonical_root.ref == ref.artifact_ref
    assert rich.integrity.context_hash.startswith("sha256:")
    assert rich.integrity.result_grade is completed.result_grade
    assert rich.integrity.issue_codes == ()
    assert rich.accepted_market_bundle_manifest_hash == rich.market_bundle_ref.manifest_hash
    verification_attempts = cast(
        list[dict[str, object]],
        _payload(store, rich.rebuild_verification.ref)["attempts"],
    )
    assert tuple(value.ref for value in rich.evidence_manifests) == tuple(
        _artifact_ref(cast(dict[str, object], value["evidence_manifest_ref"]))
        for value in verification_attempts
    )
    body = rich.to_canonical_dict()
    static_hash = body.pop("static_verification_hash")
    assert static_hash == rich.static_verification_hash == canonical_sha256(body)
    assert canonical_bytes(rich) == canonical_bytes(rich.to_canonical_dict())
    assert {key: value.source_bytes for key, value in store.values.items()} == before


def test_lean_and_rich_loaders_have_the_exact_same_read_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, ref, _, _, _ = _completed(tmp_path)
    lean_store = _Store()
    rich_store = _Store()
    lean_store.values = dict(store.values)
    rich_store.values = dict(store.values)
    lean_reads: list[ArtifactRef] = []
    rich_reads: list[ArtifactRef] = []
    lean_read = lean_store.read
    rich_read = rich_store.read

    def read_lean(*, ref: ArtifactRef) -> ArtifactReadResult:
        lean_reads.append(ref)
        return lean_read(ref=ref)

    def read_rich(*, ref: ArtifactRef) -> ArtifactReadResult:
        rich_reads.append(ref)
        return rich_read(ref=ref)

    monkeypatch.setattr(lean_store, "read", read_lean)
    monkeypatch.setattr(rich_store, "read", read_rich)

    lean = BacktestEvidenceRepository(lean_store).load_completed_v3(ref)
    rich = BacktestEvidenceRepository(rich_store).load_completed_evidence_v3(ref)

    assert lean == rich.completed
    assert lean_reads == rich_reads
    assert len(lean_reads) == len(rich_reads)


def test_completed_evidence_v3_wrong_ref_precedence_matches_lean_loader(
    tmp_path: Path,
) -> None:
    store, ref, _, _, _ = _completed(tmp_path)
    repository = BacktestEvidenceRepository(store)
    wrong_refs = (
        ref.to_artifact_ref(),
        BacktestCanonicalPublicationRef.from_artifact_ref(
            ArtifactRef(
                "canonical_publication_manifest",
                1,
                ref.artifact_ref.content_hash,
            )
        ),
    )

    for wrong_ref in wrong_refs:
        codes = []
        for method in (
            repository.load_completed_v3,
            repository.load_completed_evidence_v3,
        ):
            with pytest.raises(BacktestEvidenceError) as error:
                method(wrong_ref)  # type: ignore[arg-type]
            codes.append(error.value.code)
        assert codes == [
            BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
            BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
        ]


def test_completed_evidence_v3_rejects_constructor_bypass_mutation_and_subclass(
    tmp_path: Path,
) -> None:
    store, ref, _, _, _ = _completed(tmp_path)
    rich = BacktestEvidenceRepository(store).load_completed_evidence_v3(ref)
    different_hash = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="trace hash mismatch"):
        replace(rich, trace_hash=different_hash)

    mutated_ready = replace(rich.ready_attempts[0])
    object.__setattr__(mutated_ready, "execution_case_hash", different_hash)
    with pytest.raises(ValueError, match="rebind exactly|case hash mismatch"):
        replace(
            rich,
            ready_attempts=(mutated_ready, rich.ready_attempts[1]),
            static_verification_hash=different_hash,
        )

    class ReadySubclass(ReadyToFinalizeAttempt):
        pass

    subclass_ready = ReadySubclass(
        attempt=rich.ready_attempts[0].attempt,
        resolved_request=rich.ready_attempts[0].resolved_request,
        input_origin=rich.ready_attempts[0].input_origin,
        execution_case_hash=rich.ready_attempts[0].execution_case_hash,
        engine_result=rich.ready_attempts[0].engine_result,
    )
    with pytest.raises(TypeError, match="ready_attempts"):
        replace(
            rich,
            ready_attempts=(subclass_ready, rich.ready_attempts[1]),
        )

    class RichSubclass(_VerifiedCompletedEvidenceV3):
        pass

    values = {field.name: getattr(rich, field.name) for field in fields(rich)}
    with pytest.raises(TypeError, match="exact _VerifiedCompletedEvidenceV3"):
        RichSubclass(**values)

    bypassed = object.__new__(_VerifiedCompletedEvidenceV3)
    with pytest.raises(AttributeError):
        canonical_bytes(bypassed)


def test_completed_evidence_v3_rejects_nested_trace_entry_subclass_bypass_and_mutation(
    tmp_path: Path,
) -> None:
    store, ref, _, _, _ = _completed(tmp_path)
    repository = BacktestEvidenceRepository(store)

    rich = repository.load_completed_evidence_v3(ref)
    original = rich.first_trace.entries[0]

    class TraceEntrySubclass(ExecutionTraceEntry):
        pass

    subclass = TraceEntrySubclass(
        original.sequence,
        original.stage,
        original.instant,
        original.subject_id,
        original.evidence_hash,
    )
    trace = rich.first_trace
    original_entries = trace.entries
    object.__setattr__(
        trace,
        "entries",
        (subclass, *original_entries[1:]),
    )
    with pytest.raises(TypeError, match="exact ExecutionTraceEntry"):
        replace(rich)
    object.__setattr__(trace, "entries", original_entries)

    rich = repository.load_completed_evidence_v3(ref)
    mutated = rich.first_trace.entries[0]
    original_sequence = mutated.sequence
    object.__setattr__(mutated, "sequence", -1)
    with pytest.raises(ValueError, match="nonnegative integer"):
        replace(rich)
    object.__setattr__(mutated, "sequence", original_sequence)

    rich = repository.load_completed_evidence_v3(ref)
    trace = rich.first_trace
    original_entries = trace.entries
    bypassed = object.__new__(ExecutionTraceEntry)
    object.__setattr__(
        trace,
        "entries",
        (bypassed, *original_entries[1:]),
    )
    with pytest.raises(AttributeError):
        replace(rich)
    object.__setattr__(trace, "entries", original_entries)


def test_lean_loader_does_not_construct_rich_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, ref, _, _, _ = _completed(tmp_path)
    repository = BacktestEvidenceRepository(store)

    def fail_projection(cls, **kwargs):
        raise ValueError("rich projection failed")

    monkeypatch.setattr(
        _VerifiedCompletedEvidenceV3,
        "create",
        classmethod(fail_projection),
    )

    assert repository.load_completed_v3(ref).source_publication_ref == ref
    with pytest.raises(BacktestEvidenceError) as error:
        repository.load_completed_evidence_v3(ref)
    assert error.value.code is BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID
    assert "rich projection failed" in str(error.value)


@pytest.mark.parametrize(
    ("subject", "expected_code"),
    (
        ("trace", BacktestEvidenceFailureCode.PORT_STATIC_PROOF_MISMATCH),
        ("evidence_manifest", BacktestEvidenceFailureCode.PORT_STATIC_PROOF_MISMATCH),
        ("integrity_body", BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED),
        ("verification_body", BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID),
        ("verification_source", BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED),
        ("canonical_attempt_source", BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED),
        ("proof", BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID),
        ("completed_result_source", BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED),
        ("root_source", BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED),
        ("ref", BacktestEvidenceFailureCode.PORT_REF_NOT_FOUND),
    ),
)
def test_completed_v3_public_loaders_preserve_the_same_tamper_failure_codes(
    tmp_path: Path,
    subject: str,
    expected_code: BacktestEvidenceFailureCode,
) -> None:
    store, ref, _, _, _ = _completed(tmp_path)
    repository = BacktestEvidenceRepository(store)
    target_ref = ref

    if subject == "trace":
        evidence_ref = _first_evidence_ref(store, ref)
        engine_ref = _artifact_ref(
            _entry(_payload(store, evidence_ref), "engine-execution-result.json")
        )
        _tamper_payload(
            store,
            engine_ref,
            lambda payload: payload["trace"].update({"schema_version": 2}),
        )
    elif subject == "evidence_manifest":
        evidence_ref = _first_evidence_ref(store, ref)
        _tamper_payload(
            store,
            evidence_ref,
            lambda payload: payload.update({"manifest_hash": "sha256:" + "0" * 64}),
        )
    elif subject == "integrity_body":
        integrity_ref = _root_child_ref(store, ref, "integrity.json")
        _tamper_payload(
            store,
            integrity_ref,
            lambda payload: payload["context"].update(
                {"comparison_outcome": "mismatch"}
            ),
        )
    elif subject == "verification_body":
        verification_ref = _root_child_ref(store, ref, "rebuild-verification.json")
        _tamper_payload(
            store,
            verification_ref,
            lambda payload: payload.update({"claim": "tampered"}),
        )
    elif subject == "verification_source":
        _tamper_source(
            store,
            _root_child_ref(store, ref, "rebuild-verification.json"),
        )
    elif subject == "canonical_attempt_source":
        _tamper_source(
            store,
            _root_child_ref(store, ref, "canonical-attempt-ref.json"),
        )
    elif subject == "proof":
        proof_ref = _root_child_ref(store, ref, "proof-publication-manifest.json")
        _tamper_payload(
            store,
            proof_ref,
            lambda payload: payload.update({"publication_id": "tampered"}),
        )
    elif subject == "completed_result_source":
        _tamper_source(store, _root_child_ref(store, ref, "result.json"))
    elif subject == "root_source":
        _tamper_source(store, ref.artifact_ref)
    else:
        target_ref = BacktestCanonicalPublicationRefV2.from_artifact_ref(
            ArtifactRef(
                "canonical_publication_manifest",
                2,
                "sha256:" + "0" * 64,
            )
        )

    codes = []
    for method in (
        repository.load_completed_v3,
        repository.load_completed_evidence_v3,
    ):
        with pytest.raises(BacktestEvidenceError) as error:
            method(target_ref)
        codes.append(error.value.code)
    assert codes == [expected_code, expected_code]


def test_completed_evidence_v3_is_off_root_and_imports_without_cycle() -> None:
    assert not hasattr(crypto_quant_backtest, "_VerifiedCompletedEvidenceV3")
    assert _VerifiedCompletedEvidenceV3.__module__ == (
        "crypto_quant_backtest.verified_publications"
    )
