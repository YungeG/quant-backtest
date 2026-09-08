"""Conservative bar-extreme liquidation audit for linear perpetuals."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import gcd
from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    PositionBalanceKey,
    Price,
    PricePurpose,
    RoundingPolicy,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
    round_ratio,
)
from crypto_quant_trading import (
    ExactLinearMarginAmount,
    ExactLinearUnrealizedPnl,
    LinearAccountMarginProjection,
    LinearInstrumentMarginResult,
    LinearMarginTier,
    LinearPositionValuationEvidence,
)

from .ports import (
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortType,
)
from .resolution import RequestedResultGrade

_SCHEMA_VERSION = 1
_COMPONENT_KEY = "conservative.linear-perpetual.liquidation-audit.v1"
_LIMITATION = "bar-extremes-do-not-identify-intrabar-path-or-liquidation-time"
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


def _component_ref() -> SimulationComponentRef:
    digest = canonical_sha256(
        {
            "type": "conservative_linear_liquidation_audit_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "account_scope": "g09f-single-account-projection",
            "bar_purpose": "liquidation",
            "long_extreme": "low",
            "short_extreme": "high",
            "unrealized": "g09f-formula-half-even",
            "maintenance": "g09e-adverse-notional-tier-ceiling",
            "classification": "safe-or-ambiguous-breach",
            "decision_grade": "ambiguous-fails-closed",
            "limitation": _LIMITATION,
            "allowed_grade": "development",
        }
    )
    return SimulationComponentRef(
        SimulationPortType.LIQUIDATION_AUDIT_MODEL,
        _COMPONENT_KEY,
        1,
        digest,
    )


@dataclass(frozen=True, slots=True)
class LinearLiquidationAccountWindowEvidence:
    account_projection: LinearAccountMarginProjection
    interval_start: UtcInstant
    interval_end_exclusive: UtcInstant
    available_at: SimulationInstant
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        if type(self.account_projection) is not LinearAccountMarginProjection:
            raise TypeError("account_projection must be exact G09F Projection")
        if type(self.interval_start) is not UtcInstant or type(
            self.interval_end_exclusive
        ) is not UtcInstant:
            raise TypeError("window interval bounds must be exact UtcInstant")
        if self.interval_start >= self.interval_end_exclusive:
            raise ValueError("Account Window interval must be non-empty")
        _instant("available_at", self.available_at)
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_liquidation_account_window_evidence",
            "schema_version": _SCHEMA_VERSION,
            "account_projection": self.account_projection,
            "interval_start": self.interval_start,
            "interval_end_exclusive": self.interval_end_exclusive,
            "available_at": self.available_at,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class LinearLiquidationMarkBarEvidence:
    bar_id: str
    instrument_id: InstrumentId
    price_purpose: PricePurpose
    interval_start: UtcInstant
    interval_end_exclusive: UtcInstant
    low: Price
    high: Price
    closed_at: SimulationInstant
    available_at: SimulationInstant
    stream_id: str
    event_id: str
    revision_id: str
    supersedes_revision_id: str | None
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("bar_id", self.bar_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be exact PricePurpose")
        if type(self.interval_start) is not UtcInstant or type(
            self.interval_end_exclusive
        ) is not UtcInstant:
            raise TypeError("bar interval bounds must be exact UtcInstant")
        if self.interval_start >= self.interval_end_exclusive:
            raise ValueError("Liquidation Bar interval must be non-empty")
        if type(self.low) is not Price or type(self.high) is not Price:
            raise TypeError("low and high must be exact Price")
        _instant("closed_at", self.closed_at)
        _instant("available_at", self.available_at)
        for name, value in (
            ("stream_id", self.stream_id),
            ("event_id", self.event_id),
            ("revision_id", self.revision_id),
            ("source_key", self.source_key),
        ):
            _text(name, value)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        _hash("source_hash", self.source_hash)

    @property
    def bar_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_liquidation_mark_bar_evidence",
            "schema_version": _SCHEMA_VERSION,
            "bar_id": self.bar_id,
            "instrument_id": self.instrument_id,
            "price_purpose": self.price_purpose.value,
            "interval_start": self.interval_start,
            "interval_end_exclusive": self.interval_end_exclusive,
            "low": self.low,
            "high": self.high,
            "closed_at": self.closed_at,
            "available_at": self.available_at,
            "stream_id": self.stream_id,
            "event_id": self.event_id,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


class LinearLiquidationAuditClassification(str, Enum):
    SAFE = "safe"
    AMBIGUOUS_BREACH = "ambiguous_breach"


@dataclass(frozen=True, slots=True)
class LinearLiquidationAuditRequest:
    account_window: LinearLiquidationAccountWindowEvidence | None
    liquidation_bars: tuple[LinearLiquidationMarkBarEvidence, ...] | None
    audit_at: SimulationInstant
    requested_grade: RequestedResultGrade

    def __post_init__(self) -> None:
        if type(self.account_window) not in (
            type(None),
            LinearLiquidationAccountWindowEvidence,
        ):
            raise TypeError("account_window must be exact Evidence or None")
        if self.liquidation_bars is not None and (
            type(self.liquidation_bars) is not tuple
            or not all(
                type(value) is LinearLiquidationMarkBarEvidence
                for value in self.liquidation_bars
            )
        ):
            raise TypeError("liquidation_bars must be an exact tuple or None")
        _instant("audit_at", self.audit_at)
        if type(self.requested_grade) is not RequestedResultGrade:
            raise TypeError("requested_grade must be exact RequestedResultGrade")
        if self.liquidation_bars is not None:
            object.__setattr__(
                self,
                "liquidation_bars",
                tuple(
                    sorted(
                        self.liquidation_bars,
                        key=lambda value: (str(value.instrument_id), value.bar_id),
                    )
                ),
            )

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_liquidation_audit_request",
            "schema_version": _SCHEMA_VERSION,
            "account_window": self.account_window,
            "liquidation_bars": self.liquidation_bars,
            "audit_at": self.audit_at,
            "requested_grade": self.requested_grade.value,
        }


class LinearLiquidationAuditFailureCode(str, Enum):
    MISSING_ACCOUNT_WINDOW = "missing_account_window"
    MISSING_LIQUIDATION_BARS = "missing_liquidation_bars"
    PROJECTION_CONTEXT_MISMATCH = "projection_context_mismatch"
    ACCOUNT_WINDOW_INTERVAL_MISMATCH = "account_window_interval_mismatch"
    ACCOUNT_WINDOW_NOT_AVAILABLE = "account_window_not_available"
    DUPLICATE_LIQUIDATION_BAR = "duplicate_liquidation_bar"
    LIQUIDATION_BAR_COVERAGE_MISMATCH = "liquidation_bar_coverage_mismatch"
    LIQUIDATION_BAR_INTERVAL_MISMATCH = "liquidation_bar_interval_mismatch"
    LIQUIDATION_BAR_NOT_CLOSED = "liquidation_bar_not_closed"
    LIQUIDATION_BAR_NOT_AVAILABLE = "liquidation_bar_not_available"
    LIQUIDATION_BAR_PURPOSE_MISMATCH = "liquidation_bar_purpose_mismatch"
    LIQUIDATION_BAR_CONTEXT_MISMATCH = "liquidation_bar_context_mismatch"
    LIQUIDATION_BAR_SCALE_MISMATCH = "liquidation_bar_scale_mismatch"
    INVALID_LIQUIDATION_BAR_EXTREMES = "invalid_liquidation_bar_extremes"
    NEGATIVE_ADVERSE_MAINTENANCE = "negative_adverse_maintenance"
    AMBIGUOUS_BREACH_NOT_DECISION_GRADE = (
        "ambiguous_breach_not_decision_grade"
    )


def _position_key(value: LinearPositionValuationEvidence) -> PositionBalanceKey:
    return value.position_state.position_key


def _margin_key(value: LinearInstrumentMarginResult) -> PositionBalanceKey:
    return value.request.position_key


def _projection_context_invalid(projection: LinearAccountMarginProjection) -> bool:
    return (
        projection.component_ref.component_key
        != "account.linear-perpetual.margin-projection.v1"
        or projection.request_hash != projection.request.request_hash
    )


def _base_failure(
    request: LinearLiquidationAuditRequest,
) -> LinearLiquidationAuditFailureCode | None:
    window = request.account_window
    bars = request.liquidation_bars
    if window is None:
        return LinearLiquidationAuditFailureCode.MISSING_ACCOUNT_WINDOW
    projection = window.account_projection
    positions = projection.request.position_valuations
    if bars is None and positions:
        return LinearLiquidationAuditFailureCode.MISSING_LIQUIDATION_BARS
    if _projection_context_invalid(projection):
        return LinearLiquidationAuditFailureCode.PROJECTION_CONTEXT_MISMATCH
    if (
        projection.request.evaluated_at.instant != window.interval_start
        or window.available_at.instant < window.interval_end_exclusive
    ):
        return LinearLiquidationAuditFailureCode.ACCOUNT_WINDOW_INTERVAL_MISMATCH
    if window.available_at > request.audit_at:
        return LinearLiquidationAuditFailureCode.ACCOUNT_WINDOW_NOT_AVAILABLE
    supplied = () if bars is None else bars
    instrument_ids = tuple(value.instrument_id for value in supplied)
    bar_ids = tuple(value.bar_id for value in supplied)
    if len(instrument_ids) != len(set(instrument_ids)) or len(bar_ids) != len(
        set(bar_ids)
    ):
        return LinearLiquidationAuditFailureCode.DUPLICATE_LIQUIDATION_BAR
    position_ids = tuple(
        value.position_state.contract.instrument.instrument_id for value in positions
    )
    if set(instrument_ids) != set(position_ids):
        return LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_COVERAGE_MISMATCH
    for bar in supplied:
        if (
            bar.interval_start != window.interval_start
            or bar.interval_end_exclusive != window.interval_end_exclusive
        ):
            return LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_INTERVAL_MISMATCH
        if (
            bar.closed_at.instant < bar.interval_end_exclusive
            or bar.closed_at > bar.available_at
        ):
            return LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_NOT_CLOSED
        if bar.available_at > request.audit_at:
            return LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_NOT_AVAILABLE
        if bar.price_purpose is not PricePurpose.LIQUIDATION:
            return LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_PURPOSE_MISMATCH
        position = next(
            value for value in positions if value.position_state.contract.instrument.instrument_id == bar.instrument_id
        )
        contract = position.position_state.contract
        if (
            bar.low.instrument_id != str(bar.instrument_id)
            or bar.high.instrument_id != str(bar.instrument_id)
            or bar.low.quote_currency
            != str(contract.instrument.settlement_currency)
            or bar.high.quote_currency
            != str(contract.instrument.settlement_currency)
        ):
            return LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_CONTEXT_MISMATCH
        if (
            bar.low.scale != contract.price_scale
            or bar.high.scale != contract.price_scale
        ):
            return LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_SCALE_MISMATCH
        if (
            bar.low.units <= 0
            or bar.high.units <= 0
            or bar.low.units > bar.high.units
        ):
            return LinearLiquidationAuditFailureCode.INVALID_LIQUIDATION_BAR_EXTREMES
    return None


def _reduced_pnl(
    currency: CurrencyId, numerator: int, denominator: int
) -> ExactLinearUnrealizedPnl:
    divisor = gcd(abs(numerator), denominator)
    return ExactLinearUnrealizedPnl(
        currency, numerator // divisor, denominator // divisor
    )


def _reduced_margin(
    currency: CurrencyId, numerator: int, denominator: int
) -> ExactLinearMarginAmount:
    divisor = gcd(abs(numerator), denominator)
    return ExactLinearMarginAmount(
        currency, numerator // divisor, denominator // divisor
    )


def _adverse_price(
    valuation: LinearPositionValuationEvidence,
    bar: LinearLiquidationMarkBarEvidence,
) -> tuple[str, Price]:
    if valuation.position_state.quantity.units > 0:
        return "long", bar.low
    return "short", bar.high


def _exact_unrealized(
    valuation: LinearPositionValuationEvidence, price: Price
) -> ExactLinearUnrealizedPnl:
    state = valuation.position_state
    basis = state.average_entry_basis
    if basis is None:
        raise AssertionError("Liquidation audit requires non-flat Position")
    quantity = state.quantity
    multiplier = state.contract.contract_multiplier
    difference = price.units * basis.denominator - basis.numerator * price.scale.factor
    return _reduced_pnl(
        state.contract.instrument.settlement_currency,
        quantity.units * multiplier.units * difference,
        quantity.scale.factor
        * multiplier.scale.factor
        * price.scale.factor
        * basis.denominator,
    )


def _exact_notional(
    valuation: LinearPositionValuationEvidence, price: Price
) -> ExactLinearMarginAmount:
    state = valuation.position_state
    quantity = state.quantity
    multiplier = state.contract.contract_multiplier
    return _reduced_margin(
        state.contract.instrument.settlement_currency,
        abs(quantity.units) * multiplier.units * price.units,
        quantity.scale.factor * multiplier.scale.factor * price.scale.factor,
    )


def _contains(tier: LinearMarginTier, amount: ExactLinearMarginAmount) -> bool:
    floor = tier.notional_floor
    if amount.numerator * floor.scale.factor < floor.units * amount.denominator:
        return False
    cap = tier.notional_cap
    return cap is None or amount.numerator * cap.scale.factor < cap.units * amount.denominator


def _adverse_tier(
    margin: LinearInstrumentMarginResult, notional: ExactLinearMarginAmount
) -> LinearMarginTier:
    matches = tuple(
        tier for tier in margin.resolved_interval.tiers if _contains(tier, notional)
    )
    if len(matches) != 1:
        raise AssertionError("validated G09E Tier set must select one adverse Tier")
    return matches[0]


def _exact_maintenance(
    notional: ExactLinearMarginAmount, tier: LinearMarginTier
) -> ExactLinearMarginAmount:
    rate = tier.maintenance_margin_rate
    deduction = tier.maintenance_margin_deduction
    return _reduced_margin(
        notional.currency_id,
        notional.numerator * rate.units * deduction.scale.factor
        - deduction.units * notional.denominator * rate.scale.factor,
        notional.denominator * rate.scale.factor * deduction.scale.factor,
    )


def _quantized(
    numerator: int,
    denominator: int,
    *,
    scale,
    currency: CurrencyId,
    rounding: RoundingPolicy,
) -> Money:
    return Money(
        round_ratio(numerator * scale.factor, denominator, rounding),
        scale,
        str(currency),
    )


def _position_values(
    valuation: LinearPositionValuationEvidence,
    margin: LinearInstrumentMarginResult,
    bar: LinearLiquidationMarkBarEvidence,
) -> tuple[
    str,
    Price,
    LinearMarginTier,
    ExactLinearUnrealizedPnl,
    Money,
    ExactLinearMarginAmount,
    Money,
]:
    direction, price = _adverse_price(valuation, bar)
    exact_unrealized = _exact_unrealized(valuation, price)
    scale = margin.initial_margin.scale
    currency = exact_unrealized.currency_id
    unrealized = _quantized(
        exact_unrealized.numerator,
        exact_unrealized.denominator,
        scale=scale,
        currency=currency,
        rounding=RoundingPolicy.HALF_EVEN,
    )
    notional = _exact_notional(valuation, price)
    tier = _adverse_tier(margin, notional)
    exact_maintenance = _exact_maintenance(notional, tier)
    maintenance = _quantized(
        exact_maintenance.numerator,
        exact_maintenance.denominator,
        scale=scale,
        currency=currency,
        rounding=RoundingPolicy.CEILING,
    )
    return (
        direction,
        price,
        tier,
        exact_unrealized,
        unrealized,
        exact_maintenance,
        maintenance,
    )


@dataclass(frozen=True, slots=True)
class LinearLiquidationPositionAudit:
    position_valuation: LinearPositionValuationEvidence
    margin_result: LinearInstrumentMarginResult
    position_key: PositionBalanceKey
    direction: str
    bar: LinearLiquidationMarkBarEvidence
    adverse_price: Price
    resolved_tier: LinearMarginTier
    exact_adverse_unrealized: ExactLinearUnrealizedPnl
    adverse_unrealized: Money
    exact_adverse_maintenance: ExactLinearMarginAmount
    adverse_maintenance: Money

    def __post_init__(self) -> None:
        if type(self.position_valuation) is not LinearPositionValuationEvidence:
            raise TypeError("position_valuation must be exact G09F Evidence")
        if type(self.margin_result) is not LinearInstrumentMarginResult:
            raise TypeError("margin_result must be exact G09E Result")
        if type(self.bar) is not LinearLiquidationMarkBarEvidence:
            raise TypeError("bar must be exact Liquidation Bar")
        state = self.position_valuation.position_state
        if self.position_key != state.position_key:
            raise ValueError("position_key must match Position Evidence")
        if (
            self.margin_result.request.position_key != self.position_key
            or self.margin_result.request.contract != state.contract
            or self.margin_result.request.exposure_quantity != state.quantity
        ):
            raise ValueError("margin_result must match Position Evidence")
        if (
            self.bar.instrument_id != state.contract.instrument.instrument_id
            or self.bar.price_purpose is not PricePurpose.LIQUIDATION
            or self.bar.low.instrument_id != str(self.bar.instrument_id)
            or self.bar.high.instrument_id != str(self.bar.instrument_id)
            or self.bar.low.scale != state.contract.price_scale
            or self.bar.high.scale != state.contract.price_scale
            or self.bar.low.units <= 0
            or self.bar.high.units <= 0
            or self.bar.low.units > self.bar.high.units
        ):
            raise ValueError("bar must match Position Evidence")
        expected = _position_values(
            self.position_valuation, self.margin_result, self.bar
        )
        actual = (
            self.direction,
            self.adverse_price,
            self.resolved_tier,
            self.exact_adverse_unrealized,
            self.adverse_unrealized,
            self.exact_adverse_maintenance,
            self.adverse_maintenance,
        )
        if actual != expected:
            raise ValueError("Position Audit fields must match embedded authority")

    @property
    def audit_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_liquidation_position_audit",
            "schema_version": _SCHEMA_VERSION,
            "position_valuation": self.position_valuation,
            "margin_result": self.margin_result,
            "position_key": self.position_key,
            "direction": self.direction,
            "bar": self.bar,
            "adverse_price": self.adverse_price,
            "resolved_tier": self.resolved_tier,
            "exact_adverse_unrealized": self.exact_adverse_unrealized,
            "adverse_unrealized": self.adverse_unrealized,
            "exact_adverse_maintenance": self.exact_adverse_maintenance,
            "adverse_maintenance": self.adverse_maintenance,
        }


type _AuditValues = tuple[
    tuple[LinearLiquidationPositionAudit, ...],
    Money,
    Money,
    Money,
    Money,
    LinearLiquidationAuditClassification,
]


def _position_audit(
    valuation: LinearPositionValuationEvidence,
    margin: LinearInstrumentMarginResult,
    bar: LinearLiquidationMarkBarEvidence,
) -> LinearLiquidationPositionAudit:
    direction, price, tier, exact_pnl, pnl, exact_margin, maintenance = (
        _position_values(valuation, margin, bar)
    )
    return LinearLiquidationPositionAudit(
        valuation,
        margin,
        _position_key(valuation),
        direction,
        bar,
        price,
        tier,
        exact_pnl,
        pnl,
        exact_margin,
        maintenance,
    )


def _audit_values(request: LinearLiquidationAuditRequest) -> _AuditValues:
    window = request.account_window
    if window is None:
        raise AssertionError("Audit values require Account Window")
    projection = window.account_projection
    bars = () if request.liquidation_bars is None else request.liquidation_bars
    bar_by_instrument = {value.instrument_id: value for value in bars}
    margin_by_key = {
        _margin_key(value): value for value in projection.request.margin_results
    }
    audits = tuple(
        _position_audit(
            valuation,
            margin_by_key[_position_key(valuation)],
            bar_by_instrument[
                valuation.position_state.contract.instrument.instrument_id
            ],
        )
        for valuation in projection.request.position_valuations
    )
    scale = projection.wallet_balance.scale
    currency = projection.wallet_balance.currency
    adverse_unrealized = Money(
        sum(value.adverse_unrealized.units for value in audits), scale, currency
    )
    adverse_equity = Money(
        projection.wallet_balance.units + adverse_unrealized.units,
        scale,
        currency,
    )
    adverse_maintenance = Money(
        sum(value.adverse_maintenance.units for value in audits), scale, currency
    )
    classification = (
        LinearLiquidationAuditClassification.SAFE
        if adverse_equity.units >= adverse_maintenance.units
        else LinearLiquidationAuditClassification.AMBIGUOUS_BREACH
    )
    return (
        audits,
        projection.wallet_balance,
        adverse_unrealized,
        adverse_equity,
        adverse_maintenance,
        classification,
    )


def _failure_code(
    request: LinearLiquidationAuditRequest,
) -> LinearLiquidationAuditFailureCode | None:
    code = _base_failure(request)
    if code is not None:
        return code
    values = _audit_values(request)
    if any(value.exact_adverse_maintenance.numerator < 0 for value in values[0]):
        return LinearLiquidationAuditFailureCode.NEGATIVE_ADVERSE_MAINTENANCE
    if (
        values[-1] is LinearLiquidationAuditClassification.AMBIGUOUS_BREACH
        and request.requested_grade is RequestedResultGrade.DECISION_GRADE
    ):
        return LinearLiquidationAuditFailureCode.AMBIGUOUS_BREACH_NOT_DECISION_GRADE
    return None


def _subject_ids(
    request: LinearLiquidationAuditRequest,
    code: LinearLiquidationAuditFailureCode,
) -> tuple[str, ...]:
    return (
        code.value,
        (
            request.account_window.account_projection.projection_hash
            if request.account_window is not None
            else "missing-account-window"
        ),
        str(request.audit_at.instant.epoch_nanoseconds),
        request.requested_grade.value,
    )


@dataclass(frozen=True, slots=True)
class LinearLiquidationAuditResult:
    component_ref: SimulationComponentRef
    request: LinearLiquidationAuditRequest
    input_hash: str
    classification: LinearLiquidationAuditClassification
    position_audits: tuple[LinearLiquidationPositionAudit, ...]
    wallet_balance: Money
    adverse_unrealized: Money
    adverse_equity: Money
    adverse_maintenance: Money
    decision_grade_eligible: bool
    limitation: str

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Liquidation Audit component")
        if type(self.request) is not LinearLiquidationAuditRequest:
            raise TypeError("request must be exact Liquidation Audit Request")
        if self.input_hash != self.request.request_hash:
            raise ValueError("input_hash must match Request")
        if _failure_code(self.request) is not None:
            raise ValueError("Result Request must have no business failure")
        values = _audit_values(self.request)
        expected = (
            values[-1],
            values[0],
            values[1],
            values[2],
            values[3],
            values[4],
            values[-1] is LinearLiquidationAuditClassification.SAFE,
            _LIMITATION,
        )
        actual = (
            self.classification,
            self.position_audits,
            self.wallet_balance,
            self.adverse_unrealized,
            self.adverse_equity,
            self.adverse_maintenance,
            self.decision_grade_eligible,
            self.limitation,
        )
        if actual != expected:
            raise ValueError("Result fields must match Request")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_liquidation_audit_result",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "input_hash": self.input_hash,
            "classification": self.classification.value,
            "position_audits": self.position_audits,
            "wallet_balance": self.wallet_balance,
            "adverse_unrealized": self.adverse_unrealized,
            "adverse_equity": self.adverse_equity,
            "adverse_maintenance": self.adverse_maintenance,
            "decision_grade_eligible": self.decision_grade_eligible,
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class LinearLiquidationAuditFailure:
    component_ref: SimulationComponentRef
    request: LinearLiquidationAuditRequest
    input_hash: str
    code: LinearLiquidationAuditFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Liquidation Audit component")
        if type(self.request) is not LinearLiquidationAuditRequest:
            raise TypeError("request must be exact Liquidation Audit Request")
        if self.input_hash != self.request.request_hash:
            raise ValueError("input_hash must match Request")
        if type(self.code) is not LinearLiquidationAuditFailureCode:
            raise TypeError("code must be exact Liquidation Audit Failure Code")
        expected = _failure_code(self.request)
        if expected is None or expected is not self.code:
            raise ValueError("Failure code must match first Request failure")
        if self.subject_ids != _subject_ids(self.request, self.code):
            raise ValueError("subject_ids must match Request")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_liquidation_audit_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "input_hash": self.input_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class ConservativeLinearLiquidationAuditModel:
    @property
    def component_ref(self) -> SimulationComponentRef:
        return _component_ref()

    def audit_liquidation(
        self, request: LinearLiquidationAuditRequest, /
    ) -> SimulationPortOutcome[
        LinearLiquidationAuditResult, LinearLiquidationAuditFailure
    ]:
        if type(request) is not LinearLiquidationAuditRequest:
            raise TypeError("request must be exact Liquidation Audit Request")
        code = _failure_code(request)
        if code is not None:
            failure = LinearLiquidationAuditFailure(
                self.component_ref,
                request,
                request.request_hash,
                code,
                _subject_ids(request, code),
            )
            return SimulationPortOutcome.for_failure(
                self.component_ref, request, failure
            )
        values = _audit_values(request)
        result = LinearLiquidationAuditResult(
            self.component_ref,
            request,
            request.request_hash,
            values[-1],
            values[0],
            values[1],
            values[2],
            values[3],
            values[4],
            values[-1] is LinearLiquidationAuditClassification.SAFE,
            _LIMITATION,
        )
        return SimulationPortOutcome.for_result(self.component_ref, request, result)
