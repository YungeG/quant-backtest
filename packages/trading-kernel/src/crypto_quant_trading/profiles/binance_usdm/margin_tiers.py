"""Pure offline Binance USD-M historical margin-tier normalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    Rate,
    Scale,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
)

from ...margin import (
    LinearMarginRuleBook,
    LinearMarginRuleInterval,
    LinearMarginTier,
    LinearMarginTierBoundaryConvention,
)
from ...ports import ProfileComponentRef, ProfilePortOutcome, ProfilePortType
from .instrument_metadata import BinanceUsdmInstrumentMetadataResolution


_SCHEMA_VERSION = 1
_COMPONENT_KEY = "crypto.binance_usdm.margin-tiers.v1"
_ALGORITHM_KEY = "binance-usdm-margin-tiers-offline-v1"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?\Z")
_CONTRACT_INFO_BRACKET_UPDATE = "CONTRACT_INFO_BRACKET_UPDATE"
_USER_DATA_LEVERAGE_BRACKET = "USER_DATA_LEVERAGE_BRACKET"
_MONEY_FIELDS = (
    "notional_floor",
    "notional_cap",
    "maintenance_margin_deduction",
)
_DECIMAL_FIELDS = (
    "bracket_id",
    *_MONEY_FIELDS,
    "maintenance_margin_rate",
    "minimum_leverage_range",
    "maximum_leverage",
)
_LEVERAGE_BASIS = "notional_per_initial_margin"
_MAINTENANCE_BASIS = "maintenance_margin_fraction_of_notional"
_BOUNDARY = LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE


class BinanceUsdmMarginTierScope(str, Enum):
    DEFAULT_SYMBOL = "DEFAULT_SYMBOL"
    ACCOUNT_ADJUSTED = "ACCOUNT_ADJUSTED"


class BinanceUsdmMarginTierFailureCode(str, Enum):
    MISSING_TIER_BANDS = "missing_tier_bands"
    INSTRUMENT_METADATA_MISMATCH = "instrument_metadata_mismatch"
    TIER_NOT_AVAILABLE = "tier_not_available"
    MISSING_TIER_INTERVAL = "missing_tier_interval"
    OVERLAPPING_TIER_INTERVALS = "overlapping_tier_intervals"
    ACCOUNT_ADJUSTED_TIER_UNSUPPORTED = "account_adjusted_tier_unsupported"
    INVALID_DECIMAL_FIELD = "invalid_decimal_field"
    INVALID_BRACKET_GEOMETRY = "invalid_bracket_geometry"
    UNSUPPORTED_MARGIN_SEMANTICS = "unsupported_margin_semantics"
    METADATA_CONFLICT = "metadata_conflict"


_FAILURE_MESSAGES = {
    code: code.value.replace("_", " ") for code in BinanceUsdmMarginTierFailureCode
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


def _raw_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact string")
    return value


def _utc(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be exact UtcInstant")
    return value


def _simulation(name: str, value: object) -> SimulationInstant:
    if type(value) is not SimulationInstant or type(value.instant) is not UtcInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")
    return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierSourceRef:
    source_key: str
    source_hash: str
    source_kind: str

    def __post_init__(self) -> None:
        _text("source_key", self.source_key)
        if type(self.source_hash) is not str or _SHA256.fullmatch(self.source_hash) is None:
            raise ValueError("source_hash must be canonical sha256")
        _text("source_kind", self.source_kind)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_margin_tier_source_ref",
            "schema_version": _SCHEMA_VERSION,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "source_kind": self.source_kind,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierBracket:
    bracket_id: str
    notional_floor: str
    notional_cap: str
    maintenance_margin_rate: str
    maintenance_margin_deduction: str
    minimum_leverage_range: str
    maximum_leverage: str

    def __post_init__(self) -> None:
        for name in _DECIMAL_FIELDS:
            _raw_string(name, getattr(self, name))

    @property
    def bracket_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_margin_tier_bracket",
            "schema_version": _SCHEMA_VERSION,
            **{name: getattr(self, name) for name in _DECIMAL_FIELDS},
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierBand:
    band_id: str
    instrument_id: InstrumentId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    available_at: SimulationInstant
    scope: BinanceUsdmMarginTierScope
    notional_coef: str | None
    brackets: tuple[BinanceUsdmMarginTierBracket, ...]
    source_ref: BinanceUsdmMarginTierSourceRef

    def __post_init__(self) -> None:
        _text("band_id", self.band_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        _utc("effective_from", self.effective_from)
        _utc("effective_to_exclusive", self.effective_to_exclusive)
        _simulation("available_at", self.available_at)
        if type(self.scope) is not BinanceUsdmMarginTierScope:
            raise TypeError("scope must be exact BinanceUsdmMarginTierScope")
        if self.notional_coef is not None:
            _raw_string("notional_coef", self.notional_coef)
        if type(self.brackets) is not tuple or not all(
            type(value) is BinanceUsdmMarginTierBracket for value in self.brackets
        ):
            raise TypeError("brackets must be a tuple of exact BinanceUsdmMarginTierBracket")
        if type(self.source_ref) is not BinanceUsdmMarginTierSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmMarginTierSourceRef")

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        _utc("instant", instant)
        return self.effective_from <= instant < self.effective_to_exclusive

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_margin_tier_band",
            "schema_version": _SCHEMA_VERSION,
            "band_id": self.band_id,
            "instrument_id": self.instrument_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "available_at": self.available_at,
            "scope": self.scope.value,
            "notional_coef": self.notional_coef,
            "brackets": list(self.brackets),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierRuleBook:
    rule_book_key: str
    rule_book_version: int
    instrument_id: InstrumentId
    settlement_currency_id: CurrencyId
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    bands: tuple[BinanceUsdmMarginTierBand, ...]

    def __post_init__(self) -> None:
        _text("rule_book_key", self.rule_book_key)
        if type(self.rule_book_version) is not int or self.rule_book_version <= 0:
            raise ValueError("rule_book_version must be a positive integer")
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.settlement_currency_id) is not CurrencyId:
            raise TypeError("settlement_currency_id must be exact CurrencyId")
        _utc("coverage_from", self.coverage_from)
        _utc("coverage_to_exclusive", self.coverage_to_exclusive)
        if type(self.bands) is not tuple or not all(
            type(value) is BinanceUsdmMarginTierBand for value in self.bands
        ):
            raise TypeError("bands must be a tuple of exact BinanceUsdmMarginTierBand")
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
            "type": "binance_usdm_margin_tier_rule_book",
            "schema_version": _SCHEMA_VERSION,
            "rule_book_key": self.rule_book_key,
            "rule_book_version": self.rule_book_version,
            "instrument_id": self.instrument_id,
            "settlement_currency_id": self.settlement_currency_id,
            "coverage_from": self.coverage_from,
            "coverage_to_exclusive": self.coverage_to_exclusive,
            "bands": list(self.bands),
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierQuery:
    instrument_metadata: BinanceUsdmInstrumentMetadataResolution
    evaluated_at: UtcInstant
    captured_at: SimulationInstant
    rule_book: BinanceUsdmMarginTierRuleBook

    def __post_init__(self) -> None:
        if type(self.instrument_metadata) is not BinanceUsdmInstrumentMetadataResolution:
            raise TypeError("instrument_metadata must be exact G10A resolution")
        _utc("evaluated_at", self.evaluated_at)
        _simulation("captured_at", self.captured_at)
        if type(self.rule_book) is not BinanceUsdmMarginTierRuleBook:
            raise TypeError("rule_book must be exact BinanceUsdmMarginTierRuleBook")

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_margin_tier_query",
            "schema_version": _SCHEMA_VERSION,
            "instrument_metadata": self.instrument_metadata,
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
    try:
        units = int(integer + fraction) if fraction else int(integer)
    except ValueError as error:  # pragma: no cover - guarded by the grammar
        raise ValueError("invalid decimal") from error
    return _DecimalValue(units, len(fraction))


def _compare(left: _DecimalValue, right: _DecimalValue) -> int:
    scale = max(left.scale, right.scale)
    left_units = left.units * 10 ** (scale - left.scale)
    right_units = right.units * 10 ** (scale - right.scale)
    return (left_units > right_units) - (left_units < right_units)


def _parsed_brackets(
    band: BinanceUsdmMarginTierBand,
) -> tuple[dict[str, _DecimalValue], ...]:
    return tuple(
        {name: _decimal(getattr(bracket, name)) for name in _DECIMAL_FIELDS}
        for bracket in band.brackets
    )


def _integral_positive(value: _DecimalValue) -> bool:
    return value.scale == 0 and value.units > 0


def _geometry_error(band: BinanceUsdmMarginTierBand) -> bool:
    if not band.brackets:
        return True
    rows = _parsed_brackets(band)
    prior_id = 0
    prior_cap: _DecimalValue | None = None
    prior_maximum: _DecimalValue | None = None
    for index, row in enumerate(rows):
        bracket_id = row["bracket_id"]
        floor = row["notional_floor"]
        cap = row["notional_cap"]
        minimum = row["minimum_leverage_range"]
        maximum = row["maximum_leverage"]
        if (
            not _integral_positive(bracket_id)
            or (index == 0 and bracket_id.units != 1)
            or bracket_id.units <= prior_id
            or not _integral_positive(minimum)
            or not _integral_positive(maximum)
            or minimum.units > maximum.units
            or _compare(floor, cap) >= 0
            or (index == 0 and floor.units != 0)
            or (prior_cap is not None and _compare(prior_cap, floor) != 0)
            or (
                prior_maximum is not None
                and _compare(maximum, prior_maximum) > 0
            )
        ):
            return True
        prior_id = bracket_id.units
        prior_cap = cap
        prior_maximum = maximum
    return False


def _visible(query: BinanceUsdmMarginTierQuery) -> tuple[BinanceUsdmMarginTierBand, ...]:
    return tuple(
        band
        for band in query.rule_book.bands
        if band.available_at <= query.captured_at
    )


def _details(
    code: BinanceUsdmMarginTierFailureCode,
    *subject_ids: str,
) -> tuple[BinanceUsdmMarginTierFailureCode, str, tuple[str, ...]]:
    return code, _FAILURE_MESSAGES[code], tuple(subject_ids)


def _failure_details(
    query: BinanceUsdmMarginTierQuery,
) -> tuple[BinanceUsdmMarginTierFailureCode, str, tuple[str, ...]] | None:
    book = query.rule_book
    if not book.bands:
        return _details(
            BinanceUsdmMarginTierFailureCode.MISSING_TIER_BANDS,
            book.rule_book_key,
        )
    metadata = query.instrument_metadata
    settlement = metadata.instrument.settlement_currency
    if (
        metadata.query.effective_at != query.evaluated_at
        or metadata.query.captured_at > query.captured_at.instant
        or book.instrument_id != metadata.instrument.instrument_id
        or settlement is None
        or book.settlement_currency_id != settlement
    ):
        return _details(
            BinanceUsdmMarginTierFailureCode.INSTRUMENT_METADATA_MISMATCH,
            book.rule_book_key,
        )
    visible = _visible(query)
    if not visible:
        return _details(
            BinanceUsdmMarginTierFailureCode.TIER_NOT_AVAILABLE,
            book.rule_book_key,
        )
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
        or not any(value.contains(query.evaluated_at) for value in visible)
    ):
        return _details(
            BinanceUsdmMarginTierFailureCode.MISSING_TIER_INTERVAL,
            *(value.band_id for value in visible),
        )
    band_ids = tuple(value.band_id for value in visible)
    if len(set(band_ids)) != len(band_ids) or any(
        current.effective_from < previous.effective_to_exclusive
        for previous, current in zip(visible, visible[1:])
    ):
        return _details(
            BinanceUsdmMarginTierFailureCode.OVERLAPPING_TIER_INTERVALS,
            *band_ids,
        )
    if any(
        value.scope is BinanceUsdmMarginTierScope.ACCOUNT_ADJUSTED
        or value.notional_coef is not None
        or value.source_ref.source_kind == _USER_DATA_LEVERAGE_BRACKET
        for value in visible
    ):
        return _details(
            BinanceUsdmMarginTierFailureCode.ACCOUNT_ADJUSTED_TIER_UNSUPPORTED,
            *band_ids,
        )
    try:
        for value in visible:
            _parsed_brackets(value)
    except ValueError:
        return _details(
            BinanceUsdmMarginTierFailureCode.INVALID_DECIMAL_FIELD,
            *band_ids,
        )
    if any(_geometry_error(value) for value in visible):
        return _details(
            BinanceUsdmMarginTierFailureCode.INVALID_BRACKET_GEOMETRY,
            *band_ids,
        )
    if any(
        value.source_ref.source_kind != _CONTRACT_INFO_BRACKET_UPDATE
        for value in visible
    ):
        return _details(
            BinanceUsdmMarginTierFailureCode.UNSUPPORTED_MARGIN_SEMANTICS,
            *band_ids,
        )
    sources: dict[str, tuple[str, str]] = {}
    for value in visible:
        if value.instrument_id != book.instrument_id:
            return _details(
                BinanceUsdmMarginTierFailureCode.METADATA_CONFLICT,
                value.band_id,
            )
        source = (value.source_ref.source_hash, value.source_ref.source_kind)
        prior = sources.setdefault(value.source_ref.source_key, source)
        if prior != source:
            return _details(
                BinanceUsdmMarginTierFailureCode.METADATA_CONFLICT,
                value.source_ref.source_key,
            )
    return None


def _money_scale(bands: tuple[BinanceUsdmMarginTierBand, ...]) -> int:
    return max(
        _decimal(getattr(bracket, field)).scale
        for band in bands
        for bracket in band.brackets
        for field in _MONEY_FIELDS
    )


def _units_at(value: _DecimalValue, scale: int) -> int:
    if value.scale > scale:
        raise ValueError("inexact decimal conversion")
    return value.units * 10 ** (scale - value.scale)


def _generic_tiers(
    band: BinanceUsdmMarginTierBand,
    *,
    currency: CurrencyId,
    money_scale: Scale,
) -> tuple[LinearMarginTier, ...]:
    rows = _parsed_brackets(band)
    return tuple(
        LinearMarginTier(
            tier_id=f"{band.band_id}:bracket:{bracket.bracket_id}",
            notional_floor=Money(
                _units_at(row["notional_floor"], money_scale.places),
                money_scale,
                str(currency),
            ),
            notional_cap=Money(
                _units_at(row["notional_cap"], money_scale.places),
                money_scale,
                str(currency),
            ),
            maximum_leverage=Rate(
                row["maximum_leverage"].units,
                Scale(0),
                _LEVERAGE_BASIS,
            ),
            maintenance_margin_rate=Rate(
                row["maintenance_margin_rate"].units,
                Scale(row["maintenance_margin_rate"].scale),
                _MAINTENANCE_BASIS,
            ),
            maintenance_margin_deduction=Money(
                _units_at(
                    row["maintenance_margin_deduction"], money_scale.places
                ),
                money_scale,
                str(currency),
            ),
        )
        for bracket, row in zip(band.brackets, rows)
    )


def _generic_rule_book(
    query: BinanceUsdmMarginTierQuery,
    visible: tuple[BinanceUsdmMarginTierBand, ...],
) -> LinearMarginRuleBook:
    currency = query.rule_book.settlement_currency_id
    tier_scale = Scale(_money_scale(visible))
    intervals = tuple(
        LinearMarginRuleInterval(
            interval_id=band.band_id,
            effective_from=band.effective_from,
            effective_to_exclusive=band.effective_to_exclusive,
            available_at=band.available_at,
            tiers=_generic_tiers(
                band,
                currency=currency,
                money_scale=tier_scale,
            ),
            source_key=band.source_ref.source_key,
            source_hash=band.source_ref.source_hash,
            tier_boundary_convention=_BOUNDARY,
        )
        for band in visible
    )
    return LinearMarginRuleBook.create(
        rule_book_key=query.rule_book.rule_book_key,
        rule_book_version=query.rule_book.rule_book_version,
        instrument_id=query.rule_book.instrument_id,
        settlement_currency_id=currency,
        tier_scale=tier_scale,
        intervals=intervals,
    )


def _component_ref() -> ProfileComponentRef:
    digest = canonical_sha256(
        {
            "type": "binance_usdm_margin_tier_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "algorithm_key": _ALGORITHM_KEY,
            "source_kind": _CONTRACT_INFO_BRACKET_UPDATE,
            "boundary_convention": _BOUNDARY.value,
            "finite_terminal_coverage": True,
            "allowed_grade": "development",
        }
    )
    return ProfileComponentRef(
        port_type=ProfilePortType.MARGIN_MODEL,
        component_key=_COMPONENT_KEY,
        component_version=1,
        component_digest=digest,
    )


@dataclass(frozen=True, slots=True)
class _ResolutionValues:
    component_ref: ProfileComponentRef
    visible_bands: tuple[BinanceUsdmMarginTierBand, ...]
    active_band: BinanceUsdmMarginTierBand
    margin_rule_book: LinearMarginRuleBook
    active_interval: LinearMarginRuleInterval
    active_tiers: tuple[LinearMarginTier, ...]
    tier_boundary_convention: LinearMarginTierBoundaryConvention
    finite_terminal_notional_cap: Money
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    decision_grade_eligible: bool


def _resolution_values(query: BinanceUsdmMarginTierQuery) -> _ResolutionValues:
    visible = _visible(query)
    active_band = next(value for value in visible if value.contains(query.evaluated_at))
    margin_rule_book = _generic_rule_book(query, visible)
    active_interval = next(
        value
        for value in margin_rule_book.intervals
        if value.interval_id == active_band.band_id
    )
    terminal_cap = active_interval.tiers[-1].notional_cap
    if terminal_cap is None:  # pragma: no cover - provider geometry requires a cap
        raise AssertionError("Binance margin tiers require finite terminal coverage")
    return _ResolutionValues(
        component_ref=_component_ref(),
        visible_bands=visible,
        active_band=active_band,
        margin_rule_book=margin_rule_book,
        active_interval=active_interval,
        active_tiers=active_interval.tiers,
        tier_boundary_convention=_BOUNDARY,
        finite_terminal_notional_cap=terminal_cap,
        coverage_from=query.rule_book.coverage_from,
        coverage_to_exclusive=query.rule_book.coverage_to_exclusive,
        decision_grade_eligible=False,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierResolution:
    query: BinanceUsdmMarginTierQuery
    component_ref: ProfileComponentRef
    visible_bands: tuple[BinanceUsdmMarginTierBand, ...]
    active_band: BinanceUsdmMarginTierBand
    margin_rule_book: LinearMarginRuleBook
    active_interval: LinearMarginRuleInterval
    active_tiers: tuple[LinearMarginTier, ...]
    tier_boundary_convention: LinearMarginTierBoundaryConvention
    finite_terminal_notional_cap: Money
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmMarginTierQuery:
            raise TypeError("query must be exact BinanceUsdmMarginTierQuery")
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
            "type": "binance_usdm_margin_tier_resolution",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "component_ref": self.component_ref,
            "visible_bands": list(self.visible_bands),
            "active_band": self.active_band,
            "margin_rule_book": self.margin_rule_book,
            "active_interval": self.active_interval,
            "active_tiers": list(self.active_tiers),
            "tier_boundary_convention": self.tier_boundary_convention.value,
            "finite_terminal_notional_cap": self.finite_terminal_notional_cap,
            "coverage_from": self.coverage_from,
            "coverage_to_exclusive": self.coverage_to_exclusive,
            "decision_grade_eligible": self.decision_grade_eligible,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierFailure:
    query: BinanceUsdmMarginTierQuery
    code: BinanceUsdmMarginTierFailureCode
    message: str
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmMarginTierQuery:
            raise TypeError("query must be exact BinanceUsdmMarginTierQuery")
        if type(self.code) is not BinanceUsdmMarginTierFailureCode:
            raise TypeError("code must be exact BinanceUsdmMarginTierFailureCode")
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
            "type": "binance_usdm_margin_tier_failure",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "code": self.code.value,
            "message": self.message,
            "subject_ids": list(self.subject_ids),
        }


BinanceUsdmMarginTierOutcome = ProfilePortOutcome[
    BinanceUsdmMarginTierResolution,
    BinanceUsdmMarginTierFailure,
]


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarginTierModel:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref()

    def resolve_margin_tiers(
        self,
        query: BinanceUsdmMarginTierQuery,
        /,
    ) -> BinanceUsdmMarginTierOutcome:
        if type(query) is not BinanceUsdmMarginTierQuery:
            raise TypeError("query must be exact BinanceUsdmMarginTierQuery")
        failure = _failure_details(query)
        if failure is not None:
            code, message, subject_ids = failure
            return ProfilePortOutcome.for_failure(
                self.component_ref,
                query,
                BinanceUsdmMarginTierFailure(
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
            BinanceUsdmMarginTierResolution(
                query=query,
                **{name: getattr(values, name) for name in values.__dataclass_fields__},
            ),
        )
