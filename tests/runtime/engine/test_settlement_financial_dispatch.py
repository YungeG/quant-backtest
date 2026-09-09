"""Generic Engine settlement wiring, not source-backed A-share research evidence."""

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
    FinancialDispatchOutcome,
    FinancialDispatchResult,
    FinancialStateView,
    ScheduledAccountEvent,
    SettlementFinancialDispatchResult,
)
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Quantity,
    Scale,
    SettlementObligation,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading import (
    AccountSettlementObligation,
    AvailabilityProjection,
    SettlementBook,
    SettlementEvent,
    SettlementEventType,
)

from tests.runtime.engine._fixtures import (
    ACCOUNT,
    BAR_EVENT_ID,
    POSITION_KEY,
    CashAccountingSemanticPayload,
    bar_event,
    catalog,
    empty_settlement_rules,
    execution_case,
    sim,
    target_event,
)


class _DelayedSettlementDispatcher(DefaultCashFinancialDispatcher):
    """Test-only port implementation; existing cash accounting remains authoritative."""

    def __init__(self):
        super().__init__()
        self.final_view: FinancialStateView | None = None
        self.before_apply: FinancialStateView | None = None
        self._spec = replace(
            self.spec,
            dispatcher_key="test.delayed-settlement.v1",
            config_hash=canonical_sha256({"test_settlement_due": 250}),
        )

    def book_fill(self, plan, fill, state_view, /):
        outcome = super().book_fill(plan, fill, state_view)
        base = outcome.result
        assert base is not None
        book = state_view.settlement_book
        assert book is not None
        obligation_id = DomainId(DomainIdKind.SETTLEMENT, "stl_" + "6" * 64)
        obligation = AccountSettlementObligation(
            SettlementObligation(
                obligation_id,
                fill.fill_id,
                fill.execution_time,
                UtcInstant(250),
                POSITION_KEY.instrument_id,
                fill.quantity,
                None,
                None,
            ),
            POSITION_KEY,
        )
        recorded = SettlementEvent(
            "test.settlement.recorded",
            obligation_id,
            SettlementEventType.OBLIGATION_RECORDED,
            sim(200, TimelinePhase(90, "accounting"), 1),
            fill.fill_id.value,
            canonical_sha256(fill),
        )
        after = book.append(obligations=(obligation,), events=(recorded,))
        result = SettlementFinancialDispatchResult(
            base.dispatcher_spec,
            base.source_event_id,
            base.journal_entries,
            base.position_lot_books,
            base.artifacts,
            settlement_obligations=(obligation,),
            settlement_events=(recorded,),
            prior_settlement_book_hash=book.book_hash,
            settlement_book_hash=after.book_hash,
        )
        return replace(outcome, result=result)

    def dispatch_scheduled_event(self, event, state_view, /):
        self.before_apply = state_view
        book = state_view.settlement_book
        assert book is not None
        recorded = book.events[0]
        applied = SettlementEvent(
            "test.settlement.applied",
            recorded.settlement_obligation_id,
            SettlementEventType.SETTLEMENT_APPLIED,
            event.event_at,
            recorded.event_id,
            canonical_sha256(event),
        )
        after = book.append(events=(applied,))
        return FinancialDispatchOutcome(
            self.spec,
            canonical_sha256(event),
            result=SettlementFinancialDispatchResult(
                self.spec, event.event_id, (), state_view.position_lot_books, (),
                settlement_obligations=(),
                settlement_events=(applied,),
                prior_settlement_book_hash=book.book_hash,
                settlement_book_hash=after.book_hash,
            ),
        )

    def project_final_snapshot(self, plan, state_view, /):
        self.final_view = state_view
        return super().project_final_snapshot(plan, state_view)


def _case(dispatcher):
    case = execution_case()
    return replace(
        case,
        financial_dispatch_plan=replace(
            case.financial_dispatch_plan,
            dispatcher_spec=dispatcher.spec,
            expected_artifact_roles=(
                *case.financial_dispatch_plan.expected_artifact_roles,
                f"settlement.{BAR_EVENT_ID}",
            ),
        ),
    )


def _scheduled_case(dispatcher):
    case = _case(dispatcher)
    clock = replace(
        bar_event(), event_id="engine-settlement-260",
        event_time=UtcInstant(260), available_time=UtcInstant(260),
    )
    event = ScheduledAccountEvent(
        clock.event_id, clock.timeline_instant, "test.apply-settlement.v1",
        (dispatcher.spec.dispatcher_key,), (), empty_settlement_rules(),
        empty_settlement_rules(), (f"settlement.{clock.event_id}",),
    )
    reader = InMemoryMarketBundleReader.build(
        bundle_key="fixture.delayed-settlement.v1", schema_version=1,
        coverage_start=UtcInstant(0), coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash=canonical_sha256(catalog()),
        capabilities=(TARGET_STREAM_CAPABILITY, BAR_OPEN_CAPABILITY),
        streams={"targets": (target_event(),), "bars.open": (bar_event(), clock)},
    )
    timeline = DeterministicTimeline.open(
        reader=reader, stream_keys=("bars.open", "targets"), window=case.timeline.window,
    )
    assert isinstance(timeline, DeterministicTimeline)
    return replace(
        case, timeline=timeline,
        financial_dispatch_plan=replace(
            case.financial_dispatch_plan, scheduled_account_events=(event,),
            expected_artifact_roles=(
                *case.financial_dispatch_plan.expected_artifact_roles,
                f"settlement.{clock.event_id}",
            ),
        ),
    )


def _sellable(view):
    assert view is not None and view.settlement_book is not None
    return AvailabilityProjection().project(
        view.ledger_state, view.settlement_book.project(), view.reservation_state,
        empty_settlement_rules(),
    ).positions[0].sellable.units


def test_engine_records_actual_fill_as_pending_with_replayable_settlement_evidence():
    dispatcher = _DelayedSettlementDispatcher()
    outcome = DeterministicBarEngine(dispatcher).run(_case(dispatcher))

    assert outcome.result is not None, outcome.engine_failure
    view = dispatcher.final_view
    assert view is not None
    book = view.settlement_book
    assert book is not None
    assert len(book.obligations) == 1
    assert len(book.events) == 1
    assert book.obligations[0].obligation.source_fill_id == outcome.result.fills[0].fill_id
    availability = AvailabilityProjection().project(
        view.ledger_state, book.project(), view.reservation_state, empty_settlement_rules()
    )
    assert availability.positions[0].total.units == 5_000
    assert availability.positions[0].sellable.units == 0

    artifact = next(
        item for item in outcome.result.financial_artifacts
        if item.role == f"settlement.{BAR_EVENT_ID}"
    )
    transition = artifact.payload
    assert isinstance(transition, SettlementFinancialDispatchResult)
    assert transition.prior_settlement_book_hash == SettlementBook(ACCOUNT).book_hash
    replayed = SettlementBook(ACCOUNT).append(
        obligations=transition.settlement_obligations,
        events=transition.settlement_events,
    )
    assert replayed == book
    assert transition.settlement_book_hash == replayed.book_hash
    assert artifact.result_hash == canonical_sha256(transition)
    assert artifact.occurred_at == sim(210, TimelinePhase(90, "accounting"), 1)


@pytest.mark.parametrize("batch_size", (1, 10))
def test_scheduled_apply_releases_only_the_current_recorded_obligation(batch_size):
    dispatcher = _DelayedSettlementDispatcher()
    case = replace(_scheduled_case(dispatcher), timeline_batch_size=batch_size)
    outcome = DeterministicBarEngine(dispatcher).run(case)

    assert outcome.result is not None, outcome.engine_failure
    assert _sellable(dispatcher.before_apply) == 0
    assert _sellable(dispatcher.final_view) == 5_000
    assert dispatcher.before_apply is not None
    assert dispatcher.before_apply.settlement_book is not None
    assert len(dispatcher.before_apply.settlement_book.events) == 1
    replay = SettlementBook(ACCOUNT)
    transitions = sorted(
        (artifact for artifact in outcome.result.financial_artifacts
         if isinstance(artifact.payload, SettlementFinancialDispatchResult)),
        key=lambda artifact: artifact.occurred_at,
    )
    assert len(transitions) == 2
    for artifact in transitions:
        transition = artifact.payload
        assert isinstance(transition, SettlementFinancialDispatchResult)
        assert transition.prior_settlement_book_hash == replay.book_hash
        replay = replay.append(
            obligations=transition.settlement_obligations,
            events=transition.settlement_events,
        )
        assert transition.settlement_book_hash == replay.book_hash
    assert not replay.project().pending_obligations
    assert len(replay.project().applied_obligations) == 1
    rerun = DeterministicBarEngine(_DelayedSettlementDispatcher()).run(case)
    assert rerun.result is not None
    assert rerun.result.result_hash == outcome.result.result_hash


class _TamperingDispatcher(_DelayedSettlementDispatcher):
    def __init__(self, tamper_fill=None, tamper_scheduled=None):
        super().__init__()
        self.tamper_fill = tamper_fill
        self.tamper_scheduled = tamper_scheduled

    def book_fill(self, plan, fill, state_view, /):
        outcome = super().book_fill(plan, fill, state_view)
        if self.tamper_fill is not None:
            return replace(outcome, result=self.tamper_fill(outcome.result, state_view))
        return outcome

    def dispatch_scheduled_event(self, event, state_view, /):
        outcome = super().dispatch_scheduled_event(event, state_view)
        if self.tamper_scheduled is not None:
            return replace(outcome, result=self.tamper_scheduled(outcome.result, state_view))
        return outcome


def _rehash_delta(result, view):
    assert view.settlement_book is not None
    after = view.settlement_book.append(
        obligations=result.settlement_obligations, events=result.settlement_events,
    )
    return replace(result, settlement_book_hash=after.book_hash)


def _wrong_fill(result, view):
    wrong = DomainId(DomainIdKind.FILL, "fil_" + "9" * 64)
    registered = result.settlement_obligations[0]
    result = replace(
        result,
        settlement_obligations=(replace(
            registered, obligation=replace(registered.obligation, source_fill_id=wrong),
        ),),
        settlement_events=(replace(result.settlement_events[0], causation_id=wrong.value),),
    )
    return _rehash_delta(result, view)


def _wrong_trade_time(result, view):
    registered = result.settlement_obligations[0]
    result = replace(
        result,
        settlement_obligations=(replace(
            registered, obligation=replace(registered.obligation, trade_time=UtcInstant(201)),
        ),),
        settlement_events=(replace(
            result.settlement_events[0], occurred_at=sim(201, TimelinePhase(90, "accounting"), 1),
        ),),
    )
    return _rehash_delta(result, view)


def _before_recorded_fill(result, view):
    result = replace(result, settlement_events=(replace(
        result.settlement_events[0], occurred_at=sim(200, TimelinePhase(60, "bar_open"), 1),
    ),))
    return _rehash_delta(result, view)


def _future_applied(result, view):
    recorded = result.settlement_events[0]
    applied = replace(
        recorded, event_id="test.future.applied",
        event_type=SettlementEventType.SETTLEMENT_APPLIED,
        occurred_at=sim(250, TimelinePhase(90, "accounting"), 1),
        causation_id=recorded.event_id,
    )
    return _rehash_delta(replace(result, settlement_events=(recorded, applied)), view)


def _conflicting_event(result, view):
    recorded = result.settlement_events[0]
    return replace(result, settlement_events=(
        recorded, replace(recorded, occurred_at=sim(200, TimelinePhase(91, "conflict"), 1)),
    ))


def _wrong_scale(result, view):
    registered = result.settlement_obligations[0]
    return _rehash_delta(replace(result, settlement_obligations=(replace(
        registered, obligation=replace(
            registered.obligation,
            quantity=Quantity(50_000, Scale(4), str(POSITION_KEY.instrument_id)),
        ),
    ),)), view)


def _future_journal(result, view):
    return replace(result, journal_entries=tuple(
        replace(entry, recorded_at=sim(999, TimelinePhase(90, "accounting"), 1))
        for entry in result.journal_entries
    ))


def _future_artifact(result, view):
    artifact = result.artifacts[0]
    return replace(result, artifacts=(replace(
        artifact, occurred_at=sim(999, TimelinePhase(90, "accounting"), 1),
    ),))


def _assert_dispatch_failure(dispatcher, case, code):
    before = canonical_bytes(case)
    outcome = DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert outcome.engine_failure.subject_keys == (code.value,)
    assert dispatcher.final_view is None
    assert canonical_bytes(case) == before
    return outcome


@pytest.mark.parametrize("tamper", (
    _wrong_fill, _wrong_trade_time, _before_recorded_fill, _future_applied,
    _conflicting_event, _future_artifact, _future_journal,
    lambda result, view: replace(result, source_event_id="not-the-fill-dispatch"),
    lambda result, view: replace(result, prior_settlement_book_hash=canonical_sha256("stale")),
    lambda result, view: replace(result, settlement_book_hash=canonical_sha256("wrong")),
))
def test_invalid_fill_delta_has_no_success_or_partial_public_result(tamper):
    dispatcher = _TamperingDispatcher(tamper_fill=tamper)
    case = _case(dispatcher)
    _assert_dispatch_failure(
        dispatcher, case, FinancialDispatchFailureCode.SETTLEMENT_TRANSITION_FAILURE,
    )
    # The public input is reusable after rejection; no partial accounting is published.
    dispatcher.tamper_fill = None
    retry = DeterministicBarEngine(dispatcher).run(case)
    assert retry.result is not None
    assert len(retry.result.final_journal.entries) == 3
    assert _sellable(dispatcher.final_view) == 0


def test_resource_projection_failure_is_structured_and_publishes_no_partial_result():
    dispatcher = _TamperingDispatcher(tamper_fill=_wrong_scale)
    _assert_dispatch_failure(
        dispatcher, _case(dispatcher), FinancialDispatchFailureCode.RESOURCE_PROJECTION_FAILURE,
    )


def test_dispatcher_cannot_impersonate_the_engine_owned_settlement_artifact():
    def tamper(result, view):
        return replace(result, artifacts=(replace(
            result.artifacts[0], role=f"settlement.{result.source_event_id}",
        ),))

    dispatcher = _TamperingDispatcher(tamper_fill=tamper)
    _assert_dispatch_failure(
        dispatcher, _case(dispatcher),
        FinancialDispatchFailureCode.ARTIFACT_COVERAGE_MISMATCH,
    )


def _future_scheduled_phase(result, view):
    applied = result.settlement_events[0]
    return _rehash_delta(replace(result, settlement_events=(replace(
        applied, occurred_at=replace(
            applied.occurred_at, phase=TimelinePhase(61, "future_phase"),
        ),
    ),)), view)


def _scheduled_record_injection(result, view):
    book = view.settlement_book
    assert book is not None
    return replace(
        result, settlement_obligations=book.obligations,
        settlement_events=book.events, settlement_book_hash=book.book_hash,
    )


def _future_scheduled_snapshot(result, view):
    return replace(result, snapshot=replace(
        execution_case().financial_state.initial_snapshot, timestamp=UtcInstant(300),
    ))


@pytest.mark.parametrize("tamper", (
    _future_scheduled_phase, _scheduled_record_injection, _future_scheduled_snapshot,
))
def test_scheduled_delta_cannot_create_fill_or_future_state(tamper):
    dispatcher = _TamperingDispatcher(tamper_scheduled=tamper)
    _assert_dispatch_failure(
        dispatcher, _scheduled_case(dispatcher),
        FinancialDispatchFailureCode.SETTLEMENT_TRANSITION_FAILURE,
    )
    assert _sellable(dispatcher.before_apply) == 0


class _SettlementFromWrongHook(_DelayedSettlementDispatcher):
    def __init__(self, hook):
        super().__init__()
        self.hook = hook

    def _smuggle(self, outcome, view):
        base = outcome.result
        assert base is not None
        book = view.settlement_book
        assert book is not None
        return replace(outcome, result=SettlementFinancialDispatchResult(
            base.dispatcher_spec, base.source_event_id, base.journal_entries,
            base.position_lot_books, base.artifacts, base.snapshot,
            settlement_obligations=(), settlement_events=(book.events[-1],),
            prior_settlement_book_hash=book.book_hash, settlement_book_hash=book.book_hash,
        ))

    def book_fee(self, plan, fill, assessment, state_view, /):
        outcome = super().book_fee(plan, fill, assessment, state_view)
        return self._smuggle(outcome, state_view) if self.hook == "fee" else outcome

    def project_final_snapshot(self, plan, state_view, /):
        outcome = super().project_final_snapshot(plan, state_view)
        return self._smuggle(outcome, state_view) if self.hook == "final" else outcome


def _v2_case(dispatcher):
    case = _case(dispatcher)
    bar = case.bar_executions[0]
    plan = bar.accounting_plan
    payload = cast(CashFillAccountingPlan, plan.position_payload)
    policy = replace(payload.cost_basis_policy, policy_version=2)
    plan = replace(
        plan,
        position_payload=replace(payload, cost_basis_policy=policy),
        semantic_payload=replace(
            cast(CashAccountingSemanticPayload, plan.semantic_payload),
            cost_basis_policy=policy,
        ),
    )
    return replace(case, bar_executions=(replace(bar, accounting_plan=plan),))


@pytest.mark.parametrize("hook", ("fee", "final"))
def test_fee_and_final_snapshot_hooks_cannot_smuggle_settlement_mutations(hook):
    dispatcher = _SettlementFromWrongHook(hook)
    outcome = DeterministicBarEngine(dispatcher).run(_v2_case(dispatcher))
    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.subject_keys == (
        FinancialDispatchFailureCode.SETTLEMENT_TRANSITION_FAILURE.value,
    )


def test_settlement_preserves_v2_ledger_authoritative_lots_and_fees():
    dispatcher = _DelayedSettlementDispatcher()
    outcome = DeterministicBarEngine(dispatcher).run(_v2_case(dispatcher))
    assert outcome.result is not None, outcome.engine_failure
    lots = outcome.result.final_ledger_state.position_balances[0].lots
    assert len(lots) == 1
    assert tuple(fee.units for fee in lots[0].allocated_fees) == (53,)
    assert _sellable(dispatcher.final_view) == 0


@pytest.fixture(scope="module")
def recorded_transition():
    dispatcher = _DelayedSettlementDispatcher()
    outcome = DeterministicBarEngine(dispatcher).run(_case(dispatcher))
    assert outcome.result is not None
    return next(
        artifact.payload for artifact in outcome.result.financial_artifacts
        if isinstance(artifact.payload, SettlementFinancialDispatchResult)
    )


@pytest.mark.parametrize("changes,error", (
    ({"settlement_obligations": []}, TypeError),
    ({"settlement_obligations": ("not-an-obligation",)}, TypeError),
    ({"settlement_events": []}, TypeError),
    ({"settlement_events": ("not-an-event",)}, TypeError),
    ({"settlement_events": ()}, ValueError),
    ({"prior_settlement_book_hash": "not-a-hash"}, ValueError),
    ({"settlement_book_hash": "not-a-hash"}, ValueError),
))
def test_settlement_result_rejects_invalid_delta_contract(recorded_transition, changes, error):
    with pytest.raises(error):
        replace(recorded_transition, **changes)


def test_legacy_financial_result_bytes_and_five_positional_state_view_are_preserved():
    dispatcher = _DelayedSettlementDispatcher()
    outcome = DeterministicBarEngine(dispatcher).run(_case(dispatcher))
    assert outcome.result is not None
    view = dispatcher.final_view
    assert view is not None
    legacy = FinancialStateView(
        view.journal, view.ledger_state, view.reservation_state,
        view.position_lot_books, view.artifacts,
    )
    assert legacy.settlement_book is None
    result = FinancialDispatchResult(dispatcher.spec, "test.legacy", (), (), ())
    assert canonical_bytes(result) == canonical_bytes({
        "type": "financial_dispatch_result", "schema_version": 1,
        "dispatcher_spec": dispatcher.spec, "source_event_id": "test.legacy",
        "journal_entries": (), "position_lot_books": (), "artifacts": (), "snapshot": None,
    })
    with pytest.raises(TypeError, match="settlement_book"):
        replace(legacy, settlement_book="not-a-book")


def _forged_receipt(result, view):
    return _rehash_delta(replace(result, settlement_events=tuple(
        replace(event, source_evidence_hash=canonical_sha256("unrelated receipt"))
        for event in result.settlement_events
    )), view)


@pytest.mark.parametrize("scheduled", (False, True))
def test_settlement_event_receipt_hash_is_bound_to_actual_dispatch_input(scheduled):
    dispatcher = _TamperingDispatcher(**{
        "tamper_scheduled" if scheduled else "tamper_fill": _forged_receipt,
    })
    case = _scheduled_case(dispatcher) if scheduled else _case(dispatcher)
    _assert_dispatch_failure(
        dispatcher, case, FinancialDispatchFailureCode.SETTLEMENT_TRANSITION_FAILURE,
    )


@pytest.mark.parametrize("backdated", (
    sim(250, TimelinePhase(60, "bar_open"), 2),
    sim(260, TimelinePhase(59, "earlier_phase"), 2),
))
def test_scheduled_application_cannot_backdate_the_availability_change(backdated):
    def tamper(result, view):
        return _rehash_delta(replace(result, settlement_events=(replace(
            result.settlement_events[0], occurred_at=backdated,
        ),)), view)

    dispatcher = _TamperingDispatcher(tamper_scheduled=tamper)
    _assert_dispatch_failure(
        dispatcher, _scheduled_case(dispatcher),
        FinancialDispatchFailureCode.SETTLEMENT_TRANSITION_FAILURE,
    )
