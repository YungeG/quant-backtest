from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    InstrumentId,
    Money,
    Price,
    PricePurpose,
    Quantity,
    Rate,
    Scale,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_sha256,
)

from .bar_aggregation import BarBucket
from .source_snapshots import (
    SourceSnapshot,
    SourceSnapshotMember,
    SourceSnapshotProvenance,
    verify_source_snapshot,
)

_SCHEMA_VERSION = 1
_MEMBER_KEY = "response/daily.json"
_TS_CODE = "000001.SZ"
_TRADE_DATE = "20240102"
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_CURRENCY = "CNY"
_BUCKET_HASH = "sha256:b58489aeffd996cfa583caac981bfeb39edf0b93280f787d63b0f6b0855dc7b7"
_INTERVAL_START = 1_704_158_100_000_000_000
_INTERVAL_END = 1_704_178_800_000_000_000
_FIELDS = (
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
)
_LIMITATIONS = (
    "corporate_actions_unproven",
    "historical_listing_status_unproven",
    "late_historical_availability",
    "provider_revision_closure_unproven",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


def _text(name: str, value: object, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value) or value != value.strip():
        raise ValueError(f"{name} must be canonical text")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be NFC text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8 text") from error
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if _HASH.fullmatch(text) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return text


@dataclass(frozen=True, slots=True)
class _NumericToken:
    lexeme: str

    def __post_init__(self) -> None:
        if type(self.lexeme) is not str or _NUMBER.fullmatch(self.lexeme) is None:
            raise ValueError("invalid JSON numeric token")


def _numeric_token(value: str) -> _NumericToken:
    return _NumericToken(value)


def _constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _duplicate_free_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _units(token: _NumericToken, target_places: int) -> int:
    sign = -1 if token.lexeme.startswith("-") else 1
    whole, dot, fraction = token.lexeme.removeprefix("-").partition(".")
    if len(fraction) > target_places:
        raise ValueError("numeric token exceeds frozen scale")
    return sign * (
        int(whole) * 10**target_places
        + (int(fraction.ljust(target_places, "0")) if dot else 0)
    )


def _source_record_hash(
    ts_code: str,
    trade_date: str,
    numeric_lexemes: tuple[str, ...],
) -> str:
    return canonical_sha256(
        {
            "type": "tushare_cn_a_share_daily_source_record",
            "schema_version": _SCHEMA_VERSION,
            "fields": _FIELDS,
            "text_values": (ts_code, trade_date),
            "numeric_lexemes": numeric_lexemes,
        }
    )


def _scaled_multiplier(token: _NumericToken, maximum_places: int, multiplier: int) -> int:
    sign = -1 if token.lexeme.startswith("-") else 1
    whole, _, fraction = token.lexeme.removeprefix("-").partition(".")
    if len(fraction) > maximum_places:
        raise ValueError("numeric token exceeds frozen source scale")
    source_units = sign * int(whole + fraction)
    denominator = 10 ** len(fraction)
    numerator = source_units * multiplier
    if numerator % denominator:
        raise ValueError("numeric unit conversion is not integral")
    return numerator // denominator


def _exact_scale(value: object, places: int) -> bool:
    if type(value) is not Scale:
        return False
    try:
        return type(value.places) is int and Scale(value.places) == value and value.places == places
    except (AttributeError, TypeError, ValueError):
        return False


def _exact_utc(value: object) -> bool:
    if type(value) is not UtcInstant:
        return False
    try:
        return type(value.epoch_nanoseconds) is int and UtcInstant(value.epoch_nanoseconds) == value
    except (AttributeError, TypeError, ValueError):
        return False


def _exact_instrument(value: object) -> bool:
    if type(value) is not InstrumentId or type(value.venue) is not VenueId:
        return False
    try:
        rebuilt = InstrumentId(VenueId(value.venue.value), value.stable_key)
    except (AttributeError, TypeError, ValueError):
        return False
    return rebuilt == value


def _exact_price(value: object, *, scale: int = 2) -> bool:
    if type(value) is not Price or not _exact_scale(value.scale, scale):
        return False
    try:
        return type(value.units) is int and Price(
            value.units,
            Scale(scale),
            value.instrument_id,
            value.quote_currency,
        ) == value
    except (AttributeError, TypeError, ValueError):
        return False


def _exact_rate(value: object, *, scale: int, basis: str) -> bool:
    if type(value) is not Rate or not _exact_scale(value.scale, scale):
        return False
    try:
        return type(value.units) is int and Rate(value.units, Scale(scale), value.basis) == value and value.basis == basis
    except (AttributeError, TypeError, ValueError):
        return False


def _exact_quantity(value: object) -> bool:
    if type(value) is not Quantity or not _exact_scale(value.scale, 0):
        return False
    try:
        return type(value.units) is int and Quantity(value.units, Scale(0), value.instrument_id) == value
    except (AttributeError, TypeError, ValueError):
        return False


def _exact_money(value: object) -> bool:
    if type(value) is not Money or not _exact_scale(value.scale, 0):
        return False
    try:
        return type(value.units) is int and Money(value.units, Scale(0), value.currency) == value
    except (AttributeError, TypeError, ValueError):
        return False


def _exact_bucket(value: object) -> bool:
    if type(value) is not BarBucket or type(value.session_id) is not SessionId or type(value.trading_date) is not TradingDate:
        return False
    try:
        if type(value.included_spans) is not tuple or any(
            type(span) is not tuple
            or len(span) != 2
            or not _exact_utc(span[0])
            or not _exact_utc(span[1])
            for span in value.included_spans
        ):
            return False
        rebuilt = BarBucket(
            SessionId(value.session_id.calendar_id, value.session_id.value),
            TradingDate(value.trading_date.calendar_id, value.trading_date.value),
            tuple((UtcInstant(start.epoch_nanoseconds), UtcInstant(end.epoch_nanoseconds)) for start, end in value.included_spans),
            UtcInstant(value.interval_start.epoch_nanoseconds),
            UtcInstant(value.interval_end_exclusive.epoch_nanoseconds),
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return rebuilt == value


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyNormalizationRequest:
    schema_version: int
    snapshot_id: str
    provenance_hash: str
    member_key: str
    member_content_hash: str
    instrument_id: InstrumentId
    provider_trade_date: str
    bucket: BarBucket

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("request schema_version must be 1")
        _hash("snapshot_id", self.snapshot_id)
        _hash("provenance_hash", self.provenance_hash)
        if self.member_key != _MEMBER_KEY:
            raise ValueError("member_key must be response/daily.json")
        _hash("member_content_hash", self.member_content_hash)
        if not _exact_instrument(self.instrument_id) or self.instrument_id != _INSTRUMENT:
            raise ValueError("instrument_id must be exact xshe:000001")
        if self.provider_trade_date != _TRADE_DATE:
            raise ValueError("provider_trade_date must be 20240102")
        if not _exact_bucket(self.bucket):
            raise TypeError("bucket must be exact valid BarBucket")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_normalization_request",
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "provenance_hash": self.provenance_hash,
            "member_key": self.member_key,
            "member_content_hash": self.member_content_hash,
            "instrument_id": self.instrument_id,
            "provider_trade_date": self.provider_trade_date,
            "bucket": self.bucket,
        }

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "request_hash": self.request_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyRawBar:
    instrument_id: InstrumentId
    provider_ts_code: str
    provider_trade_date: str
    bucket: BarBucket
    available_time: UtcInstant
    open_lexeme: str
    high_lexeme: str
    low_lexeme: str
    close_lexeme: str
    pre_close_lexeme: str
    change_lexeme: str
    pct_change_lexeme: str
    volume_lots_lexeme: str
    amount_thousand_cny_lexeme: str
    open_price: Price
    high_price: Price
    low_price: Price
    close_price: Price
    pre_close_price: Price
    change_units: int
    change_scale: Scale
    pct_change: Rate
    volume: Quantity
    amount: Money
    source_record_hash: str
    limitations: tuple[str, ...]
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if not _exact_instrument(self.instrument_id) or self.instrument_id != _INSTRUMENT:
            raise ValueError("raw Bar instrument mismatch")
        if self.provider_ts_code != _TS_CODE or self.provider_trade_date != _TRADE_DATE:
            raise ValueError("raw Bar provider coordinate mismatch")
        if not _exact_bucket(self.bucket) or not _exact_utc(self.available_time):
            raise TypeError("raw Bar bucket/time types mismatch")
        lexemes = (
            self.open_lexeme,
            self.high_lexeme,
            self.low_lexeme,
            self.close_lexeme,
            self.pre_close_lexeme,
            self.change_lexeme,
            self.pct_change_lexeme,
            self.volume_lots_lexeme,
            self.amount_thousand_cny_lexeme,
        )
        if any(type(value) is not str or _NUMBER.fullmatch(value) is None for value in lexemes):
            raise ValueError("raw Bar lexemes must be canonical numeric tokens")
        prices = (
            self.open_price,
            self.high_price,
            self.low_price,
            self.close_price,
            self.pre_close_price,
        )
        if any(
            not _exact_price(value)
            or value.instrument_id != str(_INSTRUMENT)
            or value.quote_currency != _CURRENCY
            for value in prices
        ):
            raise ValueError("raw Bar prices must bind instrument/CNY scale 2")
        if type(self.change_units) is not int or not _exact_scale(self.change_scale, 2):
            raise ValueError("change must use exact integer units and scale 2")
        if not _exact_rate(self.pct_change, scale=4, basis="percent"):
            raise ValueError("percentage change must be exact percent scale 4")
        if not _exact_quantity(self.volume) or self.volume.instrument_id != str(_INSTRUMENT):
            raise ValueError("volume must be exact scale-0 shares")
        if not _exact_money(self.amount) or self.amount.currency != _CURRENCY:
            raise ValueError("amount must be exact scale-0 CNY")
        _hash("source_record_hash", self.source_record_hash)
        expected_prices = tuple(
            _units(_NumericToken(value), 2) for value in lexemes[:5]
        )
        if tuple(value.units for value in prices) != expected_prices:
            raise ValueError("raw Bar prices do not match source lexemes")
        if self.change_units != _units(_NumericToken(self.change_lexeme), 2):
            raise ValueError("raw Bar change does not match source lexeme")
        if self.pct_change.units != _units(_NumericToken(self.pct_change_lexeme), 4):
            raise ValueError("raw Bar percentage does not match source lexeme")
        if self.volume.units != _scaled_multiplier(_NumericToken(self.volume_lots_lexeme), 2, 100):
            raise ValueError("raw Bar volume does not match source lexeme")
        if self.amount.units != _scaled_multiplier(_NumericToken(self.amount_thousand_cny_lexeme), 3, 1000):
            raise ValueError("raw Bar amount does not match source lexeme")
        if self.source_record_hash != _source_record_hash(
            self.provider_ts_code,
            self.provider_trade_date,
            lexemes,
        ):
            raise ValueError("raw Bar source record hash does not match retained source")
        if not (
            0 < self.low_price.units <= self.open_price.units <= self.high_price.units
            and 0 < self.low_price.units <= self.close_price.units <= self.high_price.units
            and self.pre_close_price.units > 0
            and self.close_price.units - self.pre_close_price.units == self.change_units
            and self.volume.units >= 0
            and self.amount.units >= 0
        ):
            raise ValueError("raw Bar economic invariants mismatch")
        if not _bucket_valid(self.bucket) or self.available_time < self.bucket.interval_end_exclusive:
            raise ValueError("raw Bar bucket/availability mismatch")
        if self.limitations != _LIMITATIONS:
            raise ValueError("raw Bar limitations mismatch")
        if type(self.decision_grade_eligible) is not bool or type(self.deployment_authorized) is not bool:
            raise TypeError("qualification flags must be bool")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("qualification flags must remain false")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_raw_bar",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id,
            "provider_ts_code": self.provider_ts_code,
            "provider_trade_date": self.provider_trade_date,
            "bucket": self.bucket,
            "available_time": self.available_time,
            "open_lexeme": self.open_lexeme,
            "high_lexeme": self.high_lexeme,
            "low_lexeme": self.low_lexeme,
            "close_lexeme": self.close_lexeme,
            "pre_close_lexeme": self.pre_close_lexeme,
            "change_lexeme": self.change_lexeme,
            "pct_change_lexeme": self.pct_change_lexeme,
            "volume_lots_lexeme": self.volume_lots_lexeme,
            "amount_thousand_cny_lexeme": self.amount_thousand_cny_lexeme,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "pre_close_price": self.pre_close_price,
            "change_units": self.change_units,
            "change_scale": self.change_scale.places,
            "pct_change": self.pct_change,
            "volume": self.volume,
            "amount": self.amount,
            "source_record_hash": self.source_record_hash,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def raw_bar_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "raw_bar_hash": self.raw_bar_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailySourceTrace:
    snapshot_id: str
    provenance_hash: str
    source_key: str
    member_key: str
    member_content_hash: str
    record_index: int
    source_record_hash: str
    raw_bar_hash: str
    revision_id: str
    supersedes_revision_id: str | None
    revision_closure_complete: bool

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "provenance_hash",
            "member_content_hash",
            "source_record_hash",
            "raw_bar_hash",
            "revision_id",
        ):
            _hash(name, getattr(self, name))
        _text("source_key", self.source_key)
        if self.member_key != _MEMBER_KEY or type(self.record_index) is not int or self.record_index != 0:
            raise ValueError("trace member/index mismatch")
        if self.revision_id != self.member_content_hash or self.supersedes_revision_id is not None:
            raise ValueError("trace revision identity mismatch")
        if type(self.revision_closure_complete) is not bool or self.revision_closure_complete:
            raise ValueError("revision closure must remain incomplete")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_source_trace",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "provenance_hash": self.provenance_hash,
            "source_key": self.source_key,
            "member_key": self.member_key,
            "member_content_hash": self.member_content_hash,
            "record_index": self.record_index,
            "source_record_hash": self.source_record_hash,
            "raw_bar_hash": self.raw_bar_hash,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "revision_closure_complete": self.revision_closure_complete,
        }

    @property
    def trace_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "trace_hash": self.trace_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyExecutionReference:
    raw_bar_hash: str
    price_purpose: PricePurpose
    instrument_id: InstrumentId
    bucket: BarBucket
    available_time: UtcInstant
    open_price: Price
    high_price: Price
    low_price: Price
    close_price: Price
    volume: Quantity
    amount: Money

    def __post_init__(self) -> None:
        _hash("raw_bar_hash", self.raw_bar_hash)
        if self.price_purpose is not PricePurpose.EXECUTION_REFERENCE:
            raise ValueError("execution projection purpose mismatch")
        if not _exact_instrument(self.instrument_id) or not _exact_bucket(self.bucket) or not _exact_utc(self.available_time):
            raise TypeError("execution projection types mismatch")
        if self.instrument_id != _INSTRUMENT or not _bucket_valid(self.bucket) or self.available_time < self.bucket.interval_end_exclusive:
            raise ValueError("execution projection identity/time mismatch")
        if any(
            not _exact_price(value)
            or value.instrument_id != str(_INSTRUMENT)
            or value.quote_currency != _CURRENCY
            for value in (self.open_price, self.high_price, self.low_price, self.close_price)
        ):
            raise ValueError("execution projection price mismatch")
        if not _exact_quantity(self.volume) or self.volume.instrument_id != str(_INSTRUMENT):
            raise ValueError("execution projection volume mismatch")
        if not _exact_money(self.amount) or self.amount.currency != _CURRENCY:
            raise ValueError("execution projection amount mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_execution_reference",
            "schema_version": _SCHEMA_VERSION,
            "raw_bar_hash": self.raw_bar_hash,
            "price_purpose": self.price_purpose.value,
            "instrument_id": self.instrument_id,
            "bucket": self.bucket,
            "available_time": self.available_time,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "amount": self.amount,
        }

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "projection_hash": self.projection_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyValuation:
    raw_bar_hash: str
    price_purpose: PricePurpose
    instrument_id: InstrumentId
    valuation_at: UtcInstant
    available_time: UtcInstant
    close_price: Price

    def __post_init__(self) -> None:
        _hash("raw_bar_hash", self.raw_bar_hash)
        if self.price_purpose is not PricePurpose.VALUATION:
            raise ValueError("valuation projection purpose mismatch")
        if not _exact_instrument(self.instrument_id) or not _exact_utc(self.valuation_at) or not _exact_utc(self.available_time) or not _exact_price(self.close_price):
            raise TypeError("valuation projection types mismatch")
        if (
            self.instrument_id != _INSTRUMENT
            or self.valuation_at.epoch_nanoseconds != _INTERVAL_END
            or self.available_time < self.valuation_at
            or self.close_price.instrument_id != str(_INSTRUMENT)
            or self.close_price.quote_currency != _CURRENCY
        ):
            raise ValueError("valuation projection identity/time/price mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_valuation",
            "schema_version": _SCHEMA_VERSION,
            "raw_bar_hash": self.raw_bar_hash,
            "price_purpose": self.price_purpose.value,
            "instrument_id": self.instrument_id,
            "valuation_at": self.valuation_at,
            "available_time": self.available_time,
            "close_price": self.close_price,
        }

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "projection_hash": self.projection_hash}


class TushareCnAShareDailyNormalizationFailureCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SNAPSHOT_INVALID = "snapshot_invalid"
    SNAPSHOT_BINDING_MISMATCH = "snapshot_binding_mismatch"
    SOURCE_MEMBER_MISSING = "source_member_missing"
    SOURCE_MEMBER_BINDING_MISMATCH = "source_member_binding_mismatch"
    SOURCE_JSON_INVALID = "source_json_invalid"
    SOURCE_SCHEMA_MISMATCH = "source_schema_mismatch"
    SOURCE_RECORD_MISMATCH = "source_record_mismatch"
    DECIMAL_MAPPING_INVALID = "decimal_mapping_invalid"
    BAR_INVARIANT_VIOLATION = "bar_invariant_violation"
    BUCKET_BINDING_MISMATCH = "bucket_binding_mismatch"
    AVAILABILITY_INVALID = "availability_invalid"


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyNormalizationFailure:
    code: TushareCnAShareDailyNormalizationFailureCode
    member_key: str | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not TushareCnAShareDailyNormalizationFailureCode:
            raise TypeError("code must be exact failure code")
        if self.member_key is not None:
            _text("member_key", self.member_key)
        if self.field is not None:
            _text("field", self.field)

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_normalization_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "member_key": self.member_key,
            "field": self.field,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyNormalizationResult:
    request: TushareCnAShareDailyNormalizationRequest
    snapshot: SourceSnapshot
    raw_bar: TushareCnAShareDailyRawBar
    trace: TushareCnAShareDailySourceTrace
    execution_reference: TushareCnAShareDailyExecutionReference
    valuation: TushareCnAShareDailyValuation

    def __post_init__(self) -> None:
        if (
            type(self.request) is not TushareCnAShareDailyNormalizationRequest
            or type(self.snapshot) is not SourceSnapshot
            or type(self.raw_bar) is not TushareCnAShareDailyRawBar
            or type(self.trace) is not TushareCnAShareDailySourceTrace
            or type(self.execution_reference) is not TushareCnAShareDailyExecutionReference
            or type(self.valuation) is not TushareCnAShareDailyValuation
        ):
            raise TypeError("normalization result contains wrong value types")
        try:
            rebuilt_request = TushareCnAShareDailyNormalizationRequest(
                self.request.schema_version,
                self.request.snapshot_id,
                self.request.provenance_hash,
                self.request.member_key,
                self.request.member_content_hash,
                self.request.instrument_id,
                self.request.provider_trade_date,
                self.request.bucket,
            )
            rebuilt_raw = TushareCnAShareDailyRawBar(
                **{
                    field: getattr(self.raw_bar, field)
                    for field in self.raw_bar.__dataclass_fields__
                }
            )
            rebuilt_trace = TushareCnAShareDailySourceTrace(
                **{
                    field: getattr(self.trace, field)
                    for field in self.trace.__dataclass_fields__
                }
            )
            rebuilt_execution = TushareCnAShareDailyExecutionReference(
                **{
                    field: getattr(self.execution_reference, field)
                    for field in self.execution_reference.__dataclass_fields__
                }
            )
            rebuilt_valuation = TushareCnAShareDailyValuation(
                **{
                    field: getattr(self.valuation, field)
                    for field in self.valuation.__dataclass_fields__
                }
            )
            rebuilt_snapshot = _reconstruct_snapshot(self.snapshot)
            verified = (
                verify_source_snapshot(rebuilt_snapshot)
                if rebuilt_snapshot is not None
                else None
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("normalization result authority is invalid") from error
        if (
            rebuilt_request != self.request
            or rebuilt_raw != self.raw_bar
            or rebuilt_trace != self.trace
            or rebuilt_execution != self.execution_reference
            or rebuilt_valuation != self.valuation
            or rebuilt_snapshot is None
            or verified is None
            or verified.snapshot is None
        ):
            raise ValueError("normalization result authority reconstruction mismatch")
        member = _member(self.snapshot, self.request.member_key)
        if (
            self.request.snapshot_id != self.snapshot.snapshot_id
            or self.request.provenance_hash != self.snapshot.provenance_hash
            or member is None
            or self.request.member_content_hash != member.content_hash
        ):
            raise ValueError("request does not bind verified snapshot member")
        if (
            self.raw_bar.instrument_id != self.request.instrument_id
            or self.raw_bar.provider_trade_date != self.request.provider_trade_date
            or self.raw_bar.bucket != self.request.bucket
            or self.raw_bar.available_time.epoch_nanoseconds
            != member.acquired_at_epoch_nanoseconds
        ):
            raise ValueError("raw Bar does not bind request/member availability")
        if (
            self.trace.snapshot_id != self.snapshot.snapshot_id
            or self.trace.provenance_hash != self.snapshot.provenance_hash
            or self.trace.source_key != self.snapshot.provenance.source_key
            or self.trace.member_key != member.member_key
            or self.trace.member_content_hash != member.content_hash
            or self.trace.revision_id != member.content_hash
            or self.trace.supersedes_revision_id is not None
            or self.trace.revision_closure_complete
            or self.trace.raw_bar_hash != self.raw_bar.raw_bar_hash
            or self.trace.source_record_hash != self.raw_bar.source_record_hash
        ):
            raise ValueError("trace does not exact-bind request/snapshot/raw Bar")
        if (
            self.execution_reference.raw_bar_hash != self.raw_bar.raw_bar_hash
            or self.valuation.raw_bar_hash != self.raw_bar.raw_bar_hash
            or self.execution_reference.instrument_id != self.raw_bar.instrument_id
            or self.execution_reference.bucket != self.raw_bar.bucket
            or self.execution_reference.available_time != self.raw_bar.available_time
            or self.execution_reference.open_price != self.raw_bar.open_price
            or self.execution_reference.high_price != self.raw_bar.high_price
            or self.execution_reference.low_price != self.raw_bar.low_price
            or self.execution_reference.close_price != self.raw_bar.close_price
            or self.execution_reference.volume != self.raw_bar.volume
            or self.execution_reference.amount != self.raw_bar.amount
            or self.valuation.instrument_id != self.raw_bar.instrument_id
            or self.valuation.valuation_at != self.raw_bar.bucket.interval_end_exclusive
            or self.valuation.available_time != self.raw_bar.available_time
            or self.valuation.close_price != self.raw_bar.close_price
        ):
            raise ValueError("projections do not exact-match raw Bar")
        if self.execution_reference.projection_hash == self.valuation.projection_hash:
            raise ValueError("purpose projections must remain distinct")

    @property
    def request_hash(self) -> str:
        return self.request.request_hash

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_normalization_result",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request.to_canonical_dict(),
            "snapshot": self.snapshot.to_canonical_dict(),
            "raw_bar": self.raw_bar,
            "trace": self.trace,
            "execution_reference": self.execution_reference,
            "valuation": self.valuation,
        }

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            **self._body(),
            "request_hash": self.request_hash,
            "normalization_hash": self.normalization_hash,
        }


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyNormalizationOutcome:
    result: TushareCnAShareDailyNormalizationResult | None = None
    failure: TushareCnAShareDailyNormalizationFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one result or failure")
        if self.result is not None and type(self.result) is not TushareCnAShareDailyNormalizationResult:
            raise TypeError("result must be exact normalization result")
        if self.failure is not None and type(self.failure) is not TushareCnAShareDailyNormalizationFailure:
            raise TypeError("failure must be exact normalization failure")


def project_execution_reference(raw_bar: TushareCnAShareDailyRawBar) -> TushareCnAShareDailyExecutionReference:
    if type(raw_bar) is not TushareCnAShareDailyRawBar:
        raise TypeError("raw_bar must be exact TushareCnAShareDailyRawBar")
    return TushareCnAShareDailyExecutionReference(
        raw_bar.raw_bar_hash,
        PricePurpose.EXECUTION_REFERENCE,
        raw_bar.instrument_id,
        raw_bar.bucket,
        raw_bar.available_time,
        raw_bar.open_price,
        raw_bar.high_price,
        raw_bar.low_price,
        raw_bar.close_price,
        raw_bar.volume,
        raw_bar.amount,
    )


def project_valuation(raw_bar: TushareCnAShareDailyRawBar) -> TushareCnAShareDailyValuation:
    if type(raw_bar) is not TushareCnAShareDailyRawBar:
        raise TypeError("raw_bar must be exact TushareCnAShareDailyRawBar")
    return TushareCnAShareDailyValuation(
        raw_bar.raw_bar_hash,
        PricePurpose.VALUATION,
        raw_bar.instrument_id,
        raw_bar.bucket.interval_end_exclusive,
        raw_bar.available_time,
        raw_bar.close_price,
    )


def _failed(
    code: TushareCnAShareDailyNormalizationFailureCode,
    *,
    member_key: str | None = None,
    field: str | None = None,
) -> TushareCnAShareDailyNormalizationOutcome:
    return TushareCnAShareDailyNormalizationOutcome(
        failure=TushareCnAShareDailyNormalizationFailure(code, member_key, field)
    )


def _request_valid(request: object) -> bool:
    if type(request) is not TushareCnAShareDailyNormalizationRequest:
        return False
    try:
        TushareCnAShareDailyNormalizationRequest(
            request.schema_version,
            request.snapshot_id,
            request.provenance_hash,
            request.member_key,
            request.member_content_hash,
            request.instrument_id,
            request.provider_trade_date,
            request.bucket,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _reconstruct_snapshot(value: object) -> SourceSnapshot | None:
    if type(value) is not SourceSnapshot:
        return None
    try:
        provenance = SourceSnapshotProvenance(
            value.provenance.vendor_key,
            value.provenance.source_key,
            value.provenance.license_ref,
            value.provenance.retention_policy_ref,
        )
        members = tuple(
            SourceSnapshotMember(
                member.member_key,
                member.content_hash,
                member.byte_count,
                member.mode,
                member.acquired_at_epoch_nanoseconds,
                member.declared_sha256,
            )
            for member in value.members
        )
        rebuilt = SourceSnapshot(
            value.snapshot_id,
            value.archive_bytes,
            value.content_tree_hash,
            members,
            provenance,
            value.provenance_hash,
            value.decision_grade_eligible,
            value.deployment_authorized,
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt if rebuilt == value else None


def _member(snapshot: SourceSnapshot, key: str) -> SourceSnapshotMember | None:
    return next((value for value in snapshot.members if value.member_key == key), None)


def _parse(source: bytes) -> object:
    return json.loads(
        source.decode("utf-8"),
        parse_int=_numeric_token,
        parse_float=_numeric_token,
        parse_constant=_constant,
        object_pairs_hook=_duplicate_free_object,
    )


def _schema_row(value: object) -> tuple[str, str, tuple[_NumericToken, ...]] | None:
    if type(value) is not dict or set(value) != {"request_id", "code", "data", "msg", "detail"}:
        return None
    request_id = value.get("request_id")
    code = value.get("code")
    message = value.get("msg")
    detail = value.get("detail")
    data = value.get("data")
    try:
        _text("request_id", request_id)
    except (TypeError, ValueError):
        return None
    if (
        type(code) is not _NumericToken
        or code.lexeme != "0"
        or message != ""
        or type(detail) is not str
        or type(data) is not dict
        or set(data) != {"fields", "items", "has_more", "count"}
    ):
        return None
    if data.get("has_more") is not False:
        return None
    count = data.get("count")
    if type(count) is not _NumericToken or count.lexeme != "0":
        return None
    fields = data.get("fields")
    items = data.get("items")
    if type(fields) is not list or tuple(fields) != _FIELDS or type(items) is not list or len(items) != 1:
        return None
    row = items[0]
    if type(row) is not list or len(row) != len(_FIELDS):
        return None
    if type(row[0]) is not str or type(row[1]) is not str or any(type(value) is not _NumericToken for value in row[2:]):
        return None
    return row[0], row[1], tuple(row[2:])


def _bucket_valid(bucket: BarBucket) -> bool:
    return (
        bucket.bucket_hash == _BUCKET_HASH
        and bucket.session_id.calendar_id == "CN.XSHE"
        and bucket.session_id.value == "2024-01-02.regular"
        and bucket.trading_date.calendar_id == "CN.XSHE"
        and bucket.trading_date.value.isoformat() == "2024-01-02"
        and bucket.interval_start.epoch_nanoseconds == _INTERVAL_START
        and bucket.interval_end_exclusive.epoch_nanoseconds == _INTERVAL_END
    )


def normalize_tushare_cn_a_share_daily_v1(
    snapshot: SourceSnapshot,
    request: TushareCnAShareDailyNormalizationRequest,
) -> TushareCnAShareDailyNormalizationOutcome:
    if not _request_valid(request):
        return _failed(TushareCnAShareDailyNormalizationFailureCode.INVALID_REQUEST)
    rebuilt_snapshot = _reconstruct_snapshot(snapshot)
    if rebuilt_snapshot is None:
        return _failed(TushareCnAShareDailyNormalizationFailureCode.SNAPSHOT_INVALID)
    try:
        verified = verify_source_snapshot(rebuilt_snapshot)
    except (AttributeError, TypeError, ValueError):
        return _failed(TushareCnAShareDailyNormalizationFailureCode.SNAPSHOT_INVALID)
    if verified.snapshot is None:
        return _failed(TushareCnAShareDailyNormalizationFailureCode.SNAPSHOT_INVALID)
    snapshot = rebuilt_snapshot
    if snapshot.snapshot_id != request.snapshot_id or snapshot.provenance_hash != request.provenance_hash:
        return _failed(TushareCnAShareDailyNormalizationFailureCode.SNAPSHOT_BINDING_MISMATCH)
    member = _member(snapshot, request.member_key)
    if member is None:
        return _failed(
            TushareCnAShareDailyNormalizationFailureCode.SOURCE_MEMBER_MISSING,
            member_key=request.member_key,
        )
    if member.content_hash != request.member_content_hash:
        return _failed(
            TushareCnAShareDailyNormalizationFailureCode.SOURCE_MEMBER_BINDING_MISMATCH,
            member_key=request.member_key,
        )
    try:
        parsed = _parse(snapshot.member_bytes(request.member_key))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError):
        return _failed(
            TushareCnAShareDailyNormalizationFailureCode.SOURCE_JSON_INVALID,
            member_key=request.member_key,
        )
    row = _schema_row(parsed)
    if row is None:
        return _failed(
            TushareCnAShareDailyNormalizationFailureCode.SOURCE_SCHEMA_MISMATCH,
            member_key=request.member_key,
        )
    ts_code, trade_date, numeric = row
    if ts_code != _TS_CODE or trade_date != request.provider_trade_date or request.instrument_id != _INSTRUMENT:
        return _failed(TushareCnAShareDailyNormalizationFailureCode.SOURCE_RECORD_MISMATCH)
    lexemes = tuple(value.lexeme for value in numeric)
    source_record_hash = _source_record_hash(ts_code, trade_date, lexemes)
    try:
        open_units, high_units, low_units, close_units, pre_close_units, change_units = (
            _units(value, 2) for value in numeric[:6]
        )
        pct_units = _units(numeric[6], 4)
        volume_units = _scaled_multiplier(numeric[7], 2, 100)
        amount_units = _scaled_multiplier(numeric[8], 3, 1000)
    except (TypeError, ValueError):
        return _failed(TushareCnAShareDailyNormalizationFailureCode.DECIMAL_MAPPING_INVALID)
    if not (
        0 < low_units <= open_units <= high_units
        and 0 < low_units <= close_units <= high_units
        and pre_close_units > 0
        and close_units - pre_close_units == change_units
        and volume_units >= 0
        and amount_units >= 0
    ):
        return _failed(TushareCnAShareDailyNormalizationFailureCode.BAR_INVARIANT_VIOLATION)
    if not _bucket_valid(request.bucket):
        return _failed(TushareCnAShareDailyNormalizationFailureCode.BUCKET_BINDING_MISMATCH)
    available_time = UtcInstant(member.acquired_at_epoch_nanoseconds)
    if available_time < request.bucket.interval_end_exclusive:
        return _failed(TushareCnAShareDailyNormalizationFailureCode.AVAILABILITY_INVALID)
    price_scale = Scale(2)
    raw_bar = TushareCnAShareDailyRawBar(
        instrument_id=request.instrument_id,
        provider_ts_code=ts_code,
        provider_trade_date=trade_date,
        bucket=request.bucket,
        available_time=available_time,
        open_lexeme=lexemes[0],
        high_lexeme=lexemes[1],
        low_lexeme=lexemes[2],
        close_lexeme=lexemes[3],
        pre_close_lexeme=lexemes[4],
        change_lexeme=lexemes[5],
        pct_change_lexeme=lexemes[6],
        volume_lots_lexeme=lexemes[7],
        amount_thousand_cny_lexeme=lexemes[8],
        open_price=Price(open_units, price_scale, str(request.instrument_id), _CURRENCY),
        high_price=Price(high_units, price_scale, str(request.instrument_id), _CURRENCY),
        low_price=Price(low_units, price_scale, str(request.instrument_id), _CURRENCY),
        close_price=Price(close_units, price_scale, str(request.instrument_id), _CURRENCY),
        pre_close_price=Price(pre_close_units, price_scale, str(request.instrument_id), _CURRENCY),
        change_units=change_units,
        change_scale=price_scale,
        pct_change=Rate(pct_units, Scale(4), "percent"),
        volume=Quantity(volume_units, Scale(0), str(request.instrument_id)),
        amount=Money(amount_units, Scale(0), _CURRENCY),
        source_record_hash=source_record_hash,
        limitations=_LIMITATIONS,
        decision_grade_eligible=False,
        deployment_authorized=False,
    )
    trace = TushareCnAShareDailySourceTrace(
        snapshot.snapshot_id,
        snapshot.provenance_hash,
        snapshot.provenance.source_key,
        member.member_key,
        member.content_hash,
        0,
        source_record_hash,
        raw_bar.raw_bar_hash,
        member.content_hash,
        None,
        False,
    )
    execution = project_execution_reference(raw_bar)
    valuation = project_valuation(raw_bar)
    return TushareCnAShareDailyNormalizationOutcome(
        result=TushareCnAShareDailyNormalizationResult(
            request,
            snapshot,
            raw_bar,
            trace,
            execution,
            valuation,
        )
    )
