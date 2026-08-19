from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_domain import OrderSide, Scale
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashMarketFeePolicyV2,
    CnAShareCashStampDutyTaxPolicyV2,
    CnAShareExecutionAccessRoute,
    CnAShareFeeExecutionScopeV2,
    CnAShareFeeExecutionSelectionV2,
    CnAShareFeeProductClass,
    CnAShareFeeTradeMechanism,
    bind_cn_a_share_fee_execution_v2,
    commission_tax_v2,
    create_cn_a_share_fee_execution_authority_v2,
    project_cn_a_share_domestic_ordinary_fee_rules_v2,
)

from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    ACCOUNT,
    instrument,
    local_instant,
    market_rule_book,
    source_order,
    tax_rule_book,
)


def _valid_authority_and_order():
    source_market = market_rule_book()
    source_tax = tax_rule_book()
    market = type(source_market)(
        source_market.rule_book_key,
        source_market.rule_book_version,
        tuple(band for band in source_market.bands if band.venue_id.value == "xshe"),
    )
    tax = type(source_tax)(
        source_tax.rule_book_key,
        source_tax.rule_book_version,
        tuple(band for band in source_tax.bands if band.venue_id.value == "xshe"),
    )
    projection = project_cn_a_share_domestic_ordinary_fee_rules_v2(market, tax)
    instrument_value = instrument("xshe")
    scope = CnAShareFeeExecutionScopeV2(
        ACCOUNT,
        projection.market_fee_rule_book.bands[0].venue_id,
        instrument_value,
        instrument_value.instrument_id,
        instrument_value.instrument_type,
        instrument_value.quote_currency,
        instrument_value.settlement_currency,
        CnAShareFeeTradeMechanism.AUCTION,
        local_instant(25),
        local_instant(30),
        (OrderSide.BUY, OrderSide.SELL),
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    selection = CnAShareFeeExecutionSelectionV2(
        "fixture",
        1,
        scope.access_route,
        scope.fee_product_class,
        projection.market_fee_rule_book,
        projection.market_fee_rule_book_hash,
        projection.stamp_duty_rule_book,
        projection.stamp_duty_rule_book_hash,
        commission_tax_v2._market_component(projection.market_fee_rule_book),
        commission_tax_v2._tax_component(projection.stamp_duty_rule_book),
    )
    authority = create_cn_a_share_fee_execution_authority_v2(scope, selection)
    assert type(authority).__name__ == "CnAShareFeeExecutionAuthorityV2"
    original = source_order(
        quantity_units=100, side=OrderSide.BUY, effective_at=local_instant(26)
    )
    order = replace(
        original,
        intent=replace(
            original.intent,
            instrument_id=instrument_value.instrument_id,
            quantity=replace(
                original.intent.quantity,
                instrument_id=str(instrument_value.instrument_id),
            ),
        ),
    )
    return authority, order


def test_direct_authority_and_binding_cannot_bypass_scope() -> None:
    authority, order = _valid_authority_and_order()
    binding = bind_cn_a_share_fee_execution_v2(authority, order)
    assert type(binding).__name__ == "CnAShareFeeExecutionBindingV2"
    query = commission_tax_v2.CnAShareCashFeeRuleQueryV2.for_reservation(
        authority, binding
    )
    assert type(query).__name__ == "CnAShareCashFeeRuleQueryV2"
    assert (
        CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, Scale(2))
        .assess_fees(query)
        .result
        is not None
    )
    assert (
        CnAShareCashStampDutyTaxPolicyV2(authority, authority.authority_hash, Scale(2))
        .assess_taxes(query)
        .result
        is not None
    )
    wrong_order = replace(order, account_id="account:other")
    with pytest.raises(
        ValueError, match="binding order does not match authority scope"
    ):
        commission_tax_v2.CnAShareFeeExecutionBindingV2(
            authority,
            authority.authority_hash,
            wrong_order,
            commission_tax_v2.canonical_sha256(wrong_order),
            wrong_order.order_id,
            wrong_order.account_id,
            wrong_order.intent.instrument_id.venue,
            wrong_order.intent.instrument_id,
            wrong_order.intent.side,
            wrong_order.created_at.instant,
        )


def test_projection_rejects_v1_xshg_source_before_output() -> None:
    result = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        market_rule_book(), tax_rule_book()
    )
    assert result.code.value == "non_xshe_market_source"


def test_projection_maps_xshe_v1_bands_with_explicit_hkscc_ref() -> None:
    source_market = market_rule_book()
    source_tax = tax_rule_book()
    market = type(source_market)(
        source_market.rule_book_key,
        source_market.rule_book_version,
        tuple(band for band in source_market.bands if band.venue_id.value == "xshe"),
    )
    tax = type(source_tax)(
        source_tax.rule_book_key,
        source_tax.rule_book_version,
        tuple(band for band in source_tax.bands if band.venue_id.value == "xshe"),
    )
    result = project_cn_a_share_domestic_ordinary_fee_rules_v2(market, tax)
    assert result.access_route is CnAShareExecutionAccessRoute.DOMESTIC
    assert result.fee_product_class is CnAShareFeeProductClass.ORDINARY_A_SHARE
    assert all(
        not band.hkscc_transfer_applies for band in result.market_fee_rule_book.bands
    )
    assert all(
        band.hkscc_transfer_source_refs for band in result.market_fee_rule_book.bands
    )


def test_projection_golden_fixture_and_raw_bytes_are_locked() -> None:
    root = Path(__file__).resolve().parents[4]
    fixture = root / "tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v2.json"
    assert (
        hashlib.sha256(fixture.read_bytes()).hexdigest()
        == "80d5f0a4d920eedf01f0b5e5702809a049eba63fa3f160499d1f95f6ebd04c6e"
    )
    source_market = market_rule_book()
    source_tax = tax_rule_book()
    market = type(source_market)(
        source_market.rule_book_key,
        source_market.rule_book_version,
        tuple(band for band in source_market.bands if band.venue_id.value == "xshe"),
    )
    tax = type(source_tax)(
        source_tax.rule_book_key,
        source_tax.rule_book_version,
        tuple(band for band in source_tax.bands if band.venue_id.value == "xshe"),
    )
    result = project_cn_a_share_domestic_ordinary_fee_rules_v2(market, tax)
    golden = json.loads(fixture.read_bytes())
    assert {
        "projection_hash": result.projection_hash,
        "source_market_rule_book_hash": result.source_market_rule_book_hash,
        "source_stamp_duty_rule_book_hash": result.source_stamp_duty_rule_book_hash,
        "market_fee_rule_book_hash": result.market_fee_rule_book_hash,
        "stamp_duty_rule_book_hash": result.stamp_duty_rule_book_hash,
        "market_band_hashes": [
            band.band_hash for band in result.market_fee_rule_book.bands
        ],
        "stamp_band_hashes": [
            band.band_hash for band in result.stamp_duty_rule_book.bands
        ],
    } == {key: golden[key] for key in ("projection_hash", "source_market_rule_book_hash", "source_stamp_duty_rule_book_hash", "market_fee_rule_book_hash", "stamp_duty_rule_book_hash", "market_band_hashes", "stamp_band_hashes")}
