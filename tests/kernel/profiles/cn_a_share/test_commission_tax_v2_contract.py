from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Fill,
    InstrumentId,
    Money,
    OrderSide,
    Price,
    Quantity,
    Rate,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import ProfileComponentRef, ProfilePortType
from crypto_quant_trading.fee_reservations import FeeReservationApplicability
from crypto_quant_trading.fees import FinalFeeApplicability
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashFeeRuleQueryV2,
    CnAShareCashMarketFeePolicyV2,
    CnAShareCashStampDutyTaxPolicyV2,
    CnAShareDomesticOrdinaryFeeProjectionFailureV2,
    CnAShareDomesticOrdinaryFeeProjectionV2,
    CnAShareExecutionAccessRoute,
    CnAShareFeeAssessmentPurposeV2,
    CnAShareFeeExecutionAuthorityFailureV2,
    CnAShareFeeExecutionAuthorityV2,
    CnAShareFeeExecutionBindingFailureV2,
    CnAShareFeeExecutionBindingV2,
    CnAShareFeeExecutionScopeV2,
    CnAShareFeeExecutionSelectionV2,
    CnAShareFeeProductClass,
    CnAShareFeeQueryConstructionFailureV2,
    CnAShareFeeReservationBufferV2,
    CnAShareFeeRuleFailureV2,
    CnAShareMarketFeeBandV2,
    CnAShareMarketFeeRuleBookV2,
    CnAShareStampDutyBandV2,
    CnAShareStampDutyRuleBookV2,
    bind_cn_a_share_fee_execution_v2,
    create_cn_a_share_fee_execution_authority_v2,
    project_cn_a_share_domestic_ordinary_fee_rules_v2,
)
from crypto_quant_trading.profiles.cn_a_share import commission_tax_v2 as v2

from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    ACCOUNT,
    CNY,
    fill as make_fill,
    instrument,
    local_instant,
    market_rule_book,
    source_order,
    tax_rule_book,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v2.json"


def _forge(value: Any, /, **changes: Any) -> Any:
    """Build a dataclass-shaped hostile value without invoking its guard."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


def _xshe_sources() -> tuple[Any, Any]:
    market = market_rule_book()
    stamp = tax_rule_book()
    return (
        type(market)(
            market.rule_book_key,
            market.rule_book_version,
            tuple(band for band in market.bands if band.venue_id == VenueId("xshe")),
        ),
        type(stamp)(
            stamp.rule_book_key,
            stamp.rule_book_version,
            tuple(band for band in stamp.bands if band.venue_id == VenueId("xshe")),
        ),
    )


def _valid() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    source_market, source_stamp = _xshe_sources()
    projection = project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, source_stamp)
    assert isinstance(projection, CnAShareDomesticOrdinaryFeeProjectionV2)
    value = instrument("xshe")
    scope = CnAShareFeeExecutionScopeV2(
        ACCOUNT,
        VenueId("xshe"),
        value,
        value.instrument_id,
        value.instrument_type,
        CNY,
        CNY,
        v2.CnAShareFeeTradeMechanism.AUCTION,
        local_instant(25),
        local_instant(30),
        (OrderSide.BUY, OrderSide.SELL),
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    selection = CnAShareFeeExecutionSelectionV2(
        "fixture", 1, scope.access_route, scope.fee_product_class,
        projection.market_fee_rule_book, projection.market_fee_rule_book_hash,
        projection.stamp_duty_rule_book, projection.stamp_duty_rule_book_hash,
        v2._market_component(projection.market_fee_rule_book),
        v2._tax_component(projection.stamp_duty_rule_book),
    )
    authority = create_cn_a_share_fee_execution_authority_v2(scope, selection)
    assert isinstance(authority, CnAShareFeeExecutionAuthorityV2)
    original = source_order(quantity_units=100, side=OrderSide.BUY, effective_at=local_instant(26))
    order = replace(
        original,
        intent=replace(
            original.intent,
            instrument_id=value.instrument_id,
            quantity=replace(original.intent.quantity, instrument_id=str(value.instrument_id)),
        ),
    )
    binding = bind_cn_a_share_fee_execution_v2(authority, order)
    assert isinstance(binding, CnAShareFeeExecutionBindingV2)
    reservation = CnAShareCashFeeRuleQueryV2.for_reservation(authority, binding)
    assert isinstance(reservation, CnAShareCashFeeRuleQueryV2)
    source_fill = make_fill(order, "8", local_instant(26, 1))
    price = Price(source_fill.price.units, source_fill.price.scale, str(value.instrument_id), str(CNY))
    final_fill = replace(
        source_fill,
        venue_id=VenueId("xshe"),
        instrument_id=value.instrument_id,
        quantity=Quantity(source_fill.quantity.units, source_fill.quantity.scale, str(value.instrument_id)),
        reference_price=price,
        price=price,
    )
    final = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, final_fill)
    assert isinstance(final, CnAShareCashFeeRuleQueryV2)
    return projection, scope, selection, authority, order, binding, reservation, final, final_fill


def _failure(value: Any) -> Any:
    assert not isinstance(value, (CnAShareFeeExecutionAuthorityV2, CnAShareFeeExecutionBindingV2, CnAShareCashFeeRuleQueryV2))
    return value


def _changed_order(order: Any, name: str) -> Any:
    if name == "account":
        return replace(order, account_id="account:other")
    if name == "venue":
        ident = InstrumentId(VenueId("xshg"), "600000")
    elif name == "instrument":
        ident = InstrumentId(VenueId("xshe"), "000002")
    else:
        return replace(order, intent=replace(order.intent, side=OrderSide.SELL))
    return replace(order, intent=replace(order.intent, instrument_id=ident, quantity=replace(order.intent.quantity, instrument_id=str(ident))))


def _changed_fill(fill: Fill, name: str) -> Fill:
    if name == "order":
        return replace(fill, order_id=DomainId(DomainIdKind.ORDER, DomainIdKind.ORDER.prefix + "_" + "9" * 64))
    if name == "account":
        return replace(fill, account_id="account:other")
    if name in ("venue", "instrument"):
        ident = InstrumentId(VenueId("xshg"), "600000") if name == "venue" else InstrumentId(VenueId("xshe"), "000002")
        price = Price(fill.price.units, fill.price.scale, str(ident), str(CNY))
        return replace(
            fill,
            venue_id=ident.venue,
            instrument_id=ident,
            quantity=Quantity(fill.quantity.units, fill.quantity.scale, str(ident)),
            reference_price=price,
            price=price,
        )
    if name == "side":
        return replace(fill, side=OrderSide.SELL)
    if name == "below":
        return replace(fill, execution_time=local_instant(25))
    if name == "upper":
        return replace(fill, execution_time=local_instant(30))
    raise AssertionError(name)


def _record(value: Any) -> dict[str, Any]:
    body = json.loads(canonical_bytes(value))
    hash_name = next((name for name in ("scope_hash", "selection_hash", "authority_hash", "binding_hash", "query_hash", "resolution_hash", "failure_hash", "buffer_hash", "projection_hash", "rule_book_hash", "band_hash") if hasattr(value, name)), None)
    return {"body": body, "hash": getattr(value, hash_name) if hash_name else canonical_sha256(value)}


def _golden_values() -> dict[str, Any]:
    projection, scope, selection, authority, order, binding, reservation, final, final_fill = _valid()
    market = CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, Scale(2))
    tax = CnAShareCashStampDutyTaxPolicyV2(authority, authority.authority_hash, Scale(2))
    market_reservation = market.assess_fees(reservation).result
    tax_reservation = tax.assess_taxes(reservation).result
    market_final = market.assess_fees(final).result
    tax_final = tax.assess_taxes(final).result
    assert all(value is not None for value in (market_reservation, tax_reservation, market_final, tax_final))
    values: dict[str, Any] = {
        "scope": scope, "selection": selection, "authority": authority,
        "binding": binding, "reservation_query": reservation, "final_query": final,
        "market_component": market.component_ref, "tax_component": tax.component_ref,
        "market_reservation_resolution": market_reservation,
        "tax_reservation_resolution": tax_reservation,
        "market_final_resolution": market_final, "tax_final_resolution": tax_final,
    }
    for label, changed in {
        "scope_selection": replace(selection, access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT),
        "rule_book_scope": replace(selection, market_fee_rule_book=replace(selection.market_fee_rule_book, access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT), market_fee_rule_book_hash=replace(selection.market_fee_rule_book, access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT).rule_book_hash),
        "component_ref": replace(selection, market_fee_component_ref=ProfileComponentRef(ProfilePortType.FEE_ASSESSMENT_POLICY, "other", 2, "sha256:" + "1" * 64)),
    }.items():
        values[f"authority_failure_{label}"] = _failure(create_cn_a_share_fee_execution_authority_v2(scope, changed))
    forged_authority = _forge(authority, selection_hash="sha256:" + "0" * 64)
    values["binding_failure_authority_scope"] = _failure(bind_cn_a_share_fee_execution_v2(forged_authority, order))
    for label in ("account", "venue", "instrument"):
        values[f"binding_failure_{label}"] = _failure(bind_cn_a_share_fee_execution_v2(authority, _changed_order(order, label)))
    buy_scope = replace(scope, allowed_order_sides=(OrderSide.BUY,))
    buy_authority = create_cn_a_share_fee_execution_authority_v2(buy_scope, selection)
    assert isinstance(buy_authority, CnAShareFeeExecutionAuthorityV2)
    values["binding_failure_side"] = _failure(bind_cn_a_share_fee_execution_v2(buy_authority, _changed_order(order, "side")))
    late = replace(order, created_at=replace(order.created_at, instant=local_instant(30)))
    values["binding_failure_context"] = _failure(bind_cn_a_share_fee_execution_v2(authority, late))
    wrong_binding = _forge(binding, authority_hash="sha256:" + "0" * 64)
    values["query_failure_authority_binding"] = _failure(CnAShareCashFeeRuleQueryV2.for_reservation(authority, wrong_binding))
    bad_context = _forge(binding, order_effective_at=UtcInstant(binding.order_effective_at.epoch_nanoseconds + 1))
    values["query_failure_reservation_context"] = _failure(CnAShareCashFeeRuleQueryV2.for_reservation(authority, bad_context))
    values["query_failure_missing_fill"] = _failure(CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, None))
    for label in ("order", "account", "venue", "instrument", "side", "below", "upper"):
        values[f"query_failure_{label}"] = _failure(CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, _changed_fill(final_fill, label)))
    other = replace(authority, selection=replace(selection, selection_key="other", selection_version=2), selection_hash=replace(selection, selection_key="other", selection_version=2).selection_hash)
    # Rebuild via factory keeps its nested mirrors canonical.
    other = create_cn_a_share_fee_execution_authority_v2(scope, other.selection)
    assert isinstance(other, CnAShareFeeExecutionAuthorityV2)
    other_market = CnAShareCashMarketFeePolicyV2(other, other.authority_hash, Scale(2))
    values["policy_failure_authority"] = other_market.assess_fees(reservation).failure
    forged_query = _forge(reservation, binding_hash="sha256:" + "0" * 64)
    values["policy_failure_provenance"] = market.assess_fees(forged_query).failure
    wrong_scope_book = replace(authority.market_fee_rule_book, access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT)
    values["policy_failure_rule_book_scope"] = v2._policy_failure(market, reservation, wrong_scope_book)
    values["policy_failure_missing_interval"] = v2._failure(
        reservation,
        v2.CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL,
        ("venue_id", reservation.venue_id.value, "effective_at_hash", canonical_sha256(reservation.effective_at), "rule_book_hash", authority.market_fee_rule_book_hash, "active_band_hashes_hash", canonical_sha256(())),
    )
    values["policy_failure_overlapping_intervals"] = v2._failure(
        reservation,
        v2.CnAShareFeeRuleFailureCodeV2.OVERLAPPING_RULE_INTERVALS,
        ("venue_id", reservation.venue_id.value, "effective_at_hash", canonical_sha256(reservation.effective_at), "rule_book_hash", authority.market_fee_rule_book_hash, "active_band_hashes_hash", canonical_sha256((market_reservation.active_band_hash, market_reservation.active_band_hash))),
    )
    buffer = CnAShareFeeReservationBufferV2.create(market_resolution=market_reservation, tax_resolution=tax_reservation, maximum_fill_count=5)
    values["buffer"] = buffer
    for purpose, result in (("reservation", market_reservation), ("final_fill", market_final)):
        for index, rule in enumerate(result.reservation_charge_rules if purpose == "reservation" else result.final_fill_charge_rules):
            values[f"market_{purpose}_{index}"] = rule
        for index, rule in enumerate(result.final_order_not_applicable_rules):
            values[f"market_final_order_{index}"] = rule
    for purpose, result in (("reservation", tax_reservation), ("final_fill", tax_final)):
        rule = result.reservation_charge_rule if purpose == "reservation" else result.final_fill_charge_rule
        values[f"tax_{purpose}"] = rule
    values["tax_final_order"] = tax_reservation.final_order_not_applicable_rule
    sell_order = _changed_order(order, "side")
    sell_binding = bind_cn_a_share_fee_execution_v2(authority, sell_order)
    assert isinstance(sell_binding, CnAShareFeeExecutionBindingV2)
    sell_reservation = CnAShareCashFeeRuleQueryV2.for_reservation(authority, sell_binding)
    sell_final_fill = replace(final_fill, side=OrderSide.SELL)
    sell_final = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, sell_binding, sell_final_fill)
    assert isinstance(sell_reservation, CnAShareCashFeeRuleQueryV2) and isinstance(sell_final, CnAShareCashFeeRuleQueryV2)
    sell_market_reservation, sell_tax_reservation = market.assess_fees(sell_reservation).result, tax.assess_taxes(sell_reservation).result
    sell_market_final, sell_tax_final = market.assess_fees(sell_final).result, tax.assess_taxes(sell_final).result
    assert all(value is not None for value in (sell_market_reservation, sell_tax_reservation, sell_market_final, sell_tax_final))
    values.update({"sell_binding": sell_binding, "sell_reservation_query": sell_reservation, "sell_final_query": sell_final, "sell_market_reservation_resolution": sell_market_reservation, "sell_tax_reservation_resolution": sell_tax_reservation, "sell_market_final_resolution": sell_market_final, "sell_tax_final_resolution": sell_tax_final})
    for purpose, result in (("reservation", sell_market_reservation), ("final_fill", sell_market_final)):
        for index, rule in enumerate(result.reservation_charge_rules if purpose == "reservation" else result.final_fill_charge_rules):
            values[f"sell_market_{purpose}_{index}"] = rule
        for index, rule in enumerate(result.final_order_not_applicable_rules):
            values[f"sell_market_final_order_{index}"] = rule
    values["sell_tax_reservation"] = sell_tax_reservation.reservation_charge_rule
    values["sell_tax_final_fill"] = sell_tax_final.final_fill_charge_rule
    values["sell_tax_final_order"] = sell_tax_reservation.final_order_not_applicable_rule
    source_market, source_stamp = _xshe_sources()
    bad_market = market_rule_book()
    values["projection_failure_non_xshe_market"] = project_cn_a_share_domestic_ordinary_fee_rules_v2(bad_market, source_stamp)
    values["projection_failure_non_xshe_stamp"] = project_cn_a_share_domestic_ordinary_fee_rules_v2(_xshe_sources()[0], tax_rule_book())
    invalid_market_band = _forge(source_market.bands[0], effective_to_exclusive=source_market.bands[0].effective_from)
    values["projection_failure_market_interval"] = project_cn_a_share_domestic_ordinary_fee_rules_v2(_forge(source_market, bands=(invalid_market_band, *source_market.bands[1:])), source_stamp)
    invalid_stamp_band = _forge(source_stamp.bands[0], effective_to_exclusive=source_stamp.bands[0].effective_from)
    values["projection_failure_stamp_interval"] = project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, _forge(source_stamp, bands=(invalid_stamp_band, *source_stamp.bands[1:])))
    economic_market = _forge(source_market.bands[0], handling_source_refs=())
    values["projection_failure_market_economic"] = project_cn_a_share_domestic_ordinary_fee_rules_v2(_forge(source_market, bands=(economic_market, *source_market.bands[1:])), source_stamp)
    economic_stamp = _forge(source_stamp.bands[0], source_refs=())
    values["projection_failure_stamp_economic"] = project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, _forge(source_stamp, bands=(economic_stamp, *source_stamp.bands[1:])))
    return values


def test_golden_canonical_bodies_and_hashes_cover_all_constructed_contract_values() -> None:
    fixture = json.loads(FIXTURE.read_text())
    actual = {name: _record(value) for name, value in _golden_values().items()}
    assert actual == fixture["canonical_values"]


def test_authority_binding_and_query_first_failure_precedence_and_subjects() -> None:
    _, scope, selection, authority, order, binding, _, _, final_fill = _valid()
    # Each public construction code has an independently frozen exact canonical failure.
    golden = _golden_values()
    expected_codes = {
        "authority_failure_scope_selection": "scope_selection_mismatch", "authority_failure_rule_book_scope": "rule_book_scope_mismatch", "authority_failure_component_ref": "component_ref_mismatch",
        "binding_failure_authority_scope": "authority_scope_mismatch", "binding_failure_account": "order_account_mismatch", "binding_failure_venue": "order_venue_mismatch", "binding_failure_instrument": "order_instrument_mismatch", "binding_failure_side": "order_side_mismatch", "binding_failure_context": "order_context_mismatch",
        "query_failure_authority_binding": "authority_binding_mismatch", "query_failure_reservation_context": "reservation_context_mismatch", "query_failure_missing_fill": "missing_fill", "query_failure_order": "fill_order_mismatch", "query_failure_account": "fill_account_mismatch", "query_failure_venue": "fill_venue_mismatch", "query_failure_instrument": "fill_instrument_mismatch", "query_failure_side": "fill_side_mismatch", "query_failure_below": "execution_time_mismatch", "query_failure_upper": "execution_time_mismatch",
        "policy_failure_authority": "execution_authority_mismatch", "policy_failure_provenance": "query_provenance_mismatch", "policy_failure_rule_book_scope": "rule_book_scope_mismatch", "policy_failure_missing_interval": "missing_rule_interval", "policy_failure_overlapping_intervals": "overlapping_rule_intervals",
        "projection_failure_non_xshe_market": "non_xshe_market_source", "projection_failure_non_xshe_stamp": "non_xshe_stamp_duty_source", "projection_failure_market_interval": "market_source_interval_invalid", "projection_failure_stamp_interval": "stamp_duty_source_interval_invalid", "projection_failure_market_economic": "market_source_economic_invalid", "projection_failure_stamp_economic": "stamp_duty_source_economic_invalid",
    }
    assert {name: golden[name].code.value for name in expected_codes} == expected_codes
    both = replace(_changed_order(order, "account"), intent=replace(_changed_order(order, "account").intent, side=OrderSide.SELL))
    assert bind_cn_a_share_fee_execution_v2(authority, both).code.value == "order_account_mismatch"
    both_fill = replace(_changed_fill(final_fill, "order"), account_id="account:other")
    assert CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, both_fill).code.value == "fill_order_mismatch"
    assert CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, _changed_fill(final_fill, "below")).code.value == "execution_time_mismatch"
    assert CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, _changed_fill(final_fill, "upper")).code.value == "execution_time_mismatch"
    lower = replace(final_fill, execution_time=binding.order_effective_at)
    assert isinstance(CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, lower), CnAShareCashFeeRuleQueryV2)
    before_upper = replace(final_fill, execution_time=UtcInstant(scope.coverage_to_exclusive.epoch_nanoseconds - 1))
    assert isinstance(CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, before_upper), CnAShareCashFeeRuleQueryV2)
    lower_order = replace(order, created_at=replace(order.created_at, instant=scope.coverage_from))
    assert isinstance(bind_cn_a_share_fee_execution_v2(authority, lower_order), CnAShareFeeExecutionBindingV2)
    assert isinstance(CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, final_fill), CnAShareCashFeeRuleQueryV2)
    assert scope.coverage_from <= order.created_at.instant < scope.coverage_to_exclusive


def test_policy_rules_apply_in_fixed_order_and_preserve_separate_source_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, _, authority, _, _, reservation, final, _ = _valid()
    market = CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, Scale(2))
    tax = CnAShareCashStampDutyTaxPolicyV2(authority, authority.authority_hash, Scale(2))
    market_reservation = market.assess_fees(reservation).result
    tax_reservation = tax.assess_taxes(reservation).result
    market_final = market.assess_fees(final).result
    assert market_reservation and tax_reservation and market_final
    assert len(market_reservation.reservation_charge_rules) == len(market_final.final_fill_charge_rules) == len(market_final.final_order_not_applicable_rules) == 4
    assert [rule.applicability for rule in market_reservation.reservation_charge_rules] == [FeeReservationApplicability.APPLIES] * 3 + [FeeReservationApplicability.NOT_APPLICABLE]
    assert [rule.applicability for rule in market_final.final_fill_charge_rules] == [FinalFeeApplicability.ALWAYS] * 3 + [FinalFeeApplicability.NOT_APPLICABLE]
    assert all(rule.rate.units == 0 for rule in market_final.final_order_not_applicable_rules)
    band = market_reservation.active_band
    assert band.chinaclear_transfer_source_refs != band.hkscc_transfer_source_refs
    assert band.hkscc_transfer_applies is False and band.hkscc_transfer_rate == Rate(0, Scale(0), "fee_fraction")
    buy_tax = tax_reservation.reservation_charge_rule
    assert buy_tax.applicability is FeeReservationApplicability.NOT_APPLICABLE and buy_tax.rate.units == 0
    sell_order = _changed_order(reservation.execution_binding.order, "side")
    sell_binding = bind_cn_a_share_fee_execution_v2(authority, sell_order)
    assert isinstance(sell_binding, CnAShareFeeExecutionBindingV2)
    sell = CnAShareCashFeeRuleQueryV2.for_reservation(authority, sell_binding)
    assert isinstance(sell, CnAShareCashFeeRuleQueryV2)
    sell_tax = tax.assess_taxes(sell).result
    assert sell_tax and sell_tax.reservation_charge_rule.applicability is FeeReservationApplicability.APPLIES
    assert sell_tax.reservation_charge_rule.rule_id.startswith("cn-a-share-stamp-duty-rule-v2:sha256:")
    original_active = CnAShareMarketFeeRuleBookV2.active_bands
    monkeypatch.setattr(CnAShareMarketFeeRuleBookV2, "active_bands", lambda _self, _venue, _instant: ())
    assert market.assess_fees(reservation).failure.code.value == "missing_rule_interval"
    monkeypatch.setattr(CnAShareMarketFeeRuleBookV2, "active_bands", lambda self, venue, instant: (original_active(self, venue, instant)[0],) * 2)
    assert market.assess_fees(reservation).failure.code.value == "overlapping_rule_intervals"


def test_buffer_money_counts_ids_and_bounds() -> None:
    _, _, _, authority, _, _, reservation, final, _ = _valid()
    market = CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, Scale(2))
    tax = CnAShareCashStampDutyTaxPolicyV2(authority, authority.authority_hash, Scale(2))
    mr = market.assess_fees(reservation).result
    tr = tax.assess_taxes(reservation).result
    assert mr and tr
    buffer = CnAShareFeeReservationBufferV2.create(market_resolution=mr, tax_resolution=tr, maximum_fill_count=5)
    assert buffer.market_charge_rule.flat_amount == Money(6, Scale(2), "CNY")
    assert buffer.tax_charge_rule.flat_amount == Money(0, Scale(2), "CNY")
    assert buffer.market_charge_rule.rule_id.startswith("cn-a-share-fee-reservation-buffer-rule-v2:sha256:")
    assert buffer.covers_fill_count(5) and not buffer.covers_fill_count(6)
    with pytest.raises(ValueError, match="actual fill count exceeds reservation bound"):
        buffer.require_covers_fills((make_fill(reservation.execution_binding.order, "1", local_instant(26)),) * 6)
    with pytest.raises(ValueError, match="reservation buffer resolution context mismatch"):
        CnAShareFeeReservationBufferV2.create(market_resolution=mr, tax_resolution=tax.assess_taxes(final).result, maximum_fill_count=1)


def test_projection_maps_exact_xshe_economics_and_returns_each_structured_failure() -> None:
    source_market, source_stamp = _xshe_sources()
    projection = project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, source_stamp)
    assert isinstance(projection, CnAShareDomesticOrdinaryFeeProjectionV2)
    assert projection.market_fee_rule_book.rule_book_key.endswith("projected-v2")
    for source, projected in zip(source_market.bands, projection.market_fee_rule_book.bands, strict=True):
        assert (projected.effective_from, projected.effective_to_exclusive, projected.handling_rate, projected.regulatory_rate, projected.chinaclear_transfer_rate) == (source.effective_from, source.effective_to_exclusive, source.handling_rate, source.regulatory_rate, source.transfer_rate)
        assert projected.chinaclear_transfer_source_refs == source.transfer_source_refs
        assert projected.hkscc_transfer_applies is False and len(projected.hkscc_transfer_source_refs) == 1
        assert projected.hkscc_transfer_source_refs[0].source_key == "cn-a-share-domestic-ordinary-v1-to-v2-hkscc-not-applicable"
    assert [(band.effective_from, band.effective_to_exclusive, band.rate, band.source_refs) for band in projection.stamp_duty_rule_book.bands] == [(band.effective_from, band.effective_to_exclusive, band.rate, band.source_refs) for band in source_stamp.bands]
    bad_market = market_rule_book()
    non_xshe = project_cn_a_share_domestic_ordinary_fee_rules_v2(bad_market, source_stamp)
    assert isinstance(non_xshe, CnAShareDomesticOrdinaryFeeProjectionFailureV2) and non_xshe.code.value == "non_xshe_market_source"
    non_xshe_stamp = project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, tax_rule_book())
    assert isinstance(non_xshe_stamp, CnAShareDomesticOrdinaryFeeProjectionFailureV2) and non_xshe_stamp.code.value == "non_xshe_stamp_duty_source"
    invalid_market_band = _forge(source_market.bands[0], effective_to_exclusive=source_market.bands[0].effective_from)
    invalid_market = _forge(source_market, bands=(invalid_market_band, *source_market.bands[1:]))
    assert project_cn_a_share_domestic_ordinary_fee_rules_v2(invalid_market, source_stamp).code.value == "market_source_interval_invalid"
    invalid_stamp_band = _forge(source_stamp.bands[0], effective_to_exclusive=source_stamp.bands[0].effective_from)
    invalid_stamp = _forge(source_stamp, bands=(invalid_stamp_band, *source_stamp.bands[1:]))
    assert project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, invalid_stamp).code.value == "stamp_duty_source_interval_invalid"
    economic_market = _forge(source_market.bands[0], handling_source_refs=())
    assert project_cn_a_share_domestic_ordinary_fee_rules_v2(_forge(source_market, bands=(economic_market, *source_market.bands[1:])), source_stamp).code.value == "market_source_economic_invalid"
    economic_stamp = _forge(source_stamp.bands[0], source_refs=())
    assert project_cn_a_share_domestic_ordinary_fee_rules_v2(source_market, _forge(source_stamp, bands=(economic_stamp, *source_stamp.bands[1:]))).code.value == "stamp_duty_source_economic_invalid"


def test_query_provenance_controls_accept_canonical_direct_and_reject_tampering_and_subclasses() -> None:
    _, _, _, authority, _, binding, reservation, _, _ = _valid()
    policy = CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, Scale(2))
    direct = CnAShareCashFeeRuleQueryV2(authority, authority.authority_hash, binding, binding.binding_hash, CnAShareFeeAssessmentPurposeV2.RESERVATION, None, None, None)
    assert policy.assess_fees(direct).result is not None
    with pytest.raises(ValueError, match="query authority/binding hash mismatch"):
        replace(reservation, binding_hash="sha256:" + "0" * 64)
    changed = _forge(reservation, binding_hash="sha256:" + "0" * 64)
    assert policy.assess_fees(changed).failure.code.value == "query_provenance_mismatch"
    subclass = type("QuerySubclass", (CnAShareCashFeeRuleQueryV2,), {})
    forged_subclass = object.__new__(subclass)
    for field in fields(reservation):
        object.__setattr__(forged_subclass, field.name, getattr(reservation, field.name))
    with pytest.raises(TypeError):
        policy.assess_fees(forged_subclass)
