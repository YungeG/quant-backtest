"""Exact order-level risk decisions over supplied account-resource evidence."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Money,
    Order,
    OrderSide,
    PositionEffect,
    Quantity,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

from .fee_reservations import ResourceReservationProposal
from .market_rules import MarketRuleApproval
from .reservations import ReservationCommitment, ResourceReservationState
from .settlement import AvailabilityState, CashAvailability, PositionAvailability


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


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


def _nonnegative_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _tagged_id(prefix: str, payload: object) -> str:
    return f"{prefix}:{canonical_sha256(payload)}"


class FeeReserveFundingSource(str, Enum):
    TRADABLE_CASH = "tradable_cash"
    AVAILABLE_MARGIN = "available_margin"


@dataclass(frozen=True, slots=True)
class ExposureCapacityLimit:
    maximum: Money

    def __post_init__(self) -> None:
        if not isinstance(self.maximum, Money):
            raise TypeError("maximum must be Money")
        if self.maximum.units < 0:
            raise ValueError("exposure maximum must be nonnegative")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "exposure_capacity_limit",
            "maximum": self.maximum,
        }


def _exposure_limit_key(value: ExposureCapacityLimit) -> tuple[str, int]:
    return value.maximum.currency, value.maximum.scale.places


def _policy_config(
    *,
    account_id: str,
    venue_id: VenueId,
    allowed_sides: tuple[OrderSide, ...],
    allowed_position_effects: tuple[PositionEffect, ...],
    allowed_reduce_only_values: tuple[bool, ...],
    fee_reserve_funding_source: FeeReserveFundingSource,
    order_capacity_limit: int,
    exposure_capacity_limits: tuple[ExposureCapacityLimit, ...],
) -> dict[str, Any]:
    return {
        "type": "account_risk_policy_config",
        "schema_version": 1,
        "account_id": account_id,
        "venue_id": venue_id,
        "allowed_sides": tuple(value.value for value in allowed_sides),
        "allowed_position_effects": tuple(
            value.value for value in allowed_position_effects
        ),
        "allowed_reduce_only_values": allowed_reduce_only_values,
        "fee_reserve_funding_source": fee_reserve_funding_source.value,
        "order_capacity_limit": order_capacity_limit,
        "exposure_capacity_limits": exposure_capacity_limits,
    }


@dataclass(frozen=True, slots=True)
class AccountRiskPolicy:
    policy_key: str
    policy_version: int
    config_hash: str
    account_id: str
    venue_id: VenueId
    allowed_sides: tuple[OrderSide, ...]
    allowed_position_effects: tuple[PositionEffect, ...]
    allowed_reduce_only_values: tuple[bool, ...]
    fee_reserve_funding_source: FeeReserveFundingSource
    order_capacity_limit: int
    exposure_capacity_limits: tuple[ExposureCapacityLimit, ...]

    def __post_init__(self) -> None:
        _canonical_text("policy_key", self.policy_key)
        _positive_integer("policy_version", self.policy_version)
        _require_hash("config_hash", self.config_hash)
        _canonical_text("account_id", self.account_id)
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.allowed_sides, tuple) or not all(
            isinstance(value, OrderSide) for value in self.allowed_sides
        ):
            raise TypeError("allowed_sides must contain OrderSide")
        if not isinstance(self.allowed_position_effects, tuple) or not all(
            isinstance(value, PositionEffect)
            for value in self.allowed_position_effects
        ):
            raise TypeError(
                "allowed_position_effects must contain PositionEffect"
            )
        if not isinstance(self.allowed_reduce_only_values, tuple) or not all(
            type(value) is bool for value in self.allowed_reduce_only_values
        ):
            raise TypeError("allowed_reduce_only_values must contain bool")
        if not isinstance(
            self.fee_reserve_funding_source, FeeReserveFundingSource
        ):
            raise TypeError(
                "fee_reserve_funding_source must be FeeReserveFundingSource"
            )
        _nonnegative_integer("order_capacity_limit", self.order_capacity_limit)
        if not isinstance(self.exposure_capacity_limits, tuple) or not all(
            isinstance(value, ExposureCapacityLimit)
            for value in self.exposure_capacity_limits
        ):
            raise TypeError(
                "exposure_capacity_limits must contain ExposureCapacityLimit"
            )

        sides = tuple(sorted(self.allowed_sides, key=lambda value: value.value))
        effects = tuple(
            sorted(self.allowed_position_effects, key=lambda value: value.value)
        )
        reduce_values = tuple(sorted(self.allowed_reduce_only_values))
        limits = tuple(
            sorted(self.exposure_capacity_limits, key=_exposure_limit_key)
        )
        if not sides:
            raise ValueError("allowed_sides must not be empty")
        if not effects:
            raise ValueError("allowed_position_effects must not be empty")
        if not reduce_values:
            raise ValueError("allowed_reduce_only_values must not be empty")
        if len(sides) != len(set(sides)):
            raise ValueError("duplicate allowed OrderSide")
        if len(effects) != len(set(effects)):
            raise ValueError("duplicate allowed PositionEffect")
        if len(reduce_values) != len(set(reduce_values)):
            raise ValueError("duplicate allowed reduce-only value")
        limit_keys = tuple(_exposure_limit_key(value) for value in limits)
        if len(limit_keys) != len(set(limit_keys)):
            raise ValueError("duplicate exposure capacity Currency/Scale")

        expected = canonical_sha256(
            _policy_config(
                account_id=self.account_id,
                venue_id=self.venue_id,
                allowed_sides=sides,
                allowed_position_effects=effects,
                allowed_reduce_only_values=reduce_values,
                fee_reserve_funding_source=self.fee_reserve_funding_source,
                order_capacity_limit=self.order_capacity_limit,
                exposure_capacity_limits=limits,
            )
        )
        if self.config_hash != expected:
            raise ValueError("config_hash mismatch")
        object.__setattr__(self, "allowed_sides", sides)
        object.__setattr__(self, "allowed_position_effects", effects)
        object.__setattr__(self, "allowed_reduce_only_values", reduce_values)
        object.__setattr__(self, "exposure_capacity_limits", limits)

    @classmethod
    def create(
        cls,
        *,
        policy_key: str,
        policy_version: int,
        account_id: str,
        venue_id: VenueId,
        allowed_sides: tuple[OrderSide, ...],
        allowed_position_effects: tuple[PositionEffect, ...],
        allowed_reduce_only_values: tuple[bool, ...],
        fee_reserve_funding_source: FeeReserveFundingSource,
        order_capacity_limit: int,
        exposure_capacity_limits: tuple[ExposureCapacityLimit, ...],
    ) -> Self:
        sides = tuple(sorted(allowed_sides, key=lambda value: value.value))
        effects = tuple(
            sorted(allowed_position_effects, key=lambda value: value.value)
        )
        reduce_values = tuple(sorted(allowed_reduce_only_values))
        limits = tuple(sorted(exposure_capacity_limits, key=_exposure_limit_key))
        return cls(
            policy_key=policy_key,
            policy_version=policy_version,
            config_hash=canonical_sha256(
                _policy_config(
                    account_id=account_id,
                    venue_id=venue_id,
                    allowed_sides=sides,
                    allowed_position_effects=effects,
                    allowed_reduce_only_values=reduce_values,
                    fee_reserve_funding_source=fee_reserve_funding_source,
                    order_capacity_limit=order_capacity_limit,
                    exposure_capacity_limits=limits,
                )
            ),
            account_id=account_id,
            venue_id=venue_id,
            allowed_sides=sides,
            allowed_position_effects=effects,
            allowed_reduce_only_values=reduce_values,
            fee_reserve_funding_source=fee_reserve_funding_source,
            order_capacity_limit=order_capacity_limit,
            exposure_capacity_limits=limits,
        )

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "account_risk_policy",
            "schema_version": 1,
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "config_hash": self.config_hash,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "allowed_sides": tuple(value.value for value in self.allowed_sides),
            "allowed_position_effects": tuple(
                value.value for value in self.allowed_position_effects
            ),
            "allowed_reduce_only_values": self.allowed_reduce_only_values,
            "fee_reserve_funding_source": self.fee_reserve_funding_source.value,
            "order_capacity_limit": self.order_capacity_limit,
            "exposure_capacity_limits": self.exposure_capacity_limits,
        }


@dataclass(frozen=True, slots=True)
class PreTradeResourceRequirement:
    requirement_id: str
    requirement_source_key: str
    requirement_source_version: int
    requirement_source_hash: str
    order_id: DomainId
    market_rule_decision_id: str
    market_rule_approval_hash: str
    fee_reservation_proposal_id: str
    fee_reservation_proposal_hash: str
    commitment: ReservationCommitment

    def __post_init__(self) -> None:
        _canonical_text("requirement_source_key", self.requirement_source_key)
        _positive_integer(
            "requirement_source_version", self.requirement_source_version
        )
        _require_hash("requirement_source_hash", self.requirement_source_hash)
        if not isinstance(self.order_id, DomainId) or (
            self.order_id.kind is not DomainIdKind.ORDER
        ):
            raise TypeError("order_id must be ORDER DomainId")
        _canonical_text("market_rule_decision_id", self.market_rule_decision_id)
        _require_hash("market_rule_approval_hash", self.market_rule_approval_hash)
        _canonical_text(
            "fee_reservation_proposal_id", self.fee_reservation_proposal_id
        )
        _require_hash(
            "fee_reservation_proposal_hash", self.fee_reservation_proposal_hash
        )
        if not isinstance(self.commitment, ReservationCommitment):
            raise TypeError("commitment must be ReservationCommitment")
        if self.commitment.order_capacity_units <= 0:
            raise ValueError("resource requirement must reserve order capacity")
        expected = _tagged_id("pretrade-requirement-v1", self._identity_payload())
        if self.requirement_id != expected:
            raise ValueError("requirement_id mismatch")

    @classmethod
    def create(
        cls,
        *,
        requirement_source_key: str,
        requirement_source_version: int,
        requirement_source_hash: str,
        market_rule_approval: MarketRuleApproval,
        fee_reservation_proposal: ResourceReservationProposal,
        commitment: ReservationCommitment,
    ) -> Self:
        if not isinstance(market_rule_approval, MarketRuleApproval):
            raise TypeError("market_rule_approval must be MarketRuleApproval")
        if not isinstance(
            fee_reservation_proposal, ResourceReservationProposal
        ):
            raise TypeError(
                "fee_reservation_proposal must be ResourceReservationProposal"
            )
        order = _source_order(market_rule_approval)
        values = {
            "requirement_source_key": requirement_source_key,
            "requirement_source_version": requirement_source_version,
            "requirement_source_hash": requirement_source_hash,
            "order_id": order.order_id,
            "market_rule_decision_id": market_rule_approval.decision_id,
            "market_rule_approval_hash": canonical_sha256(market_rule_approval),
            "fee_reservation_proposal_id": fee_reservation_proposal.proposal_id,
            "fee_reservation_proposal_hash": (
                fee_reservation_proposal.proposal_hash
            ),
            "commitment": commitment,
        }
        return cls(
            requirement_id=_tagged_id("pretrade-requirement-v1", values),
            requirement_source_key=requirement_source_key,
            requirement_source_version=requirement_source_version,
            requirement_source_hash=requirement_source_hash,
            order_id=order.order_id,
            market_rule_decision_id=market_rule_approval.decision_id,
            market_rule_approval_hash=canonical_sha256(market_rule_approval),
            fee_reservation_proposal_id=fee_reservation_proposal.proposal_id,
            fee_reservation_proposal_hash=fee_reservation_proposal.proposal_hash,
            commitment=commitment,
        )

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "requirement_source_key": self.requirement_source_key,
            "requirement_source_version": self.requirement_source_version,
            "requirement_source_hash": self.requirement_source_hash,
            "order_id": self.order_id,
            "market_rule_decision_id": self.market_rule_decision_id,
            "market_rule_approval_hash": self.market_rule_approval_hash,
            "fee_reservation_proposal_id": self.fee_reservation_proposal_id,
            "fee_reservation_proposal_hash": self.fee_reservation_proposal_hash,
            "commitment": self.commitment,
        }

    @property
    def requirement_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "pretrade_resource_requirement",
            "schema_version": 1,
            "requirement_id": self.requirement_id,
            **self._identity_payload(),
        }


@dataclass(frozen=True, slots=True)
class PreTradeRiskEvaluationInput:
    market_rule_approval: MarketRuleApproval
    fee_reservation_proposal: ResourceReservationProposal
    resource_requirement: PreTradeResourceRequirement
    reservation_state: ResourceReservationState
    availability_state: AvailabilityState
    account_risk_policy: AccountRiskPolicy
    evaluated_at: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.market_rule_approval, MarketRuleApproval):
            raise TypeError("market_rule_approval must be MarketRuleApproval")
        if not isinstance(
            self.fee_reservation_proposal, ResourceReservationProposal
        ):
            raise TypeError(
                "fee_reservation_proposal must be ResourceReservationProposal"
            )
        if not isinstance(self.resource_requirement, PreTradeResourceRequirement):
            raise TypeError(
                "resource_requirement must be PreTradeResourceRequirement"
            )
        if not isinstance(self.reservation_state, ResourceReservationState):
            raise TypeError("reservation_state must be ResourceReservationState")
        if not isinstance(self.availability_state, AvailabilityState):
            raise TypeError("availability_state must be AvailabilityState")
        if not isinstance(self.account_risk_policy, AccountRiskPolicy):
            raise TypeError("account_risk_policy must be AccountRiskPolicy")
        if not isinstance(self.evaluated_at, UtcInstant):
            raise TypeError("evaluated_at must be UtcInstant")

    @property
    def input_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "pretrade_risk_evaluation_input",
            "schema_version": 1,
            "market_rule_approval": self.market_rule_approval,
            "fee_reservation_proposal": self.fee_reservation_proposal,
            "resource_requirement": self.resource_requirement,
            "reservation_state": self.reservation_state,
            "availability_state": self.availability_state,
            "account_risk_policy": self.account_risk_policy,
            "evaluated_at": self.evaluated_at,
        }


class PreTradeRiskReasonCode(str, Enum):
    ACCOUNT_PERMISSION = "account_permission"
    TRADABLE_CASH = "tradable_cash"
    SELLABLE_QUANTITY = "sellable_quantity"
    AVAILABLE_MARGIN = "available_margin"
    ORDER_CAPACITY = "order_capacity"
    EXPOSURE_CAPACITY = "exposure_capacity"


@dataclass(frozen=True, slots=True)
class PreTradeRiskCheck:
    reason_code: PreTradeRiskReasonCode
    subject_key: str
    required_units: int
    available_units: int
    scale: Scale | None
    approved: bool

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, PreTradeRiskReasonCode):
            raise TypeError("reason_code must be PreTradeRiskReasonCode")
        _canonical_text("subject_key", self.subject_key)
        _nonnegative_integer("required_units", self.required_units)
        if isinstance(self.available_units, bool) or not isinstance(
            self.available_units, int
        ):
            raise TypeError("available_units must be an integer")
        if self.scale is not None and not isinstance(self.scale, Scale):
            raise TypeError("scale must be Scale or None")
        if type(self.approved) is not bool:
            raise TypeError("approved must be bool")
        if self.approved != (self.available_units >= self.required_units):
            raise ValueError("approved must match exact required/available comparison")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "pretrade_risk_check",
            "reason_code": self.reason_code.value,
            "subject_key": self.subject_key,
            "required_units": self.required_units,
            "available_units": self.available_units,
            "scale": None if self.scale is None else self.scale.places,
            "approved": self.approved,
        }


def _check_key(value: PreTradeRiskCheck) -> tuple[str, str]:
    return value.reason_code.value, value.subject_key


def _decision_payload(
    outcome: str,
    evaluation_input: PreTradeRiskEvaluationInput,
    checks: tuple[PreTradeRiskCheck, ...],
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "evaluation_input_hash": evaluation_input.input_hash,
        "checks": checks,
    }


def _validate_decision_identity(
    *,
    decision_id: str,
    evaluation_input: PreTradeRiskEvaluationInput,
    checks: tuple[PreTradeRiskCheck, ...],
    outcome: str,
    approved: bool,
) -> None:
    _validate_decision_common(evaluation_input, checks)
    issues = _source_contract_issues(
        evaluation_input,
        _source_order(evaluation_input.market_rule_approval),
    )
    context = _resource_context(evaluation_input, issues)
    if issues:
        raise ValueError("PreTrade Risk decision cannot contain contract-invalid input")
    if checks != _economic_checks(evaluation_input, context):
        raise ValueError("PreTrade Risk checks do not match supplied evidence")
    if all(check.approved for check in checks) != approved:
        raise ValueError(f"{outcome} economic-check result mismatch")
    expected = _tagged_id(
        "pretrade-risk-decision-v1",
        _decision_payload(outcome, evaluation_input, checks),
    )
    if decision_id != expected:
        raise ValueError("decision_id mismatch")


def _decision_dict(
    *,
    type_name: str,
    decision_id: str,
    evaluation_input: PreTradeRiskEvaluationInput,
    checks: tuple[PreTradeRiskCheck, ...],
) -> dict[str, Any]:
    return {
        "type": type_name,
        "schema_version": 1,
        "decision_id": decision_id,
        "evaluation_input": evaluation_input,
        "order": _source_order(evaluation_input.market_rule_approval),
        "checks": checks,
    }


class _PreTradeRiskDecisionView:
    __slots__ = ()

    decision_id: str
    evaluation_input: PreTradeRiskEvaluationInput
    checks: tuple[PreTradeRiskCheck, ...]

    @property
    def order(self) -> Order:
        return _source_order(self.evaluation_input.market_rule_approval)

    @property
    def decision_hash(self) -> str:
        return canonical_sha256(self)

    def _canonical_decision(self, type_name: str) -> dict[str, Any]:
        return _decision_dict(
            type_name=type_name,
            decision_id=self.decision_id,
            evaluation_input=self.evaluation_input,
            checks=self.checks,
        )


@dataclass(frozen=True, slots=True)
class PreTradeRiskApproval(_PreTradeRiskDecisionView):
    decision_id: str
    evaluation_input: PreTradeRiskEvaluationInput
    checks: tuple[PreTradeRiskCheck, ...]

    def __post_init__(self) -> None:
        _validate_decision_identity(
            decision_id=self.decision_id,
            evaluation_input=self.evaluation_input,
            checks=self.checks,
            outcome="approved",
            approved=True,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return self._canonical_decision("pretrade_risk_approval")


@dataclass(frozen=True, slots=True)
class PreTradeRiskRejection(_PreTradeRiskDecisionView):
    decision_id: str
    evaluation_input: PreTradeRiskEvaluationInput
    checks: tuple[PreTradeRiskCheck, ...]

    def __post_init__(self) -> None:
        _validate_decision_identity(
            decision_id=self.decision_id,
            evaluation_input=self.evaluation_input,
            checks=self.checks,
            outcome="rejected",
            approved=False,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return self._canonical_decision("pretrade_risk_rejection")


def _validate_decision_common(
    evaluation_input: PreTradeRiskEvaluationInput,
    checks: tuple[PreTradeRiskCheck, ...],
) -> None:
    if not isinstance(evaluation_input, PreTradeRiskEvaluationInput):
        raise TypeError("evaluation_input must be PreTradeRiskEvaluationInput")
    if not isinstance(checks, tuple) or not all(
        isinstance(check, PreTradeRiskCheck) for check in checks
    ):
        raise TypeError("checks must contain PreTradeRiskCheck")
    if not checks:
        raise ValueError("PreTrade Risk decision requires checks")
    ordered = tuple(sorted(checks, key=_check_key))
    if checks != ordered:
        raise ValueError("checks must use canonical order")
    keys = tuple(_check_key(check) for check in checks)
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate PreTrade Risk check")


class PreTradeRiskContractIssueCode(str, Enum):
    EVALUATION_BEFORE_FEE_ESTIMATION = "evaluation_before_fee_estimation"
    ORDER_CONTEXT_MISMATCH = "order_context_mismatch"
    SOURCE_EVIDENCE_MISMATCH = "source_evidence_mismatch"
    ACCOUNT_CONTEXT_MISMATCH = "account_context_mismatch"
    RESERVATION_STATE_MISMATCH = "reservation_state_mismatch"
    FEE_RESERVE_MISMATCH = "fee_reserve_mismatch"
    MISSING_CASH_AVAILABILITY = "missing_cash_availability"
    MISSING_POSITION_AVAILABILITY = "missing_position_availability"
    RESOURCE_CONTEXT_MISMATCH = "resource_context_mismatch"
    MISSING_EXPOSURE_LIMIT = "missing_exposure_limit"


@dataclass(frozen=True, slots=True)
class PreTradeRiskContractIssue:
    code: PreTradeRiskContractIssueCode
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, PreTradeRiskContractIssueCode):
            raise TypeError("code must be PreTradeRiskContractIssueCode")
        _canonical_text("subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "pretrade_risk_contract_issue",
            "code": self.code.value,
            "subject_key": self.subject_key,
        }


def _issue_key(
    issue: PreTradeRiskContractIssue,
) -> tuple[str, str]:
    return issue.code.value, issue.subject_key


@dataclass(frozen=True, slots=True)
class PreTradeRiskContractFailure:
    failure_id: str
    evaluation_input: PreTradeRiskEvaluationInput
    issues: tuple[PreTradeRiskContractIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_input, PreTradeRiskEvaluationInput):
            raise TypeError("evaluation_input must be PreTradeRiskEvaluationInput")
        if not isinstance(self.issues, tuple) or not all(
            isinstance(issue, PreTradeRiskContractIssue) for issue in self.issues
        ):
            raise TypeError("issues must contain PreTradeRiskContractIssue")
        ordered = tuple(sorted(self.issues, key=_issue_key))
        if not ordered:
            raise ValueError("contract failure requires issues")
        if self.issues != ordered:
            raise ValueError("contract issues must use canonical order")
        keys = tuple(_issue_key(issue) for issue in ordered)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate PreTrade Risk contract issue")
        expected_issues = _source_contract_issues(
            self.evaluation_input,
            _source_order(self.evaluation_input.market_rule_approval),
        )
        _resource_context(self.evaluation_input, expected_issues)
        if self.issues != tuple(sorted(set(expected_issues), key=_issue_key)):
            raise ValueError("contract issues do not match supplied evidence")
        expected = _tagged_id(
            "pretrade-risk-contract-failure-v1",
            {
                "evaluation_input_hash": self.evaluation_input.input_hash,
                "issues": self.issues,
            },
        )
        if self.failure_id != expected:
            raise ValueError("failure_id mismatch")

    @property
    def codes(self) -> tuple[PreTradeRiskContractIssueCode, ...]:
        return tuple(issue.code for issue in self.issues)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "pretrade_risk_contract_failure",
            "schema_version": 1,
            "failure_id": self.failure_id,
            "evaluation_input": self.evaluation_input,
            "issues": self.issues,
        }


@dataclass(frozen=True, slots=True)
class PreTradeRiskOutcome:
    approval: PreTradeRiskApproval | None = None
    rejection: PreTradeRiskRejection | None = None
    contract_failure: PreTradeRiskContractFailure | None = None

    def __post_init__(self) -> None:
        values = (self.approval, self.rejection, self.contract_failure)
        if len(tuple(filter(None, values))) != 1:
            raise ValueError("PreTrade Risk outcome requires exactly one result")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "pretrade_risk_outcome",
            "schema_version": 1,
            "approval": self.approval,
            "rejection": self.rejection,
            "contract_failure": self.contract_failure,
        }


MoneyKey = tuple[str, int]
QuantityKey = tuple[str, int]


def _source_order(approval: MarketRuleApproval) -> Order:
    return approval.evaluation_input.executable_order_spec.source_order


def _money_totals(values: tuple[Money, ...]) -> dict[MoneyKey, int]:
    totals: defaultdict[MoneyKey, int] = defaultdict(int)
    for value in values:
        totals[(value.currency, value.scale.places)] += value.units
    return dict(totals)


def _quantity_totals(values: tuple[Quantity, ...]) -> dict[QuantityKey, int]:
    totals: defaultdict[QuantityKey, int] = defaultdict(int)
    for value in values:
        totals[(value.instrument_id, value.scale.places)] += value.units
    return dict(totals)


def _contract_failure(
    source: PreTradeRiskEvaluationInput,
    issues: list[PreTradeRiskContractIssue],
) -> PreTradeRiskOutcome:
    ordered = tuple(sorted(set(issues), key=_issue_key))
    failure_id = _tagged_id(
        "pretrade-risk-contract-failure-v1",
        {"evaluation_input_hash": source.input_hash, "issues": ordered},
    )
    return PreTradeRiskOutcome(
        contract_failure=PreTradeRiskContractFailure(
            failure_id=failure_id,
            evaluation_input=source,
            issues=ordered,
        )
    )


def _cash_availability_map(
    source: PreTradeRiskEvaluationInput,
    issues: list[PreTradeRiskContractIssue],
) -> dict[MoneyKey, CashAvailability]:
    policy = source.account_risk_policy
    result: dict[MoneyKey, CashAvailability] = {}
    for value in source.availability_state.cash:
        if value.key.account_id != policy.account_id or value.key.venue_id != policy.venue_id:
            issues.append(
                PreTradeRiskContractIssue(
                    PreTradeRiskContractIssueCode.ACCOUNT_CONTEXT_MISMATCH,
                    f"cash:{value.key.currency_id}",
                )
            )
            continue
        key = (str(value.key.currency_id), value.tradable.scale.places)
        if key in result:
            issues.append(
                PreTradeRiskContractIssue(
                    PreTradeRiskContractIssueCode.RESOURCE_CONTEXT_MISMATCH,
                    f"cash:{key[0]}:{key[1]}",
                )
            )
        result[key] = value
    return result


def _position_availability_map(
    source: PreTradeRiskEvaluationInput,
    issues: list[PreTradeRiskContractIssue],
) -> dict[QuantityKey, PositionAvailability]:
    policy = source.account_risk_policy
    result: dict[QuantityKey, PositionAvailability] = {}
    for value in source.availability_state.positions:
        if value.key.account_id != policy.account_id or value.key.venue_id != policy.venue_id:
            issues.append(
                PreTradeRiskContractIssue(
                    PreTradeRiskContractIssueCode.ACCOUNT_CONTEXT_MISMATCH,
                    f"position:{value.key.instrument_id}",
                )
            )
            continue
        key = (str(value.key.instrument_id), value.sellable.scale.places)
        if key in result:
            issues.append(
                PreTradeRiskContractIssue(
                    PreTradeRiskContractIssueCode.RESOURCE_CONTEXT_MISMATCH,
                    f"position:{key[0]}:{key[1]}",
                )
            )
        result[key] = value
    return result


def _find_wrong_money_scale(
    values: dict[MoneyKey, CashAvailability], key: MoneyKey
) -> bool:
    return any(currency == key[0] and scale != key[1] for currency, scale in values)


def _find_wrong_quantity_scale(
    values: dict[QuantityKey, PositionAvailability], key: QuantityKey
) -> bool:
    return any(instrument == key[0] and scale != key[1] for instrument, scale in values)


@dataclass(frozen=True, slots=True)
class _ResolvedRiskContext:
    order: Order
    cash: dict[MoneyKey, CashAvailability]
    positions: dict[QuantityKey, PositionAvailability]
    cash_required: dict[MoneyKey, int]
    margin_required: dict[MoneyKey, int]
    quantity_required: dict[QuantityKey, int]
    exposure_required: dict[MoneyKey, int]
    current_exposure: dict[MoneyKey, int]
    exposure_limits: dict[MoneyKey, int]


def _source_contract_issues(
    source: PreTradeRiskEvaluationInput, order: Order
) -> list[PreTradeRiskContractIssue]:
    approval = source.market_rule_approval
    proposal = source.fee_reservation_proposal
    requirement = source.resource_requirement
    policy = source.account_risk_policy
    issues: list[PreTradeRiskContractIssue] = []
    if source.evaluated_at < proposal.fee_estimate.estimated_at:
        issues.append(
            PreTradeRiskContractIssue(
                PreTradeRiskContractIssueCode.EVALUATION_BEFORE_FEE_ESTIMATION,
                "evaluated_at",
            )
        )
    if proposal.fee_estimate.market_rule_approval != approval:
        issues.append(
            PreTradeRiskContractIssue(
                PreTradeRiskContractIssueCode.SOURCE_EVIDENCE_MISMATCH,
                "fee_reservation_proposal",
            )
        )
    if proposal.order_id != order.order_id:
        issues.append(
            PreTradeRiskContractIssue(
                PreTradeRiskContractIssueCode.ORDER_CONTEXT_MISMATCH,
                "fee_reservation_proposal",
            )
        )
    if (
        requirement.order_id != order.order_id
        or requirement.market_rule_decision_id != approval.decision_id
        or requirement.market_rule_approval_hash != canonical_sha256(approval)
        or requirement.fee_reservation_proposal_id != proposal.proposal_id
        or requirement.fee_reservation_proposal_hash != proposal.proposal_hash
    ):
        issues.append(
            PreTradeRiskContractIssue(
                PreTradeRiskContractIssueCode.SOURCE_EVIDENCE_MISMATCH,
                "resource_requirement",
            )
        )
    if requirement.commitment.fee_reserve != proposal.commitment.fee_reserve:
        issues.append(
            PreTradeRiskContractIssue(
                PreTradeRiskContractIssueCode.FEE_RESERVE_MISMATCH,
                "fee_reserve",
            )
        )
    if (
        order.account_id != policy.account_id
        or order.intent.instrument_id.venue != policy.venue_id
        or source.reservation_state.account_id != policy.account_id
        or source.availability_state.account_id != policy.account_id
    ):
        issues.append(
            PreTradeRiskContractIssue(
                PreTradeRiskContractIssueCode.ACCOUNT_CONTEXT_MISMATCH,
                "account_or_venue",
            )
        )
    if (
        source.availability_state.reservation_state_hash
        != source.reservation_state.state_hash
    ):
        issues.append(
            PreTradeRiskContractIssue(
                PreTradeRiskContractIssueCode.RESERVATION_STATE_MISMATCH,
                "availability_state",
            )
        )
    return issues


def _resource_context(
    source: PreTradeRiskEvaluationInput,
    issues: list[PreTradeRiskContractIssue],
) -> _ResolvedRiskContext:
    policy = source.account_risk_policy
    commitment = source.resource_requirement.commitment
    cash = _cash_availability_map(source, issues)
    positions = _position_availability_map(source, issues)
    cash_required = _money_totals(commitment.cash)
    margin_required = _money_totals(commitment.margin)
    fee_required = _money_totals(commitment.fee_reserve)
    quantity_required = _quantity_totals(commitment.sellable_quantities)
    exposure_required = _money_totals(commitment.exposure_capacity)
    current_exposure = _money_totals(
        source.reservation_state.totals.exposure_capacity
    )
    destination = (
        cash_required
        if policy.fee_reserve_funding_source is FeeReserveFundingSource.TRADABLE_CASH
        else margin_required
    )
    for key, units in fee_required.items():
        destination[key] = destination.get(key, 0) + units

    _validate_required_availability(
        cash,
        positions,
        cash_required,
        margin_required,
        quantity_required,
        issues,
    )
    exposure_limits = {
        _exposure_limit_key(value): value.maximum.units
        for value in policy.exposure_capacity_limits
    }
    _validate_exposure_limits(
        exposure_limits,
        current_exposure,
        exposure_required,
        issues,
    )
    return _ResolvedRiskContext(
        order=_source_order(source.market_rule_approval),
        cash=cash,
        positions=positions,
        cash_required=cash_required,
        margin_required=margin_required,
        quantity_required=quantity_required,
        exposure_required=exposure_required,
        current_exposure=current_exposure,
        exposure_limits=exposure_limits,
    )


def _validate_required_availability(
    cash: dict[MoneyKey, CashAvailability],
    positions: dict[QuantityKey, PositionAvailability],
    cash_required: dict[MoneyKey, int],
    margin_required: dict[MoneyKey, int],
    quantity_required: dict[QuantityKey, int],
    issues: list[PreTradeRiskContractIssue],
) -> None:
    for key in sorted(set(cash_required) | set(margin_required)):
        if key in cash:
            continue
        code = (
            PreTradeRiskContractIssueCode.RESOURCE_CONTEXT_MISMATCH
            if _find_wrong_money_scale(cash, key)
            else PreTradeRiskContractIssueCode.MISSING_CASH_AVAILABILITY
        )
        issues.append(PreTradeRiskContractIssue(code, f"cash:{key[0]}:{key[1]}"))
    for key in sorted(quantity_required):
        if key in positions:
            continue
        code = (
            PreTradeRiskContractIssueCode.RESOURCE_CONTEXT_MISMATCH
            if _find_wrong_quantity_scale(positions, key)
            else PreTradeRiskContractIssueCode.MISSING_POSITION_AVAILABILITY
        )
        issues.append(
            PreTradeRiskContractIssue(code, f"position:{key[0]}:{key[1]}")
        )


def _validate_exposure_limits(
    exposure_limits: dict[MoneyKey, int],
    current_exposure: dict[MoneyKey, int],
    exposure_required: dict[MoneyKey, int],
    issues: list[PreTradeRiskContractIssue],
) -> None:
    for key in sorted(set(current_exposure) | set(exposure_required)):
        if key in exposure_limits:
            continue
        same_currency = any(value[0] == key[0] for value in exposure_limits)
        issues.append(
            PreTradeRiskContractIssue(
                (
                    PreTradeRiskContractIssueCode.RESOURCE_CONTEXT_MISMATCH
                    if same_currency
                    else PreTradeRiskContractIssueCode.MISSING_EXPOSURE_LIMIT
                ),
                f"exposure:{key[0]}:{key[1]}",
            )
        )


def _economic_checks(
    source: PreTradeRiskEvaluationInput, context: _ResolvedRiskContext
) -> tuple[PreTradeRiskCheck, ...]:
    order = context.order
    policy = source.account_risk_policy
    commitment = source.resource_requirement.commitment
    checks = [
        _permission_check(
            "side:" + order.intent.side.value,
            order.intent.side in policy.allowed_sides,
        ),
        _permission_check(
            "position_effect:" + order.intent.position_effect.value,
            order.intent.position_effect in policy.allowed_position_effects,
        ),
        _permission_check(
            "reduce_only:" + str(order.intent.reduce_only).lower(),
            order.intent.reduce_only in policy.allowed_reduce_only_values,
        ),
    ]
    checks.extend(_cash_checks(context))
    checks.extend(_position_checks(context))
    checks.append(
        _resource_check(
            PreTradeRiskReasonCode.ORDER_CAPACITY,
            "order_capacity",
            source.reservation_state.totals.order_capacity_units
            + commitment.order_capacity_units,
            policy.order_capacity_limit,
            None,
        )
    )
    checks.extend(_exposure_checks(context))
    return tuple(sorted(checks, key=_check_key))


def _cash_checks(context: _ResolvedRiskContext) -> list[PreTradeRiskCheck]:
    checks: list[PreTradeRiskCheck] = []
    for key, required in context.cash_required.items():
        checks.append(
            _resource_check(
                PreTradeRiskReasonCode.TRADABLE_CASH,
                f"tradable_cash:{key[0]}",
                required,
                context.cash[key].tradable.units,
                Scale(key[1]),
            )
        )
    for key, required in context.margin_required.items():
        checks.append(
            _resource_check(
                PreTradeRiskReasonCode.AVAILABLE_MARGIN,
                f"available_margin:{key[0]}",
                required,
                context.cash[key].available_margin.units,
                Scale(key[1]),
            )
        )
    return checks


def _position_checks(context: _ResolvedRiskContext) -> list[PreTradeRiskCheck]:
    return [
        _resource_check(
            PreTradeRiskReasonCode.SELLABLE_QUANTITY,
            f"sellable_quantity:{key[0]}",
            required,
            context.positions[key].sellable.units,
            Scale(key[1]),
        )
        for key, required in context.quantity_required.items()
    ]


def _exposure_checks(context: _ResolvedRiskContext) -> list[PreTradeRiskCheck]:
    keys = sorted(set(context.current_exposure) | set(context.exposure_required))
    return [
        _resource_check(
            PreTradeRiskReasonCode.EXPOSURE_CAPACITY,
            f"exposure_capacity:{key[0]}",
            context.current_exposure.get(key, 0)
            + context.exposure_required.get(key, 0),
            context.exposure_limits[key],
            Scale(key[1]),
        )
        for key in keys
    ]


@dataclass(frozen=True, slots=True)
class PreTradeRiskEvaluator:
    def evaluate(self, source: PreTradeRiskEvaluationInput) -> PreTradeRiskOutcome:
        if not isinstance(source, PreTradeRiskEvaluationInput):
            raise TypeError("source must be PreTradeRiskEvaluationInput")
        order = _source_order(source.market_rule_approval)
        issues = _source_contract_issues(source, order)
        context = _resource_context(source, issues)
        if issues:
            return _contract_failure(source, issues)

        checks = _economic_checks(source, context)
        approved = all(check.approved for check in checks)
        outcome_name = "approved" if approved else "rejected"
        decision_id = _tagged_id(
            "pretrade-risk-decision-v1",
            _decision_payload(outcome_name, source, checks),
        )
        if approved:
            return PreTradeRiskOutcome(
                approval=PreTradeRiskApproval(decision_id, source, checks)
            )
        return PreTradeRiskOutcome(
            rejection=PreTradeRiskRejection(decision_id, source, checks)
        )


def _permission_check(subject_key: str, approved: bool) -> PreTradeRiskCheck:
    return PreTradeRiskCheck(
        reason_code=PreTradeRiskReasonCode.ACCOUNT_PERMISSION,
        subject_key=subject_key,
        required_units=1,
        available_units=1 if approved else 0,
        scale=None,
        approved=approved,
    )


def _resource_check(
    reason_code: PreTradeRiskReasonCode,
    subject_key: str,
    required_units: int,
    available_units: int,
    scale: Scale | None,
) -> PreTradeRiskCheck:
    return PreTradeRiskCheck(
        reason_code=reason_code,
        subject_key=subject_key,
        required_units=required_units,
        available_units=available_units,
        scale=scale,
        approved=available_units >= required_units,
    )
