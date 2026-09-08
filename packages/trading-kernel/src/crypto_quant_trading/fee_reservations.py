"""Worst-case fee reservation from explicit immutable rule evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    DomainIdKind,
    Money,
    QuantizationPolicy,
    Rate,
    Scale,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .market_rules import MarketRuleApproval
from .ports import ProfileComponentRef, ProfilePortType
from .reservations import ReservationCommitment


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SOURCE_ORDER = {
    "market_fee": 0,
    "tax": 1,
    "account_schedule": 2,
}


def _require_text(name: str, value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be text")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be non-empty trimmed text")
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be text")
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _tagged_id(prefix: str, value: object) -> str:
    return f"{prefix}:{canonical_sha256(value)}"


class FeeReservationRuleSource(Enum):
    MARKET_FEE = "market_fee"
    TAX = "tax"
    ACCOUNT_SCHEDULE = "account_schedule"


class FeeReservationBasis(Enum):
    ORDER_NOTIONAL = "order_notional"
    FLAT_PER_ORDER = "flat_per_order"
    PER_ORDER_MINIMUM = "per_order_minimum"
    UNKNOWN = "unknown"


class FeeReservationApplicability(Enum):
    APPLIES = "applies"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


def _validate_rule_identity(
    source: FeeReservationRuleSource,
    rule_id: str,
    basis: FeeReservationBasis,
    *,
    minimum_basis_allowed: bool,
) -> None:
    if not isinstance(source, FeeReservationRuleSource):
        raise TypeError("source must be FeeReservationRuleSource")
    _require_text("rule_id", rule_id)
    if not isinstance(basis, FeeReservationBasis):
        raise TypeError("basis must be FeeReservationBasis")
    if not minimum_basis_allowed and basis is FeeReservationBasis.PER_ORDER_MINIMUM:
        raise ValueError("charge rule cannot use per_order_minimum basis")


@dataclass(frozen=True, slots=True)
class AccountFeeScheduleRef:
    schedule_key: str
    schedule_version: int
    schedule_digest: str

    def __post_init__(self) -> None:
        _require_text("schedule_key", self.schedule_key)
        if type(self.schedule_version) is not int:
            raise TypeError("schedule_version must be int")
        if self.schedule_version <= 0:
            raise ValueError("schedule_version must be positive")
        _require_hash("schedule_digest", self.schedule_digest)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "account_fee_schedule_ref",
            "schedule_key": self.schedule_key,
            "schedule_version": self.schedule_version,
            "schedule_digest": self.schedule_digest,
        }


@dataclass(frozen=True, slots=True)
class FeeReservationChargeRule:
    source: FeeReservationRuleSource
    rule_id: str
    basis: FeeReservationBasis
    applicability: FeeReservationApplicability
    rate: Rate | None
    flat_amount: Money | None
    quantization: QuantizationPolicy

    def __post_init__(self) -> None:
        _validate_rule_identity(
            self.source,
            self.rule_id,
            self.basis,
            minimum_basis_allowed=False,
        )
        if not isinstance(self.applicability, FeeReservationApplicability):
            raise TypeError("applicability must be FeeReservationApplicability")
        if not isinstance(self.quantization, QuantizationPolicy):
            raise TypeError("quantization must be QuantizationPolicy")
        if self.basis is FeeReservationBasis.ORDER_NOTIONAL:
            if not isinstance(self.rate, Rate) or self.flat_amount is not None:
                raise ValueError("order_notional requires rate and forbids flat_amount")
            if self.rate.units < 0 or self.rate.basis != "fee_fraction":
                raise ValueError("order_notional rate must be non-negative fee_fraction")
        elif self.basis is FeeReservationBasis.FLAT_PER_ORDER:
            if not isinstance(self.flat_amount, Money) or self.rate is not None:
                raise ValueError("flat_per_order requires flat_amount and forbids rate")
            if self.flat_amount.units < 0:
                raise ValueError("flat_amount must be non-negative")
        elif self.basis is FeeReservationBasis.UNKNOWN:
            if self.rate is not None or self.flat_amount is not None:
                raise ValueError("unknown basis cannot carry an interpreted amount")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_reservation_charge_rule",
            "source": self.source.value,
            "rule_id": self.rule_id,
            "basis": self.basis.value,
            "applicability": self.applicability.value,
            "rate": self.rate,
            "flat_amount": self.flat_amount,
            "quantization": self.quantization,
        }


@dataclass(frozen=True, slots=True)
class FeeReservationMinimum:
    source: FeeReservationRuleSource
    minimum_id: str
    charge_rule_ids: tuple[str, ...]
    minimum_amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.source, FeeReservationRuleSource):
            raise TypeError("source must be FeeReservationRuleSource")
        _require_text("minimum_id", self.minimum_id)
        if not isinstance(self.charge_rule_ids, tuple) or not self.charge_rule_ids:
            raise TypeError("charge_rule_ids must be a non-empty tuple")
        for rule_id in self.charge_rule_ids:
            _require_text("charge_rule_id", rule_id)
        ordered = tuple(sorted(self.charge_rule_ids))
        if len(ordered) != len(set(ordered)):
            raise ValueError("duplicate charge rule in minimum scope")
        if not isinstance(self.minimum_amount, Money):
            raise TypeError("minimum_amount must be Money")
        if self.minimum_amount.units <= 0:
            raise ValueError("minimum_amount must be positive")
        object.__setattr__(self, "charge_rule_ids", ordered)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_reservation_minimum",
            "source": self.source.value,
            "minimum_id": self.minimum_id,
            "charge_rule_ids": self.charge_rule_ids,
            "minimum_amount": self.minimum_amount,
        }


def _rule_order(rule: FeeReservationChargeRule) -> tuple[int, str]:
    return (_SOURCE_ORDER[rule.source.value], rule.rule_id)


def _minimum_order(value: FeeReservationMinimum) -> tuple[int, str]:
    return (_SOURCE_ORDER[value.source.value], value.minimum_id)


@dataclass(frozen=True, slots=True)
class FeeReservationRuleSet:
    market_fee_policy_ref: ProfileComponentRef
    tax_policy_ref: ProfileComponentRef
    account_fee_schedule_ref: AccountFeeScheduleRef
    reservation_currency: CurrencyId
    reservation_scale: Scale
    charge_rules: tuple[FeeReservationChargeRule, ...]
    minimums: tuple[FeeReservationMinimum, ...]
    config_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.market_fee_policy_ref, ProfileComponentRef) or (
            self.market_fee_policy_ref.port_type
            is not ProfilePortType.FEE_ASSESSMENT_POLICY
        ):
            raise TypeError("market_fee_policy_ref must identify FeeAssessmentPolicy")
        if not isinstance(self.tax_policy_ref, ProfileComponentRef) or (
            self.tax_policy_ref.port_type is not ProfilePortType.TAX_POLICY
        ):
            raise TypeError("tax_policy_ref must identify TaxPolicy")
        if not isinstance(self.account_fee_schedule_ref, AccountFeeScheduleRef):
            raise TypeError("account_fee_schedule_ref must be AccountFeeScheduleRef")
        if not isinstance(self.reservation_currency, CurrencyId):
            raise TypeError("reservation_currency must be CurrencyId")
        if not isinstance(self.reservation_scale, Scale):
            raise TypeError("reservation_scale must be Scale")
        if not isinstance(self.charge_rules, tuple) or not all(
            isinstance(rule, FeeReservationChargeRule) for rule in self.charge_rules
        ):
            raise TypeError("charge_rules must be FeeReservationChargeRule tuple")
        if not isinstance(self.minimums, tuple) or not all(
            isinstance(value, FeeReservationMinimum) for value in self.minimums
        ):
            raise TypeError("minimums must be FeeReservationMinimum tuple")

        ordered_rules = tuple(sorted(self.charge_rules, key=_rule_order))
        rule_ids = tuple(rule.rule_id for rule in ordered_rules)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("duplicate fee charge rule identity")
        if {rule.source for rule in ordered_rules} != set(FeeReservationRuleSource):
            raise ValueError("explicit rule coverage is required for every source")
        for rule in ordered_rules:
            if rule.quantization.target_scale != self.reservation_scale:
                raise ValueError("fee rule currency or Scale mismatch")
            if rule.flat_amount is not None and (
                rule.flat_amount.currency != str(self.reservation_currency)
                or rule.flat_amount.scale != self.reservation_scale
            ):
                raise ValueError("fee rule currency or Scale mismatch")

        ordered_minimums = tuple(sorted(self.minimums, key=_minimum_order))
        minimum_ids = tuple(value.minimum_id for value in ordered_minimums)
        if len(minimum_ids) != len(set(minimum_ids)):
            raise ValueError("duplicate fee minimum identity")
        by_id = {rule.rule_id: rule for rule in ordered_rules}
        covered: set[str] = set()
        for minimum in ordered_minimums:
            if (
                minimum.minimum_amount.currency != str(self.reservation_currency)
                or minimum.minimum_amount.scale != self.reservation_scale
            ):
                raise ValueError("fee minimum currency or Scale mismatch")
            for rule_id in minimum.charge_rule_ids:
                scoped_rule = by_id.get(rule_id)
                if scoped_rule is None:
                    raise ValueError("minimum scope references unknown charge rule")
                if scoped_rule.source is not minimum.source:
                    raise ValueError("minimum scope charge rules must have same source")
                if rule_id in covered:
                    raise ValueError("charge rule cannot belong to multiple minimums")
                covered.add(rule_id)

        object.__setattr__(self, "charge_rules", ordered_rules)
        object.__setattr__(self, "minimums", ordered_minimums)
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        market_fee_policy_ref: ProfileComponentRef,
        tax_policy_ref: ProfileComponentRef,
        account_fee_schedule_ref: AccountFeeScheduleRef,
        reservation_currency: CurrencyId,
        reservation_scale: Scale,
        charge_rules: tuple[FeeReservationChargeRule, ...],
        minimums: tuple[FeeReservationMinimum, ...],
    ) -> FeeReservationRuleSet:
        provisional = cls.__new__(cls)
        object.__setattr__(provisional, "market_fee_policy_ref", market_fee_policy_ref)
        object.__setattr__(provisional, "tax_policy_ref", tax_policy_ref)
        object.__setattr__(
            provisional, "account_fee_schedule_ref", account_fee_schedule_ref
        )
        object.__setattr__(provisional, "reservation_currency", reservation_currency)
        object.__setattr__(provisional, "reservation_scale", reservation_scale)
        object.__setattr__(
            provisional, "charge_rules", tuple(sorted(charge_rules, key=_rule_order))
        )
        object.__setattr__(
            provisional, "minimums", tuple(sorted(minimums, key=_minimum_order))
        )
        object.__setattr__(
            provisional, "config_hash", canonical_sha256(provisional.config_payload())
        )
        provisional.__post_init__()
        return provisional

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "fee_reservation_rule_set_config",
            "schema_version": 1,
            "market_fee_policy_ref": self.market_fee_policy_ref,
            "tax_policy_ref": self.tax_policy_ref,
            "account_fee_schedule_ref": self.account_fee_schedule_ref,
            "reservation_currency": self.reservation_currency,
            "reservation_scale": self.reservation_scale.places,
            "charge_rules": self.charge_rules,
            "minimums": self.minimums,
        }

    @property
    def rule_set_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "fee_reservation_rule_set",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class FeeReservationLine:
    source: FeeReservationRuleSource
    rule_id: str
    basis: FeeReservationBasis
    amount: Money

    def __post_init__(self) -> None:
        _validate_rule_identity(
            self.source,
            self.rule_id,
            self.basis,
            minimum_basis_allowed=True,
        )
        if self.basis is FeeReservationBasis.UNKNOWN:
            raise ValueError("reservation line cannot have unknown basis")
        if not isinstance(self.amount, Money):
            raise TypeError("amount must be Money")
        if self.amount.units < 0:
            raise ValueError("reservation line amount must be non-negative")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_reservation_line",
            "source": self.source.value,
            "rule_id": self.rule_id,
            "basis": self.basis.value,
            "amount": self.amount,
        }


def _line_order(line: FeeReservationLine) -> tuple[int, int, str]:
    minimum_rank = 1 if line.basis is FeeReservationBasis.PER_ORDER_MINIMUM else 0
    return (_SOURCE_ORDER[line.source.value], minimum_rank, line.rule_id)


def _validate_estimation_context(
    approval: MarketRuleApproval,
    rule_set: FeeReservationRuleSet,
    estimated_at: UtcInstant,
) -> None:
    if not isinstance(approval, MarketRuleApproval):
        raise TypeError("market_rule_approval must be MarketRuleApproval")
    if not isinstance(rule_set, FeeReservationRuleSet):
        raise TypeError("rule_set must be FeeReservationRuleSet")
    if not isinstance(estimated_at, UtcInstant):
        raise TypeError("estimated_at must be UtcInstant")


def _estimate_payload(
    approval: MarketRuleApproval,
    rule_set: FeeReservationRuleSet,
    estimated_at: UtcInstant,
    lines: tuple[FeeReservationLine, ...],
    total_fee: Money,
) -> dict[str, Any]:
    return {
        "type": "fee_reservation_estimate_identity",
        "schema_version": 1,
        "market_rule_decision_id": approval.decision_id,
        "market_rule_decision_hash": canonical_sha256(approval),
        "rule_set_hash": rule_set.rule_set_hash,
        "estimated_at": estimated_at,
        "lines": lines,
        "total_fee": total_fee,
    }


@dataclass(frozen=True, slots=True)
class FeeReservationEstimate:
    estimate_id: str
    market_rule_approval: MarketRuleApproval
    rule_set: FeeReservationRuleSet
    estimated_at: UtcInstant
    lines: tuple[FeeReservationLine, ...]
    total_fee: Money

    def __post_init__(self) -> None:
        _require_text("estimate_id", self.estimate_id)
        _validate_estimation_context(
            self.market_rule_approval,
            self.rule_set,
            self.estimated_at,
        )
        if self.estimated_at < self.market_rule_approval.evaluation_input.evaluated_at:
            raise ValueError("fee estimation precedes Market Rule evaluation")
        if not isinstance(self.lines, tuple) or not all(
            isinstance(line, FeeReservationLine) for line in self.lines
        ):
            raise TypeError("lines must be FeeReservationLine tuple")
        ordered = tuple(sorted(self.lines, key=_line_order))
        if len({(line.source, line.rule_id) for line in ordered}) != len(ordered):
            raise ValueError("duplicate fee reservation line identity")
        if not isinstance(self.total_fee, Money):
            raise TypeError("total_fee must be Money")
        for line in ordered:
            if (
                line.amount.currency != str(self.rule_set.reservation_currency)
                or line.amount.scale != self.rule_set.reservation_scale
            ):
                raise ValueError("fee reservation line currency or Scale mismatch")
        if (
            self.total_fee.currency != str(self.rule_set.reservation_currency)
            or self.total_fee.scale != self.rule_set.reservation_scale
        ):
            raise ValueError("total fee currency or Scale mismatch")
        if self.total_fee.units != sum(line.amount.units for line in ordered):
            raise ValueError("total fee does not equal reservation lines")
        object.__setattr__(self, "lines", ordered)
        expected = _tagged_id(
            "fee-reservation-estimate-v1",
            _estimate_payload(
                self.market_rule_approval,
                self.rule_set,
                self.estimated_at,
                ordered,
                self.total_fee,
            ),
        )
        if self.estimate_id != expected:
            raise ValueError("estimate_id mismatch")

    @property
    def estimate_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_reservation_estimate",
            "schema_version": 1,
            "estimate_id": self.estimate_id,
            "market_rule_approval": self.market_rule_approval,
            "rule_set": self.rule_set,
            "estimated_at": self.estimated_at,
            "lines": self.lines,
            "total_fee": self.total_fee,
        }


@dataclass(frozen=True, slots=True)
class ResourceReservationProposal:
    proposal_id: str
    order_id: DomainId
    fee_estimate: FeeReservationEstimate
    commitment: ReservationCommitment

    def __post_init__(self) -> None:
        _require_text("proposal_id", self.proposal_id)
        if not isinstance(self.order_id, DomainId) or (
            self.order_id.kind is not DomainIdKind.ORDER
        ):
            raise TypeError("order_id must be ORDER DomainId")
        if not isinstance(self.fee_estimate, FeeReservationEstimate):
            raise TypeError("fee_estimate must be FeeReservationEstimate")
        source_order = (
            self.fee_estimate.market_rule_approval.evaluation_input
            .executable_order_spec.source_order
        )
        if self.order_id != source_order.order_id:
            raise ValueError("proposal Order identity mismatch")
        if not isinstance(self.commitment, ReservationCommitment):
            raise TypeError("commitment must be ReservationCommitment")
        expected_commitment = ReservationCommitment(
            fee_reserve=(self.fee_estimate.total_fee,)
            if self.fee_estimate.total_fee.units > 0
            else ()
        )
        if self.commitment != expected_commitment:
            raise ValueError("proposal must contain only exact fee reserve")
        expected = _tagged_id(
            "resource-reservation-proposal-v1",
            {
                "order_id": self.order_id,
                "fee_estimate_hash": self.fee_estimate.estimate_hash,
                "commitment": self.commitment,
            },
        )
        if self.proposal_id != expected:
            raise ValueError("proposal_id mismatch")

    @property
    def proposal_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "resource_reservation_proposal",
            "schema_version": 1,
            "proposal_id": self.proposal_id,
            "order_id": self.order_id,
            "fee_estimate": self.fee_estimate,
            "commitment": self.commitment,
        }


class FeeReservationFailureCode(Enum):
    ESTIMATION_BEFORE_MARKET_RULE_EVALUATION = (
        "estimation_before_market_rule_evaluation"
    )
    RESERVATION_CURRENCY_MISMATCH = "reservation_currency_mismatch"
    UNKNOWN_APPLICABILITY = "unknown_applicability"
    UNKNOWN_BASIS = "unknown_basis"


@dataclass(frozen=True, slots=True)
class FeeReservationFailure:
    failure_id: str
    market_rule_approval: MarketRuleApproval
    rule_set: FeeReservationRuleSet
    estimated_at: UtcInstant
    codes: tuple[FeeReservationFailureCode, ...]
    subject_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text("failure_id", self.failure_id)
        _validate_estimation_context(
            self.market_rule_approval,
            self.rule_set,
            self.estimated_at,
        )
        if not isinstance(self.codes, tuple) or not self.codes or not all(
            isinstance(code, FeeReservationFailureCode) for code in self.codes
        ):
            raise TypeError("codes must be a non-empty FeeReservationFailureCode tuple")
        if not isinstance(self.subject_rule_ids, tuple) or (
            len(self.subject_rule_ids) != len(self.codes)
        ):
            raise ValueError("subject_rule_ids must align with failure codes")
        pairs = []
        for code, subject in zip(self.codes, self.subject_rule_ids, strict=True):
            _require_text("subject_rule_id", subject)
            pairs.append((code, subject))
        ordered = tuple(sorted(pairs, key=lambda item: (item[0].value, item[1])))
        if len(ordered) != len(set(ordered)):
            raise ValueError("duplicate fee reservation failure issue")
        object.__setattr__(self, "codes", tuple(code for code, _ in ordered))
        object.__setattr__(
            self, "subject_rule_ids", tuple(subject for _, subject in ordered)
        )
        expected = _tagged_id(
            "fee-reservation-failure-v1",
            {
                "market_rule_decision_id": self.market_rule_approval.decision_id,
                "market_rule_decision_hash": canonical_sha256(
                    self.market_rule_approval
                ),
                "rule_set_hash": self.rule_set.rule_set_hash,
                "estimated_at": self.estimated_at,
                "issues": tuple(
                    {
                        "code": code.value,
                        "subject_rule_id": subject,
                    }
                    for code, subject in ordered
                ),
            },
        )
        if self.failure_id != expected:
            raise ValueError("failure_id mismatch")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_reservation_failure",
            "schema_version": 1,
            "failure_id": self.failure_id,
            "market_rule_approval": self.market_rule_approval,
            "rule_set": self.rule_set,
            "estimated_at": self.estimated_at,
            "issues": tuple(
                {"code": code.value, "subject_rule_id": subject}
                for code, subject in zip(
                    self.codes, self.subject_rule_ids, strict=True
                )
            ),
        }


@dataclass(frozen=True, slots=True)
class FeeReservationOutcome:
    estimate: FeeReservationEstimate | None
    proposal: ResourceReservationProposal | None
    failure: FeeReservationFailure | None

    def __post_init__(self) -> None:
        success = self.estimate is not None or self.proposal is not None
        if success:
            if not isinstance(self.estimate, FeeReservationEstimate) or not isinstance(
                self.proposal, ResourceReservationProposal
            ):
                raise ValueError("successful outcome requires estimate and proposal")
            if self.failure is not None:
                raise ValueError("successful outcome forbids failure")
            if self.proposal.fee_estimate != self.estimate:
                raise ValueError("proposal Fee Estimate mismatch")
        elif not isinstance(self.failure, FeeReservationFailure):
            raise ValueError("failed outcome requires FeeReservationFailure")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_reservation_outcome",
            "schema_version": 1,
            "estimate": self.estimate,
            "proposal": self.proposal,
            "failure": self.failure,
        }


def _failure(
    approval: MarketRuleApproval,
    rule_set: FeeReservationRuleSet,
    estimated_at: UtcInstant,
    issues: tuple[tuple[FeeReservationFailureCode, str], ...],
) -> FeeReservationOutcome:
    ordered = tuple(sorted(issues, key=lambda item: (item[0].value, item[1])))
    payload = {
        "market_rule_decision_id": approval.decision_id,
        "market_rule_decision_hash": canonical_sha256(approval),
        "rule_set_hash": rule_set.rule_set_hash,
        "estimated_at": estimated_at,
        "issues": tuple(
            {"code": code.value, "subject_rule_id": subject}
            for code, subject in ordered
        ),
    }
    failure = FeeReservationFailure(
        failure_id=_tagged_id("fee-reservation-failure-v1", payload),
        market_rule_approval=approval,
        rule_set=rule_set,
        estimated_at=estimated_at,
        codes=tuple(code for code, _ in ordered),
        subject_rule_ids=tuple(subject for _, subject in ordered),
    )
    return FeeReservationOutcome(estimate=None, proposal=None, failure=failure)


class FeeReservationEstimator:
    """Estimate one Order's worst-case fee without producing accounting facts."""

    def estimate(
        self,
        market_rule_approval: MarketRuleApproval,
        rule_set: FeeReservationRuleSet,
        estimated_at: UtcInstant,
    ) -> FeeReservationOutcome:
        if not isinstance(market_rule_approval, MarketRuleApproval):
            raise TypeError("market_rule_approval must be MarketRuleApproval")
        if not isinstance(rule_set, FeeReservationRuleSet):
            raise TypeError("rule_set must be FeeReservationRuleSet")
        if not isinstance(estimated_at, UtcInstant):
            raise TypeError("estimated_at must be UtcInstant")
        if estimated_at < market_rule_approval.evaluation_input.evaluated_at:
            return _failure(
                market_rule_approval,
                rule_set,
                estimated_at,
                (
                    (
                        FeeReservationFailureCode.ESTIMATION_BEFORE_MARKET_RULE_EVALUATION,
                        market_rule_approval.decision_id,
                    ),
                ),
            )

        if (
            market_rule_approval.calculated_notional.currency
            != str(rule_set.reservation_currency)
        ):
            return _failure(
                market_rule_approval,
                rule_set,
                estimated_at,
                (
                    (
                        FeeReservationFailureCode.RESERVATION_CURRENCY_MISMATCH,
                        market_rule_approval.decision_id,
                    ),
                ),
            )

        issues = []
        for rule in rule_set.charge_rules:
            if rule.applicability is FeeReservationApplicability.UNKNOWN:
                issues.append(
                    (FeeReservationFailureCode.UNKNOWN_APPLICABILITY, rule.rule_id)
                )
            if rule.basis is FeeReservationBasis.UNKNOWN:
                issues.append((FeeReservationFailureCode.UNKNOWN_BASIS, rule.rule_id))
        if issues:
            return _failure(
                market_rule_approval, rule_set, estimated_at, tuple(issues)
            )

        lines: list[FeeReservationLine] = []
        charge_amounts: dict[str, Money] = {}
        applicable_rule_ids: set[str] = set()
        for rule in rule_set.charge_rules:
            if rule.applicability is FeeReservationApplicability.NOT_APPLICABLE:
                continue
            applicable_rule_ids.add(rule.rule_id)
            if rule.basis is FeeReservationBasis.ORDER_NOTIONAL:
                if rule.rate is None:
                    raise ValueError("validated notional rule has no rate")
                amount = market_rule_approval.calculated_notional.multiply_by_rate(
                    rule.rate,
                    result_scale=rule_set.reservation_scale,
                    rounding=rule.quantization.rounding,
                )
            else:
                if rule.flat_amount is None:
                    raise ValueError("validated flat rule has no amount")
                amount = rule.flat_amount
            line = FeeReservationLine(
                source=rule.source,
                rule_id=rule.rule_id,
                basis=rule.basis,
                amount=amount,
            )
            lines.append(line)
            charge_amounts[rule.rule_id] = amount

        for minimum in rule_set.minimums:
            scoped_ids = set(minimum.charge_rule_ids)
            subtotal = sum(
                charge_amounts[rule_id].units
                for rule_id in minimum.charge_rule_ids
                if rule_id in charge_amounts
            )
            adjustment = (
                max(minimum.minimum_amount.units - subtotal, 0)
                if scoped_ids & applicable_rule_ids
                else 0
            )
            lines.append(
                FeeReservationLine(
                    source=minimum.source,
                    rule_id=minimum.minimum_id,
                    basis=FeeReservationBasis.PER_ORDER_MINIMUM,
                    amount=Money(
                        adjustment,
                        rule_set.reservation_scale,
                        str(rule_set.reservation_currency),
                    ),
                )
            )

        ordered_lines = tuple(sorted(lines, key=_line_order))
        total_fee = Money(
            sum(line.amount.units for line in ordered_lines),
            rule_set.reservation_scale,
            str(rule_set.reservation_currency),
        )
        estimate = FeeReservationEstimate(
            estimate_id=_tagged_id(
                "fee-reservation-estimate-v1",
                _estimate_payload(
                    market_rule_approval,
                    rule_set,
                    estimated_at,
                    ordered_lines,
                    total_fee,
                ),
            ),
            market_rule_approval=market_rule_approval,
            rule_set=rule_set,
            estimated_at=estimated_at,
            lines=ordered_lines,
            total_fee=total_fee,
        )
        source_order = (
            market_rule_approval.evaluation_input.executable_order_spec.source_order
        )
        commitment = ReservationCommitment(
            fee_reserve=(total_fee,) if total_fee.units > 0 else ()
        )
        proposal_payload = {
            "order_id": source_order.order_id,
            "fee_estimate_hash": estimate.estimate_hash,
            "commitment": commitment,
        }
        proposal = ResourceReservationProposal(
            proposal_id=_tagged_id(
                "resource-reservation-proposal-v1", proposal_payload
            ),
            order_id=source_order.order_id,
            fee_estimate=estimate,
            commitment=commitment,
        )
        return FeeReservationOutcome(
            estimate=estimate,
            proposal=proposal,
            failure=None,
        )
