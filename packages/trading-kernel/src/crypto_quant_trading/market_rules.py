"""Point-in-time generic market-rule validation for translated orders."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from crypto_quant_domain import (
    ExecutionStyle,
    InstrumentId,
    Money,
    OrderSide,
    OrderStatus,
    PortfolioSnapshot,
    PositionEffect,
    Price,
    Quantity,
    RoundingPolicy,
    Scale,
    SessionId,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .orders import OrderEventStream
from .ports import ProfileComponentRef, ProfilePortType
from .reservations import ResourceReservationState
from .settlement import AvailabilityState
from .sizing import QuantityLattice
from .translation import ExecutableOrderSpec


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DECISION_ID_RE = re.compile(r"^market-rule-decision-v1:sha256:[0-9a-f]{64}$")
_INTERVAL_ID_RE = re.compile(r"^order-rule-interval-v1:sha256:[0-9a-f]{64}$")


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _positive_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _tagged_id(prefix: str, payload: Any) -> str:
    return f"{prefix}:sha256:{canonical_sha256(payload).removeprefix('sha256:')}"


class MarketSessionState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class NotionalPriceBasis(str, Enum):
    LIMIT_CONSTRAINT = "limit_constraint"
    TRIGGER_CONSTRAINT = "trigger_constraint"
    SUPPLIED_REFERENCE = "supplied_reference"


@dataclass(frozen=True, slots=True)
class OrderRuleNotionalEvidence:
    basis: NotionalPriceBasis
    price: Price
    source_hash: str
    available_at: UtcInstant | None

    def __post_init__(self) -> None:
        if not isinstance(self.basis, NotionalPriceBasis):
            raise TypeError("basis must be NotionalPriceBasis")
        if not isinstance(self.price, Price):
            raise TypeError("price must be Price")
        _require_hash("source_hash", self.source_hash)
        if self.basis is NotionalPriceBasis.SUPPLIED_REFERENCE:
            if not isinstance(self.available_at, UtcInstant):
                raise ValueError("supplied reference requires available_at")
        elif self.available_at is not None:
            raise ValueError("constraint notional evidence cannot have available_at")
        if self.basis is not NotionalPriceBasis.SUPPLIED_REFERENCE:
            if self.source_hash != canonical_sha256(self.price):
                raise ValueError("constraint source_hash must identify its exact Price")

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_rule_notional_evidence",
            "schema_version": 1,
            "basis": self.basis.value,
            "price": self.price,
            "source_hash": self.source_hash,
            "available_at": self.available_at,
        }


@dataclass(frozen=True, slots=True)
class SupplementalOrderRuleDecision:
    rule_key: str
    approved: bool
    reason_code: str

    def __post_init__(self) -> None:
        _canonical_text("rule_key", self.rule_key)
        if type(self.approved) is not bool:
            raise TypeError("approved must be bool")
        _canonical_text("reason_code", self.reason_code)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "supplemental_order_rule_decision",
            "rule_key": self.rule_key,
            "approved": self.approved,
            "reason_code": self.reason_code,
        }


def _ordered_sides(values: tuple[OrderSide, ...]) -> tuple[OrderSide, ...]:
    if any(not isinstance(value, OrderSide) for value in values):
        raise TypeError("permitted_sides must contain OrderSide")
    ordered = tuple(sorted(values, key=lambda value: value.value))
    if len(set(ordered)) != len(ordered):
        raise ValueError("permitted_sides cannot contain duplicates")
    return ordered


def _ordered_position_effects(
    values: tuple[PositionEffect, ...],
) -> tuple[PositionEffect, ...]:
    if any(not isinstance(value, PositionEffect) for value in values):
        raise TypeError("permitted_position_effects must contain PositionEffect")
    ordered = tuple(sorted(values, key=lambda value: value.value))
    if len(set(ordered)) != len(ordered):
        raise ValueError("permitted_position_effects cannot contain duplicates")
    return ordered


def _ordered_supplemental_decisions(
    values: tuple[SupplementalOrderRuleDecision, ...],
) -> tuple[SupplementalOrderRuleDecision, ...]:
    if any(not isinstance(value, SupplementalOrderRuleDecision) for value in values):
        raise TypeError(
            "supplemental_decisions must contain SupplementalOrderRuleDecision"
        )
    ordered = tuple(sorted(values, key=lambda value: value.rule_key))
    if len({value.rule_key for value in ordered}) != len(ordered):
        raise ValueError("supplemental_decisions cannot contain duplicate rule keys")
    return ordered


def _snapshot_config_payload(
    *,
    component_ref: ProfileComponentRef,
    instrument_id: InstrumentId,
    session_id: SessionId,
    session_state: MarketSessionState,
    quantity_lattice: QuantityLattice,
    price_scale: Scale,
    price_tick_units: int,
    lower_price_limit: Price | None,
    upper_price_limit: Price | None,
    permitted_sides: tuple[OrderSide, ...],
    permitted_position_effects: tuple[PositionEffect, ...],
    reduce_only_required: bool,
    notional_rounding: RoundingPolicy,
    supplemental_decisions: tuple[SupplementalOrderRuleDecision, ...],
    max_limit_order_quantity_units: int | None,
    max_market_order_quantity_units: int | None,
    market_quantity_lattice: QuantityLattice | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "order_rule_snapshot_config",
        "schema_version": (
            3
            if market_quantity_lattice is not None
            else 2
            if max_limit_order_quantity_units is not None
            or max_market_order_quantity_units is not None
            else 1
        ),
        "component_ref": component_ref,
        "instrument_id": instrument_id,
        "session_id": session_id,
        "session_state": session_state.value,
        "quantity_lattice": quantity_lattice,
        "price_scale": price_scale.places,
        "price_tick_units": price_tick_units,
        "lower_price_limit": lower_price_limit,
        "upper_price_limit": upper_price_limit,
        "permitted_sides": [value.value for value in permitted_sides],
        "permitted_position_effects": [
            value.value for value in permitted_position_effects
        ],
        "reduce_only_required": reduce_only_required,
        "notional_rounding": notional_rounding.value,
        "supplemental_decisions": supplemental_decisions,
    }
    if max_limit_order_quantity_units is not None:
        payload["max_limit_order_quantity_units"] = max_limit_order_quantity_units
    if max_market_order_quantity_units is not None:
        payload["max_market_order_quantity_units"] = max_market_order_quantity_units
    if market_quantity_lattice is not None:
        payload["market_quantity_lattice"] = market_quantity_lattice
    return payload


@dataclass(frozen=True, slots=True)
class OrderRuleSnapshot:
    component_ref: ProfileComponentRef
    instrument_id: InstrumentId
    session_id: SessionId
    session_state: MarketSessionState
    quantity_lattice: QuantityLattice
    price_scale: Scale
    price_tick_units: int
    lower_price_limit: Price | None
    upper_price_limit: Price | None
    permitted_sides: tuple[OrderSide, ...]
    permitted_position_effects: tuple[PositionEffect, ...]
    reduce_only_required: bool
    notional_rounding: RoundingPolicy
    supplemental_decisions: tuple[SupplementalOrderRuleDecision, ...]
    config_hash: str
    max_limit_order_quantity_units: int | None = None
    max_market_order_quantity_units: int | None = None
    market_quantity_lattice: QuantityLattice | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.component_ref, ProfileComponentRef):
            raise TypeError("component_ref must be ProfileComponentRef")
        if self.component_ref.port_type is not ProfilePortType.ORDER_RULE_MODEL:
            raise ValueError("component_ref must target ORDER_RULE_MODEL")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.session_id, SessionId):
            raise TypeError("session_id must be SessionId")
        if not isinstance(self.session_state, MarketSessionState):
            raise TypeError("session_state must be MarketSessionState")
        if not isinstance(self.quantity_lattice, QuantityLattice):
            raise TypeError("quantity_lattice must be QuantityLattice")
        if self.quantity_lattice.instrument_id != self.instrument_id:
            raise ValueError("quantity lattice instrument mismatch")
        if self.market_quantity_lattice is not None:
            if not isinstance(self.market_quantity_lattice, QuantityLattice):
                raise TypeError("market_quantity_lattice must be QuantityLattice or None")
            if self.market_quantity_lattice.instrument_id != self.instrument_id:
                raise ValueError("market quantity lattice instrument mismatch")
        if not isinstance(self.price_scale, Scale):
            raise TypeError("price_scale must be Scale")
        _positive_integer("price_tick_units", self.price_tick_units)
        self._validate_price_limit("lower_price_limit", self.lower_price_limit)
        self._validate_price_limit("upper_price_limit", self.upper_price_limit)
        if (
            self.lower_price_limit is not None
            and self.upper_price_limit is not None
            and self.lower_price_limit.units > self.upper_price_limit.units
        ):
            raise ValueError("lower price limit cannot exceed upper price limit")
        sides = _ordered_sides(self.permitted_sides)
        effects = _ordered_position_effects(self.permitted_position_effects)
        decisions = _ordered_supplemental_decisions(self.supplemental_decisions)
        if type(self.reduce_only_required) is not bool:
            raise TypeError("reduce_only_required must be bool")
        if not isinstance(self.notional_rounding, RoundingPolicy):
            raise TypeError("notional_rounding must be RoundingPolicy")
        for name, value, lattice in (
            (
                "max_limit_order_quantity_units",
                self.max_limit_order_quantity_units,
                self.quantity_lattice,
            ),
            (
                "max_market_order_quantity_units",
                self.max_market_order_quantity_units,
                self.market_quantity_lattice or self.quantity_lattice,
            ),
        ):
            if value is not None:
                _positive_integer(name, value)
                if value % lattice.step_units:
                    raise ValueError(f"{name} must be a multiple of lattice step")
        object.__setattr__(self, "permitted_sides", sides)
        object.__setattr__(self, "permitted_position_effects", effects)
        object.__setattr__(self, "supplemental_decisions", decisions)
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash does not match order rule snapshot")

    def _validate_price_limit(self, name: str, value: Price | None) -> None:
        if value is None:
            return
        if not isinstance(value, Price):
            raise TypeError(f"{name} must be Price or None")
        if value.instrument_id != str(self.instrument_id):
            raise ValueError(f"{name} instrument mismatch")
        if value.quote_currency != self.quantity_lattice.min_notional.currency:
            raise ValueError(f"{name} quote currency mismatch")
        if value.scale != self.price_scale:
            raise ValueError(f"{name} scale mismatch")
        if value.units <= 0:
            raise ValueError(f"{name} must be positive")

    @classmethod
    def create(
        cls,
        *,
        component_ref: ProfileComponentRef,
        instrument_id: InstrumentId,
        session_id: SessionId,
        session_state: MarketSessionState,
        quantity_lattice: QuantityLattice,
        price_scale: Scale,
        price_tick_units: int,
        lower_price_limit: Price | None,
        upper_price_limit: Price | None,
        permitted_sides: tuple[OrderSide, ...],
        permitted_position_effects: tuple[PositionEffect, ...],
        reduce_only_required: bool,
        notional_rounding: RoundingPolicy,
        supplemental_decisions: tuple[SupplementalOrderRuleDecision, ...],
        max_limit_order_quantity_units: int | None = None,
        max_market_order_quantity_units: int | None = None,
        market_quantity_lattice: QuantityLattice | None = None,
    ) -> Self:
        sides = _ordered_sides(permitted_sides)
        effects = _ordered_position_effects(permitted_position_effects)
        decisions = _ordered_supplemental_decisions(supplemental_decisions)
        payload = _snapshot_config_payload(
            component_ref=component_ref,
            instrument_id=instrument_id,
            session_id=session_id,
            session_state=session_state,
            quantity_lattice=quantity_lattice,
            price_scale=price_scale,
            price_tick_units=price_tick_units,
            lower_price_limit=lower_price_limit,
            upper_price_limit=upper_price_limit,
            permitted_sides=sides,
            permitted_position_effects=effects,
            reduce_only_required=reduce_only_required,
            notional_rounding=notional_rounding,
            supplemental_decisions=decisions,
            max_limit_order_quantity_units=max_limit_order_quantity_units,
            max_market_order_quantity_units=max_market_order_quantity_units,
            market_quantity_lattice=market_quantity_lattice,
        )
        return cls(
            component_ref=component_ref,
            instrument_id=instrument_id,
            session_id=session_id,
            session_state=session_state,
            quantity_lattice=quantity_lattice,
            price_scale=price_scale,
            price_tick_units=price_tick_units,
            lower_price_limit=lower_price_limit,
            upper_price_limit=upper_price_limit,
            permitted_sides=sides,
            permitted_position_effects=effects,
            reduce_only_required=reduce_only_required,
            notional_rounding=notional_rounding,
            supplemental_decisions=decisions,
            config_hash=canonical_sha256(payload),
            max_limit_order_quantity_units=max_limit_order_quantity_units,
            max_market_order_quantity_units=max_market_order_quantity_units,
            market_quantity_lattice=market_quantity_lattice,
        )

    def config_payload(self) -> dict[str, Any]:
        return _snapshot_config_payload(
            component_ref=self.component_ref,
            instrument_id=self.instrument_id,
            session_id=self.session_id,
            session_state=self.session_state,
            quantity_lattice=self.quantity_lattice,
            price_scale=self.price_scale,
            price_tick_units=self.price_tick_units,
            lower_price_limit=self.lower_price_limit,
            upper_price_limit=self.upper_price_limit,
            permitted_sides=self.permitted_sides,
            permitted_position_effects=self.permitted_position_effects,
            reduce_only_required=self.reduce_only_required,
            notional_rounding=self.notional_rounding,
            supplemental_decisions=self.supplemental_decisions,
            max_limit_order_quantity_units=self.max_limit_order_quantity_units,
            max_market_order_quantity_units=self.max_market_order_quantity_units,
            market_quantity_lattice=self.market_quantity_lattice,
        )

    @property
    def snapshot_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "order_rule_snapshot",
            "config_hash": self.config_hash,
        }


def _quantity_lattice_for_style(
    snapshot: OrderRuleSnapshot, style: ExecutionStyle
) -> QuantityLattice:
    if style in {ExecutionStyle.LIMIT, ExecutionStyle.STOP_LIMIT}:
        return snapshot.quantity_lattice
    return snapshot.market_quantity_lattice or snapshot.quantity_lattice


@dataclass(frozen=True, slots=True)
class OrderRuleInterval:
    interval_id: str
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant | None
    snapshot: OrderRuleSnapshot

    def __post_init__(self) -> None:
        if not isinstance(self.interval_id, str) or _INTERVAL_ID_RE.fullmatch(self.interval_id) is None:
            raise ValueError("interval_id must be a canonical order rule interval identity")
        if not isinstance(self.effective_from, UtcInstant):
            raise TypeError("effective_from must be UtcInstant")
        if self.effective_to_exclusive is not None:
            if not isinstance(self.effective_to_exclusive, UtcInstant):
                raise TypeError("effective_to_exclusive must be UtcInstant or None")
            if self.effective_to_exclusive <= self.effective_from:
                raise ValueError("effective interval must be nonempty")
        if not isinstance(self.snapshot, OrderRuleSnapshot):
            raise TypeError("snapshot must be OrderRuleSnapshot")
        if self.interval_id != _tagged_id("order-rule-interval-v1", self.identity_payload()):
            raise ValueError("interval_id mismatch")

    @classmethod
    def create(
        cls,
        *,
        effective_from: UtcInstant,
        effective_to_exclusive: UtcInstant | None,
        snapshot: OrderRuleSnapshot,
    ) -> Self:
        payload = {
            "type": "order_rule_interval_identity",
            "schema_version": 1,
            "effective_from": effective_from,
            "effective_to_exclusive": effective_to_exclusive,
            "snapshot_hash": snapshot.snapshot_hash,
        }
        return cls(
            interval_id=_tagged_id("order-rule-interval-v1", payload),
            effective_from=effective_from,
            effective_to_exclusive=effective_to_exclusive,
            snapshot=snapshot,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "type": "order_rule_interval_identity",
            "schema_version": 1,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "snapshot_hash": self.snapshot.snapshot_hash,
        }

    @property
    def interval_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant and (
            self.effective_to_exclusive is None or instant < self.effective_to_exclusive
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_rule_interval",
            "schema_version": 1,
            "interval_id": self.interval_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "snapshot": self.snapshot,
        }


def _interval_sort_key(value: OrderRuleInterval) -> tuple[int, int, str]:
    stop = (
        value.effective_to_exclusive.epoch_nanoseconds
        if value.effective_to_exclusive is not None
        else 2**127
    )
    return value.effective_from.epoch_nanoseconds, stop, value.interval_id


def _ordered_intervals(
    values: tuple[OrderRuleInterval, ...],
) -> tuple[OrderRuleInterval, ...]:
    if any(not isinstance(value, OrderRuleInterval) for value in values):
        raise TypeError("intervals must contain OrderRuleInterval")
    ordered = tuple(sorted(values, key=_interval_sort_key))
    if len({value.interval_id for value in ordered}) != len(ordered):
        raise ValueError("timeline intervals cannot contain duplicate identities")
    return ordered


@dataclass(frozen=True, slots=True)
class OrderRuleTimeline:
    timeline_key: str
    timeline_version: int
    instrument_id: InstrumentId
    intervals: tuple[OrderRuleInterval, ...]
    config_hash: str

    def __post_init__(self) -> None:
        _canonical_text("timeline_key", self.timeline_key)
        _positive_integer("timeline_version", self.timeline_version)
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        intervals = _ordered_intervals(self.intervals)
        if any(value.snapshot.instrument_id != self.instrument_id for value in intervals):
            raise ValueError("timeline interval instrument mismatch")
        object.__setattr__(self, "intervals", intervals)
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash does not match order rule timeline")

    @classmethod
    def create(
        cls,
        *,
        timeline_key: str,
        timeline_version: int,
        instrument_id: InstrumentId,
        intervals: tuple[OrderRuleInterval, ...],
    ) -> Self:
        ordered = _ordered_intervals(intervals)
        payload = {
            "type": "order_rule_timeline_config",
            "schema_version": 1,
            "timeline_key": timeline_key,
            "timeline_version": timeline_version,
            "instrument_id": instrument_id,
            "intervals": ordered,
        }
        return cls(
            timeline_key=timeline_key,
            timeline_version=timeline_version,
            instrument_id=instrument_id,
            intervals=ordered,
            config_hash=canonical_sha256(payload),
        )

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "order_rule_timeline_config",
            "schema_version": 1,
            "timeline_key": self.timeline_key,
            "timeline_version": self.timeline_version,
            "instrument_id": self.instrument_id,
            "intervals": self.intervals,
        }

    @property
    def timeline_hash(self) -> str:
        return canonical_sha256(self)

    def active_intervals(self, instant: UtcInstant) -> tuple[OrderRuleInterval, ...]:
        if not isinstance(instant, UtcInstant):
            raise TypeError("instant must be UtcInstant")
        return tuple(value for value in self.intervals if value.contains(instant))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "order_rule_timeline",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class OrderRulePositionEvidence:
    account_id: str
    evaluated_at: UtcInstant
    instrument_id: InstrumentId
    portfolio_snapshot: PortfolioSnapshot
    working_orders: tuple[OrderEventStream, ...]
    working_order_set_hash: str
    reservations: ResourceReservationState
    availability: AvailabilityState
    total_quantity: Quantity
    sellable_quantity: Quantity
    quantity_lattice_hash: str

    def __post_init__(self) -> None:
        _canonical_text("account_id", self.account_id)
        if not isinstance(self.evaluated_at, UtcInstant):
            raise TypeError("evaluated_at must be UtcInstant")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.portfolio_snapshot, PortfolioSnapshot):
            raise TypeError("portfolio_snapshot must be PortfolioSnapshot")
        if not isinstance(self.working_orders, tuple) or not all(
            isinstance(value, OrderEventStream) for value in self.working_orders
        ):
            raise TypeError("working_orders must contain OrderEventStream")
        if not isinstance(self.reservations, ResourceReservationState):
            raise TypeError("reservations must be ResourceReservationState")
        if not isinstance(self.availability, AvailabilityState):
            raise TypeError("availability must be AvailabilityState")
        if not isinstance(self.total_quantity, Quantity) or not isinstance(
            self.sellable_quantity, Quantity
        ):
            raise TypeError("position evidence quantities must be Quantity")
        _require_hash("working_order_set_hash", self.working_order_set_hash)
        _require_hash("quantity_lattice_hash", self.quantity_lattice_hash)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_rule_position_evidence",
            "schema_version": 1,
            "account_id": self.account_id,
            "evaluated_at": self.evaluated_at,
            "instrument_id": self.instrument_id,
            "portfolio_snapshot": self.portfolio_snapshot,
            "working_orders": self.working_orders,
            "working_order_set_hash": self.working_order_set_hash,
            "reservations": self.reservations,
            "availability": self.availability,
            "total_quantity": self.total_quantity,
            "sellable_quantity": self.sellable_quantity,
            "quantity_lattice_hash": self.quantity_lattice_hash,
        }


@dataclass(frozen=True, slots=True)
class OrderRuleEvaluationInput:
    executable_order_spec: ExecutableOrderSpec
    evaluated_at: UtcInstant
    notional_evidence: OrderRuleNotionalEvidence
    position_evidence: OrderRulePositionEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.executable_order_spec, ExecutableOrderSpec):
            raise TypeError("executable_order_spec must be ExecutableOrderSpec")
        if not isinstance(self.evaluated_at, UtcInstant):
            raise TypeError("evaluated_at must be UtcInstant")
        if not isinstance(self.notional_evidence, OrderRuleNotionalEvidence):
            raise TypeError("notional_evidence must be OrderRuleNotionalEvidence")
        if self.position_evidence is not None and not isinstance(
            self.position_evidence, OrderRulePositionEvidence
        ):
            raise TypeError("position_evidence must be OrderRulePositionEvidence or None")

    @property
    def input_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "order_rule_evaluation_input",
            "schema_version": 2 if self.position_evidence is not None else 1,
            "executable_order_spec": self.executable_order_spec,
            "evaluated_at": self.evaluated_at,
            "notional_evidence": self.notional_evidence,
        }
        if self.position_evidence is not None:
            payload["position_evidence"] = self.position_evidence
        return payload


class MarketRuleIssueCode(str, Enum):
    MAXIMUM_QUANTITY = "maximum_quantity"
    MINIMUM_NOTIONAL = "minimum_notional"
    MINIMUM_QUANTITY = "minimum_quantity"
    INSTRUMENT_SUSPENDED = "instrument_suspended"
    POSITION_EFFECT_NOT_PERMITTED = "position_effect_not_permitted"
    PRICE_CURRENCY = "price_currency"
    PRICE_LIMIT = "price_limit"
    PRICE_SCALE = "price_scale"
    PRICE_TICK = "price_tick"
    QUANTITY_SCALE = "quantity_scale"
    QUANTITY_STEP = "quantity_step"
    SELLABLE_QUANTITY = "sellable_quantity"
    SELL_RESIDUAL_NOT_PERMITTED = "sell_residual_not_permitted"
    REDUCE_ONLY_REQUIRED = "reduce_only_required"
    SESSION_CLOSED = "session_closed"
    SIDE_NOT_PERMITTED = "side_not_permitted"
    SUPPLEMENTAL_RULE_REJECTED = "supplemental_rule_rejected"


@dataclass(frozen=True, slots=True)
class MarketRuleIssue:
    code: MarketRuleIssueCode
    subject_key: str
    expected: str
    actual: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, MarketRuleIssueCode):
            raise TypeError("code must be MarketRuleIssueCode")
        _canonical_text("subject_key", self.subject_key)
        _canonical_text("expected", self.expected)
        _canonical_text("actual", self.actual)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "market_rule_issue",
            "code": self.code.value,
            "subject_key": self.subject_key,
            "expected": self.expected,
            "actual": self.actual,
        }


def _issue_sort_key(value: MarketRuleIssue) -> tuple[str, str, str, str]:
    return value.code.value, value.subject_key, value.expected, value.actual


class MarketRuleDataIntegrityCode(str, Enum):
    EVALUATION_BEFORE_TRANSLATION = "evaluation_before_translation"
    INSTRUMENT_CONTEXT_MISMATCH = "instrument_context_mismatch"
    INVALID_NOTIONAL_EVIDENCE = "invalid_notional_evidence"
    INVALID_POSITION_EVIDENCE = "invalid_position_evidence"
    MISSING_POSITION_EVIDENCE = "missing_position_evidence"
    MISSING_RULE_INTERVAL = "missing_rule_interval"
    OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"


def _decision_payload(
    *,
    outcome: str,
    evaluation_input: OrderRuleEvaluationInput,
    rule_timeline: OrderRuleTimeline,
    resolved_interval: OrderRuleInterval | None,
    calculated_notional: Money | None,
    issues: tuple[MarketRuleIssue, ...],
    data_integrity_code: MarketRuleDataIntegrityCode | None,
    candidate_interval_ids: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "market_rule_decision_identity",
        "schema_version": 1,
        "outcome": outcome,
        "evaluation_input_hash": evaluation_input.input_hash,
        "rule_timeline_hash": rule_timeline.timeline_hash,
        "resolved_interval_id": (
            None if resolved_interval is None else resolved_interval.interval_id
        ),
        "calculated_notional": calculated_notional,
        "issues": issues,
        "data_integrity_code": (
            None if data_integrity_code is None else data_integrity_code.value
        ),
        "candidate_interval_ids": candidate_interval_ids,
    }


def _validate_resolved_decision_evidence(
    evaluation_input: OrderRuleEvaluationInput,
    rule_timeline: OrderRuleTimeline,
    resolved_interval: OrderRuleInterval,
    calculated_notional: Money,
) -> None:
    if not isinstance(evaluation_input, OrderRuleEvaluationInput):
        raise TypeError("evaluation_input must be OrderRuleEvaluationInput")
    if not isinstance(rule_timeline, OrderRuleTimeline):
        raise TypeError("rule_timeline must be OrderRuleTimeline")
    if not isinstance(resolved_interval, OrderRuleInterval):
        raise TypeError("resolved_interval must be OrderRuleInterval")
    if not isinstance(calculated_notional, Money):
        raise TypeError("calculated_notional must be Money")
    if resolved_interval not in rule_timeline.intervals:
        raise ValueError("resolved_interval is not part of rule_timeline")
    if not resolved_interval.contains(evaluation_input.evaluated_at):
        raise ValueError("resolved_interval is not effective at evaluated_at")
    intent = evaluation_input.executable_order_spec.intent
    if rule_timeline.instrument_id != intent.instrument_id:
        raise ValueError("resolved decision instrument context mismatch")
    snapshot = resolved_interval.snapshot
    lattice = _quantity_lattice_for_style(snapshot, intent.execution_style)
    expected_notional = evaluation_input.notional_evidence.price.notional(
        intent.quantity,
        result_scale=lattice.min_notional.scale,
        rounding=snapshot.notional_rounding,
    )
    if calculated_notional != expected_notional:
        raise ValueError("calculated_notional does not match evaluation evidence")


def _resolved_decision_dict(
    *,
    type_name: str,
    decision_id: str,
    evaluation_input: OrderRuleEvaluationInput,
    rule_timeline: OrderRuleTimeline,
    resolved_interval: OrderRuleInterval,
    calculated_notional: Money,
    issues: tuple[MarketRuleIssue, ...] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": type_name,
        "schema_version": 1,
        "decision_id": decision_id,
        "evaluation_input": evaluation_input,
        "rule_timeline": rule_timeline,
        "resolved_interval": resolved_interval,
        "calculated_notional": calculated_notional,
    }
    if issues is not None:
        result["issues"] = issues
    return result


@dataclass(frozen=True, slots=True)
class MarketRuleApproval:
    decision_id: str
    evaluation_input: OrderRuleEvaluationInput
    rule_timeline: OrderRuleTimeline
    resolved_interval: OrderRuleInterval
    calculated_notional: Money

    def __post_init__(self) -> None:
        _validate_decision_id(self.decision_id)
        _validate_resolved_decision_evidence(
            self.evaluation_input,
            self.rule_timeline,
            self.resolved_interval,
            self.calculated_notional,
        )
        expected = _tagged_id(
            "market-rule-decision-v1",
            _decision_payload(
                outcome="approved",
                evaluation_input=self.evaluation_input,
                rule_timeline=self.rule_timeline,
                resolved_interval=self.resolved_interval,
                calculated_notional=self.calculated_notional,
                issues=(),
                data_integrity_code=None,
                candidate_interval_ids=(),
            ),
        )
        if self.decision_id != expected:
            raise ValueError("decision_id mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return _resolved_decision_dict(
            type_name="market_rule_approval",
            decision_id=self.decision_id,
            evaluation_input=self.evaluation_input,
            rule_timeline=self.rule_timeline,
            resolved_interval=self.resolved_interval,
            calculated_notional=self.calculated_notional,
        )


@dataclass(frozen=True, slots=True)
class MarketRuleRejection:
    decision_id: str
    evaluation_input: OrderRuleEvaluationInput
    rule_timeline: OrderRuleTimeline
    resolved_interval: OrderRuleInterval
    calculated_notional: Money
    issues: tuple[MarketRuleIssue, ...]

    def __post_init__(self) -> None:
        _validate_decision_id(self.decision_id)
        _validate_resolved_decision_evidence(
            self.evaluation_input,
            self.rule_timeline,
            self.resolved_interval,
            self.calculated_notional,
        )
        issues = tuple(sorted(self.issues, key=_issue_sort_key))
        if not issues or any(not isinstance(value, MarketRuleIssue) for value in issues):
            raise ValueError("rejection requires MarketRuleIssue values")
        if len(set(issues)) != len(issues):
            raise ValueError("rejection issues cannot contain duplicates")
        object.__setattr__(self, "issues", issues)
        expected = _tagged_id(
            "market-rule-decision-v1",
            _decision_payload(
                outcome="rejected",
                evaluation_input=self.evaluation_input,
                rule_timeline=self.rule_timeline,
                resolved_interval=self.resolved_interval,
                calculated_notional=self.calculated_notional,
                issues=issues,
                data_integrity_code=None,
                candidate_interval_ids=(),
            ),
        )
        if self.decision_id != expected:
            raise ValueError("decision_id mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return _resolved_decision_dict(
            type_name="market_rule_rejection",
            decision_id=self.decision_id,
            evaluation_input=self.evaluation_input,
            rule_timeline=self.rule_timeline,
            resolved_interval=self.resolved_interval,
            calculated_notional=self.calculated_notional,
            issues=self.issues,
        )


@dataclass(frozen=True, slots=True)
class MarketRuleDataIntegrityFailure:
    decision_id: str
    evaluation_input: OrderRuleEvaluationInput
    rule_timeline: OrderRuleTimeline
    code: MarketRuleDataIntegrityCode
    candidate_interval_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_decision_id(self.decision_id)
        if not isinstance(self.evaluation_input, OrderRuleEvaluationInput):
            raise TypeError("evaluation_input must be OrderRuleEvaluationInput")
        if not isinstance(self.rule_timeline, OrderRuleTimeline):
            raise TypeError("rule_timeline must be OrderRuleTimeline")
        if not isinstance(self.code, MarketRuleDataIntegrityCode):
            raise TypeError("code must be MarketRuleDataIntegrityCode")
        candidates = tuple(sorted(self.candidate_interval_ids))
        if len(set(candidates)) != len(candidates):
            raise ValueError("candidate_interval_ids cannot contain duplicates")
        if any(_INTERVAL_ID_RE.fullmatch(value) is None for value in candidates):
            raise ValueError("candidate_interval_ids must be canonical interval identities")
        if self.code is MarketRuleDataIntegrityCode.OVERLAPPING_RULE_INTERVALS:
            if len(candidates) < 2:
                raise ValueError("overlap failure requires candidate intervals")
        elif candidates:
            raise ValueError("only overlap failure may carry candidate intervals")
        object.__setattr__(self, "candidate_interval_ids", candidates)
        expected = _tagged_id(
            "market-rule-decision-v1",
            _decision_payload(
                outcome="data_integrity_failure",
                evaluation_input=self.evaluation_input,
                rule_timeline=self.rule_timeline,
                resolved_interval=None,
                calculated_notional=None,
                issues=(),
                data_integrity_code=self.code,
                candidate_interval_ids=candidates,
            ),
        )
        if self.decision_id != expected:
            raise ValueError("decision_id mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "market_rule_data_integrity_failure",
            "schema_version": 1,
            "decision_id": self.decision_id,
            "evaluation_input": self.evaluation_input,
            "rule_timeline": self.rule_timeline,
            "code": self.code.value,
            "candidate_interval_ids": self.candidate_interval_ids,
        }


def _validate_decision_id(value: str) -> None:
    if not isinstance(value, str) or _DECISION_ID_RE.fullmatch(value) is None:
        raise ValueError("decision_id must be a canonical market rule decision identity")


@dataclass(frozen=True, slots=True)
class MarketRuleDecision:
    approval: MarketRuleApproval | None
    rejection: MarketRuleRejection | None
    data_integrity_failure: MarketRuleDataIntegrityFailure | None

    def __post_init__(self) -> None:
        values = (self.approval, self.rejection, self.data_integrity_failure)
        if sum(map(bool, values)) != 1:
            raise ValueError("MarketRuleDecision requires exactly one outcome")
        if self.approval is not None and not isinstance(
            self.approval, MarketRuleApproval
        ):
            raise TypeError("approval must be MarketRuleApproval or None")
        if self.rejection is not None and not isinstance(
            self.rejection, MarketRuleRejection
        ):
            raise TypeError("rejection must be MarketRuleRejection or None")
        if self.data_integrity_failure is not None and not isinstance(
            self.data_integrity_failure, MarketRuleDataIntegrityFailure
        ):
            raise TypeError(
                "data_integrity_failure must be MarketRuleDataIntegrityFailure or None"
            )

    @property
    def decision_id(self) -> str:
        value = self.approval or self.rejection or self.data_integrity_failure
        if value is None:  # pragma: no cover - constructor invariant
            raise AssertionError("unreachable empty decision")
        return value.decision_id

    @property
    def decision_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "market_rule_decision",
            "schema_version": 1,
            "approval": self.approval,
            "rejection": self.rejection,
            "data_integrity_failure": self.data_integrity_failure,
        }


def _data_failure(
    evaluation_input: OrderRuleEvaluationInput,
    rule_timeline: OrderRuleTimeline,
    code: MarketRuleDataIntegrityCode,
    candidate_interval_ids: tuple[str, ...] = (),
) -> MarketRuleDecision:
    payload = _decision_payload(
        outcome="data_integrity_failure",
        evaluation_input=evaluation_input,
        rule_timeline=rule_timeline,
        resolved_interval=None,
        calculated_notional=None,
        issues=(),
        data_integrity_code=code,
        candidate_interval_ids=tuple(sorted(candidate_interval_ids)),
    )
    return MarketRuleDecision(
        approval=None,
        rejection=None,
        data_integrity_failure=MarketRuleDataIntegrityFailure(
            decision_id=_tagged_id("market-rule-decision-v1", payload),
            evaluation_input=evaluation_input,
            rule_timeline=rule_timeline,
            code=code,
            candidate_interval_ids=tuple(sorted(candidate_interval_ids)),
        ),
    )


def _valid_notional_evidence(
    evaluation_input: OrderRuleEvaluationInput,
    snapshot: OrderRuleSnapshot,
    lattice: QuantityLattice,
) -> bool:
    evidence = evaluation_input.notional_evidence
    intent = evaluation_input.executable_order_spec.intent
    price = evidence.price
    if price.units <= 0:
        return False
    if price.instrument_id != str(intent.instrument_id):
        return False
    if price.quote_currency != lattice.min_notional.currency:
        return False
    if evidence.basis is NotionalPriceBasis.SUPPLIED_REFERENCE:
        return (
            evidence.available_at is not None
            and evidence.available_at <= evaluation_input.evaluated_at
        )
    constraint = intent.price_constraint
    if constraint is None:
        return False
    expected = (
        constraint.limit_price
        if evidence.basis is NotionalPriceBasis.LIMIT_CONSTRAINT
        else constraint.trigger_price
    )
    return expected is not None and price == expected


def _price_issues(
    snapshot: OrderRuleSnapshot, price: Price, subject_key: str
) -> tuple[MarketRuleIssue, ...]:
    if price.quote_currency != snapshot.quantity_lattice.min_notional.currency:
        return (
            MarketRuleIssue(
                MarketRuleIssueCode.PRICE_CURRENCY,
                subject_key,
                snapshot.quantity_lattice.min_notional.currency,
                price.quote_currency,
            ),
        )
    if price.scale != snapshot.price_scale:
        return (
            MarketRuleIssue(
                MarketRuleIssueCode.PRICE_SCALE,
                subject_key,
                str(snapshot.price_scale.places),
                str(price.scale.places),
            ),
        )
    issues: list[MarketRuleIssue] = []
    if price.units % snapshot.price_tick_units:
        issues.append(
            MarketRuleIssue(
                MarketRuleIssueCode.PRICE_TICK,
                subject_key,
                str(snapshot.price_tick_units),
                str(price.units),
            )
        )
    if snapshot.lower_price_limit is not None and price.units < snapshot.lower_price_limit.units:
        issues.append(
            MarketRuleIssue(
                MarketRuleIssueCode.PRICE_LIMIT,
                subject_key,
                f">={snapshot.lower_price_limit.units}",
                str(price.units),
            )
        )
    if snapshot.upper_price_limit is not None and price.units > snapshot.upper_price_limit.units:
        issues.append(
            MarketRuleIssue(
                MarketRuleIssueCode.PRICE_LIMIT,
                subject_key,
                f"<={snapshot.upper_price_limit.units}",
                str(price.units),
            )
        )
    return tuple(issues)


def _working_order_set_hash(streams: tuple[OrderEventStream, ...]) -> str:
    return canonical_sha256(
        tuple(
            {
                "order_id": stream.order.order_id,
                "stream_hash": stream.stream_hash,
                "state_hash": stream.state_hash,
                "remaining_quantity": (
                    stream.state.remaining_quantity if stream.state else None
                ),
            }
            for stream in streams
        )
    )


def _valid_position_evidence(
    evaluation_input: OrderRuleEvaluationInput,
    snapshot: OrderRuleSnapshot,
    lattice: QuantityLattice,
) -> bool:
    evidence = evaluation_input.position_evidence
    if evidence is None:
        return False
    if (
        evidence.account_id
        != evaluation_input.executable_order_spec.source_order.account_id
        or evidence.evaluated_at != evaluation_input.evaluated_at
        or evidence.instrument_id != snapshot.instrument_id
        or evidence.quantity_lattice_hash != lattice.lattice_hash
        or evidence.portfolio_snapshot.account_id != evidence.account_id
        or evidence.portfolio_snapshot.timestamp != evidence.evaluated_at
        or evidence.reservations.account_id != evidence.account_id
        or evidence.availability.account_id != evidence.account_id
        or evidence.availability.ledger_state_hash
        != evidence.portfolio_snapshot.journal_state_hash
        or evidence.availability.reservation_state_hash
        != evidence.reservations.state_hash
        or evidence.total_quantity.instrument_id != str(evidence.instrument_id)
        or evidence.sellable_quantity.instrument_id != str(evidence.instrument_id)
        or evidence.total_quantity.scale != lattice.atomic_scale
        or evidence.sellable_quantity.scale != lattice.atomic_scale
        or not 0 <= evidence.sellable_quantity.units <= evidence.total_quantity.units
    ):
        return False
    working_order_ids = tuple(
        value.order.order_id for value in evidence.working_orders
    )
    if (
        len(set(working_order_ids)) != len(working_order_ids)
        or evidence.working_orders
        != tuple(
            sorted(
                evidence.working_orders,
                key=lambda value: value.order.order_id.value,
            )
        )
        or evidence.working_order_set_hash
        != _working_order_set_hash(evidence.working_orders)
    ):
        return False
    portfolio_positions = tuple(
        value
        for value in evidence.portfolio_snapshot.positions
        if value.key.account_id == evidence.account_id
        and value.key.instrument_id == evidence.instrument_id
    )
    availability_positions = tuple(
        value
        for value in evidence.availability.positions
        if value.key.account_id == evidence.account_id
        and value.key.instrument_id == evidence.instrument_id
    )
    if (
        len(portfolio_positions) != 1
        or portfolio_positions[0].quantity != evidence.total_quantity
        or len(availability_positions) != 1
        or availability_positions[0].total != evidence.total_quantity
        or availability_positions[0].sellable != evidence.sellable_quantity
    ):
        return False
    streams_by_id = {stream.order.order_id: stream for stream in evidence.working_orders}
    active_by_id = {
        value.order_id: value for value in evidence.reservations.active_reservations
    }
    if set(streams_by_id) != set(active_by_id):
        return False
    cursors_by_id = {
        value.order_id: value for value in evidence.reservations.cursors
    }
    for stream in evidence.working_orders:
        state = stream.state
        active = active_by_id.get(stream.order.order_id)
        cursor = cursors_by_id.get(stream.order.order_id)
        if (
            stream.order.account_id != evidence.account_id
            or state is None
            or state.status not in {OrderStatus.ACTIVE, OrderStatus.PARTIALLY_FILLED}
            or any(
                record.event.occurred_at.instant > evidence.evaluated_at
                for record in stream.records
            )
            or (
                stream.order.intent.instrument_id == evidence.instrument_id
                and (
                    stream.order.intent.quantity.scale != lattice.atomic_scale
                    or state.remaining_quantity.scale != lattice.atomic_scale
                    or state.remaining_quantity.instrument_id
                    != str(evidence.instrument_id)
                )
            )
            or active is None
            or active.remaining_quantity != state.remaining_quantity
            or cursor is None
            or cursor.stream_hash != stream.stream_hash
            or cursor.event_count != stream.event_count
        ):
            return False
    return True


def _position_exception_requested(
    evaluation_input: OrderRuleEvaluationInput,
    lattice: QuantityLattice,
) -> bool:
    intent = evaluation_input.executable_order_spec.intent
    quantity = intent.quantity
    if intent.side is not OrderSide.SELL or quantity.scale != lattice.atomic_scale:
        return False
    lot_units = lattice.sell_lot_units or lattice.step_units
    return (
        lattice.whole_sell_residual_permitted and quantity.units % lot_units != 0
    ) or (
        lattice.odd_lot_close_permitted
        and lattice.min_quantity_units > 0
        and quantity.units < lattice.min_quantity_units
    )


def _position_exception_issue(
    evaluation_input: OrderRuleEvaluationInput,
    lattice: QuantityLattice,
) -> MarketRuleIssue | None:
    evidence = evaluation_input.position_evidence
    if evidence is None:  # pragma: no cover - guarded by evaluator
        raise AssertionError("position evidence is required")
    intent = evaluation_input.executable_order_spec.intent
    quantity = intent.quantity
    if quantity.units > evidence.sellable_quantity.units:
        return MarketRuleIssue(
            MarketRuleIssueCode.SELLABLE_QUANTITY,
            "quantity",
            f"<={evidence.sellable_quantity.units}",
            str(quantity.units),
        )
    if intent.position_effect is not PositionEffect.CLOSE or not intent.reduce_only:
        return MarketRuleIssue(
            MarketRuleIssueCode.SELL_RESIDUAL_NOT_PERMITTED,
            "quantity",
            "close-and-reduce-only",
            str(quantity.units),
        )
    lot_units = lattice.sell_lot_units or lattice.step_units
    active_odd_sell = any(
        stream.order.intent.instrument_id == intent.instrument_id
        and stream.order.intent.side is OrderSide.SELL
        and stream.state is not None
        and stream.state.remaining_quantity.units % lot_units != 0
        for stream in evidence.working_orders
    )
    permitted = False
    if lattice.whole_sell_residual_permitted:
        residual = evidence.total_quantity.units % lot_units
        permitted = (
            residual > 0
            and quantity.units % lot_units == residual
            and not active_odd_sell
        )
    elif lattice.odd_lot_close_permitted:
        permitted = (
            evidence.total_quantity.units < lattice.min_quantity_units
            and quantity == evidence.total_quantity == evidence.sellable_quantity
        )
    if permitted:
        return None
    return MarketRuleIssue(
        MarketRuleIssueCode.SELL_RESIDUAL_NOT_PERMITTED,
        "quantity",
        "complete-unreserved-residual",
        str(quantity.units),
    )


class MarketRuleEvaluator:
    def evaluate(
        self,
        evaluation_input: OrderRuleEvaluationInput,
        rule_timeline: OrderRuleTimeline,
    ) -> MarketRuleDecision:
        if not isinstance(evaluation_input, OrderRuleEvaluationInput):
            raise TypeError("evaluation_input must be OrderRuleEvaluationInput")
        if not isinstance(rule_timeline, OrderRuleTimeline):
            raise TypeError("rule_timeline must be OrderRuleTimeline")
        spec = evaluation_input.executable_order_spec
        intent = spec.intent
        if evaluation_input.evaluated_at < spec.translation_time:
            return _data_failure(
                evaluation_input,
                rule_timeline,
                MarketRuleDataIntegrityCode.EVALUATION_BEFORE_TRANSLATION,
            )
        if rule_timeline.instrument_id != intent.instrument_id:
            return _data_failure(
                evaluation_input,
                rule_timeline,
                MarketRuleDataIntegrityCode.INSTRUMENT_CONTEXT_MISMATCH,
            )
        active = rule_timeline.active_intervals(evaluation_input.evaluated_at)
        if not active:
            return _data_failure(
                evaluation_input,
                rule_timeline,
                MarketRuleDataIntegrityCode.MISSING_RULE_INTERVAL,
            )
        if len(active) != 1:
            return _data_failure(
                evaluation_input,
                rule_timeline,
                MarketRuleDataIntegrityCode.OVERLAPPING_RULE_INTERVALS,
                tuple(value.interval_id for value in active),
            )
        resolved = active[0]
        snapshot = resolved.snapshot
        lattice = _quantity_lattice_for_style(snapshot, intent.execution_style)
        if not _valid_notional_evidence(evaluation_input, snapshot, lattice):
            return _data_failure(
                evaluation_input,
                rule_timeline,
                MarketRuleDataIntegrityCode.INVALID_NOTIONAL_EVIDENCE,
            )
        position_exception = _position_exception_requested(
            evaluation_input, lattice
        )
        if position_exception and evaluation_input.position_evidence is None:
            return _data_failure(
                evaluation_input,
                rule_timeline,
                MarketRuleDataIntegrityCode.MISSING_POSITION_EVIDENCE,
            )
        if position_exception and not _valid_position_evidence(
            evaluation_input, snapshot, lattice
        ):
            return _data_failure(
                evaluation_input,
                rule_timeline,
                MarketRuleDataIntegrityCode.INVALID_POSITION_EVIDENCE,
            )
        position_issue = (
            _position_exception_issue(evaluation_input, lattice)
            if position_exception
            else None
        )

        quantity = intent.quantity
        calculated_notional = evaluation_input.notional_evidence.price.notional(
            quantity,
            result_scale=lattice.min_notional.scale,
            rounding=snapshot.notional_rounding,
        )
        issues: list[MarketRuleIssue] = []
        if quantity.scale != lattice.atomic_scale:
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.QUANTITY_SCALE,
                    "quantity",
                    str(lattice.atomic_scale.places),
                    str(quantity.scale.places),
                )
            )
        else:
            lot_units = (
                lattice.buy_lot_units
                if intent.side is OrderSide.BUY
                else lattice.sell_lot_units
            ) or lattice.step_units
            if position_exception:
                if position_issue is not None:
                    issues.append(position_issue)
            else:
                if quantity.units % lot_units:
                    issues.append(
                        MarketRuleIssue(
                            MarketRuleIssueCode.QUANTITY_STEP,
                            "quantity",
                            str(lot_units),
                            str(quantity.units),
                        )
                    )
                if quantity.units < lattice.min_quantity_units:
                    issues.append(
                        MarketRuleIssue(
                            MarketRuleIssueCode.MINIMUM_QUANTITY,
                            "quantity",
                            f">={lattice.min_quantity_units}",
                            str(quantity.units),
                        )
                    )
        quantity_cap = (
            snapshot.max_limit_order_quantity_units
            if intent.execution_style
            in {ExecutionStyle.LIMIT, ExecutionStyle.STOP_LIMIT}
            else snapshot.max_market_order_quantity_units
        )
        if (
            quantity.scale == lattice.atomic_scale
            and quantity_cap is not None
            and quantity.units > quantity_cap
        ):
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.MAXIMUM_QUANTITY,
                    "quantity",
                    f"<={quantity_cap}",
                    str(quantity.units),
                )
            )
        if calculated_notional.units < lattice.min_notional.units:
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.MINIMUM_NOTIONAL,
                    "notional",
                    f">={lattice.min_notional.units}",
                    str(calculated_notional.units),
                )
            )
        constraint = intent.price_constraint
        if constraint is not None:
            for subject_key, price in (
                ("limit_price", constraint.limit_price),
                ("trigger_price", constraint.trigger_price),
            ):
                if price is not None:
                    issues.extend(_price_issues(snapshot, price, subject_key))
        if snapshot.session_state is MarketSessionState.CLOSED:
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.SESSION_CLOSED,
                    "session",
                    MarketSessionState.OPEN.value,
                    snapshot.session_state.value,
                )
            )
        elif snapshot.session_state is MarketSessionState.SUSPENDED:
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.INSTRUMENT_SUSPENDED,
                    "session",
                    MarketSessionState.OPEN.value,
                    snapshot.session_state.value,
                )
            )
        if intent.side not in snapshot.permitted_sides:
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.SIDE_NOT_PERMITTED,
                    "side",
                    ",".join(value.value for value in snapshot.permitted_sides)
                    or "none",
                    intent.side.value,
                )
            )
        if intent.position_effect not in snapshot.permitted_position_effects:
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.POSITION_EFFECT_NOT_PERMITTED,
                    "position_effect",
                    ",".join(
                        value.value for value in snapshot.permitted_position_effects
                    )
                    or "none",
                    intent.position_effect.value,
                )
            )
        if snapshot.reduce_only_required and not intent.reduce_only:
            issues.append(
                MarketRuleIssue(
                    MarketRuleIssueCode.REDUCE_ONLY_REQUIRED,
                    "reduce_only",
                    "true",
                    "false",
                )
            )
        for supplemental in snapshot.supplemental_decisions:
            if not supplemental.approved:
                issues.append(
                    MarketRuleIssue(
                        MarketRuleIssueCode.SUPPLEMENTAL_RULE_REJECTED,
                        supplemental.rule_key,
                        "approved",
                        supplemental.reason_code,
                    )
                )
        ordered_issues = tuple(sorted(issues, key=_issue_sort_key))
        outcome = "approved" if not ordered_issues else "rejected"
        payload = _decision_payload(
            outcome=outcome,
            evaluation_input=evaluation_input,
            rule_timeline=rule_timeline,
            resolved_interval=resolved,
            calculated_notional=calculated_notional,
            issues=ordered_issues,
            data_integrity_code=None,
            candidate_interval_ids=(),
        )
        decision_id = _tagged_id("market-rule-decision-v1", payload)
        if not ordered_issues:
            return MarketRuleDecision(
                approval=MarketRuleApproval(
                    decision_id=decision_id,
                    evaluation_input=evaluation_input,
                    rule_timeline=rule_timeline,
                    resolved_interval=resolved,
                    calculated_notional=calculated_notional,
                ),
                rejection=None,
                data_integrity_failure=None,
            )
        return MarketRuleDecision(
            approval=None,
            rejection=MarketRuleRejection(
                decision_id=decision_id,
                evaluation_input=evaluation_input,
                rule_timeline=rule_timeline,
                resolved_interval=resolved,
                calculated_notional=calculated_notional,
                issues=ordered_issues,
            ),
            data_integrity_failure=None,
        )
