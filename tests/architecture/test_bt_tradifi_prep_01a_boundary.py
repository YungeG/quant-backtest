from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_backtest as runtime
import crypto_quant_backtest.binance_usdm_tradifi_preparation as preparation

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
MODULE = PACKAGE / "binance_usdm_tradifi_preparation.py"


def _runtime_import_closure(module: Path) -> set[Path]:
    pending = [module]
    visited: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in visited or not current.exists():
            continue
        visited.add(current)
        tree = ast.parse(current.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: tuple[str, ...] = ()
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    names = ((node.module or "").split(".")[0],)
                elif (node.module or "").startswith("crypto_quant_backtest."):
                    names = ((node.module or "").split(".")[1],)
            elif isinstance(node, ast.Import):
                names = tuple(
                    alias.name.split(".")[1]
                    for alias in node.names
                    if alias.name.startswith("crypto_quant_backtest.")
                )
            pending.extend(PACKAGE / f"{name}.py" for name in names if name)
    return visited


def test_stage_a_is_runtime_owned_offline_and_builder_free() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }

    assert all(
        "bundle_builder" not in name and not name.startswith("tests")
        for name in imports
    )
    for forbidden in (
        "ArtifactEnvelopePublisher",
        "BacktestRequest",
        "ExecutionCaseComposer",
        "materialize_execution_input_bundle",
        "pickle",
        "socket",
        "requests",
        "urllib",
        "open(",
    ):
        assert forbidden not in source


def test_stage_a_transitive_runtime_imports_exclude_case_runtime() -> None:
    closure = _runtime_import_closure(MODULE)
    forbidden_modules = {
        "cash_development_provider.py",
        "composition.py",
        "execution_inputs.py",
        "facade.py",
        "integrity.py",
    }

    assert not ({path.name for path in closure} & forbidden_modules)


def test_only_intent_and_provider_are_new_root_exports() -> None:
    assert (
        runtime.BinanceUsdmTradifiBarRequestIntent
        is preparation.BinanceUsdmTradifiBarRequestIntent
    )
    assert (
        runtime.BinanceUsdmTradifiProviderInputs
        is preparation.BinanceUsdmTradifiProviderInputs
    )
    assert "BinanceUsdmTradifiBarRequestIntent" in runtime.__all__
    assert "BinanceUsdmTradifiProviderInputs" in runtime.__all__
    assert (
        "resolve_binance_usdm_tradifi_preparation_authority_v1" not in runtime.__all__
    )
    assert not hasattr(runtime, "resolve_binance_usdm_tradifi_preparation_authority_v1")
