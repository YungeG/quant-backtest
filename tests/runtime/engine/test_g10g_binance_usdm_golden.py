from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_backtest import BinanceUsdmProfileComposer
from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_trading import LinearDerivativeJournalEntry
from tests.runtime.profiles.binance_usdm._fixtures import composition_request
from tests.support.binance_usdm import (
    build_binance_usdm_execution_case,
    build_binance_usdm_resolved_request,
    run_binance_usdm_development_journey,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT
    / "tests/fixtures/runtime/engine/binance-usdm-resolved-profile-development-journey-v1.json"
)


def _actual() -> dict[str, object]:
    request = composition_request()
    composition = BinanceUsdmProfileComposer().compose(request)
    if composition.result is None:
        raise AssertionError(f"Binance composition failed: {composition.failure!r}")
    profile = composition.result
    resolved = build_binance_usdm_resolved_request(request)
    case = build_binance_usdm_execution_case(request, resolved_request=resolved)
    result = run_binance_usdm_development_journey()
    return {
        "fixture_id": "binance-usdm-resolved-profile-development-journey-v1",
        "request_hash": request.request_hash,
        "source_manifest": profile.source_manifest,
        "model_digest": profile.model_digest,
        "profile_digest": profile.profile_digest,
        "capacity_evidence_hash": request.account_capacity.evidence_hash,
        "contract_hash": canonical_sha256(profile.linear_contract),
        "account_risk_policy_hash": canonical_sha256(profile.account_risk_policy),
        "market_profile_digest": profile.market_semantics.profile_digest,
        "simulation_profile_digest": profile.simulation.profile_digest,
        "account_profile_digest": profile.execution_account.profile_digest,
        "registry_hash": canonical_sha256(profile.profile_registry),
        "dispatcher_spec_hash": canonical_sha256(profile.financial_dispatcher_spec),
        "semantic_run_id": resolved.semantic_run_id,
        "semantic_spec_hash": case.semantic_spec_hash,
        "identity_manifest_hash": case.identity_manifest.manifest_hash,
        "case_hash": case.case_hash,
        "trace_hash": result.trace.trace_hash,
        "transitions": tuple(
            entry.request.transition.kind.value
            for entry in result.final_journal.entries
            if type(entry) is LinearDerivativeJournalEntry
        ),
        "journal_hash": result.final_journal.journal_hash,
        "ledger_state_hash": result.final_ledger_state.state_hash,
        "position_units": result.final_ledger_state.position_balances[0].quantity.units,
        "realized_pnl_units": result.final_ledger_state.realized_pnl[0].amount.units,
        "funding_units": result.final_ledger_state.financing[0].amount.units,
        "fee_units": result.final_ledger_state.fees[0].amount.units,
        "artifact_roles": tuple(value.role for value in result.financial_artifacts),
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


def test_binance_usdm_development_journey_matches_static_golden() -> None:
    try:
        expected = cast(
            dict[str, Any],
            json.loads(FIXTURE.read_text(encoding="utf-8")),
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid frozen G10G fixture: {FIXTURE}") from error
    try:
        actual = cast(dict[str, Any], json.loads(canonical_bytes(_actual())))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise AssertionError("G10G evidence is not canonical") from error
    assert actual == expected
