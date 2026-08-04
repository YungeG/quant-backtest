from __future__ import annotations

from dataclasses import replace

from crypto_quant_backtest import (
    DeterministicTimeline,
    RunEndEvidence,
    TimelineWindow,
)
from crypto_quant_domain import UtcInstant, canonical_sha256
from crypto_quant_trading import (
    ActiveOrderReservation,
    FeeAssessmentBasisEvidence,
    OrderReservationCursor,
    ReservationCommitment,
    ResourceReservationState,
    SettlementBook,
)
from tests.kernel.integration.test_foundation_financial_journey import (
    build_financial_evidence,
    project_snapshot,
)
from tests.kernel.integration.test_order_acceptance_journey import run_journey
from tests.kernel.settlement._fixtures import (
    CASH_KEY,
    recorded_event,
    registered_obligation,
)
from tests.runtime.timeline._fixtures import timeline_reader


BOUNDARY = UtcInstant(300)


def final_snapshot():
    _, ledger, valuations, mark, graph_hash = build_financial_evidence()
    return replace(
        project_snapshot(ledger, valuations, mark, graph_hash),
        timestamp=BOUNDARY,
    )


def accepted_stream():
    return run_journey()["accepted_stream"]


def completed_timeline():
    reader = timeline_reader()
    window = TimelineWindow(UtcInstant(0), UtcInstant(100), BOUNDARY)
    timeline = DeterministicTimeline.open(
        reader=reader,
        stream_keys=("bars", "universe", "corporate_actions"),
        window=window,
    )
    assert isinstance(timeline, DeterministicTimeline)
    cursor = timeline.open_cursor(batch_size=2)
    while not cursor.window_complete:
        outcome = timeline.read_batch(cursor)
        assert outcome.batch is not None
        cursor = outcome.batch.next_cursor
    return window, cursor


def reservation_state() -> ResourceReservationState:
    stream = accepted_stream()
    assert stream.state is not None
    commitment = ReservationCommitment(order_capacity_units=1)
    active = ActiveOrderReservation(
        account_id=stream.order.account_id,
        order_id=stream.order.order_id,
        last_update_event_id=stream.records[-1].event.event_id,
        remaining_quantity=stream.state.remaining_quantity,
        commitment=commitment,
        source_proposal_hash=canonical_sha256({"proposal": "run-end-fixture"}),
    )
    cursor = OrderReservationCursor(
        order_id=stream.order.order_id,
        event_count=stream.event_count,
        stream_hash=stream.stream_hash,
        evidence_prefix_hash=canonical_sha256({"schedule": "run-end-fixture"}),
    )
    return ResourceReservationState(
        account_id=stream.order.account_id,
        cursors=(cursor,),
        active_reservations=(active,),
        totals=commitment,
    )


def settlement_state():
    obligation = registered_obligation(
        "a", key=CASH_KEY, units=500, settlement_time=400
    )
    event = recorded_event(obligation, "b", sequence=1)
    return SettlementBook.from_events(
        account_id=obligation.account_id,
        obligations=(obligation,),
        events=(event,),
    ).project()


def pending_fee_basis() -> FeeAssessmentBasisEvidence:
    return FeeAssessmentBasisEvidence.for_order(accepted_stream())


def run_end_evidence(
    *,
    order_streams=None,
    reservations=None,
    snapshot=None,
    timeline_cursor=None,
) -> RunEndEvidence:
    window, cursor = completed_timeline()
    return RunEndEvidence(
        timeline_window=window,
        timeline_cursor=cursor if timeline_cursor is None else timeline_cursor,
        final_snapshot=final_snapshot() if snapshot is None else snapshot,
        order_streams=(accepted_stream(),) if order_streams is None else order_streams,
        reservation_state=(
            reservation_state() if reservations is None else reservations
        ),
        settlement_state=settlement_state(),
        pending_fee_assessments=(pending_fee_basis(),),
    )
