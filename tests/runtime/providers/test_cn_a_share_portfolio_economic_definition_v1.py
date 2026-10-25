from dataclasses import fields, replace
import json

import pytest
import crypto_quant_domain as d
from crypto_quant_backtest.cn_a_share_portfolio_economic_definition_v1 import (
    CnASharePortfolioEconomicDevelopmentInputsV1 as Inputs,
    CnASharePortfolioEconomicOpeningTermsV1 as Terms,
    _read_economic_definition_v1 as read,
)
from crypto_quant_backtest.target_repository import BacktestTargetStreamRef
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_definition_source_v1


def test_economic_definition_exact_dtos_and_strict_roundtrip():
    source = economic_definition_source_v1()
    envelope = source.definition()
    assert len([f for f in fields(Inputs) if f.init]) == 12
    assert len([f for f in fields(Terms) if f.init]) == 17
    assert envelope.artifact_type == "backtest_profile_portfolio_definition" and envelope.schema_version == 2
    assert len(envelope.payload) == 17
    result = read(envelope, source.scope.target_stream_ref, source.dividend_actions)
    assert d.canonical_bytes(result) == d.canonical_bytes(source)
    assert d.canonical_bytes(result.definition()) == d.canonical_bytes(envelope)
    assert source._definition_source_hash == d.canonical_sha256(envelope)
    assert all(t.maximum_fill_count == 1 and t.slippage_model.basis_points_units == 5 for t in source.opening_terms)
    assert result.initial_marks.at == source.initial_marks.at
    assert all(m.available_at_instant is not None and m.resolved_at_instant is not None
        for b in (result.initial_marks, *result.signal_marks, *result.daily_marks, *result.checkpoint_marks) for m in b.marks)
    assert not source.trade_authorized and not source.broker_shared_pool_verified and not source.source_qualification_verified


def test_economic_definition_target_transport_excluded_but_actions_bound():
    source = economic_definition_source_v1()
    assert "target_stream_ref" not in source.economic_payload()["scope"]
    target = BacktestTargetStreamRef(d.ArtifactRef.from_envelope(d.ArtifactEnvelope.create("backtest_target_stream", 1, {"fixture": "different-transport"})))
    changed = replace(source, scope=replace(source.scope, target_stream_ref=target))
    assert changed.definition() == source.definition()
    assert d.canonical_bytes(changed) != d.canonical_bytes(source)
    with pytest.raises(ValueError, match="ActionSet"):
        read(source.definition(), source.scope.target_stream_ref,
             replace(source.dividend_actions, coverage_end_exclusive=d.UtcInstant(source.dividend_actions.coverage_end_exclusive.epoch_nanoseconds + 1)))


@pytest.mark.parametrize("mutation", ["missing", "extra", "schema_bool", "flag", "hash", "target", "clock", "mark_extra", "bps_float", "max_fills"])
def test_economic_definition_rejects_structural_and_equal_hash_substitutions(mutation):
    source = economic_definition_source_v1()
    raw = json.loads(d.canonical_bytes(source.economic_payload()))
    if mutation == "missing":
        del raw["checkpoint_marks"]
    elif mutation == "extra":
        raw["equity_override"] = 0
    elif mutation == "schema_bool":
        raw["schema_version"] = True
    elif mutation == "flag":
        raw["trade_authorized"] = True
    elif mutation == "hash":
        raw["cash_dividend_action_set_hash"] = d.canonical_sha256("different-actions")
    elif mutation == "target":
        raw["scope"]["target_stream_ref"] = source.scope.target_stream_ref.to_canonical_dict()
    elif mutation == "clock":
        del raw["initial_marks"]["marks"][0]["available_at_instant"]
    elif mutation == "mark_extra":
        raw["initial_marks"]["marks"][0]["qualified"] = True
    elif mutation == "bps_float":
        # Artifact canonicalization itself must reject float, before decoding.
        with pytest.raises(ValueError):
            d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", 2,
                {**raw, "float_override": 1.2})
        return
    else:
        raw["opening_terms"][0]["maximum_fill_count"] = 2
    envelope = d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", 2, raw)
    with pytest.raises((TypeError, ValueError)):
        read(envelope, source.scope.target_stream_ref, source.dividend_actions)


def test_economic_inputs_reject_future_initial_source_and_capital_or_scope_substitution():
    source = economic_definition_source_v1()
    with pytest.raises(ValueError):
        replace(source, initial_marks=source.signal_marks[0])
    with pytest.raises(ValueError):
        replace(source, scope=replace(source.scope, initial_cash=replace(source.scope.initial_cash, units=1)))
    with pytest.raises(ValueError):
        replace(source, dividend_actions=replace(source.dividend_actions, account_id="foreign"))
    with pytest.raises(TypeError):
        replace(source, trade_authorized=True)
    with pytest.raises(TypeError):
        replace(source.opening_terms[0], maximum_fill_count=True)


def test_economic_initial_plan4_roundtrip_has_no_prospective_claim_or_id_mapping():
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _native_initial_economic_financial_state_v1
    from crypto_quant_backtest.profile_portfolio_execution import _ProfilePortfolioExecutionPlanV2
    from crypto_quant_backtest.execution_inputs import _read_execution_case_plan_v9, _read_execution_case_plan_v8
    source = economic_definition_source_v1()
    financial, state, projection = _native_initial_economic_financial_state_v1(source)
    actions = d.ArtifactEnvelope.create("cn_a_share_cash_dividend_action_set", 1, source.dividend_actions)
    plan = _ProfilePortfolioExecutionPlanV2(source.definition(), financial, state, projection,
        (("cash_dividend_action_set", d.ArtifactRef.from_envelope(actions)),
         ("definition", d.ArtifactRef.from_envelope(source.definition())),
         ("target_stream", source.scope.target_stream_ref.to_artifact_ref())))
    raw = json.loads(d.canonical_bytes(plan))
    assert raw["schema_version"] == 4 and len(raw) == 7
    assert state.claims == () and projection.base_snapshot == projection.snapshot
    assert projection.snapshot == financial.initial_snapshot
    assert "journal_entry_ids" not in raw and "journal_entry_ids" not in source.economic_payload()
    decoded = _read_execution_case_plan_v9(raw)
    assert d.canonical_bytes(decoded) == d.canonical_bytes(plan)
    with pytest.raises(ValueError):
        _read_execution_case_plan_v8(raw)
    with pytest.raises(ValueError):
        replace(plan, source_refs=plan.source_refs[:-1])


@pytest.mark.parametrize("tax_shortfall", [False, True])
def test_public_economic_prepare_input9_seals_sources_and_all_future_journal_slots(tmp_path, tax_shortfall):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_public_sources_v1
    from tests.runtime.providers.test_cash_development_provider import build_manifest
    from crypto_quant_backtest import CashDevelopmentRequestIntent
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v1 import prepare_cn_a_share_portfolio_economic_development_backtest, _registry
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _bind_economic_portfolio_sources_v1
    from crypto_quant_backtest.composition import _compose_profile_portfolio_economic_execution_case
    from crypto_quant_backtest.execution_inputs import _EXECUTION_INPUT_CATALOG, _read_execution_inputs_v9_from_snapshot
    from crypto_quant_backtest.resolution import ProfileResolver
    source, bars, market, store, target, window = economic_public_sources_v1(tax_shortfall=tax_shortfall)
    prepared = prepare_cn_a_share_portfolio_economic_development_backtest(
        request_intent=CashDevelopmentRequestIntent(1, "economic.preparation.only", window,
            source.scope.account_id, d.CurrencyId("CNY"), 0), provider_inputs=source,
        build_artifact_manifest=build_manifest(), artifact_reader=store, artifact_publisher=store,
        market_reader=market, publication_root=tmp_path)
    assert prepared.execution_request.schema_version == 9
    bundle, failure = _read_execution_inputs_v9_from_snapshot(store, prepared.execution_request)
    assert failure is None
    resolved = ProfileResolver().resolve(request=prepared.execution_request.request,
        registry=_registry(source), market_bundle_manifest=market.manifest,
        build_artifact_manifest=bundle.build_artifact_manifest).resolved
    assert resolved is not None and resolved.semantic_run_id == prepared.semantic_run_id
    case = _compose_profile_portfolio_economic_execution_case(resolved_request=resolved, market_reader=market,
        semantic_spec=bundle.execution_case_semantic_spec, target_stream=bundle.target_stream,
        timeline_stream_keys=bundle.timeline_stream_keys, timeline_batch_size=64, execution_case_plan=bundle.execution_case_plan)
    bound = _bind_economic_portfolio_sources_v1(case, store)
    assert d.canonical_bytes(bound.inputs) == d.canonical_bytes(source) and bound.openings == bars
    assert len(bound.journal_entry_ids) == (4 if tax_shortfall else 2)
    assert len(set(v for _, v in bound.journal_entry_ids)) == len(bound.journal_entry_ids)
    assert all(v.kind is d.DomainIdKind.JOURNAL for _, v in bound.journal_entry_ids)
    assert case.execution_case_plan.initial_dividend_state.claims == ()
    assert all(not e.entry_type.value.startswith("corporate_action") for e in case.financial_state.journal.entries)
    assert case.verify_identity_manifest(prepared.semantic_run_id)
    class BrokenReader:
        def read(self, *, ref):
            raise OSError("input9 I/O original cause")
    with pytest.raises(OSError, match="original cause"):
        _read_execution_inputs_v9_from_snapshot(BrokenReader(), prepared.execution_request)


def test_old_definition_and_zero_guard_remain_separate():
    from tests.runtime.providers.test_cn_a_share_portfolio_standard_definition_v1 import source_definition
    old = source_definition()
    assert old.definition().schema_version == 1
    with pytest.raises(ValueError, match="zero-slippage"):
        replace(old.opening_terms[0], slippage_model=economic_definition_source_v1().opening_terms[0].slippage_model)
    source = economic_definition_source_v1(bps=0)
    assert source.opening_terms[0].slippage_model.basis_points_units == 0
    with pytest.raises(TypeError):
        read(old.definition(), source.scope.target_stream_ref, source.dividend_actions)
