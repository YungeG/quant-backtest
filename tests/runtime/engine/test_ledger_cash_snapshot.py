"""Live valuation through the existing Engine, not A-share research evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from crypto_quant_backtest import (
    BAR_OPEN_CAPABILITY,
    TARGET_STREAM_CAPABILITY,
    CashFillAccountingPlan,
    DefaultCashFinancialDispatcher,
    DeterministicBarEngine,
    DeterministicTimeline,
    EngineFailureCode,
    FinancialDispatchFailureCode,
    FinancialStateView,
    LedgerCashSnapshotProjectionPlan,
    ScheduledAccountEvent,
)
from crypto_quant_domain import (
    CurrencyId, InstrumentType, PortfolioSnapshot, PricePurpose, Scale, SourceSequence,
    TimelinePhase, UtcInstant, canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading import CurrencyValuationGraph, PortfolioSnapshotProjector, SnapshotProjectionFailureCode

from tests.runtime.engine._fixtures import (
    MONEY_SCALE,
    USD,
    CashAccountingSemanticPayload,
    bar_event,
    catalog,
    execution_case,
    sim,
    target_event,
    valuation_mark,
)


def _case_with_snapshot(*, at: int = 260, policy_version: int = 2):
    case = execution_case()
    bar = case.bar_executions[0]
    accounting = bar.accounting_plan
    payload = cast(CashFillAccountingPlan, accounting.position_payload)
    policy = replace(payload.cost_basis_policy, policy_version=policy_version)
    accounting = replace(
        accounting,
        position_payload=replace(payload, cost_basis_policy=policy),
        semantic_payload=replace(
            cast(CashAccountingSemanticPayload, accounting.semantic_payload),
            cost_basis_policy=policy,
        ),
    )
    clock = replace(
        bar_event(), event_id=f"engine-ledger-snapshot-{at}",
        event_time=UtcInstant(at), available_time=UtcInstant(at),
    )
    mark = replace(
        valuation_mark(price_units=11_000, resolved_at=UtcInstant(at)),
        available_at_instant=sim(at - 5, clock.timeline_instant.phase, 0),
        resolved_at_instant=clock.timeline_instant,
    )
    authority = LedgerCashSnapshotProjectionPlan(
        resolved_marks=(mark,),
        reporting_currency=USD,
        reporting_scale=MONEY_SCALE,
        instrument_catalog=catalog(),
        projection_at=clock.timeline_instant,
        currency_valuation_graph=CurrencyValuationGraph(UtcInstant(at), PricePurpose.VALUATION, ()),
        notional_quantization=payload.notional_quantization,
    )
    dispatcher = DefaultCashFinancialDispatcher()
    event = ScheduledAccountEvent(
        clock.event_id, clock.timeline_instant, authority.operation_key,
        (dispatcher.spec.snapshot_projection_key,), (), authority, authority,
        (f"snapshot.{clock.event_id}",),
    )
    reader = InMemoryMarketBundleReader.build(
        bundle_key="fixture.ledger-cash-snapshot.v1", schema_version=1,
        coverage_start=UtcInstant(0), coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash=canonical_sha256(catalog()),
        capabilities=(TARGET_STREAM_CAPABILITY, BAR_OPEN_CAPABILITY),
        streams={
            "targets": (target_event(),),
            "bars.open": tuple(sorted((bar_event(), clock), key=lambda value: value.timeline_instant)),
        },
    )
    timeline = DeterministicTimeline.open(
        reader=reader, stream_keys=("bars.open", "targets"), window=case.timeline.window,
    )
    assert isinstance(timeline, DeterministicTimeline)
    return replace(
        case, timeline=timeline, bar_executions=(replace(bar, accounting_plan=accounting),),
        financial_dispatch_plan=replace(
            case.financial_dispatch_plan, scheduled_account_events=(event,),
            expected_artifact_roles=(
                *case.financial_dispatch_plan.expected_artifact_roles, *event.expected_artifact_roles,
            ),
        ),
    )


def test_engine_projects_current_cash_lots_and_fees_without_precomputed_valuations():
    case = _case_with_snapshot()
    outcome = DeterministicBarEngine().run(case)

    assert outcome.result is not None, outcome.engine_failure
    event = case.financial_dispatch_plan.scheduled_account_events[0]
    artifact = next(item for item in outcome.result.financial_artifacts if item.role == event.expected_artifact_roles[0])
    snapshot = artifact.payload
    assert isinstance(snapshot, PortfolioSnapshot)
    assert snapshot.timestamp == UtcInstant(260)
    assert snapshot.timestamp_instant == event.event_at
    assert snapshot.cash[0].amount.units == 47_392
    assert snapshot.positions[0].quantity.units == 5_000
    assert snapshot.fees.units == 53
    assert snapshot.equity.units == 102_392
    assert snapshot.unrealized_pnl.units == 2_445
    assert snapshot.journal_state_hash == outcome.result.final_ledger_state.state_hash
    assert artifact.source_event_id == event.event_id
    assert artifact.occurred_at == event.event_at
    assert artifact.result_hash == canonical_sha256(snapshot)
    authority = cast(LedgerCashSnapshotProjectionPlan, event.payload)
    assert "valuations" not in authority.to_canonical_dict()


def _replace_event(case, event):
    old = case.financial_dispatch_plan.scheduled_account_events[0]
    return replace(
        case,
        financial_dispatch_plan=replace(
            case.financial_dispatch_plan,
            scheduled_account_events=(event,),
            expected_artifact_roles=(
                *(role for role in case.financial_dispatch_plan.expected_artifact_roles if role not in old.expected_artifact_roles),
                *event.expected_artifact_roles,
            ),
        ),
    )


def _replace_authority(case, authority):
    event = case.financial_dispatch_plan.scheduled_account_events[0]
    return _replace_event(case, replace(event, payload=authority, semantic_payload=authority))


def _assert_dispatch_failure(case, subject, code=FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE):
    before = canonical_bytes(case)
    outcome = DeterministicBarEngine().run(case)
    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert outcome.engine_failure.subject_keys == tuple(sorted((code.value, subject)))
    assert canonical_bytes(case) == before


@pytest.mark.parametrize("component", ("phase", "sequence"))
def test_live_snapshot_rejects_same_instant_future_mark_resolution(component):
    case = _case_with_snapshot()
    event = case.financial_dispatch_plan.scheduled_account_events[0]
    authority = cast(LedgerCashSnapshotProjectionPlan, event.payload)
    future = (
        replace(event.event_at, phase=TimelinePhase(1_000_000, "future-resolution"))
        if component == "phase"
        else replace(event.event_at, source_sequence=SourceSequence(event.event_at.source_sequence.value + 1))
    )
    mark = replace(authority.resolved_marks[0], resolved_at_instant=future)
    _assert_dispatch_failure(_replace_authority(case, replace(authority, resolved_marks=(mark,))), "mark_coverage_mismatch")


def test_flat_ledger_does_not_invent_positions_or_valuation_refs():
    case = _case_with_snapshot(at=150)
    outcome = DeterministicBarEngine().run(case)
    assert outcome.result is not None, outcome.engine_failure
    snapshot = next(item.payload for item in outcome.result.financial_artifacts if item.role.startswith("snapshot."))
    assert isinstance(snapshot, PortfolioSnapshot)
    assert snapshot.positions == ()
    assert snapshot.valuation_marks == ()
    assert snapshot.cash[0].amount.units == snapshot.equity.units == 100_000
    assert snapshot.fees.units == snapshot.unrealized_pnl.units == 0
    assert snapshot.journal_state_hash != outcome.result.final_ledger_state.state_hash


@pytest.mark.parametrize("at", (150, 260))
@pytest.mark.parametrize("change", ("missing", "duplicate", "utc_only", "wrong_time", "wrong_purpose"))
def test_missing_or_unusable_mark_authority_fails_even_when_flat(at, change):
    case = _case_with_snapshot(at=at)
    authority = cast(LedgerCashSnapshotProjectionPlan, case.financial_dispatch_plan.scheduled_account_events[0].payload)
    mark = authority.resolved_marks[0]
    if change == "missing":
        marks = ()
    elif change == "duplicate":
        marks = (mark, mark)
    elif change == "utc_only":
        marks = (replace(mark, available_at_instant=None, resolved_at_instant=None),)
    elif change == "wrong_time":
        marks = (valuation_mark(price_units=11_000, resolved_at=UtcInstant(at + 1)),)
    else:
        marks = (replace(mark, price_purpose=PricePurpose.EXECUTION_REFERENCE),)
    _assert_dispatch_failure(_replace_authority(case, replace(authority, resolved_marks=marks)), "mark_coverage_mismatch")


@pytest.mark.parametrize("currency,scale", ((CurrencyId("CNY"), MONEY_SCALE), (USD, Scale(3))))
def test_cash_projection_does_not_guess_currency_conversion_or_rescaling(currency, scale):
    case = _case_with_snapshot()
    authority = cast(LedgerCashSnapshotProjectionPlan, case.financial_dispatch_plan.scheduled_account_events[0].payload)
    authority = replace(
        authority, reporting_currency=currency, reporting_scale=scale,
        notional_quantization=replace(authority.notional_quantization, target_scale=scale),
    )
    _assert_dispatch_failure(_replace_authority(case, authority), "reporting_context_mismatch")


@pytest.mark.parametrize("instrument_type", (None, InstrumentType.LINEAR_PERPETUAL, InstrumentType.INVERSE_PERPETUAL, InstrumentType.OPTION, InstrumentType.FX))
def test_live_cash_projection_requires_authoritative_cash_instrument_definitions(instrument_type):
    case = _case_with_snapshot()
    authority = cast(LedgerCashSnapshotProjectionPlan, case.financial_dispatch_plan.scheduled_account_events[0].payload)
    known = authority.instrument_catalog
    if instrument_type is None:
        known = replace(known, instruments=(), symbol_timelines=())
    else:
        known = replace(known, instruments=(replace(known.instruments[0], instrument_type=instrument_type),))
    _assert_dispatch_failure(
        _replace_authority(case, replace(authority, instrument_catalog=known)),
        "cash_instrument_mismatch",
    )


def test_live_valuation_rejects_legacy_external_lots_instead_of_guessing_cost_basis():
    _assert_dispatch_failure(_case_with_snapshot(policy_version=1), "cash_lot_evidence_mismatch")


@pytest.mark.parametrize("component", ("utc", "phase", "sequence"))
def test_live_snapshot_cannot_read_a_journal_receipt_after_its_boundary(component):
    case = _case_with_snapshot()
    at = case.financial_dispatch_plan.scheduled_account_events[0].event_at
    if component == "utc":
        future = replace(at, instant=UtcInstant(270))
    elif component == "phase":
        future = replace(at, phase=TimelinePhase(1_000_000, "future-fee"))
    else:
        future = replace(at, source_sequence=SourceSequence(at.source_sequence.value + 1))
    bar = case.bar_executions[0]
    accounting = replace(
        bar.accounting_plan,
        fee_plan=replace(bar.accounting_plan.fee_plan, fee_recorded_at=future),
    )
    case = replace(case, bar_executions=(replace(bar, accounting_plan=accounting),))
    _assert_dispatch_failure(case, "journal_after_snapshot_receipt")


@pytest.mark.parametrize("field", ("operation", "component", "semantic", "roles", "identity", "receipt"))
def test_scheduled_snapshot_is_bound_to_its_operation_authority_and_receipt(field):
    case = _case_with_snapshot()
    event = case.financial_dispatch_plan.scheduled_account_events[0]
    if field == "operation":
        event = replace(event, operation_key="unknown.snapshot.v1")
    elif field == "component":
        event = replace(event, component_keys=("unknown.snapshot.component.v1",))
    elif field == "semantic":
        event = replace(event, semantic_payload=case.snapshot_plan)
    elif field == "roles":
        event = replace(event, expected_artifact_roles=("wrong.snapshot",))
    elif field == "identity":
        event = replace(event, identity_bindings=(("invented.snapshot.journal", case.financial_state.journal.entries[0].journal_entry_id),))
    else:
        authority = cast(LedgerCashSnapshotProjectionPlan, event.payload)
        authority = replace(authority, projection_at=replace(event.event_at, source_sequence=SourceSequence(99)))
        event = replace(event, payload=authority, semantic_payload=authority)
    _assert_dispatch_failure(_replace_event(case, event), event.operation_key, FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH)


@pytest.mark.parametrize("price_units,equity,unrealized", ((9_000, 92_392, -7_555), (12_000, 107_392, 7_445)))
def test_projection_uses_the_current_mark_and_gross_ledger_cost_once(price_units, equity, unrealized):
    case = _case_with_snapshot()
    event = case.financial_dispatch_plan.scheduled_account_events[0]
    authority = cast(LedgerCashSnapshotProjectionPlan, event.payload)
    mark = authority.resolved_marks[0]
    authority = replace(authority, resolved_marks=(replace(mark, price=replace(mark.price, units=price_units)),))
    outcome = DeterministicBarEngine().run(_replace_authority(case, authority))
    assert outcome.result is not None, outcome.engine_failure
    snapshot = next(item.payload for item in outcome.result.financial_artifacts if item.role == event.expected_artifact_roles[0])
    assert isinstance(snapshot, PortfolioSnapshot)
    assert snapshot.equity.units == equity
    assert snapshot.unrealized_pnl.units == unrealized
    assert snapshot.fees.units == 53


def test_snapshot_evidence_and_batching_are_deterministic_and_reusable():
    case = _case_with_snapshot()
    before = canonical_bytes(case)
    first = DeterministicBarEngine().run(case)
    second = DeterministicBarEngine().run(replace(case, timeline_batch_size=10))
    assert first.result is not None, first.engine_failure
    assert second.result is not None, second.engine_failure
    assert canonical_sha256(first.result) == canonical_sha256(second.result)
    assert canonical_bytes(case) == before


def _captured_receipt(case):
    observed: list[FinancialStateView] = []

    class CaptureReceipt(DefaultCashFinancialDispatcher):
        def dispatch_scheduled_event(self, event, state_view, /):
            observed.append(state_view)
            return super().dispatch_scheduled_event(event, state_view)

    outcome = DeterministicBarEngine(CaptureReceipt()).run(case)
    assert outcome.result is not None, outcome.engine_failure
    return outcome.result, observed[0]


def test_final_dispatch_port_reuses_live_projection_without_legacy_amount_inputs():
    case = _case_with_snapshot()
    _, receipt = _captured_receipt(case)
    authority = cast(LedgerCashSnapshotProjectionPlan, case.financial_dispatch_plan.scheduled_account_events[0].payload)
    final_at = sim(300, TimelinePhase(1_000_000, "finalize"), 0)
    mark = replace(
        valuation_mark(price_units=11_000, resolved_at=final_at.instant),
        available_at_instant=sim(295, final_at.phase, 0),
        resolved_at_instant=final_at,
    )
    authority = replace(
        authority, resolved_marks=(mark,), projection_at=final_at,
        currency_valuation_graph=CurrencyValuationGraph(final_at.instant, PricePurpose.VALUATION, ()),
    )
    plan = replace(case.financial_dispatch_plan, final_snapshot_payload=authority)
    projected = DefaultCashFinancialDispatcher().project_final_snapshot(plan, receipt)
    assert projected.result is not None, projected.failure
    assert projected.result.snapshot is not None
    assert projected.result.snapshot.timestamp == final_at.instant
    assert projected.result.snapshot.timestamp_instant == final_at
    assert projected.result.snapshot.equity.units == 102_392
    assert projected.result.snapshot.journal_state_hash == receipt.ledger_state.state_hash
    assert projected.result.journal_entries == ()
    assert projected.result.artifacts[0].role == "final_snapshot"
    assert projected.result.artifacts[0].occurred_at == final_at


@pytest.mark.parametrize("net_long", (True, False))
def test_cash_projector_rejects_short_lots_even_if_aggregate_is_long(net_long):
    case = _case_with_snapshot()
    result, _ = _captured_receipt(case)
    ledger = result.final_ledger_state
    position = ledger.position_balances[0]
    lot = position.lots[0]
    if net_long:
        lots = (
            replace(lot, quantity=replace(lot.quantity, units=6_000)),
            replace(lot, lot_id=lot.lot_id + ".short", quantity=replace(lot.quantity, units=-1_000)),
        )
        position = replace(position, lots=lots)
    else:
        quantity = replace(position.quantity, units=-5_000)
        position = replace(position, quantity=quantity, lots=(replace(lot, quantity=quantity),))
    # These are domain-valid mixed/short books, but unsupported cash valuation inputs.
    ledger = replace(ledger, position_balances=(position,))
    authority = cast(LedgerCashSnapshotProjectionPlan, case.financial_dispatch_plan.scheduled_account_events[0].payload)
    projection = PortfolioSnapshotProjector().project_cash_ledger(
        ledger_state=ledger, resolved_marks=authority.resolved_marks,
        reporting_currency=authority.reporting_currency,
        reporting_scale=authority.reporting_scale,
        projection_at=authority.projection_at,
        instrument_catalog=authority.instrument_catalog,
        currency_valuation_graph=authority.currency_valuation_graph,
        notional_quantization=authority.notional_quantization,
    )
    assert projection.snapshot is None
    assert projection.failure is not None
    assert projection.failure.code is SnapshotProjectionFailureCode.CASH_LOT_EVIDENCE_MISMATCH


def test_direct_dispatch_rejects_a_newer_journal_paired_with_a_stale_ledger():
    result, before_fill = _captured_receipt(_case_with_snapshot(at=150))
    stale = replace(before_fill, journal=result.final_journal)
    event = _case_with_snapshot().financial_dispatch_plan.scheduled_account_events[0]
    # All receipts are before 260, but the ledger still describes the initial prefix.
    assert all(entry.recorded_at <= event.event_at for entry in stale.journal.entries)
    outcome = DefaultCashFinancialDispatcher().dispatch_scheduled_event(event, stale)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE
    assert outcome.failure.subject_ids == ("journal_ledger_cursor_mismatch",)
