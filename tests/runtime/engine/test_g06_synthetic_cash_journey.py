from __future__ import annotations

from crypto_quant_backtest import (
    DeterministicBarEngine,
    EngineExecutionResult,
    ResolvedExecutionCase,
)
from crypto_quant_domain import AccountingEntryType, canonical_bytes, canonical_sha256
from crypto_quant_trading import GenericLedger, PortfolioSnapshotProjector

from tests.support.synthetic_market import (
    SYNTHETIC_PROFILE_KEY,
    SYNTHETIC_PROFILE_LIMITATION,
    SyntheticCashDevelopmentProfile,
    TestProfileRegistry,
    build_synthetic_execution_case,
)


def _profile() -> SyntheticCashDevelopmentProfile:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(
        SYNTHETIC_PROFILE_KEY
    )
    assert lookup.profile is not None
    return lookup.profile


def _run(
    *, batch_size: int = 1
) -> tuple[SyntheticCashDevelopmentProfile, ResolvedExecutionCase, EngineExecutionResult]:
    profile = _profile()
    case = build_synthetic_execution_case(
        profile, timeline_batch_size=batch_size
    )
    outcome = DeterministicBarEngine().run(case)
    assert outcome.result is not None
    assert outcome.input_validation_failure is None
    assert outcome.engine_failure is None
    assert outcome.cancellation is None
    return profile, case, outcome.result


def test_g06_cash_journey_has_exact_fill_fee_and_financial_economics() -> None:
    _, _, result = _run()

    assert len(result.decision_batches) == 1
    assert len(result.normalized_targets) == 1
    assert len(result.order_streams) == 1
    assert len(result.fills) == 1
    assert len(result.slippage_decisions) == 1
    assert len(result.fee_assessments) == 1

    batch = result.decision_batches[0]
    target = result.normalized_targets[0]
    order = result.order_streams[0].order
    fill = result.fills[0]
    slippage = result.slippage_decisions[0]
    fee = result.fee_assessments[0]

    assert target.source_decision_batch_id == batch.decision_batch_id
    assert target.active_target.source_decision_batch_id == batch.decision_batch_id
    assert order.intent.parent_id == target.normalized_target_id
    assert fill.order_id == order.order_id
    assert fill.fill_id in fee.basis_ids
    assert fill.execution_time > target.materialized_at
    assert fill.reference_price.units == 10_500
    assert slippage.reference_price.mark.source_event_id == "engine-bar-open-200"
    assert fill.slippage_amount.units == 11
    assert fill.price.units == 10_511
    assert slippage.reference_price.mark.price == fill.reference_price
    assert slippage.slippage_amount.units == fill.slippage_amount.units
    assert slippage.execution_price == fill.price
    assert slippage.decision_id == fill.slippage_decision_id
    assert fee.amount.units == 53

    entry_types = tuple(entry.entry_type for entry in result.final_journal.entries)
    expected_entry_types = tuple(
        [
            AccountingEntryType.CAPITAL_DEPOSITED,
            AccountingEntryType.FILL_BOOKED,
            AccountingEntryType.FEE_CHARGED,
        ]
    )
    assert entry_types == expected_entry_types
    assert fill.fill_id.value in result.final_journal.entries[1].source_ids
    assert fee.fee_assessment_id.value in result.final_journal.entries[2].source_ids

    ledger = result.final_ledger_state
    snapshot = result.final_portfolio_snapshot
    assert ledger.cash_balances[0].amount.units == 47_392
    assert ledger.position_balances[0].quantity.units == 5_000
    assert ledger.fees[0].amount.units == 53
    assert snapshot.equity.units == 102_392
    assert snapshot.unrealized_pnl.units == 2_445
    assert snapshot.fees.units == 53


def test_journal_marks_and_currency_valuation_rebuild_the_final_snapshot() -> None:
    _, case, result = _run()

    rebuilt_ledger = GenericLedger(case.financial_state.ledger_schema).project(
        result.final_journal
    )
    assert rebuilt_ledger == result.final_ledger_state
    assert rebuilt_ledger.state_hash == result.final_ledger_state.state_hash

    plan = case.snapshot_plan
    projection = PortfolioSnapshotProjector().project(
        ledger_state=rebuilt_ledger,
        resolved_marks=plan.resolved_marks,
        valuations=plan.valuations,
        reporting_currency=plan.reporting_currency,
        reporting_scale=plan.reporting_scale,
        timestamp=plan.timestamp,
        currency_valuation_graph_hash=plan.currency_valuation_graph_hash,
    )
    assert projection.failure is None
    assert projection.snapshot == result.final_portfolio_snapshot


def test_run_end_report_matches_open_and_pending_state() -> None:
    _, _, result = _run()
    report = result.run_end_report

    assert not report.terminated_orders
    assert not report.released_reservations
    assert report.open_positions == result.final_ledger_state.position_balances
    assert not report.pending_settlements
    assert not report.pending_fee_assessments
    assert len(report.last_valuation_mark_ids) == 1
    assert report.journal_state_hash == result.final_ledger_state.state_hash
    assert report.final_snapshot_hash == canonical_sha256(
        result.final_portfolio_snapshot
    )


def test_repeat_run_and_timeline_batch_size_have_exact_hash_parity() -> None:
    _, first_case, first = _run(batch_size=1)
    _, repeat_case, repeat = _run(batch_size=1)
    _, paged_case, paged = _run(batch_size=10)

    assert first_case.case_hash == repeat_case.case_hash == paged_case.case_hash
    assert first.result_hash == repeat.result_hash == paged.result_hash
    assert first.trace.trace_hash == repeat.trace.trace_hash == paged.trace.trace_hash
    assert (
        first.final_ledger_state.state_hash
        == repeat.final_ledger_state.state_hash
        == paged.final_ledger_state.state_hash
    )
    assert canonical_sha256(first.final_portfolio_snapshot) == canonical_sha256(
        paged.final_portfolio_snapshot
    )
    assert first.run_end_report.report_hash == paged.run_end_report.report_hash


def test_g06_remains_development_only_engine_evidence_without_run_outcome() -> None:
    profile, _, result = _run()
    try:
        evidence = canonical_bytes(
            {"profile": profile, "engine_result": result}
        ).decode("utf-8")
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise AssertionError("G06 evidence is not canonical UTF-8") from error

    assert SYNTHETIC_PROFILE_LIMITATION in evidence
    assert '"grade":"development"' in evidence
    assert '"decision_grade_eligible":false' in evidence
    assert '"deployment_authorized":false' in evidence
    for forbidden in (
        "semantic_run_id",
        "attempt_id",
        "run_outcome",
        "completed_result",
        '"deployment_authorized":true',
    ):
        assert forbidden not in evidence
