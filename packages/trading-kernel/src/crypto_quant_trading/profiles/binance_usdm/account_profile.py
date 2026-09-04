from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from crypto_quant_domain import (
    CurrencyId,
    FeeBasisType,
    InstrumentId,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading.fee_reservations import (
    AccountFeeScheduleRef,
    FeeReservationApplicability,
    FeeReservationBasis,
    FeeReservationChargeRule,
    FeeReservationRuleSet,
    FeeReservationRuleSource,
)
from crypto_quant_trading.fees import (
    FinalFeeApplicability,
    FinalFeeCalculationBasis,
    FinalFeeChargeRule,
    FinalFeeRuleSet,
    FinalFeeRuleSource,
)
from crypto_quant_trading.margin import LinearMarginLeverageEvidence
from crypto_quant_trading.ports import ProfileComponentRef, ProfilePortType
from crypto_quant_trading.pretrade_risk import FeeReserveFundingSource

from .instrument_metadata import BinanceUsdmInstrumentMetadataResolution


_SCHEMA_VERSION = 1
_MODEL_KEY = "crypto.binance_usdm.account-profile.v1"
_MODEL_VERSION = 1
_USDT = CurrencyId("USDT")
_FEE_SCALE = Scale(8)
_RESERVATION_QUANTIZATION = QuantizationPolicy(
    "binance-usdm-fee-reservation-ceiling-v1",
    _FEE_SCALE,
    RoundingPolicy.CEILING,
)
_FINAL_QUANTIZATION = QuantizationPolicy(
    "binance-usdm-final-fee-toward-zero-v1",
    _FEE_SCALE,
    RoundingPolicy.TOWARD_ZERO,
)
_LIMITATIONS = (
    "development_grade_account_history_completeness_unproven",
    "fee_rounding_parity_unproven",
    "negative_rebates_unsupported",
    "bnb_fee_discount_unsupported",
    "account_risk_policy_composition_owned_by_g10g",
)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_UNSIGNED_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?")
_SIGNED_DECIMAL = re.compile(r"(-?)(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?")


class BinanceUsdmAccountSourceKind(str, Enum):
    ACCOUNT_CONFIG = "account_config"
    SYMBOL_CONFIG = "symbol_config"
    COMMISSION_RATE = "commission_rate"
    FEE_BURN = "fee_burn"


class BinanceUsdmAccountProfileScope(str, Enum):
    STANDARD_UM = "standard_um"
    PORTFOLIO_MARGIN_UM = "portfolio_margin_um"


class BinanceUsdmAccountProfileFailureCode(str, Enum):
    MISSING_PROFILE_BANDS = "missing_profile_bands"
    INSTRUMENT_METADATA_MISMATCH = "instrument_metadata_mismatch"
    ACCOUNT_CONTEXT_MISMATCH = "account_context_mismatch"
    PROFILE_NOT_AVAILABLE = "profile_not_available"
    MISSING_PROFILE_INTERVAL = "missing_profile_interval"
    OVERLAPPING_PROFILE_INTERVALS = "overlapping_profile_intervals"
    ACCOUNT_TRADING_DISABLED = "account_trading_disabled"
    PORTFOLIO_MARGIN_UNSUPPORTED = "portfolio_margin_unsupported"
    HEDGE_MODE_UNSUPPORTED = "hedge_mode_unsupported"
    MULTI_ASSET_MODE_UNSUPPORTED = "multi_asset_mode_unsupported"
    ISOLATED_MARGIN_UNSUPPORTED = "isolated_margin_unsupported"
    AUTO_ADD_MARGIN_UNSUPPORTED = "auto_add_margin_unsupported"
    BNB_FEE_DISCOUNT_UNSUPPORTED = "bnb_fee_discount_unsupported"
    REPORTING_CURRENCY_MISMATCH = "reporting_currency_mismatch"
    INVALID_DECIMAL_FIELD = "invalid_decimal_field"
    INVALID_LEVERAGE = "invalid_leverage"
    NEGATIVE_COMMISSION_UNSUPPORTED = "negative_commission_unsupported"
    SOURCE_IDENTITY_CONFLICT = "source_identity_conflict"


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise TypeError(f"{name} must be exact non-empty string")
    return value


def _sha256(name: str, value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _simulation(name: str, value: object) -> SimulationInstant:
    if type(value) is not SimulationInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")
    return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmAccountProfileSourceRef:
    source_kind: BinanceUsdmAccountSourceKind
    source_key: str
    source_hash: str
    evidence_key: str
    revision_id: str
    supersedes_revision_id: str | None

    def __post_init__(self) -> None:
        if type(self.source_kind) is not BinanceUsdmAccountSourceKind:
            raise TypeError("source_kind must be exact BinanceUsdmAccountSourceKind")
        _text("source_key", self.source_key)
        _sha256("source_hash", self.source_hash)
        _text("evidence_key", self.evidence_key)
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)

    @property
    def source_ref_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_account_profile_source_ref",
            "schema_version": _SCHEMA_VERSION,
            "source_kind": self.source_kind.value,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "evidence_key": self.evidence_key,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmAccountProfileBand:
    band_id: str
    account_id: str
    instrument_id: InstrumentId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    available_at: SimulationInstant
    scope: BinanceUsdmAccountProfileScope
    fee_tier: int
    can_trade: bool
    dual_side_position: bool
    multi_assets_margin: bool
    trade_group_id: int
    margin_type: str
    is_auto_add_margin: bool
    leverage: str
    max_notional_value: str
    maker_commission_rate: str
    taker_commission_rate: str
    fee_burn: bool
    source_refs: tuple[BinanceUsdmAccountProfileSourceRef, ...]

    def __post_init__(self) -> None:
        _text("band_id", self.band_id)
        _text("account_id", self.account_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.effective_from) is not UtcInstant or type(
            self.effective_to_exclusive
        ) is not UtcInstant:
            raise TypeError("effective interval must use exact UtcInstant")
        if self.effective_to_exclusive <= self.effective_from:
            raise ValueError("account profile interval must be non-empty")
        _simulation("available_at", self.available_at)
        if type(self.scope) is not BinanceUsdmAccountProfileScope:
            raise TypeError("scope must be exact BinanceUsdmAccountProfileScope")
        if type(self.fee_tier) is not int or self.fee_tier < 0:
            raise ValueError("fee_tier must be a nonnegative integer")
        for name, value in (
            ("can_trade", self.can_trade),
            ("dual_side_position", self.dual_side_position),
            ("multi_assets_margin", self.multi_assets_margin),
            ("is_auto_add_margin", self.is_auto_add_margin),
            ("fee_burn", self.fee_burn),
        ):
            if type(value) is not bool:
                raise TypeError(f"{name} must be exact bool")
        if type(self.trade_group_id) is not int:
            raise TypeError("trade_group_id must be exact integer")
        _text("margin_type", self.margin_type)
        _text("leverage", self.leverage)
        _text("max_notional_value", self.max_notional_value)
        _text("maker_commission_rate", self.maker_commission_rate)
        _text("taker_commission_rate", self.taker_commission_rate)
        if type(self.source_refs) is not tuple or not all(
            type(value) is BinanceUsdmAccountProfileSourceRef
            for value in self.source_refs
        ):
            raise TypeError("source_refs must be a tuple of exact source refs")
        object.__setattr__(
            self,
            "source_refs",
            tuple(
                sorted(
                    self.source_refs,
                    key=lambda value: (
                        value.source_kind.value,
                        value.source_key,
                        value.revision_id,
                    ),
                )
            ),
        )

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant < self.effective_to_exclusive

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_account_profile_band",
            "schema_version": _SCHEMA_VERSION,
            "band_id": self.band_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "available_at": self.available_at,
            "scope": self.scope.value,
            "fee_tier": self.fee_tier,
            "can_trade": self.can_trade,
            "dual_side_position": self.dual_side_position,
            "multi_assets_margin": self.multi_assets_margin,
            "trade_group_id": self.trade_group_id,
            "margin_type": self.margin_type,
            "is_auto_add_margin": self.is_auto_add_margin,
            "leverage": self.leverage,
            "max_notional_value": self.max_notional_value,
            "maker_commission_rate": self.maker_commission_rate,
            "taker_commission_rate": self.taker_commission_rate,
            "fee_burn": self.fee_burn,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmHistoricalAccountProfileBook:
    account_profile_book_key: str
    account_profile_book_version: int
    account_id: str
    instrument_id: InstrumentId
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    bands: tuple[BinanceUsdmAccountProfileBand, ...]

    def __post_init__(self) -> None:
        _text("account_profile_book_key", self.account_profile_book_key)
        if (
            type(self.account_profile_book_version) is not int
            or self.account_profile_book_version <= 0
        ):
            raise ValueError("account_profile_book_version must be positive")
        _text("account_id", self.account_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.coverage_from) is not UtcInstant or type(
            self.coverage_to_exclusive
        ) is not UtcInstant:
            raise TypeError("coverage bounds must be exact UtcInstant")
        if self.coverage_to_exclusive <= self.coverage_from:
            raise ValueError("account profile coverage must be finite and non-empty")
        if type(self.bands) is not tuple or not all(
            type(value) is BinanceUsdmAccountProfileBand for value in self.bands
        ):
            raise TypeError("bands must be a tuple of exact account profile bands")
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
    def account_profile_book_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_historical_account_profile_book",
            "schema_version": _SCHEMA_VERSION,
            "account_profile_book_key": self.account_profile_book_key,
            "account_profile_book_version": self.account_profile_book_version,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "coverage_from": self.coverage_from,
            "coverage_to_exclusive": self.coverage_to_exclusive,
            "bands": list(self.bands),
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmAccountProfileQuery:
    instrument_resolution: BinanceUsdmInstrumentMetadataResolution
    account_id: str
    account_profile_book: BinanceUsdmHistoricalAccountProfileBook
    evaluated_at: UtcInstant
    captured_at: SimulationInstant
    reporting_currency_id: CurrencyId

    def __post_init__(self) -> None:
        if type(self.instrument_resolution) is not BinanceUsdmInstrumentMetadataResolution:
            raise TypeError(
                "instrument_resolution must be exact BinanceUsdmInstrumentMetadataResolution"
            )
        _text("account_id", self.account_id)
        if type(self.account_profile_book) is not BinanceUsdmHistoricalAccountProfileBook:
            raise TypeError(
                "account_profile_book must be exact BinanceUsdmHistoricalAccountProfileBook"
            )
        if type(self.evaluated_at) is not UtcInstant:
            raise TypeError("evaluated_at must be exact UtcInstant")
        _simulation("captured_at", self.captured_at)
        if type(self.reporting_currency_id) is not CurrencyId:
            raise TypeError("reporting_currency_id must be exact CurrencyId")

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_account_profile_query",
            "schema_version": _SCHEMA_VERSION,
            "instrument_resolution": self.instrument_resolution,
            "account_id": self.account_id,
            "account_profile_book": self.account_profile_book,
            "evaluated_at": self.evaluated_at,
            "captured_at": self.captured_at,
            "reporting_currency_id": self.reporting_currency_id,
        }


@dataclass(frozen=True, slots=True)
class _DecimalValue:
    units: int
    places: int


def _decimal(value: str, *, signed: bool) -> _DecimalValue | None:
    match = (_SIGNED_DECIMAL if signed else _UNSIGNED_DECIMAL).fullmatch(value)
    if match is None:
        return None
    negative = signed and value.startswith("-")
    body = value[1:] if negative else value
    whole, dot, fraction = body.partition(".")
    try:
        units = int(whole + fraction)
    except ValueError:
        return None
    if negative:
        units = -units
    return _DecimalValue(units, len(fraction) if dot else 0)


def _leverage(value: str) -> int | None:
    match = _UNSIGNED_DECIMAL.fullmatch(value)
    if match is None:
        return None
    whole, dot, fraction = value.partition(".")
    if dot and any(digit != "0" for digit in fraction):
        return None
    try:
        leverage = int(whole)
    except ValueError:
        return None
    return leverage if 1 <= leverage <= 125 else None


def _component_ref(port_type: ProfilePortType, key: str, policy: str) -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=port_type,
        component_key=key,
        component_version=1,
        component_digest=canonical_sha256(
            {
                "type": "binance_usdm_not_applicable_fee_component",
                "schema_version": _SCHEMA_VERSION,
                "port_type": port_type.value,
                "component_key": key,
                "policy": policy,
            }
        ),
    )


def _market_fee_ref() -> ProfileComponentRef:
    return _component_ref(
        ProfilePortType.FEE_ASSESSMENT_POLICY,
        "crypto.binance_usdm.market-fee-not-applicable.v1",
        "account-specific commission owns exchange trading fee",
    )


def _tax_ref() -> ProfileComponentRef:
    return _component_ref(
        ProfilePortType.TAX_POLICY,
        "crypto.binance_usdm.tax-not-applicable.v1",
        "no separate transaction tax in frozen profile",
    )


def _model_digest() -> str:
    return canonical_sha256(
        {
            "type": "binance_usdm_account_profile_model",
            "schema_version": _SCHEMA_VERSION,
            "model_key": _MODEL_KEY,
            "model_version": _MODEL_VERSION,
            "source_kinds": [value.value for value in BinanceUsdmAccountSourceKind],
            "supported_scope": BinanceUsdmAccountProfileScope.STANDARD_UM.value,
            "position_mode": "one_way",
            "asset_mode": "single_asset",
            "margin_type": "CROSSED",
            "auto_add_margin": False,
            "fee_burn": False,
            "currency": _USDT,
            "fee_scale": _FEE_SCALE.places,
            "leverage_basis": "notional_per_initial_margin",
            "reservation_rate": "max(maker,taker)",
            "reservation_quantization": _RESERVATION_QUANTIZATION,
            "final_basis": "per_fill_maker_or_taker_notional",
            "final_quantization": _FINAL_QUANTIZATION,
            "negative_rebate_policy": "unsupported",
            "account_risk_policy": "owned_by_g10g",
            "allowed_grade": "development",
            "limitations": list(_LIMITATIONS),
        }
    )


def _visible_bands(
    query: BinanceUsdmAccountProfileQuery,
) -> tuple[BinanceUsdmAccountProfileBand, ...]:
    return tuple(
        value
        for value in query.account_profile_book.bands
        if value.available_at <= query.captured_at
    )


def _active_bands(
    query: BinanceUsdmAccountProfileQuery,
) -> tuple[BinanceUsdmAccountProfileBand, ...]:
    return tuple(value for value in _visible_bands(query) if value.contains(query.evaluated_at))


def _instrument_mismatch(query: BinanceUsdmAccountProfileQuery) -> bool:
    resolution = query.instrument_resolution
    instrument_id = resolution.instrument.instrument_id
    book = query.account_profile_book
    return (
        book.instrument_id != instrument_id
        or resolution.query.effective_at != query.evaluated_at
        or not resolution.listing_interval.contains(query.evaluated_at)
        or resolution.query.captured_at > query.captured_at.instant
        or any(value.instrument_id != instrument_id for value in book.bands)
    )


def _account_mismatch(query: BinanceUsdmAccountProfileQuery) -> bool:
    book = query.account_profile_book
    return (
        query.account_id != book.account_id
        or any(value.account_id != query.account_id for value in book.bands)
    )


def _coverage_failure(
    query: BinanceUsdmAccountProfileQuery,
) -> BinanceUsdmAccountProfileFailureCode | None:
    visible = _visible_bands(query)
    if not visible:
        return BinanceUsdmAccountProfileFailureCode.PROFILE_NOT_AVAILABLE
    book = query.account_profile_book
    cursor = book.coverage_from
    for band in visible:
        if band.effective_from > cursor:
            return BinanceUsdmAccountProfileFailureCode.MISSING_PROFILE_INTERVAL
        if band.effective_from < cursor:
            return BinanceUsdmAccountProfileFailureCode.OVERLAPPING_PROFILE_INTERVALS
        cursor = band.effective_to_exclusive
    if cursor < book.coverage_to_exclusive:
        return BinanceUsdmAccountProfileFailureCode.MISSING_PROFILE_INTERVAL
    if cursor > book.coverage_to_exclusive:
        return BinanceUsdmAccountProfileFailureCode.OVERLAPPING_PROFILE_INTERVALS
    active = _active_bands(query)
    if not active:
        return BinanceUsdmAccountProfileFailureCode.MISSING_PROFILE_INTERVAL
    if len(active) != 1:
        return BinanceUsdmAccountProfileFailureCode.OVERLAPPING_PROFILE_INTERVALS
    return None


def _source_conflict(
    visible_bands: tuple[BinanceUsdmAccountProfileBand, ...],
) -> bool:
    if len({value.band_id for value in visible_bands}) != len(visible_bands):
        return True
    previous: dict[
        BinanceUsdmAccountSourceKind, BinanceUsdmAccountProfileSourceRef
    ] = {}
    for band in visible_bands:
        by_kind = {value.source_kind: value for value in band.source_refs}
        if (
            len(band.source_refs) != len(BinanceUsdmAccountSourceKind)
            or set(by_kind) != set(BinanceUsdmAccountSourceKind)
        ):
            return True
        for kind in BinanceUsdmAccountSourceKind:
            ref = by_kind[kind]
            prior = previous.get(kind)
            if prior is None:
                if ref.supersedes_revision_id is not None:
                    return True
            elif ref != prior and (
                ref.source_key != prior.source_key
                or ref.revision_id == prior.revision_id
                or ref.supersedes_revision_id != prior.revision_id
            ):
                return True
            previous[kind] = ref
    return False


def _first_failure(
    query: BinanceUsdmAccountProfileQuery,
) -> BinanceUsdmAccountProfileFailureCode | None:
    if not query.account_profile_book.bands:
        return BinanceUsdmAccountProfileFailureCode.MISSING_PROFILE_BANDS
    if _instrument_mismatch(query):
        return BinanceUsdmAccountProfileFailureCode.INSTRUMENT_METADATA_MISMATCH
    if _account_mismatch(query):
        return BinanceUsdmAccountProfileFailureCode.ACCOUNT_CONTEXT_MISMATCH
    coverage = _coverage_failure(query)
    if coverage is not None:
        return coverage
    band = _active_bands(query)[0]
    if not band.can_trade:
        return BinanceUsdmAccountProfileFailureCode.ACCOUNT_TRADING_DISABLED
    if band.scope is not BinanceUsdmAccountProfileScope.STANDARD_UM:
        return BinanceUsdmAccountProfileFailureCode.PORTFOLIO_MARGIN_UNSUPPORTED
    if band.dual_side_position:
        return BinanceUsdmAccountProfileFailureCode.HEDGE_MODE_UNSUPPORTED
    if band.multi_assets_margin:
        return BinanceUsdmAccountProfileFailureCode.MULTI_ASSET_MODE_UNSUPPORTED
    if band.margin_type != "CROSSED":
        return BinanceUsdmAccountProfileFailureCode.ISOLATED_MARGIN_UNSUPPORTED
    if band.is_auto_add_margin:
        return BinanceUsdmAccountProfileFailureCode.AUTO_ADD_MARGIN_UNSUPPORTED
    if band.fee_burn:
        return BinanceUsdmAccountProfileFailureCode.BNB_FEE_DISCOUNT_UNSUPPORTED
    resolution = query.instrument_resolution
    if (
        resolution.instrument.quote_currency != _USDT
        or resolution.instrument.settlement_currency != _USDT
        or query.reporting_currency_id != _USDT
    ):
        return BinanceUsdmAccountProfileFailureCode.REPORTING_CURRENCY_MISMATCH
    maker = _decimal(band.maker_commission_rate, signed=True)
    taker = _decimal(band.taker_commission_rate, signed=True)
    maximum = _decimal(band.max_notional_value, signed=False)
    if maker is None or taker is None or maximum is None:
        return BinanceUsdmAccountProfileFailureCode.INVALID_DECIMAL_FIELD
    if _leverage(band.leverage) is None:
        return BinanceUsdmAccountProfileFailureCode.INVALID_LEVERAGE
    if maker.units < 0 or taker.units < 0:
        return BinanceUsdmAccountProfileFailureCode.NEGATIVE_COMMISSION_UNSUPPORTED
    if _source_conflict(_visible_bands(query)):
        return BinanceUsdmAccountProfileFailureCode.SOURCE_IDENTITY_CONFLICT
    return None


def _rate(value: _DecimalValue) -> Rate:
    return Rate(value.units, Scale(value.places), "fee_fraction")


def _source_ref(
    band: BinanceUsdmAccountProfileBand,
    kind: BinanceUsdmAccountSourceKind,
) -> BinanceUsdmAccountProfileSourceRef:
    return next(value for value in band.source_refs if value.source_kind is kind)


def _schedule_ref(
    query: BinanceUsdmAccountProfileQuery,
    band: BinanceUsdmAccountProfileBand,
    maker: Rate,
    taker: Rate,
) -> AccountFeeScheduleRef:
    payload = {
        "type": "binance_usdm_account_fee_schedule",
        "schema_version": _SCHEMA_VERSION,
        "account_id": query.account_id,
        "instrument_id": band.instrument_id,
        "band": band,
        "maker_rate": maker,
        "taker_rate": taker,
        "currency_id": _USDT,
        "fee_scale": _FEE_SCALE.places,
        "reservation_quantization": _RESERVATION_QUANTIZATION,
        "final_quantization": _FINAL_QUANTIZATION,
        "limitations": list(_LIMITATIONS),
    }
    return AccountFeeScheduleRef(
        schedule_key=f"binance.usdm.account-fee.{query.account_id}.{band.instrument_id}",
        schedule_version=1,
        schedule_digest=canonical_sha256(payload),
    )


def _reservation_rule_set(
    schedule_ref: AccountFeeScheduleRef,
    maker: Rate,
    taker: Rate,
) -> FeeReservationRuleSet:
    worst = maker if maker.units * taker.scale.factor >= taker.units * maker.scale.factor else taker
    rules = (
        FeeReservationChargeRule(
            source=FeeReservationRuleSource.MARKET_FEE,
            rule_id="binance-usdm-market-fee-not-applicable",
            basis=FeeReservationBasis.ORDER_NOTIONAL,
            applicability=FeeReservationApplicability.NOT_APPLICABLE,
            rate=Rate(0, _FEE_SCALE, "fee_fraction"),
            flat_amount=None,
            quantization=_RESERVATION_QUANTIZATION,
        ),
        FeeReservationChargeRule(
            source=FeeReservationRuleSource.TAX,
            rule_id="binance-usdm-tax-not-applicable",
            basis=FeeReservationBasis.ORDER_NOTIONAL,
            applicability=FeeReservationApplicability.NOT_APPLICABLE,
            rate=Rate(0, _FEE_SCALE, "fee_fraction"),
            flat_amount=None,
            quantization=_RESERVATION_QUANTIZATION,
        ),
        FeeReservationChargeRule(
            source=FeeReservationRuleSource.ACCOUNT_SCHEDULE,
            rule_id="binance-usdm-account-worst-case-commission",
            basis=FeeReservationBasis.ORDER_NOTIONAL,
            applicability=FeeReservationApplicability.APPLIES,
            rate=worst,
            flat_amount=None,
            quantization=_RESERVATION_QUANTIZATION,
        ),
    )
    return FeeReservationRuleSet.create(
        market_fee_policy_ref=_market_fee_ref(),
        tax_policy_ref=_tax_ref(),
        account_fee_schedule_ref=schedule_ref,
        reservation_currency=_USDT,
        reservation_scale=_FEE_SCALE,
        charge_rules=rules,
        minimums=(),
    )


def _final_rule_set(
    schedule_ref: AccountFeeScheduleRef,
    maker: Rate,
    taker: Rate,
) -> FinalFeeRuleSet:
    rules = (
        FinalFeeChargeRule(
            source=FinalFeeRuleSource.MARKET_FEE,
            rule_id="binance-usdm-market-fee-not-applicable",
            basis_type=FeeBasisType.FILL,
            calculation_basis=FinalFeeCalculationBasis.NOTIONAL_RATE,
            applicability=FinalFeeApplicability.NOT_APPLICABLE,
            rate=Rate(0, _FEE_SCALE, "fee_fraction"),
            flat_amount=None,
            quantization=_FINAL_QUANTIZATION,
        ),
        FinalFeeChargeRule(
            source=FinalFeeRuleSource.TAX,
            rule_id="binance-usdm-tax-not-applicable",
            basis_type=FeeBasisType.FILL,
            calculation_basis=FinalFeeCalculationBasis.NOTIONAL_RATE,
            applicability=FinalFeeApplicability.NOT_APPLICABLE,
            rate=Rate(0, _FEE_SCALE, "fee_fraction"),
            flat_amount=None,
            quantization=_FINAL_QUANTIZATION,
        ),
        FinalFeeChargeRule(
            source=FinalFeeRuleSource.ACCOUNT_SCHEDULE,
            rule_id="binance-usdm-account-maker-commission",
            basis_type=FeeBasisType.FILL,
            calculation_basis=FinalFeeCalculationBasis.NOTIONAL_RATE,
            applicability=FinalFeeApplicability.MAKER_ONLY,
            rate=maker,
            flat_amount=None,
            quantization=_FINAL_QUANTIZATION,
        ),
        FinalFeeChargeRule(
            source=FinalFeeRuleSource.ACCOUNT_SCHEDULE,
            rule_id="binance-usdm-account-taker-commission",
            basis_type=FeeBasisType.FILL,
            calculation_basis=FinalFeeCalculationBasis.NOTIONAL_RATE,
            applicability=FinalFeeApplicability.TAKER_ONLY,
            rate=taker,
            flat_amount=None,
            quantization=_FINAL_QUANTIZATION,
        ),
    )
    return FinalFeeRuleSet.create(
        market_fee_policy_ref=_market_fee_ref(),
        tax_policy_ref=_tax_ref(),
        account_fee_schedule_ref=schedule_ref,
        assessment_currency=_USDT,
        assessment_scale=_FEE_SCALE,
        charge_rules=rules,
        minimums=(),
    )


@dataclass(frozen=True, slots=True)
class _ResolutionValues:
    active_band: BinanceUsdmAccountProfileBand
    leverage_evidence: LinearMarginLeverageEvidence
    account_fee_schedule_ref: AccountFeeScheduleRef
    fee_reservation_rule_set: FeeReservationRuleSet
    final_fee_rule_set: FinalFeeRuleSet


def _resolution_values(query: BinanceUsdmAccountProfileQuery) -> _ResolutionValues:
    band = _active_bands(query)[0]
    maker_value = _decimal(band.maker_commission_rate, signed=True)
    taker_value = _decimal(band.taker_commission_rate, signed=True)
    leverage = _leverage(band.leverage)
    if maker_value is None or taker_value is None or leverage is None:
        raise ValueError("account profile resolution requires validated values")
    maker = _rate(maker_value)
    taker = _rate(taker_value)
    symbol_ref = _source_ref(band, BinanceUsdmAccountSourceKind.SYMBOL_CONFIG)
    leverage_evidence = LinearMarginLeverageEvidence(
        account_id=query.account_id,
        instrument_id=band.instrument_id,
        selected_leverage=Rate(leverage, Scale(0), "notional_per_initial_margin"),
        effective_from=band.effective_from,
        effective_to_exclusive=band.effective_to_exclusive,
        available_at=band.available_at,
        source_key=symbol_ref.source_key,
        source_hash=symbol_ref.source_hash,
    )
    schedule_ref = _schedule_ref(query, band, maker, taker)
    return _ResolutionValues(
        active_band=band,
        leverage_evidence=leverage_evidence,
        account_fee_schedule_ref=schedule_ref,
        fee_reservation_rule_set=_reservation_rule_set(schedule_ref, maker, taker),
        final_fee_rule_set=_final_rule_set(schedule_ref, maker, taker),
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmAccountProfileResolution:
    model_key: str
    model_version: int
    model_digest: str
    query: BinanceUsdmAccountProfileQuery
    query_hash: str
    visible_bands: tuple[BinanceUsdmAccountProfileBand, ...]
    active_band: BinanceUsdmAccountProfileBand
    account_id: str
    account_scope: BinanceUsdmAccountProfileScope
    can_trade: bool
    position_mode: str
    asset_mode: str
    margin_type: str
    is_auto_add_margin: bool
    fee_burn: bool
    fee_tier: int
    trade_group_id: int
    leverage_evidence: LinearMarginLeverageEvidence
    account_fee_schedule_ref: AccountFeeScheduleRef
    fee_reservation_rule_set: FeeReservationRuleSet
    final_fee_rule_set: FinalFeeRuleSet
    reporting_currency_id: CurrencyId
    fee_currency_id: CurrencyId
    fee_scale: Scale
    fee_reserve_funding_source: FeeReserveFundingSource
    limitations: tuple[str, ...]
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmAccountProfileQuery:
            raise TypeError("query must be exact BinanceUsdmAccountProfileQuery")
        values = _resolution_values(self.query)
        expected = (
            _MODEL_KEY,
            _MODEL_VERSION,
            _model_digest(),
            self.query.query_hash,
            _visible_bands(self.query),
            values.active_band,
            self.query.account_id,
            BinanceUsdmAccountProfileScope.STANDARD_UM,
            True,
            "one_way",
            "single_asset",
            "CROSSED",
            False,
            False,
            values.active_band.fee_tier,
            values.active_band.trade_group_id,
            values.leverage_evidence,
            values.account_fee_schedule_ref,
            values.fee_reservation_rule_set,
            values.final_fee_rule_set,
            _USDT,
            _USDT,
            _FEE_SCALE,
            FeeReserveFundingSource.AVAILABLE_MARGIN,
            _LIMITATIONS,
            False,
        )
        actual = (
            self.model_key,
            self.model_version,
            self.model_digest,
            self.query_hash,
            self.visible_bands,
            self.active_band,
            self.account_id,
            self.account_scope,
            self.can_trade,
            self.position_mode,
            self.asset_mode,
            self.margin_type,
            self.is_auto_add_margin,
            self.fee_burn,
            self.fee_tier,
            self.trade_group_id,
            self.leverage_evidence,
            self.account_fee_schedule_ref,
            self.fee_reservation_rule_set,
            self.final_fee_rule_set,
            self.reporting_currency_id,
            self.fee_currency_id,
            self.fee_scale,
            self.fee_reserve_funding_source,
            self.limitations,
            self.decision_grade_eligible,
        )
        if actual != expected:
            raise ValueError("resolution fields do not match account profile authority")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "model_key": self.model_key,
            "model_version": self.model_version,
            "model_digest": self.model_digest,
            "query": self.query,
            "query_hash": self.query_hash,
            "visible_bands": list(self.visible_bands),
            "active_band": self.active_band,
            "account_id": self.account_id,
            "account_scope": self.account_scope.value,
            "can_trade": self.can_trade,
            "position_mode": self.position_mode,
            "asset_mode": self.asset_mode,
            "margin_type": self.margin_type,
            "is_auto_add_margin": self.is_auto_add_margin,
            "fee_burn": self.fee_burn,
            "fee_tier": self.fee_tier,
            "trade_group_id": self.trade_group_id,
            "leverage_evidence": self.leverage_evidence,
            "account_fee_schedule_ref": self.account_fee_schedule_ref,
            "fee_reservation_rule_set": self.fee_reservation_rule_set,
            "final_fee_rule_set": self.final_fee_rule_set,
            "reporting_currency_id": self.reporting_currency_id,
            "fee_currency_id": self.fee_currency_id,
            "fee_scale": self.fee_scale.places,
            "fee_reserve_funding_source": self.fee_reserve_funding_source.value,
            "limitations": list(self.limitations),
            "decision_grade_eligible": self.decision_grade_eligible,
        }

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_account_profile_resolution",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "resolution_hash": self.resolution_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmAccountProfileFailure:
    model_key: str
    model_version: int
    model_digest: str
    query: BinanceUsdmAccountProfileQuery
    query_hash: str
    code: BinanceUsdmAccountProfileFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmAccountProfileQuery:
            raise TypeError("query must be exact BinanceUsdmAccountProfileQuery")
        if type(self.code) is not BinanceUsdmAccountProfileFailureCode:
            raise TypeError("code must be exact BinanceUsdmAccountProfileFailureCode")
        expected_subjects = (
            self.code.value,
            self.query.account_id,
            str(self.query.account_profile_book.instrument_id),
            str(self.query.evaluated_at.epoch_nanoseconds),
            self.query.account_profile_book.account_profile_book_hash,
        )
        if (
            self.model_key != _MODEL_KEY
            or self.model_version != _MODEL_VERSION
            or self.model_digest != _model_digest()
            or self.query_hash != self.query.query_hash
            or self.code is not _first_failure(self.query)
            or self.subject_ids != expected_subjects
        ):
            raise ValueError("failure fields do not match account profile authority")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "model_key": self.model_key,
            "model_version": self.model_version,
            "model_digest": self.model_digest,
            "query": self.query,
            "query_hash": self.query_hash,
            "code": self.code.value,
            "subject_ids": list(self.subject_ids),
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_account_profile_failure",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "failure_hash": self.failure_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmAccountProfileOutcome:
    model_digest: str
    query_hash: str
    result: BinanceUsdmAccountProfileResolution | None
    failure: BinanceUsdmAccountProfileFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("account profile outcome requires exactly one authority")
        authority = self.result if self.result is not None else self.failure
        if authority is None:
            raise ValueError("account profile authority is missing")
        if (
            self.model_digest != _model_digest()
            or authority.model_digest != self.model_digest
            or self.query_hash != authority.query_hash
        ):
            raise ValueError("account profile outcome identity mismatch")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "model_digest": self.model_digest,
            "query_hash": self.query_hash,
            "result": self.result,
            "failure": self.failure,
        }

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_account_profile_outcome",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "outcome_hash": self.outcome_hash,
        }


class BinanceUsdmAccountProfileModel:
    @property
    def model_digest(self) -> str:
        return _model_digest()

    def resolve_account_profile(
        self,
        query: BinanceUsdmAccountProfileQuery,
        /,
    ) -> BinanceUsdmAccountProfileOutcome:
        if type(query) is not BinanceUsdmAccountProfileQuery:
            raise TypeError("query must be exact BinanceUsdmAccountProfileQuery")
        code = _first_failure(query)
        if code is not None:
            failure = BinanceUsdmAccountProfileFailure(
                model_key=_MODEL_KEY,
                model_version=_MODEL_VERSION,
                model_digest=_model_digest(),
                query=query,
                query_hash=query.query_hash,
                code=code,
                subject_ids=(
                    code.value,
                    query.account_id,
                    str(query.account_profile_book.instrument_id),
                    str(query.evaluated_at.epoch_nanoseconds),
                    query.account_profile_book.account_profile_book_hash,
                ),
            )
            return BinanceUsdmAccountProfileOutcome(
                model_digest=_model_digest(),
                query_hash=query.query_hash,
                result=None,
                failure=failure,
            )
        values = _resolution_values(query)
        result = BinanceUsdmAccountProfileResolution(
            model_key=_MODEL_KEY,
            model_version=_MODEL_VERSION,
            model_digest=_model_digest(),
            query=query,
            query_hash=query.query_hash,
            visible_bands=_visible_bands(query),
            active_band=values.active_band,
            account_id=query.account_id,
            account_scope=BinanceUsdmAccountProfileScope.STANDARD_UM,
            can_trade=True,
            position_mode="one_way",
            asset_mode="single_asset",
            margin_type="CROSSED",
            is_auto_add_margin=False,
            fee_burn=False,
            fee_tier=values.active_band.fee_tier,
            trade_group_id=values.active_band.trade_group_id,
            leverage_evidence=values.leverage_evidence,
            account_fee_schedule_ref=values.account_fee_schedule_ref,
            fee_reservation_rule_set=values.fee_reservation_rule_set,
            final_fee_rule_set=values.final_fee_rule_set,
            reporting_currency_id=_USDT,
            fee_currency_id=_USDT,
            fee_scale=_FEE_SCALE,
            fee_reserve_funding_source=FeeReserveFundingSource.AVAILABLE_MARGIN,
            limitations=_LIMITATIONS,
            decision_grade_eligible=False,
        )
        return BinanceUsdmAccountProfileOutcome(
            model_digest=_model_digest(),
            query_hash=query.query_hash,
            result=result,
            failure=None,
        )
