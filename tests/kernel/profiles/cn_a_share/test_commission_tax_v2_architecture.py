from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

import crypto_quant_trading
from crypto_quant_trading.profiles import cn_a_share

ROOT = Path(__file__).resolve().parents[4]
MODULE = (
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/commission_tax_v2.py"
)
V1_PREFIX = (
    "CnAShareBarLimitLiquidityEvaluator", "CnAShareBoard", "CnAShareCalendarDayKind", "CnAShareCashFeeRuleQuery", "CnAShareCashMarketFeePolicy", "CnAShareCashOrderRuleModel", "CnAShareCashPaymentEvidence", "CnAShareCashPaymentOutcome", "CnAShareCashPaymentRequest", "CnAShareCashStampDutyTaxPolicy", "CnAShareCashQuantityLatticeModel", "CnAShareCashSettlementModel", "CnAShareCashSessionModel", "CnAShareCorporateActionAnnouncementCandidate", "CnAShareCorporateActionDeliveryStatus", "CnAShareCorporateActionTaxDisposition", "CnAShareCorporateActionTranslationFailure", "CnAShareCorporateActionTranslationFailureCode", "CnAShareShareDeliveryEvidence", "CnAShareShareDeliveryOutcome", "CnAShareShareDeliveryRequest", "translate_corporate_action_cash_payment", "translate_corporate_action_share_delivery", "CnAShareCorporateActionAnnouncementStatus", "CnAShareCorporateActionEntitlement", "CnAShareCorporateActionEntitlementBand", "CnAShareCorporateActionEntitlementModel", "CnAShareCorporateActionEntitlementQuery", "CnAShareCorporateActionEntitlementRuleBook", "CnAShareCorporateActionFailure", "CnAShareCorporateActionFailureCode", "CnAShareCorporateActionSourceRef", "CnAShareFrozenCalendar", "CnAShareFrozenCalendarDay", "CnAShareFeeReservationBuffer", "CnAShareFeeRuleFailure", "CnAShareFeeRuleFailureCode", "CnAShareFeeRuleSourceRef", "CnAShareFeeTradeMechanism", "CnAShareInstrumentRuleContext", "CnAShareLimitLiquidityDecision", "CnAShareLimitLiquidityDecisionCode", "CnAShareLimitLiquidityInput", "CnAShareListingPhase", "CnAShareMarketFeeBand", "CnAShareMarketFeeRuleBook", "CnAShareMarketFeeRuleResolution", "CnAShareOrderRuleBand", "CnAShareOrderRuleBook", "CnAShareOrderRuleFailure", "CnAShareOrderRuleFailureCode", "CnAShareOpenObservationState", "CnAShareOrderRuleQuery", "CnAShareOrderRuleResolution", "CnAShareOrderRuleResolutionKind", "CnASharePreviousCloseEvidence", "CnAShareSessionFailure", "CnAShareSessionFailureCode", "CnAShareSessionPhase", "CnAShareSessionQuery", "CnAShareSessionResolution", "CnAShareQuantityLatticeFailure", "CnAShareQuantityLatticeFailureCode", "CnAShareQuantityLatticeQuery", "CnAShareQuantityLatticeResolution", "CnAShareRegisteredPositionSnapshot", "CnAShareRiskClass", "CnAShareRuleSourceRef", "CnAShareSettlementFailure", "CnAShareSettlementFailureCode", "CnAShareSettlementQuery", "CnAShareSettlementResolution", "CnAShareStampDutyBand", "CnAShareStampDutyRuleBook", "CnAShareStampDutyRuleResolution", "CnAShareTradeStatus", "CnAShareTradeStatusEvidence",
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


def test_v2_reflection_freezes_enum_wires_dataclass_shapes_and_positional_apis() -> None:
    module = cn_a_share.commission_tax_v2
    assert {
        "CnAShareExecutionAccessRoute": [(x.name, x.value) for x in module.CnAShareExecutionAccessRoute],
        "CnAShareFeeProductClass": [(x.name, x.value) for x in module.CnAShareFeeProductClass],
        "CnAShareFeeAssessmentPurposeV2": [(x.name, x.value) for x in module.CnAShareFeeAssessmentPurposeV2],
        "CnAShareFeeExecutionAuthorityFailureCodeV2": [(x.name, x.value) for x in module.CnAShareFeeExecutionAuthorityFailureCodeV2],
        "CnAShareFeeExecutionBindingFailureCodeV2": [(x.name, x.value) for x in module.CnAShareFeeExecutionBindingFailureCodeV2],
        "CnAShareFeeQueryConstructionFailureCodeV2": [(x.name, x.value) for x in module.CnAShareFeeQueryConstructionFailureCodeV2],
        "CnAShareFeeRuleFailureCodeV2": [(x.name, x.value) for x in module.CnAShareFeeRuleFailureCodeV2],
        "CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2": [(x.name, x.value) for x in module.CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2],
    } == {
        "CnAShareExecutionAccessRoute": [("DOMESTIC", "domestic"), ("NORTHBOUND_STOCK_CONNECT", "northbound_stock_connect")],
        "CnAShareFeeProductClass": [("ORDINARY_A_SHARE", "ordinary_a_share"), ("PREFERRED_STOCK", "preferred_stock"), ("ETF", "etf")],
        "CnAShareFeeAssessmentPurposeV2": [("RESERVATION", "reservation"), ("FINAL_FILL", "final_fill")],
        "CnAShareFeeExecutionAuthorityFailureCodeV2": [("SCOPE_SELECTION_MISMATCH", "scope_selection_mismatch"), ("RULE_BOOK_SCOPE_MISMATCH", "rule_book_scope_mismatch"), ("COMPONENT_REF_MISMATCH", "component_ref_mismatch")],
        "CnAShareFeeExecutionBindingFailureCodeV2": [("AUTHORITY_SCOPE_MISMATCH", "authority_scope_mismatch"), ("ORDER_ACCOUNT_MISMATCH", "order_account_mismatch"), ("ORDER_VENUE_MISMATCH", "order_venue_mismatch"), ("ORDER_INSTRUMENT_MISMATCH", "order_instrument_mismatch"), ("ORDER_SIDE_MISMATCH", "order_side_mismatch"), ("ORDER_CONTEXT_MISMATCH", "order_context_mismatch")],
        "CnAShareFeeQueryConstructionFailureCodeV2": [("AUTHORITY_BINDING_MISMATCH", "authority_binding_mismatch"), ("RESERVATION_CONTEXT_MISMATCH", "reservation_context_mismatch"), ("MISSING_FILL", "missing_fill"), ("FILL_ORDER_MISMATCH", "fill_order_mismatch"), ("FILL_ACCOUNT_MISMATCH", "fill_account_mismatch"), ("FILL_VENUE_MISMATCH", "fill_venue_mismatch"), ("FILL_INSTRUMENT_MISMATCH", "fill_instrument_mismatch"), ("FILL_SIDE_MISMATCH", "fill_side_mismatch"), ("EXECUTION_TIME_MISMATCH", "execution_time_mismatch")],
        "CnAShareFeeRuleFailureCodeV2": [("EXECUTION_AUTHORITY_MISMATCH", "execution_authority_mismatch"), ("QUERY_PROVENANCE_MISMATCH", "query_provenance_mismatch"), ("RULE_BOOK_SCOPE_MISMATCH", "rule_book_scope_mismatch"), ("MISSING_RULE_INTERVAL", "missing_rule_interval"), ("OVERLAPPING_RULE_INTERVALS", "overlapping_rule_intervals")],
        "CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2": [("NON_XSHE_MARKET_SOURCE", "non_xshe_market_source"), ("NON_XSHE_STAMP_DUTY_SOURCE", "non_xshe_stamp_duty_source"), ("MARKET_SOURCE_INTERVAL_INVALID", "market_source_interval_invalid"), ("STAMP_DUTY_SOURCE_INTERVAL_INVALID", "stamp_duty_source_interval_invalid"), ("MARKET_SOURCE_ECONOMIC_INVALID", "market_source_economic_invalid"), ("STAMP_DUTY_SOURCE_ECONOMIC_INVALID", "stamp_duty_source_economic_invalid")],
    }
    classes = tuple(getattr(module, name) for name in V2_EXPORTS if isinstance(getattr(module, name, None), type) and dataclasses.is_dataclass(getattr(module, name)))
    for cls in classes:
        assert getattr(cls, "__dataclass_params__").frozen
        assert hasattr(cls, "__slots__")
        signature = inspect.signature(cls)
        assert all(parameter.default is inspect.Parameter.empty for parameter in signature.parameters.values())
    expected_fields = {
        "CnAShareFeeExecutionScopeV2": "account_id venue_id instrument instrument_id instrument_type quote_currency_id settlement_currency_id trade_mechanism coverage_from coverage_to_exclusive allowed_order_sides access_route fee_product_class",
        "CnAShareFeeExecutionSelectionV2": "selection_key selection_version access_route fee_product_class market_fee_rule_book market_fee_rule_book_hash stamp_duty_rule_book stamp_duty_rule_book_hash market_fee_component_ref stamp_duty_component_ref",
        "CnAShareFeeExecutionAuthorityV2": "authority_key authority_version scope scope_hash selection selection_hash access_route fee_product_class market_fee_rule_book market_fee_rule_book_hash stamp_duty_rule_book stamp_duty_rule_book_hash market_fee_component_ref stamp_duty_component_ref",
        "CnAShareFeeExecutionBindingV2": "authority authority_hash order order_hash order_id account_id venue_id instrument_id side order_effective_at",
        "CnAShareCashFeeRuleQueryV2": "authority authority_hash execution_binding binding_hash purpose fill fill_hash fill_id",
        "CnAShareMarketFeeRuleResolutionV2": "authority authority_hash query query_hash binding_hash order_id order_hash fill fill_hash fill_id side effective_at active_band active_band_hash reservation_charge_rules final_fill_charge_rules final_order_not_applicable_rules",
        "CnAShareStampDutyRuleResolutionV2": "authority authority_hash query query_hash binding_hash order_id order_hash fill fill_hash fill_id side effective_at active_band active_band_hash reservation_charge_rule final_fill_charge_rule final_order_not_applicable_rule",
        "CnAShareFeeReservationBufferV2": "market_resolution tax_resolution maximum_fill_count market_charge_rule tax_charge_rule",
        "CnAShareMarketFeeBandV2": "venue_id effective_from effective_to_exclusive handling_applies handling_rate handling_source_refs regulatory_applies regulatory_rate regulatory_source_refs chinaclear_transfer_applies chinaclear_transfer_rate chinaclear_transfer_source_refs hkscc_transfer_applies hkscc_transfer_rate hkscc_transfer_source_refs",
        "CnAShareStampDutyBandV2": "venue_id effective_from effective_to_exclusive applies_to_sell rate source_refs",
        "CnAShareMarketFeeRuleBookV2": "rule_book_key rule_book_version access_route fee_product_class bands",
        "CnAShareStampDutyRuleBookV2": "rule_book_key rule_book_version access_route fee_product_class bands",
        "CnAShareFeeExecutionAuthorityFailureV2": "scope scope_hash selection selection_hash code subject_ids",
        "CnAShareFeeExecutionBindingFailureV2": "authority authority_hash scope scope_hash order order_hash code subject_ids",
        "CnAShareFeeQueryConstructionFailureV2": "authority authority_hash execution_binding binding_hash purpose fill fill_hash code subject_ids",
        "CnAShareFeeRuleFailureV2": "query query_hash code subject_ids",
        "CnAShareCashMarketFeePolicyV2": "authority authority_hash assessment_scale",
        "CnAShareCashStampDutyTaxPolicyV2": "authority authority_hash assessment_scale",
        "CnAShareDomesticOrdinaryFeeProjectionFailureV2": "market_rule_book market_rule_book_hash stamp_duty_rule_book stamp_duty_rule_book_hash code subject_ids",
        "CnAShareDomesticOrdinaryFeeProjectionV2": "algorithm_id source_market_rule_book source_market_rule_book_hash source_stamp_duty_rule_book source_stamp_duty_rule_book_hash access_route fee_product_class market_fee_rule_book market_fee_rule_book_hash stamp_duty_rule_book stamp_duty_rule_book_hash",
    }
    assert {name: " ".join(field.name for field in dataclasses.fields(getattr(module, name))) for name in expected_fields} == expected_fields
    for callable_ in (module.create_cn_a_share_fee_execution_authority_v2, module.bind_cn_a_share_fee_execution_v2, module.project_cn_a_share_domestic_ordinary_fee_rules_v2, module.CnAShareCashFeeRuleQueryV2.for_reservation, module.CnAShareCashFeeRuleQueryV2.for_final_fill, module.CnAShareCashMarketFeePolicyV2.assess_fees, module.CnAShareCashStampDutyTaxPolicyV2.assess_taxes):
        assert all(parameter.kind is inspect.Parameter.POSITIONAL_ONLY for parameter in inspect.signature(callable_).parameters.values())


def test_v2_ast_has_no_io_dynamic_loader_or_wall_clock_and_project_checker_passes(tmp_path: Path) -> None:
    tree = ast.parse(MODULE.read_text())
    imports = [(node.module or "") for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names]
    forbidden = ("runtime", "builder", "provider", "pathlib", "os", "io", "socket", "subprocess", "importlib", "datetime", "time", "sqlite", "requests")
    assert not any(part in module.split(".") for module in imports for part in forbidden)
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    attributes = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not {"__import__", "eval", "exec", "open"} & calls
    assert not {"import_module", "spec_from_file_location", "now", "utcnow", "time", "read_text", "read_bytes", "write_text", "write_bytes"} & attributes
    report = tmp_path / "imports.json"
    completed = subprocess.run([sys.executable, str(ROOT / "tools/architecture/check_import_boundaries.py"), "--root", str(ROOT), "--policy", str(ROOT / "architecture/import-boundaries.toml"), "--report", str(report)], check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report.exists()
