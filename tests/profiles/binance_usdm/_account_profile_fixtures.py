from __future__ import annotations

from crypto_quant_domain import (
    CurrencyId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAccountProfileBand,
    BinanceUsdmHistoricalAccountProfileBook,
    BinanceUsdmAccountProfileQuery,
    BinanceUsdmAccountProfileScope,
    BinanceUsdmAccountProfileSourceRef,
    BinanceUsdmAccountSourceKind,
)

from ._fixtures import RENAME_AT
from ._price_stream_fixtures import metadata_resolution


MILLISECOND = 1_000_000
EVALUATED_AT = RENAME_AT
CAPTURED_AT = UtcInstant(EVALUATED_AT.epoch_nanoseconds + 2 * MILLISECOND)


def simulation_instant(
    instant: UtcInstant,
    *,
    phase: int = 0,
    code: str = "account_source",
    sequence: int = 0,
) -> SimulationInstant:
    return SimulationInstant(
        instant,
        TimelinePhase(phase, code),
        SourceSequence(sequence),
    )


def account_source_ref(
    kind: BinanceUsdmAccountSourceKind,
    *,
    revision_id: str | None = None,
    supersedes_revision_id: str | None = None,
) -> BinanceUsdmAccountProfileSourceRef:
    revision = revision_id or f"{kind.value}-v1"
    key = f"account/{kind.value}/account-1/BTCUSDT"
    return BinanceUsdmAccountProfileSourceRef(
        source_kind=kind,
        source_key=key,
        source_hash=canonical_sha256(
            {
                "source_kind": kind.value,
                "source_key": key,
                "revision_id": revision,
                "supersedes_revision_id": supersedes_revision_id,
            }
        ),
        evidence_key=f"encrypted/{key}/{revision}.json",
        revision_id=revision,
        supersedes_revision_id=supersedes_revision_id,
    )


def source_refs() -> tuple[BinanceUsdmAccountProfileSourceRef, ...]:
    return tuple(account_source_ref(kind) for kind in BinanceUsdmAccountSourceKind)


def account_band(
    *,
    band_id: str = "account-profile-v1",
    account_id: str = "account-1",
    effective_from: UtcInstant | None = None,
    effective_to_exclusive: UtcInstant | None = None,
    available_at: SimulationInstant | None = None,
    scope: BinanceUsdmAccountProfileScope = BinanceUsdmAccountProfileScope.STANDARD_UM,
    fee_tier: int = 0,
    can_trade: bool = True,
    dual_side_position: bool = False,
    multi_assets_margin: bool = False,
    trade_group_id: int = -1,
    margin_type: str = "CROSSED",
    is_auto_add_margin: bool = False,
    leverage: str = "10",
    max_notional_value: str = "1000000.00000000",
    maker_commission_rate: str = "0.00020000",
    taker_commission_rate: str = "0.00050000",
    fee_burn: bool = False,
    refs: tuple[BinanceUsdmAccountProfileSourceRef, ...] | None = None,
    instrument_id=None,
) -> BinanceUsdmAccountProfileBand:
    metadata = metadata_resolution(effective_at=EVALUATED_AT, captured_at=CAPTURED_AT)
    return BinanceUsdmAccountProfileBand(
        band_id=band_id,
        account_id=account_id,
        instrument_id=instrument_id or metadata.instrument.instrument_id,
        effective_from=effective_from
        or UtcInstant(EVALUATED_AT.epoch_nanoseconds - MILLISECOND),
        effective_to_exclusive=effective_to_exclusive
        or UtcInstant(EVALUATED_AT.epoch_nanoseconds + MILLISECOND),
        available_at=available_at
        or simulation_instant(UtcInstant(EVALUATED_AT.epoch_nanoseconds + MILLISECOND)),
        scope=scope,
        fee_tier=fee_tier,
        can_trade=can_trade,
        dual_side_position=dual_side_position,
        multi_assets_margin=multi_assets_margin,
        trade_group_id=trade_group_id,
        margin_type=margin_type,
        is_auto_add_margin=is_auto_add_margin,
        leverage=leverage,
        max_notional_value=max_notional_value,
        maker_commission_rate=maker_commission_rate,
        taker_commission_rate=taker_commission_rate,
        fee_burn=fee_burn,
        source_refs=refs or source_refs(),
    )


def account_book(
    *,
    bands: tuple[BinanceUsdmAccountProfileBand, ...] | None = None,
    account_id: str = "account-1",
    instrument_id=None,
    coverage_from: UtcInstant | None = None,
    coverage_to_exclusive: UtcInstant | None = None,
) -> BinanceUsdmHistoricalAccountProfileBook:
    metadata = metadata_resolution(effective_at=EVALUATED_AT, captured_at=CAPTURED_AT)
    return BinanceUsdmHistoricalAccountProfileBook(
        account_profile_book_key="binance-usdm-account-profile-v1",
        account_profile_book_version=1,
        account_id=account_id,
        instrument_id=instrument_id or metadata.instrument.instrument_id,
        coverage_from=coverage_from
        or UtcInstant(EVALUATED_AT.epoch_nanoseconds - MILLISECOND),
        coverage_to_exclusive=coverage_to_exclusive
        or UtcInstant(EVALUATED_AT.epoch_nanoseconds + MILLISECOND),
        bands=(account_band(),) if bands is None else bands,
    )


def account_query(
    *,
    book: BinanceUsdmHistoricalAccountProfileBook | None = None,
    account_id: str = "account-1",
    evaluated_at: UtcInstant = EVALUATED_AT,
    captured_at: SimulationInstant | None = None,
    reporting_currency_id: CurrencyId = CurrencyId("USDT"),
) -> BinanceUsdmAccountProfileQuery:
    return BinanceUsdmAccountProfileQuery(
        instrument_resolution=metadata_resolution(
            effective_at=evaluated_at,
            captured_at=evaluated_at,
        ),
        account_id=account_id,
        account_profile_book=book or account_book(),
        evaluated_at=evaluated_at,
        captured_at=captured_at or simulation_instant(CAPTURED_AT),
        reporting_currency_id=reporting_currency_id,
    )
