from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .accounting import PricePurpose
from .canonical import canonical_bytes
from .identity import DomainId, DomainIdKind, require_canonical_text
from .instruments import CurrencyId, InstrumentId, VenueId
from .numeric import Money, Price, Quantity
from .time import SessionId, SimulationInstant, UtcInstant


def _require_text(name: str, value: str) -> None:
    require_canonical_text(name, value)
    canonical_bytes(value)


def _require_optional_text(name: str, value: str | None) -> None:
    if value is not None:
        _require_text(name, value)


def _require_id(name: str, value: DomainId, kind: DomainIdKind) -> None:
    if not isinstance(value, DomainId):
        raise TypeError(f"{name} must be DomainId")
    if value.kind is not kind:
        raise ValueError(f"{name} must use DomainIdKind.{kind.name}")


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class ExecutionStyle(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTX = "gtx"


class PositionEffect(str, Enum):
    AUTO = "auto"
    OPEN = "open"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class PriceConstraint:
    limit_price: Price | None = None
    trigger_price: Price | None = None

    def __post_init__(self) -> None:
        if self.limit_price is None and self.trigger_price is None:
            raise ValueError("PriceConstraint requires limit_price or trigger_price")
        prices = tuple(
            value
            for value in (self.limit_price, self.trigger_price)
            if value is not None
        )
        if not all(isinstance(value, Price) for value in prices):
            raise TypeError("PriceConstraint values must be Price")
        if any(value.units <= 0 for value in prices):
            raise ValueError("PriceConstraint prices must be positive")
        if len(prices) == 2 and (
            prices[0].instrument_id,
            prices[0].quote_currency,
        ) != (
            prices[1].instrument_id,
            prices[1].quote_currency,
        ):
            raise ValueError("PriceConstraint prices must share identity")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "price_constraint",
            "limit_price": self.limit_price,
            "trigger_price": self.trigger_price,
        }


@dataclass(frozen=True, slots=True)
class OrderIntent:
    instrument_id: InstrumentId
    side: OrderSide
    quantity: Quantity
    execution_style: ExecutionStyle
    price_constraint: PriceConstraint | None
    time_in_force: TimeInForce
    reduce_only: bool
    position_effect: PositionEffect
    urgency: str
    reason: str
    parent_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        if not isinstance(self.quantity, Quantity):
            raise TypeError("quantity must be Quantity")
        if self.quantity.units <= 0:
            raise ValueError("OrderIntent quantity must be positive")
        if self.quantity.instrument_id != str(self.instrument_id):
            raise ValueError("OrderIntent Quantity instrument identity mismatch")
        if not isinstance(self.execution_style, ExecutionStyle):
            raise TypeError("execution_style must be ExecutionStyle")
        if self.price_constraint is not None:
            if not isinstance(self.price_constraint, PriceConstraint):
                raise TypeError("price_constraint must be PriceConstraint or None")
            for value in (
                self.price_constraint.limit_price,
                self.price_constraint.trigger_price,
            ):
                if value is not None and value.instrument_id != str(self.instrument_id):
                    raise ValueError("OrderIntent PriceConstraint instrument identity mismatch")
        if not isinstance(self.time_in_force, TimeInForce):
            raise TypeError("time_in_force must be TimeInForce")
        if type(self.reduce_only) is not bool:
            raise TypeError("reduce_only must be bool")
        if not isinstance(self.position_effect, PositionEffect):
            raise TypeError("position_effect must be PositionEffect")
        _require_text("urgency", self.urgency)
        _require_text("reason", self.reason)
        _require_text("parent_id", self.parent_id)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_intent",
            "instrument_id": self.instrument_id,
            "side": self.side.value,
            "quantity": self.quantity,
            "execution_style": self.execution_style.value,
            "price_constraint": self.price_constraint,
            "time_in_force": self.time_in_force.value,
            "reduce_only": self.reduce_only,
            "position_effect": self.position_effect.value,
            "urgency": self.urgency,
            "reason": self.reason,
            "parent_id": self.parent_id,
        }


@dataclass(frozen=True, slots=True)
class Order:
    order_id: DomainId
    account_id: str
    intent: OrderIntent
    created_at: SimulationInstant

    def __post_init__(self) -> None:
        _require_id("order_id", self.order_id, DomainIdKind.ORDER)
        _require_text("account_id", self.account_id)
        if not isinstance(self.intent, OrderIntent):
            raise TypeError("intent must be OrderIntent")
        if not isinstance(self.created_at, SimulationInstant):
            raise TypeError("created_at must be SimulationInstant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order",
            "order_id": self.order_id,
            "account_id": self.account_id,
            "intent": self.intent,
            "created_at": self.created_at,
        }


class OrderEventType(str, Enum):
    ORDER_INTENT_CREATED = "order_intent_created"
    ORDER_CAPABILITY_APPROVED = "order_capability_approved"
    ORDER_CAPABILITY_REJECTED = "order_capability_rejected"
    ORDER_TRANSLATED = "order_translated"
    MARKET_RULE_APPROVED = "market_rule_approved"
    MARKET_RULE_REJECTED = "market_rule_rejected"
    FEE_RESERVATION_ESTIMATED = "fee_reservation_estimated"
    PRE_TRADE_RISK_APPROVED = "pre_trade_risk_approved"
    PRE_TRADE_RISK_REJECTED = "pre_trade_risk_rejected"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_REJECTED = "order_rejected"
    ORDER_ACTIVATED = "order_activated"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_FILLED = "order_filled"
    ORDER_CANCEL_REQUESTED = "order_cancel_requested"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_EXPIRED = "order_expired"


_FILL_EVENTS = {
    OrderEventType.ORDER_PARTIALLY_FILLED,
    OrderEventType.ORDER_FILLED,
}
_REJECTION_EVENTS = {
    OrderEventType.ORDER_CAPABILITY_REJECTED,
    OrderEventType.MARKET_RULE_REJECTED,
    OrderEventType.PRE_TRADE_RISK_REJECTED,
    OrderEventType.ORDER_REJECTED,
}


@dataclass(frozen=True, slots=True)
class OrderEvent:
    event_id: str
    order_id: DomainId
    causation_id: str
    event_type: OrderEventType
    occurred_at: SimulationInstant
    fill_id: DomainId | None = None
    evidence_id: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        _require_text("event_id", self.event_id)
        _require_id("order_id", self.order_id, DomainIdKind.ORDER)
        _require_text("causation_id", self.causation_id)
        if not isinstance(self.event_type, OrderEventType):
            raise TypeError("event_type must be OrderEventType")
        if not isinstance(self.occurred_at, SimulationInstant):
            raise TypeError("occurred_at must be SimulationInstant")
        if self.event_type in _FILL_EVENTS:
            if self.fill_id is None:
                raise ValueError("Fill events require fill_id")
            _require_id("fill_id", self.fill_id, DomainIdKind.FILL)
        elif self.fill_id is not None:
            raise ValueError("only Fill events may carry fill_id")
        if self.event_type in _REJECTION_EVENTS and self.reason_code is None:
            raise ValueError("rejection OrderEvent requires reason_code")
        _require_optional_text("evidence_id", self.evidence_id)
        _require_optional_text("reason_code", self.reason_code)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_event",
            "event_id": self.event_id,
            "order_id": self.order_id,
            "causation_id": self.causation_id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at,
            "fill_id": self.fill_id,
            "evidence_id": self.evidence_id,
            "reason_code": self.reason_code,
        }


class OrderStatus(str, Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class OrderState:
    order_id: DomainId
    status: OrderStatus
    ordered_quantity: Quantity
    cumulative_filled_quantity: Quantity
    remaining_quantity: Quantity
    last_event_id: str
    updated_at: SimulationInstant

    def __post_init__(self) -> None:
        _require_id("order_id", self.order_id, DomainIdKind.ORDER)
        if not isinstance(self.status, OrderStatus):
            raise TypeError("status must be OrderStatus")
        quantities = (
            self.ordered_quantity,
            self.cumulative_filled_quantity,
            self.remaining_quantity,
        )
        if not all(isinstance(value, Quantity) for value in quantities):
            raise TypeError("OrderState quantities must be Quantity")
        if len({value.instrument_id for value in quantities}) != 1:
            raise ValueError("OrderState quantity identity mismatch")
        if len({value.scale for value in quantities}) != 1:
            raise ValueError("OrderState quantity scale mismatch")
        if any(value.units < 0 for value in quantities):
            raise ValueError("OrderState quantities must be non-negative")
        if self.ordered_quantity.units == 0:
            raise ValueError("OrderState ordered quantity must be positive")
        if (
            self.cumulative_filled_quantity.units + self.remaining_quantity.units
            != self.ordered_quantity.units
        ):
            raise ValueError("filled and remaining quantities must sum to ordered quantity")
        if self.status is OrderStatus.PARTIALLY_FILLED and (
            self.cumulative_filled_quantity.units == 0
            or self.remaining_quantity.units == 0
        ):
            raise ValueError("PARTIALLY_FILLED requires filled and remaining quantity")
        if self.status is OrderStatus.FILLED and self.remaining_quantity.units != 0:
            raise ValueError("FILLED OrderState must have zero remaining quantity")
        _require_text("last_event_id", self.last_event_id)
        if not isinstance(self.updated_at, SimulationInstant):
            raise TypeError("updated_at must be SimulationInstant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_state",
            "order_id": self.order_id,
            "status": self.status.value,
            "ordered_quantity": self.ordered_quantity,
            "cumulative_filled_quantity": self.cumulative_filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "last_event_id": self.last_event_id,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class Fill:
    fill_id: DomainId
    order_id: DomainId
    account_id: str
    venue_id: VenueId
    instrument_id: InstrumentId
    side: OrderSide
    quantity: Quantity
    reference_price: Price
    reference_price_purpose: PricePurpose
    price: Price
    slippage_amount: Money
    slippage_decision_id: str
    slippage_model_key: str
    slippage_calibration_id: str | None
    liquidity: str | None
    execution_time: UtcInstant

    def __post_init__(self) -> None:
        _require_id("fill_id", self.fill_id, DomainIdKind.FILL)
        _require_id("order_id", self.order_id, DomainIdKind.ORDER)
        _require_text("account_id", self.account_id)
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if self.instrument_id.venue != self.venue_id:
            raise ValueError("Fill Venue and Instrument identity mismatch")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        if not isinstance(self.quantity, Quantity):
            raise TypeError("quantity must be Quantity")
        if self.quantity.units <= 0:
            raise ValueError("Fill quantity must be positive")
        if self.quantity.instrument_id != str(self.instrument_id):
            raise ValueError("Fill quantity instrument identity mismatch")
        if not isinstance(self.reference_price, Price) or not isinstance(self.price, Price):
            raise TypeError("Fill prices must be Price")
        for value in (self.reference_price, self.price):
            if value.units <= 0:
                raise ValueError("Fill prices must be positive")
            if value.instrument_id != str(self.instrument_id):
                raise ValueError("Fill price instrument identity mismatch")
        if self.reference_price.quote_currency != self.price.quote_currency:
            raise ValueError("Fill prices must share quote currency")
        if not isinstance(self.slippage_amount, Money):
            raise TypeError("slippage_amount must be Money")
        if self.slippage_amount.currency != self.price.quote_currency:
            raise ValueError("Fill slippage quote currency mismatch")
        if not isinstance(self.reference_price_purpose, PricePurpose):
            raise TypeError("reference_price_purpose must be PricePurpose")
        _require_text("slippage_decision_id", self.slippage_decision_id)
        _require_text("slippage_model_key", self.slippage_model_key)
        _require_optional_text("slippage_calibration_id", self.slippage_calibration_id)
        _require_optional_text("liquidity", self.liquidity)
        if not isinstance(self.execution_time, UtcInstant):
            raise TypeError("execution_time must be UtcInstant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fill",
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "side": self.side.value,
            "quantity": self.quantity,
            "reference_price": self.reference_price,
            "reference_price_purpose": self.reference_price_purpose.value,
            "price": self.price,
            "slippage_amount": self.slippage_amount,
            "slippage_decision_id": self.slippage_decision_id,
            "slippage_model_key": self.slippage_model_key,
            "slippage_calibration_id": self.slippage_calibration_id,
            "liquidity": self.liquidity,
            "execution_time": self.execution_time,
        }


class FeeBasisType(str, Enum):
    FILL = "fill"
    ORDER = "order"
    SESSION = "session"


@dataclass(frozen=True, slots=True)
class FeeAssessment:
    fee_assessment_id: DomainId
    basis_type: FeeBasisType
    basis_ids: tuple[DomainId | SessionId, ...]
    market_fee_rule_id: str | None
    account_fee_schedule_id: str | None
    tax_rule_id: str | None
    amount: Money
    assessment_time: UtcInstant

    def __post_init__(self) -> None:
        _require_id("fee_assessment_id", self.fee_assessment_id, DomainIdKind.FEE)
        if not isinstance(self.basis_type, FeeBasisType):
            raise TypeError("basis_type must be FeeBasisType")
        if not isinstance(self.basis_ids, tuple):
            raise TypeError("basis_ids must be a tuple")
        if not self.basis_ids:
            raise ValueError("FeeAssessment basis_ids must be non-empty")
        if self.basis_type is FeeBasisType.FILL:
            valid = all(
                isinstance(value, DomainId) and value.kind is DomainIdKind.FILL
                for value in self.basis_ids
            )
        elif self.basis_type is FeeBasisType.ORDER:
            valid = all(
                isinstance(value, DomainId) and value.kind is DomainIdKind.ORDER
                for value in self.basis_ids
            )
        else:
            valid = all(isinstance(value, SessionId) for value in self.basis_ids)
        if not valid:
            raise ValueError("FeeAssessment basis IDs do not match basis type")
        canonical_basis = [canonical_bytes(value) for value in self.basis_ids]
        if len(set(canonical_basis)) != len(canonical_basis):
            raise ValueError("duplicate FeeAssessment basis")
        rule_ids = (
            self.market_fee_rule_id,
            self.account_fee_schedule_id,
            self.tax_rule_id,
        )
        if not any(value is not None for value in rule_ids):
            raise ValueError("FeeAssessment requires at least one rule identity")
        for name, value in zip(
            ("market_fee_rule_id", "account_fee_schedule_id", "tax_rule_id"),
            rule_ids,
            strict=True,
        ):
            _require_optional_text(name, value)
        if not isinstance(self.amount, Money):
            raise TypeError("amount must be Money")
        if not isinstance(self.assessment_time, UtcInstant):
            raise TypeError("assessment_time must be UtcInstant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_assessment",
            "fee_assessment_id": self.fee_assessment_id,
            "basis_type": self.basis_type.value,
            "basis_ids": sorted(self.basis_ids, key=canonical_bytes),
            "market_fee_rule_id": self.market_fee_rule_id,
            "account_fee_schedule_id": self.account_fee_schedule_id,
            "tax_rule_id": self.tax_rule_id,
            "amount": self.amount,
            "assessment_time": self.assessment_time,
        }


@dataclass(frozen=True, slots=True)
class SettlementObligation:
    settlement_obligation_id: DomainId
    source_fill_id: DomainId
    trade_time: UtcInstant
    settlement_time: UtcInstant
    instrument_id: InstrumentId | None
    quantity: Quantity | None
    currency_id: CurrencyId | None
    amount: Money | None

    def __post_init__(self) -> None:
        _require_id(
            "settlement_obligation_id",
            self.settlement_obligation_id,
            DomainIdKind.SETTLEMENT,
        )
        _require_id("source_fill_id", self.source_fill_id, DomainIdKind.FILL)
        if not isinstance(self.trade_time, UtcInstant):
            raise TypeError("trade_time must be UtcInstant")
        if not isinstance(self.settlement_time, UtcInstant):
            raise TypeError("settlement_time must be UtcInstant")
        if self.settlement_time < self.trade_time:
            raise ValueError("settlement_time must be at or after trade_time")
        instrument_leg = self.instrument_id is not None or self.quantity is not None
        currency_leg = self.currency_id is not None or self.amount is not None
        if instrument_leg == currency_leg:
            raise ValueError("SettlementObligation requires exactly one obligation leg")
        if instrument_leg:
            if not isinstance(self.instrument_id, InstrumentId) or not isinstance(
                self.quantity, Quantity
            ):
                raise ValueError("Instrument obligation requires InstrumentId and Quantity")
            if self.quantity.instrument_id != str(self.instrument_id):
                raise ValueError("SettlementObligation instrument identity mismatch")
            units = self.quantity.units
        else:
            if not isinstance(self.currency_id, CurrencyId) or not isinstance(
                self.amount, Money
            ):
                raise ValueError("Currency obligation requires CurrencyId and Money")
            if self.amount.currency != self.currency_id.value:
                raise ValueError("SettlementObligation currency identity mismatch")
            units = self.amount.units
        if units == 0:
            raise ValueError("SettlementObligation must be non-zero")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "settlement_obligation",
            "settlement_obligation_id": self.settlement_obligation_id,
            "source_fill_id": self.source_fill_id,
            "trade_time": self.trade_time,
            "settlement_time": self.settlement_time,
            "instrument_id": self.instrument_id,
            "quantity": self.quantity,
            "currency_id": self.currency_id,
            "amount": self.amount,
        }


class TranslationStatus(str, Enum):
    TRANSLATED = "translated"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class UnsupportedCapability:
    capability: str
    requested_value: str
    reason_code: str

    def __post_init__(self) -> None:
        _require_text("capability", self.capability)
        _require_text("requested_value", self.requested_value)
        _require_text("reason_code", self.reason_code)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "unsupported_capability",
            "capability": self.capability,
            "requested_value": self.requested_value,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class TranslationFieldMapping:
    canonical_field: str
    canonical_value: str
    target_field: str
    target_value: str

    def __post_init__(self) -> None:
        _require_text("canonical_field", self.canonical_field)
        _require_text("canonical_value", self.canonical_value)
        _require_text("target_field", self.target_field)
        _require_text("target_value", self.target_value)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "translation_field_mapping",
            "canonical_field": self.canonical_field,
            "canonical_value": self.canonical_value,
            "target_field": self.target_field,
            "target_value": self.target_value,
        }


@dataclass(frozen=True, slots=True)
class OrderTranslationReport:
    report_id: str
    order_id: DomainId
    translator_key: str
    translator_version: str
    target_profile_id: str
    status: TranslationStatus
    unsupported_capabilities: tuple[UnsupportedCapability, ...]
    field_mappings: tuple[TranslationFieldMapping, ...]
    translation_time: UtcInstant

    def __post_init__(self) -> None:
        _require_text("report_id", self.report_id)
        _require_id("order_id", self.order_id, DomainIdKind.ORDER)
        _require_text("translator_key", self.translator_key)
        _require_text("translator_version", self.translator_version)
        _require_text("target_profile_id", self.target_profile_id)
        if not isinstance(self.status, TranslationStatus):
            raise TypeError("status must be TranslationStatus")
        if not isinstance(self.unsupported_capabilities, tuple) or not all(
            isinstance(value, UnsupportedCapability)
            for value in self.unsupported_capabilities
        ):
            raise TypeError("unsupported_capabilities must contain UnsupportedCapability")
        if not isinstance(self.field_mappings, tuple) or not all(
            isinstance(value, TranslationFieldMapping) for value in self.field_mappings
        ):
            raise TypeError("field_mappings must contain TranslationFieldMapping")
        unsupported_keys = [
            (value.capability, value.requested_value, value.reason_code)
            for value in self.unsupported_capabilities
        ]
        if len(set(unsupported_keys)) != len(unsupported_keys):
            raise ValueError("duplicate unsupported capability")
        canonical_fields = [value.canonical_field for value in self.field_mappings]
        if len(set(canonical_fields)) != len(canonical_fields):
            raise ValueError("duplicate canonical field mapping")
        if self.status is TranslationStatus.TRANSLATED:
            if self.unsupported_capabilities:
                raise ValueError("translated report cannot contain unsupported capability")
            if not self.field_mappings:
                raise ValueError("translated report requires field mappings")
        elif not self.unsupported_capabilities:
            raise ValueError("rejected report requires unsupported capability")
        if not isinstance(self.translation_time, UtcInstant):
            raise TypeError("translation_time must be UtcInstant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_translation_report",
            "report_id": self.report_id,
            "order_id": self.order_id,
            "translator_key": self.translator_key,
            "translator_version": self.translator_version,
            "target_profile_id": self.target_profile_id,
            "status": self.status.value,
            "unsupported_capabilities": sorted(
                self.unsupported_capabilities,
                key=lambda value: (
                    value.capability,
                    value.requested_value,
                    value.reason_code,
                ),
            ),
            "field_mappings": sorted(
                self.field_mappings,
                key=lambda value: (value.canonical_field, value.target_field),
            ),
            "translation_time": self.translation_time,
        }
