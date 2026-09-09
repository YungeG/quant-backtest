"""Same-engine live cash execution; synthetic wiring, not A-share evidence."""
from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from crypto_quant_backtest import (
    BAR_CLOSE_CAPABILITY, BAR_CLOSE_EVENT_TYPE, TARGET_STREAM_CAPABILITY,
    BarLiquidityEvidence, CashFillAccountingPlan, DeterministicBarEngine, DeterministicTimeline,
    EngineFailureCode, RuntimeIdentityClosure, DefaultCashFinancialDispatcher,
    EventScopedFillAccountingDispatchPlan, FullFillOrderFeeAccountingPlan,
    FinancialDispatchFailureCode,
    ExecutionCaseComposer, ExecutionCaseIdentityFactory, ExecutionCaseIdentityRule,
    FinancialDispatchPlan, LedgerCashSnapshotProjectionPlan, MarkToMarketCloseoutPolicy,
    NextEligibleBarCloseModel, NoEligibleBarAction, OrderEventPlan, PrecomputedTargetStream,
    ResolvedBarPlanV2, ResolvedCashPreTradeAuthority, ResolvedDecisionCycleV2,
    ResolvedExecutionCaseV2, ResolvedOrderAdmissionSlot, SlippageMarketState,
    TargetStreamDecisionSchedule, TargetStreamScheduleEntry, TimelineSegment, TimelineWindow,
    default_cash_financial_dispatcher_spec,
)
from crypto_quant_domain import (
    DomainIdKind, FeeBasisType, IdentityNamespace, OrderEventType, OrderSide, PortfolioSnapshot, PricePurpose,
    SourceSequence, TimelinePhase, TimeInForce, UtcInstant, canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading import CurrencyValuationGraph, FinalFeeApplicability, FinalFeeRuleSet
from tests.kernel.market_rules._fixtures import reference_notional_evidence
from tests.runtime.engine import _fixtures as f


def _target(at: int, weight: str):
    payload = f.target_payload(decision_time=at)
    payload["expires_at"] = 290
    payload["targets"] = [{"instrument_id": {"venue": f.VENUE.value, "stable_key": f.BTC.stable_key}, "value": weight}]
    return replace(f.target_event(), event_id=f"live-target:{at}", event_time=UtcInstant(at),
                   available_time=UtcInstant(at), phase=TimelinePhase(100, "decision"),
                   payload={"schema_version": 1, "candidate": payload})


def _bar(at: int):
    return replace(f.bar_event(), event_id=f"live-close:{at}", stream_key="bars.close",
                   capability=BAR_CLOSE_CAPABILITY, event_type=BAR_CLOSE_EVENT_TYPE,
                   event_time=UtcInstant(at), available_time=UtcInstant(at),
                   phase=TimelinePhase(60, "bar_close"), payload={
                       "schema_version": 1, "bar_kind": "real",
                       "close_price": {"units": 10_000, "scale": 2, "quote_currency": "USD"},
                       "interval_start": UtcInstant(at - 300_000_000_000).to_canonical_dict(),
                       "interval_end_exclusive": UtcInstant(at).to_canonical_dict(),
                   })


def _snapshot(at):
    mark = replace(f.valuation_mark(resolved_at=at.instant),
                   available_at_instant=replace(at, instant=UtcInstant(at.instant.epoch_nanoseconds - 5)),
                   resolved_at_instant=at)
    return LedgerCashSnapshotProjectionPlan(
        (mark,), f.USD, f.MONEY_SCALE, at, f.catalog(),
        CurrencyValuationGraph(at.instant, PricePurpose.VALUATION, ()),
        cast(CashFillAccountingPlan, f.cash_accounting_plan().position_payload).notional_quantization,
    )


def _authority(at: int):
    return ResolvedCashPreTradeAuthority(
        order_rule_timeline=f.order_rule_timeline(),
        notional_evidence=reference_notional_evidence(price_units=10_000, available_at=at),
        evaluated_at=UtcInstant(at), fee_reservation_rule_set=f.fee_reservation_rules(),
        requirement_source_key="generic.cash.live-test.v1", requirement_source_version=1,
        requirement_source_hash="sha256:" + "a1" * 32, account_risk_policy=f.account_risk_policy(),
    )


def live_case(*, weights=("0.5", "0"), bar_times=(150, 250, 270), combined_fees=False, decision_times=(100, 200)):
    targets = tuple(_target(at, weight) for at, weight in zip(decision_times, weights, strict=True))
    bars = tuple(_bar(at) for at in bar_times)
    kinds: dict[str, DomainIdKind | None] = {"journal.initial.0": DomainIdKind.JOURNAL}
    for i in range(len(targets)):
        kinds[f"order.{i}.0"] = DomainIdKind.ORDER
        kinds[f"order-event.expire.{i}"] = None
        for j in range(8):
            kinds[f"order-event.{i}.0.{j}"] = None
    for i in range(len(bars)):
        for key, kind in (("fill", DomainIdKind.FILL), ("journal.fill", DomainIdKind.JOURNAL),
                          ("fee", DomainIdKind.FEE), ("journal.fee", DomainIdKind.JOURNAL),
                          ("order-event.fill", None)):
            kinds[f"{key}.{i}"] = kind
        if combined_fees:
            kinds[f"fee.fill.{i}"] = DomainIdKind.FEE
            kinds[f"journal.fee.fill.{i}"] = DomainIdKind.JOURNAL
    rules = tuple(ExecutionCaseIdentityRule(key, key, 0, kind) for key, kind in kinds.items())
    factory = ExecutionCaseIdentityFactory(semantic_run_id="live-case-test", namespace=IdentityNamespace("backtest", "1"), identity_plan=rules)
    domain_ids = {key: factory.domain_id(key) for key, kind in kinds.items() if kind is not None}
    event_ids = {key: factory.event_id(key) for key, kind in kinds.items() if kind is None}
    cycles = []
    for i, target in enumerate(targets):
        context = replace(f.target_schedule().entries[0].validation_context,
                          decision_time=target.event_time, decision_instant=target.timeline_instant)
        schedule = TargetStreamDecisionSchedule(target.event_time, TimelineSegment.ACTIVE_TRADING, (
            TargetStreamScheduleEntry(target.event_id, f.target_schedule().entries[0].expectation, context),))
        event_types = (
            OrderEventType.ORDER_INTENT_CREATED, OrderEventType.ORDER_CAPABILITY_APPROVED,
            OrderEventType.ORDER_TRANSLATED, OrderEventType.MARKET_RULE_APPROVED,
            OrderEventType.FEE_RESERVATION_ESTIMATED, OrderEventType.PRE_TRADE_RISK_APPROVED,
            OrderEventType.ORDER_SUBMITTED, OrderEventType.ORDER_ACCEPTED,
        )
        event_plans = tuple(OrderEventPlan(
            kind, event_ids[f"order-event.{i}.0.{j}"],
            f.sim(target.event_time.epoch_nanoseconds, TimelinePhase(110, "admission"), j),
            f"simulated:{kind.value}" if j >= 6 else None,
        ) for j, kind in enumerate(event_types))
        slot = ResolvedOrderAdmissionSlot(
            domain_ids[f"order.{i}.0"], f.capability_set(), f.translation_mapping(),
            target.event_time, _authority(target.event_time.epoch_nanoseconds), event_plans,
            event_ids[f"order-event.expire.{i}"],
        )
        cycles.append(ResolvedDecisionCycleV2(
            schedule, _snapshot(target.timeline_instant), f.allocation_policy_ref(), f.MONEY_SCALE,
            f.risk_policy(), f.sizing_policy(), f.quantity_lattice(), UtcInstant(290),
            f.rebalance_policy(), slot,
        ))
    bar_plans = []
    for i, bar in enumerate(bars):
        at = bar.event_time.epoch_nanoseconds
        accounting = f.cash_accounting_plan()
        original = cast(CashFillAccountingPlan, accounting.position_payload)
        payload = replace(original,
                          cost_basis_policy=replace(original.cost_basis_policy, policy_version=2),
                          fill_journal_entry_id=domain_ids[f"journal.fill.{i}"],
                          fill_recorded_at=f.sim(at, TimelinePhase(80, "accounting"), 0),
                          fee_assessment_id=domain_ids[f"fee.{i}"], fee_assessment_time=UtcInstant(at),
                          fee_journal_entry_id=domain_ids[f"journal.fee.{i}"],
                          fee_recorded_at=f.sim(at, TimelinePhase(90, "fee"), 2))
        accounting = replace(accounting, source_event_id=bar.event_id, expected_fill_id=domain_ids[f"fill.{i}"],
                             position_payload=payload,
                             semantic_payload=f.CashAccountingSemanticPayload(payload.cash_key, payload.position_key, payload.cost_basis_policy, payload.notional_quantization),
                             fill_journal_entry_id=payload.fill_journal_entry_id, fill_recorded_at=payload.fill_recorded_at,
                             fee_plan=replace(accounting.fee_plan, fee_assessment_id=payload.fee_assessment_id,
                                              fee_assessment_time=bar.event_time, fee_journal_entry_id=payload.fee_journal_entry_id,
                                              fee_recorded_at=payload.fee_recorded_at),
                             expected_artifact_roles=(f"position_accounting.{bar.event_id}",))
        if combined_fees:
            fee = accounting.fee_plan
            prior = replace(fee, fee_assessment_id=domain_ids[f"fee.fill.{i}"],
                            fee_journal_entry_id=domain_ids[f"journal.fee.fill.{i}"],
                            fee_recorded_at=f.sim(at, TimelinePhase(85, "fill_fee"), 2))
            accounting = replace(accounting, fee_plan=FullFillOrderFeeAccountingPlan(
                fee.cash_key, fee.final_fee_rule_set, fee.fee_assessment_id, fee.fee_assessment_time,
                fee.fee_journal_entry_id, fee.fee_recorded_at, prior))
        accounting = EventScopedFillAccountingDispatchPlan(
            accounting.source_event_id, accounting.expected_fill_id, accounting.position_accounting_component,
            accounting.position_payload, accounting.semantic_payload, accounting.fill_journal_entry_id,
            accounting.fill_recorded_at, accounting.fee_plan, accounting.expected_artifact_roles,
        )
        slippage = f.slippage_model()
        envelope = slippage.applicability_envelope
        slippage = replace(slippage, applicability_envelope=type(envelope).create(
            envelope_key=envelope.envelope_key, envelope_version=envelope.envelope_version,
            instrument_id=envelope.instrument_id, valid_from=UtcInstant(at - 1), valid_to_exclusive=UtcInstant(at + 1),
            maximum_quantity=envelope.maximum_quantity, allowed_market_state_keys=envelope.allowed_market_state_keys))
        bar_plans.append(ResolvedBarPlanV2(
            bar.event_id, f.BTC, _authority(at),
            BarLiquidityEvidence.create(evidence_key="live-test", evidence_version=1, market_event=bar,
                                        evaluated_at=bar.event_time, approved=True, reason_code=None, source_hash="sha256:" + "b1" * 32),
            SlippageMarketState("normal", bar.event_time, bar.event_time, bar.event_id, "rev-1", bar.event_hash),
            slippage, domain_ids[f"fill.{i}"], event_ids[f"order-event.fill.{i}"],
            f.sim(at, TimelinePhase(70, "fill"), 0), accounting,
        ))
    reader = InMemoryMarketBundleReader.build(bundle_key="fixture.live-case.v2", schema_version=1,
        coverage_start=UtcInstant(0), coverage_end_exclusive=UtcInstant(400), instrument_catalog_hash=canonical_sha256(f.catalog()),
        capabilities=(TARGET_STREAM_CAPABILITY, BAR_CLOSE_CAPABILITY), streams={"targets": targets, "bars.close": bars})
    timeline = DeterministicTimeline.open(reader=reader, stream_keys=("bars.close", "targets"), window=TimelineWindow(UtcInstant(0), UtcInstant(90), UtcInstant(300)))
    assert isinstance(timeline, DeterministicTimeline)
    initial_ids = replace(f.LEGACY_DOMAIN_IDS, deposit_journal_id=domain_ids["journal.initial.0"])
    snapshot = _snapshot(f.sim(300, TimelinePhase(1_000_000, "engine_finalize"), 0))
    fixed_roles = ("final_snapshot", "runtime.identity_closure", *(f"snapshot.{event.event_id}" for event in targets))
    case = ResolvedExecutionCaseV2(
        "generic.live-cash-test", 2, "sha256:" + "c1" * 32, timeline, 1,
        PrecomputedTargetStream("targets", targets), tuple(cycles), tuple(bar_plans),
        f.financial_state(initial_ids), FinancialDispatchPlan(default_cash_financial_dispatcher_spec(), (), snapshot, fixed_roles),
        NextEligibleBarCloseModel.create(actions=tuple((tif, NoEligibleBarAction.EXPIRE if tif in {TimeInForce.DAY, TimeInForce.IOC, TimeInForce.FOK} else NoEligibleBarAction.KEEP_ACTIVE) for tif in TimeInForce)),
        snapshot, MarkToMarketCloseoutPolicy(), factory.manifest(),
    )
    spec = ExecutionCaseComposer.semantic_spec_from_case(case, spec_key="live-test", spec_version=2,
        identity_namespace=factory.namespace, identity_plan=rules)
    return replace(case, semantic_spec=spec, semantic_spec_hash=spec.semantic_spec_hash)


def _respec(case):
    old = case.semantic_spec
    assert old is not None
    spec = ExecutionCaseComposer.semantic_spec_from_case(case, spec_key=old.spec_key,
        spec_version=old.spec_version, identity_namespace=old.identity_namespace, identity_plan=old.identity_plan)
    return replace(case, semantic_spec=spec, semantic_spec_hash=spec.semantic_spec_hash)


def _run(case):
    before = canonical_bytes(case)
    outcome = DeterministicBarEngine().run(case)
    assert canonical_bytes(case) == before
    return outcome


def _closure(result):
    value = next(artifact.payload for artifact in result.financial_artifacts if artifact.role == "runtime.identity_closure")
    assert isinstance(value, RuntimeIdentityClosure)
    return {row.binding_key: row for row in value.dispositions}


def test_live_case_buys_then_materializes_sell_from_actual_ledger():
    case = live_case()
    before = canonical_bytes(case)
    outcome = DeterministicBarEngine().run(case)
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    assert [fill.side for fill in result.fills] == [OrderSide.BUY, OrderSide.SELL]
    assert [fill.quantity.units for fill in result.fills] == [5_000, 5_000]
    assert [fill.execution_time for fill in result.fills] == [UtcInstant(150), UtcInstant(250)]
    assert result.final_portfolio_snapshot.positions == ()
    # Existing synthetic fee authority: CEILING 10 bps; SELL also pays 5 bps tax.
    assert result.final_portfolio_snapshot.cash[0].amount.units == 99_774
    assert result.final_portfolio_snapshot.fees.units == 126
    second = next(artifact.payload for artifact in result.financial_artifacts if artifact.role == "snapshot.live-target:200")
    assert isinstance(second, PortfolioSnapshot)
    assert second.positions[0].quantity.units == 5_000
    assert second.equity.units == 99_899
    assert result.allocations[1].source_portfolio_snapshot_hash == canonical_sha256(second)
    closure = next(artifact.payload for artifact in result.financial_artifacts if artifact.role == "runtime.identity_closure")
    assert isinstance(closure, RuntimeIdentityClosure)
    rows = {row.binding_key: row for row in closure.dispositions}
    assert rows["order.1.0"].status == "used"
    assert rows["fill.2"].status == "unused"
    assert rows["fill.2"].reason == "no_active_order"
    assert case.identity_manifest is not None
    assert len(rows) == len(case.identity_manifest.bindings)
    assert canonical_bytes(case) == before
    replay = DeterministicBarEngine().run(replace(case, timeline_batch_size=10))
    assert replay.result is not None
    assert replay.result.result_hash == result.result_hash


@pytest.mark.parametrize("alteration", ("slippage", "actual_accounting_payload"))
def test_live_case_rejects_stale_semantic_authority(alteration):
    case = live_case()
    bar = case.bar_executions[-1]
    if alteration == "slippage":
        bar = replace(bar, slippage_model=replace(bar.slippage_model, basis_points_units=20))
    else:
        # Do not let a caller keep the semantic declaration while changing the
        # actual position-accounting policy that the dispatcher consumes.
        payload = cast(CashFillAccountingPlan, bar.accounting_plan.position_payload)
        payload = replace(payload, cost_basis_policy=replace(payload.cost_basis_policy, policy_version=3))
        bar = replace(bar, accounting_plan=replace(bar.accounting_plan, position_payload=payload))
    changed = replace(case, bar_executions=(*case.bar_executions[:-1], bar))
    outcome = _run(changed)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == ("live_semantic_spec",)


@pytest.mark.parametrize("evidence", ("liquidity", "liquidity_time", "state_id", "state_hash", "state_time", "fill_clock"))
def test_unused_close_still_requires_its_actual_market_evidence(evidence):
    case = live_case()
    first, second, third = case.bar_executions
    if evidence == "liquidity":
        third = replace(third, liquidity_evidence=first.liquidity_evidence)
    elif evidence == "liquidity_time":
        liquidity = third.liquidity_evidence
        third = replace(third, liquidity_evidence=BarLiquidityEvidence.create(
            evidence_key=liquidity.evidence_key, evidence_version=liquidity.evidence_version,
            market_event=_bar(270), evaluated_at=UtcInstant(271), approved=True,
            reason_code=None, source_hash=liquidity.source_hash))
    elif evidence == "state_id":
        third = replace(third, market_state=first.market_state)
    elif evidence == "state_hash":
        third = replace(third, market_state=replace(third.market_state, evidence_hash="sha256:" + "a2" * 32))
    elif evidence == "state_time":
        third = replace(third, market_state=replace(third.market_state, available_at=UtcInstant(271)))
    else:
        third = replace(third, fill_event_at=f.sim(270, TimelinePhase(50, "before_close"), 0))
    changed = _respec(replace(case, bar_executions=(first, second, third)))
    outcome = _run(changed)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.CASE_EVIDENCE_MISMATCH


def test_legacy_dispatch_plan_does_not_activate_new_event_scoped_roles():
    case = f.execution_case()
    bar = case.bar_executions[0]
    new_role = f"position_accounting.{bar.event_id}"
    bar = replace(bar, accounting_plan=replace(bar.accounting_plan, expected_artifact_roles=(new_role,)))
    case = replace(case, bar_executions=(bar,), financial_dispatch_plan=replace(
        case.financial_dispatch_plan, expected_artifact_roles=("final_snapshot", new_role)))
    result = _run(case)
    assert result.result is None and result.engine_failure is not None
    assert FinancialDispatchFailureCode.ARTIFACT_COVERAGE_MISMATCH.value in result.engine_failure.subject_keys


def test_zero_targets_close_all_unused_slots_without_inventing_financial_events():
    case = live_case(weights=("0", "0"))
    outcome = _run(case)
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    assert result.fills == result.fee_assessments == result.order_streams == ()
    assert result.final_journal == case.financial_state.journal
    assert result.final_portfolio_snapshot.equity.units == 100_000
    rows = _closure(result)
    assert rows["order.0.0"].reason == rows["order.1.0"].reason == "no_order_planned"
    assert rows["journal.initial.0"].status == "used"
    assert all(row.status == "unused" for key, row in rows.items() if key != "journal.initial.0")


def test_same_utc_close_fees_are_visible_only_to_later_phase_decision():
    case = live_case(bar_times=(150, 200, 250))
    outcome = _run(case)
    assert outcome.result is not None, outcome.engine_failure
    assert [fill.execution_time for fill in outcome.result.fills] == [UtcInstant(150), UtcInstant(250)]
    assert _closure(outcome.result)["fill.1"].reason == "no_active_order"
    # The target after the 200 close cannot trade on that already-processed close.
    case = live_case(bar_times=(200, 250, 270))
    outcome = _run(case)
    assert outcome.result is not None, outcome.engine_failure
    assert [fill.execution_time for fill in outcome.result.fills] == [UtcInstant(200), UtcInstant(250)]
    assert outcome.result.allocations[1].source_portfolio_snapshot_hash != outcome.result.allocations[0].source_portfolio_snapshot_hash


def test_signal_after_close_never_uses_that_same_close():
    outcome = _run(live_case(bar_times=(100, 150, 250)))
    assert outcome.result is not None, outcome.engine_failure
    assert [fill.execution_time for fill in outcome.result.fills] == [UtcInstant(150), UtcInstant(250)]
    assert _closure(outcome.result)["fill.0"].reason == "no_active_order"


@pytest.mark.parametrize("field", ("identity_manifest", "semantic_spec"))
def test_live_case_requires_closed_identity_authority(field):
    outcome = _run(replace(live_case(), **{field: None}))
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == ("live_identity_manifest",)


def test_live_case_rejects_reserved_identity_missing_from_manifest():
    case = live_case()
    assert case.identity_manifest is not None
    manifest = replace(case.identity_manifest, bindings=case.identity_manifest.bindings[:-1])
    outcome = _run(replace(case, identity_manifest=manifest))
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == ("live_identity_manifest",)


@pytest.mark.parametrize("field", ("event_id", "fill_id", "fill_event_id"))
def test_live_bar_identity_tampering_cannot_be_closed_as_unused(field):
    case = live_case()
    first, second, third = case.bar_executions
    with pytest.raises(ValueError):
        changed = replace(third, **{field: getattr(first, field)})
        _run(replace(case, bar_executions=(first, second, changed)))


def test_live_bar_plan_cannot_be_removed_from_observed_close_coverage():
    case = live_case()
    # Retain the original manifest: removing a reserved bar is also identity tampering.
    outcome = _run(replace(case, bar_executions=case.bar_executions[:-1]))
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == ("live_identity_manifest",)


def test_actual_settlement_identities_cannot_hide_outside_runtime_closure():
    from crypto_quant_backtest import SettlementFinancialDispatchResult
    from crypto_quant_domain import DomainId, SettlementObligation
    from crypto_quant_trading import AccountSettlementObligation, SettlementEvent, SettlementEventType

    class UnmanifestedSettlement(DefaultCashFinancialDispatcher):
        def book_fill(self, plan, fill, state, /):
            outcome = super().book_fill(plan, fill, state)
            assert outcome.result is not None and state.settlement_book is not None
            base, book = outcome.result, state.settlement_book
            identity = DomainId(DomainIdKind.SETTLEMENT, "stl_" + "ab" * 32)
            obligation = AccountSettlementObligation(SettlementObligation(
                identity, fill.fill_id, fill.execution_time, UtcInstant(400), f.BTC, fill.quantity, None, None), f.POSITION_KEY)
            event = SettlementEvent("unmanifested-settlement-record", identity, SettlementEventType.OBLIGATION_RECORDED,
                                    plan.fill_recorded_at, fill.fill_id.value, canonical_sha256(fill))
            after = book.append(obligations=(obligation,), events=(event,))
            return replace(outcome, result=SettlementFinancialDispatchResult(
                base.dispatcher_spec, base.source_event_id, base.journal_entries, base.position_lot_books, base.artifacts,
                settlement_obligations=(obligation,), settlement_events=(event,),
                prior_settlement_book_hash=book.book_hash, settlement_book_hash=after.book_hash))

    case = live_case(weights=("0", "0.5"))
    bars = tuple(replace(bar, accounting_plan=replace(bar.accounting_plan, expected_artifact_roles=(
        *bar.accounting_plan.expected_artifact_roles, f"settlement.{bar.event_id}"))) for bar in case.bar_executions)
    case = _respec(replace(case, bar_executions=bars))
    outcome = DeterministicBarEngine(UnmanifestedSettlement()).run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == ("live_identity_usage_coverage",)


def test_live_initial_state_cannot_preload_future_settlement_events():
    from tests.runtime.engine.test_settlement_financial_dispatch import _DelayedSettlementDispatcher, _case
    dispatcher = _DelayedSettlementDispatcher()
    old_outcome = DeterministicBarEngine(dispatcher).run(_case(dispatcher))
    assert old_outcome.result is not None
    assert dispatcher.final_view is not None and dispatcher.final_view.settlement_book is not None
    case = live_case()
    with pytest.raises(ValueError, match="pristine"):
        replace(case, financial_state=replace(case.financial_state, settlement_book=dispatcher.final_view.settlement_book))


def test_live_valuation_authority_is_required_even_for_zero_targets():
    case = live_case(weights=("0", "0"))
    cycle = case.decision_cycles[0]
    cycle = replace(cycle, snapshot_plan=replace(cycle.snapshot_plan, resolved_marks=()))
    outcome = _run(_respec(replace(case, decision_cycles=(cycle, case.decision_cycles[1]))))
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert "mark_coverage_mismatch" in outcome.engine_failure.subject_keys


def _blocked_end_case(*, late_phase):
    case = live_case(weights=("0", "0.5"), bar_times=(150, 270, 299))
    last = replace(_bar(299), phase=TimelinePhase(1_000_001, "late_close")) if late_phase else _bar(299)
    events = (_bar(150), _bar(270), last)
    plans = []
    for bar, event in zip(case.bar_executions, events, strict=True):
        at = event.event_time.epoch_nanoseconds
        if at >= 270:
            bar = replace(bar, liquidity_evidence=BarLiquidityEvidence.create(
                evidence_key="test.blocked", evidence_version=1, market_event=event,
                evaluated_at=event.event_time, approved=False, reason_code="no_liquidity",
                source_hash="sha256:" + "e1" * 32),
                market_state=replace(bar.market_state, evidence_hash=event.event_hash))
        if at == 299:
            accounting = bar.accounting_plan
            at_fill = f.sim(at, TimelinePhase(1_000_002, "fill"), 0)
            at_accounting = f.sim(at, TimelinePhase(1_000_003, "accounting"), 0)
            at_fee = f.sim(at, TimelinePhase(1_000_004, "fee"), 2)
            payload = replace(cast(CashFillAccountingPlan, accounting.position_payload), fill_recorded_at=at_accounting, fee_recorded_at=at_fee)
            accounting = replace(accounting, position_payload=payload, fill_recorded_at=at_accounting,
                                 fee_plan=replace(accounting.fee_plan, fee_recorded_at=at_fee))
            bar = replace(bar, fill_event_at=at_fill, accounting_plan=accounting)
        plans.append(bar)
    reader = InMemoryMarketBundleReader.build(bundle_key="fixture.live-late-end", schema_version=1,
        coverage_start=UtcInstant(0), coverage_end_exclusive=UtcInstant(400), instrument_catalog_hash=canonical_sha256(f.catalog()),
        capabilities=(TARGET_STREAM_CAPABILITY, BAR_CLOSE_CAPABILITY), streams={"targets": case.target_stream.events, "bars.close": events})
    timeline = DeterministicTimeline.open(reader=reader, stream_keys=("bars.close", "targets"), window=case.timeline.window)
    assert isinstance(timeline, DeterministicTimeline)
    return _respec(replace(case, timeline=timeline, bar_executions=tuple(plans)))


def test_live_end_window_cannot_backdate_expiration_before_last_source_phase():
    outcome = _run(_blocked_end_case(late_phase=True))
    assert outcome.result is None and outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == ("live_close_window_overlap",)


def test_unfilled_order_expires_with_used_expiration_and_unused_fill_identities():
    outcome = _run(_blocked_end_case(late_phase=False))
    assert outcome.result is not None, outcome.engine_failure
    assert outcome.result.fills == ()
    assert outcome.result.final_portfolio_snapshot.equity.units == 100_000
    rows = _closure(outcome.result)
    assert rows["order.1.0"].status == rows["order-event.expire.1"].status == "used"
    assert rows["fill.1"].reason == rows["fill.2"].reason == "no_eligible_fill"


def test_live_combined_fill_and_order_fees_close_both_identity_streams():
    outcome = _run(live_case(combined_fees=True))
    assert outcome.result is not None, outcome.engine_failure
    result = outcome.result
    assert result.final_portfolio_snapshot.positions == ()
    assert result.final_portfolio_snapshot.fees.units == 227
    assert result.final_portfolio_snapshot.cash[0].amount.units == 99_673
    assert len(result.fee_assessments) == 4
    rows = _closure(result)
    assert rows["fee.fill.0"].status == rows["fee.fill.1"].status == "used"
    assert rows["fee.fill.2"].status == "unused"


def test_zero_fill_assessment_retains_evidence_without_fabricating_fee_journal():
    case = live_case()
    bars = []
    for bar in case.bar_executions:
        fee = bar.accounting_plan.fee_plan
        rules = fee.final_fee_rule_set
        zero_rules = FinalFeeRuleSet.create(
            market_fee_policy_ref=rules.market_fee_policy_ref, tax_policy_ref=rules.tax_policy_ref,
            account_fee_schedule_ref=rules.account_fee_schedule_ref, assessment_currency=rules.assessment_currency,
            assessment_scale=rules.assessment_scale, minimums=rules.minimums,
            charge_rules=tuple(replace(rule, applicability=FinalFeeApplicability.NOT_APPLICABLE)
                               if rule.basis_type is FeeBasisType.FILL else rule for rule in rules.charge_rules),
        )
        bars.append(replace(bar, accounting_plan=replace(bar.accounting_plan, fee_plan=replace(fee, final_fee_rule_set=zero_rules))))
    outcome = _run(_respec(replace(case, bar_executions=tuple(bars))))
    assert outcome.result is not None, outcome.engine_failure
    assert outcome.result.final_portfolio_snapshot.cash[0].amount.units == 99_900
    assert len(outcome.result.fee_assessments) == 2
    rows = _closure(outcome.result)
    assert rows["fee.0"].status == "used"
    assert rows["journal.fee.0"].reason == rows["journal.fee.1"].reason == "zero_fee"
    assert rows["journal.fee.2"].reason == "no_active_order"


def test_live_engine_rejects_callback_receipts_that_overrun_next_timeline_boundary():
    case = live_case(bar_times=(200, 250, 270))
    first = case.bar_executions[0]
    fee = replace(first.accounting_plan.fee_plan, fee_recorded_at=f.sim(200, TimelinePhase(120, "late_fee"), 2))
    first = replace(first, accounting_plan=replace(first.accounting_plan, fee_plan=fee))
    outcome = _run(_respec(replace(case, bar_executions=(first, *case.bar_executions[1:]))))
    assert outcome.engine_failure is not None
    assert "live_clock_overlap" in outcome.engine_failure.subject_keys


@pytest.mark.parametrize("clock_change", ("utc", "phase", "sequence"))
def test_live_decision_rejects_misbound_snapshot_clock(clock_change):
    case = live_case()
    cycle = case.decision_cycles[0]
    at = cycle.snapshot_plan.projection_at
    if clock_change == "utc":
        at = replace(at, instant=UtcInstant(101))
    elif clock_change == "phase":
        at = replace(at, phase=TimelinePhase(101, "other"))
    else:
        at = replace(at, source_sequence=SourceSequence(2))
    with pytest.raises(ValueError):
        replace(cycle, snapshot_plan=_snapshot(at))


@pytest.mark.parametrize("alteration", ("snapshot_clock", "snapshot_ledger_hash", "artifact_clock", "journal_clock"))
def test_live_dispatch_receipts_bind_actual_engine_clock_and_ledger(alteration):
    class BrokenReceipt(DefaultCashFinancialDispatcher):
        def dispatch_scheduled_event(self, event, state, /):
            outcome = super().dispatch_scheduled_event(event, state)
            if alteration not in {"snapshot_clock", "snapshot_ledger_hash", "artifact_clock"}:
                return outcome
            assert outcome.result is not None and outcome.result.snapshot is not None
            snapshot = outcome.result.snapshot
            if alteration == "snapshot_clock":
                snapshot = replace(snapshot, timestamp_instant=None)
            elif alteration == "snapshot_ledger_hash":
                snapshot = replace(snapshot, journal_state_hash="sha256:" + "d1" * 32)
            artifact = outcome.result.artifacts[0]
            artifact = replace(artifact, payload=snapshot, result_hash=canonical_sha256(snapshot))
            if alteration == "artifact_clock":
                artifact = replace(artifact, occurred_at=replace(artifact.occurred_at, source_sequence=SourceSequence(999)))
            return replace(outcome, result=replace(outcome.result, snapshot=snapshot, artifacts=(artifact,)))

        def book_fill(self, plan, fill, state, /):
            outcome = super().book_fill(plan, fill, state)
            if alteration != "journal_clock":
                return outcome
            assert outcome.result is not None
            entry = outcome.result.journal_entries[0]
            entry = replace(entry, recorded_at=replace(entry.recorded_at, source_sequence=SourceSequence(999)))
            return replace(outcome, result=replace(outcome.result, journal_entries=(entry,)))

    outcome = BrokenReceipt()
    result = DeterministicBarEngine(outcome).run(live_case())
    assert result.result is None and result.engine_failure is not None
    assert "live_dispatch_receipt_mismatch" in result.engine_failure.subject_keys
