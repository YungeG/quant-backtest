from __future__ import annotations

from crypto_quant_domain import AccountingEntryType
from tests.support.cn_a_share import run_cn_a_share_development_journey


_CASH_OUTCOME_HASH = "sha256:001196b5827c7b08d65f7564b80ee7e04c8739e184ad03e2d4ce384fe859f27e"
_SHARE_OUTCOME_HASH = "sha256:7b46da3c1aaa504b8f5a4b4a4639d2879977d6cf4b880cadfe6b42ea72c607c1"


def _assert_equal(actual: object, expected: object) -> None:
    assert actual == expected


def test_g08h_journey_uses_branchless_financial_dispatch_and_replays() -> None:
    result = run_cn_a_share_development_journey()
    _assert_equal(
        result.operation_keys,
        (
            "cn_a_share.corporate_action.cash_payment.v1",
            "cn_a_share.corporate_action.share_delivery.v1",
        ),
    )
    _assert_equal(result.event_phases, (110, 120))
    assert result.cash_payment_outcome.failure is None
    assert result.cash_payment_outcome.journal_entry is not None
    assert result.cash_payment_outcome.journal_entry.entry_type is AccountingEntryType.CORPORATE_ACTION_CASH_PAID
    assert result.cash_payment_outcome.outcome_hash == _CASH_OUTCOME_HASH
    assert result.cash_payment_outcome.journal_entry.balance_changes[0].delta.units == 7_000
    assert result.share_delivery_outcome.failure is None
    assert result.share_delivery_outcome.journal_entry is not None
    assert result.share_delivery_outcome.journal_entry.entry_type is AccountingEntryType.CORPORATE_ACTION_POSITION_ADJUSTED
    assert result.share_delivery_outcome.outcome_hash == _SHARE_OUTCOME_HASH
    share_entry = result.share_delivery_outcome.journal_entry
    assert share_entry.balance_changes[0].delta.units == 210
    assert len(share_entry.position_lot_changes) == 1
    lot_change = share_entry.position_lot_changes[0]
    assert lot_change.before is not None
    assert lot_change.after is not None
    assert lot_change.before.total_cost_basis == lot_change.after.total_cost_basis
    assert lot_change.before.quantity.units == 500
    assert lot_change.after.quantity.units == 710
    assert result.full_replay_ledger_hash == result.prefix_resume_ledger_hash
    assert result.full_replay_lot_book_hash == result.prefix_resume_lot_book_hash
    assert result.final_ledger_state.state_hash == result.full_replay_ledger_hash
    assert result.final_lot_book_hash == result.full_replay_lot_book_hash
    assert result.final_ledger_state.state_hash == result.final_portfolio_snapshot.journal_state_hash
    assert not result.decision_grade_eligible
    assert not result.deployment_authorized


def test_g08h_journey_is_repeatable() -> None:
    first = run_cn_a_share_development_journey()
    second = run_cn_a_share_development_journey()
    assert first.result_hash == second.result_hash
    assert first.to_canonical_dict() == second.to_canonical_dict()
