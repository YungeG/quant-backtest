from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILES = (
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/binance_usdm/instrument_metadata.py",
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/binance_usdm/order_rules.py",
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/binance_usdm/margin_tiers.py",
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/binance_usdm/price_streams.py",
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/binance_usdm/funding_sources.py",
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/binance_usdm/account_profile.py",
)
GENERIC_MODULES = (
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/ledger.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/margin.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/account_margin.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/fee_reservations.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/fees.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/market_rules.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/ports.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/pretrade_risk.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/composition.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "aiohttp",
    "boto",
    "ccxt",
    "http",
    "pandas",
    "requests",
    "socket",
    "sqlalchemy",
    "subprocess",
    "urllib",
    "websockets",
)
ACCOUNT_PROFILE_ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "re",
    "crypto_quant_domain",
    "crypto_quant_trading.fee_reservations",
    "crypto_quant_trading.fees",
    "crypto_quant_trading.margin",
    "crypto_quant_trading.ports",
    "crypto_quant_trading.pretrade_risk",
    "instrument_metadata",
}
FORBIDDEN_CALLS = {
    "connect",
    "open",
    "popen",
    "read_text",
    "read_bytes",
    "run",
    "system",
    "time",
    "urlopen",
    "write_text",
    "write_bytes",
}
PUBLIC_NAMES = (
    "BINANCE_USDM_OPEN_ENDED_DELIVERY_AT",
    "BinanceUsdmContractStatus",
    "BinanceUsdmInstrumentMetadataSourceRef",
    "BinanceUsdmInstrumentMetadataRevision",
    "BinanceUsdmInstrumentMetadataQuery",
    "BinanceUsdmListingInterval",
    "BinanceUsdmLinearContractMetadata",
    "BinanceUsdmInstrumentMetadataResolution",
    "BinanceUsdmInstrumentMetadataFailureCode",
    "BinanceUsdmInstrumentMetadataFailure",
    "BinanceUsdmInstrumentMetadataOutcome",
    "BinanceUsdmInstrumentModel",
    "BinanceUsdmOrderAdmissionMode",
    "BinanceUsdmDeferredRuleKey",
    "BinanceUsdmOrderRuleSourceRef",
    "BinanceUsdmOrderRuleBand",
    "BinanceUsdmOrderRuleBook",
    "BinanceUsdmOrderRuleQuery",
    "BinanceUsdmOrderRuleResolution",
    "BinanceUsdmOrderRuleFailureCode",
    "BinanceUsdmOrderRuleFailure",
    "BinanceUsdmOrderRuleOutcome",
    "BinanceUsdmOrderRuleModel",
    "BinanceUsdmMarginTierScope",
    "BinanceUsdmMarginTierSourceRef",
    "BinanceUsdmMarginTierBracket",
    "BinanceUsdmMarginTierBand",
    "BinanceUsdmMarginTierRuleBook",
    "BinanceUsdmMarginTierQuery",
    "BinanceUsdmMarginTierResolution",
    "BinanceUsdmMarginTierFailureCode",
    "BinanceUsdmMarginTierFailure",
    "BinanceUsdmMarginTierOutcome",
    "BinanceUsdmMarginTierModel",
    "BinanceUsdmPriceSourceKind",
    "BinanceUsdmPriceSourceRef",
    "BinanceUsdmAggregateTradePrice",
    "BinanceUsdmMarkPriceKline",
    "BinanceUsdmPriceStreamCoverage",
    "BinanceUsdmHistoricalPriceBook",
    "BinanceUsdmPricePurposeQuery",
    "BinanceUsdmLiquidationMarkBar",
    "BinanceUsdmPricePurposeResolution",
    "BinanceUsdmPriceStreamFailureCode",
    "BinanceUsdmPriceStreamFailure",
    "BinanceUsdmPriceStreamOutcome",
    "BinanceUsdmPriceStreamModel",
    "BinanceUsdmFundingSourceRef",
    "BinanceUsdmFundingRateRecord",
    "BinanceUsdmFundingCoverage",
    "BinanceUsdmHistoricalFundingBook",
    "BinanceUsdmFundingSourceQuery",
    "BinanceUsdmFundingSourceResolution",
    "BinanceUsdmFundingSourceFailureCode",
    "BinanceUsdmFundingSourceFailure",
    "BinanceUsdmFundingSourceOutcome",
    "BinanceUsdmFundingSourceModel",
    "BinanceUsdmAccountSourceKind",
    "BinanceUsdmAccountProfileSourceRef",
    "BinanceUsdmAccountProfileScope",
    "BinanceUsdmAccountProfileBand",
    "BinanceUsdmHistoricalAccountProfileBook",
    "BinanceUsdmAccountProfileQuery",
    "BinanceUsdmAccountProfileResolution",
    "BinanceUsdmAccountProfileFailureCode",
    "BinanceUsdmAccountProfileFailure",
    "BinanceUsdmAccountProfileOutcome",
    "BinanceUsdmAccountProfileModel",
)


def test_binance_usdm_profile_exports_the_frozen_public_seam() -> None:
    module = importlib.import_module("crypto_quant_trading.profiles.binance_usdm")

    assert module.__all__ == list(PUBLIC_NAMES)
    for name in PUBLIC_NAMES:
        assert getattr(module, name) is not None


def test_binance_usdm_adapters_are_offline_and_rule_neutral() -> None:
    for path in PROFILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)

        assert not {
            value
            for value in imports
            if value.startswith(FORBIDDEN_IMPORT_PREFIXES)
        }
        assert not calls.intersection(FORBIDDEN_CALLS)
        for forbidden in (
            "pricePrecision",
            "quantityPrecision",
            "tickSize",
            "stepSize",
            "minNotional",
            "filesystem",
            "wall_clock",
            "deployment_authorized",
        ):
            assert forbidden not in source


def test_binance_usdm_account_profile_has_exact_import_allowlist() -> None:
    path = PROFILES[-1]
    tree = ast.parse(path.read_text(encoding="utf-8"))
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
    assert imports <= ACCOUNT_PROFILE_ALLOWED_IMPORTS


def test_generic_kernel_and_runtime_do_not_branch_on_binance_metadata() -> None:
    for path in GENERIC_MODULES:
        source = path.read_text(encoding="utf-8")
        assert "BinanceUsdm" not in source
        assert "binance_usdm.instrument_metadata" not in source
        assert "binance_usdm.order_rules" not in source
        assert "binance_usdm.margin_tiers" not in source
        assert "binance_usdm.price_streams" not in source
        assert "binance_usdm.funding_sources" not in source
        assert "binance_usdm.account_profile" not in source
