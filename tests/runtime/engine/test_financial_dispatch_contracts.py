from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    DefaultCashFinancialDispatcher,
    DeterministicBarEngine,
    EngineFailureCode,
    FinancialDispatchFailureCode,
    default_cash_financial_dispatcher_spec,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256

from tests.runtime.engine._fixtures import execution_case


def test_engine_rejects_missing_or_invalid_financial_dispatcher() -> None:
    with pytest.raises(TypeError, match="FinancialEventDispatcher"):
        DeterministicBarEngine(None)
    with pytest.raises(TypeError, match="FinancialEventDispatcher"):
        DeterministicBarEngine(object())


def test_cash_execution_uses_canonical_financial_dispatch_plan() -> None:
    case = execution_case()

    outcome = DeterministicBarEngine().run(case)

    assert outcome.result is not None
    assert case.financial_dispatch_plan.dispatcher_spec == (
        default_cash_financial_dispatcher_spec()
    )
    roles = tuple(value.role for value in outcome.result.financial_artifacts)
    expected_roles = ("position_accounting", "final_snapshot")
    assert roles == expected_roles
    assert canonical_sha256(outcome.result.financial_artifacts[1].payload) == (
        canonical_sha256(outcome.result.final_portfolio_snapshot)
    )
    assert canonical_bytes(case) == canonical_bytes(execution_case())


def test_dispatcher_spec_mismatch_fails_before_fill_accounting() -> None:
    case = execution_case()
    wrong = replace(
        default_cash_financial_dispatcher_spec(),
        dispatcher_key="wrong.financial-dispatcher.v1",
    )
    dispatcher = DefaultCashFinancialDispatcher()
    object.__setattr__(dispatcher, "_spec", wrong)

    outcome = DeterministicBarEngine(dispatcher).run(case)

    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code == EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    expected_subjects = (
        FinancialDispatchFailureCode.DISPATCHER_SPEC_MISMATCH.value,
    )
    assert outcome.engine_failure.subject_keys == expected_subjects


def test_financial_plan_changes_case_and_semantic_identity() -> None:
    case = execution_case()
    changed = replace(
        case.financial_dispatch_plan,
        expected_artifact_roles=("final_snapshot",),
    )

    changed_case = replace(case, financial_dispatch_plan=changed)

    assert changed_case.case_hash != case.case_hash
    assert canonical_sha256(changed) != canonical_sha256(case.financial_dispatch_plan)
