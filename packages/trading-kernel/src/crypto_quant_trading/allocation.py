from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    PortfolioSnapshot,
    Scale,
    SimulationInstant,
    StrategySleeveId,
    TargetExposureFraction,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .decisions import LatestSleeveDecisionState


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOCATION_ID_RE = re.compile(r"^portfolio-allocation-v[12]:sha256:[0-9a-f]{64}$")


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _exact_product_units(
    left_units: int,
    left_scale: Scale,
    right_units: int,
    right_scale: Scale,
    result_scale: Scale,
) -> int | None:
    units = left_units * right_units
    difference = result_scale.places - left_scale.places - right_scale.places
    if difference >= 0:
        return units * 10**difference
    divisor = 10 ** (-difference)
    if units % divisor:
        return None
    return units // divisor


@dataclass(frozen=True, slots=True)
class CapitalAllocationPolicyRef:
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
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "capital_allocation_policy_ref",
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class StrategyAllocation:
    strategy_id: str
    sleeve_id: StrategySleeveId
    valuation_time: UtcInstant
    valuation_currency: CurrencyId
    allocation_nav: Money
    policy_ref: CapitalAllocationPolicyRef
    source_portfolio_snapshot_hash: str
    valuation_instant: SimulationInstant | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        _canonical_text("strategy_id", self.strategy_id)
        if not isinstance(self.sleeve_id, StrategySleeveId):
            raise TypeError("sleeve_id must be StrategySleeveId")
        if not isinstance(self.valuation_time, UtcInstant):
            raise TypeError("valuation_time must be UtcInstant")
        if self.valuation_instant is not None:
            if not isinstance(self.valuation_instant, SimulationInstant):
                raise TypeError("valuation_instant must be SimulationInstant or None")
            if self.valuation_instant.instant != self.valuation_time:
                raise ValueError("valuation_instant instant must equal valuation_time")
        if not isinstance(self.valuation_currency, CurrencyId):
            raise TypeError("valuation_currency must be CurrencyId")
        if not isinstance(self.allocation_nav, Money):
            raise TypeError("allocation_nav must be Money")
        if self.allocation_nav.currency != str(self.valuation_currency):
            raise ValueError("allocation_nav currency must match valuation_currency")
        if not isinstance(self.policy_ref, CapitalAllocationPolicyRef):
            raise TypeError("policy_ref must be CapitalAllocationPolicyRef")
        _require_hash(
            "source_portfolio_snapshot_hash", self.source_portfolio_snapshot_hash
        )

    @property
    def allocation_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        value = {
            "type": "strategy_allocation",
            "strategy_id": self.strategy_id,
            "sleeve_id": self.sleeve_id,
            "valuation_time": self.valuation_time,
            "valuation_currency": self.valuation_currency,
            "allocation_nav": self.allocation_nav,
            "policy_ref": self.policy_ref,
            "source_portfolio_snapshot_hash": self.source_portfolio_snapshot_hash,
        }
        if self.valuation_instant is not None:
            value["valuation_instant"] = self.valuation_instant
        return value


@dataclass(frozen=True, slots=True)
class SleeveTargetNotional:
    strategy_id: str
    sleeve_id: StrategySleeveId
    instrument_id: InstrumentId
    target_fraction: TargetExposureFraction
    allocation_nav: Money
    target_notional: Money

    def __post_init__(self) -> None:
        _canonical_text("strategy_id", self.strategy_id)
        if not isinstance(self.sleeve_id, StrategySleeveId):
            raise TypeError("sleeve_id must be StrategySleeveId")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.target_fraction, TargetExposureFraction):
            raise TypeError("target_fraction must be TargetExposureFraction")
        if self.target_fraction.instrument_id != self.instrument_id:
            raise ValueError("target_fraction instrument mismatch")
        if not isinstance(self.allocation_nav, Money):
            raise TypeError("allocation_nav must be Money")
        if not isinstance(self.target_notional, Money):
            raise TypeError("target_notional must be Money")
        if self.allocation_nav.currency != self.target_notional.currency:
            raise ValueError("target_notional currency mismatch")
        expected = _exact_product_units(
            self.allocation_nav.units,
            self.allocation_nav.scale,
            self.target_fraction.units,
            self.target_fraction.scale,
            self.target_notional.scale,
        )
        if expected is None or expected != self.target_notional.units:
            raise ValueError("target_notional is not the exact target product")

    @property
    def attribution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "sleeve_target_notional",
            "strategy_id": self.strategy_id,
            "sleeve_id": self.sleeve_id,
            "instrument_id": self.instrument_id,
            "target_fraction": self.target_fraction,
            "allocation_nav": self.allocation_nav,
            "target_notional": self.target_notional,
        }


@dataclass(frozen=True, slots=True)
class NetInstrumentTarget:
    instrument_id: InstrumentId
    valuation_currency: CurrencyId
    target_notional: Money
    sleeve_attributions: tuple[SleeveTargetNotional, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.valuation_currency, CurrencyId):
            raise TypeError("valuation_currency must be CurrencyId")
        if not isinstance(self.target_notional, Money):
            raise TypeError("target_notional must be Money")
        if self.target_notional.currency != str(self.valuation_currency):
            raise ValueError("target_notional currency must match valuation_currency")
        if not isinstance(self.sleeve_attributions, tuple) or not self.sleeve_attributions:
            raise ValueError("sleeve_attributions must be a non-empty tuple")
        if not all(
            isinstance(value, SleeveTargetNotional)
            for value in self.sleeve_attributions
        ):
            raise TypeError("sleeve_attributions must contain SleeveTargetNotional")
        ordered = tuple(
            sorted(
                self.sleeve_attributions,
                key=lambda value: (value.sleeve_id, value.strategy_id),
            )
        )
        if len({value.sleeve_id for value in ordered}) != len(ordered):
            raise ValueError("duplicate Sleeve attribution")
        if any(value.instrument_id != self.instrument_id for value in ordered):
            raise ValueError("Sleeve attribution instrument mismatch")
        if any(
            value.target_notional.currency != self.target_notional.currency
            or value.target_notional.scale != self.target_notional.scale
            for value in ordered
        ):
            raise ValueError("Sleeve attribution notional context mismatch")
        if sum(value.target_notional.units for value in ordered) != self.target_notional.units:
            raise ValueError("net target must equal Sleeve attribution sum")
        object.__setattr__(self, "sleeve_attributions", ordered)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "net_instrument_target",
            "instrument_id": self.instrument_id,
            "valuation_currency": self.valuation_currency,
            "target_notional": self.target_notional,
            "sleeve_attributions": self.sleeve_attributions,
        }


class AllocationConstraintCode(str, Enum):
    EMPTY_SLEEVE_STATE = "empty_sleeve_state"
    MISSING_ALLOCATION = "missing_allocation"
    DUPLICATE_ALLOCATION = "duplicate_allocation"
    UNEXPECTED_ALLOCATION = "unexpected_allocation"
    STRATEGY_ID_MISMATCH = "strategy_id_mismatch"
    VALUATION_TIME_MISMATCH = "valuation_time_mismatch"
    VALUATION_INSTANT_MISMATCH = "valuation_instant_mismatch"
    VALUATION_CURRENCY_MISMATCH = "valuation_currency_mismatch"
    ALLOCATION_SCALE_MISMATCH = "allocation_scale_mismatch"
    SNAPSHOT_HASH_MISMATCH = "snapshot_hash_mismatch"
    POLICY_MISMATCH = "policy_mismatch"
    NEGATIVE_ALLOCATION_NAV = "negative_allocation_nav"
    TOTAL_ALLOCATION_EXCEEDS_EQUITY = "total_allocation_exceeds_equity"
    TARGET_NOT_EFFECTIVE = "target_not_effective"
    TARGET_EXPIRED = "target_expired"
    TARGET_NOTIONAL_INEXACT = "target_notional_inexact"


@dataclass(frozen=True, slots=True)
class AllocationConstraintDecision:
    code: AllocationConstraintCode
    subject_key: str
    evidence_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, AllocationConstraintCode):
            raise TypeError("code must be AllocationConstraintCode")
        _canonical_text("subject_key", self.subject_key)
        if self.evidence_hash is not None:
            _require_hash("evidence_hash", self.evidence_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "allocation_constraint_decision",
            "code": self.code.value,
            "subject_key": self.subject_key,
            "evidence_hash": self.evidence_hash,
        }


def _decision_key(
    decision: AllocationConstraintDecision,
) -> tuple[str, str, str]:
    return (decision.code.value, decision.subject_key, decision.evidence_hash or "")


@dataclass(frozen=True, slots=True)
class CapitalAllocationFailure:
    valuation_time: UtcInstant
    source_sleeve_state_hash: str
    source_portfolio_snapshot_hash: str
    decisions: tuple[AllocationConstraintDecision, ...]
    valuation_instant: SimulationInstant | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.valuation_time, UtcInstant):
            raise TypeError("valuation_time must be UtcInstant")
        if self.valuation_instant is not None:
            if not isinstance(self.valuation_instant, SimulationInstant):
                raise TypeError("valuation_instant must be SimulationInstant or None")
            if self.valuation_instant.instant != self.valuation_time:
                raise ValueError("valuation_instant instant must equal valuation_time")
        _require_hash("source_sleeve_state_hash", self.source_sleeve_state_hash)
        _require_hash(
            "source_portfolio_snapshot_hash", self.source_portfolio_snapshot_hash
        )
        if not isinstance(self.decisions, tuple) or not self.decisions:
            raise ValueError("decisions must be a non-empty tuple")
        if not all(
            isinstance(value, AllocationConstraintDecision) for value in self.decisions
        ):
            raise TypeError("decisions must contain AllocationConstraintDecision")
        object.__setattr__(
            self,
            "decisions",
            tuple(sorted(set(self.decisions), key=_decision_key)),
        )

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        value = {
            "type": "capital_allocation_failure",
            "valuation_time": self.valuation_time,
            "source_sleeve_state_hash": self.source_sleeve_state_hash,
            "source_portfolio_snapshot_hash": self.source_portfolio_snapshot_hash,
            "decisions": self.decisions,
        }
        if self.valuation_instant is not None:
            value["valuation_instant"] = self.valuation_instant
        return value


@dataclass(frozen=True, slots=True)
class PortfolioAllocation:
    allocation_id: str
    valuation_time: UtcInstant
    valuation_currency: CurrencyId
    target_notional_scale: Scale
    policy_ref: CapitalAllocationPolicyRef
    source_sleeve_state_hash: str
    source_portfolio_snapshot_hash: str
    allocations: tuple[StrategyAllocation, ...]
    total_allocation_nav: Money
    sleeve_targets: tuple[SleeveTargetNotional, ...]
    net_targets: tuple[NetInstrumentTarget, ...]
    valuation_instant: SimulationInstant | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.allocation_id, str) or _ALLOCATION_ID_RE.fullmatch(
            self.allocation_id
        ) is None:
            raise ValueError("allocation_id must be a portfolio-allocation identity")
        if not isinstance(self.valuation_time, UtcInstant):
            raise TypeError("valuation_time must be UtcInstant")
        if self.valuation_instant is not None:
            if not isinstance(self.valuation_instant, SimulationInstant):
                raise TypeError("valuation_instant must be SimulationInstant or None")
            if self.valuation_instant.instant != self.valuation_time:
                raise ValueError("valuation_instant instant must equal valuation_time")
        if not isinstance(self.valuation_currency, CurrencyId):
            raise TypeError("valuation_currency must be CurrencyId")
        if not isinstance(self.target_notional_scale, Scale):
            raise TypeError("target_notional_scale must be Scale")
        if not isinstance(self.policy_ref, CapitalAllocationPolicyRef):
            raise TypeError("policy_ref must be CapitalAllocationPolicyRef")
        _require_hash("source_sleeve_state_hash", self.source_sleeve_state_hash)
        _require_hash(
            "source_portfolio_snapshot_hash", self.source_portfolio_snapshot_hash
        )
        if not isinstance(self.allocations, tuple) or not self.allocations:
            raise ValueError("allocations must be a non-empty tuple")
        if not all(isinstance(value, StrategyAllocation) for value in self.allocations):
            raise TypeError("allocations must contain StrategyAllocation")
        if not isinstance(self.total_allocation_nav, Money):
            raise TypeError("total_allocation_nav must be Money")
        if not isinstance(self.sleeve_targets, tuple) or not all(
            isinstance(value, SleeveTargetNotional) for value in self.sleeve_targets
        ):
            raise TypeError("sleeve_targets must contain SleeveTargetNotional")
        if not isinstance(self.net_targets, tuple) or not all(
            isinstance(value, NetInstrumentTarget) for value in self.net_targets
        ):
            raise TypeError("net_targets must contain NetInstrumentTarget")

        ordered_allocations = tuple(
            sorted(self.allocations, key=lambda value: (value.sleeve_id, value.strategy_id))
        )
        ordered_sleeve_targets = tuple(
            sorted(
                self.sleeve_targets,
                key=lambda value: (
                    value.instrument_id,
                    value.sleeve_id,
                    value.strategy_id,
                ),
            )
        )
        ordered_net_targets = tuple(
            sorted(self.net_targets, key=lambda value: value.instrument_id)
        )
        if len({value.sleeve_id for value in ordered_allocations}) != len(
            ordered_allocations
        ):
            raise ValueError("duplicate StrategyAllocation Sleeve")
        if any(
            value.valuation_time != self.valuation_time
            or value.valuation_instant != self.valuation_instant
            or value.valuation_currency != self.valuation_currency
            or value.policy_ref != self.policy_ref
            or value.source_portfolio_snapshot_hash
            != self.source_portfolio_snapshot_hash
            for value in ordered_allocations
        ):
            raise ValueError("StrategyAllocation context mismatch")
        if any(
            value.allocation_nav.currency != str(self.valuation_currency)
            or value.allocation_nav.scale != self.total_allocation_nav.scale
            for value in ordered_allocations
        ):
            raise ValueError("StrategyAllocation NAV context mismatch")
        if self.total_allocation_nav.currency != str(self.valuation_currency):
            raise ValueError("total_allocation_nav currency mismatch")
        if sum(value.allocation_nav.units for value in ordered_allocations) != (
            self.total_allocation_nav.units
        ):
            raise ValueError("total_allocation_nav mismatch")
        if any(
            value.target_notional.scale != self.target_notional_scale
            for value in ordered_sleeve_targets
        ):
            raise ValueError("Sleeve target scale mismatch")
        allocation_by_sleeve = {
            (value.strategy_id, value.sleeve_id): value for value in ordered_allocations
        }
        if any(
            allocation_by_sleeve.get((value.strategy_id, value.sleeve_id)) is None
            or allocation_by_sleeve[(value.strategy_id, value.sleeve_id)].allocation_nav
            != value.allocation_nav
            for value in ordered_sleeve_targets
        ):
            raise ValueError("Sleeve target does not match StrategyAllocation")
        expected_by_instrument: dict[InstrumentId, list[SleeveTargetNotional]] = (
            defaultdict(list)
        )
        for value in ordered_sleeve_targets:
            expected_by_instrument[value.instrument_id].append(value)
        expected_net_targets = tuple(
            NetInstrumentTarget(
                instrument_id=instrument_id,
                valuation_currency=self.valuation_currency,
                target_notional=Money(
                    sum(item.target_notional.units for item in values),
                    self.target_notional_scale,
                    str(self.valuation_currency),
                ),
                sleeve_attributions=tuple(values),
            )
            for instrument_id, values in sorted(expected_by_instrument.items())
        )
        if ordered_net_targets != expected_net_targets:
            raise ValueError("net_targets do not match Sleeve attribution")
        schema_version = 2 if self.valuation_instant is not None else 1
        identity_payload = {
            "type": "portfolio_allocation_identity",
            "schema_version": schema_version,
            "valuation_time": self.valuation_time,
            "valuation_currency": self.valuation_currency,
            "target_notional_scale": self.target_notional_scale.places,
            "policy_ref": self.policy_ref,
            "source_sleeve_state_hash": self.source_sleeve_state_hash,
            "source_portfolio_snapshot_hash": self.source_portfolio_snapshot_hash,
            "allocations": ordered_allocations,
            "sleeve_targets": ordered_sleeve_targets,
            "net_targets": ordered_net_targets,
        }
        if self.valuation_instant is not None:
            identity_payload["valuation_instant"] = self.valuation_instant
        expected_id = (
            f"portfolio-allocation-v{schema_version}:"
            f"{canonical_sha256(identity_payload)}"
        )
        if self.allocation_id != expected_id:
            raise ValueError("allocation_id does not match allocation identity")
        object.__setattr__(self, "allocations", ordered_allocations)
        object.__setattr__(self, "sleeve_targets", ordered_sleeve_targets)
        object.__setattr__(self, "net_targets", ordered_net_targets)

    @property
    def allocation_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        value = {
            "type": "portfolio_allocation",
            "allocation_id": self.allocation_id,
            "valuation_time": self.valuation_time,
            "valuation_currency": self.valuation_currency,
            "target_notional_scale": self.target_notional_scale.places,
            "policy_ref": self.policy_ref,
            "source_sleeve_state_hash": self.source_sleeve_state_hash,
            "source_portfolio_snapshot_hash": self.source_portfolio_snapshot_hash,
            "allocations": self.allocations,
            "total_allocation_nav": self.total_allocation_nav,
            "sleeve_targets": self.sleeve_targets,
            "net_targets": self.net_targets,
        }
        if self.valuation_instant is not None:
            value["valuation_instant"] = self.valuation_instant
        return value


@dataclass(frozen=True, slots=True)
class PortfolioAllocationOutcome:
    allocation: PortfolioAllocation | None
    failure: CapitalAllocationFailure | None

    def __post_init__(self) -> None:
        if (self.allocation is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one allocation or failure")
        if self.allocation is not None and not isinstance(
            self.allocation, PortfolioAllocation
        ):
            raise TypeError("allocation must be PortfolioAllocation")
        if self.failure is not None and not isinstance(
            self.failure, CapitalAllocationFailure
        ):
            raise TypeError("failure must be CapitalAllocationFailure")

    @classmethod
    def succeeded(cls, allocation: PortfolioAllocation) -> PortfolioAllocationOutcome:
        return cls(allocation=allocation, failure=None)

    @classmethod
    def failed(cls, failure: CapitalAllocationFailure) -> PortfolioAllocationOutcome:
        return cls(allocation=None, failure=failure)

    def to_canonical_dict(self) -> dict[str, Any]:
        if self.allocation is not None:
            return {
                "type": "portfolio_allocation_outcome",
                "status": "allocated",
                "allocation": self.allocation,
            }
        return {
            "type": "portfolio_allocation_outcome",
            "status": "failed",
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class PortfolioAllocator:
    def allocate(
        self,
        *,
        sleeve_state: LatestSleeveDecisionState,
        portfolio_snapshot: PortfolioSnapshot,
        allocations: tuple[StrategyAllocation, ...],
        target_notional_scale: Scale,
    ) -> PortfolioAllocationOutcome:
        if not isinstance(sleeve_state, LatestSleeveDecisionState):
            raise TypeError("sleeve_state must be LatestSleeveDecisionState")
        if not isinstance(portfolio_snapshot, PortfolioSnapshot):
            raise TypeError("portfolio_snapshot must be PortfolioSnapshot")
        if not isinstance(allocations, tuple) or not all(
            isinstance(value, StrategyAllocation) for value in allocations
        ):
            raise TypeError("allocations must be a tuple of StrategyAllocation")
        if not isinstance(target_notional_scale, Scale):
            raise TypeError("target_notional_scale must be Scale")

        valuation_time = sleeve_state.as_of or portfolio_snapshot.timestamp
        valuation_instant = sleeve_state.as_of_instant
        state_hash = sleeve_state.state_hash
        snapshot_hash = canonical_sha256(portfolio_snapshot)
        issues: list[AllocationConstraintDecision] = []
        if sleeve_state.as_of is None:
            issues.append(
                AllocationConstraintDecision(
                    AllocationConstraintCode.EMPTY_SLEEVE_STATE,
                    "latest_sleeve_decision_state",
                    state_hash,
                )
            )
        elif portfolio_snapshot.timestamp != sleeve_state.as_of:
            issues.append(
                AllocationConstraintDecision(
                    AllocationConstraintCode.VALUATION_TIME_MISMATCH,
                    "portfolio_snapshot",
                    snapshot_hash,
                )
            )
        if portfolio_snapshot.timestamp_instant != valuation_instant:
            issues.append(
                AllocationConstraintDecision(
                    AllocationConstraintCode.VALUATION_INSTANT_MISMATCH,
                    "portfolio_snapshot",
                    snapshot_hash,
                )
            )

        expected = {
            value.target_snapshot.sleeve_id: value for value in sleeve_state.decisions
        }
        by_sleeve: dict[StrategySleeveId, list[StrategyAllocation]] = defaultdict(list)
        for allocation_input in allocations:
            by_sleeve[allocation_input.sleeve_id].append(allocation_input)
            if allocation_input.sleeve_id not in expected:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.UNEXPECTED_ALLOCATION,
                        allocation_input.sleeve_id.value,
                        allocation_input.allocation_hash,
                    )
                )

        valid_allocations: list[StrategyAllocation] = []
        sleeve_targets: list[SleeveTargetNotional] = []
        for sleeve_id, decision in expected.items():
            matching = by_sleeve.get(sleeve_id, [])
            if not matching:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.MISSING_ALLOCATION, sleeve_id.value
                    )
                )
                continue
            if len(matching) > 1:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.DUPLICATE_ALLOCATION, sleeve_id.value
                    )
                )
                continue
            strategy_allocation = matching[0]
            valid_allocations.append(strategy_allocation)
            if strategy_allocation.strategy_id != decision.strategy_id:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.STRATEGY_ID_MISMATCH,
                        sleeve_id.value,
                        strategy_allocation.allocation_hash,
                    )
                )
            if strategy_allocation.valuation_time != valuation_time:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.VALUATION_TIME_MISMATCH,
                        sleeve_id.value,
                        strategy_allocation.allocation_hash,
                    )
                )
            if strategy_allocation.valuation_instant != valuation_instant:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.VALUATION_INSTANT_MISMATCH,
                        sleeve_id.value,
                        strategy_allocation.allocation_hash,
                    )
                )
            if (
                strategy_allocation.valuation_currency
                != portfolio_snapshot.reporting_currency
                or strategy_allocation.allocation_nav.currency
                != str(portfolio_snapshot.reporting_currency)
            ):
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.VALUATION_CURRENCY_MISMATCH,
                        sleeve_id.value,
                        strategy_allocation.allocation_hash,
                    )
                )
            if (
                strategy_allocation.allocation_nav.scale
                != portfolio_snapshot.equity.scale
            ):
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.ALLOCATION_SCALE_MISMATCH,
                        sleeve_id.value,
                        strategy_allocation.allocation_hash,
                    )
                )
            if strategy_allocation.source_portfolio_snapshot_hash != snapshot_hash:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.SNAPSHOT_HASH_MISMATCH,
                        sleeve_id.value,
                        strategy_allocation.allocation_hash,
                    )
                )
            if strategy_allocation.allocation_nav.units < 0:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.NEGATIVE_ALLOCATION_NAV,
                        sleeve_id.value,
                        strategy_allocation.allocation_hash,
                    )
                )

            target_snapshot = decision.target_snapshot
            if target_snapshot.effective_time > valuation_time:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.TARGET_NOT_EFFECTIVE,
                        sleeve_id.value,
                        canonical_sha256(target_snapshot),
                    )
                )
            if (
                target_snapshot.expires_at is not None
                and target_snapshot.expires_at <= valuation_time
            ):
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.TARGET_EXPIRED,
                        sleeve_id.value,
                        canonical_sha256(target_snapshot),
                    )
                )

            for target_fraction in target_snapshot.targets:
                target_units = _exact_product_units(
                    strategy_allocation.allocation_nav.units,
                    strategy_allocation.allocation_nav.scale,
                    target_fraction.units,
                    target_fraction.scale,
                    target_notional_scale,
                )
                if target_units is None:
                    issues.append(
                        AllocationConstraintDecision(
                            AllocationConstraintCode.TARGET_NOTIONAL_INEXACT,
                            f"{sleeve_id.value}:{target_fraction.instrument_id}",
                            canonical_sha256(target_fraction),
                        )
                    )
                    continue
                sleeve_targets.append(
                    SleeveTargetNotional(
                        strategy_id=decision.strategy_id,
                        sleeve_id=sleeve_id,
                        instrument_id=target_fraction.instrument_id,
                        target_fraction=target_fraction,
                        allocation_nav=strategy_allocation.allocation_nav,
                        target_notional=Money(
                            target_units,
                            target_notional_scale,
                            strategy_allocation.allocation_nav.currency,
                        ),
                    )
                )

        policies = {value.policy_ref for value in valid_allocations}
        if len(policies) > 1:
            issues.append(
                AllocationConstraintDecision(
                    AllocationConstraintCode.POLICY_MISMATCH,
                    "capital_allocation_policy",
                    canonical_sha256(tuple(sorted(value.policy_hash for value in policies))),
                )
            )

        nav_context_valid = all(
            value.allocation_nav.units >= 0
            and value.allocation_nav.currency == portfolio_snapshot.equity.currency
            and value.allocation_nav.scale == portfolio_snapshot.equity.scale
            for value in valid_allocations
        )
        if nav_context_valid:
            total_units = sum(value.allocation_nav.units for value in valid_allocations)
            equity_budget = max(portfolio_snapshot.equity.units, 0)
            if total_units > equity_budget:
                issues.append(
                    AllocationConstraintDecision(
                        AllocationConstraintCode.TOTAL_ALLOCATION_EXCEEDS_EQUITY,
                        "portfolio_equity",
                        snapshot_hash,
                    )
                )

        if issues:
            return PortfolioAllocationOutcome.failed(
                CapitalAllocationFailure(
                    valuation_time=valuation_time,
                    source_sleeve_state_hash=state_hash,
                    source_portfolio_snapshot_hash=snapshot_hash,
                    decisions=tuple(issues),
                    valuation_instant=valuation_instant,
                )
            )

        ordered_allocations = tuple(
            sorted(
                valid_allocations,
                key=lambda value: (value.sleeve_id, value.strategy_id),
            )
        )
        ordered_sleeve_targets = tuple(
            sorted(
                sleeve_targets,
                key=lambda value: (
                    value.instrument_id,
                    value.sleeve_id,
                    value.strategy_id,
                ),
            )
        )
        policy_ref = ordered_allocations[0].policy_ref
        total_nav = Money(
            sum(value.allocation_nav.units for value in ordered_allocations),
            portfolio_snapshot.equity.scale,
            str(portfolio_snapshot.reporting_currency),
        )
        by_instrument: dict[InstrumentId, list[SleeveTargetNotional]] = defaultdict(list)
        for sleeve_target in ordered_sleeve_targets:
            by_instrument[sleeve_target.instrument_id].append(sleeve_target)
        net_targets = tuple(
            NetInstrumentTarget(
                instrument_id=instrument_id,
                valuation_currency=portfolio_snapshot.reporting_currency,
                target_notional=Money(
                    sum(value.target_notional.units for value in values),
                    target_notional_scale,
                    str(portfolio_snapshot.reporting_currency),
                ),
                sleeve_attributions=tuple(values),
            )
            for instrument_id, values in sorted(by_instrument.items())
        )
        schema_version = 2 if valuation_instant is not None else 1
        identity_payload = {
            "type": "portfolio_allocation_identity",
            "schema_version": schema_version,
            "valuation_time": valuation_time,
            "valuation_currency": portfolio_snapshot.reporting_currency,
            "target_notional_scale": target_notional_scale.places,
            "policy_ref": policy_ref,
            "source_sleeve_state_hash": state_hash,
            "source_portfolio_snapshot_hash": snapshot_hash,
            "allocations": ordered_allocations,
            "sleeve_targets": ordered_sleeve_targets,
            "net_targets": net_targets,
        }
        if valuation_instant is not None:
            identity_payload["valuation_instant"] = valuation_instant
        portfolio_allocation = PortfolioAllocation(
            allocation_id=(
                f"portfolio-allocation-v{schema_version}:"
                f"{canonical_sha256(identity_payload)}"
            ),
            valuation_time=valuation_time,
            valuation_currency=portfolio_snapshot.reporting_currency,
            target_notional_scale=target_notional_scale,
            policy_ref=policy_ref,
            source_sleeve_state_hash=state_hash,
            source_portfolio_snapshot_hash=snapshot_hash,
            allocations=ordered_allocations,
            total_allocation_nav=total_nav,
            sleeve_targets=ordered_sleeve_targets,
            net_targets=net_targets,
            valuation_instant=valuation_instant,
        )
        return PortfolioAllocationOutcome.succeeded(portfolio_allocation)
