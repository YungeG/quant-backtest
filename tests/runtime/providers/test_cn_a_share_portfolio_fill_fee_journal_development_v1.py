"""Synthetic cross-module smoke: native Fill/Fee Kernel facts in ONE account Journal.

Test-only, not a public prepare, portfolio Engine, source-qualified rates or PnL.
"""
from __future__ import annotations

from dataclasses import replace
import pytest

from crypto_quant_domain import (
    AccountingEntryType, CashBalanceKey, CurrencyId, DomainIdKind, Money,
    OrderEventType, PositionBalanceKey, RoundingPolicy, SimulationInstant,
    SourceSequence, TimelinePhase,
)
from crypto_quant_trading import (
    CashInstrumentAccounting, CostBasisMethod, CostBasisPolicy,
    FeeAssessmentBasisEvidence, FeeAssessmentEngine, GenericLedger,
    OrderEventRecord, OrderEventStream,
)
from crypto_quant_backtest.cn_a_share_portfolio_funding_development_v1 import (
    build_synthetic_cross_venue_funding_candidate_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialStepDevelopmentV1,
    book_cn_a_share_portfolio_financial_batch_development_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_next_open_development_v1 import (
    evaluate_cn_a_share_portfolio_next_open_development_v1,
)
from tests.kernel.orders._fixtures import event, full_lifecycle_records
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    QUANTIZATION, domain_id, fee_query, final_fill_rule_set, final_order_rule_set, policies,
)
from tests.kernel.profiles.cn_a_share.test_portfolio_open_risk_development_v1 import _opening_case
from tests.kernel.profiles.cn_a_share.test_portfolio_order_plan_v1 import _accepted
from tests.kernel.profiles.cn_a_share.test_portfolio_sellability_v1 import _two_week_sources
from tests.runtime.providers.test_cn_a_share_portfolio_funding_development_v1 import (
    ACCOUNT, SCALE, fixture as funding_fixture,
)
from tests.runtime.providers.test_cn_a_share_portfolio_next_open_development_v1 import _open_source


POLICY = CostBasisPolicy("cn.synthetic.portfolio.fifo.v2", 2, CostBasisMethod.FIFO,
                         RoundingPolicy.HALF_EVEN)


def _at(t, phase: int, name: str, sequence: int):
    return SimulationInstant(t, TimelinePhase(phase, name), SourceSequence(sequence))


def _financial_sources(day: int = 28):
    plan, cash, positions, reservations, evidence, t = _opening_case(day)
    _, schema, rules, _, keys, _ = _two_week_sources()
    funding = funding_fixture()
    opening = build_synthetic_cross_venue_funding_candidate_v1(
        **{**funding, "ledger_schema": schema, "settlement_rules": rules,
           "amount": Money(50_000, SCALE, "CNY")}).journal
    # The B1 candidate in this test must be the same 50/50 source prefix used
    # by the B4 risk/Fill sample, not the fixture's older 60/40 allocation.
    assert opening.journal_hash == plan.cash.journal_hash
    accounting = CashInstrumentAccounting()
    fee_engine = FeeAssessmentEngine()
    fill_entries = []
    fee_fill_entries = []
    fee_order_entries = []
    fills = []
    assessments = []
    steps = []
    for seq, (digit, item, key) in enumerate((("6", evidence[0], keys[0]),
                                                ("7", evidence[1], keys[1])), start=1):
        prop, order, _, _, observation = item
        stream, _, records, subject = _accepted(prop, digit, fee=prop.estimated_fee.units)
        risk, liquidity, market_state, zero = _open_source(
            item, plan, cash, positions, reservations, t)
        outcome = evaluate_cn_a_share_portfolio_next_open_development_v1(
            plan=plan, stream=stream, observation=observation,
            risk=risk, liquidity=liquidity, market_state=market_state,
            slippage_model=zero, eligibility_window_exhausted=True)
        fill = outcome.fill
        assert fill is not None and not outcome.trade_authorized
        fills.append(fill)
        cash_key = CashBalanceKey(ACCOUNT, fill.venue_id, CurrencyId("CNY"))
        position_key = PositionBalanceKey(ACCOUNT, fill.venue_id, fill.instrument_id)
        booked = accounting.book_fill(
            fill=fill, cash_key=cash_key, position_key=position_key, open_lots=(),
            cost_basis_policy=POLICY, notional_quantization=QUANTIZATION,
            journal_entry_id=domain_id(DomainIdKind.JOURNAL, "a" if seq == 1 else "b"),
            recorded_at=_at(t, 70, "accounting", seq))
        assert booked.failure is None and booked.result is not None
        fill_entries.append(booked.result.journal_entry)
        activated = OrderEventRecord(full_lifecycle_records(subject)[8].event)
        filled = OrderEventRecord(event(
            subject, f"cn-portfolio-full-{digit}", OrderEventType.ORDER_FILLED,
            t.epoch_nanoseconds, activated.event.event_id, fill_id=fill.fill_id), fill)
        terminal = OrderEventStream.from_records(subject, records + (activated, filled))
        assert terminal.state is not None and terminal.state.remaining_quantity.units == 0
        fill_rules = final_fill_rule_set(fill)
        order_rules = final_order_rule_set(side=fill.side, effective_at=t,
                                            venue=fill.venue_id.value)
        market_policy, tax_policy = policies()
        fee_query_at_fill = fee_query(fill.side, fill.execution_time,
                                      venue=fill.venue_id.value)
        market_resolution = market_policy.assess_fees(fee_query_at_fill).result
        tax_resolution = tax_policy.assess_taxes(fee_query_at_fill).result
        assert market_resolution is not None and tax_resolution is not None
        steps.append(CnASharePortfolioFinancialStepDevelopmentV1(
            outcome, risk, terminal, fill_rules, order_rules,
            market_resolution, tax_resolution))
        fill_fee = fee_engine.assess(
            basis=FeeAssessmentBasisEvidence.for_fill(fill),
            rule_set=fill_rules,
            fee_assessment_id=domain_id(DomainIdKind.FEE, "1" if seq == 1 else "2"),
            assessment_time=t)
        assert fill_fee.failure is None and fill_fee.result is not None
        assessments.append(fill_fee.result.assessment)
        charged_fill = accounting.charge_fee(
            assessment=fill_fee.result.assessment, related_fill=fill, cash_key=cash_key,
            open_lots=booked.result.open_lots, cost_basis_policy=POLICY,
            journal_entry_id=domain_id(DomainIdKind.JOURNAL, "c" if seq == 1 else "d"),
            recorded_at=_at(t, 90, "fees", seq))
        assert charged_fill.failure is None and charged_fill.result is not None
        fee_fill_entries.append(charged_fill.result.journal_entry)
        order_fee = fee_engine.assess(
            basis=FeeAssessmentBasisEvidence.for_order(terminal),
            rule_set=order_rules,
            fee_assessment_id=domain_id(DomainIdKind.FEE, "3" if seq == 1 else "4"),
            assessment_time=t)
        assert order_fee.failure is None and order_fee.result is not None
        assessments.append(order_fee.result.assessment)
        charged_order = accounting.charge_order_fee(
            assessment=order_fee.result.assessment, order_stream=terminal, cash_key=cash_key,
            open_lots=charged_fill.result.open_lots, cost_basis_policy=POLICY,
            journal_entry_id=domain_id(DomainIdKind.JOURNAL, "e" if seq == 1 else "f"),
            recorded_at=_at(t, 91, "order_fee", seq))
        assert charged_order.failure is None and charged_order.result is not None
        fee_order_entries.append(charged_order.result.journal_entry)
    full = opening.append_many((*fill_entries, *fee_fill_entries, *fee_order_entries))
    ledger = GenericLedger(schema)
    state = ledger.project(full)
    assert ledger.resume(full, ledger.project(opening)) == state
    assert [entry.entry_type for entry in full.entries[-6:]] == (
        [AccountingEntryType.FILL_BOOKED] * 2 + [AccountingEntryType.FEE_CHARGED] * 4)
    assert {f.venue_id.value for f in fills} == {"xshg", "xshe"}
    assert [state.position_quantity(key).units for key in keys] == [100, 100]
    total_fee = sum(value.amount.units for value in assessments)
    assert total_fee > 0
    assert sum(state.cash_amount(CashBalanceKey(ACCOUNT, f.venue_id, CurrencyId("CNY"))).units
               for f in fills) == 100_000 - 80_000 - total_fee
    assert all(state.cash_amount(CashBalanceKey(ACCOUNT, f.venue_id, CurrencyId("CNY"))).units >= 0
               for f in fills)
    # Same global book refs cannot justify using SH selected rules for an SZ Fill.
    with pytest.raises(ValueError, match="venue fee"):
        replace(steps[1], final_fill_rules=steps[0].final_fill_rules)
    batch = book_cn_a_share_portfolio_financial_batch_development_v1(
        prior_journal=opening, ledger_schema=schema, cost_basis_policy=POLICY,
        notional_quantization=QUANTIZATION, steps=tuple(steps))
    assert not batch.trade_authorized and batch.synthetic_development_only
    assert {f.fill_id for f in batch.fills} == {f.fill_id for f in fills}
    assert sorted(a.amount.units for a in batch.fee_assessments) == sorted(
        a.amount.units for a in assessments)
    assert [batch.ledger_state.position_quantity(key).units for key in keys] == [100, 100]
    assert sum(batch.ledger_state.cash_amount(
        CashBalanceKey(ACCOUNT, f.venue_id, CurrencyId("CNY"))).units for f in fills) == (
        100_000 - 80_000 - total_fee)
    assert GenericLedger(schema).resume(batch.journal, GenericLedger(schema).project(opening)) == batch.ledger_state
    assert batch == book_cn_a_share_portfolio_financial_batch_development_v1(
        prior_journal=opening, ledger_schema=schema, cost_basis_policy=POLICY,
        notional_quantization=QUANTIZATION, steps=tuple(steps))
    return (batch, opening, schema, tuple(steps),
            (evidence[0][4].event, evidence[1][4].event))


def _financial_batch(day: int = 28):
    return _financial_sources(day)[0]


def test_two_venue_real_open_fills_book_fee_into_one_replayable_synthetic_journal():
    _financial_batch()
