from __future__ import annotations

from crypto_quant_domain import SessionId, UtcInstant, canonical_sha256
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmDeferredRuleKey,
    BinanceUsdmInstrumentModel,
    BinanceUsdmOrderAdmissionMode,
    BinanceUsdmOrderRuleBand,
    BinanceUsdmOrderRuleBook,
    BinanceUsdmOrderRuleQuery,
    BinanceUsdmOrderRuleSourceRef,
)
from tests.profiles.binance_usdm._fixtures import (
    DELIST_AT,
    ONBOARD_AT,
    RENAME_AT,
    query as instrument_query,
    revision,
)


SESSION_ID = SessionId("binance_usdm", "continuous")
REQUIRED_FILTERS = (
    "LOT_SIZE",
    "MARKET_LOT_SIZE",
    "MIN_NOTIONAL",
    "PRICE_FILTER",
)


def metadata_resolution(
    *,
    effective_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 10),
    captured_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 20),
    status: str = "TRADING",
):
    outcome = BinanceUsdmInstrumentModel().resolve_instrument(
        instrument_query(
            revision(status=status),
            effective_at=effective_at,
            captured_at=captured_at,
        )
    )
    assert outcome.result is not None
    return outcome.result


def source_ref(key: str) -> BinanceUsdmOrderRuleSourceRef:
    return BinanceUsdmOrderRuleSourceRef(
        source_key=key,
        source_hash=canonical_sha256({"source_key": key}),
    )


def band(
    band_id: str = "rules-v1",
    *,
    effective_from: UtcInstant = ONBOARD_AT,
    effective_to_exclusive: UtcInstant = RENAME_AT,
    available_at: UtcInstant | None = None,
    min_price: str = "0.00",
    max_price: str = "1000000.00",
    tick_size: str = "0.10",
    limit_min_qty: str = "0.001",
    limit_max_qty: str = "100.000",
    limit_step_size: str = "0.001",
    market_min_qty: str = "0.005",
    market_max_qty: str = "50.000",
    market_step_size: str = "0.005",
    min_notional: str = "5.00",
    filter_keys: tuple[str, ...] = REQUIRED_FILTERS,
    order_types: tuple[str, ...] = ("LIMIT", "MARKET"),
    time_in_forces: tuple[str, ...] = ("FOK", "GTC", "GTX", "IOC"),
    admission_mode: BinanceUsdmOrderAdmissionMode = BinanceUsdmOrderAdmissionMode.NORMAL,
    supports_reduce_only: bool = True,
    deferred_rule_keys: tuple[str, ...] = (),
    source_key: str | None = None,
    instrument_id=None,
) -> BinanceUsdmOrderRuleBand:
    instrument = metadata_resolution().instrument.instrument_id
    return BinanceUsdmOrderRuleBand(
        band_id=band_id,
        instrument_id=instrument if instrument_id is None else instrument_id,
        effective_from=effective_from,
        effective_to_exclusive=effective_to_exclusive,
        available_at=(
            UtcInstant(effective_from.epoch_nanoseconds + 1)
            if available_at is None
            else available_at
        ),
        min_price=min_price,
        max_price=max_price,
        tick_size=tick_size,
        limit_min_qty=limit_min_qty,
        limit_max_qty=limit_max_qty,
        limit_step_size=limit_step_size,
        market_min_qty=market_min_qty,
        market_max_qty=market_max_qty,
        market_step_size=market_step_size,
        min_notional=min_notional,
        filter_keys=filter_keys,
        order_types=order_types,
        time_in_forces=time_in_forces,
        admission_mode=admission_mode,
        supports_reduce_only=supports_reduce_only,
        deferred_rule_keys=deferred_rule_keys,
        source_ref=source_ref(source_key or f"exchange-info/{band_id}.json"),
    )


def rule_book(*bands: BinanceUsdmOrderRuleBand) -> BinanceUsdmOrderRuleBook:
    return BinanceUsdmOrderRuleBook(
        rule_book_key="binance-usdm-btc-usdt-order-rules-v1",
        rule_book_version=1,
        instrument_id=metadata_resolution().instrument.instrument_id,
        coverage_from=ONBOARD_AT,
        coverage_to_exclusive=DELIST_AT,
        bands=bands,
    )


def complete_bands(
    *,
    second_available_at: UtcInstant | None = None,
    second_admission: BinanceUsdmOrderAdmissionMode = BinanceUsdmOrderAdmissionMode.NORMAL,
    second_deferred: tuple[str, ...] = (),
) -> tuple[BinanceUsdmOrderRuleBand, BinanceUsdmOrderRuleBand]:
    first = band()
    second = band(
        "rules-v2",
        effective_from=RENAME_AT,
        effective_to_exclusive=DELIST_AT,
        available_at=second_available_at,
        tick_size="0.01",
        admission_mode=second_admission,
        deferred_rule_keys=second_deferred,
    )
    return first, second


def order_rule_query(
    *bands: BinanceUsdmOrderRuleBand,
    evaluated_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 10),
    captured_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 20),
    metadata_status: str = "TRADING",
) -> BinanceUsdmOrderRuleQuery:
    metadata = metadata_resolution(
        effective_at=evaluated_at,
        captured_at=captured_at,
        status=metadata_status,
    )
    return BinanceUsdmOrderRuleQuery(
        instrument_metadata=metadata,
        session_id=SESSION_ID,
        evaluated_at=evaluated_at,
        captured_at=captured_at,
        rule_book=rule_book(*bands),
    )


__all__ = [
    "DELIST_AT",
    "ONBOARD_AT",
    "RENAME_AT",
    "REQUIRED_FILTERS",
    "SESSION_ID",
    "band",
    "complete_bands",
    "metadata_resolution",
    "order_rule_query",
    "rule_book",
    "source_ref",
    "BinanceUsdmDeferredRuleKey",
]
