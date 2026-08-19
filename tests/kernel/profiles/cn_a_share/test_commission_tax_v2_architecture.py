from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import crypto_quant_trading
from crypto_quant_trading.profiles import cn_a_share

ROOT = Path(__file__).resolve().parents[4]
MODULE = (
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/commission_tax_v2.py"
)
V1_PREFIX = (
    "CnAShareBarLimitLiquidityEvaluator",
    "CnAShareBoard",
    "CnAShareCalendarDayKind",
    "CnAShareCashFeeRuleQuery",
    "CnAShareCashMarketFeePolicy",
    "CnAShareCashOrderRuleModel",
)
V2_EXPORTS = (
    "CnAShareExecutionAccessRoute",
    "CnAShareFeeProductClass",
    "CnAShareFeeAssessmentPurposeV2",
    "CnAShareFeeExecutionScopeV2",
    "CnAShareFeeExecutionSelectionV2",
    "CnAShareFeeExecutionAuthorityV2",
    "CnAShareFeeExecutionAuthorityFailureCodeV2",
    "CnAShareFeeExecutionAuthorityFailureV2",
    "CnAShareFeeExecutionBindingV2",
    "CnAShareFeeExecutionBindingFailureCodeV2",
    "CnAShareFeeExecutionBindingFailureV2",
    "CnAShareCashFeeRuleQueryV2",
    "CnAShareFeeQueryConstructionFailureCodeV2",
    "CnAShareFeeQueryConstructionFailureV2",
    "CnAShareMarketFeeBandV2",
    "CnAShareMarketFeeRuleBookV2",
    "CnAShareStampDutyBandV2",
    "CnAShareStampDutyRuleBookV2",
    "CnAShareMarketFeeRuleResolutionV2",
    "CnAShareStampDutyRuleResolutionV2",
    "CnAShareFeeRuleFailureCodeV2",
    "CnAShareFeeRuleFailureV2",
    "CnAShareCashMarketFeePolicyV2",
    "CnAShareCashStampDutyTaxPolicyV2",
    "CnAShareFeeReservationBufferV2",
    "CnAShareDomesticOrdinaryFeeProjectionV2",
    "CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2",
    "CnAShareDomesticOrdinaryFeeProjectionFailureV2",
    "create_cn_a_share_fee_execution_authority_v2",
    "bind_cn_a_share_fee_execution_v2",
    "project_cn_a_share_domestic_ordinary_fee_rules_v2",
)
LOCKS = {
    "tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json": "3ef26743bc9cebfe546f77812c6773cbdf3353e0337d03ed512d5f1c396f702b",
    "tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json": "aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f",
    "tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json": "08358c1c0d2144fb23c1b1c8862fa6c879bd285533e5fa415e5cc0273013e905",
    "tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json": "19017a07fbfd2da954483648fb168d87212f88e92fccca7c28fb0a514b202515",
    "tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/publication.expected.json": "7a95188cf05d401fcaed80b548f82f22f0b9bc23f6423c6ff1190de775291f7d",
}


def test_v2_exports_are_append_only_and_not_root_reexports() -> None:
    assert tuple(cn_a_share.__all__[: len(V1_PREFIX)]) == V1_PREFIX
    assert tuple(cn_a_share.__all__[-len(V2_EXPORTS) :]) == V2_EXPORTS
    assert all(not hasattr(crypto_quant_trading, name) for name in V2_EXPORTS)


def test_v2_kernel_has_only_kernel_imports() -> None:
    tree = ast.parse(MODULE.read_text())
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        "runtime" in module or "builder" in module or "provider" in module
        for module in modules
    )
    assert not {"pathlib", "os", "io", "socket", "subprocess"} & modules


def test_v1_fixture_bytes_are_frozen() -> None:
    assert {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in LOCKS
    } == LOCKS
