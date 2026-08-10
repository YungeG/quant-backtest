"""Single-account linear perpetual margin projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import gcd
from typing import Any

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    Money,
    PositionBalanceKey,
    PricePurpose,
    QuantizationPolicy,
    RoundingPolicy,
    SimulationInstant,
    VenueId,
    canonical_sha256,
    round_ratio,
)

from .ledger import LedgerBalanceRegistration, LedgerState
from .margin import LinearInstrumentMarginResult
from .marks import ResolvedMark, StaleMarkPolicy
from .ports import ProfileComponentRef, ProfilePortType
from .reservations import ResourceReservationState
from .derivatives import LinearPositionState

_SCHEMA_VERSION = 1
_COMPONENT_KEY = "account.linear-perpetual.margin-projection.v1"
_HEX = "0123456789abcdef"


def _text(name: str, value: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")


def _hash(name: str, value: str) -> None:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in _HEX for character in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 hash")


def _instant(name: str, value: SimulationInstant) -> None:
    if type(value) is not SimulationInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")


def _component_ref() -> ProfileComponentRef:
    digest = canonical_sha256(
        {
            "type": "linear_account_margin_projection_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "scope": "single-account-single-venue-single-settlement-currency",
            "wallet_balance": "ledger-settlement-cash",
            "unrealized_pnl": (
                "signed-quantity*multiplier*(valuation-mark-average-entry)"
            ),
            "equity": "wallet-balance+instrument-unrealized-pnl",
            "position_margin": "g09e-results",
            "working_order_margin": "reservation-state-totals-margin",
            "available_margin": (
                "equity-position-initial-margin-working-order-margin"
            ),
            "pnl_quantization": "half-even-per-instrument",
            "allowed_grade": "development",
        }
    )
    return ProfileComponentRef(ProfilePortType.MARGIN_MODEL, _COMPONENT_KEY, 1, digest)


@dataclass(frozen=True, slots=True)
class LinearMarginLedgerEvidence:
    ledger_state: LedgerState
    projected_through: SimulationInstant
    available_at: SimulationInstant
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        if type(self.ledger_state) is not LedgerState:
            raise TypeError("ledger_state must be exact LedgerState")
        _instant("projected_through", self.projected_through)
        _instant("available_at", self.available_at)
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_margin_ledger_evidence",
            "schema_version": _SCHEMA_VERSION,
            "ledger_state": self.ledger_state,
            "projected_through": self.projected_through,
            "available_at": self.available_at,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class LinearMarginReservationEvidence:
    reservation_state: ResourceReservationState
    projected_through: SimulationInstant
    available_at: SimulationInstant
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        if type(self.reservation_state) is not ResourceReservationState:
            raise TypeError("reservation_state must be exact ResourceReservationState")
        _instant("projected_through", self.projected_through)
        _instant("available_at", self.available_at)
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_margin_reservation_evidence",
            "schema_version": _SCHEMA_VERSION,
            "reservation_state": self.reservation_state,
            "projected_through": self.projected_through,
            "available_at": self.available_at,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class LinearPositionValuationEvidence:
    position_state: LinearPositionState
    resolved_mark: ResolvedMark
    stale_policy: StaleMarkPolicy

    def __post_init__(self) -> None:
        if type(self.position_state) is not LinearPositionState:
            raise TypeError("position_state must be exact LinearPositionState")
        if type(self.resolved_mark) is not ResolvedMark:
            raise TypeError("resolved_mark must be exact ResolvedMark")
        if type(self.stale_policy) is not StaleMarkPolicy:
            raise TypeError("stale_policy must be exact StaleMarkPolicy")

    @property
    def valuation_evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_valuation_evidence",
            "schema_version": _SCHEMA_VERSION,
            "position_state": self.position_state,
            "resolved_mark": self.resolved_mark,
            "stale_policy": self.stale_policy,
        }


@dataclass(frozen=True, slots=True)
class ExactLinearUnrealizedPnl:
    currency_id: CurrencyId
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.currency_id) is not CurrencyId:
            raise TypeError("currency_id must be exact CurrencyId")
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("numerator and denominator must be exact integers")
        if self.denominator <= 0:
            raise ValueError("denominator must be positive")
        if gcd(abs(self.numerator), self.denominator) != 1:
            raise ValueError("Unrealized PnL must be GCD-reduced")

    @property
    def pnl_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "exact_linear_unrealized_pnl",
            "schema_version": _SCHEMA_VERSION,
            "currency_id": self.currency_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
        }


@dataclass(frozen=True, slots=True)
class LinearPositionUnrealizedPnl:
    valuation_evidence: LinearPositionValuationEvidence
    valuation_evidence_hash: str
    exact_unrealized_pnl: ExactLinearUnrealizedPnl
    unrealized_pnl: Money

    def __post_init__(self) -> None:
        if type(self.valuation_evidence) is not LinearPositionValuationEvidence:
            raise TypeError("valuation_evidence must be exact Evidence")
        if self.valuation_evidence_hash != self.valuation_evidence.valuation_evidence_hash:
            raise ValueError("valuation_evidence_hash must match Evidence")
        if type(self.exact_unrealized_pnl) is not ExactLinearUnrealizedPnl:
            raise TypeError("exact_unrealized_pnl must be exact PnL")
        if type(self.unrealized_pnl) is not Money:
            raise TypeError("unrealized_pnl must be exact Money")
        expected_exact = _exact_unrealized(self.valuation_evidence)
        expected_money = Money(
            round_ratio(
                expected_exact.numerator * self.unrealized_pnl.scale.factor,
                expected_exact.denominator,
                RoundingPolicy.HALF_EVEN,
            ),
            self.unrealized_pnl.scale,
            str(expected_exact.currency_id),
        )
        if (
            self.exact_unrealized_pnl != expected_exact
            or self.unrealized_pnl != expected_money
        ):
            raise ValueError("Unrealized PnL fields must match Evidence")

    @property
    def pnl_result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_position_unrealized_pnl",
            "schema_version": _SCHEMA_VERSION,
            "valuation_evidence": self.valuation_evidence,
            "valuation_evidence_hash": self.valuation_evidence_hash,
            "exact_unrealized_pnl": self.exact_unrealized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
        }


@dataclass(frozen=True, slots=True)
class LinearAccountMarginProjectionRequest:
    account_id: str
    venue_id: VenueId
    evaluated_at: SimulationInstant
    ledger_evidence: LinearMarginLedgerEvidence | None
    position_valuations: tuple[LinearPositionValuationEvidence, ...]
    margin_results: tuple[LinearInstrumentMarginResult, ...]
    reservation_evidence: LinearMarginReservationEvidence | None
    settlement_cash_registration: LedgerBalanceRegistration
    unrealized_pnl_quantization: QuantizationPolicy

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        if type(self.venue_id) is not VenueId:
            raise TypeError("venue_id must be exact VenueId")
        _instant("evaluated_at", self.evaluated_at)
        if type(self.ledger_evidence) not in (type(None), LinearMarginLedgerEvidence):
            raise TypeError("ledger_evidence must be exact Evidence or None")
        if type(self.position_valuations) is not tuple or not all(
            type(value) is LinearPositionValuationEvidence
            for value in self.position_valuations
        ):
            raise TypeError("position_valuations must contain exact Evidence")
        if type(self.margin_results) is not tuple or not all(
            type(value) is LinearInstrumentMarginResult
            for value in self.margin_results
        ):
            raise TypeError("margin_results must contain exact G09E Results")
        if type(self.reservation_evidence) not in (
            type(None),
            LinearMarginReservationEvidence,
        ):
            raise TypeError("reservation_evidence must be exact Evidence or None")
        if type(self.settlement_cash_registration) is not LedgerBalanceRegistration:
            raise TypeError("settlement_cash_registration must be exact Registration")
        if type(self.unrealized_pnl_quantization) is not QuantizationPolicy:
            raise TypeError("unrealized_pnl_quantization must be exact Policy")
        object.__setattr__(
            self,
            "position_valuations",
            tuple(
                sorted(
                    self.position_valuations,
                    key=lambda value: str(value.position_state.position_key.instrument_id),
                )
            ),
        )
        object.__setattr__(
            self,
            "margin_results",
            tuple(
                sorted(
                    self.margin_results,
                    key=lambda value: str(value.request.position_key.instrument_id),
                )
            ),
        )

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_account_margin_projection_request",
            "schema_version": _SCHEMA_VERSION,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "evaluated_at": self.evaluated_at,
            "ledger_evidence": self.ledger_evidence,
            "position_valuations": self.position_valuations,
            "margin_results": self.margin_results,
            "reservation_evidence": self.reservation_evidence,
            "settlement_cash_registration": self.settlement_cash_registration,
            "unrealized_pnl_quantization": self.unrealized_pnl_quantization,
        }


class LinearAccountMarginProjectionFailureCode(str, Enum):
    MISSING_LEDGER_EVIDENCE = "missing_ledger_evidence"
    MISSING_RESERVATION_EVIDENCE = "missing_reservation_evidence"
    ACCOUNT_CONTEXT_MISMATCH = "account_context_mismatch"
    LEDGER_PROJECTION_INSTANT_MISMATCH = "ledger_projection_instant_mismatch"
    LEDGER_NOT_AVAILABLE = "ledger_not_available"
    RESERVATION_PROJECTION_INSTANT_MISMATCH = "reservation_projection_instant_mismatch"
    RESERVATION_NOT_AVAILABLE = "reservation_not_available"
    SETTLEMENT_CASH_CONTEXT_MISMATCH = "settlement_cash_context_mismatch"
    DUPLICATE_POSITION = "duplicate_position"
    POSITION_CONTEXT_MISMATCH = "position_context_mismatch"
    DUPLICATE_MARGIN_RESULT = "duplicate_margin_result"
    MARGIN_COVERAGE_MISMATCH = "margin_coverage_mismatch"
    MARGIN_CONTEXT_MISMATCH = "margin_context_mismatch"
    VALUATION_COVERAGE_MISMATCH = "valuation_coverage_mismatch"
    VALUATION_MARK_PURPOSE_MISMATCH = "valuation_mark_purpose_mismatch"
    VALUATION_MARK_CONTEXT_MISMATCH = "valuation_mark_context_mismatch"
    VALUATION_MARK_INSTANT_MISMATCH = "valuation_mark_instant_mismatch"
    VALUATION_MARK_SCALE_MISMATCH = "valuation_mark_scale_mismatch"
    NON_POSITIVE_VALUATION_MARK = "non_positive_valuation_mark"
    VALUATION_MARK_POLICY_MISMATCH = "valuation_mark_policy_mismatch"
    VALUATION_MARK_NOT_AVAILABLE = "valuation_mark_not_available"
    QUANTIZATION_SCALE_MISMATCH = "quantization_scale_mismatch"
    UNSAFE_UNREALIZED_PNL_ROUNDING = "unsafe_unrealized_pnl_rounding"
    RESERVATION_CONTEXT_MISMATCH = "reservation_context_mismatch"
    RESERVATION_MARGIN_CONTEXT_MISMATCH = "reservation_margin_context_mismatch"


def _cash_key(request: LinearAccountMarginProjectionRequest) -> CashBalanceKey | None:
    key = request.settlement_cash_registration.key
    return key if type(key) is CashBalanceKey else None


def _ledger_keys_match(request: LinearAccountMarginProjectionRequest) -> bool:
    evidence = request.ledger_evidence
    cash_key = _cash_key(request)
    if evidence is None or cash_key is None:
        return True
    for registration in evidence.ledger_state.schema.registrations:
        key = registration.key
        if key.account_id != request.account_id or key.venue_id != request.venue_id:
            return False
        if type(key) is CashBalanceKey and key.currency_id != cash_key.currency_id:
            return False
    return True


def _position_key(value: LinearPositionValuationEvidence) -> PositionBalanceKey:
    return value.position_state.position_key


def _margin_key(value: LinearInstrumentMarginResult) -> PositionBalanceKey:
    return value.request.position_key


def _mark_policy_invalid(evidence: LinearPositionValuationEvidence) -> bool:
    mark = evidence.resolved_mark
    policy = evidence.stale_policy
    expected_age = mark.resolved_at.epoch_nanoseconds - mark.observed_at.epoch_nanoseconds
    return (
        mark.stale_policy_key != policy.policy_key
        or mark.stale_policy_version != policy.policy_version
        or mark.stale_policy_hash != policy.policy_hash
        or mark.age_nanoseconds != expected_age
        or mark.age_nanoseconds > policy.max_age_nanoseconds
        or (mark.age_nanoseconds > 0 and not policy.allow_forward_fill)
    )


def _evaluate_failure(
    request: LinearAccountMarginProjectionRequest,
) -> LinearAccountMarginProjectionFailureCode | None:
    ledger = request.ledger_evidence
    reservation = request.reservation_evidence
    if ledger is None:
        return LinearAccountMarginProjectionFailureCode.MISSING_LEDGER_EVIDENCE
    if reservation is None:
        return LinearAccountMarginProjectionFailureCode.MISSING_RESERVATION_EVIDENCE
    if not _ledger_keys_match(request):
        return LinearAccountMarginProjectionFailureCode.ACCOUNT_CONTEXT_MISMATCH
    if ledger.projected_through != request.evaluated_at:
        return LinearAccountMarginProjectionFailureCode.LEDGER_PROJECTION_INSTANT_MISMATCH
    if ledger.available_at > request.evaluated_at:
        return LinearAccountMarginProjectionFailureCode.LEDGER_NOT_AVAILABLE
    if reservation.projected_through != request.evaluated_at:
        return LinearAccountMarginProjectionFailureCode.RESERVATION_PROJECTION_INSTANT_MISMATCH
    if reservation.available_at > request.evaluated_at:
        return LinearAccountMarginProjectionFailureCode.RESERVATION_NOT_AVAILABLE
    cash_key = _cash_key(request)
    if (
        cash_key is None
        or cash_key.account_id != request.account_id
        or cash_key.venue_id != request.venue_id
        or request.settlement_cash_registration not in ledger.ledger_state.schema.registrations
    ):
        return LinearAccountMarginProjectionFailureCode.SETTLEMENT_CASH_CONTEXT_MISMATCH

    position_keys = tuple(_position_key(value) for value in request.position_valuations)
    if len(position_keys) != len(set(position_keys)):
        return LinearAccountMarginProjectionFailureCode.DUPLICATE_POSITION
    for evidence in request.position_valuations:
        state = evidence.position_state
        if (
            state.quantity.units == 0
            or state.position_key.account_id != request.account_id
            or state.position_key.venue_id != request.venue_id
            or ledger.ledger_state.position_quantity(state.position_key) != state.quantity
        ):
            return LinearAccountMarginProjectionFailureCode.POSITION_CONTEXT_MISMATCH

    margin_keys = tuple(_margin_key(value) for value in request.margin_results)
    if len(margin_keys) != len(set(margin_keys)):
        return LinearAccountMarginProjectionFailureCode.DUPLICATE_MARGIN_RESULT
    if set(margin_keys) != set(position_keys):
        return LinearAccountMarginProjectionFailureCode.MARGIN_COVERAGE_MISMATCH
    margin_by_key = {_margin_key(value): value for value in request.margin_results}
    valuation_by_key = {_position_key(value): value for value in request.position_valuations}
    for key, value in margin_by_key.items():
        state = valuation_by_key[key].position_state
        margin_request = value.request
        if (
            margin_request.position_key != key
            or margin_request.contract != state.contract
            or margin_request.evaluated_at != request.evaluated_at
            or margin_request.exposure_quantity != state.quantity
            or value.initial_margin.currency != str(cash_key.currency_id)
            or value.maintenance_margin.currency != str(cash_key.currency_id)
            or value.initial_margin.scale != request.settlement_cash_registration.scale
            or value.maintenance_margin.scale != request.settlement_cash_registration.scale
        ):
            return LinearAccountMarginProjectionFailureCode.MARGIN_CONTEXT_MISMATCH

    ledger_position_keys = tuple(
        balance.key for balance in ledger.ledger_state.position_balances
    )
    if set(position_keys) != set(ledger_position_keys):
        return LinearAccountMarginProjectionFailureCode.VALUATION_COVERAGE_MISMATCH
    for evidence in request.position_valuations:
        state = evidence.position_state
        mark = evidence.resolved_mark
        policy = evidence.stale_policy
        contract = state.contract
        if (
            mark.price_purpose is not PricePurpose.VALUATION
            or policy.price_purpose is not PricePurpose.VALUATION
        ):
            return LinearAccountMarginProjectionFailureCode.VALUATION_MARK_PURPOSE_MISMATCH
        if (
            mark.instrument_id != contract.instrument.instrument_id
            or mark.quote_currency_id != contract.instrument.settlement_currency
        ):
            return LinearAccountMarginProjectionFailureCode.VALUATION_MARK_CONTEXT_MISMATCH
        if mark.resolved_at != request.evaluated_at.instant:
            return LinearAccountMarginProjectionFailureCode.VALUATION_MARK_INSTANT_MISMATCH
        if mark.price.scale != contract.price_scale:
            return LinearAccountMarginProjectionFailureCode.VALUATION_MARK_SCALE_MISMATCH
        if mark.price.units <= 0:
            return LinearAccountMarginProjectionFailureCode.NON_POSITIVE_VALUATION_MARK
        if _mark_policy_invalid(evidence):
            return LinearAccountMarginProjectionFailureCode.VALUATION_MARK_POLICY_MISMATCH
        if mark.available_at > request.evaluated_at.instant:
            return LinearAccountMarginProjectionFailureCode.VALUATION_MARK_NOT_AVAILABLE
    if (
        request.unrealized_pnl_quantization.target_scale
        != request.settlement_cash_registration.scale
    ):
        return LinearAccountMarginProjectionFailureCode.QUANTIZATION_SCALE_MISMATCH
    if request.unrealized_pnl_quantization.rounding is not RoundingPolicy.HALF_EVEN:
        return LinearAccountMarginProjectionFailureCode.UNSAFE_UNREALIZED_PNL_ROUNDING
    if reservation.reservation_state.account_id != request.account_id:
        return LinearAccountMarginProjectionFailureCode.RESERVATION_CONTEXT_MISMATCH
    if any(
        value.currency != str(cash_key.currency_id)
        or value.scale != request.settlement_cash_registration.scale
        for value in reservation.reservation_state.totals.margin
    ):
        return LinearAccountMarginProjectionFailureCode.RESERVATION_MARGIN_CONTEXT_MISMATCH
    return None


def _reduced(currency: CurrencyId, numerator: int, denominator: int) -> ExactLinearUnrealizedPnl:
    divisor = gcd(abs(numerator), denominator)
    return ExactLinearUnrealizedPnl(currency, numerator // divisor, denominator // divisor)


def _exact_unrealized(evidence: LinearPositionValuationEvidence) -> ExactLinearUnrealizedPnl:
    state = evidence.position_state
    basis = state.average_entry_basis
    if basis is None:
        raise AssertionError("non-flat Position requires average-entry basis")
    quantity = state.quantity
    multiplier = state.contract.contract_multiplier
    mark = evidence.resolved_mark.price
    price_difference_numerator = mark.units * basis.denominator - basis.numerator * mark.scale.factor
    numerator = quantity.units * multiplier.units * price_difference_numerator
    denominator = (
        quantity.scale.factor
        * multiplier.scale.factor
        * mark.scale.factor
        * basis.denominator
    )
    return _reduced(state.contract.instrument.settlement_currency, numerator, denominator)


def _money(exact: ExactLinearUnrealizedPnl, policy: QuantizationPolicy) -> Money:
    return Money(
        round_ratio(
            exact.numerator * policy.target_scale.factor,
            exact.denominator,
            RoundingPolicy.HALF_EVEN,
        ),
        policy.target_scale,
        str(exact.currency_id),
    )


def _sum_money(values: tuple[Money, ...], *, scale, currency: str) -> Money:
    return Money(sum(value.units for value in values), scale, currency)


type _ProjectionValues = tuple[
    Money,
    Money,
    Money,
    Money,
    tuple[LinearPositionUnrealizedPnl, ...],
    Money,
    Money,
    Money,
    Money,
    Money,
    Money,
]


def _projection_values(request: LinearAccountMarginProjectionRequest) -> _ProjectionValues:
    if request.ledger_evidence is None or request.reservation_evidence is None:
        raise AssertionError("Projection values require evidence")
    key = _cash_key(request)
    if key is None:
        raise AssertionError("Projection values require Cash key")
    ledger = request.ledger_evidence.ledger_state
    scale = request.settlement_cash_registration.scale
    currency = str(key.currency_id)
    wallet = ledger.cash_amount(key)
    realized = ledger.realized_pnl_amount(key)
    fees = ledger.fee_amount(key)
    funding = ledger.financing_amount(key)
    position_values = tuple(
        LinearPositionUnrealizedPnl(
            evidence,
            evidence.valuation_evidence_hash,
            exact := _exact_unrealized(evidence),
            _money(exact, request.unrealized_pnl_quantization),
        )
        for evidence in request.position_valuations
    )
    total_unrealized = _sum_money(
        tuple(value.unrealized_pnl for value in position_values),
        scale=scale,
        currency=currency,
    )
    equity = Money(wallet.units + total_unrealized.units, scale, currency)
    total_initial = _sum_money(
        tuple(value.initial_margin for value in request.margin_results),
        scale=scale,
        currency=currency,
    )
    total_maintenance = _sum_money(
        tuple(value.maintenance_margin for value in request.margin_results),
        scale=scale,
        currency=currency,
    )
    working = _sum_money(
        request.reservation_evidence.reservation_state.totals.margin,
        scale=scale,
        currency=currency,
    )
    available = Money(equity.units - total_initial.units - working.units, scale, currency)
    return (
        wallet,
        realized,
        fees,
        funding,
        position_values,
        total_unrealized,
        equity,
        total_initial,
        total_maintenance,
        working,
        available,
    )


def _subject_ids(
    request: LinearAccountMarginProjectionRequest,
    code: LinearAccountMarginProjectionFailureCode,
) -> tuple[str, ...]:
    return (
        code.value,
        request.account_id,
        str(request.venue_id),
        canonical_sha256(request.settlement_cash_registration),
        (
            request.ledger_evidence.ledger_state.state_hash
            if request.ledger_evidence is not None
            else "missing-margin-ledger"
        ),
        (
            request.reservation_evidence.reservation_state.state_hash
            if request.reservation_evidence is not None
            else "missing-margin-reservation"
        ),
    )


@dataclass(frozen=True, slots=True)
class LinearAccountMarginProjection:
    component_ref: ProfileComponentRef
    request: LinearAccountMarginProjectionRequest
    request_hash: str
    wallet_balance: Money
    realized_pnl: Money
    fees: Money
    funding: Money
    position_unrealized_pnl: tuple[LinearPositionUnrealizedPnl, ...]
    total_unrealized_pnl: Money
    equity: Money
    total_initial_margin: Money
    total_maintenance_margin: Money
    working_order_margin_reservation: Money
    available_margin: Money

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Account Margin component")
        if type(self.request) is not LinearAccountMarginProjectionRequest:
            raise TypeError("request must be exact Projection Request")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match Request")
        if _evaluate_failure(self.request) is not None:
            raise ValueError("Projection Request must have no business failure")
        actual = (
            self.wallet_balance,
            self.realized_pnl,
            self.fees,
            self.funding,
            self.position_unrealized_pnl,
            self.total_unrealized_pnl,
            self.equity,
            self.total_initial_margin,
            self.total_maintenance_margin,
            self.working_order_margin_reservation,
            self.available_margin,
        )
        if actual != _projection_values(self.request):
            raise ValueError("Projection fields must match Request")

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_account_margin_projection",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "wallet_balance": self.wallet_balance,
            "realized_pnl": self.realized_pnl,
            "fees": self.fees,
            "funding": self.funding,
            "position_unrealized_pnl": self.position_unrealized_pnl,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "equity": self.equity,
            "total_initial_margin": self.total_initial_margin,
            "total_maintenance_margin": self.total_maintenance_margin,
            "working_order_margin_reservation": self.working_order_margin_reservation,
            "available_margin": self.available_margin,
        }


@dataclass(frozen=True, slots=True)
class LinearAccountMarginProjectionFailure:
    component_ref: ProfileComponentRef
    request: LinearAccountMarginProjectionRequest
    request_hash: str
    code: LinearAccountMarginProjectionFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Account Margin component")
        if type(self.request) is not LinearAccountMarginProjectionRequest:
            raise TypeError("request must be exact Projection Request")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match Request")
        if type(self.code) is not LinearAccountMarginProjectionFailureCode:
            raise TypeError("code must be exact Failure Code")
        expected = _evaluate_failure(self.request)
        if expected is None or expected is not self.code:
            raise ValueError("Failure code must match first Request failure")
        if self.subject_ids != _subject_ids(self.request, self.code):
            raise ValueError("subject_ids must match Request")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_account_margin_projection_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class LinearAccountMarginProjectionOutcome:
    component_ref: ProfileComponentRef
    request_hash: str
    projection: LinearAccountMarginProjection | None
    failure: LinearAccountMarginProjectionFailure | None

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Account Margin component")
        if (self.projection is None) == (self.failure is None):
            raise ValueError("Outcome requires exactly one Projection or Failure")
        value = self.projection if self.projection is not None else self.failure
        if value is None or value.component_ref != self.component_ref:
            raise ValueError("Outcome value component mismatch")
        if value.request_hash != self.request_hash:
            raise ValueError("Outcome request_hash mismatch")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_account_margin_projection_outcome",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request_hash": self.request_hash,
            "projection": self.projection,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class LinearAccountMarginProjector:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref()

    def project(
        self, request: LinearAccountMarginProjectionRequest, /
    ) -> LinearAccountMarginProjectionOutcome:
        if type(request) is not LinearAccountMarginProjectionRequest:
            raise TypeError("request must be exact Projection Request")
        code = _evaluate_failure(request)
        if code is not None:
            failure = LinearAccountMarginProjectionFailure(
                self.component_ref,
                request,
                request.request_hash,
                code,
                _subject_ids(request, code),
            )
            return LinearAccountMarginProjectionOutcome(
                self.component_ref, request.request_hash, None, failure
            )
        values = _projection_values(request)
        projection = LinearAccountMarginProjection(
            self.component_ref,
            request,
            request.request_hash,
            *values,
        )
        return LinearAccountMarginProjectionOutcome(
            self.component_ref, request.request_hash, projection, None
        )
