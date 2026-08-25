"""Deterministic next-real-bar-open execution eligibility and full-fill construction."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Self, cast

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    DomainIdKind,
    Fill,
    Money,
    OrderStatus,
    Price,
    PricePurpose,
    Quantity,
    Scale,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent
from crypto_quant_trading import (
    MarketRuleApproval,
    MarketSessionState,
    OrderEventStream,
    PreTradeRiskApproval,
    ResolvedMark,
)

from .ports import (
    SimulationCapabilityRequirement,
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortSpec,
    SimulationPortType,
)
from .slippage import (
    ExecutionReferencePrice,
    SlippageApplicabilityViolation,
    SlippageDecision,
    SlippageMarketState,
    SlippageRequest,
)

BAR_OPEN_CAPABILITY = MarketBundleCapability("bar_open", 1)
BAR_OPEN_EVENT_TYPE = "bar_open"
_COMPONENT_KEY = "next_eligible_bar_open.v1"
_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if not value or value.strip() != value or unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be non-empty canonical text")
    return value


def _require_hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")
    return value


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


class BarOpenKind(str, Enum):
    REAL = "real"
    GAP_PLACEHOLDER = "gap_placeholder"
    FORWARD_FILLED = "forward_filled"


class BarIneligibilityReason(str, Enum):
    GAP_PLACEHOLDER = "gap_placeholder"
    FORWARD_FILLED = "forward_filled"
    LIQUIDITY_BLOCKED = "liquidity_blocked"
    NO_ELIGIBLE_BAR = "no_eligible_bar"


class NoEligibleBarAction(str, Enum):
    FULL_FILL = "full_fill"
    KEEP_ACTIVE = "keep_active"
    EXPIRE = "expire"


@dataclass(frozen=True)
class BarOpenObservation:
    event: MarketEvent
    kind: BarOpenKind
    open_price: Price | None

    def __post_init__(self) -> None:
        if not isinstance(self.event, MarketEvent):
            raise TypeError("event must be MarketEvent")
        if self.event.capability != BAR_OPEN_CAPABILITY:
            raise ValueError("MarketEvent must have bar_open@1 capability")
        if self.event.event_type != BAR_OPEN_EVENT_TYPE:
            raise ValueError("MarketEvent must have bar_open event type")
        if self.event.instrument_id is None:
            raise ValueError("bar open event requires Instrument identity")
        if self.event.available_time != self.event.event_time:
            raise ValueError("bar open must be available at its event time")
        if not isinstance(self.kind, BarOpenKind):
            raise TypeError("kind must be BarOpenKind")
        if self.kind is BarOpenKind.REAL:
            if not isinstance(self.open_price, Price):
                raise TypeError("real bar requires open_price")
            if self.open_price.units <= 0:
                raise ValueError("real bar open price must be positive")
            if self.open_price.instrument_id != str(self.event.instrument_id):
                raise ValueError("bar open price instrument mismatch")
        elif self.open_price is not None:
            raise ValueError("non-real bar cannot carry an execution open price")

    @classmethod
    def from_event(cls, event: MarketEvent) -> Self:
        if not isinstance(event, MarketEvent):
            raise TypeError("event must be MarketEvent")
        expected_fields = {"schema_version", "bar_kind", "open_price"}
        if set(event.payload) != expected_fields:
            raise ValueError("bar open payload must contain exact fields")
        if event.payload["schema_version"] != 1:
            raise ValueError("unsupported bar open schema_version")
        try:
            kind = BarOpenKind(event.payload["bar_kind"])
        except (TypeError, ValueError) as error:
            raise ValueError("unsupported bar_kind") from error
        raw_price = event.payload["open_price"]
        if kind is not BarOpenKind.REAL:
            if raw_price is not None:
                raise ValueError("non-real bar open_price must be null")
            return cls(event=event, kind=kind, open_price=None)
        if not isinstance(raw_price, Mapping) or set(raw_price) != {
            "units",
            "scale",
            "quote_currency",
        }:
            raise ValueError("real bar open_price must contain exact fields")
        if event.instrument_id is None:
            raise ValueError("bar open event requires Instrument identity")
        price = Price(
            units=_integer("open_price.units", raw_price["units"]),
            scale=Scale(_integer("open_price.scale", raw_price["scale"])),
            instrument_id=str(event.instrument_id),
            quote_currency=_canonical_text(
                "open_price.quote_currency", raw_price["quote_currency"]
            ),
        )
        return cls(event=event, kind=kind, open_price=price)

    @property
    def observation_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "bar_open_observation",
            "schema_version": 1,
            "event": self.event,
            "bar_kind": self.kind.value,
            "open_price": self.open_price,
        }


@dataclass(frozen=True)
class BarLiquidityEvidence:
    evidence_key: str
    evidence_version: int
    market_event_id: str
    market_event_hash: str
    evaluated_at: UtcInstant
    approved: bool
    reason_code: str | None
    source_hash: str
    evidence_id: str

    def __post_init__(self) -> None:
        _canonical_text("evidence_key", self.evidence_key)
        if isinstance(self.evidence_version, bool) or not isinstance(
            self.evidence_version, int
        ):
            raise TypeError("evidence_version must be an integer")
        if self.evidence_version <= 0:
            raise ValueError("evidence_version must be positive")
        _canonical_text("market_event_id", self.market_event_id)
        _require_hash("market_event_hash", self.market_event_hash)
        if not isinstance(self.evaluated_at, UtcInstant):
            raise TypeError("evaluated_at must be UtcInstant")
        if type(self.approved) is not bool:
            raise TypeError("approved must be bool")
        if self.approved and self.reason_code is not None:
            raise ValueError("approved liquidity evidence cannot carry reason_code")
        if not self.approved and self.reason_code is None:
            raise ValueError("blocked liquidity evidence requires reason_code")
        if self.reason_code is not None:
            _canonical_text("reason_code", self.reason_code)
        _require_hash("source_hash", self.source_hash)
        _require_hash("evidence_id", self.evidence_id)
        if self.evidence_id != canonical_sha256(self._identity_payload()):
            raise ValueError("liquidity evidence_id mismatch")

    @classmethod
    def create(
        cls,
        *,
        evidence_key: str,
        evidence_version: int,
        market_event: MarketEvent,
        evaluated_at: UtcInstant,
        approved: bool,
        reason_code: str | None,
        source_hash: str,
    ) -> Self:
        payload = {
            "type": "bar_liquidity_evidence_identity",
            "schema_version": 1,
            "evidence_key": evidence_key,
            "evidence_version": evidence_version,
            "market_event_id": market_event.event_id,
            "market_event_hash": market_event.event_hash,
            "evaluated_at": evaluated_at,
            "approved": approved,
            "reason_code": reason_code,
            "source_hash": source_hash,
        }
        return cls(
            evidence_key=evidence_key,
            evidence_version=evidence_version,
            market_event_id=market_event.event_id,
            market_event_hash=market_event.event_hash,
            evaluated_at=evaluated_at,
            approved=approved,
            reason_code=reason_code,
            source_hash=source_hash,
            evidence_id=canonical_sha256(payload),
        )

    def _identity_payload(self) -> dict[str, object]:
        return {
            "type": "bar_liquidity_evidence_identity",
            "schema_version": 1,
            "evidence_key": self.evidence_key,
            "evidence_version": self.evidence_version,
            "market_event_id": self.market_event_id,
            "market_event_hash": self.market_event_hash,
            "evaluated_at": self.evaluated_at,
            "approved": self.approved,
            "reason_code": self.reason_code,
            "source_hash": self.source_hash,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "bar_liquidity_evidence",
            "schema_version": 1,
            "evidence_id": self.evidence_id,
            **{
                key: value
                for key, value in self._identity_payload().items()
                if key not in {"type", "schema_version"}
            },
        }


@dataclass(frozen=True)
class BarOpenCandidate:
    observation: BarOpenObservation
    market_rule_approval: MarketRuleApproval | None
    pretrade_risk_approval: PreTradeRiskApproval | None
    liquidity_evidence: BarLiquidityEvidence | None
    market_state: SlippageMarketState | None

    def __post_init__(self) -> None:
        if not isinstance(self.observation, BarOpenObservation):
            raise TypeError("observation must be BarOpenObservation")
        if self.market_rule_approval is not None and not isinstance(
            self.market_rule_approval, MarketRuleApproval
        ):
            raise TypeError("market_rule_approval must be MarketRuleApproval or None")
        if self.pretrade_risk_approval is not None and not isinstance(
            self.pretrade_risk_approval, PreTradeRiskApproval
        ):
            raise TypeError("pretrade_risk_approval must be PreTradeRiskApproval or None")
        if self.liquidity_evidence is not None:
            if not isinstance(self.liquidity_evidence, BarLiquidityEvidence):
                raise TypeError("liquidity_evidence must be BarLiquidityEvidence or None")
            if (
                self.liquidity_evidence.market_event_id != self.observation.event.event_id
                or self.liquidity_evidence.market_event_hash
                != self.observation.event.event_hash
            ):
                raise ValueError("liquidity evidence MarketEvent mismatch")
        if self.market_state is not None and not isinstance(
            self.market_state, SlippageMarketState
        ):
            raise TypeError("market_state must be SlippageMarketState or None")
        if self.observation.kind is not BarOpenKind.REAL and any(
            value is not None
            for value in (
                self.market_rule_approval,
                self.pretrade_risk_approval,
                self.liquidity_evidence,
                self.market_state,
            )
        ):
            raise ValueError("non-real bar cannot carry execution gate evidence")

    @property
    def candidate_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "bar_open_candidate",
            "schema_version": 1,
            "observation": self.observation,
            "market_rule_approval": self.market_rule_approval,
            "pretrade_risk_approval": self.pretrade_risk_approval,
            "liquidity_evidence": self.liquidity_evidence,
            "market_state": self.market_state,
        }


@dataclass(frozen=True)
class NextBarOpenApplicability:
    tif_actions: tuple[tuple[TimeInForce, NoEligibleBarAction], ...]

    def __post_init__(self) -> None:
        if type(self.tif_actions) is not tuple:
            raise TypeError("tif_actions must be tuple")
        normalized: list[tuple[TimeInForce, NoEligibleBarAction]] = []
        for rule in self.tif_actions:
            if type(rule) is not tuple or len(rule) != 2:
                raise TypeError("each tif action must be a pair")
            tif, action = rule
            if not isinstance(tif, TimeInForce):
                raise TypeError("tif action key must be TimeInForce")
            if not isinstance(action, NoEligibleBarAction):
                raise TypeError("tif action value must be NoEligibleBarAction")
            if action is NoEligibleBarAction.FULL_FILL:
                raise ValueError("TIF no-eligible action cannot be full_fill")
            normalized.append((tif, action))
        if len(normalized) != len({tif for tif, _ in normalized}):
            raise ValueError("duplicate TimeInForce action")
        if {tif for tif, _ in normalized} != set(TimeInForce):
            raise ValueError("tif_actions must cover every TimeInForce")
        object.__setattr__(
            self,
            "tif_actions",
            tuple(sorted(normalized, key=lambda value: value[0].value)),
        )

    def action_for(self, tif: TimeInForce) -> NoEligibleBarAction:
        return dict(self.tif_actions)[tif]

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "next_bar_open_applicability",
            "schema_version": 1,
            "tif_actions": [
                {"time_in_force": tif.value, "action": action.value}
                for tif, action in self.tif_actions
            ],
        }


@dataclass(frozen=True)
class NextBarOpenRequest:
    order_stream: OrderEventStream
    candidate: BarOpenCandidate | None
    eligibility_window_exhausted: bool

    def __post_init__(self) -> None:
        if not isinstance(self.order_stream, OrderEventStream):
            raise TypeError("order_stream must be OrderEventStream")
        if self.candidate is not None and not isinstance(
            self.candidate, BarOpenCandidate
        ):
            raise TypeError("candidate must be BarOpenCandidate or None")
        if type(self.eligibility_window_exhausted) is not bool:
            raise TypeError("eligibility_window_exhausted must be bool")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "next_bar_open_request",
            "schema_version": 1,
            "order_stream_hash": self.order_stream.stream_hash,
            "order_state_hash": self.order_stream.state_hash,
            "candidate": self.candidate,
            "eligibility_window_exhausted": self.eligibility_window_exhausted,
        }


class NextBarOpenFailureCode(str, Enum):
    ORDER_STATE_INELIGIBLE = "order_state_ineligible"
    ORDER_ALREADY_FILLED = "order_already_filled"
    SAME_BAR_FORBIDDEN = "same_bar_forbidden"
    CANDIDATE_CONTEXT_MISMATCH = "candidate_context_mismatch"
    MISSING_GATE_APPROVAL = "missing_gate_approval"
    GATE_EVIDENCE_MISMATCH = "gate_evidence_mismatch"
    MARKET_RULE_INTERVAL_MISMATCH = "market_rule_interval_mismatch"
    MARKET_SESSION_CLOSED = "market_session_closed"
    LIQUIDITY_EVIDENCE_MISMATCH = "liquidity_evidence_mismatch"
    FUTURE_MARKET_STATE = "future_market_state"


@dataclass(frozen=True)
class NextBarOpenFailure:
    request: NextBarOpenRequest
    component_ref: SimulationComponentRef
    code: NextBarOpenFailureCode
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, NextBarOpenRequest):
            raise TypeError("request must be NextBarOpenRequest")
        _validate_execution_component(self.component_ref)
        if not isinstance(self.code, NextBarOpenFailureCode):
            raise TypeError("code must be NextBarOpenFailureCode")
        _canonical_text("subject_key", self.subject_key)

    @property
    def failure_id(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "next_bar_open_failure",
            "schema_version": 1,
            "failure_id": canonical_sha256(
                {
                    "request": self.request,
                    "component_ref": self.component_ref,
                    "code": self.code.value,
                    "subject_key": self.subject_key,
                }
            ),
            "request": self.request,
            "component_ref": self.component_ref,
            "code": self.code.value,
            "subject_key": self.subject_key,
        }


@dataclass(frozen=True)
class NextBarOpenDecision:
    request: NextBarOpenRequest
    component_ref: SimulationComponentRef
    applicability: NextBarOpenApplicability
    action: NoEligibleBarAction
    candidate: BarOpenCandidate | None
    reference_price: ExecutionReferencePrice | None
    fill_quantity: Quantity | None
    ineligibility_reason: BarIneligibilityReason | None

    def __post_init__(self) -> None:
        if not isinstance(self.request, NextBarOpenRequest):
            raise TypeError("request must be NextBarOpenRequest")
        _validate_execution_component(self.component_ref)
        if not isinstance(self.applicability, NextBarOpenApplicability):
            raise TypeError("applicability must be NextBarOpenApplicability")
        if not isinstance(self.action, NoEligibleBarAction):
            raise TypeError("action must be NoEligibleBarAction")
        if self.candidate != self.request.candidate:
            raise ValueError("decision candidate must match request")
        if self.action is NoEligibleBarAction.FULL_FILL:
            if self.candidate is None or self.candidate.observation.kind is not BarOpenKind.REAL:
                raise ValueError("full fill requires real candidate")
            if not isinstance(self.reference_price, ExecutionReferencePrice):
                raise TypeError("full fill requires ExecutionReferencePrice")
            if not isinstance(self.fill_quantity, Quantity) or self.fill_quantity.units <= 0:
                raise ValueError("full fill requires positive Quantity")
            if self.ineligibility_reason is not None:
                raise ValueError("full fill cannot carry ineligibility reason")
            state = self.request.order_stream.state
            if state is None or self.fill_quantity != state.remaining_quantity:
                raise ValueError("full fill quantity must equal exact remaining Quantity")
            if self.reference_price.mark.source_event_id != self.candidate.observation.event.event_id:
                raise ValueError("reference price source event mismatch")
        else:
            if self.reference_price is not None or self.fill_quantity is not None:
                raise ValueError("no-fill decision cannot carry reference or fill Quantity")
            if not isinstance(self.ineligibility_reason, BarIneligibilityReason):
                raise TypeError("no-fill decision requires ineligibility reason")

    @property
    def decision_id(self) -> str:
        return canonical_sha256(self._canonical_body())

    def _canonical_body(self) -> dict[str, object]:
        return {
            "request": self.request,
            "component_ref": self.component_ref,
            "applicability": self.applicability,
            "action": self.action.value,
            "candidate": self.candidate,
            "reference_price": self.reference_price,
            "fill_quantity": self.fill_quantity,
            "ineligibility_reason": (
                None
                if self.ineligibility_reason is None
                else self.ineligibility_reason.value
            ),
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "next_bar_open_decision",
            "schema_version": 1,
            "decision_id": self.decision_id,
            **self._canonical_body(),
        }


def _validate_execution_component(component_ref: SimulationComponentRef) -> None:
    if not isinstance(component_ref, SimulationComponentRef):
        raise TypeError("component_ref must be SimulationComponentRef")
    if component_ref.port_type is not SimulationPortType.EXECUTION_MODEL:
        raise ValueError("component_ref must target EXECUTION_MODEL")
    if component_ref.component_key != _COMPONENT_KEY or component_ref.component_version != 1:
        raise ValueError("component_ref must identify next_eligible_bar_open.v1")


def _no_fill_action(
    request: NextBarOpenRequest,
    applicability: NextBarOpenApplicability,
) -> NoEligibleBarAction:
    if not request.eligibility_window_exhausted:
        return NoEligibleBarAction.KEEP_ACTIVE
    return applicability.action_for(request.order_stream.order.intent.time_in_force)


def _failure(
    request: NextBarOpenRequest,
    component_ref: SimulationComponentRef,
    code: NextBarOpenFailureCode,
    subject_key: str,
) -> SimulationPortOutcome[NextBarOpenDecision, NextBarOpenFailure]:
    return SimulationPortOutcome.for_failure(
        component_ref,
        request,
        NextBarOpenFailure(request, component_ref, code, subject_key),
    )


@dataclass(frozen=True)
class NextEligibleBarOpenModel:
    component_ref: SimulationComponentRef
    applicability: NextBarOpenApplicability

    def __post_init__(self) -> None:
        _validate_execution_component(self.component_ref)
        if not isinstance(self.applicability, NextBarOpenApplicability):
            raise TypeError("applicability must be NextBarOpenApplicability")
        if self.component_ref.component_digest != canonical_sha256(self.applicability):
            raise ValueError("component digest must match applicability")

    @classmethod
    def create(
        cls,
        *,
        actions: tuple[tuple[TimeInForce, NoEligibleBarAction], ...],
    ) -> Self:
        applicability = NextBarOpenApplicability(actions)
        return cls(
            component_ref=SimulationComponentRef(
                port_type=SimulationPortType.EXECUTION_MODEL,
                component_key=_COMPONENT_KEY,
                component_version=1,
                component_digest=canonical_sha256(applicability),
            ),
            applicability=applicability,
        )

    def spec(self) -> SimulationPortSpec:
        return SimulationPortSpec(
            component_ref=self.component_ref,
            required_capabilities=(
                SimulationCapabilityRequirement("bar_open", 1),
            ),
            applicability=self.applicability,
        )

    def simulate_execution(
        self, request: NextBarOpenRequest, /
    ) -> SimulationPortOutcome[NextBarOpenDecision, NextBarOpenFailure]:
        if not isinstance(request, NextBarOpenRequest):
            raise TypeError("request must be NextBarOpenRequest")
        stream = request.order_stream
        state = stream.state
        if state is None or state.status not in {OrderStatus.ACCEPTED, OrderStatus.ACTIVE}:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.ORDER_STATE_INELIGIBLE,
                "order_state",
            )
        if state.cumulative_filled_quantity.units != 0:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.ORDER_ALREADY_FILLED,
                "order_fill_state",
            )
        candidate = request.candidate
        if candidate is None:
            return self._no_fill(
                request,
                BarIneligibilityReason.NO_ELIGIBLE_BAR,
            )
        observation = candidate.observation
        if observation.event.instrument_id != stream.order.intent.instrument_id:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.CANDIDATE_CONTEXT_MISMATCH,
                observation.event.event_id,
            )
        if observation.event.event_time <= state.updated_at.instant:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.SAME_BAR_FORBIDDEN,
                observation.event.event_id,
            )
        if observation.kind is BarOpenKind.GAP_PLACEHOLDER:
            return self._no_fill(request, BarIneligibilityReason.GAP_PLACEHOLDER)
        if observation.kind is BarOpenKind.FORWARD_FILLED:
            return self._no_fill(request, BarIneligibilityReason.FORWARD_FILLED)
        failure = self._validate_real_candidate(request, candidate)
        if failure is not None:
            return failure
        liquidity_evidence = cast(BarLiquidityEvidence, candidate.liquidity_evidence)
        if not liquidity_evidence.approved:
            return self._no_fill(request, BarIneligibilityReason.LIQUIDITY_BLOCKED)
        mark = _reference_mark(observation)
        decision = NextBarOpenDecision(
            request=request,
            component_ref=self.component_ref,
            applicability=self.applicability,
            action=NoEligibleBarAction.FULL_FILL,
            candidate=candidate,
            reference_price=ExecutionReferencePrice(mark),
            fill_quantity=state.remaining_quantity,
            ineligibility_reason=None,
        )
        return SimulationPortOutcome.for_result(self.component_ref, request, decision)

    def _no_fill(
        self,
        request: NextBarOpenRequest,
        reason: BarIneligibilityReason,
    ) -> SimulationPortOutcome[NextBarOpenDecision, NextBarOpenFailure]:
        decision = NextBarOpenDecision(
            request=request,
            component_ref=self.component_ref,
            applicability=self.applicability,
            action=_no_fill_action(request, self.applicability),
            candidate=request.candidate,
            reference_price=None,
            fill_quantity=None,
            ineligibility_reason=reason,
        )
        return SimulationPortOutcome.for_result(self.component_ref, request, decision)

    def _validate_real_candidate(
        self,
        request: NextBarOpenRequest,
        candidate: BarOpenCandidate,
    ) -> SimulationPortOutcome[NextBarOpenDecision, NextBarOpenFailure] | None:
        event = candidate.observation.event
        market = candidate.market_rule_approval
        funding = candidate.pretrade_risk_approval
        if market is None or funding is None:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.MISSING_GATE_APPROVAL,
                event.event_id,
            )
        order = request.order_stream.order
        if (
            market.evaluation_input.executable_order_spec.source_order != order
            or funding.evaluation_input.market_rule_approval != market
        ):
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.GATE_EVIDENCE_MISMATCH,
                event.event_id,
            )
        if (
            market.evaluation_input.evaluated_at != event.available_time
            or not market.resolved_interval.contains(event.event_time)
        ):
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.MARKET_RULE_INTERVAL_MISMATCH,
                event.event_id,
            )
        if market.resolved_interval.snapshot.session_state is not MarketSessionState.OPEN:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.MARKET_SESSION_CLOSED,
                event.event_id,
            )
        if funding.evaluation_input.evaluated_at != event.available_time:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.GATE_EVIDENCE_MISMATCH,
                event.event_id,
            )
        liquidity = candidate.liquidity_evidence
        if (
            liquidity is None
            or liquidity.evaluated_at != event.available_time
            or liquidity.market_event_id != event.event_id
            or liquidity.market_event_hash != event.event_hash
        ):
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.LIQUIDITY_EVIDENCE_MISMATCH,
                event.event_id,
            )
        market_state = candidate.market_state
        if market_state is None:
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.MISSING_GATE_APPROVAL,
                "slippage_market_state",
            )
        if (
            market_state.source_event_id != event.event_id
            or market_state.available_at > event.available_time
        ):
            return _failure(
                request,
                self.component_ref,
                NextBarOpenFailureCode.FUTURE_MARKET_STATE,
                event.event_id,
            )
        return None


def _reference_mark(observation: BarOpenObservation) -> ResolvedMark:
    instrument_id = observation.event.instrument_id
    if observation.open_price is None or instrument_id is None:
        raise ValueError("real Bar Open reference requires Price and Instrument")
    event = observation.event
    policy_hash = canonical_sha256(
        {
            "type": "bar_open_exact_policy",
            "schema_version": 1,
            "policy_key": "bar_open_exact.v1",
            "policy_version": 1,
        }
    )
    return ResolvedMark(
        instrument_id=instrument_id,
        quote_currency_id=CurrencyId(observation.open_price.quote_currency),
        price_purpose=PricePurpose.EXECUTION_REFERENCE,
        price=observation.open_price,
        observed_at=event.event_time,
        available_at=event.available_time,
        resolved_at=event.available_time,
        age_nanoseconds=0,
        stream_id=event.stream_key,
        source_event_id=event.event_id,
        revision_id=event.revision_id,
        stale_policy_key="bar_open_exact.v1",
        stale_policy_version=1,
        stale_policy_hash=policy_hash,
    )


class FullFillConstructionFailureCode(str, Enum):
    DECISION_NOT_ELIGIBLE = "decision_not_eligible"
    SLIPPAGE_NOT_SUCCESSFUL = "slippage_not_successful"
    SLIPPAGE_EVIDENCE_MISMATCH = "slippage_evidence_mismatch"
    INVALID_FILL_ID = "invalid_fill_id"


@dataclass(frozen=True)
class FullFillConstructionFailure:
    decision: NextBarOpenDecision
    code: FullFillConstructionFailureCode
    slippage_outcome_hash: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.decision, NextBarOpenDecision):
            raise TypeError("decision must be NextBarOpenDecision")
        if not isinstance(self.code, FullFillConstructionFailureCode):
            raise TypeError("code must be FullFillConstructionFailureCode")
        if self.slippage_outcome_hash is not None:
            _require_hash("slippage_outcome_hash", self.slippage_outcome_hash)

    @property
    def failure_id(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "full_fill_construction_failure",
            "schema_version": 1,
            "failure_id": canonical_sha256(
                {
                    "decision": self.decision,
                    "code": self.code.value,
                    "slippage_outcome_hash": self.slippage_outcome_hash,
                }
            ),
            "decision": self.decision,
            "code": self.code.value,
            "slippage_outcome_hash": self.slippage_outcome_hash,
        }


@dataclass(frozen=True)
class FullFillResult:
    decision: NextBarOpenDecision
    slippage_decision: SlippageDecision
    fill: Fill

    def __post_init__(self) -> None:
        if not isinstance(self.decision, NextBarOpenDecision):
            raise TypeError("decision must be NextBarOpenDecision")
        if not isinstance(self.slippage_decision, SlippageDecision):
            raise TypeError("slippage_decision must be SlippageDecision")
        if not isinstance(self.fill, Fill):
            raise TypeError("fill must be Fill")
        _validate_fill_evidence(self.decision, self.slippage_decision)
        if self.fill.order_id != self.decision.request.order_stream.order.order_id:
            raise ValueError("Fill Order identity mismatch")
        if self.fill.quantity != self.decision.fill_quantity:
            raise ValueError("Fill must use exact full remaining Quantity")
        if self.fill.slippage_decision_id != self.slippage_decision.decision_id:
            raise ValueError("Fill slippage decision mismatch")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "full_fill_result",
            "schema_version": 1,
            "decision": self.decision,
            "slippage_decision": self.slippage_decision,
            "fill": self.fill,
        }


def _slippage_outcome_hash(
    outcome: SimulationPortOutcome[SlippageDecision, SlippageApplicabilityViolation],
) -> str:
    return canonical_sha256(outcome)


def _validate_fill_evidence(
    decision: NextBarOpenDecision,
    slippage: SlippageDecision,
) -> None:
    if (
        decision.action is not NoEligibleBarAction.FULL_FILL
        or decision.reference_price is None
        or decision.fill_quantity is None
        or decision.candidate is None
        or decision.candidate.market_state is None
    ):
        raise ValueError("decision is not eligible for full Fill")
    expected_request = SlippageRequest(
        reference_price=decision.reference_price,
        side=decision.request.order_stream.order.intent.side,
        quantity=decision.fill_quantity,
        market_state=decision.candidate.market_state,
    )
    if slippage.request != expected_request:
        raise ValueError("Slippage request does not match execution decision")


class FullFillBuilder:
    def build(
        self,
        *,
        decision: NextBarOpenDecision,
        slippage_outcome: SimulationPortOutcome[
            SlippageDecision, SlippageApplicabilityViolation
        ],
        fill_id: DomainId,
    ) -> FullFillResult | FullFillConstructionFailure:
        if not isinstance(decision, NextBarOpenDecision):
            raise TypeError("decision must be NextBarOpenDecision")
        outcome_hash = _slippage_outcome_hash(slippage_outcome)
        if decision.action is not NoEligibleBarAction.FULL_FILL:
            return FullFillConstructionFailure(
                decision,
                FullFillConstructionFailureCode.DECISION_NOT_ELIGIBLE,
                outcome_hash,
            )
        if slippage_outcome.result is None:
            return FullFillConstructionFailure(
                decision,
                FullFillConstructionFailureCode.SLIPPAGE_NOT_SUCCESSFUL,
                outcome_hash,
            )
        if (
            slippage_outcome.component_ref != slippage_outcome.result.component_ref
            or slippage_outcome.input_hash
            != canonical_sha256(slippage_outcome.result.request)
        ):
            return FullFillConstructionFailure(
                decision,
                FullFillConstructionFailureCode.SLIPPAGE_EVIDENCE_MISMATCH,
                outcome_hash,
            )
        try:
            _validate_fill_evidence(decision, slippage_outcome.result)
        except (TypeError, ValueError):
            return FullFillConstructionFailure(
                decision,
                FullFillConstructionFailureCode.SLIPPAGE_EVIDENCE_MISMATCH,
                outcome_hash,
            )
        if not isinstance(fill_id, DomainId) or fill_id.kind is not DomainIdKind.FILL:
            return FullFillConstructionFailure(
                decision,
                FullFillConstructionFailureCode.INVALID_FILL_ID,
                outcome_hash,
            )
        order = decision.request.order_stream.order
        slippage = slippage_outcome.result
        reference_price = cast(ExecutionReferencePrice, decision.reference_price)
        fill_quantity = cast(Quantity, decision.fill_quantity)
        candidate = cast(BarOpenCandidate, decision.candidate)
        fill = Fill(
            fill_id=fill_id,
            order_id=order.order_id,
            account_id=order.account_id,
            venue_id=order.intent.instrument_id.venue,
            instrument_id=order.intent.instrument_id,
            side=order.intent.side,
            quantity=fill_quantity,
            reference_price=reference_price.mark.price,
            reference_price_purpose=PricePurpose.EXECUTION_REFERENCE,
            price=slippage.execution_price,
            slippage_amount=Money(
                slippage.slippage_amount.units,
                slippage.slippage_amount.scale,
                slippage.slippage_amount.quote_currency,
            ),
            slippage_decision_id=slippage.decision_id,
            slippage_model_key=slippage.component_ref.component_key,
            slippage_calibration_id=canonical_sha256(slippage.calibration_ref),
            liquidity="full",
            execution_time=candidate.observation.event.event_time,
        )
        return FullFillResult(decision, slippage, fill)


@dataclass(frozen=True, slots=True)
class LiquidityRoleFullFillBuilder:
    liquidity_role: str

    def __post_init__(self) -> None:
        if type(self.liquidity_role) is not str:
            raise TypeError("liquidity_role must be str")
        if self.liquidity_role not in ("maker", "taker"):
            raise ValueError("liquidity_role must be maker or taker")

    def build(
        self,
        *,
        decision: NextBarOpenDecision,
        slippage_outcome: SimulationPortOutcome[
            SlippageDecision, SlippageApplicabilityViolation
        ],
        fill_id: DomainId,
    ) -> FullFillResult | FullFillConstructionFailure:
        result = FullFillBuilder().build(
            decision=decision,
            slippage_outcome=slippage_outcome,
            fill_id=fill_id,
        )
        if isinstance(result, FullFillConstructionFailure):
            return result
        return FullFillResult(
            result.decision,
            result.slippage_decision,
            replace(result.fill, liquidity=self.liquidity_role),
        )
