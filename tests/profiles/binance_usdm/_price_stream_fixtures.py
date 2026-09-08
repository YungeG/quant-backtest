from __future__ import annotations

from crypto_quant_domain import (
    CurrencyId,
    PricePurpose,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import StaleMarkPolicy
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAggregateTradePrice,
    BinanceUsdmHistoricalPriceBook,
    BinanceUsdmInstrumentModel,
    BinanceUsdmMarkPriceKline,
    BinanceUsdmPricePurposeQuery,
    BinanceUsdmPriceSourceKind,
    BinanceUsdmPriceSourceRef,
    BinanceUsdmPriceStreamCoverage,
)

from ._fixtures import ONBOARD_AT, RENAME_AT, query as instrument_query, revision

MILLISECOND = 1_000_000
BASE_MILLISECONDS = RENAME_AT.epoch_nanoseconds // MILLISECOND
BAR_START = UtcInstant((BASE_MILLISECONDS - 120_000) * MILLISECOND)
BAR_MIDDLE = UtcInstant((BASE_MILLISECONDS - 60_000) * MILLISECOND)
REQUESTED_AT = RENAME_AT
CAPTURED_AT = UtcInstant(RENAME_AT.epoch_nanoseconds + 20 * MILLISECOND)


def simulation_instant(
    instant: UtcInstant,
    *,
    phase: int = 0,
    sequence: int = 0,
) -> SimulationInstant:
    return SimulationInstant(
        instant=instant,
        phase=TimelinePhase(phase, "market_data"),
        source_sequence=SourceSequence(sequence),
    )


def metadata_resolution(
    *,
    effective_at: UtcInstant = REQUESTED_AT,
    captured_at: UtcInstant = CAPTURED_AT,
):
    outcome = BinanceUsdmInstrumentModel().resolve_instrument(
        instrument_query(
            revision(),
            effective_at=effective_at,
            captured_at=captured_at,
        )
    )
    assert outcome.result is not None
    return outcome.result


def source_ref(key: str, *, revision_id: str = "archive-v1") -> BinanceUsdmPriceSourceRef:
    return BinanceUsdmPriceSourceRef(
        source_key=key,
        source_hash=canonical_sha256({"source_key": key, "revision_id": revision_id}),
        archive_key=f"data/futures/um/{key}",
        revision_id=revision_id,
        supersedes_revision_id=None,
    )


def aggregate_trade(
    event_id: str = "agg:101",
    *,
    aggregate_trade_id: int = 101,
    price: str = "50000.10",
    trade_at: UtcInstant | None = None,
    available_at: SimulationInstant | None = None,
    instrument_id=None,
    ref: BinanceUsdmPriceSourceRef | None = None,
) -> BinanceUsdmAggregateTradePrice:
    observed = trade_at or UtcInstant(REQUESTED_AT.epoch_nanoseconds - 5 * MILLISECOND)
    return BinanceUsdmAggregateTradePrice(
        event_id=event_id,
        instrument_id=instrument_id or metadata_resolution().instrument.instrument_id,
        aggregate_trade_id=aggregate_trade_id,
        price=price,
        quantity="0.250",
        first_trade_id=aggregate_trade_id * 10,
        last_trade_id=aggregate_trade_id * 10 + 1,
        trade_at=observed,
        available_at=available_at
        or simulation_instant(UtcInstant(observed.epoch_nanoseconds + MILLISECOND)),
        buyer_is_maker=False,
        source_ref=ref or source_ref(f"daily/aggTrades/BTCUSDT/{event_id}"),
    )


def mark_bar(
    event_id: str,
    *,
    open_time_ms: int,
    close_time_ms: int,
    open_price: str,
    high_price: str,
    low_price: str,
    close_price: str,
    available_delay_ms: int = 0,
    instrument_id=None,
    ref: BinanceUsdmPriceSourceRef | None = None,
) -> BinanceUsdmMarkPriceKline:
    closed = UtcInstant((close_time_ms + 1) * MILLISECOND)
    return BinanceUsdmMarkPriceKline(
        event_id=event_id,
        instrument_id=instrument_id or metadata_resolution().instrument.instrument_id,
        interval_key="1m",
        open_time_milliseconds=open_time_ms,
        close_time_milliseconds=close_time_ms,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        closed_at=simulation_instant(closed),
        available_at=simulation_instant(
            UtcInstant(closed.epoch_nanoseconds + available_delay_ms * MILLISECOND)
        ),
        closed_final=True,
        source_ref=ref or source_ref(f"daily/markPriceKlines/BTCUSDT/{event_id}"),
    )


def mark_bars() -> tuple[BinanceUsdmMarkPriceKline, ...]:
    return (
        mark_bar(
            "mark:1",
            open_time_ms=BASE_MILLISECONDS - 120_000,
            close_time_ms=BASE_MILLISECONDS - 60_001,
            open_price="49900.00",
            high_price="50100.00",
            low_price="49800.00",
            close_price="50000.00",
        ),
        mark_bar(
            "mark:2",
            open_time_ms=BASE_MILLISECONDS - 60_000,
            close_time_ms=BASE_MILLISECONDS - 1,
            open_price="50000.00",
            high_price="50300.00",
            low_price="49700.00",
            close_price="50200.00",
        ),
    )


def coverage(
    purpose: PricePurpose,
    *,
    source_kind: BinanceUsdmPriceSourceKind | None = None,
    coverage_from: UtcInstant = BAR_START,
    coverage_to_exclusive: UtcInstant = UtcInstant(
        REQUESTED_AT.epoch_nanoseconds + MILLISECOND
    ),
) -> BinanceUsdmPriceStreamCoverage:
    kind = source_kind or (
        BinanceUsdmPriceSourceKind.AGGREGATE_TRADE
        if purpose is PricePurpose.EXECUTION_REFERENCE
        else BinanceUsdmPriceSourceKind.MARK_PRICE_KLINE
    )
    return BinanceUsdmPriceStreamCoverage(
        coverage_id=f"{purpose.value}-coverage-v1",
        instrument_id=metadata_resolution().instrument.instrument_id,
        price_purpose=purpose,
        source_kind=kind,
        coverage_from=coverage_from,
        coverage_to_exclusive=coverage_to_exclusive,
        stream_id=f"binance_usdm.{kind.value}.{purpose.value}.v1",
        source_ref=source_ref(f"coverage/{purpose.value}"),
    )


def price_book(
    *,
    aggregate_trades: tuple[BinanceUsdmAggregateTradePrice, ...] | None = None,
    bars: tuple[BinanceUsdmMarkPriceKline, ...] | None = None,
    coverages: tuple[BinanceUsdmPriceStreamCoverage, ...] | None = None,
) -> BinanceUsdmHistoricalPriceBook:
    return BinanceUsdmHistoricalPriceBook(
        price_book_key="binance-usdm-btcusdt-price-book-v1",
        price_book_version=1,
        instrument_id=metadata_resolution().instrument.instrument_id,
        quote_currency_id=CurrencyId("USDT"),
        coverages=(
            tuple(
                coverage(purpose)
                for purpose in (
                    PricePurpose.EXECUTION_REFERENCE,
                    PricePurpose.VALUATION,
                    PricePurpose.MARGIN,
                    PricePurpose.LIQUIDATION,
                )
            )
            if coverages is None
            else coverages
        ),
        aggregate_trades=(aggregate_trade(),)
        if aggregate_trades is None
        else aggregate_trades,
        mark_price_klines=mark_bars() if bars is None else bars,
    )


def stale_policy(
    purpose: PricePurpose,
    *,
    max_age_nanoseconds: int = 10 * MILLISECOND,
    allow_forward_fill: bool = True,
) -> StaleMarkPolicy:
    return StaleMarkPolicy(
        policy_key=f"binance-usdm-{purpose.value}-v1",
        policy_version=1,
        price_purpose=purpose,
        max_age_nanoseconds=max_age_nanoseconds,
        allow_forward_fill=allow_forward_fill,
    )


def price_query(
    purpose: PricePurpose,
    *,
    book: BinanceUsdmHistoricalPriceBook | None = None,
    requested_at: UtcInstant = REQUESTED_AT,
    captured_at: SimulationInstant | None = None,
    liquidation_interval_start: UtcInstant | None = None,
    liquidation_interval_end_exclusive: UtcInstant | None = None,
) -> BinanceUsdmPricePurposeQuery:
    return BinanceUsdmPricePurposeQuery(
        instrument_metadata=metadata_resolution(
            effective_at=requested_at,
            captured_at=(captured_at or simulation_instant(CAPTURED_AT)).instant,
        ),
        price_book=book or price_book(),
        price_purpose=purpose,
        requested_at=requested_at,
        captured_at=captured_at or simulation_instant(CAPTURED_AT),
        stale_policy=None if purpose is PricePurpose.LIQUIDATION else stale_policy(purpose),
        liquidation_interval_start=liquidation_interval_start,
        liquidation_interval_end_exclusive=liquidation_interval_end_exclusive,
    )
