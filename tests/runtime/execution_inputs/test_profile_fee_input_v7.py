"""Actual CN fee policy binding through the unchanged #30 public Backtest seam."""
import json
from dataclasses import replace

import pytest

import crypto_quant_backtest as bt
import crypto_quant_domain as d

from tests.runtime.execution_inputs.test_live_execution_input_v7 import _prepared, _published_engine_payload


def test_v7_profile_fee_authority_is_hydrated_and_retained(tmp_path):
    runtime, transport, store, _ = _prepared(tmp_path, profile_fees=True)
    publication = runtime.run(transport)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    completed = bt.BacktestEvidenceRepository(store).load_completed(publication)
    snapshot = completed.execution_summary.final_portfolio_snapshot
    assert snapshot.fees.units == 8142
    assert snapshot.cash[0].amount.units == 9_991_858
    assert snapshot.positions == ()
    payload = _published_engine_payload(store, publication)
    rules = [row for row in payload["financial_artifacts"] if row["role"].startswith("fee_rules.")]
    assert len(rules) == 9
    actual_fills = {fill["fill_id"]["value"] for fill in payload["fills"]}
    final_queries = [row["payload"]["query"] for row in rules if row["payload"]["query"]["fill"] is not None]
    assert len(final_queries) == 4
    assert {query["fill"]["fill_id"]["value"] for query in final_queries} == actual_fills
    assert runtime.run(transport) == publication


@pytest.mark.parametrize("change", ("extra_order", "future_fill", "schema", "dispatcher"))
def test_v7_fee_binding_tampering_fails_before_attempt(tmp_path, change):
    runtime, transport, store, _ = _prepared(tmp_path, profile_fees=True)
    envelope = store.values[transport.execution_input_bundle_ref]
    payload = json.loads(d.canonical_bytes(envelope.payload))
    binding = payload["execution_case_plan"]["decision_cycles"][0]["admission_slot"]["pretrade_authority"]["fee_reservation_rule_set"]
    if change == "schema":
        binding["schema_version"] = 99
    elif change == "dispatcher":
        binding["dispatcher_spec_hash"] = "sha256:" + "0" * 64
    else:
        binding[change] = "forbidden_future_economic_value"
    changed = d.ArtifactEnvelope.create(envelope.artifact_type, envelope.schema_version, payload)
    transport = replace(transport, execution_input_bundle_ref=store.put(envelope=changed))
    with pytest.raises(RuntimeError, match="execution input"):
        runtime.run(transport)
    assert not (tmp_path / "runs").exists()
