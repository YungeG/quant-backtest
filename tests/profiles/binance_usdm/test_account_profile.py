from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    CurrencyId,
    DomainIdKind,
    InstrumentId,
    RoundingPolicy,
    Scale,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import (
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FeeReservationRuleSource,
    FeeReserveFundingSource,
    FinalFeeApplicability,
    FinalFeeRuleSource,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAccountProfileFailureCode,
    BinanceUsdmAccountProfileModel,
    BinanceUsdmAccountProfileResolution,
    BinanceUsdmAccountProfileScope,
    BinanceUsdmAccountSourceKind,
)

from tests.kernel.fees._fixtures import assessment_time, domain_id, fill_basis

from ._account_profile_fixtures import (
    CAPTURED_AT,
    EVALUATED_AT,
    MILLISECOND,
    account_band,
    account_book,
    account_query,
    account_source_ref,
    simulation_instant,
    source_refs,
)


def _resolve(**kwargs):
    return BinanceUsdmAccountProfileModel().resolve_account_profile(
        account_query(**kwargs)
    )


def test_maps_cross_single_asset_account_to_fee_and_leverage_evidence() -> None:
    outcome = _resolve()

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.account_id == "account-1"
    assert result.account_scope is BinanceUsdmAccountProfileScope.STANDARD_UM
    assert result.can_trade
    assert result.position_mode == "one_way"
    assert result.asset_mode == "single_asset"
    assert result.margin_type == "CROSSED"
    assert not result.is_auto_add_margin
    assert not result.fee_burn
    assert result.fee_tier == 0
    assert result.trade_group_id == -1
    assert result.reporting_currency_id == CurrencyId("USDT")
    assert result.fee_currency_id == CurrencyId("USDT")
    assert result.fee_scale == Scale(8)
    assert result.leverage_evidence.selected_leverage.units == 10
    assert result.leverage_evidence.selected_leverage.scale == Scale(0)
    assert (
        result.leverage_evidence.selected_leverage.basis
        == "notional_per_initial_margin"
    )
    symbol_ref = next(
        value
        for value in result.active_band.source_refs
        if value.source_kind is BinanceUsdmAccountSourceKind.SYMBOL_CONFIG
    )
    assert result.leverage_evidence.source_key == symbol_ref.source_key
    assert result.leverage_evidence.source_hash == symbol_ref.source_hash
    assert (
        result.fee_reserve_funding_source
        is FeeReserveFundingSource.AVAILABLE_MARGIN
    )

    assert (
        result.fee_reservation_rule_set.account_fee_schedule_ref
        == result.account_fee_schedule_ref
    )
    assert (
        result.final_fee_rule_set.account_fee_schedule_ref
        == result.account_fee_schedule_ref
    )
    reservation_account = next(
        rule
        for rule in result.fee_reservation_rule_set.charge_rules
        if rule.source is FeeReservationRuleSource.ACCOUNT_SCHEDULE
    )
    assert reservation_account.rate is not None
    assert reservation_account.rate.units == 50_000
    assert reservation_account.rate.scale == Scale(8)
    assert (
        reservation_account.quantization.rounding is RoundingPolicy.CEILING
    )
    reservation_coverage = tuple(
        rule
        for rule in result.fee_reservation_rule_set.charge_rules
        if rule.source is not FeeReservationRuleSource.ACCOUNT_SCHEDULE
    )
    assert all(rule.basis.value == "order_notional" for rule in reservation_coverage)
    assert all(rule.rate is not None and rule.rate.units == 0 for rule in reservation_coverage)

    final_account = tuple(
        rule
        for rule in result.final_fee_rule_set.charge_rules
        if rule.source is FinalFeeRuleSource.ACCOUNT_SCHEDULE
    )
    maker = next(
        rule for rule in final_account if rule.applicability is FinalFeeApplicability.MAKER_ONLY
    )
    taker = next(
        rule for rule in final_account if rule.applicability is FinalFeeApplicability.TAKER_ONLY
    )
    assert maker.rate is not None and maker.rate.units == 20_000
    assert taker.rate is not None and taker.rate.units == 50_000
    assert maker.quantization.rounding is RoundingPolicy.TOWARD_ZERO
    assert taker.quantization.rounding is RoundingPolicy.TOWARD_ZERO
    final_coverage = tuple(
        rule
        for rule in result.final_fee_rule_set.charge_rules
        if rule.source is not FinalFeeRuleSource.ACCOUNT_SCHEDULE
    )
    assert all(rule.calculation_basis.value == "notional_rate" for rule in final_coverage)
    assert all(rule.rate is not None and rule.rate.units == 0 for rule in final_coverage)
    assert not result.decision_grade_eligible


def test_reservation_uses_worse_rate_even_when_maker_exceeds_taker() -> None:
    outcome = _resolve(
        book=account_book(
            bands=(
                account_band(
                    maker_commission_rate="0.00070000",
                    taker_commission_rate="0.00050000",
                ),
            )
        )
    )
    assert outcome.result is not None
    account_rule = next(
        rule
        for rule in outcome.result.fee_reservation_rule_set.charge_rules
        if rule.source is FeeReservationRuleSource.ACCOUNT_SCHEDULE
    )
    assert account_rule.rate is not None
    assert account_rule.rate.units == 70_000


def test_visibility_and_input_order_are_deterministic() -> None:
    band = account_band()
    before = _resolve(captured_at=simulation_instant(EVALUATED_AT))
    at = _resolve(captured_at=band.available_at)
    after = _resolve()

    assert before.failure is not None
    assert before.failure.code is BinanceUsdmAccountProfileFailureCode.PROFILE_NOT_AVAILABLE
    assert at.result is not None
    assert after.result is not None

    forward = _resolve(book=account_book(bands=(band,)))
    reverse = _resolve(book=account_book(bands=tuple(reversed((band,)))))
    repeated = _resolve(book=account_book(bands=(band,)))
    assert forward.to_canonical_dict() == reverse.to_canonical_dict()
    assert repeated.to_canonical_dict() == forward.to_canonical_dict()


def test_historical_fee_and_leverage_transition_is_half_open() -> None:
    transition = EVALUATED_AT
    first_refs = source_refs()
    second_refs = tuple(
        account_source_ref(
            kind,
            revision_id=f"{kind.value}-v2",
            supersedes_revision_id=f"{kind.value}-v1",
        )
        for kind in BinanceUsdmAccountSourceKind
    )
    first = account_band(
        band_id="account-profile-v1",
        effective_from=UtcInstant(transition.epoch_nanoseconds - 2 * MILLISECOND),
        effective_to_exclusive=transition,
        available_at=simulation_instant(
            UtcInstant(transition.epoch_nanoseconds - 2 * MILLISECOND)
        ),
        leverage="5",
        maker_commission_rate="0.00010000",
        taker_commission_rate="0.00040000",
        refs=first_refs,
    )
    second = account_band(
        band_id="account-profile-v2",
        effective_from=transition,
        effective_to_exclusive=UtcInstant(
            transition.epoch_nanoseconds + 2 * MILLISECOND
        ),
        available_at=simulation_instant(transition),
        leverage="20.0",
        fee_tier=1,
        maker_commission_rate="0.00020000",
        taker_commission_rate="0.00050000",
        refs=second_refs,
    )
    book = account_book(
        bands=(second, first),
        coverage_from=first.effective_from,
        coverage_to_exclusive=second.effective_to_exclusive,
    )

    before = _resolve(
        book=book,
        evaluated_at=UtcInstant(transition.epoch_nanoseconds - 1),
    )
    at = _resolve(book=book, evaluated_at=transition)
    after = _resolve(
        book=book,
        evaluated_at=UtcInstant(transition.epoch_nanoseconds + 1),
    )

    assert before.result is not None
    assert before.result.active_band.band_id == "account-profile-v1"
    assert before.result.leverage_evidence.selected_leverage.units == 5
    assert at.result is not None
    assert at.result.active_band.band_id == "account-profile-v2"
    assert at.result.leverage_evidence.selected_leverage.units == 20
    assert at.result.fee_tier == 1
    assert after.to_canonical_dict() != at.to_canonical_dict()


def test_source_revision_branch_gap_duplicate_and_changed_bytes_fail_closed() -> None:
    transition = EVALUATED_AT
    first_refs = source_refs()
    first = account_band(
        effective_from=UtcInstant(transition.epoch_nanoseconds - MILLISECOND),
        effective_to_exclusive=transition,
        available_at=simulation_instant(
            UtcInstant(transition.epoch_nanoseconds - MILLISECOND)
        ),
        refs=first_refs,
    )

    def outcome_for(second_refs, *, band_id: str = "account-profile-v2"):
        second = account_band(
            band_id=band_id,
            effective_from=transition,
            effective_to_exclusive=UtcInstant(
                transition.epoch_nanoseconds + MILLISECOND
            ),
            available_at=simulation_instant(transition),
            refs=second_refs,
        )
        return _resolve(
            book=account_book(
                bands=(first, second),
                coverage_from=first.effective_from,
                coverage_to_exclusive=second.effective_to_exclusive,
            )
        )

    symbol = next(
        value
        for value in first_refs
        if value.source_kind is BinanceUsdmAccountSourceKind.SYMBOL_CONFIG
    )
    cases = (
        tuple(
            account_source_ref(
                value.source_kind,
                revision_id="symbol-config-v2",
                supersedes_revision_id="wrong-parent",
            )
            if value is symbol
            else value
            for value in first_refs
        ),
        tuple(
            account_source_ref(
                value.source_kind,
                revision_id="symbol-config-v3",
                supersedes_revision_id="symbol-config-v0",
            )
            if value is symbol
            else value
            for value in first_refs
        ),
        tuple(
            replace(value, source_hash="sha256:" + "f" * 64)
            if value is symbol
            else value
            for value in first_refs
        ),
    )
    for refs in cases:
        outcome = outcome_for(refs)
        assert outcome.failure is not None
        assert outcome.failure.code is BinanceUsdmAccountProfileFailureCode.SOURCE_IDENTITY_CONFLICT

    duplicate = outcome_for(first_refs, band_id=first.band_id)
    assert duplicate.failure is not None
    assert duplicate.failure.code is BinanceUsdmAccountProfileFailureCode.SOURCE_IDENTITY_CONFLICT


def test_frozen_failure_precedence_covers_all_business_failures() -> None:
    other_instrument = InstrumentId(VenueId("binance_usdm"), "other-perpetual")
    late = account_band(
        available_at=simulation_instant(
            UtcInstant(CAPTURED_AT.epoch_nanoseconds + MILLISECOND)
        )
    )
    outside = account_band(
        effective_from=UtcInstant(EVALUATED_AT.epoch_nanoseconds + MILLISECOND),
        effective_to_exclusive=UtcInstant(EVALUATED_AT.epoch_nanoseconds + 2 * MILLISECOND),
    )
    overlap = replace(account_band(), band_id="overlap-v2")
    refs = source_refs()
    conflicting_refs = refs[:-1] + (
        account_source_ref(BinanceUsdmAccountSourceKind.ACCOUNT_CONFIG),
    )

    cases = (
        (BinanceUsdmAccountProfileFailureCode.MISSING_PROFILE_BANDS, {"book": account_book(bands=())}),
        (
            BinanceUsdmAccountProfileFailureCode.INSTRUMENT_METADATA_MISMATCH,
            {"book": account_book(instrument_id=other_instrument)},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.ACCOUNT_CONTEXT_MISMATCH,
            {"book": account_book(account_id="other-account")},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.PROFILE_NOT_AVAILABLE,
            {"book": account_book(bands=(late,))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.MISSING_PROFILE_INTERVAL,
            {"book": account_book(bands=(outside,))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.OVERLAPPING_PROFILE_INTERVALS,
            {"book": account_book(bands=(account_band(), overlap))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.ACCOUNT_TRADING_DISABLED,
            {"book": account_book(bands=(account_band(can_trade=False),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.PORTFOLIO_MARGIN_UNSUPPORTED,
            {"book": account_book(bands=(account_band(scope=BinanceUsdmAccountProfileScope.PORTFOLIO_MARGIN_UM),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.HEDGE_MODE_UNSUPPORTED,
            {"book": account_book(bands=(account_band(dual_side_position=True),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.MULTI_ASSET_MODE_UNSUPPORTED,
            {"book": account_book(bands=(account_band(multi_assets_margin=True),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.ISOLATED_MARGIN_UNSUPPORTED,
            {"book": account_book(bands=(account_band(margin_type="ISOLATED"),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.AUTO_ADD_MARGIN_UNSUPPORTED,
            {"book": account_book(bands=(account_band(is_auto_add_margin=True),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.BNB_FEE_DISCOUNT_UNSUPPORTED,
            {"book": account_book(bands=(account_band(fee_burn=True),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.REPORTING_CURRENCY_MISMATCH,
            {"reporting_currency_id": CurrencyId("BUSD")},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.INVALID_DECIMAL_FIELD,
            {"book": account_book(bands=(account_band(max_notional_value="1e6"),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.INVALID_LEVERAGE,
            {"book": account_book(bands=(account_band(leverage="1.5"),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.NEGATIVE_COMMISSION_UNSUPPORTED,
            {"book": account_book(bands=(account_band(maker_commission_rate="-0.00010000"),))},
        ),
        (
            BinanceUsdmAccountProfileFailureCode.SOURCE_IDENTITY_CONFLICT,
            {"book": account_book(bands=(account_band(refs=conflicting_refs),))},
        ),
    )

    assert len(cases) == len(BinanceUsdmAccountProfileFailureCode)
    for expected, kwargs in cases:
        outcome = _resolve(**kwargs)
        assert outcome.result is None, expected
        assert outcome.failure is not None, expected
        assert outcome.failure.code is expected

    multi_defect = _resolve(
        book=account_book(
            bands=(),
            instrument_id=other_instrument,
            account_id="other-account",
        )
    )
    assert multi_defect.failure is not None
    assert multi_defect.failure.code is BinanceUsdmAccountProfileFailureCode.MISSING_PROFILE_BANDS


def test_zero_commission_and_leverage_boundaries_are_supported() -> None:
    for leverage, expected_units in (("1", 1), ("10.0", 10), ("125.000", 125)):
        outcome = _resolve(
            book=account_book(
                bands=(
                    account_band(
                        leverage=leverage,
                        maker_commission_rate="0.00000000",
                        taker_commission_rate="0.00000000",
                    ),
                )
            )
        )
        assert outcome.result is not None
        assert outcome.result.leverage_evidence.selected_leverage.units == expected_units


def test_schedule_digest_preserves_raw_rate_and_fee_tier_identity() -> None:
    base = _resolve()
    same_value_short_scale = _resolve(
        book=account_book(
            bands=(account_band(maker_commission_rate="0.0002"),)
        )
    )
    different_tier = _resolve(
        book=account_book(bands=(account_band(fee_tier=1),))
    )
    assert base.result is not None
    assert same_value_short_scale.result is not None
    assert different_tier.result is not None
    assert (
        base.result.account_fee_schedule_ref.schedule_digest
        != same_value_short_scale.result.account_fee_schedule_ref.schedule_digest
    )
    assert (
        base.result.account_fee_schedule_ref.schedule_digest
        != different_tier.result.account_fee_schedule_ref.schedule_digest
    )


def test_generic_fee_engine_applies_actual_fill_liquidity() -> None:
    def usdt_fill_basis(liquidity: str) -> FeeAssessmentBasisEvidence:
        basis = fill_basis(liquidity=liquidity)
        source_fill = basis.direct_fills[0]
        price = replace(source_fill.price, quote_currency="USDT")
        translated_fill = replace(
            source_fill,
            reference_price=price,
            price=price,
            slippage_amount=replace(source_fill.slippage_amount, currency="USDT"),
        )
        return replace(basis, direct_fills=(translated_fill,))

    outcome = _resolve()
    assert outcome.result is not None
    rule_set = outcome.result.final_fee_rule_set
    engine = FeeAssessmentEngine()

    maker = engine.assess(
        basis=usdt_fill_basis("maker"),
        rule_set=rule_set,
        fee_assessment_id=domain_id(DomainIdKind.FEE, "7"),
        assessment_time=assessment_time(),
    )
    taker = engine.assess(
        basis=usdt_fill_basis("taker"),
        rule_set=rule_set,
        fee_assessment_id=domain_id(DomainIdKind.FEE, "8"),
        assessment_time=assessment_time(),
    )
    assert maker.result is not None
    assert taker.result is not None
    assert maker.result.assessment.amount.units * 5 == taker.result.assessment.amount.units * 2


def test_resolution_constructor_rejects_forged_authority() -> None:
    outcome = _resolve()
    assert outcome.result is not None
    assert isinstance(outcome.result, BinanceUsdmAccountProfileResolution)
    with pytest.raises(ValueError, match="resolution fields"):
        replace(outcome.result, model_digest="sha256:" + "0" * 64)
