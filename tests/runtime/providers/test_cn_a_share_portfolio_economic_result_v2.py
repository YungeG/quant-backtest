"""Cold V2 source/activation integrity, actual input9 and storage identity."""
from dataclasses import replace
import copy
import json

import pytest
import crypto_quant_domain as d
import crypto_quant_backtest as bt
from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import (
    _completed_children_v1, _verify_economic_native_result_v1, _artifact, _trace,
)
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import economic_prepared_case_v2
from tests.runtime.providers.test_cn_a_share_portfolio_economic_public_v2 import _cold_guards


def _raw(value):
    return json.loads(d.canonical_bytes(value))


@pytest.fixture(scope="module")
def completed_v2(tmp_path_factory):
    root = tmp_path_factory.mktemp("v2-cold-public")
    prepared, case, inputs, store, market = economic_prepared_case_v2(root)
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is bt.BacktestCanonicalPublicationRef
    _, _, _, engine = _completed_children_v1(store, ref)
    return prepared, case, inputs, store, market, ref, _raw(engine.payload)


def _rechain_result_v2(raw):
    """Recompute every changed financial envelope/witness/head/trace, never finances."""
    artifacts = raw["financial_artifacts"]
    for a in artifacts:
        env = d.ArtifactEnvelope.create(a["payload"]["artifact_type"], a["payload"]["schema_version"], a["payload"]["payload"])
        a["payload"] = _raw(env)
        a["result_hash"] = d.canonical_sha256(env)
    head = d.canonical_sha256(tuple(d.canonical_sha256(a) for a in sorted(
        (a for a in artifacts if a["role"] != "economic_attempt_witness"),
        key=lambda a: (_artifact(a).occurred_at, a["source_event_id"], a["role"]))))
    for a in artifacts:
        if a["role"] == "economic_attempt_witness":
            outer = a["payload"]["payload"]
            outer["economic_witness"]["checkpoint_head"] = head
            outer["economic_witness_hash"] = d.canonical_sha256(outer["economic_witness"])
            a["payload"] = _raw(d.ArtifactEnvelope.create(a["payload"]["artifact_type"], 2, outer))
            a["result_hash"] = d.canonical_sha256(a["payload"])
    ordered = sorted(artifacts, key=lambda a: (_artifact(a).occurred_at, a["source_event_id"], a["role"]))
    raw["trace"]["entries"] = [{"sequence": i, "stage": "financial_event", "instant": a["occurred_at"],
        "subject_id": a["source_event_id"], "evidence_hash": d.canonical_sha256(a)} for i, a in enumerate(ordered)]
    _trace(raw["trace"])
    return raw


def _rehash_publication_v2(store, publication, original, changed):
    """Rehash the finite recorded publication DAG so semantic rejection is non-vacuous."""
    values = [_raw(e) for e in store.values.values()]
    old_summary = {**original, "type": "canonical_execution_summary"}
    new_summary = {**changed, "type": "canonical_execution_summary"}
    for summary in (old_summary, new_summary):
        del summary["case_hash"], summary["target_stream_digest"]
    hashes = {d.canonical_sha256(original): d.canonical_sha256(changed),
        d.canonical_sha256(original["trace"]): d.canonical_sha256(changed["trace"]),
        d.canonical_sha256(old_summary): d.canonical_sha256(new_summary)}
    derived = []
    for e in values:
        if e["artifact_type"] == "evidence_manifest":
            m = e["payload"]
            record = next(v["payload"]["ready_to_finalize"] for v in values if v["artifact_type"] == "attempt_execution_record"
                and v["payload"]["ready_to_finalize"]["attempt"]["attempt_id"] == m["attempt_id"])
            derived.append({"type": "finalized_attempt_evidence", "schema_version": 1, "attempt": record["attempt"],
                "status": m["status"], "terminal_outcome": m["terminal_outcome"], "manifest_hash": m["manifest_hash"],
                "manifest_source_hash": d.canonical_sha256(e),
                "relative_directory": f"runs/{m['semantic_run_id']}/attempts/{m['attempt_id']}", "deployment_authorized": False})
    sizes = {}
    def transform(value):
        if type(value) is str:
            return hashes.get(value, value)
        if type(value) is list:
            result = [transform(v) for v in value]
        elif type(value) is dict:
            if value.get("type") == "engine_execution_result":
                return copy.deepcopy(changed)
            result = {k: transform(v) for k, v in value.items()}
            if "artifact_type" in value and "payload" in value and "content_hash" in value:
                result["content_hash"] = d.ArtifactEnvelope.create(result["artifact_type"], result["schema_version"], result["payload"]).content_hash
                if value["content_hash"] != result["content_hash"]:
                    hashes[value["content_hash"]] = result["content_hash"]
                sizes[d.canonical_sha256(value)] = len(d.canonical_bytes(result))
            if "byte_count" in value and value.get("source_hash") in sizes:
                result["byte_count"] = sizes[value["source_hash"]]
            if value.get("type") == "evidence_manifest_identity":
                identity = {k: v for k, v in result.items() if k != "manifest_hash"}
                result["manifest_hash"] = d.canonical_sha256(identity)
                hashes[value["manifest_hash"]] = result["manifest_hash"]
        else:
            return value
        before, after = d.canonical_sha256(value), d.canonical_sha256(result)
        if before != after:
            hashes[before] = after
        return result
    for _ in range(16):
        before = dict(hashes)
        transformed = [transform(e) for e in values]
        for value in derived:
            transform(value)
        if hashes == before:
            break
    else:
        raise AssertionError("finite publication DAG did not stabilize")
    clone = type(store)()
    for e in transformed:
        env = d.ArtifactEnvelope(e["artifact_type"], e["schema_version"], e["payload"], e["content_hash"])
        clone.put(envelope=env)
    root_hash = hashes.get(publication.artifact_ref.content_hash, publication.artifact_ref.content_hash)
    return clone, bt.BacktestCanonicalPublicationRef(d.ArtifactRef("canonical_publication_manifest", 1, root_hash))


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "phase", "phase_code", "sequence", "source_event", "source_hash",
    "retained_marks", "policy", "activation_marks", "source_clock", "missing_field", "signal_version"])
def test_v2_cold_rehashed_activation_tamper(completed_v2, monkeypatch, mutation):
    _, case, inputs, store, market, ref, original = completed_v2
    raw = copy.deepcopy(original)
    signal = next(a for a in raw["financial_artifacts"] if a["role"] == "economic_signal")
    activation = signal["payload"]["payload"]["activation"]
    if mutation == "omit":
        raw["financial_artifacts"].remove(signal)
        for name in ("decision_batches", "allocations", "approved_targets", "normalized_targets"):
            raw[name] = []
    elif mutation == "duplicate":
        raw["financial_artifacts"].append(copy.deepcopy(signal))
    elif mutation in ("phase", "phase_code", "sequence", "source_clock"):
        clock = activation["source_at"] if mutation == "source_clock" else activation["activation_at"]
        if mutation == "phase": clock["phase"]["rank"] = 31
        elif mutation == "phase_code": clock["phase"]["code"] = "wrong"
        else: clock["source_sequence"]["value"] += 1
    elif mutation == "source_event": activation["source_event_id"] += ".wrong"
    elif mutation == "missing_field": del activation["activation_marks_hash"]
    elif mutation == "signal_version": signal["payload"]["schema_version"] = 1
    else:
        key = {"source_hash": "source_event_hash", "retained_marks": "retained_signal_marks_hash",
            "policy": "activation_stale_policy_hash", "activation_marks": "activation_marks_hash"}[mutation]
        activation[key] = d.canonical_sha256({"false": mutation})
    raw = _rechain_result_v2(raw)
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        with pytest.raises(d.ArtifactIntegrityError, match="activation|role/component|prior activation|extra economic signal"):
            _verify_economic_native_result_v1(case=case, reader=store, result=raw)
    # The entire manifest graph is independently structurally accepted, then
    # the existing repository must reject the source-derived semantic forgery.
    forged_store, forged_ref = _rehash_publication_v2(store, ref, original, raw)
    repository = bt.BacktestEvidenceRepository(reader=forged_store)
    repository._load_completed_structural_v1(forged_ref)
    with monkeypatch.context() as cold:
        _cold_guards(cold, forged_store)
        with pytest.raises((d.ArtifactIntegrityError, bt.BacktestEvidenceError), match="activation|role/component|prior activation|extra economic signal"):
            repository.load_completed(forged_ref, economic_market_reader=market)


@pytest.mark.parametrize("mode", ["missing", "tampered"])
def test_v2_actual_input9_required_and_storage_exception_identity(completed_v2, monkeypatch, mode):
    prepared, case, inputs, store, market, ref, _ = completed_v2
    clone = type(store)()
    clone.values.update(store.values)
    input_ref = prepared.execution_request.execution_input_bundle_ref
    if mode == "missing": del clone.values[input_ref]
    else: clone.values[input_ref] = d.ArtifactEnvelope.create("backtest_execution_input_bundle", 9, {"tampered": True})
    repository = bt.BacktestEvidenceRepository(reader=clone)
    with monkeypatch.context() as cold:
        _cold_guards(cold, clone)
        with pytest.raises((d.ArtifactNotFoundError, d.ArtifactIntegrityError, bt.BacktestEvidenceError, ValueError)):
            repository.load_completed(ref, economic_market_reader=market)
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot
    _, failure = _read_execution_inputs_v9_from_snapshot(clone, prepared.execution_request)
    assert failure.code.value == ("execution_input_unavailable" if mode == "missing" else "execution_input_tampered")
    sentinel = PermissionError("actual input9 sentinel")
    read = store.read
    def broken(*, ref):
        if ref == input_ref: raise sentinel
        return read(ref=ref)
    with monkeypatch.context() as cold:
        cold.setattr(store, "read", broken)
        _cold_guards(cold, store)
        with pytest.raises(PermissionError) as caught:
            bt.BacktestEvidenceRepository(reader=store).load_completed(ref, economic_market_reader=market)
        assert caught.value is sentinel
        with pytest.raises(PermissionError) as caught:
            prepared.runtime.run(prepared.execution_request)
        assert caught.value is sentinel
