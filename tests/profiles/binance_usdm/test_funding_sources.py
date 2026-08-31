from __future__ import annotations

from dataclasses import replace

import pytest
from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    Scale,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import LinearFundingPublicationStatus, LinearPerpetualContract
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmFundingSourceFailureCode,
    BinanceUsdmFundingSourceModel,
    BinanceUsdmFundingSourceModelV2,
    BinanceUsdmFundingSourceResolution,
)

from ._funding_source_fixtures import (
    CAPTURED_AT,
    MILLISECOND,
    TARGET_AT,
    TARGET_MILLISECONDS,
    application_key,
    funding_book,
    funding_coverage,
    funding_query,
    funding_record,
    funding_source_ref,
    linear_contract,
    simulation_instant,
)


def _resolve(**kwargs):
    return BinanceUsdmFundingSourceModel().resolve_funding_source(
        funding_query(**kwargs)
    )


def _resolve_v2(**kwargs):
    return BinanceUsdmFundingSourceModelV2().resolve_funding_source(
        funding_query(**kwargs)
    )


def test_maps_regular_history_row_to_frozen_funding_evidence() -> None:
    outcome = _resolve()

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.slot_id == application_key().funding_slot_id
    assert result.publication.status is LinearFundingPublicationStatus.FINAL_RATE
    assert result.publication.published_rate is not None
    assert result.publication.published_rate.units == 10_000
    assert result.publication.published_rate.scale == Scale(8)
    assert result.publication.published_rate.basis == "funding_fraction_of_notional"
    assert result.publication.publication_available_at.instant == TARGET_AT
    assert result.publication.publication_available_at.phase.rank == 110
    assert result.publication.publication_available_at.phase.code == "funding_settlement"
    assert result.publication.publication_available_at.source_sequence.value == 0

    mark = result.funding_mark_evidence.resolved_mark
    policy = result.funding_mark_evidence.stale_policy
    assert mark.price_purpose is PricePurpose.FUNDING
    assert mark.price.units == 5_000_012_345_678
    assert mark.price.scale == Scale(8)
    assert mark.observed_at == TARGET_AT
    assert mark.resolved_at == TARGET_AT
    assert mark.age_nanoseconds == 0
    assert policy.max_age_nanoseconds == 0
    assert not policy.allow_forward_fill

    settlement = result.settlement_evidence
    assert settlement.application_key == application_key()
    assert settlement.effective_time == TARGET_AT
    assert settlement.applied_at == result.publication.publication_available_at
    assert settlement.applied_rate == result.publication.published_rate
    assert settlement.event_id == result.publication.event_id
    assert settlement.event_hash == result.publication.event_hash
    assert settlement.source_hash == result.publication.source_hash
    assert not result.decision_grade_eligible


def test_v2_success_cache_is_bounded_and_excludes_failures() -> None:
    model = BinanceUsdmFundingSourceModelV2()
    model._reset_cache_for_test()
    try:
        failed_query = funding_query(book=funding_book(records=()))
        first_failure = model.resolve_funding_source(failed_query)
        second_failure = model.resolve_funding_source(failed_query)
        assert first_failure.failure is not None
        assert second_failure.failure is not None
        assert first_failure is not second_failure
        assert model._cache_stats_for_test() == (0, 0, 2)

        query = funding_query()
        first = model.resolve_funding_source(query)
        assert first.result is not None
        assert model.resolve_funding_source(query) is first
        assert model._cache_stats_for_test() == (1, 1, 3)

        tampered_query = replace(
            query,
            funding_book=replace(
                query.funding_book,
                funding_book_key="tampered-funding-cache",
            ),
        )
        assert tampered_query.query_hash != query.query_hash
        assert model.resolve_funding_source(tampered_query).result is not None
        assert model._cache_stats_for_test() == (2, 1, 4)

        for index in range(model._CACHE_CAPACITY):
            outcome = model.resolve_funding_source(
                replace(
                    query,
                    funding_book=replace(
                        query.funding_book,
                        funding_book_key=f"funding-cache-{index}",
                    ),
                )
            )
            assert outcome.result is not None

        assert model._cache_stats_for_test() == (256, 1, 260)
        assert model.resolve_funding_source(query) is not first
        assert model._cache_stats_for_test() == (256, 1, 261)
        assert model.resolve_funding_source(query).result is not None
        assert model._cache_stats_for_test() == (256, 2, 261)
    finally:
        model._reset_cache_for_test()


def test_v1_rejects_finer_nondivisible_mark_and_v2_preserves_raw_scale() -> None:
    kwargs = {
        "book": funding_book(
            records=(funding_record(mark_price="20.39013424"),)
        ),
        "contract": linear_contract(price_scale=Scale(2)),
    }

    v1 = _resolve(**kwargs)
    assert v1.result is None
    assert v1.failure is not None
    assert v1.failure.code is BinanceUsdmFundingSourceFailureCode.MARK_SCALE_MISMATCH

    v2 = _resolve_v2(**kwargs)
    assert v2.failure is None
    assert v2.result is not None
    assert v2.result.model_key == "crypto.binance_usdm.funding-sources.v2"
    assert v2.result.model_version == 2
    assert v2.result.model_digest == (
        "sha256:0244952eb591fb6c4942179743478570506ad632801a9458104d50c5a61af5f4"
    )
    assert BinanceUsdmFundingSourceModel().model_digest == (
        "sha256:25111c2eff3f6c05364b142e321c98c585117ffd9063271f0af52e2d35298db7"
    )
    assert v2.result.mark_observation.price.units == 2_039_013_424
    assert v2.result.mark_observation.price.scale == Scale(8)
    assert v2.result.funding_mark_evidence.resolved_mark.price.units == 2_039_013_424
    assert v2.result.funding_mark_evidence.resolved_mark.price.scale == Scale(8)
    assert replace(v2.result) == v2.result


def test_signed_zero_rates_and_nonstandard_slot_times_map_without_schedule_inference() -> None:
    for raw, units in (("-0.00025000", -25_000), ("0.00000000", 0)):
        outcome = _resolve(book=funding_book(records=(funding_record(funding_rate=raw),)))
        assert outcome.result is not None
        assert outcome.result.publication.published_rate is not None
        assert outcome.result.publication.published_rate.units == units

    shifted = UtcInstant(TARGET_AT.epoch_nanoseconds + 37 * MILLISECOND)
    shifted_ms = shifted.epoch_nanoseconds // MILLISECOND
    shifted_record = funding_record(
        funding_time_milliseconds=shifted_ms,
        archive_available_at=simulation_instant(
            UtcInstant(shifted.epoch_nanoseconds + MILLISECOND)
        ),
        event_id="funding:BTCUSDT:1710000000037:Regular",
    )
    shifted_coverage = funding_coverage(
        coverage_from=UtcInstant(shifted.epoch_nanoseconds - MILLISECOND),
        coverage_to_exclusive=UtcInstant(shifted.epoch_nanoseconds + MILLISECOND),
    )
    outcome = _resolve(
        target_at=shifted,
        key=application_key(target_at=shifted),
        book=funding_book(records=(shifted_record,), coverages=(shifted_coverage,)),
        captured_at=simulation_instant(
            UtcInstant(shifted.epoch_nanoseconds + 2 * MILLISECOND)
        ),
    )
    assert outcome.result is not None
    assert outcome.result.slot_id.target_funding_time == shifted


def test_archive_visibility_coverage_and_input_order_are_deterministic() -> None:
    record = funding_record()
    before = _resolve(captured_at=simulation_instant(TARGET_AT))
    at = _resolve(captured_at=record.archive_available_at)
    after = _resolve()

    assert before.failure is not None
    assert before.failure.code is BinanceUsdmFundingSourceFailureCode.SOURCE_NOT_AVAILABLE
    assert at.result is not None
    assert after.result is not None

    coverage = funding_coverage()
    reverse = funding_book(records=(record,), coverages=(coverage,))
    forward_outcome = _resolve(book=reverse)
    reverse_outcome = _resolve(
        book=funding_book(records=tuple(reversed(reverse.records)), coverages=tuple(reversed(reverse.coverages)))
    )
    assert forward_outcome.to_canonical_dict() == reverse_outcome.to_canonical_dict()


def test_frozen_failure_precedence_covers_all_business_failures() -> None:
    metadata_book = funding_book(
        instrument_id=InstrumentId(VenueId("binance_usdm"), "other-perpetual")
    )
    other_instrument = replace(
        linear_contract().instrument,
        instrument_id=InstrumentId(VenueId("binance_usdm"), "other-perpetual"),
    )
    contract_mismatch = LinearPerpetualContract(
        instrument=other_instrument,
        quantity_scale=Scale(3),
        price_scale=Scale(8),
        contract_multiplier=linear_contract().contract_multiplier,
    )
    late_record = funding_record(
        archive_available_at=simulation_instant(
            UtcInstant(CAPTURED_AT.epoch_nanoseconds + MILLISECOND)
        )
    )
    overlap = replace(funding_coverage(), coverage_id="overlap-v2")
    superseding_ref = funding_source_ref(
        revision_id="funding-archive-v2",
        supersedes_revision_id="funding-archive-v1",
    )
    first = funding_record()
    changed = funding_record(funding_rate="0.00020000", source_ref=first.source_ref)

    cases = (
        (
            BinanceUsdmFundingSourceFailureCode.INSTRUMENT_METADATA_MISMATCH,
            {"book": metadata_book},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.CONTRACT_CONTEXT_MISMATCH,
            {"contract": contract_mismatch},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.APPLICATION_KEY_MISMATCH,
            {
                "key": application_key(
                    target_at=UtcInstant(TARGET_AT.epoch_nanoseconds + MILLISECOND)
                )
            },
        ),
        (
            BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_SOURCE_RECORDS,
            {"book": funding_book(records=())},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.SOURCE_NOT_AVAILABLE,
            {"book": funding_book(records=(late_record,))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_COVERAGE,
            {"book": funding_book(coverages=())},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.OVERLAPPING_FUNDING_COVERAGE,
            {"book": funding_book(coverages=(funding_coverage(), overlap))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.MISSING_RATE_TYPE,
            {"book": funding_book(records=(funding_record(rate_type=None),))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.UNSUPPORTED_RATE_TYPE,
            {"book": funding_book(records=(funding_record(rate_type="Special"),))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_RATE,
            {"book": funding_book(records=(funding_record(funding_rate=None),))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_MARK,
            {"book": funding_book(records=(funding_record(mark_price=None),))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.INVALID_DECIMAL_FIELD,
            {"book": funding_book(records=(funding_record(funding_rate="1e-4"),))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.INVALID_SOURCE_TIMING,
            {
                "book": funding_book(
                    records=(
                        funding_record(
                            archive_available_at=simulation_instant(
                                UtcInstant(TARGET_AT.epoch_nanoseconds - MILLISECOND)
                            )
                        ),
                    )
                )
            },
        ),
        (
            BinanceUsdmFundingSourceFailureCode.UNSUPPORTED_SOURCE_REVISION,
            {
                "book": funding_book(
                    records=(funding_record(source_ref=superseding_ref),)
                )
            },
        ),
        (
            BinanceUsdmFundingSourceFailureCode.SOURCE_IDENTITY_CONFLICT,
            {"book": funding_book(records=(first, changed))},
        ),
        (
            BinanceUsdmFundingSourceFailureCode.MARK_SCALE_MISMATCH,
            {
                "book": funding_book(
                    records=(funding_record(mark_price="20.39013424"),)
                ),
                "contract": linear_contract(price_scale=Scale(2)),
            },
        ),
    )

    assert len(cases) == len(BinanceUsdmFundingSourceFailureCode)
    for expected, kwargs in cases:
        outcome = _resolve(**kwargs)
        assert outcome.result is None, expected
        assert outcome.failure is not None, expected
        assert outcome.failure.code is expected

    multi_defect = _resolve(
        book=funding_book(
            records=(),
            instrument_id=InstrumentId(VenueId("binance_usdm"), "other-perpetual"),
        )
    )
    assert multi_defect.failure is not None
    assert (
        multi_defect.failure.code
        is BinanceUsdmFundingSourceFailureCode.INSTRUMENT_METADATA_MISMATCH
    )


def test_special_rows_cannot_be_ignored_or_combined_with_regular_funding() -> None:
    regular = funding_record()
    special = funding_record(
        rate_type="Special",
        event_id="funding:BTCUSDT:1710000000000:Special",
    )
    outcome = _resolve(book=funding_book(records=(regular, special)))

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmFundingSourceFailureCode.UNSUPPORTED_RATE_TYPE


def test_current_or_predicted_sources_and_constructor_forgery_fail_closed() -> None:
    with pytest.raises(ValueError, match="source_kind"):
        funding_source_ref(source_kind="mark_price_stream")

    outcome = _resolve()
    assert outcome.result is not None
    assert isinstance(outcome.result, BinanceUsdmFundingSourceResolution)
    with pytest.raises(ValueError, match="resolution fields"):
        replace(outcome.result, model_digest="sha256:" + "0" * 64)



def test_source_record_requires_millisecond_target_identity() -> None:
    with pytest.raises(ValueError, match="millisecond"):
        _resolve(
            target_at=UtcInstant(TARGET_AT.epoch_nanoseconds + 1),
            key=application_key(),
        )

    assert TARGET_MILLISECONDS * MILLISECOND == TARGET_AT.epoch_nanoseconds
