"""#30 approved public Engine/Backtest seams; synthetic prices, real CN fees.

No future order or fill is supplied to fee authority. Retained-price public
preparation acceptance is a separate gate.
"""
from dataclasses import replace

import pytest

import crypto_quant_backtest as bt
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_trading.profiles.cn_a_share import CnAShareFeeReservationBufferV2, CnAShareMarketFeeRuleResolutionV2
from crypto_quant_trading.profiles.cn_a_share.january_2024_development_fee_authority import january_2024_commission_scenarios

from tests.runtime.engine.test_cn_a_share_live_settlement import cn_case, profile
from tests.runtime.engine.test_live_execution_case import _respec
from tests.runtime.profiles.cn_a_share.test_000703_development_profile_v2 import _rebind


def profile_fee_case(*, commission_scenario="5bps", **kwargs):
    case, dispatcher = cn_case(combined_fees=True, **kwargs)
    if commission_scenario != "5bps":
        scenario = next(value for value in january_2024_commission_scenarios() if value.scenario_key == commission_scenario)
        request = _rebind(profile().request, commission_scenario=bt.CnAShareDevelopmentCommissionScenarioV2(
            scenario.scenario_key, scenario.commission_rate, scenario.account_fee_schedule_ref, True))
        resolved = bt.CnAShareProfileComposerV2().compose(request).result
        assert resolved is not None
        dispatcher = bt.CnAShareDevelopmentFinancialDispatcherV2(resolved)
        case = replace(case, financial_dispatch_plan=replace(case.financial_dispatch_plan, dispatcher_spec=dispatcher.spec))
    binding = bt.ProfileFeeRuleBinding(dispatcher.spec.spec_hash, d.CurrencyId("CNY"), d.Scale(2))
    cycles = tuple(replace(cycle, admission_slot=replace(cycle.admission_slot,
        pretrade_authority=replace(cycle.admission_slot.pretrade_authority, fee_reservation_rule_set=binding)))
        for cycle in case.decision_cycles)
    bars = []
    for bar in case.bar_executions:
        fee = bar.accounting_plan.fee_plan
        assert isinstance(fee, bt.FullFillOrderFeeAccountingPlan)
        assert fee.fill_fee_plan is not None
        bars.append(replace(bar,
            pretrade_authority=replace(bar.pretrade_authority, fee_reservation_rule_set=binding),
            accounting_plan=replace(bar.accounting_plan, fee_plan=replace(fee,
                final_fee_rule_set=binding,
                fill_fee_plan=replace(fee.fill_fee_plan, final_fee_rule_set=binding)))))
    return _respec(replace(case, decision_cycles=cycles, bar_executions=tuple(bars))), dispatcher


def test_profile_fee_rules_bind_actual_live_order_and_fill():
    case, dispatcher = profile_fee_case()
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    # Each notional = CNY 50,000. Handling 1.71 + regulatory 1 + transfer .50;
    # SELL stamp 25, and each ORDER commission 25 (5bps).
    assert sorted(fee.amount.units for fee in result.fee_assessments) == [321, 2500, 2500, 2821]
    assert result.final_portfolio_snapshot.cash[0].amount.units == 9_991_858
    assert result.final_portfolio_snapshot.fees.units == 8142
    assert result.final_portfolio_snapshot.positions == ()
    assert len(result.order_streams) == 2
    resolutions = [artifact.payload for artifact in result.financial_artifacts
        if artifact.role.startswith("fee_rules.")]
    assert len(resolutions) == 9  # 3 admission attempts, 2 execution gates, 4 assessments
    actual_orders = {stream.order.order_id: stream.order for stream in result.order_streams}
    for resolution in resolutions:
        assert isinstance(resolution, bt.ProfileFeeRuleResolution)
        query = resolution.query
        if query.order.order_id in actual_orders:
            assert query.order == actual_orders[query.order.order_id]
        if query.fill is not None:
            assert query.fill in result.fills
            assert query.fill.order_id == query.order.order_id
        assert resolution.rule_set is not None
        assert resolution.failure_code is None
        # Full policy outcomes, not a copied rate or a rewritten side identity.
        market = resolution.evidence[0]
        assert isinstance(market, t.ProfilePortOutcome)
        assert isinstance(market.result, CnAShareMarketFeeRuleResolutionV2)
        assert market.result.query.order_hash == d.canonical_sha256(query.order)
        assert market.result.fill == query.fill


@pytest.mark.parametrize("scenario, commission, total", (("3bps", 500, 1628), ("5bps", 500, 1628), ("8bps", 800, 2228)))
def test_profile_commission_scenarios_keep_cent_rounding_then_order_minimum(scenario, commission, total):
    case, dispatcher = profile_fee_case(commission_scenario=scenario, weights=("0.1", "0", "0"))
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    assert {fill.quantity.units for fill in result.fills} == {100}
    assert sorted(fee.amount.units for fee in result.fee_assessments) == sorted((64, 564, commission, commission))
    assert result.final_portfolio_snapshot.fees.units == total
    assert result.final_portfolio_snapshot.cash[0].amount.units == 10_000_000 - total
    for artifact in result.financial_artifacts:
        if not artifact.role.startswith("fee_rules."):
            continue
        resolution = artifact.payload
        assert isinstance(resolution, bt.ProfileFeeRuleResolution)
        if resolution.query.basis_type is None:
            assert isinstance(resolution.rule_set, t.FeeReservationRuleSet)
            assert resolution.rule_set.minimums[0].minimum_amount.units == 500
            # The existing kernel buffer is pinned to one full fill, never partials.
            buffer = resolution.evidence[-1]
            assert isinstance(buffer, CnAShareFeeReservationBufferV2)
            assert buffer.maximum_fill_count == 1


@pytest.mark.parametrize("mode", ("missing", "raises", "wrong_query", "wrong_binding"))
def test_profile_fee_resolver_never_silently_uses_fixed_rules(mode):
    case, dispatcher = profile_fee_case()
    if mode == "missing":
        class MissingResolver(bt.DefaultCashFinancialDispatcher):
            @property
            def spec(self):
                return dispatcher.spec
        supplied = MissingResolver()
    else:
        class BrokenResolver(bt.CnAShareDevelopmentFinancialDispatcherV2):
            def resolve_fee_rules(self, query, /):
                if mode == "raises":
                    raise ValueError("private provider information")
                if mode == "wrong_query":
                    query = replace(query, evaluated_at=replace(query.evaluated_at,
                        source_sequence=d.SourceSequence(query.evaluated_at.source_sequence.value + 1)))
                return super().resolve_fee_rules(query)
        supplied = BrokenResolver(profile())
    if mode == "wrong_binding":
        cycle = case.decision_cycles[0]
        authority = cycle.admission_slot.pretrade_authority
        assert isinstance(authority.fee_reservation_rule_set, bt.ProfileFeeRuleBinding)
        binding = replace(authority.fee_reservation_rule_set, dispatcher_spec_hash="sha256:" + "0" * 64)
        cycle = replace(cycle, admission_slot=replace(cycle.admission_slot,
            pretrade_authority=replace(authority, fee_reservation_rule_set=binding)))
        case = _respec(replace(case, decision_cycles=(cycle, *case.decision_cycles[1:])))
    outcome = bt.DeterministicBarEngine(supplied).run(case)
    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is bt.EngineFailureCode.FEE_RESERVATION
    assert "private provider information" not in d.canonical_bytes(outcome).decode()


def test_no_order_never_resolves_future_fee_rules():
    case, dispatcher = profile_fee_case(weights=("0", "0", "0"))
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    assert result.order_streams == result.fills == result.fee_assessments == ()
    assert not any(artifact.role.startswith("fee_rules.") for artifact in result.financial_artifacts)
    assert result.final_portfolio_snapshot.fees.units == 0
