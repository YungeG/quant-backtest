from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from crypto_quant_domain import (
    ExecutionStyle,
    OrderIntent,
    PositionEffect,
    TimeInForce,
    UnsupportedCapability,
    canonical_bytes,
    canonical_sha256,
)


_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_DECISION_ID_RE = re.compile(r"order-capability-decision-v1:sha256:[0-9a-f]{64}")


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be canonical non-empty text")
    stripped = value.strip()
    if not stripped or stripped != value:
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(stripped)


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 digest")


def _require_decision_id(value: str) -> None:
    if not isinstance(value, str) or _DECISION_ID_RE.fullmatch(value) is None:
        raise ValueError("decision_id must be a deterministic v1 identity")


class OrderCapabilityKey(str, Enum):
    EXECUTION_STYLE = "execution_style"
    PRICE_CONSTRAINT = "price_constraint"
    TIME_IN_FORCE = "time_in_force"
    REDUCE_ONLY = "reduce_only"
    POSITION_EFFECT = "position_effect"


class PriceConstraintShape(str, Enum):
    NONE = "none"
    LIMIT = "limit"
    TRIGGER = "trigger"
    LIMIT_AND_TRIGGER = "limit_and_trigger"

    @classmethod
    def from_intent(cls, intent: OrderIntent) -> Self:
        if not isinstance(intent, OrderIntent):
            raise TypeError("intent must be OrderIntent")
        constraint = intent.price_constraint
        if constraint is None:
            return cls.NONE
        if constraint.limit_price is not None and constraint.trigger_price is not None:
            return cls.LIMIT_AND_TRIGGER
        if constraint.limit_price is not None:
            return cls.LIMIT
        return cls.TRIGGER


@dataclass(frozen=True, slots=True)
class OrderStyleCapability:
    execution_style: ExecutionStyle
    price_constraint_shapes: tuple[PriceConstraintShape, ...]
    time_in_forces: tuple[TimeInForce, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.execution_style, ExecutionStyle):
            raise TypeError("execution_style must be ExecutionStyle")
        if not isinstance(self.price_constraint_shapes, tuple) or not all(
            isinstance(value, PriceConstraintShape)
            for value in self.price_constraint_shapes
        ):
            raise TypeError(
                "price_constraint_shapes must contain PriceConstraintShape"
            )
        if len(set(self.price_constraint_shapes)) != len(
            self.price_constraint_shapes
        ):
            raise ValueError("duplicate PriceConstraintShape")
        if not isinstance(self.time_in_forces, tuple) or not all(
            isinstance(value, TimeInForce) for value in self.time_in_forces
        ):
            raise TypeError("time_in_forces must contain TimeInForce")
        if len(set(self.time_in_forces)) != len(self.time_in_forces):
            raise ValueError("duplicate TimeInForce")
        object.__setattr__(
            self,
            "price_constraint_shapes",
            tuple(sorted(self.price_constraint_shapes, key=lambda value: value.value)),
        )
        object.__setattr__(
            self,
            "time_in_forces",
            tuple(sorted(self.time_in_forces, key=lambda value: value.value)),
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_style_capability",
            "execution_style": self.execution_style.value,
            "price_constraint_shapes": tuple(
                value.value for value in self.price_constraint_shapes
            ),
            "time_in_forces": tuple(value.value for value in self.time_in_forces),
        }


def _style_key(value: OrderStyleCapability) -> str:
    return value.execution_style.value


def _ordered_capability_values(
    style_capabilities: tuple[OrderStyleCapability, ...],
    supported_position_effects: tuple[PositionEffect, ...],
    declared_capability_keys: tuple[str, ...],
) -> tuple[
    tuple[OrderStyleCapability, ...],
    tuple[PositionEffect, ...],
    tuple[str, ...],
]:
    return (
        tuple(sorted(style_capabilities, key=_style_key)),
        tuple(sorted(supported_position_effects, key=lambda value: value.value)),
        tuple(sorted(declared_capability_keys)),
    )


def _capability_config_payload(
    *,
    capability_set_key: str,
    capability_set_version: int,
    style_capabilities: tuple[OrderStyleCapability, ...],
    supports_reduce_only: bool,
    supported_position_effects: tuple[PositionEffect, ...],
    declared_capability_keys: tuple[str, ...],
) -> dict[str, Any]:
    ordered_styles, ordered_effects, ordered_keys = _ordered_capability_values(
        style_capabilities,
        supported_position_effects,
        declared_capability_keys,
    )
    return {
        "type": "order_capability_set_config",
        "schema_version": 1,
        "capability_set_key": capability_set_key,
        "capability_set_version": capability_set_version,
        "style_capabilities": ordered_styles,
        "supports_reduce_only": supports_reduce_only,
        "supported_position_effects": tuple(
            value.value for value in ordered_effects
        ),
        "declared_capability_keys": ordered_keys,
    }


@dataclass(frozen=True, slots=True)
class OrderCapabilitySet:
    capability_set_key: str
    capability_set_version: int
    style_capabilities: tuple[OrderStyleCapability, ...]
    supports_reduce_only: bool
    supported_position_effects: tuple[PositionEffect, ...]
    declared_capability_keys: tuple[str, ...]
    config_hash: str

    def __post_init__(self) -> None:
        _canonical_text("capability_set_key", self.capability_set_key)
        if isinstance(self.capability_set_version, bool) or not isinstance(
            self.capability_set_version, int
        ):
            raise TypeError("capability_set_version must be an integer")
        if self.capability_set_version <= 0:
            raise ValueError("capability_set_version must be positive")
        if not isinstance(self.style_capabilities, tuple) or not all(
            isinstance(value, OrderStyleCapability)
            for value in self.style_capabilities
        ):
            raise TypeError("style_capabilities must contain OrderStyleCapability")
        styles = [value.execution_style for value in self.style_capabilities]
        if len(set(styles)) != len(styles):
            raise ValueError("duplicate execution style capability")
        if type(self.supports_reduce_only) is not bool:
            raise TypeError("supports_reduce_only must be bool")
        if not isinstance(self.supported_position_effects, tuple) or not all(
            isinstance(value, PositionEffect)
            for value in self.supported_position_effects
        ):
            raise TypeError(
                "supported_position_effects must contain PositionEffect"
            )
        if len(set(self.supported_position_effects)) != len(
            self.supported_position_effects
        ):
            raise ValueError("duplicate supported PositionEffect")
        if not isinstance(self.declared_capability_keys, tuple) or not all(
            isinstance(value, str) for value in self.declared_capability_keys
        ):
            raise TypeError("declared_capability_keys must contain strings")
        for value in self.declared_capability_keys:
            _canonical_text("declared capability key", value)
        if len(set(self.declared_capability_keys)) != len(
            self.declared_capability_keys
        ):
            raise ValueError("duplicate declared capability")
        _require_hash("config_hash", self.config_hash)

        ordered_styles, ordered_effects, ordered_keys = _ordered_capability_values(
            self.style_capabilities,
            self.supported_position_effects,
            self.declared_capability_keys,
        )
        expected_hash = canonical_sha256(self.config_payload())
        if self.config_hash != expected_hash:
            raise ValueError("OrderCapabilitySet config_hash mismatch")
        object.__setattr__(self, "style_capabilities", ordered_styles)
        object.__setattr__(self, "supported_position_effects", ordered_effects)
        object.__setattr__(self, "declared_capability_keys", ordered_keys)

    @classmethod
    def create(
        cls,
        *,
        capability_set_key: str,
        capability_set_version: int,
        style_capabilities: tuple[OrderStyleCapability, ...],
        supports_reduce_only: bool,
        supported_position_effects: tuple[PositionEffect, ...],
        declared_capability_keys: tuple[str, ...],
    ) -> Self:
        ordered_styles, ordered_effects, ordered_keys = _ordered_capability_values(
            style_capabilities,
            supported_position_effects,
            declared_capability_keys,
        )
        config_payload = _capability_config_payload(
            capability_set_key=capability_set_key,
            capability_set_version=capability_set_version,
            style_capabilities=ordered_styles,
            supports_reduce_only=supports_reduce_only,
            supported_position_effects=ordered_effects,
            declared_capability_keys=ordered_keys,
        )
        config_hash = canonical_sha256(config_payload)
        return cls(
            capability_set_key=capability_set_key,
            capability_set_version=capability_set_version,
            style_capabilities=ordered_styles,
            supports_reduce_only=supports_reduce_only,
            supported_position_effects=ordered_effects,
            declared_capability_keys=ordered_keys,
            config_hash=config_hash,
        )

    def config_payload(self) -> dict[str, Any]:
        return _capability_config_payload(
            capability_set_key=self.capability_set_key,
            capability_set_version=self.capability_set_version,
            style_capabilities=self.style_capabilities,
            supports_reduce_only=self.supports_reduce_only,
            supported_position_effects=self.supported_position_effects,
            declared_capability_keys=self.declared_capability_keys,
        )

    @property
    def capability_set_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "order_capability_set",
            "config_hash": self.config_hash,
        }


def _decision_payload(
    *,
    outcome: str,
    intent_hash: str,
    capability_set_hash: str,
    unsupported_capabilities: tuple[UnsupportedCapability, ...],
) -> dict[str, Any]:
    return {
        "type": "order_capability_decision_identity",
        "schema_version": 1,
        "outcome": outcome,
        "intent_hash": intent_hash,
        "capability_set_hash": capability_set_hash,
        "unsupported_capabilities": unsupported_capabilities,
    }


def _derive_decision_id(
    *,
    outcome: str,
    intent_hash: str,
    capability_set_hash: str,
    unsupported_capabilities: tuple[UnsupportedCapability, ...] = (),
) -> str:
    return "order-capability-decision-v1:" + canonical_sha256(
        _decision_payload(
            outcome=outcome,
            intent_hash=intent_hash,
            capability_set_hash=capability_set_hash,
            unsupported_capabilities=unsupported_capabilities,
        )
    )


def _validate_decision_evidence(
    *,
    decision_id: str,
    source_intent: OrderIntent,
    capability_set: OrderCapabilitySet,
    intent_hash: str,
    capability_set_hash: str,
    outcome: str,
    unsupported_capabilities: tuple[UnsupportedCapability, ...] = (),
) -> None:
    _require_decision_id(decision_id)
    if not isinstance(source_intent, OrderIntent):
        raise TypeError("source_intent must be OrderIntent")
    if not isinstance(capability_set, OrderCapabilitySet):
        raise TypeError("capability_set must be OrderCapabilitySet")
    _require_hash("intent_hash", intent_hash)
    _require_hash("capability_set_hash", capability_set_hash)
    if intent_hash != canonical_sha256(source_intent):
        raise ValueError("intent_hash mismatch")
    if capability_set_hash != capability_set.capability_set_hash:
        raise ValueError("capability_set_hash mismatch")
    expected = _derive_decision_id(
        outcome=outcome,
        intent_hash=intent_hash,
        capability_set_hash=capability_set_hash,
        unsupported_capabilities=unsupported_capabilities,
    )
    if decision_id != expected:
        raise ValueError("decision_id mismatch")


@dataclass(frozen=True, slots=True)
class OrderCapabilityApproval:
    decision_id: str
    source_intent: OrderIntent
    capability_set: OrderCapabilitySet
    intent_hash: str
    capability_set_hash: str

    def __post_init__(self) -> None:
        _validate_decision_evidence(
            decision_id=self.decision_id,
            source_intent=self.source_intent,
            capability_set=self.capability_set,
            intent_hash=self.intent_hash,
            capability_set_hash=self.capability_set_hash,
            outcome="approved",
        )

    @classmethod
    def create(
        cls, source_intent: OrderIntent, capability_set: OrderCapabilitySet
    ) -> Self:
        intent_hash = canonical_sha256(source_intent)
        capability_set_hash = capability_set.capability_set_hash
        return cls(
            decision_id=_derive_decision_id(
                outcome="approved",
                intent_hash=intent_hash,
                capability_set_hash=capability_set_hash,
            ),
            source_intent=source_intent,
            capability_set=capability_set,
            intent_hash=intent_hash,
            capability_set_hash=capability_set_hash,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_capability_approval",
            "schema_version": 1,
            "decision_id": self.decision_id,
            "source_intent": self.source_intent,
            "capability_set": self.capability_set,
            "intent_hash": self.intent_hash,
            "capability_set_hash": self.capability_set_hash,
        }


@dataclass(frozen=True, slots=True)
class CapabilityRejection:
    decision_id: str
    source_intent: OrderIntent
    capability_set: OrderCapabilitySet
    intent_hash: str
    capability_set_hash: str
    unsupported_capabilities: tuple[UnsupportedCapability, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.unsupported_capabilities, tuple) or not all(
            isinstance(value, UnsupportedCapability)
            for value in self.unsupported_capabilities
        ):
            raise TypeError(
                "unsupported_capabilities must contain UnsupportedCapability"
            )
        if not self.unsupported_capabilities:
            raise ValueError("CapabilityRejection requires unsupported capability")
        ordered = tuple(
            sorted(
                self.unsupported_capabilities,
                key=lambda value: (
                    value.capability,
                    value.requested_value,
                    value.reason_code,
                ),
            )
        )
        keys = [
            (value.capability, value.requested_value, value.reason_code)
            for value in ordered
        ]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate unsupported capability")
        object.__setattr__(self, "unsupported_capabilities", ordered)
        _validate_decision_evidence(
            decision_id=self.decision_id,
            source_intent=self.source_intent,
            capability_set=self.capability_set,
            intent_hash=self.intent_hash,
            capability_set_hash=self.capability_set_hash,
            outcome="rejected",
            unsupported_capabilities=ordered,
        )

    @classmethod
    def create(
        cls,
        source_intent: OrderIntent,
        capability_set: OrderCapabilitySet,
        unsupported_capabilities: tuple[UnsupportedCapability, ...],
    ) -> Self:
        ordered = tuple(
            sorted(
                unsupported_capabilities,
                key=lambda value: (
                    value.capability,
                    value.requested_value,
                    value.reason_code,
                ),
            )
        )
        intent_hash = canonical_sha256(source_intent)
        capability_set_hash = capability_set.capability_set_hash
        return cls(
            decision_id=_derive_decision_id(
                outcome="rejected",
                intent_hash=intent_hash,
                capability_set_hash=capability_set_hash,
                unsupported_capabilities=ordered,
            ),
            source_intent=source_intent,
            capability_set=capability_set,
            intent_hash=intent_hash,
            capability_set_hash=capability_set_hash,
            unsupported_capabilities=ordered,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "capability_rejection",
            "schema_version": 1,
            "decision_id": self.decision_id,
            "source_intent": self.source_intent,
            "capability_set": self.capability_set,
            "intent_hash": self.intent_hash,
            "capability_set_hash": self.capability_set_hash,
            "unsupported_capabilities": self.unsupported_capabilities,
        }


@dataclass(frozen=True, slots=True)
class OrderCapabilityDecision:
    approval: OrderCapabilityApproval | None
    rejection: CapabilityRejection | None

    def __post_init__(self) -> None:
        if (self.approval is None) == (self.rejection is None):
            raise ValueError("decision requires exactly one approval or rejection")
        if self.approval is not None and not isinstance(
            self.approval, OrderCapabilityApproval
        ):
            raise TypeError("approval must be OrderCapabilityApproval or None")
        if self.rejection is not None and not isinstance(
            self.rejection, CapabilityRejection
        ):
            raise TypeError("rejection must be CapabilityRejection or None")

    @property
    def decision_id(self) -> str:
        selected = self.approval if self.approval is not None else self.rejection
        if selected is None:  # pragma: no cover - protected by __post_init__
            raise RuntimeError("invalid capability decision")
        return selected.decision_id

    @property
    def decision_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_capability_decision",
            "schema_version": 1,
            "approval": self.approval,
            "rejection": self.rejection,
        }


class OrderCapabilityValidator:
    def validate(
        self,
        intent: OrderIntent,
        capability_set: OrderCapabilitySet,
    ) -> OrderCapabilityDecision:
        if not isinstance(intent, OrderIntent):
            raise TypeError("intent must be OrderIntent")
        if not isinstance(capability_set, OrderCapabilitySet):
            raise TypeError("capability_set must be OrderCapabilitySet")

        declared = set(capability_set.declared_capability_keys)
        known = {value.value for value in OrderCapabilityKey}
        shape = PriceConstraintShape.from_intent(intent)
        requested = {
            OrderCapabilityKey.EXECUTION_STYLE.value: intent.execution_style.value,
            OrderCapabilityKey.PRICE_CONSTRAINT.value: shape.value,
            OrderCapabilityKey.TIME_IN_FORCE.value: intent.time_in_force.value,
            OrderCapabilityKey.REDUCE_ONLY.value: str(intent.reduce_only).lower(),
            OrderCapabilityKey.POSITION_EFFECT.value: intent.position_effect.value,
        }
        unsupported: list[UnsupportedCapability] = []

        for key in sorted(known - declared):
            unsupported.append(
                UnsupportedCapability(
                    capability=key,
                    requested_value=requested[key],
                    reason_code="missing_capability_declaration",
                )
            )
        for key in sorted(declared - known):
            unsupported.append(
                UnsupportedCapability(
                    capability=key,
                    requested_value="declared",
                    reason_code="unknown_capability",
                )
            )

        by_style = {
            value.execution_style: value
            for value in capability_set.style_capabilities
        }
        style_capability = by_style.get(intent.execution_style)
        if OrderCapabilityKey.EXECUTION_STYLE.value in declared:
            if style_capability is None:
                unsupported.append(
                    UnsupportedCapability(
                        capability=OrderCapabilityKey.EXECUTION_STYLE.value,
                        requested_value=intent.execution_style.value,
                        reason_code="unsupported_execution_style",
                    )
                )
        if style_capability is not None:
            if (
                OrderCapabilityKey.PRICE_CONSTRAINT.value in declared
                and shape not in style_capability.price_constraint_shapes
            ):
                unsupported.append(
                    UnsupportedCapability(
                        capability=OrderCapabilityKey.PRICE_CONSTRAINT.value,
                        requested_value=shape.value,
                        reason_code="unsupported_price_constraint",
                    )
                )
            if (
                OrderCapabilityKey.TIME_IN_FORCE.value in declared
                and intent.time_in_force not in style_capability.time_in_forces
            ):
                unsupported.append(
                    UnsupportedCapability(
                        capability=OrderCapabilityKey.TIME_IN_FORCE.value,
                        requested_value=intent.time_in_force.value,
                        reason_code="unsupported_time_in_force",
                    )
                )
        if (
            OrderCapabilityKey.REDUCE_ONLY.value in declared
            and intent.reduce_only
            and not capability_set.supports_reduce_only
        ):
            unsupported.append(
                UnsupportedCapability(
                    capability=OrderCapabilityKey.REDUCE_ONLY.value,
                    requested_value="true",
                    reason_code="unsupported_reduce_only",
                )
            )
        if (
            OrderCapabilityKey.POSITION_EFFECT.value in declared
            and intent.position_effect
            not in capability_set.supported_position_effects
        ):
            unsupported.append(
                UnsupportedCapability(
                    capability=OrderCapabilityKey.POSITION_EFFECT.value,
                    requested_value=intent.position_effect.value,
                    reason_code="unsupported_position_effect",
                )
            )

        if unsupported:
            return OrderCapabilityDecision(
                approval=None,
                rejection=CapabilityRejection.create(
                    intent,
                    capability_set,
                    tuple(unsupported),
                ),
            )
        return OrderCapabilityDecision(
            approval=OrderCapabilityApproval.create(intent, capability_set),
            rejection=None,
        )
