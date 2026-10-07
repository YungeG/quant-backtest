"""Synthetic Aug2023 GTC cancel/RunEnd closure; no actual strategy evidence."""
from dataclasses import replace
import json

import pytest
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading.profiles.cn_a_share.portfolio_order_capability_development_v1 import (
    cn_a_share_portfolio_cash_capabilities_development_v1,
)
from crypto_quant_backtest import BacktestTargetStreamRepository
from crypto_quant_backtest.cn_a_share_portfolio_standard_engine_v1 import _CnASharePortfolioStandardEngineV1
from crypto_quant_backtest.cn_a_share_portfolio_standard_result_v1 import _verify_standard_native_result_v1
from crypto_quant_backtest.cn_a_share_portfolio_standard_case_v1 import (
    _native_initial_financial_state_v1, _standard_identity_plan_v1,
)
from crypto_quant_backtest.engine import ExecutionCaseIdentityFactory
from crypto_quant_backtest.execution import BarLiquidityEvidence
from crypto_quant_backtest.profile_portfolio_execution import (
    _ProfilePortfolioExecutionPlanV1, _ResolvedProfilePortfolioCaseV1,
    _profile_portfolio_semantic_spec_from_case,
)
from crypto_quant_backtest.slippage import SlippageApplicabilityEnvelope
from crypto_quant_backtest.target_stream import PrecomputedTargetStream
from crypto_quant_backtest.timeline import DeterministicTimelineV2, TimelineWindow
from tests.runtime.providers.test_cn_a_share_portfolio_standard_case_v1 import _sources
from tests.runtime.providers.test_cn_a_share_portfolio_standard_native_state_v1 import _target
from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import _native_n
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    policies, fee_query, reservation_rule_set, final_order_rule_set,
)


@pytest.fixture(scope="module", params=[False, True], ids=["real", "initial_gap"])
def cancelled_result(request):
    source, friday_bars, _, store, _, _ = _sources()
    monday = d.UtcInstant(friday_bars[0].event_time.epoch_nanoseconds + 3 * 86_400_000_000_000)
    # Extract immutable SOURCES only; the old fixture's quantities/Fills are not
    # inputs to this Engine. Its live sizing starts again from capital-only cash.
    native = _native_n(2, capital=10_000_000, at_override=monday,
        price_units_by_code={"600000": 1137, "000001": 2231})
    bars, added = [], []
    for step, raw, witnesses in zip(native[4], native[6], native[7], strict=True):
        raw = replace(raw, event_id=raw.event_id + ".monday")
        instrument = raw.instrument_id
        assert instrument is not None
        base = next(term for term in source.opening_terms
            if term.instrument_id == instrument and term.side is d.OrderSide.BUY)
        market = step.risk.market
        liquidity, state, zero = witnesses
        assert zero is not None
        liquidity = BarLiquidityEvidence.create(evidence_key="cancel.synthetic.real.buy", evidence_version=1,
            market_event=raw, evaluated_at=monday, approved=True, reason_code=None, source_hash=raw.event_hash)
        state = replace(state, source_event_id=raw.event_id, evidence_hash=raw.event_hash)
        buy = replace(base, bar_event_id=raw.event_id, bar_event_hash=raw.event_hash,
            rule_timeline=market.rule_timeline, notional_evidence=market.evaluation_input.notional_evidence,
            reservation_rules=step.risk.fee.fee_estimate.rule_set,
            final_fill_rules=step.final_fill_rules, final_order_rules=step.final_order_rules,
            market_fee_resolution=step.market_fee_resolution, tax_resolution=step.tax_resolution,
            liquidity=liquidity, market_state=state, slippage_model=zero)
        definition = source.scope.instrument_catalog.instrument(instrument)
        mp, tp = policies()
        query = fee_query(d.OrderSide.SELL, monday, venue=instrument.venue.value, instrument_definition=definition)
        market_fees, tax = mp.assess_fees(query).result, tp.assess_taxes(query).result
        assert market_fees is not None and tax is not None
        fill_rules = replace(buy.final_fill_rules, charge_rules=(*market_fees.final_fill_charge_rules,
            tax.final_fill_charge_rule, *(r for r in buy.final_fill_rules.charge_rules
                if r.source is t.FinalFeeRuleSource.ACCOUNT_SCHEDULE)))
        sell = replace(buy, side=d.OrderSide.SELL, market_fee_resolution=market_fees, tax_resolution=tax,
            reservation_rules=reservation_rule_set(side=d.OrderSide.SELL, effective_at=monday,
                venue=instrument.venue.value, instrument_definition=definition), final_fill_rules=fill_rules,
            final_order_rules=final_order_rule_set(side=d.OrderSide.SELL, effective_at=monday,
                venue=instrument.venue.value, instrument_definition=definition),
            liquidity=BarLiquidityEvidence.create(evidence_key="cancel.synthetic.blocked.sell", evidence_version=1,
                market_event=raw, evaluated_at=monday, approved=False, reason_code="synthetic_limit_lock",
                source_hash=raw.event_hash))
        bars.append(raw)
        added.extend((buy, sell))
    base_terms = source.opening_terms
    if request.param:
        missing = friday_bars[-1]
        friday_bars = (*friday_bars[:-1], replace(missing, payload={"schema_version": 1,
            "bar_kind": "gap_placeholder", "open_price": None}))
        # The DTO's whole-scope term guard stays intact: this instrument has
        # real Monday BUY/SELL sources, just no fake price/rules for Friday's gap.
        base_terms = tuple(term for term in base_terms if term.bar_event_id != missing.event_id)
    bars = tuple((*friday_bars, *bars))

    def shifted(batch, when):
        clock = replace(batch.at, instant=when)
        return replace(batch, at=clock, marks=tuple(replace(m, observed_at=when, available_at=when,
            resolved_at=when, available_at_instant=clock, resolved_at_instant=clock) for m in batch.marks))

    before_monday = d.UtcInstant(monday.epoch_nanoseconds - 1)
    after_monday = d.UtcInstant(monday.epoch_nanoseconds + 3_600_000_000_000)
    close = d.UtcInstant(monday.epoch_nanoseconds + 7_200_000_000_000)
    end = d.UtcInstant(monday.epoch_nanoseconds + 86_400_000_000_000)
    window = TimelineWindow(source.signal_marks[0].at.instant, source.signal_marks[0].at.instant, end)
    reader = InMemoryMarketBundleReader.build(bundle_key="native.cancel.synthetic", schema_version=1,
        coverage_start=window.data_start, coverage_end_exclusive=end,
        instrument_catalog_hash=d.canonical_sha256(source.scope.instrument_catalog),
        capabilities=(bars[0].capability,), streams={bars[0].stream_key: bars})

    def widen(term):
        envelope = term.slippage_model.applicability_envelope
        wide = SlippageApplicabilityEnvelope.create(envelope_key=envelope.envelope_key,
            envelope_version=envelope.envelope_version, instrument_id=envelope.instrument_id,
            valid_from=envelope.valid_from, valid_to_exclusive=envelope.valid_to_exclusive,
            maximum_quantity=replace(envelope.maximum_quantity, units=1_000_000),
            allowed_market_state_keys=envelope.allowed_market_state_keys)
        return replace(term, capability_set=cn_a_share_portfolio_cash_capabilities_development_v1(),
            slippage_model=replace(term.slippage_model, applicability_envelope=wide))

    source = replace(source, scope=replace(source.scope, market_bundle_ref=reader.bundle_ref),
        signal_marks=(source.signal_marks[0], shifted(source.signal_marks[0], before_monday),
            shifted(source.signal_marks[0], after_monday)),
        daily_marks=(source.daily_marks[0], shifted(source.daily_marks[0], close)),
        opening_terms=tuple(sorted((widen(t) for t in (*base_terms, *added)),
            key=lambda t: (t.opening_at, t.instrument_id, t.side.value))))
    targets = PrecomputedTargetStream("targets",
        (_target(source, 0), _target(source, 1, selected=()), _target(source, 2, selected=())))
    target_ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(
        d.ArtifactRef("fixture_context", 1, d.canonical_sha256("synthetic.cancel")), targets)
    source = replace(source, scope=replace(source.scope, target_stream_ref=target_ref))
    definition = source.definition()
    plan = _ProfilePortfolioExecutionPlanV1(definition, _native_initial_financial_state_v1(source),
        (("definition", store.put(envelope=definition)), ("target_stream", target_ref.to_artifact_ref())))
    timeline = DeterministicTimelineV2.open(reader=reader, stream_keys=(bars[0].stream_key,),
        target_stream=targets, window=window)
    assert type(timeline) is DeterministicTimelineV2
    template = _ResolvedProfilePortfolioCaseV1("native.cancel.synthetic", 1, timeline, targets, 2,
        plan, d.canonical_sha256("unsealed"))
    identities = _standard_identity_plan_v1(source, targets, bars)
    spec = _profile_portfolio_semantic_spec_from_case(template, spec_key="native.cancel.synthetic", spec_version=1,
        identity_namespace=d.IdentityNamespace("backtest", "1"), identity_plan=identities)
    factory = ExecutionCaseIdentityFactory(semantic_run_id="native-cancel-synthetic-only",
        namespace=spec.identity_namespace, identity_plan=identities)
    for rule in identities:
        if rule.domain_kind is None:
            factory.event_id(rule.binding_key)
        else:
            factory.domain_id(rule.binding_key)
    case = replace(template, semantic_spec_hash=spec.semantic_spec_hash, semantic_spec=spec,
        identity_manifest=factory.manifest())
    outcome = _CnASharePortfolioStandardEngineV1(artifact_reader=store)._run(case, None)
    assert outcome.result is not None, outcome
    _verify_standard_native_result_v1(case=case, reader=store, result=outcome.result.to_canonical_dict())
    return case, store, outcome.result


@pytest.mark.parametrize("part", ["valid", "omit_cancel", "cancel_evidence"])
def test_gtc_supersession_closes_native_cancel_history(cancelled_result, part):
    case, store, result = cancelled_result
    sellers = [s for s in result.order_streams if s.order.intent.side is d.OrderSide.SELL]
    assert len(sellers) == len(result.fills) and len(sellers) in {1, 2}
    assert all(s.state is not None and s.state.status is d.OrderStatus.CANCELLED for s in sellers)
    assert not result.run_end_report.terminated_orders and not result.run_end_report.released_reservations
    if part == "valid":
        assert all(s.order.intent.time_in_force is d.TimeInForce.GTC for s in sellers)
        witness = next(a.payload.payload for a in result.financial_artifacts if a.role == "native_attempt_witness")
        assert len(witness["pending_intentions"]) == len(sellers)  # New intentions, not actual exits.
        return
    stream = sellers[0]
    records = stream.records[:-2] if part == "omit_cancel" else (*stream.records[:-1],
        replace(stream.records[-1], event=replace(stream.records[-1].event,
            evidence_id=d.canonical_sha256("foreign-cancel-proof"))))
    forged = t.OrderEventStream.from_records(stream.order, records)
    raw = json.loads(d.canonical_bytes(result.to_canonical_dict()))
    raw["order_streams"][result.order_streams.index(stream)] = json.loads(d.canonical_bytes(forged))
    with pytest.raises(ValueError, match="standard native"):
        _verify_standard_native_result_v1(case=case, reader=store, result=raw)


@pytest.mark.parametrize("part", ["omit_fact", "wrong_action"])
def test_nonreal_day_intention_retains_exact_fact(cancelled_result, part):
    case, store, result = cancelled_result
    from tests.runtime.providers.test_cn_a_share_portfolio_standard_engine_v1 import _reseal
    raw = json.loads(d.canonical_bytes(result.to_canonical_dict()))
    gaps = [a for a in raw["financial_artifacts"] if a["role"] == "pending_no_real_open"]
    if not gaps:
        pytest.skip("real-opening fixture has no non-real intention")
    assert len(gaps) == 1 and len(result.fills) == 1
    artifact = gaps[0]
    assert artifact["payload"]["payload"]["action"] == "expire_at_daily_close"
    day = next(a for a in raw["financial_artifacts"] if a["role"] == "native_daily_snapshot")
    assert not day["payload"]["payload"]["pending_intentions"]
    index = raw["financial_artifacts"].index(artifact)
    if part == "omit_fact":
        raw["financial_artifacts"].pop(index)
        raw["trace"]["entries"].pop(index)
        for i, entry in enumerate(raw["trace"]["entries"]):
            entry["sequence"] = i
    else:
        artifact["payload"]["payload"]["action"] = "keep_intent"
        _reseal(raw, artifact)
    with pytest.raises(ValueError, match="standard native"):
        _verify_standard_native_result_v1(case=case, reader=store, result=raw)
