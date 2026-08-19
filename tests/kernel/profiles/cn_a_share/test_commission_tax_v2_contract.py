from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest
from crypto_quant_domain import (
    Price,
    Quantity,
    Scale,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import ProfileComponentRef, ProfilePortType
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashFeeRuleQueryV2,
    CnAShareCashMarketFeePolicyV2,
    CnAShareCashStampDutyTaxPolicyV2,
    CnAShareDomesticOrdinaryFeeProjectionV2,
    CnAShareExecutionAccessRoute,
    CnAShareFeeExecutionAuthorityFailureV2,
    CnAShareFeeExecutionAuthorityV2,
    CnAShareFeeExecutionBindingV2,
    CnAShareFeeExecutionScopeV2,
    CnAShareFeeExecutionSelectionV2,
    CnAShareFeeProductClass,
    CnAShareFeeReservationBufferV2,
    CnAShareFeeRuleFailureCodeV2,
    CnAShareFeeRuleFailureV2,
    CnAShareMarketFeeBandV2,
    CnAShareMarketFeeRuleBookV2,
    bind_cn_a_share_fee_execution_v2,
    create_cn_a_share_fee_execution_authority_v2,
    project_cn_a_share_domestic_ordinary_fee_rules_v2,
)
from crypto_quant_trading.profiles.cn_a_share import commission_tax_v2 as v2

from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    ACCOUNT,
    CNY,
    instrument,
    local_instant,
    market_rule_book,
    source_order,
    tax_rule_book,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    fill as make_fill,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v2.json"


def _forge(value: Any, /, **changes: Any) -> Any:
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


def _xshe_sources() -> tuple[Any, Any]:
    market, stamp = market_rule_book(), tax_rule_book()
    return (
        type(market)(market.rule_book_key, market.rule_book_version, tuple(x for x in market.bands if x.venue_id == VenueId("xshe"))),
        type(stamp)(stamp.rule_book_key, stamp.rule_book_version, tuple(x for x in stamp.bands if x.venue_id == VenueId("xshe"))),
    )


def _valid() -> tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any]:
    source_market, source_stamp = _xshe_sources()
    projection = project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, source_stamp)
    assert isinstance(projection, CnAShareDomesticOrdinaryFeeProjectionV2)
    value = instrument("xshe")
    scope = CnAShareFeeExecutionScopeV2(
        ACCOUNT, VenueId("xshe"), value, value.instrument_id, value.instrument_type,
        CNY, CNY, v2.CnAShareFeeTradeMechanism.AUCTION, local_instant(25), local_instant(30),
        (v2.OrderSide.BUY, v2.OrderSide.SELL), CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    selection = CnAShareFeeExecutionSelectionV2(
        "fixture", 1, scope.access_route, scope.fee_product_class,
        projection.market_fee_rule_book, projection.market_fee_rule_book_hash,
        projection.stamp_duty_rule_book, projection.stamp_duty_rule_book_hash,
        v2._market_component(projection.market_fee_rule_book), v2._tax_component(projection.stamp_duty_rule_book),
    )
    authority = create_cn_a_share_fee_execution_authority_v2(scope, selection)
    assert isinstance(authority, CnAShareFeeExecutionAuthorityV2)
    original = source_order(quantity_units=100, side=v2.OrderSide.BUY, effective_at=local_instant(26))
    order = replace(original, intent=replace(original.intent, instrument_id=value.instrument_id, quantity=replace(original.intent.quantity, instrument_id=str(value.instrument_id))))
    binding = bind_cn_a_share_fee_execution_v2(authority, order)
    assert isinstance(binding, CnAShareFeeExecutionBindingV2)
    reservation = CnAShareCashFeeRuleQueryV2.for_reservation(authority, binding)
    assert isinstance(reservation, CnAShareCashFeeRuleQueryV2)
    base_fill = make_fill(order, "8", local_instant(26, 1))
    price = Price(base_fill.price.units, base_fill.price.scale, str(value.instrument_id), str(CNY))
    fill = replace(base_fill, venue_id=VenueId("xshe"), instrument_id=value.instrument_id, quantity=Quantity(base_fill.quantity.units, base_fill.quantity.scale, str(value.instrument_id)), reference_price=price, price=price)
    final = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, fill)
    assert isinstance(final, CnAShareCashFeeRuleQueryV2)
    return projection, scope, selection, authority, order, binding, reservation, final, fill


def _values() -> dict[str, Any]:
    projection, scope, selection, authority, _order, binding, reservation, final, _fill = _valid()
    market = CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, Scale(2))
    tax = CnAShareCashStampDutyTaxPolicyV2(authority, authority.authority_hash, Scale(2))
    mr, tr = market.assess_fees(reservation).result, tax.assess_taxes(reservation).result
    mf, tf = market.assess_fees(final).result, tax.assess_taxes(final).result
    assert mr and tr and mf and tf
    component_bad = replace(selection, market_fee_component_ref=ProfileComponentRef(ProfilePortType.FEE_ASSESSMENT_POLICY, "other", 2, "sha256:" + "1" * 64))
    authority_failure = create_cn_a_share_fee_execution_authority_v2(scope, component_bad)
    assert isinstance(authority_failure, CnAShareFeeExecutionAuthorityFailureV2)
    missing_fill = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, None)
    buffer = CnAShareFeeReservationBufferV2.create(market_resolution=mr, tax_resolution=tr, maximum_fill_count=5)
    return {
        "scope": scope, "selection": selection, "authority": authority, "binding": binding,
        "reservation_query": reservation, "final_query": final, "market_resolution": mr,
        "tax_resolution": tr, "final_market_resolution": mf, "final_tax_resolution": tf,
        "authority_component_failure": authority_failure, "missing_fill_failure": missing_fill,
        "buffer": buffer, "projection": projection,
    }


def _record(value: Any, /) -> str:
    return canonical_sha256(value)


def test_compact_golden_hashes_and_representative_canonical_bodies() -> None:
    values = _values()
    fixture = json.loads(FIXTURE.read_text())
    assert {name: _record(value) for name, value in values.items()} == fixture["hashes"]
    representatives = {type(value).__name__: json.loads(canonical_bytes(value)) for value in values.values()}
    assert representatives == fixture["representative_bodies"]


def test_concrete_boundaries_reject_rule_book_binding_order_fill_and_nested_attacks() -> None:
    _, _scope, selection, authority, order, binding, reservation, final, fill = _valid()

    class InjectedBook(CnAShareMarketFeeRuleBookV2):
        def active_bands(self, *_: object) -> tuple[CnAShareMarketFeeBandV2, ...]:
            return ()

    injected = object.__new__(InjectedBook)
    for field in fields(selection.market_fee_rule_book):
        object.__setattr__(injected, field.name, getattr(selection.market_fee_rule_book, field.name))
    with pytest.raises(TypeError, match="selection rule books"):
        replace(selection, market_fee_rule_book=injected, market_fee_rule_book_hash=injected.rule_book_hash)

    class BindingAttack(CnAShareFeeExecutionBindingV2):
        @property
        def side(self) -> Any:
            return v2.OrderSide.SELL

    attacked = object.__new__(BindingAttack)
    with pytest.raises(TypeError, match="concrete v2"):
        CnAShareCashFeeRuleQueryV2.for_reservation(authority, attacked)
    with pytest.raises(TypeError, match="concrete"):
        bind_cn_a_share_fee_execution_v2(authority, _forge(order, intent=_forge(order.intent, quantity=_forge(order.intent.quantity, units=-1))))
    with pytest.raises(TypeError, match="concrete Fill"):
        CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, _forge(fill, execution_time=_forge(fill.execution_time, epoch_nanoseconds="bad")))
    assert isinstance(CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, None), type(_values()["missing_fill_failure"]))
    assert reservation.side is v2.OrderSide.BUY and final.effective_at == fill.execution_time


def test_resolution_buffer_and_policy_failures_are_not_substitutable() -> None:
    _, _, _, authority, _, _binding, reservation, final, _ = _valid()
    market = CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, Scale(2))
    tax = CnAShareCashStampDutyTaxPolicyV2(authority, authority.authority_hash, Scale(2))
    mr, tr = market.assess_fees(reservation).result, tax.assess_taxes(reservation).result
    assert mr and tr
    with pytest.raises((TypeError, ValueError)):
        type(mr)(*([getattr(mr, field.name) for field in fields(mr)][:-1] + [()]))
    with pytest.raises(ValueError, match="reservation buffer resolution context mismatch"):
        CnAShareFeeReservationBufferV2.create(market_resolution=mr, tax_resolution=tax.assess_taxes(final).result, maximum_fill_count=1)
    forged_subjects = ("missing_rule_interval", authority.authority_hash, reservation.query_hash, "forged")
    with pytest.raises(ValueError, match="fee rule failure invalid"):
        CnAShareFeeRuleFailureV2(reservation, reservation.query_hash, CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL, forged_subjects)
    assert market.assess_fees(reservation).result is not None
    assert tax.assess_taxes(reservation).result is not None


def test_authority_precedence_and_projection_fail_closed_for_untrusted_sources() -> None:
    _, scope, selection, _, _, _, _, _, _ = _valid()
    class BookSubclass(CnAShareMarketFeeRuleBookV2):
        pass
    malformed = object.__new__(BookSubclass)
    for field in fields(selection.market_fee_rule_book):
        object.__setattr__(malformed, field.name, getattr(selection.market_fee_rule_book, field.name))
    combined = _forge(selection, access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT, market_fee_rule_book=malformed, market_fee_rule_book_hash=malformed.rule_book_hash)
    first = create_cn_a_share_fee_execution_authority_v2(scope, combined)
    assert isinstance(first, CnAShareFeeExecutionAuthorityFailureV2)
    assert first.code.value == "scope_selection_mismatch"
    market, stamp = _xshe_sources()
    assert project_cn_a_share_domestic_ordinary_fee_rules_v2(market_rule_book(), stamp).code.value == "non_xshe_market_source"
    with pytest.raises(TypeError, match="concrete v1"):
        project_cn_a_share_domestic_ordinary_fee_rules_v2(_forge(market, bands=()), stamp)
    class V1BookSubclass(type(market)):
        pass
    v1_subclass = object.__new__(V1BookSubclass)
    for field in fields(market):
        object.__setattr__(v1_subclass, field.name, getattr(market, field.name))
    with pytest.raises(TypeError, match="concrete v1"):
        project_cn_a_share_domestic_ordinary_fee_rules_v2(v1_subclass, stamp)
    economic = _forge(market.bands[0], handling_source_refs=())
    with pytest.raises(TypeError, match="concrete v1"):
        project_cn_a_share_domestic_ordinary_fee_rules_v2(_forge(market, bands=(economic, *market.bands[1:])), stamp)
