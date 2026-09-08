from __future__ import annotations

from tests.support.binance_usdm import run_binance_usdm_development_journey


def test_binance_usdm_journey_uses_branchless_financial_dispatch() -> None:
    result = run_binance_usdm_development_journey()

    assert len(result.fills) == 3
    assert len(result.fee_assessments) == 3
    roles = {value.role for value in result.financial_artifacts}
    assert {
        "linear_position_transition",
        "funding_settlement",
        "account_margin_projection",
        "liquidation_audit",
        "portfolio_snapshot",
    } <= roles
    assert result.final_journal.entries
    assert result.final_ledger_state.state_hash == result.final_portfolio_snapshot.journal_state_hash


def test_binance_usdm_journey_is_repeatable() -> None:
    first = run_binance_usdm_development_journey()
    second = run_binance_usdm_development_journey()

    assert first.result_hash == second.result_hash
