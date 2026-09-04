"""Finite historical commission-independent A-share market fee and tax rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar
import unicodedata

from crypto_quant_domain import (
    FeeBasisType,
    Fill,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    OrderSide,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
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


_SUPPORTED_VENUES = frozenset((VenueId("xshg"), VenueId("xshe")))
_MARKET_COMPONENT_KEY = "equity.cn_a_share.cash.market-fees.v1"
_TAX_COMPONENT_KEY = "equity.cn_a_share.cash.stamp-duty.v1"
_MARKET_ALGORITHM_KEY = "cn-a-share-historical-market-fees-v1"
_TAX_ALGORITHM_KEY = "cn-a-share-historical-stamp-duty-v1"
_MARKET_RULE_TAG = "cn-a-share-market-fee-rule-v1"
_TAX_RULE_TAG = "cn-a-share-stamp-duty-rule-v1"
_MARKET_BUFFER_RULE_TAG = "cn-a-share-market-fee-rounding-buffer-v1"
_TAX_BUFFER_RULE_TAG = "cn-a-share-tax-rounding-buffer-v1"


class CnAShareFeeTradeMechanism(str, Enum):
    AUCTION = "auction"
    BLOCK = "block"


class CnAShareFeeRuleFailureCode(str, Enum):
    UNSUPPORTED_VENUE = "unsupported_venue"
    UNSUPPORTED_INSTRUMENT = "unsupported_instrument"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    UNSUPPORTED_TRADE_MECHANISM = "unsupported_trade_mechanism"
    MISSING_RULE_INTERVAL = "missing_rule_interval"
    OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"


def _text(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be canonical NFC text")


def _hash(name: str, value: str) -> None:
    digest = value.removeprefix("sha256:") if isinstance(value, str) else ""
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _version(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _fee_rate(name: str, value: Rate) -> None:
    if not isinstance(value, Rate):
        raise TypeError(f"{name} must be Rate")
    if value.units < 0 or value.basis != "fee_fraction":
        raise ValueError(f"{name} must be a non-negative fee_fraction")


def _source_refs(
    name: str, values: tuple[CnAShareFeeRuleSourceRef, ...]
) -> tuple[CnAShareFeeRuleSourceRef, ...]:
    if not isinstance(values, tuple) or not values or not all(
        isinstance(value, CnAShareFeeRuleSourceRef) for value in values
    ):
        raise TypeError(f"{name} must be a non-empty source-ref tuple")
    ordered = tuple(sorted(values, key=lambda value: (value.source_key, value.source_hash)))
    if len(ordered) != len(set(ordered)):
        raise ValueError(f"{name} contains duplicate source refs")
    return ordered


def _rule_id(tag: str, payload: dict[str, Any]) -> str:
    return f"{tag}:{canonical_sha256(payload)}"


@dataclass(frozen=True)
class CnAShareFeeRuleSourceRef:
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_fee_rule_source_ref",
            "schema_version": 1,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


class _EffectiveBand:
    venue_id: VenueId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant < self.effective_to_exclusive


def _validate_effective_band(value: _EffectiveBand) -> None:
    if not isinstance(value.venue_id, VenueId):
        raise TypeError("venue_id must be VenueId")
    if not isinstance(value.effective_from, UtcInstant) or not isinstance(
        value.effective_to_exclusive, UtcInstant
    ):
        raise TypeError("effective interval must use UtcInstant")
    if value.effective_from >= value.effective_to_exclusive:
        raise ValueError("effective interval must be non-empty")


@dataclass(frozen=True)
class CnAShareMarketFeeBand(_EffectiveBand):
    venue_id: VenueId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    handling_rate: Rate
    handling_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]
    regulatory_rate: Rate
    regulatory_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]
    transfer_rate: Rate
    transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]

    def __post_init__(self) -> None:
        _validate_effective_band(self)
        for name in ("handling_rate", "regulatory_rate", "transfer_rate"):
            _fee_rate(name, getattr(self, name))
        for name in (
            "handling_source_refs",
            "regulatory_source_refs",
            "transfer_source_refs",
        ):
            object.__setattr__(self, name, _source_refs(name, getattr(self, name)))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_market_fee_band",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "handling_rate": self.handling_rate,
            "handling_source_refs": self.handling_source_refs,
            "regulatory_rate": self.regulatory_rate,
            "regulatory_source_refs": self.regulatory_source_refs,
            "transfer_rate": self.transfer_rate,
            "transfer_source_refs": self.transfer_source_refs,
        }


@dataclass(frozen=True)
class CnAShareStampDutyBand(_EffectiveBand):
    venue_id: VenueId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    rate: Rate
    source_refs: tuple[CnAShareFeeRuleSourceRef, ...]

    def __post_init__(self) -> None:
        _validate_effective_band(self)
        _fee_rate("rate", self.rate)
        object.__setattr__(self, "source_refs", _source_refs("source_refs", self.source_refs))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_stamp_duty_band",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "rate": self.rate,
            "source_refs": self.source_refs,
        }


_BandT = TypeVar("_BandT", bound=_EffectiveBand)


@dataclass(frozen=True)
class _FiniteRuleBook(Generic[_BandT]):
    rule_book_key: str
    rule_book_version: int
    bands: tuple[_BandT, ...]

    _band_type: ClassVar[type[_EffectiveBand]]
    _canonical_type: ClassVar[str]

    def __post_init__(self) -> None:
        _text("rule_book_key", self.rule_book_key)
        _version("rule_book_version", self.rule_book_version)
        if not isinstance(self.bands, tuple) or not self.bands or not all(
            isinstance(value, self._band_type) for value in self.bands
        ):
            raise TypeError(f"bands must contain {self._band_type.__name__}")
        object.__setattr__(
            self,
            "bands",
            tuple(
                sorted(
                    self.bands,
                    key=lambda value: (
                        value.venue_id.value,
                        value.effective_from,
                        value.effective_to_exclusive,
                        value.band_hash,
                    ),
                )
            ),
        )

    @property
    def rule_book_hash(self) -> str:
        return canonical_sha256(self)

    def active_bands(
        self, venue_id: VenueId, instant: UtcInstant
    ) -> tuple[_BandT, ...]:
        return tuple(
            value
            for value in self.bands
            if value.venue_id == venue_id and value.contains(instant)
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": self._canonical_type,
            "schema_version": 1,
            "rule_book_key": self.rule_book_key,
            "rule_book_version": self.rule_book_version,
            "bands": self.bands,
        }


class CnAShareMarketFeeRuleBook(_FiniteRuleBook[CnAShareMarketFeeBand]):
    _band_type = CnAShareMarketFeeBand
    _canonical_type = "cn_a_share_market_fee_rule_book"


class CnAShareStampDutyRuleBook(_FiniteRuleBook[CnAShareStampDutyBand]):
    _band_type = CnAShareStampDutyBand
    _canonical_type = "cn_a_share_stamp_duty_rule_book"


@dataclass(frozen=True)
class CnAShareCashFeeRuleQuery:
    instrument: InstrumentDefinition
    side: OrderSide
    effective_at: UtcInstant
    trade_mechanism: CnAShareFeeTradeMechanism

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, InstrumentDefinition):
            raise TypeError("instrument must be InstrumentDefinition")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        if not isinstance(self.effective_at, UtcInstant):
            raise TypeError("effective_at must be UtcInstant")
        if not isinstance(self.trade_mechanism, CnAShareFeeTradeMechanism):
            raise TypeError("trade_mechanism must be CnAShareFeeTradeMechanism")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_cash_fee_rule_query",
            "schema_version": 1,
            "instrument": self.instrument,
            "side": self.side.value,
            "effective_at": self.effective_at,
            "trade_mechanism": self.trade_mechanism.value,
        }


def _validate_resolution_query(
    query: CnAShareCashFeeRuleQuery,
    query_hash: str,
    venue_id: VenueId,
    instrument_id: InstrumentId,
    side: OrderSide,
    effective_at: UtcInstant,
) -> None:
    if not isinstance(query, CnAShareCashFeeRuleQuery):
        raise TypeError("query must be CnAShareCashFeeRuleQuery")
    _hash("query_hash", query_hash)
    if canonical_sha256(query) != query_hash:
        raise ValueError("query_hash must match query")
    if (
        query.instrument.instrument_id.venue != venue_id
        or query.instrument.instrument_id != instrument_id
        or query.side is not side
        or query.effective_at != effective_at
        or query.trade_mechanism is not CnAShareFeeTradeMechanism.AUCTION
    ):
        raise ValueError("resolution query context mismatch")


def _validate_resolution_context(
    venue_id: VenueId,
    instrument_id: InstrumentId,
    side: OrderSide,
    effective_at: UtcInstant,
    query: CnAShareCashFeeRuleQuery,
    query_hash: str,
) -> None:
    _validate_resolution_identity(venue_id, instrument_id, side, effective_at)
    _validate_resolution_query(
        query, query_hash, venue_id, instrument_id, side, effective_at
    )


def _resolution_canonical_fields(
    venue_id: VenueId,
    instrument_id: InstrumentId,
    side: OrderSide,
    effective_at: UtcInstant,
    query: CnAShareCashFeeRuleQuery,
    query_hash: str,
) -> dict[str, Any]:
    return {
        "venue_id": venue_id,
        "instrument_id": instrument_id,
        "side": side.value,
        "effective_at": effective_at,
        "query": query,
        "query_hash": query_hash,
    }


@dataclass(frozen=True)
class CnAShareMarketFeeRuleResolution:
    venue_id: VenueId
    instrument_id: InstrumentId
    side: OrderSide
    effective_at: UtcInstant
    query: CnAShareCashFeeRuleQuery
    query_hash: str
    active_band: CnAShareMarketFeeBand
    active_band_hash: str
    reservation_charge_rules: tuple[FeeReservationChargeRule, ...]
    final_fill_charge_rules: tuple[FinalFeeChargeRule, ...]
    final_order_not_applicable_rule: FinalFeeChargeRule

    def __post_init__(self) -> None:
        _validate_resolution_context(
            self.venue_id,
            self.instrument_id,
            self.side,
            self.effective_at,
            self.query,
            self.query_hash,
        )
        if not isinstance(self.active_band, CnAShareMarketFeeBand):
            raise TypeError("active_band must be CnAShareMarketFeeBand")
        _hash("active_band_hash", self.active_band_hash)
        if (
            self.active_band.venue_id != self.venue_id
            or not self.active_band.contains(self.effective_at)
            or self.active_band.band_hash != self.active_band_hash
        ):
            raise ValueError("active market fee Band mismatch")
        expected = _market_rules(self.active_band, Scale(2))
        if (
            self.reservation_charge_rules,
            self.final_fill_charge_rules,
            self.final_order_not_applicable_rule,
        ) != expected:
            raise ValueError("market fee resolution rule semantics mismatch")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_market_fee_rule_resolution",
            "schema_version": 1,
            **_resolution_canonical_fields(
                self.venue_id,
                self.instrument_id,
                self.side,
                self.effective_at,
                self.query,
                self.query_hash,
            ),
            "active_band": self.active_band,
            "active_band_hash": self.active_band_hash,
            "reservation_charge_rules": self.reservation_charge_rules,
            "final_fill_charge_rules": self.final_fill_charge_rules,
            "final_order_not_applicable_rule": self.final_order_not_applicable_rule,
        }


@dataclass(frozen=True)
class CnAShareStampDutyRuleResolution:
    venue_id: VenueId
    instrument_id: InstrumentId
    side: OrderSide
    effective_at: UtcInstant
    query: CnAShareCashFeeRuleQuery
    query_hash: str
    active_band: CnAShareStampDutyBand
    active_band_hash: str
    reservation_charge_rule: FeeReservationChargeRule
    final_fill_charge_rule: FinalFeeChargeRule
    final_order_not_applicable_rule: FinalFeeChargeRule

    def __post_init__(self) -> None:
        _validate_resolution_context(
            self.venue_id,
            self.instrument_id,
            self.side,
            self.effective_at,
            self.query,
            self.query_hash,
        )
        if not isinstance(self.active_band, CnAShareStampDutyBand):
            raise TypeError("active_band must be CnAShareStampDutyBand")
        _hash("active_band_hash", self.active_band_hash)
        if (
            self.active_band.venue_id != self.venue_id
            or not self.active_band.contains(self.effective_at)
            or self.active_band.band_hash != self.active_band_hash
        ):
            raise ValueError("active stamp duty Band mismatch")
        expected = _tax_rules(self.active_band, self.side, Scale(2))
        if (
            self.reservation_charge_rule,
            self.final_fill_charge_rule,
            self.final_order_not_applicable_rule,
        ) != expected:
            raise ValueError("stamp duty resolution rule semantics mismatch")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_stamp_duty_rule_resolution",
            "schema_version": 1,
            **_resolution_canonical_fields(
                self.venue_id,
                self.instrument_id,
                self.side,
                self.effective_at,
                self.query,
                self.query_hash,
            ),
            "active_band": self.active_band,
            "active_band_hash": self.active_band_hash,
            "reservation_charge_rule": self.reservation_charge_rule,
            "final_fill_charge_rule": self.final_fill_charge_rule,
            "final_order_not_applicable_rule": self.final_order_not_applicable_rule,
        }


@dataclass(frozen=True)
class CnAShareFeeReservationBuffer:
    market_resolution: CnAShareMarketFeeRuleResolution
    tax_resolution: CnAShareStampDutyRuleResolution
    maximum_fill_count: int
    market_charge_rule: FeeReservationChargeRule
    tax_charge_rule: FeeReservationChargeRule

    def __post_init__(self) -> None:
        if not isinstance(self.market_resolution, CnAShareMarketFeeRuleResolution):
            raise TypeError("market_resolution must be CnAShareMarketFeeRuleResolution")
        if not isinstance(self.tax_resolution, CnAShareStampDutyRuleResolution):
            raise TypeError("tax_resolution must be CnAShareStampDutyRuleResolution")
        if (
            self.market_resolution.query != self.tax_resolution.query
            or self.market_resolution.query_hash != self.tax_resolution.query_hash
            or self.market_resolution.venue_id != self.tax_resolution.venue_id
            or self.market_resolution.instrument_id != self.tax_resolution.instrument_id
            or self.market_resolution.side is not self.tax_resolution.side
            or self.market_resolution.effective_at != self.tax_resolution.effective_at
        ):
            raise ValueError("reservation buffer resolution context mismatch")
        if (
            isinstance(self.maximum_fill_count, bool)
            or not isinstance(self.maximum_fill_count, int)
            or self.maximum_fill_count <= 0
        ):
            raise ValueError("maximum_fill_count must be a positive integer")
        expected = _buffer_rules(
            self.market_resolution,
            self.tax_resolution,
            self.maximum_fill_count,
        )
        if (self.market_charge_rule, self.tax_charge_rule) != expected:
            raise ValueError("reservation buffer rule semantics mismatch")

    @classmethod
    def create(
        cls,
        *,
        market_resolution: CnAShareMarketFeeRuleResolution,
        tax_resolution: CnAShareStampDutyRuleResolution,
        maximum_fill_count: int,
    ) -> CnAShareFeeReservationBuffer:
        market_rule, tax_rule = _buffer_rules(
            market_resolution, tax_resolution, maximum_fill_count
        )
        return cls(
            market_resolution,
            tax_resolution,
            maximum_fill_count,
            market_rule,
            tax_rule,
        )

    @property
    def buffer_hash(self) -> str:
        return canonical_sha256(self)

    def covers_fill_count(self, fill_count: int) -> bool:
        if isinstance(fill_count, bool) or not isinstance(fill_count, int) or fill_count < 0:
            raise ValueError("fill_count must be a non-negative integer")
        return fill_count <= self.maximum_fill_count

    def require_covers_fills(self, fills: tuple[Fill, ...]) -> None:
        if not isinstance(fills, tuple) or not all(isinstance(value, Fill) for value in fills):
            raise TypeError("fills must be a tuple of Fill")
        if not self.covers_fill_count(len(fills)):
            raise ValueError("actual fill count exceeds reservation bound")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_fee_reservation_buffer",
            "schema_version": 1,
            "market_resolution": self.market_resolution,
            "tax_resolution": self.tax_resolution,
            "maximum_fill_count": self.maximum_fill_count,
            "market_charge_rule": self.market_charge_rule,
            "tax_charge_rule": self.tax_charge_rule,
        }


@dataclass(frozen=True)
class CnAShareFeeRuleFailure:
    query: CnAShareCashFeeRuleQuery
    query_hash: str
    code: CnAShareFeeRuleFailureCode

    def __post_init__(self) -> None:
        if not isinstance(self.query, CnAShareCashFeeRuleQuery):
            raise TypeError("query must be CnAShareCashFeeRuleQuery")
        _hash("query_hash", self.query_hash)
        if canonical_sha256(self.query) != self.query_hash:
            raise ValueError("query_hash must match query")
        if not isinstance(self.code, CnAShareFeeRuleFailureCode):
            raise TypeError("code must be CnAShareFeeRuleFailureCode")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_fee_rule_failure",
            "schema_version": 1,
            "query": self.query,
            "query_hash": self.query_hash,
            "code": self.code.value,
        }


def _quantization(version: str, scale: Scale) -> QuantizationPolicy:
    return QuantizationPolicy(version, scale, RoundingPolicy.HALF_UP)


def _market_rule_id(
    band: CnAShareMarketFeeBand,
    *,
    source_refs: tuple[CnAShareFeeRuleSourceRef, ...],
    charge_key: str,
    purpose: str,
    basis: str,
) -> str:
    return _rule_id(
        _MARKET_RULE_TAG,
        {
            "component_key": _MARKET_COMPONENT_KEY,
            "band_hash": band.band_hash,
            "source_refs": source_refs,
            "charge_key": charge_key,
            "purpose": purpose,
            "basis_type": basis,
        },
    )


def _tax_rule_id(
    band: CnAShareStampDutyBand, *, purpose: str, basis: str
) -> str:
    return _rule_id(
        _TAX_RULE_TAG,
        {
            "component_key": _TAX_COMPONENT_KEY,
            "band_hash": band.band_hash,
            "source_refs": band.source_refs,
            "charge_key": "stamp_duty",
            "purpose": purpose,
            "basis_type": basis,
        },
    )


def _validate_resolution_identity(
    venue_id: VenueId,
    instrument_id: InstrumentId,
    side: OrderSide,
    effective_at: UtcInstant,
) -> None:
    if (
        not isinstance(venue_id, VenueId)
        or not isinstance(instrument_id, InstrumentId)
        or instrument_id.venue != venue_id
    ):
        raise ValueError("resolution identity mismatch")
    if not isinstance(side, OrderSide) or not isinstance(effective_at, UtcInstant):
        raise TypeError("resolution side/time has invalid type")


def _market_rules(
    band: CnAShareMarketFeeBand,
    scale: Scale,
) -> tuple[
    tuple[FeeReservationChargeRule, ...],
    tuple[FinalFeeChargeRule, ...],
    FinalFeeChargeRule,
]:
    quantization = _quantization(
        "cn-a-share-market-fee.cny-cent.half-up.v1", scale
    )
    charges = (
        ("exchange_handling", band.handling_rate, band.handling_source_refs),
        ("regulatory", band.regulatory_rate, band.regulatory_source_refs),
        ("transfer", band.transfer_rate, band.transfer_source_refs),
    )
    reservation = tuple(
        FeeReservationChargeRule(
            FeeReservationRuleSource.MARKET_FEE,
            _market_rule_id(
                band,
                source_refs=source_refs,
                charge_key=charge_key,
                purpose="reservation",
                basis=FeeReservationBasis.ORDER_NOTIONAL.value,
            ),
            FeeReservationBasis.ORDER_NOTIONAL,
            FeeReservationApplicability.APPLIES,
            rate,
            None,
            quantization,
        )
        for charge_key, rate, source_refs in charges
    )
    final_fill = tuple(
        FinalFeeChargeRule(
            FinalFeeRuleSource.MARKET_FEE,
            _market_rule_id(
                band,
                source_refs=source_refs,
                charge_key=charge_key,
                purpose="final_fill",
                basis=FeeBasisType.FILL.value,
            ),
            FeeBasisType.FILL,
            FinalFeeCalculationBasis.NOTIONAL_RATE,
            FinalFeeApplicability.ALWAYS,
            rate,
            None,
            quantization,
        )
        for charge_key, rate, source_refs in charges
    )
    all_sources = _source_refs(
        "market_order_source_refs",
        tuple({source for _, _, refs in charges for source in refs}),
    )
    final_order = FinalFeeChargeRule(
        FinalFeeRuleSource.MARKET_FEE,
        _market_rule_id(
            band,
            source_refs=all_sources,
            charge_key="market_fee_order_coverage",
            purpose="final_order",
            basis=FeeBasisType.ORDER.value,
        ),
        FeeBasisType.ORDER,
        FinalFeeCalculationBasis.NOTIONAL_RATE,
        FinalFeeApplicability.NOT_APPLICABLE,
        Rate(0, Scale(0), "fee_fraction"),
        None,
        quantization,
    )
    return reservation, final_fill, final_order


def _tax_rules(
    band: CnAShareStampDutyBand,
    side: OrderSide,
    scale: Scale,
) -> tuple[FeeReservationChargeRule, FinalFeeChargeRule, FinalFeeChargeRule]:
    quantization = _quantization(
        "cn-a-share-stamp-duty.cny-cent.half-up.v1", scale
    )
    reservation = FeeReservationChargeRule(
        FeeReservationRuleSource.TAX,
        _tax_rule_id(
            band,
            purpose="reservation",
            basis=FeeReservationBasis.ORDER_NOTIONAL.value,
        ),
        FeeReservationBasis.ORDER_NOTIONAL,
        (
            FeeReservationApplicability.APPLIES
            if side is OrderSide.SELL
            else FeeReservationApplicability.NOT_APPLICABLE
        ),
        band.rate,
        None,
        quantization,
    )
    final_fill = FinalFeeChargeRule(
        FinalFeeRuleSource.TAX,
        _tax_rule_id(band, purpose="final_fill", basis=FeeBasisType.FILL.value),
        FeeBasisType.FILL,
        FinalFeeCalculationBasis.NOTIONAL_RATE,
        FinalFeeApplicability.SELL_ONLY,
        band.rate,
        None,
        quantization,
    )
    final_order = FinalFeeChargeRule(
        FinalFeeRuleSource.TAX,
        _tax_rule_id(band, purpose="final_order", basis=FeeBasisType.ORDER.value),
        FeeBasisType.ORDER,
        FinalFeeCalculationBasis.NOTIONAL_RATE,
        FinalFeeApplicability.NOT_APPLICABLE,
        Rate(0, Scale(0), "fee_fraction"),
        None,
        quantization,
    )
    return reservation, final_fill, final_order


def _buffer_rules(
    market_resolution: CnAShareMarketFeeRuleResolution,
    tax_resolution: CnAShareStampDutyRuleResolution,
    maximum_fill_count: int,
) -> tuple[FeeReservationChargeRule, FeeReservationChargeRule]:
    if (
        isinstance(maximum_fill_count, bool)
        or not isinstance(maximum_fill_count, int)
        or maximum_fill_count <= 0
    ):
        raise ValueError("maximum_fill_count must be a positive integer")
    quantization = _quantization(
        "cn-a-share-fee-reservation-buffer.cny-cent.half-up.v1", Scale(2)
    )
    units_per_component = maximum_fill_count // 2
    common = {
        "market_resolution_hash": market_resolution.resolution_hash,
        "tax_resolution_hash": tax_resolution.resolution_hash,
        "maximum_fill_count": maximum_fill_count,
        "buffer_formula": "floor(maximum_fill_count/2)-cny-cent-per-component",
        "side": market_resolution.side.value,
    }
    market_rule = FeeReservationChargeRule(
        FeeReservationRuleSource.MARKET_FEE,
        _rule_id(_MARKET_BUFFER_RULE_TAG, {**common, "component_count": 3}),
        FeeReservationBasis.FLAT_PER_ORDER,
        FeeReservationApplicability.APPLIES,
        None,
        Money(3 * units_per_component, Scale(2), "CNY"),
        quantization,
    )
    tax_rule = FeeReservationChargeRule(
        FeeReservationRuleSource.TAX,
        _rule_id(_TAX_BUFFER_RULE_TAG, {**common, "component_count": 1}),
        FeeReservationBasis.FLAT_PER_ORDER,
        (
            FeeReservationApplicability.APPLIES
            if market_resolution.side is OrderSide.SELL
            else FeeReservationApplicability.NOT_APPLICABLE
        ),
        None,
        Money(units_per_component, Scale(2), "CNY"),
        quantization,
    )
    return market_rule, tax_rule


def _failure(
    component_ref: ProfileComponentRef,
    query: CnAShareCashFeeRuleQuery,
    code: CnAShareFeeRuleFailureCode,
) -> ProfilePortOutcome[Any, CnAShareFeeRuleFailure]:
    return ProfilePortOutcome.for_failure(
        component_ref,
        query,
        CnAShareFeeRuleFailure(query, canonical_sha256(query), code),
    )


def _common_failure(
    component_ref: ProfileComponentRef, query: CnAShareCashFeeRuleQuery
) -> ProfilePortOutcome[Any, CnAShareFeeRuleFailure] | None:
    instrument = query.instrument
    venue_id = instrument.instrument_id.venue
    if venue_id not in _SUPPORTED_VENUES:
        return _failure(component_ref, query, CnAShareFeeRuleFailureCode.UNSUPPORTED_VENUE)
    if instrument.instrument_type is not InstrumentType.EQUITY:
        return _failure(component_ref, query, CnAShareFeeRuleFailureCode.UNSUPPORTED_INSTRUMENT)
    if str(instrument.quote_currency) != "CNY" or str(instrument.settlement_currency) != "CNY":
        return _failure(component_ref, query, CnAShareFeeRuleFailureCode.UNSUPPORTED_CURRENCY)
    if query.trade_mechanism is not CnAShareFeeTradeMechanism.AUCTION:
        return _failure(
            component_ref,
            query,
            CnAShareFeeRuleFailureCode.UNSUPPORTED_TRADE_MECHANISM,
        )
    return None


def _resolved_band(
    component_ref: ProfileComponentRef,
    query: CnAShareCashFeeRuleQuery,
    rule_book: _FiniteRuleBook[_BandT],
) -> _BandT | ProfilePortOutcome[Any, CnAShareFeeRuleFailure]:
    common = _common_failure(component_ref, query)
    if common is not None:
        return common
    bands = rule_book.active_bands(
        query.instrument.instrument_id.venue, query.effective_at
    )
    if not bands:
        return _failure(
            component_ref, query, CnAShareFeeRuleFailureCode.MISSING_RULE_INTERVAL
        )
    if len(bands) != 1:
        return _failure(
            component_ref,
            query,
            CnAShareFeeRuleFailureCode.OVERLAPPING_RULE_INTERVALS,
        )
    return bands[0]


@dataclass(frozen=True)
class CnAShareCashMarketFeePolicy:
    rule_book: CnAShareMarketFeeRuleBook
    assessment_scale: Scale = Scale(2)

    def __post_init__(self) -> None:
        if not isinstance(self.rule_book, CnAShareMarketFeeRuleBook):
            raise TypeError("rule_book must be CnAShareMarketFeeRuleBook")
        if self.assessment_scale != Scale(2):
            raise ValueError("A-share fee assessment_scale must be CNY Scale 2")

    @property
    def component_ref(self) -> ProfileComponentRef:
        return ProfileComponentRef(
            ProfilePortType.FEE_ASSESSMENT_POLICY,
            _MARKET_COMPONENT_KEY,
            1,
            canonical_sha256(
                {
                    "type": "cn_a_share_cash_market_fee_component",
                    "schema_version": 1,
                    "component_key": _MARKET_COMPONENT_KEY,
                    "component_version": 1,
                    "algorithm_key": _MARKET_ALGORITHM_KEY,
                    "rule_book_hash": self.rule_book.rule_book_hash,
                    "assessment_scale": self.assessment_scale.places,
                    "rounding": RoundingPolicy.HALF_UP.value,
                }
            ),
        )

    def assess_fees(
        self, query: CnAShareCashFeeRuleQuery, /
    ) -> ProfilePortOutcome[CnAShareMarketFeeRuleResolution, CnAShareFeeRuleFailure]:
        if not isinstance(query, CnAShareCashFeeRuleQuery):
            raise TypeError("query must be CnAShareCashFeeRuleQuery")
        resolved = _resolved_band(self.component_ref, query, self.rule_book)
        if isinstance(resolved, ProfilePortOutcome):
            return resolved
        band = resolved
        reservation, final_fill, final_order = _market_rules(
            band, self.assessment_scale
        )
        return ProfilePortOutcome.for_result(
            self.component_ref,
            query,
            CnAShareMarketFeeRuleResolution(
                query.instrument.instrument_id.venue,
                query.instrument.instrument_id,
                query.side,
                query.effective_at,
                query,
                canonical_sha256(query),
                band,
                band.band_hash,
                reservation,
                final_fill,
                final_order,
            ),
        )


@dataclass(frozen=True)
class CnAShareCashStampDutyTaxPolicy:
    rule_book: CnAShareStampDutyRuleBook
    assessment_scale: Scale = Scale(2)

    def __post_init__(self) -> None:
        if not isinstance(self.rule_book, CnAShareStampDutyRuleBook):
            raise TypeError("rule_book must be CnAShareStampDutyRuleBook")
        if self.assessment_scale != Scale(2):
            raise ValueError("A-share tax assessment_scale must be CNY Scale 2")

    @property
    def component_ref(self) -> ProfileComponentRef:
        return ProfileComponentRef(
            ProfilePortType.TAX_POLICY,
            _TAX_COMPONENT_KEY,
            1,
            canonical_sha256(
                {
                    "type": "cn_a_share_cash_stamp_duty_component",
                    "schema_version": 1,
                    "component_key": _TAX_COMPONENT_KEY,
                    "component_version": 1,
                    "algorithm_key": _TAX_ALGORITHM_KEY,
                    "rule_book_hash": self.rule_book.rule_book_hash,
                    "assessment_scale": self.assessment_scale.places,
                    "rounding": RoundingPolicy.HALF_UP.value,
                }
            ),
        )

    def assess_taxes(
        self, query: CnAShareCashFeeRuleQuery, /
    ) -> ProfilePortOutcome[CnAShareStampDutyRuleResolution, CnAShareFeeRuleFailure]:
        if not isinstance(query, CnAShareCashFeeRuleQuery):
            raise TypeError("query must be CnAShareCashFeeRuleQuery")
        resolved = _resolved_band(self.component_ref, query, self.rule_book)
        if isinstance(resolved, ProfilePortOutcome):
            return resolved
        band = resolved
        reservation, final_fill, final_order = _tax_rules(
            band, query.side, self.assessment_scale
        )
        return ProfilePortOutcome.for_result(
            self.component_ref,
            query,
            CnAShareStampDutyRuleResolution(
                query.instrument.instrument_id.venue,
                query.instrument.instrument_id,
                query.side,
                query.effective_at,
                query,
                canonical_sha256(query),
                band,
                band.band_hash,
                reservation,
                final_fill,
                final_order,
            ),
        )
