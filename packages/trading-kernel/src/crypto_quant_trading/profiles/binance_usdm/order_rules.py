"""Pure offline Binance USD-M historical order-rule normalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from crypto_quant_domain import (
    CurrencyId,
    ExecutionStyle,
    InstrumentId,
    Money,
    OrderSide,
    PositionEffect,
    Price,
    RoundingPolicy,
    Scale,
    SessionId,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)

from ...capabilities import (
    OrderCapabilitySet,
    OrderStyleCapability,
    PriceConstraintShape,
)
from ...market_rules import (
    MarketSessionState,
    OrderRuleInterval,
    OrderRuleSnapshot,
    OrderRuleTimeline,
    SupplementalOrderRuleDecision,
)
from ...ports import ProfileComponentRef, ProfilePortOutcome, ProfilePortType
from ...sizing import QuantityLattice
from .instrument_metadata import BinanceUsdmInstrumentMetadataResolution


_SCHEMA_VERSION = 1
_COMPONENT_KEY = "crypto.binance_usdm.order-rules.v1"
_ALGORITHM_KEY = "binance-usdm-order-rules-offline-v1"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?\Z")
_REQUIRED_FILTERS = frozenset(
    {"PRICE_FILTER", "LOT_SIZE", "MARKET_LOT_SIZE", "MIN_NOTIONAL"}
)
_SUPPORTED_ORDER_TYPES = frozenset(
    {
        "LIMIT",
        "MARKET",
        "STOP",
        "STOP_MARKET",
        "TAKE_PROFIT",
        "TAKE_PROFIT_MARKET",
        "TRAILING_STOP_MARKET",
    }
)
_SUPPORTED_TIFS = frozenset({"GTC", "IOC", "FOK", "GTX"})
_DECIMAL_FIELDS = (
    "min_price",
    "max_price",
    "tick_size",
    "limit_min_qty",
    "limit_max_qty",
    "limit_step_size",
    "market_min_qty",
    "market_max_qty",
    "market_step_size",
    "min_notional",
)


class BinanceUsdmOrderAdmissionMode(str, Enum):
    NORMAL = "NORMAL"
    REDUCE_ONLY = "REDUCE_ONLY"
    CLOSED = "CLOSED"


class BinanceUsdmDeferredRuleKey(str, Enum):
    PERCENT_PRICE = "PERCENT_PRICE"
    MAX_NUM_ORDERS = "MAX_NUM_ORDERS"
    MAX_NUM_ALGO_ORDERS = "MAX_NUM_ALGO_ORDERS"
    MARKET_TAKE_BOUND = "MARKET_TAKE_BOUND"
    TRIGGER_PROTECT = "TRIGGER_PROTECT"
    ADVANCED_ORDER_CAPABILITIES = "ADVANCED_ORDER_CAPABILITIES"


class BinanceUsdmOrderRuleFailureCode(str, Enum):
    MISSING_RULE_BANDS = "missing_rule_bands"
    INSTRUMENT_METADATA_MISMATCH = "instrument_metadata_mismatch"
    RULE_NOT_AVAILABLE = "rule_not_available"
    MISSING_RULE_INTERVAL = "missing_rule_interval"
    OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"
    MISSING_REQUIRED_FILTER = "missing_required_filter"
    UNSUPPORTED_FILTER = "unsupported_filter"
    INVALID_DECIMAL_FIELD = "invalid_decimal_field"
    INVALID_FILTER_GEOMETRY = "invalid_filter_geometry"
    UNSUPPORTED_ORDER_CAPABILITY = "unsupported_order_capability"
    ADMISSION_STATUS_CONFLICT = "admission_status_conflict"
    METADATA_CONFLICT = "metadata_conflict"


_FAILURE_MESSAGES = {
    code: code.value.replace("_", " ") for code in BinanceUsdmOrderRuleFailureCode
}


def _text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be non-empty canonical text")
    return value


def _instant(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be exact UtcInstant")
    return value


def _ordered_text(name: str, values: object) -> tuple[str, ...]:
    if type(values) is not tuple or not all(type(value) is str for value in values):
        raise TypeError(f"{name} must be a tuple of exact strings")
    for value in values:
        _text(name, value)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} cannot contain duplicates")
    return tuple(sorted(values))


@dataclass(frozen=True, slots=True)
class BinanceUsdmOrderRuleSourceRef:
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("source_key", self.source_key)
        if type(self.source_hash) is not str or _SHA256.fullmatch(self.source_hash) is None:
            raise ValueError("source_hash must be canonical sha256")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_order_rule_source_ref",
            "schema_version": _SCHEMA_VERSION,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmOrderRuleBand:
    band_id: str
    instrument_id: InstrumentId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    available_at: UtcInstant
    min_price: str
    max_price: str
    tick_size: str
    limit_min_qty: str
    limit_max_qty: str
    limit_step_size: str
    market_min_qty: str
    market_max_qty: str
    market_step_size: str
    min_notional: str
    filter_keys: tuple[str, ...]
    order_types: tuple[str, ...]
    time_in_forces: tuple[str, ...]
    admission_mode: BinanceUsdmOrderAdmissionMode
    supports_reduce_only: bool
    deferred_rule_keys: tuple[str, ...]
    source_ref: BinanceUsdmOrderRuleSourceRef

    def __post_init__(self) -> None:
        _text("band_id", self.band_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        _instant("effective_from", self.effective_from)
        _instant("effective_to_exclusive", self.effective_to_exclusive)
        _instant("available_at", self.available_at)
        for name in _DECIMAL_FIELDS:
            _text(name, getattr(self, name))
        object.__setattr__(self, "filter_keys", _ordered_text("filter_keys", self.filter_keys))
        object.__setattr__(self, "order_types", _ordered_text("order_types", self.order_types))
        object.__setattr__(
            self, "time_in_forces", _ordered_text("time_in_forces", self.time_in_forces)
        )
        object.__setattr__(
            self,
            "deferred_rule_keys",
            _ordered_text("deferred_rule_keys", self.deferred_rule_keys),
        )
        if type(self.admission_mode) is not BinanceUsdmOrderAdmissionMode:
            raise TypeError("admission_mode must be exact BinanceUsdmOrderAdmissionMode")
        if type(self.supports_reduce_only) is not bool:
            raise TypeError("supports_reduce_only must be bool")
        if type(self.source_ref) is not BinanceUsdmOrderRuleSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmOrderRuleSourceRef")

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        _instant("instant", instant)
        return self.effective_from <= instant < self.effective_to_exclusive

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_order_rule_band",
            "schema_version": _SCHEMA_VERSION,
            "band_id": self.band_id,
            "instrument_id": self.instrument_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "available_at": self.available_at,
            **{name: getattr(self, name) for name in _DECIMAL_FIELDS},
            "filter_keys": list(self.filter_keys),
            "order_types": list(self.order_types),
            "time_in_forces": list(self.time_in_forces),
            "admission_mode": self.admission_mode.value,
            "supports_reduce_only": self.supports_reduce_only,
            "deferred_rule_keys": list(self.deferred_rule_keys),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmOrderRuleBook:
    rule_book_key: str
    rule_book_version: int
    instrument_id: InstrumentId
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    bands: tuple[BinanceUsdmOrderRuleBand, ...]

    def __post_init__(self) -> None:
        _text("rule_book_key", self.rule_book_key)
        if type(self.rule_book_version) is not int or self.rule_book_version <= 0:
            raise ValueError("rule_book_version must be a positive integer")
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        _instant("coverage_from", self.coverage_from)
        _instant("coverage_to_exclusive", self.coverage_to_exclusive)
        if type(self.bands) is not tuple or not all(
            type(value) is BinanceUsdmOrderRuleBand for value in self.bands
        ):
            raise TypeError("bands must be a tuple of exact BinanceUsdmOrderRuleBand")
        object.__setattr__(
            self,
            "bands",
            tuple(
                sorted(
                    self.bands,
                    key=lambda value: (
                        value.effective_from,
                        value.effective_to_exclusive,
                        value.band_id,
                    ),
                )
            ),
        )

    @property
    def rule_book_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_order_rule_book",
            "schema_version": _SCHEMA_VERSION,
            "rule_book_key": self.rule_book_key,
            "rule_book_version": self.rule_book_version,
            "instrument_id": self.instrument_id,
            "coverage_from": self.coverage_from,
            "coverage_to_exclusive": self.coverage_to_exclusive,
            "bands": list(self.bands),
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmOrderRuleQuery:
    instrument_metadata: BinanceUsdmInstrumentMetadataResolution
    session_id: SessionId
    evaluated_at: UtcInstant
    captured_at: UtcInstant
    rule_book: BinanceUsdmOrderRuleBook

    def __post_init__(self) -> None:
        if type(self.instrument_metadata) is not BinanceUsdmInstrumentMetadataResolution:
            raise TypeError("instrument_metadata must be exact G10A resolution")
        if type(self.session_id) is not SessionId:
            raise TypeError("session_id must be exact SessionId")
        _instant("evaluated_at", self.evaluated_at)
        _instant("captured_at", self.captured_at)
        if type(self.rule_book) is not BinanceUsdmOrderRuleBook:
            raise TypeError("rule_book must be exact BinanceUsdmOrderRuleBook")

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_order_rule_query",
            "schema_version": _SCHEMA_VERSION,
            "instrument_metadata": self.instrument_metadata,
            "session_id": self.session_id,
            "evaluated_at": self.evaluated_at,
            "captured_at": self.captured_at,
            "rule_book": self.rule_book,
        }


@dataclass(frozen=True, slots=True)
class _DecimalValue:
    units: int
    scale: int


def _decimal(value: str) -> _DecimalValue:
    match = _DECIMAL.fullmatch(value)
    if match is None:
        raise ValueError("invalid decimal")
    integer, _, fraction = value.partition(".")
    fraction = fraction.rstrip("0")
    scale = len(fraction)
    try:
        units = int(integer + fraction) if fraction else int(integer)
    except ValueError as error:  # pragma: no cover - guarded by the grammar
        raise ValueError("invalid decimal") from error
    return _DecimalValue(units, scale)


def _units_at(value: _DecimalValue, scale: int) -> int:
    if value.scale > scale:
        raise ValueError("inexact decimal conversion")
    return value.units * 10 ** (scale - value.scale)


@dataclass(frozen=True, slots=True)
class _BandValues:
    snapshot: OrderRuleSnapshot
    limit_lattice: QuantityLattice
    market_lattice: QuantityLattice
    price_scale: Scale
    quantity_scale: Scale
    capabilities: OrderCapabilitySet
    deferred: tuple[BinanceUsdmDeferredRuleKey, ...]


@dataclass(frozen=True, slots=True)
class _ResolutionValues:
    component_ref: ProfileComponentRef
    visible_bands: tuple[BinanceUsdmOrderRuleBand, ...]
    active_band: BinanceUsdmOrderRuleBand
    rule_timeline: OrderRuleTimeline
    active_snapshot: OrderRuleSnapshot
    limit_quantity_lattice: QuantityLattice
    market_quantity_lattice: QuantityLattice
    price_scale: Scale
    quantity_scale: Scale
    order_capabilities: OrderCapabilitySet
    active_deferred_rule_keys: tuple[BinanceUsdmDeferredRuleKey, ...]
    deferred_rule_keys: tuple[BinanceUsdmDeferredRuleKey, ...]
    decision_grade_eligible: bool


@dataclass(frozen=True, slots=True)
class BinanceUsdmOrderRuleResolution:
    query: BinanceUsdmOrderRuleQuery
    component_ref: ProfileComponentRef
    visible_bands: tuple[BinanceUsdmOrderRuleBand, ...]
    active_band: BinanceUsdmOrderRuleBand
    rule_timeline: OrderRuleTimeline
    active_snapshot: OrderRuleSnapshot
    limit_quantity_lattice: QuantityLattice
    market_quantity_lattice: QuantityLattice
    price_scale: Scale
    quantity_scale: Scale
    order_capabilities: OrderCapabilitySet
    active_deferred_rule_keys: tuple[BinanceUsdmDeferredRuleKey, ...]
    deferred_rule_keys: tuple[BinanceUsdmDeferredRuleKey, ...]
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmOrderRuleQuery:
            raise TypeError("query must be exact BinanceUsdmOrderRuleQuery")
        if _failure_details(self.query) is not None:
            raise ValueError("resolution query has a business failure")
        expected = _resolution_values(self.query)
        fields = expected.__dataclass_fields__
        if tuple(getattr(self, name) for name in fields) != tuple(
            getattr(expected, name) for name in fields
        ):
            raise ValueError("resolution fields must match embedded query")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_order_rule_resolution",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "component_ref": self.component_ref,
            "visible_bands": list(self.visible_bands),
            "active_band": self.active_band,
            "rule_timeline": self.rule_timeline,
            "active_snapshot": self.active_snapshot,
            "limit_quantity_lattice": self.limit_quantity_lattice,
            "market_quantity_lattice": self.market_quantity_lattice,
            "price_scale": self.price_scale.places,
            "quantity_scale": self.quantity_scale.places,
            "order_capabilities": self.order_capabilities,
            "active_deferred_rule_keys": [
                value.value for value in self.active_deferred_rule_keys
            ],
            "deferred_rule_keys": [value.value for value in self.deferred_rule_keys],
            "decision_grade_eligible": self.decision_grade_eligible,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmOrderRuleFailure:
    query: BinanceUsdmOrderRuleQuery
    code: BinanceUsdmOrderRuleFailureCode
    message: str
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmOrderRuleQuery:
            raise TypeError("query must be exact BinanceUsdmOrderRuleQuery")
        if type(self.code) is not BinanceUsdmOrderRuleFailureCode:
            raise TypeError("code must be exact BinanceUsdmOrderRuleFailureCode")
        _text("message", self.message)
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str and bool(value) for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be a tuple of non-empty strings")
        if _failure_details(self.query) != (self.code, self.message, self.subject_ids):
            raise ValueError("failure fields must match embedded query")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_order_rule_failure",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "code": self.code.value,
            "message": self.message,
            "subject_ids": list(self.subject_ids),
        }


BinanceUsdmOrderRuleOutcome = ProfilePortOutcome[
    BinanceUsdmOrderRuleResolution,
    BinanceUsdmOrderRuleFailure,
]


def _details(
    code: BinanceUsdmOrderRuleFailureCode, *subject_ids: str
) -> tuple[BinanceUsdmOrderRuleFailureCode, str, tuple[str, ...]]:
    return code, _FAILURE_MESSAGES[code], tuple(subject_ids)


def _visible(query: BinanceUsdmOrderRuleQuery) -> tuple[BinanceUsdmOrderRuleBand, ...]:
    return tuple(
        value
        for value in query.rule_book.bands
        if value.available_at <= query.captured_at
    )


def _parsed_band(band: BinanceUsdmOrderRuleBand) -> dict[str, _DecimalValue]:
    return {name: _decimal(getattr(band, name)) for name in _DECIMAL_FIELDS}


def _inexact_decimal(band: BinanceUsdmOrderRuleBand) -> bool:
    values = _parsed_band(band)
    price_scale = max(
        values[name].scale for name in ("min_price", "max_price", "tick_size")
    )
    quantity_scale = max(
        values[name].scale
        for name in (
            "limit_min_qty",
            "limit_max_qty",
            "limit_step_size",
            "market_min_qty",
            "market_max_qty",
            "market_step_size",
        )
    )
    return values["min_notional"].scale > price_scale + quantity_scale


def _geometry_error(band: BinanceUsdmOrderRuleBand) -> bool:
    values = _parsed_band(band)
    price_scale = max(
        values[name].scale for name in ("min_price", "max_price", "tick_size")
    )
    quantity_scale = max(
        values[name].scale
        for name in (
            "limit_min_qty",
            "limit_max_qty",
            "limit_step_size",
            "market_min_qty",
            "market_max_qty",
            "market_step_size",
        )
    )
    if price_scale + quantity_scale > 18:
        return True
    try:
        min_notional = _units_at(values["min_notional"], price_scale + quantity_scale)
    except ValueError:
        return True
    tick = _units_at(values["tick_size"], price_scale)
    min_price = _units_at(values["min_price"], price_scale)
    max_price = _units_at(values["max_price"], price_scale)
    if (
        tick <= 0
        or (min_price and min_price % tick)
        or (max_price and max_price % tick)
        or (min_price and max_price and min_price > max_price)
        or min_notional <= 0
    ):
        return True
    for prefix in ("limit", "market"):
        minimum = _units_at(values[f"{prefix}_min_qty"], quantity_scale)
        maximum = _units_at(values[f"{prefix}_max_qty"], quantity_scale)
        step = _units_at(values[f"{prefix}_step_size"], quantity_scale)
        if (
            minimum <= 0
            or maximum <= 0
            or step <= 0
            or minimum > maximum
            or minimum % step
            or maximum % step
        ):
            return True
    return False


def _capability_error(band: BinanceUsdmOrderRuleBand) -> bool:
    if (
        band.admission_mode is BinanceUsdmOrderAdmissionMode.REDUCE_ONLY
        and not band.supports_reduce_only
    ):
        return True
    if not {"LIMIT", "MARKET"}.issubset(band.order_types):
        return True
    if any(value not in _SUPPORTED_ORDER_TYPES for value in band.order_types):
        return True
    if any(value not in _SUPPORTED_TIFS for value in band.time_in_forces):
        return True
    if not set(band.time_in_forces).intersection(_SUPPORTED_TIFS):
        return True
    advanced = set(band.order_types) - {"LIMIT", "MARKET"}
    return bool(advanced) and (
        BinanceUsdmDeferredRuleKey.ADVANCED_ORDER_CAPABILITIES.value
        not in band.deferred_rule_keys
    )


def _failure_details(
    query: BinanceUsdmOrderRuleQuery,
) -> tuple[BinanceUsdmOrderRuleFailureCode, str, tuple[str, ...]] | None:
    bands = query.rule_book.bands
    if not bands:
        return _details(
            BinanceUsdmOrderRuleFailureCode.MISSING_RULE_BANDS,
            query.rule_book.rule_book_key,
        )
    metadata = query.instrument_metadata
    if (
        metadata.query.effective_at != query.evaluated_at
        or metadata.query.captured_at > query.captured_at
        or query.rule_book.instrument_id != metadata.instrument.instrument_id
    ):
        return _details(
            BinanceUsdmOrderRuleFailureCode.INSTRUMENT_METADATA_MISMATCH,
            query.rule_book.rule_book_key,
        )
    visible = _visible(query)
    if not visible:
        return _details(
            BinanceUsdmOrderRuleFailureCode.RULE_NOT_AVAILABLE,
            query.rule_book.rule_book_key,
        )
    book = query.rule_book
    if (
        book.coverage_from >= book.coverage_to_exclusive
        or query.evaluated_at < book.coverage_from
        or query.evaluated_at >= book.coverage_to_exclusive
        or visible[0].effective_from != book.coverage_from
        or visible[-1].effective_to_exclusive != book.coverage_to_exclusive
        or any(
            current.effective_from > previous.effective_to_exclusive
            for previous, current in zip(visible, visible[1:])
        )
    ):
        return _details(
            BinanceUsdmOrderRuleFailureCode.MISSING_RULE_INTERVAL,
            *(value.band_id for value in visible),
        )
    band_ids = tuple(value.band_id for value in visible)
    if len(set(band_ids)) != len(band_ids) or any(
        current.effective_from < previous.effective_to_exclusive
        for previous, current in zip(visible, visible[1:])
    ):
        return _details(
            BinanceUsdmOrderRuleFailureCode.OVERLAPPING_RULE_INTERVALS,
            *band_ids,
        )
    if any(not _REQUIRED_FILTERS.issubset(value.filter_keys) for value in visible):
        return _details(
            BinanceUsdmOrderRuleFailureCode.MISSING_REQUIRED_FILTER,
            *(value.band_id for value in visible),
        )
    deferred_values = {value.value for value in BinanceUsdmDeferredRuleKey}
    if any(
        set(value.filter_keys) != _REQUIRED_FILTERS
        or any(key not in deferred_values for key in value.deferred_rule_keys)
        for value in visible
    ):
        return _details(
            BinanceUsdmOrderRuleFailureCode.UNSUPPORTED_FILTER,
            *(value.band_id for value in visible),
        )
    try:
        for value in visible:
            _parsed_band(value)
    except ValueError:
        return _details(
            BinanceUsdmOrderRuleFailureCode.INVALID_DECIMAL_FIELD,
            *(value.band_id for value in visible),
        )
    if any(_inexact_decimal(value) for value in visible):
        return _details(
            BinanceUsdmOrderRuleFailureCode.INVALID_DECIMAL_FIELD,
            *(value.band_id for value in visible),
        )
    if any(_geometry_error(value) for value in visible):
        return _details(
            BinanceUsdmOrderRuleFailureCode.INVALID_FILTER_GEOMETRY,
            *(value.band_id for value in visible),
        )
    if any(_capability_error(value) for value in visible):
        return _details(
            BinanceUsdmOrderRuleFailureCode.UNSUPPORTED_ORDER_CAPABILITY,
            *(value.band_id for value in visible),
        )
    active = tuple(value for value in visible if value.contains(query.evaluated_at))
    if len(active) != 1:
        return _details(
            BinanceUsdmOrderRuleFailureCode.MISSING_RULE_INTERVAL,
            *(value.band_id for value in visible),
        )
    if not metadata.tradable and active[0].admission_mode is not BinanceUsdmOrderAdmissionMode.CLOSED:
        return _details(
            BinanceUsdmOrderRuleFailureCode.ADMISSION_STATUS_CONFLICT,
            active[0].band_id,
        )
    source_rows: dict[str, str] = {}
    for value in visible:
        if value.instrument_id != book.instrument_id:
            return _details(
                BinanceUsdmOrderRuleFailureCode.METADATA_CONFLICT,
                value.band_id,
            )
        prior = source_rows.setdefault(
            value.source_ref.source_key, value.source_ref.source_hash
        )
        if prior != value.source_ref.source_hash:
            return _details(
                BinanceUsdmOrderRuleFailureCode.METADATA_CONFLICT,
                value.source_ref.source_key,
            )
    return None


def _admission_values(
    mode: BinanceUsdmOrderAdmissionMode,
) -> tuple[
    MarketSessionState,
    tuple[OrderSide, ...],
    tuple[PositionEffect, ...],
    bool,
]:
    if mode is BinanceUsdmOrderAdmissionMode.NORMAL:
        return (
            MarketSessionState.OPEN,
            (OrderSide.BUY, OrderSide.SELL),
            (PositionEffect.AUTO, PositionEffect.OPEN, PositionEffect.CLOSE),
            False,
        )
    if mode is BinanceUsdmOrderAdmissionMode.REDUCE_ONLY:
        return (
            MarketSessionState.OPEN,
            (OrderSide.BUY, OrderSide.SELL),
            (PositionEffect.CLOSE,),
            True,
        )
    return MarketSessionState.SUSPENDED, (), (), False


def _band_values(
    band: BinanceUsdmOrderRuleBand,
    *,
    component_ref: ProfileComponentRef,
    session_id: SessionId,
    settlement_currency: CurrencyId,
) -> _BandValues:
    values = _parsed_band(band)
    price_places = max(
        values[name].scale for name in ("min_price", "max_price", "tick_size")
    )
    quantity_places = max(
        values[name].scale
        for name in (
            "limit_min_qty",
            "limit_max_qty",
            "limit_step_size",
            "market_min_qty",
            "market_max_qty",
            "market_step_size",
        )
    )
    price_scale = Scale(price_places)
    quantity_scale = Scale(quantity_places)
    min_notional = Money(
        _units_at(values["min_notional"], price_places + quantity_places),
        Scale(price_places + quantity_places),
        settlement_currency.value,
    )

    def lattice(prefix: str) -> QuantityLattice:
        step = _units_at(values[f"{prefix}_step_size"], quantity_places)
        return QuantityLattice.create(
            instrument_id=band.instrument_id,
            lattice_key=f"{_COMPONENT_KEY}:{band.band_id}:{prefix}",
            lattice_version=1,
            atomic_scale=quantity_scale,
            step_units=step,
            buy_lot_units=step,
            sell_lot_units=step,
            min_quantity_units=_units_at(
                values[f"{prefix}_min_qty"], quantity_places
            ),
            min_notional=min_notional,
            odd_lot_close_permitted=False,
        )

    limit_lattice = lattice("limit")
    market_lattice = lattice("market")
    session_state, sides, effects, reduce_only = _admission_values(
        band.admission_mode
    )
    lower_units = _units_at(values["min_price"], price_places)
    upper_units = _units_at(values["max_price"], price_places)
    snapshot = OrderRuleSnapshot.create(
        component_ref=component_ref,
        instrument_id=band.instrument_id,
        session_id=session_id,
        session_state=session_state,
        quantity_lattice=limit_lattice,
        market_quantity_lattice=market_lattice,
        price_scale=price_scale,
        price_tick_units=_units_at(values["tick_size"], price_places),
        lower_price_limit=(
            None
            if lower_units == 0
            else Price(
                lower_units,
                price_scale,
                str(band.instrument_id),
                settlement_currency.value,
            )
        ),
        upper_price_limit=(
            None
            if upper_units == 0
            else Price(
                upper_units,
                price_scale,
                str(band.instrument_id),
                settlement_currency.value,
            )
        ),
        permitted_sides=sides,
        permitted_position_effects=effects,
        reduce_only_required=reduce_only,
        notional_rounding=RoundingPolicy.TOWARD_ZERO,
        supplemental_decisions=(
            SupplementalOrderRuleDecision(
                rule_key="binance_usdm_rule_band",
                approved=True,
                reason_code=band.band_hash,
            ),
        ),
        max_limit_order_quantity_units=_units_at(
            values["limit_max_qty"], quantity_places
        ),
        max_market_order_quantity_units=_units_at(
            values["market_max_qty"], quantity_places
        ),
    )
    limit_tifs = tuple(
        TimeInForce[value]
        for value in ("FOK", "GTC", "GTX", "IOC")
        if value in band.time_in_forces
    )
    capabilities = OrderCapabilitySet.create(
        capability_set_key=f"{_COMPONENT_KEY}:{band.band_id}",
        capability_set_version=1,
        style_capabilities=(
            OrderStyleCapability(
                execution_style=ExecutionStyle.LIMIT,
                price_constraint_shapes=(PriceConstraintShape.LIMIT,),
                time_in_forces=limit_tifs,
            ),
            OrderStyleCapability(
                execution_style=ExecutionStyle.MARKET,
                price_constraint_shapes=(PriceConstraintShape.NONE,),
                time_in_forces=(TimeInForce.IOC,),
            ),
        ),
        supports_reduce_only=band.supports_reduce_only,
        supported_position_effects=effects,
        declared_capability_keys=(
            "binance_usdm_limit",
            "binance_usdm_market",
            "binance_usdm_reduce_only",
        ),
    )
    deferred = tuple(BinanceUsdmDeferredRuleKey(value) for value in band.deferred_rule_keys)
    return _BandValues(
        snapshot=snapshot,
        limit_lattice=limit_lattice,
        market_lattice=market_lattice,
        price_scale=price_scale,
        quantity_scale=quantity_scale,
        capabilities=capabilities,
        deferred=deferred,
    )


def _component_ref() -> ProfileComponentRef:
    digest = canonical_sha256(
        {
            "type": "binance_usdm_order_rule_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "algorithm_key": _ALGORITHM_KEY,
            "required_filters": sorted(_REQUIRED_FILTERS),
            "deferred_rule_keys": [
                value.value for value in BinanceUsdmDeferredRuleKey
            ],
            "admission_modes": [value.value for value in BinanceUsdmOrderAdmissionMode],
        }
    )
    return ProfileComponentRef(
        port_type=ProfilePortType.ORDER_RULE_MODEL,
        component_key=_COMPONENT_KEY,
        component_version=1,
        component_digest=digest,
    )


def _resolution_values(query: BinanceUsdmOrderRuleQuery) -> _ResolutionValues:
    component_ref = _component_ref()
    visible = _visible(query)
    settlement = query.instrument_metadata.instrument.settlement_currency
    normalized = {
        value.band_id: _band_values(
            value,
            component_ref=component_ref,
            session_id=query.session_id,
            settlement_currency=settlement,
        )
        for value in visible
    }
    intervals = tuple(
        OrderRuleInterval.create(
            effective_from=value.effective_from,
            effective_to_exclusive=value.effective_to_exclusive,
            snapshot=normalized[value.band_id].snapshot,
        )
        for value in visible
    )
    timeline = OrderRuleTimeline.create(
        timeline_key=query.rule_book.rule_book_key,
        timeline_version=query.rule_book.rule_book_version,
        instrument_id=query.rule_book.instrument_id,
        intervals=intervals,
    )
    active = next(value for value in visible if value.contains(query.evaluated_at))
    active_values = normalized[active.band_id]
    active_deferred = active_values.deferred
    all_deferred = tuple(
        sorted(
            {item for value in normalized.values() for item in value.deferred},
            key=lambda item: item.value,
        )
    )
    return _ResolutionValues(
        component_ref=component_ref,
        visible_bands=visible,
        active_band=active,
        rule_timeline=timeline,
        active_snapshot=active_values.snapshot,
        limit_quantity_lattice=active_values.limit_lattice,
        market_quantity_lattice=active_values.market_lattice,
        price_scale=active_values.price_scale,
        quantity_scale=active_values.quantity_scale,
        order_capabilities=active_values.capabilities,
        active_deferred_rule_keys=active_deferred,
        deferred_rule_keys=all_deferred,
        decision_grade_eligible=not all_deferred,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmOrderRuleModel:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref()

    def resolve_order_rules(
        self, query: BinanceUsdmOrderRuleQuery, /
    ) -> BinanceUsdmOrderRuleOutcome:
        if type(query) is not BinanceUsdmOrderRuleQuery:
            raise TypeError("query must be exact BinanceUsdmOrderRuleQuery")
        failure = _failure_details(query)
        if failure is not None:
            code, message, subject_ids = failure
            return ProfilePortOutcome.for_failure(
                self.component_ref,
                query,
                BinanceUsdmOrderRuleFailure(
                    query=query,
                    code=code,
                    message=message,
                    subject_ids=subject_ids,
                ),
            )
        values = _resolution_values(query)
        return ProfilePortOutcome.for_result(
            self.component_ref,
            query,
            BinanceUsdmOrderRuleResolution(
                query=query,
                **{name: getattr(values, name) for name in values.__dataclass_fields__},
            ),
        )
