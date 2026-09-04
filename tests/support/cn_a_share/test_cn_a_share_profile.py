from __future__ import annotations

from dataclasses import fields, is_dataclass
import inspect

from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareProfileCompositionFailureCode,
    CnAShareProfileCompositionRequest,
    CnAShareResolvedProfile,
)
from tests.support.cn_a_share import (
    CnAShareDevelopmentFinancialDispatcher,
    CnAShareDevelopmentJourneyResult,
    build_cn_a_share_execution_case,
    build_cn_a_share_resolved_request,
    run_cn_a_share_development_journey,
)


def _assert_equal(actual: object, expected: object) -> None:
    assert actual == expected


def _field_names(value: type[object]) -> tuple[str, ...]:
    assert is_dataclass(value)
    assert hasattr(value, "__slots__")
    return tuple(field.name for field in fields(value))


def test_cn_a_share_dispatcher_contract_is_test_support_only() -> None:
    assert CnAShareDevelopmentFinancialDispatcher.CASH_PAYMENT_OPERATION_KEY == "cn_a_share.corporate_action.cash_payment.v1"
    assert CnAShareDevelopmentFinancialDispatcher.SHARE_DELIVERY_OPERATION_KEY == "cn_a_share.corporate_action.share_delivery.v1"
    assert CnAShareDevelopmentFinancialDispatcher.CASH_PAYMENT_PHASE == 110
    assert CnAShareDevelopmentFinancialDispatcher.SHARE_DELIVERY_PHASE == 120
    dispatcher = CnAShareDevelopmentFinancialDispatcher()
    assert dispatcher.spec.dispatcher_key == "equity.cn_a_share.cash-financial-dispatch.v1"
    for method in ("book_fill", "book_fee", "dispatch_scheduled_event", "project_final_snapshot"):
        assert callable(getattr(dispatcher, method))


def test_cn_a_share_builder_signatures_are_frozen() -> None:
    request_signature = inspect.signature(build_cn_a_share_resolved_request)
    assert tuple(request_signature.parameters) == ("failure_codes",)
    failure_codes = request_signature.parameters["failure_codes"]
    assert failure_codes.kind is inspect.Parameter.KEYWORD_ONLY
    assert failure_codes.default == ()
    case_signature = inspect.signature(build_cn_a_share_execution_case)
    assert tuple(case_signature.parameters) == ("resolved_profile",)
    resolved_profile = case_signature.parameters["resolved_profile"]
    assert resolved_profile.kind is inspect.Parameter.KEYWORD_ONLY
    assert resolved_profile.default is None
    assert inspect.signature(run_cn_a_share_development_journey).parameters == {}
    assert isinstance(build_cn_a_share_resolved_request(), CnAShareProfileCompositionRequest)
    assert build_cn_a_share_execution_case() is not None


def test_cn_a_share_development_journey_result_schema_is_exact() -> None:
    _assert_equal(_field_names(CnAShareDevelopmentJourneyResult), (
        "resolved_profile", "execution_case_hash", "trace_hash", "operation_keys", "event_phases",
        "cash_payment_outcome", "share_delivery_outcome", "final_journal_hash", "final_ledger_state",
        "final_lot_book_hash", "final_portfolio_snapshot", "full_replay_ledger_hash",
        "prefix_resume_ledger_hash", "full_replay_lot_book_hash", "prefix_resume_lot_book_hash",
        "decision_grade_eligible", "deployment_authorized",
    ))
    assert isinstance(build_cn_a_share_resolved_request(failure_codes=(CnAShareProfileCompositionFailureCode.MISSING_INSTRUMENT_SCOPE,)), CnAShareProfileCompositionRequest)
    assert isinstance(inspect.getattr_static(CnAShareDevelopmentJourneyResult, "result_hash"), property)
    journey = run_cn_a_share_development_journey()
    assert isinstance(journey.resolved_profile, CnAShareResolvedProfile)
    assert journey.to_canonical_dict()["type"] == "cn_a_share_development_journey_result"
