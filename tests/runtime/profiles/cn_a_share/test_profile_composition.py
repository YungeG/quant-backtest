from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
import inspect
from typing import get_type_hints

import pytest

import crypto_quant_backtest
from crypto_quant_backtest import (
    BacktestProfileRegistry,
    ExecutionAccountProfileRegistration,
    FinancialDispatcherSpec,
    MarketSemanticsProfileRegistration,
    SimulationComponentRef,
    SimulationProfileRegistration,
    TimelineWindow,
)
from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareAccountScopeDeclaration,
    CnAShareAnnouncementRevisionSetDeclaration,
    CnAShareExecutionAccountProfile,
    CnAShareIdentityHistoryDeclaration,
    CnAShareInstrumentScopeDeclaration,
    CnAShareMarketSemanticsProfile,
    CnAShareProfileComposer,
    CnAShareProfileCompositionFailure,
    CnAShareProfileCompositionFailureCode,
    CnAShareProfileCompositionOutcome,
    CnAShareProfileCompositionRequest,
    CnAShareRegisterRevisionSetDeclaration,
    CnAShareResolvedProfile,
    CnAShareSimulationProfile,
)
from crypto_quant_domain import (
    InstrumentDefinition,
    InstrumentId,
    PositionBalanceKey,
    SimulationInstant,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import AccountRiskPolicy, ProfileComponentRef, ProfilePortType
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashPaymentRequest,
    CnAShareCorporateActionEntitlement,
    CnAShareCorporateActionEntitlementRuleBook,
    CnAShareFrozenCalendar,
    CnAShareInstrumentRuleContext,
    CnAShareMarketFeeRuleBook,
    CnAShareOrderRuleBook,
    CnAShareShareDeliveryRequest,
    CnAShareStampDutyRuleBook,
)
from tests.support.cn_a_share import build_cn_a_share_resolved_request


_PUBLIC_NAMES = (
    "CnAShareInstrumentScopeDeclaration",
    "CnAShareAccountScopeDeclaration",
    "CnAShareAnnouncementRevisionSetDeclaration",
    "CnAShareRegisterRevisionSetDeclaration",
    "CnAShareIdentityHistoryDeclaration",
    "CnAShareProfileCompositionRequest",
    "CnAShareMarketSemanticsProfile",
    "CnAShareSimulationProfile",
    "CnAShareExecutionAccountProfile",
    "CnAShareResolvedProfile",
    "CnAShareProfileCompositionFailureCode",
    "CnAShareProfileCompositionFailure",
    "CnAShareProfileCompositionOutcome",
    "CnAShareProfileComposer",
)
_FAILURE_ORDER = (
    "missing_instrument_scope",
    "missing_account_scope",
    "missing_announcement_revision_set",
    "missing_register_revision_set",
    "missing_identity_history",
    "instrument_scope_mismatch",
    "account_scope_mismatch",
    "authority_context_mismatch",
    "revision_closure_mismatch",
    "cross_query_identity_conflict",
    "timeline_coverage_mismatch",
    "evidence_not_available",
    "unsupported_tax_disposition",
    "unsupported_xshg_share_delivery",
    "component_identity_conflict",
)
_TYPE_LITERALS = {
    CnAShareInstrumentScopeDeclaration: "cn_a_share_instrument_scope_declaration",
    CnAShareAccountScopeDeclaration: "cn_a_share_account_scope_declaration",
    CnAShareAnnouncementRevisionSetDeclaration: "cn_a_share_announcement_revision_set_declaration",
    CnAShareRegisterRevisionSetDeclaration: "cn_a_share_register_revision_set_declaration",
    CnAShareIdentityHistoryDeclaration: "cn_a_share_identity_history_declaration",
    CnAShareProfileCompositionRequest: "cn_a_share_profile_composition_request",
    CnAShareMarketSemanticsProfile: "cn_a_share_market_semantics_profile",
    CnAShareSimulationProfile: "cn_a_share_simulation_profile",
    CnAShareExecutionAccountProfile: "cn_a_share_execution_account_profile",
    CnAShareResolvedProfile: "cn_a_share_resolved_profile",
    CnAShareProfileCompositionFailure: "cn_a_share_profile_composition_failure",
    CnAShareProfileCompositionOutcome: "cn_a_share_profile_composition_outcome",
}


def _assert_equal(actual: object, expected: object) -> None:
    assert actual == expected


def _field_names(value: type[object]) -> tuple[str, ...]:
    assert is_dataclass(value)
    assert hasattr(value, "__slots__")
    return tuple(field.name for field in fields(value))


def test_public_api_and_declaration_schemas_are_exact() -> None:
    for name in _PUBLIC_NAMES:
        assert getattr(crypto_quant_backtest, name) is globals()[name]
    _assert_equal(_field_names(CnAShareInstrumentScopeDeclaration), (
        "instrument", "rule_context", "coverage_from", "coverage_to_exclusive", "available_at",
        "is_ordinary_domestic_a_share", "is_standard_cash_auction", "is_b_or_h_share",
        "is_fund_or_bond", "is_stock_connect", "has_lending_or_repo", "has_pledge_or_freeze",
        "is_restricted_or_pre_ipo", "has_differential_distribution", "has_issuer_self_distribution",
        "source_snapshot_hash", "source_manifest_hash",
    ))
    assert get_type_hints(CnAShareInstrumentScopeDeclaration) == {
        "instrument": InstrumentDefinition, "rule_context": CnAShareInstrumentRuleContext,
        "coverage_from": UtcInstant, "coverage_to_exclusive": UtcInstant,
        "available_at": SimulationInstant, "is_ordinary_domestic_a_share": bool,
        "is_standard_cash_auction": bool, "is_b_or_h_share": bool, "is_fund_or_bond": bool,
        "is_stock_connect": bool, "has_lending_or_repo": bool, "has_pledge_or_freeze": bool,
        "is_restricted_or_pre_ipo": bool, "has_differential_distribution": bool,
        "has_issuer_self_distribution": bool, "source_snapshot_hash": str, "source_manifest_hash": str,
    }
    _assert_equal(_field_names(CnAShareAccountScopeDeclaration), (
        "account_id", "venue_id", "coverage_from", "coverage_to_exclusive", "available_at",
        "is_cash_account", "is_domestic_access", "has_margin_or_short_permission",
        "has_stock_connect_permission", "authorizes_available_margin_use", "source_snapshot_hash",
        "source_manifest_hash",
    ))
    assert get_type_hints(CnAShareAccountScopeDeclaration) == {
        "account_id": str, "venue_id": VenueId, "coverage_from": UtcInstant,
        "coverage_to_exclusive": UtcInstant, "available_at": SimulationInstant,
        "is_cash_account": bool, "is_domestic_access": bool,
        "has_margin_or_short_permission": bool, "has_stock_connect_permission": bool,
        "authorizes_available_margin_use": bool, "source_snapshot_hash": str,
        "source_manifest_hash": str,
    }
    revision_chain_type = tuple[tuple[str, str | None, str], ...]
    _assert_equal(_field_names(CnAShareAnnouncementRevisionSetDeclaration), (
        "venue_id", "instrument_id", "corporate_action_id", "revision_chain", "terminal_revision_id",
        "is_cancelled", "coverage_from", "coverage_to_exclusive", "available_at",
        "source_snapshot_hash", "source_manifest_hash",
    ))
    assert get_type_hints(CnAShareAnnouncementRevisionSetDeclaration) == {
        "venue_id": VenueId, "instrument_id": InstrumentId, "corporate_action_id": str,
        "revision_chain": revision_chain_type, "terminal_revision_id": str, "is_cancelled": bool,
        "coverage_from": UtcInstant, "coverage_to_exclusive": UtcInstant,
        "available_at": SimulationInstant, "source_snapshot_hash": str, "source_manifest_hash": str,
    }
    _assert_equal(_field_names(CnAShareRegisterRevisionSetDeclaration), (
        "account_id", "position_key", "register_series_id", "revision_chain", "terminal_revision_id",
        "coverage_from", "coverage_to_exclusive", "available_at", "source_snapshot_hash",
        "source_manifest_hash",
    ))
    assert get_type_hints(CnAShareRegisterRevisionSetDeclaration) == {
        "account_id": str, "position_key": PositionBalanceKey, "register_series_id": str,
        "revision_chain": revision_chain_type, "terminal_revision_id": str,
        "coverage_from": UtcInstant, "coverage_to_exclusive": UtcInstant,
        "available_at": SimulationInstant, "source_snapshot_hash": str, "source_manifest_hash": str,
    }
    identity_tuple_type = tuple[tuple[str, str], ...]
    _assert_equal(_field_names(CnAShareIdentityHistoryDeclaration), (
        "corporate_action_hashes", "register_snapshot_hashes", "register_revision_hashes",
        "coverage_from", "coverage_to_exclusive", "available_at", "source_snapshot_hash",
        "source_manifest_hash",
    ))
    assert get_type_hints(CnAShareIdentityHistoryDeclaration) == {
        "corporate_action_hashes": identity_tuple_type,
        "register_snapshot_hashes": identity_tuple_type,
        "register_revision_hashes": identity_tuple_type,
        "coverage_from": UtcInstant, "coverage_to_exclusive": UtcInstant,
        "available_at": SimulationInstant, "source_snapshot_hash": str, "source_manifest_hash": str,
    }
    for value in (
        CnAShareInstrumentScopeDeclaration, CnAShareAccountScopeDeclaration,
        CnAShareAnnouncementRevisionSetDeclaration, CnAShareRegisterRevisionSetDeclaration,
        CnAShareIdentityHistoryDeclaration,
    ):
        assert isinstance(inspect.getattr_static(value, "declaration_hash"), property)


def test_request_result_failure_and_outcome_schemas_are_exact() -> None:
    _assert_equal(_field_names(CnAShareProfileCompositionRequest), (
        "instrument_scope", "account_scope", "announcement_revision_set", "register_revision_set",
        "identity_history", "calendar", "order_rule_book", "market_fee_rule_book",
        "stamp_duty_rule_book", "corporate_action_rule_book", "corporate_action_entitlements",
        "cash_payment_requests", "share_delivery_requests", "timeline_window", "composed_at",
    ))
    assert get_type_hints(CnAShareProfileCompositionRequest) == {
        "instrument_scope": CnAShareInstrumentScopeDeclaration | None,
        "account_scope": CnAShareAccountScopeDeclaration | None,
        "announcement_revision_set": CnAShareAnnouncementRevisionSetDeclaration | None,
        "register_revision_set": CnAShareRegisterRevisionSetDeclaration | None,
        "identity_history": CnAShareIdentityHistoryDeclaration | None,
        "calendar": CnAShareFrozenCalendar, "order_rule_book": CnAShareOrderRuleBook,
        "market_fee_rule_book": CnAShareMarketFeeRuleBook,
        "stamp_duty_rule_book": CnAShareStampDutyRuleBook,
        "corporate_action_rule_book": CnAShareCorporateActionEntitlementRuleBook,
        "corporate_action_entitlements": tuple[CnAShareCorporateActionEntitlement, ...],
        "cash_payment_requests": tuple[CnAShareCashPaymentRequest, ...],
        "share_delivery_requests": tuple[CnAShareShareDeliveryRequest, ...],
        "timeline_window": TimelineWindow, "composed_at": SimulationInstant,
    }
    _assert_equal(_field_names(CnAShareMarketSemanticsProfile), (
        "model_digest", "source_manifest_hash", "component_manifest", "financial_dispatcher_spec",
        "profile_key", "profile_version",
    ))
    assert get_type_hints(CnAShareMarketSemanticsProfile) == {
        "model_digest": str, "source_manifest_hash": str,
        "component_manifest": tuple[ProfileComponentRef, ...],
        "financial_dispatcher_spec": FinancialDispatcherSpec, "profile_key": str,
        "profile_version": int,
    }
    _assert_equal(_field_names(CnAShareSimulationProfile), (
        "model_digest", "component_manifest", "profile_key", "profile_version",
    ))
    assert get_type_hints(CnAShareSimulationProfile) == {
        "model_digest": str, "component_manifest": tuple[SimulationComponentRef, ...],
        "profile_key": str, "profile_version": int,
    }
    _assert_equal(_field_names(CnAShareExecutionAccountProfile), (
        "model_digest", "source_manifest_hash", "account_id", "venue_id", "account_risk_policy",
        "profile_key", "profile_version", "account_type", "margin_mode",
    ))
    assert get_type_hints(CnAShareExecutionAccountProfile) == {
        "model_digest": str, "source_manifest_hash": str, "account_id": str, "venue_id": str,
        "account_risk_policy": AccountRiskPolicy, "profile_key": str, "profile_version": int,
        "account_type": str, "margin_mode": str,
    }
    _assert_equal(_field_names(CnAShareResolvedProfile), (
        "request", "model_key", "model_version", "model_digest", "source_manifest",
        "account_risk_policy", "market_semantics", "simulation", "execution_account",
        "market_registration", "simulation_registration", "execution_account_registration",
        "profile_registry", "financial_dispatcher_spec", "limitations", "decision_grade_eligible",
        "profile_qualified", "deployment_authorized",
    ))
    assert get_type_hints(CnAShareResolvedProfile) == {
        "request": CnAShareProfileCompositionRequest, "model_key": str, "model_version": int,
        "model_digest": str, "source_manifest": tuple[str, ...],
        "account_risk_policy": AccountRiskPolicy,
        "market_semantics": CnAShareMarketSemanticsProfile,
        "simulation": CnAShareSimulationProfile,
        "execution_account": CnAShareExecutionAccountProfile,
        "market_registration": MarketSemanticsProfileRegistration,
        "simulation_registration": SimulationProfileRegistration,
        "execution_account_registration": ExecutionAccountProfileRegistration,
        "profile_registry": BacktestProfileRegistry,
        "financial_dispatcher_spec": FinancialDispatcherSpec,
        "limitations": tuple[str, ...], "decision_grade_eligible": bool,
        "profile_qualified": bool, "deployment_authorized": bool,
    }
    assert tuple(code.value for code in CnAShareProfileCompositionFailureCode) == _FAILURE_ORDER
    _assert_equal(_field_names(CnAShareProfileCompositionFailure), (
        "request", "model_digest", "code", "subject_ids",
    ))
    _assert_equal(_field_names(CnAShareProfileCompositionOutcome), (
        "request_hash", "model_digest", "result", "failure",
    ))
    signature = inspect.signature(CnAShareProfileComposer.compose)
    assert tuple(signature.parameters) == ("self", "request")
    assert signature.parameters["request"].kind is inspect.Parameter.POSITIONAL_ONLY


def test_success_reconstructs_all_profile_authorities() -> None:
    request = build_cn_a_share_resolved_request()
    outcome = CnAShareProfileComposer().compose(request)
    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.request_hash == request.request_hash
    assert outcome.model_digest == outcome.result.model_digest
    assert outcome.result.request == request
    assert outcome.result.financial_dispatcher_spec.dispatcher_key == "equity.cn_a_share.cash-financial-dispatch.v1"
    assert {ref.port_type for ref in outcome.result.market_semantics.component_manifest} == set(ProfilePortType)
    assert not outcome.result.decision_grade_eligible
    assert not outcome.result.profile_qualified
    assert not outcome.result.deployment_authorized
    values = (
        request.instrument_scope, request.account_scope, request.announcement_revision_set,
        request.register_revision_set, request.identity_history, request,
        outcome.result.market_semantics, outcome.result.simulation,
        outcome.result.execution_account, outcome.result, outcome,
    )
    for value in values:
        assert value is not None
        assert value.to_canonical_dict()["type"] == _TYPE_LITERALS[type(value)]


@pytest.mark.parametrize("code", tuple(CnAShareProfileCompositionFailureCode))
def test_every_failure_is_reachable_and_atomic(code: CnAShareProfileCompositionFailureCode) -> None:
    request = build_cn_a_share_resolved_request(failure_codes=(code,))
    outcome = CnAShareProfileComposer().compose(request)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is code
    assert outcome.failure.request == request
    assert outcome.failure.subject_ids == (code.value, request.request_hash)


def test_first_failure_precedence_is_stable_for_multi_defect_requests() -> None:
    codes = tuple(CnAShareProfileCompositionFailureCode)
    request = build_cn_a_share_resolved_request(failure_codes=(codes[-1], codes[8], codes[0]))
    outcome = CnAShareProfileComposer().compose(request)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is codes[0]


def test_failure_outcome_and_result_reject_forgery() -> None:
    failure_request = build_cn_a_share_resolved_request(
        failure_codes=(CnAShareProfileCompositionFailureCode.MISSING_ACCOUNT_SCOPE,)
    )
    failed = CnAShareProfileComposer().compose(failure_request)
    assert failed.failure is not None
    with pytest.raises(ValueError):
        replace(failed.failure, code=CnAShareProfileCompositionFailureCode.COMPONENT_IDENTITY_CONFLICT)
    with pytest.raises(ValueError):
        replace(failed, failure=None)
    success = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    assert success.result is not None
    with pytest.raises(ValueError):
        replace(success.result, deployment_authorized=True)
    with pytest.raises(ValueError):
        replace(success, failure=failed.failure)
