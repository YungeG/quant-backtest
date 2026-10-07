"""Input8 contract sentinels only: not the requested CN two-week A/B run."""
from dataclasses import dataclass, replace
import json

import pytest
import crypto_quant_backtest as bt
import crypto_quant_domain as d

from crypto_quant_backtest.composition import _compose_profile_portfolio_execution_case
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG, _DecodedExecutionInputBundleV8,
    _materialize_execution_input_bundle_v8, _read_execution_inputs_v8_from_snapshot,
)
from crypto_quant_backtest.profile_portfolio_execution import (
    _ProfilePortfolioExecutionPlanV1, _ResolvedProfilePortfolioCaseV1,
    _profile_portfolio_semantic_spec_from_case,
)
from tests.runtime.execution_inputs.test_live_execution_input_v7 import _Implementation, _prepared


@dataclass(frozen=True)
class _PortfolioImplementation(_Implementation):
    def to_canonical_dict(self):
        return {**super().to_canonical_dict(), "portfolio_contract_sentinel": 1}

    def build_portfolio_engine(self, *, case, artifact_reader):
        raise ValueError("contract sentinel has no economic engine")


def _fixture(tmp_path):
    old_runtime, old_transport, store, old_case = _prepared(tmp_path)
    old_spec = old_case.semantic_spec
    assert old_spec is not None
    assert isinstance(old_case.timeline, bt.DeterministicTimelineV2)
    definition = d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", 1,
        {"test_only": "contract sentinel", "policy": "frozen before request",
         "no_predicted_fills_or_quantities": True})
    plan = _ProfilePortfolioExecutionPlanV1(definition, old_case.financial_state)
    template = _ResolvedProfilePortfolioCaseV1("test.portfolio-native", 1,
        old_case.timeline, old_case.target_stream, old_case.timeline_batch_size,
        plan, d.canonical_sha256("unsealed"))
    spec = _profile_portfolio_semantic_spec_from_case(template,
        spec_key="test.portfolio-native", spec_version=1,
        identity_namespace=old_spec.identity_namespace, identity_plan=old_spec.identity_plan)
    base = old_runtime._registry
    registration = base.market_semantics_profiles[0]
    old = registration.implementation
    assert isinstance(old, _Implementation)
    impl = _PortfolioImplementation(old.kind, old.component_manifest,
        old.financial_dispatcher_spec, old.dispatcher_mode)
    registry = replace(base, market_semantics_profiles=(replace(registration,
        implementation=impl, profile_digest=impl.profile_digest),))
    decoded = _EXECUTION_INPUT_CATALOG.read(store.read(ref=old_transport.execution_input_bundle_ref).source_bytes).artifact
    manifest = replace(decoded.build_artifact_manifest,
        artifacts=tuple(replace(a, content_hash=impl.profile_digest)
            if a.artifact_key == registration.profile_key else a
            for a in decoded.build_artifact_manifest.artifacts))
    request = replace(old_transport.request, execution_case_semantic_hash=spec.semantic_spec_hash,
        build_artifact_manifest_hash=manifest.manifest_hash)
    resolution = bt.ProfileResolver().resolve(request=request, registry=registry,
        market_bundle_manifest=old_case.timeline.reader.manifest, build_artifact_manifest=manifest)
    assert resolution.resolved is not None
    resolved = resolution.resolved
    case = _compose_profile_portfolio_execution_case(resolved_request=resolved,
        market_reader=old_case.timeline.reader, semantic_spec=spec,
        target_stream=old_case.target_stream, timeline_stream_keys=old_case.timeline.stream_keys,
        timeline_batch_size=old_case.timeline_batch_size, execution_case_plan=plan)
    envelope = _materialize_execution_input_bundle_v8(resolved_request=resolved, execution_case=case)
    transport = bt.BacktestExecutionRequest(8, request, store.put(envelope=envelope))
    runtime = bt.BacktestRuntime(registry=registry, artifact_reader=store,
        artifact_publisher=store, market_reader=old_case.timeline.reader, publication_root=tmp_path)
    return runtime, transport, store, resolved, case, envelope


def test_input8_round_trip_reconstructs_same_definition_and_identity_slots(tmp_path):
    runtime, transport, store, resolved, case, envelope = _fixture(tmp_path)
    decoded = _EXECUTION_INPUT_CATALOG.read(d.canonical_bytes(envelope))
    assert type(decoded.artifact) is _DecodedExecutionInputBundleV8
    read, failure = _read_execution_inputs_v8_from_snapshot(store, transport)
    assert failure is None and read is not None
    rebuilt = _compose_profile_portfolio_execution_case(resolved_request=resolved,
        market_reader=case.timeline.reader, semantic_spec=read.execution_case_semantic_spec,
        target_stream=read.target_stream, timeline_stream_keys=read.timeline_stream_keys,
        timeline_batch_size=read.timeline_batch_size, execution_case_plan=read.execution_case_plan)
    assert rebuilt.case_hash == case.case_hash
    assert rebuilt.identity_manifest == case.identity_manifest
    assert rebuilt.verify_identity_manifest(resolved.semantic_run_id)
    # Definition has no request hash, transport input reference, future fill or quantity.
    assert "request_hash" not in json.dumps(dict(read.execution_case_plan.definition.payload))
    assert decoded.envelope == envelope


def test_input8_runtime_demands_registered_profile_engine_before_attempt_publication(tmp_path):
    runtime, transport, store, resolved, case, envelope = _fixture(tmp_path)
    before = set(store.values)
    with pytest.raises(RuntimeError, match="portfolio_profile_binding_mismatch"):
        runtime.run(transport)
    assert set(store.values) == before
    assert not (tmp_path / "runs" / resolved.semantic_run_id).exists()


def test_producer_transport_refs_change_input_bytes_not_economic_identity(tmp_path):
    runtime, transport, store, resolved, case, envelope = _fixture(tmp_path)
    assert case.semantic_spec is not None
    changed = replace(case, execution_case_plan=replace(case.execution_case_plan,
        source_refs=(("producer_context", d.ArtifactRef("producer_context", 1,
            d.canonical_sha256("independent-context"))),)))
    assert changed.case_hash == case.case_hash
    assert bt.ExecutionCaseComposer.semantic_spec_from_case(changed,
        spec_key=case.semantic_spec.spec_key, spec_version=1,
        identity_namespace=case.semantic_spec.identity_namespace,
        identity_plan=case.semantic_spec.identity_plan) == case.semantic_spec
    retained = _materialize_execution_input_bundle_v8(resolved_request=resolved, execution_case=changed)
    assert retained.content_hash != envelope.content_hash
    decoded = _EXECUTION_INPUT_CATALOG.read(d.canonical_bytes(retained)).artifact
    assert decoded.execution_case_plan.source_refs == changed.execution_case_plan.source_refs


@pytest.mark.parametrize("location", ["payload", "plan", "definition", "wrong_plan_version", "bad_definition_hash"])
def test_input8_rejects_unknown_fields_and_noncanonical_plan_before_execution(tmp_path, location):
    runtime, transport, store, resolved, case, envelope = _fixture(tmp_path)
    raw = json.loads(d.canonical_bytes(envelope))
    if location == "payload":
        raw["payload"]["extra"] = True
    elif location == "plan":
        raw["payload"]["execution_case_plan"]["extra"] = True
    elif location == "definition":
        raw["payload"]["execution_case_plan"]["definition"]["extra"] = True
    elif location == "wrong_plan_version":
        raw["payload"]["execution_case_plan"]["schema_version"] = 2
    else:
        raw["payload"]["execution_case_plan"]["definition"]["content_hash"] = d.canonical_sha256("wrong")
    mutated = d.ArtifactEnvelope.create(raw["artifact_type"], raw["schema_version"], raw["payload"])
    with pytest.raises(d.ArtifactCatalogError):
        _EXECUTION_INPUT_CATALOG.read(d.canonical_bytes(mutated))
    assert not (tmp_path / "runs" / resolved.semantic_run_id).exists()


def test_changed_economic_definition_cannot_reuse_request_or_identity_manifest(tmp_path):
    runtime, transport, store, resolved, case, envelope = _fixture(tmp_path)
    assert case.semantic_spec is not None
    changed_plan = replace(case.execution_case_plan,
        definition=d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", 1,
            {"policy": "different economic assumption"}))
    with pytest.raises(ValueError, match="does not match the semantic spec"):
        _compose_profile_portfolio_execution_case(resolved_request=resolved,
            market_reader=case.timeline.reader, semantic_spec=case.semantic_spec,
            target_stream=case.target_stream, timeline_stream_keys=case.timeline.stream_keys,
            timeline_batch_size=case.timeline_batch_size, execution_case_plan=changed_plan)
    foreign = replace(case, identity_manifest=None)
    assert not foreign.verify_identity_manifest(resolved.semantic_run_id)
    with pytest.raises(ValueError, match="identity seal"):
        _materialize_execution_input_bundle_v8(resolved_request=resolved, execution_case=foreign)


def test_profile_rejects_unowned_native_head_before_ready_or_canonical_publication(tmp_path, monkeypatch):
    runtime, transport, store, resolved, case, envelope = _fixture(tmp_path)
    # A borrowed *legacy* result is intentionally NOT an economic portfolio
    # result. It must never obtain a new portfolio completed publication.
    seed_runtime, seed_transport, seed_store, seed_case = _prepared(tmp_path / "legacy-seed")
    implementation = seed_runtime._registry.market_semantics_profiles[0].implementation
    assert isinstance(implementation, _Implementation)
    seed = bt.DeterministicBarEngine(implementation.build_financial_dispatcher()).run(seed_case)
    seed_result = seed.result
    assert seed_result is not None
    calls = []

    class RejectingEngine:
        def run(self, executed_case, *, cancellation=None):
            calls.append("run")
            return bt.EngineExecutionOutcome(result=replace(seed_result, case_hash=executed_case.case_hash))

        def verify_result(self, executed_case, result):
            calls.append("verify")
            raise ValueError("missing native model-account head and plan continuity")

        def verify_cached(self, executed_case, publication_ref):
            raise AssertionError("no completion exists to replay")

    monkeypatch.setattr(_PortfolioImplementation, "build_portfolio_engine",
        lambda self, **kwargs: RejectingEngine())
    publication = runtime.run(transport)
    assert type(publication) is d.ArtifactRef
    assert calls == ["run", "verify"]
    assert b'"portfolio_economic_evidence_invalid"' in b"\n".join(
        d.canonical_bytes(value) for value in store.values.values())
    assert not (tmp_path / "runs" / resolved.semantic_run_id / "canonical-v2").exists()
    assert not any(ref.artifact_type == "backtest_canonical_publication_manifest"
                   for ref in store.values)


def test_input8_request_hash_and_account_must_bind_the_registered_case(tmp_path):
    runtime, transport, store, resolved, case, envelope = _fixture(tmp_path)
    foreign_request = replace(transport.request, execution_account_id="foreign-account")
    changed = bt.BacktestExecutionRequest(8, foreign_request, transport.execution_input_bundle_ref)
    decoded, failure = _read_execution_inputs_v8_from_snapshot(store, changed)
    assert decoded is None and failure is not None
    assert failure.code.value == "request_binding_mismatch"
    registry = replace(runtime._registry, execution_account_profiles=(
        replace(runtime._registry.execution_account_profiles[0], account_id="foreign-account"),))
    resolution = bt.ProfileResolver().resolve(request=foreign_request, registry=registry,
        market_bundle_manifest=case.timeline.reader.manifest,
        build_artifact_manifest=resolved.build_artifact_manifest)
    assert resolution.resolved is not None
    with pytest.raises(ValueError, match="account/currency/development"):
        _materialize_execution_input_bundle_v8(resolved_request=resolution.resolved, execution_case=case)
