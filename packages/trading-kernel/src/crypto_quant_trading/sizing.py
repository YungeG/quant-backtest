"""Deterministic approved-notional to exact-quantity materialization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from crypto_quant_domain import (
    ActivePortfolioTarget,
    CurrencyId,
    InstrumentId,
    Money,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .marks import ResolvedMark
from .risk import ApprovedInstrumentTarget, ApprovedPortfolioTarget


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_NORMALIZED_TARGET_ID_RE = re.compile(
    r"^normalized-portfolio-target-v1:sha256:[0-9a-f]{64}$"
)


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    valid_digest = isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None
    if not valid_digest:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _integer(name: str, value: int, *, minimum: int = 0) -> None:
    valid_integer = isinstance(value, int) and not isinstance(value, bool)
    if not valid_integer:
        raise TypeError(f"{name} must be an integer")
    if not value >= minimum:
        raise ValueError(f"{name} must be at least {minimum}")


def _signed_multiple_toward_zero(units: int, multiple: int) -> int:
    sign = -1 if units < 0 else 1
    return sign * (abs(units) // multiple) * multiple


class ResidualPositionPolicy(str, Enum):
    HOLD_DUST = "hold_dust"
    CLOSE_IF_PERMITTED = "close_if_permitted"
    FAIL = "fail"


class PositionSizingAction(str, Enum):
    EXACT = "exact"
    ROUNDED_TOWARD_ZERO = "rounded_toward_zero"
    BELOW_MINIMUM_QUANTITY = "below_minimum_quantity"
    BELOW_MINIMUM_NOTIONAL = "below_minimum_notional"
    ODD_LOT_CLOSE = "odd_lot_close"
    SELL_RESIDUAL_COMPONENT = "sell_residual_component"
    RESIDUAL_HELD = "residual_held"


class PositionSizingReasonCode(str, Enum):
    EXACT_LATTICE = "exact_lattice"
    QUANTITY_STEP = "quantity_step"
    BUY_LOT = "buy_lot"
    SELL_LOT = "sell_lot"
    MINIMUM_QUANTITY = "minimum_quantity"
    MINIMUM_NOTIONAL = "minimum_notional"
    ODD_LOT_CLOSE_PERMITTED = "odd_lot_close_permitted"
    SELL_RESIDUAL_COMPONENT_PERMITTED = "sell_residual_component_permitted"
    ODD_LOT_CLOSE_NOT_PERMITTED = "odd_lot_close_not_permitted"
    RESIDUAL_POLICY_HOLD = "residual_policy_hold"


class PositionSizingFailureCode(str, Enum):
    MISSING_POLICY = "missing_policy"
    MISSING_INPUT = "missing_input"
    DUPLICATE_INPUT = "duplicate_input"
    UNEXPECTED_INPUT = "unexpected_input"
    INSTRUMENT_CONTEXT_MISMATCH = "instrument_context_mismatch"
    MARK_TIME_MISMATCH = "mark_time_mismatch"
    PRICE_PURPOSE_MISMATCH = "price_purpose_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    SCALE_MISMATCH = "scale_mismatch"
    INVALID_SIZING_PRICE = "invalid_sizing_price"
    RESIDUAL_NOT_PERMITTED = "residual_not_permitted"
    APPROVED_EXPOSURE_EXCEEDED = "approved_exposure_exceeded"


@dataclass(frozen=True, slots=True)
class PositionSizingPolicy:
    policy_key: str
    policy_version: int
    price_purpose: PricePurpose
    rounding: RoundingPolicy
    residual_policy: ResidualPositionPolicy
    config_hash: str

    def __post_init__(self) -> None:
        _canonical_text("policy_key", self.policy_key)
        _integer("policy_version", self.policy_version, minimum=1)
        if not isinstance(self.price_purpose, PricePurpose):
            raise TypeError("price_purpose must be PricePurpose")
        if not isinstance(self.rounding, RoundingPolicy):
            raise TypeError("rounding must be RoundingPolicy")
        if self.rounding is not RoundingPolicy.TOWARD_ZERO:
            raise ValueError("v1 position sizing rounding must be toward_zero")
        if not isinstance(self.residual_policy, ResidualPositionPolicy):
            raise TypeError("residual_policy must be ResidualPositionPolicy")
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash does not match position sizing policy")

    @classmethod
    def create(
        cls,
        *,
        policy_key: str,
        policy_version: int,
        price_purpose: PricePurpose,
        rounding: RoundingPolicy,
        residual_policy: ResidualPositionPolicy,
    ) -> Self:
        payload = {
            "type": "position_sizing_policy_config",
            "schema_version": 1,
            "policy_key": policy_key,
            "policy_version": policy_version,
            "price_purpose": price_purpose.value,
            "rounding": rounding.value,
            "residual_policy": residual_policy.value,
        }
        return cls(
            policy_key=policy_key,
            policy_version=policy_version,
            price_purpose=price_purpose,
            rounding=rounding,
            residual_policy=residual_policy,
            config_hash=canonical_sha256(payload),
        )

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "position_sizing_policy_config",
            "schema_version": 1,
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "price_purpose": self.price_purpose.value,
            "rounding": self.rounding.value,
            "residual_policy": self.residual_policy.value,
        }

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "position_sizing_policy",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class QuantityLattice:
    instrument_id: InstrumentId
    lattice_key: str
    lattice_version: int
    atomic_scale: Scale
    step_units: int
    buy_lot_units: int | None
    sell_lot_units: int | None
    min_quantity_units: int
    min_notional: Money
    odd_lot_close_permitted: bool
    config_hash: str
    whole_sell_residual_permitted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        _canonical_text("lattice_key", self.lattice_key)
        _integer("lattice_version", self.lattice_version, minimum=1)
        if not isinstance(self.atomic_scale, Scale):
            raise TypeError("atomic_scale must be Scale")
        _integer("step_units", self.step_units, minimum=1)
        for name, value in (
            ("buy_lot_units", self.buy_lot_units),
            ("sell_lot_units", self.sell_lot_units),
        ):
            if value is not None:
                _integer(name, value, minimum=1)
                if value % self.step_units:
                    raise ValueError(f"{name} must be a multiple of step_units")
        _integer("min_quantity_units", self.min_quantity_units)
        if self.min_quantity_units % self.step_units:
            raise ValueError("min_quantity_units must be a multiple of step_units")
        if not isinstance(self.min_notional, Money):
            raise TypeError("min_notional must be Money")
        if self.min_notional.units < 0:
            raise ValueError("min_notional cannot be negative")
        if not isinstance(self.odd_lot_close_permitted, bool):
            raise TypeError("odd_lot_close_permitted must be bool")
        if not isinstance(self.whole_sell_residual_permitted, bool):
            raise TypeError("whole_sell_residual_permitted must be bool")
        if self.whole_sell_residual_permitted and (
            self.sell_lot_units is None
            or not self.odd_lot_close_permitted
            or self.min_quantity_units != 0
            or self.min_notional.units != 0
        ):
            raise ValueError(
                "whole sell residual requires sell lot, odd close, and zero minimums"
            )
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash does not match quantity lattice")

    @classmethod
    def create(
        cls,
        *,
        instrument_id: InstrumentId,
        lattice_key: str,
        lattice_version: int,
        atomic_scale: Scale,
        step_units: int,
        buy_lot_units: int | None,
        sell_lot_units: int | None,
        min_quantity_units: int,
        min_notional: Money,
        odd_lot_close_permitted: bool,
        whole_sell_residual_permitted: bool = False,
    ) -> Self:
        payload = {
            "type": "quantity_lattice_config",
            "schema_version": 2 if whole_sell_residual_permitted else 1,
            "instrument_id": instrument_id,
            "lattice_key": lattice_key,
            "lattice_version": lattice_version,
            "atomic_scale": atomic_scale.places,
            "step_units": step_units,
            "buy_lot_units": buy_lot_units,
            "sell_lot_units": sell_lot_units,
            "min_quantity_units": min_quantity_units,
            "min_notional": min_notional,
            "odd_lot_close_permitted": odd_lot_close_permitted,
        }
        if whole_sell_residual_permitted:
            payload["whole_sell_residual_permitted"] = True
        return cls(
            instrument_id=instrument_id,
            lattice_key=lattice_key,
            lattice_version=lattice_version,
            atomic_scale=atomic_scale,
            step_units=step_units,
            buy_lot_units=buy_lot_units,
            sell_lot_units=sell_lot_units,
            min_quantity_units=min_quantity_units,
            min_notional=min_notional,
            odd_lot_close_permitted=odd_lot_close_permitted,
            config_hash=canonical_sha256(payload),
            whole_sell_residual_permitted=whole_sell_residual_permitted,
        )

    def config_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "quantity_lattice_config",
            "schema_version": 2 if self.whole_sell_residual_permitted else 1,
            "instrument_id": self.instrument_id,
            "lattice_key": self.lattice_key,
            "lattice_version": self.lattice_version,
            "atomic_scale": self.atomic_scale.places,
            "step_units": self.step_units,
            "buy_lot_units": self.buy_lot_units,
            "sell_lot_units": self.sell_lot_units,
            "min_quantity_units": self.min_quantity_units,
            "min_notional": self.min_notional,
            "odd_lot_close_permitted": self.odd_lot_close_permitted,
        }
        if self.whole_sell_residual_permitted:
            payload["whole_sell_residual_permitted"] = True
        return payload

    @property
    def lattice_hash(self) -> str:
        return canonical_sha256(self)

    def lot_units_for_target(self, units: int) -> int:
        if units > 0:
            return self.buy_lot_units or self.step_units
        if units < 0:
            return self.sell_lot_units or self.step_units
        return self.step_units

    def lot_units_for_close(self, current_units: int) -> int:
        if current_units > 0:
            return self.sell_lot_units or self.step_units
        if current_units < 0:
            return self.buy_lot_units or self.step_units
        return self.step_units

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "quantity_lattice",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class InstrumentSizingInput:
    instrument_id: InstrumentId
    mark: ResolvedMark
    current_quantity: Quantity
    lattice: QuantityLattice

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.mark, ResolvedMark):
            raise TypeError("mark must be ResolvedMark")
        if not isinstance(self.current_quantity, Quantity):
            raise TypeError("current_quantity must be Quantity")
        if not isinstance(self.lattice, QuantityLattice):
            raise TypeError("lattice must be QuantityLattice")
        if (
            self.mark.instrument_id != self.instrument_id
            or self.lattice.instrument_id != self.instrument_id
            or self.current_quantity.instrument_id != str(self.instrument_id)
        ):
            raise ValueError("InstrumentSizingInput instrument identity mismatch")
        if self.current_quantity.scale != self.lattice.atomic_scale:
            raise ValueError("current_quantity scale must match lattice atomic_scale")

    @property
    def input_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "instrument_sizing_input",
            "instrument_id": self.instrument_id,
            "mark": self.mark,
            "current_quantity": self.current_quantity,
            "lattice": self.lattice,
        }


@dataclass(frozen=True, slots=True)
class PositionSizingDecision:
    instrument_id: InstrumentId
    approved_notional: Money
    current_quantity: Quantity
    raw_quantity: Quantity
    final_quantity: Quantity
    residual_quantity: Quantity
    final_notional: Money
    applied_lot_units: int
    actions: tuple[PositionSizingAction, ...]
    reason_codes: tuple[PositionSizingReasonCode, ...]
    mark_id: str
    lattice_hash: str
    policy_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.approved_notional, Money) or not isinstance(
            self.final_notional, Money
        ):
            raise TypeError("approved_notional and final_notional must be Money")
        quantities = (
            self.current_quantity,
            self.raw_quantity,
            self.final_quantity,
            self.residual_quantity,
        )
        if not all(isinstance(value, Quantity) for value in quantities):
            raise TypeError("sizing quantities must be Quantity")
        if any(value.instrument_id != str(self.instrument_id) for value in quantities):
            raise ValueError("sizing decision quantity identity mismatch")
        if len({value.scale for value in quantities}) != 1:
            raise ValueError("sizing decision quantity scale mismatch")
        if self.residual_quantity.units != (
            self.raw_quantity.units - self.final_quantity.units
        ):
            raise ValueError("residual_quantity must equal raw minus final")
        if (
            self.approved_notional.currency != self.final_notional.currency
            or self.approved_notional.scale != self.final_notional.scale
        ):
            raise ValueError("sizing decision notional context mismatch")
        _integer("applied_lot_units", self.applied_lot_units, minimum=1)
        if not isinstance(self.actions, tuple) or not self.actions:
            raise ValueError("actions must be a non-empty tuple")
        if not all(isinstance(value, PositionSizingAction) for value in self.actions):
            raise TypeError("actions must contain PositionSizingAction")
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("reason_codes must be a non-empty tuple")
        if not all(
            isinstance(value, PositionSizingReasonCode) for value in self.reason_codes
        ):
            raise TypeError("reason_codes must contain PositionSizingReasonCode")
        actions = tuple(sorted(set(self.actions), key=lambda value: value.value))
        reasons = tuple(sorted(set(self.reason_codes), key=lambda value: value.value))
        _require_hash("mark_id", self.mark_id)
        _require_hash("lattice_hash", self.lattice_hash)
        _require_hash("policy_hash", self.policy_hash)
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "reason_codes", reasons)

    @property
    def decision_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_sizing_decision",
            "instrument_id": self.instrument_id,
            "approved_notional": self.approved_notional,
            "current_quantity": self.current_quantity,
            "raw_quantity": self.raw_quantity,
            "final_quantity": self.final_quantity,
            "residual_quantity": self.residual_quantity,
            "final_notional": self.final_notional,
            "applied_lot_units": self.applied_lot_units,
            "actions": [value.value for value in self.actions],
            "reason_codes": [value.value for value in self.reason_codes],
            "mark_id": self.mark_id,
            "lattice_hash": self.lattice_hash,
            "policy_hash": self.policy_hash,
        }


@dataclass(frozen=True, slots=True)
class NormalizedInstrumentTarget:
    source_target: ApprovedInstrumentTarget
    sizing_input: InstrumentSizingInput
    decision: PositionSizingDecision

    def __post_init__(self) -> None:
        if not isinstance(self.source_target, ApprovedInstrumentTarget):
            raise TypeError("source_target must be ApprovedInstrumentTarget")
        if not isinstance(self.sizing_input, InstrumentSizingInput):
            raise TypeError("sizing_input must be InstrumentSizingInput")
        if not isinstance(self.decision, PositionSizingDecision):
            raise TypeError("decision must be PositionSizingDecision")
        instrument_id = self.source_target.source_target.instrument_id
        if (
            self.sizing_input.instrument_id != instrument_id
            or self.decision.instrument_id != instrument_id
            or self.decision.approved_notional != self.source_target.approved_notional
            or self.decision.current_quantity != self.sizing_input.current_quantity
            or self.decision.mark_id != self.sizing_input.mark.mark_id
            or self.decision.lattice_hash != self.sizing_input.lattice.lattice_hash
        ):
            raise ValueError("normalized target provenance mismatch")
        expected_notional = self.sizing_input.mark.price.notional(
            self.decision.final_quantity,
            result_scale=self.decision.approved_notional.scale,
            rounding=RoundingPolicy.TOWARD_ZERO,
        )
        if self.decision.final_notional != expected_notional:
            raise ValueError("normalized target final notional mismatch")
        if (
            abs(expected_notional.units) > abs(self.decision.approved_notional.units)
            and PositionSizingAction.RESIDUAL_HELD not in self.decision.actions
        ):
            raise ValueError("normalized target exceeds approved exposure")

    @property
    def instrument_id(self) -> InstrumentId:
        return self.decision.instrument_id

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "normalized_instrument_target",
            "source_target": self.source_target,
            "sizing_input": self.sizing_input,
            "decision": self.decision,
        }


@dataclass(frozen=True, slots=True)
class NormalizedPortfolioTarget:
    normalized_target_id: str
    source_decision_batch_id: str
    materialized_at: UtcInstant
    source_approved_target_id: str
    source_approved_target_hash: str
    policy: PositionSizingPolicy
    targets: tuple[NormalizedInstrumentTarget, ...]
    active_target: ActivePortfolioTarget

    def __post_init__(self) -> None:
        if (
            not isinstance(self.normalized_target_id, str)
            or _NORMALIZED_TARGET_ID_RE.fullmatch(self.normalized_target_id) is None
        ):
            raise ValueError("normalized_target_id must be a normalized target identity")
        _canonical_text("source_decision_batch_id", self.source_decision_batch_id)
        if not isinstance(self.materialized_at, UtcInstant):
            raise TypeError("materialized_at must be UtcInstant")
        _canonical_text("source_approved_target_id", self.source_approved_target_id)
        _require_hash("source_approved_target_hash", self.source_approved_target_hash)
        if not isinstance(self.policy, PositionSizingPolicy):
            raise TypeError("policy must be PositionSizingPolicy")
        if not isinstance(self.targets, tuple) or not all(
            isinstance(value, NormalizedInstrumentTarget) for value in self.targets
        ):
            raise TypeError("targets must contain NormalizedInstrumentTarget")
        if not isinstance(self.active_target, ActivePortfolioTarget):
            raise TypeError("active_target must be ActivePortfolioTarget")
        targets = tuple(sorted(self.targets, key=lambda value: value.instrument_id))
        if len({value.instrument_id for value in targets}) != len(targets):
            raise ValueError("duplicate normalized Instrument target")
        if self.active_target.source_decision_batch_id != self.source_decision_batch_id:
            raise ValueError("active target source DecisionBatch mismatch")
        if self.active_target.materialized_at != self.materialized_at:
            raise ValueError("active target materialization time mismatch")
        expected_quantities = tuple(
            (value.instrument_id, value.decision.final_quantity) for value in targets
        )
        if self.active_target.quantities != expected_quantities:
            raise ValueError("active target quantities do not match normalized targets")
        if any(value.decision.policy_hash != self.policy.policy_hash for value in targets):
            raise ValueError("normalized target policy mismatch")
        identity_payload = self._identity_payload(targets)
        expected_id = f"normalized-portfolio-target-v1:{canonical_sha256(identity_payload)}"
        if self.normalized_target_id != expected_id:
            raise ValueError("normalized_target_id does not match materialization identity")
        object.__setattr__(self, "targets", targets)

    @classmethod
    def create(
        cls,
        *,
        source_decision_batch_id: str,
        approved_target: ApprovedPortfolioTarget,
        policy: PositionSizingPolicy,
        targets: tuple[NormalizedInstrumentTarget, ...],
    ) -> Self:
        targets = tuple(sorted(targets, key=lambda value: value.instrument_id))
        active_target = ActivePortfolioTarget(
            source_decision_batch_id=source_decision_batch_id,
            materialized_at=approved_target.approved_at,
            quantities=tuple(
                (value.instrument_id, value.decision.final_quantity) for value in targets
            ),
        )
        identity_payload = {
            "type": "normalized_portfolio_target_identity",
            "schema_version": 1,
            "source_decision_batch_id": source_decision_batch_id,
            "materialized_at": approved_target.approved_at,
            "source_approved_target_id": approved_target.approved_target_id,
            "source_approved_target_hash": approved_target.approved_target_hash,
            "policy": policy,
            "targets": targets,
            "active_target": active_target,
        }
        return cls(
            normalized_target_id=(
                "normalized-portfolio-target-v1:"
                f"{canonical_sha256(identity_payload)}"
            ),
            source_decision_batch_id=source_decision_batch_id,
            materialized_at=approved_target.approved_at,
            source_approved_target_id=approved_target.approved_target_id,
            source_approved_target_hash=approved_target.approved_target_hash,
            policy=policy,
            targets=targets,
            active_target=active_target,
        )

    def _identity_payload(
        self, targets: tuple[NormalizedInstrumentTarget, ...]
    ) -> dict[str, Any]:
        return {
            "type": "normalized_portfolio_target_identity",
            "schema_version": 1,
            "source_decision_batch_id": self.source_decision_batch_id,
            "materialized_at": self.materialized_at,
            "source_approved_target_id": self.source_approved_target_id,
            "source_approved_target_hash": self.source_approved_target_hash,
            "policy": self.policy,
            "targets": targets,
            "active_target": self.active_target,
        }

    @property
    def normalized_target_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self._identity_payload(self.targets),
            "type": "normalized_portfolio_target",
            "normalized_target_id": self.normalized_target_id,
        }


@dataclass(frozen=True, slots=True)
class PositionSizingFailure:
    code: PositionSizingFailureCode
    subject_keys: tuple[str, ...]
    source_approved_target_id: str
    source_approved_target_hash: str
    policy_hash: str | None
    evidence_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.code, PositionSizingFailureCode):
            raise TypeError("code must be PositionSizingFailureCode")
        if not isinstance(self.subject_keys, tuple) or not self.subject_keys:
            raise ValueError("subject_keys must be a non-empty tuple")
        for value in self.subject_keys:
            _canonical_text("subject_key", value)
        _canonical_text("source_approved_target_id", self.source_approved_target_id)
        _require_hash("source_approved_target_hash", self.source_approved_target_hash)
        if self.policy_hash is not None:
            _require_hash("policy_hash", self.policy_hash)
        if not isinstance(self.evidence_hashes, tuple):
            raise TypeError("evidence_hashes must be a tuple")
        for value in self.evidence_hashes:
            _require_hash("evidence_hash", value)
        object.__setattr__(self, "subject_keys", tuple(sorted(set(self.subject_keys))))
        object.__setattr__(
            self, "evidence_hashes", tuple(sorted(set(self.evidence_hashes)))
        )

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_sizing_failure",
            "code": self.code.value,
            "subject_keys": list(self.subject_keys),
            "source_approved_target_id": self.source_approved_target_id,
            "source_approved_target_hash": self.source_approved_target_hash,
            "policy_hash": self.policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
        }


@dataclass(frozen=True, slots=True)
class PositionSizingOutcome:
    normalized_target: NormalizedPortfolioTarget | None
    failure: PositionSizingFailure | None

    def __post_init__(self) -> None:
        if (self.normalized_target is None) == (self.failure is None):
            raise ValueError("PositionSizingOutcome requires exactly one result")
        if self.normalized_target is not None and not isinstance(
            self.normalized_target, NormalizedPortfolioTarget
        ):
            raise TypeError("normalized_target must be NormalizedPortfolioTarget")
        if self.failure is not None and not isinstance(
            self.failure, PositionSizingFailure
        ):
            raise TypeError("failure must be PositionSizingFailure")

    @classmethod
    def succeeded(cls, value: NormalizedPortfolioTarget) -> Self:
        return cls(normalized_target=value, failure=None)

    @classmethod
    def failed(cls, failure: PositionSizingFailure) -> Self:
        return cls(normalized_target=None, failure=failure)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_sizing_outcome",
            "normalized_target": self.normalized_target,
            "failure": self.failure,
        }


class PositionSizer:
    def materialize(
        self,
        *,
        approved_target: ApprovedPortfolioTarget,
        source_decision_batch_id: str,
        policy: PositionSizingPolicy | None,
        inputs: tuple[InstrumentSizingInput, ...],
    ) -> PositionSizingOutcome:
        if not isinstance(approved_target, ApprovedPortfolioTarget):
            raise TypeError("approved_target must be ApprovedPortfolioTarget")
        _canonical_text("source_decision_batch_id", source_decision_batch_id)
        if not isinstance(inputs, tuple) or not all(
            isinstance(value, InstrumentSizingInput) for value in inputs
        ):
            raise TypeError("inputs must contain InstrumentSizingInput")
        if policy is None:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.MISSING_POLICY,
                ("position_sizing_policy",),
                None,
                (),
            )
        if not isinstance(policy, PositionSizingPolicy):
            raise TypeError("policy must be PositionSizingPolicy or None")

        expected = {
            value.source_target.instrument_id for value in approved_target.targets
        }
        input_ids = [value.instrument_id for value in inputs]
        duplicates = sorted(
            {value for value in input_ids if input_ids.count(value) > 1}
        )
        if duplicates:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.DUPLICATE_INPUT,
                tuple(map(str, duplicates)),
                policy,
                tuple(value.input_hash for value in inputs),
            )
        actual = set(input_ids)
        missing = sorted(expected - actual)
        if missing:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.MISSING_INPUT,
                tuple(map(str, missing)),
                policy,
                tuple(value.input_hash for value in inputs),
            )
        unexpected = sorted(actual - expected)
        if unexpected:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.UNEXPECTED_INPUT,
                tuple(map(str, unexpected)),
                policy,
                tuple(value.input_hash for value in inputs),
            )

        by_instrument = {value.instrument_id: value for value in inputs}
        normalized: list[NormalizedInstrumentTarget] = []
        for approved_instrument in approved_target.targets:
            instrument_id = approved_instrument.source_target.instrument_id
            sizing_input = by_instrument[instrument_id]
            failure = self._validate_context(
                approved_target, approved_instrument, sizing_input, policy
            )
            if failure is not None:
                return failure
            result = self._size_one(approved_instrument, sizing_input, policy)
            if isinstance(result, PositionSizingFailureCode):
                return self._failed(
                    approved_target,
                    result,
                    (str(instrument_id),),
                    policy,
                    (sizing_input.input_hash,),
                )
            normalized.append(result)

        return PositionSizingOutcome.succeeded(
            NormalizedPortfolioTarget.create(
                source_decision_batch_id=source_decision_batch_id,
                approved_target=approved_target,
                policy=policy,
                targets=tuple(normalized),
            )
        )

    def _validate_context(
        self,
        approved_target: ApprovedPortfolioTarget,
        approved_instrument: ApprovedInstrumentTarget,
        sizing_input: InstrumentSizingInput,
        policy: PositionSizingPolicy,
    ) -> PositionSizingOutcome | None:
        instrument_id = approved_instrument.source_target.instrument_id
        if sizing_input.instrument_id != instrument_id:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.INSTRUMENT_CONTEXT_MISMATCH,
                (str(instrument_id),),
                policy,
                (sizing_input.input_hash,),
            )
        if sizing_input.mark.resolved_at != approved_target.approved_at:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.MARK_TIME_MISMATCH,
                (str(instrument_id),),
                policy,
                (sizing_input.mark.mark_id,),
            )
        if sizing_input.mark.price.units <= 0:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.INVALID_SIZING_PRICE,
                (str(instrument_id),),
                policy,
                (sizing_input.mark.mark_id,),
            )
        if sizing_input.mark.price_purpose is not policy.price_purpose:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.PRICE_PURPOSE_MISMATCH,
                (str(instrument_id),),
                policy,
                (sizing_input.mark.mark_id,),
            )
        approved_notional = approved_instrument.approved_notional
        if (
            approved_notional.currency != str(sizing_input.mark.quote_currency_id)
            or sizing_input.lattice.min_notional.currency
            != approved_notional.currency
        ):
            return self._failed(
                approved_target,
                PositionSizingFailureCode.CURRENCY_MISMATCH,
                (str(instrument_id),),
                policy,
                (sizing_input.input_hash,),
            )
        if sizing_input.lattice.min_notional.scale != approved_notional.scale:
            return self._failed(
                approved_target,
                PositionSizingFailureCode.SCALE_MISMATCH,
                (str(instrument_id),),
                policy,
                (sizing_input.input_hash,),
            )
        return None

    def _size_one(
        self,
        approved: ApprovedInstrumentTarget,
        sizing_input: InstrumentSizingInput,
        policy: PositionSizingPolicy,
    ) -> NormalizedInstrumentTarget | PositionSizingFailureCode:
        instrument_id = sizing_input.instrument_id
        lattice = sizing_input.lattice
        raw = approved.approved_notional.quantity_at(
            sizing_input.mark.price,
            result_scale=lattice.atomic_scale,
            rounding=policy.rounding,
        )
        current_units = sizing_input.current_quantity.units
        used_sell_residual = False
        position_relative = (
            lattice.whole_sell_residual_permitted
            and current_units >= 0
            and raw.units >= 0
        )
        if position_relative:
            if current_units == raw.units:
                lot_units = lattice.step_units
                final_units = raw.units
            elif raw.units == 0:
                lot_units = lattice.sell_lot_units or lattice.step_units
                final_units = 0
            elif raw.units > current_units:
                lot_units = lattice.buy_lot_units or lattice.step_units
                final_units = current_units + (
                    (raw.units - current_units) // lot_units
                ) * lot_units
            else:
                lot_units = lattice.sell_lot_units or lattice.step_units
                residual_units = current_units % lot_units
                candidates = [(raw.units // lot_units) * lot_units]
                if raw.units >= residual_units:
                    candidates.append(
                        residual_units
                        + ((raw.units - residual_units) // lot_units) * lot_units
                    )
                final_units = max(candidates)
                sold_units = current_units - final_units
                used_sell_residual = (
                    final_units != 0
                    and residual_units > 0
                    and sold_units % lot_units == residual_units
                )
        else:
            lot_units = lattice.lot_units_for_target(raw.units)
            final_units = _signed_multiple_toward_zero(raw.units, lot_units)

        buy_lot_reason = (
            raw.units > current_units if position_relative else raw.units > 0
        )
        actions: list[PositionSizingAction] = []
        reasons: list[PositionSizingReasonCode] = []
        if final_units == raw.units:
            actions.append(PositionSizingAction.EXACT)
            reasons.append(PositionSizingReasonCode.EXACT_LATTICE)
        else:
            actions.append(PositionSizingAction.ROUNDED_TOWARD_ZERO)
            reasons.extend(
                (
                    PositionSizingReasonCode.QUANTITY_STEP,
                    PositionSizingReasonCode.BUY_LOT
                    if buy_lot_reason
                    else PositionSizingReasonCode.SELL_LOT,
                )
            )

        candidate = Quantity(final_units, lattice.atomic_scale, str(instrument_id))
        candidate_notional = sizing_input.mark.price.notional(
            candidate,
            result_scale=approved.approved_notional.scale,
            rounding=policy.rounding,
        )
        if final_units and abs(final_units) < lattice.min_quantity_units:
            actions.append(PositionSizingAction.BELOW_MINIMUM_QUANTITY)
            reasons.append(PositionSizingReasonCode.MINIMUM_QUANTITY)
            final_units = 0
        if candidate.units and abs(candidate_notional.units) < lattice.min_notional.units:
            actions.append(PositionSizingAction.BELOW_MINIMUM_NOTIONAL)
            reasons.append(PositionSizingReasonCode.MINIMUM_NOTIONAL)
            final_units = 0

        if final_units == 0 and current_units != 0:
            close_lot = lattice.lot_units_for_close(current_units)
            odd_close = abs(current_units) % close_lot != 0
            if odd_close:
                lot_units = close_lot
                if lattice.odd_lot_close_permitted:
                    actions.append(PositionSizingAction.ODD_LOT_CLOSE)
                    reasons.append(PositionSizingReasonCode.ODD_LOT_CLOSE_PERMITTED)
                elif policy.residual_policy is ResidualPositionPolicy.FAIL:
                    return PositionSizingFailureCode.RESIDUAL_NOT_PERMITTED
                else:
                    final_units = current_units
                    actions.append(PositionSizingAction.RESIDUAL_HELD)
                    reasons.extend(
                        (
                            PositionSizingReasonCode.ODD_LOT_CLOSE_NOT_PERMITTED,
                            PositionSizingReasonCode.RESIDUAL_POLICY_HOLD,
                        )
                    )
        if used_sell_residual:
            actions.append(PositionSizingAction.SELL_RESIDUAL_COMPONENT)
            reasons.append(
                PositionSizingReasonCode.SELL_RESIDUAL_COMPONENT_PERMITTED
            )

        final = Quantity(final_units, lattice.atomic_scale, str(instrument_id))
        residual = Quantity(
            raw.units - final.units,
            lattice.atomic_scale,
            str(instrument_id),
        )
        if residual.units and policy.residual_policy is ResidualPositionPolicy.FAIL:
            return PositionSizingFailureCode.RESIDUAL_NOT_PERMITTED
        final_notional = sizing_input.mark.price.notional(
            final,
            result_scale=approved.approved_notional.scale,
            rounding=policy.rounding,
        )
        if (
            abs(final_notional.units) > abs(approved.approved_notional.units)
            and PositionSizingAction.RESIDUAL_HELD not in actions
        ):
            return PositionSizingFailureCode.APPROVED_EXPOSURE_EXCEEDED
        decision = PositionSizingDecision(
            instrument_id=instrument_id,
            approved_notional=approved.approved_notional,
            current_quantity=sizing_input.current_quantity,
            raw_quantity=raw,
            final_quantity=final,
            residual_quantity=residual,
            final_notional=final_notional,
            applied_lot_units=lot_units,
            actions=tuple(actions),
            reason_codes=tuple(reasons),
            mark_id=sizing_input.mark.mark_id,
            lattice_hash=lattice.lattice_hash,
            policy_hash=policy.policy_hash,
        )
        return NormalizedInstrumentTarget(
            source_target=approved,
            sizing_input=sizing_input,
            decision=decision,
        )

    @staticmethod
    def _failed(
        approved_target: ApprovedPortfolioTarget,
        code: PositionSizingFailureCode,
        subject_keys: tuple[str, ...],
        policy: PositionSizingPolicy | None,
        evidence_hashes: tuple[str, ...],
    ) -> PositionSizingOutcome:
        return PositionSizingOutcome.failed(
            PositionSizingFailure(
                code=code,
                subject_keys=subject_keys,
                source_approved_target_id=approved_target.approved_target_id,
                source_approved_target_hash=approved_target.approved_target_hash,
                policy_hash=policy.policy_hash if policy is not None else None,
                evidence_hashes=evidence_hashes,
            )
        )


__all__ = [
    "InstrumentSizingInput",
    "NormalizedInstrumentTarget",
    "NormalizedPortfolioTarget",
    "PositionSizer",
    "PositionSizingAction",
    "PositionSizingDecision",
    "PositionSizingFailure",
    "PositionSizingFailureCode",
    "PositionSizingOutcome",
    "PositionSizingPolicy",
    "PositionSizingReasonCode",
    "QuantityLattice",
    "ResidualPositionPolicy",
]
