from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import TypeAlias

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Price,
    PricePurpose,
    Scale,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
)

from ...marks import (
    MarkObservation,
    MarkResolutionFailure,
    MarkResolutionOutcome,
    MarkResolver,
    ResolvedMark,
    StaleMarkPolicy,
)
from .instrument_metadata import BinanceUsdmInstrumentMetadataResolution

_SCHEMA_VERSION = 1
_MODEL_KEY = "crypto.binance_usdm.price-streams.v1"
_MODEL_VERSION = 1
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?")
_LIMITATIONS = (
    "development_grade_archive_completeness_unproven",
    "settlement_price_unsupported",
    "funding_price_owned_by_g10e",
)


class BinanceUsdmPriceSourceKind(str, Enum):
    AGGREGATE_TRADE = "aggregate_trade"
    MARK_PRICE_KLINE = "mark_price_kline"


class BinanceUsdmPriceStreamFailureCode(str, Enum):
    INSTRUMENT_METADATA_MISMATCH = "instrument_metadata_mismatch"
    UNSUPPORTED_PRICE_PURPOSE = "unsupported_price_purpose"
    PRICE_PURPOSE_OWNED_BY_G10E = "price_purpose_owned_by_g10e"
    MISSING_SOURCE_RECORDS = "missing_source_records"
    SOURCE_NOT_AVAILABLE = "source_not_available"
    MISSING_PURPOSE_COVERAGE = "missing_purpose_coverage"
    OVERLAPPING_PURPOSE_COVERAGE = "overlapping_purpose_coverage"
    INVALID_DECIMAL_FIELD = "invalid_decimal_field"
    INVALID_SOURCE_TIMING = "invalid_source_timing"
    UNREPRESENTABLE_AVAILABILITY_ORDER = "unrepresentable_availability_order"
    SOURCE_IDENTITY_CONFLICT = "source_identity_conflict"
    MARK_RESOLUTION_FAILED = "mark_resolution_failed"
    METADATA_CONFLICT = "metadata_conflict"


def _text(name: str, value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty stripped text")


def _sha256(name: str, value: object) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")


def _utc(name: str, value: object) -> None:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be exact UtcInstant")


def _simulation(name: str, value: object) -> None:
    if type(value) is not SimulationInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")


@dataclass(frozen=True, slots=True)
class BinanceUsdmPriceSourceRef:
    source_key: str
    source_hash: str
    archive_key: str
    revision_id: str
    supersedes_revision_id: str | None

    def __post_init__(self) -> None:
        _text("source_key", self.source_key)
        _sha256("source_hash", self.source_hash)
        _text("archive_key", self.archive_key)
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
            if self.supersedes_revision_id == self.revision_id:
                raise ValueError("source revision cannot supersede itself")

    @property
    def source_ref_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_price_source_ref",
            "schema_version": _SCHEMA_VERSION,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "archive_key": self.archive_key,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmAggregateTradePrice:
    event_id: str
    instrument_id: InstrumentId
    aggregate_trade_id: int
    price: str
    quantity: str
    first_trade_id: int
    last_trade_id: int
    trade_at: UtcInstant
    available_at: SimulationInstant
    buyer_is_maker: bool
    source_ref: BinanceUsdmPriceSourceRef

    def __post_init__(self) -> None:
        _text("event_id", self.event_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        for name in ("aggregate_trade_id", "first_trade_id", "last_trade_id"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        _text("price", self.price)
        _text("quantity", self.quantity)
        _utc("trade_at", self.trade_at)
        _simulation("available_at", self.available_at)
        if type(self.buyer_is_maker) is not bool:
            raise TypeError("buyer_is_maker must be bool")
        if type(self.source_ref) is not BinanceUsdmPriceSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmPriceSourceRef")

    @property
    def event_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_aggregate_trade_price",
            "schema_version": _SCHEMA_VERSION,
            "event_id": self.event_id,
            "instrument_id": self.instrument_id,
            "aggregate_trade_id": self.aggregate_trade_id,
            "price": self.price,
            "quantity": self.quantity,
            "first_trade_id": self.first_trade_id,
            "last_trade_id": self.last_trade_id,
            "trade_at": self.trade_at,
            "available_at": self.available_at,
            "buyer_is_maker": self.buyer_is_maker,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarkPriceKline:
    event_id: str
    instrument_id: InstrumentId
    interval_key: str
    open_time_milliseconds: int
    close_time_milliseconds: int
    open_price: str
    high_price: str
    low_price: str
    close_price: str
    closed_at: SimulationInstant
    available_at: SimulationInstant
    closed_final: bool
    source_ref: BinanceUsdmPriceSourceRef

    def __post_init__(self) -> None:
        _text("event_id", self.event_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        _text("interval_key", self.interval_key)
        for name in ("open_time_milliseconds", "close_time_milliseconds"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in ("open_price", "high_price", "low_price", "close_price"):
            _text(name, getattr(self, name))
        _simulation("closed_at", self.closed_at)
        _simulation("available_at", self.available_at)
        if type(self.closed_final) is not bool:
            raise TypeError("closed_final must be bool")
        if type(self.source_ref) is not BinanceUsdmPriceSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmPriceSourceRef")

    @property
    def interval_start(self) -> UtcInstant:
        return UtcInstant(self.open_time_milliseconds * 1_000_000)

    @property
    def interval_end_exclusive(self) -> UtcInstant:
        return UtcInstant((self.close_time_milliseconds + 1) * 1_000_000)

    @property
    def event_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_mark_price_kline",
            "schema_version": _SCHEMA_VERSION,
            "event_id": self.event_id,
            "instrument_id": self.instrument_id,
            "interval_key": self.interval_key,
            "open_time_milliseconds": self.open_time_milliseconds,
            "close_time_milliseconds": self.close_time_milliseconds,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "closed_at": self.closed_at,
            "available_at": self.available_at,
            "closed_final": self.closed_final,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmPriceStreamCoverage:
    coverage_id: str
    instrument_id: InstrumentId
    price_purpose: PricePurpose
    source_kind: BinanceUsdmPriceSourceKind
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    stream_id: str
    source_ref: BinanceUsdmPriceSourceRef

    def __post_init__(self) -> None:
        _text("coverage_id", self.coverage_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be exact PricePurpose")
        if type(self.source_kind) is not BinanceUsdmPriceSourceKind:
            raise TypeError("source_kind must be exact BinanceUsdmPriceSourceKind")
        _utc("coverage_from", self.coverage_from)
        _utc("coverage_to_exclusive", self.coverage_to_exclusive)
        _text("stream_id", self.stream_id)
        if type(self.source_ref) is not BinanceUsdmPriceSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmPriceSourceRef")

    def contains(self, instant: UtcInstant) -> bool:
        return self.coverage_from <= instant < self.coverage_to_exclusive

    @property
    def coverage_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_price_stream_coverage",
            "schema_version": _SCHEMA_VERSION,
            "coverage_id": self.coverage_id,
            "instrument_id": self.instrument_id,
            "price_purpose": self.price_purpose.value,
            "source_kind": self.source_kind.value,
            "coverage_from": self.coverage_from,
            "coverage_to_exclusive": self.coverage_to_exclusive,
            "stream_id": self.stream_id,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmHistoricalPriceBook:
    price_book_key: str
    price_book_version: int
    instrument_id: InstrumentId
    quote_currency_id: CurrencyId
    coverages: tuple[BinanceUsdmPriceStreamCoverage, ...]
    aggregate_trades: tuple[BinanceUsdmAggregateTradePrice, ...]
    mark_price_klines: tuple[BinanceUsdmMarkPriceKline, ...]

    def __post_init__(self) -> None:
        _text("price_book_key", self.price_book_key)
        if type(self.price_book_version) is not int or self.price_book_version <= 0:
            raise ValueError("price_book_version must be a positive integer")
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.quote_currency_id) is not CurrencyId:
            raise TypeError("quote_currency_id must be exact CurrencyId")
        if type(self.coverages) is not tuple or not all(
            type(value) is BinanceUsdmPriceStreamCoverage for value in self.coverages
        ):
            raise TypeError("coverages must be a tuple of exact coverages")
        if type(self.aggregate_trades) is not tuple or not all(
            type(value) is BinanceUsdmAggregateTradePrice
            for value in self.aggregate_trades
        ):
            raise TypeError("aggregate_trades must be a tuple of exact records")
        if type(self.mark_price_klines) is not tuple or not all(
            type(value) is BinanceUsdmMarkPriceKline
            for value in self.mark_price_klines
        ):
            raise TypeError("mark_price_klines must be a tuple of exact records")
        object.__setattr__(
            self,
            "coverages",
            tuple(
                sorted(
                    self.coverages,
                    key=lambda value: (
                        value.price_purpose.value,
                        value.coverage_from,
                        value.coverage_to_exclusive,
                        value.coverage_id,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "aggregate_trades",
            tuple(
                sorted(
                    self.aggregate_trades,
                    key=lambda value: (
                        value.trade_at,
                        value.aggregate_trade_id,
                        value.event_id,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "mark_price_klines",
            tuple(
                sorted(
                    self.mark_price_klines,
                    key=lambda value: (
                        value.open_time_milliseconds,
                        value.close_time_milliseconds,
                        value.event_id,
                    ),
                )
            ),
        )

    @property
    def price_book_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_historical_price_book",
            "schema_version": _SCHEMA_VERSION,
            "price_book_key": self.price_book_key,
            "price_book_version": self.price_book_version,
            "instrument_id": self.instrument_id,
            "quote_currency_id": self.quote_currency_id,
            "coverages": list(self.coverages),
            "aggregate_trades": list(self.aggregate_trades),
            "mark_price_klines": list(self.mark_price_klines),
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmPricePurposeQuery:
    instrument_metadata: BinanceUsdmInstrumentMetadataResolution
    price_book: BinanceUsdmHistoricalPriceBook
    price_purpose: PricePurpose
    requested_at: UtcInstant
    captured_at: SimulationInstant
    stale_policy: StaleMarkPolicy | None
    liquidation_interval_start: UtcInstant | None
    liquidation_interval_end_exclusive: UtcInstant | None

    def __post_init__(self) -> None:
        if type(self.instrument_metadata) is not BinanceUsdmInstrumentMetadataResolution:
            raise TypeError(
                "instrument_metadata must be exact BinanceUsdmInstrumentMetadataResolution"
            )
        if type(self.price_book) is not BinanceUsdmHistoricalPriceBook:
            raise TypeError("price_book must be exact BinanceUsdmHistoricalPriceBook")
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be exact PricePurpose")
        _utc("requested_at", self.requested_at)
        _simulation("captured_at", self.captured_at)
        if self.stale_policy is not None and type(self.stale_policy) is not StaleMarkPolicy:
            raise TypeError("stale_policy must be exact StaleMarkPolicy or None")
        for name in (
            "liquidation_interval_start",
            "liquidation_interval_end_exclusive",
        ):
            value = getattr(self, name)
            if value is not None:
                _utc(name, value)

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_price_purpose_query",
            "schema_version": _SCHEMA_VERSION,
            "instrument_metadata": self.instrument_metadata,
            "price_book": self.price_book,
            "price_purpose": self.price_purpose.value,
            "requested_at": self.requested_at,
            "captured_at": self.captured_at,
            "stale_policy": self.stale_policy,
            "liquidation_interval_start": self.liquidation_interval_start,
            "liquidation_interval_end_exclusive": self.liquidation_interval_end_exclusive,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmLiquidationMarkBar:
    event_id: str
    instrument_id: InstrumentId
    price_purpose: PricePurpose
    interval_start: UtcInstant
    interval_end_exclusive: UtcInstant
    low: Price
    high: Price
    closed_at: SimulationInstant
    available_at: SimulationInstant
    stream_id: str
    revision_id: str
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("event_id", self.event_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if self.price_purpose is not PricePurpose.LIQUIDATION:
            raise ValueError("liquidation bar must use LIQUIDATION purpose")
        _utc("interval_start", self.interval_start)
        _utc("interval_end_exclusive", self.interval_end_exclusive)
        if type(self.low) is not Price or type(self.high) is not Price:
            raise TypeError("low and high must be exact Price")
        _simulation("closed_at", self.closed_at)
        _simulation("available_at", self.available_at)
        _text("stream_id", self.stream_id)
        _text("revision_id", self.revision_id)
        _text("source_key", self.source_key)
        _sha256("source_hash", self.source_hash)

    @property
    def bar_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_liquidation_mark_bar",
            "schema_version": _SCHEMA_VERSION,
            "event_id": self.event_id,
            "instrument_id": self.instrument_id,
            "price_purpose": self.price_purpose.value,
            "interval_start": self.interval_start,
            "interval_end_exclusive": self.interval_end_exclusive,
            "low": self.low,
            "high": self.high,
            "closed_at": self.closed_at,
            "available_at": self.available_at,
            "stream_id": self.stream_id,
            "revision_id": self.revision_id,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


PriceSourceRecord: TypeAlias = BinanceUsdmAggregateTradePrice | BinanceUsdmMarkPriceKline


@dataclass(frozen=True, slots=True)
class _DecimalValue:
    units: int
    scale: int


def _decimal(value: str) -> _DecimalValue | None:
    match = _DECIMAL.fullmatch(value)
    if match is None:
        return None
    fraction = match.group(1) or ""
    units = 0
    for character in value:
        if character != ".":
            units = units * 10 + ord(character) - ord("0")
    scale = len(fraction)
    while scale and units % 10 == 0:
        units //= 10
        scale -= 1
    if units <= 0:
        return None
    return _DecimalValue(units, scale)


def _units_at(value: _DecimalValue, scale: int) -> int:
    return value.units * 10 ** (scale - value.scale)


def _compare(left: _DecimalValue, right: _DecimalValue) -> int:
    scale = max(left.scale, right.scale)
    return _units_at(left, scale) - _units_at(right, scale)


def _expected_source_kind(purpose: PricePurpose) -> BinanceUsdmPriceSourceKind:
    if purpose is PricePurpose.EXECUTION_REFERENCE:
        return BinanceUsdmPriceSourceKind.AGGREGATE_TRADE
    return BinanceUsdmPriceSourceKind.MARK_PRICE_KLINE


def _model_digest() -> str:
    return canonical_sha256(
        {
            "type": "binance_usdm_price_stream_model",
            "schema_version": _SCHEMA_VERSION,
            "model_key": _MODEL_KEY,
            "model_version": _MODEL_VERSION,
            "mapping": {
                PricePurpose.EXECUTION_REFERENCE.value: "aggregate_trade.price@trade_time",
                PricePurpose.VALUATION.value: "mark_price_kline.close",
                PricePurpose.MARGIN.value: "mark_price_kline.close",
                PricePurpose.LIQUIDATION.value: "mark_price_kline.close+low+high",
                PricePurpose.SETTLEMENT.value: "unsupported",
                PricePurpose.FUNDING.value: "owned_by_g10e",
            },
            "limitations": list(_LIMITATIONS),
        }
    )


def _relevant_records(query: BinanceUsdmPricePurposeQuery) -> tuple[PriceSourceRecord, ...]:
    if query.price_purpose is PricePurpose.EXECUTION_REFERENCE:
        return query.price_book.aggregate_trades
    return query.price_book.mark_price_klines


def _visible_records(query: BinanceUsdmPricePurposeQuery) -> tuple[PriceSourceRecord, ...]:
    return tuple(
        value
        for value in _relevant_records(query)
        if value.available_at <= query.captured_at
    )


def _purpose_coverages(
    query: BinanceUsdmPricePurposeQuery,
) -> tuple[BinanceUsdmPriceStreamCoverage, ...]:
    expected = _expected_source_kind(query.price_purpose)
    return tuple(
        value
        for value in query.price_book.coverages
        if value.price_purpose is query.price_purpose
        and value.source_kind is expected
    )


def _coverage_failure(
    query: BinanceUsdmPricePurposeQuery,
) -> BinanceUsdmPriceStreamFailureCode | None:
    coverages = _purpose_coverages(query)
    if not coverages:
        return BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE
    for previous, current in zip(coverages, coverages[1:], strict=False):
        if current.coverage_from < previous.coverage_to_exclusive:
            return BinanceUsdmPriceStreamFailureCode.OVERLAPPING_PURPOSE_COVERAGE
        if current.coverage_from > previous.coverage_to_exclusive:
            return BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE
    if query.price_purpose is PricePurpose.LIQUIDATION:
        start = query.liquidation_interval_start
        end = query.liquidation_interval_end_exclusive
        if start is None or end is None or start >= end:
            return BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE
        cursor = start
        for coverage in coverages:
            if coverage.coverage_to_exclusive <= cursor:
                continue
            if coverage.coverage_from != cursor:
                return BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE
            cursor = min(coverage.coverage_to_exclusive, end)
            if cursor == end:
                return None
        return BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE
    matching = tuple(value for value in coverages if value.contains(query.requested_at))
    if not matching:
        return BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE
    if len(matching) != 1:
        return BinanceUsdmPriceStreamFailureCode.OVERLAPPING_PURPOSE_COVERAGE
    return None


def _decimal_failure(records: tuple[PriceSourceRecord, ...]) -> bool:
    for record in records:
        fields = (
            (record.price, record.quantity)
            if isinstance(record, BinanceUsdmAggregateTradePrice)
            else (
                record.open_price,
                record.high_price,
                record.low_price,
                record.close_price,
            )
        )
        if any(_decimal(value) is None for value in fields):
            return True
    return False


def _timing_failure(records: tuple[PriceSourceRecord, ...]) -> bool:
    for record in records:
        if isinstance(record, BinanceUsdmAggregateTradePrice):
            if (
                record.first_trade_id > record.last_trade_id
                or record.available_at.instant < record.trade_at
            ):
                return True
        else:
            if (
                not record.closed_final
                or record.open_time_milliseconds > record.close_time_milliseconds
                or record.closed_at.instant != record.interval_end_exclusive
                or record.available_at < record.closed_at
            ):
                return True
            values = tuple(
                _decimal(value)
                for value in (
                    record.open_price,
                    record.high_price,
                    record.low_price,
                    record.close_price,
                )
            )
            open_value, high_value, low_value, close_value = values
            if (
                open_value is None
                or high_value is None
                or low_value is None
                or close_value is None
            ):
                continue
            if (
                _compare(low_value, high_value) > 0
                or _compare(open_value, low_value) < 0
                or _compare(open_value, high_value) > 0
                or _compare(close_value, low_value) < 0
                or _compare(close_value, high_value) > 0
            ):
                return True
    return False


def _unrepresentable(records: tuple[PriceSourceRecord, ...]) -> bool:
    for record in records:
        observed = (
            record.trade_at
            if isinstance(record, BinanceUsdmAggregateTradePrice)
            else record.closed_at.instant
        )
        available = record.available_at
        if available.instant == observed and (
            available.phase.rank != 0 or available.source_sequence.value != 0
        ):
            return True
    return False


def _identity_conflict(records: tuple[PriceSourceRecord, ...]) -> bool:
    event_ids: set[str] = set()
    natural_ids: set[tuple[object, ...]] = set()
    revisions = {value.source_ref.revision_id for value in records}
    source_hashes: dict[str, str] = {}
    for record in records:
        if record.event_id in event_ids:
            return True
        event_ids.add(record.event_id)
        natural = (
            ("aggregate_trade", record.aggregate_trade_id)
            if isinstance(record, BinanceUsdmAggregateTradePrice)
            else (
                "mark_price_kline",
                record.interval_key,
                record.open_time_milliseconds,
            )
        )
        if natural in natural_ids:
            return True
        natural_ids.add(natural)
        if record.instrument_id != records[0].instrument_id:
            return True
        previous_hash = source_hashes.setdefault(
            record.source_ref.source_key,
            record.source_ref.source_hash,
        )
        if previous_hash != record.source_ref.source_hash:
            return True
        superseded = record.source_ref.supersedes_revision_id
        if superseded is not None and superseded not in revisions:
            return True
    return False


def _metadata_mismatch(query: BinanceUsdmPricePurposeQuery) -> bool:
    metadata = query.instrument_metadata
    book = query.price_book
    if (
        metadata.query.effective_at != query.requested_at
        or metadata.query.captured_at > query.captured_at.instant
        or metadata.instrument.instrument_id != book.instrument_id
        or metadata.contract_metadata.instrument_id != book.instrument_id
        or metadata.contract_metadata.quote_currency != book.quote_currency_id
        or metadata.contract_metadata.settlement_currency != book.quote_currency_id
        or not metadata.listing_interval.contains(query.requested_at)
    ):
        return True
    if query.price_purpose is PricePurpose.LIQUIDATION:
        start = query.liquidation_interval_start
        end = query.liquidation_interval_end_exclusive
        if start is None or end is None or start >= end:
            return False
        if not metadata.listing_interval.contains(start):
            return True
        final = UtcInstant(end.epoch_nanoseconds - 1)
        if not metadata.listing_interval.contains(final):
            return True
    return (
        any(value.instrument_id != book.instrument_id for value in book.coverages)
        or any(
            value.instrument_id != book.instrument_id
            for value in book.aggregate_trades
        )
        or any(
            value.instrument_id != book.instrument_id
            for value in book.mark_price_klines
        )
    )


def _details(
    code: BinanceUsdmPriceStreamFailureCode,
    *subject_ids: str,
) -> tuple[BinanceUsdmPriceStreamFailureCode, str, tuple[str, ...], MarkResolutionFailure | None]:
    return code, code.value.replace("_", " "), tuple(subject_ids) or (code.value,), None


def _point_observations(
    query: BinanceUsdmPricePurposeQuery,
    records: tuple[PriceSourceRecord, ...],
    coverages: tuple[BinanceUsdmPriceStreamCoverage, ...],
) -> tuple[MarkObservation, ...]:
    observations: list[MarkObservation] = []
    for record in records:
        observed_at = (
            record.trade_at
            if isinstance(record, BinanceUsdmAggregateTradePrice)
            else UtcInstant(record.close_time_milliseconds * 1_000_000)
        )
        coverage = next((value for value in coverages if value.contains(observed_at)), None)
        if coverage is None:
            continue
        raw_price = (
            record.price
            if isinstance(record, BinanceUsdmAggregateTradePrice)
            else record.close_price
        )
        parsed = _decimal(raw_price)
        if parsed is None:
            raise ValueError("validated point price became invalid")
        observations.append(
            MarkObservation(
                instrument_id=query.price_book.instrument_id,
                quote_currency_id=query.price_book.quote_currency_id,
                price_purpose=query.price_purpose,
                price=Price(
                    parsed.units,
                    Scale(parsed.scale),
                    str(query.price_book.instrument_id),
                    str(query.price_book.quote_currency_id),
                ),
                observed_at=observed_at,
                available_at=record.available_at.instant,
                stream_id=coverage.stream_id,
                source_event_id=record.event_id,
                revision_id=record.source_ref.revision_id,
            )
        )
    return tuple(observations)


def _liquidation_bars(
    query: BinanceUsdmPricePurposeQuery,
    records: tuple[PriceSourceRecord, ...],
    coverages: tuple[BinanceUsdmPriceStreamCoverage, ...],
) -> tuple[BinanceUsdmLiquidationMarkBar, ...] | None:
    start = query.liquidation_interval_start
    end = query.liquidation_interval_end_exclusive
    if start is None or end is None:
        return None
    rows = tuple(
        value
        for value in records
        if isinstance(value, BinanceUsdmMarkPriceKline)
        and value.interval_end_exclusive > start
        and value.interval_start < end
    )
    if not rows:
        return None
    cursor = start
    result: list[BinanceUsdmLiquidationMarkBar] = []
    for row in rows:
        if row.interval_start != cursor or row.interval_end_exclusive > end:
            return None
        coverage = next(
            (value for value in coverages if value.contains(row.interval_start)),
            None,
        )
        if coverage is None:
            return None
        low = _decimal(row.low_price)
        high = _decimal(row.high_price)
        if low is None or high is None:
            return None
        scale = max(low.scale, high.scale)
        result.append(
            BinanceUsdmLiquidationMarkBar(
                event_id=row.event_id,
                instrument_id=row.instrument_id,
                price_purpose=PricePurpose.LIQUIDATION,
                interval_start=row.interval_start,
                interval_end_exclusive=row.interval_end_exclusive,
                low=Price(
                    _units_at(low, scale),
                    Scale(scale),
                    str(row.instrument_id),
                    str(query.price_book.quote_currency_id),
                ),
                high=Price(
                    _units_at(high, scale),
                    Scale(scale),
                    str(row.instrument_id),
                    str(query.price_book.quote_currency_id),
                ),
                closed_at=row.closed_at,
                available_at=row.available_at,
                stream_id=coverage.stream_id,
                revision_id=row.source_ref.revision_id,
                source_key=row.source_ref.source_key,
                source_hash=row.source_ref.source_hash,
            )
        )
        cursor = row.interval_end_exclusive
    return tuple(result) if cursor == end else None


def _resolve_point_mark(
    query: BinanceUsdmPricePurposeQuery,
    observations: tuple[MarkObservation, ...],
    stale_policy: StaleMarkPolicy,
) -> MarkResolutionOutcome:
    return MarkResolver().resolve(
        observations,
        instrument_id=query.price_book.instrument_id,
        price_purpose=query.price_purpose,
        requested_at=query.requested_at,
        stale_policy=stale_policy,
    )


def _failure_details(
    query: BinanceUsdmPricePurposeQuery,
) -> tuple[
    BinanceUsdmPriceStreamFailureCode,
    str,
    tuple[str, ...],
    MarkResolutionFailure | None,
] | None:
    if _metadata_mismatch(query):
        return _details(BinanceUsdmPriceStreamFailureCode.INSTRUMENT_METADATA_MISMATCH)
    if query.price_purpose is PricePurpose.SETTLEMENT:
        return _details(BinanceUsdmPriceStreamFailureCode.UNSUPPORTED_PRICE_PURPOSE)
    if query.price_purpose is PricePurpose.FUNDING:
        return _details(BinanceUsdmPriceStreamFailureCode.PRICE_PURPOSE_OWNED_BY_G10E)
    records = _relevant_records(query)
    if not records:
        return _details(BinanceUsdmPriceStreamFailureCode.MISSING_SOURCE_RECORDS)
    visible = _visible_records(query)
    if not visible:
        return _details(BinanceUsdmPriceStreamFailureCode.SOURCE_NOT_AVAILABLE)
    coverage_failure = _coverage_failure(query)
    if coverage_failure is not None:
        return _details(coverage_failure)
    if _decimal_failure(visible):
        return _details(BinanceUsdmPriceStreamFailureCode.INVALID_DECIMAL_FIELD)
    if _timing_failure(visible):
        return _details(BinanceUsdmPriceStreamFailureCode.INVALID_SOURCE_TIMING)
    if _unrepresentable(visible):
        return _details(
            BinanceUsdmPriceStreamFailureCode.UNREPRESENTABLE_AVAILABILITY_ORDER
        )
    if _identity_conflict(visible):
        return _details(BinanceUsdmPriceStreamFailureCode.SOURCE_IDENTITY_CONFLICT)
    coverages = _purpose_coverages(query)
    if query.price_purpose is PricePurpose.LIQUIDATION:
        if query.stale_policy is not None:
            return _details(BinanceUsdmPriceStreamFailureCode.METADATA_CONFLICT)
        if _liquidation_bars(query, visible, coverages) is None:
            return _details(BinanceUsdmPriceStreamFailureCode.MISSING_PURPOSE_COVERAGE)
        return None
    if query.stale_policy is None or query.stale_policy.price_purpose is not query.price_purpose:
        return _details(BinanceUsdmPriceStreamFailureCode.METADATA_CONFLICT)
    observations = _point_observations(query, visible, coverages)
    mark_outcome = _resolve_point_mark(query, observations, query.stale_policy)
    if mark_outcome.failure is not None:
        code = BinanceUsdmPriceStreamFailureCode.MARK_RESOLUTION_FAILED
        return code, code.value.replace("_", " "), (mark_outcome.failure.code.value,), mark_outcome.failure
    return None


@dataclass(frozen=True, slots=True)
class _ResolutionValues:
    model_key: str
    model_version: int
    model_digest: str
    visible_source_records: tuple[PriceSourceRecord, ...]
    active_coverages: tuple[BinanceUsdmPriceStreamCoverage, ...]
    observations: tuple[MarkObservation, ...]
    resolved_mark: ResolvedMark | None
    liquidation_bars: tuple[BinanceUsdmLiquidationMarkBar, ...]
    limitations: tuple[str, ...]
    decision_grade_eligible: bool


def _resolution_values(query: BinanceUsdmPricePurposeQuery) -> _ResolutionValues:
    if _failure_details(query) is not None:
        raise ValueError("query has a price stream failure")
    visible = _visible_records(query)
    coverages = _purpose_coverages(query)
    if query.price_purpose is PricePurpose.LIQUIDATION:
        observations = _point_observations(query, visible, coverages)
        bars = _liquidation_bars(query, visible, coverages)
        if bars is None:
            raise ValueError("validated liquidation bars became unavailable")
        resolved_mark = None
    else:
        observations = _point_observations(query, visible, coverages)
        if query.stale_policy is None:
            raise ValueError("validated point query lost stale policy")
        mark_outcome = _resolve_point_mark(
            query,
            observations,
            query.stale_policy,
        )
        if mark_outcome.resolved_mark is None:
            raise ValueError("validated point query lost resolved mark")
        resolved_mark = mark_outcome.resolved_mark
        bars = ()
    return _ResolutionValues(
        model_key=_MODEL_KEY,
        model_version=_MODEL_VERSION,
        model_digest=_model_digest(),
        visible_source_records=visible,
        active_coverages=coverages,
        observations=observations,
        resolved_mark=resolved_mark,
        liquidation_bars=bars,
        limitations=_LIMITATIONS,
        decision_grade_eligible=False,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmPricePurposeResolution:
    query: BinanceUsdmPricePurposeQuery
    model_key: str
    model_version: int
    model_digest: str
    visible_source_records: tuple[PriceSourceRecord, ...]
    active_coverages: tuple[BinanceUsdmPriceStreamCoverage, ...]
    observations: tuple[MarkObservation, ...]
    resolved_mark: ResolvedMark | None
    liquidation_bars: tuple[BinanceUsdmLiquidationMarkBar, ...]
    limitations: tuple[str, ...]
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmPricePurposeQuery:
            raise TypeError("query must be exact BinanceUsdmPricePurposeQuery")
        expected = _resolution_values(self.query)
        actual = tuple(getattr(self, name) for name in expected.__dataclass_fields__)
        wanted = tuple(getattr(expected, name) for name in expected.__dataclass_fields__)
        if actual != wanted:
            raise ValueError("resolution fields must match embedded query")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_price_purpose_resolution",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "model_key": self.model_key,
            "model_version": self.model_version,
            "model_digest": self.model_digest,
            "visible_source_records": list(self.visible_source_records),
            "active_coverages": list(self.active_coverages),
            "observations": list(self.observations),
            "resolved_mark": self.resolved_mark,
            "liquidation_bars": list(self.liquidation_bars),
            "limitations": list(self.limitations),
            "decision_grade_eligible": self.decision_grade_eligible,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmPriceStreamFailure:
    query: BinanceUsdmPricePurposeQuery
    code: BinanceUsdmPriceStreamFailureCode
    message: str
    subject_ids: tuple[str, ...]
    mark_failure: MarkResolutionFailure | None

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmPricePurposeQuery:
            raise TypeError("query must be exact BinanceUsdmPricePurposeQuery")
        if type(self.code) is not BinanceUsdmPriceStreamFailureCode:
            raise TypeError("code must be exact BinanceUsdmPriceStreamFailureCode")
        _text("message", self.message)
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str and bool(value) for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be a tuple of non-empty strings")
        expected = _failure_details(self.query)
        if expected != (self.code, self.message, self.subject_ids, self.mark_failure):
            raise ValueError("failure fields must match embedded query")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_price_stream_failure",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "code": self.code.value,
            "message": self.message,
            "subject_ids": list(self.subject_ids),
            "mark_failure": self.mark_failure,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmPriceStreamOutcome:
    query_hash: str
    model_digest: str
    result: BinanceUsdmPricePurposeResolution | None
    failure: BinanceUsdmPriceStreamFailure | None

    def __post_init__(self) -> None:
        _sha256("query_hash", self.query_hash)
        _sha256("model_digest", self.model_digest)
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one result or failure")
        value = self.result if self.result is not None else self.failure
        if value is None:
            raise ValueError("outcome lost result and failure")
        if value.query.query_hash != self.query_hash or self.model_digest != _model_digest():
            raise ValueError("outcome identity must match embedded query and model")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_price_stream_outcome",
            "schema_version": _SCHEMA_VERSION,
            "query_hash": self.query_hash,
            "model_digest": self.model_digest,
            "result": self.result,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmPriceStreamModel:
    @property
    def model_digest(self) -> str:
        return _model_digest()

    def resolve_price_purpose(
        self,
        query: BinanceUsdmPricePurposeQuery,
        /,
    ) -> BinanceUsdmPriceStreamOutcome:
        if type(query) is not BinanceUsdmPricePurposeQuery:
            raise TypeError("query must be exact BinanceUsdmPricePurposeQuery")
        failure = _failure_details(query)
        if failure is not None:
            code, message, subject_ids, mark_failure = failure
            return BinanceUsdmPriceStreamOutcome(
                query_hash=query.query_hash,
                model_digest=self.model_digest,
                result=None,
                failure=BinanceUsdmPriceStreamFailure(
                    query=query,
                    code=code,
                    message=message,
                    subject_ids=subject_ids,
                    mark_failure=mark_failure,
                ),
            )
        values = _resolution_values(query)
        return BinanceUsdmPriceStreamOutcome(
            query_hash=query.query_hash,
            model_digest=self.model_digest,
            result=BinanceUsdmPricePurposeResolution(
                query=query,
                **{name: getattr(values, name) for name in values.__dataclass_fields__},
            ),
            failure=None,
        )
