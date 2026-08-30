"""Exact single-instrument linear perpetual margin requirements."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import gcd
from typing import Any, Self

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    InstrumentId,
    Money,
    PositionBalanceKey,
    PricePurpose,
    Quantity,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
    round_ratio,
)

from .derivatives import LinearPerpetualContract
from .ledger import LedgerBalanceRegistration
from .marks import ResolvedMark, StaleMarkPolicy
from .ports import ProfileComponentRef, ProfilePortOutcome, ProfilePortType

_SCHEMA_VERSION = 1
_COMPONENT_KEY = "instrument.linear-perpetual.margin-requirement.v1"
_LEVERAGE_BASIS = "notional_per_initial_margin"
_MAINTENANCE_BASIS = "maintenance_margin_fraction_of_notional"
_HEX = "0123456789abcdef"


def _text(name: str, value: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")


def _hash(name: str, value: str) -> None:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in _HEX for character in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 hash")


def _instant(name: str, value: SimulationInstant) -> None:
    if type(value) is not SimulationInstant or type(value.instant) is not UtcInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")


def _component_ref() -> ProfileComponentRef:
    digest = canonical_sha256(
        {
            "type": "linear_margin_requirement_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "algorithm_key": "linear-instrument-margin-requirement-v1",
            "exposure": "caller-supplied-signed-quantity",
            "notional": "abs(quantity)*multiplier*margin_mark",
            "tier_interval": "lower-inclusive-upper-exclusive",
            "rule_resolution": "exact-one-historical-interval",
            "initial_margin": "notional/selected_leverage",
            "maintenance_margin": (
                "notional*maintenance_rate-maintenance_deduction"
            ),
            "quantization": "independent-ceiling-boundaries",
            "allowed_grade": "development",
        }
    )
    return ProfileComponentRef(ProfilePortType.MARGIN_MODEL, _COMPONENT_KEY, 1, digest)


def _component_ref_v2() -> ProfileComponentRef:
    digest = canonical_sha256(
        {
            "type": "linear_margin_requirement_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY + ".independent-tier-scale",
            "component_version": 2,
            "algorithm_key": "linear-instrument-margin-requirement-v2",
            "tier_scale_policy": "independent_exact_notional_scale",
            "margin_mark_scale": "exact-raw-mark-scale",
            "allowed_grade": "development",
        }
    )
    return ProfileComponentRef(
        ProfilePortType.MARGIN_MODEL,
        _COMPONENT_KEY + ".independent-tier-scale",
        2,
        digest,
    )


@dataclass(frozen=True, slots=True)
class LinearMarginLeverageEvidence:
    account_id: str
    instrument_id: InstrumentId
    selected_leverage: Rate
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant | None
    available_at: SimulationInstant
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.selected_leverage) is not Rate:
            raise TypeError("selected_leverage must be exact Rate")
        if type(self.effective_from) is not UtcInstant:
            raise TypeError("effective_from must be exact UtcInstant")
        if self.effective_to_exclusive is not None:
            if type(self.effective_to_exclusive) is not UtcInstant:
                raise TypeError("effective_to_exclusive must be exact UtcInstant or None")
            if self.effective_from >= self.effective_to_exclusive:
                raise ValueError("leverage effective interval must be non-empty")
        _instant("available_at", self.available_at)
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    @property
    def leverage_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant and (
            self.effective_to_exclusive is None
            or instant < self.effective_to_exclusive
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_margin_leverage_evidence",
            "schema_version": _SCHEMA_VERSION,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "selected_leverage": self.selected_leverage,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "available_at": self.available_at,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class LinearMarginTier:
    tier_id: str
    notional_floor: Money
    notional_cap: Money | None
    maximum_leverage: Rate
    maintenance_margin_rate: Rate
    maintenance_margin_deduction: Money

    def __post_init__(self) -> None:
        _text("tier_id", self.tier_id)
        if type(self.notional_floor) is not Money:
            raise TypeError("notional_floor must be exact Money")
        if self.notional_floor.units < 0:
            raise ValueError("notional_floor cannot be negative")
        if self.notional_cap is not None:
            if type(self.notional_cap) is not Money:
                raise TypeError("notional_cap must be exact Money or None")
            if self.notional_cap.units < 0:
                raise ValueError("notional_cap cannot be negative")
        if type(self.maximum_leverage) is not Rate:
            raise TypeError("maximum_leverage must be exact Rate")
        if self.maximum_leverage.units <= 0:
            raise ValueError("maximum_leverage must be positive")
        if type(self.maintenance_margin_rate) is not Rate:
            raise TypeError("maintenance_margin_rate must be exact Rate")
        if self.maintenance_margin_rate.units < 0:
            raise ValueError("maintenance_margin_rate cannot be negative")
        if type(self.maintenance_margin_deduction) is not Money:
            raise TypeError("maintenance_margin_deduction must be exact Money")
        if self.maintenance_margin_deduction.units < 0:
            raise ValueError("maintenance_margin_deduction cannot be negative")

    @property
    def tier_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_margin_tier",
            "schema_version": _SCHEMA_VERSION,
            "tier_id": self.tier_id,
            "notional_floor": self.notional_floor,
            "notional_cap": self.notional_cap,
            "maximum_leverage": self.maximum_leverage,
            "maintenance_margin_rate": self.maintenance_margin_rate,
            "maintenance_margin_deduction": self.maintenance_margin_deduction,
        }


class LinearMarginTierBoundaryConvention(str, Enum):
    LOWER_INCLUSIVE_UPPER_EXCLUSIVE = "lower_inclusive_upper_exclusive"
    LOWER_EXCLUSIVE_UPPER_INCLUSIVE = "lower_exclusive_upper_inclusive"


@dataclass(frozen=True, slots=True)
class LinearMarginRuleInterval:
    interval_id: str
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant | None
    available_at: SimulationInstant
    tiers: tuple[LinearMarginTier, ...]
    source_key: str
    source_hash: str
    tier_boundary_convention: LinearMarginTierBoundaryConvention = (
        LinearMarginTierBoundaryConvention.LOWER_INCLUSIVE_UPPER_EXCLUSIVE
    )

    def __post_init__(self) -> None:
        _text("interval_id", self.interval_id)
        if type(self.effective_from) is not UtcInstant:
            raise TypeError("effective_from must be exact UtcInstant")
        if self.effective_to_exclusive is not None:
            if type(self.effective_to_exclusive) is not UtcInstant:
                raise TypeError("effective_to_exclusive must be exact UtcInstant or None")
            if self.effective_from >= self.effective_to_exclusive:
                raise ValueError("rule interval must be non-empty")
        _instant("available_at", self.available_at)
        if type(self.tiers) is not tuple or not all(
            type(value) is LinearMarginTier for value in self.tiers
        ):
            raise TypeError("tiers must be an exact tuple of LinearMarginTier")
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)
        if type(self.tier_boundary_convention) is not LinearMarginTierBoundaryConvention:
            raise TypeError(
                "tier_boundary_convention must be exact LinearMarginTierBoundaryConvention"
            )

    @property
    def interval_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant and (
            self.effective_to_exclusive is None
            or instant < self.effective_to_exclusive
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = {
            "type": "linear_margin_rule_interval",
            "schema_version": _SCHEMA_VERSION,
            "interval_id": self.interval_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "available_at": self.available_at,
            "tiers": self.tiers,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }
        if self.tier_boundary_convention is not (
            LinearMarginTierBoundaryConvention.LOWER_INCLUSIVE_UPPER_EXCLUSIVE
        ):
            payload["schema_version"] = 2
            payload["tier_boundary_convention"] = self.tier_boundary_convention.value
        return payload


def _interval_order(
    value: LinearMarginRuleInterval,
) -> tuple[int, int, int, str]:
    end = value.effective_to_exclusive
    return (
        value.effective_from.epoch_nanoseconds,
        1 if end is None else 0,
        0 if end is None else end.epoch_nanoseconds,
        value.interval_id,
    )


@dataclass(frozen=True, slots=True)
class LinearMarginRuleBook:
    rule_book_key: str
    rule_book_version: int
    instrument_id: InstrumentId
    settlement_currency_id: CurrencyId
    tier_scale: Scale
    intervals: tuple[LinearMarginRuleInterval, ...]
    config_hash: str

    def __post_init__(self) -> None:
        _text("rule_book_key", self.rule_book_key)
        if type(self.rule_book_version) is not int or self.rule_book_version <= 0:
            raise ValueError("rule_book_version must be a positive exact integer")
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.settlement_currency_id) is not CurrencyId:
            raise TypeError("settlement_currency_id must be exact CurrencyId")
        if type(self.tier_scale) is not Scale:
            raise TypeError("tier_scale must be exact Scale")
        if type(self.intervals) is not tuple or not all(
            type(value) is LinearMarginRuleInterval for value in self.intervals
        ):
            raise TypeError("intervals must be an exact tuple of Rule Intervals")
        ordered = tuple(sorted(self.intervals, key=_interval_order))
        object.__setattr__(self, "intervals", ordered)
        _hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash must match Margin Rule Book config")

    @classmethod
    def create(
        cls,
        *,
        rule_book_key: str,
        rule_book_version: int,
        instrument_id: InstrumentId,
        settlement_currency_id: CurrencyId,
        tier_scale: Scale,
        intervals: tuple[LinearMarginRuleInterval, ...],
    ) -> Self:
        ordered = tuple(sorted(intervals, key=_interval_order))
        payload = {
            "type": "linear_margin_rule_book_config",
            "schema_version": _SCHEMA_VERSION,
            "rule_book_key": rule_book_key,
            "rule_book_version": rule_book_version,
            "instrument_id": instrument_id,
            "settlement_currency_id": settlement_currency_id,
            "tier_scale": tier_scale.places,
            "intervals": ordered,
        }
        return cls(
            rule_book_key,
            rule_book_version,
            instrument_id,
            settlement_currency_id,
            tier_scale,
            ordered,
            canonical_sha256(payload),
        )

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "linear_margin_rule_book_config",
            "schema_version": _SCHEMA_VERSION,
            "rule_book_key": self.rule_book_key,
            "rule_book_version": self.rule_book_version,
            "instrument_id": self.instrument_id,
            "settlement_currency_id": self.settlement_currency_id,
            "tier_scale": self.tier_scale.places,
            "intervals": self.intervals,
        }

    @property
    def rule_book_hash(self) -> str:
        return canonical_sha256(self)

    def active_intervals(
        self, instant: UtcInstant
    ) -> tuple[LinearMarginRuleInterval, ...]:
        return tuple(value for value in self.intervals if value.contains(instant))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "linear_margin_rule_book",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class LinearMarginMarkEvidence:
    resolved_mark: ResolvedMark
    stale_policy: StaleMarkPolicy

    def __post_init__(self) -> None:
        if type(self.resolved_mark) is not ResolvedMark:
            raise TypeError("resolved_mark must be exact ResolvedMark")
        if type(self.stale_policy) is not StaleMarkPolicy:
            raise TypeError("stale_policy must be exact StaleMarkPolicy")

    @property
    def mark_evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_margin_mark_evidence",
            "schema_version": _SCHEMA_VERSION,
            "resolved_mark": self.resolved_mark,
            "stale_policy": self.stale_policy,
        }


@dataclass(frozen=True, slots=True)
class ExactLinearMarginAmount:
    currency_id: CurrencyId
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.currency_id) is not CurrencyId:
            raise TypeError("currency_id must be exact CurrencyId")
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("numerator and denominator must be exact integers")
        if self.denominator <= 0:
            raise ValueError("denominator must be positive")
        if gcd(abs(self.numerator), self.denominator) != 1:
            raise ValueError("Margin amount must be GCD-reduced")

    @property
    def amount_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "exact_linear_margin_amount",
            "schema_version": _SCHEMA_VERSION,
            "currency_id": self.currency_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
        }


@dataclass(frozen=True, slots=True)
class LinearInstrumentMarginRequest:
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    exposure_quantity: Quantity
    evaluated_at: SimulationInstant
    leverage_evidence: LinearMarginLeverageEvidence | None
    rule_book: LinearMarginRuleBook | None
    margin_mark_evidence: LinearMarginMarkEvidence | None
    settlement_cash_registration: LedgerBalanceRegistration
    requirement_quantization: QuantizationPolicy

    def __post_init__(self) -> None:
        if type(self.position_key) is not PositionBalanceKey:
            raise TypeError("position_key must be exact PositionBalanceKey")
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        if type(self.exposure_quantity) is not Quantity:
            raise TypeError("exposure_quantity must be exact Quantity")
        _instant("evaluated_at", self.evaluated_at)
        if type(self.leverage_evidence) not in (
            type(None),
            LinearMarginLeverageEvidence,
        ):
            raise TypeError("leverage_evidence must be exact Evidence or None")
        if type(self.rule_book) not in (type(None), LinearMarginRuleBook):
            raise TypeError("rule_book must be exact Rule Book or None")
        if type(self.margin_mark_evidence) not in (
            type(None),
            LinearMarginMarkEvidence,
        ):
            raise TypeError("margin_mark_evidence must be exact Evidence or None")
        if type(self.settlement_cash_registration) is not LedgerBalanceRegistration:
            raise TypeError("settlement_cash_registration must be exact Registration")
        if type(self.requirement_quantization) is not QuantizationPolicy:
            raise TypeError("requirement_quantization must be exact QuantizationPolicy")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_instrument_margin_request",
            "schema_version": _SCHEMA_VERSION,
            "position_key": self.position_key,
            "contract": self.contract,
            "exposure_quantity": self.exposure_quantity,
            "evaluated_at": self.evaluated_at,
            "leverage_evidence": self.leverage_evidence,
            "rule_book": self.rule_book,
            "margin_mark_evidence": self.margin_mark_evidence,
            "settlement_cash_registration": self.settlement_cash_registration,
            "requirement_quantization": self.requirement_quantization,
        }


class LinearInstrumentMarginFailureCode(str, Enum):
    MISSING_LEVERAGE_EVIDENCE = "missing_leverage_evidence"
    MISSING_MARGIN_RULE_BOOK = "missing_margin_rule_book"
    MISSING_MARGIN_MARK = "missing_margin_mark"
    POSITION_CONTEXT_MISMATCH = "position_context_mismatch"
    LEVERAGE_CONTEXT_MISMATCH = "leverage_context_mismatch"
    UNSUPPORTED_LEVERAGE_BASIS = "unsupported_leverage_basis"
    NON_POSITIVE_LEVERAGE = "non_positive_leverage"
    LEVERAGE_NOT_EFFECTIVE = "leverage_not_effective"
    LEVERAGE_NOT_AVAILABLE = "leverage_not_available"
    RULE_BOOK_CONTEXT_MISMATCH = "rule_book_context_mismatch"
    MISSING_HISTORICAL_RULE = "missing_historical_rule"
    OVERLAPPING_HISTORICAL_RULES = "overlapping_historical_rules"
    HISTORICAL_RULE_NOT_AVAILABLE = "historical_rule_not_available"
    TIER_ORDER_MISMATCH = "tier_order_mismatch"
    TIER_CONTEXT_MISMATCH = "tier_context_mismatch"
    TIER_GAP = "tier_gap"
    TIER_OVERLAP = "tier_overlap"
    UNSUPPORTED_TIER_BASIS = "unsupported_tier_basis"
    MARGIN_MARK_PURPOSE_MISMATCH = "margin_mark_purpose_mismatch"
    MARGIN_MARK_CONTEXT_MISMATCH = "margin_mark_context_mismatch"
    MARGIN_MARK_INSTANT_MISMATCH = "margin_mark_instant_mismatch"
    MARGIN_MARK_SCALE_MISMATCH = "margin_mark_scale_mismatch"
    NON_POSITIVE_MARGIN_MARK = "non_positive_margin_mark"
    MARGIN_MARK_POLICY_MISMATCH = "margin_mark_policy_mismatch"
    MARGIN_MARK_NOT_AVAILABLE = "margin_mark_not_available"
    NOTIONAL_OUTSIDE_TIER_COVERAGE = "notional_outside_tier_coverage"
    LEVERAGE_EXCEEDS_TIER_MAXIMUM = "leverage_exceeds_tier_maximum"
    NEGATIVE_MAINTENANCE_REQUIREMENT = "negative_maintenance_requirement"
    SETTLEMENT_CASH_CONTEXT_MISMATCH = "settlement_cash_context_mismatch"
    QUANTIZATION_SCALE_MISMATCH = "quantization_scale_mismatch"
    UNSAFE_MARGIN_ROUNDING = "unsafe_margin_rounding"


def _money_value(value: Money) -> tuple[int, int]:
    return value.units, value.scale.factor


def _less(left: Money, right: Money) -> bool:
    l_units, l_factor = _money_value(left)
    r_units, r_factor = _money_value(right)
    return l_units * r_factor < r_units * l_factor


def _greater(left: Money, right: Money) -> bool:
    l_units, l_factor = _money_value(left)
    r_units, r_factor = _money_value(right)
    return l_units * r_factor > r_units * l_factor


def _tier_order_invalid(tiers: tuple[LinearMarginTier, ...]) -> bool:
    return any(
        not _less(previous.notional_floor, current.notional_floor)
        for previous, current in zip(tiers, tiers[1:])
    )


def _tier_context_invalid(
    rule_book: LinearMarginRuleBook,
    tiers: tuple[LinearMarginTier, ...],
) -> bool:
    currency = str(rule_book.settlement_currency_id)
    scale = rule_book.tier_scale
    values = tuple(
        money
        for tier in tiers
        for money in (
            tier.notional_floor,
            tier.notional_cap,
            tier.maintenance_margin_deduction,
        )
        if money is not None
    )
    return any(value.currency != currency or value.scale != scale for value in values)


def _tier_gap(
    tiers: tuple[LinearMarginTier, ...],
    convention: LinearMarginTierBoundaryConvention,
) -> bool:
    if not tiers or tiers[0].notional_floor.units != 0:
        return True
    if (
        convention
        is LinearMarginTierBoundaryConvention.LOWER_INCLUSIVE_UPPER_EXCLUSIVE
        and tiers[-1].notional_cap is not None
    ):
        return True
    return any(
        previous.notional_cap is not None
        and _less(previous.notional_cap, current.notional_floor)
        for previous, current in zip(tiers, tiers[1:])
    )


def _tier_overlap(tiers: tuple[LinearMarginTier, ...]) -> bool:
    return any(
        previous.notional_cap is None
        or _greater(previous.notional_cap, current.notional_floor)
        for previous, current in zip(tiers, tiers[1:])
    )


def _tier_basis_invalid(tiers: tuple[LinearMarginTier, ...]) -> bool:
    return any(
        tier.maximum_leverage.basis != _LEVERAGE_BASIS
        or tier.maintenance_margin_rate.basis != _MAINTENANCE_BASIS
        for tier in tiers
    )


def _reduced(
    currency: CurrencyId, numerator: int, denominator: int
) -> ExactLinearMarginAmount:
    divisor = gcd(abs(numerator), denominator)
    return ExactLinearMarginAmount(
        currency, numerator // divisor, denominator // divisor
    )


def _exact_notional(
    request: LinearInstrumentMarginRequest,
) -> ExactLinearMarginAmount:
    evidence = request.margin_mark_evidence
    if evidence is None:
        raise AssertionError("Margin notional requires Mark evidence")
    quantity = request.exposure_quantity
    multiplier = request.contract.contract_multiplier
    price = evidence.resolved_mark.price
    return _reduced(
        request.contract.instrument.settlement_currency,
        abs(quantity.units) * multiplier.units * price.units,
        quantity.scale.factor * multiplier.scale.factor * price.scale.factor,
    )


def _amount_at_least_money(
    amount: ExactLinearMarginAmount, money: Money
) -> bool:
    return (
        amount.numerator * money.scale.factor
        >= money.units * amount.denominator
    )


def _amount_below_money(
    amount: ExactLinearMarginAmount, money: Money
) -> bool:
    return (
        amount.numerator * money.scale.factor
        < money.units * amount.denominator
    )


def _amount_above_money(
    amount: ExactLinearMarginAmount, money: Money
) -> bool:
    return (
        amount.numerator * money.scale.factor
        > money.units * amount.denominator
    )


def _amount_at_most_money(
    amount: ExactLinearMarginAmount, money: Money
) -> bool:
    return not _amount_above_money(amount, money)


def _selected_tier(
    tiers: tuple[LinearMarginTier, ...],
    notional: ExactLinearMarginAmount,
    convention: LinearMarginTierBoundaryConvention,
) -> LinearMarginTier | None:
    if convention is LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE:
        matches = tuple(
            tier
            for tier in tiers
            if (
                _amount_above_money(notional, tier.notional_floor)
                or (notional.numerator == 0 and tier.notional_floor.units == 0)
            )
            and (
                tier.notional_cap is None
                or _amount_at_most_money(notional, tier.notional_cap)
            )
        )
    else:
        matches = tuple(
            tier
            for tier in tiers
            if _amount_at_least_money(notional, tier.notional_floor)
            and (
                tier.notional_cap is None
                or _amount_below_money(notional, tier.notional_cap)
            )
        )
    if len(matches) > 1:
        raise AssertionError("valid Tier set cannot select multiple Tiers")
    return matches[0] if matches else None


def _exact_initial(
    notional: ExactLinearMarginAmount, leverage: Rate
) -> ExactLinearMarginAmount:
    return _reduced(
        notional.currency_id,
        notional.numerator * leverage.scale.factor,
        notional.denominator * leverage.units,
    )


def _exact_maintenance(
    notional: ExactLinearMarginAmount, tier: LinearMarginTier
) -> ExactLinearMarginAmount:
    rate = tier.maintenance_margin_rate
    deduction = tier.maintenance_margin_deduction
    numerator = (
        notional.numerator * rate.units * deduction.scale.factor
        - deduction.units * notional.denominator * rate.scale.factor
    )
    denominator = (
        notional.denominator * rate.scale.factor * deduction.scale.factor
    )
    return _reduced(notional.currency_id, numerator, denominator)


def _leverage_exceeds(selected: Rate, maximum: Rate) -> bool:
    return (
        selected.units * maximum.scale.factor
        > maximum.units * selected.scale.factor
    )


type _EvaluationValues = tuple[
    LinearMarginRuleInterval,
    LinearMarginTier,
    ExactLinearMarginAmount,
    ExactLinearMarginAmount,
    ExactLinearMarginAmount,
]


def _evaluate(
    request: LinearInstrumentMarginRequest,
    *,
    allow_independent_tier_scale: bool = False,
    allow_raw_margin_mark_scale: bool = False,
) -> tuple[LinearInstrumentMarginFailureCode | None, _EvaluationValues | None]:
    leverage = request.leverage_evidence
    rule_book = request.rule_book
    mark_evidence = request.margin_mark_evidence
    if leverage is None:
        return LinearInstrumentMarginFailureCode.MISSING_LEVERAGE_EVIDENCE, None
    if rule_book is None:
        return LinearInstrumentMarginFailureCode.MISSING_MARGIN_RULE_BOOK, None
    if mark_evidence is None:
        return LinearInstrumentMarginFailureCode.MISSING_MARGIN_MARK, None

    instrument = request.contract.instrument
    instrument_id = instrument.instrument_id
    quantity = request.exposure_quantity
    if (
        request.position_key.venue_id != instrument_id.venue
        or request.position_key.instrument_id != instrument_id
        or quantity.instrument_id != str(instrument_id)
        or quantity.scale != request.contract.quantity_scale
    ):
        return LinearInstrumentMarginFailureCode.POSITION_CONTEXT_MISMATCH, None
    if (
        leverage.account_id != request.position_key.account_id
        or leverage.instrument_id != instrument_id
    ):
        return LinearInstrumentMarginFailureCode.LEVERAGE_CONTEXT_MISMATCH, None
    if leverage.selected_leverage.basis != _LEVERAGE_BASIS:
        return LinearInstrumentMarginFailureCode.UNSUPPORTED_LEVERAGE_BASIS, None
    if leverage.selected_leverage.units <= 0:
        return LinearInstrumentMarginFailureCode.NON_POSITIVE_LEVERAGE, None
    if not leverage.contains(request.evaluated_at.instant):
        return LinearInstrumentMarginFailureCode.LEVERAGE_NOT_EFFECTIVE, None
    if leverage.available_at > request.evaluated_at:
        return LinearInstrumentMarginFailureCode.LEVERAGE_NOT_AVAILABLE, None
    if (
        rule_book.instrument_id != instrument_id
        or rule_book.settlement_currency_id != instrument.settlement_currency
        or (
            not allow_independent_tier_scale
            and rule_book.tier_scale != request.contract.price_scale
        )
    ):
        return LinearInstrumentMarginFailureCode.RULE_BOOK_CONTEXT_MISMATCH, None

    active = rule_book.active_intervals(request.evaluated_at.instant)
    if not active:
        return LinearInstrumentMarginFailureCode.MISSING_HISTORICAL_RULE, None
    if len(active) != 1:
        return LinearInstrumentMarginFailureCode.OVERLAPPING_HISTORICAL_RULES, None
    interval = active[0]
    if interval.available_at > request.evaluated_at:
        return LinearInstrumentMarginFailureCode.HISTORICAL_RULE_NOT_AVAILABLE, None
    tiers = interval.tiers
    if _tier_order_invalid(tiers):
        return LinearInstrumentMarginFailureCode.TIER_ORDER_MISMATCH, None
    if _tier_context_invalid(rule_book, tiers):
        return LinearInstrumentMarginFailureCode.TIER_CONTEXT_MISMATCH, None
    if _tier_gap(tiers, interval.tier_boundary_convention):
        return LinearInstrumentMarginFailureCode.TIER_GAP, None
    if _tier_overlap(tiers):
        return LinearInstrumentMarginFailureCode.TIER_OVERLAP, None
    if _tier_basis_invalid(tiers):
        return LinearInstrumentMarginFailureCode.UNSUPPORTED_TIER_BASIS, None

    mark = mark_evidence.resolved_mark
    policy = mark_evidence.stale_policy
    if (
        mark.price_purpose is not PricePurpose.MARGIN
        or policy.price_purpose is not PricePurpose.MARGIN
    ):
        return LinearInstrumentMarginFailureCode.MARGIN_MARK_PURPOSE_MISMATCH, None
    if (
        mark.instrument_id != instrument_id
        or mark.quote_currency_id != instrument.settlement_currency
    ):
        return LinearInstrumentMarginFailureCode.MARGIN_MARK_CONTEXT_MISMATCH, None
    if mark.resolved_at != request.evaluated_at.instant:
        return LinearInstrumentMarginFailureCode.MARGIN_MARK_INSTANT_MISMATCH, None
    if (
        not allow_raw_margin_mark_scale
        and mark.price.scale != request.contract.price_scale
    ):
        return LinearInstrumentMarginFailureCode.MARGIN_MARK_SCALE_MISMATCH, None
    if mark.price.units <= 0:
        return LinearInstrumentMarginFailureCode.NON_POSITIVE_MARGIN_MARK, None
    expected_age = (
        mark.resolved_at.epoch_nanoseconds - mark.observed_at.epoch_nanoseconds
    )
    if (
        mark.stale_policy_key != policy.policy_key
        or mark.stale_policy_version != policy.policy_version
        or mark.stale_policy_hash != policy.policy_hash
        or mark.age_nanoseconds != expected_age
        or mark.age_nanoseconds > policy.max_age_nanoseconds
        or (mark.age_nanoseconds > 0 and not policy.allow_forward_fill)
    ):
        return LinearInstrumentMarginFailureCode.MARGIN_MARK_POLICY_MISMATCH, None
    if mark.available_at > request.evaluated_at.instant:
        return LinearInstrumentMarginFailureCode.MARGIN_MARK_NOT_AVAILABLE, None

    notional = _exact_notional(request)
    tier = _selected_tier(tiers, notional, interval.tier_boundary_convention)
    if tier is None:
        return LinearInstrumentMarginFailureCode.NOTIONAL_OUTSIDE_TIER_COVERAGE, None
    if _leverage_exceeds(leverage.selected_leverage, tier.maximum_leverage):
        return LinearInstrumentMarginFailureCode.LEVERAGE_EXCEEDS_TIER_MAXIMUM, None
    initial = _exact_initial(notional, leverage.selected_leverage)
    maintenance = _exact_maintenance(notional, tier)
    if maintenance.numerator < 0:
        return LinearInstrumentMarginFailureCode.NEGATIVE_MAINTENANCE_REQUIREMENT, None

    registration = request.settlement_cash_registration
    expected_cash_key = CashBalanceKey(
        request.position_key.account_id,
        request.position_key.venue_id,
        instrument.settlement_currency,
    )
    if type(registration.key) is not CashBalanceKey or registration.key != expected_cash_key:
        return LinearInstrumentMarginFailureCode.SETTLEMENT_CASH_CONTEXT_MISMATCH, None
    if request.requirement_quantization.target_scale != registration.scale:
        return LinearInstrumentMarginFailureCode.QUANTIZATION_SCALE_MISMATCH, None
    if request.requirement_quantization.rounding is not RoundingPolicy.CEILING:
        return LinearInstrumentMarginFailureCode.UNSAFE_MARGIN_ROUNDING, None
    return None, (interval, tier, notional, initial, maintenance)


def _quantized(
    exact: ExactLinearMarginAmount, policy: QuantizationPolicy
) -> Money:
    return Money(
        round_ratio(
            exact.numerator * policy.target_scale.factor,
            exact.denominator,
            RoundingPolicy.CEILING,
        ),
        policy.target_scale,
        str(exact.currency_id),
    )


def _subject_values(
    request: LinearInstrumentMarginRequest,
    *,
    include_tier: bool,
) -> tuple[LinearMarginRuleInterval | None, LinearMarginTier | None]:
    interval = None
    tier = None
    rule_book = request.rule_book
    if rule_book is not None:
        active = rule_book.active_intervals(request.evaluated_at.instant)
        if len(active) == 1:
            interval = active[0]
            tiers = interval.tiers
            if (
                include_tier
                and not _tier_order_invalid(tiers)
                and not _tier_context_invalid(rule_book, tiers)
                and not _tier_gap(tiers, interval.tier_boundary_convention)
                and not _tier_overlap(tiers)
                and not _tier_basis_invalid(tiers)
                and request.margin_mark_evidence is not None
            ):
                notional = _exact_notional(request)
                tier = _selected_tier(
                    tiers, notional, interval.tier_boundary_convention
                )
    return interval, tier


def _failure_subject_ids(
    request: LinearInstrumentMarginRequest,
    code: LinearInstrumentMarginFailureCode,
) -> tuple[str, ...]:
    leverage = request.leverage_evidence
    rule_book = request.rule_book
    mark = request.margin_mark_evidence
    include_tier = code in {
        LinearInstrumentMarginFailureCode.LEVERAGE_EXCEEDS_TIER_MAXIMUM,
        LinearInstrumentMarginFailureCode.NEGATIVE_MAINTENANCE_REQUIREMENT,
        LinearInstrumentMarginFailureCode.SETTLEMENT_CASH_CONTEXT_MISMATCH,
        LinearInstrumentMarginFailureCode.QUANTIZATION_SCALE_MISMATCH,
        LinearInstrumentMarginFailureCode.UNSAFE_MARGIN_ROUNDING,
    }
    interval, tier = _subject_values(request, include_tier=include_tier)
    return (
        code.value,
        request.position_key.account_id,
        str(request.contract.instrument.instrument_id),
        leverage.source_key if leverage is not None else "missing-margin-leverage",
        rule_book.rule_book_key if rule_book is not None else "missing-margin-rule-book",
        interval.interval_id if interval is not None else "missing-margin-rule-interval",
        tier.tier_id if tier is not None else "missing-margin-tier",
        mark.resolved_mark.mark_id if mark is not None else "missing-margin-mark",
    )


@dataclass(frozen=True, slots=True)
class LinearInstrumentMarginResult:
    component_ref: ProfileComponentRef
    request: LinearInstrumentMarginRequest
    request_hash: str
    resolved_interval: LinearMarginRuleInterval
    resolved_tier: LinearMarginTier
    exact_notional: ExactLinearMarginAmount
    exact_initial_margin: ExactLinearMarginAmount
    exact_maintenance_margin: ExactLinearMarginAmount
    initial_margin: Money
    maintenance_margin: Money

    def __post_init__(self) -> None:
        if self.component_ref not in (_component_ref(), _component_ref_v2()):
            raise ValueError("component_ref must match Margin requirement component")
        if type(self.request) is not LinearInstrumentMarginRequest:
            raise TypeError("request must be exact LinearInstrumentMarginRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        failure, values = _evaluate(
            self.request,
            allow_independent_tier_scale=self.component_ref == _component_ref_v2(),
            allow_raw_margin_mark_scale=self.component_ref == _component_ref_v2(),
        )
        if failure is not None or values is None:
            raise ValueError("Result Request must have no business failure")
        interval, tier, notional, initial, maintenance = values
        expected = (
            interval,
            tier,
            notional,
            initial,
            maintenance,
            _quantized(initial, self.request.requirement_quantization),
            _quantized(maintenance, self.request.requirement_quantization),
        )
        actual = (
            self.resolved_interval,
            self.resolved_tier,
            self.exact_notional,
            self.exact_initial_margin,
            self.exact_maintenance_margin,
            self.initial_margin,
            self.maintenance_margin,
        )
        if actual != expected:
            raise ValueError("Result fields must match embedded Request")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_instrument_margin_result",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "resolved_interval": self.resolved_interval,
            "resolved_tier": self.resolved_tier,
            "exact_notional": self.exact_notional,
            "exact_initial_margin": self.exact_initial_margin,
            "exact_maintenance_margin": self.exact_maintenance_margin,
            "initial_margin": self.initial_margin,
            "maintenance_margin": self.maintenance_margin,
        }


@dataclass(frozen=True, slots=True)
class LinearInstrumentMarginFailure:
    component_ref: ProfileComponentRef
    request: LinearInstrumentMarginRequest
    request_hash: str
    code: LinearInstrumentMarginFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.component_ref not in (_component_ref(), _component_ref_v2()):
            raise ValueError("component_ref must match Margin requirement component")
        if type(self.request) is not LinearInstrumentMarginRequest:
            raise TypeError("request must be exact LinearInstrumentMarginRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if type(self.code) is not LinearInstrumentMarginFailureCode:
            raise TypeError("code must be exact Margin Failure Code")
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be an exact tuple of strings")
        failure, _ = _evaluate(
            self.request,
            allow_independent_tier_scale=self.component_ref == _component_ref_v2(),
            allow_raw_margin_mark_scale=self.component_ref == _component_ref_v2(),
        )
        if failure is None or failure is not self.code:
            raise ValueError("Failure must match first Request failure")
        if self.subject_ids != _failure_subject_ids(self.request, self.code):
            raise ValueError("subject_ids must match embedded Request")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_instrument_margin_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class LinearInstrumentMarginModel:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref()

    def evaluate_margin(
        self, request: LinearInstrumentMarginRequest, /
    ) -> ProfilePortOutcome[
        LinearInstrumentMarginResult, LinearInstrumentMarginFailure
    ]:
        if type(request) is not LinearInstrumentMarginRequest:
            raise TypeError("request must be exact LinearInstrumentMarginRequest")
        failure, values = _evaluate(request)
        if failure is not None:
            value = LinearInstrumentMarginFailure(
                self.component_ref,
                request,
                request.request_hash,
                failure,
                _failure_subject_ids(request, failure),
            )
            return ProfilePortOutcome.for_failure(self.component_ref, request, value)
        if values is None:
            raise AssertionError("successful Margin evaluation requires values")
        interval, tier, notional, initial, maintenance = values
        result = LinearInstrumentMarginResult(
            self.component_ref,
            request,
            request.request_hash,
            interval,
            tier,
            notional,
            initial,
            maintenance,
            _quantized(initial, request.requirement_quantization),
            _quantized(maintenance, request.requirement_quantization),
        )
        return ProfilePortOutcome.for_result(self.component_ref, request, result)


@dataclass(frozen=True, slots=True)
class LinearInstrumentMarginModelV2:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref_v2()

    def evaluate_margin(
        self, request: LinearInstrumentMarginRequest, /
    ) -> ProfilePortOutcome[
        LinearInstrumentMarginResult, LinearInstrumentMarginFailure
    ]:
        if type(request) is not LinearInstrumentMarginRequest:
            raise TypeError("request must be exact LinearInstrumentMarginRequest")
        failure, values = _evaluate(
            request,
            allow_independent_tier_scale=True,
            allow_raw_margin_mark_scale=True,
        )
        if failure is not None:
            value = LinearInstrumentMarginFailure(
                self.component_ref,
                request,
                request.request_hash,
                failure,
                _failure_subject_ids(request, failure),
            )
            return ProfilePortOutcome.for_failure(self.component_ref, request, value)
        if values is None:
            raise AssertionError("successful Margin evaluation requires values")
        interval, tier, notional, initial, maintenance = values
        result = LinearInstrumentMarginResult(
            self.component_ref,
            request,
            request.request_hash,
            interval,
            tier,
            notional,
            initial,
            maintenance,
            _quantized(initial, request.requirement_quantization),
            _quantized(maintenance, request.requirement_quantization),
        )
        return ProfilePortOutcome.for_result(self.component_ref, request, result)
