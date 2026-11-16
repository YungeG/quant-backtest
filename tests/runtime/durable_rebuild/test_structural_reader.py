"""Real input3/4 -> attempts/proof -> source-only cold readers; synthetic data only."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest
from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactNotFoundError, ArtifactReadResult, ArtifactRef,
    canonical_bytes, canonical_sha256,
)
from crypto_quant_backtest import BacktestRuntime, BacktestEvidenceRepository, BacktestAnalysisRuntime
from crypto_quant_backtest._durable_artifact_codec import (
    _DurableDecodeContext, _same_resolved_source_roots, decode_durable_artifact_source,
)
from crypto_quant_backtest._durable_rebuild import (
    _read_verification, _load_durable_decode_context, _validate_verification_structure,
)
from crypto_quant_backtest.engine import EngineExecutionResult, DeterministicBarEngine
from crypto_quant_backtest.resolution import BacktestProfileRegistry, _EvidenceProfileHeader
from tests.runtime.test_durable_rebuild_facade import _journey_values, _local_reader
from tests.runtime.test_durable_rebuild_facade_v4 import _v4_values


class PoisonArtifact:
    def __eq__(self, other):
        pytest.fail("provider artifact was compared")

    def to_canonical_dict(self):
        pytest.fail("provider artifact was serialized")


class StructuralStore:
    def __init__(self):
        self.sources = {}
        self.puts = 0

    def put(self, *, envelope):
        ref = ArtifactRef.from_envelope(envelope)
        source = canonical_bytes(envelope)
        if ref in self.sources:
            assert self.sources[ref] == source
        self.sources[ref] = source
        self.puts += 1
        return ref

    def read(self, *, ref):
        try:
            source = self.sources[ref]
        except KeyError as error:
            raise ArtifactNotFoundError(ref.content_hash) from error
        envelope = ArtifactEnvelope(**json.loads(source))
        return ArtifactReadResult(envelope=envelope, artifact=PoisonArtifact(),
            source_bytes=source, source_hash="sha256:" + hashlib.sha256(source).hexdigest())

    def copy(self):
        store = StructuralStore()
        store.sources = dict(self.sources)
        return store


@pytest.fixture(scope="module", params=(3, 4), ids=("input3", "input4"))
def generated(request, tmp_path_factory):
    root = tmp_path_factory.mktemp("structural" + str(request.param))
    if request.param == 3:
        values = _journey_values(with_unused_inputs=True)
        prepared, resolved, case, envelope, execution, registry = values
    else:
        values, envelope, execution, registry = _v4_values(with_unused_inputs=True)
        prepared, resolved, case = values[:3]
    store = StructuralStore()
    assert store.put(envelope=envelope) == execution.execution_input_bundle_ref
    runtime = BacktestRuntime(registry=registry, artifact_reader=store, artifact_publisher=store,
        market_reader=_local_reader(root / "market", prepared.verified_reader), publication_root=root / "published")
    publication = runtime.run(execution)
    assert type(publication) is not ArtifactRef, [json.loads(raw) for ref, raw in store.sources.items()
        if ref.artifact_type in {"blocked_run_report", "failure_report", "integrity_report"}]
    completed = BacktestEvidenceRepository(store).load_completed_v3(publication)
    source = store.read(ref=completed.rebuild_verification_ref)
    verification = _read_verification(source.envelope.payload)
    context = _load_durable_decode_context(verification, store)
    return store, publication, runtime, execution, resolved, case, verification, context


def test_from_input_structural_reader_reaches_lean_and_rich_cold_completion(generated, monkeypatch):
    store, publication, runtime, request, resolved, case, verification, context = generated
    puts = store.puts
    repository = BacktestEvidenceRepository(store)
    lean = repository.load_completed_v3(publication)
    rich = repository.load_completed_evidence_v3(publication)
    assert lean == rich.completed
    assert _same_resolved_source_roots(rich.resolved_request, resolved)
    assert canonical_bytes(rich.resolved_request) == canonical_bytes(resolved)
    assert rich.first_engine_result.case_hash == case.case_hash
    assert rich.first_engine_result.final_ledger_state.schema == context.ledger_schema
    registrations = context.ledger_schema.registrations
    unused = next(value for value in registrations if "unused-durable-context" in str(value.key))
    assert unused.scale.places == 3
    assert all(balance.key != unused.key for balance in rich.first_engine_result.final_ledger_state.position_balances)
    assert all(change.key != unused.key for entry in rich.first_engine_result.final_journal.entries for change in entry.balance_changes)
    assert all("unused-cold-market-state" in decision.applicability.envelope.allowed_market_state_keys
               for decision in rich.first_engine_result.slippage_decisions)
    assert isinstance(rich.resolved_request.environment.market_semantics.implementation, _EvidenceProfileHeader)
    assert store.puts == puts
    _validate_verification_structure(verification, store, context=context)
    with pytest.raises(TypeError, match="evidence-only"):
        rich.resolved_request.environment.market_semantics.implementation.build_financial_dispatcher()
    with pytest.raises(TypeError, match="evidence-only"):
        BacktestProfileRegistry((rich.resolved_request.environment.market_semantics,), (), ())
    def forbidden(*args, **kwargs):
        pytest.fail("cold/cache reader reran Engine")
    monkeypatch.setattr(DeterministicBarEngine, "run", forbidden)
    assert runtime.run(request) == publication
    assert store.puts == puts
    # Analysis is an explicit allowed publication, not part of readonly cold/cache assertions.
    analysis = BacktestAnalysisRuntime(store)
    metric = analysis.publish_metric_profile()
    result = repository.load_analysis_v2(analysis.derive(lean, metric))
    assert result.source_execution_result_hash == lean.source_execution_result_hash


def _engine_source(generated):
    store, _, _, _, _, _, verification, context = generated
    ref = verification.attempts[0].engine_result_ref
    return ref, store.read(ref=ref), context


def _changed_source(source, payload):
    envelope = ArtifactEnvelope.create(source.envelope.artifact_type, source.envelope.schema_version, payload)
    return ArtifactRef.from_envelope(envelope), ArtifactReadResult(envelope=envelope, artifact=PoisonArtifact(),
        source_bytes=canonical_bytes(envelope), source_hash=canonical_sha256(envelope))


@pytest.mark.parametrize("mutation", ("schema_hash", "envelope_hash", "market_hash", "dimensions", "bool_dimension",
                                      "applicable", "snapshot", "run_end", "trace", "extra", "schema_bool"))
def test_codec_rejects_nested_tamper_without_reexecuting(generated, mutation, monkeypatch):
    _, source, context = _engine_source(generated)
    payload = json.loads(canonical_bytes(source.envelope.payload))
    if mutation == "schema_hash":
        payload["final_ledger_state"]["schema_hash"] = "sha256:" + "f" * 64
    elif mutation in {"envelope_hash", "market_hash", "dimensions", "bool_dimension", "applicable"}:
        value = payload["slippage_decisions"][0]["applicability"]
        if mutation == "envelope_hash": value["envelope_hash"] = "sha256:" + "f" * 64
        elif mutation == "market_hash": value["market_state_hash"] = "sha256:" + "f" * 64
        elif mutation == "dimensions": value["checked_dimensions"].reverse()
        elif mutation == "bool_dimension": value["checked_dimensions"][0] = True
        else: value["applicable"] = False
    elif mutation == "snapshot": payload["final_portfolio_snapshot"]["journal_state_hash"] = "sha256:" + "f" * 64
    elif mutation == "run_end": payload["run_end_report"]["final_snapshot_hash"] = "sha256:" + "f" * 64
    elif mutation == "trace": payload["trace"]["entries"][0]["sequence"] = -1
    elif mutation == "extra": payload["unknown"] = True
    else: payload["schema_version"] = True
    ref, changed = _changed_source(source, payload)
    monkeypatch.setattr(DeterministicBarEngine, "run", lambda *a, **k: pytest.fail("decoder executed Engine"))
    with pytest.raises((ValueError, TypeError)):
        decode_durable_artifact_source(changed, ref, EngineExecutionResult, context=context)


@pytest.mark.parametrize("mutation", ("missing", "empty_envelopes", "wrong_schema", "foreign_run", "foreign_input", "wrong_source_hash"))
def test_context_cannot_replace_original_input_roots(generated, mutation):
    store, _, _, _, _, _, verification, context = generated
    if mutation == "missing":
        ref, source, _ = _engine_source(generated)
        with pytest.raises(TypeError): decode_durable_artifact_source(source, ref, EngineExecutionResult)
        return
    if mutation == "empty_envelopes": context = replace(context, slippage_envelopes=())
    elif mutation == "wrong_schema":
        import crypto_quant_trading as t
        context = replace(context, ledger_schema=t.LedgerSchema(tuple(reg for reg in context.ledger_schema.registrations
                               if "unused-durable-context" not in str(reg.key))))
    elif mutation == "foreign_run": context = replace(context, semantic_run_id="run_" + "0" * 64)
    elif mutation == "foreign_input": context = replace(context, execution_input_ref=ArtifactRef("backtest_execution_input_bundle", context.execution_input_ref.schema_version, "sha256:" + "0" * 64))
    else: context = replace(context, execution_input_source_hash="sha256:" + "0" * 64)
    with pytest.raises((ValueError, TypeError)):
        _validate_verification_structure(verification, store, context=context)


def test_duplicate_context_envelope_is_not_an_authorization(generated):
    context = generated[-1]
    with pytest.raises(ValueError):
        replace(context, slippage_envelopes=context.slippage_envelopes * 2)


@pytest.mark.parametrize("mutation", ("absent", "hash"))
def test_cold_lean_rich_and_cache_reject_missing_or_changed_input(generated, mutation, monkeypatch):
    store, publication, runtime, request, _, _, verification, _ = generated
    copy = store.copy()
    ref = request.execution_input_bundle_ref
    if mutation == "absent": del copy.sources[ref]
    else: copy.sources[ref] += b" "
    for operation in ("load_completed_v3", "load_completed_evidence_v3"):
        with pytest.raises(Exception) as caught:
            getattr(BacktestEvidenceRepository(copy), operation)(publication)
        assert getattr(caught.value, "code", None) is not None
    from crypto_quant_backtest._durable_rebuild import DurableRebuildPublisherV1
    completed = BacktestEvidenceRepository(store).load_completed_v3(publication)
    proof_ref = completed.proof_publication_manifest_ref
    proof_payload = json.loads(store.sources[proof_ref])["payload"]
    directory = runtime._publication_root / "runs" / verification.semantic_run_id / "rebuild-proofs" / proof_payload["proof_id"]
    expected = (store.sources[completed.rebuild_verification_ref], store.sources[proof_ref])
    with pytest.raises((ValueError, TypeError)):
        DurableRebuildPublisherV1(root=runtime._publication_root, artifact_reader=copy)._read_directory(
            directory, expected, require_read_only=True)
    with monkeypatch.context() as missing:
        missing.setattr(store, "sources", copy.sources)
        missing.setattr(DeterministicBarEngine, "run", lambda *a, **k: pytest.fail("cache rebuilt missing evidence"))
        with pytest.raises(Exception) as caught:
            runtime.run(request)
        # The existing facade input-source gate can reject before cache graph
        # validation; do not weaken or relabel its original failure precedence.
        assert any(code in str(caught.value).lower() for code in
                   ("execution_input_unavailable", "execution_input_tampered", "cache_static_graph_mismatch"))


@pytest.mark.parametrize("mutation", ("duplicate", "float", "nan", "bool_version", "unknown_header", "wrong_source_hash", "wrong_ref"))
def test_strict_source_grammar_ignores_provider_artifact(generated, mutation):
    ref, source, context = _engine_source(generated)
    raw = source.source_bytes
    if mutation == "duplicate": raw = raw.replace(b'{"artifact_type":', b'{"schema_version":1,"artifact_type":', 1)
    elif mutation == "float": raw = raw.replace(b'"schema_version":1', b'"schema_version":1.0', 1)
    elif mutation == "nan": raw = raw.replace(b'"schema_version":1', b'"schema_version":NaN', 1)
    elif mutation == "bool_version": raw = raw.replace(b'"schema_version":1', b'"schema_version":true', 1)
    elif mutation == "unknown_header": raw = raw.replace(b'{"artifact_type":', b'{"unexpected":0,"artifact_type":', 1)
    elif mutation == "wrong_ref": ref = ArtifactRef("engine_execution_result", 1, "sha256:" + "0" * 64)
    with pytest.raises((ValueError, TypeError)):
        # The native source constructor may reject first. Never bypass it with
        # object.__new__ merely to smuggle impossible bytes to the codec.
        changed = replace(source, source_bytes=raw, source_hash=("sha256:" + "0" * 64 if mutation == "wrong_source_hash" else "sha256:" + hashlib.sha256(raw).hexdigest()))
        decode_durable_artifact_source(changed, ref, EngineExecutionResult, context=context)


def test_full_build_provenance_and_all_profile_headers_remain_bound(generated):
    from crypto_quant_backtest._durable_artifact_codec import _context_from_verified_inputs
    from crypto_quant_backtest.execution_inputs import _EXECUTION_INPUT_CATALOG
    store, publication, _, request, live, _, verification, context = generated
    changed_build = replace(context.build_artifact_manifest,
                            provenance=replace(context.build_artifact_manifest.provenance, hostname="different-evidence-host"))
    assert changed_build.manifest_hash == context.build_artifact_manifest.manifest_hash
    assert not _same_resolved_source_roots(replace(live, build_artifact_manifest=changed_build), live)
    with pytest.raises(ValueError):
        _validate_verification_structure(verification, store, context=replace(context, build_artifact_manifest=changed_build))
    source = store.read(ref=request.execution_input_bundle_ref)
    decoded = _EXECUTION_INPUT_CATALOG.read(source.source_bytes).artifact
    with pytest.raises(ValueError):
        _context_from_verified_inputs(source, decoded, request, changed_build, context.semantic_run_id)
    cold = BacktestEvidenceRepository(store).load_completed_evidence_v3(publication).resolved_request.environment
    for fields in ({"simulation_profiles": (cold.simulation,)}, {"execution_account_profiles": (cold.execution_account,)}):
        with pytest.raises(TypeError, match="evidence-only"):
            BacktestProfileRegistry(**fields)


def test_terminal_proof_uses_the_same_original_input_context(tmp_path, monkeypatch):
    prepared, _, _, envelope, request, registry = _journey_values(
        limitations=("synthetic-decision-grade-limitation",), with_unused_inputs=True)
    store = StructuralStore()
    store.put(envelope=envelope)
    runtime = BacktestRuntime(registry=registry, artifact_reader=store, artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader), publication_root=tmp_path / "published")
    ref = runtime.run(request)
    assert type(ref) is ArtifactRef and ref.schema_version == 2
    before = store.puts
    monkeypatch.setattr(DeterministicBarEngine, "run", lambda *a, **k: pytest.fail("terminal cold reader reran Engine"))
    terminal = BacktestEvidenceRepository(store).load_terminal(ref)
    assert terminal.status.value == "BLOCKED" and store.puts == before
    copy = store.copy()
    del copy.sources[request.execution_input_bundle_ref]
    with pytest.raises(Exception) as caught:
        BacktestEvidenceRepository(copy).load_terminal(ref)
    assert getattr(caught.value, "code", None) is not None


def test_envelope_collection_empty_or_repeated_slots_is_not_graph_acceptance(generated):
    from crypto_quant_backtest._durable_artifact_codec import _input_envelopes
    from crypto_quant_backtest.execution_inputs import _EXECUTION_INPUT_CATALOG
    store, _, _, request, _, _, _, context = generated
    decoded = _EXECUTION_INPUT_CATALOG.read(store.read(ref=request.execution_input_bundle_ref).source_bytes).artifact
    empty = replace(decoded, execution_case_plan=replace(decoded.execution_case_plan, bar_executions=()))
    repeated = replace(decoded, execution_case_plan=replace(decoded.execution_case_plan,
                       bar_executions=decoded.execution_case_plan.bar_executions * 2))
    assert _input_envelopes(empty) == ()
    assert _input_envelopes(repeated) == context.slippage_envelopes
    # Only normalization is asserted here: the modified plans are not published
    # or treated as accepted original input/run graphs.
