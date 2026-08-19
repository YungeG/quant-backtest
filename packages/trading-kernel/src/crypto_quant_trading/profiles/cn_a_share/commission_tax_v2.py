"""Finite XSHE route/product-aware A-share execution fee rules (v2)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, cast

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    FeeBasisType,
    Fill,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    Order,
    OrderIntent,
    OrderSide,
    Price,
    PriceConstraint,
    Quantity,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_sha256,
)

from crypto_quant_trading.fee_reservations import (
    FeeReservationApplicability,
    FeeReservationBasis,
    FeeReservationChargeRule,
    FeeReservationRuleSource,
)
from crypto_quant_trading.fees import (
    FinalFeeApplicability,
    FinalFeeCalculationBasis,
    FinalFeeChargeRule,
    FinalFeeRuleSource,
)
from crypto_quant_trading.ports import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)

from .commission_tax import (
    CnAShareFeeRuleSourceRef,
    CnAShareFeeTradeMechanism,
    CnAShareMarketFeeBand,
    CnAShareMarketFeeRuleBook,
    CnAShareStampDutyBand,
    CnAShareStampDutyRuleBook,
)

_MARKET_KEY = "equity.cn_a_share.cash.market-fees.route-product.v2"
_TAX_KEY = "equity.cn_a_share.cash.stamp-duty.route-product.v2"
_AUTHORITY_KEY = "equity.cn_a_share.cash.fee-execution-authority.route-product.v2"
_ZERO = Rate(0, Scale(0), "fee_fraction")
_SCALE = Scale(2)


class CnAShareExecutionAccessRoute(str, Enum):
    DOMESTIC = "domestic"
    NORTHBOUND_STOCK_CONNECT = "northbound_stock_connect"


class CnAShareFeeProductClass(str, Enum):
    ORDINARY_A_SHARE = "ordinary_a_share"
    PREFERRED_STOCK = "preferred_stock"
    ETF = "etf"


class CnAShareFeeAssessmentPurposeV2(str, Enum):
    RESERVATION = "reservation"
    FINAL_FILL = "final_fill"


def _enum_member(value: object, enum_type: type[Any], /) -> bool:
    return (
        issubclass(enum_type, Enum)
        and type(value) is enum_type
        and any(value is member for member in enum_type)
    )


def _text(name: str, value: object) -> None:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be canonical non-empty text")


def _hash(name: str, value: object) -> None:
    if (
        type(value) is not str
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(c not in "0123456789abcdef" for c in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _canonical_hash(value: object, /) -> bool:
    try:
        _hash("hash", value)
    except (TypeError, ValueError):
        return False
    return True


def _rate(name: str, value: object) -> None:
    if not _concrete_rate(value):
        raise TypeError(f"{name} must be concrete Rate")
    rate = cast(Rate, value)
    if rate.units < 0 or rate.basis != "fee_fraction":
        raise ValueError(f"{name} must be a non-negative fee_fraction")


def _sources(name: str, values: object) -> tuple[CnAShareFeeRuleSourceRef, ...]:
    if (
        type(values) is not tuple
        or not values
        or not all(
            type(x) is CnAShareFeeRuleSourceRef and _exact(x, CnAShareFeeRuleSourceRef)
            for x in values
        )
    ):
        raise TypeError(f"{name} must be a non-empty source-ref tuple")
    ordered = tuple(sorted(values, key=lambda x: (x.source_key, x.source_hash)))
    if ordered != values:
        raise ValueError(f"{name} must be canonical-sorted")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} contains duplicate source refs")
    return values


def _interval(effective_from: object, effective_to_exclusive: object) -> None:
    if not (
        _concrete_instant(effective_from) and _concrete_instant(effective_to_exclusive)
    ):
        raise TypeError("effective interval must use concrete UtcInstant")
    start = cast(UtcInstant, effective_from)
    stop = cast(UtcInstant, effective_to_exclusive)
    if start >= stop:
        raise ValueError("effective interval must be non-empty")


def _canonical(type_name: str, **fields: Any) -> dict[str, Any]:
    return {"type": type_name, "schema_version": 1, **fields}


def _exact(value: object, cls: type[Any], /) -> bool:
    """Reject object.__new__ values and subclasses at canonical boundaries."""
    if type(value) is not cls:
        return False
    try:
        rebuilt = cls(*(getattr(value, field.name) for field in fields(cls)))
    except (TypeError, ValueError, AttributeError):
        return False
    return rebuilt == value


def _concrete_venue(value: object) -> bool:
    return (
        type(value) is VenueId and type(value.value) is str and _exact(value, VenueId)
    )


def _concrete_instrument_id(value: object) -> bool:
    return (
        type(value) is InstrumentId
        and _concrete_venue(value.venue)
        and type(value.stable_key) is str
        and _exact(value, InstrumentId)
    )


def _concrete_currency(value: object) -> bool:
    return (
        type(value) is CurrencyId
        and type(value.value) is str
        and _exact(value, CurrencyId)
    )


def _concrete_scale(value: object) -> bool:
    return type(value) is Scale and type(value.places) is int and _exact(value, Scale)


def _concrete_rate(value: object) -> bool:
    return (
        type(value) is Rate
        and type(value.units) is int
        and type(value.basis) is str
        and _concrete_scale(value.scale)
        and _exact(value, Rate)
    )


def _concrete_money(value: object) -> bool:
    return (
        type(value) is Money
        and type(value.units) is int
        and type(value.currency) is str
        and _concrete_scale(value.scale)
        and _exact(value, Money)
    )


def _concrete_quantity(value: object) -> bool:
    return (
        type(value) is Quantity
        and type(value.units) is int
        and type(value.instrument_id) is str
        and _concrete_scale(value.scale)
        and _exact(value, Quantity)
    )


def _concrete_price(value: object) -> bool:
    return (
        type(value) is Price
        and type(value.units) is int
        and type(value.instrument_id) is str
        and type(value.quote_currency) is str
        and _concrete_scale(value.scale)
        and _exact(value, Price)
    )


def _concrete_domain_id(value: object) -> bool:
    return (
        type(value) is DomainId
        and _enum_member(value.kind, type(value.kind))
        and type(value.value) is str
        and _exact(value, DomainId)
    )


def _concrete_instant(value: object) -> bool:
    return (
        type(value) is UtcInstant
        and type(value.epoch_nanoseconds) is int
        and _exact(value, UtcInstant)
    )


def _concrete_instrument(value: object) -> bool:
    return (
        type(value) is InstrumentDefinition
        and _concrete_instrument_id(value.instrument_id)
        and _enum_member(value.instrument_type, InstrumentType)
        and (value.base_currency is None or _concrete_currency(value.base_currency))
        and _concrete_currency(value.quote_currency)
        and _concrete_currency(value.settlement_currency)
        and _exact(value, InstrumentDefinition)
    )


def _concrete_order(value: object) -> bool:
    if type(value) is not Order or type(value.intent) is not OrderIntent:
        return False
    intent = value.intent
    if not (
        _concrete_domain_id(value.order_id)
        and type(value.account_id) is str
        and _concrete_instrument_id(intent.instrument_id)
        and _enum_member(intent.side, OrderSide)
        and _concrete_quantity(intent.quantity)
        and _enum_member(intent.execution_style, type(intent.execution_style))
        and _enum_member(intent.time_in_force, type(intent.time_in_force))
        and type(intent.reduce_only) is bool
        and _enum_member(intent.position_effect, type(intent.position_effect))
        and type(intent.urgency) is str
        and type(intent.reason) is str
        and type(intent.parent_id) is str
        and (
            intent.price_constraint is None
            or type(intent.price_constraint) is PriceConstraint
        )
        and (
            intent.price_constraint is None
            or all(
                price is None or _concrete_price(price)
                for price in (
                    intent.price_constraint.limit_price,
                    intent.price_constraint.trigger_price,
                )
            )
        )
        and type(value.created_at) is SimulationInstant
        and _concrete_instant(value.created_at.instant)
        and type(value.created_at.phase) is TimelinePhase
        and type(value.created_at.phase.rank) is int
        and type(value.created_at.phase.code) is str
        and type(value.created_at.source_sequence) is SourceSequence
        and type(value.created_at.source_sequence.value) is int
        and _exact(value.created_at.phase, TimelinePhase)
        and _exact(value.created_at.source_sequence, SourceSequence)
    ):
        return False
    try:
        constraint = (
            None
            if intent.price_constraint is None
            else PriceConstraint(
                intent.price_constraint.limit_price,
                intent.price_constraint.trigger_price,
            )
        )
        rebuilt_intent = OrderIntent(
            intent.instrument_id,
            intent.side,
            intent.quantity,
            intent.execution_style,
            constraint,
            intent.time_in_force,
            intent.reduce_only,
            intent.position_effect,
            intent.urgency,
            intent.reason,
            intent.parent_id,
        )
        rebuilt_time = SimulationInstant(
            value.created_at.instant,
            value.created_at.phase,
            value.created_at.source_sequence,
        )
        return (
            Order(value.order_id, value.account_id, rebuilt_intent, rebuilt_time)
            == value
        )
    except (TypeError, ValueError, AttributeError):
        return False


def _concrete_fill(value: object) -> bool:
    if type(value) is not Fill:
        return False
    if not (
        _concrete_domain_id(value.fill_id)
        and _concrete_domain_id(value.order_id)
        and type(value.account_id) is str
        and _concrete_venue(value.venue_id)
        and _enum_member(value.side, OrderSide)
        and _concrete_instrument_id(value.instrument_id)
        and _concrete_quantity(value.quantity)
        and _concrete_price(value.reference_price)
        and _enum_member(
            value.reference_price_purpose, type(value.reference_price_purpose)
        )
        and _concrete_price(value.price)
        and _concrete_money(value.slippage_amount)
        and type(value.slippage_decision_id) is str
        and type(value.slippage_model_key) is str
        and (
            value.slippage_calibration_id is None
            or type(value.slippage_calibration_id) is str
        )
        and (value.liquidity is None or type(value.liquidity) is str)
        and _concrete_instant(value.execution_time)
    ):
        return False
    try:
        return Fill(*(getattr(value, field.name) for field in fields(Fill))) == value
    except (TypeError, ValueError, AttributeError):
        return False


def _concrete_quantization(value: object) -> bool:
    if not (
        type(value) is QuantizationPolicy
        and _concrete_scale(value.target_scale)
        and _enum_member(value.rounding, RoundingPolicy)
    ):
        return False
    try:
        _text("quantization version", value.version)
    except (TypeError, ValueError, AttributeError):
        return False
    return _exact(value, QuantizationPolicy)


def _concrete_reservation_rule(value: object) -> bool:
    if not (
        type(value) is FeeReservationChargeRule
        and _enum_member(value.source, FeeReservationRuleSource)
        and _enum_member(value.basis, FeeReservationBasis)
        and _enum_member(value.applicability, FeeReservationApplicability)
        and (value.rate is None or _concrete_rate(value.rate))
        and (value.flat_amount is None or _concrete_money(value.flat_amount))
        and _concrete_quantization(value.quantization)
    ):
        return False
    try:
        _text("reservation rule_id", value.rule_id)
    except (TypeError, ValueError, AttributeError):
        return False
    return _exact(value, FeeReservationChargeRule)


def _concrete_final_rule(value: object) -> bool:
    if not (
        type(value) is FinalFeeChargeRule
        and _enum_member(value.source, FinalFeeRuleSource)
        and _enum_member(value.basis_type, FeeBasisType)
        and _enum_member(value.calculation_basis, FinalFeeCalculationBasis)
        and _enum_member(value.applicability, FinalFeeApplicability)
        and (value.rate is None or _concrete_rate(value.rate))
        and (value.flat_amount is None or _concrete_money(value.flat_amount))
        and _concrete_quantization(value.quantization)
    ):
        return False
    try:
        _text("final rule_id", value.rule_id)
    except (TypeError, ValueError, AttributeError):
        return False
    return _exact(value, FinalFeeChargeRule)


@dataclass(frozen=True, slots=True)
class CnAShareFeeExecutionScopeV2:
    account_id: str
    venue_id: VenueId
    instrument: InstrumentDefinition
    instrument_id: InstrumentId
    instrument_type: InstrumentType
    quote_currency_id: CurrencyId
    settlement_currency_id: CurrencyId
    trade_mechanism: CnAShareFeeTradeMechanism
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    allowed_order_sides: tuple[OrderSide, ...]
    access_route: CnAShareExecutionAccessRoute
    fee_product_class: CnAShareFeeProductClass

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        if not _concrete_venue(self.venue_id) or self.venue_id != VenueId("xshe"):
            raise ValueError("scope venue_id must be XSHE")
        if not (
            _concrete_instrument(self.instrument)
            and _concrete_instrument_id(self.instrument_id)
        ):
            raise TypeError("scope instrument identity must be concrete")
        if (
            self.instrument.instrument_id != self.instrument_id
            or self.instrument_id.venue != self.venue_id
        ):
            raise ValueError("scope instrument identity mismatch")
        if self.instrument_type is not InstrumentType.EQUITY:
            raise ValueError("scope instrument_type must be EQUITY")
        if self.instrument.instrument_type is not self.instrument_type:
            raise ValueError("scope instrument_type mismatch")
        if not _concrete_currency(
            self.quote_currency_id
        ) or self.quote_currency_id != CurrencyId("CNY"):
            raise ValueError("scope quote_currency_id must be CNY")
        if not _concrete_currency(
            self.settlement_currency_id
        ) or self.settlement_currency_id != CurrencyId("CNY"):
            raise ValueError("scope settlement_currency_id must be CNY")
        if (
            self.instrument.quote_currency != self.quote_currency_id
            or self.instrument.settlement_currency != self.settlement_currency_id
        ):
            raise ValueError("scope currency identity mismatch")
        if self.trade_mechanism is not CnAShareFeeTradeMechanism.AUCTION:
            raise ValueError("scope trade_mechanism must be AUCTION")
        if (
            not _concrete_instant(self.coverage_from)
            or not _concrete_instant(self.coverage_to_exclusive)
            or self.coverage_from >= self.coverage_to_exclusive
        ):
            raise ValueError("scope coverage interval must be finite and non-empty")
        if type(self.allowed_order_sides) is not tuple or not all(
            _enum_member(side, OrderSide) for side in self.allowed_order_sides
        ):
            raise TypeError("allowed_order_sides must be an OrderSide tuple")
        if self.allowed_order_sides != tuple(
            sorted(self.allowed_order_sides, key=lambda x: x.value)
        ) or len(set(self.allowed_order_sides)) != len(self.allowed_order_sides):
            raise ValueError("allowed_order_sides must be canonical unique")
        if not _enum_member(
            self.access_route, CnAShareExecutionAccessRoute
        ) or not _enum_member(self.fee_product_class, CnAShareFeeProductClass):
            raise TypeError("scope route/product must be enums")

    @property
    def scope_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_execution_scope_v2",
            account_id=self.account_id,
            venue_id=self.venue_id,
            instrument=self.instrument,
            instrument_id=self.instrument_id,
            instrument_type=self.instrument_type.value,
            quote_currency_id=self.quote_currency_id,
            settlement_currency_id=self.settlement_currency_id,
            trade_mechanism=self.trade_mechanism.value,
            coverage_from=self.coverage_from,
            coverage_to_exclusive=self.coverage_to_exclusive,
            allowed_order_sides=tuple(x.value for x in self.allowed_order_sides),
            access_route=self.access_route.value,
            fee_product_class=self.fee_product_class.value,
        )


@dataclass(frozen=True, slots=True)
class CnAShareMarketFeeBandV2:
    venue_id: VenueId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    handling_applies: bool
    handling_rate: Rate
    handling_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]
    regulatory_applies: bool
    regulatory_rate: Rate
    regulatory_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]
    chinaclear_transfer_applies: bool
    chinaclear_transfer_rate: Rate
    chinaclear_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]
    hkscc_transfer_applies: bool
    hkscc_transfer_rate: Rate
    hkscc_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]

    def __post_init__(self) -> None:
        if not _concrete_venue(self.venue_id):
            raise TypeError("venue_id must be concrete VenueId")
        _interval(self.effective_from, self.effective_to_exclusive)
        for applies, rate, refs, name in (
            (
                self.handling_applies,
                self.handling_rate,
                self.handling_source_refs,
                "handling",
            ),
            (
                self.regulatory_applies,
                self.regulatory_rate,
                self.regulatory_source_refs,
                "regulatory",
            ),
            (
                self.chinaclear_transfer_applies,
                self.chinaclear_transfer_rate,
                self.chinaclear_transfer_source_refs,
                "chinaclear_transfer",
            ),
            (
                self.hkscc_transfer_applies,
                self.hkscc_transfer_rate,
                self.hkscc_transfer_source_refs,
                "hkscc_transfer",
            ),
        ):
            if type(applies) is not bool:
                raise TypeError(f"{name}_applies must be bool")
            _rate(f"{name}_rate", rate)
            _sources(f"{name}_source_refs", refs)
            if not applies and rate != _ZERO:
                raise ValueError(f"{name} false applicability requires zero rate")

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant < self.effective_to_exclusive

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_market_fee_band_v2",
            venue_id=self.venue_id,
            effective_from=self.effective_from,
            effective_to_exclusive=self.effective_to_exclusive,
            handling_applies=self.handling_applies,
            handling_rate=self.handling_rate,
            handling_source_refs=self.handling_source_refs,
            regulatory_applies=self.regulatory_applies,
            regulatory_rate=self.regulatory_rate,
            regulatory_source_refs=self.regulatory_source_refs,
            chinaclear_transfer_applies=self.chinaclear_transfer_applies,
            chinaclear_transfer_rate=self.chinaclear_transfer_rate,
            chinaclear_transfer_source_refs=self.chinaclear_transfer_source_refs,
            hkscc_transfer_applies=self.hkscc_transfer_applies,
            hkscc_transfer_rate=self.hkscc_transfer_rate,
            hkscc_transfer_source_refs=self.hkscc_transfer_source_refs,
        )


@dataclass(frozen=True, slots=True)
class CnAShareStampDutyBandV2:
    venue_id: VenueId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    applies_to_sell: bool
    rate: Rate
    source_refs: tuple[CnAShareFeeRuleSourceRef, ...]

    def __post_init__(self) -> None:
        if not _concrete_venue(self.venue_id):
            raise TypeError("venue_id must be concrete VenueId")
        _interval(self.effective_from, self.effective_to_exclusive)
        if type(self.applies_to_sell) is not bool:
            raise TypeError("applies_to_sell must be bool")
        _rate("rate", self.rate)
        _sources("source_refs", self.source_refs)
        if not self.applies_to_sell and self.rate != _ZERO:
            raise ValueError("false sell applicability requires zero rate")

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant < self.effective_to_exclusive

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_stamp_duty_band_v2",
            venue_id=self.venue_id,
            effective_from=self.effective_from,
            effective_to_exclusive=self.effective_to_exclusive,
            applies_to_sell=self.applies_to_sell,
            rate=self.rate,
            source_refs=self.source_refs,
        )


@dataclass(frozen=True, slots=True)
class CnAShareMarketFeeRuleBookV2:
    rule_book_key: str
    rule_book_version: int
    access_route: CnAShareExecutionAccessRoute
    fee_product_class: CnAShareFeeProductClass
    bands: tuple[CnAShareMarketFeeBandV2, ...]

    def __post_init__(self) -> None:
        _text("rule_book_key", self.rule_book_key)
        if type(self.rule_book_version) is not int or self.rule_book_version != 2:
            raise ValueError("rule_book_version must be 2")
        if not _enum_member(
            self.access_route, CnAShareExecutionAccessRoute
        ) or not _enum_member(self.fee_product_class, CnAShareFeeProductClass):
            raise TypeError("rule book route/product must be enums")
        if type(self.bands) is not tuple or not all(
            _concrete_market_band(band) for band in self.bands
        ):
            raise TypeError("bands must contain concrete CnAShareMarketFeeBandV2")
        if self.bands != tuple(
            sorted(
                self.bands,
                key=lambda x: (
                    x.venue_id.value,
                    x.effective_from,
                    x.effective_to_exclusive,
                    x.band_hash,
                ),
            )
        ):
            raise ValueError("bands must be canonical-sorted")

    @property
    def rule_book_hash(self) -> str:
        return canonical_sha256(self)

    def active_bands(
        self, venue: VenueId, instant: UtcInstant
    ) -> tuple[CnAShareMarketFeeBandV2, ...]:
        return tuple(
            x for x in self.bands if x.venue_id == venue and x.contains(instant)
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_market_fee_rule_book_v2",
            rule_book_key=self.rule_book_key,
            rule_book_version=self.rule_book_version,
            access_route=self.access_route.value,
            fee_product_class=self.fee_product_class.value,
            bands=self.bands,
        )


@dataclass(frozen=True, slots=True)
class CnAShareStampDutyRuleBookV2:
    rule_book_key: str
    rule_book_version: int
    access_route: CnAShareExecutionAccessRoute
    fee_product_class: CnAShareFeeProductClass
    bands: tuple[CnAShareStampDutyBandV2, ...]

    def __post_init__(self) -> None:
        _text("rule_book_key", self.rule_book_key)
        if type(self.rule_book_version) is not int or self.rule_book_version != 2:
            raise ValueError("rule_book_version must be 2")
        if not _enum_member(
            self.access_route, CnAShareExecutionAccessRoute
        ) or not _enum_member(self.fee_product_class, CnAShareFeeProductClass):
            raise TypeError("rule book route/product must be enums")
        if type(self.bands) is not tuple or not all(
            _concrete_stamp_band(band) for band in self.bands
        ):
            raise TypeError("bands must contain concrete CnAShareStampDutyBandV2")
        if self.bands != tuple(
            sorted(
                self.bands,
                key=lambda x: (
                    x.venue_id.value,
                    x.effective_from,
                    x.effective_to_exclusive,
                    x.band_hash,
                ),
            )
        ):
            raise ValueError("bands must be canonical-sorted")

    @property
    def rule_book_hash(self) -> str:
        return canonical_sha256(self)

    def active_bands(
        self, venue: VenueId, instant: UtcInstant
    ) -> tuple[CnAShareStampDutyBandV2, ...]:
        return tuple(
            x for x in self.bands if x.venue_id == venue and x.contains(instant)
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_stamp_duty_rule_book_v2",
            rule_book_key=self.rule_book_key,
            rule_book_version=self.rule_book_version,
            access_route=self.access_route.value,
            fee_product_class=self.fee_product_class.value,
            bands=self.bands,
        )


@dataclass(frozen=True, slots=True)
class CnAShareFeeExecutionSelectionV2:
    selection_key: str
    selection_version: int
    access_route: CnAShareExecutionAccessRoute
    fee_product_class: CnAShareFeeProductClass
    market_fee_rule_book: CnAShareMarketFeeRuleBookV2
    market_fee_rule_book_hash: str
    stamp_duty_rule_book: CnAShareStampDutyRuleBookV2
    stamp_duty_rule_book_hash: str
    market_fee_component_ref: ProfileComponentRef
    stamp_duty_component_ref: ProfileComponentRef

    def __post_init__(self) -> None:
        _text("selection_key", self.selection_key)
        if type(self.selection_version) is not int or self.selection_version <= 0:
            raise ValueError("selection_version must be positive")
        if not _enum_member(
            self.access_route, CnAShareExecutionAccessRoute
        ) or not _enum_member(self.fee_product_class, CnAShareFeeProductClass):
            raise TypeError("selection route/product must be enums")
        if not (
            _concrete_market_book(self.market_fee_rule_book)
            and _concrete_stamp_book(self.stamp_duty_rule_book)
        ):
            raise TypeError("selection rule books must be v2")
        _hash("market_fee_rule_book_hash", self.market_fee_rule_book_hash)
        _hash("stamp_duty_rule_book_hash", self.stamp_duty_rule_book_hash)
        if (
            self.market_fee_rule_book_hash != self.market_fee_rule_book.rule_book_hash
            or self.stamp_duty_rule_book_hash
            != self.stamp_duty_rule_book.rule_book_hash
        ):
            raise ValueError("selection rule book hash mismatch")
        if (
            not _concrete_component_ref(self.market_fee_component_ref)
            or self.market_fee_component_ref.port_type
            is not ProfilePortType.FEE_ASSESSMENT_POLICY
        ):
            raise TypeError("market_fee_component_ref must identify fee policy")
        if (
            not _concrete_component_ref(self.stamp_duty_component_ref)
            or self.stamp_duty_component_ref.port_type is not ProfilePortType.TAX_POLICY
        ):
            raise TypeError("stamp_duty_component_ref must identify tax policy")

    @property
    def selection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_execution_selection_v2",
            selection_key=self.selection_key,
            selection_version=self.selection_version,
            access_route=self.access_route.value,
            fee_product_class=self.fee_product_class.value,
            market_fee_rule_book=self.market_fee_rule_book,
            market_fee_rule_book_hash=self.market_fee_rule_book_hash,
            stamp_duty_rule_book=self.stamp_duty_rule_book,
            stamp_duty_rule_book_hash=self.stamp_duty_rule_book_hash,
            market_fee_component_ref=self.market_fee_component_ref,
            stamp_duty_component_ref=self.stamp_duty_component_ref,
        )


class CnAShareFeeExecutionAuthorityFailureCodeV2(str, Enum):
    SCOPE_SELECTION_MISMATCH = "scope_selection_mismatch"
    RULE_BOOK_SCOPE_MISMATCH = "rule_book_scope_mismatch"
    COMPONENT_REF_MISMATCH = "component_ref_mismatch"


@dataclass(frozen=True, slots=True)
class CnAShareFeeExecutionAuthorityFailureV2:
    scope: CnAShareFeeExecutionScopeV2
    scope_hash: str
    selection: CnAShareFeeExecutionSelectionV2
    selection_hash: str
    code: CnAShareFeeExecutionAuthorityFailureCodeV2
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            _reconstructed_scope(self.scope) is None
            or type(self.selection) is not CnAShareFeeExecutionSelectionV2
        ):
            raise TypeError("authority failure context invalid")
        try:
            selection_hash = canonical_sha256(self.selection)
        except (TypeError, ValueError, AttributeError) as error:
            raise TypeError("authority failure selection is not canonical") from error
        if self.selection_hash != selection_hash:
            raise ValueError("authority failure selection hash mismatch")
        _hash("scope_hash", self.scope_hash)
        _hash("selection_hash", self.selection_hash)
        if (
            self.scope_hash != self.scope.scope_hash
            or self.selection_hash != self.selection.selection_hash
        ):
            raise ValueError("authority failure hash mismatch")
        if (
            not _enum_member(self.code, CnAShareFeeExecutionAuthorityFailureCodeV2)
            or type(self.subject_ids) is not tuple
        ):
            raise TypeError("authority failure invalid")
        expected = _authority_failure_subjects(self.scope, self.selection, self.code)
        if self.subject_ids != expected:
            raise ValueError("authority failure subject_ids mismatch")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_execution_authority_failure_v2",
            scope=self.scope,
            scope_hash=self.scope_hash,
            selection=self.selection,
            selection_hash=self.selection_hash,
            code=self.code.value,
            subject_ids=self.subject_ids,
        )


@dataclass(frozen=True, slots=True)
class CnAShareFeeExecutionAuthorityV2:
    authority_key: str
    authority_version: int
    scope: CnAShareFeeExecutionScopeV2
    scope_hash: str
    selection: CnAShareFeeExecutionSelectionV2
    selection_hash: str
    access_route: CnAShareExecutionAccessRoute
    fee_product_class: CnAShareFeeProductClass
    market_fee_rule_book: CnAShareMarketFeeRuleBookV2
    market_fee_rule_book_hash: str
    stamp_duty_rule_book: CnAShareStampDutyRuleBookV2
    stamp_duty_rule_book_hash: str
    market_fee_component_ref: ProfileComponentRef
    stamp_duty_component_ref: ProfileComponentRef

    def __post_init__(self) -> None:
        _text("authority_key", self.authority_key)
        if (
            self.authority_key != _AUTHORITY_KEY
            or type(self.authority_version) is not int
            or self.authority_version != 2
        ):
            raise ValueError("authority identity mismatch")
        if (
            _reconstructed_scope(self.scope) is None
            or _reconstructed_selection(self.selection) is None
        ):
            raise TypeError("authority scope/selection invalid")
        _hash("scope_hash", self.scope_hash)
        _hash("selection_hash", self.selection_hash)
        _hash("market_fee_rule_book_hash", self.market_fee_rule_book_hash)
        _hash("stamp_duty_rule_book_hash", self.stamp_duty_rule_book_hash)
        if (self.scope_hash, self.selection_hash) != (
            self.scope.scope_hash,
            self.selection.selection_hash,
        ):
            raise ValueError("authority scope/selection hash mismatch")
        if (
            self.access_route,
            self.fee_product_class,
            self.market_fee_rule_book,
            self.market_fee_rule_book_hash,
            self.stamp_duty_rule_book,
            self.stamp_duty_rule_book_hash,
            self.market_fee_component_ref,
            self.stamp_duty_component_ref,
        ) != (
            self.selection.access_route,
            self.selection.fee_product_class,
            self.selection.market_fee_rule_book,
            self.selection.market_fee_rule_book_hash,
            self.selection.stamp_duty_rule_book,
            self.selection.stamp_duty_rule_book_hash,
            self.selection.market_fee_component_ref,
            self.selection.stamp_duty_component_ref,
        ):
            raise ValueError("authority selection mismatch")
        if (
            self.scope.access_route is not self.access_route
            or self.scope.fee_product_class is not self.fee_product_class
        ):
            raise ValueError("authority scope mismatch")
        if _authority_problem(self.scope, self.selection) is not None:
            raise ValueError("authority selection is not authorized for scope")

    @property
    def authority_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_execution_authority_v2",
            authority_key=self.authority_key,
            authority_version=self.authority_version,
            scope=self.scope,
            scope_hash=self.scope_hash,
            selection=self.selection,
            selection_hash=self.selection_hash,
            access_route=self.access_route.value,
            fee_product_class=self.fee_product_class.value,
            market_fee_rule_book=self.market_fee_rule_book,
            market_fee_rule_book_hash=self.market_fee_rule_book_hash,
            stamp_duty_rule_book=self.stamp_duty_rule_book,
            stamp_duty_rule_book_hash=self.stamp_duty_rule_book_hash,
            market_fee_component_ref=self.market_fee_component_ref,
            stamp_duty_component_ref=self.stamp_duty_component_ref,
        )


def _authority_failure_subjects(
    scope: CnAShareFeeExecutionScopeV2,
    selection: CnAShareFeeExecutionSelectionV2,
    code: CnAShareFeeExecutionAuthorityFailureCodeV2,
) -> tuple[str, ...]:
    prefix = (code.value, scope.scope_hash, selection.selection_hash)
    if code is CnAShareFeeExecutionAuthorityFailureCodeV2.SCOPE_SELECTION_MISMATCH:
        return (
            *prefix,
            "scope_access_route",
            scope.access_route.value,
            "selection_access_route",
            selection.access_route.value,
            "scope_fee_product_class",
            scope.fee_product_class.value,
            "selection_fee_product_class",
            selection.fee_product_class.value,
        )
    if code is CnAShareFeeExecutionAuthorityFailureCodeV2.RULE_BOOK_SCOPE_MISMATCH:
        return (
            *prefix,
            "market_fee_rule_book_hash",
            selection.market_fee_rule_book_hash,
            "stamp_duty_rule_book_hash",
            selection.stamp_duty_rule_book_hash,
            "scope_venue_id",
            scope.venue_id.value,
        )
    return (
        *prefix,
        "market_fee_component_digest",
        selection.market_fee_component_ref.component_digest,
        "stamp_duty_component_digest",
        selection.stamp_duty_component_ref.component_digest,
    )


def _authority_failure(
    scope: CnAShareFeeExecutionScopeV2,
    selection: CnAShareFeeExecutionSelectionV2,
    code: CnAShareFeeExecutionAuthorityFailureCodeV2,
    suffix: tuple[str, ...],
) -> CnAShareFeeExecutionAuthorityFailureV2:
    expected = _authority_failure_subjects(scope, selection, code)
    if suffix != expected[3:]:
        raise ValueError("authority failure suffix mismatch")
    return CnAShareFeeExecutionAuthorityFailureV2(
        scope, scope.scope_hash, selection, selection.selection_hash, code, expected
    )


def _concrete_source_ref(value: object) -> bool:
    return (
        type(value) is CnAShareFeeRuleSourceRef
        and type(value.source_key) is str
        and type(value.source_hash) is str
        and _exact(value, CnAShareFeeRuleSourceRef)
    )


def _concrete_market_band(value: object) -> bool:
    return (
        type(value) is CnAShareMarketFeeBandV2
        and _concrete_venue(value.venue_id)
        and _concrete_instant(value.effective_from)
        and _concrete_instant(value.effective_to_exclusive)
        and all(
            _concrete_rate(rate)
            and type(refs) is tuple
            and all(_concrete_source_ref(ref) for ref in refs)
            for rate, refs in (
                (value.handling_rate, value.handling_source_refs),
                (value.regulatory_rate, value.regulatory_source_refs),
                (value.chinaclear_transfer_rate, value.chinaclear_transfer_source_refs),
                (value.hkscc_transfer_rate, value.hkscc_transfer_source_refs),
            )
        )
        and _exact(value, CnAShareMarketFeeBandV2)
    )


def _concrete_stamp_band(value: object) -> bool:
    return (
        type(value) is CnAShareStampDutyBandV2
        and _concrete_venue(value.venue_id)
        and _concrete_instant(value.effective_from)
        and _concrete_instant(value.effective_to_exclusive)
        and _concrete_rate(value.rate)
        and type(value.source_refs) is tuple
        and all(_concrete_source_ref(ref) for ref in value.source_refs)
        and _exact(value, CnAShareStampDutyBandV2)
    )


def _concrete_market_book(value: object) -> bool:
    return (
        type(value) is CnAShareMarketFeeRuleBookV2
        and type(value.bands) is tuple
        and all(_concrete_market_band(band) for band in value.bands)
        and _exact(value, CnAShareMarketFeeRuleBookV2)
    )


def _concrete_stamp_book(value: object) -> bool:
    return (
        type(value) is CnAShareStampDutyRuleBookV2
        and type(value.bands) is tuple
        and all(_concrete_stamp_band(band) for band in value.bands)
        and _exact(value, CnAShareStampDutyRuleBookV2)
    )


def _concrete_component_ref(value: object) -> bool:
    return (
        type(value) is ProfileComponentRef
        and _enum_member(value.port_type, ProfilePortType)
        and type(value.component_key) is str
        and type(value.component_version) is int
        and type(value.component_digest) is str
        and _exact(value, ProfileComponentRef)
    )


def _reconstructed_scope(value: object) -> CnAShareFeeExecutionScopeV2 | None:
    if not (
        type(value) is CnAShareFeeExecutionScopeV2
        and _concrete_instrument(value.instrument)
        and _concrete_instrument_id(value.instrument_id)
        and _concrete_currency(value.quote_currency_id)
        and _concrete_currency(value.settlement_currency_id)
        and _concrete_instant(value.coverage_from)
        and _concrete_instant(value.coverage_to_exclusive)
        and type(value.allowed_order_sides) is tuple
        and all(_enum_member(side, OrderSide) for side in value.allowed_order_sides)
    ):
        return None
    return value if _exact(value, CnAShareFeeExecutionScopeV2) else None


def _reconstructed_selection(value: object) -> CnAShareFeeExecutionSelectionV2 | None:
    if not (
        type(value) is CnAShareFeeExecutionSelectionV2
        and _concrete_market_book(value.market_fee_rule_book)
        and _concrete_stamp_book(value.stamp_duty_rule_book)
        and _concrete_component_ref(value.market_fee_component_ref)
        and _concrete_component_ref(value.stamp_duty_component_ref)
    ):
        return None
    return value if _exact(value, CnAShareFeeExecutionSelectionV2) else None


def _authority_problem(
    scope: CnAShareFeeExecutionScopeV2,
    selection: CnAShareFeeExecutionSelectionV2,
) -> CnAShareFeeExecutionAuthorityFailureCodeV2 | None:
    # Route/product selection is the declared first semantic failure, before
    # structural/book validation of the selected payload.
    if (
        scope.access_route is not selection.access_route
        or scope.fee_product_class is not selection.fee_product_class
    ):
        return CnAShareFeeExecutionAuthorityFailureCodeV2.SCOPE_SELECTION_MISMATCH
    if (
        _reconstructed_scope(scope) is None
        or _reconstructed_selection(selection) is None
    ):
        return CnAShareFeeExecutionAuthorityFailureCodeV2.RULE_BOOK_SCOPE_MISMATCH
    if (
        selection.market_fee_rule_book.access_route is not scope.access_route
        or selection.market_fee_rule_book.fee_product_class
        is not scope.fee_product_class
        or selection.stamp_duty_rule_book.access_route is not scope.access_route
        or selection.stamp_duty_rule_book.fee_product_class
        is not scope.fee_product_class
        or any(
            band.venue_id != scope.venue_id
            for band in selection.market_fee_rule_book.bands
        )
        or any(
            band.venue_id != scope.venue_id
            for band in selection.stamp_duty_rule_book.bands
        )
    ):
        return CnAShareFeeExecutionAuthorityFailureCodeV2.RULE_BOOK_SCOPE_MISMATCH
    if selection.market_fee_component_ref != _market_component(
        selection.market_fee_rule_book
    ) or selection.stamp_duty_component_ref != _tax_component(
        selection.stamp_duty_rule_book
    ):
        return CnAShareFeeExecutionAuthorityFailureCodeV2.COMPONENT_REF_MISMATCH
    return None


def create_cn_a_share_fee_execution_authority_v2(
    scope: CnAShareFeeExecutionScopeV2, selection: CnAShareFeeExecutionSelectionV2, /
) -> CnAShareFeeExecutionAuthorityV2 | CnAShareFeeExecutionAuthorityFailureV2:
    if (
        type(scope) is not CnAShareFeeExecutionScopeV2
        or type(selection) is not CnAShareFeeExecutionSelectionV2
    ):
        raise TypeError("scope and selection must be v2")
    code = _authority_problem(scope, selection)
    if code is CnAShareFeeExecutionAuthorityFailureCodeV2.SCOPE_SELECTION_MISMATCH:
        return _authority_failure(
            scope,
            selection,
            code,
            (
                "scope_access_route",
                scope.access_route.value,
                "selection_access_route",
                selection.access_route.value,
                "scope_fee_product_class",
                scope.fee_product_class.value,
                "selection_fee_product_class",
                selection.fee_product_class.value,
            ),
        )
    if code is CnAShareFeeExecutionAuthorityFailureCodeV2.RULE_BOOK_SCOPE_MISMATCH:
        return _authority_failure(
            scope,
            selection,
            code,
            (
                "market_fee_rule_book_hash",
                selection.market_fee_rule_book_hash,
                "stamp_duty_rule_book_hash",
                selection.stamp_duty_rule_book_hash,
                "scope_venue_id",
                scope.venue_id.value,
            ),
        )
    if code is CnAShareFeeExecutionAuthorityFailureCodeV2.COMPONENT_REF_MISMATCH:
        return _authority_failure(
            scope,
            selection,
            code,
            (
                "market_fee_component_digest",
                selection.market_fee_component_ref.component_digest,
                "stamp_duty_component_digest",
                selection.stamp_duty_component_ref.component_digest,
            ),
        )
    return CnAShareFeeExecutionAuthorityV2(
        _AUTHORITY_KEY,
        2,
        scope,
        scope.scope_hash,
        selection,
        selection.selection_hash,
        scope.access_route,
        scope.fee_product_class,
        selection.market_fee_rule_book,
        selection.market_fee_rule_book_hash,
        selection.stamp_duty_rule_book,
        selection.stamp_duty_rule_book_hash,
        selection.market_fee_component_ref,
        selection.stamp_duty_component_ref,
    )


class CnAShareFeeExecutionBindingFailureCodeV2(str, Enum):
    AUTHORITY_SCOPE_MISMATCH = "authority_scope_mismatch"
    ORDER_ACCOUNT_MISMATCH = "order_account_mismatch"
    ORDER_VENUE_MISMATCH = "order_venue_mismatch"
    ORDER_INSTRUMENT_MISMATCH = "order_instrument_mismatch"
    ORDER_SIDE_MISMATCH = "order_side_mismatch"
    ORDER_CONTEXT_MISMATCH = "order_context_mismatch"


@dataclass(frozen=True, slots=True)
class CnAShareFeeExecutionBindingV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    order: Order
    order_hash: str
    order_id: DomainId
    account_id: str
    venue_id: VenueId
    instrument_id: InstrumentId
    side: OrderSide
    order_effective_at: UtcInstant

    def __post_init__(self) -> None:
        if (
            _reconstructed_authority(self.authority) is None
            or not _concrete_order(self.order)
            or not _concrete_domain_id(self.order_id)
            or not _concrete_venue(self.venue_id)
            or not _concrete_instrument_id(self.instrument_id)
            or not _enum_member(self.side, OrderSide)
            or not _concrete_instant(self.order_effective_at)
        ):
            raise TypeError("binding authority/order invalid")
        _text("account_id", self.account_id)
        _hash("authority_hash", self.authority_hash)
        _hash("order_hash", self.order_hash)
        if (
            self.authority_hash != self.authority.authority_hash
            or self.order_hash != canonical_sha256(self.order)
        ):
            raise ValueError("binding hash mismatch")
        if (
            self.order_id,
            self.account_id,
            self.venue_id,
            self.instrument_id,
            self.side,
            self.order_effective_at,
        ) != (
            self.order.order_id,
            self.order.account_id,
            self.order.intent.instrument_id.venue,
            self.order.intent.instrument_id,
            self.order.intent.side,
            self.order.created_at.instant,
        ):
            raise ValueError("binding order context mismatch")
        if _binding_problem(self.authority, self.order) is not None:
            raise ValueError("binding order does not match authority scope")

    @property
    def binding_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_execution_binding_v2",
            authority=self.authority,
            authority_hash=self.authority_hash,
            order=self.order,
            order_hash=self.order_hash,
            order_id=self.order_id,
            account_id=self.account_id,
            venue_id=self.venue_id,
            instrument_id=self.instrument_id,
            side=self.side.value,
            order_effective_at=self.order_effective_at,
        )


@dataclass(frozen=True, slots=True)
class CnAShareFeeExecutionBindingFailureV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    scope: CnAShareFeeExecutionScopeV2
    scope_hash: str
    order: Order
    order_hash: str
    code: CnAShareFeeExecutionBindingFailureCodeV2
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not _concrete_authority_context(self.authority)
            or _reconstructed_scope(self.scope) is None
            or self.scope != self.authority.scope
            or not _concrete_order(self.order)
        ):
            raise TypeError("binding failure context invalid")
        _hash("authority_hash", self.authority_hash)
        _hash("scope_hash", self.scope_hash)
        _hash("order_hash", self.order_hash)
        if (self.authority_hash, self.scope_hash, self.order_hash) != (
            self.authority.authority_hash,
            self.scope.scope_hash,
            canonical_sha256(self.order),
        ):
            raise ValueError("binding failure hash mismatch")
        if not _enum_member(self.code, CnAShareFeeExecutionBindingFailureCodeV2):
            raise TypeError("binding failure code invalid")
        if self.subject_ids != _binding_failure_subjects(
            self.authority, self.order, self.code
        ):
            raise ValueError("binding failure subject_ids mismatch")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_execution_binding_failure_v2",
            authority=self.authority,
            authority_hash=self.authority_hash,
            scope=self.scope,
            scope_hash=self.scope_hash,
            order=self.order,
            order_hash=self.order_hash,
            code=self.code.value,
            subject_ids=self.subject_ids,
        )


def _binding_failure_subjects(
    authority: CnAShareFeeExecutionAuthorityV2,
    order: Order,
    code: CnAShareFeeExecutionBindingFailureCodeV2,
) -> tuple[str, ...]:
    scope = authority.scope
    prefix = (
        code.value,
        authority.authority_hash,
        scope.scope_hash,
        canonical_sha256(order),
    )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.AUTHORITY_SCOPE_MISMATCH:
        return (
            *prefix,
            "authority_scope_hash",
            authority.scope_hash,
            "authority_selection_hash",
            authority.selection_hash,
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_ACCOUNT_MISMATCH:
        return (
            *prefix,
            "order_account_id",
            order.account_id,
            "scope_account_id",
            scope.account_id,
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_VENUE_MISMATCH:
        return (
            *prefix,
            "order_venue_id",
            order.intent.instrument_id.venue.value,
            "scope_venue_id",
            scope.venue_id.value,
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_INSTRUMENT_MISMATCH:
        return (
            *prefix,
            "order_instrument_id",
            str(order.intent.instrument_id),
            "scope_instrument_id",
            str(scope.instrument_id),
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_SIDE_MISMATCH:
        return (
            *prefix,
            "order_side",
            order.intent.side.value,
            "allowed_order_sides_hash",
            canonical_sha256(scope.allowed_order_sides),
        )
    return (
        *prefix,
        "order_created_at_hash",
        canonical_sha256(order.created_at.instant),
        "scope_coverage_from_hash",
        canonical_sha256(scope.coverage_from),
        "scope_coverage_to_exclusive_hash",
        canonical_sha256(scope.coverage_to_exclusive),
        "scope_trade_mechanism",
        scope.trade_mechanism.value,
    )


def _binding_failure(
    authority: CnAShareFeeExecutionAuthorityV2,
    order: Order,
    code: CnAShareFeeExecutionBindingFailureCodeV2,
    suffix: tuple[str, ...],
) -> CnAShareFeeExecutionBindingFailureV2:
    expected = _binding_failure_subjects(authority, order, code)
    if suffix != expected[4:]:
        raise ValueError("binding failure suffix mismatch")
    return CnAShareFeeExecutionBindingFailureV2(
        authority,
        authority.authority_hash,
        authority.scope,
        authority.scope_hash,
        order,
        canonical_sha256(order),
        code,
        expected,
    )


def _concrete_authority_context(value: object) -> bool:
    if not (
        type(value) is CnAShareFeeExecutionAuthorityV2
        and type(value.authority_key) is str
        and value.authority_key == _AUTHORITY_KEY
        and type(value.authority_version) is int
        and value.authority_version == 2
        and _reconstructed_scope(value.scope) is not None
        and _reconstructed_selection(value.selection) is not None
        and _concrete_market_book(value.market_fee_rule_book)
        and _concrete_stamp_book(value.stamp_duty_rule_book)
        and _concrete_component_ref(value.market_fee_component_ref)
        and _concrete_component_ref(value.stamp_duty_component_ref)
    ):
        return False
    try:
        for name in (
            "scope_hash",
            "selection_hash",
            "market_fee_rule_book_hash",
            "stamp_duty_rule_book_hash",
        ):
            _hash(name, getattr(value, name))
    except (TypeError, ValueError, AttributeError):
        return False
    return (
        value.scope_hash == value.scope.scope_hash
        and value.selection_hash == value.selection.selection_hash
        and value.market_fee_rule_book_hash == value.market_fee_rule_book.rule_book_hash
        and value.stamp_duty_rule_book_hash == value.stamp_duty_rule_book.rule_book_hash
        and (
            value.access_route,
            value.fee_product_class,
            value.market_fee_rule_book,
            value.market_fee_rule_book_hash,
            value.stamp_duty_rule_book,
            value.stamp_duty_rule_book_hash,
            value.market_fee_component_ref,
            value.stamp_duty_component_ref,
        )
        == (
            value.selection.access_route,
            value.selection.fee_product_class,
            value.selection.market_fee_rule_book,
            value.selection.market_fee_rule_book_hash,
            value.selection.stamp_duty_rule_book,
            value.selection.stamp_duty_rule_book_hash,
            value.selection.market_fee_component_ref,
            value.selection.stamp_duty_component_ref,
        )
    )


def _reconstructed_authority(value: object) -> CnAShareFeeExecutionAuthorityV2 | None:
    return (
        cast(CnAShareFeeExecutionAuthorityV2, value)
        if _concrete_authority_context(value)
        and _exact(value, CnAShareFeeExecutionAuthorityV2)
        else None
    )


def _binding_problem(
    authority: CnAShareFeeExecutionAuthorityV2, order: Order
) -> CnAShareFeeExecutionBindingFailureCodeV2 | None:
    scope = authority.scope
    if (
        _reconstructed_authority(authority) is None
        or authority.scope_hash != scope.scope_hash
        or authority.selection_hash != authority.selection.selection_hash
    ):
        return CnAShareFeeExecutionBindingFailureCodeV2.AUTHORITY_SCOPE_MISMATCH
    if order.account_id != scope.account_id:
        return CnAShareFeeExecutionBindingFailureCodeV2.ORDER_ACCOUNT_MISMATCH
    if order.intent.instrument_id.venue != scope.venue_id:
        return CnAShareFeeExecutionBindingFailureCodeV2.ORDER_VENUE_MISMATCH
    if order.intent.instrument_id != scope.instrument_id:
        return CnAShareFeeExecutionBindingFailureCodeV2.ORDER_INSTRUMENT_MISMATCH
    if order.intent.side not in scope.allowed_order_sides:
        return CnAShareFeeExecutionBindingFailureCodeV2.ORDER_SIDE_MISMATCH
    if (
        not scope.coverage_from
        <= order.created_at.instant
        < scope.coverage_to_exclusive
    ):
        return CnAShareFeeExecutionBindingFailureCodeV2.ORDER_CONTEXT_MISMATCH
    return None


def bind_cn_a_share_fee_execution_v2(
    authority: CnAShareFeeExecutionAuthorityV2, order: Order, /
) -> CnAShareFeeExecutionBindingV2 | CnAShareFeeExecutionBindingFailureV2:
    if not _concrete_authority_context(authority) or not _concrete_order(order):
        raise TypeError("authority and order must be concrete")
    scope = authority.scope
    code = _binding_problem(authority, order)
    if code is CnAShareFeeExecutionBindingFailureCodeV2.AUTHORITY_SCOPE_MISMATCH:
        return _binding_failure(
            authority,
            order,
            code,
            (
                "authority_scope_hash",
                authority.scope_hash,
                "authority_selection_hash",
                authority.selection_hash,
            ),
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_ACCOUNT_MISMATCH:
        return _binding_failure(
            authority,
            order,
            code,
            (
                "order_account_id",
                order.account_id,
                "scope_account_id",
                scope.account_id,
            ),
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_VENUE_MISMATCH:
        return _binding_failure(
            authority,
            order,
            code,
            (
                "order_venue_id",
                order.intent.instrument_id.venue.value,
                "scope_venue_id",
                scope.venue_id.value,
            ),
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_INSTRUMENT_MISMATCH:
        return _binding_failure(
            authority,
            order,
            code,
            (
                "order_instrument_id",
                str(order.intent.instrument_id),
                "scope_instrument_id",
                str(scope.instrument_id),
            ),
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_SIDE_MISMATCH:
        return _binding_failure(
            authority,
            order,
            code,
            (
                "order_side",
                order.intent.side.value,
                "allowed_order_sides_hash",
                canonical_sha256(scope.allowed_order_sides),
            ),
        )
    if code is CnAShareFeeExecutionBindingFailureCodeV2.ORDER_CONTEXT_MISMATCH:
        return _binding_failure(
            authority,
            order,
            code,
            (
                "order_created_at_hash",
                canonical_sha256(order.created_at.instant),
                "scope_coverage_from_hash",
                canonical_sha256(scope.coverage_from),
                "scope_coverage_to_exclusive_hash",
                canonical_sha256(scope.coverage_to_exclusive),
                "scope_trade_mechanism",
                scope.trade_mechanism.value,
            ),
        )
    return CnAShareFeeExecutionBindingV2(
        authority,
        authority.authority_hash,
        order,
        canonical_sha256(order),
        order.order_id,
        order.account_id,
        order.intent.instrument_id.venue,
        order.intent.instrument_id,
        order.intent.side,
        order.created_at.instant,
    )


def _concrete_binding_context(value: object) -> bool:
    if not (
        type(value) is CnAShareFeeExecutionBindingV2
        and _reconstructed_authority(value.authority) is not None
        and _concrete_order(value.order)
        and _concrete_domain_id(value.order_id)
        and type(value.account_id) is str
        and _concrete_venue(value.venue_id)
        and _concrete_instrument_id(value.instrument_id)
        and _enum_member(value.side, OrderSide)
        and _concrete_instant(value.order_effective_at)
    ):
        return False
    try:
        _text("account_id", value.account_id)
        _hash("authority_hash", value.authority_hash)
        _hash("order_hash", value.order_hash)
    except (TypeError, ValueError, AttributeError):
        return False
    return (
        value.authority_hash == value.authority.authority_hash
        and value.order_hash == canonical_sha256(value.order)
        and (
            value.order_id,
            value.account_id,
            value.venue_id,
            value.instrument_id,
            value.side,
        )
        == (
            value.order.order_id,
            value.order.account_id,
            value.order.intent.instrument_id.venue,
            value.order.intent.instrument_id,
            value.order.intent.side,
        )
    )


def _reconstructed_binding(value: object) -> CnAShareFeeExecutionBindingV2 | None:
    return (
        cast(CnAShareFeeExecutionBindingV2, value)
        if _concrete_binding_context(value)
        and _exact(value, CnAShareFeeExecutionBindingV2)
        else None
    )


class CnAShareFeeQueryConstructionFailureCodeV2(str, Enum):
    AUTHORITY_BINDING_MISMATCH = "authority_binding_mismatch"
    RESERVATION_CONTEXT_MISMATCH = "reservation_context_mismatch"
    MISSING_FILL = "missing_fill"
    FILL_ORDER_MISMATCH = "fill_order_mismatch"
    FILL_ACCOUNT_MISMATCH = "fill_account_mismatch"
    FILL_VENUE_MISMATCH = "fill_venue_mismatch"
    FILL_INSTRUMENT_MISMATCH = "fill_instrument_mismatch"
    FILL_SIDE_MISMATCH = "fill_side_mismatch"
    EXECUTION_TIME_MISMATCH = "execution_time_mismatch"


@dataclass(frozen=True, slots=True)
class CnAShareCashFeeRuleQueryV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    execution_binding: CnAShareFeeExecutionBindingV2
    binding_hash: str
    purpose: CnAShareFeeAssessmentPurposeV2
    fill: Fill | None
    fill_hash: str | None
    fill_id: DomainId | None

    def __post_init__(self) -> None:
        if (
            _reconstructed_authority(self.authority) is None
            or _reconstructed_binding(self.execution_binding) is None
        ):
            raise TypeError("query authority/binding invalid")
        _hash("authority_hash", self.authority_hash)
        _hash("binding_hash", self.binding_hash)
        if (
            self.authority_hash != self.authority.authority_hash
            or self.binding_hash != self.execution_binding.binding_hash
        ):
            raise ValueError("query authority/binding hash mismatch")
        if not _enum_member(self.purpose, CnAShareFeeAssessmentPurposeV2):
            raise TypeError("purpose must be CnAShareFeeAssessmentPurposeV2")
        if self.fill is None:
            if self.purpose is CnAShareFeeAssessmentPurposeV2.FINAL_FILL:
                raise ValueError("final fill query requires Fill")
            if self.fill_hash is not None or self.fill_id is not None:
                raise ValueError("missing Fill provenance mismatch")
        else:
            if self.fill_hash is None:
                raise ValueError("Fill provenance mismatch")
            _hash("fill_hash", self.fill_hash)
            if (
                not _concrete_fill(self.fill)
                or self.fill_hash != canonical_sha256(self.fill)
                or self.fill_id != self.fill.fill_id
            ):
                raise ValueError("Fill provenance mismatch")

    @property
    def order_id(self) -> DomainId:
        return self.execution_binding.order_id

    @property
    def order_hash(self) -> str:
        return self.execution_binding.order_hash

    @property
    def account_id(self) -> str:
        return self.execution_binding.account_id

    @property
    def venue_id(self) -> VenueId:
        return self.execution_binding.venue_id

    @property
    def instrument_id(self) -> InstrumentId:
        return self.execution_binding.instrument_id

    @property
    def side(self) -> OrderSide:
        return self.execution_binding.side

    @property
    def effective_at(self) -> UtcInstant:
        if self.purpose is CnAShareFeeAssessmentPurposeV2.RESERVATION:
            return self.execution_binding.order_effective_at
        if self.fill is None:
            raise ValueError("final fill query requires Fill")
        return self.fill.execution_time

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_cash_fee_rule_query_v2",
            authority=self.authority,
            authority_hash=self.authority_hash,
            execution_binding=self.execution_binding,
            binding_hash=self.binding_hash,
            purpose=self.purpose.value,
            fill=self.fill,
            fill_hash=self.fill_hash,
            fill_id=self.fill_id,
            order_id=self.order_id,
            order_hash=self.order_hash,
            account_id=self.account_id,
            venue_id=self.venue_id,
            instrument_id=self.instrument_id,
            side=self.side.value,
            effective_at=self.effective_at,
        )

    @classmethod
    def for_reservation(
        cls,
        authority: CnAShareFeeExecutionAuthorityV2,
        execution_binding: CnAShareFeeExecutionBindingV2,
        /,
    ) -> CnAShareCashFeeRuleQueryV2 | CnAShareFeeQueryConstructionFailureV2:
        return _construct_query(
            authority,
            execution_binding,
            CnAShareFeeAssessmentPurposeV2.RESERVATION,
            None,
        )

    @classmethod
    def for_final_fill(
        cls,
        authority: CnAShareFeeExecutionAuthorityV2,
        execution_binding: CnAShareFeeExecutionBindingV2,
        fill: Fill | None,
        /,
    ) -> CnAShareCashFeeRuleQueryV2 | CnAShareFeeQueryConstructionFailureV2:
        return _construct_query(
            authority,
            execution_binding,
            CnAShareFeeAssessmentPurposeV2.FINAL_FILL,
            fill,
        )


@dataclass(frozen=True, slots=True)
class CnAShareFeeQueryConstructionFailureV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    execution_binding: CnAShareFeeExecutionBindingV2
    binding_hash: str
    purpose: CnAShareFeeAssessmentPurposeV2
    fill: Fill | None
    fill_hash: str | None
    code: CnAShareFeeQueryConstructionFailureCodeV2
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            _reconstructed_authority(self.authority) is None
            or not _concrete_binding_context(self.execution_binding)
            or not _enum_member(self.purpose, CnAShareFeeAssessmentPurposeV2)
            or not _enum_member(self.code, CnAShareFeeQueryConstructionFailureCodeV2)
        ):
            raise TypeError("query failure context invalid")
        _hash("authority_hash", self.authority_hash)
        _hash("binding_hash", self.binding_hash)
        if self.fill_hash is not None:
            _hash("fill_hash", self.fill_hash)
        if (self.authority_hash, self.binding_hash) != (
            self.authority.authority_hash,
            self.execution_binding.binding_hash,
        ):
            raise ValueError("query failure hash mismatch")
        if self.fill is None:
            if self.fill_hash is not None:
                raise ValueError("missing fill hash mismatch")
        elif not _concrete_fill(self.fill) or self.fill_hash != canonical_sha256(
            self.fill
        ):
            raise ValueError("fill hash mismatch")
        if self.subject_ids != _query_failure_subjects(
            self.authority, self.execution_binding, self.purpose, self.fill, self.code
        ):
            raise ValueError("query failure subject_ids mismatch")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_query_construction_failure_v2",
            authority=self.authority,
            authority_hash=self.authority_hash,
            execution_binding=self.execution_binding,
            binding_hash=self.binding_hash,
            purpose=self.purpose.value,
            fill=self.fill,
            fill_hash=self.fill_hash,
            code=self.code.value,
            subject_ids=self.subject_ids,
        )


def _query_failure_subjects(
    authority: CnAShareFeeExecutionAuthorityV2,
    binding: CnAShareFeeExecutionBindingV2,
    purpose: CnAShareFeeAssessmentPurposeV2,
    fill: Fill | None,
    code: CnAShareFeeQueryConstructionFailureCodeV2,
) -> tuple[str, ...]:
    fill_hash = None if fill is None else canonical_sha256(fill)
    prefix = (
        code.value,
        authority.authority_hash,
        binding.binding_hash,
        purpose.value,
        fill_hash or "none",
    )
    if code is CnAShareFeeQueryConstructionFailureCodeV2.AUTHORITY_BINDING_MISMATCH:
        return (*prefix, "binding_authority_hash", binding.authority_hash)
    if code is CnAShareFeeQueryConstructionFailureCodeV2.RESERVATION_CONTEXT_MISMATCH:
        return (
            *prefix,
            "order_id",
            binding.order_id.value,
            "order_hash",
            binding.order_hash,
            "order_effective_at_hash",
            canonical_sha256(binding.order_effective_at),
        )
    if code is CnAShareFeeQueryConstructionFailureCodeV2.MISSING_FILL:
        return (*prefix, "fill", "none")
    if fill is None:
        raise ValueError("fill is required for fill failure")
    if code is CnAShareFeeQueryConstructionFailureCodeV2.FILL_ORDER_MISMATCH:
        return (
            *prefix,
            "fill_order_id",
            fill.order_id.value,
            "binding_order_id",
            binding.order_id.value,
        )
    if code is CnAShareFeeQueryConstructionFailureCodeV2.FILL_ACCOUNT_MISMATCH:
        return (
            *prefix,
            "fill_account_id",
            fill.account_id,
            "binding_account_id",
            binding.account_id,
        )
    if code is CnAShareFeeQueryConstructionFailureCodeV2.FILL_VENUE_MISMATCH:
        return (
            *prefix,
            "fill_venue_id",
            fill.venue_id.value,
            "binding_venue_id",
            binding.venue_id.value,
        )
    if code is CnAShareFeeQueryConstructionFailureCodeV2.FILL_INSTRUMENT_MISMATCH:
        return (
            *prefix,
            "fill_instrument_id",
            str(fill.instrument_id),
            "binding_instrument_id",
            str(binding.instrument_id),
        )
    if code is CnAShareFeeQueryConstructionFailureCodeV2.FILL_SIDE_MISMATCH:
        return (
            *prefix,
            "fill_side",
            fill.side.value,
            "binding_side",
            binding.side.value,
        )
    return (
        *prefix,
        "fill_execution_time_hash",
        canonical_sha256(fill.execution_time),
        "binding_order_effective_at_hash",
        canonical_sha256(binding.order_effective_at),
        "scope_coverage_to_exclusive_hash",
        canonical_sha256(authority.scope.coverage_to_exclusive),
    )


def _query_failure(
    authority: CnAShareFeeExecutionAuthorityV2,
    binding: CnAShareFeeExecutionBindingV2,
    purpose: CnAShareFeeAssessmentPurposeV2,
    fill: Fill | None,
    code: CnAShareFeeQueryConstructionFailureCodeV2,
    suffix: tuple[str, ...],
) -> CnAShareFeeQueryConstructionFailureV2:
    fill_hash = None if fill is None else canonical_sha256(fill)
    expected = _query_failure_subjects(authority, binding, purpose, fill, code)
    if suffix != expected[5:]:
        raise ValueError("query failure suffix mismatch")
    return CnAShareFeeQueryConstructionFailureV2(
        authority,
        authority.authority_hash,
        binding,
        binding.binding_hash,
        purpose,
        fill,
        fill_hash,
        code,
        expected,
    )


def _construct_query(
    authority: CnAShareFeeExecutionAuthorityV2,
    binding: CnAShareFeeExecutionBindingV2,
    purpose: CnAShareFeeAssessmentPurposeV2,
    fill: Fill | None,
) -> CnAShareCashFeeRuleQueryV2 | CnAShareFeeQueryConstructionFailureV2:
    if _reconstructed_authority(authority) is None or not _concrete_binding_context(
        binding
    ):
        raise TypeError("authority and execution_binding must be concrete v2")
    if fill is not None and not _concrete_fill(fill):
        raise TypeError("fill must be concrete Fill or None")
    rebuilt_binding = bind_cn_a_share_fee_execution_v2(authority, binding.order)
    if (
        binding.authority != authority
        or binding.authority_hash != authority.authority_hash
    ):
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.AUTHORITY_BINDING_MISMATCH,
            ("binding_authority_hash", binding.authority_hash),
        )
    if purpose is CnAShareFeeAssessmentPurposeV2.RESERVATION:
        if binding.order_effective_at != binding.order.created_at.instant:
            return _query_failure(
                authority,
                binding,
                purpose,
                None,
                CnAShareFeeQueryConstructionFailureCodeV2.RESERVATION_CONTEXT_MISMATCH,
                (
                    "order_id",
                    binding.order_id.value,
                    "order_hash",
                    binding.order_hash,
                    "order_effective_at_hash",
                    canonical_sha256(binding.order_effective_at),
                ),
            )
        if (
            type(rebuilt_binding) is not CnAShareFeeExecutionBindingV2
            or rebuilt_binding != binding
            or rebuilt_binding.binding_hash != binding.binding_hash
        ):
            return _query_failure(
                authority,
                binding,
                purpose,
                None,
                CnAShareFeeQueryConstructionFailureCodeV2.AUTHORITY_BINDING_MISMATCH,
                ("binding_authority_hash", binding.authority_hash),
            )
        return CnAShareCashFeeRuleQueryV2(
            authority,
            authority.authority_hash,
            binding,
            binding.binding_hash,
            purpose,
            None,
            None,
            None,
        )
    if (
        type(rebuilt_binding) is not CnAShareFeeExecutionBindingV2
        or rebuilt_binding != binding
        or rebuilt_binding.binding_hash != binding.binding_hash
    ):
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.AUTHORITY_BINDING_MISMATCH,
            ("binding_authority_hash", binding.authority_hash),
        )
    if fill is None:
        return _query_failure(
            authority,
            binding,
            purpose,
            None,
            CnAShareFeeQueryConstructionFailureCodeV2.MISSING_FILL,
            ("fill", "none"),
        )
    if type(fill) is not Fill:
        raise TypeError("fill must be concrete Fill or None")
    if fill.order_id != binding.order_id:
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.FILL_ORDER_MISMATCH,
            (
                "fill_order_id",
                fill.order_id.value,
                "binding_order_id",
                binding.order_id.value,
            ),
        )
    if fill.account_id != binding.account_id:
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.FILL_ACCOUNT_MISMATCH,
            (
                "fill_account_id",
                fill.account_id,
                "binding_account_id",
                binding.account_id,
            ),
        )
    if fill.venue_id != binding.venue_id:
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.FILL_VENUE_MISMATCH,
            (
                "fill_venue_id",
                fill.venue_id.value,
                "binding_venue_id",
                binding.venue_id.value,
            ),
        )
    if fill.instrument_id != binding.instrument_id:
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.FILL_INSTRUMENT_MISMATCH,
            (
                "fill_instrument_id",
                str(fill.instrument_id),
                "binding_instrument_id",
                str(binding.instrument_id),
            ),
        )
    if fill.side is not binding.side:
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.FILL_SIDE_MISMATCH,
            ("fill_side", fill.side.value, "binding_side", binding.side.value),
        )
    if (
        not binding.order_effective_at
        <= fill.execution_time
        < authority.scope.coverage_to_exclusive
    ):
        return _query_failure(
            authority,
            binding,
            purpose,
            fill,
            CnAShareFeeQueryConstructionFailureCodeV2.EXECUTION_TIME_MISMATCH,
            (
                "fill_execution_time_hash",
                canonical_sha256(fill.execution_time),
                "binding_order_effective_at_hash",
                canonical_sha256(binding.order_effective_at),
                "scope_coverage_to_exclusive_hash",
                canonical_sha256(authority.scope.coverage_to_exclusive),
            ),
        )
    return CnAShareCashFeeRuleQueryV2(
        authority,
        authority.authority_hash,
        binding,
        binding.binding_hash,
        purpose,
        fill,
        canonical_sha256(fill),
        fill.fill_id,
    )


def _reconstructed_query(value: object) -> CnAShareCashFeeRuleQueryV2 | None:
    if not (
        type(value) is CnAShareCashFeeRuleQueryV2
        and _reconstructed_authority(value.authority) is not None
        and _reconstructed_binding(value.execution_binding) is not None
        and (value.fill is None or _concrete_fill(value.fill))
    ):
        return None
    try:
        rebuilt = (
            CnAShareCashFeeRuleQueryV2.for_reservation(
                value.authority, value.execution_binding
            )
            if value.purpose is CnAShareFeeAssessmentPurposeV2.RESERVATION
            else CnAShareCashFeeRuleQueryV2.for_final_fill(
                value.authority, value.execution_binding, value.fill
            )
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if type(rebuilt) is CnAShareCashFeeRuleQueryV2
        and rebuilt == value
        and rebuilt.query_hash == value.query_hash
        else None
    )


class CnAShareFeeRuleFailureCodeV2(str, Enum):
    EXECUTION_AUTHORITY_MISMATCH = "execution_authority_mismatch"
    QUERY_PROVENANCE_MISMATCH = "query_provenance_mismatch"
    RULE_BOOK_SCOPE_MISMATCH = "rule_book_scope_mismatch"
    MISSING_RULE_INTERVAL = "missing_rule_interval"
    OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"


@dataclass(frozen=True, slots=True)
class CnAShareFeeRuleFailureV2:
    query: CnAShareCashFeeRuleQueryV2
    query_hash: str
    code: CnAShareFeeRuleFailureCodeV2
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _hash("query_hash", self.query_hash)
        if (
            not _concrete_query_context(self.query)
            or self.query_hash != self.query.query_hash
            or not _enum_member(self.code, CnAShareFeeRuleFailureCodeV2)
            or type(self.subject_ids) is not tuple
            or not _valid_rule_failure_subjects(self.query, self.code, self.subject_ids)
        ):
            raise ValueError("fee rule failure invalid")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_rule_failure_v2",
            query=self.query,
            query_hash=self.query_hash,
            code=self.code.value,
            subject_ids=self.subject_ids,
        )


def _active_market_bands(
    book: CnAShareMarketFeeRuleBookV2, venue: VenueId, instant: UtcInstant, /
) -> tuple[CnAShareMarketFeeBandV2, ...]:
    if not (
        _concrete_market_book(book)
        and _concrete_venue(venue)
        and _concrete_instant(instant)
    ):
        raise TypeError("market rule book context must be concrete")
    return tuple(
        band
        for band in book.bands
        if band.venue_id == venue
        and band.effective_from <= instant < band.effective_to_exclusive
    )


def _active_stamp_bands(
    book: CnAShareStampDutyRuleBookV2, venue: VenueId, instant: UtcInstant, /
) -> tuple[CnAShareStampDutyBandV2, ...]:
    if not (
        _concrete_stamp_book(book)
        and _concrete_venue(venue)
        and _concrete_instant(instant)
    ):
        raise TypeError("stamp rule book context must be concrete")
    return tuple(
        band
        for band in book.bands
        if band.venue_id == venue
        and band.effective_from <= instant < band.effective_to_exclusive
    )


def _concrete_query_context(value: object) -> bool:
    if not (
        type(value) is CnAShareCashFeeRuleQueryV2
        and _reconstructed_authority(value.authority) is not None
        and _concrete_binding_context(value.execution_binding)
        and _enum_member(value.purpose, CnAShareFeeAssessmentPurposeV2)
        and (value.fill is None or _concrete_fill(value.fill))
        and (value.fill_id is None or _concrete_domain_id(value.fill_id))
        and not (
            value.purpose is CnAShareFeeAssessmentPurposeV2.FINAL_FILL
            and value.fill is None
        )
    ):
        return False
    try:
        _hash("authority_hash", value.authority_hash)
        _hash("binding_hash", value.binding_hash)
        if value.fill_hash is not None:
            _hash("fill_hash", value.fill_hash)
        canonical_sha256(value)
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _valid_rule_failure_subjects(
    query: CnAShareCashFeeRuleQueryV2,
    code: CnAShareFeeRuleFailureCodeV2,
    subjects: tuple[str, ...],
) -> bool:
    if (
        len(subjects) < 3
        or subjects[0] != code.value
        or subjects[2] != query.query_hash
    ):
        return False
    suffix = subjects[3:]
    if code is CnAShareFeeRuleFailureCodeV2.EXECUTION_AUTHORITY_MISMATCH:
        if (
            len(suffix) != 8
            or suffix[:2] != ("query_authority_hash", query.authority_hash)
            or suffix[2] != "policy_authority_hash"
            or subjects[1] != suffix[3]
            or suffix[4:7]
            != ("query_scope_hash", query.authority.scope_hash, "policy_scope_hash")
        ):
            return False
        try:
            _hash("policy_authority_hash", suffix[3])
            _hash("policy_scope_hash", suffix[7])
        except (TypeError, ValueError):
            return False
        return True
    if subjects[1] != query.authority_hash:
        return False
    if code is CnAShareFeeRuleFailureCodeV2.RULE_BOOK_SCOPE_MISMATCH:
        return suffix == (
            "scope_hash",
            query.authority.scope_hash,
            "market_fee_rule_book_hash",
            query.authority.market_fee_rule_book_hash,
            "stamp_duty_rule_book_hash",
            query.authority.stamp_duty_rule_book_hash,
        )
    if code is CnAShareFeeRuleFailureCodeV2.QUERY_PROVENANCE_MISMATCH:
        rebuilt = _provenance(query)
        expected = (
            (
                "purpose",
                query.purpose.value,
                "reconstructed_query_hash",
                rebuilt.query_hash,
            )
            if type(rebuilt) is CnAShareCashFeeRuleQueryV2
            else (
                "purpose",
                query.purpose.value,
                "query_construction_failure_hash",
                cast(CnAShareFeeQueryConstructionFailureV2, rebuilt).failure_hash,
            )
        )
        return suffix == expected
    if (
        len(suffix) != 8
        or suffix[:2] != ("venue_id", query.venue_id.value)
        or suffix[2:4] != ("effective_at_hash", canonical_sha256(query.effective_at))
        or suffix[4] != "rule_book_hash"
        or suffix[6] != "active_band_hashes_hash"
    ):
        return False
    if suffix[5] == query.authority.market_fee_rule_book_hash:
        active = _active_market_bands(
            query.authority.market_fee_rule_book, query.venue_id, query.effective_at
        )
    elif suffix[5] == query.authority.stamp_duty_rule_book_hash:
        active = _active_stamp_bands(
            query.authority.stamp_duty_rule_book, query.venue_id, query.effective_at
        )
    else:
        return False
    expected = (
        canonical_sha256(())
        if code is CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL
        else canonical_sha256(tuple(sorted(band.band_hash for band in active)))
    )
    return (
        not active
        if code is CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL
        else len(active) > 1
    ) and suffix[7] == expected


def _market_component(book: CnAShareMarketFeeRuleBookV2) -> ProfileComponentRef:
    body = _canonical(
        "cn_a_share_cash_market_fee_component_v2",
        component_key=_MARKET_KEY,
        component_version=2,
        algorithm_key="cn-a-share-historical-market-fees-route-product-v2",
        rule_book_hash=book.rule_book_hash,
        access_route=book.access_route.value,
        fee_product_class=book.fee_product_class.value,
        assessment_scale=2,
        rounding="half_up",
        quantization_version="cn-a-share-market-fee.cny-cent.half-up.v2",
    )
    return ProfileComponentRef(
        ProfilePortType.FEE_ASSESSMENT_POLICY, _MARKET_KEY, 2, canonical_sha256(body)
    )


def _tax_component(book: CnAShareStampDutyRuleBookV2) -> ProfileComponentRef:
    body = _canonical(
        "cn_a_share_cash_stamp_duty_component_v2",
        component_key=_TAX_KEY,
        component_version=2,
        algorithm_key="cn-a-share-historical-stamp-duty-route-product-v2",
        rule_book_hash=book.rule_book_hash,
        access_route=book.access_route.value,
        fee_product_class=book.fee_product_class.value,
        assessment_scale=2,
        rounding="half_up",
        quantization_version="cn-a-share-stamp-duty.cny-cent.half-up.v2",
    )
    return ProfileComponentRef(
        ProfilePortType.TAX_POLICY, _TAX_KEY, 2, canonical_sha256(body)
    )


def _failure(
    query: CnAShareCashFeeRuleQueryV2,
    code: CnAShareFeeRuleFailureCodeV2,
    suffix: tuple[str, ...],
    policy_authority_hash: str | None = None,
) -> CnAShareFeeRuleFailureV2:
    return CnAShareFeeRuleFailureV2(
        query,
        query.query_hash,
        code,
        (
            code.value,
            policy_authority_hash or query.authority_hash,
            query.query_hash,
            *suffix,
        ),
    )


def _provenance(
    query: CnAShareCashFeeRuleQueryV2,
) -> CnAShareCashFeeRuleQueryV2 | CnAShareFeeQueryConstructionFailureV2:
    if query.purpose is CnAShareFeeAssessmentPurposeV2.RESERVATION:
        return CnAShareCashFeeRuleQueryV2.for_reservation(
            query.authority, query.execution_binding
        )
    return CnAShareCashFeeRuleQueryV2.for_final_fill(
        query.authority, query.execution_binding, query.fill
    )


def _policy_failure(
    policy: Any, query: CnAShareCashFeeRuleQueryV2, book: Any
) -> CnAShareFeeRuleFailureV2 | None:
    if (
        query.authority != policy.authority
        or query.authority_hash != policy.authority_hash
    ):
        return _failure(
            query,
            CnAShareFeeRuleFailureCodeV2.EXECUTION_AUTHORITY_MISMATCH,
            (
                "query_authority_hash",
                query.authority_hash,
                "policy_authority_hash",
                policy.authority_hash,
                "query_scope_hash",
                query.authority.scope_hash,
                "policy_scope_hash",
                policy.authority.scope_hash,
            ),
            policy.authority_hash,
        )
    reconstructed = _provenance(query)
    if (
        type(reconstructed) is not CnAShareCashFeeRuleQueryV2
        or reconstructed != query
        or reconstructed.query_hash != query.query_hash
    ):
        suffix = (
            (
                "purpose",
                query.purpose.value,
                "reconstructed_query_hash",
                reconstructed.query_hash,
            )
            if type(reconstructed) is CnAShareCashFeeRuleQueryV2
            else (
                "purpose",
                query.purpose.value,
                "query_construction_failure_hash",
                cast(CnAShareFeeQueryConstructionFailureV2, reconstructed).failure_hash,
            )
        )
        return _failure(
            query, CnAShareFeeRuleFailureCodeV2.QUERY_PROVENANCE_MISMATCH, suffix
        )
    if (
        book.access_route is not query.authority.access_route
        or book.fee_product_class is not query.authority.fee_product_class
    ):
        return _failure(
            query,
            CnAShareFeeRuleFailureCodeV2.RULE_BOOK_SCOPE_MISMATCH,
            (
                "scope_hash",
                query.authority.scope_hash,
                "market_fee_rule_book_hash",
                query.authority.market_fee_rule_book_hash,
                "stamp_duty_rule_book_hash",
                query.authority.stamp_duty_rule_book_hash,
            ),
        )
    return None


def _generated_id(
    tag: str,
    rule_type: str,
    component: ProfileComponentRef,
    book_hash: str,
    band_hash: str,
    query: CnAShareCashFeeRuleQueryV2,
    charge_key: str,
    purpose: str,
    basis_type: str,
    applies: bool,
    refs: tuple[CnAShareFeeRuleSourceRef, ...],
    quantization_version: str,
) -> str:
    return f"{tag}:{canonical_sha256(_canonical('cn_a_share_fee_generated_rule_id_v2', rule_type=rule_type, rule_schema_version=1, component_key=component.component_key, component_version=component.component_version, component_digest=component.component_digest, rule_book_hash=book_hash, band_hash=band_hash, authority_hash=query.authority_hash, binding_hash=query.binding_hash, query_hash=query.query_hash, access_route=query.authority.access_route.value, fee_product_class=query.authority.fee_product_class.value, charge_key=charge_key, purpose=purpose, basis_type=basis_type, applies=applies, source_refs=refs, quantization_version=quantization_version))}"


def _market_rules(
    authority: CnAShareFeeExecutionAuthorityV2,
    query: CnAShareCashFeeRuleQueryV2,
    band: CnAShareMarketFeeBandV2,
) -> tuple[
    tuple[FeeReservationChargeRule, ...],
    tuple[FinalFeeChargeRule, ...],
    tuple[FinalFeeChargeRule, ...],
]:
    quant = QuantizationPolicy(
        "cn-a-share-market-fee.cny-cent.half-up.v2", _SCALE, RoundingPolicy.HALF_UP
    )
    component = _market_component(authority.market_fee_rule_book)
    charges = (
        (
            "handling",
            band.handling_applies,
            band.handling_rate,
            band.handling_source_refs,
        ),
        (
            "securities_regulatory",
            band.regulatory_applies,
            band.regulatory_rate,
            band.regulatory_source_refs,
        ),
        (
            "chinaclear_transfer",
            band.chinaclear_transfer_applies,
            band.chinaclear_transfer_rate,
            band.chinaclear_transfer_source_refs,
        ),
        (
            "hkscc_transfer",
            band.hkscc_transfer_applies,
            band.hkscc_transfer_rate,
            band.hkscc_transfer_source_refs,
        ),
    )

    def rid(
        key: str,
        applies: bool,
        refs: tuple[CnAShareFeeRuleSourceRef, ...],
        purpose: str,
        basis: str,
    ) -> str:
        return _generated_id(
            "cn-a-share-market-fee-rule-v2",
            "cn_a_share_market_fee_charge_rule_v2",
            component,
            authority.market_fee_rule_book_hash,
            band.band_hash,
            query,
            key,
            purpose,
            basis,
            applies,
            refs,
            quant.version,
        )

    reserve = tuple(
        FeeReservationChargeRule(
            FeeReservationRuleSource.MARKET_FEE,
            rid(k, a, r, "reservation", "order_notional"),
            FeeReservationBasis.ORDER_NOTIONAL,
            FeeReservationApplicability.APPLIES
            if a
            else FeeReservationApplicability.NOT_APPLICABLE,
            rate if a else _ZERO,
            None,
            quant,
        )
        for k, a, rate, r in charges
    )
    final = tuple(
        FinalFeeChargeRule(
            FinalFeeRuleSource.MARKET_FEE,
            rid(k, a, r, "final_fill", "fill"),
            FeeBasisType.FILL,
            FinalFeeCalculationBasis.NOTIONAL_RATE,
            FinalFeeApplicability.ALWAYS if a else FinalFeeApplicability.NOT_APPLICABLE,
            rate if a else _ZERO,
            None,
            quant,
        )
        for k, a, rate, r in charges
    )
    order = tuple(
        FinalFeeChargeRule(
            FinalFeeRuleSource.MARKET_FEE,
            rid(k, False, r, "final_order", "order"),
            FeeBasisType.ORDER,
            FinalFeeCalculationBasis.NOTIONAL_RATE,
            FinalFeeApplicability.NOT_APPLICABLE,
            _ZERO,
            None,
            quant,
        )
        for k, _, _, r in charges
    )
    return reserve, final, order


def _tax_rules(
    authority: CnAShareFeeExecutionAuthorityV2,
    query: CnAShareCashFeeRuleQueryV2,
    band: CnAShareStampDutyBandV2,
) -> tuple[FeeReservationChargeRule, FinalFeeChargeRule, FinalFeeChargeRule]:
    quant = QuantizationPolicy(
        "cn-a-share-stamp-duty.cny-cent.half-up.v2", _SCALE, RoundingPolicy.HALF_UP
    )
    component = _tax_component(authority.stamp_duty_rule_book)
    applies = band.applies_to_sell and query.side is OrderSide.SELL

    def rid(applies: bool, purpose: str, basis: str) -> str:
        return _generated_id(
            "cn-a-share-stamp-duty-rule-v2",
            "cn_a_share_stamp_duty_charge_rule_v2",
            component,
            authority.stamp_duty_rule_book_hash,
            band.band_hash,
            query,
            "stamp_duty",
            purpose,
            basis,
            applies,
            band.source_refs,
            quant.version,
        )

    rate = band.rate if applies else _ZERO
    return (
        FeeReservationChargeRule(
            FeeReservationRuleSource.TAX,
            rid(applies, "reservation", "order_notional"),
            FeeReservationBasis.ORDER_NOTIONAL,
            FeeReservationApplicability.APPLIES
            if applies
            else FeeReservationApplicability.NOT_APPLICABLE,
            rate,
            None,
            quant,
        ),
        FinalFeeChargeRule(
            FinalFeeRuleSource.TAX,
            rid(applies, "final_fill", "fill"),
            FeeBasisType.FILL,
            FinalFeeCalculationBasis.NOTIONAL_RATE,
            FinalFeeApplicability.ALWAYS
            if applies
            else FinalFeeApplicability.NOT_APPLICABLE,
            rate,
            None,
            quant,
        ),
        FinalFeeChargeRule(
            FinalFeeRuleSource.TAX,
            rid(False, "final_order", "order"),
            FeeBasisType.ORDER,
            FinalFeeCalculationBasis.NOTIONAL_RATE,
            FinalFeeApplicability.NOT_APPLICABLE,
            _ZERO,
            None,
            quant,
        ),
    )


@dataclass(frozen=True, slots=True)
class CnAShareMarketFeeRuleResolutionV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    query: CnAShareCashFeeRuleQueryV2
    query_hash: str
    binding_hash: str
    order_id: DomainId
    order_hash: str
    fill: Fill | None
    fill_hash: str | None
    fill_id: DomainId | None
    side: OrderSide
    effective_at: UtcInstant
    active_band: CnAShareMarketFeeBandV2
    active_band_hash: str
    reservation_charge_rules: tuple[FeeReservationChargeRule, ...]
    final_fill_charge_rules: tuple[FinalFeeChargeRule, ...]
    final_order_not_applicable_rules: tuple[FinalFeeChargeRule, ...]

    def __post_init__(self) -> None:
        if (
            _reconstructed_authority(self.authority) is None
            or _reconstructed_query(self.query) is None
            or not _concrete_domain_id(self.order_id)
            or not (self.fill is None or _concrete_fill(self.fill))
            or not (self.fill_id is None or _concrete_domain_id(self.fill_id))
            or not _enum_member(self.side, OrderSide)
            or not _concrete_instant(self.effective_at)
            or not _concrete_market_band(self.active_band)
            or type(self.reservation_charge_rules) is not tuple
            or not all(
                _concrete_reservation_rule(rule)
                for rule in self.reservation_charge_rules
            )
            or type(self.final_fill_charge_rules) is not tuple
            or not all(
                _concrete_final_rule(rule) for rule in self.final_fill_charge_rules
            )
            or type(self.final_order_not_applicable_rules) is not tuple
            or not all(
                _concrete_final_rule(rule)
                for rule in self.final_order_not_applicable_rules
            )
        ):
            raise TypeError("market resolution context invalid")
        for name, value in (
            ("authority_hash", self.authority_hash),
            ("query_hash", self.query_hash),
            ("binding_hash", self.binding_hash),
            ("order_hash", self.order_hash),
            ("active_band_hash", self.active_band_hash),
        ):
            _hash(name, value)
        if self.fill_hash is not None:
            _hash("fill_hash", self.fill_hash)
        if (self.authority_hash, self.query_hash, self.binding_hash) != (
            self.authority.authority_hash,
            self.query.query_hash,
            self.query.binding_hash,
        ):
            raise ValueError("market resolution hash mismatch")
        if (
            self.query.authority != self.authority
            or self.query.authority_hash != self.authority_hash
        ):
            raise ValueError("market resolution authority mismatch")
        if (
            self.order_id,
            self.order_hash,
            self.fill,
            self.fill_hash,
            self.fill_id,
            self.side,
            self.effective_at,
        ) != (
            self.query.order_id,
            self.query.order_hash,
            self.query.fill,
            self.query.fill_hash,
            self.query.fill_id,
            self.query.side,
            self.query.effective_at,
        ):
            raise ValueError("market resolution query provenance mismatch")
        active = _active_market_bands(
            self.authority.market_fee_rule_book, self.query.venue_id, self.effective_at
        )
        if (
            len(active) != 1
            or self.active_band != active[0]
            or self.active_band_hash != active[0].band_hash
        ):
            raise ValueError("active market band mismatch")
        if (
            self.reservation_charge_rules,
            self.final_fill_charge_rules,
            self.final_order_not_applicable_rules,
        ) != _market_rules(self.authority, self.query, self.active_band):
            raise ValueError("market resolution rule semantics mismatch")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_market_fee_rule_resolution_v2",
            authority=self.authority,
            authority_hash=self.authority_hash,
            query=self.query,
            query_hash=self.query_hash,
            binding_hash=self.binding_hash,
            order_id=self.order_id,
            order_hash=self.order_hash,
            fill=self.fill,
            fill_hash=self.fill_hash,
            fill_id=self.fill_id,
            side=self.side.value,
            effective_at=self.effective_at,
            active_band=self.active_band,
            active_band_hash=self.active_band_hash,
            reservation_charge_rules=self.reservation_charge_rules,
            final_fill_charge_rules=self.final_fill_charge_rules,
            final_order_not_applicable_rules=self.final_order_not_applicable_rules,
        )


@dataclass(frozen=True, slots=True)
class CnAShareStampDutyRuleResolutionV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    query: CnAShareCashFeeRuleQueryV2
    query_hash: str
    binding_hash: str
    order_id: DomainId
    order_hash: str
    fill: Fill | None
    fill_hash: str | None
    fill_id: DomainId | None
    side: OrderSide
    effective_at: UtcInstant
    active_band: CnAShareStampDutyBandV2
    active_band_hash: str
    reservation_charge_rule: FeeReservationChargeRule
    final_fill_charge_rule: FinalFeeChargeRule
    final_order_not_applicable_rule: FinalFeeChargeRule

    def __post_init__(self) -> None:
        if (
            _reconstructed_authority(self.authority) is None
            or _reconstructed_query(self.query) is None
            or not _concrete_domain_id(self.order_id)
            or not (self.fill is None or _concrete_fill(self.fill))
            or not (self.fill_id is None or _concrete_domain_id(self.fill_id))
            or not _enum_member(self.side, OrderSide)
            or not _concrete_instant(self.effective_at)
            or not _concrete_stamp_band(self.active_band)
            or not _concrete_reservation_rule(self.reservation_charge_rule)
            or not _concrete_final_rule(self.final_fill_charge_rule)
            or not _concrete_final_rule(self.final_order_not_applicable_rule)
        ):
            raise TypeError("stamp resolution context invalid")
        for name, value in (
            ("authority_hash", self.authority_hash),
            ("query_hash", self.query_hash),
            ("binding_hash", self.binding_hash),
            ("order_hash", self.order_hash),
            ("active_band_hash", self.active_band_hash),
        ):
            _hash(name, value)
        if self.fill_hash is not None:
            _hash("fill_hash", self.fill_hash)
        if (self.authority_hash, self.query_hash, self.binding_hash) != (
            self.authority.authority_hash,
            self.query.query_hash,
            self.query.binding_hash,
        ):
            raise ValueError("stamp resolution hash mismatch")
        if (
            self.query.authority != self.authority
            or self.query.authority_hash != self.authority_hash
        ):
            raise ValueError("stamp resolution authority mismatch")
        if (
            self.order_id,
            self.order_hash,
            self.fill,
            self.fill_hash,
            self.fill_id,
            self.side,
            self.effective_at,
        ) != (
            self.query.order_id,
            self.query.order_hash,
            self.query.fill,
            self.query.fill_hash,
            self.query.fill_id,
            self.query.side,
            self.query.effective_at,
        ):
            raise ValueError("stamp resolution query provenance mismatch")
        active = _active_stamp_bands(
            self.authority.stamp_duty_rule_book, self.query.venue_id, self.effective_at
        )
        if (
            len(active) != 1
            or self.active_band != active[0]
            or self.active_band_hash != active[0].band_hash
        ):
            raise ValueError("active stamp band mismatch")
        if (
            self.reservation_charge_rule,
            self.final_fill_charge_rule,
            self.final_order_not_applicable_rule,
        ) != _tax_rules(self.authority, self.query, self.active_band):
            raise ValueError("stamp resolution rule semantics mismatch")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_stamp_duty_rule_resolution_v2",
            authority=self.authority,
            authority_hash=self.authority_hash,
            query=self.query,
            query_hash=self.query_hash,
            binding_hash=self.binding_hash,
            order_id=self.order_id,
            order_hash=self.order_hash,
            fill=self.fill,
            fill_hash=self.fill_hash,
            fill_id=self.fill_id,
            side=self.side.value,
            effective_at=self.effective_at,
            active_band=self.active_band,
            active_band_hash=self.active_band_hash,
            reservation_charge_rule=self.reservation_charge_rule,
            final_fill_charge_rule=self.final_fill_charge_rule,
            final_order_not_applicable_rule=self.final_order_not_applicable_rule,
        )


@dataclass(frozen=True, slots=True)
class CnAShareCashMarketFeePolicyV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    assessment_scale: Scale

    def __post_init__(self) -> None:
        _hash("authority_hash", self.authority_hash)
        if (
            _reconstructed_authority(self.authority) is None
            or self.authority_hash != self.authority.authority_hash
            or not _concrete_scale(self.assessment_scale)
            or self.assessment_scale != _SCALE
        ):
            raise ValueError("market policy authority or scale mismatch")

    @property
    def component_ref(self) -> ProfileComponentRef:
        return _market_component(self.authority.market_fee_rule_book)

    def assess_fees(
        self, query: CnAShareCashFeeRuleQueryV2, /
    ) -> ProfilePortOutcome[
        CnAShareMarketFeeRuleResolutionV2, CnAShareFeeRuleFailureV2
    ]:
        if (
            type(self) is not CnAShareCashMarketFeePolicyV2
            or _reconstructed_authority(self.authority) is None
            or not _canonical_hash(self.authority_hash)
            or self.authority_hash != self.authority.authority_hash
            or not _concrete_scale(self.assessment_scale)
            or self.assessment_scale != _SCALE
        ):
            raise TypeError("market policy context invalid")
        if not _concrete_query_context(query):
            raise TypeError("query context must be concrete")
        failure = _policy_failure(self, query, self.authority.market_fee_rule_book)
        if failure is not None:
            return ProfilePortOutcome.for_failure(self.component_ref, query, failure)
        active = _active_market_bands(
            self.authority.market_fee_rule_book, query.venue_id, query.effective_at
        )
        if len(active) != 1:
            code = (
                CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL
                if not active
                else CnAShareFeeRuleFailureCodeV2.OVERLAPPING_RULE_INTERVALS
            )
            hashes = (
                canonical_sha256(())
                if not active
                else canonical_sha256(tuple(sorted(x.band_hash for x in active)))
            )
            failure = _failure(
                query,
                code,
                (
                    "venue_id",
                    query.venue_id.value,
                    "effective_at_hash",
                    canonical_sha256(query.effective_at),
                    "rule_book_hash",
                    self.authority.market_fee_rule_book_hash,
                    "active_band_hashes_hash",
                    hashes,
                ),
            )
            return ProfilePortOutcome.for_failure(self.component_ref, query, failure)
        band = active[0]
        reservation, final, order = _market_rules(self.authority, query, band)
        return ProfilePortOutcome.for_result(
            self.component_ref,
            query,
            CnAShareMarketFeeRuleResolutionV2(
                self.authority,
                self.authority_hash,
                query,
                query.query_hash,
                query.binding_hash,
                query.order_id,
                query.order_hash,
                query.fill,
                query.fill_hash,
                query.fill_id,
                query.side,
                query.effective_at,
                band,
                band.band_hash,
                reservation,
                final,
                order,
            ),
        )


@dataclass(frozen=True, slots=True)
class CnAShareCashStampDutyTaxPolicyV2:
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    assessment_scale: Scale

    def __post_init__(self) -> None:
        _hash("authority_hash", self.authority_hash)
        if (
            _reconstructed_authority(self.authority) is None
            or self.authority_hash != self.authority.authority_hash
            or not _concrete_scale(self.assessment_scale)
            or self.assessment_scale != _SCALE
        ):
            raise ValueError("stamp policy authority or scale mismatch")

    @property
    def component_ref(self) -> ProfileComponentRef:
        return _tax_component(self.authority.stamp_duty_rule_book)

    def assess_taxes(
        self, query: CnAShareCashFeeRuleQueryV2, /
    ) -> ProfilePortOutcome[
        CnAShareStampDutyRuleResolutionV2, CnAShareFeeRuleFailureV2
    ]:
        if (
            type(self) is not CnAShareCashStampDutyTaxPolicyV2
            or _reconstructed_authority(self.authority) is None
            or not _canonical_hash(self.authority_hash)
            or self.authority_hash != self.authority.authority_hash
            or not _concrete_scale(self.assessment_scale)
            or self.assessment_scale != _SCALE
        ):
            raise TypeError("stamp policy context invalid")
        if not _concrete_query_context(query):
            raise TypeError("query context must be concrete")
        failure = _policy_failure(self, query, self.authority.stamp_duty_rule_book)
        if failure is not None:
            return ProfilePortOutcome.for_failure(self.component_ref, query, failure)
        active = _active_stamp_bands(
            self.authority.stamp_duty_rule_book, query.venue_id, query.effective_at
        )
        if len(active) != 1:
            code = (
                CnAShareFeeRuleFailureCodeV2.MISSING_RULE_INTERVAL
                if not active
                else CnAShareFeeRuleFailureCodeV2.OVERLAPPING_RULE_INTERVALS
            )
            hashes = (
                canonical_sha256(())
                if not active
                else canonical_sha256(tuple(sorted(x.band_hash for x in active)))
            )
            failure = _failure(
                query,
                code,
                (
                    "venue_id",
                    query.venue_id.value,
                    "effective_at_hash",
                    canonical_sha256(query.effective_at),
                    "rule_book_hash",
                    self.authority.stamp_duty_rule_book_hash,
                    "active_band_hashes_hash",
                    hashes,
                ),
            )
            return ProfilePortOutcome.for_failure(self.component_ref, query, failure)
        band = active[0]
        reservation, final, order = _tax_rules(self.authority, query, band)
        return ProfilePortOutcome.for_result(
            self.component_ref,
            query,
            CnAShareStampDutyRuleResolutionV2(
                self.authority,
                self.authority_hash,
                query,
                query.query_hash,
                query.binding_hash,
                query.order_id,
                query.order_hash,
                query.fill,
                query.fill_hash,
                query.fill_id,
                query.side,
                query.effective_at,
                band,
                band.band_hash,
                reservation,
                final,
                order,
            ),
        )


@dataclass(frozen=True, slots=True)
class CnAShareFeeReservationBufferV2:
    market_resolution: CnAShareMarketFeeRuleResolutionV2
    tax_resolution: CnAShareStampDutyRuleResolutionV2
    maximum_fill_count: int
    market_charge_rule: FeeReservationChargeRule
    tax_charge_rule: FeeReservationChargeRule

    def __post_init__(self) -> None:
        if (
            type(self.market_resolution) is not CnAShareMarketFeeRuleResolutionV2
            or type(self.tax_resolution) is not CnAShareStampDutyRuleResolutionV2
        ):
            raise TypeError("buffer resolutions must be concrete v2")
        if not (
            _concrete_reservation_rule(self.market_charge_rule)
            and _concrete_reservation_rule(self.tax_charge_rule)
        ):
            raise TypeError("buffer rules must be concrete")
        if type(self.maximum_fill_count) is not int or self.maximum_fill_count <= 0:
            raise ValueError("maximum_fill_count must be a positive integer")
        if not _same_context(self.market_resolution, self.tax_resolution):
            raise ValueError("reservation buffer resolution context mismatch")
        if (self.market_charge_rule, self.tax_charge_rule) != _buffer_rules(
            self.market_resolution, self.tax_resolution, self.maximum_fill_count
        ):
            raise ValueError("reservation buffer rule semantics mismatch")

    @classmethod
    def create(
        cls,
        *,
        market_resolution: CnAShareMarketFeeRuleResolutionV2,
        tax_resolution: CnAShareStampDutyRuleResolutionV2,
        maximum_fill_count: int,
    ) -> CnAShareFeeReservationBufferV2:
        if not _same_context(market_resolution, tax_resolution):
            raise ValueError("reservation buffer resolution context mismatch")
        market, tax = _buffer_rules(
            market_resolution, tax_resolution, maximum_fill_count
        )
        return cls(market_resolution, tax_resolution, maximum_fill_count, market, tax)

    def covers_fill_count(self, fill_count: int, /) -> bool:
        if type(fill_count) is not int or fill_count < 0:
            raise ValueError("fill_count must be a non-negative integer")
        return fill_count <= self.maximum_fill_count

    def require_covers_fills(self, fills: tuple[Fill, ...], /) -> None:
        if type(fills) is not tuple or not all(_concrete_fill(fill) for fill in fills):
            raise TypeError("fills must be a tuple of concrete Fill")
        if not self.covers_fill_count(len(fills)):
            raise ValueError("actual fill count exceeds reservation bound")

    @property
    def buffer_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_fee_reservation_buffer_v2",
            market_resolution=self.market_resolution,
            tax_resolution=self.tax_resolution,
            maximum_fill_count=self.maximum_fill_count,
            market_charge_rule=self.market_charge_rule,
            tax_charge_rule=self.tax_charge_rule,
        )


def _same_context(market: Any, tax: Any) -> bool:
    if (
        type(market) is not CnAShareMarketFeeRuleResolutionV2
        or type(tax) is not CnAShareStampDutyRuleResolutionV2
    ):
        return False
    try:
        reconstructed_market = CnAShareMarketFeeRuleResolutionV2(
            market.authority,
            market.authority_hash,
            market.query,
            market.query_hash,
            market.binding_hash,
            market.order_id,
            market.order_hash,
            market.fill,
            market.fill_hash,
            market.fill_id,
            market.side,
            market.effective_at,
            market.active_band,
            market.active_band_hash,
            market.reservation_charge_rules,
            market.final_fill_charge_rules,
            market.final_order_not_applicable_rules,
        )
        reconstructed_tax = CnAShareStampDutyRuleResolutionV2(
            tax.authority,
            tax.authority_hash,
            tax.query,
            tax.query_hash,
            tax.binding_hash,
            tax.order_id,
            tax.order_hash,
            tax.fill,
            tax.fill_hash,
            tax.fill_id,
            tax.side,
            tax.effective_at,
            tax.active_band,
            tax.active_band_hash,
            tax.reservation_charge_rule,
            tax.final_fill_charge_rule,
            tax.final_order_not_applicable_rule,
        )
    except (TypeError, ValueError):
        return False
    if reconstructed_market != market or reconstructed_tax != tax:
        return False
    return (
        market.authority,
        market.authority_hash,
        market.query,
        market.query_hash,
        market.binding_hash,
        market.order_id,
        market.order_hash,
        market.fill,
        market.fill_hash,
        market.fill_id,
        market.side,
        market.effective_at,
        market.query.purpose,
    ) == (
        tax.authority,
        tax.authority_hash,
        tax.query,
        tax.query_hash,
        tax.binding_hash,
        tax.order_id,
        tax.order_hash,
        tax.fill,
        tax.fill_hash,
        tax.fill_id,
        tax.side,
        tax.effective_at,
        tax.query.purpose,
    ) and market.query.purpose is CnAShareFeeAssessmentPurposeV2.RESERVATION


def _buffer_rules(
    market: CnAShareMarketFeeRuleResolutionV2,
    tax: CnAShareStampDutyRuleResolutionV2,
    count: int,
) -> tuple[FeeReservationChargeRule, FeeReservationChargeRule]:
    if type(count) is not int or count <= 0:
        raise ValueError("maximum_fill_count must be a positive integer")
    quant = QuantizationPolicy(
        "cn-a-share-fee-reservation-buffer.cny-cent.half-up.v2",
        _SCALE,
        RoundingPolicy.HALF_UP,
    )
    unit = count // 2
    market_count = sum(
        x.applicability is FeeReservationApplicability.APPLIES
        for x in market.reservation_charge_rules
    )
    tax_count = int(
        tax.reservation_charge_rule.applicability is FeeReservationApplicability.APPLIES
    )

    def rule(
        component: ProfileComponentRef,
        resolution_hash: str,
        component_count: int,
        charge_key: str,
        source: FeeReservationRuleSource,
    ) -> FeeReservationChargeRule:
        applies = component_count > 0
        amount = Money(component_count * unit, _SCALE, "CNY")
        preimage = _canonical(
            "cn_a_share_fee_reservation_buffer_rule_id_v2",
            rule_type="cn_a_share_fee_reservation_buffer_rule_v2",
            rule_schema_version=1,
            component_key=component.component_key,
            component_version=component.component_version,
            component_digest=component.component_digest,
            authority_hash=market.authority_hash,
            scope_hash=market.authority.scope_hash,
            binding_hash=market.binding_hash,
            market_resolution_hash=market.resolution_hash,
            tax_resolution_hash=tax.resolution_hash,
            maximum_fill_count=count,
            component_count=component_count,
            applies=applies,
            charge_key=charge_key,
            basis_type="flat_per_order",
            amount=amount,
            quantization_version=quant.version,
        )
        return FeeReservationChargeRule(
            source,
            f"cn-a-share-fee-reservation-buffer-rule-v2:{canonical_sha256(preimage)}",
            FeeReservationBasis.FLAT_PER_ORDER,
            FeeReservationApplicability.APPLIES
            if applies
            else FeeReservationApplicability.NOT_APPLICABLE,
            None,
            amount,
            quant,
        )

    return rule(
        _market_component(market.authority.market_fee_rule_book),
        market.resolution_hash,
        market_count,
        "handling",
        FeeReservationRuleSource.MARKET_FEE,
    ), rule(
        _tax_component(tax.authority.stamp_duty_rule_book),
        tax.resolution_hash,
        tax_count,
        "stamp_duty",
        FeeReservationRuleSource.TAX,
    )


def _safe_hash(value: object, /) -> str | None:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError, AttributeError):
        return None


def _raw_v1_market_book(value: object) -> bool:
    return (
        type(value) is CnAShareMarketFeeRuleBook
        and type(value.rule_book_key) is str
        and type(value.rule_book_version) is int
        and type(value.bands) is tuple
        and all(type(band) is CnAShareMarketFeeBand for band in value.bands)
        and _safe_hash(value) is not None
    )


def _raw_v1_stamp_book(value: object) -> bool:
    return (
        type(value) is CnAShareStampDutyRuleBook
        and type(value.rule_book_key) is str
        and type(value.rule_book_version) is int
        and type(value.bands) is tuple
        and all(type(band) is CnAShareStampDutyBand for band in value.bands)
        and _safe_hash(value) is not None
    )


def _raw_band_hash(value: object, /) -> str:
    result = _safe_hash(value)
    if result is None:
        raise ValueError("projection source cannot be canonically identified")
    return result


def _raw_band_order(values: tuple[Any, ...], /) -> tuple[Any, ...]:
    def key(band: Any) -> tuple[Any, ...]:
        venue = getattr(band, "venue_id", None)
        start = getattr(band, "effective_from", None)
        stop = getattr(band, "effective_to_exclusive", None)
        return (
            0 if _concrete_venue(venue) else 1,
            cast(VenueId, venue).value
            if _concrete_venue(venue)
            else _raw_band_hash(venue),
            0 if _concrete_instant(start) else 1,
            cast(UtcInstant, start).epoch_nanoseconds
            if _concrete_instant(start)
            else _raw_band_hash(start),
            0 if _concrete_instant(stop) else 1,
            cast(UtcInstant, stop).epoch_nanoseconds
            if _concrete_instant(stop)
            else _raw_band_hash(stop),
            _raw_band_hash(band),
        )

    return tuple(sorted(values, key=key))


class CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2(str, Enum):
    NON_XSHE_MARKET_SOURCE = "non_xshe_market_source"
    NON_XSHE_STAMP_DUTY_SOURCE = "non_xshe_stamp_duty_source"
    MARKET_SOURCE_INTERVAL_INVALID = "market_source_interval_invalid"
    STAMP_DUTY_SOURCE_INTERVAL_INVALID = "stamp_duty_source_interval_invalid"
    MARKET_SOURCE_ECONOMIC_INVALID = "market_source_economic_invalid"
    STAMP_DUTY_SOURCE_ECONOMIC_INVALID = "stamp_duty_source_economic_invalid"


@dataclass(frozen=True, slots=True)
class CnAShareDomesticOrdinaryFeeProjectionFailureV2:
    market_rule_book: CnAShareMarketFeeRuleBook
    market_rule_book_hash: str
    stamp_duty_rule_book: CnAShareStampDutyRuleBook
    stamp_duty_rule_book_hash: str
    code: CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _hash("market_rule_book_hash", self.market_rule_book_hash)
        _hash("stamp_duty_rule_book_hash", self.stamp_duty_rule_book_hash)
        if (
            not _raw_v1_market_book(self.market_rule_book)
            or not _raw_v1_stamp_book(self.stamp_duty_rule_book)
            or not _enum_member(
                self.code, CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2
            )
        ):
            raise TypeError("projection failure context invalid")
        if (self.market_rule_book_hash, self.stamp_duty_rule_book_hash) != (
            _raw_band_hash(self.market_rule_book),
            _raw_band_hash(self.stamp_duty_rule_book),
        ):
            raise ValueError("projection failure hash mismatch")
        if type(
            self.subject_ids
        ) is not tuple or self.subject_ids != _projection_failure_subjects(
            self.market_rule_book, self.stamp_duty_rule_book, self.code
        ):
            raise ValueError("projection failure subject_ids mismatch")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_domestic_ordinary_fee_projection_failure_v2",
            market_rule_book=self.market_rule_book,
            market_rule_book_hash=self.market_rule_book_hash,
            stamp_duty_rule_book=self.stamp_duty_rule_book,
            stamp_duty_rule_book_hash=self.stamp_duty_rule_book_hash,
            code=self.code.value,
            subject_ids=self.subject_ids,
        )


@dataclass(frozen=True, slots=True)
class CnAShareDomesticOrdinaryFeeProjectionV2:
    algorithm_id: str
    source_market_rule_book: CnAShareMarketFeeRuleBook
    source_market_rule_book_hash: str
    source_stamp_duty_rule_book: CnAShareStampDutyRuleBook
    source_stamp_duty_rule_book_hash: str
    access_route: CnAShareExecutionAccessRoute
    fee_product_class: CnAShareFeeProductClass
    market_fee_rule_book: CnAShareMarketFeeRuleBookV2
    market_fee_rule_book_hash: str
    stamp_duty_rule_book: CnAShareStampDutyRuleBookV2
    stamp_duty_rule_book_hash: str

    def __post_init__(self) -> None:
        _text("algorithm_id", self.algorithm_id)
        for name, value in (
            ("source_market_rule_book_hash", self.source_market_rule_book_hash),
            ("source_stamp_duty_rule_book_hash", self.source_stamp_duty_rule_book_hash),
            ("market_fee_rule_book_hash", self.market_fee_rule_book_hash),
            ("stamp_duty_rule_book_hash", self.stamp_duty_rule_book_hash),
        ):
            _hash(name, value)
        if (
            self.algorithm_id
            != "cn-a-share-domestic-ordinary-v1-to-v2-fee-projection-v1"
        ):
            raise ValueError("projection algorithm_id mismatch")
        if not (
            _concrete_v1_market_book(self.source_market_rule_book)
            and _concrete_v1_stamp_book(self.source_stamp_duty_rule_book)
        ):
            raise TypeError("projection source books invalid")
        if (
            self.source_market_rule_book_hash,
            self.source_stamp_duty_rule_book_hash,
        ) != (
            self.source_market_rule_book.rule_book_hash,
            self.source_stamp_duty_rule_book.rule_book_hash,
        ):
            raise ValueError("projection source hash mismatch")
        if (
            self.access_route is not CnAShareExecutionAccessRoute.DOMESTIC
            or self.fee_product_class is not CnAShareFeeProductClass.ORDINARY_A_SHARE
        ):
            raise ValueError("projection scope mismatch")
        if not (
            _concrete_market_book(self.market_fee_rule_book)
            and _concrete_stamp_book(self.stamp_duty_rule_book)
        ):
            raise TypeError("projection v2 books invalid")
        if (self.market_fee_rule_book_hash, self.stamp_duty_rule_book_hash) != (
            self.market_fee_rule_book.rule_book_hash,
            self.stamp_duty_rule_book.rule_book_hash,
        ):
            raise ValueError("projection v2 hash mismatch")
        _ensure_projectable_sources(
            self.source_market_rule_book, self.source_stamp_duty_rule_book
        )
        expected_market, expected_stamp = _projected_books(
            self.source_market_rule_book, self.source_stamp_duty_rule_book
        )
        if (self.market_fee_rule_book, self.stamp_duty_rule_book) != (
            expected_market,
            expected_stamp,
        ):
            raise ValueError("projection output economics mismatch")

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return _canonical(
            "cn_a_share_domestic_ordinary_fee_projection_v2",
            algorithm_id=self.algorithm_id,
            source_market_rule_book=self.source_market_rule_book,
            source_market_rule_book_hash=self.source_market_rule_book_hash,
            source_stamp_duty_rule_book=self.source_stamp_duty_rule_book,
            source_stamp_duty_rule_book_hash=self.source_stamp_duty_rule_book_hash,
            access_route=self.access_route.value,
            fee_product_class=self.fee_product_class.value,
            market_fee_rule_book=self.market_fee_rule_book,
            market_fee_rule_book_hash=self.market_fee_rule_book_hash,
            stamp_duty_rule_book=self.stamp_duty_rule_book,
            stamp_duty_rule_book_hash=self.stamp_duty_rule_book_hash,
        )


def _projection_failure_subjects(
    market: CnAShareMarketFeeRuleBook,
    stamp: CnAShareStampDutyRuleBook,
    code: CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2,
) -> tuple[str, ...]:
    prefix = (code.value, _raw_band_hash(market), _raw_band_hash(stamp))
    market_bands = _raw_band_order(market.bands)
    stamp_bands = _raw_band_order(stamp.bands)
    if (
        code
        is CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.NON_XSHE_MARKET_SOURCE
    ):
        band = next(
            band
            for band in market_bands
            if not _concrete_venue(band.venue_id) or band.venue_id != VenueId("xshe")
        )
        return (
            *prefix,
            "venue_id",
            band.venue_id.value if _concrete_venue(band.venue_id) else "invalid",
            "band_hash",
            _raw_band_hash(band),
        )
    if (
        code
        is CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.NON_XSHE_STAMP_DUTY_SOURCE
    ):
        band = next(
            band
            for band in stamp_bands
            if not _concrete_venue(band.venue_id) or band.venue_id != VenueId("xshe")
        )
        return (
            *prefix,
            "venue_id",
            band.venue_id.value if _concrete_venue(band.venue_id) else "invalid",
            "band_hash",
            _raw_band_hash(band),
        )
    if (
        code
        is CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.MARKET_SOURCE_INTERVAL_INVALID
    ):
        band = next(
            band
            for band in market_bands
            if not _concrete_instant(band.effective_from)
            or not _concrete_instant(band.effective_to_exclusive)
            or band.effective_from >= band.effective_to_exclusive
        )
        return (
            *prefix,
            "band_hash",
            _raw_band_hash(band),
            "effective_from_hash",
            _raw_band_hash(band.effective_from),
            "effective_to_exclusive_hash",
            _raw_band_hash(band.effective_to_exclusive),
        )
    if (
        code
        is CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.STAMP_DUTY_SOURCE_INTERVAL_INVALID
    ):
        band = next(
            band
            for band in stamp_bands
            if not _concrete_instant(band.effective_from)
            or not _concrete_instant(band.effective_to_exclusive)
            or band.effective_from >= band.effective_to_exclusive
        )
        return (
            *prefix,
            "band_hash",
            _raw_band_hash(band),
            "effective_from_hash",
            _raw_band_hash(band.effective_from),
            "effective_to_exclusive_hash",
            _raw_band_hash(band.effective_to_exclusive),
        )
    if (
        code
        is CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.MARKET_SOURCE_ECONOMIC_INVALID
    ):
        band = next(band for band in market_bands if not _valid_v1_market(band))
        return (
            *prefix,
            "band_hash",
            _raw_band_hash(band),
            "economic_hash",
            _raw_band_hash(band),
        )
    band = next(band for band in stamp_bands if not _valid_v1_stamp(band))
    return (
        *prefix,
        "band_hash",
        _raw_band_hash(band),
        "economic_hash",
        _raw_band_hash(band),
    )


def _projection_failure(
    market: CnAShareMarketFeeRuleBook,
    stamp: CnAShareStampDutyRuleBook,
    code: CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2,
    suffix: tuple[str, ...],
) -> CnAShareDomesticOrdinaryFeeProjectionFailureV2:
    expected = _projection_failure_subjects(market, stamp, code)
    if suffix != expected[3:]:
        raise ValueError("projection failure suffix mismatch")
    return CnAShareDomesticOrdinaryFeeProjectionFailureV2(
        market,
        _raw_band_hash(market),
        stamp,
        _raw_band_hash(stamp),
        code,
        expected,
    )


def _valid_v1_sources(values: object) -> bool:
    if (
        type(values) is not tuple
        or not values
        or not all(_concrete_source_ref(value) for value in values)
    ):
        return False
    return values == tuple(
        sorted(values, key=lambda value: (value.source_key, value.source_hash))
    ) and len(set(values)) == len(values)


def _valid_v1_market(value: Any) -> bool:
    return (
        type(value) is CnAShareMarketFeeBand
        and all(
            _concrete_rate(getattr(value, n, None))
            and getattr(value, n).units >= 0
            and getattr(value, n).basis == "fee_fraction"
            for n in ("handling_rate", "regulatory_rate", "transfer_rate")
        )
        and all(
            _valid_v1_sources(getattr(value, n, None))
            for n in (
                "handling_source_refs",
                "regulatory_source_refs",
                "transfer_source_refs",
            )
        )
    )


def _valid_v1_stamp(value: Any) -> bool:
    return (
        type(value) is CnAShareStampDutyBand
        and _concrete_rate(getattr(value, "rate", None))
        and value.rate.units >= 0
        and value.rate.basis == "fee_fraction"
        and _valid_v1_sources(getattr(value, "source_refs", None))
    )


def _concrete_v1_market_book(value: object) -> bool:
    return (
        type(value) is CnAShareMarketFeeRuleBook
        and type(value.rule_book_key) is str
        and type(value.rule_book_version) is int
        and type(value.bands) is tuple
        and all(
            type(band) is CnAShareMarketFeeBand
            and _concrete_venue(band.venue_id)
            and _concrete_instant(band.effective_from)
            and _concrete_instant(band.effective_to_exclusive)
            and all(
                _concrete_rate(getattr(band, name))
                for name in ("handling_rate", "regulatory_rate", "transfer_rate")
            )
            and all(
                _valid_v1_sources(getattr(band, name))
                for name in (
                    "handling_source_refs",
                    "regulatory_source_refs",
                    "transfer_source_refs",
                )
            )
            and _exact(band, CnAShareMarketFeeBand)
            for band in value.bands
        )
        and _exact(value, CnAShareMarketFeeRuleBook)
    )


def _concrete_v1_stamp_book(value: object) -> bool:
    return (
        type(value) is CnAShareStampDutyRuleBook
        and type(value.rule_book_key) is str
        and type(value.rule_book_version) is int
        and type(value.bands) is tuple
        and all(
            type(band) is CnAShareStampDutyBand
            and _concrete_venue(band.venue_id)
            and _concrete_instant(band.effective_from)
            and _concrete_instant(band.effective_to_exclusive)
            and _concrete_rate(band.rate)
            and _valid_v1_sources(band.source_refs)
            and _exact(band, CnAShareStampDutyBand)
            for band in value.bands
        )
        and _exact(value, CnAShareStampDutyRuleBook)
    )


def project_cn_a_share_domestic_ordinary_fee_rules_v2(
    market_rule_book: CnAShareMarketFeeRuleBook,
    stamp_duty_rule_book: CnAShareStampDutyRuleBook,
    /,
) -> (
    CnAShareDomesticOrdinaryFeeProjectionV2
    | CnAShareDomesticOrdinaryFeeProjectionFailureV2
):
    if not (
        _raw_v1_market_book(market_rule_book)
        and _raw_v1_stamp_book(stamp_duty_rule_book)
    ):
        raise TypeError("source rule books must be exact v1 outer values")
    market_bands = _raw_band_order(market_rule_book.bands)
    stamp_bands = _raw_band_order(stamp_duty_rule_book.bands)
    for band in market_bands:
        if not _concrete_venue(band.venue_id) or band.venue_id != VenueId("xshe"):
            return _projection_failure(
                market_rule_book,
                stamp_duty_rule_book,
                CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.NON_XSHE_MARKET_SOURCE,
                (
                    "venue_id",
                    band.venue_id.value
                    if _concrete_venue(band.venue_id)
                    else "invalid",
                    "band_hash",
                    _raw_band_hash(band),
                ),
            )
    for band in stamp_bands:
        if not _concrete_venue(band.venue_id) or band.venue_id != VenueId("xshe"):
            return _projection_failure(
                market_rule_book,
                stamp_duty_rule_book,
                CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.NON_XSHE_STAMP_DUTY_SOURCE,
                (
                    "venue_id",
                    band.venue_id.value
                    if _concrete_venue(band.venue_id)
                    else "invalid",
                    "band_hash",
                    _raw_band_hash(band),
                ),
            )
    for band in market_bands:
        if (
            not _concrete_instant(band.effective_from)
            or not _concrete_instant(band.effective_to_exclusive)
            or band.effective_from >= band.effective_to_exclusive
        ):
            return _projection_failure(
                market_rule_book,
                stamp_duty_rule_book,
                CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.MARKET_SOURCE_INTERVAL_INVALID,
                (
                    "band_hash",
                    _raw_band_hash(band),
                    "effective_from_hash",
                    _raw_band_hash(band.effective_from),
                    "effective_to_exclusive_hash",
                    _raw_band_hash(band.effective_to_exclusive),
                ),
            )
    for band in stamp_bands:
        if (
            not _concrete_instant(band.effective_from)
            or not _concrete_instant(band.effective_to_exclusive)
            or band.effective_from >= band.effective_to_exclusive
        ):
            return _projection_failure(
                market_rule_book,
                stamp_duty_rule_book,
                CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.STAMP_DUTY_SOURCE_INTERVAL_INVALID,
                (
                    "band_hash",
                    _raw_band_hash(band),
                    "effective_from_hash",
                    _raw_band_hash(band.effective_from),
                    "effective_to_exclusive_hash",
                    _raw_band_hash(band.effective_to_exclusive),
                ),
            )
    for band in market_bands:
        if not _valid_v1_market(band):
            return _projection_failure(
                market_rule_book,
                stamp_duty_rule_book,
                CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.MARKET_SOURCE_ECONOMIC_INVALID,
                (
                    "band_hash",
                    _raw_band_hash(band),
                    "economic_hash",
                    _raw_band_hash(band),
                ),
            )
    for band in stamp_bands:
        if not _valid_v1_stamp(band):
            return _projection_failure(
                market_rule_book,
                stamp_duty_rule_book,
                CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2.STAMP_DUTY_SOURCE_ECONOMIC_INVALID,
                (
                    "band_hash",
                    _raw_band_hash(band),
                    "economic_hash",
                    _raw_band_hash(band),
                ),
            )
    _ensure_projectable_sources(market_rule_book, stamp_duty_rule_book)
    market_hash = market_rule_book.rule_book_hash
    stamp_hash = stamp_duty_rule_book.rule_book_hash
    market, stamp = _projected_books(market_rule_book, stamp_duty_rule_book)
    return CnAShareDomesticOrdinaryFeeProjectionV2(
        "cn-a-share-domestic-ordinary-v1-to-v2-fee-projection-v1",
        market_rule_book,
        market_hash,
        stamp_duty_rule_book,
        stamp_hash,
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
        market,
        market.rule_book_hash,
        stamp,
        stamp.rule_book_hash,
    )


def _ensure_projectable_sources(
    market_rule_book: CnAShareMarketFeeRuleBook,
    stamp_duty_rule_book: CnAShareStampDutyRuleBook,
) -> None:
    if (
        type(market_rule_book.bands) is not tuple
        or type(stamp_duty_rule_book.bands) is not tuple
        or not market_rule_book.bands
        or not stamp_duty_rule_book.bands
    ):
        raise ValueError("projection source rule books must be non-empty")
    if market_rule_book.bands != tuple(
        sorted(
            market_rule_book.bands,
            key=lambda band: (
                band.venue_id.value,
                band.effective_from,
                band.effective_to_exclusive,
                band.band_hash,
            ),
        )
    ) or stamp_duty_rule_book.bands != tuple(
        sorted(
            stamp_duty_rule_book.bands,
            key=lambda band: (
                band.venue_id.value,
                band.effective_from,
                band.effective_to_exclusive,
                band.band_hash,
            ),
        )
    ):
        raise ValueError("projection source bands must be canonical-sorted")
    if any(
        type(band) is not CnAShareMarketFeeBand or band.venue_id != VenueId("xshe")
        for band in market_rule_book.bands
    ):
        raise ValueError("projection market source must be XSHE-only")
    if any(
        type(band) is not CnAShareStampDutyBand or band.venue_id != VenueId("xshe")
        for band in stamp_duty_rule_book.bands
    ):
        raise ValueError("projection stamp source must be XSHE-only")
    if any(
        type(band.effective_from) is not UtcInstant
        or type(band.effective_to_exclusive) is not UtcInstant
        or band.effective_from >= band.effective_to_exclusive
        for band in market_rule_book.bands
    ) or any(
        type(band.effective_from) is not UtcInstant
        or type(band.effective_to_exclusive) is not UtcInstant
        or band.effective_from >= band.effective_to_exclusive
        for band in stamp_duty_rule_book.bands
    ):
        raise ValueError("projection source intervals invalid")
    if any(not _valid_v1_market(band) for band in market_rule_book.bands) or any(
        not _valid_v1_stamp(band) for band in stamp_duty_rule_book.bands
    ):
        raise ValueError("projection source economics invalid")


def _projected_books(
    market_rule_book: CnAShareMarketFeeRuleBook,
    stamp_duty_rule_book: CnAShareStampDutyRuleBook,
) -> tuple[CnAShareMarketFeeRuleBookV2, CnAShareStampDutyRuleBookV2]:
    market_hash = market_rule_book.rule_book_hash
    stamp_hash = stamp_duty_rule_book.rule_book_hash

    def hkscc(band: CnAShareMarketFeeBand) -> CnAShareFeeRuleSourceRef:
        digest = canonical_sha256(
            _canonical(
                "cn_a_share_fee_compatibility_hkscc_source_v2",
                source_market_rule_book_hash=market_hash,
                source_stamp_duty_rule_book_hash=stamp_hash,
                venue_id="xshe",
                effective_from=band.effective_from,
                effective_to_exclusive=band.effective_to_exclusive,
                access_route="domestic",
                fee_product_class="ordinary_a_share",
                charge_key="hkscc_transfer",
                applies=False,
            )
        )
        return CnAShareFeeRuleSourceRef(
            "cn-a-share-domestic-ordinary-v1-to-v2-hkscc-not-applicable", digest
        )

    market_bands = tuple(
        CnAShareMarketFeeBandV2(
            b.venue_id,
            b.effective_from,
            b.effective_to_exclusive,
            True,
            b.handling_rate,
            b.handling_source_refs,
            True,
            b.regulatory_rate,
            b.regulatory_source_refs,
            True,
            b.transfer_rate,
            b.transfer_source_refs,
            False,
            _ZERO,
            (hkscc(b),),
        )
        for b in market_rule_book.bands
    )
    stamp_bands = tuple(
        CnAShareStampDutyBandV2(
            b.venue_id,
            b.effective_from,
            b.effective_to_exclusive,
            True,
            b.rate,
            b.source_refs,
        )
        for b in stamp_duty_rule_book.bands
    )
    return (
        CnAShareMarketFeeRuleBookV2(
            "equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share.projected-v2",
            2,
            CnAShareExecutionAccessRoute.DOMESTIC,
            CnAShareFeeProductClass.ORDINARY_A_SHARE,
            market_bands,
        ),
        CnAShareStampDutyRuleBookV2(
            "equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share.projected-v2",
            2,
            CnAShareExecutionAccessRoute.DOMESTIC,
            CnAShareFeeProductClass.ORDINARY_A_SHARE,
            stamp_bands,
        ),
    )
