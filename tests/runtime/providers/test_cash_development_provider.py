from __future__ import annotations

from dataclasses import fields, is_dataclass
from inspect import signature

import crypto_quant_backtest as backtest


def test_cash_development_public_contract_is_additive_and_hides_resolved_types() -> None:
    names = (
        "CashDevelopmentRequestIntent",
        "BacktestRequestRef",
        "CashDevelopmentProviderInputs",
        "PreparedBacktestExecution",
        "prepare_cash_development_backtest",
    )
    for name in names:
        assert name in backtest.__all__, f"BT-GAP-09 RED: missing public {name}"

    intent = backtest.CashDevelopmentRequestIntent
    provider_inputs = backtest.CashDevelopmentProviderInputs
    request_ref = backtest.BacktestRequestRef
    prepared = backtest.PreparedBacktestExecution
    prepare = backtest.prepare_cash_development_backtest

    assert all(is_dataclass(value) for value in (intent, provider_inputs, request_ref, prepared))
    assert tuple(value.name for value in fields(intent)) == (
        "schema_version",
        "experiment_id",
        "timeline_window",
        "execution_account_id",
        "reporting_currency",
        "master_random_seed",
    )
    assert tuple(value.name for value in fields(provider_inputs)) == (
        "schema_version",
        "build_artifact_manifest",
        "instrument_catalog",
        "strategy_id",
        "sleeve_id",
        "initial_cash",
        "quantity_lattice",
        "decision_mark",
        "final_mark",
        "order_capabilities",
    )
    assert tuple(value.name for value in fields(request_ref)) == ("artifact_ref",)
    assert tuple(value.name for value in fields(prepared)) == (
        "request_ref",
        "semantic_run_id",
        "execution_request",
        "runtime",
    )

    parameters = signature(prepare).parameters
    assert tuple(parameters) == (
        "request_intent",
        "provider_inputs",
        "artifact_reader",
        "artifact_publisher",
        "market_reader",
        "publication_root",
    )
    assert all(value.kind.name == "KEYWORD_ONLY" for value in parameters.values())
    assert not {
        "ResolvedBacktestRequest",
        "ResolvedExecutionCase",
        "ExecutionCaseSemanticSpec",
    } & set(parameters)

    cancellation = signature(backtest.BacktestRuntime.run_with_cancellation).parameters
    assert tuple(cancellation) == ("self", "request", "cancellation")
    assert tuple(signature(backtest.BacktestRuntime.run).parameters) == ("self", "request")
