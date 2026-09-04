from __future__ import annotations

from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmInstrumentModel,
    BinanceUsdmMarginTierBand,
    BinanceUsdmMarginTierBracket,
    BinanceUsdmMarginTierQuery,
    BinanceUsdmMarginTierRuleBook,
    BinanceUsdmMarginTierScope,
    BinanceUsdmMarginTierSourceRef,
)
from tests.profiles.binance_usdm._fixtures import (
    DELIST_AT,
    ONBOARD_AT,
    RENAME_AT,
    query as instrument_query,
    revision,
)


CONTRACT_INFO_BRACKET_UPDATE = "CONTRACT_INFO_BRACKET_UPDATE"
CONTRACT_INFO_STATUS_UPDATE = "CONTRACT_INFO_STATUS_UPDATE"
USER_DATA_LEVERAGE_BRACKET = "USER_DATA_LEVERAGE_BRACKET"
EVIDENCE_PHASE = TimelinePhase(60, "margin_tier_evidence")


def simulation_instant(
    instant: UtcInstant,
    sequence: int = 0,
) -> SimulationInstant:
    return SimulationInstant(instant, EVIDENCE_PHASE, SourceSequence(sequence))


def metadata_resolution(
    *,
    effective_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 10),
    captured_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 20),
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


def source_ref(
    key: str,
    *,
    source_kind: str = CONTRACT_INFO_BRACKET_UPDATE,
) -> BinanceUsdmMarginTierSourceRef:
    return BinanceUsdmMarginTierSourceRef(
        source_key=key,
        source_hash=canonical_sha256(
            {"source_key": key, "source_kind": source_kind}
        ),
        source_kind=source_kind,
    )


def bracket(
    bracket_id: str,
    *,
    notional_floor: str,
    notional_cap: str,
    maintenance_margin_rate: str,
    maintenance_margin_deduction: str,
    minimum_leverage_range: str,
    maximum_leverage: str,
) -> BinanceUsdmMarginTierBracket:
    return BinanceUsdmMarginTierBracket(
        bracket_id=bracket_id,
        notional_floor=notional_floor,
        notional_cap=notional_cap,
        maintenance_margin_rate=maintenance_margin_rate,
        maintenance_margin_deduction=maintenance_margin_deduction,
        minimum_leverage_range=minimum_leverage_range,
        maximum_leverage=maximum_leverage,
    )


def first_brackets() -> tuple[BinanceUsdmMarginTierBracket, ...]:
    return (
        bracket(
            "1",
            notional_floor="0",
            notional_cap="5000.000",
            maintenance_margin_rate="0.0100",
            maintenance_margin_deduction="0",
            minimum_leverage_range="21",
            maximum_leverage="50",
        ),
        bracket(
            "2",
            notional_floor="5000.000",
            notional_cap="25000",
            maintenance_margin_rate="0.025",
            maintenance_margin_deduction="75.000",
            minimum_leverage_range="11",
            maximum_leverage="20",
        ),
        bracket(
            "3",
            notional_floor="25000",
            notional_cap="100000",
            maintenance_margin_rate="0.05",
            maintenance_margin_deduction="700",
            minimum_leverage_range="1",
            maximum_leverage="10",
        ),
    )


def second_brackets() -> tuple[BinanceUsdmMarginTierBracket, ...]:
    return (
        bracket(
            "1",
            notional_floor="0",
            notional_cap="10000.00",
            maintenance_margin_rate="0.0200",
            maintenance_margin_deduction="0",
            minimum_leverage_range="21",
            maximum_leverage="25",
        ),
        bracket(
            "2",
            notional_floor="10000.00",
            notional_cap="50000",
            maintenance_margin_rate="0.05",
            maintenance_margin_deduction="300.0",
            minimum_leverage_range="6",
            maximum_leverage="10",
        ),
        bracket(
            "3",
            notional_floor="50000",
            notional_cap="200000",
            maintenance_margin_rate="0.10",
            maintenance_margin_deduction="2800",
            minimum_leverage_range="1",
            maximum_leverage="5",
        ),
    )


def band(
    band_id: str = "margin-tiers-v1",
    *,
    effective_from: UtcInstant = ONBOARD_AT,
    effective_to_exclusive: UtcInstant = RENAME_AT,
    available_at: SimulationInstant | None = None,
    scope: BinanceUsdmMarginTierScope = BinanceUsdmMarginTierScope.DEFAULT_SYMBOL,
    notional_coef: str | None = None,
    brackets: tuple[BinanceUsdmMarginTierBracket, ...] | None = None,
    source_key: str | None = None,
    source_kind: str = CONTRACT_INFO_BRACKET_UPDATE,
    instrument_id=None,
) -> BinanceUsdmMarginTierBand:
    instrument = metadata_resolution().instrument.instrument_id
    return BinanceUsdmMarginTierBand(
        band_id=band_id,
        instrument_id=instrument if instrument_id is None else instrument_id,
        effective_from=effective_from,
        effective_to_exclusive=effective_to_exclusive,
        available_at=(
            simulation_instant(
                UtcInstant(effective_from.epoch_nanoseconds + 1)
            )
            if available_at is None
            else available_at
        ),
        scope=scope,
        notional_coef=notional_coef,
        brackets=first_brackets() if brackets is None else brackets,
        source_ref=source_ref(
            source_key or f"contract-info/{band_id}.json",
            source_kind=source_kind,
        ),
    )


def complete_bands(
    *,
    second_available_at: SimulationInstant | None = None,
) -> tuple[BinanceUsdmMarginTierBand, BinanceUsdmMarginTierBand]:
    return (
        band(),
        band(
            "margin-tiers-v2",
            effective_from=RENAME_AT,
            effective_to_exclusive=DELIST_AT,
            available_at=second_available_at,
            brackets=second_brackets(),
        ),
    )


def rule_book(
    *bands: BinanceUsdmMarginTierBand,
) -> BinanceUsdmMarginTierRuleBook:
    metadata = metadata_resolution()
    settlement = metadata.instrument.settlement_currency
    assert settlement is not None
    return BinanceUsdmMarginTierRuleBook(
        rule_book_key="binance-usdm-btc-usdt-margin-tiers-v1",
        rule_book_version=1,
        instrument_id=metadata.instrument.instrument_id,
        settlement_currency_id=settlement,
        coverage_from=ONBOARD_AT,
        coverage_to_exclusive=DELIST_AT,
        bands=bands,
    )


def margin_tier_query(
    *bands: BinanceUsdmMarginTierBand,
    evaluated_at: UtcInstant = UtcInstant(RENAME_AT.epoch_nanoseconds + 10),
    captured_at: SimulationInstant | None = None,
) -> BinanceUsdmMarginTierQuery:
    capture = captured_at or simulation_instant(
        UtcInstant(RENAME_AT.epoch_nanoseconds + 20)
    )
    return BinanceUsdmMarginTierQuery(
        instrument_metadata=metadata_resolution(
            effective_at=evaluated_at,
            captured_at=capture.instant,
        ),
        evaluated_at=evaluated_at,
        captured_at=capture,
        rule_book=rule_book(*bands),
    )


__all__ = [
    "CONTRACT_INFO_BRACKET_UPDATE",
    "CONTRACT_INFO_STATUS_UPDATE",
    "USER_DATA_LEVERAGE_BRACKET",
    "band",
    "bracket",
    "complete_bands",
    "first_brackets",
    "margin_tier_query",
    "metadata_resolution",
    "rule_book",
    "second_brackets",
    "simulation_instant",
    "source_ref",
]
