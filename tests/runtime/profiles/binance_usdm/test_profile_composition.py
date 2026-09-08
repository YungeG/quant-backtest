from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    BinanceUsdmProfileComposer,
    BinanceUsdmProfileCompositionFailureCode,
    BinanceUsdmResolvedProfile,
)
from crypto_quant_domain import CurrencyId, PositionEffect, PricePurpose, Scale
from crypto_quant_trading import FeeReserveFundingSource, ProfilePortType

from ._fixtures import capacity_evidence, composition_request


def _compose(**overrides):
    return BinanceUsdmProfileComposer().compose(composition_request(**overrides))


def test_composes_contract_risk_profiles_registry_and_dispatcher_spec() -> None:
    outcome = _compose()

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert isinstance(result, BinanceUsdmResolvedProfile)
    assert (
        result.linear_contract.instrument
        == result.request.instrument_metadata.instrument
    )
    assert result.linear_contract.price_scale == result.request.order_rules.price_scale
    assert (
        result.linear_contract.quantity_scale
        == result.request.order_rules.quantity_scale
    )
    assert (
        result.linear_contract.contract_multiplier
        == result.request.instrument_metadata.contract_metadata.contract_multiplier
    )

    policy = result.account_risk_policy
    assert policy.account_id == "account-1"
    assert policy.fee_reserve_funding_source is FeeReserveFundingSource.AVAILABLE_MARGIN
    assert policy.order_capacity_limit == 10
    expected_effects = (
        PositionEffect.AUTO,
        PositionEffect.CLOSE,
        PositionEffect.OPEN,
    )
    assert policy.allowed_position_effects == expected_effects
    assert len(policy.exposure_capacity_limits) == 1
    assert policy.exposure_capacity_limits[0].maximum.currency == "USDT"
    assert policy.exposure_capacity_limits[0].maximum.scale == Scale(8)
    assert policy.exposure_capacity_limits[0].maximum.units == 20_000_000_000_000

    assert {
        value.port_type for value in result.market_semantics.component_manifest
    } == set(ProfilePortType)
    assert result.market_registration.profile_key == "crypto.binance_usdm.v1"
    assert result.simulation_registration.profile_key == "bar.next_eligible_open.conservative.v1"
    assert result.execution_account_registration.profile_key == "binance.usdm.standard-cross.v1"
    expected_currencies = (CurrencyId("USDT"),)
    assert (
        result.execution_account_registration.supported_reporting_currencies
        == expected_currencies
    )
    assert result.financial_dispatcher_spec.dispatcher_key == "crypto.binance_usdm.linear-financial-dispatch.v1"
    expected_deferred = ("MAX_NUM_ALGO_ORDERS", "MAX_NUM_ORDERS")
    assert result.source_deferred_rule_keys == expected_deferred
    assert result.resolved_deferred_rule_keys == result.source_deferred_rule_keys
    assert not result.decision_grade_eligible
    assert not result.deployment_authorized


def test_requires_exact_price_purpose_and_funding_coverage() -> None:
    request = composition_request()
    by_purpose = {
        value.query.price_purpose: value for value in request.price_purposes
    }

    missing = _compose(
        price_purposes=tuple(
            value
            for purpose, value in by_purpose.items()
            if purpose is not PricePurpose.MARGIN
        )
    )
    assert missing.failure is not None
    assert missing.failure.code is BinanceUsdmProfileCompositionFailureCode.MISSING_PRICE_PURPOSE

    duplicate = _compose(
        price_purposes=request.price_purposes + (by_purpose[PricePurpose.VALUATION],)
    )
    assert duplicate.failure is not None
    assert duplicate.failure.code is BinanceUsdmProfileCompositionFailureCode.PRICE_PURPOSE_COVERAGE_MISMATCH

    no_funding = _compose(funding_sources=())
    assert no_funding.failure is not None
    assert no_funding.failure.code is BinanceUsdmProfileCompositionFailureCode.MISSING_FUNDING_SOURCE


def test_capacity_uses_matching_source_and_conservative_minimum() -> None:
    request = composition_request()
    expanded = _compose(
        account_capacity=replace(
            request.account_capacity,
            max_num_orders=5,
            max_num_algo_orders=20,
        )
    )
    assert expanded.result is not None
    assert expanded.result.account_risk_policy.order_capacity_limit == 5

    wrong_source = _compose(
        account_capacity=replace(
            request.account_capacity,
            source_hash="sha256:" + "f" * 64,
        )
    )
    assert wrong_source.failure is not None
    assert wrong_source.failure.code is BinanceUsdmProfileCompositionFailureCode.ORDER_CAPACITY_SOURCE_MISMATCH


def test_frozen_failure_precedence_covers_all_composition_failures() -> None:
    request = composition_request()
    cases = (
        (BinanceUsdmProfileCompositionFailureCode.MISSING_INSTRUMENT_METADATA, {"instrument_metadata": None}),
        (BinanceUsdmProfileCompositionFailureCode.MISSING_ORDER_RULES, {"order_rules": None}),
        (BinanceUsdmProfileCompositionFailureCode.MISSING_MARGIN_TIERS, {"margin_tiers": None}),
        (BinanceUsdmProfileCompositionFailureCode.MISSING_ACCOUNT_PROFILE, {"account_profile": None}),
        (BinanceUsdmProfileCompositionFailureCode.MISSING_ACCOUNT_CAPACITY, {"account_capacity": None}),
        (BinanceUsdmProfileCompositionFailureCode.MISSING_PRICE_PURPOSE, {"price_purposes": ()}),
        (BinanceUsdmProfileCompositionFailureCode.MISSING_FUNDING_SOURCE, {"funding_sources": ()}),
    )
    for expected, override in cases:
        outcome = _compose(**override)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected

    multi_defect = _compose(
        instrument_metadata=None,
        order_rules=None,
        margin_tiers=None,
        account_profile=None,
        account_capacity=None,
        price_purposes=(),
        funding_sources=(),
    )
    assert multi_defect.failure is not None
    assert multi_defect.failure.code is BinanceUsdmProfileCompositionFailureCode.MISSING_INSTRUMENT_METADATA

    assert len(BinanceUsdmProfileCompositionFailureCode) == 19


def test_resolved_profile_rejects_forged_identity() -> None:
    outcome = _compose()
    assert outcome.result is not None
    with pytest.raises(ValueError, match="resolved profile"):
        replace(outcome.result, model_digest="sha256:" + "0" * 64)
