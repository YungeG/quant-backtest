from __future__ import annotations

from dataclasses import replace

from crypto_quant_backtest import (
    CloseoutPolicy,
    EngineTermination,
    EngineTerminationCode,
    MarkToMarketCloseoutPolicy,
    RunEndCloseoutDecision,
    RunEndCloseoutFailure,
    RunEndCloseoutMode,
    RunEndCloseoutRequest,
    RunEndCloseoutStatus,
    RunEndCoordinator,
    RunEndReport,
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortSpec,
    SimulationPortType,
)
from crypto_quant_domain import (
    OrderEvent,
    OrderEventType,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import OrderEventRecord
from tests.runtime.run_end._fixtures import BOUNDARY, accepted_stream, run_end_evidence


class LiquidatePolicy:
    def __init__(self, *, completed: bool = True) -> None:
        self.completed = completed
        self.component_ref = SimulationComponentRef(
            SimulationPortType.CLOSEOUT_POLICY,
            "liquidate_before_end.test.v1",
            1,
            canonical_sha256({"policy": "liquidate_before_end.test.v1"}),
        )

    def spec(self) -> SimulationPortSpec:
        return SimulationPortSpec(
            self.component_ref,
            (),
            MarkToMarketCloseoutPolicy().spec().applicability,
        )

    def resolve_closeout(
        self, request: RunEndCloseoutRequest, /
    ) -> SimulationPortOutcome[RunEndCloseoutDecision, RunEndCloseoutFailure]:
        decision = RunEndCloseoutDecision(
            mode=RunEndCloseoutMode.LIQUIDATE_BEFORE_END,
            status=(
                RunEndCloseoutStatus.LIQUIDATION_COMPLETED
                if self.completed
                else RunEndCloseoutStatus.LIQUIDATION_INCOMPLETE
            ),
            completed_at=request.trading_end_exclusive,
            completion_evidence_hashes=(
                canonical_sha256({"full_chain": "complete"}),
            )
            if self.completed
            else (),
        )
        return SimulationPortOutcome.for_result(self.component_ref, request, decision)


class MismatchedOutcomePolicy(LiquidatePolicy):
    def resolve_closeout(
        self, request: RunEndCloseoutRequest, /
    ) -> SimulationPortOutcome[RunEndCloseoutDecision, RunEndCloseoutFailure]:
        other_component = SimulationComponentRef(
            SimulationPortType.CLOSEOUT_POLICY,
            "different_closeout.test.v1",
            1,
            canonical_sha256({"policy": "different_closeout.test.v1"}),
        )
        return SimulationPortOutcome.for_result(
            other_component,
            request,
            RunEndCloseoutDecision(
                mode=RunEndCloseoutMode.LIQUIDATE_BEFORE_END,
                status=RunEndCloseoutStatus.LIQUIDATION_COMPLETED,
                completed_at=request.trading_end_exclusive,
                completion_evidence_hashes=(
                    canonical_sha256({"full_chain": "complete"}),
                ),
            ),
        )


class FailingPolicy:
    component_ref = SimulationComponentRef(
        SimulationPortType.CLOSEOUT_POLICY,
        "failing_closeout.test.v1",
        1,
        canonical_sha256({"policy": "failing_closeout.test.v1"}),
    )

    def spec(self) -> SimulationPortSpec:
        return SimulationPortSpec(
            self.component_ref,
            (),
            MarkToMarketCloseoutPolicy().spec().applicability,
        )

    def resolve_closeout(
        self, request: RunEndCloseoutRequest, /
    ) -> SimulationPortOutcome[RunEndCloseoutDecision, RunEndCloseoutFailure]:
        return SimulationPortOutcome.for_failure(
            self.component_ref,
            request,
            RunEndCloseoutFailure("closeout_unavailable", "account:primary"),
        )


def test_mark_to_market_preserves_positions_and_reports_run_end_evidence() -> None:
    evidence = run_end_evidence()
    policy: CloseoutPolicy[
        RunEndCloseoutRequest, RunEndCloseoutDecision, RunEndCloseoutFailure
    ] = MarkToMarketCloseoutPolicy()
    before_stream_hash = evidence.order_streams[0].stream_hash

    outcome = RunEndCoordinator().coordinate(evidence, policy)

    assert outcome.termination is None
    assert isinstance(outcome.report, RunEndReport)
    report = outcome.report
    assert report.closeout_status is RunEndCloseoutStatus.POSITIONS_PRESERVED
    assert report.open_positions == evidence.final_snapshot.positions
    assert len(report.terminated_orders) == 1
    assert report.terminated_orders[0].order_id == evidence.order_streams[0].order.order_id
    assert len(report.released_reservations) == 1
    assert report.released_reservations[0].order_id == report.terminated_orders[0].order_id
    assert report.pending_settlements == evidence.settlement_state.pending_obligations
    assert report.pending_fee_assessments[0].basis_hash == evidence.pending_fee_assessments[0].basis_hash
    assert report.last_valuation_mark_ids == tuple(
        sorted(mark.mark_id for mark in evidence.final_snapshot.valuation_marks)
    )
    assert evidence.order_streams[0].stream_hash == before_stream_hash
    assert all(record.fill is None for record in evidence.order_streams[0].records)


def test_input_order_does_not_change_run_end_report() -> None:
    evidence = run_end_evidence()
    policy = MarkToMarketCloseoutPolicy()

    left = RunEndCoordinator().coordinate(evidence, policy)
    right = RunEndCoordinator().coordinate(
        replace(
            evidence,
            order_streams=tuple(reversed(evidence.order_streams)),
            pending_fee_assessments=tuple(
                reversed(evidence.pending_fee_assessments)
            ),
        ),
        policy,
    )

    assert left.report is not None and right.report is not None
    assert left.report == right.report
    assert left.report.report_hash == right.report.report_hash


def test_incomplete_timeline_or_boundary_event_terminates_before_policy() -> None:
    evidence = run_end_evidence()
    incomplete = replace(
        evidence,
        timeline_cursor=replace(evidence.timeline_cursor, window_complete=False),
    )
    incomplete_outcome = RunEndCoordinator().coordinate(
        incomplete, MarkToMarketCloseoutPolicy()
    )

    stream = accepted_stream()
    last = stream.records[-1].event
    at_boundary = stream.append(
        OrderEventRecord(
            OrderEvent(
                event_id="event:run-end:at-boundary",
                order_id=stream.order.order_id,
                causation_id=last.event_id,
                event_type=OrderEventType.ORDER_ACTIVATED,
                occurred_at=SimulationInstant(
                    BOUNDARY,
                    TimelinePhase(90, "run_end_test"),
                    SourceSequence(1),
                ),
                evidence_id=canonical_sha256({"boundary": "forbidden"}),
            )
        )
    )
    boundary_outcome = RunEndCoordinator().coordinate(
        run_end_evidence(order_streams=(at_boundary,)),
        MarkToMarketCloseoutPolicy(),
    )

    assert isinstance(incomplete_outcome.termination, EngineTermination)
    assert incomplete_outcome.termination.code is EngineTerminationCode.TIMELINE_INCOMPLETE
    assert boundary_outcome.termination is not None
    assert boundary_outcome.termination.code is EngineTerminationCode.BOUNDARY_VIOLATION


def test_closeout_failure_mismatch_and_incomplete_liquidation_terminate() -> None:
    failure = RunEndCoordinator().coordinate(run_end_evidence(), FailingPolicy())
    mismatch = RunEndCoordinator().coordinate(
        run_end_evidence(), MismatchedOutcomePolicy()
    )
    incomplete = RunEndCoordinator().coordinate(run_end_evidence(), LiquidatePolicy())

    assert failure.report is None
    assert failure.termination is not None
    assert failure.termination.code is EngineTerminationCode.CLOSEOUT_POLICY_FAILURE
    assert mismatch.termination is not None
    assert mismatch.termination.code is EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH
    assert incomplete.report is None
    assert incomplete.termination is not None
    assert incomplete.termination.code is EngineTerminationCode.LIQUIDATION_INCOMPLETE


def test_snapshot_and_reservation_cursor_context_must_match() -> None:
    evidence = run_end_evidence()
    stale_snapshot = replace(
        evidence,
        final_snapshot=replace(evidence.final_snapshot, timestamp=UtcInstant(299)),
    )
    cursor = evidence.reservation_state.cursors[0]
    forged_reservations = replace(
        evidence.reservation_state,
        cursors=(
            replace(
                cursor,
                stream_hash=canonical_sha256({"forged": "order-stream"}),
            ),
        ),
    )

    snapshot_outcome = RunEndCoordinator().coordinate(
        stale_snapshot, MarkToMarketCloseoutPolicy()
    )
    reservation_outcome = RunEndCoordinator().coordinate(
        replace(evidence, reservation_state=forged_reservations),
        MarkToMarketCloseoutPolicy(),
    )

    assert snapshot_outcome.termination is not None
    assert snapshot_outcome.termination.code is EngineTerminationCode.EVIDENCE_MISMATCH
    assert reservation_outcome.termination is not None
    assert reservation_outcome.termination.code is EngineTerminationCode.EVIDENCE_MISMATCH


def test_liquidation_completion_requires_no_positions_orders_reservations_or_fees() -> None:
    evidence = run_end_evidence()
    flat_snapshot = replace(evidence.final_snapshot, positions=())
    no_orders = replace(
        evidence,
        final_snapshot=flat_snapshot,
        order_streams=(),
        pending_fee_assessments=(),
        reservation_state=replace(
            evidence.reservation_state,
            cursors=(),
            active_reservations=(),
            totals=type(evidence.reservation_state.totals).empty(),
        ),
    )

    pending_fee = RunEndCoordinator().coordinate(
        replace(no_orders, pending_fee_assessments=evidence.pending_fee_assessments),
        LiquidatePolicy(),
    )
    completed = RunEndCoordinator().coordinate(no_orders, LiquidatePolicy())

    assert pending_fee.termination is not None
    assert pending_fee.termination.code is EngineTerminationCode.LIQUIDATION_INCOMPLETE
    assert completed.termination is None
    assert completed.report is not None
    assert completed.report.closeout_status is RunEndCloseoutStatus.LIQUIDATION_COMPLETED
    assert not completed.report.open_positions
    assert not completed.report.terminated_orders
    assert not completed.report.released_reservations
