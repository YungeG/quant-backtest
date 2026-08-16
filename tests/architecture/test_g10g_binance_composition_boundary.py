from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSITION = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_profile.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/composition.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/resolution.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/financial_dispatch.py",
)
PUBLIC_NAMES = (
    "BinanceUsdmAccountCapacityEvidence",
    "BinanceUsdmProfileCompositionRequest",
    "BinanceUsdmMarketSemanticsProfile",
    "BinanceUsdmSimulationProfile",
    "BinanceUsdmExecutionAccountProfile",
    "BinanceUsdmResolvedProfile",
    "BinanceUsdmProfileCompositionFailureCode",
    "BinanceUsdmProfileCompositionFailure",
    "BinanceUsdmProfileCompositionOutcome",
    "BinanceUsdmProfileComposer",
)
ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "re",
    "typing",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "crypto_quant_trading",
    "crypto_quant_trading.profiles.binance_usdm",
    "execution",
    "financial_dispatch",
    "liquidation_audit",
    "ports",
    "resolution",
    "run_end",
    "slippage",
    "timeline",
}
FORBIDDEN_CALLS = {
    "connect",
    "open",
    "popen",
    "read_bytes",
    "read_text",
    "run",
    "system",
    "time",
    "urlopen",
    "write_bytes",
    "write_text",
}


def test_g10g_public_exports_are_frozen() -> None:
    module = importlib.import_module("crypto_quant_backtest")
    for name in PUBLIC_NAMES:
        assert name in module.__all__
        assert getattr(module, name) is not None


def test_g10g_production_composition_is_offline_and_allowlisted() -> None:
    source = COMPOSITION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    calls = {
        node.func.id
        if isinstance(node.func, ast.Name)
        else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert imports <= ALLOWED_IMPORTS
    assert not calls.intersection(FORBIDDEN_CALLS)
    for forbidden in (
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "MarketBundleReader",
        "DeterministicBarEngine",
        "AuditableBacktestRunner",
        "deployment_authorized=True",
    ):
        assert forbidden not in source


def test_generic_runtime_remains_binance_branchless() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "BinanceUsdm" not in source
        assert "binance_usdm_profile" not in source
