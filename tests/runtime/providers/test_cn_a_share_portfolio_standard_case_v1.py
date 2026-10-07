"""Cold-source/coordinate probes only; not the actual October public A/B gate."""
from dataclasses import replace
from collections.abc import Mapping

import pytest
import crypto_quant_domain as d
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading import FinalFeeRuleSet, FinalFeeRuleSource
from crypto_quant_backtest import BacktestTargetStreamRepository
from crypto_quant_backtest.cn_a_share_portfolio_standard_case_v1 import (
    _native_initial_financial_state_v1, _read_opening_sources_v1,
    _standard_identity_plan_v1, _bind_standard_portfolio_sources_v1,
)
from crypto_quant_backtest.profile_portfolio_execution import (
    _ProfilePortfolioExecutionPlanV1, _ResolvedProfilePortfolioCaseV1,
    _profile_portfolio_semantic_spec_from_case,
)
from crypto_quant_backtest.engine import ExecutionCaseIdentityFactory
from crypto_quant_backtest.target_stream import PrecomputedTargetStream
from crypto_quant_backtest.timeline import DeterministicTimelineV2, TimelineWindow
from tests.runtime.providers.test_cn_a_share_portfolio_standard_definition_v1 import source_definition
from tests.runtime.providers.test_cn_a_share_portfolio_standard_native_state_v1 import _target
from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import _native_n
from tests.runtime.providers.test_cn_a_share_portfolio_preparation_inputs_v1 import _Cas
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    policies, fee_query, reservation_rule_set, final_order_rule_set,
)


def _sources():
    source = source_definition()
    values = _native_n(2, capital=10_000_000, price_units_by_code={"600000": 1137, "000001": 2231})
    bars = values[6]
    terms = list(source.opening_terms)
    market, tax = policies()
    for buy in source.opening_terms:
        definition = source.scope.instrument_catalog.instrument(buy.instrument_id)
        query = fee_query(d.OrderSide.SELL, buy.opening_at, venue=buy.instrument_id.venue.value,
            instrument_definition=definition)
        m, t = market.assess_fees(query).result, tax.assess_taxes(query).result
        assert m is not None and t is not None
        old = buy.final_fill_rules
        fill_rules = FinalFeeRuleSet.create(market_fee_policy_ref=old.market_fee_policy_ref,
            tax_policy_ref=old.tax_policy_ref, account_fee_schedule_ref=old.account_fee_schedule_ref,
            assessment_currency=old.assessment_currency, assessment_scale=old.assessment_scale,
            charge_rules=(*m.final_fill_charge_rules, t.final_fill_charge_rule,
                *(r for r in old.charge_rules if r.source is FinalFeeRuleSource.ACCOUNT_SCHEDULE)),
            minimums=old.minimums)
        terms.append(replace(buy, side=d.OrderSide.SELL, market_fee_resolution=m, tax_resolution=t,
            reservation_rules=reservation_rule_set(side=d.OrderSide.SELL, effective_at=buy.opening_at,
                venue=buy.instrument_id.venue.value, instrument_definition=definition),
            final_fill_rules=fill_rules,
            final_order_rules=final_order_rule_set(side=d.OrderSide.SELL, effective_at=buy.opening_at,
                venue=buy.instrument_id.venue.value, instrument_definition=definition)))
    daily = source.daily_marks[0]
    clock = d.SimulationInstant(daily.at.instant, d.TimelinePhase(100, "post_open_valuation"), daily.at.source_sequence)
    daily = replace(daily, at=clock, marks=tuple(replace(m,
        available_at_instant=clock, resolved_at_instant=clock) for m in daily.marks))
    start = source.signal_marks[0].at.instant
    end = d.UtcInstant(clock.instant.epoch_nanoseconds + 86_400_000_000_000)
    reader = InMemoryMarketBundleReader.build(bundle_key="standard.cold-source.test", schema_version=1,
        coverage_start=start, coverage_end_exclusive=end,
        instrument_catalog_hash=d.canonical_sha256(source.scope.instrument_catalog),
        capabilities=(bars[0].capability,), streams={bars[0].stream_key: bars})
    source = replace(source, scope=replace(source.scope, market_bundle_ref=reader.bundle_ref),
        opening_terms=tuple(sorted(terms, key=lambda term: (term.opening_at, term.instrument_id, term.side.value))),
        daily_marks=(daily,))
    store = _Cas()
    targets = PrecomputedTargetStream("targets", (_target(source, 0),))
    target_ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(
        d.ArtifactRef("fixture_context", 1, d.canonical_sha256("context")), targets)
    source = replace(source, scope=replace(source.scope, target_stream_ref=target_ref))
    window = TimelineWindow(start, start, end)
    return source, bars, reader, store, targets, window


def _case():
    source, bars, reader, store, targets, window = _sources()
    definition = source.definition()
    definition_ref = store.put(envelope=definition)
    plan = _ProfilePortfolioExecutionPlanV1(definition, _native_initial_financial_state_v1(source),
        (("definition", definition_ref), ("target_stream", source.scope.target_stream_ref.to_artifact_ref())))
    timeline = DeterministicTimelineV2.open(reader=reader, stream_keys=(bars[0].stream_key,),
        target_stream=targets, window=window)
    assert type(timeline) is DeterministicTimelineV2
    template = _ResolvedProfilePortfolioCaseV1("cn.standard.cold-source.test", 1, timeline, targets, 2,
        plan, d.canonical_sha256("unsealed"))
    rules = _standard_identity_plan_v1(source, targets, bars)
    spec = _profile_portfolio_semantic_spec_from_case(template, spec_key="cn.standard.cold-source.test", spec_version=1,
        identity_namespace=d.IdentityNamespace("backtest", "1"), identity_plan=rules)
    factory = ExecutionCaseIdentityFactory(semantic_run_id="cold-source-test-only",
        namespace=spec.identity_namespace, identity_plan=rules)
    for rule in rules:
        if rule.domain_kind is None:
            factory.event_id(rule.binding_key)
        else:
            factory.domain_id(rule.binding_key)
    case = replace(template, semantic_spec_hash=spec.semantic_spec_hash,
        semantic_spec=spec, identity_manifest=factory.manifest())
    return case, source, store, bars


def test_cold_source_binding_reads_whole_native_definition_and_target_projection():
    case, source, store, bars = _case()
    bound = _bind_standard_portfolio_sources_v1(case, store)
    assert bound.inputs == source and bound.openings == bars
    assert len(case.financial_state.settlement_rules.cash_rules) == 2
    assert all(not r.pending_receivable_tradable for r in case.financial_state.settlement_rules.cash_rules)
    assert all(not r.pending_receivable_sellable for r in case.financial_state.settlement_rules.position_rules)
    assert all(store.reads[ref] > 0 for _, ref in case.execution_case_plan.source_refs)
    assert source.trade_authorized is False


def test_native_coordinates_depend_on_scope_and_source_slots_not_prices_or_quantities():
    source, bars, reader, store, targets, window = _sources()
    original = _standard_identity_plan_v1(source, targets, bars)
    changed = replace(source, signal_marks=tuple(replace(b, marks=tuple(replace(m,
        price=replace(m.price, units=m.price.units + 1)) for m in b.marks)) for b in source.signal_marks))
    assert _standard_identity_plan_v1(changed, targets, bars) == original
    assert sum(r.domain_kind is d.DomainIdKind.ORDER for r in original) == len(source.scope.instrument_ids)
    assert all(r.domain_kind in (None, d.DomainIdKind.ORDER) for r in original)


def test_changed_target_producer_context_is_cold_read_transport_not_economic_identity():
    case, source, store, bars = _case()
    ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(
        d.ArtifactRef("fixture_context", 1, d.canonical_sha256("different producer context")), case.target_stream)
    changed = replace(case, execution_case_plan=replace(case.execution_case_plan,
        source_refs=(("definition", dict(case.execution_case_plan.source_refs)["definition"]),
                     ("target_stream", ref.to_artifact_ref()))))
    assert changed.case_hash == case.case_hash
    bound = _bind_standard_portfolio_sources_v1(changed, store)
    assert bound.inputs.scope.target_stream_ref == ref
    assert bound.inputs.definition() == source.definition()
    assert store.reads[ref.to_artifact_ref()] > 0

@pytest.mark.parametrize("part", ["half_side", "daily_before_open", "missing_stock", "later_fee_time"])
def test_cold_opening_sources_reject_half_rules_early_marks_and_substitution(part):
    source, bars, reader, store, targets, window = _sources()
    if part == "half_side":
        source = replace(source, opening_terms=tuple(t for t in source.opening_terms if t.side is d.OrderSide.BUY))
    elif part == "daily_before_open":
        daily = source.daily_marks[0]
        clock = d.SimulationInstant(daily.at.instant, d.TimelinePhase(30, "too_early"), daily.at.source_sequence)
        source = replace(source, daily_marks=(replace(daily, at=clock,
            marks=tuple(replace(m, available_at_instant=clock, resolved_at_instant=clock) for m in daily.marks)),))
    elif part == "missing_stock":
        reader = InMemoryMarketBundleReader.build(bundle_key="missing-stock", schema_version=1,
            coverage_start=window.data_start, coverage_end_exclusive=window.end_exclusive,
            instrument_catalog_hash=d.canonical_sha256(source.scope.instrument_catalog),
            capabilities=(bars[0].capability,), streams={bars[0].stream_key: bars[:1]})
        source = replace(source, scope=replace(source.scope, market_bundle_ref=reader.bundle_ref))
    else:
        source = replace(source, opening_terms=tuple(replace(t,
            notional_evidence=replace(t.notional_evidence, available_at=d.UtcInstant(t.opening_at.epoch_nanoseconds - 1)))
            for t in source.opening_terms))
    with pytest.raises(ValueError, match="source terms|valuation|cover|substitution"):
        _read_opening_sources_v1(source, reader, window)


@pytest.mark.parametrize("part", ["missing_retained", "changed_transport_economics", "borrowed_state", "wrong_slots"])
def test_cold_native_case_rejects_missing_bytes_foreign_state_and_slot_seal(part):
    case, source, store, bars = _case()
    if part == "missing_retained":
        del store.values[dict(case.execution_case_plan.source_refs)["definition"]]
        with pytest.raises(d.ArtifactNotFoundError):
            _bind_standard_portfolio_sources_v1(case, store)
        return
    if part == "changed_transport_economics":
        event = case.target_stream.events[0]
        payload = event.payload["candidate"]
        assert isinstance(payload, Mapping)
        candidate = dict(payload)
        candidate["targets"] = []
        changed = PrecomputedTargetStream("targets", (replace(event,
            payload={"schema_version": 1, "candidate": candidate}),))
        ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(
            d.ArtifactRef("fixture_context", 1, d.canonical_sha256("other")), changed)
        case = replace(case, execution_case_plan=replace(case.execution_case_plan,
            source_refs=(("definition", dict(case.execution_case_plan.source_refs)["definition"]),
                         ("target_stream", ref.to_artifact_ref()))))
    elif part == "borrowed_state":
        rules = case.financial_state.settlement_rules
        # Build a valid differently configured native policy, not an invalid hash fixture.
        from crypto_quant_trading import MarketSettlementRules
        wrong = MarketSettlementRules.create(policy_key=rules.policy_key, policy_version=rules.policy_version,
            account_id=rules.account_id, cash_rules=tuple(replace(r, pending_receivable_tradable=True)
                for r in rules.cash_rules), position_rules=rules.position_rules)
        case = replace(case, execution_case_plan=replace(case.execution_case_plan,
            financial_state=replace(case.financial_state, settlement_rules=wrong)))
    else:
        assert case.semantic_spec is not None
        assert case.identity_manifest is not None
        spec = replace(case.semantic_spec, identity_plan=case.semantic_spec.identity_plan[:-1])
        case = replace(case, semantic_spec=spec, semantic_spec_hash=spec.semantic_spec_hash,
            identity_manifest=replace(case.identity_manifest, bindings=case.identity_manifest.bindings[:-1]))
    with pytest.raises(ValueError, match="projection|native initial state|identity coordinate|semantic"):
        _bind_standard_portfolio_sources_v1(case, store)
