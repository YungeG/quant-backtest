"""Finite January-2024 closed-minute authority for 000703.SZ."""

from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_sha256
from crypto_quant_market_data import MarketBundleManifest, MarketEvent

from .bundle_validation import validate_market_bundle_v1
from .tushare_cn_a_share_minute import TushareCnAShareMinuteNormalizationResult
from .tushare_cn_a_share_minute_bundle import (
    project_tushare_cn_a_share_minute_bar_close_events_v1,
)


_WORKLIST = (
    "20240102", "20240103", "20240104", "20240105", "20240108", "20240109",
    "20240110", "20240111", "20240112", "20240115", "20240116", "20240117",
    "20240118", "20240119", "20240122", "20240123", "20240124", "20240125",
    "20240126", "20240129", "20240130", "20240131",
)
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000703")
_START = UtcInstant(1_704_124_800_000_000_000)
_END = UtcInstant(1_706_716_800_000_000_000)
_BUNDLE_KEY = "tushare-000703-xshe-minute-close-202401-development-v1"


@dataclass(frozen=True, slots=True)
class Tushare000703January2024MinuteAuthority:
    manifest: MarketBundleManifest
    events: tuple[MarketEvent, ...]

    def __post_init__(self) -> None:
        if type(self.manifest) is not MarketBundleManifest:
            raise TypeError("manifest must be exact MarketBundleManifest")
        if type(self.events) is not tuple or not all(
            type(event) is MarketEvent for event in self.events
        ):
            raise TypeError("events must be an exact MarketEvent tuple")
        validation = validate_market_bundle_v1(
            bundle_key=self.manifest.bundle_key,
            schema_version=self.manifest.schema_version,
            coverage_start=self.manifest.coverage_start,
            coverage_end_exclusive=self.manifest.coverage_end_exclusive,
            instrument_catalog_hash=self.manifest.instrument_catalog_hash,
            events=self.events,
        )
        if validation.failure is not None or validation.manifest != self.manifest:
            raise ValueError("monthly minute authority manifest mismatch")


def _rebuild(
    value: object,
) -> TushareCnAShareMinuteNormalizationResult:
    if type(value) is not TushareCnAShareMinuteNormalizationResult:
        raise TypeError("results must contain exact minute normalization results")
    return TushareCnAShareMinuteNormalizationResult(
        value.request,
        value.snapshot,
        value.raw_bars,
        value.traces,
        value.execution_references,
        value.valuations,
    )


def build_tushare_000703_january_2024_minute_authority_v1(
    results: tuple[TushareCnAShareMinuteNormalizationResult, ...],
    /,
) -> Tushare000703January2024MinuteAuthority:
    if type(results) is not tuple:
        raise TypeError("results must be a tuple")
    rebuilt = tuple(_rebuild(value) for value in results)
    if tuple(value.request.provider_trade_date for value in rebuilt) != _WORKLIST:
        raise ValueError("results must exact-cover the January worklist")
    if any(value.request.instrument_id != _INSTRUMENT for value in rebuilt):
        raise ValueError("results must cover 000703.SZ on XSHE")

    events = tuple(
        event
        for result in rebuilt
        for event in project_tushare_cn_a_share_minute_bar_close_events_v1(result)
    )
    instrument_catalog_hash = canonical_sha256(
        {
            "type": "tushare_000703_january_2024_minute_instrument_catalog",
            "schema_version": 1,
            "instrument_id": _INSTRUMENT,
            "normalization_hashes": tuple(
                result.normalization_hash for result in rebuilt
            ),
        }
    )
    validation = validate_market_bundle_v1(
        bundle_key=_BUNDLE_KEY,
        schema_version=1,
        coverage_start=_START,
        coverage_end_exclusive=_END,
        instrument_catalog_hash=instrument_catalog_hash,
        events=events,
    )
    if validation.failure is not None or validation.manifest is None:
        raise ValueError("monthly minute authority event validation failed")
    return Tushare000703January2024MinuteAuthority(validation.manifest, events)
