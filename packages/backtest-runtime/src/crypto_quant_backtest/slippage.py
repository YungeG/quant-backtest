from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from crypto_quant_domain import (
    InstrumentId,
    OrderSide,
    Price,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import ResolvedMark

from .ports import (
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortSpec,
    SimulationPortType,
)


_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_CHECKED_DIMENSIONS: tuple[SlippageApplicabilityDimension, ...]


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be nonempty without surrounding whitespace")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be canonical NFC text")
    return value


def _positive_integer(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _require_hash(name: str, value: object) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")
    return value


def _round_ratio(numerator: int, denominator: int, policy: RoundingPolicy) -> int:
    if denominator <= 0:
        raise ValueError("rounding denominator must be positive")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    truncated = sign * quotient
    if remainder == 0 or policy is RoundingPolicy.TOWARD_ZERO:
        return truncated
    if policy is RoundingPolicy.AWAY_FROM_ZERO:
        return sign * (quotient + 1)
    if policy is RoundingPolicy.FLOOR:
        return truncated - 1 if sign < 0 else truncated
    if policy is RoundingPolicy.CEILING:
        return truncated + 1 if sign > 0 else truncated
    doubled = remainder * 2
    if doubled < denominator:
        magnitude = quotient
    elif doubled > denominator:
        magnitude = quotient + 1
    elif policy is RoundingPolicy.HALF_EVEN:
        magnitude = quotient if quotient % 2 == 0 else quotient + 1
    elif policy is RoundingPolicy.HALF_UP:
        magnitude = quotient + 1
    else:  # pragma: no cover - enum exhaustiveness guard
        raise AssertionError(f"unhandled rounding policy: {policy}")
    return sign * magnitude


class SlippageModelKind(str, Enum):
    DETERMINISTIC_BPS_V1 = "deterministic_bps.v1"
    ZERO_SLIPPAGE_DEVELOPMENT_V1 = "zero_slippage.development.v1"


class SlippageLimitation(str, Enum):
    ZERO_SLIPPAGE_DEVELOPMENT_ONLY = "zero_slippage_development_only"


class SlippageApplicabilityDimension(str, Enum):
    INSTRUMENT = "instrument"
    TIME_WINDOW = "time_window"
    QUANTITY = "quantity"
    MARKET_STATE = "market_state"
    EXECUTION_PRICE_POSITIVE = "execution_price_positive"


_CHECKED_DIMENSIONS = (
    SlippageApplicabilityDimension.INSTRUMENT,
    SlippageApplicabilityDimension.TIME_WINDOW,
    SlippageApplicabilityDimension.QUANTITY,
    SlippageApplicabilityDimension.MARKET_STATE,
)


@dataclass(frozen=True, slots=True)
class SlippageCalibrationRef:
    calibration_key: str
    calibration_version: int
    calibration_digest: str

    def __post_init__(self) -> None:
        _canonical_text("calibration_key", self.calibration_key)
        _positive_integer("calibration_version", self.calibration_version)
        _require_hash("calibration_digest", self.calibration_digest)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "slippage_calibration_ref",
            "calibration_key": self.calibration_key,
            "calibration_version": self.calibration_version,
            "calibration_digest": self.calibration_digest,
        }


@dataclass(frozen=True, slots=True)
class SlippageApplicabilityEnvelope:
    envelope_key: str
    envelope_version: int
    instrument_id: InstrumentId
    valid_from: UtcInstant
    valid_to_exclusive: UtcInstant
    maximum_quantity: Quantity
    allowed_market_state_keys: tuple[str, ...]
    config_hash: str

    def __post_init__(self) -> None:
        _canonical_text("envelope_key", self.envelope_key)
        _positive_integer("envelope_version", self.envelope_version)
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.valid_from, UtcInstant) or not isinstance(
            self.valid_to_exclusive, UtcInstant
        ):
            raise TypeError("validity bounds must be UtcInstant")
        if self.valid_to_exclusive <= self.valid_from:
            raise ValueError("valid_to_exclusive must be after valid_from")
        if not isinstance(self.maximum_quantity, Quantity):
            raise TypeError("maximum_quantity must be Quantity")
        if self.maximum_quantity.units <= 0:
            raise ValueError("maximum_quantity must be positive")
        if self.maximum_quantity.instrument_id != str(self.instrument_id):
            raise ValueError("maximum_quantity instrument identity mismatch")
        if type(self.allowed_market_state_keys) is not tuple:
            raise TypeError("allowed_market_state_keys must be tuple")
        if not self.allowed_market_state_keys:
            raise ValueError("allowed_market_state_keys must be nonempty")
        states = tuple(
            sorted(
                _canonical_text("allowed market state key", value)
                for value in self.allowed_market_state_keys
            )
        )
        if len(states) != len(set(states)):
            raise ValueError("duplicate allowed market state key")
        object.__setattr__(self, "allowed_market_state_keys", states)
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash does not match slippage applicability envelope")

    @classmethod
    def create(
        cls,
        *,
        envelope_key: str,
        envelope_version: int,
        instrument_id: InstrumentId,
        valid_from: UtcInstant,
        valid_to_exclusive: UtcInstant,
        maximum_quantity: Quantity,
        allowed_market_state_keys: tuple[str, ...],
    ) -> Self:
        states = tuple(sorted(allowed_market_state_keys))
        payload = {
            "type": "slippage_applicability_envelope_config",
            "schema_version": 1,
            "envelope_key": envelope_key,
            "envelope_version": envelope_version,
            "instrument_id": instrument_id,
            "valid_from": valid_from,
            "valid_to_exclusive": valid_to_exclusive,
            "maximum_quantity": maximum_quantity,
            "allowed_market_state_keys": list(states),
        }
        return cls(
            envelope_key=envelope_key,
            envelope_version=envelope_version,
            instrument_id=instrument_id,
            valid_from=valid_from,
            valid_to_exclusive=valid_to_exclusive,
            maximum_quantity=maximum_quantity,
            allowed_market_state_keys=states,
            config_hash=canonical_sha256(payload),
        )

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "slippage_applicability_envelope_config",
            "schema_version": 1,
            "envelope_key": self.envelope_key,
            "envelope_version": self.envelope_version,
            "instrument_id": self.instrument_id,
            "valid_from": self.valid_from,
            "valid_to_exclusive": self.valid_to_exclusive,
            "maximum_quantity": self.maximum_quantity,
            "allowed_market_state_keys": list(self.allowed_market_state_keys),
        }

    @property
    def envelope_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "slippage_applicability_envelope",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class SlippageMarketState:
    state_key: str
    observed_at: UtcInstant
    available_at: UtcInstant
    source_event_id: str
    revision_id: str
    evidence_hash: str

    def __post_init__(self) -> None:
        _canonical_text("state_key", self.state_key)
        if not isinstance(self.observed_at, UtcInstant) or not isinstance(
            self.available_at, UtcInstant
        ):
            raise TypeError("market-state times must be UtcInstant")
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        _canonical_text("source_event_id", self.source_event_id)
        _canonical_text("revision_id", self.revision_id)
        _require_hash("evidence_hash", self.evidence_hash)

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "slippage_market_state",
            "state_key": self.state_key,
            "observed_at": self.observed_at,
            "available_at": self.available_at,
            "source_event_id": self.source_event_id,
            "revision_id": self.revision_id,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True, slots=True)
class ExecutionReferencePrice:
    mark: ResolvedMark

    def __post_init__(self) -> None:
        if not isinstance(self.mark, ResolvedMark):
            raise TypeError("mark must be ResolvedMark")
        if self.mark.price_purpose is not PricePurpose.EXECUTION_REFERENCE:
            raise ValueError("mark purpose must be execution_reference")
        if self.mark.price.units <= 0:
            raise ValueError("execution reference price must be positive")

    @property
    def reference_id(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_reference_price",
            "mark": self.mark,
        }


@dataclass(frozen=True, slots=True)
class SlippageRequest:
    reference_price: ExecutionReferencePrice
    side: OrderSide
    quantity: Quantity
    market_state: SlippageMarketState

    def __post_init__(self) -> None:
        if not isinstance(self.reference_price, ExecutionReferencePrice):
            raise TypeError("reference_price must be ExecutionReferencePrice")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        if not isinstance(self.quantity, Quantity):
            raise TypeError("quantity must be Quantity")
        if self.quantity.units <= 0:
            raise ValueError("quantity must be positive")
        if self.quantity.instrument_id != str(self.reference_price.mark.instrument_id):
            raise ValueError("quantity and reference instrument identity mismatch")
        if not isinstance(self.market_state, SlippageMarketState):
            raise TypeError("market_state must be SlippageMarketState")
        if self.market_state.available_at > self.reference_price.mark.resolved_at:
            raise ValueError("future market state evidence is forbidden")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "slippage_request",
            "reference_price": self.reference_price,
            "side": self.side.value,
            "quantity": self.quantity,
            "market_state": self.market_state,
        }


@dataclass(frozen=True, slots=True)
class SlippageApplicabilityResult:
    envelope: SlippageApplicabilityEnvelope
    market_state: SlippageMarketState
    checked_dimensions: tuple[SlippageApplicabilityDimension, ...]
    applicable: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, SlippageApplicabilityEnvelope):
            raise TypeError("envelope must be SlippageApplicabilityEnvelope")
        if not isinstance(self.market_state, SlippageMarketState):
            raise TypeError("market_state must be SlippageMarketState")
        if self.checked_dimensions != _CHECKED_DIMENSIONS:
            raise ValueError("checked_dimensions must contain the complete v1 envelope")
        if type(self.applicable) is not bool:
            raise TypeError("applicable must be bool")
        if not self.applicable:
            raise ValueError("SlippageApplicabilityResult must be applicable")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "slippage_applicability_result",
            "envelope_hash": self.envelope.envelope_hash,
            "market_state_hash": self.market_state.state_hash,
            "checked_dimensions": [value.value for value in self.checked_dimensions],
            "applicable": self.applicable,
        }


@dataclass(frozen=True, slots=True)
class SlippageDecision:
    request: SlippageRequest
    component_ref: SimulationComponentRef
    calibration_ref: SlippageCalibrationRef
    applicability: SlippageApplicabilityResult
    basis_points_units: int
    basis_points_scale: Scale
    rounding: RoundingPolicy
    slippage_amount: Price
    execution_price: Price
    limitations: tuple[SlippageLimitation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, SlippageRequest):
            raise TypeError("request must be SlippageRequest")
        _validate_component(self.component_ref)
        if not isinstance(self.calibration_ref, SlippageCalibrationRef):
            raise TypeError("calibration_ref must be SlippageCalibrationRef")
        if not isinstance(self.applicability, SlippageApplicabilityResult):
            raise TypeError("applicability must be SlippageApplicabilityResult")
        if self.applicability.market_state != self.request.market_state:
            raise ValueError("applicability market state does not match request")
        if _applicability_failures(self.request, self.applicability.envelope):
            raise ValueError("applicability result does not match request and envelope")
        _validate_bps(self.basis_points_units, self.basis_points_scale, self.rounding)
        _validate_limitations(
            SlippageModelKind(self.component_ref.component_key),
            self.basis_points_units,
            self.limitations,
        )
        reference = self.request.reference_price.mark.price
        for name, value in (
            ("slippage_amount", self.slippage_amount),
            ("execution_price", self.execution_price),
        ):
            if not isinstance(value, Price):
                raise TypeError(f"{name} must be Price")
            if value.instrument_id != reference.instrument_id or value.quote_currency != reference.quote_currency or value.scale != reference.scale:
                raise ValueError(f"{name} identity/scale must match reference price")
        if self.execution_price.units <= 0:
            raise ValueError("execution_price must be positive")
        magnitude = _round_ratio(
            reference.units * self.basis_points_units,
            10_000 * self.basis_points_scale.factor,
            self.rounding,
        )
        expected_amount = magnitude if self.request.side is OrderSide.BUY else -magnitude
        if self.slippage_amount.units != expected_amount:
            raise ValueError("slippage amount does not match configured BPS")
        if self.execution_price.units != reference.units + expected_amount:
            raise ValueError("execution_price must equal reference plus slippage amount")

    @property
    def reference_price(self) -> ExecutionReferencePrice:
        return self.request.reference_price

    @property
    def decision_id(self) -> str:
        return canonical_sha256(self._canonical_body())

    def _canonical_body(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "component_ref": self.component_ref,
            "calibration_ref": self.calibration_ref,
            "applicability": self.applicability,
            "basis_points_units": self.basis_points_units,
            "basis_points_scale": self.basis_points_scale.places,
            "rounding": self.rounding.value,
            "slippage_amount": self.slippage_amount,
            "execution_price": self.execution_price,
            "limitations": [value.value for value in self.limitations],
        }

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "slippage_decision",
            "decision_id": self.decision_id,
            **self._canonical_body(),
        }


@dataclass(frozen=True, slots=True)
class SlippageApplicabilityViolation:
    request: SlippageRequest
    request_hash: str
    component_ref: SimulationComponentRef
    calibration_ref: SlippageCalibrationRef
    envelope: SlippageApplicabilityEnvelope
    envelope_hash: str
    failed_dimensions: tuple[SlippageApplicabilityDimension, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, SlippageRequest):
            raise TypeError("request must be SlippageRequest")
        _require_hash("request_hash", self.request_hash)
        if self.request_hash != canonical_sha256(self.request):
            raise ValueError("request_hash does not match request")
        _validate_component(self.component_ref)
        if not isinstance(self.calibration_ref, SlippageCalibrationRef):
            raise TypeError("calibration_ref must be SlippageCalibrationRef")
        if not isinstance(self.envelope, SlippageApplicabilityEnvelope):
            raise TypeError("envelope must be SlippageApplicabilityEnvelope")
        _require_hash("envelope_hash", self.envelope_hash)
        if self.envelope_hash != self.envelope.envelope_hash:
            raise ValueError("envelope_hash does not match envelope")
        if type(self.failed_dimensions) is not tuple or not self.failed_dimensions:
            raise ValueError("failed_dimensions must be a nonempty tuple")
        if not all(
            isinstance(value, SlippageApplicabilityDimension)
            for value in self.failed_dimensions
        ):
            raise TypeError("failed_dimensions must contain applicability dimensions")
        canonical = tuple(
            value
            for value in SlippageApplicabilityDimension
            if value in self.failed_dimensions
        )
        if len(canonical) != len(set(self.failed_dimensions)):
            raise ValueError("duplicate failed applicability dimension")
        object.__setattr__(self, "failed_dimensions", canonical)

    @property
    def violation_id(self) -> str:
        return canonical_sha256(self._canonical_body())

    def _canonical_body(self) -> dict[str, Any]:
        return {
            "request_hash": self.request_hash,
            "component_ref": self.component_ref,
            "calibration_ref": self.calibration_ref,
            "envelope_hash": self.envelope_hash,
            "failed_dimensions": [value.value for value in self.failed_dimensions],
        }

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "slippage_applicability_violation",
            "violation_id": self.violation_id,
            **self._canonical_body(),
        }


def _validate_component(component_ref: SimulationComponentRef) -> SlippageModelKind:
    if not isinstance(component_ref, SimulationComponentRef):
        raise TypeError("component_ref must be SimulationComponentRef")
    if component_ref.port_type is not SimulationPortType.SLIPPAGE_MODEL:
        raise ValueError("component_ref must identify a slippage model")
    try:
        kind = SlippageModelKind(component_ref.component_key)
    except ValueError as error:
        raise ValueError("unsupported slippage component key") from error
    if component_ref.component_version != 1:
        raise ValueError("v1 slippage component version must be 1")
    return kind


def _validate_bps(
    basis_points_units: object,
    basis_points_scale: object,
    rounding: object,
) -> None:
    if type(basis_points_units) is not int:
        raise TypeError("basis_points_units must be int")
    if basis_points_units < 0:
        raise ValueError("basis_points_units cannot be negative")
    if not isinstance(basis_points_scale, Scale):
        raise TypeError("basis_points_scale must be Scale")
    if not isinstance(rounding, RoundingPolicy):
        raise TypeError("rounding must be RoundingPolicy")


def _validate_limitations(
    kind: SlippageModelKind,
    basis_points_units: int,
    limitations: object,
) -> None:
    if type(limitations) is not tuple or not all(
        isinstance(value, SlippageLimitation) for value in limitations
    ):
        raise TypeError("limitations must be a tuple of SlippageLimitation")
    if len(limitations) != len(set(limitations)):
        raise ValueError("duplicate slippage limitation")
    if kind is SlippageModelKind.DETERMINISTIC_BPS_V1:
        if basis_points_units == 0:
            raise ValueError("deterministic_bps.v1 requires nonzero BPS")
        if limitations:
            raise ValueError("deterministic_bps.v1 cannot carry development limitations")
    elif limitations != (SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,):
        raise ValueError("zero slippage requires its development limitation")
    elif basis_points_units != 0:
        raise ValueError("zero_slippage.development.v1 requires zero BPS")


def _applicability_failures(
    request: SlippageRequest,
    envelope: SlippageApplicabilityEnvelope,
) -> tuple[SlippageApplicabilityDimension, ...]:
    resolved_at = request.reference_price.mark.resolved_at
    failures: list[SlippageApplicabilityDimension] = []
    if request.reference_price.mark.instrument_id != envelope.instrument_id:
        failures.append(SlippageApplicabilityDimension.INSTRUMENT)
    if not envelope.valid_from <= resolved_at < envelope.valid_to_exclusive:
        failures.append(SlippageApplicabilityDimension.TIME_WINDOW)
    quantity = request.quantity
    maximum = envelope.maximum_quantity
    if (
        quantity.instrument_id != maximum.instrument_id
        or quantity.scale != maximum.scale
        or quantity.units > maximum.units
    ):
        failures.append(SlippageApplicabilityDimension.QUANTITY)
    if request.market_state.state_key not in envelope.allowed_market_state_keys:
        failures.append(SlippageApplicabilityDimension.MARKET_STATE)
    return tuple(failures)


@dataclass(frozen=True, slots=True)
class DeterministicBpsSlippageModel:
    component_ref: SimulationComponentRef
    calibration_ref: SlippageCalibrationRef
    applicability_envelope: SlippageApplicabilityEnvelope
    basis_points_units: int
    basis_points_scale: Scale
    rounding: RoundingPolicy
    limitations: tuple[SlippageLimitation, ...]

    def __post_init__(self) -> None:
        kind = _validate_component(self.component_ref)
        if not isinstance(self.calibration_ref, SlippageCalibrationRef):
            raise TypeError("calibration_ref must be SlippageCalibrationRef")
        if not isinstance(self.applicability_envelope, SlippageApplicabilityEnvelope):
            raise TypeError(
                "applicability_envelope must be SlippageApplicabilityEnvelope"
            )
        _validate_bps(
            self.basis_points_units,
            self.basis_points_scale,
            self.rounding,
        )
        _validate_limitations(kind, self.basis_points_units, self.limitations)

    def spec(self) -> SimulationPortSpec:
        return SimulationPortSpec(
            component_ref=self.component_ref,
            required_capabilities=(),
            applicability=self.applicability_envelope,
        )

    def decide_slippage(
        self, request: SlippageRequest, /
    ) -> SimulationPortOutcome[SlippageDecision, SlippageApplicabilityViolation]:
        if not isinstance(request, SlippageRequest):
            raise TypeError("request must be SlippageRequest")
        failed = _applicability_failures(request, self.applicability_envelope)
        if failed:
            failure = self._violation(request, failed)
            return SimulationPortOutcome(
                component_ref=self.component_ref,
                input_hash=canonical_sha256(request),
                result=None,
                failure=failure,
            )

        reference = request.reference_price.mark.price
        magnitude = _round_ratio(
            reference.units * self.basis_points_units,
            10_000 * self.basis_points_scale.factor,
            self.rounding,
        )
        signed_amount = magnitude if request.side is OrderSide.BUY else -magnitude
        execution_units = reference.units + signed_amount
        if execution_units <= 0:
            failure = self._violation(
                request,
                (SlippageApplicabilityDimension.EXECUTION_PRICE_POSITIVE,),
            )
            return SimulationPortOutcome(
                component_ref=self.component_ref,
                input_hash=canonical_sha256(request),
                result=None,
                failure=failure,
            )
        amount = Price(
            signed_amount,
            reference.scale,
            reference.instrument_id,
            reference.quote_currency,
        )
        execution_price = Price(
            execution_units,
            reference.scale,
            reference.instrument_id,
            reference.quote_currency,
        )
        decision = SlippageDecision(
            request=request,
            component_ref=self.component_ref,
            calibration_ref=self.calibration_ref,
            applicability=SlippageApplicabilityResult(
                envelope=self.applicability_envelope,
                market_state=request.market_state,
                checked_dimensions=_CHECKED_DIMENSIONS,
            ),
            basis_points_units=self.basis_points_units,
            basis_points_scale=self.basis_points_scale,
            rounding=self.rounding,
            slippage_amount=amount,
            execution_price=execution_price,
            limitations=self.limitations,
        )
        return SimulationPortOutcome(
            component_ref=self.component_ref,
            input_hash=canonical_sha256(request),
            result=decision,
            failure=None,
        )

    def _violation(
        self,
        request: SlippageRequest,
        failed_dimensions: tuple[SlippageApplicabilityDimension, ...],
    ) -> SlippageApplicabilityViolation:
        return SlippageApplicabilityViolation(
            request=request,
            request_hash=canonical_sha256(request),
            component_ref=self.component_ref,
            calibration_ref=self.calibration_ref,
            envelope=self.applicability_envelope,
            envelope_hash=self.applicability_envelope.envelope_hash,
            failed_dimensions=failed_dimensions,
        )
