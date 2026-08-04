from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self, cast

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    Scale,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .allocation import NetInstrumentTarget, PortfolioAllocation


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_APPROVED_TARGET_ID_RE = re.compile(
    r"^approved-portfolio-target-v1:sha256:[0-9a-f]{64}$"
)


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _money(units: int, scale: Scale, currency: CurrencyId) -> Money:
    return Money(units, scale, str(currency))


class PortfolioRiskAction(str, Enum):
    APPROVE = "approve"
    CLAMP = "clamp"
    REJECT = "reject"


class PortfolioRiskScope(str, Enum):
    TARGET_ABSOLUTE_NOTIONAL = "target_absolute_notional"
    GROSS_EXPOSURE = "gross_exposure"
    ABSOLUTE_NET_EXPOSURE = "absolute_net_exposure"


class PortfolioRiskReasonCode(str, Enum):
    WITHIN_LIMIT = "within_limit"
    TARGET_LIMIT_EXCEEDED = "target_limit_exceeded"
    GROSS_LIMIT_EXCEEDED = "gross_limit_exceeded"
    ABSOLUTE_NET_LIMIT_EXCEEDED = "absolute_net_limit_exceeded"


@dataclass(frozen=True, slots=True)
class PortfolioRiskPolicyRef:
    policy_key: str
    policy_version: int
    config_hash: str

    def __post_init__(self) -> None:
        _canonical_text("policy_key", self.policy_key)
        if isinstance(self.policy_version, bool) or not isinstance(
            self.policy_version, int
        ):
            raise TypeError("policy_version must be an integer")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        _require_hash("config_hash", self.config_hash)

    @property
    def policy_ref_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_risk_policy_ref",
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class PortfolioRiskLimit:
    limit_id: str
    scope: PortfolioRiskScope
    maximum: Money
    breach_action: PortfolioRiskAction
    instrument_id: InstrumentId | None

    def __post_init__(self) -> None:
        _canonical_text("limit_id", self.limit_id)
        if not isinstance(self.scope, PortfolioRiskScope):
            raise TypeError("scope must be PortfolioRiskScope")
        if not isinstance(self.maximum, Money):
            raise TypeError("maximum must be Money")
        if self.maximum.units < 0:
            raise ValueError("maximum must be nonnegative")
        if not isinstance(self.breach_action, PortfolioRiskAction):
            raise TypeError("breach_action must be PortfolioRiskAction")
        if self.scope is PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL:
            if not isinstance(self.instrument_id, InstrumentId):
                raise ValueError("target limit requires instrument_id")
            if self.breach_action not in {
                PortfolioRiskAction.CLAMP,
                PortfolioRiskAction.REJECT,
            }:
                raise ValueError("target breach action must clamp or reject")
        else:
            if self.instrument_id is not None:
                raise ValueError("aggregate limit cannot have instrument_id")
            if self.breach_action is not PortfolioRiskAction.REJECT:
                raise ValueError("aggregate breach action must reject in v1")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_risk_limit",
            "limit_id": self.limit_id,
            "scope": self.scope.value,
            "maximum": self.maximum,
            "breach_action": self.breach_action.value,
            "instrument_id": self.instrument_id,
        }


def _limit_key(limit: PortfolioRiskLimit) -> tuple[str, str, str]:
    return (
        limit.scope.value,
        "" if limit.instrument_id is None else str(limit.instrument_id),
        limit.limit_id,
    )


def _policy_config_payload(
    valuation_currency: CurrencyId,
    notional_scale: Scale,
    limits: tuple[PortfolioRiskLimit, ...],
) -> dict[str, Any]:
    return {
        "type": "portfolio_risk_policy_config",
        "schema_version": 1,
        "valuation_currency": valuation_currency,
        "notional_scale": notional_scale.places,
        "limits": tuple(sorted(limits, key=_limit_key)),
    }


@dataclass(frozen=True, slots=True)
class PortfolioRiskPolicy:
    policy_ref: PortfolioRiskPolicyRef
    valuation_currency: CurrencyId
    notional_scale: Scale
    limits: tuple[PortfolioRiskLimit, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.policy_ref, PortfolioRiskPolicyRef):
            raise TypeError("policy_ref must be PortfolioRiskPolicyRef")
        if not isinstance(self.valuation_currency, CurrencyId):
            raise TypeError("valuation_currency must be CurrencyId")
        if not isinstance(self.notional_scale, Scale):
            raise TypeError("notional_scale must be Scale")
        if not isinstance(self.limits, tuple) or not all(
            isinstance(limit, PortfolioRiskLimit) for limit in self.limits
        ):
            raise TypeError("limits must contain PortfolioRiskLimit")

        ordered = tuple(sorted(self.limits, key=_limit_key))
        if len({limit.limit_id for limit in ordered}) != len(ordered):
            raise ValueError("duplicate risk limit_id")
        if any(
            limit.maximum.currency != str(self.valuation_currency)
            or limit.maximum.scale != self.notional_scale
            for limit in ordered
        ):
            raise ValueError("risk limit currency or scale mismatch")
        target_instruments = [
            limit.instrument_id
            for limit in ordered
            if limit.scope is PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL
        ]
        if len(set(target_instruments)) != len(target_instruments):
            raise ValueError("duplicate target risk limit")
        for aggregate_scope in (
            PortfolioRiskScope.GROSS_EXPOSURE,
            PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
        ):
            if sum(limit.scope == aggregate_scope for limit in ordered) != 1:
                raise ValueError(f"policy requires exactly one {aggregate_scope.value} limit")

        expected_hash = canonical_sha256(
            _policy_config_payload(
                self.valuation_currency,
                self.notional_scale,
                ordered,
            )
        )
        if self.policy_ref.config_hash != expected_hash:
            raise ValueError("policy_ref config_hash does not match policy config")
        object.__setattr__(self, "limits", ordered)

    @classmethod
    def create(
        cls,
        *,
        policy_key: str,
        policy_version: int,
        valuation_currency: CurrencyId,
        notional_scale: Scale,
        limits: tuple[PortfolioRiskLimit, ...],
    ) -> Self:
        ordered = tuple(sorted(limits, key=_limit_key))
        config_hash = canonical_sha256(
            _policy_config_payload(valuation_currency, notional_scale, ordered)
        )
        return cls(
            policy_ref=PortfolioRiskPolicyRef(
                policy_key=policy_key,
                policy_version=policy_version,
                config_hash=config_hash,
            ),
            valuation_currency=valuation_currency,
            notional_scale=notional_scale,
            limits=ordered,
        )

    def config_payload(self) -> dict[str, Any]:
        return _policy_config_payload(
            self.valuation_currency,
            self.notional_scale,
            self.limits,
        )

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_risk_policy",
            "policy_ref": self.policy_ref,
            "valuation_currency": self.valuation_currency,
            "notional_scale": self.notional_scale.places,
            "limits": self.limits,
        }


@dataclass(frozen=True, slots=True)
class PortfolioRiskDecision:
    scope: PortfolioRiskScope
    action: PortfolioRiskAction
    reason_code: PortfolioRiskReasonCode
    limit_id: str
    policy_ref: PortfolioRiskPolicyRef
    before_notional: Money
    after_notional: Money
    limit_notional: Money
    instrument_id: InstrumentId | None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, PortfolioRiskScope):
            raise TypeError("scope must be PortfolioRiskScope")
        if not isinstance(self.action, PortfolioRiskAction):
            raise TypeError("action must be PortfolioRiskAction")
        if not isinstance(self.reason_code, PortfolioRiskReasonCode):
            raise TypeError("reason_code must be PortfolioRiskReasonCode")
        _canonical_text("limit_id", self.limit_id)
        if not isinstance(self.policy_ref, PortfolioRiskPolicyRef):
            raise TypeError("policy_ref must be PortfolioRiskPolicyRef")
        if not all(
            isinstance(value, Money)
            for value in (
                self.before_notional,
                self.after_notional,
                self.limit_notional,
            )
        ):
            raise TypeError("risk decision notionals must be Money")
        contexts = {
            (value.currency, value.scale)
            for value in (
                self.before_notional,
                self.after_notional,
                self.limit_notional,
            )
        }
        if len(contexts) != 1:
            raise ValueError("risk decision notional context mismatch")
        if self.limit_notional.units < 0:
            raise ValueError("risk decision limit must be nonnegative")

        if self.scope is PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL:
            if not isinstance(self.instrument_id, InstrumentId):
                raise ValueError("target risk decision requires instrument_id")
            expected_breach_reason = PortfolioRiskReasonCode.TARGET_LIMIT_EXCEEDED
        else:
            if self.instrument_id is not None:
                raise ValueError("aggregate risk decision cannot have instrument_id")
            expected_breach_reason = (
                PortfolioRiskReasonCode.GROSS_LIMIT_EXCEEDED
                if self.scope is PortfolioRiskScope.GROSS_EXPOSURE
                else PortfolioRiskReasonCode.ABSOLUTE_NET_LIMIT_EXCEEDED
            )

        exceeded = abs(self.before_notional.units) > self.limit_notional.units
        if self.action is PortfolioRiskAction.APPROVE:
            if exceeded or self.after_notional != self.before_notional:
                raise ValueError("approve decision must preserve a within-limit value")
            if self.reason_code is not PortfolioRiskReasonCode.WITHIN_LIMIT:
                raise ValueError("approve decision reason must be within_limit")
        elif self.action is PortfolioRiskAction.CLAMP:
            if self.scope is not PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL:
                raise ValueError("aggregate clamp is unsupported in v1")
            expected_units = (
                self.limit_notional.units
                if self.before_notional.units >= 0
                else -self.limit_notional.units
            )
            if not exceeded or self.after_notional.units != expected_units:
                raise ValueError("clamp decision must truncate toward zero to limit")
            if self.reason_code is not expected_breach_reason:
                raise ValueError("clamp decision reason mismatch")
        else:
            if not exceeded or self.after_notional.units != 0:
                raise ValueError("reject decision must zero an exceeded value")
            if self.reason_code is not expected_breach_reason:
                raise ValueError("reject decision reason mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_risk_decision",
            "scope": self.scope.value,
            "action": self.action.value,
            "reason_code": self.reason_code.value,
            "limit_id": self.limit_id,
            "policy_ref": self.policy_ref,
            "before_notional": self.before_notional,
            "after_notional": self.after_notional,
            "limit_notional": self.limit_notional,
            "instrument_id": self.instrument_id,
        }


def _decision_key(
    decision: PortfolioRiskDecision,
) -> tuple[str, str, str]:
    return (
        decision.scope.value,
        "" if decision.instrument_id is None else str(decision.instrument_id),
        decision.limit_id,
    )


@dataclass(frozen=True, slots=True)
class ApprovedInstrumentTarget:
    source_target: NetInstrumentTarget
    approved_notional: Money

    def __post_init__(self) -> None:
        if not isinstance(self.source_target, NetInstrumentTarget):
            raise TypeError("source_target must be NetInstrumentTarget")
        if not isinstance(self.approved_notional, Money):
            raise TypeError("approved_notional must be Money")
        if (
            self.approved_notional.currency != self.source_target.target_notional.currency
            or self.approved_notional.scale != self.source_target.target_notional.scale
        ):
            raise ValueError("approved target notional context mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "approved_instrument_target",
            "source_target": self.source_target,
            "approved_notional": self.approved_notional,
        }


@dataclass(frozen=True, slots=True)
class ApprovedPortfolioTarget:
    approved_target_id: str
    approved_at: UtcInstant
    source_allocation_id: str
    source_allocation_hash: str
    policy_ref: PortfolioRiskPolicyRef
    targets: tuple[ApprovedInstrumentTarget, ...]
    gross_exposure: Money
    net_exposure: Money
    decisions: tuple[PortfolioRiskDecision, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.approved_target_id, str)
            or _APPROVED_TARGET_ID_RE.fullmatch(self.approved_target_id) is None
        ):
            raise ValueError("approved_target_id must be an approved target identity")
        if not isinstance(self.approved_at, UtcInstant):
            raise TypeError("approved_at must be UtcInstant")
        _canonical_text("source_allocation_id", self.source_allocation_id)
        _require_hash("source_allocation_hash", self.source_allocation_hash)
        if not isinstance(self.policy_ref, PortfolioRiskPolicyRef):
            raise TypeError("policy_ref must be PortfolioRiskPolicyRef")
        if not isinstance(self.targets, tuple) or not all(
            isinstance(target, ApprovedInstrumentTarget) for target in self.targets
        ):
            raise TypeError("targets must contain ApprovedInstrumentTarget")
        if not isinstance(self.decisions, tuple) or not all(
            isinstance(decision, PortfolioRiskDecision) for decision in self.decisions
        ):
            raise TypeError("decisions must contain PortfolioRiskDecision")
        if not isinstance(self.gross_exposure, Money) or not isinstance(
            self.net_exposure, Money
        ):
            raise TypeError("gross_exposure and net_exposure must be Money")
        if (
            self.gross_exposure.currency != self.net_exposure.currency
            or self.gross_exposure.scale != self.net_exposure.scale
        ):
            raise ValueError("approved exposure context mismatch")

        targets = tuple(
            sorted(self.targets, key=lambda target: target.source_target.instrument_id)
        )
        decisions = tuple(sorted(self.decisions, key=_decision_key))
        if len({target.source_target.instrument_id for target in targets}) != len(targets):
            raise ValueError("duplicate approved Instrument target")
        if len(
            {(decision.scope, decision.instrument_id) for decision in decisions}
        ) != len(decisions):
            raise ValueError("duplicate risk decision scope")
        if any(decision.policy_ref != self.policy_ref for decision in decisions):
            raise ValueError("risk decision policy mismatch")
        if any(
            value.currency != self.gross_exposure.currency
            or value.scale != self.gross_exposure.scale
            for decision in decisions
            for value in (
                decision.before_notional,
                decision.after_notional,
                decision.limit_notional,
            )
        ):
            raise ValueError("risk decision exposure context mismatch")
        target_decisions = {
            decision.instrument_id: decision
            for decision in decisions
            if decision.scope is PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL
        }
        if set(target_decisions) != {
            target.source_target.instrument_id for target in targets
        }:
            raise ValueError("approved target decisions do not cover targets")
        aggregate_decisions = {
            decision.scope: decision
            for decision in decisions
            if decision.scope is not PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL
        }
        if set(aggregate_decisions) != {
            PortfolioRiskScope.GROSS_EXPOSURE,
            PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
        }:
            raise ValueError("approved target requires gross and net decisions")
        if any(
            target_decisions[target.source_target.instrument_id].before_notional
            != target.source_target.target_notional
            for target in targets
        ):
            raise ValueError("risk decision before target mismatch")

        intermediate = tuple(
            target_decisions[target.source_target.instrument_id].after_notional
            for target in targets
        )
        gross_before = sum(abs(value.units) for value in intermediate)
        net_before = sum(value.units for value in intermediate)
        if aggregate_decisions[
            PortfolioRiskScope.GROSS_EXPOSURE
        ].before_notional.units != gross_before:
            raise ValueError("gross decision input mismatch")
        if aggregate_decisions[
            PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE
        ].before_notional.units != net_before:
            raise ValueError("net decision input mismatch")

        aggregate_rejected = any(
            decision.action is PortfolioRiskAction.REJECT
            for decision in aggregate_decisions.values()
        )
        expected_final = (
            tuple(0 for _ in targets)
            if aggregate_rejected
            else tuple(value.units for value in intermediate)
        )
        if tuple(target.approved_notional.units for target in targets) != expected_final:
            raise ValueError("approved target does not match risk decisions")
        if self.gross_exposure.units != sum(abs(value) for value in expected_final):
            raise ValueError("gross_exposure mismatch")
        if self.net_exposure.units != sum(expected_final):
            raise ValueError("net_exposure mismatch")
        if any(
            target.approved_notional.currency != self.gross_exposure.currency
            or target.approved_notional.scale != self.gross_exposure.scale
            for target in targets
        ):
            raise ValueError("approved target exposure context mismatch")

        identity_payload = {
            "type": "approved_portfolio_target_identity",
            "schema_version": 1,
            "approved_at": self.approved_at,
            "source_allocation_id": self.source_allocation_id,
            "source_allocation_hash": self.source_allocation_hash,
            "policy_ref": self.policy_ref,
            "targets": targets,
            "decisions": decisions,
        }
        expected_id = f"approved-portfolio-target-v1:{canonical_sha256(identity_payload)}"
        if self.approved_target_id != expected_id:
            raise ValueError("approved_target_id does not match target identity")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "decisions", decisions)

    @classmethod
    def create(
        cls,
        *,
        approved_at: UtcInstant,
        source_allocation: PortfolioAllocation,
        policy_ref: PortfolioRiskPolicyRef,
        targets: tuple[ApprovedInstrumentTarget, ...],
        decisions: tuple[PortfolioRiskDecision, ...],
    ) -> Self:
        targets = tuple(
            sorted(targets, key=lambda target: target.source_target.instrument_id)
        )
        decisions = tuple(sorted(decisions, key=_decision_key))
        if targets:
            scale = targets[0].approved_notional.scale
            currency = source_allocation.valuation_currency
        else:
            scale = source_allocation.target_notional_scale
            currency = source_allocation.valuation_currency
        gross = _money(
            sum(abs(target.approved_notional.units) for target in targets),
            scale,
            currency,
        )
        net = _money(
            sum(target.approved_notional.units for target in targets),
            scale,
            currency,
        )
        identity_payload = {
            "type": "approved_portfolio_target_identity",
            "schema_version": 1,
            "approved_at": approved_at,
            "source_allocation_id": source_allocation.allocation_id,
            "source_allocation_hash": source_allocation.allocation_hash,
            "policy_ref": policy_ref,
            "targets": targets,
            "decisions": decisions,
        }
        return cls(
            approved_target_id=(
                "approved-portfolio-target-v1:"
                f"{canonical_sha256(identity_payload)}"
            ),
            approved_at=approved_at,
            source_allocation_id=source_allocation.allocation_id,
            source_allocation_hash=source_allocation.allocation_hash,
            policy_ref=policy_ref,
            targets=targets,
            gross_exposure=gross,
            net_exposure=net,
            decisions=decisions,
        )

    @property
    def economic_rejected(self) -> bool:
        return any(
            decision.action is PortfolioRiskAction.REJECT
            for decision in self.decisions
        )

    @property
    def approved_target_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "approved_portfolio_target",
            "approved_target_id": self.approved_target_id,
            "approved_at": self.approved_at,
            "source_allocation_id": self.source_allocation_id,
            "source_allocation_hash": self.source_allocation_hash,
            "policy_ref": self.policy_ref,
            "targets": self.targets,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "decisions": self.decisions,
            "economic_rejected": self.economic_rejected,
        }


class PortfolioRiskContractIssueCode(str, Enum):
    MISSING_POLICY = "missing_policy"
    VALUATION_CURRENCY_MISMATCH = "valuation_currency_mismatch"
    NOTIONAL_SCALE_MISMATCH = "notional_scale_mismatch"
    MISSING_INSTRUMENT_LIMIT = "missing_instrument_limit"
    UNEXPECTED_INSTRUMENT_LIMIT = "unexpected_instrument_limit"


@dataclass(frozen=True, slots=True)
class PortfolioRiskContractIssue:
    code: PortfolioRiskContractIssueCode
    subject_key: str
    evidence_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, PortfolioRiskContractIssueCode):
            raise TypeError("code must be PortfolioRiskContractIssueCode")
        _canonical_text("subject_key", self.subject_key)
        _require_hash("evidence_hash", self.evidence_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_risk_contract_issue",
            "code": self.code.value,
            "subject_key": self.subject_key,
            "evidence_hash": self.evidence_hash,
        }


def _issue(
    code: PortfolioRiskContractIssueCode,
    subject_key: str,
    evidence: object,
) -> PortfolioRiskContractIssue:
    return PortfolioRiskContractIssue(
        code=code,
        subject_key=subject_key,
        evidence_hash=canonical_sha256(
            {
                "type": "portfolio_risk_contract_issue_evidence",
                "schema_version": 1,
                "code": code.value,
                "subject_key": subject_key,
                "evidence": evidence,
            }
        ),
    )


@dataclass(frozen=True, slots=True)
class PortfolioRiskContractFailure:
    source_allocation_id: str
    source_allocation_hash: str
    policy_hash: str | None
    issues: tuple[PortfolioRiskContractIssue, ...]

    def __post_init__(self) -> None:
        _canonical_text("source_allocation_id", self.source_allocation_id)
        _require_hash("source_allocation_hash", self.source_allocation_hash)
        if self.policy_hash is not None:
            _require_hash("policy_hash", self.policy_hash)
        if not isinstance(self.issues, tuple) or not self.issues:
            raise ValueError("issues must be a non-empty tuple")
        if not all(isinstance(issue, PortfolioRiskContractIssue) for issue in self.issues):
            raise TypeError("issues must contain PortfolioRiskContractIssue")
        ordered = tuple(
            sorted(self.issues, key=lambda issue: (issue.code.value, issue.subject_key))
        )
        if len({(issue.code, issue.subject_key) for issue in ordered}) != len(ordered):
            raise ValueError("duplicate Portfolio Risk contract issue")
        object.__setattr__(self, "issues", ordered)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_risk_contract_failure",
            "source_allocation_id": self.source_allocation_id,
            "source_allocation_hash": self.source_allocation_hash,
            "policy_hash": self.policy_hash,
            "issues": self.issues,
        }


@dataclass(frozen=True, slots=True)
class PortfolioRiskOutcome:
    approved_target: ApprovedPortfolioTarget | None
    failure: PortfolioRiskContractFailure | None

    def __post_init__(self) -> None:
        if (self.approved_target is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one approved_target or failure")

    @classmethod
    def succeeded(cls, approved_target: ApprovedPortfolioTarget) -> Self:
        return cls(approved_target=approved_target, failure=None)

    @classmethod
    def failed(cls, failure: PortfolioRiskContractFailure) -> Self:
        return cls(approved_target=None, failure=failure)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_risk_outcome",
            "approved_target": self.approved_target,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class PortfolioRiskEvaluator:
    def evaluate(
        self,
        *,
        allocation: PortfolioAllocation,
        policy: PortfolioRiskPolicy | None,
    ) -> PortfolioRiskOutcome:
        if not isinstance(allocation, PortfolioAllocation):
            raise TypeError("allocation must be PortfolioAllocation")
        if policy is None:
            return self._failed(
                allocation,
                None,
                (
                    _issue(
                        PortfolioRiskContractIssueCode.MISSING_POLICY,
                        "portfolio-risk-policy",
                        {"source_allocation_id": allocation.allocation_id},
                    ),
                ),
            )
        if not isinstance(policy, PortfolioRiskPolicy):
            raise TypeError("policy must be PortfolioRiskPolicy or None")

        issues: list[PortfolioRiskContractIssue] = []
        if policy.valuation_currency != allocation.valuation_currency:
            issues.append(
                _issue(
                    PortfolioRiskContractIssueCode.VALUATION_CURRENCY_MISMATCH,
                    "portfolio-risk-policy",
                    {
                        "expected": allocation.valuation_currency,
                        "actual": policy.valuation_currency,
                    },
                )
            )
        if policy.notional_scale != allocation.target_notional_scale:
            issues.append(
                _issue(
                    PortfolioRiskContractIssueCode.NOTIONAL_SCALE_MISMATCH,
                    "portfolio-risk-policy",
                    {
                        "expected": allocation.target_notional_scale.places,
                        "actual": policy.notional_scale.places,
                    },
                )
            )

        expected_instruments = {
            target.instrument_id for target in allocation.net_targets
        }
        target_limits = {
            cast(InstrumentId, limit.instrument_id): limit
            for limit in policy.limits
            if limit.scope is PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL
        }
        for instrument_id in sorted(expected_instruments - set(target_limits)):
            issues.append(
                _issue(
                    PortfolioRiskContractIssueCode.MISSING_INSTRUMENT_LIMIT,
                    str(instrument_id),
                    {"instrument_id": instrument_id},
                )
            )
        for instrument_id in sorted(set(target_limits) - expected_instruments):
            if instrument_id is None:
                continue
            issues.append(
                _issue(
                    PortfolioRiskContractIssueCode.UNEXPECTED_INSTRUMENT_LIMIT,
                    str(instrument_id),
                    {"instrument_id": instrument_id},
                )
            )
        if issues:
            return self._failed(allocation, policy, tuple(issues))

        decisions: list[PortfolioRiskDecision] = []
        intermediate: dict[InstrumentId, Money] = {}
        for target in allocation.net_targets:
            limit = target_limits[target.instrument_id]
            before = target.target_notional
            if abs(before.units) <= limit.maximum.units:
                action = PortfolioRiskAction.APPROVE
                after = before
                reason = PortfolioRiskReasonCode.WITHIN_LIMIT
            elif limit.breach_action is PortfolioRiskAction.CLAMP:
                action = PortfolioRiskAction.CLAMP
                after = _money(
                    limit.maximum.units if before.units >= 0 else -limit.maximum.units,
                    before.scale,
                    allocation.valuation_currency,
                )
                reason = PortfolioRiskReasonCode.TARGET_LIMIT_EXCEEDED
            else:
                action = PortfolioRiskAction.REJECT
                after = _money(0, before.scale, allocation.valuation_currency)
                reason = PortfolioRiskReasonCode.TARGET_LIMIT_EXCEEDED
            decisions.append(
                PortfolioRiskDecision(
                    scope=PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
                    action=action,
                    reason_code=reason,
                    limit_id=limit.limit_id,
                    policy_ref=policy.policy_ref,
                    before_notional=before,
                    after_notional=after,
                    limit_notional=limit.maximum,
                    instrument_id=target.instrument_id,
                )
            )
            intermediate[target.instrument_id] = after

        gross_units = sum(abs(value.units) for value in intermediate.values())
        net_units = sum(value.units for value in intermediate.values())
        aggregate_values = {
            PortfolioRiskScope.GROSS_EXPOSURE: gross_units,
            PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE: net_units,
        }
        aggregate_rejected = False
        for scope in (
            PortfolioRiskScope.GROSS_EXPOSURE,
            PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
        ):
            limit = next(limit for limit in policy.limits if limit.scope is scope)
            before = _money(
                aggregate_values[scope],
                policy.notional_scale,
                policy.valuation_currency,
            )
            exceeded = abs(before.units) > limit.maximum.units
            action = (
                PortfolioRiskAction.REJECT
                if exceeded
                else PortfolioRiskAction.APPROVE
            )
            after = (
                _money(0, policy.notional_scale, policy.valuation_currency)
                if exceeded
                else before
            )
            reason = (
                PortfolioRiskReasonCode.WITHIN_LIMIT
                if not exceeded
                else (
                    PortfolioRiskReasonCode.GROSS_LIMIT_EXCEEDED
                    if scope is PortfolioRiskScope.GROSS_EXPOSURE
                    else PortfolioRiskReasonCode.ABSOLUTE_NET_LIMIT_EXCEEDED
                )
            )
            decisions.append(
                PortfolioRiskDecision(
                    scope=scope,
                    action=action,
                    reason_code=reason,
                    limit_id=limit.limit_id,
                    policy_ref=policy.policy_ref,
                    before_notional=before,
                    after_notional=after,
                    limit_notional=limit.maximum,
                    instrument_id=None,
                )
            )
            aggregate_rejected = aggregate_rejected or exceeded

        approved_targets = tuple(
            ApprovedInstrumentTarget(
                source_target=target,
                approved_notional=(
                    _money(
                        0,
                        allocation.target_notional_scale,
                        allocation.valuation_currency,
                    )
                    if aggregate_rejected
                    else intermediate[target.instrument_id]
                ),
            )
            for target in allocation.net_targets
        )
        return PortfolioRiskOutcome.succeeded(
            ApprovedPortfolioTarget.create(
                approved_at=allocation.valuation_time,
                source_allocation=allocation,
                policy_ref=policy.policy_ref,
                targets=approved_targets,
                decisions=tuple(decisions),
            )
        )

    @staticmethod
    def _failed(
        allocation: PortfolioAllocation,
        policy: PortfolioRiskPolicy | None,
        issues: tuple[PortfolioRiskContractIssue, ...],
    ) -> PortfolioRiskOutcome:
        return PortfolioRiskOutcome.failed(
            PortfolioRiskContractFailure(
                source_allocation_id=allocation.allocation_id,
                source_allocation_hash=allocation.allocation_hash,
                policy_hash=None if policy is None else policy.policy_hash,
                issues=issues,
            )
        )
