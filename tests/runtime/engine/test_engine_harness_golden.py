from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import canonical_bytes, canonical_sha256

from tests.runtime.engine._fixtures import run_result


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/runtime/deterministic-engine-orchestration-v1.json"


def canonical_value(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise AssertionError("Engine canonical value is invalid") from error


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid frozen Engine fixture: {FIXTURE}") from error


def test_engine_execution_matches_static_golden_artifact() -> None:
    result = run_result()
    actual = {
        "fixture_id": "deterministic-engine-orchestration-v1",
        "case_hash": result.case_hash,
        "target_stream_digest": result.target_stream_digest,
        "trace_hash": result.trace.trace_hash,
        "journal_hash": result.final_journal.journal_hash,
        "ledger_state_hash": result.final_ledger_state.state_hash,
        "snapshot_hash": canonical_sha256(result.final_portfolio_snapshot),
        "run_end_report_hash": result.run_end_report.report_hash,
        "result_hash": result.result_hash,
        "counts": {
            "trace_entries": len(result.trace.entries),
            "decision_batches": len(result.decision_batches),
            "allocations": len(result.allocations),
            "approved_targets": len(result.approved_targets),
            "normalized_targets": len(result.normalized_targets),
            "order_plans": len(result.order_plans),
            "order_streams": len(result.order_streams),
            "fills": len(result.fills),
            "slippage_decisions": len(result.slippage_decisions),
            "fee_assessments": len(result.fee_assessments),
            "journal_entries": result.final_journal.entry_count,
        },
        "trace": canonical_value(result.trace),
        "final_ledger_state": canonical_value(result.final_ledger_state),
        "final_snapshot": canonical_value(result.final_portfolio_snapshot),
        "run_end_report": canonical_value(result.run_end_report),
    }
    assert actual == load_fixture()
