from __future__ import annotations

from crypto_quant_domain import (
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    FundingSlotId,
    LinearFundingApplicationKey,
    LinearPerpetualContract,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmFundingCoverage,
    BinanceUsdmFundingRateRecord,
    BinanceUsdmFundingSourceQuery,
    BinanceUsdmFundingSourceRef,
    BinanceUsdmHistoricalFundingBook,
)

from ._fixtures import RENAME_AT
from ._price_stream_fixtures import metadata_resolution


MILLISECOND = 1_000_000
TARGET_AT = RENAME_AT
TARGET_MILLISECONDS = TARGET_AT.epoch_nanoseconds // MILLISECOND
METADATA_CAPTURED_AT = TARGET_AT
ARCHIVE_AVAILABLE_AT = UtcInstant(TARGET_AT.epoch_nanoseconds + MILLISECOND)
CAPTURED_AT = UtcInstant(TARGET_AT.epoch_nanoseconds + 2 * MILLISECOND)


def simulation_instant(
    instant: UtcInstant,
    *,
    phase: int = 0,
    code: str = "archive_capture",
    sequence: int = 0,
) -> SimulationInstant:
    return SimulationInstant(
        instant=instant,
        phase=TimelinePhase(phase, code),
        source_sequence=SourceSequence(sequence),
    )


def funding_source_ref(
    key: str = "fundingRate/BTCUSDT/2024-03",
    *,
    source_kind: str = "funding_rate_history",
    revision_id: str = "funding-archive-v1",
    supersedes_revision_id: str | None = None,
) -> BinanceUsdmFundingSourceRef:
    return BinanceUsdmFundingSourceRef(
        source_kind=source_kind,
        source_key=key,
        source_hash=canonical_sha256(
            {
                "source_kind": source_kind,
                "source_key": key,
                "revision_id": revision_id,
                "supersedes_revision_id": supersedes_revision_id,
            }
        ),
        archive_key=f"data/futures/um/monthly/{key}.zip",
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
    )


def funding_record(
    *,
    funding_time_milliseconds: int = TARGET_MILLISECONDS,
    funding_rate: str | None = "0.00010000",
    mark_price: str | None = "50000.12345678",
    rate_type: str | None = "Regular",
    archive_available_at: SimulationInstant | None = None,
    event_id: str = "funding:BTCUSDT:1710000000000:Regular",
    source_ref: BinanceUsdmFundingSourceRef | None = None,
    instrument_id=None,
) -> BinanceUsdmFundingRateRecord:
    metadata = metadata_resolution(effective_at=TARGET_AT, captured_at=CAPTURED_AT)
    ref = source_ref or funding_source_ref()
    return BinanceUsdmFundingRateRecord(
        instrument_id=instrument_id or metadata.instrument.instrument_id,
        funding_time_milliseconds=funding_time_milliseconds,
        funding_rate=funding_rate,
        mark_price=mark_price,
        rate_type=rate_type,
        archive_available_at=archive_available_at
        or simulation_instant(ARCHIVE_AVAILABLE_AT),
        event_id=event_id,
        revision_id=ref.revision_id,
        source_ref=ref,
    )


def funding_coverage(
    *,
    coverage_id: str = "btc-usdt-funding-coverage-v1",
    coverage_from: UtcInstant | None = None,
    coverage_to_exclusive: UtcInstant | None = None,
    source_ref: BinanceUsdmFundingSourceRef | None = None,
    instrument_id=None,
) -> BinanceUsdmFundingCoverage:
    metadata = metadata_resolution(effective_at=TARGET_AT, captured_at=CAPTURED_AT)
    ref = source_ref or funding_source_ref()
    return BinanceUsdmFundingCoverage(
        coverage_id=coverage_id,
        instrument_id=instrument_id or metadata.instrument.instrument_id,
        coverage_from=coverage_from
        or UtcInstant(TARGET_AT.epoch_nanoseconds - MILLISECOND),
        coverage_to_exclusive=coverage_to_exclusive
        or UtcInstant(TARGET_AT.epoch_nanoseconds + MILLISECOND),
        stream_key="binance-usdm-funding-rate-history-v1",
        stream_version=1,
        source_ref=ref,
    )


def funding_book(
    *,
    records: tuple[BinanceUsdmFundingRateRecord, ...] | None = None,
    coverages: tuple[BinanceUsdmFundingCoverage, ...] | None = None,
    instrument_id=None,
) -> BinanceUsdmHistoricalFundingBook:
    metadata = metadata_resolution(effective_at=TARGET_AT, captured_at=CAPTURED_AT)
    return BinanceUsdmHistoricalFundingBook(
        funding_book_key="binance-usdm-historical-funding-v1",
        funding_book_version=1,
        instrument_id=instrument_id or metadata.instrument.instrument_id,
        coverages=(funding_coverage(),) if coverages is None else coverages,
        records=(funding_record(),) if records is None else records,
    )


def linear_contract(*, price_scale: Scale = Scale(8)) -> LinearPerpetualContract:
    metadata = metadata_resolution(effective_at=TARGET_AT, captured_at=CAPTURED_AT)
    return LinearPerpetualContract(
        instrument=metadata.instrument,
        quantity_scale=Scale(3),
        price_scale=price_scale,
        contract_multiplier=metadata.contract_metadata.contract_multiplier,
    )


def application_key(
    *,
    target_at: UtcInstant = TARGET_AT,
    account_id: str = "account-1",
) -> LinearFundingApplicationKey:
    metadata = metadata_resolution(effective_at=target_at, captured_at=CAPTURED_AT)
    return LinearFundingApplicationKey.derive(
        account_id,
        FundingSlotId.derive(metadata.instrument.instrument_id, target_at),
    )


def funding_query(
    *,
    book: BinanceUsdmHistoricalFundingBook | None = None,
    contract: LinearPerpetualContract | None = None,
    key: LinearFundingApplicationKey | None = None,
    target_at: UtcInstant = TARGET_AT,
    captured_at: SimulationInstant | None = None,
) -> BinanceUsdmFundingSourceQuery:
    return BinanceUsdmFundingSourceQuery(
        instrument_resolution=metadata_resolution(
            effective_at=target_at,
            captured_at=METADATA_CAPTURED_AT,
        ),
        contract=contract or linear_contract(),
        application_key=key or application_key(target_at=target_at),
        funding_book=book or funding_book(),
        target_funding_time=target_at,
        captured_at=captured_at or simulation_instant(CAPTURED_AT),
    )
