"""Economic settlement codec bridge; not an input9/cold-result acceptance test."""
from dataclasses import replace
import json

import pytest

from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_trading import SettlementLifecycleError
from crypto_quant_backtest.cn_a_share_portfolio_settlement_development_v1 import (
    _book_body, read_cn_a_share_portfolio_settlement_book_source_v1,
)
from tests.kernel.profiles.cn_a_share.test_cash_dividend_projection_v1 import _inputs
from tests.kernel.profiles.cn_a_share.test_cash_dividend_accounting_v1 import _history


@pytest.mark.parametrize("factory", [_inputs, _history])
def test_economic_book_codec_preserves_runtime_source_bytes(factory):
    inputs = factory()
    book = inputs.settlement_book
    body = inputs.to_canonical_dict()["settlement_book"]
    assert canonical_bytes(body) == canonical_bytes(_book_body(book))
    decoded = read_cn_a_share_portfolio_settlement_book_source_v1(json.loads(canonical_bytes(body)))
    assert decoded == book
    assert canonical_bytes(_book_body(decoded)) == canonical_bytes(body)
    assert canonical_sha256(_book_body(decoded)) == canonical_sha256(body)
    prefix = replace(book, events=book.events[:-1])
    assert canonical_bytes(inputs.to_canonical_dict()["settlement_book"]) != canonical_bytes(_book_body(prefix))


@pytest.mark.parametrize("mutation", ["hash", "extra", "missing", "prefix"])
def test_economic_book_codec_strict_reader_rejects_tampering(mutation):
    body = json.loads(canonical_bytes(_inputs().to_canonical_dict()["settlement_book"]))
    if mutation == "hash":
        body["book_hash"] = canonical_sha256("not-this-book")
    elif mutation == "extra":
        body["spendable"] = 0
    elif mutation == "missing":
        del body["events"]
    else:
        body["events"] = body["events"][:-1]
    with pytest.raises(ValueError):
        read_cn_a_share_portfolio_settlement_book_source_v1(body)


def test_strict_economic_mark_reader_roundtrip_and_missing_full_clock():
    from crypto_quant_backtest.cn_a_share_portfolio_economic_values_v1 import _read_economic_resolved_mark_v1
    mark = _inputs().marks[0]
    raw = json.loads(canonical_bytes(mark))
    decoded = _read_economic_resolved_mark_v1(raw)
    assert decoded == mark
    for key in ("available_at_instant", "resolved_at_instant"):
        missing = dict(raw)
        del missing[key]
        with pytest.raises(ValueError):
            _read_economic_resolved_mark_v1(missing)
        null = dict(raw, **{key: None})
        with pytest.raises(ValueError):
            _read_economic_resolved_mark_v1(null)


def test_strict_economic_values_roundtrip_all_pure_contracts():
    import crypto_quant_domain as d
    import crypto_quant_backtest.cn_a_share_portfolio_economic_values_v1 as readers
    import crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 as economic
    from tests.kernel.profiles.cn_a_share.test_cash_dividend_accounting_v1 import _step
    inputs = _inputs()
    projection = economic.project_cn_a_share_portfolio_economic_state_v1(inputs)
    rejected = economic.project_cn_a_share_portfolio_economic_state_v1(replace(inputs, marks=inputs.marks[:-1]))
    h = _history()
    action = h.action_set.actions[0]
    request = economic.CnAShareCashDividendTransitionInputsV1(replace(h, as_of=action.entitlement_at),
        action.action_id, action.instrument_id, "ENTITLE")
    failed = economic.transition_cn_a_share_cash_dividend_v1(request)
    pairs = [(inputs, readers._read_cn_a_share_portfolio_economic_projection_inputs_v1),
        (projection, readers._read_cn_a_share_economic_projection_outcome_v1),
        (projection.projection, readers._read_cn_a_share_portfolio_economic_projection_v1),
        (projection.projection.cash_rows[0], readers._read_cn_a_share_economic_cash_row_v1),
        (rejected.failure, readers._read_cn_a_share_economic_projection_failure_v1),
        (action, readers._read_cn_a_share_cash_dividend_action_v1),
        (action.tax_policy, readers._read_cn_a_share_cash_dividend_tax_policy_v1),
        (h.action_set, readers._read_cn_a_share_cash_dividend_action_set_v1),
        (request, readers._read_cn_a_share_cash_dividend_transition_inputs_v1),
        (failed, readers._read_cn_a_share_cash_dividend_transition_outcome_v1),
        (failed.failure, readers._read_cn_a_share_cash_dividend_transition_failure_v1)]
    for kind in ("REGISTER", "ENTITLE", "PAY", "TAX"):
        h, transition = _step(h, kind)
        pairs.append((transition, readers._read_cn_a_share_cash_dividend_transition_v1))
    pairs += [(h, readers._read_cn_a_share_cash_dividend_history_inputs_v1),
        (h.dividend_state, readers._read_cn_a_share_cash_dividend_state_v1),
        (h.dividend_state.claims[0], readers._read_cn_a_share_cash_dividend_claim_v1)]
    ref = d.ArtifactRef.from_envelope(d.ArtifactEnvelope.create("synthetic_dividend_model_source", 1, {"model": "test"}))
    pairs.append((replace(action, source_evidence_refs=(ref,)), readers._read_cn_a_share_cash_dividend_action_v1))
    for value, reader in pairs:
        raw = json.loads(canonical_bytes(value))
        assert canonical_bytes(reader(raw)) == canonical_bytes(value)
        extra = dict(raw, unknown_economic_field=0)
        with pytest.raises(ValueError):
            reader(extra)
        with pytest.raises(ValueError):
            reader({**raw, "schema_version": True})


@pytest.mark.parametrize("mutation", ["unknown", "hash", "clock", "bool", "float", "ratio", "refs", "order"])
def test_strict_economic_action_readers_reject_malformed_source_values(mutation):
    from crypto_quant_backtest.cn_a_share_portfolio_economic_values_v1 import _read_cn_a_share_cash_dividend_action_set_v1
    raw = json.loads(canonical_bytes(_history().action_set))
    action = raw["actions"][0]
    if mutation == "unknown":
        action["qualified"] = True
    elif mutation == "hash":
        action["tax_policy"]["policy_hash"] = canonical_sha256("not-a-field")
    elif mutation == "clock":
        action["registered_at"]["source_sequence"]["value"] = True
    elif mutation == "bool":
        action["cash_per_share"]["units"] = True
    elif mutation == "float":
        action["cash_per_share"]["units"] = 1.2
    elif mutation == "ratio":
        action["tax_policy"]["numerator"] = 2
        action["tax_policy"]["denominator"] = 10
    elif mutation == "refs":
        action["source_evidence_refs"] = ["sha256:" + "a" * 64]
    else:
        raw["actions"] = [action, action]
    with pytest.raises((TypeError, ValueError)):
        _read_cn_a_share_cash_dividend_action_set_v1(raw)


def test_native_economic_cold_result_uses_only_recorded_proofs_no_live_fanin(tmp_path, monkeypatch):
    import crypto_quant_trading as t
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    import crypto_quant_backtest.cn_a_share_portfolio_economic_opening_v1 as opening
    import crypto_quant_backtest.cn_a_share_portfolio_financial_core_v1 as core
    _, case, inputs, store, market = economic_prepared_case_v1(tmp_path)
    outcome = _CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    assert outcome.result is not None and len(outcome.result.fills) == 2
    before = canonical_bytes(outcome.result)
    def forbidden(*args, **kwargs):
        raise AssertionError("cold cannot execute/select/live-book/append/publish")
    monkeypatch.setattr(_CnASharePortfolioEconomicEngineV1, "run", forbidden)
    monkeypatch.setattr(opening, "_economic_opening_v1", forbidden)
    monkeypatch.setattr(opening, "_book_economic_full_fill_batch_v1", forbidden)
    monkeypatch.setattr(core, "book_native_cn_portfolio_financial_core_v1", forbidden)
    monkeypatch.setattr(t.AccountingJournal, "append", forbidden)
    monkeypatch.setattr(t.AccountingJournal, "append_many", forbidden)
    monkeypatch.setattr(store, "put", forbidden)
    _verify_economic_native_result_v1(case=case, reader=store, result=outcome.result)
    _verify_economic_native_result_v1(case=case, reader=store, result=outcome.result)
    assert canonical_bytes(outcome.result) == before


def test_completed_source_binding_bootstrap_reads_actual_prepared_input9_without_execution(tmp_path, monkeypatch):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v1 import _registry
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _bootstrap_economic_case_v1
    from crypto_quant_backtest.resolution import ProfileResolver
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot
    prepared, case, inputs, store, market = economic_prepared_case_v1(tmp_path)
    bundle, failure = _read_execution_inputs_v9_from_snapshot(store, prepared.execution_request)
    assert failure is None
    resolved = ProfileResolver().resolve(request=prepared.execution_request.request, registry=_registry(inputs),
        market_bundle_manifest=market.manifest, build_artifact_manifest=bundle.build_artifact_manifest).resolved
    binding = {"type": "cn_a_share_portfolio_economic_completed_sources", "schema_version": 1,
        "source_refs": case.execution_case_plan.source_refs, "semantic_spec": case.semantic_spec,
        "identity_manifest": case.identity_manifest, "timeline_stream_keys": case.timeline.stream_keys}
    raw_binding = json.loads(canonical_bytes(binding))
    original_input = prepared.execution_request.execution_input_bundle_ref
    before = store.reads.get(original_input, 0)
    def no_publish(*args, **kwargs):
        raise AssertionError("bootstrap cannot publish or discover missing data")
    monkeypatch.setattr(store, "put", no_publish)
    checked, rebuilt, actual_ref, refs = _bootstrap_economic_case_v1(reader=store, market_reader=market,
        resolved_raw=json.loads(canonical_bytes(resolved)), binding=raw_binding, build_artifact_manifest=resolved.build_artifact_manifest)
    assert actual_ref == original_input and store.reads[original_input] > before
    assert rebuilt.case_hash == case.case_hash and checked.semantic_run_id == prepared.semantic_run_id
    del store.values[original_input]
    from crypto_quant_domain import ArtifactNotFoundError
    with pytest.raises(ArtifactNotFoundError):
        _bootstrap_economic_case_v1(reader=store, market_reader=market,
            resolved_raw=json.loads(canonical_bytes(resolved)), binding=raw_binding, build_artifact_manifest=resolved.build_artifact_manifest)


@pytest.fixture(scope="module")
def recorded_buy_sell_batches(tmp_path_factory):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    import crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 as engine
    directory = tmp_path_factory.mktemp("recorded-buy-sell")
    prepared, case, inputs, store, market = economic_prepared_case_v1(directory, cash_exit=True)
    batches = []
    original = engine._book_economic_full_fill_batch_v1
    def captured(*, sources, steps):
        result = original(sources=sources, steps=steps)
        batches.append((sources, steps, result))
        return result
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(engine, "_book_economic_full_fill_batch_v1", captured)
        outcome = engine._CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    if outcome.engine_failure is not None:
        (directory / "failure-context.json").write_bytes(canonical_bytes(outcome.engine_failure))
    assert outcome.result is not None and len(outcome.result.fills) == 4, None if outcome.engine_failure is None else (outcome.engine_failure.code.value, outcome.engine_failure.subject_keys)
    assert any(fill.side.value == "sell" for fill in outcome.result.fills)
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    _verify_economic_native_result_v1(case=case, reader=store, result=outcome.result)
    return inputs, batches, case, store, outcome.result


@pytest.mark.parametrize("mutation", ["cost_basis", "fee_allocation", "realized_pnl"])
def test_native_recorded_journal_rehashed_substitutions_rejected_semantically(recorded_buy_sell_batches, mutation):
    import crypto_quant_domain as d
    import crypto_quant_trading as t
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_recorded_financial_batch_v1
    inputs, batches, *_ = recorded_buy_sell_batches
    source, steps, result = next(row for row in batches if (row[1][0].opening.fill.side is d.OrderSide.SELL) == (mutation == "realized_pnl"))
    journal, ledger, fills, fees = result
    delta = list(journal.entries[source.journal.entry_count:])
    if mutation == "realized_pnl":
        entry = delta[0]
        pnl = entry.realized_pnl[0] if entry.realized_pnl else d.Money(0, d.Scale(2), "CNY")
        delta[0] = replace(entry, realized_pnl=(replace(pnl, units=pnl.units + 1),))
    else:
        index = 0 if mutation == "cost_basis" else len(steps)
        entry = delta[index]
        change = entry.position_lot_changes[0]
        lot = change.after
        if mutation == "cost_basis":
            lot = replace(lot, total_cost_basis=replace(lot.total_cost_basis, units=lot.total_cost_basis.units + 1))
        else:
            allocated = lot.allocated_fees[0]
            lot = replace(lot, allocated_fees=(replace(allocated, units=allocated.units + 1), *lot.allocated_fees[1:]))
        delta[index] = replace(entry, position_lot_changes=(replace(change, after=lot), *entry.position_lot_changes[1:]))
    rehashed = t.AccountingJournal((*source.journal.entries, *delta))
    assert rehashed.journal_hash != journal.journal_hash
    with pytest.raises(d.ArtifactIntegrityError, match="complete original native journal"):
        _verify_recorded_financial_batch_v1(inputs=inputs, prior=source.journal, steps=steps,
            recorded=rehashed.entries[source.journal.entry_count:], fees=fees)


def test_economic_book_codec_rejects_inconsistent_obligation_facts():
    body = json.loads(canonical_bytes(_inputs().to_canonical_dict()["settlement_book"]))
    body["obligations"] = []
    with pytest.raises(SettlementLifecycleError):
        read_cn_a_share_portfolio_settlement_book_source_v1(body)


def test_cold_native_rederivation_only_calls_original_claim_apis(recorded_buy_sell_batches,monkeypatch):
    import crypto_quant_domain as d
    import crypto_quant_trading as k
    import crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 as live
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    inputs,batches,case,store,result=recorded_buy_sell_batches
    calls={"book_fill":0,"charge_fee":0,"charge_order_fee":0,"assess":0}
    assessed_ids=[]
    for owner,name in ((k.CashInstrumentAccounting,"book_fill"),(k.CashInstrumentAccounting,"charge_fee"),
            (k.CashInstrumentAccounting,"charge_order_fee"),(k.FeeAssessmentEngine,"assess")):
        original=getattr(owner,name)
        def spy(*args,_original=original,_name=name,**kwargs):
            calls[_name]+=1
            if _name=="assess":
                assessed_ids.append(kwargs["fee_assessment_id"])
            return _original(*args,**kwargs)
        monkeypatch.setattr(owner,name,spy)
    def forbidden(*args,**kwargs):
        raise AssertionError("cold proof entered live selector, admission, fan-in or mutation")
    for name in ("_book_economic_full_fill_batch_v1","_economic_evaluation_v1","_economic_venue_funding_v1","_economic_opening_v1","_admit_economic_order_v1"):
        monkeypatch.setattr(live,name,forbidden)
    monkeypatch.setattr(live._CnASharePortfolioEconomicEngineV1,"run",forbidden)
    monkeypatch.setattr(k.AccountingJournal,"append",forbidden)
    monkeypatch.setattr(k.AccountingJournal,"append_many",forbidden)
    _verify_economic_native_result_v1(case=case,reader=store,result=result)
    # Each already-recorded fee is checked as evidence and again in its immutable native financial batch.
    from collections import Counter
    assert calls=={"book_fill":4,"charge_fee":4,"charge_order_fee":4,"assess":16}
    assert Counter(assessed_ids)==Counter({fee.fee_assessment_id:2 for fee in result.fee_assessments})


def test_fully_rehashed_omission_of_source_eligible_buy_admission_and_fill_is_rejected(tmp_path,monkeypatch):
    import crypto_quant_domain as d
    import crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 as live
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    from crypto_quant_backtest.engine import ExecutionTrace
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    _,case,inputs,store,_=economic_prepared_case_v1(tmp_path)
    original=live._economic_evaluation_v1
    omitted=next(i for i in inputs.scope.instrument_ids if i.venue.value=="xshe")
    def fake_budget_refusal(order,*args,**kwargs):
        result=original(order,*args,**kwargs)
        return (*result[:4],"native_cash_or_t1_unavailable") if order.intent.instrument_id==omitted else result
    with monkeypatch.context() as patch:
        patch.setattr(live,"_economic_evaluation_v1",fake_budget_refusal)
        forged=live._CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case).result
    assert forged is not None and len(forged.fills)==1
    assert all(f.instrument_id!=omitted for f in forged.fills)
    artifacts=[];replacements={}
    for artifact in forged.financial_artifacts:
        if artifact.role=="economic_opening_batch":
            payload=dict(artifact.payload.payload)
            payload["outcomes"]=tuple(v for v in payload["outcomes"] if v["reason"]!="native_cash_or_t1_unavailable")
            envelope=d.ArtifactEnvelope.create(artifact.payload.artifact_type,artifact.payload.schema_version,payload)
            changed=replace(artifact,payload=envelope,result_hash=d.canonical_sha256(envelope))
            replacements[artifact.artifact_hash]=changed.artifact_hash
            artifact=changed
        artifacts.append(artifact)
    head=d.canonical_sha256(tuple(a.artifact_hash for a in sorted((a for a in artifacts if a.role!="economic_attempt_witness"),key=lambda a:(a.occurred_at,a.source_event_id,a.role))))
    for index,artifact in enumerate(artifacts):
        if artifact.role=="economic_attempt_witness":
            payload=dict(artifact.payload.payload);witness=dict(payload["economic_witness"]);witness["checkpoint_head"]=head
            payload["economic_witness"]=witness;payload["economic_witness_hash"]=d.canonical_sha256(witness)
            envelope=d.ArtifactEnvelope.create(artifact.payload.artifact_type,2,payload)
            changed=replace(artifact,payload=envelope,result_hash=d.canonical_sha256(envelope))
            replacements[artifact.artifact_hash]=changed.artifact_hash;artifacts[index]=changed
    trace=ExecutionTrace(tuple(replace(row,evidence_hash=replacements.get(row.evidence_hash,row.evidence_hash)) for row in forged.trace.entries))
    forged=replace(forged,financial_artifacts=tuple(artifacts),trace=trace)
    # Native constructors recompute every changed envelope, trace and result hash; no stale hash rejection is accepted.
    assert d.canonical_sha256(forged)==forged.result_hash
    with pytest.raises(d.ArtifactIntegrityError,match="source-eligible pending candidate"):
        _verify_economic_native_result_v1(case=case,reader=store,result=forged)


@pytest.mark.parametrize("mutation",["filled_id","omit_activation","ordinal","evidence"])
def test_fully_rehashed_structurally_valid_terminal_records_require_exact_sealed_coordinates(tmp_path,monkeypatch,mutation):
    import crypto_quant_domain as d
    import crypto_quant_trading as native
    import crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 as live
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    _,case,inputs,store,_=economic_prepared_case_v1(tmp_path)
    original=live._terminal_economic_order_v1
    def changed_terminal(*args,**kwargs):
        stream=original(*args,**kwargs)
        records=list(stream.records);event=records[-1].event
        if mutation=="filled_id":
            event=replace(event,event_id="evt_"+d.canonical_sha256({"wrong_filled_id":event.event_id})[7:])
        elif mutation=="omit_activation":
            assert records[-2].event.event_type is d.OrderEventType.ORDER_ACTIVATED
            del records[-2]
            event=replace(event,causation_id=records[-2].event.event_id)
        elif mutation=="ordinal":
            event=replace(event,occurred_at=replace(event.occurred_at,source_sequence=d.SourceSequence(event.occurred_at.source_sequence.value+10)))
        else:
            event=replace(event,evidence_id=d.canonical_sha256({"unrelated_filled_evidence":event.evidence_id}))
        records[-1]=native.OrderEventRecord(event,records[-1].fill)
        return native.OrderEventStream(stream.order,tuple(records))
    with monkeypatch.context() as patch:
        patch.setattr(live,"_terminal_economic_order_v1",changed_terminal)
        result=live._CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case).result
    assert result is not None and len(result.fills)==2
    assert result.result_hash==d.canonical_sha256(result)
    with pytest.raises(d.ArtifactIntegrityError,match="terminal exact sealed activation/Fill"):
        _verify_economic_native_result_v1(case=case,reader=store,result=result)


@pytest.mark.parametrize("mutation",["expiry_id","expiry_clock","expiry_evidence"])
def test_native_structurally_valid_expiry_records_require_exact_sealed95_coordinates(recorded_buy_sell_batches,mutation):
    import crypto_quant_domain as d
    import crypto_quant_trading as native
    from crypto_quant_backtest.execution import NoEligibleBarAction
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _bind_economic_portfolio_sources_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _expected_terminal_stream_v1,_verify_recorded_terminal_v1
    inputs,batches,case,store,_=recorded_buy_sell_batches
    source,steps,_=batches[0];step=steps[0]
    stream=next(s for s in source.order_streams if s.order.order_id==step.opening.order_id)
    assert stream.order.intent.time_in_force is d.TimeInForce.DAY and stream.state.status is d.OrderStatus.ACCEPTED
    opening=replace(step.opening,action=NoEligibleBarAction.EXPIRE,reason="venue_extra_budget_unavailable",fill=None)
    bound=_bind_economic_portfolio_sources_v1(case,store)
    index=next(i for i,e in enumerate(bound.openings) if e.event_id==step.terms.bar_event_id)
    args=dict(case=case,stream=stream,opening=opening,signal_index=0,opening_index=index,ordinal=1,when=source.at.instant)
    expected=_expected_terminal_stream_v1(**args)
    assert expected.records[-1].event.occurred_at.phase.rank==95
    assert _verify_recorded_terminal_v1(terminal=expected,**args)==expected
    event=expected.records[-1].event
    if mutation=="expiry_id":event=replace(event,event_id="expiry.unrelated."+d.canonical_sha256(event.event_id)[7:])
    elif mutation=="expiry_clock":event=replace(event,occurred_at=replace(event.occurred_at,source_sequence=d.SourceSequence(index+2)))
    else:event=replace(event,evidence_id=d.canonical_sha256("unrelated expiry evidence"))
    supplied=native.OrderEventStream(stream.order,(*stream.records,native.OrderEventRecord(event,None)))
    assert supplied.state.status is d.OrderStatus.EXPIRED
    with pytest.raises(d.ArtifactIntegrityError,match="exact sealed"):
        _verify_recorded_terminal_v1(terminal=supplied,**args)


@pytest.mark.parametrize("mutation",["created_at_sequence","signal_origin"])
def test_rehashed_admission_requires_complete_source_order_and_signal_origin(tmp_path,monkeypatch,mutation):
    import crypto_quant_domain as d
    import crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 as live
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    _,case,inputs,store,_=economic_prepared_case_v1(tmp_path,cash_exit=True)
    original=live._admit_economic_order_v1
    admission_class=live._EconomicAdmissionV1
    def changed_admit(case,order,opening_index,admission,terms,observation,ordinal):
        if mutation=="created_at_sequence" and admission.signal_index==0:
            order=replace(order,created_at=replace(order.created_at,source_sequence=d.SourceSequence(order.created_at.source_sequence.value+1)))
            quote,market,issues,fee,reason=live._economic_evaluation_v1(order,observation,terms)
            assert reason is None
            object.__setattr__(admission,"fee",fee)
            object.__setattr__(admission,"quote",quote)
        return original(case,order,opening_index,admission,terms,observation,ordinal)
    def changed_origin(signal_index,*args,**kwargs):
        return admission_class(1 if signal_index==0 else signal_index,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(live,"_admit_economic_order_v1",changed_admit)
        if mutation=="signal_origin":patch.setattr(live,"_EconomicAdmissionV1",changed_origin)
        outcome=live._CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    assert outcome.result is not None and len(outcome.result.fills)==4
    assert outcome.result.result_hash==d.canonical_sha256(outcome.result)
    with pytest.raises(d.ArtifactIntegrityError,match="complete source Order or signal origin"):
        _verify_economic_native_result_v1(case=case,reader=store,result=outcome.result)
