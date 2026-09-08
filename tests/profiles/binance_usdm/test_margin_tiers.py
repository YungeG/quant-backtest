from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    CashBalanceKey,
    Money,
    PositionBalanceKey,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Quantity,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    LedgerBalanceRegistration,
    LinearInstrumentMarginFailureCode,
    LinearInstrumentMarginModel,
    LinearInstrumentMarginRequest,
    LinearMarginLeverageEvidence,
    LinearMarginMarkEvidence,
    LinearMarginTierBoundaryConvention,
    LinearPerpetualContract,
    ProfilePortType,
    ResolvedMark,
    StaleMarkPolicy,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmMarginTierFailureCode,
    BinanceUsdmMarginTierModel,
    BinanceUsdmMarginTierQuery,
    BinanceUsdmMarginTierScope,
    BinanceUsdmMarginTierSourceRef,
)
from tests.profiles.binance_usdm._fixtures import RENAME_AT
from tests.profiles.binance_usdm._margin_tier_fixtures import (
    CONTRACT_INFO_STATUS_UPDATE,
    USER_DATA_LEVERAGE_BRACKET,
    band,
    complete_bands,
    margin_tier_query,
    simulation_instant,
)


def _failure_code(query: BinanceUsdmMarginTierQuery):
    outcome = BinanceUsdmMarginTierModel().resolve_margin_tiers(query)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.failure_hash == canonical_sha256(outcome.failure)
    return outcome.failure.code


def test_resolves_archived_contract_info_brackets_to_generic_margin_rules() -> None:
    first, second = complete_bands()

    outcome = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        margin_tier_query(second, first)
    )

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.component_ref.port_type is ProfilePortType.MARGIN_MODEL
    assert result.component_ref.component_key == "crypto.binance_usdm.margin-tiers.v1"
    assert result.visible_bands == (first, second)
    assert result.active_band == second
    assert result.margin_rule_book.instrument_id == second.instrument_id
    assert len(result.margin_rule_book.intervals) == 2
    assert result.active_interval == result.margin_rule_book.intervals[1]
    assert result.active_tiers == result.active_interval.tiers
    assert result.tier_boundary_convention is (
        LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE
    )
    assert result.active_interval.tier_boundary_convention is (
        result.tier_boundary_convention
    )
    assert result.active_tiers[0].notional_floor == Money(0, Scale(0), "USDT")
    assert result.active_tiers[0].notional_cap == Money(
        10_000, Scale(0), "USDT"
    )
    assert result.active_tiers[0].maximum_leverage == Rate(
        25, Scale(0), "notional_per_initial_margin"
    )
    assert result.active_tiers[0].maintenance_margin_rate == Rate(
        2, Scale(2), "maintenance_margin_fraction_of_notional"
    )
    assert result.active_tiers[1].maintenance_margin_deduction == Money(
        300, Scale(0), "USDT"
    )
    assert result.finite_terminal_notional_cap == Money(
        200_000, Scale(0), "USDT"
    )
    assert result.coverage_from == first.effective_from
    assert result.coverage_to_exclusive == second.effective_to_exclusive
    assert not result.decision_grade_eligible
    assert result.resolution_hash == canonical_sha256(result)


def test_time_boundaries_and_input_order_are_point_in_time_exact() -> None:
    first, second = complete_bands()
    model = BinanceUsdmMarginTierModel()
    before = model.resolve_margin_tiers(
        margin_tier_query(
            first,
            second,
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds - 1),
        )
    )
    at = model.resolve_margin_tiers(
        margin_tier_query(first, second, evaluated_at=RENAME_AT)
    )
    after = model.resolve_margin_tiers(
        margin_tier_query(
            first,
            second,
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 1),
        )
    )
    reverse = model.resolve_margin_tiers(margin_tier_query(second, first))
    ordered = model.resolve_margin_tiers(margin_tier_query(first, second))

    assert before.result is not None
    assert before.result.active_band == first
    assert at.result is not None
    assert at.result.active_band == second
    assert after.result is not None
    assert after.result.active_band == second
    assert reverse == ordered


def test_late_contract_info_never_backfills_historical_tiers() -> None:
    late = simulation_instant(
        UtcInstant(RENAME_AT.epoch_nanoseconds + 100)
    )
    first, second = complete_bands(second_available_at=late)

    hidden = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        margin_tier_query(first, second)
    )
    visible = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        margin_tier_query(
            first,
            second,
            captured_at=simulation_instant(
                UtcInstant(late.instant.epoch_nanoseconds + 1)
            ),
        )
    )

    assert hidden.failure is not None
    assert hidden.failure.code is (
        BinanceUsdmMarginTierFailureCode.MISSING_TIER_INTERVAL
    )
    assert visible.result is not None
    assert visible.result.active_band == second


def test_account_adjusted_and_authenticated_brackets_are_never_public_history() -> None:
    first, second = complete_bands()
    account_adjusted = replace(
        second,
        scope=BinanceUsdmMarginTierScope.ACCOUNT_ADJUSTED,
    )
    with_coef = replace(second, notional_coef="1.0")
    user_data = replace(
        second,
        source_ref=BinanceUsdmMarginTierSourceRef(
            source_key="fapi/v1/leverageBracket",
            source_hash="sha256:" + "a" * 64,
            source_kind=USER_DATA_LEVERAGE_BRACKET,
        ),
    )

    for rejected in (account_adjusted, with_coef, user_data):
        assert _failure_code(margin_tier_query(first, rejected)) is (
            BinanceUsdmMarginTierFailureCode.ACCOUNT_ADJUSTED_TIER_UNSUPPORTED
        )


@pytest.mark.parametrize(
    ("query", "expected"),
    (
        (
            margin_tier_query(),
            BinanceUsdmMarginTierFailureCode.MISSING_TIER_BANDS,
        ),
        (
            replace(
                margin_tier_query(*complete_bands()),
                evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 11),
            ),
            BinanceUsdmMarginTierFailureCode.INSTRUMENT_METADATA_MISMATCH,
        ),
        (
            margin_tier_query(
                *(
                    replace(
                        value,
                        available_at=simulation_instant(
                            UtcInstant(RENAME_AT.epoch_nanoseconds + 100)
                        ),
                    )
                    for value in complete_bands()
                )
            ),
            BinanceUsdmMarginTierFailureCode.TIER_NOT_AVAILABLE,
        ),
        (
            margin_tier_query(
                replace(
                    complete_bands()[0],
                    effective_to_exclusive=UtcInstant(
                        RENAME_AT.epoch_nanoseconds - 1
                    ),
                ),
                complete_bands()[1],
            ),
            BinanceUsdmMarginTierFailureCode.MISSING_TIER_INTERVAL,
        ),
        (
            margin_tier_query(
                replace(
                    complete_bands()[0],
                    effective_to_exclusive=UtcInstant(
                        RENAME_AT.epoch_nanoseconds + 1
                    ),
                ),
                complete_bands()[1],
            ),
            BinanceUsdmMarginTierFailureCode.OVERLAPPING_TIER_INTERVALS,
        ),
        (
            margin_tier_query(
                complete_bands()[0],
                replace(
                    complete_bands()[1],
                    scope=BinanceUsdmMarginTierScope.ACCOUNT_ADJUSTED,
                    brackets=(
                        replace(
                            complete_bands()[1].brackets[0],
                            notional_cap="1E4",
                        ),
                    ),
                ),
            ),
            BinanceUsdmMarginTierFailureCode.ACCOUNT_ADJUSTED_TIER_UNSUPPORTED,
        ),
        (
            margin_tier_query(
                complete_bands()[0],
                replace(
                    complete_bands()[1],
                    brackets=(
                        replace(
                            complete_bands()[1].brackets[0],
                            notional_cap="1E4",
                        ),
                        *complete_bands()[1].brackets[1:],
                    ),
                ),
            ),
            BinanceUsdmMarginTierFailureCode.INVALID_DECIMAL_FIELD,
        ),
        (
            margin_tier_query(
                complete_bands()[0],
                replace(
                    complete_bands()[1],
                    brackets=tuple(reversed(complete_bands()[1].brackets)),
                ),
            ),
            BinanceUsdmMarginTierFailureCode.INVALID_BRACKET_GEOMETRY,
        ),
        (
            margin_tier_query(
                complete_bands()[0],
                band(
                    "margin-tiers-v2",
                    effective_from=RENAME_AT,
                    effective_to_exclusive=complete_bands()[1].effective_to_exclusive,
                    brackets=complete_bands()[1].brackets,
                    source_kind=CONTRACT_INFO_STATUS_UPDATE,
                ),
            ),
            BinanceUsdmMarginTierFailureCode.UNSUPPORTED_MARGIN_SEMANTICS,
        ),
        (
            margin_tier_query(
                complete_bands()[0],
                replace(
                    complete_bands()[1],
                    source_ref=BinanceUsdmMarginTierSourceRef(
                        source_key=complete_bands()[0].source_ref.source_key,
                        source_hash="sha256:" + "f" * 64,
                        source_kind=complete_bands()[0].source_ref.source_kind,
                    ),
                ),
            ),
            BinanceUsdmMarginTierFailureCode.METADATA_CONFLICT,
        ),
    ),
)
def test_provider_failures_follow_frozen_precedence(
    query: BinanceUsdmMarginTierQuery,
    expected: BinanceUsdmMarginTierFailureCode,
) -> None:
    assert len(BinanceUsdmMarginTierFailureCode) == 10
    assert _failure_code(query) is expected


def _margin_request(result, *, notional: int, leverage: int):
    metadata = result.query.instrument_metadata
    instrument = metadata.instrument
    settlement = instrument.settlement_currency
    assert settlement is not None
    evaluated_at = SimulationInstant(
        result.query.evaluated_at,
        TimelinePhase(100, "margin_requirement"),
        SourceSequence(0),
    )
    policy = StaleMarkPolicy(
        "binance-usdm-margin-mark.v1",
        1,
        PricePurpose.MARGIN,
        0,
        False,
    )
    mark = ResolvedMark(
        instrument_id=instrument.instrument_id,
        quote_currency_id=settlement,
        price_purpose=PricePurpose.MARGIN,
        price=Price(
            1,
            Scale(0),
            str(instrument.instrument_id),
            str(settlement),
        ),
        observed_at=result.query.evaluated_at,
        available_at=result.query.evaluated_at,
        resolved_at=result.query.evaluated_at,
        age_nanoseconds=0,
        stream_id="binance-usdm-margin-mark.stream.v1",
        source_event_id="binance-usdm-margin-mark-event",
        revision_id="binance-usdm-margin-mark-revision",
        stale_policy_key=policy.policy_key,
        stale_policy_version=policy.policy_version,
        stale_policy_hash=policy.policy_hash,
    )
    account_id = "binance-usdm-margin-account"
    return LinearInstrumentMarginRequest(
        position_key=PositionBalanceKey(
            account_id,
            instrument.instrument_id.venue,
            instrument.instrument_id,
        ),
        contract=LinearPerpetualContract(
            instrument=instrument,
            quantity_scale=Scale(0),
            price_scale=Scale(0),
            contract_multiplier=Rate(
                1, Scale(0), "base_quantity_per_contract"
            ),
        ),
        exposure_quantity=Quantity(
            notional,
            Scale(0),
            str(instrument.instrument_id),
        ),
        evaluated_at=evaluated_at,
        leverage_evidence=LinearMarginLeverageEvidence(
            account_id=account_id,
            instrument_id=instrument.instrument_id,
            selected_leverage=Rate(
                leverage, Scale(0), "notional_per_initial_margin"
            ),
            effective_from=result.query.evaluated_at,
            effective_to_exclusive=None,
            available_at=SimulationInstant(
                UtcInstant(result.query.evaluated_at.epoch_nanoseconds - 1),
                TimelinePhase(50, "account_leverage_evidence"),
                SourceSequence(0),
            ),
            source_key="binance-usdm-account-leverage.v1",
            source_hash="sha256:" + "1" * 64,
        ),
        rule_book=result.margin_rule_book,
        margin_mark_evidence=LinearMarginMarkEvidence(mark, policy),
        settlement_cash_registration=LedgerBalanceRegistration(
            CashBalanceKey(
                account_id,
                instrument.instrument_id.venue,
                settlement,
            ),
            Scale(0),
        ),
        requirement_quantization=QuantizationPolicy(
            "binance-usdm-margin-requirement.v1",
            Scale(0),
            RoundingPolicy.CEILING,
        ),
    )


def test_provider_mi_is_not_selected_leverage_and_cf_is_not_recomputed() -> None:
    outcome = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        margin_tier_query(*complete_bands())
    )
    assert outcome.result is not None
    result = outcome.result
    model = LinearInstrumentMarginModel()

    below_mi = model.evaluate_margin(
        _margin_request(result, notional=10_000, leverage=5)
    )
    between_mi_ma = model.evaluate_margin(
        _margin_request(result, notional=10_000, leverage=22)
    )
    above_ma = model.evaluate_margin(
        _margin_request(result, notional=10_000, leverage=26)
    )
    deduction = model.evaluate_margin(
        _margin_request(result, notional=50_000, leverage=10)
    )

    assert below_mi.result is not None
    assert between_mi_ma.result is not None
    assert above_ma.failure is not None
    assert above_ma.failure.code is (
        LinearInstrumentMarginFailureCode.LEVERAGE_EXCEEDS_TIER_MAXIMUM
    )
    assert deduction.result is not None
    assert deduction.result.maintenance_margin == Money(2_200, Scale(0), "USDT")


def test_raw_trailing_zeros_enter_identity_but_not_mapped_economics() -> None:
    first, second = complete_bands()
    normalized = replace(
        second,
        brackets=(
            replace(second.brackets[0], notional_cap="10000.0"),
            *second.brackets[1:],
        ),
    )
    model = BinanceUsdmMarginTierModel()
    original = model.resolve_margin_tiers(margin_tier_query(first, second))
    changed = model.resolve_margin_tiers(margin_tier_query(first, normalized))

    assert original.result is not None
    assert changed.result is not None
    assert second.brackets[0].bracket_hash != normalized.brackets[0].bracket_hash
    assert original.result.active_tiers == changed.result.active_tiers
    assert original != changed


def test_resolution_and_failure_constructors_reject_forgery() -> None:
    success = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        margin_tier_query(*complete_bands())
    )
    assert success.result is not None
    with pytest.raises(ValueError, match="resolution fields"):
        replace(success.result, decision_grade_eligible=True)

    failed = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        margin_tier_query()
    )
    assert failed.failure is not None
    with pytest.raises(ValueError, match="failure fields"):
        replace(
            failed.failure,
            code=BinanceUsdmMarginTierFailureCode.METADATA_CONFLICT,
        )
