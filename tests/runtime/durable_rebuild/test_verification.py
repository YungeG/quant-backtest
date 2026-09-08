from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import crypto_quant_backtest._durable_rebuild as durable
import pytest
from crypto_quant_backtest import (
    AttemptConsistencySet,
    AttemptEvidenceWriter,
    AttemptIdentity,
    AuditableBacktestRunner,
    DeterministicBarEngine,
    ExecutionCaseComposer,
    ExecutionResultHasher,
    InputOrigin,
    ProfileResolver,
)
from crypto_quant_backtest._durable_rebuild import (
    _ARTIFACT_CATALOG,
    DeterministicRebuildVerificationV1,
    DurableRebuildError,
    DurableRebuildFailureCode,
    DurableRebuildVerifierV1,
    RebuildComparisonOutcome,
    RebuildDivergenceSubject,
    _read_verification,
)
from crypto_quant_backtest.composition import (
    _compose_execution_case_v3,
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from crypto_quant_backtest.engine import ExecutionCaseIdentityFactory
from crypto_quant_backtest.evidence import EvidenceArtifactRole
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG,
    BacktestExecutionRequest,
    _materialize_execution_input_bundle_v3,
)
from crypto_quant_backtest.timeline import DeterministicTimeline
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import LocalMarketBundleReader

from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.runtime.execution_hash._fixtures import ready_branch
from tests.runtime.execution_inputs.test_multi_resolution_bundle_v3 import _contract
from tests.runtime.resolution._fixtures import profile_registry


class _Store:
    def __init__(self) -> None:
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}
        self.reads: dict[ArtifactRef, int] = {}

    def put(self, artifact_type: str, artifact: object) -> ArtifactRef:
        envelope = ArtifactEnvelope.create(artifact_type, 1, artifact)
        ref = ArtifactRef.from_envelope(envelope)
        source = canonical_bytes(envelope)
        self.values[ref] = ArtifactReadResult(
            envelope=envelope,
            artifact=artifact,
            source_bytes=source,
            source_hash=canonical_sha256(envelope),
        )
        return ref

    def put_envelope(self, envelope: ArtifactEnvelope) -> ArtifactRef:
        decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope))
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = decoded
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        self.reads[ref] = self.reads.get(ref, 0) + 1
        return self.values[ref]


def _local_reader(root: Path, reader) -> LocalMarketBundleReader:
    result = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=reader.manifest,
        stream_payloads={
            key: canonical_bytes(events)
            for key, events in reader.streams.items()
        },
        retention_policy_ref="retention.local-market-bundle-repository-v1",
    )
    assert result.result is not None
    return LocalMarketBundleReader.open(
        repository_root=root.resolve(), bundle_ref=result.result.bundle_ref
    )


def _fresh_contract():
    prepared, resolved, hydrated, _, _ = _contract()
    timeline = DeterministicTimeline.open(
        reader=prepared.verified_reader,
        stream_keys=hydrated.timeline_stream_keys,
        window=resolved.request.timeline_window,
    )
    base_spec = replace(
        hydrated.execution_case_semantic_spec,
        timeline_semantic_hash=ExecutionCaseComposer.timeline_semantic_hash(timeline),
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=base_spec,
        execution_case_plan=hydrated.execution_case_plan,
        market_data_preparation=prepared.preparation,
    )
    registry = profile_registry(
        extra_market_capabilities=tuple(
            capability
            for capability in prepared.verified_reader.manifest.capabilities
            if capability.key == "price_bars"
        )
    )
    request_value = replace(
        resolved.request, execution_case_semantic_hash=spec.semantic_spec_hash
    )
    resolution = ProfileResolver().resolve(
        request=request_value,
        registry=registry,
        market_bundle_manifest=prepared.verified_reader.manifest,
        build_artifact_manifest=resolved.build_artifact_manifest,
    )
    assert resolution.resolved is not None
    resolved = resolution.resolved
    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=resolved.semantic_run_id,
        namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    generated = SyntheticExecutionCaseBuilder().build(
        identities, spec.semantic_spec_hash
    )
    authority_plan = hydrated.execution_case_plan
    plan = _ExecutionCasePlan(
        decision_cycles=generated.decision_cycles,
        bar_executions=generated.bar_executions,
        financial_state=generated.financial_state,
        financial_dispatch_plan=generated.financial_dispatch_plan,
        execution_model=authority_plan.execution_model,
        snapshot_plan=authority_plan.snapshot_plan,
        closeout_policy=generated.closeout_policy,
    )
    assert (
        _execution_case_semantic_spec_v3(
            base_spec=base_spec,
            execution_case_plan=plan,
            market_data_preparation=prepared.preparation,
        )
        == spec
    )
    hydrated = _HydratedExecutionCaseInputs(
        spec,
        hydrated.timeline_stream_keys,
        hydrated.target_stream,
        hydrated.timeline_batch_size,
        plan,
    )
    case = _compose_execution_case_v3(
        resolved_request=resolved,
        market_reader=prepared.verified_reader,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    envelope = _materialize_execution_input_bundle_v3(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    request = BacktestExecutionRequest(
        schema_version=3,
        request=resolved.request,
        execution_input_bundle_ref=ArtifactRef.from_envelope(envelope),
    )
    return prepared, resolved, case, envelope, request, registry


def _proof_fixture(
    tmp_path: Path,
    *,
    changed_rebuild: bool = False,
    monkeypatch: pytest.MonkeyPatch | None = None,
):
    prepared, resolved, case, envelope, request, registry = _fresh_contract()
    local = _local_reader(tmp_path / "market", prepared.verified_reader)
    runner = AuditableBacktestRunner(
        engine=DeterministicBarEngine(), publication_root=tmp_path / "publication"
    )
    runner._verify_v3_contract(
        resolved_request=resolved,
        execution_case=case,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        market_data_preparation=prepared.preparation,
    )
    first = runner._execute_verified(
        resolved_request=resolved,
        execution_case=case,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        cancellation=None,
    )
    second = runner._retry_from_start_verified(
        previous=first,
        resolved_request=resolved,
        execution_case=case,
        next_attempt_ordinal=2,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        market_data_preparation=prepared.preparation,
    )
    writer = AttemptEvidenceWriter(root=tmp_path / "publication")
    first_publication = writer.publish(first)
    second_publication = writer.publish(second)
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None
    finalized = (first_publication.finalized, second_publication.finalized)
    hashes = (
        ExecutionResultHasher.bind(ready_branch(first), finalized[0]),
        ExecutionResultHasher.bind(ready_branch(second), finalized[1]),
    )
    attempts = AttemptConsistencySet(resolved, hashes, finalized)
    store = _Store()
    store.put_envelope(envelope)
    for record, evidence in ((first, finalized[0]), (second, finalized[1])):
        store.put("evidence_manifest", evidence.manifest)
        store.put("backtest_request", resolved.request)
        store.put("resolved_backtest_environment", resolved.environment)
        store.put("build_artifact_manifest", resolved.build_artifact_manifest)
        store.put("market_bundle_ref", resolved.environment.market_bundle_ref)
        store.put(
            "environment_compatibility_report",
            resolved.environment.compatibility_report,
        )
        store.put("attempt_execution_record", record)
        assert record.ready_to_finalize is not None
        store.put("engine_execution_result", record.ready_to_finalize.engine_result)

    counts = {
        "read": 0,
        "reopen": 0,
        "prep": 0,
        "resolution": 0,
        "composition": 0,
        "execution": 0,
    }
    original_reopen = local._reopen_with_provenance_v1

    def reopen():
        counts["reopen"] += 1
        return original_reopen()

    local._reopen_with_provenance_v1 = reopen  # type: ignore[method-assign]

    if changed_rebuild and monkeypatch is None:
        raise ValueError("changed_rebuild requires monkeypatch")
    original_read = durable._read_execution_inputs_v3_from_snapshot
    original_resolve = durable.ProfileResolver.resolve
    original_prep = durable._prepare_multi_resolution_market_data_from_retained_v1
    original_compose = durable._compose_execution_case_v3
    original_run = durable.DeterministicBarEngine.run

    def read(*args, **kwargs):
        counts["read"] += 1
        return original_read(*args, **kwargs)

    def resolve(self, *args, **kwargs):
        counts["resolution"] += 1
        return original_resolve(self, *args, **kwargs)

    def prep(*args, **kwargs):
        counts["prep"] += 1
        return original_prep(*args, **kwargs)

    def compose(*args, **kwargs):
        counts["composition"] += 1
        return original_compose(*args, **kwargs)

    def run(self, *args, **kwargs):
        counts["execution"] += 1
        outcome = original_run(self, *args, **kwargs)
        if not changed_rebuild or outcome.result is None:
            return outcome
        changed = replace(
            outcome.result,
            trace=replace(
                outcome.result.trace,
                entries=(
                    replace(
                        outcome.result.trace.entries[0],
                        evidence_hash=canonical_sha256({"changed": True}),
                    ),
                    *outcome.result.trace.entries[1:],
                ),
            ),
        )
        return replace(outcome, result=changed)

    if monkeypatch is not None:
        monkeypatch.setattr(
            durable, "_read_execution_inputs_v3_from_snapshot", read
        )
        monkeypatch.setattr(durable.ProfileResolver, "resolve", resolve)
        monkeypatch.setattr(
            durable,
            "_prepare_multi_resolution_market_data_from_retained_v1",
            prep,
        )
        monkeypatch.setattr(durable, "_compose_execution_case_v3", compose)
        monkeypatch.setattr(durable.DeterministicBarEngine, "run", run)

    verifier = DurableRebuildVerifierV1(
        artifact_reader=store,
        market_reader=local,
        profile_registry=registry,
    )
    verification = verifier.verify(
        request=request,
        resolved_request=resolved,
        prepared_market_data=prepared,
        execution_case=case,
        attempts=attempts,
    )
    return {
        "verification": verification,
        "verifier": verifier,
        "store": store,
        "request": request,
        "resolved": resolved,
        "prepared": prepared,
        "case": case,
        "attempts": attempts,
        "counts": counts,
        "root": tmp_path / "publication",
    }


def test_verifier_reads_and_recomputes_once_without_a_rebuild_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _proof_fixture(tmp_path, monkeypatch=monkeypatch)
    verification = fixture["verification"]
    assert all(
        comparison.outcome is RebuildComparisonOutcome.EQUAL
        for comparison in verification.comparisons
    )
    assert fixture["counts"] == {
        "read": 2,
        "reopen": 1,
        "prep": 1,
        "resolution": 1,
        "composition": 1,
        "execution": 1,
    }
    execution_ref = fixture["request"].execution_input_bundle_ref
    assert fixture["store"].reads[execution_ref] == 2
    assert [entry.attempt.ordinal for entry in verification.attempts] == [1, 2]
    assert not hasattr(verification.fresh_rebuild, "attempt")


def test_mismatch_is_valid_and_uses_first_divergence_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verification = _proof_fixture(
        tmp_path, changed_rebuild=True, monkeypatch=monkeypatch
    )["verification"]
    assert verification.comparisons[0].outcome is RebuildComparisonOutcome.EQUAL
    assert [value.outcome for value in verification.comparisons[1:]] == [
        RebuildComparisonOutcome.MISMATCH,
        RebuildComparisonOutcome.MISMATCH,
    ]
    assert [value.first_divergence for value in verification.comparisons[1:]] == [
        RebuildDivergenceSubject.TRACE_HASH,
        RebuildDivergenceSubject.TRACE_HASH,
    ]


def test_exact_decoder_rejects_extra_keys_attempt_order_and_cross_run(tmp_path: Path) -> None:
    verification = _proof_fixture(tmp_path)["verification"]
    payload = json.loads(canonical_bytes(verification).decode())
    payload["extra"] = True
    with pytest.raises(ValueError):
        _read_verification(payload)

    payload = json.loads(canonical_bytes(verification).decode())
    payload["attempts"].reverse()
    with pytest.raises(ValueError):
        _read_verification(payload)

    payload = json.loads(canonical_bytes(verification).decode())
    payload["attempts"][0]["attempt"]["semantic_run_id"] = "run_" + "0" * 64
    with pytest.raises(ValueError):
        _read_verification(payload)


def test_structure_rejects_bare_id_and_transitive_engine_mismatch(tmp_path: Path) -> None:
    fixture = _proof_fixture(tmp_path)
    verification = fixture["verification"]
    first = verification.attempts[0]
    result = fixture["store"].values[first.engine_result_ref]
    changed = replace(
        result.artifact,
        trace=replace(
            result.artifact.trace,
            entries=(
                replace(
                    result.artifact.trace.entries[0],
                    evidence_hash=canonical_sha256({"tampered": True}),
                ),
                *result.artifact.trace.entries[1:],
            ),
        ),
    )
    fixture["store"].values[first.engine_result_ref] = ArtifactReadResult(
        envelope=result.envelope,
        artifact=changed,
        source_bytes=result.source_bytes,
        source_hash=result.source_hash,
    )
    with pytest.raises(DurableRebuildError) as error:
        fixture["verifier"].verify(
            request=fixture["request"],
            resolved_request=fixture["resolved"],
            prepared_market_data=fixture["prepared"],
            execution_case=fixture["case"],
            attempts=fixture["attempts"],
        )
    assert error.value.code is DurableRebuildFailureCode.PROOF_CONSTRUCTION_FAILED


def test_structure_rejects_transitive_source_hash_mismatch(tmp_path: Path) -> None:
    fixture = _proof_fixture(tmp_path)
    verification = fixture["verification"]
    first = verification.attempts[0]
    manifest = fixture["store"].values[first.evidence_manifest_ref].artifact
    record_entry = next(
        entry
        for entry in manifest.artifacts
        if entry.role is EvidenceArtifactRole.ATTEMPT_EXECUTION_RECORD
    )
    record_ref = ArtifactRef(
        record_entry.artifact_type,
        record_entry.schema_version,
        record_entry.content_hash,
    )
    result = fixture["store"].values[record_ref]
    object.__setattr__(result, "source_hash", "sha256:" + "0" * 64)

    with pytest.raises(DurableRebuildError) as error:
        fixture["verifier"].verify(
            request=fixture["request"],
            resolved_request=fixture["resolved"],
            prepared_market_data=fixture["prepared"],
            execution_case=fixture["case"],
            attempts=fixture["attempts"],
        )
    assert error.value.code is DurableRebuildFailureCode.PROOF_CONSTRUCTION_FAILED


def test_constructor_bypass_rejects_self_consistent_g12d_layout_and_manifest_hash(
    tmp_path: Path,
) -> None:
    verification = _proof_fixture(tmp_path)["verification"]
    publication = dict(verification.market_bundle_publication)
    publication["manifest_relative_path"] = "bundles/wrong/manifest.json"
    publication["publication_hash"] = canonical_sha256(
        {key: value for key, value in publication.items() if key != "publication_hash"}
    )
    with pytest.raises(ValueError):
        replace(
            verification,
            market_bundle_publication=MappingProxyType(publication),
            market_bundle_publication_source_hash=durable._source_hash(
                canonical_bytes(publication)
            ),
        )

    retention = dict(verification.market_bundle_retention_proof)
    retention["manifest_source_hash"] = "sha256:" + "0" * 64
    retention["proof_hash"] = canonical_sha256(
        {key: value for key, value in retention.items() if key != "proof_hash"}
    )
    with pytest.raises(ValueError):
        replace(
            verification,
            market_bundle_retention_proof=MappingProxyType(retention),
            market_bundle_retention_source_hash=durable._source_hash(
                canonical_bytes(retention)
            ),
        )


def test_wire_catalog_is_private_and_artifact_round_trips(tmp_path: Path) -> None:
    verification = _proof_fixture(tmp_path)["verification"]
    written = _ARTIFACT_CATALOG.write_current(
        "deterministic_rebuild_verification", verification
    )
    read = _ARTIFACT_CATALOG.read(written.source_bytes)
    assert type(read.artifact) is DeterministicRebuildVerificationV1
    assert read.artifact == verification
    import crypto_quant_backtest

    assert not hasattr(crypto_quant_backtest, "DurableRebuildVerifierV1")
    assert "DurableRebuildVerifierV1" not in crypto_quant_backtest.__all__


_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "runtime"
    / "durable_rebuild"
    / "deterministic-rebuild-verification-v1.json"
)
_FIXTURE_SHA = (
    "33f262070a59ce52a350b99dcffdd9548a0643755690beeda9afffbada20aad7"
)


def test_golden_fixture_canonical_bytes_and_decode(tmp_path: Path) -> None:
    import hashlib

    fixture_bytes = _FIXTURE_PATH.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == _FIXTURE_SHA

    verification = _proof_fixture(tmp_path)["verification"]
    assert canonical_bytes(verification) == fixture_bytes

    decoded = _read_verification(json.loads(fixture_bytes))
    assert decoded == verification


def test_golden_fixture_is_deterministic_across_roots(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    verification_a = _proof_fixture(root_a)["verification"]
    verification_b = _proof_fixture(root_b)["verification"]
    assert canonical_bytes(verification_a) == canonical_bytes(verification_b)
