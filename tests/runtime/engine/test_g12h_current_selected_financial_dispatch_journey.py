from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

from crypto_quant_backtest import (
    CashFillAccountingPlan,
    DefaultCashFinancialDispatcher,
    FillAccountingDispatchPlan,
    FinancialStateView,
)
from crypto_quant_backtest.cn_a_share_current_selected_fee_binding import (
    CnAShareCurrentSelectedFeePreparedExecutionV2,
    prepare_cn_a_share_current_selected_fee_execution_v2,
)
from crypto_quant_domain import (
    CashBalanceKey,
    DomainId,
    DomainIdKind,
    FeeBasisType,
    Fill,
    Money,
    OrderSide,
    PositionBalanceKey,
    SimulationInstant,
    SourceSequence,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FinalFeeRuleSet,
    FinalFeeRuleSource,
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
    ReservationCommitment,
    ResourceReservationState,
)
from crypto_quant_trading.profiles.cn_a_share.commission_tax_v2 import (
    CnAShareMarketFeeRuleResolutionV2,
    CnAShareStampDutyRuleResolutionV2,
)

from tests.runtime.engine._financial_dispatch_fixtures import (
    lot_books_from_ledger,
    v2_cash_plan,
)
from tests.runtime.engine._fixtures import (
    CashAccountingSemanticPayload,
    SyntheticExecutionCaseBuilder,
)
from tests.runtime.profiles.cn_a_share._current_selected_fee_fixtures import (
    build_artifact_manifest,
    current_selected_fill,
    july_order,
    published_inputs,
    resolved_profile,
)


def _domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def _state(
    journal: AccountingJournal,
    ledger: GenericLedger,
    cash_key: CashBalanceKey,
) -> FinancialStateView:
    ledger_state = ledger.project(journal)
    return FinancialStateView(
        journal,
        ledger_state,
        ResourceReservationState(
            cash_key.account_id,
            (),
            (),
            ReservationCommitment.empty(),
        ),
        lot_books_from_ledger(ledger_state),
        (),
    )


def _rule_set(
    prepared: CnAShareCurrentSelectedFeePreparedExecutionV2,
    fill: Fill,
) -> tuple[
    FinalFeeRuleSet,
    CnAShareMarketFeeRuleResolutionV2,
    CnAShareStampDutyRuleResolutionV2,
]:
    market_policy, tax_policy = prepared.policies()
    query = prepared.final_fill_query(fill)
    market = market_policy.assess_fees(query).result
    tax = tax_policy.assess_taxes(query).result
    assert market is not None and tax is not None
    assert (
        market_policy.component_ref
        == prepared.binding.authority.market_fee_component_ref
    )
    assert (
        tax_policy.component_ref == prepared.binding.authority.stamp_duty_component_ref
    )

    base_rules = v2_cash_plan().fee_plan.final_fee_rule_set
    account_rule = next(
        rule
        for rule in base_rules.charge_rules
        if rule.source is FinalFeeRuleSource.ACCOUNT_SCHEDULE
        and rule.basis_type is FeeBasisType.FILL
    )
    rule_set = FinalFeeRuleSet.create(
        market_fee_policy_ref=prepared.binding.authority.market_fee_component_ref,
        tax_policy_ref=prepared.binding.authority.stamp_duty_component_ref,
        account_fee_schedule_ref=base_rules.account_fee_schedule_ref,
        assessment_currency=prepared.binding.authority.scope.instrument.quote_currency,
        assessment_scale=market.final_fill_charge_rules[0].quantization.target_scale,
        charge_rules=(
            *market.final_fill_charge_rules,
            tax.final_fill_charge_rule,
            account_rule,
        ),
        minimums=(),
    )
    return rule_set, market, tax


def _plan(
    *,
    prepared: CnAShareCurrentSelectedFeePreparedExecutionV2,
    fill: Fill,
    rule_set: FinalFeeRuleSet,
    cash_key: CashBalanceKey,
    position_key: PositionBalanceKey,
    fill_digit: str,
    fee_digit: str,
    assessment_digit: str,
    sequence: int,
) -> FillAccountingDispatchPlan:
    plan = v2_cash_plan()
    fill_recorded_at = SimulationInstant(
        fill.execution_time,
        plan.fill_recorded_at.phase,
        SourceSequence(sequence),
    )
    fee_time = UtcInstant(fill.execution_time.epoch_nanoseconds + 1)
    fee_recorded_at = SimulationInstant(
        fee_time,
        plan.fee_plan.fee_recorded_at.phase,
        SourceSequence(sequence + 1),
    )
    fill_journal_id = _domain_id(DomainIdKind.JOURNAL, fill_digit)
    fee_journal_id = _domain_id(DomainIdKind.JOURNAL, fee_digit)
    fee_assessment_id = _domain_id(DomainIdKind.FEE, assessment_digit)
    payload = replace(
        cast(CashFillAccountingPlan, plan.position_payload),
        cash_key=cash_key,
        position_key=position_key,
        fill_journal_entry_id=fill_journal_id,
        fill_recorded_at=fill_recorded_at,
        final_fee_rule_set=rule_set,
        fee_assessment_id=fee_assessment_id,
        fee_assessment_time=fee_time,
        fee_journal_entry_id=fee_journal_id,
        fee_recorded_at=fee_recorded_at,
    )
    fee_plan = replace(
        plan.fee_plan,
        cash_key=cash_key,
        final_fee_rule_set=rule_set,
        fee_assessment_id=fee_assessment_id,
        fee_assessment_time=fee_time,
        fee_journal_entry_id=fee_journal_id,
        fee_recorded_at=fee_recorded_at,
    )
    return replace(
        plan,
        source_event_id=f"g12h-{prepared.execution_binding.order.intent.side.value}-fill",
        expected_fill_id=fill.fill_id,
        position_payload=payload,
        semantic_payload=replace(
            cast(CashAccountingSemanticPayload, plan.semantic_payload),
            cash_key=cash_key,
            position_key=position_key,
        ),
        fill_journal_entry_id=fill_journal_id,
        fill_recorded_at=fill_recorded_at,
        fee_plan=fee_plan,
    )


def _book_journey(
    *,
    buy_fill: Fill,
    sell_fill: Fill,
    buy_plan: FillAccountingDispatchPlan,
    sell_plan: FillAccountingDispatchPlan,
    ledger: GenericLedger,
    cash_key: CashBalanceKey,
    position_key: PositionBalanceKey,
) -> dict[str, object]:
    dispatcher = DefaultCashFinancialDispatcher()
    journal = AccountingJournal.from_entries(())

    for fill, plan in ((buy_fill, buy_plan), (sell_fill, sell_plan)):
        fill_state = _state(journal, ledger, cash_key)
        fill_outcome = dispatcher.book_fill(plan, fill, fill_state)
        assert fill_outcome.result is not None
        journal = journal.append_many(fill_outcome.result.journal_entries)
        fill_ledger = ledger.project(journal)
        assert (
            lot_books_from_ledger(fill_ledger) == fill_outcome.result.position_lot_books
        )
        if fill.side is OrderSide.BUY:
            assert fill_ledger.cash_amount(cash_key).units == -100_000
            assert fill_ledger.position_quantity(position_key).units == 100
            opened_lot = dict(lot_books_from_ledger(fill_ledger))[position_key][0]
            assert opened_lot.quantity == fill.quantity
            assert opened_lot.total_cost_basis is not None
            assert opened_lot.total_cost_basis.units == 100_000
            assert opened_lot.allocated_fees == ()
        else:
            assert fill_ledger.cash_amount(cash_key).units == -6
            assert fill_ledger.position_quantity(position_key).units == 0
            assert lot_books_from_ledger(fill_ledger) == ()

        basis = FeeAssessmentBasisEvidence.for_fill(fill)
        assessed = FeeAssessmentEngine().assess(
            basis=basis,
            rule_set=plan.fee_plan.final_fee_rule_set,
            fee_assessment_id=plan.fee_plan.fee_assessment_id,
            assessment_time=plan.fee_plan.fee_assessment_time,
        )
        assert assessed.result is not None
        assert assessed.result.basis == basis

        fee_state = _state(journal, ledger, cash_key)
        fee_outcome = dispatcher.book_fee(
            plan,
            fill,
            assessed.result,
            fee_state,
        )
        assert fee_outcome.result is not None
        fee_entry = fee_outcome.result.journal_entries[0]
        assert set(fee_entry.source_ids) == {
            assessed.result.assessment.fee_assessment_id.value,
            fill.fill_id.value,
            assessed.result.assessment.market_fee_rule_id,
            assessed.result.assessment.tax_rule_id,
            assessed.result.assessment.account_fee_schedule_id,
        }
        journal = journal.append_many(fee_outcome.result.journal_entries)
        fee_ledger = ledger.project(journal)
        assert (
            lot_books_from_ledger(fee_ledger) == fee_outcome.result.position_lot_books
        )
        if fill.side is OrderSide.BUY:
            assert fee_ledger.cash_amount(cash_key).units == -100_006
            allocated_lot = dict(lot_books_from_ledger(fee_ledger))[position_key][0]
            assert allocated_lot.total_cost_basis is not None
            assert allocated_lot.total_cost_basis.units == 100_000
            assert allocated_lot.allocated_fees == (assessed.result.assessment.amount,)
        else:
            assert fee_ledger.cash_amount(cash_key).units == -62
            assert fee_ledger.position_quantity(position_key).units == 0
            assert lot_books_from_ledger(fee_ledger) == ()

    full = ledger.project(journal)
    prefix = ledger.project(journal, stop=journal.cursor_at(2))
    resumed = ledger.resume(journal, prefix)
    assert resumed == full
    assert lot_books_from_ledger(resumed) == lot_books_from_ledger(full)
    return {
        "journal_hash": journal.journal_hash,
        "ledger_hash": full.state_hash,
        "lot_book_hash": canonical_sha256(lot_books_from_ledger(full)),
        "cash_units": full.cash_amount(cash_key).units,
        "position_units": full.position_quantity(position_key).units,
        "fee_units": full.fee_amount(cash_key).units,
        "realized_pnl_units": full.realized_pnl_amount(cash_key).units,
    }


def test_g12h_current_selected_financial_dispatch_books_and_replays(
    tmp_path: Path,
) -> None:
    _, manifest, events, report = published_inputs(tmp_path)
    profile = resolved_profile()
    build = build_artifact_manifest(profile)
    base_spec = SyntheticExecutionCaseBuilder().semantic_spec()

    def prepare(side: OrderSide) -> CnAShareCurrentSelectedFeePreparedExecutionV2:
        return prepare_cn_a_share_current_selected_fee_execution_v2(
            resolved_profile=profile,
            market_bundle_manifest=manifest,
            events=events,
            coverage_report=report,
            build_artifact_manifest=build,
            base_spec=base_spec,
            order=july_order(profile, side),
        )

    buy = prepare(OrderSide.BUY)
    sell = prepare(OrderSide.SELL)
    buy_fill = current_selected_fill(buy, "8")
    sell_fill = replace(
        current_selected_fill(sell, "9"),
        execution_time=UtcInstant(
            buy_fill.execution_time.epoch_nanoseconds + 3_600_000_000_000
        ),
    )
    assert buy_fill.quantity == sell_fill.quantity

    buy_rules, buy_market, buy_tax = _rule_set(buy, buy_fill)
    sell_rules, sell_market, sell_tax = _rule_set(sell, sell_fill)
    assert set(buy_rules.charge_rules) == {
        *buy_market.final_fill_charge_rules,
        buy_tax.final_fill_charge_rule,
        next(
            rule
            for rule in buy_rules.charge_rules
            if rule.source is FinalFeeRuleSource.ACCOUNT_SCHEDULE
        ),
    }
    assert [
        (rule.applicability.value, rule.rate.units, rule.rate.scale.places)
        for rule in buy_market.final_fill_charge_rules
        if rule.rate is not None
    ] == [
        ("always", 341, 7),
        ("always", 2, 5),
        ("always", 1, 5),
        ("not_applicable", 0, 0),
    ]
    assert buy_tax.final_fill_charge_rule.applicability.value == "not_applicable"
    assert sell_tax.final_fill_charge_rule.applicability.value == "always"
    assert sell_tax.final_fill_charge_rule.rate is not None
    assert (
        sell_tax.final_fill_charge_rule.rate.units,
        sell_tax.final_fill_charge_rule.rate.scale.places,
    ) == (5, 4)

    authority = buy.binding.authority
    instrument = authority.scope.instrument
    cash_key = CashBalanceKey(
        authority.scope.account_id,
        authority.scope.venue_id,
        instrument.quote_currency,
    )
    position_key = PositionBalanceKey(
        authority.scope.account_id,
        authority.scope.venue_id,
        instrument.instrument_id,
    )
    ledger = GenericLedger(
        LedgerSchema(
            (
                LedgerBalanceRegistration(cash_key, buy_rules.assessment_scale),
                LedgerBalanceRegistration(position_key, buy_fill.quantity.scale),
            )
        )
    )
    buy_plan = _plan(
        prepared=buy,
        fill=buy_fill,
        rule_set=buy_rules,
        cash_key=cash_key,
        position_key=position_key,
        fill_digit="3",
        fee_digit="5",
        assessment_digit="4",
        sequence=1,
    )
    sell_plan = _plan(
        prepared=sell,
        fill=sell_fill,
        rule_set=sell_rules,
        cash_key=cash_key,
        position_key=position_key,
        fill_digit="6",
        fee_digit="7",
        assessment_digit="f",
        sequence=3,
    )

    for fill, plan, market, tax, expected_amounts in (
        (buy_fill, buy_plan, buy_market, buy_tax, (3, 2, 1, 0, 0, 0)),
        (sell_fill, sell_plan, sell_market, sell_tax, (3, 2, 1, 0, 50, 0)),
    ):
        assessed = FeeAssessmentEngine().assess(
            basis=FeeAssessmentBasisEvidence.for_fill(fill),
            rule_set=plan.fee_plan.final_fee_rule_set,
            fee_assessment_id=plan.fee_plan.fee_assessment_id,
            assessment_time=plan.fee_plan.fee_assessment_time,
        )
        assert assessed.result is not None
        line_by_rule = {line.rule.rule_id: line for line in assessed.result.lines}
        ordered_rules = (
            *market.final_fill_charge_rules,
            tax.final_fill_charge_rule,
            next(
                rule
                for rule in plan.fee_plan.final_fee_rule_set.charge_rules
                if rule.source is FinalFeeRuleSource.ACCOUNT_SCHEDULE
            ),
        )
        assert (
            tuple(line_by_rule[rule.rule_id].amount.units for rule in ordered_rules)
            == expected_amounts
        )
        hkscc = line_by_rule[market.final_fill_charge_rules[3].rule_id]
        assert not hkscc.applied
        assert hkscc.notional == Money(0, buy_rules.assessment_scale, "CNY")
        assert hkscc.amount == Money(0, buy_rules.assessment_scale, "CNY")
        stamp = line_by_rule[tax.final_fill_charge_rule.rule_id]
        assert stamp.applied is (fill.side is OrderSide.SELL)
        assert stamp.amount.units == (50 if fill.side is OrderSide.SELL else 0)

    assert buy.semantic_spec.financial_inputs_hash == (
        "sha256:f39985966cc1c054f4ca8465ba93382291ecfd79b387c5d12943587aa719c8c5"
    )
    assert sell.semantic_spec.financial_inputs_hash == (
        buy.semantic_spec.financial_inputs_hash
    )

    first = _book_journey(
        buy_fill=buy_fill,
        sell_fill=sell_fill,
        buy_plan=buy_plan,
        sell_plan=sell_plan,
        ledger=ledger,
        cash_key=cash_key,
        position_key=position_key,
    )
    second = _book_journey(
        buy_fill=buy_fill,
        sell_fill=sell_fill,
        buy_plan=buy_plan,
        sell_plan=sell_plan,
        ledger=ledger,
        cash_key=cash_key,
        position_key=position_key,
    )
    assert first == second
    assert (
        canonical_sha256(first)
        == canonical_sha256(second)
        == ("sha256:0d8a916d7adf18d202df5f4365c837fb9b28dcd3f3d715c534318576938853f4")
    )
    assert first["cash_units"] == -62
    assert first["position_units"] == 0
    assert first["fee_units"] == 62
    assert first["realized_pnl_units"] == 0
