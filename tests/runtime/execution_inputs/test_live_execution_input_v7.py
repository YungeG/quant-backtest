"""#30 public Backtest seam: real CN settlement, synthetic prices/fee rules.

This is a transport/runner sentinel, not retained-source strategy acceptance.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import json

import pytest

import crypto_quant_backtest as bt
import crypto_quant_domain as d
from crypto_quant_market_data import InMemoryMarketBundleReader, InputValidationFailure
from tests.runtime.engine.test_cn_a_share_live_settlement import cn_case, instant, profile
from tests.runtime.engine.test_live_execution_case import _respec
from tests.runtime.resolution._fixtures import build_manifest, profile_registry, request
from tests.runtime.target_stream.test_backtest_target_stream_execution import _Cas


@dataclass(frozen=True)
class _Implementation:
    kind: str
    component_manifest: tuple
    financial_dispatcher_spec: bt.FinancialDispatcherSpec | None = None
    dispatcher_mode: str = "cn"

    @property
    def profile_digest(self):
        return d.canonical_sha256(self)

    def to_canonical_dict(self):
        return {"type": "v7_test_profile", "kind": self.kind, "profile_hash": profile().profile_hash,
                "component_manifest": self.component_manifest, "financial_dispatcher_spec": self.financial_dispatcher_spec,
                "dispatcher_mode": self.dispatcher_mode}

    def build_financial_dispatcher(self):
        if self.dispatcher_mode == "raises":
            raise ValueError("private provider details must be redacted")
        if self.dispatcher_mode == "wrong":
            return bt.DefaultCashFinancialDispatcher()
        return bt.CnAShareDevelopmentFinancialDispatcherV2(profile(), closed_bar_execution=self.dispatcher_mode == "closed")


class _Builder:
    def __init__(self, combined_fees=False, profile_fees=False, closed_endpoint=None):
        self.combined_fees = combined_fees
        self.profile_fees = profile_fees
        self.closed_endpoint = closed_endpoint

    def make(self, identities=None):
        if self.closed_endpoint is not None:
            from tests.runtime.engine.test_cn_a_share_closed_receipts import closed_receipt_case
            case, _, _ = closed_receipt_case(*self.closed_endpoint, identity_factory=identities)
        elif self.profile_fees:
            from tests.runtime.engine.test_cn_a_share_profile_fee_runtime import profile_fee_case
            case, _ = profile_fee_case(identity_factory=identities)
        else:
            case, _ = cn_case(identity_factory=identities, synthetic_fees=True, combined_fees=self.combined_fees)
        old = case.timeline.reader
        [bar_stream] = [stream.stream_key for stream in old.manifest.streams if stream.capability == bt.BAR_CLOSE_CAPABILITY]
        cursor = old.open_cursor(bar_stream, batch_size=16)
        assert not isinstance(cursor, InputValidationFailure)
        bars, _ = old.read_batch(cursor)
        reader = InMemoryMarketBundleReader.build(bundle_key="v7-test.market-only", schema_version=1,
            coverage_start=case.timeline.window.data_start, coverage_end_exclusive=case.timeline.window.end_exclusive,
            instrument_catalog_hash=old.manifest.instrument_catalog_hash, capabilities=(bt.BAR_CLOSE_CAPABILITY,),
            streams={bar_stream: bars})
        timeline = bt.DeterministicTimelineV2.open(reader=reader, stream_keys=(bar_stream,),
            target_stream=case.target_stream, window=case.timeline.window)
        assert isinstance(timeline, bt.DeterministicTimelineV2)
        return _respec(replace(case, timeline=timeline))

    def semantic_spec(self):
        spec = self.make().semantic_spec
        assert spec is not None
        return spec

    def build(self, identities, semantic_spec_hash):
        case = self.make(identities)
        return replace(case, identity_manifest=None, semantic_spec=None, semantic_spec_hash=semantic_spec_hash)


def _prepared(tmp_path: Path, *, dispatcher_mode="cn", account_override=None, combined_fees=False, profile_fees=False, closed_endpoint=None):
    builder = _Builder(combined_fees, profile_fees, closed_endpoint)
    template = builder.make()
    spec = template.semantic_spec
    assert spec is not None
    dispatch = template.financial_dispatch_plan.dispatcher_spec
    base = profile_registry()
    market_base, simulation_base, account_base = base.market_semantics_profiles[0], base.simulation_profiles[0], base.execution_account_profiles[0]
    market_refs = {ref.port_type: ref for ref in market_base.component_manifest}
    for ref in (dispatch.position_accounting_component, dispatch.financing_component, dispatch.margin_component):
        market_refs[ref.port_type] = ref
    simulation_refs = {ref.port_type: ref for ref in simulation_base.component_manifest}
    for ref in (template.execution_model.component_ref, template.closeout_policy.spec().component_ref,
                template.bar_executions[0].slippage_model.component_ref, dispatch.liquidation_audit_component):
        simulation_refs[ref.port_type] = ref
    market = _Implementation("market", tuple(sorted(market_refs.values(), key=lambda ref: ref.port_type.value)), dispatch, dispatcher_mode)
    simulation = _Implementation("simulation", tuple(sorted(simulation_refs.values(), key=lambda ref: ref.port_type.value)))
    venue = profile().request.instrument_scope.instrument.instrument_id.venue.value
    registry = bt.BacktestProfileRegistry(
        (replace(market_base, implementation=market, profile_digest=market.profile_digest, venue_id=venue,
                 required_bundle_capabilities=(bt.BAR_CLOSE_CAPABILITY,), component_manifest=market.component_manifest,
                 financial_dispatcher_spec=dispatch),),
        (replace(simulation_base, implementation=simulation, profile_digest=simulation.profile_digest,
                 required_bundle_capabilities=(bt.BAR_CLOSE_CAPABILITY,), component_manifest=simulation.component_manifest),),
        (replace(account_base, account_id=account_override or profile().request.account_scope.account_id, venue_id=venue,
                 supported_reporting_currencies=(d.CurrencyId("CNY"),)),))
    manifest, reader = build_manifest(), template.timeline.reader
    profile_digests = {market_base.profile_key: market.profile_digest, simulation_base.profile_key: simulation.profile_digest}
    manifest = replace(manifest, artifacts=tuple(replace(artifact, content_hash=profile_digests[artifact.artifact_key])
        if artifact.artifact_key in profile_digests else artifact for artifact in manifest.artifacts))
    public = replace(request(manifest, bundle=reader.manifest), timeline_window=template.timeline.window,
        execution_account_id=account_override or profile().request.account_scope.account_id, reporting_currency=d.CurrencyId("CNY"),
        execution_case_semantic_hash=spec.semantic_spec_hash, target_stream_digest=spec.target_stream_digest)
    resolved = bt.ProfileResolver().resolve(request=public, registry=registry, market_bundle_manifest=reader.manifest,
        build_artifact_manifest=manifest)
    assert resolved.resolved is not None, d.canonical_bytes(resolved.failure).decode()
    case = bt.ExecutionCaseComposer().compose(resolved_request=resolved.resolved, builder=builder)
    envelope = bt.materialize_execution_input_bundle_v7(resolved_request=resolved.resolved, execution_case=case)
    store = _Cas()
    transport = bt.BacktestExecutionRequest(7, public, store.put(envelope=envelope))
    runtime = bt.BacktestRuntime(registry=registry, artifact_reader=store, artifact_publisher=store,
        market_reader=reader, publication_root=tmp_path)
    return runtime, transport, store, case


def _published_engine_payload(store, publication):
    manifest = store.read(ref=publication.to_artifact_ref()).envelope.payload
    assert manifest["deployment_authorized"] is False
    entry = next(row for row in manifest["artifacts"] if row["artifact_type"] == "canonical_attempt_ref")
    attempt = store.read(ref=d.ArtifactRef(entry["artifact_type"], entry["schema_version"], entry["content_hash"])).envelope.payload
    return store.read(ref=d.ArtifactRef("engine_execution_result", 1, attempt["engine_result_artifact_content_hash"])).envelope.payload


@pytest.mark.parametrize("combined_fees, fee_units", ((False, 12_500), (True, 22_500)))
def test_v7_public_run_reconstructs_live_cn_case_and_replays(tmp_path, combined_fees, fee_units):
    runtime, transport, store, case = _prepared(tmp_path, combined_fees=combined_fees)
    before = d.canonical_bytes(case)
    publication = runtime.run(transport)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    completed = bt.BacktestEvidenceRepository(store).load_completed(publication)
    summary = completed.execution_summary
    assert [(fill.side, fill.quantity.units, fill.execution_time) for fill in summary.fills] == [
        (d.OrderSide.BUY, 500, instant(2, 9, 40)), (d.OrderSide.SELL, 500, instant(3, 9, 40))]
    assert summary.final_portfolio_snapshot.positions == ()
    assert summary.final_portfolio_snapshot.cash[0].amount.units == 10_000_000 - fee_units
    assert summary.final_portfolio_snapshot.fees.units == fee_units
    assert completed.result_grade.value == "development"
    result = _published_engine_payload(store, publication)
    assert len(result["order_streams"]) == 2
    closure = next(row["payload"] for row in result["financial_artifacts"] if row["role"] == "runtime.identity_closure")
    dispositions = {row["binding_key"]: row for row in closure["dispositions"]}
    assert dispositions["order.1.0"]["reason"] == "pending_position_settlement"
    assert dispositions["settlement-event.applied.0.1"]["status"] == "used"
    assert dispositions["settlement-event.applied.2.0"]["reason"] == "pending_beyond_window"
    assert len(result["fee_assessments"]) == (4 if combined_fees else 2)
    assert runtime.run(transport) == publication
    assert d.canonical_bytes(case) == before


def test_v7_materialization_cannot_claim_another_resolved_account(tmp_path):
    with pytest.raises(ValueError, match="live case profile"):
        _prepared(tmp_path, account_override="account:another")


@pytest.mark.parametrize("mode", ("wrong", "raises"))
def test_v7_profile_dispatcher_failures_never_downgrade_or_publish(tmp_path, mode):
    runtime, transport, _, _ = _prepared(tmp_path, dispatcher_mode=mode)
    with pytest.raises(RuntimeError, match="^execution input hydration failed: financial_dispatcher_binding_mismatch$"):
        runtime.run(transport)
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("change", ("extra_order", "future_settlement", "clock", "catalog", "allocation_basis", "plan_version", "open_execution", "identity", "target", "dispatcher"))
def test_v7_payload_tampering_is_rejected_before_attempt(tmp_path, change):
    runtime, transport, store, case = _prepared(tmp_path)
    payload = json.loads(d.canonical_bytes(store.values[transport.execution_input_bundle_ref].payload))
    plan = payload["execution_case_plan"]
    if change == "extra_order":
        plan["bar_executions"][0]["order_id"] = plan["decision_cycles"][0]["admission_slot"]["order_id"]
    elif change == "future_settlement":
        plan["bar_executions"][0]["accounting_plan"]["settlement_slots"][0]["amount"] = 123
    elif change == "clock":
        del plan["decision_cycles"][0]["snapshot_plan"]["resolved_marks"][0]["resolved_at_instant"]
    elif change == "catalog":
        plan["decision_cycles"][0]["schedule"]["entries"][0]["validation_context"]["instrument_catalog_hash"] = "sha256:" + "0" * 64
    elif change == "allocation_basis":
        plan["decision_cycles"][0]["allocation_basis"] = "precomputed_nav"
    elif change == "plan_version":
        plan["schema_version"] = 1
    elif change == "open_execution":
        applicability = case.execution_model.spec().applicability
        assert isinstance(applicability, bt.NextBarCloseApplicability)
        plan["execution_model_spec"] = json.loads(d.canonical_bytes(bt.NextEligibleBarOpenModel.create(
            actions=applicability.tif_actions).spec()))
    elif change == "identity":
        spec = case.semantic_spec
        assert spec is not None
        other = bt.ExecutionCaseIdentityFactory(semantic_run_id="unbound", namespace=spec.identity_namespace, identity_plan=spec.identity_plan)
        plan["decision_cycles"][0]["admission_slot"]["order_id"] = json.loads(d.canonical_bytes(other.domain_id("order.0.0")))
    elif change == "target":
        payload["target_stream"]["events"][0]["source_hash"] = "sha256:" + "0" * 64
    else:
        plan["financial_dispatch_plan"]["dispatcher_spec"] = json.loads(d.canonical_bytes(bt.default_cash_financial_dispatcher_spec()))
    envelope = d.ArtifactEnvelope.create("backtest_execution_input_bundle", 7, payload)
    tampered = replace(transport, execution_input_bundle_ref=store.put(envelope=envelope))
    with pytest.raises(RuntimeError, match="execution input hydration failed:"):
        runtime.run(tampered)
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("mode", ("missing", "tampered"))
def test_v7_source_receipt_failures_are_not_economic_results(tmp_path, mode):
    runtime, transport, store, _ = _prepared(tmp_path)
    ref = transport.execution_input_bundle_ref
    if mode == "missing":
        del store.values[ref]
    else:
        payload = dict(store.values[ref].payload)
        payload["timeline_batch_size"] = 2
        store.values[ref] = d.ArtifactEnvelope.create("backtest_execution_input_bundle", 7, payload)
    code = "execution_input_unavailable" if mode == "missing" else "execution_input_tampered"
    with pytest.raises(RuntimeError, match=code):
        runtime.run(transport)
    assert not (tmp_path / "runs").exists()
