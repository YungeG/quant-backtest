from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    AnalysisArtifactRefV2,
    BacktestAnalysisRuntime,
    BacktestCanonicalPublicationRefV2,
    BacktestEvidenceRepository,
    BacktestExecutionRequest,
    BacktestRuntime,
    EngineCancellationRequest,
    ModelRequestBinding,
    RequestedResultGrade,
)
from crypto_quant_backtest.composition import _HydratedExecutionCaseInputs
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG,
    _DecodedExecutionInputBundleV3,
    _materialize_execution_input_bundle_v4,
)
from crypto_quant_domain import ArtifactRef, canonical_bytes

from tests.runtime.test_durable_rebuild_facade import (
    _journey_values,
    _local_reader,
    _seed_attempt_graph,
    _Store,
)


def _v4_values(model_binding: ModelRequestBinding | None = None):
    values = _journey_values(model_binding=model_binding)
    _, resolved, case, v3_envelope, _, registry = values
    decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(v3_envelope)).artifact
    assert type(decoded) is _DecodedExecutionInputBundleV3
    hydrated = _HydratedExecutionCaseInputs(
        decoded.execution_case_semantic_spec,
        decoded.timeline_stream_keys,
        case.target_stream,
        decoded.timeline_batch_size,
        decoded.execution_case_plan,
    )
    envelope = _materialize_execution_input_bundle_v4(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=decoded.market_data_preparation,
    )
    request = BacktestExecutionRequest(
        4,
        resolved.request,
        ArtifactRef.from_envelope(envelope),
    )
    return values, envelope, request, registry


def _runtime(tmp_path: Path, values, envelope, registry):
    prepared = values[0]
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    store.put(envelope=envelope)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    )
    return store, runtime


def test_schema4_uses_existing_durable_proof_canonical_v3_and_analysis(
    tmp_path: Path,
) -> None:
    values, envelope, request, registry = _v4_values()
    store, runtime = _runtime(tmp_path, values, envelope, registry)

    publication_ref = runtime.run(request)
    assert type(publication_ref) is BacktestCanonicalPublicationRefV2
    completed = BacktestEvidenceRepository(store).load_completed_v3(publication_ref)
    assert completed.source_publication_ref == publication_ref
    analysis_runtime = BacktestAnalysisRuntime(store)
    metric_ref = analysis_runtime.publish_metric_profile()
    analysis_ref = analysis_runtime.derive(completed, metric_ref)
    assert type(analysis_ref) is AnalysisArtifactRefV2
    analysis = BacktestEvidenceRepository(store).load_analysis_v2(analysis_ref)
    assert analysis.source_publication_ref == publication_ref
    assert analysis.source_execution_result_hash == completed.source_execution_result_hash

    before = store.puts
    assert runtime.run(request) == publication_ref
    assert store.puts == before


def test_schema4_model_binding_survives_proof_repository_and_cache_replay(
    tmp_path: Path,
) -> None:
    binding = ModelRequestBinding(
        strategy_id="durable-v3-model-bound-strategy",
        input_name="primary_model",
        model_key="alpha.primary",
        timeline_hash="sha256:" + "1" * 64,
        artifact_ref_hash="sha256:" + "2" * 64,
    )
    values, envelope, request, registry = _v4_values(binding)
    store, runtime = _runtime(tmp_path, values, envelope, registry)

    publication_ref = runtime.run(request)
    repository = BacktestEvidenceRepository(store)
    completed = repository.load_completed_v3(publication_ref)
    rich = repository.load_completed_evidence_v3(publication_ref)

    assert request.request.model_binding == binding
    assert completed.engine_context.model_binding == binding
    assert rich.resolved_request.request.model_binding == binding
    assert rich.completed.engine_context.model_binding == binding
    before = store.puts
    assert runtime.run(request) == publication_ref
    assert store.puts == before


def test_schema4_off_durable_lane_fails_before_artifact_io(tmp_path: Path) -> None:
    values, envelope, request, registry = _v4_values()
    store, runtime = _runtime(tmp_path, values, envelope, registry)
    before = tuple(store.values)

    with pytest.raises(RuntimeError, match="malformed_execution_request"):
        runtime.run_with_cancellation(
            request,
            EngineCancellationRequest("never-read", "schema4-cancellation-forbidden"),
        )
    assert tuple(store.values) == before

    non_decision = BacktestExecutionRequest(
        4,
        replace(
            request.request,
            result_grade_requested=RequestedResultGrade.DEVELOPMENT,
        ),
        request.execution_input_bundle_ref,
    )
    with pytest.raises(RuntimeError, match="malformed_execution_request"):
        runtime.run(non_decision)
    assert tuple(store.values) == before

    class NoReadStore(_Store):
        def read(self, *, ref: ArtifactRef):
            raise AssertionError(f"schema4 non-Local lane read {ref}")

    no_read = NoReadStore()
    non_local = BacktestRuntime(
        registry=registry,
        artifact_reader=no_read,
        artifact_publisher=no_read,
        market_reader=values[0].verified_reader,
        publication_root=tmp_path / "non-local",
    )
    with pytest.raises(RuntimeError, match="malformed_execution_request"):
        non_local.run(request)
    assert no_read.puts == 0


def test_schema4_cache_rechecks_local_proof(tmp_path: Path) -> None:
    values, envelope, request, registry = _v4_values()
    _, runtime = _runtime(tmp_path, values, envelope, registry)
    publication_ref = runtime.run(request)
    assert type(publication_ref) is BacktestCanonicalPublicationRefV2
    proof_file = next(
        (tmp_path / "publication" / "runs").glob(
            "run_*/rebuild-proofs/proof_*/verification.json"
        )
    )
    proof_file.chmod(0o644)

    with pytest.raises(RuntimeError, match="cache_local_proof_mismatch"):
        runtime.run(request)
