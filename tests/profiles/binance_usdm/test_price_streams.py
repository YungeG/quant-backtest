from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import CurrencyId, PricePurpose, UtcInstant
from crypto_quant_trading import MarkResolutionFailureCode
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmHistoricalPriceBook,
    BinanceUsdmPricePurposeResolution,
    BinanceUsdmPriceStreamFailureCode,
    BinanceUsdmPriceStreamModel,
)

from ._price_stream_fixtures import (
    BAR_MIDDLE,
    BAR_START,
    CAPTURED_AT,
    MILLISECOND,
    REQUESTED_AT,
    aggregate_trade,
    coverage,
    mark_bars,
    price_book,
    price_query,
    simulation_instant,
    stale_policy,
)


def _resolve(purpose: PricePurpose, **kwargs):
    return BinanceUsdmPriceStreamModel().resolve_price_purpose(
        price_query(purpose, **kwargs)
    )


def test_maps_first_party_sources_to_separate_price_purpose_streams() -> None:
    execution = _resolve(PricePurpose.EXECUTION_REFERENCE)
    valuation = _resolve(PricePurpose.VALUATION)
    margin = _resolve(PricePurpose.MARGIN)

    assert execution.failure is None
    assert execution.result is not None
    assert execution.result.resolved_mark is not None
    assert execution.result.resolved_mark.price_purpose is PricePurpose.EXECUTION_REFERENCE
    assert execution.result.resolved_mark.price.units == 500_001
    assert execution.result.resolved_mark.price.scale.places == 1
    assert execution.result.resolved_mark.source_event_id == "agg:101"

    assert valuation.failure is None
    assert valuation.result is not None
    assert valuation.result.resolved_mark is not None
    assert valuation.result.resolved_mark.price_purpose is PricePurpose.VALUATION
    assert valuation.result.resolved_mark.price.units == 50_200

    assert margin.failure is None
    assert margin.result is not None
    assert margin.result.resolved_mark is not None
    assert margin.result.resolved_mark.price_purpose is PricePurpose.MARGIN
    assert margin.result.resolved_mark.price == valuation.result.resolved_mark.price
    assert margin.result.resolved_mark.stream_id != valuation.result.resolved_mark.stream_id
    assert margin.result.observations[0].observation_hash != valuation.result.observations[0].observation_hash
    assert not execution.result.decision_grade_eligible
    assert not valuation.result.decision_grade_eligible
    assert not margin.result.decision_grade_eligible


def test_liquidation_mapping_returns_exact_closed_mark_bar_coverage() -> None:
    outcome = _resolve(
        PricePurpose.LIQUIDATION,
        liquidation_interval_start=BAR_START,
        liquidation_interval_end_exclusive=REQUESTED_AT,
    )

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.resolved_mark is None
    assert len(outcome.result.liquidation_bars) == 2
    first, second = outcome.result.liquidation_bars
    assert first.interval_start == BAR_START
    assert first.interval_end_exclusive == BAR_MIDDLE
    assert first.low.units == 49_800
    assert first.high.units == 50_100
    assert second.interval_start == BAR_MIDDLE
    assert second.interval_end_exclusive == REQUESTED_AT
    assert second.low.units == 49_700
    assert second.high.units == 50_300
    assert all(bar.price_purpose is PricePurpose.LIQUIDATION for bar in outcome.result.liquidation_bars)


def test_settlement_and_funding_fail_before_source_selection() -> None:
    empty = BinanceUsdmHistoricalPriceBook(
        price_book_key="empty-v1",
        price_book_version=1,
        instrument_id=price_book().instrument_id,
        quote_currency_id=price_book().quote_currency_id,
        coverages=(),
        aggregate_trades=(),
        mark_price_klines=(),
    )

    settlement = _resolve(PricePurpose.SETTLEMENT, book=empty)
    funding = _resolve(PricePurpose.FUNDING, book=empty)

    assert settlement.result is None
    assert settlement.failure is not None
    assert settlement.failure.code is BinanceUsdmPriceStreamFailureCode.UNSUPPORTED_PRICE_PURPOSE
    assert funding.result is None
    assert funding.failure is not None
    assert funding.failure.code is BinanceUsdmPriceStreamFailureCode.PRICE_PURPOSE_OWNED_BY_G10E


def test_source_availability_and_generic_stale_policy_remain_authoritative() -> None:
    late_capture = simulation_instant(UtcInstant(BAR_START.epoch_nanoseconds - MILLISECOND))
    late = _resolve(PricePurpose.VALUATION, captured_at=late_capture)
    assert late.result is None
    assert late.failure is not None
    assert late.failure.code is BinanceUsdmPriceStreamFailureCode.SOURCE_NOT_AVAILABLE

    stale_query = price_query(PricePurpose.VALUATION)
    stale_query = replace(
        stale_query,
        stale_policy=stale_policy(
            PricePurpose.VALUATION,
            max_age_nanoseconds=0,
            allow_forward_fill=False,
        ),
    )
    stale = BinanceUsdmPriceStreamModel().resolve_price_purpose(stale_query)
    assert stale.result is None
    assert stale.failure is not None
    assert stale.failure.code is BinanceUsdmPriceStreamFailureCode.MARK_RESOLUTION_FAILED
    assert stale.failure.mark_failure is not None
    assert stale.failure.mark_failure.code is MarkResolutionFailureCode.STALE_MARK


def test_same_utc_phase_only_late_availability_fails_closed() -> None:
    observed = UtcInstant(REQUESTED_AT.epoch_nanoseconds - 5 * MILLISECOND)
    trade = aggregate_trade(
        trade_at=observed,
        available_at=simulation_instant(observed, phase=1, sequence=1),
    )
    outcome = _resolve(
        PricePurpose.EXECUTION_REFERENCE,
        book=price_book(aggregate_trades=(trade,)),
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmPriceStreamFailureCode.UNREPRESENTABLE_AVAILABILITY_ORDER
    )


def test_liquidation_gap_is_not_filled_by_point_mark_forward_fill() -> None:
    bars = mark_bars()
    outcome = _resolve(
        PricePurpose.LIQUIDATION,
        book=price_book(bars=(bars[0],)),
        liquidation_interval_start=BAR_START,
        liquidation_interval_end_exclusive=REQUESTED_AT,
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE


def test_input_order_is_canonical_and_duplicate_event_identity_fails() -> None:
    bars = mark_bars()
    forward = _resolve(PricePurpose.VALUATION, book=price_book(bars=bars))
    reverse = _resolve(PricePurpose.VALUATION, book=price_book(bars=tuple(reversed(bars))))
    assert forward.to_canonical_dict() == reverse.to_canonical_dict()

    first = aggregate_trade()
    changed = aggregate_trade(price="50001.10", ref=first.source_ref)
    conflict = _resolve(
        PricePurpose.EXECUTION_REFERENCE,
        book=price_book(aggregate_trades=(first, changed)),
    )
    assert conflict.result is None
    assert conflict.failure is not None
    assert conflict.failure.code is BinanceUsdmPriceStreamFailureCode.SOURCE_IDENTITY_CONFLICT


def test_frozen_failure_precedence_and_source_validation() -> None:
    empty = price_book(aggregate_trades=())
    missing = _resolve(PricePurpose.EXECUTION_REFERENCE, book=empty)
    assert missing.failure is not None
    assert missing.failure.code is BinanceUsdmPriceStreamFailureCode.MISSING_SOURCE_RECORDS

    mismatched = replace(empty, quote_currency_id=CurrencyId("BUSD"))
    metadata_first = _resolve(PricePurpose.EXECUTION_REFERENCE, book=mismatched)
    assert metadata_first.failure is not None
    assert (
        metadata_first.failure.code
        is BinanceUsdmPriceStreamFailureCode.INSTRUMENT_METADATA_MISMATCH
    )

    malformed = _resolve(
        PricePurpose.EXECUTION_REFERENCE,
        book=price_book(aggregate_trades=(replace(aggregate_trade(), price="5E4"),)),
    )
    assert malformed.failure is not None
    assert malformed.failure.code is BinanceUsdmPriceStreamFailureCode.INVALID_DECIMAL_FIELD

    bars = mark_bars()
    invalid_timing = _resolve(
        PricePurpose.VALUATION,
        book=price_book(bars=(bars[0], replace(bars[1], closed_final=False))),
    )
    assert invalid_timing.failure is not None
    assert invalid_timing.failure.code is BinanceUsdmPriceStreamFailureCode.INVALID_SOURCE_TIMING

    valuation = coverage(PricePurpose.VALUATION)
    overlap = replace(valuation, coverage_id="valuation-overlap-v2")
    overlapping = _resolve(
        PricePurpose.VALUATION,
        book=price_book(
            coverages=(
                coverage(PricePurpose.EXECUTION_REFERENCE),
                valuation,
                overlap,
                coverage(PricePurpose.MARGIN),
                coverage(PricePurpose.LIQUIDATION),
            )
        ),
    )
    assert overlapping.failure is not None
    assert (
        overlapping.failure.code
        is BinanceUsdmPriceStreamFailureCode.OVERLAPPING_PURPOSE_COVERAGE
    )


def test_resolution_constructor_rejects_forged_authority() -> None:
    outcome = _resolve(PricePurpose.VALUATION)
    assert outcome.result is not None
    with pytest.raises(ValueError, match="resolution fields"):
        replace(
            outcome.result,
            model_digest="sha256:" + "0" * 64,
        )
    assert isinstance(outcome.result, BinanceUsdmPricePurposeResolution)
