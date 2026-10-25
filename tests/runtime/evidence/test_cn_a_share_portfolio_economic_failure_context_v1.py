from dataclasses import replace
import json

import pytest
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_backtest.engine import EngineFailure, EngineFailureCode, ExecutionTrace
from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_failure_context_v1, _read_economic_failure_v1
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1


def test_engine_failure_none_preserves_seven_legacy_keys_and_keyword_only_context():
    h = d.canonical_sha256("failure.identity")
    failure = EngineFailure(EngineFailureCode.ACCOUNTING_FAILURE, h, ExecutionTrace().trace_hash, ("native",))
    raw = failure.to_canonical_dict()
    assert len(raw) == 7 and "schema_version" not in raw and "economic_failure_context" not in raw
    with pytest.raises(TypeError):
        EngineFailure(EngineFailureCode.ACCOUNTING_FAILURE, h, ExecutionTrace().trace_hash, ("native",), (), None, None)


def test_native_book_failure_keeps_committed_admission67_not_provisional_fills(tmp_path, monkeypatch):
    _, case, inputs, store, market = economic_prepared_case_v1(tmp_path)
    original = t.CashInstrumentAccounting.book_fill
    def rejected(self, **kwargs):
        key = kwargs["cash_key"]
        return original(self, **{**kwargs, "cash_key": d.CashBalanceKey(key.account_id, key.venue_id, d.CurrencyId("USD"))})
    monkeypatch.setattr(t.CashInstrumentAccounting, "book_fill", rejected)
    outcome = _CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    assert outcome.result is None and outcome.engine_failure.code is EngineFailureCode.ACCOUNTING_FAILURE
    context = outcome.engine_failure.economic_failure_context.payload
    assert context["prefix_checkpoint"]["at"]["phase"]["rank"] == 67
    assert not any(e["entry_type"] == "fill_booked" for e in context["journal"]["entries"])
    assert all(s["records"][-1]["event"]["event_type"] == "order_accepted" for s in context["order_streams"])
    diagnostic=next(a for a in context["financial_artifacts"] if a["role"]=="economic_native_failure")
    assert diagnostic["payload"]["payload"]["operation"]=="fill_accounting"
    assert diagnostic["payload"]["payload"]["native_inputs"] and diagnostic["payload"]["payload"]["native_outcome"]
    monkeypatch.setattr(t.CashInstrumentAccounting, "book_fill", original)
    with pytest.raises(d.ArtifactIntegrityError,match="actually succeeds|complete actual rejected outcome"):
        _verify_economic_failure_context_v1(case=case, reader=store, failure=outcome.engine_failure)


def test_real_pay_prefix_tax_failure_cold_roundtrip_without_live_mutations(tmp_path, monkeypatch):
    _, case, inputs, store, market = economic_prepared_case_v1(tmp_path, tax_shortfall=True)
    outcome = _CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    failure = outcome.engine_failure
    assert failure is not None and failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    raw = json.loads(d.canonical_bytes(failure))
    assert len(raw) == 9 and raw["schema_version"] == 2
    assert len(raw["economic_failure_context"]["payload"]) == 24
    before = d.canonical_bytes(failure)
    def forbidden(*args, **kwargs):
        raise AssertionError("cold failure cannot execute, append or publish")
    monkeypatch.setattr(_CnASharePortfolioEconomicEngineV1, "run", forbidden)
    monkeypatch.setattr(t.AccountingJournal, "append", forbidden)
    monkeypatch.setattr(t.AccountingJournal, "append_many", forbidden)
    monkeypatch.setattr(store, "put", forbidden)
    _verify_economic_failure_context_v1(case=case, reader=store, failure=failure)
    decoded = _read_economic_failure_v1(case=case, reader=store, value=raw)
    assert d.canonical_bytes(decoded) == before == d.canonical_bytes(failure)
    altered = json.loads(before)
    del altered["economic_failure_context"]
    with pytest.raises((TypeError, ValueError)):
        _read_economic_failure_v1(case=case, reader=store, value=altered)


@pytest.fixture(scope="module")
def io_boundary_context(tmp_path_factory):
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v1 import _registry
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot
    from crypto_quant_backtest.resolution import ProfileResolver
    prepared,case,inputs,store,market=economic_prepared_case_v1(tmp_path_factory.mktemp("io-boundary"))
    bundle,failure=_read_execution_inputs_v9_from_snapshot(store,prepared.execution_request)
    assert failure is None
    resolved=ProfileResolver().resolve(request=prepared.execution_request.request,registry=_registry(inputs),
        market_bundle_manifest=market.manifest,build_artifact_manifest=bundle.build_artifact_manifest).resolved
    engine=_CnASharePortfolioEconomicEngineV1(artifact_reader=store)
    outcome=engine.run(case)
    assert outcome.result is not None
    return prepared,case,inputs,store,market,resolved,engine,outcome


@pytest.mark.parametrize("boundary",["compose","build","run","verify_result","lock_body","cache_read"])
def test_all_economic_outer_io_boundaries_propagate_original_exception(tmp_path,monkeypatch,io_boundary_context,boundary):
    import crypto_quant_backtest.runner as runner_module
    import crypto_quant_backtest.facade as facade_module
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v1 import _NativeEconomicPortfolioProfileV1
    prepared,case,inputs,store,market,resolved,engine,outcome=io_boundary_context
    sentinel=OSError("original economic boundary "+boundary)
    def broken(*args,**kwargs):
        raise sentinel
    if boundary=="compose":
        monkeypatch.setattr(facade_module,"_compose_profile_portfolio_economic_execution_case",broken)
        invoke=lambda:prepared.runtime._run_v6(prepared.execution_request,cancellation=None)
    elif boundary=="build":
        monkeypatch.setattr(_NativeEconomicPortfolioProfileV1,"build_portfolio_engine",broken)
        invoke=lambda:prepared.runtime._economic_case_engine(resolved,case)
    else:
        runner=runner_module.AuditableBacktestRunner.for_v2(publication_root=tmp_path,engine=engine)
        if boundary=="run":
            monkeypatch.setattr(engine,"run",broken)
        elif boundary=="verify_result":
            monkeypatch.setattr(engine,"run",lambda *args,**kwargs:outcome)
            monkeypatch.setattr(engine,"verify_result",broken)
        elif boundary=="lock_body":
            monkeypatch.setattr(runner,"_execute_verified_locked",broken)
        else:
            (tmp_path/"runs"/resolved.semantic_run_id/"canonical-v2").mkdir(parents=True)
            monkeypatch.setattr(runner_module,"_read_canonical_cache_hit_v2",broken)
        invoke=lambda:runner._execute_verified(resolved_request=resolved,execution_case=case,
            attempt=runner_module.AttemptIdentity.first(resolved.semantic_run_id),
            input_origin=prepared.runtime._input_origin(resolved),cancellation=None)
    with pytest.raises(OSError) as caught:
        invoke()
    assert caught.value is sentinel
    assert not tuple(tmp_path.glob("runs/*/attempts/*/failure-report.json"))



def test_failure_verifier_io_is_not_converted_to_terminal_failed(tmp_path,monkeypatch):
    import crypto_quant_backtest.runner as runner_module
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v1 import _registry
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot
    from crypto_quant_backtest.resolution import ProfileResolver
    prepared,case,inputs,store,market=economic_prepared_case_v1(tmp_path/"source",tax_shortfall=True)
    bundle,failure=_read_execution_inputs_v9_from_snapshot(store,prepared.execution_request)
    resolved=ProfileResolver().resolve(request=prepared.execution_request.request,registry=_registry(inputs),
        market_bundle_manifest=market.manifest,build_artifact_manifest=bundle.build_artifact_manifest).resolved
    engine=_CnASharePortfolioEconomicEngineV1(artifact_reader=store)
    outcome=engine.run(case)
    assert outcome.engine_failure is not None
    sentinel=OSError("original failure verifier I/O")
    monkeypatch.setattr(engine,"run",lambda *args,**kwargs:outcome)
    def broken(*args,**kwargs):
        raise sentinel
    monkeypatch.setattr(engine,"verify_failure",broken)
    runner=runner_module.AuditableBacktestRunner.for_v2(publication_root=tmp_path/"failure-io",engine=engine)
    with pytest.raises(OSError) as caught:
        runner._execute_verified(resolved_request=resolved,execution_case=case,
            attempt=runner_module.AttemptIdentity.first(resolved.semantic_run_id),
            input_origin=prepared.runtime._input_origin(resolved),cancellation=None)
    assert caught.value is sentinel
    assert not tuple((tmp_path/"failure-io").glob("runs/*/attempts/*/failure-report.json"))


@pytest.fixture(scope="module")
def genuine_capability_failure(tmp_path_factory):
    _,case,inputs,store,_=economic_prepared_case_v1(tmp_path_factory.mktemp("genuine-capability-failure"),cash_exit=True,reject_sell_capability=True)
    outcome=_CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    assert outcome.engine_failure is not None and outcome.engine_failure.code is EngineFailureCode.CAPABILITY_REJECTED
    _verify_economic_failure_context_v1(case=case,reader=store,failure=outcome.engine_failure)
    return case,store,outcome.engine_failure


def test_genuine_source_provable_native_failure_retains_complete_original_claim_and_rejects_live_calls(genuine_capability_failure,monkeypatch):
    case,store,failure=genuine_capability_failure
    def forbidden(*args,**kwargs):raise AssertionError("cold native cause may not run or append")
    monkeypatch.setattr(_CnASharePortfolioEconomicEngineV1,"run",forbidden)
    monkeypatch.setattr(t.AccountingJournal,"append",forbidden)
    monkeypatch.setattr(t.AccountingJournal,"append_many",forbidden)
    _verify_economic_failure_context_v1(case=case,reader=store,failure=failure)
    context=failure.economic_failure_context.payload
    assert len([a for a in context["financial_artifacts"] if a["role"]=="economic_native_failure"])==1


@pytest.mark.parametrize("mutation",["cause","code","inputs","claim"])
def test_fully_rehashed_unrelated_native_failure_cause_code_inputs_and_claim_rejected(genuine_capability_failure,mutation):
    case,store,failure=genuine_capability_failure
    raw=json.loads(d.canonical_bytes(failure.economic_failure_context.payload))
    diagnostic=next(a for a in raw["financial_artifacts"] if a["role"]=="economic_native_failure")
    value=diagnostic["payload"]["payload"]
    from crypto_quant_backtest.execution_inputs import _read_order
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _bind_economic_portfolio_sources_v1
    order=_read_order(value["original_claim"]["order"])
    altered=replace(order,intent=replace(order.intent,quantity=replace(order.intent.quantity,units=order.intent.quantity.units+100)))
    bound=_bind_economic_portfolio_sources_v1(case,store)
    term=next(t for t in bound.inputs.opening_terms if d.canonical_bytes(t)==d.canonical_bytes(value["original_claim"]["terms"]))
    unrelated=t.OrderCapabilityValidator().validate(altered.intent,term.capability_set)
    if mutation=="cause":
        value["native_outcome"]=json.loads(d.canonical_bytes(unrelated))
    elif mutation=="code":
        value["engine_failure_code"]=EngineFailureCode.FEE_RESERVATION.value
        raw["base_failure"]["code"]=value["engine_failure_code"]
        raw["base_failure"]["subject_keys"]=sorted(value["engine_failure_code"] if s==failure.code.value else s for s in raw["base_failure"]["subject_keys"])
    elif mutation=="inputs":
        value["native_inputs"]["intent"]=json.loads(d.canonical_bytes(altered.intent))
        value["native_outcome"]=json.loads(d.canonical_bytes(unrelated))
    else:
        value["original_claim"]["order"]=json.loads(d.canonical_bytes(altered))
        value["native_inputs"]["intent"]=json.loads(d.canonical_bytes(altered.intent))
        value["native_outcome"]=json.loads(d.canonical_bytes(unrelated))
    diagnostic["payload"]=json.loads(d.canonical_bytes(d.ArtifactEnvelope.create("cn_a_share_portfolio_economic_native_failure",1,value)))
    diagnostic["result_hash"]=d.canonical_sha256(diagnostic["payload"])
    raw["trace"]["entries"][-2]["evidence_hash"]=d.canonical_sha256(diagnostic)
    cause_hash=d.canonical_sha256(value["native_outcome"])
    raw["trace"]["entries"][-1]["evidence_hash"]=cause_hash
    trace_hash=d.canonical_sha256(raw["trace"])
    raw["base_failure"]["trace_hash"]=trace_hash
    raw["base_failure"]["evidence_hashes"]=[cause_hash]
    envelope=d.ArtifactEnvelope.create("cn_a_share_portfolio_economic_failure_context",1,raw)
    forged=replace(failure,code=EngineFailureCode(raw["base_failure"]["code"]),trace_hash=trace_hash,
        subject_keys=tuple(raw["base_failure"]["subject_keys"]),evidence_hashes=tuple(sorted((cause_hash,d.canonical_sha256(envelope)))),economic_failure_context=envelope)
    with pytest.raises(d.ArtifactIntegrityError):
        _verify_economic_failure_context_v1(case=case,reader=store,failure=forged)


def _fully_rehash_native_diagnostic_failure(failure,raw):
    diagnostic=next(a for a in raw["financial_artifacts"] if a["role"]=="economic_native_failure")
    value=diagnostic["payload"]["payload"]
    diagnostic["payload"]=json.loads(d.canonical_bytes(d.ArtifactEnvelope.create("cn_a_share_portfolio_economic_native_failure",1,value)))
    diagnostic["source_event_id"]=raw["failed_event_id"];diagnostic["occurred_at"]=raw["failed_at"]
    diagnostic["result_hash"]=d.canonical_sha256(diagnostic["payload"])
    cause_hash=d.canonical_sha256(value["native_outcome"])
    for row in raw["trace"]["entries"][-2:]:
        row["instant"]=raw["failed_at"];row["subject_id"]=raw["failed_event_id"]
    raw["trace"]["entries"][-2]["evidence_hash"]=d.canonical_sha256(diagnostic)
    raw["trace"]["entries"][-1]["evidence_hash"]=cause_hash
    trace_hash=d.canonical_sha256(raw["trace"])
    raw["base_failure"]["trace_hash"]=trace_hash;raw["base_failure"]["evidence_hashes"]=[cause_hash]
    envelope=d.ArtifactEnvelope.create("cn_a_share_portfolio_economic_failure_context",1,raw)
    return replace(failure,trace_hash=trace_hash,subject_keys=tuple(raw["base_failure"]["subject_keys"]),
        evidence_hashes=tuple(sorted((cause_hash,d.canonical_sha256(envelope)))),economic_failure_context=envelope)


@pytest.mark.parametrize("mutation",["other_rejected_sell","first_bar","phase","phase_code","sequence"])
def test_rehashed_native_failure_requires_deterministic_first_funding_call_and_full_clock(genuine_capability_failure,mutation):
    from crypto_quant_backtest.execution_inputs import _read_order
    from crypto_quant_backtest.execution import BarOpenObservation
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _bind_economic_portfolio_sources_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_opening_v1 import _economic_evaluation_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import _EconomicNativeFailureV1
    case,store,failure=genuine_capability_failure
    raw=json.loads(d.canonical_bytes(failure.economic_failure_context.payload))
    diagnostic=next(a for a in raw["financial_artifacts"] if a["role"]=="economic_native_failure")
    value=diagnostic["payload"]["payload"]
    bound=_bind_economic_portfolio_sources_v1(case,store)
    when=failure.economic_failure_context.payload["failed_at"]["instant"]
    bars=tuple(e for e in bound.openings if json.loads(d.canonical_bytes(e.event_time))==json.loads(d.canonical_bytes(when)))
    assert len(bars)==2
    if mutation=="other_rejected_sell":
        order=_read_order(next(o for o in raw["pending_intentions"] if o["order_id"]!=value["original_claim"]["order"]["order_id"]))
        term=next(t for t in bound.inputs.opening_terms if t.instrument_id==order.intent.instrument_id and t.side is order.intent.side and t.opening_at==bars[0].event_time)
        event=next(e for e in bars if e.instrument_id==order.intent.instrument_id)
        try:_economic_evaluation_v1(order,BarOpenObservation.from_event(event),term)
        except _EconomicNativeFailureV1 as rejected:
            value["original_claim"]=json.loads(d.canonical_bytes(rejected.original_claim))
            value["native_inputs"]=json.loads(d.canonical_bytes(rejected.native_inputs))
            value["native_outcome"]=json.loads(d.canonical_bytes(rejected.evidence))
        else:pytest.fail("other pending SELL must be genuinely rejected by native capability")
    elif mutation=="first_bar":
        old=raw["failed_event_id"];raw["failed_event_id"]=bars[1].event_id
        raw["base_failure"]["subject_keys"]=sorted(raw["failed_event_id"] if s==old else s for s in raw["base_failure"]["subject_keys"])
    elif mutation=="phase":raw["failed_at"]["phase"]["rank"]+=1
    elif mutation=="phase_code":raw["failed_at"]["phase"]["code"]="zz_non_native"
    else:raw["failed_at"]["source_sequence"]["value"]+=1
    forged=_fully_rehash_native_diagnostic_failure(failure,raw)
    with pytest.raises(d.ArtifactIntegrityError,match="FIRST failing|first-bar49"):
        _verify_economic_failure_context_v1(case=case,reader=store,failure=forged)
