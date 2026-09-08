from __future__ import annotations

from crypto_quant_domain import UtcInstant, canonical_sha256
from crypto_quant_trading.profiles.binance_usdm import (
    BINANCE_USDM_OPEN_ENDED_DELIVERY_AT,
    BinanceUsdmInstrumentMetadataQuery,
    BinanceUsdmInstrumentMetadataRevision,
    BinanceUsdmInstrumentMetadataSourceRef,
)


ONBOARD_AT = UtcInstant(1_700_000_000_000_000_000)
RENAME_AT = UtcInstant(1_710_000_000_000_000_000)
DELIST_AT = UtcInstant(1_720_000_000_000_000_000)


def source_ref(key: str) -> BinanceUsdmInstrumentMetadataSourceRef:
    return BinanceUsdmInstrumentMetadataSourceRef(
        source_key=key,
        source_hash=canonical_sha256({"source_key": key}),
    )


def revision(
    revision_id: str = "btc-v1",
    *,
    supersedes_revision_id: str | None = None,
    stable_instrument_key: str = "btc-usdt-perpetual",
    symbol: str = "BTCUSDT",
    pair: str = "BTCUSDT",
    contract_type: str = "PERPETUAL",
    status: str = "TRADING",
    onboard_at: UtcInstant = ONBOARD_AT,
    delivery_at: UtcInstant = BINANCE_USDM_OPEN_ENDED_DELIVERY_AT,
    base_asset: str = "BTC",
    quote_asset: str = "USDT",
    margin_asset: str = "USDT",
    effective_from: UtcInstant = ONBOARD_AT,
    available_at: UtcInstant | None = None,
) -> BinanceUsdmInstrumentMetadataRevision:
    return BinanceUsdmInstrumentMetadataRevision(
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
        stable_instrument_key=stable_instrument_key,
        symbol=symbol,
        pair=pair,
        contract_type=contract_type,
        status=status,
        onboard_at=onboard_at,
        delivery_at=delivery_at,
        base_asset=base_asset,
        quote_asset=quote_asset,
        margin_asset=margin_asset,
        effective_from=effective_from,
        available_at=available_at or UtcInstant(effective_from.epoch_nanoseconds + 1),
        source_ref=source_ref(f"exchange-info/{revision_id}.json"),
    )


def query(
    *revisions: BinanceUsdmInstrumentMetadataRevision,
    stable_instrument_key: str = "btc-usdt-perpetual",
    effective_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 10),
    captured_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 20),
) -> BinanceUsdmInstrumentMetadataQuery:
    return BinanceUsdmInstrumentMetadataQuery(
        stable_instrument_key=stable_instrument_key,
        effective_at=effective_at,
        captured_at=captured_at,
        revisions=revisions,
    )
