from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest
from crypto_quant_domain import (
    Money,
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
        object.__setattr__(
            result, field.name, changes.get(field.name, getattr(value, field.name))
        )
    return result


def _forged_enum(member: Any, /) -> Any:
    value = str.__new__(type(member), member.value)
    object.__setattr__(value, "_name_", "FORGED")
    object.__setattr__(value, "_value_", member.value)
    return value


def _xshe_sources() -> tuple[Any, Any]:
    market, stamp = market_rule_book(), tax_rule_book()
    return (
        type(market)(
            market.rule_book_key,
            market.rule_book_version,
            tuple(x for x in market.bands if x.venue_id == VenueId("xshe")),
        ),
        type(stamp)(
            stamp.rule_book_key,
            stamp.rule_book_version,
            tuple(x for x in stamp.bands if x.venue_id == VenueId("xshe")),
        ),
    )


def _valid(
    *,
    side: Any = v2.OrderSide.BUY,
    order_effective_at: Any = None,
    fill_effective_at: Any = None,
) -> tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any]:
    source_market, source_stamp = _xshe_sources()
    projection = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        source_market, source_stamp
    )
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
        (v2.OrderSide.BUY, v2.OrderSide.SELL),
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
        v2._market_component(projection.market_fee_rule_book),
        v2._tax_component(projection.stamp_duty_rule_book),
    )
    authority = create_cn_a_share_fee_execution_authority_v2(scope, selection)
    assert isinstance(authority, CnAShareFeeExecutionAuthorityV2)
    order_effective_at = order_effective_at or local_instant(26)
    fill_effective_at = fill_effective_at or local_instant(26, 1)
    original = source_order(
        quantity_units=100, side=side, effective_at=order_effective_at
    )
    order = replace(
        original,
        intent=replace(
            original.intent,
            instrument_id=value.instrument_id,
            quantity=replace(
                original.intent.quantity, instrument_id=str(value.instrument_id)
            ),
        ),
    )
    binding = bind_cn_a_share_fee_execution_v2(authority, order)
    assert isinstance(binding, CnAShareFeeExecutionBindingV2)
    reservation = CnAShareCashFeeRuleQueryV2.for_reservation(authority, binding)
    assert isinstance(reservation, CnAShareCashFeeRuleQueryV2)
    base_fill = make_fill(order, "8", fill_effective_at)
    price = Price(
        base_fill.price.units, base_fill.price.scale, str(value.instrument_id), str(CNY)
    )
    fill = replace(
        base_fill,
        venue_id=VenueId("xshe"),
        instrument_id=value.instrument_id,
        quantity=Quantity(
            base_fill.quantity.units, base_fill.quantity.scale, str(value.instrument_id)
        ),
        reference_price=price,
        price=price,
    )
    final = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, fill)
    assert isinstance(final, CnAShareCashFeeRuleQueryV2)
    return (
        projection,
        scope,
        selection,
        authority,
        order,
        binding,
        reservation,
        final,
        fill,
    )


def _values() -> dict[str, Any]:
    (
        projection,
        scope,
        selection,
        authority,
        _order,
        binding,
        reservation,
        final,
        _fill,
    ) = _valid()
    market = CnAShareCashMarketFeePolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    tax = CnAShareCashStampDutyTaxPolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    mr, tr = (
        market.assess_fees(reservation).result,
        tax.assess_taxes(reservation).result,
    )
    mf, tf = market.assess_fees(final).result, tax.assess_taxes(final).result
    assert mr and tr and mf and tf
    component_bad = replace(
        selection,
        market_fee_component_ref=ProfileComponentRef(
            ProfilePortType.FEE_ASSESSMENT_POLICY, "other", 2, "sha256:" + "1" * 64
        ),
    )
    authority_failure = create_cn_a_share_fee_execution_authority_v2(
        scope, component_bad
    )
    assert isinstance(authority_failure, CnAShareFeeExecutionAuthorityFailureV2)
    missing_fill = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, None)
    buffer = CnAShareFeeReservationBufferV2.create(
        market_resolution=mr, tax_resolution=tr, maximum_fill_count=5
    )
    return {
        "scope": scope,
        "selection": selection,
        "authority": authority,
        "binding": binding,
        "reservation_query": reservation,
        "final_query": final,
        "market_resolution": mr,
        "tax_resolution": tr,
        "final_market_resolution": mf,
        "final_tax_resolution": tf,
        "authority_component_failure": authority_failure,
        "missing_fill_failure": missing_fill,
        "buffer": buffer,
        "projection": projection,
    }


def _record(value: Any, /) -> str:
    return canonical_sha256(value)


def test_compact_golden_hashes_and_representative_canonical_bodies() -> None:
    values = _values()
    fixture = json.loads(FIXTURE.read_text())
    assert {name: _record(value) for name, value in values.items()} == fixture["hashes"]
    representatives = {
        type(value).__name__: json.loads(canonical_bytes(value))
        for value in values.values()
    }
    assert representatives == fixture["representative_bodies"]


def test_concrete_boundaries_reject_rule_book_binding_order_fill_and_nested_attacks() -> (
    None
):
    _, _scope, selection, authority, order, binding, reservation, final, fill = _valid()

    class InjectedBook(CnAShareMarketFeeRuleBookV2):
        def active_bands(self, *_: object) -> tuple[CnAShareMarketFeeBandV2, ...]:
            return ()

    injected = object.__new__(InjectedBook)
    for field in fields(selection.market_fee_rule_book):
        object.__setattr__(
            injected, field.name, getattr(selection.market_fee_rule_book, field.name)
        )
    with pytest.raises(TypeError, match="selection rule books"):
        replace(
            selection,
            market_fee_rule_book=injected,
            market_fee_rule_book_hash=injected.rule_book_hash,
        )

    class BindingAttack(CnAShareFeeExecutionBindingV2):
        @property
        def side(self) -> Any:
            return v2.OrderSide.SELL

    attacked = object.__new__(BindingAttack)
    with pytest.raises(TypeError, match="concrete v2"):
        CnAShareCashFeeRuleQueryV2.for_reservation(authority, attacked)
    with pytest.raises(TypeError, match="concrete"):
        bind_cn_a_share_fee_execution_v2(
            authority,
            _forge(
                order,
                intent=_forge(
                    order.intent, quantity=_forge(order.intent.quantity, units=-1)
                ),
            ),
        )
    with pytest.raises(TypeError, match="concrete Fill"):
        CnAShareCashFeeRuleQueryV2.for_final_fill(
            authority,
            binding,
            _forge(
                fill,
                execution_time=_forge(fill.execution_time, epoch_nanoseconds="bad"),
            ),
        )
    assert isinstance(
        CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, None),
        type(_values()["missing_fill_failure"]),
    )
    assert (
        reservation.side is v2.OrderSide.BUY
        and final.effective_at == fill.execution_time
    )


def test_resolution_buffer_and_policy_failures_are_not_substitutable() -> None:
    _, _, _, authority, _, _binding, reservation, final, _ = _valid()
    market = CnAShareCashMarketFeePolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    tax = CnAShareCashStampDutyTaxPolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    mr, tr = (
        market.assess_fees(reservation).result,
        tax.assess_taxes(reservation).result,
    )
    assert mr and tr
    with pytest.raises((TypeError, ValueError)):
        type(mr)(*([getattr(mr, field.name) for field in fields(mr)][:-1] + [()]))
    with pytest.raises(
        ValueError, match="reservation buffer resolution context mismatch"
    ):
        CnAShareFeeReservationBufferV2.create(
            market_resolution=mr,
            tax_resolution=tax.assess_taxes(final).result,
            maximum_fill_count=1,
        )
    forged_subjects = (
        "missing_rule_interval",
        authority.authority_hash,
        reservation.query_hash,
        "forged",
    )
    with pytest.raises(ValueError, match="fee rule failure invalid"):
        CnAShareFeeRuleFailureV2(
            reservation,
            reservation.query_hash,
            CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL,
            forged_subjects,
        )
    assert market.assess_fees(reservation).result is not None
    assert tax.assess_taxes(reservation).result is not None


def test_generated_rule_enum_members_are_not_substitutable() -> None:
    _, _, _, authority, _, _, reservation, _, _ = _valid()
    market = CnAShareCashMarketFeePolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    tax = CnAShareCashStampDutyTaxPolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    market_resolution = market.assess_fees(reservation).result
    tax_resolution = tax.assess_taxes(reservation).result
    assert market_resolution and tax_resolution

    market_rule = market_resolution.final_fill_charge_rules[0]
    forged_applicability = _forged_enum(market_rule.applicability)
    forged_market_rule = replace(market_rule, applicability=forged_applicability)
    with pytest.raises(TypeError, match="market resolution context"):
        replace(
            market_resolution,
            final_fill_charge_rules=(
                forged_market_rule,
                *market_resolution.final_fill_charge_rules[1:],
            ),
        )

    tax_rule = tax_resolution.final_fill_charge_rule
    forged_rounding = _forged_enum(tax_rule.quantization.rounding)
    forged_quantization = replace(tax_rule.quantization, rounding=forged_rounding)
    forged_tax_rule = replace(tax_rule, quantization=forged_quantization)
    with pytest.raises(TypeError, match="stamp resolution context"):
        replace(tax_resolution, final_fill_charge_rule=forged_tax_rule)


def test_authority_precedence_and_projection_fail_closed_for_untrusted_sources() -> (
    None
):
    _, scope, selection, _, _, _, _, _, _ = _valid()

    class BookSubclass(CnAShareMarketFeeRuleBookV2):
        pass

    malformed = object.__new__(BookSubclass)
    for field in fields(selection.market_fee_rule_book):
        object.__setattr__(
            malformed, field.name, getattr(selection.market_fee_rule_book, field.name)
        )
    combined = _forge(
        selection,
        access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT,
        market_fee_rule_book=malformed,
        market_fee_rule_book_hash=malformed.rule_book_hash,
    )
    first = create_cn_a_share_fee_execution_authority_v2(scope, combined)
    assert isinstance(first, CnAShareFeeExecutionAuthorityFailureV2)
    assert first.code.value == "scope_selection_mismatch"
    market, stamp = _xshe_sources()
    assert (
        project_cn_a_share_domestic_ordinary_fee_rules_v2(
            market_rule_book(), stamp
        ).code.value
        == "non_xshe_market_source"
    )
    with pytest.raises(ValueError, match="non-empty"):
        project_cn_a_share_domestic_ordinary_fee_rules_v2(
            _forge(market, bands=()), stamp
        )

    class V1BookSubclass(type(market)):
        pass

    v1_subclass = object.__new__(V1BookSubclass)
    for field in fields(market):
        object.__setattr__(v1_subclass, field.name, getattr(market, field.name))
    with pytest.raises(TypeError, match="exact v1"):
        project_cn_a_share_domestic_ordinary_fee_rules_v2(v1_subclass, stamp)
    economic = _forge(market.bands[0], handling_source_refs=())
    economic_failure = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        _forge(market, bands=(economic, *market.bands[1:])), stamp
    )
    assert economic_failure.code.value == "market_source_economic_invalid"


def test_nested_constructor_bypasses_and_policy_subclasses_fail_closed() -> None:
    projection, scope, selection, authority, _, _, reservation, _, fill = _valid()

    class SideTuple(tuple):
        pass

    with pytest.raises(TypeError, match="OrderSide tuple"):
        replace(scope, allowed_order_sides=SideTuple(scope.allowed_order_sides))

    band = selection.market_fee_rule_book.bands[0]
    with pytest.raises(ValueError, match="non-negative fee_fraction"):
        replace(band, handling_rate=_forge(band.handling_rate, units=-1))
    with pytest.raises(TypeError, match="concrete CnAShareMarketFeeBandV2"):
        replace(
            selection.market_fee_rule_book,
            bands=(_forge(band, effective_to_exclusive=band.effective_from),),
        )

    class AuthoritySubclass(CnAShareFeeExecutionAuthorityV2):
        pass

    attacked_authority = object.__new__(AuthoritySubclass)
    for field in fields(authority):
        object.__setattr__(
            attacked_authority, field.name, getattr(authority, field.name)
        )
    with pytest.raises(ValueError, match="policy authority"):
        CnAShareCashMarketFeePolicyV2(
            attacked_authority, attacked_authority.authority_hash, Scale(2)
        )

    market = CnAShareCashMarketFeePolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    tax = CnAShareCashStampDutyTaxPolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    market_resolution = market.assess_fees(reservation).result
    tax_resolution = tax.assess_taxes(reservation).result
    assert market_resolution and tax_resolution
    buffer = CnAShareFeeReservationBufferV2.create(
        market_resolution=market_resolution,
        tax_resolution=tax_resolution,
        maximum_fill_count=1,
    )

    class FillSubclass(type(fill)):
        pass

    attacked_fill = object.__new__(FillSubclass)
    for field in fields(fill):
        object.__setattr__(attacked_fill, field.name, getattr(fill, field.name))
    with pytest.raises(TypeError, match="concrete Fill"):
        buffer.require_covers_fills((attacked_fill,))

    _, source_stamp = _xshe_sources()
    with pytest.raises(ValueError, match="XSHE-only"):
        CnAShareDomesticOrdinaryFeeProjectionV2(
            projection.algorithm_id,
            market_rule_book(),
            market_rule_book().rule_book_hash,
            source_stamp,
            source_stamp.rule_book_hash,
            projection.access_route,
            projection.fee_product_class,
            projection.market_fee_rule_book,
            projection.market_fee_rule_book_hash,
            projection.stamp_duty_rule_book,
            projection.stamp_duty_rule_book_hash,
        )


def test_forged_enum_members_cannot_change_fee_semantics() -> None:
    _, scope, selection, authority, order, binding, _, _, fill = _valid()
    forged_sell = _forged_enum(v2.OrderSide.SELL)
    forged_route = _forged_enum(CnAShareExecutionAccessRoute.DOMESTIC)

    with pytest.raises(TypeError, match="OrderSide tuple"):
        replace(
            scope,
            allowed_order_sides=(v2.OrderSide.BUY, forged_sell),
        )
    with pytest.raises(TypeError, match="scope route/product"):
        replace(scope, access_route=forged_route)
    with pytest.raises(TypeError, match="rule book route/product"):
        replace(selection.market_fee_rule_book, access_route=forged_route)

    forged_order = _forge(order, intent=_forge(order.intent, side=forged_sell))
    with pytest.raises(TypeError, match="authority and order must be concrete"):
        bind_cn_a_share_fee_execution_v2(authority, forged_order)
    forged_fill = _forge(fill, side=forged_sell)
    with pytest.raises(TypeError, match="concrete Fill"):
        CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, forged_fill)


def test_spoofed_venue_string_subclass_is_not_xshe() -> None:
    _, scope, selection, _, _, _, _, _, _ = _valid()

    class SpoofStr(str):
        def __eq__(self, other: object) -> bool:
            return other == "xshe" or super().__eq__(other)

        __hash__ = str.__hash__

    forged_venue = object.__new__(VenueId)
    object.__setattr__(forged_venue, "value", SpoofStr("other"))
    assert forged_venue == VenueId("xshe")

    with pytest.raises(ValueError, match="scope venue_id must be XSHE"):
        replace(scope, venue_id=forged_venue)
    with pytest.raises(TypeError, match="concrete VenueId"):
        replace(selection.market_fee_rule_book.bands[0], venue_id=forged_venue)

    market, stamp = _xshe_sources()
    forged_band = _forge(market.bands[0], venue_id=forged_venue)
    failure = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        _forge(market, bands=(forged_band, *market.bands[1:])), stamp
    )
    assert failure.code.value == "non_xshe_market_source"
    assert failure.subject_ids[4] == "invalid"


def test_spoofed_identity_strings_cannot_pass_success_constructors() -> None:
    projection, _, _, authority, _, binding, reservation, final, _ = _valid()

    class SpoofStr(str):
        def __eq__(self, other: object) -> bool:
            return True

        __hash__ = str.__hash__

    with pytest.raises(ValueError, match="authority_key"):
        replace(authority, authority_key=SpoofStr("other"))
    with pytest.raises(ValueError, match="canonical sha256"):
        CnAShareCashMarketFeePolicyV2(
            authority, SpoofStr(authority.authority_hash), Scale(2)
        )
    with pytest.raises(ValueError, match="account_id"):
        replace(binding, account_id=SpoofStr(binding.account_id))
    assert final.fill_hash is not None
    with pytest.raises(ValueError, match="canonical sha256"):
        replace(final, fill_hash=SpoofStr(final.fill_hash))
    with pytest.raises(ValueError, match="algorithm_id"):
        replace(projection, algorithm_id=SpoofStr("other"))

    market, stamp = _xshe_sources()
    with pytest.raises(TypeError, match="exact v1 outer"):
        project_cn_a_share_domestic_ordinary_fee_rules_v2(
            _forge(market, rule_book_key=SpoofStr(market.rule_book_key)), stamp
        )

    policy = CnAShareCashMarketFeePolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    assert policy.assess_fees(reservation).result is not None


def test_interval_and_active_band_hash_failures_bind_real_evidence() -> None:
    market_source, stamp_source = _xshe_sources()
    invalid_interval = _forge(
        market_source.bands[0],
        effective_to_exclusive=market_source.bands[0].effective_from,
    )
    interval_failure = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        _forge(market_source, bands=(invalid_interval, *market_source.bands[1:])),
        stamp_source,
    )
    assert interval_failure.code.value == "market_source_interval_invalid"

    _, scope, selection, _, order, _, _, _, _ = _valid()
    active = next(
        band
        for band in selection.market_fee_rule_book.bands
        if band.contains(order.created_at.instant)
    )
    overlapping_book = replace(
        selection.market_fee_rule_book,
        bands=tuple(
            sorted(
                (*selection.market_fee_rule_book.bands, active),
                key=lambda band: (
                    band.venue_id.value,
                    band.effective_from,
                    band.effective_to_exclusive,
                    band.band_hash,
                ),
            )
        ),
    )
    overlapping_selection = replace(
        selection,
        market_fee_rule_book=overlapping_book,
        market_fee_rule_book_hash=overlapping_book.rule_book_hash,
        market_fee_component_ref=v2._market_component(overlapping_book),
    )
    overlapping_authority = create_cn_a_share_fee_execution_authority_v2(
        scope, overlapping_selection
    )
    assert isinstance(overlapping_authority, CnAShareFeeExecutionAuthorityV2)
    overlapping_binding = bind_cn_a_share_fee_execution_v2(overlapping_authority, order)
    assert isinstance(overlapping_binding, CnAShareFeeExecutionBindingV2)
    overlapping_query = CnAShareCashFeeRuleQueryV2.for_reservation(
        overlapping_authority, overlapping_binding
    )
    assert isinstance(overlapping_query, CnAShareCashFeeRuleQueryV2)
    failure = (
        CnAShareCashMarketFeePolicyV2(
            overlapping_authority, overlapping_authority.authority_hash, Scale(2)
        )
        .assess_fees(overlapping_query)
        .failure
    )
    assert (
        failure
        and failure.code is CnAShareFeeRuleFailureCodeV2.OVERLAPPING_RULE_INTERVALS
    )
    assert failure.subject_ids[-1] == canonical_sha256(
        tuple(sorted((active.band_hash, active.band_hash)))
    )
    with pytest.raises(ValueError, match="fee rule failure invalid"):
        replace(
            failure,
            subject_ids=(*failure.subject_ids[:-1], "sha256:" + "0" * 64),
        )


def test_exact_scope_error_wires_and_structured_context_failures() -> None:
    _, scope, _, authority, order, binding, _, _, _ = _valid()
    with pytest.raises(ValueError, match="^scope venue_id must be XSHE$"):
        replace(scope, venue_id=VenueId("xshg"))
    with pytest.raises(ValueError, match="^scope quote_currency_id must be CNY$"):
        replace(scope, quote_currency_id=v2.CurrencyId("USD"))
    with pytest.raises(ValueError, match="^scope settlement_currency_id must be CNY$"):
        replace(scope, settlement_currency_id=v2.CurrencyId("USD"))
    with pytest.raises(
        ValueError, match="^scope coverage interval must be finite and non-empty$"
    ):
        replace(scope, coverage_to_exclusive=scope.coverage_from)

    mismatched_scope = replace(
        scope, access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT
    )
    mismatched_authority = _forge(
        authority, scope=mismatched_scope, scope_hash=mismatched_scope.scope_hash
    )
    binding_failure = bind_cn_a_share_fee_execution_v2(mismatched_authority, order)
    assert binding_failure.code.value == "authority_scope_mismatch"

    mismatched_binding = _forge(binding, order_effective_at=local_instant(27))
    query_failure = CnAShareCashFeeRuleQueryV2.for_reservation(
        authority, mismatched_binding
    )
    assert query_failure.code.value == "reservation_context_mismatch"


def test_final_fill_execution_interval_is_lower_inclusive_upper_exclusive() -> None:
    _, _, _, authority, _, binding, _, _, fill = _valid()
    lower = replace(fill, execution_time=binding.order_effective_at)
    lower_query = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, lower)
    assert isinstance(lower_query, CnAShareCashFeeRuleQueryV2)

    upper = replace(fill, execution_time=authority.scope.coverage_to_exclusive)
    upper_failure = CnAShareCashFeeRuleQueryV2.for_final_fill(authority, binding, upper)
    assert upper_failure.code.value == "execution_time_mismatch"


def test_policy_and_projection_diagnostic_contexts_fail_closed() -> None:
    _, _, _, authority, _, _, reservation, final, fill = _valid()
    policy = CnAShareCashMarketFeePolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    forged_policy = _forge(policy, authority_hash="sha256:" + "0" * 64)
    with pytest.raises((TypeError, ValueError), match="policy context"):
        forged_policy.assess_fees(reservation)

    malformed_fill = _forge(
        fill,
        execution_time=_forge(fill.execution_time, epoch_nanoseconds="bad"),
    )
    malformed_query = _forge(
        final,
        fill=malformed_fill,
        fill_hash=canonical_sha256(malformed_fill),
        effective_at=malformed_fill.execution_time,
    )
    with pytest.raises(TypeError, match="query context"):
        policy.assess_fees(malformed_query)

    market, stamp = _xshe_sources()
    malformed_venue = _forge(market.bands[0], venue_id="xshe")
    venue_failure = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        _forge(market, bands=(malformed_venue, *market.bands[1:])), stamp
    )
    assert venue_failure.code.value == "non_xshe_market_source"
    assert venue_failure.subject_ids[4] == "invalid"

    bool_rate = _forge(market.bands[0].handling_rate, units=True)
    economic_band = _forge(market.bands[0], handling_rate=bool_rate)
    economic_failure = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        _forge(market, bands=(economic_band, *market.bands[1:])), stamp
    )
    assert economic_failure.code.value == "market_source_economic_invalid"

    class NegativeInt(int):
        def __lt__(self, other: object) -> bool:
            return False

    subclass_rate = _forge(market.bands[0].handling_rate, units=NegativeInt(-1))
    subclass_failure = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        _forge(
            market,
            bands=(
                _forge(market.bands[0], handling_rate=subclass_rate),
                *market.bands[1:],
            ),
        ),
        stamp,
    )
    assert subclass_failure.code.value == "market_source_economic_invalid"


def test_projection_failure_uses_canonical_band_order() -> None:
    market, stamp = _xshe_sources()
    early = _forge(
        market.bands[0], effective_to_exclusive=market.bands[0].effective_from
    )
    late = _forge(
        market.bands[1], effective_to_exclusive=market.bands[1].effective_from
    )
    failure = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        _forge(market, bands=(late, early)), stamp
    )
    assert failure.code.value == "market_source_interval_invalid"
    assert failure.subject_ids[4] == v2._raw_band_hash(early)


def test_missing_interval_and_sell_transition_buffer_economics() -> None:
    _, scope, selection, _, order, _, _, _, _ = _valid()
    empty_book = replace(selection.market_fee_rule_book, bands=())
    empty_selection = replace(
        selection,
        market_fee_rule_book=empty_book,
        market_fee_rule_book_hash=empty_book.rule_book_hash,
        market_fee_component_ref=v2._market_component(empty_book),
    )
    empty_authority = create_cn_a_share_fee_execution_authority_v2(
        scope, empty_selection
    )
    assert isinstance(empty_authority, CnAShareFeeExecutionAuthorityV2)
    empty_binding = bind_cn_a_share_fee_execution_v2(empty_authority, order)
    assert isinstance(empty_binding, CnAShareFeeExecutionBindingV2)
    empty_query = CnAShareCashFeeRuleQueryV2.for_reservation(
        empty_authority, empty_binding
    )
    assert isinstance(empty_query, CnAShareCashFeeRuleQueryV2)
    missing = (
        CnAShareCashMarketFeePolicyV2(
            empty_authority, empty_authority.authority_hash, Scale(2)
        )
        .assess_fees(empty_query)
        .failure
    )
    assert (
        missing and missing.code is CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL
    )
    assert missing.subject_ids[-1] == canonical_sha256(())

    _, _, _, authority, _, _, reservation, final, fill = _valid(
        side=v2.OrderSide.SELL,
        order_effective_at=local_instant(28),
        fill_effective_at=local_instant(28),
    )
    market_policy = CnAShareCashMarketFeePolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    tax_policy = CnAShareCashStampDutyTaxPolicyV2(
        authority, authority.authority_hash, Scale(2)
    )
    reservation_market = market_policy.assess_fees(reservation).result
    reservation_tax = tax_policy.assess_taxes(reservation).result
    final_market = market_policy.assess_fees(final).result
    final_tax = tax_policy.assess_taxes(final).result
    assert reservation_market and reservation_tax and final_market and final_tax
    assert reservation_market.reservation_charge_rules[0].rate.units == 487
    assert final_market.final_fill_charge_rules[0].rate.units == 341
    assert reservation_tax.reservation_charge_rule.applicability.value == "applies"
    assert final_tax.final_fill_charge_rule.applicability.value == "always"
    assert reservation_tax.reservation_charge_rule.rate.units == 1
    assert final_tax.final_fill_charge_rule.rate.units == 5
    assert all(
        rule.applicability.value == "not_applicable"
        for rule in final_market.final_order_not_applicable_rules
    )
    assert (
        final_tax.final_order_not_applicable_rule.applicability.value
        == "not_applicable"
    )

    buffer = CnAShareFeeReservationBufferV2.create(
        market_resolution=reservation_market,
        tax_resolution=reservation_tax,
        maximum_fill_count=2,
    )
    assert buffer.market_charge_rule.flat_amount == Money(3, Scale(2), "CNY")
    assert buffer.tax_charge_rule.flat_amount == Money(1, Scale(2), "CNY")
    buffer.require_covers_fills((fill, fill))
    with pytest.raises(ValueError, match="actual fill count exceeds reservation bound"):
        buffer.require_covers_fills((fill, fill, fill))
