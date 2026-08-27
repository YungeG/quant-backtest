"""Pure exact position projection for linear perpetual contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from math import gcd
from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    DomainIdKind,
    Fill,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    OrderSide,
    PositionBalanceKey,
    Price,
    PricePurpose,
    Quantity,
    Rate,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)

_SCHEMA_VERSION = 1
_MULTIPLIER_BASIS = "base_quantity_per_contract"


def _require_hash(name: str, value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact string")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be canonical sha256")


def _require_scale(name: str, value: Scale) -> None:
    if type(value) is not Scale or type(value.places) is not int:
        raise TypeError(f"{name} must be exact Scale")


def _require_instrument_id(name: str, value: InstrumentId) -> None:
    if type(value) is not InstrumentId:
        raise TypeError(f"{name} must be exact InstrumentId")
    if type(value.venue) is not VenueId or type(value.venue.value) is not str:
        raise TypeError(f"{name} Venue must be exact")
    if type(value.stable_key) is not str:
        raise TypeError(f"{name} stable_key must be exact string")


def _require_currency(name: str, value: CurrencyId) -> None:
    if type(value) is not CurrencyId or type(value.value) is not str:
        raise TypeError(f"{name} must be exact CurrencyId")


def _require_position_key(value: PositionBalanceKey) -> None:
    if type(value) is not PositionBalanceKey:
        raise TypeError("position_key must be exact PositionBalanceKey")
    if type(value.account_id) is not str:
        raise TypeError("position_key account_id must be exact string")
    if type(value.venue_id) is not VenueId or type(value.venue_id.value) is not str:
        raise TypeError("position_key venue_id must be exact VenueId")
    _require_instrument_id("position_key instrument_id", value.instrument_id)


def _require_quantity(name: str, value: Quantity) -> None:
    if type(value) is not Quantity or type(value.units) is not int:
        raise TypeError(f"{name} must be exact Quantity")
    _require_scale(f"{name} scale", value.scale)
    if type(value.instrument_id) is not str:
        raise TypeError(f"{name} instrument_id must be exact string")


def _require_price(name: str, value: Price) -> None:
    if type(value) is not Price or type(value.units) is not int:
        raise TypeError(f"{name} must be exact Price")
    _require_scale(f"{name} scale", value.scale)
    if type(value.instrument_id) is not str or type(value.quote_currency) is not str:
        raise TypeError(f"{name} identities must be exact strings")


def _require_money(name: str, value: Money) -> None:
    if type(value) is not Money or type(value.units) is not int:
        raise TypeError(f"{name} must be exact Money")
    _require_scale(f"{name} scale", value.scale)
    if type(value.currency) is not str:
        raise TypeError(f"{name} currency must be exact string")


def _require_fill(value: Fill) -> None:
    if type(value) is not Fill:
        raise TypeError("fills must contain exact Fill values")
    for name, domain_id, kind in (
        ("fill_id", value.fill_id, DomainIdKind.FILL),
        ("order_id", value.order_id, DomainIdKind.ORDER),
    ):
        if type(domain_id) is not DomainId or type(domain_id.kind) is not DomainIdKind:
            raise TypeError(f"Fill {name} must be exact DomainId")
        if domain_id.kind is not kind or type(domain_id.value) is not str:
            raise TypeError(f"Fill {name} identity must be exact")
    if (
        type(value.account_id) is not str
        or type(value.venue_id) is not VenueId
        or type(value.venue_id.value) is not str
    ):
        raise TypeError("Fill account and Venue identities must be exact")
    _require_instrument_id("Fill instrument_id", value.instrument_id)
    if type(value.side) is not OrderSide:
        raise TypeError("Fill side must be exact OrderSide")
    _require_quantity("Fill quantity", value.quantity)
    _require_price("Fill reference_price", value.reference_price)
    _require_price("Fill price", value.price)
    if type(value.reference_price_purpose) is not PricePurpose:
        raise TypeError("Fill reference_price_purpose must be exact PricePurpose")
    _require_money("Fill slippage_amount", value.slippage_amount)
    for name, required_text in (
        ("slippage_decision_id", value.slippage_decision_id),
        ("slippage_model_key", value.slippage_model_key),
    ):
        if type(required_text) is not str:
            raise TypeError(f"Fill {name} must be exact string")
    for name, optional_text in (
        ("slippage_calibration_id", value.slippage_calibration_id),
        ("liquidity", value.liquidity),
    ):
        if optional_text is not None and type(optional_text) is not str:
            raise TypeError(f"Fill {name} must be exact string or None")
    if type(value.execution_time) is not UtcInstant or type(
        value.execution_time.epoch_nanoseconds
    ) is not int:
        raise TypeError("Fill execution_time must be exact UtcInstant")


class LinearPositionTransitionKind(str, Enum):
    OPEN = "open"
    ADD = "add"
    REDUCE = "reduce"
    CLOSE = "close"
    FLIP = "flip"


class LinearPositionProjectionFailureCode(str, Enum):
    POSITION_CONTEXT_MISMATCH = "position_context_mismatch"
    DUPLICATE_FILL_ID = "duplicate_fill_id"
    NON_MONOTONIC_EXECUTION_TIME = "non_monotonic_execution_time"
    FILL_CONTEXT_MISMATCH = "fill_context_mismatch"
    QUANTITY_SCALE_MISMATCH = "quantity_scale_mismatch"
    PRICE_CONTEXT_MISMATCH = "price_context_mismatch"
    PRICE_SCALE_MISMATCH = "price_scale_mismatch"


@dataclass(frozen=True, slots=True)
class LinearPerpetualContract:
    instrument: InstrumentDefinition
    quantity_scale: Scale
    price_scale: Scale
    contract_multiplier: Rate

    def __post_init__(self) -> None:
        if type(self.instrument) is not InstrumentDefinition:
            raise TypeError("instrument must be exact InstrumentDefinition")
        _require_instrument_id("instrument instrument_id", self.instrument.instrument_id)
        if type(self.instrument.instrument_type) is not InstrumentType:
            raise TypeError("instrument_type must be exact InstrumentType")
        if self.instrument.base_currency is not None:
            _require_currency("instrument base_currency", self.instrument.base_currency)
        _require_currency("instrument quote_currency", self.instrument.quote_currency)
        _require_currency(
            "instrument settlement_currency", self.instrument.settlement_currency
        )
        if self.instrument.instrument_type is not InstrumentType.LINEAR_PERPETUAL:
            raise ValueError("instrument must be LINEAR_PERPETUAL")
        if self.instrument.base_currency is None:
            raise ValueError("linear perpetual requires base currency")
        if self.instrument.quote_currency != self.instrument.settlement_currency:
            raise ValueError("quote and settlement currency must match")
        _require_scale("quantity_scale", self.quantity_scale)
        _require_scale("price_scale", self.price_scale)
        if type(self.contract_multiplier) is not Rate or type(
            self.contract_multiplier.units
        ) is not int:
            raise TypeError("contract_multiplier must be exact Rate")
        _require_scale("contract_multiplier scale", self.contract_multiplier.scale)
        if type(self.contract_multiplier.basis) is not str:
            raise TypeError("contract_multiplier basis must be exact string")
        if (
            self.contract_multiplier.units <= 0
            or self.contract_multiplier.basis != _MULTIPLIER_BASIS
        ):
            raise ValueError("contract multiplier must be positive base quantity per contract")

    @property
    def contract_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_perpetual_contract",
            "schema_version": _SCHEMA_VERSION,
            "instrument": self.instrument,
            "quantity_scale": self.quantity_scale.places,
            "price_scale": self.price_scale.places,
            "contract_multiplier": self.contract_multiplier,
        }


@dataclass(frozen=True, slots=True)
class ExactAverageEntryBasis:
    instrument_id: InstrumentId
    quote_currency: CurrencyId
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        _require_instrument_id("instrument_id", self.instrument_id)
        _require_currency("quote_currency", self.quote_currency)
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("basis numerator and denominator must be integers")
        if self.numerator <= 0 or self.denominator <= 0:
            raise ValueError("basis numerator and denominator must be positive")
        if gcd(self.numerator, self.denominator) != 1:
            raise ValueError("basis must be GCD-reduced")

    @property
    def basis_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "exact_average_entry_basis",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id,
            "quote_currency": self.quote_currency,
            "numerator": self.numerator,
            "denominator": self.denominator,
        }


@dataclass(frozen=True, slots=True)
class LinearPositionState:
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    quantity: Quantity
    average_entry_basis: ExactAverageEntryBasis | None

    def __post_init__(self) -> None:
        _require_position_key(self.position_key)
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        _require_quantity("position quantity", self.quantity)
        instrument_id = self.contract.instrument.instrument_id
        if (
            self.position_key.venue_id != instrument_id.venue
            or self.position_key.instrument_id != instrument_id
            or self.quantity.instrument_id != str(instrument_id)
            or self.quantity.scale != self.contract.quantity_scale
        ):
            raise ValueError("position state context mismatch")
        if (self.quantity.units == 0) != (self.average_entry_basis is None):
            raise ValueError("flat state must have no basis and non-flat state must have basis")
        if self.average_entry_basis is not None and type(
            self.average_entry_basis
        ) is not ExactAverageEntryBasis:
            raise TypeError("average_entry_basis must be ExactAverageEntryBasis or None")
        if self.average_entry_basis is not None and (
            self.average_entry_basis.instrument_id != instrument_id
            or self.average_entry_basis.quote_currency
            != self.contract.instrument.quote_currency
        ):
            raise ValueError("position basis context mismatch")

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_state",
            "schema_version": _SCHEMA_VERSION,
            "position_key": self.position_key,
            "contract": self.contract,
            "quantity": self.quantity,
            "average_entry_basis": self.average_entry_basis,
        }


def _flat_state(
    position_key: PositionBalanceKey,
    contract: LinearPerpetualContract,
) -> LinearPositionState:
    return LinearPositionState(
        position_key,
        contract,
        Quantity(0, contract.quantity_scale, str(contract.instrument.instrument_id)),
        None,
    )


@dataclass(frozen=True, slots=True)
class LinearPositionProjectionRequest:
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    fills: tuple[Fill, ...]

    def __post_init__(self) -> None:
        _require_position_key(self.position_key)
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        if type(self.fills) is not tuple:
            raise TypeError("fills must be an exact tuple of Fill")
        for fill in self.fills:
            _require_fill(fill)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_projection_request",
            "schema_version": _SCHEMA_VERSION,
            "position_key": self.position_key,
            "contract": self.contract,
            "fills": self.fills,
        }


@dataclass(frozen=True, slots=True)
class LinearPositionTransition:
    kind: LinearPositionTransitionKind
    fill: Fill
    before: LinearPositionState
    after: LinearPositionState
    closed_quantity: Quantity

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LinearPositionTransitionKind):
            raise TypeError("kind must be LinearPositionTransitionKind")
        _require_fill(self.fill)
        if type(self.before) is not LinearPositionState or type(
            self.after
        ) is not LinearPositionState:
            raise TypeError("before and after must be exact LinearPositionState")
        _require_quantity("closed_quantity", self.closed_quantity)
        embedded_request = LinearPositionProjectionRequest(
            self.before.position_key,
            self.before.contract,
            (self.fill,),
        )
        if (
            _first_failure(
                embedded_request, allow_compatible_price_scale=True
            )
            is not None
        ):
            raise ValueError("transition Fill must match before State context")
        expected = _transition_values(self.before, self.fill)
        if expected != (self.kind, self.after, self.closed_quantity):
            raise ValueError("transition must match embedded before State and Fill")

    @property
    def transition_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_transition",
            "schema_version": _SCHEMA_VERSION,
            "kind": self.kind.value,
            "fill": self.fill,
            "before": self.before,
            "after": self.after,
            "closed_quantity": self.closed_quantity,
        }


@dataclass(frozen=True, slots=True)
class LinearPositionProjection:
    request: LinearPositionProjectionRequest
    request_hash: str
    transitions: tuple[LinearPositionTransition, ...]
    final_state: LinearPositionState

    def __post_init__(self) -> None:
        if type(self.request) is not LinearPositionProjectionRequest:
            raise TypeError("request must be exact LinearPositionProjectionRequest")
        _require_hash("request_hash", self.request_hash)
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if type(self.transitions) is not tuple or not all(
            type(value) is LinearPositionTransition for value in self.transitions
        ):
            raise TypeError("transitions must be a tuple of LinearPositionTransition")
        if type(self.final_state) is not LinearPositionState:
            raise TypeError("final_state must be exact LinearPositionState")
        if (
            _first_failure(
                self.request, allow_compatible_price_scale=True
            )
            is not None
        ):
            raise ValueError("Projection Request must not contain a business failure")
        state = _flat_state(self.request.position_key, self.request.contract)
        expected: list[LinearPositionTransition] = []
        for fill in self.request.fills:
            transition = _project_fill(state, fill)
            expected.append(transition)
            state = transition.after
        if self.transitions != tuple(expected):
            raise ValueError("transitions must match the complete transition prefix")
        if self.final_state != state:
            raise ValueError("final_state must match the final Transition")

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_projection",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_hash": self.request_hash,
            "transitions": self.transitions,
            "final_state": self.final_state,
        }


def _price_fits_contract_scale(price: Price, scale: Scale) -> bool:
    difference = price.scale.places - scale.places
    return difference <= 0 or price.units % (10**difference) == 0


def _first_failure(
    request: LinearPositionProjectionRequest,
    *,
    allow_compatible_price_scale: bool = False,
) -> tuple[
    LinearPositionProjectionFailureCode,
    int | None,
    DomainId | None,
] | None:
    instrument_id = request.contract.instrument.instrument_id
    if (
        request.position_key.venue_id != instrument_id.venue
        or request.position_key.instrument_id != instrument_id
    ):
        return (
            LinearPositionProjectionFailureCode.POSITION_CONTEXT_MISMATCH,
            None,
            None,
        )
    seen: set[DomainId] = set()
    previous_time = None
    for index, fill in enumerate(request.fills):
        if fill.fill_id in seen:
            return (
                LinearPositionProjectionFailureCode.DUPLICATE_FILL_ID,
                index,
                fill.fill_id,
            )
        if previous_time is not None and fill.execution_time < previous_time:
            return (
                LinearPositionProjectionFailureCode.NON_MONOTONIC_EXECUTION_TIME,
                index,
                fill.fill_id,
            )
        if (
            fill.account_id != request.position_key.account_id
            or fill.venue_id != request.position_key.venue_id
            or fill.instrument_id != request.position_key.instrument_id
        ):
            return (
                LinearPositionProjectionFailureCode.FILL_CONTEXT_MISMATCH,
                index,
                fill.fill_id,
            )
        if fill.quantity.scale != request.contract.quantity_scale:
            return (
                LinearPositionProjectionFailureCode.QUANTITY_SCALE_MISMATCH,
                index,
                fill.fill_id,
            )
        if (
            fill.price.instrument_id != str(instrument_id)
            or fill.price.quote_currency
            != str(request.contract.instrument.quote_currency)
        ):
            return (
                LinearPositionProjectionFailureCode.PRICE_CONTEXT_MISMATCH,
                index,
                fill.fill_id,
            )
        if (
            fill.price.scale != request.contract.price_scale
            and not (
                allow_compatible_price_scale
                and _price_fits_contract_scale(fill.price, request.contract.price_scale)
            )
        ):
            return (
                LinearPositionProjectionFailureCode.PRICE_SCALE_MISMATCH,
                index,
                fill.fill_id,
            )
        seen.add(fill.fill_id)
        previous_time = fill.execution_time
    return None


@dataclass(frozen=True, slots=True)
class LinearPositionProjectionFailure:
    request: LinearPositionProjectionRequest
    request_hash: str
    code: LinearPositionProjectionFailureCode
    fill_index: int | None
    fill_id: DomainId | None

    def __post_init__(self) -> None:
        if type(self.request) is not LinearPositionProjectionRequest:
            raise TypeError("request must be exact LinearPositionProjectionRequest")
        _require_hash("request_hash", self.request_hash)
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match Request")
        if not isinstance(self.code, LinearPositionProjectionFailureCode):
            raise TypeError("code must be LinearPositionProjectionFailureCode")
        if self.fill_index is not None and (
            type(self.fill_index) is not int or self.fill_index < 0
        ):
            raise ValueError("fill_index must be a non-negative integer or None")
        if self.fill_id is not None and (
            type(self.fill_id) is not DomainId
            or type(self.fill_id.kind) is not DomainIdKind
            or type(self.fill_id.value) is not str
        ):
            raise TypeError("fill_id must be exact DomainId or None")
        expected = _first_failure(self.request)
        if expected is None or expected != (self.code, self.fill_index, self.fill_id):
            raise ValueError("failure must match the first Request failure")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_projection_failure",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "fill_index": self.fill_index,
            "fill_id": self.fill_id,
        }


@dataclass(frozen=True, slots=True)
class LinearPositionProjectionOutcome:
    request_hash: str
    result: LinearPositionProjection | None
    failure: LinearPositionProjectionFailure | None

    def __post_init__(self) -> None:
        _require_hash("request_hash", self.request_hash)
        if self.result is not None and type(
            self.result
        ) is not LinearPositionProjection:
            raise TypeError("result must be LinearPositionProjection or None")
        if self.failure is not None and type(
            self.failure
        ) is not LinearPositionProjectionFailure:
            raise TypeError("failure must be LinearPositionProjectionFailure or None")
        if (self.result is None) == (self.failure is None):
            raise ValueError("Outcome requires exactly one result or failure")
        value = self.result if self.result is not None else self.failure
        if value is None or value.request_hash != self.request_hash:
            raise ValueError("Outcome request_hash must match its value")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_projection_outcome",
            "schema_version": _SCHEMA_VERSION,
            "request_hash": self.request_hash,
            "result": self.result,
            "failure": self.failure,
        }


def _basis_from_price(fill: Fill) -> ExactAverageEntryBasis:
    divisor = gcd(fill.price.units, fill.price.scale.factor)
    return ExactAverageEntryBasis(
        fill.instrument_id,
        CurrencyId(fill.price.quote_currency),
        fill.price.units // divisor,
        fill.price.scale.factor // divisor,
    )


def _weighted_basis(
    prior: ExactAverageEntryBasis,
    prior_units: int,
    fill: Fill,
) -> ExactAverageEntryBasis:
    price_factor = fill.price.scale.factor
    fill_units = fill.quantity.units
    numerator = (
        prior.numerator * prior_units * price_factor
        + fill.price.units * fill_units * prior.denominator
    )
    denominator = (
        prior.denominator * (prior_units + fill_units) * price_factor
    )
    divisor = gcd(numerator, denominator)
    return ExactAverageEntryBasis(
        prior.instrument_id,
        prior.quote_currency,
        numerator // divisor,
        denominator // divisor,
    )


def _transition_values(
    before: LinearPositionState,
    fill: Fill,
) -> tuple[LinearPositionTransitionKind, LinearPositionState, Quantity]:
    q0 = before.quantity.units
    delta = fill.quantity.units if fill.side is OrderSide.BUY else -fill.quantity.units
    q1 = q0 + delta
    basis: ExactAverageEntryBasis | None
    if q0 == 0:
        kind = LinearPositionTransitionKind.OPEN
        basis = _basis_from_price(fill)
        closed_units = 0
    elif (q0 > 0) == (delta > 0):
        kind = LinearPositionTransitionKind.ADD
        if before.average_entry_basis is None:
            raise AssertionError("non-flat position must have entry basis")
        basis = _weighted_basis(before.average_entry_basis, abs(q0), fill)
        closed_units = 0
    elif abs(delta) < abs(q0):
        kind = LinearPositionTransitionKind.REDUCE
        basis = before.average_entry_basis
        closed_units = abs(delta)
    elif abs(delta) == abs(q0):
        kind = LinearPositionTransitionKind.CLOSE
        basis = None
        closed_units = abs(q0)
    else:
        kind = LinearPositionTransitionKind.FLIP
        basis = _basis_from_price(fill)
        closed_units = abs(q0)
    instrument_id = str(before.contract.instrument.instrument_id)
    after = LinearPositionState(
        before.position_key,
        before.contract,
        Quantity(q1, before.contract.quantity_scale, instrument_id),
        basis,
    )
    closed_quantity = Quantity(
        closed_units,
        before.contract.quantity_scale,
        instrument_id,
    )
    return kind, after, closed_quantity


def _project_fill(
    before: LinearPositionState,
    fill: Fill,
) -> LinearPositionTransition:
    kind, after, closed_quantity = _transition_values(before, fill)
    return LinearPositionTransition(
        kind,
        fill,
        before,
        after,
        closed_quantity,
    )


@dataclass(frozen=True, slots=True)
class LinearPositionProjector:
    def project(
        self, request: LinearPositionProjectionRequest, /
    ) -> LinearPositionProjectionOutcome:
        if type(request) is not LinearPositionProjectionRequest:
            raise TypeError("request must be exact LinearPositionProjectionRequest")
        failure = _first_failure(request)
        if failure is not None:
            code, fill_index, fill_id = failure
            value = LinearPositionProjectionFailure(
                request,
                request.request_hash,
                code,
                fill_index,
                fill_id,
            )
            return LinearPositionProjectionOutcome(
                request.request_hash,
                None,
                value,
            )
        state = _flat_state(request.position_key, request.contract)
        transitions: list[LinearPositionTransition] = []
        for fill in request.fills:
            transition = _project_fill(state, fill)
            transitions.append(transition)
            state = transition.after
        projection = LinearPositionProjection(
            request,
            request.request_hash,
            tuple(transitions),
            state,
        )
        return LinearPositionProjectionOutcome(request.request_hash, projection, None)


@dataclass(frozen=True, slots=True)
class LinearPositionProjectorV2:
    """Project exact fills whose price is representable on the contract lattice."""

    def project(
        self, request: LinearPositionProjectionRequest, /
    ) -> LinearPositionProjectionOutcome:
        if type(request) is not LinearPositionProjectionRequest:
            raise TypeError("request must be exact LinearPositionProjectionRequest")
        failure = _first_failure(request, allow_compatible_price_scale=True)
        if failure is not None:
            code, fill_index, fill_id = failure
            value = LinearPositionProjectionFailure(
                request,
                request.request_hash,
                code,
                fill_index,
                fill_id,
            )
            return LinearPositionProjectionOutcome(request.request_hash, None, value)
        state = _flat_state(request.position_key, request.contract)
        transitions: list[LinearPositionTransition] = []
        for fill in request.fills:
            transition = _project_fill(state, fill)
            transitions.append(transition)
            state = transition.after
        projection = LinearPositionProjection(
            request,
            request.request_hash,
            tuple(transitions),
            state,
        )
        return LinearPositionProjectionOutcome(request.request_hash, projection, None)
