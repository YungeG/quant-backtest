from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from crypto_quant_backtest import (
    BacktestAnalysisRuntime,
    BacktestMetricProfile,
    CanonicalResultPublisher,
    CompletedBacktestResultV2,
    EngineExecutionContext,
    ModelRequestBinding,
    VerifiedCompletedPublicationV2,
)
from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, canonical_bytes
from tests.runtime.integration._fixtures import completed_journey
from tests.runtime.integrity._fixtures import rebuild_evidence

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/runtime/bt-gap03-completed-publication-v2.json"
_FIXTURE_SHA256 = "71c3ff2bfa71ef07eb8d95e80914db35549a1ba53d5c1f1ddf447d7a6265916b"
_V1_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/runtime/integrity-canonical-result-publication-v1.json"
_V1_FIXTURE_SHA256 = "e2c160f990f52ea1e67ff81934411a9e32dac92ae7bb55feb52c1b67ae866586"


def _context(journey) -> EngineExecutionContext:
    case = journey.case
    assert case.identity_manifest is not None
    return EngineExecutionContext(
        semantic_run_id=journey.attempts.semantic_run_id,
        semantic_spec_hash=case.semantic_spec_hash,
        case_hash=case.case_hash,
        target_stream_digest=case.target_stream.target_stream_digest,
        identity_manifest_hash=case.identity_manifest.manifest_hash,
        financial_state=case.financial_state,
    )


def _publish_v2(root: Path):
    journey = completed_journey(root)
    outcome = CanonicalResultPublisher(root=root).publish_v2(
        resolved_request=journey.attempts.resolved_request,
        attempt_hashes=journey.attempts.attempt_hashes,
        finalized_attempts=journey.attempts.finalized_attempts,
        rebuild_evidence=rebuild_evidence(journey.attempts),
        engine_context=_context(journey),
    )
    assert outcome.finalized_result_v2 is not None
    return journey, outcome.finalized_result_v2


def test_contract_fixture_is_frozen_and_v1_fixture_is_unchanged() -> None:
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert sha256(_V1_FIXTURE.read_bytes()).hexdigest() == _V1_FIXTURE_SHA256
    fixture = json.loads(_FIXTURE.read_text())
    assert fixture["publication"]["manifest_schema_version"] == 1
    assert fixture["completed_result"]["schema_version"] == 2
    assert fixture["completed_result"]["additional_fields"] == [
        "engine_execution_context",
        "canonical_evidence_manifest_ref",
    ]


def test_v2_result_lives_under_v1_manifest_root_and_coexists_with_v1(tmp_path: Path) -> None:
    journey, finalized = _publish_v2(tmp_path)
    v1 = journey.publication.finalized_result
    assert v1 is not None
    assert v1.relative_directory.endswith("/canonical")
    assert finalized.relative_directory.endswith("/canonical-v2")
    assert (tmp_path / v1.relative_directory).is_dir()
    assert (tmp_path / finalized.relative_directory).is_dir()

    result_source = (tmp_path / finalized.relative_directory / "result.json").read_bytes()
    result_envelope = ArtifactEnvelope(**json.loads(result_source))
    assert result_envelope.schema_version == 2
    assert result_source == canonical_bytes(result_envelope)
    evidence_ref = result_envelope.payload["canonical_evidence_manifest_ref"]
    assert evidence_ref["artifact_type"] == "evidence_manifest"
    assert evidence_ref["schema_version"] == 1
    expected_evidence_ref = ArtifactRef.from_envelope(
        ArtifactEnvelope.create(
            "evidence_manifest",
            1,
            finalized.result.context.attempts.canonical_evidence.manifest,
        )
    )
    assert evidence_ref == expected_evidence_ref.to_canonical_dict()
    manifest_envelope = ArtifactEnvelope.create(
        "canonical_publication_manifest", 1, finalized.manifest
    )
    assert ArtifactRef.from_envelope(manifest_envelope).schema_version == 1
    assert {entry.relative_path: entry.schema_version for entry in finalized.manifest.artifacts} == {
        "canonical-attempt-ref.json": 1,
        "integrity.json": 1,
        "result.json": 2,
    }


def _model_binding() -> ModelRequestBinding:
    return ModelRequestBinding(
        strategy_id="integrity-model-binding-test",
        input_name="primary_model",
        model_key="alpha.primary",
        timeline_hash="sha256:" + "1" * 64,
        artifact_ref_hash="sha256:" + "2" * 64,
    )


def test_v2_context_tampering_is_rejected(tmp_path: Path) -> None:
    journey = completed_journey(tmp_path)
    v1 = journey.publication.finalized_result
    assert v1 is not None
    context = _context(journey)
    with pytest.raises(ValueError, match="case hash"):
        CompletedBacktestResultV2(
            context=v1.result.context,
            canonical_attempt_ref=v1.canonical_attempt_ref,
            integrity_report=v1.integrity_report,
            engine_context=replace(context, case_hash="sha256:" + "0" * 64),
        )
    with pytest.raises(TypeError, match="exact ResolvedFinancialState"):
        replace(context, financial_state=object())
    with pytest.raises(ValueError, match="model binding"):
        CompletedBacktestResultV2(
            context=v1.result.context,
            canonical_attempt_ref=v1.canonical_attempt_ref,
            integrity_report=v1.integrity_report,
            engine_context=replace(context, model_binding=_model_binding()),
        )


def test_v2_publication_rejects_model_binding_mismatch_before_canonical_files(
    tmp_path: Path,
) -> None:
    journey = completed_journey(tmp_path)
    publisher = CanonicalResultPublisher(root=tmp_path)
    with pytest.raises(ValueError, match="model binding"):
        publisher.publish_v2(
            resolved_request=journey.attempts.resolved_request,
            attempt_hashes=journey.attempts.attempt_hashes,
            finalized_attempts=journey.attempts.finalized_attempts,
            rebuild_evidence=rebuild_evidence(journey.attempts),
            engine_context=replace(_context(journey), model_binding=_model_binding()),
        )
    assert not (
        tmp_path
        / "runs"
        / journey.attempts.semantic_run_id
        / "canonical-v2"
    ).exists()


def test_v2_publication_and_ref_are_deterministic(tmp_path: Path) -> None:
    _, first = _publish_v2(tmp_path / "a")
    _, second = _publish_v2(tmp_path / "b")
    assert canonical_bytes(first.result) == canonical_bytes(second.result)
    assert canonical_bytes(first.manifest) == canonical_bytes(second.manifest)
    first_ref = ArtifactRef.from_envelope(
        ArtifactEnvelope.create("canonical_publication_manifest", 1, first.manifest)
    )
    second_ref = ArtifactRef.from_envelope(
        ArtifactEnvelope.create("canonical_publication_manifest", 1, second.manifest)
    )
    assert first_ref == second_ref


def test_analysis_accepts_the_explicit_v2_verified_value(tmp_path: Path) -> None:
    class Publisher:
        def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
            return ArtifactRef.from_envelope(envelope)

    _, finalized = _publish_v2(tmp_path)
    completed = VerifiedCompletedPublicationV2.from_finalized(finalized)
    profile = BacktestMetricProfile("simple_period_return.fill_count.v1", 1)
    profile_ref = ArtifactRef.from_envelope(
        ArtifactEnvelope.create("backtest_metric_profile", 1, profile)
    )
    result = BacktestAnalysisRuntime(Publisher()).derive(completed, profile_ref)
    assert result.artifact_ref.artifact_type == "backtest_analysis"
