"""Native V2 failure prefixes and original-source cancellation boundaries."""
from dataclasses import replace
import json

import pytest
import crypto_quant_domain as d
import crypto_quant_backtest as bt
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import (
    economic_public_sources_v2, _prepare_sources_v2, _changed_target_v2,
)
from tests.runtime.providers.test_cn_a_share_portfolio_economic_public_v2 import _cold_guards, _assert_public_replay_v2


@pytest.mark.parametrize("boundary,reason", [("expiry_equal", "target_expired"), ("future_effective", "target_not_effective")])
def test_v2_activation_native_failure_prefix(tmp_path, monkeypatch, boundary, reason):
    inputs, _, market, store, _, window = economic_public_sources_v2()
    n = inputs.initial_marks.at.instant.epoch_nanoseconds
    inputs = _changed_target_v2(inputs, store, **({"expires_at": n} if boundary == "expiry_equal" else {"effective_time": n + 1}))
    prepared, case, inputs, store, market = _prepare_sources_v2(tmp_path, inputs, market, store, window)
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is d.ArtifactRef
    records = tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))
    reports = tuple(tmp_path.glob("runs/*/attempts/*/failure-report.json"))
    assert len(records) == len(reports) == 1
    report = json.loads(reports[0].read_bytes())["payload"]
    assert json.loads(records[0].read_bytes())["payload"]["failed_report"] == report
    failure = report["issue"]["source_evidence"]
    assert failure["schema_version"] == 2 and failure["code"] == "allocation"
    context = failure["economic_failure_context"]["payload"]
    assert context["failed_event_id"] == inputs.source_target_stream.events[0].event_id
    assert context["failed_at"]["phase"] == {"type": "timeline_phase", "rank": 30, "code": "cn_economic_native"}
    assert context["prefix_checkpoint"]["at"] == context["failed_at"]
    assert context["journal"]["entries"] == json.loads(d.canonical_bytes(inputs.initial_journal))["entries"]
    assert not context["order_streams"] and not context["pending_intentions"] and not context["admissions"]
    artifacts = context["financial_artifacts"]
    assert len(artifacts) == 1 and artifacts[0]["role"] == "economic_native_failure"
    diagnostic = artifacts[0]["payload"]["payload"]
    assert artifacts[0]["payload"]["schema_version"] == diagnostic["schema_version"] == 2
    assert diagnostic["operation"] == "portfolio_allocation"
    assert type(diagnostic["native_inputs"]["target_notional_scale"]) is int
    assert diagnostic["native_inputs"]["target_notional_scale"] == 14
    assert tuple(row["code"] for row in diagnostic["native_outcome"]["failure"]["decisions"]) == (reason,)
    assert diagnostic["original_claim"]["source"] == context["prefix_checkpoint"]
    assert diagnostic["original_claim"]["event"] == json.loads(d.canonical_bytes(inputs.source_target_stream.events[0]))
    repository = bt.BacktestEvidenceRepository(reader=store)
    terminal = repository.load_terminal(ref, economic_market_reader=market)
    assert terminal.status.value == "FAILED"
    _assert_public_replay_v2(prepared, ref, store, tmp_path, monkeypatch)
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        assert repository.load_terminal(ref, economic_market_reader=market) == terminal
    assert len(tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))) == 1
    assert not tuple(tmp_path.glob("runs/*/canonical-v2/result.json"))


def _rehash_failure_v2(failure, raw, *, diagnostic_version=2):
    diagnostic = next(a for a in raw["financial_artifacts"] if a["role"] == "economic_native_failure")
    value = diagnostic["payload"]["payload"]
    diagnostic["payload"] = json.loads(d.canonical_bytes(d.ArtifactEnvelope.create(
        "cn_a_share_portfolio_economic_native_failure", diagnostic_version, value)))
    diagnostic["result_hash"] = d.canonical_sha256(diagnostic["payload"])
    raw["trace"]["entries"][-2]["evidence_hash"] = d.canonical_sha256(diagnostic)
    cause = d.canonical_sha256(value["native_outcome"])
    raw["trace"]["entries"][-1]["evidence_hash"] = cause
    trace_hash = d.canonical_sha256(raw["trace"])
    raw["base_failure"]["trace_hash"] = trace_hash
    raw["base_failure"]["evidence_hashes"] = [cause]
    envelope = d.ArtifactEnvelope.create("cn_a_share_portfolio_economic_failure_context", 1, raw)
    return replace(failure, trace_hash=trace_hash, evidence_hashes=tuple(sorted((cause, d.canonical_sha256(envelope)))),
        economic_failure_context=envelope)


@pytest.fixture(scope="module")
def expired_v2(tmp_path_factory):
    inputs, _, market, store, _, window = economic_public_sources_v2()
    inputs = _changed_target_v2(inputs, store, expires_at=inputs.initial_marks.at.instant.epoch_nanoseconds)
    prepared, case, inputs, store, market = _prepare_sources_v2(tmp_path_factory.mktemp("v2-expired"), inputs, market, store, window)
    ref = prepared.runtime.run(prepared.execution_request)
    report = next(e.payload for e in store.values.values() if e.artifact_type == "failure_report")
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _read_economic_failure_v1
    failure = _read_economic_failure_v1(case=case, reader=store, value=report["issue"]["source_evidence"])
    return case, store, failure


@pytest.mark.parametrize("mutation", ["scale13", "scale_bool", "missing_scale", "envelope1", "payload1", "both1", "operation", "source", "future_prefix"])
def test_v2_native_diagnostic2_rehashed_substitutions(expired_v2, monkeypatch, mutation):
    case, store, failure = expired_v2
    raw = json.loads(d.canonical_bytes(failure.economic_failure_context.payload))
    value = raw["financial_artifacts"][-1]["payload"]["payload"]
    version = 2
    if mutation == "scale13": value["native_inputs"]["target_notional_scale"] = 13
    elif mutation == "scale_bool": value["native_inputs"]["target_notional_scale"] = True
    elif mutation == "missing_scale": del value["native_inputs"]["target_notional_scale"]
    elif mutation in ("envelope1", "payload1", "both1"):
        if mutation != "payload1": version = 1
        if mutation != "envelope1": value["schema_version"] = 1
    elif mutation == "operation": value["operation"] = "target_validation"
    elif mutation == "source": value["original_claim"]["event"]["event_id"] += ".wrong"
    else: raw["prefix_checkpoint"]["at"]["source_sequence"]["value"] += 1
    forged = _rehash_failure_v2(failure, raw, diagnostic_version=version)
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_failure_context_v1
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        with pytest.raises((d.ArtifactIntegrityError, ValueError)):
            _verify_economic_failure_context_v1(case=case, reader=store, failure=forged)


def test_v2_later_financial_failure_prefix(tmp_path, monkeypatch):
    import crypto_quant_trading as t
    from dataclasses import fields
    inputs, _, market, store, _, window = economic_public_sources_v2()
    changed = []
    for term in inputs.opening_terms:
        rules = term.final_order_rules
        kwargs = {f.name: getattr(rules, f.name) for f in fields(rules) if f.name != "config_hash"}
        selected = tuple(r for r in rules.charge_rules if r.source is t.FinalFeeRuleSource.ACCOUNT_SCHEDULE)
        assert selected, "synthetic source must retain an actual account-fee rule"
        kwargs["charge_rules"] = tuple(replace(r, calculation_basis=t.FinalFeeCalculationBasis.UNKNOWN,
            rate=None, flat_amount=None) if r in selected else r for r in rules.charge_rules)
        updated = type(rules).create(**kwargs)
        assert tuple(r for r in updated.charge_rules if r.source is not t.FinalFeeRuleSource.ACCOUNT_SCHEDULE) == tuple(
            r for r in rules.charge_rules if r.source is not t.FinalFeeRuleSource.ACCOUNT_SCHEDULE)
        changed.append(replace(term, final_order_rules=updated))
    inputs = replace(inputs, opening_terms=tuple(changed))
    prepared, case, inputs, store, market = _prepare_sources_v2(tmp_path, inputs, market, store, window)
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is d.ArtifactRef
    reports = tuple(tmp_path.glob("runs/*/attempts/*/blocked-run-report.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_bytes())["payload"]
    failure = report["issue"]["source_evidence"]
    assert failure["code"] == "fee_assessment_failure"
    context = failure["economic_failure_context"]["payload"]
    assert context["prefix_checkpoint"]["at"]["phase"]["rank"] == 67
    assert context["failed_at"]["phase"]["rank"] == 97
    assert tuple(a["role"] for a in context["financial_artifacts"]) == ("economic_signal", "economic_native_failure")
    diagnostic = context["financial_artifacts"][-1]["payload"]["payload"]
    assert diagnostic["operation"] == "order_fee_assessment"
    assert all(e["entry_type"] != "fill_booked" for e in context["journal"]["entries"])
    assert len(context["order_streams"]) == 2
    assert all(s["records"][-1]["event"]["event_type"] == "order_accepted" for s in context["order_streams"])
    repository = bt.BacktestEvidenceRepository(reader=store)
    assert repository.load_terminal(ref, economic_market_reader=market).status.value == "BLOCKED"
    _assert_public_replay_v2(prepared, ref, store, tmp_path, monkeypatch)
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        assert repository.load_terminal(ref, economic_market_reader=market).status.value == "BLOCKED"


@pytest.mark.parametrize("frontier", ["source", "first_opening", "later_opening", "invalid"])
def test_v2_cancellation_original_frontiers(tmp_path, monkeypatch, frontier):
    import crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 as live
    import crypto_quant_trading as t
    inputs, bars, market, store, target, window = economic_public_sources_v2()
    prepared, case, inputs, store, market = _prepare_sources_v2(tmp_path, inputs, market, store, window)
    event = target.events[0] if frontier == "source" else bars[0] if frontier == "first_opening" else bars[-1]
    cancellation = bt.EngineCancellationRequest("not-source" if frontier == "invalid" else event.event_id, "synthetic_boundary")
    artifacts, traces, allocations = [], [], []
    artifact, trace, allocate = live.FinancialDispatchArtifact, live.ExecutionTrace, t.PortfolioAllocator.allocate
    def capture_artifact(*args, **kwargs):
        value = artifact(*args, **kwargs)
        artifacts.append(value)
        return value
    def capture_trace(*args, **kwargs):
        value = trace(*args, **kwargs)
        traces.append(value)
        return value
    def capture_allocation(self, **kwargs):
        allocations.append(kwargs["sleeve_state"].as_of_instant)
        return allocate(self, **kwargs)
    with monkeypatch.context() as spies:
        spies.setattr(live, "FinancialDispatchArtifact", capture_artifact)
        spies.setattr(live, "ExecutionTrace", capture_trace)
        spies.setattr(t.PortfolioAllocator, "allocate", capture_allocation)
        if frontier == "invalid":
            with pytest.raises(ValueError, match="real market/target event"):
                prepared.runtime.run_with_cancellation(prepared.execution_request, cancellation)
            assert not artifacts and not allocations
            return
        ref = prepared.runtime.run_with_cancellation(prepared.execution_request, cancellation)
    assert type(ref) is d.ArtifactRef
    reports = tuple(tmp_path.glob("runs/*/attempts/*/cancellation-report.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_bytes())["payload"]
    recorded = report["cancellation"]
    emitted = []
    cursor = case.timeline.open_cursor(batch_size=64)
    while not cursor.window_complete:
        batch = case.timeline.read_batch(cursor).batch
        emitted.extend(row.event.event_id for row in batch.events)
        cursor = batch.next_cursor
    assert recorded["processed_timeline_events"] == emitted.index(event.event_id)
    assert recorded["trace_hash"] == traces[-1].trace_hash
    assert all(a.occurred_at.instant < event.event_time for a in artifacts)
    if frontier == "source": assert not artifacts and not allocations
    elif frontier == "first_opening": assert [a.role for a in artifacts] == ["economic_signal"] and allocations
    else:
        assert sum(a.role == "economic_opening_batch" for a in artifacts) == 1
        assert sum(a.role == "economic_daily_projection" for a in artifacts) == 1
        assert all(a.occurred_at >= inputs.initial_marks.at for a in artifacts)
    repository = bt.BacktestEvidenceRepository(reader=store)
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        assert repository.load_terminal(ref, economic_market_reader=market).status.value == "CANCELLED"
    _assert_public_replay_v2(prepared, ref, store, tmp_path, monkeypatch)
    assert len(tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))) == 1
