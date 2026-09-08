from __future__ import annotations

from dataclasses import replace

from crypto_quant_backtest import (
    DeterministicBarEngine,
    NextEligibleBarCloseModel,
    NoEligibleBarAction,
)
from crypto_quant_domain import Money, OrderStatus, Scale, TimeInForce
from crypto_quant_trading import PortfolioValueKind

from tests.runtime.engine._fixtures import CASH_KEY, execution_case


def _no_candidate_case(action: NoEligibleBarAction):
    base = execution_case()
    cash_value = next(
        value
        for value in base.snapshot_plan.valuations
        if value.value_ref.kind is PortfolioValueKind.CASH
    )
    cash = Money(100_000, Scale(2), "USD")
    snapshot = replace(
        base.snapshot_plan,
        resolved_marks=(),
        valuations=(replace(cash_value, native_value=cash, reporting_value=cash),),
    )
    return replace(
        base,
        bar_executions=(),
        execution_model=NextEligibleBarCloseModel.create(
            actions=tuple((tif, action) for tif in TimeInForce)
        ),
        snapshot_plan=snapshot,
        financial_dispatch_plan=replace(
            base.financial_dispatch_plan,
            final_snapshot_payload=snapshot,
            expected_artifact_roles=("final_snapshot",),
        ),
    )


def test_close_window_without_candidate_keeps_order_for_run_end() -> None:
    case = _no_candidate_case(NoEligibleBarAction.KEEP_ACTIVE)
    outcome = DeterministicBarEngine().run(case)

    assert outcome.engine_failure is None
    assert outcome.result is not None
    result = outcome.result
    state = result.order_streams[0].state
    assert state is not None
    assert state.status is OrderStatus.ACCEPTED
    assert len(result.run_end_report.terminated_orders) == 1
    assert len(result.run_end_report.released_reservations) == 1
    assert result.fills == result.fee_assessments == ()
    assert result.final_journal == case.financial_state.journal
    assert result.final_ledger_state.cash_amount(CASH_KEY) == Money(100_000, Scale(2), "USD")


def test_close_window_expiry_releases_reservations_before_run_end() -> None:
    case = _no_candidate_case(NoEligibleBarAction.EXPIRE)
    outcome = DeterministicBarEngine().run(case)

    assert outcome.engine_failure is None
    assert outcome.result is not None
    result = outcome.result
    [stream] = result.order_streams
    assert stream.state is not None
    assert stream.state.status is OrderStatus.EXPIRED
    assert (
        stream.records[-1].event.occurred_at.instant.epoch_nanoseconds
        == case.timeline.window.end_exclusive.epoch_nanoseconds - 1
    )
    assert result.run_end_report.terminated_orders == ()
    assert result.run_end_report.released_reservations == ()
    assert result.fills == result.fee_assessments == ()
    assert result.final_journal == case.financial_state.journal
    assert result.final_portfolio_snapshot.equity == Money(100_000, Scale(2), "USD")
    replay = DeterministicBarEngine().run(replace(case, timeline_batch_size=3))
    assert replay.result is not None
    assert replay.result.result_hash == result.result_hash
