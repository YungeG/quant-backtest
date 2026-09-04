from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import MarkToMarketCloseoutPolicy, RunEndCoordinator
from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.runtime.run_end._fixtures import run_end_evidence


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/runtime/deterministic-run-end-report-v1.json"


def test_run_end_report_matches_canonical_golden() -> None:
    evidence = run_end_evidence()
    policy = MarkToMarketCloseoutPolicy()
    outcome = RunEndCoordinator().coordinate(evidence, policy)
    assert outcome.report is not None

    report = outcome.report
    actual = json.loads(
        canonical_bytes(
            {
                "fixture_id": "deterministic-run-end-report-v1",
                "evidence_hash": evidence.evidence_hash,
                "policy_spec_hash": canonical_sha256(policy.spec()),
                "outcome_hash": outcome.outcome_hash,
                "report_id": report.report_id,
                "report_hash": report.report_hash,
                "closeout_status": report.closeout_status.value,
                "terminated_order_ids": [
                    item.order_id.value for item in report.terminated_orders
                ],
                "released_reservation_hashes": [
                    item.release_hash for item in report.released_reservations
                ],
                "open_position_instruments": [
                    str(item.key.instrument_id) for item in report.open_positions
                ],
                "pending_settlement_ids": [
                    item.obligation.settlement_obligation_id.value
                    for item in report.pending_settlements
                ],
                "pending_fee_basis_hashes": [
                    item.basis_hash for item in report.pending_fee_assessments
                ],
                "last_valuation_mark_ids": report.last_valuation_mark_ids,
            }
        )
    )
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected
