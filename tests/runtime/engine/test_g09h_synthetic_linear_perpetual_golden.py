from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_backtest import DeterministicBarEngine
from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_trading import LinearDerivativeJournalEntry
from tests.support.synthetic_market import (
    SyntheticLinearPerpetualDevelopmentProfile,
    TestProfileRegistry,
    build_synthetic_linear_perpetual_execution_case,
    build_synthetic_linear_perpetual_resolved_request,
)
from tests.support.synthetic_market.linear_perpetual import (
    PROFILE_KEY,
    SyntheticLinearFinancialDispatcher,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT
    / "tests/fixtures/runtime/engine/synthetic-linear-perpetual-development-journey-v1.json"
)


def _actual() -> dict[str, object]:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(PROFILE_KEY)
    profile = lookup.profile
    assert isinstance(profile, SyntheticLinearPerpetualDevelopmentProfile)
    resolved = build_synthetic_linear_perpetual_resolved_request(profile)
    case = build_synthetic_linear_perpetual_execution_case(
        profile,
        resolved_request=resolved,
    )
    outcome = DeterministicBarEngine(SyntheticLinearFinancialDispatcher()).run(case)
    if outcome.result is None:
        raise AssertionError(f"synthetic Linear Engine failed: {outcome.engine_failure!r}")
    result = outcome.result
    transitions = tuple(
        entry.request.transition.kind.value
        for entry in result.final_journal.entries
        if type(entry) is LinearDerivativeJournalEntry
    )
    return {
        "fixture_id": "synthetic-linear-perpetual-development-journey-v1",
        "profile_digest": profile.profile_digest,
        "dispatcher_spec_hash": canonical_sha256(case.financial_dispatch_plan.dispatcher_spec),
        "semantic_run_id": resolved.semantic_run_id,
        "semantic_spec_hash": case.semantic_spec_hash,
        "identity_manifest_hash": case.identity_manifest.manifest_hash,
        "case_hash": case.case_hash,
        "trace_hash": result.trace.trace_hash,
        "transitions": transitions,
        "journal_entry_types": tuple(
            type(entry).__name__ for entry in result.final_journal.entries
        ),
        "journal_hash": result.final_journal.journal_hash,
        "ledger_state_hash": result.final_ledger_state.state_hash,
        "position_units": result.final_ledger_state.position_balances[0].quantity.units,
        "realized_pnl_units": result.final_ledger_state.realized_pnl[0].amount.units,
        "funding_units": result.final_ledger_state.financing[0].amount.units,
        "fee_units": result.final_ledger_state.fees[0].amount.units,
        "artifact_roles": tuple(
            value.role for value in result.financial_artifacts
        ),
        "artifact_hashes": tuple(
            value.artifact_hash for value in result.financial_artifacts
        ),
        "snapshot_hash": canonical_sha256(result.final_portfolio_snapshot),
        "run_end_report_hash": result.run_end_report.report_hash,
        "result_hash": result.result_hash,
        "limitations": profile.limitations,
        "decision_grade_eligible": profile.decision_grade_eligible,
        "deployment_authorized": profile.deployment_authorized,
    }


def test_synthetic_linear_perpetual_journey_matches_static_golden() -> None:
    try:
        expected = cast(
            dict[str, Any],
            json.loads(FIXTURE.read_text(encoding="utf-8")),
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid frozen G09H fixture: {FIXTURE}") from error
    try:
        actual = cast(dict[str, Any], json.loads(canonical_bytes(_actual())))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise AssertionError("G09H evidence is not canonical") from error
    assert actual == expected
