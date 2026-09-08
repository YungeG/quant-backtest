from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Self

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    ExecutionStyle,
    InstrumentId,
    OrderIntent,
    OrderSide,
    OrderStatus,
    PortfolioSnapshot,
    PositionEffect,
    Quantity,
    Scale,
    TimeInForce,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .orders import OrderEventStream
from .reservations import ResourceReservationState
from .settlement import AvailabilityState
from .sizing import NormalizedPortfolioTarget


_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_ID_RE = re.compile(r"[a-z][a-z0-9-]*-v1:sha256:[0-9a-f]{64}")
_TERMINAL_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
}


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 digest")


def _require_identity(name: str, value: str) -> None:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a deterministic v1 identity")


def _quantity(instrument_id: InstrumentId, scale: Scale, units: int) -> Quantity:
    return Quantity(units, scale, str(instrument_id))


def _quantity_triplet(
    current: Quantity, target: Quantity, coverage: Quantity
) -> None:
    values = (current, target, coverage)
    if len({value.instrument_id for value in values}) != 1:
        raise ValueError("Rebalance quantities must share Instrument identity")
    if len({value.scale for value in values}) != 1:
        raise ValueError("Rebalance quantities must share Scale")


@dataclass(frozen=True, slots=True)
class RebalancePolicy:
    policy_key: str
    policy_version: int
    execution_style: ExecutionStyle
    time_in_force: TimeInForce
    urgency: str
    plan_valid_for_nanoseconds: int | None
    config_hash: str

    def __post_init__(self) -> None:
        _canonical_text("policy_key", self.policy_key)
        if isinstance(self.policy_version, bool) or not isinstance(
            self.policy_version, int
        ):
            raise TypeError("policy_version must be an integer")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        if not isinstance(self.execution_style, ExecutionStyle):
            raise TypeError("execution_style must be ExecutionStyle")
        if not isinstance(self.time_in_force, TimeInForce):
            raise TypeError("time_in_force must be TimeInForce")
        _canonical_text("urgency", self.urgency)
        if self.plan_valid_for_nanoseconds is not None:
            if isinstance(self.plan_valid_for_nanoseconds, bool) or not isinstance(
                self.plan_valid_for_nanoseconds, int
            ):
                raise TypeError("plan_valid_for_nanoseconds must be an integer or None")
            if self.plan_valid_for_nanoseconds <= 0:
                raise ValueError("plan_valid_for_nanoseconds must be positive")
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("RebalancePolicy config_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        policy_key: str,
        policy_version: int,
        execution_style: ExecutionStyle,
        time_in_force: TimeInForce,
        urgency: str,
        plan_valid_for_nanoseconds: int | None,
    ) -> Self:
        payload = {
            "type": "rebalance_policy_config",
            "schema_version": 1,
            "policy_key": policy_key,
            "policy_version": policy_version,
            "execution_style": execution_style.value,
            "time_in_force": time_in_force.value,
            "urgency": urgency,
            "plan_valid_for_nanoseconds": plan_valid_for_nanoseconds,
        }
        return cls(
            policy_key=policy_key,
            policy_version=policy_version,
            execution_style=execution_style,
            time_in_force=time_in_force,
            urgency=urgency,
            plan_valid_for_nanoseconds=plan_valid_for_nanoseconds,
            config_hash=canonical_sha256(payload),
        )

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "rebalance_policy_config",
            "schema_version": 1,
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "execution_style": self.execution_style.value,
            "time_in_force": self.time_in_force.value,
            "urgency": self.urgency,
            "plan_valid_for_nanoseconds": self.plan_valid_for_nanoseconds,
        }

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "rebalance_policy",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class TargetValidity:
    normalized_target_id: str
    normalized_target_hash: str
    valid_from: UtcInstant
    valid_until: UtcInstant | None

    def __post_init__(self) -> None:
        _require_identity("normalized_target_id", self.normalized_target_id)
        _require_hash("normalized_target_hash", self.normalized_target_hash)
        if not isinstance(self.valid_from, UtcInstant):
            raise TypeError("valid_from must be UtcInstant")
        if self.valid_until is not None:
            if not isinstance(self.valid_until, UtcInstant):
                raise TypeError("valid_until must be UtcInstant or None")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be after valid_from")

    def is_active_at(self, instant: UtcInstant) -> bool:
        if not isinstance(instant, UtcInstant):
            raise TypeError("instant must be UtcInstant")
        return self.valid_from <= instant and (
            self.valid_until is None or instant < self.valid_until
        )

    @property
    def validity_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "target_validity",
            "schema_version": 1,
            "normalized_target_id": self.normalized_target_id,
            "normalized_target_hash": self.normalized_target_hash,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }


@dataclass(frozen=True, slots=True)
class PlannedOrder:
    planned_order_id: str
    instrument_id: InstrumentId
    intent: OrderIntent
    current_quantity: Quantity
    target_quantity: Quantity
    retained_working_coverage: Quantity
    planned_delta: Quantity
    policy_hash: str

    def __post_init__(self) -> None:
        _require_identity("planned_order_id", self.planned_order_id)
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.intent, OrderIntent):
            raise TypeError("intent must be OrderIntent")
        if self.intent.instrument_id != self.instrument_id:
            raise ValueError("PlannedOrder Intent instrument mismatch")
        quantities = (
            self.current_quantity,
            self.target_quantity,
            self.retained_working_coverage,
            self.planned_delta,
        )
        if not all(isinstance(value, Quantity) for value in quantities):
            raise TypeError("PlannedOrder quantities must be Quantity")
        if any(value.instrument_id != str(self.instrument_id) for value in quantities):
            raise ValueError("PlannedOrder Quantity instrument mismatch")
        if len({value.scale for value in quantities}) != 1:
            raise ValueError("PlannedOrder Quantity Scale mismatch")
        if self.planned_delta.units == 0:
            raise ValueError("PlannedOrder delta must be non-zero")
        expected_side = (
            OrderSide.BUY if self.planned_delta.units > 0 else OrderSide.SELL
        )
        if self.intent.side is not expected_side:
            raise ValueError("PlannedOrder side does not match signed delta")
        if self.intent.quantity.units != abs(self.planned_delta.units) or (
            self.intent.quantity.scale != self.planned_delta.scale
        ):
            raise ValueError("PlannedOrder Intent quantity does not match delta")
        _require_hash("policy_hash", self.policy_hash)

    @property
    def planned_order_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "planned_order",
            "schema_version": 1,
            "planned_order_id": self.planned_order_id,
            "instrument_id": self.instrument_id,
            "intent": self.intent,
            "current_quantity": self.current_quantity,
            "target_quantity": self.target_quantity,
            "retained_working_coverage": self.retained_working_coverage,
            "planned_delta": self.planned_delta,
            "policy_hash": self.policy_hash,
        }


@dataclass(frozen=True, slots=True)
class CancelIntent:
    cancel_intent_id: str
    order_id: DomainId
    instrument_id: InstrumentId
    reason_code: str
    normalized_target_id: str

    def __post_init__(self) -> None:
        _require_identity("cancel_intent_id", self.cancel_intent_id)
        if not isinstance(self.order_id, DomainId) or (
            self.order_id.kind is not DomainIdKind.ORDER
        ):
            raise ValueError("order_id must be an ORDER DomainId")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        _canonical_text("reason_code", self.reason_code)
        _require_identity("normalized_target_id", self.normalized_target_id)

    @property
    def cancel_intent_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cancel_intent",
            "schema_version": 1,
            "cancel_intent_id": self.cancel_intent_id,
            "order_id": self.order_id,
            "instrument_id": self.instrument_id,
            "reason_code": self.reason_code,
            "normalized_target_id": self.normalized_target_id,
        }


class PlanningOmissionCode(str, Enum):
    ALREADY_COVERED = "already_covered"
    CANCELLATION_PENDING = "cancellation_pending"
    TARGET_EXPIRED = "target_expired"
    POSITION_RELATIVE_REACHABILITY_STALE = (
        "position_relative_reachability_stale"
    )


@dataclass(frozen=True, slots=True)
class PlanningOmission:
    instrument_id: InstrumentId
    code: PlanningOmissionCode
    current_quantity: Quantity
    target_quantity: Quantity
    retained_working_coverage: Quantity

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.code, PlanningOmissionCode):
            raise TypeError("code must be PlanningOmissionCode")
        _quantity_triplet(
            self.current_quantity,
            self.target_quantity,
            self.retained_working_coverage,
        )
        if self.current_quantity.instrument_id != str(self.instrument_id):
            raise ValueError("PlanningOmission Instrument mismatch")

    @property
    def omission_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "planning_omission",
            "instrument_id": self.instrument_id,
            "code": self.code.value,
            "current_quantity": self.current_quantity,
            "target_quantity": self.target_quantity,
            "retained_working_coverage": self.retained_working_coverage,
        }


@dataclass(frozen=True, slots=True)
class OrderPlan:
    plan_id: str
    account_id: str
    created_at: UtcInstant
    based_on_normalized_target_id: str
    based_on_normalized_target_hash: str
    based_on_target_validity_hash: str
    based_on_portfolio_snapshot_hash: str
    based_on_working_order_set_hash: str
    based_on_reservation_state_hash: str
    based_on_availability_state_hash: str
    policy: RebalancePolicy
    valid_until: UtcInstant | None
    planned_orders: tuple[PlannedOrder, ...]
    cancel_intents: tuple[CancelIntent, ...]
    omissions: tuple[PlanningOmission, ...]
    supersedes_plan_id: str | None

    def __post_init__(self) -> None:
        _require_identity("plan_id", self.plan_id)
        _canonical_text("account_id", self.account_id)
        if not isinstance(self.created_at, UtcInstant):
            raise TypeError("created_at must be UtcInstant")
        _require_identity(
            "based_on_normalized_target_id", self.based_on_normalized_target_id
        )
        for name in (
            "based_on_normalized_target_hash",
            "based_on_target_validity_hash",
            "based_on_portfolio_snapshot_hash",
            "based_on_working_order_set_hash",
            "based_on_reservation_state_hash",
            "based_on_availability_state_hash",
        ):
            _require_hash(name, getattr(self, name))
        if not isinstance(self.policy, RebalancePolicy):
            raise TypeError("policy must be RebalancePolicy")
        if self.valid_until is not None:
            if not isinstance(self.valid_until, UtcInstant):
                raise TypeError("valid_until must be UtcInstant or None")
            if self.valid_until <= self.created_at:
                raise ValueError("OrderPlan valid_until must be after created_at")
        if not isinstance(self.planned_orders, tuple) or not all(
            isinstance(value, PlannedOrder) for value in self.planned_orders
        ):
            raise TypeError("planned_orders must contain PlannedOrder")
        if not isinstance(self.cancel_intents, tuple) or not all(
            isinstance(value, CancelIntent) for value in self.cancel_intents
        ):
            raise TypeError("cancel_intents must contain CancelIntent")
        if not isinstance(self.omissions, tuple) or not all(
            isinstance(value, PlanningOmission) for value in self.omissions
        ):
            raise TypeError("omissions must contain PlanningOmission")
        planned = tuple(sorted(self.planned_orders, key=lambda value: value.instrument_id))
        cancels = tuple(
            sorted(self.cancel_intents, key=lambda value: value.order_id.value)
        )
        omissions = tuple(sorted(self.omissions, key=lambda value: value.instrument_id))
        if len({value.instrument_id for value in planned}) != len(planned):
            raise ValueError("OrderPlan has duplicate Planned Instrument")
        if len({value.order_id for value in cancels}) != len(cancels):
            raise ValueError("OrderPlan has duplicate Cancel Order")
        if len({value.instrument_id for value in omissions}) != len(omissions):
            raise ValueError("OrderPlan has duplicate Omission Instrument")
        cancel_instruments = {value.instrument_id for value in cancels}
        if cancel_instruments & {value.instrument_id for value in planned}:
            raise ValueError("OrderPlan cannot cancel and replace one Instrument together")
        if self.supersedes_plan_id is not None:
            _require_identity("supersedes_plan_id", self.supersedes_plan_id)
            if self.supersedes_plan_id == self.plan_id:
                raise ValueError("OrderPlan cannot supersede itself")
        object.__setattr__(self, "planned_orders", planned)
        object.__setattr__(self, "cancel_intents", cancels)
        object.__setattr__(self, "omissions", omissions)
        expected_id = f"order-plan-v1:{canonical_sha256(self.identity_payload())}"
        if self.plan_id != expected_id:
            raise ValueError("OrderPlan plan_id mismatch")

    @classmethod
    def create(
        cls,
        *,
        account_id: str,
        created_at: UtcInstant,
        based_on_normalized_target_id: str,
        based_on_normalized_target_hash: str,
        based_on_target_validity_hash: str,
        based_on_portfolio_snapshot_hash: str,
        based_on_working_order_set_hash: str,
        based_on_reservation_state_hash: str,
        based_on_availability_state_hash: str,
        policy: RebalancePolicy,
        valid_until: UtcInstant | None,
        planned_orders: tuple[PlannedOrder, ...],
        cancel_intents: tuple[CancelIntent, ...],
        omissions: tuple[PlanningOmission, ...],
        supersedes_plan_id: str | None,
    ) -> Self:
        planned = tuple(sorted(planned_orders, key=lambda value: value.instrument_id))
        cancels = tuple(
            sorted(cancel_intents, key=lambda value: value.order_id.value)
        )
        omitted = tuple(sorted(omissions, key=lambda value: value.instrument_id))
        identity = {
            "type": "order_plan_identity",
            "schema_version": 1,
            "account_id": account_id,
            "created_at": created_at,
            "based_on_normalized_target_id": based_on_normalized_target_id,
            "based_on_normalized_target_hash": based_on_normalized_target_hash,
            "based_on_target_validity_hash": based_on_target_validity_hash,
            "based_on_portfolio_snapshot_hash": based_on_portfolio_snapshot_hash,
            "based_on_working_order_set_hash": based_on_working_order_set_hash,
            "based_on_reservation_state_hash": based_on_reservation_state_hash,
            "based_on_availability_state_hash": based_on_availability_state_hash,
            "policy": policy,
            "valid_until": valid_until,
            "planned_orders": planned,
            "cancel_intents": cancels,
            "omissions": omitted,
            "supersedes_plan_id": supersedes_plan_id,
        }
        return cls(
            plan_id=f"order-plan-v1:{canonical_sha256(identity)}",
            account_id=account_id,
            created_at=created_at,
            based_on_normalized_target_id=based_on_normalized_target_id,
            based_on_normalized_target_hash=based_on_normalized_target_hash,
            based_on_target_validity_hash=based_on_target_validity_hash,
            based_on_portfolio_snapshot_hash=based_on_portfolio_snapshot_hash,
            based_on_working_order_set_hash=based_on_working_order_set_hash,
            based_on_reservation_state_hash=based_on_reservation_state_hash,
            based_on_availability_state_hash=based_on_availability_state_hash,
            policy=policy,
            valid_until=valid_until,
            planned_orders=planned,
            cancel_intents=cancels,
            omissions=omitted,
            supersedes_plan_id=supersedes_plan_id,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "type": "order_plan_identity",
            "schema_version": 1,
            "account_id": self.account_id,
            "created_at": self.created_at,
            "based_on_normalized_target_id": self.based_on_normalized_target_id,
            "based_on_normalized_target_hash": self.based_on_normalized_target_hash,
            "based_on_target_validity_hash": self.based_on_target_validity_hash,
            "based_on_portfolio_snapshot_hash": self.based_on_portfolio_snapshot_hash,
            "based_on_working_order_set_hash": self.based_on_working_order_set_hash,
            "based_on_reservation_state_hash": self.based_on_reservation_state_hash,
            "based_on_availability_state_hash": self.based_on_availability_state_hash,
            "policy": self.policy,
            "valid_until": self.valid_until,
            "planned_orders": self.planned_orders,
            "cancel_intents": self.cancel_intents,
            "omissions": self.omissions,
            "supersedes_plan_id": self.supersedes_plan_id,
        }

    @property
    def plan_hash(self) -> str:
        return canonical_sha256(self)

    def is_valid_at(self, instant: UtcInstant) -> bool:
        return self.created_at <= instant and (
            self.valid_until is None or instant < self.valid_until
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "type": "order_plan", "plan_id": self.plan_id}


@dataclass(frozen=True, slots=True)
class RebalanceDecision:
    decision_id: str
    plan: OrderPlan

    def __post_init__(self) -> None:
        _require_identity("decision_id", self.decision_id)
        if not isinstance(self.plan, OrderPlan):
            raise TypeError("plan must be OrderPlan")
        expected = f"rebalance-decision-v1:{canonical_sha256(self.plan)}"
        if self.decision_id != expected:
            raise ValueError("RebalanceDecision decision_id mismatch")

    @classmethod
    def create(cls, plan: OrderPlan) -> Self:
        return cls(
            decision_id=f"rebalance-decision-v1:{canonical_sha256(plan)}",
            plan=plan,
        )

    @property
    def decision_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "rebalance_decision",
            "schema_version": 1,
            "decision_id": self.decision_id,
            "plan": self.plan,
        }


class RebalanceFailureCode(str, Enum):
    MISSING_POLICY = "missing_policy"
    TARGET_VALIDITY_MISMATCH = "target_validity_mismatch"
    CONTEXT_MISMATCH = "context_mismatch"
    DUPLICATE_WORKING_ORDER = "duplicate_working_order"
    TERMINAL_WORKING_ORDER = "terminal_working_order"
    QUANTITY_SCALE_MISMATCH = "quantity_scale_mismatch"
    PRIOR_PLAN_MISMATCH = "prior_plan_mismatch"


@dataclass(frozen=True, slots=True)
class RebalanceFailure:
    code: RebalanceFailureCode
    subject_keys: tuple[str, ...]
    evidence_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.code, RebalanceFailureCode):
            raise TypeError("code must be RebalanceFailureCode")
        if not isinstance(self.subject_keys, tuple):
            raise TypeError("subject_keys must be a tuple")
        if not self.subject_keys:
            raise ValueError("RebalanceFailure requires a subject")
        for value in self.subject_keys:
            _canonical_text("subject_key", value)
        subjects = tuple(sorted(set(self.subject_keys)))
        if not isinstance(self.evidence_hashes, tuple):
            raise TypeError("evidence_hashes must be a tuple")
        for value in self.evidence_hashes:
            _require_hash("evidence_hash", value)
        evidence = tuple(sorted(set(self.evidence_hashes)))
        object.__setattr__(self, "subject_keys", subjects)
        object.__setattr__(self, "evidence_hashes", evidence)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "rebalance_failure",
            "schema_version": 1,
            "code": self.code.value,
            "subject_keys": self.subject_keys,
            "evidence_hashes": self.evidence_hashes,
        }


@dataclass(frozen=True, slots=True)
class RebalanceOutcome:
    decision: RebalanceDecision | None
    failure: RebalanceFailure | None

    def __post_init__(self) -> None:
        if (self.decision is None) == (self.failure is None):
            raise ValueError("RebalanceOutcome requires exactly one decision or failure")

    @classmethod
    def succeeded(cls, decision: RebalanceDecision) -> Self:
        return cls(decision, None)

    @classmethod
    def failed(cls, failure: RebalanceFailure) -> Self:
        return cls(None, failure)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "rebalance_outcome",
            "decision": self.decision,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class _Basis:
    target_hash: str
    validity_hash: str
    snapshot_hash: str
    working_hash: str
    reservation_hash: str
    availability_hash: str
    policy_hash: str


class RebalanceCoordinator:
    def coordinate(
        self,
        *,
        target: NormalizedPortfolioTarget,
        target_validity: TargetValidity,
        portfolio_snapshot: PortfolioSnapshot,
        working_orders: tuple[OrderEventStream, ...],
        reservations: ResourceReservationState,
        availability: AvailabilityState,
        policy: RebalancePolicy | None,
        as_of: UtcInstant,
        prior_plan: OrderPlan | None = None,
    ) -> RebalanceOutcome:
        evidence = self._base_evidence(
            target, target_validity, portfolio_snapshot, reservations, availability
        )
        if policy is None:
            return self._failed(
                RebalanceFailureCode.MISSING_POLICY,
                (target.normalized_target_id,),
                evidence,
            )
        if not isinstance(policy, RebalancePolicy):
            raise TypeError("policy must be RebalancePolicy or None")
        if not isinstance(as_of, UtcInstant):
            raise TypeError("as_of must be UtcInstant")
        if not isinstance(working_orders, tuple) or not all(
            isinstance(value, OrderEventStream) for value in working_orders
        ):
            raise TypeError("working_orders must contain OrderEventStream")

        context_failure = self._validate_context(
            target,
            target_validity,
            portfolio_snapshot,
            reservations,
            availability,
            as_of,
            policy,
            evidence,
        )
        if context_failure is not None:
            return context_failure

        ordered_streams = tuple(
            sorted(working_orders, key=lambda value: value.order.order_id.value)
        )
        order_ids = tuple(value.order.order_id.value for value in ordered_streams)
        if len(order_ids) != len(set(order_ids)):
            return self._failed(
                RebalanceFailureCode.DUPLICATE_WORKING_ORDER,
                order_ids,
                evidence,
            )
        for stream in ordered_streams:
            state = stream.state
            if state is None or state.status in _TERMINAL_STATUSES:
                return self._failed(
                    RebalanceFailureCode.TERMINAL_WORKING_ORDER,
                    (stream.order.order_id.value,),
                    evidence + (stream.stream_hash,),
                )
            if stream.order.account_id != portfolio_snapshot.account_id:
                return self._failed(
                    RebalanceFailureCode.CONTEXT_MISMATCH,
                    (stream.order.order_id.value, stream.order.account_id),
                    evidence + (stream.stream_hash,),
                )
            if state.updated_at.instant > as_of:
                return self._failed(
                    RebalanceFailureCode.CONTEXT_MISMATCH,
                    (stream.order.order_id.value, "future_working_order"),
                    evidence + (stream.stream_hash,),
                )

        working_hash = self._working_order_set_hash(ordered_streams)
        basis = _Basis(
            target_hash=target.normalized_target_hash,
            validity_hash=target_validity.validity_hash,
            snapshot_hash=canonical_sha256(portfolio_snapshot),
            working_hash=working_hash,
            reservation_hash=reservations.state_hash,
            availability_hash=availability.state_hash,
            policy_hash=policy.policy_hash,
        )
        reservation_failure = self._validate_reservation_context(
            ordered_streams, reservations, evidence + (working_hash,)
        )
        if reservation_failure is not None:
            return reservation_failure

        if prior_plan is not None:
            if not isinstance(prior_plan, OrderPlan):
                raise TypeError("prior_plan must be OrderPlan or None")
            if prior_plan.account_id != portfolio_snapshot.account_id or (
                prior_plan.created_at > as_of
            ):
                return self._failed(
                    RebalanceFailureCode.PRIOR_PLAN_MISMATCH,
                    (prior_plan.plan_id,),
                    evidence + (prior_plan.plan_hash,),
                )
            if (
                target_validity.is_active_at(as_of)
                and prior_plan.is_valid_at(as_of)
                and self._same_basis(prior_plan, basis)
            ):
                return RebalanceOutcome.succeeded(
                    RebalanceDecision.create(prior_plan)
                )

        maps = self._quantity_maps(target, portfolio_snapshot, ordered_streams)
        if isinstance(maps, RebalanceOutcome):
            return maps
        target_units, current_units, streams_by_instrument, scales = maps
        normalized_by_instrument = {
            value.instrument_id: value for value in target.targets
        }

        planned: list[PlannedOrder] = []
        cancels: list[CancelIntent] = []
        omissions: list[PlanningOmission] = []
        active_target = target_validity.is_active_at(as_of)
        instruments = tuple(
            sorted(
                set(target_units) | set(current_units) | set(streams_by_instrument)
            )
        )
        for instrument_id in instruments:
            scale = scales[instrument_id]
            current = _quantity(
                instrument_id, scale, current_units.get(instrument_id, 0)
            )
            desired = _quantity(
                instrument_id, scale, target_units.get(instrument_id, 0)
            )
            instrument_streams = streams_by_instrument.get(instrument_id, ())

            if not active_target:
                for stream in instrument_streams:
                    if stream.state is not None and (
                        stream.state.status is not OrderStatus.CANCEL_REQUESTED
                    ):
                        cancels.append(
                            self._cancel(
                                stream,
                                instrument_id,
                                target.normalized_target_id,
                                "target_expired",
                            )
                        )
                omissions.append(
                    PlanningOmission(
                        instrument_id,
                        PlanningOmissionCode.TARGET_EXPIRED,
                        current,
                        desired,
                        _quantity(instrument_id, scale, 0),
                    )
                )
                continue

            if any(
                stream.state is not None
                and stream.state.status is OrderStatus.CANCEL_REQUESTED
                for stream in instrument_streams
            ):
                coverage_units = self._signed_coverage(instrument_streams)
                omissions.append(
                    PlanningOmission(
                        instrument_id,
                        PlanningOmissionCode.CANCELLATION_PENDING,
                        current,
                        desired,
                        _quantity(instrument_id, scale, coverage_units),
                    )
                )
                continue

            normalized = normalized_by_instrument.get(instrument_id)
            if (
                normalized is not None
                and normalized.sizing_input.lattice.whole_sell_residual_permitted
                and normalized.sizing_input.current_quantity.units >= 0
                and normalized.decision.raw_quantity.units >= 0
                and current != normalized.sizing_input.current_quantity
                and current != desired
            ):
                lineage_streams = tuple(
                    value
                    for value in instrument_streams
                    if value.order.intent.parent_id
                    == target.normalized_target_id
                )
                lineage_coverage = self._signed_coverage(lineage_streams)
                if lineage_coverage != desired.units - current.units:
                    omissions.append(
                        PlanningOmission(
                            instrument_id,
                            PlanningOmissionCode.POSITION_RELATIVE_REACHABILITY_STALE,
                            current,
                            desired,
                            _quantity(
                                instrument_id,
                                scale,
                                lineage_coverage,
                            ),
                        )
                    )
                    continue

            full_delta = desired.units - current.units
            if current.units and desired.units and (
                (current.units > 0) != (desired.units > 0)
            ):
                stage_delta = -current.units
            else:
                stage_delta = full_delta

            retained_units = 0
            conflicts: list[OrderEventStream] = []
            for stream in instrument_streams:
                signed = self._signed_remaining(stream)
                candidate = retained_units + signed
                compatible = stage_delta != 0 and (
                    (signed > 0) == (stage_delta > 0)
                ) and abs(candidate) <= abs(stage_delta)
                if compatible:
                    retained_units = candidate
                else:
                    conflicts.append(stream)

            if conflicts:
                for stream in conflicts:
                    cancels.append(
                        self._cancel(
                            stream,
                            instrument_id,
                            target.normalized_target_id,
                            "working_order_conflicts_with_target",
                        )
                    )
                omissions.append(
                    PlanningOmission(
                        instrument_id,
                        PlanningOmissionCode.CANCELLATION_PENDING,
                        current,
                        desired,
                        _quantity(instrument_id, scale, retained_units),
                    )
                )
                continue

            delta_units = stage_delta - retained_units
            coverage = _quantity(instrument_id, scale, retained_units)
            if delta_units == 0:
                omissions.append(
                    PlanningOmission(
                        instrument_id,
                        PlanningOmissionCode.ALREADY_COVERED,
                        current,
                        desired,
                        coverage,
                    )
                )
                continue
            planned.append(
                self._planned_order(
                    target,
                    policy,
                    instrument_id,
                    current,
                    desired,
                    coverage,
                    _quantity(instrument_id, scale, delta_units),
                )
            )

        valid_until = None
        if policy.plan_valid_for_nanoseconds is not None:
            valid_until = UtcInstant(
                as_of.epoch_nanoseconds + policy.plan_valid_for_nanoseconds
            )
        plan = OrderPlan.create(
            account_id=portfolio_snapshot.account_id,
            created_at=as_of,
            based_on_normalized_target_id=target.normalized_target_id,
            based_on_normalized_target_hash=basis.target_hash,
            based_on_target_validity_hash=basis.validity_hash,
            based_on_portfolio_snapshot_hash=basis.snapshot_hash,
            based_on_working_order_set_hash=basis.working_hash,
            based_on_reservation_state_hash=basis.reservation_hash,
            based_on_availability_state_hash=basis.availability_hash,
            policy=policy,
            valid_until=valid_until,
            planned_orders=tuple(planned),
            cancel_intents=tuple(cancels),
            omissions=tuple(omissions),
            supersedes_plan_id=prior_plan.plan_id if prior_plan is not None else None,
        )
        return RebalanceOutcome.succeeded(RebalanceDecision.create(plan))

    @staticmethod
    def _base_evidence(
        target: NormalizedPortfolioTarget,
        validity: TargetValidity,
        snapshot: PortfolioSnapshot,
        reservations: ResourceReservationState,
        availability: AvailabilityState,
    ) -> tuple[str, ...]:
        return (
            canonical_sha256(target),
            canonical_sha256(validity),
            canonical_sha256(snapshot),
            canonical_sha256(reservations),
            canonical_sha256(availability),
        )

    def _validate_context(
        self,
        target: NormalizedPortfolioTarget,
        validity: TargetValidity,
        snapshot: PortfolioSnapshot,
        reservations: ResourceReservationState,
        availability: AvailabilityState,
        as_of: UtcInstant,
        policy: RebalancePolicy,
        evidence: tuple[str, ...],
    ) -> RebalanceOutcome | None:
        if validity.normalized_target_id != target.normalized_target_id or (
            validity.normalized_target_hash != target.normalized_target_hash
        ) or validity.valid_from != target.materialized_at:
            return self._failed(
                RebalanceFailureCode.TARGET_VALIDITY_MISMATCH,
                (target.normalized_target_id,),
                evidence + (policy.policy_hash,),
            )
        if target.materialized_at > as_of or snapshot.timestamp > as_of:
            return self._failed(
                RebalanceFailureCode.CONTEXT_MISMATCH,
                ("future_target_or_snapshot",),
                evidence + (policy.policy_hash,),
            )
        if reservations.account_id != snapshot.account_id or (
            availability.account_id != snapshot.account_id
        ):
            return self._failed(
                RebalanceFailureCode.CONTEXT_MISMATCH,
                (snapshot.account_id, reservations.account_id, availability.account_id),
                evidence + (policy.policy_hash,),
            )
        if availability.reservation_state_hash != reservations.state_hash or (
            availability.ledger_state_hash != snapshot.journal_state_hash
        ):
            return self._failed(
                RebalanceFailureCode.CONTEXT_MISMATCH,
                ("availability_evidence_hash",),
                evidence + (policy.policy_hash,),
            )
        return None

    def _validate_reservation_context(
        self,
        streams: tuple[OrderEventStream, ...],
        reservations: ResourceReservationState,
        evidence: tuple[str, ...],
    ) -> RebalanceOutcome | None:
        streams_by_id = {stream.order.order_id: stream for stream in streams}
        active_by_id = {
            reservation.order_id: reservation
            for reservation in reservations.active_reservations
        }
        for stream in streams:
            if stream.state is not None and stream.state.status in {
                OrderStatus.ACTIVE,
                OrderStatus.PARTIALLY_FILLED,
            } and stream.order.order_id not in active_by_id:
                return self._failed(
                    RebalanceFailureCode.CONTEXT_MISMATCH,
                    (stream.order.order_id.value, "working_order_without_reservation"),
                    evidence + (reservations.state_hash, stream.stream_hash),
                )
        for active in reservations.active_reservations:
            matched_stream = streams_by_id.get(active.order_id)
            if matched_stream is None or matched_stream.state is None:
                return self._failed(
                    RebalanceFailureCode.CONTEXT_MISMATCH,
                    (active.order_id.value, "reservation_without_working_order"),
                    evidence + (reservations.state_hash,),
                )
            if active.remaining_quantity != matched_stream.state.remaining_quantity:
                return self._failed(
                    RebalanceFailureCode.CONTEXT_MISMATCH,
                    (active.order_id.value, "reservation_remaining_quantity"),
                    evidence
                    + (reservations.state_hash, matched_stream.stream_hash),
                )
        cursor_by_id = {cursor.order_id: cursor for cursor in reservations.cursors}
        for active in reservations.active_reservations:
            stream = streams_by_id[active.order_id]
            cursor = cursor_by_id.get(active.order_id)
            if cursor is None or cursor.stream_hash != stream.stream_hash or (
                cursor.event_count != stream.event_count
            ):
                return self._failed(
                    RebalanceFailureCode.CONTEXT_MISMATCH,
                    (active.order_id.value, "reservation_cursor"),
                    evidence + (reservations.state_hash, stream.stream_hash),
                )
        return None

    def _quantity_maps(
        self,
        target: NormalizedPortfolioTarget,
        snapshot: PortfolioSnapshot,
        streams: tuple[OrderEventStream, ...],
    ) -> tuple[
        dict[InstrumentId, int],
        dict[InstrumentId, int],
        dict[InstrumentId, tuple[OrderEventStream, ...]],
        dict[InstrumentId, Scale],
    ] | RebalanceOutcome:
        target_values = {
            instrument_id: quantity.units
            for instrument_id, quantity in target.active_target.quantities
        }
        current_values = {
            value.key.instrument_id: value.quantity.units for value in snapshot.positions
        }
        scales: dict[InstrumentId, Scale] = {
            instrument_id: quantity.scale
            for instrument_id, quantity in target.active_target.quantities
        }
        for value in snapshot.positions:
            known = scales.get(value.key.instrument_id)
            if known is not None and known != value.quantity.scale:
                return self._failed(
                    RebalanceFailureCode.QUANTITY_SCALE_MISMATCH,
                    (str(value.key.instrument_id),),
                    (target.normalized_target_hash, canonical_sha256(snapshot)),
                )
            scales[value.key.instrument_id] = value.quantity.scale

        grouped: defaultdict[InstrumentId, list[OrderEventStream]] = defaultdict(list)
        for stream in streams:
            instrument_id = stream.order.intent.instrument_id
            state = stream.state
            if state is None:
                raise AssertionError("validated Working Order is missing state")
            known = scales.get(instrument_id)
            if known is not None and known != state.remaining_quantity.scale:
                return self._failed(
                    RebalanceFailureCode.QUANTITY_SCALE_MISMATCH,
                    (str(instrument_id), stream.order.order_id.value),
                    (target.normalized_target_hash, stream.stream_hash),
                )
            scales[instrument_id] = state.remaining_quantity.scale
            grouped[instrument_id].append(stream)
        grouped_tuple = {
            instrument_id: tuple(
                sorted(values, key=lambda value: value.order.order_id.value)
            )
            for instrument_id, values in grouped.items()
        }
        return target_values, current_values, grouped_tuple, scales

    @staticmethod
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

    @staticmethod
    def _same_basis(plan: OrderPlan, basis: _Basis) -> bool:
        return (
            plan.based_on_normalized_target_hash == basis.target_hash
            and plan.based_on_target_validity_hash == basis.validity_hash
            and plan.based_on_portfolio_snapshot_hash == basis.snapshot_hash
            and plan.based_on_working_order_set_hash == basis.working_hash
            and plan.based_on_reservation_state_hash == basis.reservation_hash
            and plan.based_on_availability_state_hash == basis.availability_hash
            and plan.policy.policy_hash == basis.policy_hash
        )

    @staticmethod
    def _signed_remaining(stream: OrderEventStream) -> int:
        state = stream.state
        if state is None:
            raise AssertionError("Working Order is missing state")
        units = state.remaining_quantity.units
        return units if stream.order.intent.side is OrderSide.BUY else -units

    def _signed_coverage(self, streams: tuple[OrderEventStream, ...]) -> int:
        return sum(self._signed_remaining(stream) for stream in streams)

    @staticmethod
    def _cancel(
        stream: OrderEventStream,
        instrument_id: InstrumentId,
        normalized_target_id: str,
        reason_code: str,
    ) -> CancelIntent:
        payload = {
            "type": "cancel_intent_identity",
            "schema_version": 1,
            "order_id": stream.order.order_id,
            "stream_hash": stream.stream_hash,
            "instrument_id": instrument_id,
            "reason_code": reason_code,
            "normalized_target_id": normalized_target_id,
        }
        return CancelIntent(
            cancel_intent_id=f"cancel-intent-v1:{canonical_sha256(payload)}",
            order_id=stream.order.order_id,
            instrument_id=instrument_id,
            reason_code=reason_code,
            normalized_target_id=normalized_target_id,
        )

    @staticmethod
    def _planned_order(
        target: NormalizedPortfolioTarget,
        policy: RebalancePolicy,
        instrument_id: InstrumentId,
        current: Quantity,
        desired: Quantity,
        coverage: Quantity,
        delta: Quantity,
    ) -> PlannedOrder:
        closing = current.units != 0 and delta.units * current.units < 0
        intent = OrderIntent(
            instrument_id=instrument_id,
            side=OrderSide.BUY if delta.units > 0 else OrderSide.SELL,
            quantity=_quantity(instrument_id, delta.scale, abs(delta.units)),
            execution_style=policy.execution_style,
            price_constraint=None,
            time_in_force=policy.time_in_force,
            reduce_only=closing,
            position_effect=(PositionEffect.CLOSE if closing else PositionEffect.OPEN),
            urgency=policy.urgency,
            reason=f"rebalance:{policy.policy_key}",
            parent_id=target.normalized_target_id,
        )
        payload = {
            "type": "planned_order_identity",
            "schema_version": 1,
            "normalized_target_id": target.normalized_target_id,
            "normalized_target_hash": target.normalized_target_hash,
            "policy_hash": policy.policy_hash,
            "instrument_id": instrument_id,
            "intent": intent,
            "current_quantity": current,
            "target_quantity": desired,
            "retained_working_coverage": coverage,
            "planned_delta": delta,
        }
        return PlannedOrder(
            planned_order_id=f"planned-order-v1:{canonical_sha256(payload)}",
            instrument_id=instrument_id,
            intent=intent,
            current_quantity=current,
            target_quantity=desired,
            retained_working_coverage=coverage,
            planned_delta=delta,
            policy_hash=policy.policy_hash,
        )

    @staticmethod
    def _failed(
        code: RebalanceFailureCode,
        subjects: tuple[str, ...],
        evidence: tuple[str, ...],
    ) -> RebalanceOutcome:
        return RebalanceOutcome.failed(RebalanceFailure(code, subjects, evidence))


__all__ = [
    "CancelIntent",
    "OrderPlan",
    "PlannedOrder",
    "PlanningOmission",
    "PlanningOmissionCode",
    "RebalanceCoordinator",
    "RebalanceDecision",
    "RebalanceFailure",
    "RebalanceFailureCode",
    "RebalanceOutcome",
    "RebalancePolicy",
    "TargetValidity",
]
