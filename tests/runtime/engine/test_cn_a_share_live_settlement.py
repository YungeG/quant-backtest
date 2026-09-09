"""Real CN calendar/settlement via public Engine; synthetic prices/zero fees only.

The unchanged Engine.run seam is authorized by #30. This is adapter wiring,
not retained-source market/fee acceptance or an executable research experiment.
"""
from dataclasses import replace
from datetime import datetime
from functools import cache
from zoneinfo import ZoneInfo

import pytest

import crypto_quant_backtest as bt
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketEvent
from crypto_quant_trading.profiles.cn_a_share import CnAShareCashSettlementModel, CnAShareSettlementResolution
from tests.runtime.engine import _fixtures as f
from tests.runtime.engine.test_live_execution_case import _closure, _respec
from tests.runtime.profiles.cn_a_share.test_000703_development_profile_v2 import _request


def instant(day, hour=0, minute=0):
    return d.UtcInstant.from_datetime(datetime(2024, 1, day, hour, minute, tzinfo=ZoneInfo("Asia/Shanghai")))


def clock(at, rank, code, sequence=0):
    return d.SimulationInstant(at, d.TimelinePhase(rank, code), d.SourceSequence(sequence))


@cache
def profile():
    outcome = bt.CnAShareProfileComposerV2().compose(_request())
    assert outcome.result is not None, outcome.failure
    return outcome.result


def cn_case(*, weights=("0.5", "0", "0"), decision_times=None, close_times=None, end_at=None, synthetic_fees=False, identity_factory=None, combined_fees=False, source_bars=None, source_price=None):
    authority = profile()
    dispatcher = bt.CnAShareDevelopmentFinancialDispatcherV2(authority)
    request = authority.request
    instrument = request.instrument_scope.instrument
    iid, venue, cny = instrument.instrument_id, instrument.instrument_id.venue, d.CurrencyId("CNY")
    account = request.account_scope.account_id
    cash_key, position_key = d.CashBalanceKey(account, venue, cny), d.PositionBalanceKey(account, venue, iid)
    catalog = d.InstrumentCatalog((cny,), (instrument,), ())
    scale = d.Scale(2)
    initial = d.Money(10_000_000, scale, "CNY")
    start, end = instant(2), end_at or instant(3, 10, 5)
    window = bt.TimelineWindow(start, instant(2, 9, 30), end)
    times = decision_times or (instant(2, 9, 35), instant(2, 10), instant(3, 9, 35))
    bar_times = close_times or (instant(2, 9, 40), instant(2, 10, 5), instant(3, 9, 40))
    price = source_price or d.Price(10_000, scale, str(iid), "CNY")
    quant = d.QuantizationPolicy("cn-test.notional", scale, d.RoundingPolicy.HALF_UP)
    strategy, sleeve = "strategy:cn-test", d.StrategySleeveId("sleeve:cn-test")
    targets = []
    for i, (at, weight) in enumerate(zip(times, weights, strict=True)):
        payload = f.target_payload(decision_time=at.epoch_nanoseconds)
        payload.update(strategy_id=strategy, sleeve_id=sleeve.value, expires_at=end.epoch_nanoseconds,
            targets=[{"instrument_id": {"venue": venue.value, "stable_key": iid.stable_key}, "value": weight}])
        targets.append(MarketEvent(f"cn-target:{i}", "targets", bt.TARGET_STREAM_EVENT_TYPE, bt.TARGET_STREAM_CAPABILITY,
            None, at, at, d.TimelinePhase(100, "decision"), d.SourceSequence(i), "test-revision", None,
            "cn-test.synthetic", "sha256:" + "1" * 64, {"schema_version": 1, "candidate": payload}))
    bars = tuple(MarketEvent(f"cn-close:{i}", "bars.close", bt.BAR_CLOSE_EVENT_TYPE, bt.BAR_CLOSE_CAPABILITY,
        iid, at, at, d.TimelinePhase(60, "bar_close"), d.SourceSequence(i), "test-revision", None,
        "cn-test.synthetic", "sha256:" + "1" * 64,
        {"schema_version": 1, "bar_kind": "real", "close_price": {"units": price.units, "scale": 2, "quote_currency": "CNY"},
         "interval_start": d.UtcInstant(at.epoch_nanoseconds - 300_000_000_000).to_canonical_dict(),
         "interval_end_exclusive": at.to_canonical_dict()}) for i, at in enumerate(bar_times))
    bars = source_bars or bars
    bar_stream = bars[0].stream_key
    kinds: dict[str, d.DomainIdKind | None] = {"journal.initial.0": d.DomainIdKind.JOURNAL}
    for i in range(len(targets)):
        kinds[f"order.{i}.0"] = d.DomainIdKind.ORDER
        kinds[f"order-event.expire.{i}"] = None
        for j in range(8):
            kinds[f"order-event.{i}.0.{j}"] = None
    for i in range(len(bars)):
        for key, kind in (("fill", d.DomainIdKind.FILL), ("journal.fill", d.DomainIdKind.JOURNAL),
                          ("fee", d.DomainIdKind.FEE), ("journal.fee", d.DomainIdKind.JOURNAL), ("order-event.fill", None)):
            kinds[f"{key}.{i}"] = kind
        if combined_fees:
            kinds[f"fee.fill.{i}"] = d.DomainIdKind.FEE
            kinds[f"journal.fee.fill.{i}"] = d.DomainIdKind.JOURNAL
        for j in range(2):
            for key, kind in (("settlement", d.DomainIdKind.SETTLEMENT), ("settlement-event.recorded", None), ("settlement-event.applied", None)):
                kinds[f"{key}.{i}.{j}"] = kind
    rules = tuple(bt.ExecutionCaseIdentityRule(key, key, 0, kind) for key, kind in kinds.items())
    factory = identity_factory or bt.ExecutionCaseIdentityFactory(semantic_run_id="cn-settlement-wiring", namespace=d.IdentityNamespace("backtest", "1"), identity_plan=rules)
    ids = {key: factory.domain_id(key) for key, kind in kinds.items() if kind is not None}
    event_ids = {key: factory.event_id(key) for key, kind in kinds.items() if kind is None}
    schema = t.LedgerSchema((t.LedgerBalanceRegistration(cash_key, scale), t.LedgerBalanceRegistration(position_key, d.Scale(0))))
    deposit = d.AccountingJournalEntry(ids["journal.initial.0"], d.AccountingEntryType.CAPITAL_DEPOSITED,
        account, venue, start, clock(start, 1, "initial"), ("cn-test.initial-capital",),
        (d.BalanceChange(cash_key, initial),), (), (), ())
    journal = t.AccountingJournal.from_entries((deposit,))
    ledger = t.GenericLedger(schema).project(journal)

    def snapshot(at):
        mark = t.ResolvedMark(iid, cny, d.PricePurpose.VALUATION, price, at.instant, at.instant, at.instant, 0,
            "valuation", f"mark:{at.instant.epoch_nanoseconds}", "test-revision", "test-fresh", 1, "sha256:" + "1" * 64,
            available_at_instant=at, resolved_at_instant=at)
        return bt.LedgerCashSnapshotProjectionPlan((mark,), cny, scale, at, catalog,
            t.CurrencyValuationGraph(at.instant, d.PricePurpose.VALUATION, ()), quant)

    zero = d.Money(0, scale, "CNY")
    initial_snapshot = d.PortfolioSnapshot(account, start, cny, ledger.cash_balances, (), zero, zero, zero, zero, initial,
        (), ledger.state_hash, d.canonical_sha256(()), d.canonical_sha256(()),
        t.CurrencyValuationGraph(start, d.PricePurpose.VALUATION, ()).graph_hash)
    model = CnAShareCashSettlementModel(request.calendar)
    financial = bt.ResolvedFinancialState(journal, schema, initial_snapshot, (bt.PositionLotBook(position_key),),
        (), (), (), t.SettlementBook(account), model.availability_rules(schema))
    lattice = t.QuantityLattice.create(instrument_id=iid, lattice_key="cn-test.lattice", lattice_version=1,
        atomic_scale=d.Scale(0), step_units=1, buy_lot_units=100, sell_lot_units=100, min_quantity_units=0,
        min_notional=zero, odd_lot_close_permitted=True)
    reservation_base, final_base = f.fee_reservation_rules(), f.final_fee_rule_set()
    reservation_fees = t.FeeReservationRuleSet.create(market_fee_policy_ref=reservation_base.market_fee_policy_ref,
        tax_policy_ref=reservation_base.tax_policy_ref, account_fee_schedule_ref=reservation_base.account_fee_schedule_ref,
        reservation_currency=cny, reservation_scale=scale, minimums=(),
        charge_rules=tuple(replace(rule, applicability=rule.applicability if synthetic_fees else t.FeeReservationApplicability.NOT_APPLICABLE,
            flat_amount=replace(rule.flat_amount, currency="CNY") if rule.flat_amount is not None else None)
            for rule in reservation_base.charge_rules))
    final_fees = t.FinalFeeRuleSet.create(market_fee_policy_ref=final_base.market_fee_policy_ref,
        tax_policy_ref=final_base.tax_policy_ref, account_fee_schedule_ref=final_base.account_fee_schedule_ref,
        assessment_currency=cny, assessment_scale=scale, minimums=(),
        charge_rules=tuple(replace(rule, applicability=rule.applicability if synthetic_fees else t.FinalFeeApplicability.NOT_APPLICABLE,
            flat_amount=replace(rule.flat_amount, currency="CNY") if rule.flat_amount is not None else None)
            for rule in final_base.charge_rules))
    risk = t.PortfolioRiskPolicy.create(policy_key="cn-test.risk", policy_version=1, valuation_currency=cny,
        notional_scale=scale, limits=(t.PortfolioRiskLimit("gross", t.PortfolioRiskScope.GROSS_EXPOSURE,
        initial, t.PortfolioRiskAction.REJECT, None), t.PortfolioRiskLimit("net", t.PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
        initial, t.PortfolioRiskAction.REJECT, None), t.PortfolioRiskLimit("target", t.PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
        initial, t.PortfolioRiskAction.REJECT, iid)))
    account_risk = t.AccountRiskPolicy.create(policy_key="cn-test.account-risk", policy_version=1, account_id=account,
        venue_id=venue, allowed_sides=(d.OrderSide.BUY, d.OrderSide.SELL),
        allowed_position_effects=(d.PositionEffect.AUTO, d.PositionEffect.OPEN, d.PositionEffect.CLOSE),
        allowed_reduce_only_values=(False, True), fee_reserve_funding_source=t.FeeReserveFundingSource.TRADABLE_CASH,
        order_capacity_limit=1, exposure_capacity_limits=(t.ExposureCapacityLimit(initial),))
    rule_snapshot = t.OrderRuleSnapshot.create(component_ref=f.order_rule_timeline().intervals[0].snapshot.component_ref,
        instrument_id=iid, session_id=d.SessionId("CN.XSHE", "test-open"), session_state=t.MarketSessionState.OPEN,
        quantity_lattice=lattice, price_scale=scale, price_tick_units=1, lower_price_limit=None, upper_price_limit=None,
        permitted_sides=(d.OrderSide.BUY, d.OrderSide.SELL),
        permitted_position_effects=(d.PositionEffect.AUTO, d.PositionEffect.OPEN, d.PositionEffect.CLOSE),
        reduce_only_required=False, notional_rounding=d.RoundingPolicy.HALF_UP, supplemental_decisions=())
    rule_timeline = t.OrderRuleTimeline.create(timeline_key="cn-test.rules", timeline_version=1, instrument_id=iid,
        intervals=(t.OrderRuleInterval.create(effective_from=start, effective_to_exclusive=end, snapshot=rule_snapshot),))

    def pretrade(at):
        return bt.ResolvedCashPreTradeAuthority(rule_timeline, t.OrderRuleNotionalEvidence(t.NotionalPriceBasis.SUPPLIED_REFERENCE,
            price, d.canonical_sha256(price), at), at, reservation_fees, "cn-test.authority", 1, authority.profile_hash, account_risk)

    event_types = (d.OrderEventType.ORDER_INTENT_CREATED, d.OrderEventType.ORDER_CAPABILITY_APPROVED,
        d.OrderEventType.ORDER_TRANSLATED, d.OrderEventType.MARKET_RULE_APPROVED, d.OrderEventType.FEE_RESERVATION_ESTIMATED,
        d.OrderEventType.PRE_TRADE_RISK_APPROVED, d.OrderEventType.ORDER_SUBMITTED, d.OrderEventType.ORDER_ACCEPTED)
    cycles = []
    for i, event in enumerate(targets):
        context = t.StrategyOutputValidationContext(strategy, sleeve, event.event_time, catalog, (iid,), decision_instant=event.timeline_instant)
        schedule = bt.TargetStreamDecisionSchedule(event.event_time, bt.TimelineSegment.ACTIVE_TRADING,
            (bt.TargetStreamScheduleEntry(event.event_id, t.DecisionBatchExpectation(strategy, sleeve), context),))
        slot = bt.ResolvedOrderAdmissionSlot(ids[f"order.{i}.0"], f.capability_set(), f.translation_mapping(), event.event_time,
            pretrade(event.event_time), tuple(bt.OrderEventPlan(kind, event_ids[f"order-event.{i}.0.{j}"],
                clock(event.event_time, 110, "admission", j), "test-venue" if j >= 6 else None) for j, kind in enumerate(event_types)),
            event_ids[f"order-event.expire.{i}"])
        cycles.append(bt.ResolvedDecisionCycleV2(schedule, snapshot(event.timeline_instant), f.allocation_policy_ref(), scale,
            risk, f.sizing_policy(), lattice, end, t.RebalancePolicy.create(policy_key="cn-test.rebalance", policy_version=1,
            execution_style=d.ExecutionStyle.MARKET, time_in_force=d.TimeInForce.DAY, urgency="normal", plan_valid_for_nanoseconds=None), slot))
    plans = []
    for i, event in enumerate(bars):
        at = event.event_time
        fill_clock, fee_clock = clock(at, 80, "accounting"), clock(at, 90, "fee", 2)
        policy = t.CostBasisPolicy("cn-test.fifo", 2, t.CostBasisMethod.FIFO, d.RoundingPolicy.HALF_UP)
        payload = bt.CashFillAccountingPlan(cash_key, position_key, policy, quant, ids[f"journal.fill.{i}"], fill_clock,
            final_fees, ids[f"fee.{i}"], at, ids[f"journal.fee.{i}"], fee_clock)
        accounting = bt.SettlementFillAccountingDispatchPlan(event.event_id, ids[f"fill.{i}"], dispatcher.spec.position_accounting_component,
            payload, f.CashAccountingSemanticPayload(cash_key, position_key, policy, quant), ids[f"journal.fill.{i}"], fill_clock,
            bt.FeeAccountingDispatchPlan(cash_key, final_fees, ids[f"fee.{i}"], at, ids[f"journal.fee.{i}"], fee_clock),
            (f"position_accounting.{event.event_id}", f"settlement.{event.event_id}", f"settlement_resolution.{event.event_id}"),
            settlement_slots=tuple(bt.SettlementIdentitySlot(key, ids[f"settlement.{i}.{j}"], event_ids[f"settlement-event.recorded.{i}.{j}"],
                event_ids[f"settlement-event.applied.{i}.{j}"]) for j, key in enumerate((cash_key, position_key))),
            settlement_recorded_at=clock(at, 75, "settlement_record"))
        if combined_fees:
            fee = accounting.fee_plan
            child = replace(fee, fee_assessment_id=ids[f"fee.fill.{i}"],
                fee_journal_entry_id=ids[f"journal.fee.fill.{i}"], fee_recorded_at=clock(at, 85, "fill_fee", 2))
            accounting = replace(accounting, fee_plan=bt.FullFillOrderFeeAccountingPlan(
                fee.cash_key, fee.final_fee_rule_set, fee.fee_assessment_id, fee.fee_assessment_time,
                fee.fee_journal_entry_id, fee.fee_recorded_at, child))
        base_slippage = f.slippage_model()
        slippage = replace(base_slippage, basis_points_units=0,
            component_ref=replace(base_slippage.component_ref, component_key="zero_slippage.development.v1"),
            limitations=(bt.SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,),
            applicability_envelope=bt.SlippageApplicabilityEnvelope.create(
            envelope_key="cn-test.slippage", envelope_version=1, instrument_id=iid, valid_from=start, valid_to_exclusive=end,
            maximum_quantity=d.Quantity(1_000_000, d.Scale(0), str(iid)), allowed_market_state_keys=("normal",)))
        plans.append(bt.ResolvedBarPlanV2(event.event_id, iid, pretrade(at), bt.BarLiquidityEvidence.create(evidence_key="cn-test.liquidity",
            evidence_version=1, market_event=event, evaluated_at=at, approved=True, reason_code=None, source_hash=event.event_hash),
            bt.SlippageMarketState("normal", at, at, event.event_id, event.revision_id, event.event_hash), slippage,
            ids[f"fill.{i}"], event_ids[f"order-event.fill.{i}"], clock(at, 70, "fill"), accounting))
    reader = InMemoryMarketBundleReader.build(bundle_key="cn-settlement.synthetic-prices", schema_version=1, coverage_start=start,
        coverage_end_exclusive=end, instrument_catalog_hash=d.canonical_sha256(catalog),
        capabilities=(bt.TARGET_STREAM_CAPABILITY, bt.BAR_CLOSE_CAPABILITY), streams={"targets": tuple(targets), bar_stream: bars})
    timeline = bt.DeterministicTimeline.open(reader=reader, stream_keys=(bar_stream, "targets"), window=window)
    assert isinstance(timeline, bt.DeterministicTimeline)
    final = snapshot(clock(end, 1_000_000, "engine_finalize"))
    dispatch_plan = bt.FinancialDispatchPlan(dispatcher.spec, (), final,
        ("final_snapshot", "runtime.identity_closure", *(f"snapshot.{event.event_id}" for event in targets)))
    execution = bt.NextEligibleBarCloseModel.create(actions=tuple((tif, bt.NoEligibleBarAction.EXPIRE if tif in
        {d.TimeInForce.DAY, d.TimeInForce.IOC, d.TimeInForce.FOK} else bt.NoEligibleBarAction.KEEP_ACTIVE) for tif in d.TimeInForce))
    case = bt.ResolvedExecutionCaseV2("cn-settlement.wiring", 2, "sha256:" + "2" * 64, timeline, 1,
        bt.PrecomputedTargetStream("targets", tuple(targets)), tuple(cycles), tuple(plans), financial, dispatch_plan,
        execution, final, bt.MarkToMarketCloseoutPolicy(), factory.manifest())
    spec = bt.ExecutionCaseComposer.semantic_spec_from_case(case, spec_key="cn-settlement.wiring", spec_version=2,
        identity_namespace=factory.namespace, identity_plan=rules)
    return replace(case, semantic_spec=spec, semantic_spec_hash=spec.semantic_spec_hash), dispatcher


def test_profile_settlement_uses_actual_fills_then_real_next_day_boundary():
    case, dispatcher = cn_case()
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    assert [(fill.side, fill.execution_time, fill.quantity.units) for fill in result.fills] == [
        (d.OrderSide.BUY, instant(2, 9, 40), 500), (d.OrderSide.SELL, instant(3, 9, 40), 500)]
    assert len(result.order_streams) == 2
    assert result.final_portfolio_snapshot.positions == ()
    assert result.final_portfolio_snapshot.cash[0].amount.units == 10_000_000
    rows = _closure(result)
    assert rows["order.1.0"].reason == "pending_position_settlement"
    assert rows["settlement-event.applied.0.1"].status == "used"
    assert rows["settlement-event.applied.2.0"].reason == "pending_beyond_window"
    resolutions = [a.payload for a in result.financial_artifacts if a.role.startswith("settlement_resolution.")]
    assert len(resolutions) == 2
    buy_resolution, sell_resolution = resolutions
    assert isinstance(buy_resolution, t.ProfilePortOutcome) and isinstance(buy_resolution.result, CnAShareSettlementResolution)
    assert isinstance(sell_resolution, t.ProfilePortOutcome) and isinstance(sell_resolution.result, CnAShareSettlementResolution)
    assert buy_resolution.result.position_availability_time == instant(3)
    assert sell_resolution.result.cash_withdrawal_time == instant(4, 16)
    maturity = next(a for a in result.financial_artifacts if a.role.startswith("settlement.settlement-due:"))
    assert maturity.occurred_at == case.decision_cycles[2].snapshot_plan.projection_at
    assert isinstance(maturity.payload, bt.SettlementFinancialDispatchResult)
    assert all(e.occurred_at == maturity.occurred_at for e in maturity.payload.settlement_events)
    replay = bt.DeterministicBarEngine(dispatcher).run(replace(case, timeline_batch_size=16))
    assert replay.result is not None and replay.result.result_hash == result.result_hash


def test_profile_cash_fee_hook_preserves_nonzero_fee_accounting():
    # Synthetic 10 bps market fee and SELL 5 bps tax; not January CN fee authority.
    case, dispatcher = cn_case(synthetic_fees=True)
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is not None, outcome.engine_failure
    assert outcome.result.final_portfolio_snapshot.fees == d.Money(12_500, d.Scale(2), "CNY")
    assert outcome.result.final_portfolio_snapshot.cash[0].amount.units == 9_987_500
    assert outcome.result.final_portfolio_snapshot.positions == ()
    rows = _closure(outcome.result)
    assert rows["journal.fee.0"].status == rows["journal.fee.2"].status == "used"


def test_resolved_profile_identity_is_bound_to_the_dispatcher_spec():
    case, original = cn_case()
    before = profile().request
    new_request = replace(before, composed_at=replace(before.composed_at,
        instant=d.UtcInstant(before.composed_at.instant.epoch_nanoseconds + 1)))
    composed = bt.CnAShareProfileComposerV2().compose(new_request)
    assert composed.result is not None, composed.failure
    changed = bt.CnAShareDevelopmentFinancialDispatcherV2(composed.result)
    assert changed.spec != original.spec
    outcome = bt.DeterministicBarEngine(changed).run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is bt.EngineFailureCode.FINANCIAL_DISPATCH_FAILURE


def test_no_fill_keeps_settlement_slots_unused_and_january_has_no_dividend_events():
    case, dispatcher = cn_case(weights=("0", "0", "0"))
    assert dispatcher.scheduled_account_events == ()
    result = bt.DeterministicBarEngine(dispatcher).run(case)
    assert result.result is not None, result.engine_failure
    assert result.result.fills == ()
    assert all(row.status == "unused" for key, row in _closure(result.result).items() if key.startswith("settlement"))
    assert not any(artifact.role.startswith(("settlement.", "settlement_resolution.", "tushare_dividend"))
        for artifact in result.result.financial_artifacts)


def test_profile_dispatcher_spec_cannot_be_replaced_with_generic_cash():
    case, _ = cn_case()
    outcome = bt.DeterministicBarEngine().run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is bt.EngineFailureCode.FINANCIAL_DISPATCH_FAILURE


@pytest.mark.parametrize("change", ("missing_resolution_role", "plain_accounting_plan"))
def test_profile_cannot_silently_run_cash_accounting_without_settlement(change):
    case, dispatcher = cn_case()
    first = case.bar_executions[0]
    plan = first.accounting_plan
    if change == "missing_resolution_role":
        plan = replace(plan, expected_artifact_roles=tuple(role for role in plan.expected_artifact_roles
            if not role.startswith("settlement_resolution.")))
    else:
        plan = bt.EventScopedFillAccountingDispatchPlan(plan.source_event_id, plan.expected_fill_id,
            plan.position_accounting_component, plan.position_payload, plan.semantic_payload, plan.fill_journal_entry_id,
            plan.fill_recorded_at, plan.fee_plan, plan.expected_artifact_roles)
        # Keep identity closure honest for the non-settlement case, so the profile
        # dispatch seam (not an unrelated manifest check) rejects this downgrade.
        removed = {f"{prefix}.0.{j}" for prefix in ("settlement", "settlement-event.recorded", "settlement-event.applied") for j in range(2)}
        assert case.semantic_spec is not None and case.identity_manifest is not None
        spec = replace(case.semantic_spec, identity_plan=tuple(rule for rule in case.semantic_spec.identity_plan if rule.binding_key not in removed))
        manifest = replace(case.identity_manifest, bindings=tuple(row for row in case.identity_manifest.bindings if row.binding_key not in removed))
        case = replace(case, identity_manifest=manifest, semantic_spec=spec, semantic_spec_hash=spec.semantic_spec_hash)
    case = _respec(replace(case, bar_executions=(replace(first, accounting_plan=plan), *case.bar_executions[1:])))
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is bt.EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert "cn_a_share_settlement_scope" in outcome.engine_failure.subject_keys


@pytest.mark.parametrize("at", (instant(2, 12), instant(2, 15)))
def test_existing_model_session_rejection_is_not_retimed_or_bypassed(at):
    case, dispatcher = cn_case(weights=("0.5", "0.5", "0"),
        decision_times=(instant(2, 9, 35), instant(3, 9, 30), instant(3, 9, 35)),
        close_times=(at, instant(3, 9, 40), instant(3, 9, 45)))
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is bt.EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert "trade_time_not_open" in outcome.engine_failure.subject_keys


def test_actual_january_final_trade_without_frozen_successor_fails_closed():
    case, dispatcher = cn_case(weights=("0.5", "0.5", "0"), end_at=instant(31, 16),
        decision_times=(instant(31, 9, 35), instant(31, 10), instant(31, 11)),
        close_times=(instant(31, 9, 40), instant(31, 10, 5), instant(31, 11, 5)))
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert "calendar_coverage_missing" in outcome.engine_failure.subject_keys
