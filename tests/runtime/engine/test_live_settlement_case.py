"""Public same-engine pending-position contract; synthetic times, not CN evidence."""
from dataclasses import replace
from typing import cast

import pytest

from crypto_quant_backtest import (
    DefaultCashFinancialDispatcher, DeterministicBarEngine, ExecutionCaseIdentityFactory,
    CashFillAccountingPlan, EngineFailureCode, ExecutionCaseIdentityRule,
    SettlementFinancialDispatchResult, SettlementFillAccountingDispatchPlan,
)
from crypto_quant_domain import (
    DomainIdKind, Money, Quantity, OrderSide, SettlementObligation, TimelinePhase, UtcInstant, canonical_sha256,
)
from crypto_quant_trading import AccountSettlementObligation, FeeReservationRuleSet, FinalFeeRuleSet, SettlementEvent, SettlementEventType
from tests.runtime.engine import _fixtures as f
from tests.runtime.engine.test_live_execution_case import _closure, _respec, live_case


def settlement_case(*, weights=("0.5", "0", "0"), decision_times=(100, 200, 260), bar_times=(150, 250, 280)):
    from crypto_quant_backtest import SettlementFillAccountingDispatchPlan, SettlementIdentitySlot

    case = live_case(weights=weights, decision_times=decision_times, bar_times=bar_times)
    assert case.semantic_spec is not None and case.identity_manifest is not None
    rules = list(case.semantic_spec.identity_plan)
    for i in range(len(case.bar_executions)):
        for j in range(2):
            for prefix, kind in (("settlement", DomainIdKind.SETTLEMENT),
                                 ("settlement-event.recorded", None), ("settlement-event.applied", None)):
                key = f"{prefix}.{i}.{j}"
                rules.append(ExecutionCaseIdentityRule(key, key, 0, kind))
    factory = ExecutionCaseIdentityFactory(semantic_run_id=case.identity_manifest.semantic_run_id,
        namespace=case.identity_manifest.namespace, identity_plan=tuple(rules))
    for rule in rules:
        factory.domain_id(rule.binding_key) if rule.domain_kind else factory.event_id(rule.binding_key)
    bars = []
    for i, bar in enumerate(case.bar_executions):
        old = bar.accounting_plan
        assert isinstance(old.position_payload, CashFillAccountingPlan)
        slots = tuple(SettlementIdentitySlot(key, factory.domain_id(f"settlement.{i}.{j}"),
            factory.event_id(f"settlement-event.recorded.{i}.{j}"), factory.event_id(f"settlement-event.applied.{i}.{j}"))
            for j, key in enumerate((old.position_payload.cash_key, old.position_payload.position_key)))
        plan = SettlementFillAccountingDispatchPlan(old.source_event_id, old.expected_fill_id,
            old.position_accounting_component, old.position_payload, old.semantic_payload, old.fill_journal_entry_id,
            old.fill_recorded_at, old.fee_plan, (*old.expected_artifact_roles, f"settlement.{bar.event_id}"),
            settlement_slots=slots, settlement_recorded_at=f.sim(bar.fill_event_at.instant.epoch_nanoseconds, TimelinePhase(75, "settlement_record"), 0))
        bars.append(replace(bar, accounting_plan=plan))
    # Existing kernel rule: pending receivables reduce sellable, not economic holdings.
    financial = case.financial_state
    position_rule = replace(financial.settlement_rules.position_rules[0], pending_receivable_sellable=False)
    rules_before = financial.settlement_rules
    financial = replace(financial, settlement_rules=type(rules_before).create(policy_key=rules_before.policy_key,
        policy_version=rules_before.policy_version, account_id=rules_before.account_id,
        cash_rules=rules_before.cash_rules, position_rules=(position_rule,)))
    spec = replace(case.semantic_spec, identity_plan=tuple(rules))
    return _respec(replace(case, bar_executions=tuple(bars), financial_state=financial,
        identity_manifest=factory.manifest(), semantic_spec=spec, semantic_spec_hash=spec.semantic_spec_hash))


class SyntheticSettlementDispatcher(DefaultCashFinancialDispatcher):
    """Frozen test-only maturation facts; real profile must use its kernel model."""
    position_due = 225
    cash_due = 400
    position_due_by_fill_time: dict[int, int] = {}

    def book_fill(self, plan, fill, state, /):
        outcome = super().book_fill(plan, fill, state)
        assert outcome.result is not None and state.settlement_book is not None
        base, book = outcome.result, state.settlement_book
        changes = {change.key: change.value for change in base.journal_entries[0].balance_changes}
        obligations, events = [], []
        for slot in plan.settlement_slots:
            value = changes[slot.balance_key]
            position = slot.balance_key == f.POSITION_KEY
            position_due = self.position_due_by_fill_time.get(fill.execution_time.epoch_nanoseconds, self.position_due)
            due = (position_due if position else self.cash_due) if value.units > 0 else fill.execution_time.epoch_nanoseconds
            obligation = AccountSettlementObligation(SettlementObligation(slot.obligation_id, fill.fill_id,
                fill.execution_time, UtcInstant(due), f.BTC if position else None, cast(Quantity, value) if position else None,
                None if position else f.USD, None if position else cast(Money, value)), slot.balance_key)
            obligations.append(obligation)
            events.append(SettlementEvent(slot.recorded_event_id, slot.obligation_id, SettlementEventType.OBLIGATION_RECORDED,
                plan.settlement_recorded_at, fill.fill_id.value, canonical_sha256(fill)))
            if due <= fill.execution_time.epoch_nanoseconds:
                events.append(SettlementEvent(slot.applied_event_id, slot.obligation_id, SettlementEventType.SETTLEMENT_APPLIED,
                    plan.fill_recorded_at, slot.recorded_event_id, canonical_sha256(fill)))
        after = book.append(obligations=tuple(obligations), events=tuple(events))
        return replace(outcome, result=SettlementFinancialDispatchResult(base.dispatcher_spec, base.source_event_id,
            base.journal_entries, base.position_lot_books, base.artifacts, settlement_obligations=tuple(obligations),
            settlement_events=tuple(events), prior_settlement_book_hash=book.book_hash, settlement_book_hash=after.book_hash))


def test_pending_sell_defers_until_real_boundary_then_next_target_sells_full_position():
    from crypto_quant_backtest import PendingPositionSellDeferral

    case = settlement_case()
    outcome = DeterministicBarEngine(SyntheticSettlementDispatcher()).run(case)
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    assert [(fill.side, fill.execution_time, fill.quantity.units) for fill in result.fills] == [
        (OrderSide.BUY, UtcInstant(150), 5000), (OrderSide.SELL, UtcInstant(280), 5000)]
    assert result.final_portfolio_snapshot.positions == ()
    assert result.final_portfolio_snapshot.cash[0].amount.units == 99774
    assert len(result.order_streams) == 2
    deferred = next(a.payload for a in result.financial_artifacts if a.role == "deferral.live-target:200")
    assert isinstance(deferred, PendingPositionSellDeferral)
    assert deferred.rejection.order.intent.quantity.units == 5000
    assert deferred.pending_obligations[0].units == 5000
    receipts = [a.payload for a in result.financial_artifacts if isinstance(a.payload, SettlementFinancialDispatchResult)]
    applied = [e for receipt in receipts for e in receipt.settlement_events
               if e.event_type is SettlementEventType.SETTLEMENT_APPLIED]
    accounting = case.bar_executions[0].accounting_plan
    assert isinstance(accounting, SettlementFillAccountingDispatchPlan)
    position_id = accounting.settlement_slots[1].obligation_id
    maturity = next(e for e in applied if e.settlement_obligation_id == position_id)
    assert maturity.occurred_at == f.sim(250, TimelinePhase(60, "bar_close"), 2)
    rows = _closure(result)
    assert rows["order.1.0"].reason == "pending_position_settlement"
    assert rows["settlement-event.applied.0.1"].status == "used"
    assert rows["settlement-event.applied.2.0"].reason == "pending_beyond_window"
    assert rows["settlement.1.0"].reason == "no_active_order"
    replay = DeterministicBarEngine(SyntheticSettlementDispatcher()).run(replace(case, timeline_batch_size=10))
    assert replay.result is not None and replay.result.result_hash == result.result_hash


def _policy(policy, **changes):
    values = {name: getattr(policy, name) for name in (
        "policy_key", "policy_version", "account_id", "venue_id", "allowed_sides", "allowed_position_effects",
        "allowed_reduce_only_values", "fee_reserve_funding_source", "order_capacity_limit", "exposure_capacity_limits")}
    return type(policy).create(**(values | changes))


def _fee_rules(rules, **changes):
    values = {name: getattr(rules, name) for name in (
        "market_fee_policy_ref", "tax_policy_ref", "account_fee_schedule_ref", "reservation_currency",
        "reservation_scale", "charge_rules", "minimums")}
    return type(rules).create(**(values | changes))


@pytest.mark.parametrize("authority", ("permission", "exposure", "fee_cash", "market", "fee"))
def test_pending_position_does_not_hide_other_failed_authority(authority):
    case = settlement_case()
    cycle = case.decision_cycles[1]
    old = cycle.admission_slot.pretrade_authority
    if authority == "permission":
        new = replace(old, account_risk_policy=_policy(old.account_risk_policy, allowed_sides=(OrderSide.BUY,)))
        expected = EngineFailureCode.PRETRADE_REJECTED
    elif authority == "exposure":
        limits = tuple(replace(limit, maximum=replace(limit.maximum, units=1)) for limit in old.account_risk_policy.exposure_capacity_limits)
        new = replace(old, account_risk_policy=_policy(old.account_risk_policy, exposure_capacity_limits=limits))
        expected = EngineFailureCode.PRETRADE_REJECTED
    elif authority == "fee_cash":
        rules = old.fee_reservation_rule_set
        assert isinstance(rules, FeeReservationRuleSet)
        minimums = tuple(replace(value, minimum_amount=replace(value.minimum_amount, units=999999)) for value in rules.minimums)
        new = replace(old, fee_reservation_rule_set=_fee_rules(rules, minimums=minimums))
        expected = EngineFailureCode.PRETRADE_REJECTED
    elif authority == "market":
        new = replace(old, notional_evidence=replace(old.notional_evidence, available_at=UtcInstant(201)))
        expected = EngineFailureCode.MARKET_RULE_DATA_FAILURE
    else:
        from crypto_quant_trading import FeeReservationApplicability
        rules = old.fee_reservation_rule_set
        assert isinstance(rules, FeeReservationRuleSet)
        new = replace(old, fee_reservation_rule_set=_fee_rules(rules,
            charge_rules=tuple(replace(value, applicability=FeeReservationApplicability.UNKNOWN) for value in rules.charge_rules)))
        expected = EngineFailureCode.FEE_RESERVATION
    changed = replace(cycle, admission_slot=replace(cycle.admission_slot, pretrade_authority=new))
    outcome = DeterministicBarEngine(SyntheticSettlementDispatcher()).run(_respec(replace(case,
        decision_cycles=(case.decision_cycles[0], changed, case.decision_cycles[2]))))
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is expected


def test_partially_sellable_position_fails_without_capping_or_deferral():
    dispatcher = SyntheticSettlementDispatcher()
    dispatcher.position_due_by_fill_time = {150: 225, 250: 350}
    case = settlement_case(weights=("0.5", "0.8", "0"))
    # The first zero-fee synthetic fill leaves equity 99950: 80% is exact cents.
    from crypto_quant_trading import FinalFeeApplicability
    bar = case.bar_executions[0]
    fee = bar.accounting_plan.fee_plan
    rules = fee.final_fee_rule_set
    assert isinstance(rules, FinalFeeRuleSet)
    zero = type(rules).create(market_fee_policy_ref=rules.market_fee_policy_ref, tax_policy_ref=rules.tax_policy_ref,
        account_fee_schedule_ref=rules.account_fee_schedule_ref, assessment_currency=rules.assessment_currency,
        assessment_scale=rules.assessment_scale, minimums=rules.minimums,
        charge_rules=tuple(replace(rule, applicability=FinalFeeApplicability.NOT_APPLICABLE) for rule in rules.charge_rules))
    bar = replace(bar, accounting_plan=replace(bar.accounting_plan, fee_plan=replace(fee, final_fee_rule_set=zero)))
    case = _respec(replace(case, bar_executions=(bar, *case.bar_executions[1:])))
    outcome = DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.PRETRADE_REJECTED
    assert outcome.engine_failure.subject_keys == (f"sellable_quantity:{f.BTC}",)


def test_active_sell_reservation_is_not_subtracted_twice_or_replaced_by_deferral():
    case = settlement_case(decision_times=(100, 260, 270))
    outcome = DeterministicBarEngine(SyntheticSettlementDispatcher()).run(case)
    assert outcome.result is not None, outcome.engine_failure
    assert len(outcome.result.order_streams) == 2
    assert [fill.quantity.units for fill in outcome.result.fills] == [5000, 5000]
    assert not any(a.role.startswith("deferral.") for a in outcome.result.financial_artifacts)
    assert _closure(outcome.result)["order.2.0"].reason == "no_order_planned"


@pytest.mark.parametrize("boundary", ("decision", "finalize", "beyond", "exclusive_end"))
def test_due_is_processed_only_at_actual_observed_boundaries(boundary):
    dispatcher = SyntheticSettlementDispatcher()
    dispatcher.position_due = {"beyond": 301, "exclusive_end": 300}.get(boundary, 225)
    case = settlement_case(weights=("0.5", "0"), decision_times=(100, 260 if boundary == "decision" else 200),
        bar_times=(150,))
    result = DeterministicBarEngine(dispatcher).run(case)
    assert result.result is not None, result.engine_failure
    rows = _closure(result.result)
    if boundary in {"beyond", "exclusive_end"}:
        assert rows["settlement-event.applied.0.1"].reason == "pending_beyond_window"
    else:
        artifacts = [a for a in result.result.financial_artifacts if a.role.startswith("settlement.settlement-due:")]
        assert len(artifacts) == 1
        assert artifacts[0].occurred_at == (f.sim(260, TimelinePhase(100, "decision"), 1) if boundary == "decision"
            else f.sim(300, TimelinePhase(1_000_000, "engine_finalize"), 0))
        assert rows["settlement-event.applied.0.1"].status == "used"


@pytest.mark.parametrize("tamper", ("quantity", "record_id", "immediate_missing", "future_applied"))
def test_fill_settlement_slots_bind_actual_accounting_and_lifecycle(tamper):
    class Broken(SyntheticSettlementDispatcher):
        def book_fill(self, plan, fill, state, /):
            outcome = super().book_fill(plan, fill, state)
            result = outcome.result
            assert isinstance(result, SettlementFinancialDispatchResult)
            obligations, events = result.settlement_obligations, result.settlement_events
            if tamper == "quantity":
                position = next(value for value in obligations if value.balance_key == f.POSITION_KEY)
                assert position.obligation.quantity is not None
                broken = replace(position, obligation=replace(position.obligation, quantity=replace(position.obligation.quantity, units=1)))
                obligations = tuple(broken if value == position else value for value in obligations)
            elif tamper == "record_id":
                events = tuple(replace(value, event_id="unbound-record") if value.settlement_obligation_id == plan.settlement_slots[1].obligation_id else value for value in events)
            elif tamper == "immediate_missing":
                events = tuple(value for value in events if value.event_type is not SettlementEventType.SETTLEMENT_APPLIED)
            else:
                position = plan.settlement_slots[1]
                events = (*events, SettlementEvent(position.applied_event_id, position.obligation_id, SettlementEventType.SETTLEMENT_APPLIED,
                    f.sim(225, TimelinePhase(80, "accounting"), 0), position.recorded_event_id, canonical_sha256(fill)))
            after = state.settlement_book.append(obligations=obligations, events=events)
            return replace(outcome, result=replace(result, settlement_obligations=obligations,
                settlement_events=events, settlement_book_hash=after.book_hash))

    outcome = DeterministicBarEngine(Broken()).run(settlement_case())
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == ("live_fill_settlement_coverage",)


@pytest.mark.parametrize("tamper", ("drop", "backdate", "swap", "journal"))
def test_due_dispatch_cannot_omit_backdate_or_rebind_application(tamper):
    class Broken(SyntheticSettlementDispatcher):
        def dispatch_scheduled_event(self, event, state, /):
            outcome = super().dispatch_scheduled_event(event, state)
            if not event.event_id.startswith("settlement-due:"):
                return outcome
            result = outcome.result
            assert isinstance(result, SettlementFinancialDispatchResult)
            events = result.settlement_events
            if tamper == "drop":
                from crypto_quant_backtest import FinancialDispatchResult
                return replace(outcome, result=FinancialDispatchResult(result.dispatcher_spec, result.source_event_id,
                    (), result.position_lot_books, ()))
            elif tamper == "backdate":
                events = tuple(replace(value, occurred_at=f.sim(225, TimelinePhase(1, "backdate"), 0)) for value in events)
            elif tamper == "swap":
                events = tuple(replace(value, event_id="unbound-application") for value in events)
            else:
                return replace(outcome, result=replace(result, journal_entries=(state.journal.entries[0],)))
            after = state.settlement_book.append(events=events)
            return replace(outcome, result=replace(result, settlement_events=events, settlement_book_hash=after.book_hash))

    outcome = DeterministicBarEngine(Broken()).run(settlement_case())
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE


def test_finalization_applies_in_window_due_but_keeps_exact_end_due_pending():
    from crypto_quant_trading import PositionSizingPolicy, ResidualPositionPolicy
    from crypto_quant_domain import PricePurpose, RoundingPolicy

    dispatcher = SyntheticSettlementDispatcher()
    dispatcher.position_due_by_fill_time = {150: 299, 250: 300}
    case = settlement_case(weights=("0.5", "0.8", "0"), bar_times=(150, 250))
    # With the synthetic spread but no first fee, equity=99950 and 80% is exact cents.
    from crypto_quant_trading import FinalFeeApplicability, FinalFeeRuleSet
    first, second = case.bar_executions
    fee = first.accounting_plan.fee_plan
    rules = fee.final_fee_rule_set
    assert isinstance(rules, FinalFeeRuleSet)
    zero = FinalFeeRuleSet.create(market_fee_policy_ref=rules.market_fee_policy_ref,
        tax_policy_ref=rules.tax_policy_ref, account_fee_schedule_ref=rules.account_fee_schedule_ref,
        assessment_currency=rules.assessment_currency, assessment_scale=rules.assessment_scale,
        minimums=rules.minimums, charge_rules=tuple(replace(rule, applicability=FinalFeeApplicability.NOT_APPLICABLE)
            for rule in rules.charge_rules))
    first = replace(first, accounting_plan=replace(first.accounting_plan, fee_plan=replace(fee, final_fee_rule_set=zero)))
    case = replace(case, bar_executions=(first, second))
    sizing = PositionSizingPolicy.create(policy_key="test.mixed-boundary", policy_version=1,
        price_purpose=PricePurpose.VALUATION, rounding=RoundingPolicy.TOWARD_ZERO,
        residual_policy=ResidualPositionPolicy.CLOSE_IF_PERMITTED)
    case = _respec(replace(case, decision_cycles=tuple(replace(cycle, sizing_policy=sizing) for cycle in case.decision_cycles)))
    outcome = DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is not None, outcome.engine_failure
    rows = _closure(outcome.result)
    assert rows["settlement-event.applied.0.1"].status == "used"
    assert rows["settlement-event.applied.1.1"].reason == "pending_beyond_window"
    [artifact] = [value for value in outcome.result.financial_artifacts if value.role.startswith("settlement.settlement-due:")]
    assert artifact.occurred_at.instant == UtcInstant(300)
    assert isinstance(artifact.payload, SettlementFinancialDispatchResult)
    assert len(artifact.payload.settlement_events) == 1


def test_reserved_settlement_slots_are_required_even_when_no_fill_occurs():
    case = settlement_case(weights=("0", "0", "0"))
    outcome = DeterministicBarEngine(SyntheticSettlementDispatcher()).run(case)
    assert outcome.result is not None, outcome.engine_failure
    assert not any(a.role.startswith("settlement.") for a in outcome.result.financial_artifacts)
    rows = _closure(outcome.result)
    assert all(row.status == "unused" for key, row in rows.items() if key.startswith("settlement"))
    assert case.identity_manifest is not None
    bindings = tuple(value for value in case.identity_manifest.bindings if value.binding_key != "settlement-event.applied.0.1")
    bad = replace(case, identity_manifest=replace(case.identity_manifest, bindings=bindings))
    failure = DeterministicBarEngine(SyntheticSettlementDispatcher()).run(bad)
    assert failure.engine_failure is not None and failure.engine_failure.subject_keys == ("live_identity_manifest",)
