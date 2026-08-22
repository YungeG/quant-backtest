from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import crypto_quant_backtest.facade as facade_module
import crypto_quant_backtest.runner as runner_module
import pytest
from crypto_quant_backtest import (
    AttemptEvidenceWriter,
    AttemptIdentity,
    AuditableBacktestRunner,
    BacktestAnalysisRuntime,
    BacktestCanonicalPublicationRefV2,
    BacktestEvidenceError,
    BacktestEvidenceFailureCode,
    BacktestEvidenceRepository,
    BacktestProfileRegistry,
    BacktestRuntime,
    DeterministicBarEngine,
    ExecutionCaseComposer,
    InputOrigin,
    ProfileResolver,
    RequestedResultGrade,
)
from crypto_quant_backtest.composition import (
    _compose_execution_case_v3,
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from crypto_quant_backtest.engine import ExecutionCaseIdentityFactory
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
    ArtifactNotFoundError,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import LocalMarketBundleReader

from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.runtime.execution_inputs.test_multi_resolution_bundle_v3 import _contract
from tests.runtime.resolution._fixtures import profile_registry


class _Store:
    def __init__(self) -> None:
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}
        self.puts = 0

    def put_exact(
        self, artifact_type: str, artifact: object, schema_version: int = 1
    ) -> ArtifactRef:
        envelope = ArtifactEnvelope.create(artifact_type, schema_version, artifact)
        ref = ArtifactRef.from_envelope(envelope)
        source = canonical_bytes(envelope)
        self.values[ref] = ArtifactReadResult(
            envelope=envelope,
            artifact=artifact,
            source_bytes=source,
            source_hash=canonical_sha256(envelope),
        )
        return ref

    def put_input(self, envelope: ArtifactEnvelope) -> ArtifactRef:
        decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope))
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = decoded
        return ref

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        self.puts += 1
        ref = ArtifactRef.from_envelope(envelope)
        if ref not in self.values:
            source = canonical_bytes(envelope)
            self.values[ref] = ArtifactReadResult(
                envelope=envelope,
                artifact=object(),
                source_bytes=source,
                source_hash=canonical_sha256(envelope),
            )
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        try:
            return self.values[ref]
        except KeyError as error:
            raise ArtifactNotFoundError(ref.content_hash) from error


def _decision_registry(
    prepared, *, limitations: tuple[str, ...] = ()
) -> BacktestProfileRegistry:
    base = profile_registry(
        extra_market_capabilities=tuple(
            capability
            for capability in prepared.verified_reader.manifest.capabilities
            if capability.key == "price_bars"
        )
    )
    return BacktestProfileRegistry(
        market_semantics_profiles=tuple(
            replace(
                value,
                grade=RequestedResultGrade.DECISION_GRADE,
                limitations=limitations,
                decision_grade_eligible=True,
            )
            for value in base.market_semantics_profiles
        ),
        simulation_profiles=tuple(
            replace(
                value,
                grade=RequestedResultGrade.DECISION_GRADE,
                limitations=(),
                decision_grade_eligible=True,
            )
            for value in base.simulation_profiles
        ),
        execution_account_profiles=tuple(
            replace(
                value,
                grade=RequestedResultGrade.DECISION_GRADE,
                limitations=(),
                decision_grade_eligible=True,
            )
            for value in base.execution_account_profiles
        ),
    )


def _journey_values(*, limitations: tuple[str, ...] = ()):
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
    registry = _decision_registry(prepared, limitations=limitations)
    request_value = replace(
        resolved.request,
        execution_case_semantic_hash=spec.semantic_spec_hash,
        result_grade_requested=RequestedResultGrade.DECISION_GRADE,
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


def _local_reader(root: Path, reader) -> LocalMarketBundleReader:
    result = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=reader.manifest,
        stream_payloads={
            key: canonical_bytes(events) for key, events in reader.streams.items()
        },
        retention_policy_ref="retention.local-market-bundle-repository-v1",
    )
    assert result.result is not None
    return LocalMarketBundleReader.open(
        repository_root=root.resolve(), bundle_ref=result.result.bundle_ref
    )


def _seed_attempt_graph(store: _Store, root: Path, values) -> None:
    prepared, resolved, case, envelope, _, _ = values
    store.put_input(envelope)
    runner = AuditableBacktestRunner(
        engine=DeterministicBarEngine(), publication_root=root
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
        cancellation=None,
    )
    writer = AttemptEvidenceWriter(root=root)
    publications = (writer.publish(first), writer.publish(second))
    records = (first, second)
    for record, publication in zip(records, publications, strict=True):
        assert publication.finalized is not None
        store.put_exact("evidence_manifest", publication.finalized.manifest)
        store.put_exact("backtest_request", resolved.request)
        store.put_exact("resolved_backtest_environment", resolved.environment)
        store.put_exact("build_artifact_manifest", resolved.build_artifact_manifest)
        store.put_exact("market_bundle_ref", resolved.environment.market_bundle_ref)
        store.put_exact(
            "environment_compatibility_report",
            resolved.environment.compatibility_report,
        )
        store.put_exact("attempt_execution_record", record)
        assert record.ready_to_finalize is not None
        store.put_exact(
            "engine_execution_result", record.ready_to_finalize.engine_result
        )
    return records, tuple(value.finalized for value in publications)


def test_decision_grade_durable_journey_repository_analysis_and_cache(
    tmp_path: Path,
) -> None:
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    local = _local_reader(tmp_path / "market", prepared.verified_reader)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=local,
        publication_root=tmp_path / "publication",
    )

    publication_ref = runtime.run(request)
    assert type(publication_ref) is BacktestCanonicalPublicationRefV2
    completed = BacktestEvidenceRepository(store).load_completed_v3(publication_ref)
    analysis_runtime = BacktestAnalysisRuntime(store)
    metric_ref = analysis_runtime.publish_metric_profile()
    analysis_ref = analysis_runtime.derive(completed, metric_ref)
    loaded_analysis = BacktestEvidenceRepository(store).load_analysis_v2(analysis_ref)
    assert loaded_analysis.source_publication_ref == publication_ref
    assert loaded_analysis.source_execution_result_hash == (
        completed.source_execution_result_hash
    )

    before = store.puts
    assert runtime.run(request) == publication_ref
    assert store.puts == before


def test_canonical_v3_cache_rejects_local_proof_mutation(tmp_path: Path) -> None:
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    publication_root = tmp_path / "publication"
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=publication_root,
    )
    runtime.run(request)
    proof_file = next(
        (publication_root / "runs").glob(
            "run_*/rebuild-proofs/proof_*/verification.json"
        )
    )
    proof_file.chmod(0o644)

    with pytest.raises(RuntimeError, match="cache_local_proof_mismatch"):
        runtime.run(request)


def test_canonical_v3_cache_rejects_missing_static_graph(tmp_path: Path) -> None:
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    )
    publication_ref = runtime.run(request)
    assert type(publication_ref) is BacktestCanonicalPublicationRefV2
    del store.values[publication_ref.artifact_ref]

    with pytest.raises(RuntimeError, match="cache_static_graph_mismatch"):
        runtime.run(request)


def test_successful_body_with_lock_release_failure_returns_no_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    )
    original = facade_module.RunPublicationLock.__exit__

    def fail_release(self, exc_type, exc_value, traceback) -> None:
        original(self, exc_type, exc_value, traceback)
        self.release_error = OSError("injected")

    monkeypatch.setattr(
        facade_module.RunPublicationLock,
        "__exit__",
        fail_release,
    )
    with pytest.raises(RuntimeError, match="run_lock_unavailable"):
        runtime.run(request)


def test_canonical_v3_cache_fsyncs_proof_and_canonical_finals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    )
    publication_ref = runtime.run(request)
    calls: list[str] = []
    original = runner_module.fsync_directory

    def fsync(path: Path) -> None:
        calls.append(path.name)
        original(path)

    monkeypatch.setattr(runner_module, "fsync_directory", fsync)
    assert runtime.run(request) == publication_ref
    assert calls[0].startswith("proof_")
    assert calls[1] == "rebuild-proofs"
    assert calls[2] == "canonical-v3"
    assert calls[3].startswith("run_")


def test_canonical_v3_cache_fsync_failure_is_local_proof_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    )
    runtime.run(request)
    monkeypatch.setattr(
        runner_module,
        "fsync_directory",
        lambda path: (_ for _ in ()).throw(OSError("injected")),
    )

    with pytest.raises(RuntimeError, match="cache_local_proof_mismatch"):
        runtime.run(request)


def _manifest_entry(payload: dict[str, object], path: str) -> dict[str, object]:
    return next(
        value
        for value in payload["artifacts"]  # type: ignore[union-attr]
        if value["relative_path"] == path
    )


def _rewrite_terminal_context_outcome(store: _Store, ref: ArtifactRef) -> ArtifactRef:
    manifest_envelope = json.loads(store.values[ref].source_bytes)
    manifest_payload = manifest_envelope["payload"]
    integrity_entry = _manifest_entry(manifest_payload, "integrity.json")
    integrity_ref = ArtifactRef(
        integrity_entry["artifact_type"],
        integrity_entry["schema_version"],
        integrity_entry["content_hash"],
    )
    integrity_envelope = json.loads(store.values[integrity_ref].source_bytes)
    integrity_payload = integrity_envelope["payload"]
    integrity_payload["context"]["comparison_outcome"] = "mismatch"
    integrity_payload["context_hash"] = canonical_sha256(
        integrity_payload["context"]
    )
    new_integrity_envelope = ArtifactEnvelope.create(
        "integrity_report", 2, integrity_payload
    )
    new_integrity_ref = store.put(envelope=new_integrity_envelope)

    outcome_entry = _manifest_entry(manifest_payload, "evaluation-outcome.json")
    outcome_ref = ArtifactRef(
        outcome_entry["artifact_type"],
        outcome_entry["schema_version"],
        outcome_entry["content_hash"],
    )
    outcome_envelope = json.loads(store.values[outcome_ref].source_bytes)
    outcome_payload = outcome_envelope["payload"]
    outcome_payload["integrity_report_hash"] = canonical_sha256(integrity_payload)
    outcome_payload["evaluation_id"] = "evaluation_" + canonical_sha256(
        {
            "type": "integrity_evaluation_identity_v2",
            "semantic_run_id": outcome_payload["semantic_run_id"],
            "integrity_report_hash": outcome_payload["integrity_report_hash"],
            "outcome": outcome_payload["outcome"],
        }
    ).removeprefix("sha256:")
    new_outcome_envelope = ArtifactEnvelope.create(
        "integrity_evaluation_record", 2, outcome_payload
    )
    new_outcome_ref = store.put(envelope=new_outcome_envelope)

    for entry, envelope, child_ref in (
        (integrity_entry, new_integrity_envelope, new_integrity_ref),
        (outcome_entry, new_outcome_envelope, new_outcome_ref),
    ):
        source = canonical_bytes(envelope)
        entry["content_hash"] = child_ref.content_hash
        entry["source_hash"] = canonical_sha256(envelope)
        entry["byte_count"] = len(source)
    manifest_payload["publication_id"] = outcome_payload["evaluation_id"]
    return store.put(
        envelope=ArtifactEnvelope.create(
            "canonical_publication_manifest", 2, manifest_payload
        )
    )


def test_terminal_v2_rejects_context_outcome_that_disagrees_with_proof(
    tmp_path: Path,
) -> None:
    values = _journey_values(limitations=("test_local_source_limitation",))
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    )
    ref = runtime.run(request)
    assert type(ref) is ArtifactRef
    tampered = _rewrite_terminal_context_outcome(store, ref)

    with pytest.raises(BacktestEvidenceError) as error:
        BacktestEvidenceRepository(store).load_terminal(tampered)

    assert error.value.code is BacktestEvidenceFailureCode.PORT_STATIC_PROOF_MISMATCH


def test_reachable_decision_grade_limitation_publishes_blocked_v2(
    tmp_path: Path,
) -> None:
    values = _journey_values(limitations=("test_local_source_limitation",))
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    )

    ref = runtime.run(request)
    assert type(ref) is ArtifactRef
    assert ref.artifact_type == "canonical_publication_manifest"
    assert ref.schema_version == 2
    terminal = BacktestEvidenceRepository(store).load_terminal(ref)
    assert terminal.status.value == "BLOCKED"
