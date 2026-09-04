from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from tests.support.cn_a_share import run_cn_a_share_development_journey


FIXTURE = Path(__file__).parents[2] / "fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json"
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_FIXTURE_SHA256 = "08358c1c0d2144fb23c1b1c8862fa6c879bd285533e5fa415e5cc0273013e905"


def _actual() -> dict[str, object]:
    result = run_cn_a_share_development_journey()
    assert result.cash_payment_outcome.journal_entry is not None
    assert result.share_delivery_outcome.journal_entry is not None
    cash_entry = result.cash_payment_outcome.journal_entry
    share_entry = result.share_delivery_outcome.journal_entry
    lot_change = share_entry.position_lot_changes[0]
    assert lot_change.before is not None
    assert lot_change.after is not None
    total_basis = lot_change.before.total_cost_basis
    assert total_basis is not None
    return {
        "fixture_id": "cn-a-share-resolved-profile-development-journey-v1", "schema_version": 1,
        "profile_fixture_id": "cn-a-share-resolved-profile-composition-v1",
        "venue_id": result.resolved_profile.execution_account.venue_id,
        "operation_keys": list(result.operation_keys), "event_phases": list(result.event_phases),
        "cash_payment": {"outcome_hash": result.cash_payment_outcome.outcome_hash, "entry_type": cash_entry.entry_type.value, "currency": cash_entry.balance_changes[0].delta.currency, "scale": cash_entry.balance_changes[0].delta.scale.places, "units": cash_entry.balance_changes[0].delta.units},
        "share_delivery": {"outcome_hash": result.share_delivery_outcome.outcome_hash, "entry_type": share_entry.entry_type.value, "quantity_scale": share_entry.balance_changes[0].delta.scale.places, "delivered_units": share_entry.balance_changes[0].delta.units, "before_units": lot_change.before.quantity.units, "after_units": lot_change.after.quantity.units, "total_cost_basis_currency": total_basis.currency, "total_cost_basis_scale": total_basis.scale.places, "total_cost_basis_units": total_basis.units},
        "replay_controls": {"full_equals_prefix_resume_ledger": result.full_replay_ledger_hash == result.prefix_resume_ledger_hash, "full_equals_prefix_resume_lot_book": result.full_replay_lot_book_hash == result.prefix_resume_lot_book_hash, "snapshot_binds_final_journal_state": result.final_ledger_state.state_hash == result.final_portfolio_snapshot.journal_state_hash},
        "negative_cases": ["applied_tax_before_effects", "deferred_unsupported_tax_before_effects", "xshg_share_delivery_before_effects", "event_before_available_at", "wrong_event_phase", "fractional_share_delivery", "sub_cent_cash_payment", "multiple_or_missing_target_lot", "dispatcher_plan_divergence"],
        "qualification": {"allowed_grade": "development", "decision_grade_eligible": result.decision_grade_eligible, "profile_qualified": result.resolved_profile.profile_qualified, "deployment_authorized": result.deployment_authorized},
    }


def test_g08h_journey_matches_static_golden() -> None:
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _FIXTURE_SHA256
    try:
        expected = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AssertionError("invalid G08H Journey golden fixture") from error
    assert _actual() == expected


def test_g08h_journey_dynamic_hashes_are_canonical() -> None:
    result = run_cn_a_share_development_journey()
    for value in (result.execution_case_hash, result.trace_hash, result.final_journal_hash, result.final_ledger_state.state_hash, result.final_lot_book_hash, result.result_hash):
        assert _HASH.fullmatch(value)
