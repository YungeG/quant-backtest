from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from pathlib import Path

import crypto_quant_backtest
import crypto_quant_backtest.strategy_runtime as strategy_runtime
from crypto_quant_backtest import (
    PortfolioStrategyInvocationContext,
    PortfolioStrategyRegistration,
    invoke_portfolio_strategies,
)


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/strategy_runtime.py"
)
ROOT_API = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "crypto_quant_domain",
    "crypto_quant_trading",
    "dataclasses",
    "decision_schedule",
    "enum",
    "model_revisions",
    "observation_windows",
    "observations",
    "random_streams",
    "resolution",
    "strategy_state",
    "timeline",
    "typing",
    "universe",
}
PUBLIC_NAMES = {
    "PortfolioStrategyInvocation",
    "PortfolioStrategyInvocationContext",
    "PortfolioStrategyInvocationFailureCode",
    "PortfolioStrategyInvocationOutput",
    "PortfolioStrategyInvocationStatus",
    "PortfolioStrategyRegistration",
    "invoke_portfolio_strategies",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def test_g11i_is_one_offline_orchestrator_over_frozen_public_seams() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Protocol",
        "Registry",
        "Factory",
        "Executor",
        "Thread",
        "Process",
        "asyncio",
        "datetime",
        "pathlib",
        "random.",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "pickle",
        "joblib",
        "importlib",
        "open(",
    ):
        assert forbidden not in source
    assert source.count("AtomicDecisionBatchCollector().collect(") == 1
    assert source.count("validator.validate(") == 1
    assert "DecisionBatch(" not in source
    assert "LatestSleeveDecisionState(" not in source

    assert list(inspect.signature(invoke_portfolio_strategies).parameters) == [
        "eligibility",
        "instrument_catalog",
        "registrations",
        "prior_decision_state",
    ]
    assert {field.name for field in fields(PortfolioStrategyRegistration)} == {
        "expectation",
        "strategy_artifact",
        "strategy",
        "observation_results",
        "universe",
        "windows",
        "previous_checkpoint",
        "random_streams",
        "model_timelines",
        "previous_output",
    }
    assert {field.name for field in fields(PortfolioStrategyInvocationContext)} == {
        "expectation",
        "eligibility",
        "observation_results",
        "universe",
        "windows",
        "previous_target",
        "previous_state_hash",
        "previous_input_instant",
        "previous_checkpoint_hash",
        "previous_output_hash",
        "random_streams",
        "model_timelines",
        "instrument_catalog_hash",
    }
    assert set(strategy_runtime.__all__) == PUBLIC_NAMES
    assert PUBLIC_NAMES <= set(crypto_quant_backtest.__all__)
    root_tree = ast.parse(ROOT_API.read_text(encoding="utf-8"))
    root_imports = {
        alias.name
        for node in ast.walk(root_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "strategy_runtime"
        for alias in node.names
    }
    assert root_imports == PUBLIC_NAMES

    for path in GENERIC_RUNTIME:
        generic_source = path.read_text(encoding="utf-8")
        assert "PortfolioStrategyInvocation" not in generic_source
        assert "strategy_runtime" not in generic_source
