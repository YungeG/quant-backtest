from __future__ import annotations

from pathlib import Path

from crypto_quant_backtest import DeterministicBarEngine
from crypto_quant_backtest.binance_usdm_tradifi_case_planner import (
    plan_binance_usdm_tradifi_case_v1,
)
from crypto_quant_domain import Money

from tests.runtime.providers.test_binance_usdm_tradifi_preparation import _resolve


def test_empty_retained_bundle_plans_composes_and_runs_flat() -> None:
    preparation = _resolve(0).result
    assert preparation is not None

    planned = plan_binance_usdm_tradifi_case_v1(preparation)
    outcome = DeterministicBarEngine().run(planned.execution_case)

    assert planned.execution_case.decision_cycles == ()
    assert planned.execution_case.bar_executions == ()
    assert outcome.engine_failure is None and outcome.result is not None
    snapshot = outcome.result.final_portfolio_snapshot
    assert snapshot.positions == ()
    assert snapshot.financing == Money(0, snapshot.financing.scale, "USDT")
    assert {artifact.role for artifact in outcome.result.financial_artifacts} == {
        "final_snapshot",
        "funding_accounting",
        "funding_eligibility",
        "margin_projection.final",
    }


def test_production_planner_has_no_test_builder_or_financial_simulation_imports() -> None:
    source = (
        Path(__file__).parents[3]
        / "packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_tradifi_case_planner.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "crypto_quant_bundle_builder",
        "tests.",
        "BinanceUsdmTradifiLinearFinancialDispatcher",
        "FeeAssessmentEngine",
        "LinearDerivativeAccounting",
        "dispatch_funding_before",
        "book_fill(",
        "book_fee(",
    ):
        assert forbidden not in source
