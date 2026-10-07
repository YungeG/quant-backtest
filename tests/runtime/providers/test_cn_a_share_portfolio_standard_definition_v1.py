"""Source-definition constructor/decoder checks, not public economic A/B acceptance."""
from dataclasses import replace
import hashlib
import json

import pytest
import crypto_quant_domain as d
from crypto_quant_trading import ResolvedMark
from crypto_quant_backtest.cn_a_share_portfolio_standard_definition_v1 import (
    CnASharePortfolioOpeningTermsDevelopmentV1,
    CnASharePortfolioMarkBatchDevelopmentV1,
    CnASharePortfolioStandardDevelopmentInputsV1,
    _read_standard_definition_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_daily_nav_diagnostic_v1 import CnAShareRetainedDividendGuardV1
from crypto_quant_backtest.target_repository import BacktestTargetStreamRef
from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import _native_n, COST_BASIS, QUANTIZATION


def source_definition():
    # Fixture-native rules only; no diagnostic Case/Result is converted, no
    # prospective Order/approval/quantity/Fill enters the resulting DTO.
    scope, journal, schema, at, steps, calendars, bars, witnesses, rules = _native_n(
        2, capital=10_000_000, price_units_by_code={"600000": 1137, "000001": 2231})
    scope = replace(scope, initial_cash=d.Money(10_000_000, d.Scale(2), "CNY"))
    terms = []
    for step, bar, witness in zip(steps, bars, witnesses, strict=True):
        risk = step.risk
        market = risk.market
        spec = market.evaluation_input.executable_order_spec
        liquidity, state, zero = witness
        assert zero is not None
        terms.append(CnASharePortfolioOpeningTermsDevelopmentV1(
            bar.event_id, bar.event_hash, bar.instrument_id, d.OrderSide.BUY,
            spec.capability_approval.capability_set, spec.translation_mapping,
            market.rule_timeline, market.evaluation_input.notional_evidence,
            risk.fee.fee_estimate.rule_set, step.final_fill_rules, step.final_order_rules,
            step.market_fee_resolution, step.tax_resolution, liquidity, state, zero))
    before = d.UtcInstant(at.epoch_nanoseconds - 86_400_000_000_000)

    def marks(when):
        clock = d.SimulationInstant(when, d.TimelinePhase(30, "source_valuation"), d.SourceSequence(1))
        prices = {"600000": 1137, "000001": 2231}
        values = tuple(ResolvedMark(i, d.CurrencyId("CNY"), d.PricePurpose.VALUATION,
            d.Price(prices[i.stable_key], d.Scale(2), str(i), "CNY"), when, when, when, 0,
            "synthetic.source.marks", "source-mark:" + str(i), "fixture.rev1",
            "synthetic.source.mark", 1, d.canonical_sha256("source-mark"),
            available_at_instant=clock, resolved_at_instant=clock) for i in scope.instrument_ids)
        return CnASharePortfolioMarkBatchDevelopmentV1(clock, values)

    fields = ["ts_code", "end_date", "ann_date", "div_proc", "stk_div", "stk_bo_rate", "stk_co_rate",
        "cash_div", "cash_div_tax", "record_date", "ex_date", "pay_date", "div_listdate", "imp_ann_date"]
    raw = json.dumps({"code": 0, "data": {"fields": fields, "items": []}}).encode()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    guards = tuple(CnAShareRetainedDividendGuardV1(raw, digest,
        i.stable_key + (".SH" if i.venue.value == "xshg" else ".SZ")) for i in scope.instrument_ids)
    return CnASharePortfolioStandardDevelopmentInputsV1(scope, journal, calendars,
        steps[0].risk.plan.policy, tuple(terms), (marks(before),), (marks(at),),
        COST_BASIS, QUANTIZATION, guards)


def test_source_only_definition_round_trip_retains_native_full_clocks_and_rule_facts():
    source = source_definition()
    envelope = source.definition()
    decoded = _read_standard_definition_v1(envelope, source.scope.target_stream_ref)
    assert decoded == source
    assert decoded.definition() == envelope
    assert all(m.available_at_instant is not None and m.resolved_at_instant is not None
        for b in decoded.signal_marks for m in b.marks)
    assert decoded.source_qualification_verified is False
    assert decoded.broker_shared_pool_verified is False
    assert decoded.trade_authorized is False
    payload = json.loads(d.canonical_bytes(envelope))
    assert "target_stream_ref" not in payload["payload"]["scope"]
    assert not any(name in payload["payload"] for name in
        ("order", "opening", "fill", "risk", "allocation", "quantities", "financial_result"))


def test_source_definition_target_context_changes_transport_not_economics():
    source = source_definition()
    changed = replace(source, scope=replace(source.scope, target_stream_ref=BacktestTargetStreamRef(
        d.ArtifactRef("backtest_target_stream", 1, d.canonical_sha256("another-context")))))
    assert changed.definition() == source.definition()
    assert d.canonical_bytes(changed) != d.canonical_bytes(source)


def test_source_marks_reject_same_utc_future_resolution_phase():
    source = source_definition()
    batch = source.signal_marks[0]
    future = d.SimulationInstant(batch.at.instant, d.TimelinePhase(31, "future_resolution"), batch.at.source_sequence)
    marks = (replace(batch.marks[0], resolved_at_instant=future), *batch.marks[1:])
    with pytest.raises(ValueError, match="future"):
        replace(batch, marks=marks)


def test_source_definition_declared_capital_must_match_native_initial_journal():
    source = source_definition()
    with pytest.raises(ValueError, match="declared CNY capital"):
        replace(source, scope=replace(source.scope,
            initial_cash=d.Money(source.scope.initial_cash.units + 1, d.Scale(2), "CNY")))


@pytest.mark.parametrize("field", ["fees", "realized_pnl", "financing"])
def test_initial_capital_entry_cannot_smuggle_economic_attributions(field):
    from crypto_quant_trading import AccountingJournal
    source = source_definition()
    entries = source.initial_journal.entries
    changed = replace(entries[0], **{field: (d.Money(1, d.Scale(2), "CNY"),)})
    journal = AccountingJournal.from_entries((changed, *entries[1:]))
    with pytest.raises(ValueError, match="capital-only"):
        replace(source, initial_journal=journal)


def test_source_marks_cannot_drop_both_exact_clock_fields():
    source = source_definition()
    batch = source.signal_marks[0]
    marks = tuple(replace(m, available_at_instant=None, resolved_at_instant=None) for m in batch.marks)
    with pytest.raises(ValueError, match="full-clock"):
        replace(batch, marks=marks)


@pytest.mark.parametrize("field", ["reservation_rules", "final_fill_rules", "final_order_rules"])
def test_fee_rules_cannot_disagree_with_retained_market_band_under_same_refs(field):
    from crypto_quant_trading import (
        FeeReservationRuleSet, FeeReservationRuleSource, FinalFeeRuleSet, FinalFeeRuleSource,
    )
    source = source_definition()
    term = source.opening_terms[0]
    rule_set = getattr(term, field)
    source_kind = FeeReservationRuleSource.MARKET_FEE if field == "reservation_rules" else FinalFeeRuleSource.MARKET_FEE
    charges = list(rule_set.charge_rules)
    index = next(i for i, rule in enumerate(charges) if rule.source is source_kind
                 and (field == "final_order_rules" or rule.rate is not None))
    old = charges[index]
    if field == "final_order_rules":
        from crypto_quant_trading import FinalFeeApplicability
        charges[index] = replace(old, applicability=FinalFeeApplicability.ALWAYS,
            rate=d.Rate(1, d.Scale(4), "fee_fraction"))
    else:
        charges[index] = replace(old, rate=d.Rate(0, d.Scale(0), "fee_fraction"))
    if field == "reservation_rules":
        changed = FeeReservationRuleSet.create(
            market_fee_policy_ref=rule_set.market_fee_policy_ref, tax_policy_ref=rule_set.tax_policy_ref,
            account_fee_schedule_ref=rule_set.account_fee_schedule_ref,
            reservation_currency=rule_set.reservation_currency, reservation_scale=rule_set.reservation_scale,
            charge_rules=tuple(charges), minimums=rule_set.minimums)
    else:
        changed = FinalFeeRuleSet.create(
            market_fee_policy_ref=rule_set.market_fee_policy_ref, tax_policy_ref=rule_set.tax_policy_ref,
            account_fee_schedule_ref=rule_set.account_fee_schedule_ref,
            assessment_currency=rule_set.assessment_currency, assessment_scale=rule_set.assessment_scale,
            charge_rules=tuple(charges), minimums=rule_set.minimums)
    with pytest.raises(ValueError, match="retained fee resolution"):
        replace(term, **{field: changed})


@pytest.mark.parametrize("mutation", ["unknown", "source_grade", "wrong_band", "missing_guard", "bad_guard_hash", "drop_clock", "buffer_count"])
def test_source_definition_rejects_schema_fee_and_action_provenance_drift(mutation):
    source = source_definition()
    payload = json.loads(d.canonical_bytes(source.definition()))["payload"]
    if mutation == "unknown":
        payload["unexpected"] = True
    elif mutation == "source_grade":
        payload["source_qualification_verified"] = True
    elif mutation == "wrong_band":
        payload["opening_terms"][0]["market_fee_resolution"]["active_band_hash"] = d.canonical_sha256("wrong")
    elif mutation == "missing_guard":
        payload["dividend_guards"] = payload["dividend_guards"][:-1]
    elif mutation == "bad_guard_hash":
        payload["dividend_guards"][0]["response_sha256"] = d.canonical_sha256("wrong")
    elif mutation == "drop_clock":
        for mark in payload["signal_marks"][0]["marks"]:
            mark.pop("available_at_instant")
            mark.pop("resolved_at_instant")
    else:
        payload["opening_terms"][0]["maximum_fill_count"] += 1
    bad = d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", 1, payload)
    with pytest.raises((ValueError, TypeError)):
        _read_standard_definition_v1(bad, source.scope.target_stream_ref)
