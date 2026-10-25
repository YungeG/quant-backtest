"""Exact additive economic leaf and Runtime transport boundaries."""
import ast
import importlib
from pathlib import Path

import crypto_quant_backtest as bt
from crypto_quant_backtest.execution_inputs import _DecodedExecutionInputBundleV9

ROOT = Path(__file__).resolve().parents[2]
KERNEL_NAMES = (
    "CnAShareCashDividendClaimV1", "CnAShareCashDividendStateV1", "CnASharePortfolioEconomicProjectionInputsV1",
    "CnAShareEconomicCashRowV1", "CnASharePortfolioEconomicProjectionV1", "CnAShareEconomicProjectionFailureCodeV1",
    "CnAShareEconomicProjectionFailureV1", "CnAShareEconomicProjectionOutcomeV1", "project_cn_a_share_portfolio_economic_state_v1",
    "CnAShareCashDividendTaxPolicyV1", "CnAShareCashDividendActionV1", "CnAShareCashDividendActionSetV1",
    "CnAShareCashDividendHistoryInputsV1", "verify_cn_a_share_cash_dividend_history_v1", "CnAShareCashDividendTransitionInputsV1",
    "CnAShareCashDividendTransitionV1", "CnAShareCashDividendTransitionFailureCodeV1", "CnAShareCashDividendTransitionFailureV1",
    "CnAShareCashDividendTransitionOutcomeV1", "transition_cn_a_share_cash_dividend_v1",
)
RUNTIME_NAMES = (
    "CnASharePortfolioEconomicDevelopmentInputsV1", "CnASharePortfolioEconomicOpeningTermsV1",
    "prepare_cn_a_share_portfolio_economic_development_backtest", "CnASharePortfolioEconomicDailyNavMetricProfileV1",
    "CnASharePortfolioEconomicDailyNavPointV1", "CnASharePortfolioEconomicDailyNavAnalysisV1",
    "CnASharePortfolioEconomicDailyNavAnalysisRefV1", "CnASharePortfolioEconomicDailyNavAnalysisRuntimeV1",
)


def test_exact_public_economic_leaf_and_runtime_identities():
    leaf = importlib.import_module("crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1")
    generic = importlib.import_module("crypto_quant_trading")
    assert tuple(leaf.__all__) == KERNEL_NAMES
    for name in KERNEL_NAMES:
        value = getattr(leaf, name)
        assert getattr(importlib.import_module(value.__module__), name) is value
        assert not hasattr(generic, name)
    for name in RUNTIME_NAMES:
        value = getattr(bt, name)
        assert name in bt.__all__ and getattr(importlib.import_module(value.__module__), name) is value
    assert _DecodedExecutionInputBundleV9.__bases__ == (object,)
    assert len(_DecodedExecutionInputBundleV9.__dataclass_fields__) == 8


def test_economic_values_has_no_top_level_transport_cycle_or_contextual_engine():
    path = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_portfolio_economic_values_v1.py"
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or "execution_inputs" not in node.module
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or "economic_engine" not in node.module
            assert node.module is None or "publisher" not in node.module
    for path in (ROOT / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share").glob("cash_dividend_*v1.py"):
        assert "crypto_quant_backtest" not in path.read_text()
