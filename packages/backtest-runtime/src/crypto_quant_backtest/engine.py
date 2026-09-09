"""Deterministic, outcome-free Bar Engine orchestration harness."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, cast
import unicodedata

from crypto_quant_domain import (
    CurrencyId,
    DecisionBatch,
    InstrumentId,
    OrderSide,
    PositionEffect,
    PricePurpose,
    Quantity,
    DomainId,
    DomainIdKind,
    FeeAssessment,
    FeeBasisType,
    IdentityNamespace,
    Fill,
    Order,
    OrderEvent,
    OrderEventType,
    OrderStatus,
    PortfolioSnapshot,
    PositionBalanceKey,
    PositionLot,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
    derive_domain_id,
)
from crypto_quant_market_data import InputValidationFailure
from crypto_quant_trading import (
    AccountingJournal,
    AccountSettlementObligation,
    AccountRiskPolicy,
    CapitalAllocationPolicyRef,
    QuantityLattice,
    ApprovedPortfolioTarget,
    AvailabilityProjection,
    AvailabilityProjectionError,
    AvailabilityState,
    ExecutableOrderSpec,
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FeeChargedJournalTranslator,
    FeeReservationEstimator,
    FeeReservationRuleSet,
    FinalFeeRuleSet,
    GenericLedger,
    InstrumentSizingInput,
    JournalError,
    LatestSleeveDecisionState,
    LedgerError,
    LedgerSchema,
    LedgerState,
    MarketRuleEvaluator,
    MarketSettlementRules,
    NormalizedPortfolioTarget,
    OrderCapabilitySet,
    OrderCapabilityValidator,
    OrderEventRecord,
    OrderEventStream,
    OrderPlan,
    OrderReservationSchedule,
    OrderReservationUpdate,
    OrderRuleEvaluationInput,
    OrderRuleNotionalEvidence,
    OrderRuleTimeline,
    OrderTranslationMapping,
    OrderTranslator,
    PortfolioAllocation,
    PortfolioAllocator,
    PortfolioRiskEvaluator,
    PortfolioRiskPolicy,
    PositionSizer,
    PositionSizingPolicy,
    PreTradeResourceRequirement,
    PreTradeRiskEvaluationInput,
    PreTradeRiskEvaluator,
    PreTradeRiskRejection,
    PreTradeRiskReasonCode,
    ReportingCurrencyValuation,
    ReservationCommitment,
    RebalanceCoordinator,
    RebalancePolicy,
    ResolvedMark,
    ResourceReservationBook,
    ResourceReservationError,
    ResourceReservationState,
    SettlementBook,
    SettlementBookError,
    SettlementBookState,
    SettlementEventType,
    StrategyAllocation,
    TargetValidity,
)

from .financial_dispatch import (
    CashFillAccountingPlan,
    DefaultCashFinancialDispatcher,
    EventScopedFillAccountingDispatchPlan,
    FullFillOrderFeeAccountingPlan,
    FillAccountingDispatchPlan,
    FinancialDispatchArtifact,
    FinancialDispatchFailureCode,
    FinancialDispatchOutcome,
    FinancialDispatchPlan,
    FinancialDispatchResult,
    FinancialEventDispatcher,
    FinancialStateView,
    ProfileFeeRuleBinding,
    ProfileFeeRuleQuery,
    ProfileFeeRuleResolution,
    ProfileFeeRuleResolver,
    LedgerCashSnapshotProjectionPlan,
    ScheduledAccountEvent,
    SettlementFinancialDispatchResult,
    SettlementFillAccountingDispatchPlan,
    SettlementIdentitySlot,
    SettlementApplicationPlan,
)
from .execution import (
    BAR_CLOSE_CAPABILITY,
    BAR_OPEN_CAPABILITY,
    BarCloseCandidate,
    BarCloseObservation,
    BarLiquidityEvidence,
    BarOpenCandidate,
    BarOpenObservation,
    FullFillBuilder,
    FullFillConstructionFailure,
    NextBarCloseDecision,
    NextBarCloseRequest,
    NextBarOpenDecision,
    NextBarOpenRequest,
    NextEligibleBarCloseModel,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
)
from .ports import CloseoutPolicy, SimulationPortOutcome
from .run_end import (
    EngineTermination,
    RunEndCloseoutDecision,
    RunEndCloseoutFailure,
    RunEndCloseoutRequest,
    RunEndCoordinator,
    RunEndEvidence,
    RunEndReport,
)
from .slippage import (
    DeterministicBpsSlippageModel,
    SlippageApplicabilityViolation,
    SlippageDecision,
    SlippageMarketState,
    SlippageRequest,
)
from .target_stream import (
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
)
from .timeline import (
    DeterministicTimeline,
    TimelineEvent,
    TimelineSegment,
)


_HASH_PREFIX = "sha256:"
_DEFAULT_FINANCIAL_DISPATCHER = object()
_FINALIZE_PHASE = TimelinePhase(1_000_000, "engine_finalize")
_REQUIRED_ADMISSION_EVENTS = (
    OrderEventType.ORDER_INTENT_CREATED,
    OrderEventType.ORDER_CAPABILITY_APPROVED,
    OrderEventType.ORDER_TRANSLATED,
    OrderEventType.MARKET_RULE_APPROVED,
    OrderEventType.FEE_RESERVATION_ESTIMATED,
    OrderEventType.PRE_TRADE_RISK_APPROVED,
    OrderEventType.ORDER_SUBMITTED,
    OrderEventType.ORDER_ACCEPTED,
)


def _text(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    value.encode("utf-8")
    return value


def _hash(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(_HASH_PREFIX)
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be canonical sha256 digest")
    return value


def _namespace_dict(value: IdentityNamespace) -> dict[str, str]:
    return {
        "algorithm": value.algorithm,
        "value": value.value,
        "version": value.version,
    }


def _domain_id(name: str, value: DomainId, kind: DomainIdKind) -> DomainId:
    if not isinstance(value, DomainId) or value.kind is not kind:
        raise TypeError(f"{name} must be {kind.value} DomainId")
    return value


def _stable_tuple(values: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(sorted(values, key=canonical_bytes))


def _lot_state(values: dict[PositionBalanceKey, tuple[PositionLot, ...]]) -> tuple[
    tuple[PositionBalanceKey, tuple[PositionLot, ...]],
    ...
]:
    return tuple(sorted(values.items(), key=lambda value: canonical_bytes(value[0])))


def _lot_books_from_ledger(
    state: LedgerState,
) -> dict[PositionBalanceKey, tuple[PositionLot, ...]]:
    return {
        value.key: value.lots for value in state.position_balances if value.lots
    }


@dataclass(frozen=True, slots=True)
class OrderEventPlan:
    """Caller-supplied deterministic identity/time for one admission event."""

    event_type: OrderEventType
    event_id: str
    occurred_at: SimulationInstant
    external_evidence_id: str | None = None

    def __post_init__(self) -> None:
        if self.event_type not in _REQUIRED_ADMISSION_EVENTS:
            raise ValueError("unsupported admission event type")
        _text("event_id", self.event_id)
        if not isinstance(self.occurred_at, SimulationInstant):
            raise TypeError("occurred_at must be SimulationInstant")
        if self.external_evidence_id is not None:
            _text("external_evidence_id", self.external_evidence_id)
        requires_external = self.event_type in {
            OrderEventType.ORDER_SUBMITTED,
            OrderEventType.ORDER_ACCEPTED,
        }
        if requires_external != (self.external_evidence_id is not None):
            raise ValueError("only submission/acceptance events require external evidence")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_order_event_plan",
            "event_type": self.event_type.value,
            "event_id": self.event_id,
            "occurred_at": self.occurred_at,
            "external_evidence_id": self.external_evidence_id,
        }


@dataclass(frozen=True, slots=True)
class ResolvedPreTradePlan:
    """Pre-resolved generic rule/risk evidence; no resource formula is inferred."""

    order_rule_timeline: OrderRuleTimeline
    notional_evidence: OrderRuleNotionalEvidence
    market_rule_evaluated_at: UtcInstant
    fee_reservation_rule_set: FeeReservationRuleSet
    fee_estimated_at: UtcInstant
    resource_commitment: ReservationCommitment
    requirement_source_key: str
    requirement_source_version: int
    requirement_source_hash: str
    account_risk_policy: AccountRiskPolicy
    pretrade_evaluated_at: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.order_rule_timeline, OrderRuleTimeline):
            raise TypeError("order_rule_timeline must be OrderRuleTimeline")
        if not isinstance(self.notional_evidence, OrderRuleNotionalEvidence):
            raise TypeError("notional_evidence must be OrderRuleNotionalEvidence")
        if not all(
            isinstance(value, UtcInstant)
            for value in (
                self.market_rule_evaluated_at,
                self.fee_estimated_at,
                self.pretrade_evaluated_at,
            )
        ):
            raise TypeError("pre-trade times must be UtcInstant")
        if not (
            self.market_rule_evaluated_at
            <= self.fee_estimated_at
            <= self.pretrade_evaluated_at
        ):
            raise ValueError("pre-trade stage times must be monotonic")
        if not isinstance(self.fee_reservation_rule_set, FeeReservationRuleSet):
            raise TypeError("fee_reservation_rule_set must be FeeReservationRuleSet")
        if not isinstance(self.resource_commitment, ReservationCommitment):
            raise TypeError("resource_commitment must be ReservationCommitment")
        if self.resource_commitment.is_empty:
            raise ValueError("resource_commitment cannot be empty")
        _text("requirement_source_key", self.requirement_source_key)
        if (
            isinstance(self.requirement_source_version, bool)
            or not isinstance(self.requirement_source_version, int)
            or self.requirement_source_version <= 0
        ):
            raise ValueError("requirement_source_version must be positive integer")
        _hash("requirement_source_hash", self.requirement_source_hash)
        if not isinstance(self.account_risk_policy, AccountRiskPolicy):
            raise TypeError("account_risk_policy must be AccountRiskPolicy")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_pretrade_plan",
            "order_rule_timeline": self.order_rule_timeline,
            "notional_evidence": self.notional_evidence,
            "market_rule_evaluated_at": self.market_rule_evaluated_at,
            "fee_reservation_rule_set": self.fee_reservation_rule_set,
            "fee_estimated_at": self.fee_estimated_at,
            "resource_commitment": self.resource_commitment,
            "requirement_source_key": self.requirement_source_key,
            "requirement_source_version": self.requirement_source_version,
            "requirement_source_hash": self.requirement_source_hash,
            "account_risk_policy": self.account_risk_policy,
            "pretrade_evaluated_at": self.pretrade_evaluated_at,
        }


@dataclass(frozen=True, slots=True)
class ResolvedOrderAdmission:
    """Exact Order and G05 admission evidence selected by the Case Builder."""

    order: Order
    capability_set: OrderCapabilitySet
    translation_mapping: OrderTranslationMapping
    translation_time: UtcInstant
    pretrade_plan: ResolvedPreTradePlan
    event_plan: tuple[OrderEventPlan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.order, Order):
            raise TypeError("order must be Order")
        if not isinstance(self.capability_set, OrderCapabilitySet):
            raise TypeError("capability_set must be OrderCapabilitySet")
        if not isinstance(self.translation_mapping, OrderTranslationMapping):
            raise TypeError("translation_mapping must be OrderTranslationMapping")
        if not isinstance(self.translation_time, UtcInstant):
            raise TypeError("translation_time must be UtcInstant")
        if not isinstance(self.pretrade_plan, ResolvedPreTradePlan):
            raise TypeError("pretrade_plan must be ResolvedPreTradePlan")
        if not isinstance(self.event_plan, tuple) or not all(
            isinstance(value, OrderEventPlan) for value in self.event_plan
        ):
            raise TypeError("event_plan must contain OrderEventPlan")
        if tuple(value.event_type for value in self.event_plan) != _REQUIRED_ADMISSION_EVENTS:
            raise ValueError("event_plan must contain the exact admission gate order")
        if self.event_plan[0].occurred_at != self.order.created_at:
            raise ValueError("created event must use Order.created_at")
        keys = tuple((value.occurred_at, value.event_id) for value in self.event_plan)
        if any(left >= right for left, right in zip(keys, keys[1:], strict=False)):
            raise ValueError("admission event plan must use strict stable order")
        event_ids = tuple(value.event_id for value in self.event_plan)
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("admission event IDs must be unique")
        if self.translation_time > self.pretrade_plan.market_rule_evaluated_at:
            raise ValueError("translation cannot occur after Market Rule evaluation")

    @property
    def admission_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_order_admission",
            "order": self.order,
            "capability_set": self.capability_set,
            "translation_mapping": self.translation_mapping,
            "translation_time": self.translation_time,
            "pretrade_plan": self.pretrade_plan,
            "event_plan": self.event_plan,
        }


@dataclass(frozen=True, slots=True)
class ResolvedDecisionCycle:
    """One scheduled Target batch and all resolved G04/G05 inputs."""

    schedule: TargetStreamDecisionSchedule
    allocations: tuple[StrategyAllocation, ...]
    target_notional_scale: Scale
    risk_policy: PortfolioRiskPolicy
    sizing_policy: PositionSizingPolicy
    sizing_inputs: tuple[InstrumentSizingInput, ...]
    target_validity: TargetValidity
    rebalance_policy: RebalancePolicy
    planning_at: UtcInstant
    admissions: tuple[ResolvedOrderAdmission, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.schedule, TargetStreamDecisionSchedule):
            raise TypeError("schedule must be TargetStreamDecisionSchedule")
        for name, values, expected_type in (
            ("allocations", self.allocations, StrategyAllocation),
            ("sizing_inputs", self.sizing_inputs, InstrumentSizingInput),
            ("admissions", self.admissions, ResolvedOrderAdmission),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(value, expected_type) for value in values
            ):
                raise TypeError(f"{name} contains invalid values")
        if self.schedule.segment is TimelineSegment.ACTIVE_TRADING and not self.allocations:
            raise ValueError("active decision cycle requires allocations")
        if not isinstance(self.target_notional_scale, Scale):
            raise TypeError("target_notional_scale must be Scale")
        if not isinstance(self.risk_policy, PortfolioRiskPolicy):
            raise TypeError("risk_policy must be PortfolioRiskPolicy")
        if not isinstance(self.sizing_policy, PositionSizingPolicy):
            raise TypeError("sizing_policy must be PositionSizingPolicy")
        if not isinstance(self.target_validity, TargetValidity):
            raise TypeError("target_validity must be TargetValidity")
        if not isinstance(self.rebalance_policy, RebalancePolicy):
            raise TypeError("rebalance_policy must be RebalancePolicy")
        if not isinstance(self.planning_at, UtcInstant):
            raise TypeError("planning_at must be UtcInstant")
        if self.schedule.segment is TimelineSegment.ACTIVE_TRADING and (
            self.planning_at < self.schedule.decision_time
        ):
            raise ValueError("planning_at cannot precede Decision Time")
        admission_ids = tuple(value.order.order_id.value for value in self.admissions)
        if len(set(admission_ids)) != len(admission_ids):
            raise ValueError("decision cycle admission Order IDs must be unique")
        object.__setattr__(self, "allocations", _stable_tuple(self.allocations))
        object.__setattr__(self, "sizing_inputs", _stable_tuple(self.sizing_inputs))
        object.__setattr__(self, "admissions", _stable_tuple(self.admissions))

    @property
    def cycle_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_decision_cycle",
            "schedule": self.schedule,
            "allocations": self.allocations,
            "target_notional_scale": self.target_notional_scale.places,
            "risk_policy": self.risk_policy,
            "sizing_policy": self.sizing_policy,
            "sizing_inputs": self.sizing_inputs,
            "target_validity": self.target_validity,
            "rebalance_policy": self.rebalance_policy,
            "planning_at": self.planning_at,
            "admissions": self.admissions,
        }


@dataclass(frozen=True, slots=True)
class ResolvedBarExecution:
    """One exact Bar Event/order execution and accounting plan."""

    event_id: str
    order_id: DomainId
    pretrade_plan: ResolvedPreTradePlan
    liquidity_evidence: BarLiquidityEvidence
    market_state: SlippageMarketState
    slippage_model: DeterministicBpsSlippageModel
    fill_id: DomainId
    fill_event_id: str
    fill_event_at: SimulationInstant
    accounting_plan: FillAccountingDispatchPlan

    def __post_init__(self) -> None:
        _text("event_id", self.event_id)
        _domain_id("order_id", self.order_id, DomainIdKind.ORDER)
        if not isinstance(self.pretrade_plan, ResolvedPreTradePlan):
            raise TypeError("pretrade_plan must be ResolvedPreTradePlan")
        if not isinstance(self.liquidity_evidence, BarLiquidityEvidence):
            raise TypeError("liquidity_evidence must be BarLiquidityEvidence")
        if not isinstance(self.market_state, SlippageMarketState):
            raise TypeError("market_state must be SlippageMarketState")
        if not isinstance(self.slippage_model, DeterministicBpsSlippageModel):
            raise TypeError("slippage_model must be DeterministicBpsSlippageModel")
        _domain_id("fill_id", self.fill_id, DomainIdKind.FILL)
        _text("fill_event_id", self.fill_event_id)
        if not isinstance(self.fill_event_at, SimulationInstant):
            raise TypeError("fill_event_at must be SimulationInstant")
        if not isinstance(self.accounting_plan, FillAccountingDispatchPlan):
            raise TypeError("accounting_plan must be FillAccountingDispatchPlan")
        if (
            self.accounting_plan.source_event_id != self.event_id
            or self.accounting_plan.expected_fill_id != self.fill_id
        ):
            raise ValueError("accounting plan must match resolved Bar execution")

    @property
    def execution_hash(self) -> str:
        return canonical_sha256(self)

    def _slippage_config(self) -> dict[str, object]:
        model = self.slippage_model
        return {
            "component_ref": model.component_ref,
            "calibration_ref": model.calibration_ref,
            "applicability_envelope": model.applicability_envelope,
            "basis_points_units": model.basis_points_units,
            "basis_points_scale": model.basis_points_scale.places,
            "rounding": model.rounding.value,
            "limitations": tuple(value.value for value in model.limitations),
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_bar_execution",
            "event_id": self.event_id,
            "order_id": self.order_id,
            "pretrade_plan": self.pretrade_plan,
            "liquidity_evidence": self.liquidity_evidence,
            "market_state": self.market_state,
            "slippage_model": self._slippage_config(),
            "fill_id": self.fill_id,
            "fill_event_id": self.fill_event_id,
            "fill_event_at": self.fill_event_at,
            "accounting_plan": self.accounting_plan,
        }


@dataclass(frozen=True, slots=True)
class PositionLotBook:
    position_key: PositionBalanceKey
    lots: tuple[PositionLot, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.position_key, PositionBalanceKey):
            raise TypeError("position_key must be PositionBalanceKey")
        if not isinstance(self.lots, tuple) or not all(
            isinstance(value, PositionLot) for value in self.lots
        ):
            raise TypeError("lots must contain PositionLot")
        if any(value.position_key != self.position_key for value in self.lots):
            raise ValueError("Position Lot book key mismatch")
        object.__setattr__(self, "lots", _stable_tuple(self.lots))

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "position_lot_book",
            "position_key": self.position_key,
            "lots": self.lots,
        }


@dataclass(frozen=True, slots=True)
class ResolvedFinancialState:
    journal: AccountingJournal
    ledger_schema: LedgerSchema
    initial_snapshot: PortfolioSnapshot
    lot_books: tuple[PositionLotBook, ...]
    order_streams: tuple[OrderEventStream, ...]
    order_admissions: tuple[ResolvedOrderAdmission, ...]
    reservation_schedules: tuple[OrderReservationSchedule, ...]
    settlement_book: SettlementBook
    settlement_rules: MarketSettlementRules

    def __post_init__(self) -> None:
        if not isinstance(self.journal, AccountingJournal):
            raise TypeError("journal must be AccountingJournal")
        if not isinstance(self.ledger_schema, LedgerSchema):
            raise TypeError("ledger_schema must be LedgerSchema")
        if not isinstance(self.initial_snapshot, PortfolioSnapshot):
            raise TypeError("initial_snapshot must be PortfolioSnapshot")
        for name, values, expected_type in (
            ("lot_books", self.lot_books, PositionLotBook),
            ("order_streams", self.order_streams, OrderEventStream),
            ("order_admissions", self.order_admissions, ResolvedOrderAdmission),
            ("reservation_schedules", self.reservation_schedules, OrderReservationSchedule),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(value, expected_type) for value in values
            ):
                raise TypeError(f"{name} contains invalid values")
        if not isinstance(self.settlement_book, SettlementBook):
            raise TypeError("settlement_book must be SettlementBook")
        if not isinstance(self.settlement_rules, MarketSettlementRules):
            raise TypeError("settlement_rules must be MarketSettlementRules")
        ledger_state = GenericLedger(self.ledger_schema).project(self.journal)
        if ledger_state.state_hash != self.initial_snapshot.journal_state_hash:
            raise ValueError("initial Snapshot does not match Journal/Ledger state")
        if self.initial_snapshot.account_id != self.settlement_rules.account_id:
            raise ValueError("initial financial account mismatch")
        if self.settlement_book.account_id != self.initial_snapshot.account_id:
            raise ValueError("SettlementBook account mismatch")
        lot_keys = tuple(canonical_bytes(value.position_key) for value in self.lot_books)
        if len(set(lot_keys)) != len(lot_keys):
            raise ValueError("duplicate Position Lot book")
        object.__setattr__(self, "lot_books", _stable_tuple(self.lot_books))
        stream_ids = {value.order.order_id for value in self.order_streams}
        admission_ids = {value.order.order_id for value in self.order_admissions}
        if stream_ids != admission_ids:
            raise ValueError("initial Order streams and admissions must exact-cover")
        object.__setattr__(self, "order_streams", _stable_tuple(self.order_streams))
        object.__setattr__(self, "order_admissions", _stable_tuple(self.order_admissions))
        object.__setattr__(
            self, "reservation_schedules", _stable_tuple(self.reservation_schedules)
        )

    def to_canonical_dict(self) -> dict[str, object]:
        settlement_state = self.settlement_book.project()
        return {
            "type": "resolved_financial_state",
            "journal": self.journal,
            "ledger_schema": self.ledger_schema,
            "initial_snapshot": self.initial_snapshot,
            "lot_books": self.lot_books,
            "order_streams": self.order_streams,
            "order_admissions": self.order_admissions,
            "reservation_schedules": self.reservation_schedules,
            "settlement_book_hash": self.settlement_book.book_hash,
            "settlement_state": settlement_state,
            "settlement_rules": self.settlement_rules,
        }


@dataclass(frozen=True, slots=True)
class SnapshotProjectionPlan:
    resolved_marks: tuple[ResolvedMark, ...]
    valuations: tuple[ReportingCurrencyValuation, ...]
    reporting_currency: CurrencyId
    reporting_scale: Scale
    timestamp: UtcInstant
    currency_valuation_graph_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.resolved_marks, tuple) or not all(
            isinstance(value, ResolvedMark) for value in self.resolved_marks
        ):
            raise TypeError("resolved_marks must contain ResolvedMark")
        if not isinstance(self.valuations, tuple) or not all(
            isinstance(value, ReportingCurrencyValuation) for value in self.valuations
        ):
            raise TypeError("valuations must contain ReportingCurrencyValuation")
        if not isinstance(self.reporting_currency, CurrencyId):
            raise TypeError("reporting_currency must be CurrencyId")
        if not isinstance(self.reporting_scale, Scale):
            raise TypeError("reporting_scale must be Scale")
        if not isinstance(self.timestamp, UtcInstant):
            raise TypeError("timestamp must be UtcInstant")
        _hash("currency_valuation_graph_hash", self.currency_valuation_graph_hash)
        object.__setattr__(self, "resolved_marks", _stable_tuple(self.resolved_marks))
        object.__setattr__(self, "valuations", _stable_tuple(self.valuations))

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "snapshot_projection_plan",
            "resolved_marks": self.resolved_marks,
            "valuations": self.valuations,
            "reporting_currency": self.reporting_currency,
            "reporting_scale": self.reporting_scale.places,
            "timestamp": self.timestamp,
            "currency_valuation_graph_hash": self.currency_valuation_graph_hash,
        }


@dataclass(frozen=True, slots=True)
class ExecutionCaseIdentityRule:
    binding_key: str
    semantic_key: str
    ordinal: int
    domain_kind: DomainIdKind | None = None

    def __post_init__(self) -> None:
        _text("binding_key", self.binding_key)
        _text("semantic_key", self.semantic_key)
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int):
            raise TypeError("ordinal must be integer")
        if self.ordinal < 0:
            raise ValueError("ordinal must be nonnegative")
        if self.domain_kind is not None and not isinstance(
            self.domain_kind, DomainIdKind
        ):
            raise TypeError("domain_kind must be DomainIdKind or None")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "binding_key": self.binding_key,
            "identity_type": "domain_id" if self.domain_kind is not None else "event_id",
            "domain_kind": (
                self.domain_kind.value if self.domain_kind is not None else None
            ),
            "semantic_key": self.semantic_key,
            "ordinal": self.ordinal,
        }


@dataclass(frozen=True, slots=True)
class ExecutionCaseSemanticSpec:
    schema_version: int
    spec_key: str
    spec_version: int
    case_key: str
    case_version: int
    identity_namespace: IdentityNamespace
    identity_plan: tuple[ExecutionCaseIdentityRule, ...]
    timeline_semantic_hash: str
    target_stream_digest: str
    decision_inputs_hash: str
    execution_inputs_hash: str
    financial_inputs_hash: str
    snapshot_inputs_hash: str
    run_end_inputs_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("ExecutionCaseSemanticSpec schema_version must be 1")
        _text("spec_key", self.spec_key)
        _text("case_key", self.case_key)
        for name in ("spec_version", "case_version"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be positive integer")
        if not isinstance(self.identity_namespace, IdentityNamespace):
            raise TypeError("identity_namespace must be IdentityNamespace")
        if not isinstance(self.identity_plan, tuple) or not self.identity_plan:
            raise ValueError("identity_plan must be a nonempty tuple")
        if not all(
            isinstance(value, ExecutionCaseIdentityRule)
            for value in self.identity_plan
        ):
            raise TypeError("identity_plan must contain ExecutionCaseIdentityRule")
        ordered_plan = tuple(
            sorted(self.identity_plan, key=lambda value: value.binding_key)
        )
        if len({value.binding_key for value in ordered_plan}) != len(ordered_plan):
            raise ValueError("identity_plan binding keys must be unique")
        domain_coordinates = tuple(
            (value.domain_kind, value.semantic_key, value.ordinal)
            for value in ordered_plan
            if value.domain_kind is not None
        )
        if len(set(domain_coordinates)) != len(domain_coordinates):
            raise ValueError("Domain ID identity_plan coordinates must be unique")
        object.__setattr__(self, "identity_plan", ordered_plan)
        for name in (
            "timeline_semantic_hash",
            "target_stream_digest",
            "decision_inputs_hash",
            "execution_inputs_hash",
            "financial_inputs_hash",
            "snapshot_inputs_hash",
            "run_end_inputs_hash",
        ):
            _hash(name, getattr(self, name))

    @property
    def semantic_spec_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_case_semantic_spec",
            "schema_version": self.schema_version,
            "spec_key": self.spec_key,
            "spec_version": self.spec_version,
            "case_key": self.case_key,
            "case_version": self.case_version,
            "identity_namespace": _namespace_dict(self.identity_namespace),
            "identity_plan": self.identity_plan,
            "timeline_semantic_hash": self.timeline_semantic_hash,
            "target_stream_digest": self.target_stream_digest,
            "decision_inputs_hash": self.decision_inputs_hash,
            "execution_inputs_hash": self.execution_inputs_hash,
            "financial_inputs_hash": self.financial_inputs_hash,
            "snapshot_inputs_hash": self.snapshot_inputs_hash,
            "run_end_inputs_hash": self.run_end_inputs_hash,
        }


def _derive_event_id(
    *,
    namespace: IdentityNamespace,
    semantic_run_id: str,
    binding_key: str,
    semantic_key: str,
    ordinal: int,
) -> str:
    digest = canonical_sha256(
        {
            "type": "execution_case_event_identity_v1",
            "namespace": _namespace_dict(namespace),
            "semantic_run_id": semantic_run_id,
            "binding_key": binding_key,
            "semantic_key": semantic_key,
            "ordinal": ordinal,
        }
    )
    return f"evt_{digest.removeprefix('sha256:')}"


@dataclass(frozen=True, slots=True)
class ExecutionCaseIdentityBinding:
    binding_key: str
    semantic_key: str
    ordinal: int
    value: str
    domain_kind: DomainIdKind | None = None

    def __post_init__(self) -> None:
        _text("binding_key", self.binding_key)
        _text("semantic_key", self.semantic_key)
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int):
            raise TypeError("ordinal must be integer")
        if self.ordinal < 0:
            raise ValueError("ordinal must be nonnegative")
        _text("value", self.value)
        if self.domain_kind is not None and not isinstance(
            self.domain_kind, DomainIdKind
        ):
            raise TypeError("domain_kind must be DomainIdKind or None")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "binding_key": self.binding_key,
            "identity_type": "domain_id" if self.domain_kind is not None else "event_id",
            "domain_kind": (
                self.domain_kind.value if self.domain_kind is not None else None
            ),
            "semantic_key": self.semantic_key,
            "ordinal": self.ordinal,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class ExecutionCaseIdentityManifest:
    semantic_run_id: str
    namespace: IdentityNamespace
    bindings: tuple[ExecutionCaseIdentityBinding, ...]

    def __post_init__(self) -> None:
        _text("semantic_run_id", self.semantic_run_id)
        if not isinstance(self.namespace, IdentityNamespace):
            raise TypeError("namespace must be IdentityNamespace")
        if not isinstance(self.bindings, tuple) or not self.bindings:
            raise ValueError("bindings must be a nonempty tuple")
        if not all(
            isinstance(value, ExecutionCaseIdentityBinding) for value in self.bindings
        ):
            raise TypeError("bindings must contain ExecutionCaseIdentityBinding")
        ordered = tuple(sorted(self.bindings, key=lambda value: value.binding_key))
        if len({value.binding_key for value in ordered}) != len(ordered):
            raise ValueError("identity binding keys must be unique")
        if len({value.value for value in ordered}) != len(ordered):
            raise ValueError("identity binding values must be unique")
        for binding in ordered:
            if binding.domain_kind is not None:
                expected = derive_domain_id(
                    namespace=self.namespace,
                    kind=binding.domain_kind,
                    semantic_run_id=self.semantic_run_id,
                    semantic_key=binding.semantic_key.encode("utf-8"),
                    ordinal=binding.ordinal,
                ).value
            else:
                expected = _derive_event_id(
                    namespace=self.namespace,
                    semantic_run_id=self.semantic_run_id,
                    binding_key=binding.binding_key,
                    semantic_key=binding.semantic_key,
                    ordinal=binding.ordinal,
                )
            if binding.value != expected:
                raise ValueError(f"identity binding mismatch: {binding.binding_key}")
        object.__setattr__(self, "bindings", ordered)

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_case_identity_manifest",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "namespace": _namespace_dict(self.namespace),
            "bindings": self.bindings,
        }


class ExecutionCaseIdentityFactory:
    def __init__(
        self,
        *,
        semantic_run_id: str,
        namespace: IdentityNamespace,
        identity_plan: tuple[ExecutionCaseIdentityRule, ...],
    ) -> None:
        _text("semantic_run_id", semantic_run_id)
        if not isinstance(namespace, IdentityNamespace):
            raise TypeError("namespace must be IdentityNamespace")
        if not isinstance(identity_plan, tuple) or not identity_plan:
            raise ValueError("identity_plan must be a nonempty tuple")
        if not all(
            isinstance(value, ExecutionCaseIdentityRule) for value in identity_plan
        ):
            raise TypeError("identity_plan must contain ExecutionCaseIdentityRule")
        rules = {value.binding_key: value for value in identity_plan}
        if len(rules) != len(identity_plan):
            raise ValueError("identity_plan binding keys must be unique")
        domain_coordinates = tuple(
            (value.domain_kind, value.semantic_key, value.ordinal)
            for value in identity_plan
            if value.domain_kind is not None
        )
        if len(set(domain_coordinates)) != len(domain_coordinates):
            raise ValueError("Domain ID identity_plan coordinates must be unique")
        self._semantic_run_id = semantic_run_id
        self._namespace = namespace
        self._rules = rules
        self._bindings: dict[str, ExecutionCaseIdentityBinding] = {}

    @property
    def semantic_run_id(self) -> str:
        return self._semantic_run_id

    @property
    def namespace(self) -> IdentityNamespace:
        return self._namespace

    def domain_id(self, binding_key: str) -> DomainId:
        rule = self._rule(binding_key)
        if rule.domain_kind is None:
            raise ValueError(f"identity rule is not a Domain ID: {binding_key}")
        identity = derive_domain_id(
            namespace=self._namespace,
            kind=rule.domain_kind,
            semantic_run_id=self._semantic_run_id,
            semantic_key=rule.semantic_key.encode("utf-8"),
            ordinal=rule.ordinal,
        )
        self._record(rule, identity.value)
        return identity

    def event_id(self, binding_key: str) -> str:
        rule = self._rule(binding_key)
        if rule.domain_kind is not None:
            raise ValueError(f"identity rule is not an Event ID: {binding_key}")
        value = _derive_event_id(
            namespace=self._namespace,
            semantic_run_id=self._semantic_run_id,
            binding_key=rule.binding_key,
            semantic_key=rule.semantic_key,
            ordinal=rule.ordinal,
        )
        self._record(rule, value)
        return value

    def manifest(self) -> ExecutionCaseIdentityManifest:
        if set(self._bindings) != set(self._rules):
            missing = sorted(set(self._rules) - set(self._bindings))
            raise ValueError(f"identity_plan was not exact-covered: {missing}")
        return ExecutionCaseIdentityManifest(
            semantic_run_id=self._semantic_run_id,
            namespace=self._namespace,
            bindings=tuple(self._bindings.values()),
        )

    def _rule(self, binding_key: str) -> ExecutionCaseIdentityRule:
        _text("binding_key", binding_key)
        try:
            return self._rules[binding_key]
        except KeyError as error:
            raise ValueError(f"unknown identity binding key: {binding_key}") from error

    def _record(self, rule: ExecutionCaseIdentityRule, value: str) -> None:
        binding = ExecutionCaseIdentityBinding(
            binding_key=rule.binding_key,
            semantic_key=rule.semantic_key,
            ordinal=rule.ordinal,
            value=value,
            domain_kind=rule.domain_kind,
        )
        existing = self._bindings.get(rule.binding_key)
        if existing is not None and existing != binding:
            raise ValueError(f"identity binding key reused: {rule.binding_key}")
        self._bindings[rule.binding_key] = binding


@dataclass(frozen=True, slots=True)
class ResolvedExecutionCase:
    case_key: str
    case_version: int
    semantic_spec_hash: str
    timeline: DeterministicTimeline
    timeline_batch_size: int
    target_stream: PrecomputedTargetStream
    decision_cycles: tuple[ResolvedDecisionCycle, ...]
    bar_executions: tuple[ResolvedBarExecution, ...]
    financial_state: ResolvedFinancialState
    financial_dispatch_plan: FinancialDispatchPlan
    execution_model: NextEligibleBarOpenModel | NextEligibleBarCloseModel
    snapshot_plan: SnapshotProjectionPlan
    closeout_policy: CloseoutPolicy[
        RunEndCloseoutRequest, RunEndCloseoutDecision, RunEndCloseoutFailure
    ]
    identity_manifest: ExecutionCaseIdentityManifest | None = None
    semantic_spec: ExecutionCaseSemanticSpec | None = None

    def __post_init__(self) -> None:
        _text("case_key", self.case_key)
        if (
            isinstance(self.case_version, bool)
            or not isinstance(self.case_version, int)
            or self.case_version <= 0
        ):
            raise ValueError("case_version must be positive integer")
        _hash("semantic_spec_hash", self.semantic_spec_hash)
        if not isinstance(self.timeline, DeterministicTimeline):
            raise TypeError("timeline must be DeterministicTimeline")
        if (
            isinstance(self.timeline_batch_size, bool)
            or not isinstance(self.timeline_batch_size, int)
            or self.timeline_batch_size <= 0
        ):
            raise ValueError("timeline_batch_size must be positive integer")
        if not isinstance(self.target_stream, PrecomputedTargetStream):
            raise TypeError("target_stream must be PrecomputedTargetStream")
        if not isinstance(self.decision_cycles, tuple) or not all(
            isinstance(value, ResolvedDecisionCycle) for value in self.decision_cycles
        ):
            raise TypeError("decision_cycles must contain ResolvedDecisionCycle")
        if not isinstance(self.bar_executions, tuple) or not all(
            isinstance(value, ResolvedBarExecution) for value in self.bar_executions
        ):
            raise TypeError("bar_executions must contain ResolvedBarExecution")
        if not isinstance(self.financial_state, ResolvedFinancialState):
            raise TypeError("financial_state must be ResolvedFinancialState")
        if not isinstance(self.financial_dispatch_plan, FinancialDispatchPlan):
            raise TypeError("financial_dispatch_plan must be FinancialDispatchPlan")
        if self.financial_dispatch_plan.final_snapshot_payload != self.snapshot_plan:
            raise ValueError("financial dispatch final Snapshot payload mismatch")
        if not isinstance(self.execution_model, (NextEligibleBarOpenModel, NextEligibleBarCloseModel)):
            raise TypeError("execution_model must be NextEligibleBarOpenModel or NextEligibleBarCloseModel")
        if not isinstance(self.snapshot_plan, SnapshotProjectionPlan):
            raise TypeError("snapshot_plan must be SnapshotProjectionPlan")
        if not callable(getattr(self.closeout_policy, "spec", None)) or not callable(
            getattr(self.closeout_policy, "resolve_closeout", None)
        ):
            raise TypeError("closeout_policy must satisfy CloseoutPolicy")
        if self.identity_manifest is not None and not isinstance(
            self.identity_manifest, ExecutionCaseIdentityManifest
        ):
            raise TypeError(
                "identity_manifest must be ExecutionCaseIdentityManifest or None"
            )
        if self.semantic_spec is not None and not isinstance(
            self.semantic_spec, ExecutionCaseSemanticSpec
        ):
            raise TypeError(
                "semantic_spec must be ExecutionCaseSemanticSpec or None"
            )
        if (
            self.semantic_spec is not None
            and self.semantic_spec.semantic_spec_hash != self.semantic_spec_hash
        ):
            raise ValueError("semantic_spec does not match semantic_spec_hash")
        if self.snapshot_plan.timestamp != self.timeline.window.end_exclusive:
            raise ValueError("Snapshot plan timestamp must equal Timeline end_exclusive")
        cycle_times = tuple(value.schedule.decision_time for value in self.decision_cycles)
        if len(set(cycle_times)) != len(cycle_times):
            raise ValueError("decision cycles must have unique Decision Times")
        bar_ids = tuple(value.event_id for value in self.bar_executions)
        if len(set(bar_ids)) != len(bar_ids):
            raise ValueError("bar execution Event IDs must be unique")
        order_ids = tuple(
            admission.order.order_id.value
            for cycle in self.decision_cycles
            for admission in cycle.admissions
        ) + tuple(
            admission.order.order_id.value
            for admission in self.financial_state.order_admissions
        )
        if len(set(order_ids)) != len(order_ids):
            raise ValueError("resolved admission Order IDs must be globally unique")
        known_orders = set(order_ids)
        if any(value.order_id.value not in known_orders for value in self.bar_executions):
            raise ValueError("bar execution references unknown Order")
        target_event_ids = {value.event_id for value in self.target_stream.events}
        scheduled_event_ids = {
            entry.event_id
            for cycle in self.decision_cycles
            for entry in cycle.schedule.entries
        }
        if target_event_ids != scheduled_event_ids:
            raise ValueError("TargetStream and Decision schedules must exact-cover events")
        object.__setattr__(self, "decision_cycles", _stable_tuple(self.decision_cycles))
        object.__setattr__(self, "bar_executions", _stable_tuple(self.bar_executions))

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def verify_identity_manifest(self, semantic_run_id: str) -> bool:
        manifest = self.identity_manifest
        spec = self.semantic_spec
        if (
            manifest is None
            or spec is None
            or manifest.semantic_run_id != semantic_run_id
            or spec.semantic_spec_hash != self.semantic_spec_hash
        ):
            return False
        actual_plan = {
            binding.binding_key: (
                binding.semantic_key,
                binding.ordinal,
                binding.domain_kind,
            )
            for binding in manifest.bindings
        }
        expected_plan = {
            rule.binding_key: (
                rule.semantic_key,
                rule.ordinal,
                rule.domain_kind,
            )
            for rule in spec.identity_plan
        }
        if actual_plan != expected_plan:
            return False
        actual = {
            binding.binding_key: (binding.value, binding.domain_kind)
            for binding in manifest.bindings
        }
        return actual == self._expected_identity_bindings()

    def _expected_identity_bindings(
        self,
    ) -> dict[str, tuple[str, DomainIdKind | None]]:
        expected: dict[str, tuple[str, DomainIdKind | None]] = {}
        for index, entry in enumerate(self.financial_state.journal.entries):
            expected[f"journal.initial.{index}"] = (
                entry.journal_entry_id.value,
                DomainIdKind.JOURNAL,
            )
        initial_streams = sorted(
            self.financial_state.order_streams,
            key=lambda stream: (
                stream.order.created_at,
                stream.order.intent.parent_id,
            ),
        )
        for order_index, stream in enumerate(initial_streams):
            expected[f"order.initial.{order_index}"] = (
                stream.order.order_id.value,
                DomainIdKind.ORDER,
            )
            for event_index, record in enumerate(stream.records):
                expected[f"order-event.initial.{order_index}.{event_index}"] = (
                    record.event.event_id,
                    None,
                )
        for cycle_index, cycle in enumerate(self.decision_cycles):
            for admission_index, admission in enumerate(cycle.admissions):
                expected[f"order.{cycle_index}.{admission_index}"] = (
                    admission.order.order_id.value,
                    DomainIdKind.ORDER,
                )
                for event_index, event_plan in enumerate(admission.event_plan):
                    expected[
                        f"order-event.{cycle_index}.{admission_index}.{event_index}"
                    ] = (event_plan.event_id, None)
        for bar_index, execution in enumerate(self.bar_executions):
            expected[f"fill.{bar_index}"] = (
                execution.fill_id.value,
                DomainIdKind.FILL,
            )
            expected[f"journal.fill.{bar_index}"] = (
                execution.accounting_plan.fill_journal_entry_id.value,
                DomainIdKind.JOURNAL,
            )
            expected[f"fee.{bar_index}"] = (
                execution.accounting_plan.fee_plan.fee_assessment_id.value,
                DomainIdKind.FEE,
            )
            expected[f"journal.fee.{bar_index}"] = (
                execution.accounting_plan.fee_plan.fee_journal_entry_id.value,
                DomainIdKind.JOURNAL,
            )
            expected[f"order-event.fill.{bar_index}"] = (
                execution.fill_event_id,
                None,
            )
            fee = execution.accounting_plan.fee_plan
            if isinstance(fee, FullFillOrderFeeAccountingPlan) and fee.fill_fee_plan is not None:
                expected[f"fee.fill.{bar_index}"] = (fee.fill_fee_plan.fee_assessment_id.value, DomainIdKind.FEE)
                expected[f"journal.fee.fill.{bar_index}"] = (fee.fill_fee_plan.fee_journal_entry_id.value, DomainIdKind.JOURNAL)
        for account_event in self.financial_dispatch_plan.scheduled_account_events:
            for binding_key, value in account_event.identity_bindings:
                if binding_key in expected:
                    raise ValueError("duplicate financial identity binding key")
                expected[binding_key] = (value.value, value.kind)
        return expected

    def to_canonical_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "resolved_execution_case",
            "schema_version": 1,
            "case_key": self.case_key,
            "case_version": self.case_version,
            "timeline": {
                "timeline_id": self.timeline.timeline_id,
                "bundle_ref": self.timeline.reader.bundle_ref,
                "stream_keys": self.timeline.stream_keys,
                "window": self.timeline.window,
            },
            # Batch size is operational and intentionally excluded from semantic identity.
            "target_stream": self.target_stream,
            "decision_cycles": self.decision_cycles,
            "bar_executions": self.bar_executions,
            "financial_state": self.financial_state,
            "financial_dispatch_plan": self.financial_dispatch_plan,
            "execution_model_spec": self.execution_model.spec(),
            "snapshot_plan": self.snapshot_plan,
            "closeout_policy_spec": self.closeout_policy.spec(),
        }
        if self.identity_manifest is not None:
            payload["semantic_spec_hash"] = self.semantic_spec_hash
            payload["identity_manifest_hash"] = self.identity_manifest.manifest_hash
        return payload


@dataclass(frozen=True, slots=True)
class ResolvedCashPreTradeAuthority:
    """Cash admission facts, without a future quantity or resource commitment."""

    order_rule_timeline: OrderRuleTimeline
    notional_evidence: OrderRuleNotionalEvidence
    evaluated_at: UtcInstant
    fee_reservation_rule_set: FeeReservationRuleSet | ProfileFeeRuleBinding
    requirement_source_key: str
    requirement_source_version: int
    requirement_source_hash: str
    account_risk_policy: AccountRiskPolicy

    def __post_init__(self) -> None:
        for value, expected in (
            (self.order_rule_timeline, OrderRuleTimeline),
            (self.notional_evidence, OrderRuleNotionalEvidence),
            (self.evaluated_at, UtcInstant),
            (self.account_risk_policy, AccountRiskPolicy),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"cash pretrade authority requires {expected.__name__}")
        if not isinstance(self.fee_reservation_rule_set, FeeReservationRuleSet) and type(self.fee_reservation_rule_set) is not ProfileFeeRuleBinding:
            raise TypeError("cash pretrade authority requires fee rules or exact profile binding")
        _text("requirement_source_key", self.requirement_source_key)
        _hash("requirement_source_hash", self.requirement_source_hash)
        if type(self.requirement_source_version) is not int or self.requirement_source_version <= 0:
            raise ValueError("requirement_source_version must be positive")

    def materialize(self, commitment: ReservationCommitment,
                    fee_rules: FeeReservationRuleSet | None = None) -> ResolvedPreTradePlan:
        rules = self.fee_reservation_rule_set if fee_rules is None else fee_rules
        if not isinstance(rules, FeeReservationRuleSet):
            raise TypeError("profile fee authority must be resolved against the actual Order")
        return ResolvedPreTradePlan(
            self.order_rule_timeline, self.notional_evidence, self.evaluated_at,
            rules, self.evaluated_at, commitment,
            self.requirement_source_key, self.requirement_source_version,
            self.requirement_source_hash, self.account_risk_policy, self.evaluated_at,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_cash_pretrade_authority", "schema_version": 1,
            "order_rule_timeline": self.order_rule_timeline,
            "notional_evidence": self.notional_evidence, "evaluated_at": self.evaluated_at,
            "fee_reservation_rule_set": self.fee_reservation_rule_set,
            "requirement_source_key": self.requirement_source_key,
            "requirement_source_version": self.requirement_source_version,
            "requirement_source_hash": self.requirement_source_hash,
            "account_risk_policy": self.account_risk_policy,
        }


@dataclass(frozen=True, slots=True)
class ResolvedOrderAdmissionSlot:
    """Reserved identities and authority; the Engine supplies the actual Order."""

    order_id: DomainId
    capability_set: OrderCapabilitySet
    translation_mapping: OrderTranslationMapping
    translation_time: UtcInstant
    pretrade_authority: ResolvedCashPreTradeAuthority
    event_plan: tuple[OrderEventPlan, ...]
    expiration_event_id: str

    def __post_init__(self) -> None:
        _domain_id("order_id", self.order_id, DomainIdKind.ORDER)
        _text("expiration_event_id", self.expiration_event_id)
        for value, expected in (
            (self.capability_set, OrderCapabilitySet),
            (self.translation_mapping, OrderTranslationMapping),
            (self.translation_time, UtcInstant),
            (self.pretrade_authority, ResolvedCashPreTradeAuthority),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"admission slot requires {expected.__name__}")
        if not isinstance(self.event_plan, tuple) or not all(isinstance(event, OrderEventPlan) for event in self.event_plan):
            raise TypeError("event_plan must contain OrderEventPlan")
        if tuple(event.event_type for event in self.event_plan) != _REQUIRED_ADMISSION_EVENTS:
            raise ValueError("admission slot must contain the exact eight gate events")
        clocks = tuple(event.occurred_at for event in self.event_plan)
        if any(left >= right for left, right in zip(clocks, clocks[1:], strict=False)):
            raise ValueError("admission slot clocks must be strictly ordered")
        ids = (self.expiration_event_id, *(event.event_id for event in self.event_plan))
        if len(set(ids)) != len(ids):
            raise ValueError("admission slot identities must be unique")
        if any(clock.instant != self.translation_time for clock in clocks) or self.pretrade_authority.evaluated_at != self.translation_time:
            raise ValueError("live admission gates must share the receipt UTC instant")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_order_admission_slot", "schema_version": 1,
            "order_id": self.order_id, "capability_set": self.capability_set,
            "translation_mapping": self.translation_mapping, "translation_time": self.translation_time,
            "pretrade_authority": self.pretrade_authority, "event_plan": self.event_plan,
            "expiration_event_id": self.expiration_event_id,
        }


@dataclass(frozen=True, slots=True)
class ResolvedDecisionCycleV2:
    """One full-equity sleeve, one cash instrument, and no caller-owned holdings."""

    schedule: TargetStreamDecisionSchedule
    snapshot_plan: LedgerCashSnapshotProjectionPlan
    allocation_policy: CapitalAllocationPolicyRef
    target_notional_scale: Scale
    risk_policy: PortfolioRiskPolicy
    sizing_policy: PositionSizingPolicy
    quantity_lattice: QuantityLattice
    target_valid_until: UtcInstant | None
    rebalance_policy: RebalancePolicy
    admission_slot: ResolvedOrderAdmissionSlot

    def __post_init__(self) -> None:
        for value, expected in (
            (self.schedule, TargetStreamDecisionSchedule),
            (self.snapshot_plan, LedgerCashSnapshotProjectionPlan),
            (self.allocation_policy, CapitalAllocationPolicyRef),
            (self.target_notional_scale, Scale), (self.risk_policy, PortfolioRiskPolicy),
            (self.sizing_policy, PositionSizingPolicy), (self.quantity_lattice, QuantityLattice),
            (self.rebalance_policy, RebalancePolicy), (self.admission_slot, ResolvedOrderAdmissionSlot),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"live decision requires {expected.__name__}")
        if self.schedule.segment is not TimelineSegment.ACTIVE_TRADING or len(self.schedule.entries) != 1:
            raise ValueError("live cash case supports one active sleeve per decision")
        at = self.snapshot_plan.projection_at
        context = self.schedule.entries[0].validation_context
        if at.instant != self.schedule.decision_time or context.decision_instant != at:
            raise ValueError("live decision requires the exact snapshot/decision receipt")
        if context.universe != (self.quantity_lattice.instrument_id,) or context.instrument_catalog != self.snapshot_plan.instrument_catalog:
            raise ValueError("live decision instrument authority mismatch")
        if self.sizing_policy.price_purpose is not PricePurpose.VALUATION:
            raise ValueError("live cash sizing requires explicit VALUATION authority")
        if self.admission_slot.translation_time != at.instant or self.admission_slot.event_plan[0].occurred_at <= at:
            raise ValueError("live admission must follow decision at the same UTC instant")
        if self.target_valid_until is not None and (
            not isinstance(self.target_valid_until, UtcInstant) or self.target_valid_until <= at.instant
        ):
            raise ValueError("target_valid_until must follow the decision")

    @property
    def cycle_hash(self) -> str:
        return canonical_sha256(self)

    @property
    def planning_at(self) -> UtcInstant:
        return self.schedule.decision_time

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_decision_cycle", "schema_version": 2,
            "schedule": self.schedule, "snapshot_plan": self.snapshot_plan,
            "allocation_policy": self.allocation_policy, "allocation_basis": "current_equity",
            "target_notional_scale": self.target_notional_scale.places,
            "risk_policy": self.risk_policy, "sizing_policy": self.sizing_policy,
            "quantity_lattice": self.quantity_lattice, "target_valid_until": self.target_valid_until,
            "rebalance_policy": self.rebalance_policy, "admission_slot": self.admission_slot,
        }


@dataclass(frozen=True, slots=True)
class ResolvedBarPlanV2:
    """One observed close with reserved fill identities, not a future Order ID."""

    event_id: str
    instrument_id: InstrumentId
    pretrade_authority: ResolvedCashPreTradeAuthority
    liquidity_evidence: BarLiquidityEvidence
    market_state: SlippageMarketState
    slippage_model: DeterministicBpsSlippageModel
    fill_id: DomainId
    fill_event_id: str
    fill_event_at: SimulationInstant
    accounting_plan: FillAccountingDispatchPlan

    def __post_init__(self) -> None:
        _text("event_id", self.event_id)
        _text("fill_event_id", self.fill_event_id)
        _domain_id("fill_id", self.fill_id, DomainIdKind.FILL)
        for value, expected in (
            (self.instrument_id, InstrumentId), (self.pretrade_authority, ResolvedCashPreTradeAuthority),
            (self.liquidity_evidence, BarLiquidityEvidence), (self.market_state, SlippageMarketState),
            (self.slippage_model, DeterministicBpsSlippageModel), (self.fill_event_at, SimulationInstant),
            (self.accounting_plan, EventScopedFillAccountingDispatchPlan),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"live bar requires {expected.__name__}")
        accounting = self.accounting_plan
        if accounting.source_event_id != self.event_id or accounting.expected_fill_id != self.fill_id:
            raise ValueError("live bar accounting identity mismatch")
        payload = accounting.position_payload
        if type(payload) is not CashFillAccountingPlan or payload.cost_basis_policy.policy_version < 2 or payload.position_key.instrument_id != self.instrument_id:
            raise ValueError("live cash execution requires authoritative v2 cash lot accounting")
        if self.pretrade_authority.evaluated_at != self.fill_event_at.instant:
            raise ValueError("live bar authority must use the actual close receipt UTC")
        if isinstance(accounting, SettlementFillAccountingDispatchPlan) and accounting.settlement_recorded_at < self.fill_event_at:
            raise ValueError("settlement recording cannot precede its actual fill receipt")
        fee = accounting.fee_plan
        clocks = (self.fill_event_at, accounting.fill_recorded_at, fee.assessment_at, fee.fee_recorded_at)
        if isinstance(fee, FullFillOrderFeeAccountingPlan) and fee.fill_fee_plan is not None:
            prior = fee.fill_fee_plan
            clocks = (*clocks[:2], prior.assessment_at, prior.fee_recorded_at, *clocks[2:])
        if any(at.instant != self.fill_event_at.instant for at in clocks) or any(
            left >= right for left, right in zip(clocks, clocks[1:], strict=False)
        ):
            raise ValueError("live fill/accounting/fee receipts must be strictly ordered at close UTC")
        if f"position_accounting.{self.event_id}" not in accounting.expected_artifact_roles:
            raise ValueError("live bar must declare event-scoped position accounting evidence")

    @property
    def execution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_bar_plan", "schema_version": 2,
            "event_id": self.event_id, "instrument_id": self.instrument_id,
            "pretrade_authority": self.pretrade_authority,
            "liquidity_evidence": self.liquidity_evidence, "market_state": self.market_state,
            "slippage_model": {
                "component_ref": self.slippage_model.component_ref, "calibration_ref": self.slippage_model.calibration_ref,
                "applicability_envelope": self.slippage_model.applicability_envelope,
                "basis_points_units": self.slippage_model.basis_points_units,
                "basis_points_scale": self.slippage_model.basis_points_scale.places,
                "rounding": self.slippage_model.rounding.value,
                "limitations": tuple(value.value for value in self.slippage_model.limitations),
            },
            "fill_id": self.fill_id, "fill_event_id": self.fill_event_id,
            "fill_event_at": self.fill_event_at, "accounting_plan": self.accounting_plan,
        }


@dataclass(frozen=True, slots=True)
class ResolvedExecutionCaseV2:
    """Additive live-state cash case. Legacy cases and codecs are unchanged."""

    case_key: str
    case_version: int
    semantic_spec_hash: str
    timeline: DeterministicTimeline
    timeline_batch_size: int
    target_stream: PrecomputedTargetStream
    decision_cycles: tuple[ResolvedDecisionCycleV2, ...]
    bar_executions: tuple[ResolvedBarPlanV2, ...]
    financial_state: ResolvedFinancialState
    financial_dispatch_plan: FinancialDispatchPlan
    execution_model: NextEligibleBarCloseModel
    snapshot_plan: LedgerCashSnapshotProjectionPlan
    closeout_policy: CloseoutPolicy[RunEndCloseoutRequest, RunEndCloseoutDecision, RunEndCloseoutFailure]
    identity_manifest: ExecutionCaseIdentityManifest | None = None
    semantic_spec: ExecutionCaseSemanticSpec | None = None

    def __post_init__(self) -> None:
        _text("case_key", self.case_key)
        _hash("semantic_spec_hash", self.semantic_spec_hash)
        for name in ("case_version", "timeline_batch_size"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive integer")
        for value, expected in (
            (self.timeline, DeterministicTimeline), (self.target_stream, PrecomputedTargetStream),
            (self.financial_state, ResolvedFinancialState), (self.financial_dispatch_plan, FinancialDispatchPlan),
            (self.execution_model, NextEligibleBarCloseModel), (self.snapshot_plan, LedgerCashSnapshotProjectionPlan),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"live case requires {expected.__name__}")
        for values, expected in ((self.decision_cycles, ResolvedDecisionCycleV2), (self.bar_executions, ResolvedBarPlanV2)):
            if not isinstance(values, tuple) or not all(type(value) is expected for value in values):
                raise TypeError(f"live case must contain exact {expected.__name__}")
        if not callable(getattr(self.closeout_policy, "spec", None)) or not callable(getattr(self.closeout_policy, "resolve_closeout", None)):
            raise TypeError("closeout_policy must satisfy CloseoutPolicy")
        if self.identity_manifest is not None and not isinstance(self.identity_manifest, ExecutionCaseIdentityManifest):
            raise TypeError("identity_manifest must be ExecutionCaseIdentityManifest")
        if self.semantic_spec is not None and (
            not isinstance(self.semantic_spec, ExecutionCaseSemanticSpec) or self.semantic_spec.semantic_spec_hash != self.semantic_spec_hash
        ):
            raise ValueError("live semantic spec mismatch")
        if self.snapshot_plan.projection_at != SimulationInstant(self.timeline.window.end_exclusive, _FINALIZE_PHASE, SourceSequence(0)):
            raise ValueError("live final snapshot requires the exact Engine finalization clock")
        if self.financial_dispatch_plan.final_snapshot_payload != self.snapshot_plan:
            raise ValueError("live financial dispatch snapshot mismatch")
        financial = self.financial_state
        if financial.order_streams or financial.order_admissions or financial.reservation_schedules or financial.settlement_book.events or financial.settlement_book.obligations:
            raise ValueError("live cash case requires pristine initial order and settlement state")
        if any(entry.recorded_at.instant >= self.timeline.window.trading_start for entry in financial.journal.entries):
            raise ValueError("initial journal must precede live trading")
        cycles = tuple(sorted(self.decision_cycles, key=lambda cycle: cycle.snapshot_plan.projection_at))
        bars = tuple(sorted(self.bar_executions, key=lambda bar: (bar.fill_event_at, bar.event_id)))
        clocks = tuple(cycle.snapshot_plan.projection_at for cycle in cycles)
        if len(set(clocks)) != len(clocks) or len({bar.event_id for bar in bars}) != len(bars):
            raise ValueError("live decision clocks and bar event IDs must be unique")
        instruments = {cycle.quantity_lattice.instrument_id for cycle in cycles} | {bar.instrument_id for bar in bars}
        if len(instruments) != 1:
            raise ValueError("live cash case supports exactly one instrument")
        contexts = {cycle.schedule.entries[0].expectation for cycle in cycles}
        if len(contexts) != 1:
            raise ValueError("live cash case supports exactly one full-equity sleeve")
        scheduled_ids = tuple(cycle.schedule.entries[0].event_id for cycle in cycles)
        if len(set(scheduled_ids)) != len(scheduled_ids) or set(scheduled_ids) != {event.event_id for event in self.target_stream.events}:
            raise ValueError("live TargetStream schedules must exact-cover events")
        targets = {event.event_id: event for event in self.target_stream.events}
        for cycle in cycles:
            if targets[cycle.schedule.entries[0].event_id].timeline_instant != cycle.snapshot_plan.projection_at:
                raise ValueError("live decision receipt does not match its actual target event")
        fixed_roles = {
            "final_snapshot", "runtime.identity_closure", *(f"snapshot.{event_id}" for event_id in scheduled_ids),
            *(role for event in self.financial_dispatch_plan.scheduled_account_events for role in event.expected_artifact_roles),
        }
        if tuple(sorted(fixed_roles)) != self.financial_dispatch_plan.expected_artifact_roles:
            raise ValueError("live fixed artifact roles must exact-cover snapshots and scheduled events")
        dynamic_roles = tuple(role for bar in bars for role in bar.accounting_plan.expected_artifact_roles)
        if len(set(dynamic_roles)) != len(dynamic_roles) or set(dynamic_roles) & fixed_roles:
            raise ValueError("live dynamic artifact roles must be unique and disjoint")
        object.__setattr__(self, "decision_cycles", cycles)
        object.__setattr__(self, "bar_executions", bars)
        self._expected_identity_bindings()

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def verify_identity_manifest(self, semantic_run_id: str) -> bool:
        manifest, spec = self.identity_manifest, self.semantic_spec
        if manifest is None or spec is None or manifest.semantic_run_id != semantic_run_id or manifest.namespace != spec.identity_namespace:
            return False
        actual_plan = tuple((b.binding_key, b.semantic_key, b.ordinal, b.domain_kind) for b in manifest.bindings)
        expected_plan = tuple((b.binding_key, b.semantic_key, b.ordinal, b.domain_kind) for b in spec.identity_plan)
        actual = {b.binding_key: (b.value, b.domain_kind) for b in manifest.bindings}
        return actual_plan == expected_plan and actual == self._expected_identity_bindings()

    def _expected_identity_bindings(self) -> dict[str, tuple[str, DomainIdKind | None]]:
        expected: dict[str, tuple[str, DomainIdKind | None]] = {
            f"journal.initial.{i}": (entry.journal_entry_id.value, DomainIdKind.JOURNAL)
            for i, entry in enumerate(self.financial_state.journal.entries)
        }
        for i, cycle in enumerate(self.decision_cycles):
            slot = cycle.admission_slot
            expected[f"order.{i}.0"] = (slot.order_id.value, DomainIdKind.ORDER)
            expected[f"order-event.expire.{i}"] = (slot.expiration_event_id, None)
            for j, event in enumerate(slot.event_plan):
                expected[f"order-event.{i}.0.{j}"] = (event.event_id, None)
        for i, bar in enumerate(self.bar_executions):
            plan, fee = bar.accounting_plan, bar.accounting_plan.fee_plan
            for key, value, kind in (
                ("fill", bar.fill_id.value, DomainIdKind.FILL),
                ("order-event.fill", bar.fill_event_id, None),
                ("journal.fill", plan.fill_journal_entry_id.value, DomainIdKind.JOURNAL),
                ("fee", fee.fee_assessment_id.value, DomainIdKind.FEE),
                ("journal.fee", fee.fee_journal_entry_id.value, DomainIdKind.JOURNAL),
            ):
                expected[f"{key}.{i}"] = (value, kind)
            if isinstance(plan, SettlementFillAccountingDispatchPlan):
                for j, slot in enumerate(plan.settlement_slots):
                    expected[f"settlement.{i}.{j}"] = (slot.obligation_id.value, DomainIdKind.SETTLEMENT)
                    expected[f"settlement-event.recorded.{i}.{j}"] = (slot.recorded_event_id, None)
                    expected[f"settlement-event.applied.{i}.{j}"] = (slot.applied_event_id, None)
            if isinstance(fee, FullFillOrderFeeAccountingPlan) and fee.fill_fee_plan is not None:
                prior = fee.fill_fee_plan
                expected[f"fee.fill.{i}"] = (prior.fee_assessment_id.value, DomainIdKind.FEE)
                expected[f"journal.fee.fill.{i}"] = (prior.fee_journal_entry_id.value, DomainIdKind.JOURNAL)
        for event in self.financial_dispatch_plan.scheduled_account_events:
            for key, value in event.identity_bindings:
                if key in expected:
                    raise ValueError("duplicate live financial identity binding")
                expected[key] = (value.value, value.kind)
        if len({value for value, _ in expected.values()}) != len(expected):
            raise ValueError("live identity slots must be globally unique")
        return expected

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_execution_case", "schema_version": 2,
            "case_key": self.case_key, "case_version": self.case_version,
            "semantic_spec_hash": self.semantic_spec_hash,
            "timeline": {"timeline_id": self.timeline.timeline_id, "bundle_ref": self.timeline.reader.bundle_ref,
                         "stream_keys": self.timeline.stream_keys, "window": self.timeline.window},
            "target_stream": self.target_stream, "decision_cycles": self.decision_cycles,
            "bar_executions": self.bar_executions, "financial_state": self.financial_state,
            "financial_dispatch_plan": self.financial_dispatch_plan,
            "execution_model_spec": self.execution_model.spec(), "snapshot_plan": self.snapshot_plan,
            "closeout_policy_spec": self.closeout_policy.spec(),
            "identity_manifest_hash": self.identity_manifest.manifest_hash if self.identity_manifest else None,
        }


ExecutionCase = ResolvedExecutionCase | ResolvedExecutionCaseV2


@dataclass(frozen=True, slots=True)
class RuntimeIdentityDisposition:
    binding_key: str
    value: str
    status: str
    reason: str | None
    evidence_hash: str | None

    def __post_init__(self) -> None:
        _text("binding_key", self.binding_key)
        _text("value", self.value)
        if self.status == "used":
            if self.reason is not None:
                raise ValueError("used identity cannot have an unused reason")
            _hash("evidence_hash", cast(str, self.evidence_hash))
        elif self.status == "unused":
            _text("reason", cast(str, self.reason))
            if self.evidence_hash is not None:
                raise ValueError("unused identity cannot claim execution evidence")
        else:
            raise ValueError("identity disposition must be used or unused")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"binding_key": self.binding_key, "value": self.value, "status": self.status,
                "reason": self.reason, "evidence_hash": self.evidence_hash}


@dataclass(frozen=True, slots=True)
class RuntimeIdentityClosure:
    identity_manifest_hash: str
    dispositions: tuple[RuntimeIdentityDisposition, ...]

    def __post_init__(self) -> None:
        _hash("identity_manifest_hash", self.identity_manifest_hash)
        if not isinstance(self.dispositions, tuple) or not all(type(item) is RuntimeIdentityDisposition for item in self.dispositions):
            raise TypeError("dispositions must contain RuntimeIdentityDisposition")
        if len({item.binding_key for item in self.dispositions}) != len(self.dispositions) or len({item.value for item in self.dispositions}) != len(self.dispositions):
            raise ValueError("identity dispositions must be unique")
        object.__setattr__(self, "dispositions", tuple(sorted(self.dispositions, key=lambda item: item.binding_key)))

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "runtime_identity_closure", "schema_version": 1,
                "identity_manifest_hash": self.identity_manifest_hash, "dispositions": self.dispositions}


@dataclass(frozen=True, slots=True)
class PendingPositionSellDeferral:
    """A full planned SELL rejected only by not-yet-sellable positive receipts."""

    rejection: PreTradeRiskRejection
    pending_obligations: tuple[AccountSettlementObligation, ...]
    settlement_book_hash: str
    deferred_at: SimulationInstant

    def __post_init__(self) -> None:
        if type(self.rejection) is not PreTradeRiskRejection or not isinstance(self.deferred_at, SimulationInstant):
            raise TypeError("deferral requires authoritative rejection and receipt")
        _hash("settlement_book_hash", self.settlement_book_hash)
        if (not isinstance(self.pending_obligations, tuple) or not self.pending_obligations
                or not all(type(value) is AccountSettlementObligation for value in self.pending_obligations)):
            raise TypeError("deferral requires actual pending obligations")
        order = self.rejection.order
        source = self.rejection.evaluation_input
        failed = tuple(check for check in self.rejection.checks if not check.approved)
        positions = tuple(value for value in source.availability_state.positions
                          if value.key.instrument_id == order.intent.instrument_id)
        if (order.intent.side is not OrderSide.SELL or self.deferred_at.instant != source.evaluated_at
                or len(failed) != 1 or failed[0].reason_code is not PreTradeRiskReasonCode.SELLABLE_QUANTITY
                or failed[0].available_units != 0 or failed[0].required_units != order.intent.quantity.units
                or len(positions) != 1 or positions[0].sellable.units != 0
                or positions[0].total.scale != order.intent.quantity.scale
                or any(value.units for value in source.reservation_state.totals.sellable_quantities
                       if value.instrument_id == order.intent.quantity.instrument_id)
                or any(value.balance_key != positions[0].key or value.units <= 0
                       or value.value.scale != order.intent.quantity.scale
                       or value.obligation.settlement_time <= self.deferred_at.instant
                       for value in self.pending_obligations)
                or len({value.obligation.settlement_obligation_id for value in self.pending_obligations}) != len(self.pending_obligations)
                or sum(value.units for value in self.pending_obligations) != positions[0].total.units
                or positions[0].total.units < order.intent.quantity.units):
            raise ValueError("not an exclusively pending-position full SELL deferral")
        object.__setattr__(self, "pending_obligations", tuple(sorted(self.pending_obligations,
            key=lambda value: value.obligation.settlement_obligation_id.value)))

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "pending_position_sell_deferral", "schema_version": 1,
                "rejection": self.rejection, "pending_obligations": self.pending_obligations,
                "settlement_book_hash": self.settlement_book_hash, "deferred_at": self.deferred_at}


class EngineStage(str, Enum):
    TIMELINE_EVENT = "timeline_event"
    TARGET_WARMUP_SUPPRESSED = "target_warmup_suppressed"
    DECISION_BATCH = "decision_batch"
    CAPITAL_ALLOCATION = "capital_allocation"
    PORTFOLIO_RISK = "portfolio_risk"
    POSITION_SIZING = "position_sizing"
    ORDER_PLAN = "order_plan"
    ORDER_CAPABILITY = "order_capability"
    ORDER_TRANSLATION = "order_translation"
    MARKET_RULE = "market_rule"
    FEE_RESERVATION = "fee_reservation"
    PRETRADE_RISK = "pretrade_risk"
    ORDER_ACCEPTED = "order_accepted"
    EXECUTION_DECISION = "execution_decision"
    SLIPPAGE = "slippage"
    FILL = "fill"
    FILL_ACCOUNTING = "fill_accounting"
    FINANCIAL_EVENT = "financial_event"
    FEE_ASSESSMENT = "fee_assessment"
    FEE_ACCOUNTING = "fee_accounting"
    LEDGER_STATE = "ledger_state"
    PORTFOLIO_SNAPSHOT = "portfolio_snapshot"
    RUN_END = "run_end"


@dataclass(frozen=True, slots=True)
class ExecutionTraceEntry:
    sequence: int
    stage: EngineStage
    instant: SimulationInstant
    subject_id: str
    evidence_hash: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValueError("trace sequence must be nonnegative integer")
        if not isinstance(self.stage, EngineStage):
            raise TypeError("stage must be EngineStage")
        if not isinstance(self.instant, SimulationInstant):
            raise TypeError("instant must be SimulationInstant")
        _text("subject_id", self.subject_id)
        _hash("evidence_hash", self.evidence_hash)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "stage": self.stage.value,
            "instant": self.instant,
            "subject_id": self.subject_id,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    entries: tuple[ExecutionTraceEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple) or not all(
            isinstance(value, ExecutionTraceEntry) for value in self.entries
        ):
            raise TypeError("entries must contain ExecutionTraceEntry")
        if tuple(value.sequence for value in self.entries) != tuple(
            range(len(self.entries))
        ):
            raise ValueError("trace sequences must be contiguous from zero")

    @property
    def trace_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_trace",
            "schema_version": 1,
            "entries": self.entries,
        }


class EngineFailureCode(str, Enum):
    TIMELINE_FAILURE = "timeline_failure"
    TARGET_INPUT_DECODE = "target_input_decode"
    TARGET_VALIDATION = "target_validation"
    DECISION_BATCH = "decision_batch"
    ALLOCATION = "allocation"
    PORTFOLIO_RISK = "portfolio_risk"
    POSITION_SIZING = "position_sizing"
    REBALANCE = "rebalance"
    ORDER_PLAN_MISMATCH = "order_plan_mismatch"
    CAPABILITY_REJECTED = "capability_rejected"
    TRANSLATION_REJECTED = "translation_rejected"
    MARKET_RULE_REJECTED = "market_rule_rejected"
    MARKET_RULE_DATA_FAILURE = "market_rule_data_failure"
    FEE_RESERVATION = "fee_reservation"
    PRETRADE_REJECTED = "pretrade_rejected"
    PRETRADE_CONTRACT_FAILURE = "pretrade_contract_failure"
    EXECUTION_FAILURE = "execution_failure"
    SLIPPAGE_FAILURE = "slippage_failure"
    FILL_CONSTRUCTION = "fill_construction"
    ACCOUNTING_FAILURE = "accounting_failure"
    FINANCIAL_DISPATCH_FAILURE = "financial_dispatch_failure"
    FEE_ASSESSMENT_FAILURE = "fee_assessment_failure"
    FEE_ACCOUNTING_FAILURE = "fee_accounting_failure"
    SNAPSHOT_PROJECTION_FAILURE = "snapshot_projection_failure"
    RUN_END_TERMINATED = "run_end_terminated"
    CASE_EVIDENCE_MISMATCH = "case_evidence_mismatch"
    MISSING_SCHEDULED_EVENT = "missing_scheduled_event"


@dataclass(frozen=True, slots=True)
class EngineFailure:
    code: EngineFailureCode
    case_hash: str
    trace_hash: str
    subject_keys: tuple[str, ...]
    evidence_hashes: tuple[str, ...] = ()
    termination: EngineTermination | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, EngineFailureCode):
            raise TypeError("code must be EngineFailureCode")
        _hash("case_hash", self.case_hash)
        _hash("trace_hash", self.trace_hash)
        if not isinstance(self.subject_keys, tuple) or not self.subject_keys:
            raise ValueError("subject_keys must be nonempty")
        subjects = tuple(sorted({_text("subject_key", value) for value in self.subject_keys}))
        hashes = tuple(sorted({_hash("evidence_hash", value) for value in self.evidence_hashes}))
        if self.termination is not None and not isinstance(self.termination, EngineTermination):
            raise TypeError("termination must be EngineTermination or None")
        object.__setattr__(self, "subject_keys", subjects)
        object.__setattr__(self, "evidence_hashes", hashes)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_failure",
            "code": self.code.value,
            "case_hash": self.case_hash,
            "trace_hash": self.trace_hash,
            "subject_keys": self.subject_keys,
            "evidence_hashes": self.evidence_hashes,
            "termination": self.termination,
        }


@dataclass(frozen=True, slots=True)
class EngineCancellationRequest:
    cancel_before_event_id: str
    reason_code: str

    def __post_init__(self) -> None:
        _text("cancel_before_event_id", self.cancel_before_event_id)
        _text("reason_code", self.reason_code)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_cancellation_request",
            "cancel_before_event_id": self.cancel_before_event_id,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class EngineCancellation:
    case_hash: str
    request: EngineCancellationRequest
    processed_timeline_events: int
    trace_hash: str

    def __post_init__(self) -> None:
        _hash("case_hash", self.case_hash)
        if not isinstance(self.request, EngineCancellationRequest):
            raise TypeError("request must be EngineCancellationRequest")
        if (
            isinstance(self.processed_timeline_events, bool)
            or not isinstance(self.processed_timeline_events, int)
            or self.processed_timeline_events < 0
        ):
            raise ValueError("processed_timeline_events must be nonnegative integer")
        _hash("trace_hash", self.trace_hash)

    @property
    def cancellation_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_cancellation",
            "case_hash": self.case_hash,
            "request": self.request,
            "processed_timeline_events": self.processed_timeline_events,
            "trace_hash": self.trace_hash,
        }


@dataclass(frozen=True, slots=True)
class EngineExecutionResult:
    case_hash: str
    target_stream_digest: str
    trace: ExecutionTrace
    decision_batches: tuple[DecisionBatch, ...]
    allocations: tuple[PortfolioAllocation, ...]
    approved_targets: tuple[ApprovedPortfolioTarget, ...]
    normalized_targets: tuple[NormalizedPortfolioTarget, ...]
    order_plans: tuple[OrderPlan, ...]
    order_streams: tuple[OrderEventStream, ...]
    fills: tuple[Fill, ...]
    slippage_decisions: tuple[SlippageDecision, ...]
    fee_assessments: tuple[FeeAssessment, ...]
    financial_artifacts: tuple[FinancialDispatchArtifact, ...]
    final_journal: AccountingJournal
    final_ledger_state: LedgerState
    final_portfolio_snapshot: PortfolioSnapshot
    run_end_report: RunEndReport

    def __post_init__(self) -> None:
        _hash("case_hash", self.case_hash)
        _hash("target_stream_digest", self.target_stream_digest)
        if not isinstance(self.trace, ExecutionTrace):
            raise TypeError("trace must be ExecutionTrace")
        for name, values, expected_type in (
            ("decision_batches", self.decision_batches, DecisionBatch),
            ("allocations", self.allocations, PortfolioAllocation),
            ("approved_targets", self.approved_targets, ApprovedPortfolioTarget),
            ("normalized_targets", self.normalized_targets, NormalizedPortfolioTarget),
            ("order_plans", self.order_plans, OrderPlan),
            ("order_streams", self.order_streams, OrderEventStream),
            ("fills", self.fills, Fill),
            ("slippage_decisions", self.slippage_decisions, SlippageDecision),
            ("fee_assessments", self.fee_assessments, FeeAssessment),
            ("financial_artifacts", self.financial_artifacts, FinancialDispatchArtifact),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(value, expected_type) for value in values
            ):
                raise TypeError(f"{name} contains invalid values")
        if not isinstance(self.final_journal, AccountingJournal):
            raise TypeError("final_journal must be AccountingJournal")
        if not isinstance(self.final_ledger_state, LedgerState):
            raise TypeError("final_ledger_state must be LedgerState")
        if not isinstance(self.final_portfolio_snapshot, PortfolioSnapshot):
            raise TypeError("final_portfolio_snapshot must be PortfolioSnapshot")
        if not isinstance(self.run_end_report, RunEndReport):
            raise TypeError("run_end_report must be RunEndReport")
        if self.final_ledger_state.state_hash != self.final_portfolio_snapshot.journal_state_hash:
            raise ValueError("Final Snapshot must reference Final Ledger State")
        if canonical_sha256(self.final_portfolio_snapshot) != self.run_end_report.final_snapshot_hash:
            raise ValueError("RunEndReport must reference Final Snapshot")
        object.__setattr__(self, "order_streams", _stable_tuple(self.order_streams))
        object.__setattr__(self, "fills", _stable_tuple(self.fills))
        object.__setattr__(
            self, "slippage_decisions", _stable_tuple(self.slippage_decisions)
        )
        object.__setattr__(self, "fee_assessments", _stable_tuple(self.fee_assessments))
        object.__setattr__(
            self,
            "financial_artifacts",
            tuple(
                sorted(
                    self.financial_artifacts,
                    key=lambda value: (
                        canonical_bytes(value.occurred_at),
                        value.source_event_id,
                        value.role,
                    ),
                )
            ),
        )

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_execution_result",
            "schema_version": 1,
            "case_hash": self.case_hash,
            "target_stream_digest": self.target_stream_digest,
            "trace": self.trace,
            "decision_batches": self.decision_batches,
            "allocations": self.allocations,
            "approved_targets": self.approved_targets,
            "normalized_targets": self.normalized_targets,
            "order_plans": self.order_plans,
            "order_streams": self.order_streams,
            "fills": self.fills,
            "slippage_decisions": self.slippage_decisions,
            "fee_assessments": self.fee_assessments,
            "financial_artifacts": self.financial_artifacts,
            "final_journal": self.final_journal,
            "final_ledger_state": self.final_ledger_state,
            "final_portfolio_snapshot": self.final_portfolio_snapshot,
            "run_end_report": self.run_end_report,
        }


@dataclass(frozen=True, slots=True)
class EngineExecutionOutcome:
    result: EngineExecutionResult | None = None
    input_validation_failure: InputValidationFailure | None = None
    engine_failure: EngineFailure | None = None
    cancellation: EngineCancellation | None = None

    def __post_init__(self) -> None:
        branches = (
            self.result is not None,
            self.input_validation_failure is not None,
            self.engine_failure is not None,
            self.cancellation is not None,
        )
        if sum(branches) != 1:
            raise ValueError("Engine outcome requires exactly one branch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_execution_outcome",
            "result": self.result,
            "input_validation_failure": self.input_validation_failure,
            "engine_failure": self.engine_failure,
            "cancellation": self.cancellation,
        }


@dataclass(slots=True)
class _EngineState:
    journal: AccountingJournal
    ledger: GenericLedger
    ledger_state: LedgerState
    snapshot: PortfolioSnapshot
    lot_books: dict[PositionBalanceKey, tuple[PositionLot, ...]]
    settlement_book: SettlementBook
    settlement_state: SettlementBookState
    reservation_book: ResourceReservationBook
    reservation_state: ResourceReservationState
    availability: AvailabilityState
    order_streams: dict[str, OrderEventStream]
    reservation_schedules: dict[str, OrderReservationSchedule]
    admissions: dict[str, ResolvedOrderAdmission] = field(default_factory=dict)
    latest_sleeve_state: LatestSleeveDecisionState | None = None
    trace_entries: list[ExecutionTraceEntry] = field(default_factory=list)
    decision_batches: list[DecisionBatch] = field(default_factory=list)
    allocations: list[PortfolioAllocation] = field(default_factory=list)
    approved_targets: list[ApprovedPortfolioTarget] = field(default_factory=list)
    normalized_targets: list[NormalizedPortfolioTarget] = field(default_factory=list)
    order_plans: list[OrderPlan] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    slippage_decisions: list[SlippageDecision] = field(default_factory=list)
    fee_assessments: list[FeeAssessment] = field(default_factory=list)
    financial_artifacts: list[FinancialDispatchArtifact] = field(default_factory=list)
    live_clock: SimulationInstant | None = None
    live_unused_reasons: dict[str, str] = field(default_factory=dict)
    live_dynamic_roles: set[str] = field(default_factory=set)
    live_settlement_slots: dict[DomainId, SettlementIdentitySlot] = field(default_factory=dict)


class DeterministicBarEngine:
    """Pure orchestration over a fully resolved immutable execution case."""

    def __init__(
        self,
        financial_dispatcher: FinancialEventDispatcher | object = _DEFAULT_FINANCIAL_DISPATCHER,
    ) -> None:
        if financial_dispatcher is _DEFAULT_FINANCIAL_DISPATCHER:
            financial_dispatcher = DefaultCashFinancialDispatcher()
        if not isinstance(financial_dispatcher, FinancialEventDispatcher):
            raise TypeError("financial_dispatcher must satisfy FinancialEventDispatcher")
        self._financial_dispatcher = financial_dispatcher

    def run(
        self,
        case: ExecutionCase | InputValidationFailure,
        *,
        cancellation: EngineCancellationRequest | None = None,
    ) -> EngineExecutionOutcome:
        if isinstance(case, InputValidationFailure):
            return EngineExecutionOutcome(input_validation_failure=case)
        if not isinstance(case, ResolvedExecutionCase) and type(case) is not ResolvedExecutionCaseV2:
            raise TypeError("case must be a supported resolved execution case or InputValidationFailure")
        if cancellation is not None and not isinstance(
            cancellation, EngineCancellationRequest
        ):
            raise TypeError("cancellation must be EngineCancellationRequest or None")
        try:
            return self._execute(case, cancellation)
        except (JournalError, SettlementBookError, TypeError, ValueError) as error:
            trace = ExecutionTrace()
            return EngineExecutionOutcome(
                engine_failure=EngineFailure(
                    EngineFailureCode.CASE_EVIDENCE_MISMATCH,
                    case.case_hash,
                    trace.trace_hash,
                    (type(error).__name__,),
                    (canonical_sha256({"error_type": type(error).__name__}),),
                )
            )

    def _execute(
        self,
        case: ExecutionCase,
        cancellation: EngineCancellationRequest | None,
    ) -> EngineExecutionOutcome:
        state = self._initial_state(case)
        live = isinstance(case, ResolvedExecutionCaseV2)
        if live:
            state.live_settlement_slots = {slot.obligation_id: slot for bar in case.bar_executions
                if isinstance(bar.accounting_plan, SettlementFillAccountingDispatchPlan)
                for slot in bar.accounting_plan.settlement_slots}
        if live and (case.identity_manifest is None or not case.verify_identity_manifest(case.identity_manifest.semantic_run_id)):
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_identity_manifest",))
        if live:
            # Composition owns the ID-free preimage. Import only after module
            # initialization, rather than duplicating its canonical rules here.
            from .composition import ExecutionCaseComposer

            spec = case.semantic_spec
            assert spec is not None
            if ExecutionCaseComposer.semantic_spec_from_case(
                case, spec_key=spec.spec_key, spec_version=spec.spec_version,
                identity_namespace=spec.identity_namespace, identity_plan=spec.identity_plan,
            ) != spec:
                return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_semantic_spec",))
        if self._financial_dispatcher.spec != case.financial_dispatch_plan.dispatcher_spec:
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (FinancialDispatchFailureCode.DISPATCHER_SPEC_MISMATCH.value,),
                (
                    canonical_sha256(
                        {
                            "dispatcher_spec": self._financial_dispatcher.spec,
                            "case_dispatcher_spec": case.financial_dispatch_plan.dispatcher_spec,
                        }
                    ),
                ),
            )
        cycles_by_event: dict[str, ResolvedDecisionCycle | ResolvedDecisionCycleV2] = {}
        cycle_buffers: dict[str, list[TimelineEvent]] = {}
        for resolved_cycle in case.decision_cycles:
            cycle_buffers[resolved_cycle.cycle_hash] = []
            for entry in resolved_cycle.schedule.entries:
                cycles_by_event[entry.event_id] = resolved_cycle
        bars_by_event = {value.event_id: value for value in case.bar_executions}
        account_events_by_event = {
            value.event_id: value
            for value in case.financial_dispatch_plan.scheduled_account_events
        }
        processed_events = 0
        processed_cycles: set[str] = set()
        processed_bars: set[str] = set()
        processed_account_events: set[str] = set()
        timeline_cursor = case.timeline.open_cursor(batch_size=case.timeline_batch_size)

        while not timeline_cursor.window_complete:
            timeline_outcome = case.timeline.read_batch(timeline_cursor)
            if timeline_outcome.failure is not None:
                return self._failed(
                    case,
                    state,
                    EngineFailureCode.TIMELINE_FAILURE,
                    (timeline_outcome.failure.code.value,),
                    (canonical_sha256(timeline_outcome.failure),),
                )
            batch = timeline_outcome.batch
            if batch is None:
                raise ValueError("Timeline returned neither batch nor failure")
            timeline_cursor = batch.next_cursor
            for timeline_event in batch.events:
                event = timeline_event.event
                if (
                    cancellation is not None
                    and event.event_id == cancellation.cancel_before_event_id
                ):
                    return EngineExecutionOutcome(
                        cancellation=EngineCancellation(
                            case.case_hash,
                            cancellation,
                            processed_events,
                            self._trace(state).trace_hash,
                        )
                    )
                if live and state.live_clock is not None and event.timeline_instant <= state.live_clock:
                    return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_clock_overlap", event.event_id))
                if live:
                    state.live_clock = event.timeline_instant
                self._trace_add(
                    state,
                    EngineStage.TIMELINE_EVENT,
                    event.timeline_instant,
                    event.event_id,
                    event.event_hash,
                )
                processed_events += 1
                if live:
                    failure = self._due_settlements(case, state, event.event_id, event.event_hash, event.timeline_instant)
                    if failure is not None:
                        return failure

                account_event = account_events_by_event.get(event.event_id)
                if live and account_event is not None:
                    failure = self._scheduled_account_event(case, state, account_event, timeline_event)
                    if failure is not None:
                        return failure
                    processed_account_events.add(account_event.event_id)

                matched_cycle = cycles_by_event.get(event.event_id)
                if matched_cycle is not None:
                    buffer = cycle_buffers[matched_cycle.cycle_hash]
                    buffer.append(timeline_event)
                    if len(buffer) == len(matched_cycle.schedule.entries):
                        failure = self._decision_cycle(
                            case, state, matched_cycle, tuple(buffer)
                        )
                        if failure is not None:
                            return failure
                        processed_cycles.add(matched_cycle.cycle_hash)

                bar = bars_by_event.get(event.event_id)
                if live and event.capability == BAR_CLOSE_CAPABILITY and bar is None:
                    return self._failed(case, state, EngineFailureCode.MISSING_SCHEDULED_EVENT, (event.event_id,))
                if bar is not None:
                    failure = (
                        self._live_bar_execution(case, state, bar, timeline_event)
                        if isinstance(bar, ResolvedBarPlanV2)
                        else self._bar_execution(case, state, bar, timeline_event)
                    )
                    if failure is not None:
                        return failure
                    processed_bars.add(bar.execution_hash)

                if not live and account_event is not None:
                    failure = self._scheduled_account_event(case, state, account_event, timeline_event)
                    if failure is not None:
                        return failure
                    processed_account_events.add(account_event.event_id)

        missing_cycles = tuple(
            cycle.cycle_hash
            for cycle in case.decision_cycles
            if cycle.cycle_hash not in processed_cycles
        )
        missing_bars = tuple(
            value.execution_hash
            for value in case.bar_executions
            if value.execution_hash not in processed_bars
        )
        missing_account_events = tuple(
            value.event_id
            for value in case.financial_dispatch_plan.scheduled_account_events
            if value.event_id not in processed_account_events
        )
        if missing_cycles or missing_bars or missing_account_events:
            return self._failed(
                case,
                state,
                EngineFailureCode.MISSING_SCHEDULED_EVENT,
                missing_cycles + missing_bars + missing_account_events,
            )

        # A close model must see the explicit end-of-window no-candidate branch;
        # open execution retains its established run-end behavior.
        if isinstance(case.execution_model, NextEligibleBarCloseModel):
            failure = self._close_execution_window(case, state)
            if failure is not None:
                return failure

        if live:
            # Finalization is an actual processing boundary, not an economic-time backdate.
            failure = self._due_settlements(case, state, "engine-finalize", case.case_hash, case.snapshot_plan.projection_at,
                include_boundary=False)
            if failure is not None:
                return failure
        # Cursor batch size is an operational read concern, not economic evidence.
        timeline_cursor = case.timeline.resume_cursor(timeline_cursor, batch_size=1)
        snapshot_dispatch = self._financial_dispatcher.project_final_snapshot(
            case.financial_dispatch_plan,
            self._financial_state_view(state),
        )
        failure = self._apply_financial_dispatch(
            case,
            state,
            snapshot_dispatch,
            expected_snapshot=True,
            expected_source_event_id="engine-finalize" if isinstance(case, ResolvedExecutionCaseV2) else None,
            dispatch_at=case.snapshot_plan.projection_at if isinstance(case, ResolvedExecutionCaseV2) else None,
        )
        if failure is not None:
            return failure
        expected_roles = case.financial_dispatch_plan.expected_artifact_roles
        if isinstance(case, ResolvedExecutionCaseV2):
            failure = self._close_live_identities(case, state)
            if failure is not None:
                return failure
            filled = {fill.fill_id for fill in state.fills}
            expected_roles = tuple(sorted((*expected_roles, *state.live_dynamic_roles, *(
                role for bar in case.bar_executions if bar.fill_id in filled
                for role in bar.accounting_plan.expected_artifact_roles
            ))))
        actual_roles = tuple(sorted(value.role for value in state.financial_artifacts))
        if actual_roles != expected_roles:
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (FinancialDispatchFailureCode.ARTIFACT_COVERAGE_MISMATCH.value,),
                (
                    canonical_sha256(actual_roles),
                    canonical_sha256(expected_roles),
                ),
            )
        finalize_instant = SimulationInstant(
            case.timeline.window.end_exclusive,
            _FINALIZE_PHASE,
            SourceSequence(0),
        )
        self._trace_add(
            state,
            EngineStage.PORTFOLIO_SNAPSHOT,
            finalize_instant,
            state.snapshot.account_id,
            canonical_sha256(state.snapshot),
        )

        run_end = RunEndCoordinator().coordinate(
            RunEndEvidence(
                timeline_window=case.timeline.window,
                timeline_cursor=timeline_cursor,
                final_snapshot=state.snapshot,
                order_streams=tuple(state.order_streams.values()),
                reservation_state=state.reservation_state,
                settlement_state=state.settlement_state,
                pending_fee_assessments=(),
            ),
            case.closeout_policy,
        )
        if run_end.report is None:
            termination = cast(EngineTermination, run_end.termination)
            return self._failed(
                case,
                state,
                EngineFailureCode.RUN_END_TERMINATED,
                (termination.code.value,),
                (termination.termination_id,),
                termination=termination,
            )
        self._trace_add(
            state,
            EngineStage.RUN_END,
            finalize_instant,
            state.snapshot.account_id,
            run_end.report.report_hash,
        )
        result = EngineExecutionResult(
            case_hash=case.case_hash,
            target_stream_digest=case.target_stream.target_stream_digest,
            trace=self._trace(state),
            decision_batches=tuple(state.decision_batches),
            allocations=tuple(state.allocations),
            approved_targets=tuple(state.approved_targets),
            normalized_targets=tuple(state.normalized_targets),
            order_plans=tuple(state.order_plans),
            order_streams=tuple(state.order_streams.values()),
            fills=tuple(state.fills),
            slippage_decisions=tuple(state.slippage_decisions),
            fee_assessments=tuple(state.fee_assessments),
            financial_artifacts=tuple(state.financial_artifacts),
            final_journal=state.journal,
            final_ledger_state=state.ledger_state,
            final_portfolio_snapshot=state.snapshot,
            run_end_report=run_end.report,
        )
        return EngineExecutionOutcome(result=result)

    def _due_settlements(
        self, case: ExecutionCase, state: _EngineState, boundary_id: str,
        boundary_hash: str, boundary_at: SimulationInstant, *, include_boundary: bool = True,
    ) -> EngineExecutionOutcome | None:
        due = tuple(value for value in state.settlement_state.pending_obligations
                    if value.obligation.settlement_time < boundary_at.instant
                    or (include_boundary and value.obligation.settlement_time == boundary_at.instant))
        if not due:
            return None
        if any(value.obligation.settlement_obligation_id not in state.live_settlement_slots for value in due):
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("unmanifested_due_settlement",))
        payload = SettlementApplicationPlan(boundary_id, boundary_hash, state.settlement_book.book_hash,
            tuple(state.live_settlement_slots[value.obligation.settlement_obligation_id] for value in due),
            include_boundary=include_boundary)
        event_id = f"settlement-due:{boundary_id}"
        event = ScheduledAccountEvent(event_id, boundary_at, payload.operation_key, (payload.operation_key,), (),
            payload, payload, (f"settlement.{event_id}",))
        outcome = self._financial_dispatcher.dispatch_scheduled_event(event, self._financial_state_view(state))
        result = outcome.result
        if outcome.failure is None and (not isinstance(result, SettlementFinancialDispatchResult)
                or result.journal_entries or result.snapshot is not None or result.artifacts
                or {(value.event_id, value.settlement_obligation_id, value.causation_id) for value in result.settlement_events}
                   != {(slot.applied_event_id, slot.obligation_id, slot.recorded_event_id) for slot in payload.slots}
                or len(result.settlement_events) != len(payload.slots)):
            return self._failed(case, state, EngineFailureCode.FINANCIAL_DISPATCH_FAILURE, ("live_due_application_coverage",))
        failure = self._apply_financial_dispatch(case, state, outcome, expected_snapshot=False,
            expected_source_event_id=event_id, expected_source_evidence_hash=canonical_sha256(event), dispatch_at=boundary_at)
        if failure is None:
            state.live_dynamic_roles.add(f"settlement.{event_id}")
        return failure

    def _scheduled_account_event(
        self, case: ExecutionCase, state: _EngineState,
        account_event: ScheduledAccountEvent, timeline_event: TimelineEvent,
    ) -> EngineExecutionOutcome | None:
        event = timeline_event.event
        if account_event.event_at != event.timeline_instant:
            return self._failed(
                case, state, EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH.value,),
                (canonical_sha256(account_event), event.event_hash),
            )
        return self._apply_financial_dispatch(
            case, state, self._financial_dispatcher.dispatch_scheduled_event(account_event, self._financial_state_view(state)),
            expected_snapshot=None, expected_source_event_id=account_event.event_id,
            expected_source_evidence_hash=canonical_sha256(account_event), dispatch_at=account_event.event_at,
        )

    def _resolve_profile_fee_rules(
        self, case: ExecutionCase, state: _EngineState, source_event_id: str,
        query: ProfileFeeRuleQuery,
    ) -> FeeReservationRuleSet | FinalFeeRuleSet | EngineExecutionOutcome:
        code = EngineFailureCode.FEE_RESERVATION if query.basis_type is None else EngineFailureCode.FEE_ASSESSMENT_FAILURE
        dispatcher = self._financial_dispatcher
        if (type(case) is not ResolvedExecutionCaseV2 or not isinstance(dispatcher, ProfileFeeRuleResolver)
                or query.binding.dispatcher_spec_hash != case.financial_dispatch_plan.dispatcher_spec.spec_hash
                or query.binding.dispatcher_spec_hash != dispatcher.spec.spec_hash):
            return self._failed(case, state, code, ("profile_fee_binding_mismatch", source_event_id))
        try:
            outcome = dispatcher.resolve_fee_rules(query)
            if type(outcome) is not ProfileFeeRuleResolution or outcome.query != query:
                raise ValueError("profile fee resolution query mismatch")
            # Revalidate the immutable result at the dispatcher trust boundary.
            outcome = ProfileFeeRuleResolution(outcome.query, outcome.rule_set, outcome.evidence, outcome.failure_code)
        except Exception:
            return self._failed(case, state, code, ("profile_fee_resolution_invalid", source_event_id))
        if outcome.failure_code is not None:
            return self._failed(case, state, code, (outcome.failure_code, source_event_id), (canonical_sha256(outcome),))
        scope = query.basis_type.value if query.basis_type is not None else "reservation"
        role = f"fee_rules.{scope}.{source_event_id}"
        if role in state.live_dynamic_roles:
            return self._failed(case, state, code, ("duplicate_profile_fee_resolution", source_event_id))
        state.financial_artifacts.append(FinancialDispatchArtifact(role, source_event_id, query.evaluated_at,
            dispatcher.spec.dispatcher_key, dispatcher.spec.dispatcher_version, dispatcher.spec.config_hash,
            canonical_sha256(query), canonical_sha256(outcome), outcome))
        state.live_dynamic_roles.add(role)
        if outcome.rule_set is None:
            raise ValueError("successful profile fee resolution has no rule set")
        return outcome.rule_set

    def _materialize_cash_pretrade(
        self, case: ExecutionCase, state: _EngineState, order: Order,
        capability_set: OrderCapabilitySet, mapping: OrderTranslationMapping,
        translation_time: UtcInstant, authority: ResolvedCashPreTradeAuthority,
        source_event_id: str, fee_resolved_at: SimulationInstant,
    ) -> ResolvedPreTradePlan | EngineExecutionOutcome:
        # Reuse the authoritative kernel decisions. This preparation supplies the
        # exact commitment to the unchanged admission/execution gates below.
        capability = OrderCapabilityValidator().validate(order.intent, capability_set)
        if capability.approval is None:
            return self._failed(case, state, EngineFailureCode.CAPABILITY_REJECTED, (order.order_id.value,), (capability.decision_hash,))
        translation = OrderTranslator().translate(order, capability.approval, mapping, translation_time)
        if translation.executable_spec is None:
            return self._failed(case, state, EngineFailureCode.TRANSLATION_REJECTED, (order.order_id.value,), (translation.result_hash,))
        market = MarketRuleEvaluator().evaluate(
            OrderRuleEvaluationInput(translation.executable_spec, authority.evaluated_at, authority.notional_evidence),
            authority.order_rule_timeline,
        )
        if market.data_integrity_failure is not None:
            return self._failed(case, state, EngineFailureCode.MARKET_RULE_DATA_FAILURE,
                                (market.data_integrity_failure.code.value,), (canonical_sha256(market.data_integrity_failure),))
        if market.rejection is not None:
            return self._failed(case, state, EngineFailureCode.MARKET_RULE_REJECTED,
                                tuple(issue.subject_key for issue in market.rejection.issues), (canonical_sha256(market.rejection),))
        approval = market.approval
        if approval is None:
            raise ValueError("Market Rule returned no cash authority")
        rules = authority.fee_reservation_rule_set
        if isinstance(rules, ProfileFeeRuleBinding):
            resolved = self._resolve_profile_fee_rules(case, state, source_event_id,
                ProfileFeeRuleQuery(rules, order, fee_resolved_at))
            if isinstance(resolved, EngineExecutionOutcome):
                return resolved
            if type(resolved) is not FeeReservationRuleSet:
                raise ValueError("reservation resolver returned final fee rules")
            rules = resolved
        fees = FeeReservationEstimator().estimate(approval, rules, authority.evaluated_at)
        if fees.proposal is None:
            return self._failed(case, state, EngineFailureCode.FEE_RESERVATION, (order.order_id.value,), (canonical_sha256(fees),))
        intent = order.intent
        if intent.side not in {OrderSide.BUY, OrderSide.SELL} or intent.position_effect not in {PositionEffect.AUTO, PositionEffect.OPEN, PositionEffect.CLOSE}:
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_cash_intent",))
        notional = approval.calculated_notional
        if notional is None:
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_cash_notional",))
        commitment = ReservationCommitment(
            cash=(notional,) if intent.side is OrderSide.BUY else (),
            sellable_quantities=(intent.quantity,) if intent.side is OrderSide.SELL else (),
            fee_reserve=fees.proposal.commitment.fee_reserve,
            order_capacity_units=1, exposure_capacity=(notional,),
        )
        return authority.materialize(commitment, rules)

    def _live_bar_execution(
        self, case: ExecutionCase, state: _EngineState, plan: ResolvedBarPlanV2, timeline_event: TimelineEvent,
    ) -> EngineExecutionOutcome | None:
        event = timeline_event.event
        if event.capability != BAR_CLOSE_CAPABILITY or event.instrument_id != plan.instrument_id or event.event_time != plan.fill_event_at.instant:
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_bar_receipt", event.event_id))
        # Validate unused candidates too: unused identity is not permission to
        # substitute another bar's market evidence or a pre-close fill receipt.
        observation = BarCloseObservation.from_event(event)
        BarCloseCandidate(observation, None, None, plan.liquidity_evidence, plan.market_state)
        market_state = plan.market_state
        if (
            plan.liquidity_evidence.evaluated_at != event.available_time
            or market_state.source_event_id != event.event_id
            or market_state.evidence_hash != event.event_hash
            or market_state.revision_id != event.revision_id
            or market_state.observed_at != event.event_time
            or market_state.available_at != event.available_time
            or plan.fill_event_at <= event.timeline_instant
        ):
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_bar_market_evidence", event.event_id))
        active = tuple(stream for stream in state.order_streams.values()
                       if stream.order.intent.instrument_id == plan.instrument_id and stream.state is not None
                       and stream.state.status in {OrderStatus.ACCEPTED, OrderStatus.ACTIVE})
        if not active:
            state.live_unused_reasons[plan.fill_id.value] = "no_active_order"
            return None
        if len(active) != 1:
            return self._failed(case, state, EngineFailureCode.ORDER_PLAN_MISMATCH, ("live_bar_order_capacity", event.event_id))
        stream = active[0]
        admission = state.admissions[stream.order.order_id.value]
        pretrade = self._materialize_cash_pretrade(
            case, state, stream.order, admission.capability_set, admission.translation_mapping,
            admission.translation_time, plan.pretrade_authority, event.event_id, event.timeline_instant,
        )
        if isinstance(pretrade, EngineExecutionOutcome):
            return pretrade
        execution = ResolvedBarExecution(
            plan.event_id, stream.order.order_id, pretrade, plan.liquidity_evidence, plan.market_state,
            plan.slippage_model, plan.fill_id, plan.fill_event_id, plan.fill_event_at, plan.accounting_plan,
        )
        failure = self._bar_execution(case, state, execution, timeline_event)
        if failure is None:
            if any(fill.fill_id == plan.fill_id for fill in state.fills):
                state.live_clock = plan.accounting_plan.fee_plan.fee_recorded_at
            else:
                state.live_unused_reasons[plan.fill_id.value] = "no_eligible_fill"
        return failure

    def _close_live_identities(
        self, case: ResolvedExecutionCaseV2, state: _EngineState,
    ) -> EngineExecutionOutcome | None:
        manifest = case.identity_manifest
        if manifest is None:
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_identity_manifest",))
        observed: dict[str, tuple[DomainIdKind | None, str]] = {}
        for entry in state.journal.entries:
            observed[entry.journal_entry_id.value] = (DomainIdKind.JOURNAL, canonical_sha256(entry))
        for stream in state.order_streams.values():
            observed[stream.order.order_id.value] = (DomainIdKind.ORDER, canonical_sha256(stream.order))
            for record in stream.records:
                observed[record.event.event_id] = (None, canonical_sha256(record.event))
        for fill in state.fills:
            observed[fill.fill_id.value] = (DomainIdKind.FILL, canonical_sha256(fill))
        for obligation in state.settlement_book.obligations:
            identity = obligation.obligation.settlement_obligation_id
            observed[identity.value] = (DomainIdKind.SETTLEMENT, canonical_sha256(obligation))
        for event in state.settlement_book.events:
            observed[event.event_id] = (None, canonical_sha256(event))
        fees = {fee.fee_assessment_id: fee for fee in state.fee_assessments}
        for fee in state.fee_assessments:
            observed[fee.fee_assessment_id.value] = (DomainIdKind.FEE, canonical_sha256(fee))
        unused: dict[str, str] = {}
        for cycle in case.decision_cycles:
            slot = cycle.admission_slot
            if slot.order_id.value not in observed:
                reason = state.live_unused_reasons.get(slot.order_id.value)
                if reason is None:
                    return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("unclosed_order_slot", slot.order_id.value))
                for value in (slot.order_id.value, *(event.event_id for event in slot.event_plan), slot.expiration_event_id):
                    unused[value] = reason
            elif slot.expiration_event_id not in observed:
                unused[slot.expiration_event_id] = "order_not_expired"
        pending = {value.obligation.settlement_obligation_id: value for value in state.settlement_state.pending_obligations}
        for bar in case.bar_executions:
            fee = bar.accounting_plan.fee_plan
            settlement_slots = (bar.accounting_plan.settlement_slots
                                if isinstance(bar.accounting_plan, SettlementFillAccountingDispatchPlan) else ())
            fee_plans = (fee,)
            if isinstance(fee, FullFillOrderFeeAccountingPlan) and fee.fill_fee_plan is not None:
                fee_plans = (fee.fill_fee_plan, fee)
            if bar.fill_id.value not in observed:
                reason = state.live_unused_reasons.get(bar.fill_id.value)
                if reason is None:
                    return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("unclosed_fill_slot", bar.fill_id.value))
                ids = (bar.fill_id.value, bar.fill_event_id, bar.accounting_plan.fill_journal_entry_id.value,
                       *(value for plan in fee_plans for value in (plan.fee_assessment_id.value, plan.fee_journal_entry_id.value)))
                for value in (*ids, *(identity for slot in settlement_slots
                        for identity in (slot.obligation_id.value, slot.recorded_event_id, slot.applied_event_id))):
                    unused[value] = reason
            else:
                for slot in settlement_slots:
                    if slot.applied_event_id not in observed:
                        obligation = pending.get(slot.obligation_id)
                        if obligation is None or obligation.obligation.settlement_time < case.timeline.window.end_exclusive:
                            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("unclosed_due_settlement", slot.obligation_id.value))
                        unused[slot.applied_event_id] = "pending_beyond_window"
                for plan in fee_plans:
                    assessment = fees.get(plan.fee_assessment_id)
                    if assessment is not None and assessment.amount.units == 0:
                        unused[plan.fee_journal_entry_id.value] = "zero_fee"
        expected = {binding.value: binding.domain_kind for binding in manifest.bindings}
        if set(observed) & set(unused) or set(observed) | set(unused) != set(expected) or any(
            expected.get(value) != kind for value, (kind, _) in observed.items()
        ):
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_identity_usage_coverage",))
        dispositions = tuple(RuntimeIdentityDisposition(
            binding.binding_key, binding.value, "used" if binding.value in observed else "unused",
            None if binding.value in observed else unused[binding.value],
            observed[binding.value][1] if binding.value in observed else None,
        ) for binding in manifest.bindings)
        payload = RuntimeIdentityClosure(manifest.manifest_hash, dispositions)
        if any(artifact.role == "runtime.identity_closure" for artifact in state.financial_artifacts):
            return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("runtime_identity_role_impersonation",))
        state.financial_artifacts.append(FinancialDispatchArtifact(
            "runtime.identity_closure", "engine-finalize", case.snapshot_plan.projection_at,
            "generic.live-case.identity-closure.v1", 1, case.semantic_spec_hash,
            canonical_sha256({"manifest": manifest, "dispositions": dispositions}), canonical_sha256(payload), payload,
        ))
        return None

    def _initial_state(self, case: ExecutionCase) -> _EngineState:
        financial = case.financial_state
        ledger = GenericLedger(financial.ledger_schema)
        ledger_state = ledger.project(financial.journal)
        has_position_lot_changes = any(
            entry.position_lot_changes for entry in financial.journal.entries
        )
        order_streams = {
            value.order.order_id.value: value for value in financial.order_streams
        }
        schedules = {
            value.order_id.value: value for value in financial.reservation_schedules
        }
        reservation_book = ResourceReservationBook(financial.initial_snapshot.account_id)
        reservation_state = reservation_book.project(
            tuple(order_streams.values()), tuple(schedules.values())
        )
        settlement_state = financial.settlement_book.project()
        availability = AvailabilityProjection().project(
            ledger_state,
            settlement_state,
            reservation_state,
            financial.settlement_rules,
        )
        lot_books = (
            _lot_books_from_ledger(ledger_state)
            if has_position_lot_changes
            else {value.position_key: value.lots for value in financial.lot_books}
        )
        return _EngineState(
            journal=financial.journal,
            ledger=ledger,
            ledger_state=ledger_state,
            snapshot=financial.initial_snapshot,
            lot_books=lot_books,
            settlement_book=financial.settlement_book,
            settlement_state=settlement_state,
            reservation_book=reservation_book,
            reservation_state=reservation_state,
            availability=availability,
            order_streams=order_streams,
            reservation_schedules=schedules,
            admissions={
                value.order.order_id.value: value
                for value in financial.order_admissions
            },
        )

    @staticmethod
    def _policy_v2_cash_position_key(
        case: ExecutionCase, source_event_id: str
    ) -> PositionBalanceKey | None:
        for execution in case.bar_executions:
            plan = execution.accounting_plan
            payload = plan.position_payload
            if (
                plan.source_event_id == source_event_id
                and type(payload) is CashFillAccountingPlan
                and payload.cost_basis_policy.policy_version >= 2
            ):
                return payload.position_key
        return None

    @staticmethod
    def _financial_state_view(state: _EngineState) -> FinancialStateView:
        lot_books = tuple(
            sorted(state.lot_books.items(), key=lambda value: canonical_bytes(value[0]))
        )
        return FinancialStateView(
            state.journal,
            state.ledger_state,
            state.reservation_state,
            lot_books,
            tuple(state.financial_artifacts),
            state.settlement_book,
        )

    @staticmethod
    def _stage_settlement_book(
        book: SettlementBook,
        result: SettlementFinancialDispatchResult,
        *,
        expected_source_event_id: str | None,
        expected_source_evidence_hash: str | None,
        dispatch_at: SimulationInstant | None,
        source_fill_record: OrderEventRecord | None,
    ) -> SettlementBook:
        if dispatch_at is None or result.source_event_id != expected_source_event_id:
            raise ValueError("settlement requires the actual fill or scheduled dispatch context")
        if expected_source_evidence_hash is None or any(
            event.source_evidence_hash != expected_source_evidence_hash
            for event in result.settlement_events
        ):
            raise ValueError("settlement evidence does not match the actual dispatch receipt")
        if result.prior_settlement_book_hash != book.book_hash:
            raise ValueError("stale settlement book")
        if any(event.occurred_at > dispatch_at for event in result.settlement_events):
            raise ValueError("future settlement event")
        if any(entry.recorded_at > dispatch_at for entry in result.journal_entries):
            raise ValueError("future settlement accounting")
        if any(artifact.occurred_at > dispatch_at for artifact in result.artifacts):
            raise ValueError("future settlement artifact")
        if result.snapshot is not None and result.snapshot.timestamp > dispatch_at.instant:
            raise ValueError("future settlement snapshot")
        if source_fill_record is None:
            if result.settlement_obligations or any(
                event.event_type is not SettlementEventType.SETTLEMENT_APPLIED
                or event.occurred_at != dispatch_at
                for event in result.settlement_events
            ):
                raise ValueError("scheduled settlement may only apply at the actual receipt")
        else:
            fill = source_fill_record.fill
            if fill is None or any(
                value.obligation.source_fill_id != fill.fill_id
                or value.obligation.trade_time != fill.execution_time
                for value in result.settlement_obligations
            ):
                raise ValueError("settlement obligation does not match the actual fill")
            obligation_ids = {
                value.obligation.settlement_obligation_id
                for value in result.settlement_obligations
            }
            if any(
                event.settlement_obligation_id not in obligation_ids
                or event.occurred_at < source_fill_record.event.occurred_at
                for event in result.settlement_events
            ):
                raise ValueError("settlement event does not follow the actual recorded fill")
        staged = book.append(
            obligations=result.settlement_obligations, events=result.settlement_events
        )
        if staged.book_hash != result.settlement_book_hash:
            raise ValueError("settlement book hash mismatch")
        return staged

    @staticmethod
    def _validate_live_fill_settlement(
        plan: SettlementFillAccountingDispatchPlan, result: FinancialDispatchResult,
    ) -> bool:
        if not isinstance(result, SettlementFinancialDispatchResult) or len(result.journal_entries) != 1:
            return False
        changes = {value.key: value.value for value in result.journal_entries[0].balance_changes}
        obligations = {value.obligation.settlement_obligation_id: value for value in result.settlement_obligations}
        if (len(result.settlement_obligations) != len(plan.settlement_slots)
                or set(obligations) != {slot.obligation_id for slot in plan.settlement_slots}
                or set(changes) != {slot.balance_key for slot in plan.settlement_slots}):
            return False
        expected = set()
        for slot in plan.settlement_slots:
            obligation = obligations[slot.obligation_id]
            if obligation.balance_key != slot.balance_key or obligation.value != changes[slot.balance_key]:
                return False
            expected.add((slot.recorded_event_id, slot.obligation_id, SettlementEventType.OBLIGATION_RECORDED,
                          plan.settlement_recorded_at, obligation.obligation.source_fill_id.value))
            if obligation.obligation.settlement_time <= plan.fill_recorded_at.instant:
                expected.add((slot.applied_event_id, slot.obligation_id, SettlementEventType.SETTLEMENT_APPLIED,
                              plan.fill_recorded_at, slot.recorded_event_id))
        actual = {(value.event_id, value.settlement_obligation_id, value.event_type, value.occurred_at, value.causation_id)
                  for value in result.settlement_events}
        return actual == expected and len(result.settlement_events) == len(expected)

    def _apply_financial_dispatch(
        self,
        case: ExecutionCase,
        state: _EngineState,
        outcome: FinancialDispatchOutcome,
        *,
        expected_snapshot: bool | None,
        expected_source_event_id: str | None = None,
        expected_source_evidence_hash: str | None = None,
        dispatch_at: SimulationInstant | None = None,
        source_fill_record: OrderEventRecord | None = None,
    ) -> EngineExecutionOutcome | None:
        if (
            not isinstance(outcome, FinancialDispatchOutcome)
            or outcome.dispatcher_spec != self._financial_dispatcher.spec
        ):
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (FinancialDispatchFailureCode.DISPATCHER_SPEC_MISMATCH.value,),
            )
        if outcome.failure is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (outcome.failure.code.value,) + outcome.failure.subject_ids,
                (outcome.failure.failure_hash,),
            )
        result = outcome.result
        if not isinstance(result, FinancialDispatchResult) or (
            expected_snapshot is not None
            and expected_snapshot != (result.snapshot is not None)
        ):
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value,),
                (canonical_sha256(outcome),),
            )
        if isinstance(case, ResolvedExecutionCaseV2) and source_fill_record is not None:
            plans = tuple(bar.accounting_plan for bar in case.bar_executions if bar.event_id == expected_source_event_id)
            if (len(plans) != 1 or (isinstance(plans[0], SettlementFillAccountingDispatchPlan)
                    and not self._validate_live_fill_settlement(plans[0], result))):
                return self._failed(case, state, EngineFailureCode.FINANCIAL_DISPATCH_FAILURE, ("live_fill_settlement_coverage",))
        if expected_snapshot and result.journal_entries:
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE.value,),
                (canonical_sha256(result),),
            )
        if isinstance(case, ResolvedExecutionCaseV2) and (
            dispatch_at is None
            or (expected_source_event_id is not None and result.source_event_id != expected_source_event_id)
            or any(entry.recorded_at != dispatch_at for entry in result.journal_entries)
            or any(artifact.occurred_at != dispatch_at or artifact.source_event_id != result.source_event_id for artifact in result.artifacts)
            or (result.snapshot is not None and result.snapshot.timestamp_instant != dispatch_at)
        ):
            return self._failed(case, state, EngineFailureCode.FINANCIAL_DISPATCH_FAILURE, ("live_dispatch_receipt_mismatch",))
        staged_journal = state.journal
        if result.journal_entries:
            try:
                staged_journal = state.journal.append_many(result.journal_entries)
            except JournalError:
                return self._failed(
                    case,
                    state,
                    EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                    (FinancialDispatchFailureCode.JOURNAL_APPEND_FAILURE.value,),
                    (canonical_sha256(result),),
                )
        staged_ledger = state.ledger_state
        if result.journal_entries:
            try:
                staged_ledger = state.ledger.project(staged_journal)
            except LedgerError:
                return self._failed(
                    case,
                    state,
                    EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                    (
                        FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value,
                        "generic_ledger_projection",
                    ),
                    (canonical_sha256(result),),
                )
        if isinstance(case, ResolvedExecutionCaseV2) and result.snapshot is not None and result.snapshot.journal_state_hash != staged_ledger.state_hash:
            return self._failed(case, state, EngineFailureCode.FINANCIAL_DISPATCH_FAILURE, ("live_dispatch_receipt_mismatch",))
        staged_book = state.settlement_book
        artifacts = result.artifacts
        if isinstance(result, SettlementFinancialDispatchResult):
            try:
                staged_book = self._stage_settlement_book(
                    staged_book, result,
                    expected_source_event_id=expected_source_event_id,
                    expected_source_evidence_hash=expected_source_evidence_hash,
                    dispatch_at=dispatch_at,
                    source_fill_record=source_fill_record,
                )
            except (SettlementBookError, ValueError):
                return self._failed(
                    case, state, EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                    (FinancialDispatchFailureCode.SETTLEMENT_TRANSITION_FAILURE.value,),
                    (canonical_sha256(result),),
                )
            assert dispatch_at is not None
            artifacts += (FinancialDispatchArtifact(
                f"settlement.{result.source_event_id}",
                result.source_event_id,
                dispatch_at,
                result.dispatcher_spec.dispatcher_key,
                result.dispatcher_spec.dispatcher_version,
                result.dispatcher_spec.config_hash,
                canonical_sha256({
                    "dispatch_input_hash": outcome.input_hash,
                    "prior_settlement_book_hash": state.settlement_book.book_hash,
                    "source_event_id": expected_source_event_id,
                    "source_evidence_hash": expected_source_evidence_hash,
                    "dispatch_at": dispatch_at,
                    "source_fill_record": source_fill_record,
                }),
                canonical_sha256(result),
                result,
            ),)
        v2_position_key = self._policy_v2_cash_position_key(
            case, result.source_event_id
        )
        replay_authority = v2_position_key is not None or any(
            entry.position_lot_changes for entry in staged_journal.entries
        )
        projected_lots = _lot_books_from_ledger(staged_ledger)
        v2_position_keys = {
            payload.position_key
            for execution in case.bar_executions
            if type(payload := execution.accounting_plan.position_payload)
            is CashFillAccountingPlan
            and payload.cost_basis_policy.policy_version >= 2
        }
        if any(
            staged_ledger.position_quantity(key).units and not projected_lots.get(key)
            for key in v2_position_keys
        ):
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (
                    FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value,
                    "position_lot_books",
                ),
                (canonical_sha256(result),),
            )
        if replay_authority and _lot_state(projected_lots) != result.position_lot_books:
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (
                    FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value,
                    "position_lot_books",
                ),
                (canonical_sha256(result),),
            )
        existing_roles = {value.role for value in state.financial_artifacts}
        roles = tuple(value.role for value in artifacts)
        if existing_roles.intersection(roles) or len(set(roles)) != len(roles):
            return self._failed(
                case,
                state,
                EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                (FinancialDispatchFailureCode.ARTIFACT_COVERAGE_MISMATCH.value,),
                (canonical_sha256(artifacts),),
            )
        staged_resources = None
        if result.journal_entries or isinstance(result, SettlementFinancialDispatchResult):
            try:
                staged_resources = self._project_resources(
                    case, state, staged_ledger, staged_book
                )
            except (AvailabilityProjectionError, ResourceReservationError, SettlementBookError):
                return self._failed(
                    case, state, EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
                    (FinancialDispatchFailureCode.RESOURCE_PROJECTION_FAILURE.value,),
                    (canonical_sha256(result),),
                )
        state.journal = staged_journal
        state.ledger_state = staged_ledger
        state.settlement_book = staged_book
        if staged_resources is not None:
            state.reservation_state, state.settlement_state, state.availability = staged_resources

        state.lot_books = (
            projected_lots
            if replay_authority
            else dict(result.position_lot_books)
        )
        state.financial_artifacts.extend(artifacts)
        if result.snapshot is not None:
            state.snapshot = result.snapshot
        for artifact in artifacts:
            self._trace_add(
                state,
                EngineStage.FINANCIAL_EVENT,
                artifact.occurred_at,
                artifact.source_event_id,
                artifact.artifact_hash,
            )
        return None

    def _decision_cycle(
        self,
        case: ExecutionCase,
        state: _EngineState,
        cycle: ResolvedDecisionCycle | ResolvedDecisionCycleV2,
        events: tuple[TimelineEvent, ...],
    ) -> EngineExecutionOutcome | None:
        injection_outcome = PrecomputedTargetStreamAdapter().inject(
            stream=case.target_stream,
            timeline_events=events,
            schedule=cycle.schedule,
            prior_state=state.latest_sleeve_state,
        )
        trace_instant = max(value.event.timeline_instant for value in events)
        if injection_outcome.decode_failure is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.TARGET_INPUT_DECODE,
                tuple(value.code.value for value in injection_outcome.decode_failure.issues),
                (canonical_sha256(injection_outcome.decode_failure),),
            )
        if injection_outcome.validation_failures:
            return self._failed(
                case,
                state,
                EngineFailureCode.TARGET_VALIDATION,
                tuple(value.event_id for value in injection_outcome.validation_failures),
                tuple(
                    canonical_sha256(value)
                    for value in injection_outcome.validation_failures
                ),
            )
        if injection_outcome.batch_failure is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.DECISION_BATCH,
                tuple(value.subject_key for value in injection_outcome.batch_failure.issues),
                (injection_outcome.batch_failure.failure_hash,),
            )
        if injection_outcome.suppression is not None:
            self._trace_add(
                state,
                EngineStage.TARGET_WARMUP_SUPPRESSED,
                trace_instant,
                cycle.schedule.schedule_hash,
                canonical_sha256(injection_outcome.suppression),
            )
            return None
        injection = injection_outcome.injection
        if injection is None:
            raise ValueError("Target adapter returned invalid success branch")
        state.latest_sleeve_state = injection.state
        state.decision_batches.append(injection.batch)
        self._trace_add(
            state,
            EngineStage.DECISION_BATCH,
            trace_instant,
            injection.batch.decision_batch_id,
            canonical_sha256(injection.batch),
        )

        if isinstance(cycle, ResolvedDecisionCycleV2):
            event_id = cycle.schedule.entries[0].event_id
            snapshot_event = ScheduledAccountEvent(
                event_id, trace_instant, cycle.snapshot_plan.operation_key,
                (case.financial_dispatch_plan.dispatcher_spec.snapshot_projection_key,), (),
                cycle.snapshot_plan, cycle.snapshot_plan, (f"snapshot.{event_id}",),
            )
            failure = self._apply_financial_dispatch(
                case, state, self._financial_dispatcher.dispatch_scheduled_event(snapshot_event, self._financial_state_view(state)),
                expected_snapshot=True, expected_source_event_id=event_id,
                expected_source_evidence_hash=canonical_sha256(snapshot_event), dispatch_at=trace_instant,
            )
            if failure is not None:
                return failure
            context = cycle.schedule.entries[0].expectation
            allocations = (StrategyAllocation(
                context.strategy_id, context.sleeve_id, state.snapshot.timestamp,
                state.snapshot.reporting_currency, state.snapshot.equity, cycle.allocation_policy,
                canonical_sha256(state.snapshot), valuation_instant=trace_instant,
            ),)
            instrument = cycle.quantity_lattice.instrument_id
            position_key = PositionBalanceKey(state.snapshot.account_id, instrument.venue, instrument)
            marks = tuple(mark for mark in cycle.snapshot_plan.resolved_marks if mark.instrument_id == instrument)
            if len(marks) != 1:
                return self._failed(case, state, EngineFailureCode.POSITION_SIZING, ("live_mark_coverage",))
            sizing_inputs = (InstrumentSizingInput(instrument, marks[0], state.ledger_state.position_quantity(position_key), cycle.quantity_lattice),)
        else:
            allocations = cycle.allocations
            sizing_inputs = cycle.sizing_inputs
        allocation_outcome = PortfolioAllocator().allocate(
            sleeve_state=injection.state,
            portfolio_snapshot=state.snapshot,
            allocations=allocations,
            target_notional_scale=cycle.target_notional_scale,
        )
        if allocation_outcome.allocation is None:
            failure = cast(Any, allocation_outcome.failure)
            return self._failed(
                case,
                state,
                EngineFailureCode.ALLOCATION,
                tuple(value.subject_key for value in failure.decisions),
                (failure.failure_hash,),
            )
        allocation = allocation_outcome.allocation
        state.allocations.append(allocation)
        self._trace_add(
            state,
            EngineStage.CAPITAL_ALLOCATION,
            trace_instant,
            allocation.allocation_id,
            allocation.allocation_hash,
        )

        risk_outcome = PortfolioRiskEvaluator().evaluate(
            allocation=allocation,
            policy=cycle.risk_policy,
        )
        if risk_outcome.approved_target is None:
            failure = cast(Any, risk_outcome.failure)
            return self._failed(
                case,
                state,
                EngineFailureCode.PORTFOLIO_RISK,
                tuple(value.subject_key for value in failure.issues),
                (failure.failure_hash,),
            )
        approved = risk_outcome.approved_target
        state.approved_targets.append(approved)
        self._trace_add(
            state,
            EngineStage.PORTFOLIO_RISK,
            trace_instant,
            approved.approved_target_id,
            approved.approved_target_hash,
        )

        sizing_outcome = PositionSizer().materialize(
            approved_target=approved,
            source_decision_batch_id=injection.batch.decision_batch_id,
            policy=cycle.sizing_policy,
            inputs=sizing_inputs,
        )
        if sizing_outcome.normalized_target is None:
            failure = cast(Any, sizing_outcome.failure)
            return self._failed(
                case,
                state,
                EngineFailureCode.POSITION_SIZING,
                failure.subject_keys,
                (failure.failure_hash,),
            )
        normalized = sizing_outcome.normalized_target
        state.normalized_targets.append(normalized)
        self._trace_add(
            state,
            EngineStage.POSITION_SIZING,
            trace_instant,
            normalized.normalized_target_id,
            normalized.normalized_target_hash,
        )

        validity = (TargetValidity(normalized.normalized_target_id, normalized.normalized_target_hash,
                                   normalized.materialized_at, cycle.target_valid_until)
                    if isinstance(cycle, ResolvedDecisionCycleV2) else cycle.target_validity)
        working = tuple(state.order_streams.values())
        if isinstance(cycle, ResolvedDecisionCycleV2):
            working = tuple(stream for stream in working if stream.state is not None and stream.state.status in {OrderStatus.ACCEPTED, OrderStatus.ACTIVE})
        planning_outcome = RebalanceCoordinator().coordinate(
            target=normalized,
            target_validity=validity,
            portfolio_snapshot=state.snapshot,
            working_orders=working,
            reservations=state.reservation_state,
            availability=state.availability,
            policy=cycle.rebalance_policy,
            as_of=cycle.planning_at,
        )
        if planning_outcome.decision is None:
            failure = cast(Any, planning_outcome.failure)
            return self._failed(
                case,
                state,
                EngineFailureCode.REBALANCE,
                failure.subject_keys,
                (failure.failure_hash,),
            )
        plan = planning_outcome.decision.plan
        state.order_plans.append(plan)
        self._trace_add(
            state,
            EngineStage.ORDER_PLAN,
            trace_instant,
            plan.plan_id,
            plan.plan_hash,
        )
        if plan.cancel_intents:
            return self._failed(
                case,
                state,
                EngineFailureCode.ORDER_PLAN_MISMATCH,
                tuple(value.order_id.value for value in plan.cancel_intents),
                tuple(value.cancel_intent_hash for value in plan.cancel_intents),
            )
        if isinstance(cycle, ResolvedDecisionCycleV2):
            slot = cycle.admission_slot
            if len(plan.planned_orders) > 1:
                return self._failed(case, state, EngineFailureCode.ORDER_PLAN_MISMATCH, ("live_order_slot_capacity",))
            if not plan.planned_orders:
                state.live_unused_reasons[slot.order_id.value] = "no_order_planned"
                return None
            order = Order(slot.order_id, state.snapshot.account_id, plan.planned_orders[0].intent, slot.event_plan[0].occurred_at)
            pretrade = self._materialize_cash_pretrade(case, state, order, slot.capability_set,
                slot.translation_mapping, slot.translation_time, slot.pretrade_authority,
                cycle.schedule.entries[0].event_id, slot.event_plan[4].occurred_at)
            if isinstance(pretrade, EngineExecutionOutcome):
                return pretrade
            admission = ResolvedOrderAdmission(order, slot.capability_set, slot.translation_mapping, slot.translation_time, pretrade, slot.event_plan)
            failure = self._admit_order(case, state, admission, deferral_event_id=cycle.schedule.entries[0].event_id)
            if failure is not None:
                return failure
            if slot.order_id.value not in state.live_unused_reasons:
                state.live_clock = slot.event_plan[-1].occurred_at
            self._refresh_resources(case, state)
            return None
        admission_by_intent = {
            canonical_sha256(value.order.intent): value for value in cycle.admissions
        }
        planned_hashes = {canonical_sha256(value.intent) for value in plan.planned_orders}
        if planned_hashes != set(admission_by_intent):
            return self._failed(
                case,
                state,
                EngineFailureCode.ORDER_PLAN_MISMATCH,
                tuple(sorted(planned_hashes ^ set(admission_by_intent))),
            )
        for planned in plan.planned_orders:
            admission = admission_by_intent[canonical_sha256(planned.intent)]
            failure = self._admit_order(case, state, admission)
            if failure is not None:
                return failure
        self._refresh_resources(case, state)
        return None

    def _admit_order(
        self,
        case: ExecutionCase,
        state: _EngineState,
        admission: ResolvedOrderAdmission,
        *, deferral_event_id: str | None = None,
    ) -> EngineExecutionOutcome | None:
        order = admission.order
        if order.order_id.value in state.order_streams:
            return self._failed(
                case,
                state,
                EngineFailureCode.ORDER_PLAN_MISMATCH,
                (order.order_id.value,),
            )
        capability = OrderCapabilityValidator().validate(
            order.intent, admission.capability_set
        )
        if capability.approval is None:
            rejection = cast(Any, capability.rejection)
            return self._failed(
                case,
                state,
                EngineFailureCode.CAPABILITY_REJECTED,
                tuple(value.capability for value in rejection.unsupported_capabilities),
                (canonical_sha256(rejection),),
            )
        self._trace_add(
            state,
            EngineStage.ORDER_CAPABILITY,
            admission.event_plan[1].occurred_at,
            order.order_id.value,
            capability.decision_hash,
        )
        translation = OrderTranslator().translate(
            order,
            capability.approval,
            admission.translation_mapping,
            admission.translation_time,
        )
        if translation.executable_spec is None:
            return self._failed(
                case,
                state,
                EngineFailureCode.TRANSLATION_REJECTED,
                (translation.report.report_id,),
                (translation.result_hash,),
            )
        self._trace_add(
            state,
            EngineStage.ORDER_TRANSLATION,
            admission.event_plan[2].occurred_at,
            order.order_id.value,
            translation.result_hash,
        )
        gate = self._pretrade_gate(
            case,
            state,
            order,
            translation.executable_spec,
            admission.pretrade_plan,
            exclude_order_id=None,
            defer_pending_at=admission.event_plan[5].occurred_at if deferral_event_id is not None else None,
        )
        if isinstance(gate, EngineExecutionOutcome):
            return gate
        if isinstance(gate, PendingPositionSellDeferral):
            assert deferral_event_id is not None
            role = f"deferral.{deferral_event_id}"
            artifact = FinancialDispatchArtifact(role, deferral_event_id, gate.deferred_at,
                "generic.cash.pending-position-deferral.v1", 1, case.semantic_spec_hash,
                canonical_sha256({"admission": admission, "settlement_book_hash": state.settlement_book.book_hash}),
                canonical_sha256(gate), gate)
            if role in {value.role for value in state.financial_artifacts}:
                return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_deferral_role_impersonation",))
            state.financial_artifacts.append(artifact)
            state.live_dynamic_roles.add(role)
            state.live_unused_reasons[order.order_id.value] = "pending_position_settlement"
            state.live_clock = gate.deferred_at
            self._trace_add(state, EngineStage.PRETRADE_RISK, gate.deferred_at, order.order_id.value, artifact.artifact_hash)
            return None
        market_approval, fee_outcome, pretrade_approval = gate
        self._trace_add(
            state,
            EngineStage.MARKET_RULE,
            admission.event_plan[3].occurred_at,
            order.order_id.value,
            canonical_sha256(market_approval),
        )
        self._trace_add(
            state,
            EngineStage.FEE_RESERVATION,
            admission.event_plan[4].occurred_at,
            order.order_id.value,
            fee_outcome.outcome_hash,
        )
        self._trace_add(
            state,
            EngineStage.PRETRADE_RISK,
            admission.event_plan[5].occurred_at,
            order.order_id.value,
            pretrade_approval.decision_hash,
        )
        evidence_ids = (
            canonical_sha256(order.intent),
            capability.approval.decision_id,
            translation.result_hash,
            market_approval.decision_id,
            cast(Any, fee_outcome.estimate).estimate_id,
            pretrade_approval.decision_id,
            cast(str, admission.event_plan[6].external_evidence_id),
            cast(str, admission.event_plan[7].external_evidence_id),
        )
        records: list[OrderEventRecord] = []
        cause = order.intent.parent_id
        for planned, evidence_id in zip(
            admission.event_plan, evidence_ids, strict=True
        ):
            event = OrderEvent(
                event_id=planned.event_id,
                order_id=order.order_id,
                causation_id=cause,
                event_type=planned.event_type,
                occurred_at=planned.occurred_at,
                fill_id=None,
                evidence_id=evidence_id,
            )
            records.append(OrderEventRecord(event))
            cause = event.event_id
        stream = OrderEventStream.from_records(order, tuple(records))
        if stream.state is None or stream.state.status.value != "accepted":
            raise ValueError("admission event plan did not produce Accepted Order")
        accepted_event = admission.event_plan[-1]
        schedule = OrderReservationSchedule(
            order_id=order.order_id,
            source_proposal_hash=cast(Any, fee_outcome.proposal).proposal_hash,
            updates=(
                OrderReservationUpdate(
                    order_id=order.order_id,
                    event_id=accepted_event.event_id,
                    event_type=accepted_event.event_type,
                    remaining_quantity=order.intent.quantity,
                    commitment=admission.pretrade_plan.resource_commitment,
                    source_evidence_hash=pretrade_approval.decision_hash,
                ),
            ),
        )
        state.order_streams[order.order_id.value] = stream
        state.reservation_schedules[order.order_id.value] = schedule
        state.admissions[order.order_id.value] = admission
        self._trace_add(
            state,
            EngineStage.ORDER_ACCEPTED,
            admission.event_plan[-1].occurred_at,
            order.order_id.value,
            stream.stream_hash,
        )
        return None

    def _pretrade_gate(
        self,
        case: ExecutionCase,
        state: _EngineState,
        order: Order,
        executable_spec: ExecutableOrderSpec,
        plan: ResolvedPreTradePlan,
        *,
        exclude_order_id: str | None,
        defer_pending_at: SimulationInstant | None = None,
    ) -> tuple[Any, Any, Any] | PendingPositionSellDeferral | EngineExecutionOutcome:
        market = MarketRuleEvaluator().evaluate(
            OrderRuleEvaluationInput(
                executable_order_spec=executable_spec,
                evaluated_at=plan.market_rule_evaluated_at,
                notional_evidence=plan.notional_evidence,
            ),
            plan.order_rule_timeline,
        )
        if market.data_integrity_failure is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.MARKET_RULE_DATA_FAILURE,
                (market.data_integrity_failure.code.value,),
                (canonical_sha256(market.data_integrity_failure),),
            )
        if market.rejection is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.MARKET_RULE_REJECTED,
                tuple(value.subject_key for value in market.rejection.issues),
                (canonical_sha256(market.rejection),),
            )
        approval = market.approval
        if approval is None:
            raise ValueError("Market Rule returned invalid success branch")
        fees = FeeReservationEstimator().estimate(
            approval,
            plan.fee_reservation_rule_set,
            plan.fee_estimated_at,
        )
        if fees.proposal is None or fees.estimate is None:
            failure = cast(Any, fees.failure)
            return self._failed(
                case,
                state,
                EngineFailureCode.FEE_RESERVATION,
                tuple(code.value for code in failure.codes),
                (failure.failure_hash,),
            )
        if plan.resource_commitment.fee_reserve != fees.proposal.commitment.fee_reserve:
            return self._failed(
                case,
                state,
                EngineFailureCode.CASE_EVIDENCE_MISMATCH,
                ("fee_reserve", order.order_id.value),
                (canonical_sha256(plan.resource_commitment), fees.proposal.proposal_hash),
            )
        reservations = self._reservation_state_excluding(state, exclude_order_id)
        availability = AvailabilityProjection().project(
            state.ledger_state,
            state.settlement_state,
            reservations,
            case.financial_state.settlement_rules,
        )
        requirement = PreTradeResourceRequirement.create(
            requirement_source_key=plan.requirement_source_key,
            requirement_source_version=plan.requirement_source_version,
            requirement_source_hash=plan.requirement_source_hash,
            market_rule_approval=approval,
            fee_reservation_proposal=fees.proposal,
            commitment=plan.resource_commitment,
        )
        risk_input = PreTradeRiskEvaluationInput(
            market_rule_approval=approval,
            fee_reservation_proposal=fees.proposal,
            resource_requirement=requirement,
            reservation_state=reservations,
            availability_state=availability,
            account_risk_policy=plan.account_risk_policy,
            evaluated_at=plan.pretrade_evaluated_at,
        )
        risk = PreTradeRiskEvaluator().evaluate(risk_input)
        if risk.contract_failure is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.PRETRADE_CONTRACT_FAILURE,
                tuple(value.subject_key for value in risk.contract_failure.issues),
                (risk.contract_failure.failure_hash,),
            )
        if risk.rejection is not None:
            if isinstance(case, ResolvedExecutionCaseV2) and defer_pending_at is not None and exclude_order_id is None:
                pending = tuple(value for value in state.settlement_state.pending_obligations
                    if isinstance(value.balance_key, PositionBalanceKey) and value.balance_key.instrument_id == order.intent.instrument_id)
                if pending:
                    try:
                        return PendingPositionSellDeferral(risk.rejection, pending, state.settlement_book.book_hash, defer_pending_at)
                    except ValueError:
                        pass  # Other permissions/resources, reservations, or partial availability remain failures.
            return self._failed(
                case,
                state,
                EngineFailureCode.PRETRADE_REJECTED,
                tuple(value.subject_key for value in risk.rejection.checks if not value.approved),
                (risk.rejection.decision_hash,),
            )
        if risk.approval is None:
            raise ValueError("PreTradeRisk returned invalid success branch")
        return approval, fees, risk.approval

    def _close_execution_window(
        self, case: ExecutionCase, state: _EngineState
    ) -> EngineExecutionOutcome | None:
        model = cast(NextEligibleBarCloseModel, case.execution_model)
        # Order events must remain inside the half-open trading window.
        occurred_at = SimulationInstant(
            UtcInstant(case.timeline.window.end_exclusive.epoch_nanoseconds - 1),
            _FINALIZE_PHASE,
            SourceSequence(0),
        )
        for order_id, stream in tuple(state.order_streams.items()):
            if stream.state is None or stream.state.status not in {OrderStatus.ACCEPTED, OrderStatus.ACTIVE}:
                continue
            if isinstance(case, ResolvedExecutionCaseV2) and state.live_clock is not None and occurred_at <= state.live_clock:
                return self._failed(case, state, EngineFailureCode.CASE_EVIDENCE_MISMATCH, ("live_close_window_overlap",))
            outcome = model.simulate_execution(NextBarCloseRequest(stream, None, True))
            if outcome.failure is not None:
                return self._failed(case, state, EngineFailureCode.EXECUTION_FAILURE, (outcome.failure.code.value,), (canonical_sha256(outcome.failure),))
            decision = cast(NextBarCloseDecision, outcome.result)
            self._trace_add(state, EngineStage.EXECUTION_DECISION, occurred_at, order_id, canonical_sha256(decision))
            if decision.action is not NoEligibleBarAction.EXPIRE:
                continue
            expiration = OrderEvent(
                event_id=(next(cycle.admission_slot.expiration_event_id for cycle in case.decision_cycles if cycle.admission_slot.order_id.value == order_id)
                          if isinstance(case, ResolvedExecutionCaseV2) else f"execution-window-expired:{order_id}"),
                order_id=stream.order.order_id,
                causation_id=stream.records[-1].event.event_id,
                event_type=OrderEventType.ORDER_EXPIRED,
                occurred_at=occurred_at,
                fill_id=None,
                evidence_id=decision.decision_id,
            )
            state.order_streams[order_id] = stream.append(OrderEventRecord(expiration))
            self._refresh_resources(case, state)
        return None

    def _bar_execution(
        self,
        case: ExecutionCase,
        state: _EngineState,
        plan: ResolvedBarExecution,
        timeline_event: TimelineEvent,
    ) -> EngineExecutionOutcome | None:
        stream = state.order_streams.get(plan.order_id.value)
        admission = state.admissions.get(plan.order_id.value)
        if stream is None or admission is None:
            return self._failed(
                case,
                state,
                EngineFailureCode.CASE_EVIDENCE_MISMATCH,
                (plan.order_id.value, plan.event_id),
            )
        capability = OrderCapabilityValidator().validate(
            stream.order.intent, admission.capability_set
        )
        if capability.approval is None:
            return self._failed(
                case,
                state,
                EngineFailureCode.CAPABILITY_REJECTED,
                (plan.order_id.value,),
            )
        translation = OrderTranslator().translate(
            stream.order,
            capability.approval,
            admission.translation_mapping,
            admission.translation_time,
        )
        if translation.executable_spec is None:
            return self._failed(
                case,
                state,
                EngineFailureCode.TRANSLATION_REJECTED,
                (plan.order_id.value,),
                (translation.result_hash,),
            )
        gate = self._pretrade_gate(
            case,
            state,
            stream.order,
            translation.executable_spec,
            plan.pretrade_plan,
            exclude_order_id=plan.order_id.value,
        )
        if isinstance(gate, EngineExecutionOutcome):
            return gate
        if isinstance(gate, PendingPositionSellDeferral):
            raise ValueError("execution gates cannot defer already admitted orders")
        market_approval, _, pretrade_approval = gate
        event = timeline_event.event
        if isinstance(case.execution_model, NextEligibleBarOpenModel):
            if event.capability != BAR_OPEN_CAPABILITY:
                return self._failed(case, state, EngineFailureCode.EXECUTION_FAILURE, (event.event_id, event.capability.identity), (event.event_hash,))
            candidate = BarOpenCandidate(BarOpenObservation.from_event(event), market_approval, pretrade_approval, plan.liquidity_evidence, plan.market_state)
            execution_outcome = case.execution_model.simulate_execution(NextBarOpenRequest(stream, candidate, False))
        else:
            if event.capability != BAR_CLOSE_CAPABILITY:
                return self._failed(case, state, EngineFailureCode.EXECUTION_FAILURE, (event.event_id, event.capability.identity), (event.event_hash,))
            candidate = BarCloseCandidate(BarCloseObservation.from_event(event), market_approval, pretrade_approval, plan.liquidity_evidence, plan.market_state)
            execution_outcome = case.execution_model.simulate_execution(NextBarCloseRequest(stream, candidate, False))
        if execution_outcome.failure is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.EXECUTION_FAILURE,
                (execution_outcome.failure.code.value,),
                (canonical_sha256(execution_outcome.failure),),
            )
        decision = cast(NextBarOpenDecision | NextBarCloseDecision, execution_outcome.result)
        self._trace_add(
            state,
            EngineStage.EXECUTION_DECISION,
            event.timeline_instant,
            stream.order.order_id.value,
            canonical_sha256(decision),
        )
        if decision.action is not NoEligibleBarAction.FULL_FILL:
            return None
        if decision.reference_price is None or decision.fill_quantity is None:
            raise ValueError("full-fill decision lacks reference price or quantity")
        slippage_request = SlippageRequest(
            reference_price=decision.reference_price,
            side=stream.order.intent.side,
            quantity=decision.fill_quantity,
            market_state=plan.market_state,
        )
        slippage_outcome = plan.slippage_model.decide_slippage(slippage_request)
        if slippage_outcome.failure is not None:
            return self._failed(
                case,
                state,
                EngineFailureCode.SLIPPAGE_FAILURE,
                tuple(value.value for value in slippage_outcome.failure.failed_dimensions),
                (canonical_sha256(slippage_outcome.failure),),
            )
        slippage = cast(SlippageDecision, slippage_outcome.result)
        state.slippage_decisions.append(slippage)
        self._trace_add(
            state,
            EngineStage.SLIPPAGE,
            event.timeline_instant,
            stream.order.order_id.value,
            canonical_sha256(slippage),
        )
        fill_result = FullFillBuilder().build(
            decision=decision,
            slippage_outcome=cast(
                SimulationPortOutcome[SlippageDecision, SlippageApplicabilityViolation],
                slippage_outcome,
            ),
            fill_id=plan.fill_id,
        )
        if isinstance(fill_result, FullFillConstructionFailure):
            return self._failed(
                case,
                state,
                EngineFailureCode.FILL_CONSTRUCTION,
                (fill_result.code.value,),
                (fill_result.failure_id,),
            )
        fill = fill_result.fill
        if (
            plan.fill_event_at.instant != fill.execution_time
            or (
                plan.fill_event_at.phase.rank,
                plan.fill_event_at.phase.code,
                plan.fill_event_at.source_sequence.value,
            )
            <= (
                event.phase.rank,
                event.phase.code,
                event.source_sequence.value,
            )
        ):
            return self._failed(
                case,
                state,
                EngineFailureCode.CASE_EVIDENCE_MISMATCH,
                (plan.fill_event_id,),
                (fill_result.result_hash,),
            )
        if isinstance(plan.accounting_plan.fee_plan, FullFillOrderFeeAccountingPlan) and (
            fill.quantity != stream.order.intent.quantity
            or any(record.fill is not None for record in stream.records)
        ):
            return self._failed(
                case, state, EngineFailureCode.FEE_ASSESSMENT_FAILURE,
                ("single_full_fill_order_fee_required",),
            )
        cause = stream.records[-1].event.event_id
        fill_event = OrderEvent(
            event_id=plan.fill_event_id,
            order_id=stream.order.order_id,
            causation_id=cause,
            event_type=OrderEventType.ORDER_FILLED,
            occurred_at=plan.fill_event_at,
            fill_id=fill.fill_id,
            evidence_id=fill_result.result_hash,
        )
        stream = stream.append(OrderEventRecord(fill_event, fill))
        state.order_streams[plan.order_id.value] = stream
        state.fills.append(fill)
        self._trace_add(
            state,
            EngineStage.FILL,
            plan.fill_event_at,
            fill.fill_id.value,
            canonical_sha256(fill),
        )
        self._refresh_resources(case, state)

        accounting = plan.accounting_plan
        dispatch = self._financial_dispatcher.book_fill(
            accounting,
            fill,
            self._financial_state_view(state),
        )
        failure = self._apply_financial_dispatch(
            case,
            state,
            dispatch,
            expected_snapshot=False,
            expected_source_event_id=accounting.source_event_id,
            expected_source_evidence_hash=canonical_sha256(fill),
            dispatch_at=accounting.fill_recorded_at,
            source_fill_record=stream.records[-1],
        )
        if failure is not None:
            return failure
        if dispatch.result is None:
            raise ValueError("successful financial dispatch lacks result")
        self._trace_add(
            state,
            EngineStage.FILL_ACCOUNTING,
            accounting.fill_recorded_at,
            accounting.fill_journal_entry_id.value,
            canonical_sha256(dispatch.result),
        )

        fee = accounting.fee_plan
        if isinstance(fee, FullFillOrderFeeAccountingPlan) and fee.fill_fee_plan is not None:
            failure = self._assess_and_book_fee(
                case, state, replace(accounting, fee_plan=fee.fill_fee_plan), stream, fill
            )
            if failure is not None:
                return failure
        return self._assess_and_book_fee(case, state, accounting, stream, fill)

    def _assess_and_book_fee(
        self,
        case: ExecutionCase,
        state: _EngineState,
        accounting: FillAccountingDispatchPlan,
        stream: OrderEventStream,
        fill: Fill,
    ) -> EngineExecutionOutcome | None:
        fee = accounting.fee_plan
        rules = fee.final_fee_rule_set
        if isinstance(rules, ProfileFeeRuleBinding):
            resolved = self._resolve_profile_fee_rules(case, state, accounting.source_event_id,
                ProfileFeeRuleQuery(rules, stream.order, fee.assessment_at,
                    FeeBasisType.ORDER if isinstance(fee, FullFillOrderFeeAccountingPlan) else FeeBasisType.FILL, fill))
            if isinstance(resolved, EngineExecutionOutcome):
                return resolved
            if type(resolved) is not FinalFeeRuleSet:
                raise ValueError("final resolver returned reservation rules")
            rules = resolved
            fee = replace(fee, final_fee_rule_set=rules)
            accounting = replace(accounting, fee_plan=fee)
        fee_outcome = FeeAssessmentEngine().assess(
            basis=(
                FeeAssessmentBasisEvidence.for_order(stream)
                if isinstance(fee, FullFillOrderFeeAccountingPlan)
                else FeeAssessmentBasisEvidence.for_fill(fill)
            ),
            rule_set=rules,
            fee_assessment_id=fee.fee_assessment_id,
            assessment_time=fee.fee_assessment_time,
        )
        if fee_outcome.result is None:
            assessment_failure = cast(Any, fee_outcome.failure)
            return self._failed(
                case,
                state,
                EngineFailureCode.FEE_ASSESSMENT_FAILURE,
                tuple(value.value for value in assessment_failure.codes),
                (assessment_failure.failure_hash,),
            )
        state.fee_assessments.append(fee_outcome.result.assessment)
        self._trace_add(
            state,
            EngineStage.FEE_ASSESSMENT,
            fee.assessment_at,
            fee.fee_assessment_id.value,
            fee_outcome.result.result_hash,
        )
        # A zero assessment is authoritative evidence, not a cash mutation.
        if fee_outcome.result.assessment.amount.units:
            if (
                type(accounting.position_payload) is CashFillAccountingPlan
                and accounting.position_payload.cost_basis_policy.policy_version >= 2
            ):
                fee_dispatch = self._financial_dispatcher.book_fee(
                    accounting, fill, fee_outcome.result, self._financial_state_view(state)
                )
                failure = self._apply_financial_dispatch(
                    case,
                    state,
                    fee_dispatch,
                    expected_snapshot=False,
                    expected_source_event_id=accounting.source_event_id if isinstance(case, ResolvedExecutionCaseV2) else None,
                    dispatch_at=fee.fee_recorded_at if isinstance(case, ResolvedExecutionCaseV2) else None,
                )
                if failure is not None:
                    return failure
                if fee_dispatch.result is None:
                    raise RuntimeError("successful fee dispatch lacks result")
                self._trace_add(
                    state,
                    EngineStage.FEE_ACCOUNTING,
                    fee.fee_recorded_at,
                    fee.fee_journal_entry_id.value,
                    canonical_sha256(fee_dispatch.result),
                )
            else:
                fee_journal = FeeChargedJournalTranslator().translate(
                    result=fee_outcome.result,
                    cash_key=fee.cash_key,
                    journal_entry_id=fee.fee_journal_entry_id,
                    recorded_at=fee.fee_recorded_at,
                )
                if fee_journal.result is None:
                    fee_failure = cast(Any, fee_journal.failure)
                    return self._failed(
                        case,
                        state,
                        EngineFailureCode.FEE_ACCOUNTING_FAILURE,
                        (fee_failure.code.value,),
                        (fee_failure.failure_hash,),
                    )
                state.journal = state.journal.append(fee_journal.result.journal_entry)
                self._trace_add(
                    state,
                    EngineStage.FEE_ACCOUNTING,
                    fee.fee_recorded_at,
                    fee.fee_journal_entry_id.value,
                    fee_journal.result.result_hash,
                )
                state.ledger_state = state.ledger.project(state.journal)
                self._refresh_resources(case, state)
        self._trace_add(
            state,
            EngineStage.LEDGER_STATE,
            fee.fee_recorded_at,
            state.snapshot.account_id,
            state.ledger_state.state_hash,
        )
        return None

    def _reservation_state_excluding(
        self, state: _EngineState, order_id: str | None
    ) -> ResourceReservationState:
        if order_id is None:
            return state.reservation_state
        streams = tuple(
            value
            for key, value in state.order_streams.items()
            if key != order_id
        )
        schedules = tuple(
            value
            for key, value in state.reservation_schedules.items()
            if key != order_id
        )
        return state.reservation_book.project(streams, schedules)

    @staticmethod
    def _project_resources(
        case: ExecutionCase,
        state: _EngineState,
        ledger_state: LedgerState,
        settlement_book: SettlementBook,
    ) -> tuple[ResourceReservationState, SettlementBookState, AvailabilityState]:
        reservations = state.reservation_book.project(
            tuple(state.order_streams.values()),
            tuple(state.reservation_schedules.values()),
        )
        settlement = settlement_book.project()
        availability = AvailabilityProjection().project(
            ledger_state, settlement, reservations,
            case.financial_state.settlement_rules,
        )
        return reservations, settlement, availability

    def _refresh_resources(
        self, case: ExecutionCase, state: _EngineState
    ) -> None:
        state.reservation_state, state.settlement_state, state.availability = (
            self._project_resources(case, state, state.ledger_state, state.settlement_book)
        )

    @staticmethod
    def _trace(state: _EngineState) -> ExecutionTrace:
        return ExecutionTrace(tuple(state.trace_entries))

    @staticmethod
    def _trace_add(
        state: _EngineState,
        stage: EngineStage,
        instant: SimulationInstant,
        subject_id: str,
        evidence_hash: str,
    ) -> None:
        state.trace_entries.append(
            ExecutionTraceEntry(
                sequence=len(state.trace_entries),
                stage=stage,
                instant=instant,
                subject_id=subject_id,
                evidence_hash=evidence_hash,
            )
        )

    def _failed(
        self,
        case: ExecutionCase,
        state: _EngineState,
        code: EngineFailureCode,
        subjects: tuple[str, ...],
        evidence_hashes: tuple[str, ...] = (),
        *,
        termination: EngineTermination | None = None,
    ) -> EngineExecutionOutcome:
        normalized_subjects = subjects or (code.value,)
        return EngineExecutionOutcome(
            engine_failure=EngineFailure(
                code=code,
                case_hash=case.case_hash,
                trace_hash=self._trace(state).trace_hash,
                subject_keys=normalized_subjects,
                evidence_hashes=evidence_hashes,
                termination=termination,
            )
        )
