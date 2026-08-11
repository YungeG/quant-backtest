from __future__ import annotations

import pytest

from crypto_quant_backtest import RequestedResultGrade
from tests.runtime.profiles.binance_usdm._fixtures import composition_request
from tests.support.binance_usdm import (
    BinanceUsdmDevelopmentFinancialDispatcher,
    build_binance_usdm_resolved_request,
)


def test_binance_profile_resolves_only_as_development() -> None:
    resolved = build_binance_usdm_resolved_request(composition_request())

    assert resolved.environment.compatibility_report.allowed_grade is RequestedResultGrade.DEVELOPMENT
    assert not resolved.environment.deployment_authorized
    assert "development_profile" in resolved.environment.limitations


def test_binance_dispatcher_spec_matches_resolved_profile() -> None:
    resolved = build_binance_usdm_resolved_request(composition_request())
    dispatcher = BinanceUsdmDevelopmentFinancialDispatcher(composition_request())

    assert dispatcher.spec == resolved.environment.market_semantics.implementation.financial_dispatcher_spec


def test_decision_grade_request_fails_before_engine_execution() -> None:
    with pytest.raises(ValueError, match="decision-grade"):
        build_binance_usdm_resolved_request(
            composition_request(),
            requested_grade=RequestedResultGrade.DECISION_GRADE,
        )
