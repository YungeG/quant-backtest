from __future__ import annotations

from dataclasses import replace
from typing import cast

from crypto_quant_backtest import DeterministicBarEngine, EngineStage
from crypto_quant_backtest.financial_dispatch import CashFillAccountingPlan
from crypto_quant_domain import canonical_sha256
from crypto_quant_trading import FinalFeeRuleSet

from tests.kernel.fees._fixtures import all_rules
from tests.runtime.engine._fixtures import execution_case


def _taker_fee_case():
    case = execution_case()
    execution = case.bar_executions[0]
    accounting = execution.accounting_plan
    legacy = accounting.fee_plan.final_fee_rule_set
    taker_rules = FinalFeeRuleSet.create(
        market_fee_policy_ref=legacy.market_fee_policy_ref,
        tax_policy_ref=legacy.tax_policy_ref,
        account_fee_schedule_ref=legacy.account_fee_schedule_ref,
        assessment_currency=legacy.assessment_currency,
        assessment_scale=legacy.assessment_scale,
        charge_rules=all_rules(),
        minimums=(),
    )
    accounting = replace(
        accounting,
        position_payload=replace(
            cast(CashFillAccountingPlan, accounting.position_payload),
            final_fee_rule_set=taker_rules,
        ),
        fee_plan=replace(
            accounting.fee_plan,
            final_fee_rule_set=taker_rules,
        ),
    )
    return replace(
        case,
        bar_executions=(
            replace(
                execution,
                accounting_plan=accounting,
                fill_liquidity_role="taker",
            ),
        ),
    )


def _fee_trace_hash(result) -> str:
    return next(
        entry.evidence_hash
        for entry in result.trace.entries
        if entry.stage is EngineStage.FEE_ASSESSMENT
    )


def test_engine_uses_role_builder_and_accepts_taker_fee_path() -> None:
    legacy = DeterministicBarEngine().run(execution_case()).result
    taker = DeterministicBarEngine().run(_taker_fee_case()).result
    assert legacy is not None and taker is not None

    assert legacy.fills[0].liquidity == "full"
    assert taker.fills[0].liquidity == "taker"
    assert taker.fee_assessments[0].amount.units == 53
    assert canonical_sha256(legacy.fills[0]) != canonical_sha256(taker.fills[0])
    assert legacy.result_hash != taker.result_hash
    assert _fee_trace_hash(legacy) != _fee_trace_hash(taker)


def test_none_role_keeps_existing_full_fill_path() -> None:
    case = execution_case()
    assert case.bar_executions[0].fill_liquidity_role is None
    result = DeterministicBarEngine().run(case).result
    assert result is not None
    assert result.fills[0].liquidity == "full"
