from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import DeterministicBarEngine
from crypto_quant_domain import canonical_bytes, canonical_sha256

from tests.support.synthetic_market import (
    SYNTHETIC_PROFILE_KEY,
    TestProfileRegistry,
    build_synthetic_execution_case,
)


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/runtime/g06-synthetic-cash-happy-path-v1.json"


def test_g06_synthetic_cash_journey_matches_static_golden_artifact() -> None:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(
        SYNTHETIC_PROFILE_KEY
    )
    assert lookup.profile is not None
    profile = lookup.profile
    case = build_synthetic_execution_case(profile, timeline_batch_size=1)
    outcome = DeterministicBarEngine().run(case)
    assert outcome.result is not None
    result = outcome.result

    fill = result.fills[0]
    slippage = result.slippage_decisions[0]
    fee = result.fee_assessments[0]
    ledger = result.final_ledger_state
    snapshot = result.final_portfolio_snapshot
    report = result.run_end_report
    evidence = {
        "profile": {
            "profile_key": profile.profile_key,
            "profile_version": profile.profile_version,
            "profile_digest": profile.profile_digest,
            "grade": profile.grade,
            "limitations": profile.limitations,
            "decision_grade_eligible": profile.decision_grade_eligible,
            "deployment_authorized": profile.deployment_authorized,
            "market_profile_digest": profile.market_semantics.profile_digest,
            "simulation_profile_digest": profile.simulation.profile_digest,
            "execution_account_profile_digest": (
                profile.execution_account.profile_digest
            ),
        },
        "case_hash": case.case_hash,
        "target_stream_digest": result.target_stream_digest,
        "result_hash": result.result_hash,
        "trace_hash": result.trace.trace_hash,
        "trace_stages": tuple(entry.stage.value for entry in result.trace.entries),
        "decision_batch_id": result.decision_batches[0].decision_batch_id,
        "normalized_target_id": result.normalized_targets[0].normalized_target_id,
        "order_id": result.order_streams[0].order.order_id.value,
        "fill": {
            "fill_id": fill.fill_id.value,
            "order_id": fill.order_id.value,
            "quantity_units": fill.quantity.units,
            "quantity_scale": fill.quantity.scale.places,
            "reference_price_units": fill.reference_price.units,
            "slippage_units": fill.slippage_amount.units,
            "execution_price_units": fill.price.units,
            "execution_time_ns": fill.execution_time.epoch_nanoseconds,
            "slippage_decision_id": fill.slippage_decision_id,
        },
        "slippage": {
            "decision_id": slippage.decision_id,
            "component_key": slippage.component_ref.component_key,
            "calibration_key": slippage.calibration_ref.calibration_key,
            "calibration_version": slippage.calibration_ref.calibration_version,
            "calibration_digest": slippage.calibration_ref.calibration_digest,
            "basis_points_units": slippage.basis_points_units,
            "execution_price_units": slippage.execution_price.units,
        },
        "fee": {
            "assessment_id": fee.fee_assessment_id.value,
            "basis_type": fee.basis_type.value,
            "basis_ids": tuple(value.value for value in fee.basis_ids),
            "amount_units": fee.amount.units,
            "amount_scale": fee.amount.scale.places,
        },
        "journal": {
            "journal_hash": result.final_journal.journal_hash,
            "entries": tuple(
                {
                    "entry_id": entry.journal_entry_id.value,
                    "entry_type": entry.entry_type.value,
                    "source_ids": entry.source_ids,
                }
                for entry in result.final_journal.entries
            ),
        },
        "ledger": {
            "state_hash": ledger.state_hash,
            "cash_units": ledger.cash_balances[0].amount.units,
            "position_units": ledger.position_balances[0].quantity.units,
            "fee_units": ledger.fees[0].amount.units,
        },
        "snapshot": {
            "snapshot_hash": canonical_sha256(snapshot),
            "journal_state_hash": snapshot.journal_state_hash,
            "equity_units": snapshot.equity.units,
            "unrealized_pnl_units": snapshot.unrealized_pnl.units,
            "fee_units": snapshot.fees.units,
            "valuation_mark_ids": tuple(
                mark.mark_id for mark in snapshot.valuation_marks
            ),
            "currency_valuation_graph_hash": (
                snapshot.currency_valuation_graph_hash
            ),
        },
        "run_end": {
            "report_hash": report.report_hash,
            "closeout_mode": report.closeout_mode.value,
            "closeout_status": report.closeout_status.value,
            "terminated_order_count": len(report.terminated_orders),
            "released_reservation_count": len(report.released_reservations),
            "open_position_units": tuple(
                position.quantity.units for position in report.open_positions
            ),
            "pending_settlement_count": len(report.pending_settlements),
            "pending_fee_count": len(report.pending_fee_assessments),
            "last_valuation_mark_ids": report.last_valuation_mark_ids,
        },
    }
    try:
        actual = json.loads(canonical_bytes(evidence))
        expected_text = GOLDEN.read_text(encoding="utf-8")
        expected = json.loads(expected_text)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AssertionError("invalid G06 static golden evidence") from error

    assert actual == expected
