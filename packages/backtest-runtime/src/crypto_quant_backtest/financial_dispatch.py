"""Profile-neutral financial dispatch contracts for the Bar Engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable
import unicodedata

from crypto_quant_domain import (
    AccountingJournalEntry,
    CashBalanceKey,
    DomainId,
    DomainIdKind,
    Fill,
    PortfolioSnapshot,
    PositionBalanceKey,
    PositionLot,
    Price,
    QuantizationPolicy,
    SimulationInstant,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    CashInstrumentAccounting,
    CostBasisPolicy,
    FinalFeeAssessmentResult,
    FinalFeeRuleSet,
    LedgerBalanceRegistration,
    LedgerState,
    LinearFundingApplicationIdentity,
    LinearPerpetualContract,
    PortfolioSnapshotProjector,
    ProfileComponentRef,
    ProfilePortType,
    ResourceReservationState,
)

from .ports import SimulationComponentRef, SimulationPortType


_HASH_PREFIX = "sha256:"
_CASH_DISPATCHER_KEY = "generic.cash.financial-dispatcher.v1"


def _text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(_HASH_PREFIX)
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be canonical sha256 digest")
    return value


def _canonical_payload(name: str, value: object) -> object:
    if not callable(getattr(value, "to_canonical_dict", None)):
        raise TypeError(f"{name} must satisfy canonical contract")
    canonical_sha256(value)
    return value


def _texts(name: str, values: object) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    normalized = tuple(sorted(_text(name, value) for value in values))
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must be unique")
    return normalized


@dataclass(frozen=True, slots=True)
class FinancialDispatcherSpec:
    dispatcher_key: str
    dispatcher_version: int
    config_hash: str
    position_accounting_component: ProfileComponentRef
    financing_component: ProfileComponentRef
    margin_component: ProfileComponentRef
    liquidation_audit_component: SimulationComponentRef
    snapshot_projection_key: str
    snapshot_projection_version: int

    def __post_init__(self) -> None:
        _text("dispatcher_key", self.dispatcher_key)
        if type(self.dispatcher_version) is not int or self.dispatcher_version <= 0:
            raise ValueError("dispatcher_version must be positive integer")
        _hash("config_hash", self.config_hash)
        expected = (
            (self.position_accounting_component, ProfilePortType.POSITION_ACCOUNTING_MODEL),
            (self.financing_component, ProfilePortType.FINANCING_MODEL),
            (self.margin_component, ProfilePortType.MARGIN_MODEL),
        )
        for component, port_type in expected:
            if not isinstance(component, ProfileComponentRef):
                raise TypeError("profile components must be ProfileComponentRef")
            if component.port_type is not port_type:
                raise ValueError("profile component port mismatch")
        if not isinstance(self.liquidation_audit_component, SimulationComponentRef):
            raise TypeError("liquidation_audit_component must be SimulationComponentRef")
        if (
            self.liquidation_audit_component.port_type
            is not SimulationPortType.LIQUIDATION_AUDIT_MODEL
        ):
            raise ValueError("liquidation audit component port mismatch")
        _text("snapshot_projection_key", self.snapshot_projection_key)
        if (
            type(self.snapshot_projection_version) is not int
            or self.snapshot_projection_version <= 0
        ):
            raise ValueError("snapshot_projection_version must be positive integer")

    @property
    def spec_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "financial_dispatcher_spec",
            "schema_version": 1,
            "dispatcher_key": self.dispatcher_key,
            "dispatcher_version": self.dispatcher_version,
            "config_hash": self.config_hash,
            "position_accounting_component": self.position_accounting_component,
            "financing_component": self.financing_component,
            "margin_component": self.margin_component,
            "liquidation_audit_component": self.liquidation_audit_component,
            "snapshot_projection_key": self.snapshot_projection_key,
            "snapshot_projection_version": self.snapshot_projection_version,
        }


@dataclass(frozen=True, slots=True)
class LinearDerivativeFillAccountingPlan:
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    settlement_cash_registration: LedgerBalanceRegistration
    pnl_quantization: QuantizationPolicy

    def __post_init__(self) -> None:
        if type(self.position_key) is not PositionBalanceKey:
            raise TypeError("position_key must be exact PositionBalanceKey")
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        if type(self.settlement_cash_registration) is not LedgerBalanceRegistration:
            raise TypeError(
                "settlement_cash_registration must be exact LedgerBalanceRegistration"
            )
        if type(self.pnl_quantization) is not QuantizationPolicy:
            raise TypeError("pnl_quantization must be exact QuantizationPolicy")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_linear_fill_payload",
            "position_key": self.position_key,
            "contract": self.contract,
            "settlement_cash_registration": self.settlement_cash_registration,
            "pnl_quantization": self.pnl_quantization,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingAccountEventPlan:
    settlement_identity: LinearFundingApplicationIdentity
    recorded_at: SimulationInstant

    def __post_init__(self) -> None:
        if type(self.settlement_identity) is not LinearFundingApplicationIdentity:
            raise TypeError(
                "settlement_identity must be exact LinearFundingApplicationIdentity"
            )
        if type(self.recorded_at) is not SimulationInstant:
            raise TypeError("recorded_at must be exact SimulationInstant")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_funding_dispatch_payload",
            "settlement_identity": self.settlement_identity,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class LinearMarginLiquidationAuditPlan:
    evaluated_at: SimulationInstant
    valuation_price: Price
    margin_price: Price
    interval_start: UtcInstant
    interval_end_exclusive: UtcInstant
    liquidation_low: Price
    liquidation_high: Price
    audit_at: SimulationInstant
    role_suffix: str

    def __post_init__(self) -> None:
        if type(self.evaluated_at) is not SimulationInstant or type(
            self.audit_at
        ) is not SimulationInstant:
            raise TypeError("evaluation and audit times must be SimulationInstant")
        for name in (
            "valuation_price",
            "margin_price",
            "liquidation_low",
            "liquidation_high",
        ):
            if type(getattr(self, name)) is not Price:
                raise TypeError(f"{name} must be exact Price")
        if type(self.interval_start) is not UtcInstant or type(
            self.interval_end_exclusive
        ) is not UtcInstant:
            raise TypeError("audit interval must use exact UtcInstant")
        if self.interval_end_exclusive <= self.interval_start:
            raise ValueError("audit interval must be non-empty")
        _text("role_suffix", self.role_suffix)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_margin_audit_payload",
            "evaluated_at": self.evaluated_at,
            "valuation_price": self.valuation_price,
            "margin_price": self.margin_price,
            "interval_start": self.interval_start,
            "interval_end_exclusive": self.interval_end_exclusive,
            "liquidation_low": self.liquidation_low,
            "liquidation_high": self.liquidation_high,
            "audit_at": self.audit_at,
            "role_suffix": self.role_suffix,
        }


@dataclass(frozen=True, slots=True)
class CashFillAccountingPlan:
    """Legacy cash payload retained as one concrete dispatcher payload."""

    cash_key: CashBalanceKey
    position_key: PositionBalanceKey
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy
    fill_journal_entry_id: DomainId
    fill_recorded_at: SimulationInstant
    final_fee_rule_set: FinalFeeRuleSet
    fee_assessment_id: DomainId
    fee_assessment_time: UtcInstant
    fee_journal_entry_id: DomainId
    fee_recorded_at: SimulationInstant

    def __post_init__(self) -> None:
        if not isinstance(self.cash_key, CashBalanceKey):
            raise TypeError("cash_key must be CashBalanceKey")
        if not isinstance(self.position_key, PositionBalanceKey):
            raise TypeError("position_key must be PositionBalanceKey")
        if (
            self.cash_key.account_id != self.position_key.account_id
            or self.cash_key.venue_id != self.position_key.venue_id
        ):
            raise ValueError("Cash/Position accounting context mismatch")
        if not isinstance(self.cost_basis_policy, CostBasisPolicy):
            raise TypeError("cost_basis_policy must be CostBasisPolicy")
        if not isinstance(self.notional_quantization, QuantizationPolicy):
            raise TypeError("notional_quantization must be QuantizationPolicy")
        for name, value, kind in (
            ("fill_journal_entry_id", self.fill_journal_entry_id, DomainIdKind.JOURNAL),
            ("fee_assessment_id", self.fee_assessment_id, DomainIdKind.FEE),
            ("fee_journal_entry_id", self.fee_journal_entry_id, DomainIdKind.JOURNAL),
        ):
            if not isinstance(value, DomainId) or value.kind is not kind:
                raise ValueError(f"{name} has invalid DomainId kind")
        if not isinstance(self.fill_recorded_at, SimulationInstant) or not isinstance(
            self.fee_recorded_at, SimulationInstant
        ):
            raise TypeError("recorded times must be SimulationInstant")
        if not isinstance(self.final_fee_rule_set, FinalFeeRuleSet):
            raise TypeError("final_fee_rule_set must be FinalFeeRuleSet")
        if not isinstance(self.fee_assessment_time, UtcInstant):
            raise TypeError("fee_assessment_time must be UtcInstant")
        if not (
            self.fill_recorded_at.instant
            <= self.fee_assessment_time
            <= self.fee_recorded_at.instant
        ):
            raise ValueError("Fill/Fee accounting times must be monotonic")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cash_fill_accounting_plan",
            "cash_key": self.cash_key,
            "position_key": self.position_key,
            "cost_basis_policy": self.cost_basis_policy,
            "notional_quantization": self.notional_quantization,
            "fill_journal_entry_id": self.fill_journal_entry_id,
            "fill_recorded_at": self.fill_recorded_at,
            "final_fee_rule_set": self.final_fee_rule_set,
            "fee_assessment_id": self.fee_assessment_id,
            "fee_assessment_time": self.fee_assessment_time,
            "fee_journal_entry_id": self.fee_journal_entry_id,
            "fee_recorded_at": self.fee_recorded_at,
        }


@dataclass(frozen=True, slots=True)
class FeeAccountingDispatchPlan:
    cash_key: CashBalanceKey
    final_fee_rule_set: FinalFeeRuleSet
    fee_assessment_id: DomainId
    fee_assessment_time: UtcInstant
    fee_journal_entry_id: DomainId
    fee_recorded_at: SimulationInstant

    def __post_init__(self) -> None:
        if not isinstance(self.cash_key, CashBalanceKey):
            raise TypeError("cash_key must be CashBalanceKey")
        if not isinstance(self.final_fee_rule_set, FinalFeeRuleSet):
            raise TypeError("final_fee_rule_set must be FinalFeeRuleSet")
        if (
            not isinstance(self.fee_assessment_id, DomainId)
            or self.fee_assessment_id.kind is not DomainIdKind.FEE
        ):
            raise ValueError("fee_assessment_id must be Fee DomainId")
        if (
            not isinstance(self.fee_journal_entry_id, DomainId)
            or self.fee_journal_entry_id.kind is not DomainIdKind.JOURNAL
        ):
            raise ValueError("fee_journal_entry_id must be Journal DomainId")
        if not isinstance(self.fee_assessment_time, UtcInstant):
            raise TypeError("fee_assessment_time must be UtcInstant")
        if not isinstance(self.fee_recorded_at, SimulationInstant):
            raise TypeError("fee_recorded_at must be SimulationInstant")
        if self.fee_assessment_time > self.fee_recorded_at.instant:
            raise ValueError("fee accounting times must be monotonic")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "fee_accounting_dispatch_plan",
            "schema_version": 1,
            "cash_key": self.cash_key,
            "final_fee_rule_set": self.final_fee_rule_set,
            "fee_assessment_id": self.fee_assessment_id,
            "fee_assessment_time": self.fee_assessment_time,
            "fee_journal_entry_id": self.fee_journal_entry_id,
            "fee_recorded_at": self.fee_recorded_at,
        }


@dataclass(frozen=True, slots=True)
class FillAccountingDispatchPlan:
    source_event_id: str
    expected_fill_id: DomainId
    position_accounting_component: ProfileComponentRef
    position_payload: object
    semantic_payload: object
    fill_journal_entry_id: DomainId
    fill_recorded_at: SimulationInstant
    fee_plan: FeeAccountingDispatchPlan
    expected_artifact_roles: tuple[str, ...]

    def __post_init__(self) -> None:
        _text("source_event_id", self.source_event_id)
        if (
            not isinstance(self.expected_fill_id, DomainId)
            or self.expected_fill_id.kind is not DomainIdKind.FILL
        ):
            raise ValueError("expected_fill_id must be Fill DomainId")
        if not isinstance(self.position_accounting_component, ProfileComponentRef):
            raise TypeError("position_accounting_component must be ProfileComponentRef")
        if (
            self.position_accounting_component.port_type
            is not ProfilePortType.POSITION_ACCOUNTING_MODEL
        ):
            raise ValueError("position accounting component port mismatch")
        _canonical_payload("position_payload", self.position_payload)
        _canonical_payload("semantic_payload", self.semantic_payload)
        if (
            not isinstance(self.fill_journal_entry_id, DomainId)
            or self.fill_journal_entry_id.kind is not DomainIdKind.JOURNAL
        ):
            raise ValueError("fill_journal_entry_id must be Journal DomainId")
        if not isinstance(self.fill_recorded_at, SimulationInstant):
            raise TypeError("fill_recorded_at must be SimulationInstant")
        if not isinstance(self.fee_plan, FeeAccountingDispatchPlan):
            raise TypeError("fee_plan must be FeeAccountingDispatchPlan")
        object.__setattr__(
            self,
            "expected_artifact_roles",
            _texts("expected_artifact_roles", self.expected_artifact_roles),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "fill_accounting_dispatch_plan",
            "schema_version": 1,
            "source_event_id": self.source_event_id,
            "expected_fill_id": self.expected_fill_id,
            "position_accounting_component": self.position_accounting_component,
            "position_payload": self.position_payload,
            "semantic_payload": self.semantic_payload,
            "fill_journal_entry_id": self.fill_journal_entry_id,
            "fill_recorded_at": self.fill_recorded_at,
            "fee_plan": self.fee_plan,
            "expected_artifact_roles": self.expected_artifact_roles,
        }


@dataclass(frozen=True, slots=True)
class ScheduledAccountEvent:
    event_id: str
    event_at: SimulationInstant
    operation_key: str
    component_keys: tuple[str, ...]
    identity_bindings: tuple[tuple[str, DomainId], ...]
    payload: object
    semantic_payload: object
    expected_artifact_roles: tuple[str, ...]

    def __post_init__(self) -> None:
        _text("event_id", self.event_id)
        if not isinstance(self.event_at, SimulationInstant):
            raise TypeError("event_at must be SimulationInstant")
        _text("operation_key", self.operation_key)
        object.__setattr__(self, "component_keys", _texts("component_keys", self.component_keys))
        if type(self.identity_bindings) is not tuple:
            raise TypeError("identity_bindings must be tuple")
        binding_keys: list[str] = []
        for binding_key, value in self.identity_bindings:
            binding_keys.append(_text("binding_key", binding_key))
            if not isinstance(value, DomainId):
                raise TypeError("identity binding value must be DomainId")
        if len(set(binding_keys)) != len(binding_keys):
            raise ValueError("identity binding keys must be unique")
        object.__setattr__(
            self,
            "identity_bindings",
            tuple(sorted(self.identity_bindings, key=lambda value: value[0])),
        )
        _canonical_payload("payload", self.payload)
        _canonical_payload("semantic_payload", self.semantic_payload)
        object.__setattr__(
            self,
            "expected_artifact_roles",
            _texts("expected_artifact_roles", self.expected_artifact_roles),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "scheduled_account_event",
            "schema_version": 1,
            "event_id": self.event_id,
            "event_at": self.event_at,
            "operation_key": self.operation_key,
            "component_keys": self.component_keys,
            "identity_bindings": self.identity_bindings,
            "payload": self.payload,
            "semantic_payload": self.semantic_payload,
            "expected_artifact_roles": self.expected_artifact_roles,
        }


@dataclass(frozen=True, slots=True)
class FinancialDispatchPlan:
    dispatcher_spec: FinancialDispatcherSpec
    scheduled_account_events: tuple[ScheduledAccountEvent, ...]
    final_snapshot_payload: object
    expected_artifact_roles: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.dispatcher_spec, FinancialDispatcherSpec):
            raise TypeError("dispatcher_spec must be FinancialDispatcherSpec")
        if type(self.scheduled_account_events) is not tuple or not all(
            isinstance(value, ScheduledAccountEvent)
            for value in self.scheduled_account_events
        ):
            raise TypeError("scheduled_account_events must contain ScheduledAccountEvent")
        ordered = tuple(
            sorted(
                self.scheduled_account_events,
                key=lambda value: (canonical_bytes(value.event_at), value.event_id),
            )
        )
        if len({value.event_id for value in ordered}) != len(ordered):
            raise ValueError("scheduled Account Event IDs must be unique")
        object.__setattr__(self, "scheduled_account_events", ordered)
        _canonical_payload("final_snapshot_payload", self.final_snapshot_payload)
        object.__setattr__(
            self,
            "expected_artifact_roles",
            _texts("expected_artifact_roles", self.expected_artifact_roles),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "financial_dispatch_plan",
            "schema_version": 1,
            "dispatcher_spec": self.dispatcher_spec,
            "scheduled_account_events": self.scheduled_account_events,
            "final_snapshot_payload": self.final_snapshot_payload,
            "expected_artifact_roles": self.expected_artifact_roles,
        }


@dataclass(frozen=True, slots=True)
class FinancialDispatchArtifact:
    role: str
    source_event_id: str
    occurred_at: SimulationInstant
    component_key: str
    component_version: int
    component_digest: str
    input_hash: str
    result_hash: str
    payload: object

    def __post_init__(self) -> None:
        _text("role", self.role)
        _text("source_event_id", self.source_event_id)
        if not isinstance(self.occurred_at, SimulationInstant):
            raise TypeError("occurred_at must be SimulationInstant")
        _text("component_key", self.component_key)
        if type(self.component_version) is not int or self.component_version <= 0:
            raise ValueError("component_version must be positive integer")
        _hash("component_digest", self.component_digest)
        _hash("input_hash", self.input_hash)
        _hash("result_hash", self.result_hash)
        _canonical_payload("payload", self.payload)
        if self.result_hash != canonical_sha256(self.payload):
            raise ValueError("result_hash must match payload")

    @property
    def artifact_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "financial_dispatch_artifact",
            "schema_version": 1,
            "role": self.role,
            "source_event_id": self.source_event_id,
            "occurred_at": self.occurred_at,
            "component_key": self.component_key,
            "component_version": self.component_version,
            "component_digest": self.component_digest,
            "input_hash": self.input_hash,
            "result_hash": self.result_hash,
            "payload": self.payload,
        }


PositionLotState = tuple[tuple[PositionBalanceKey, tuple[PositionLot, ...]], ...]


def _validate_lot_state(values: PositionLotState) -> None:
    if type(values) is not tuple:
        raise TypeError("position_lot_books must be tuple")
    for key, lots in values:
        if not isinstance(key, PositionBalanceKey) or type(lots) is not tuple or not all(
            isinstance(value, PositionLot) for value in lots
        ):
            raise TypeError("invalid position lot state")


def _validate_artifacts(values: tuple[FinancialDispatchArtifact, ...]) -> None:
    if type(values) is not tuple or not all(
        isinstance(value, FinancialDispatchArtifact) for value in values
    ):
        raise TypeError("artifacts must contain FinancialDispatchArtifact")


@dataclass(frozen=True, slots=True)
class FinancialStateView:
    journal: AccountingJournal
    ledger_state: LedgerState
    reservation_state: ResourceReservationState
    position_lot_books: PositionLotState
    artifacts: tuple[FinancialDispatchArtifact, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.journal, AccountingJournal):
            raise TypeError("journal must be AccountingJournal")
        if not isinstance(self.ledger_state, LedgerState):
            raise TypeError("ledger_state must be LedgerState")
        if not isinstance(self.reservation_state, ResourceReservationState):
            raise TypeError("reservation_state must be ResourceReservationState")
        _validate_lot_state(self.position_lot_books)
        _validate_artifacts(self.artifacts)


@dataclass(frozen=True, slots=True)
class FinancialDispatchResult:
    dispatcher_spec: FinancialDispatcherSpec
    source_event_id: str
    journal_entries: tuple[AccountingJournalEntry, ...]
    position_lot_books: PositionLotState
    artifacts: tuple[FinancialDispatchArtifact, ...]
    snapshot: PortfolioSnapshot | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dispatcher_spec, FinancialDispatcherSpec):
            raise TypeError("dispatcher_spec must be FinancialDispatcherSpec")
        _text("source_event_id", self.source_event_id)
        if type(self.journal_entries) is not tuple or not all(
            isinstance(value, AccountingJournalEntry) for value in self.journal_entries
        ):
            raise TypeError("journal_entries must contain AccountingJournalEntry")
        _validate_lot_state(self.position_lot_books)
        _validate_artifacts(self.artifacts)
        if self.snapshot is not None and not isinstance(self.snapshot, PortfolioSnapshot):
            raise TypeError("snapshot must be PortfolioSnapshot or None")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "financial_dispatch_result",
            "schema_version": 1,
            "dispatcher_spec": self.dispatcher_spec,
            "source_event_id": self.source_event_id,
            "journal_entries": self.journal_entries,
            "position_lot_books": self.position_lot_books,
            "artifacts": self.artifacts,
            "snapshot": self.snapshot,
        }


class FinancialDispatchFailureCode(str, Enum):
    DISPATCHER_SPEC_MISMATCH = "dispatcher_spec_mismatch"
    FILL_PLAN_MISMATCH = "fill_plan_mismatch"
    EVENT_PLAN_MISMATCH = "event_plan_mismatch"
    PROFILE_COMPONENT_FAILURE = "profile_component_failure"
    JOURNAL_APPEND_FAILURE = "journal_append_failure"
    ARTIFACT_COVERAGE_MISMATCH = "artifact_coverage_mismatch"
    SNAPSHOT_PROJECTION_FAILURE = "snapshot_projection_failure"


@dataclass(frozen=True, slots=True)
class FinancialDispatchFailure:
    dispatcher_spec: FinancialDispatcherSpec
    source_event_id: str
    input_hash: str
    code: FinancialDispatchFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.dispatcher_spec, FinancialDispatcherSpec):
            raise TypeError("dispatcher_spec must be FinancialDispatcherSpec")
        _text("source_event_id", self.source_event_id)
        _hash("input_hash", self.input_hash)
        if not isinstance(self.code, FinancialDispatchFailureCode):
            raise TypeError("code must be FinancialDispatchFailureCode")
        object.__setattr__(self, "subject_ids", _texts("subject_ids", self.subject_ids))

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "financial_dispatch_failure",
            "schema_version": 1,
            "dispatcher_spec": self.dispatcher_spec,
            "source_event_id": self.source_event_id,
            "input_hash": self.input_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class FinancialDispatchOutcome:
    dispatcher_spec: FinancialDispatcherSpec
    input_hash: str
    result: FinancialDispatchResult | None = None
    failure: FinancialDispatchFailure | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dispatcher_spec, FinancialDispatcherSpec):
            raise TypeError("dispatcher_spec must be FinancialDispatcherSpec")
        _hash("input_hash", self.input_hash)
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one result or failure")
        value = self.result if self.result is not None else self.failure
        if value is None or value.dispatcher_spec != self.dispatcher_spec:
            raise ValueError("outcome dispatcher spec mismatch")
        if self.failure is not None and self.failure.input_hash != self.input_hash:
            raise ValueError("outcome input hash mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "financial_dispatch_outcome",
            "schema_version": 1,
            "dispatcher_spec": self.dispatcher_spec,
            "input_hash": self.input_hash,
            "result": self.result,
            "failure": self.failure,
        }


@runtime_checkable
class FinancialEventDispatcher(Protocol):
    @property
    def spec(self) -> FinancialDispatcherSpec: ...

    def book_fill(
        self,
        plan: FillAccountingDispatchPlan,
        fill: Fill,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome: ...

    def book_fee(
        self,
        plan: FillAccountingDispatchPlan,
        fill: Fill,
        assessment: FinalFeeAssessmentResult,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome: ...

    def dispatch_scheduled_event(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome: ...

    def project_final_snapshot(
        self,
        plan: FinancialDispatchPlan,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome: ...


def _component_ref(port_type: ProfilePortType, key: str) -> ProfileComponentRef:
    payload = {
        "type": "default_cash_financial_component",
        "port_type": port_type.value,
        "component_key": key,
        "component_version": 1,
    }
    return ProfileComponentRef(port_type, key, 1, canonical_sha256(payload))


def default_cash_financial_dispatcher_spec() -> FinancialDispatcherSpec:
    position = _component_ref(
        ProfilePortType.POSITION_ACCOUNTING_MODEL,
        "cash.instrument.position-accounting.v1",
    )
    financing = _component_ref(
        ProfilePortType.FINANCING_MODEL,
        "cash.no-financing.v1",
    )
    margin = _component_ref(ProfilePortType.MARGIN_MODEL, "cash.no-margin.v1")
    liquidation_payload = {
        "type": "default_cash_liquidation_component",
        "component_key": "cash.no-liquidation-audit.v1",
        "component_version": 1,
    }
    liquidation = SimulationComponentRef(
        SimulationPortType.LIQUIDATION_AUDIT_MODEL,
        "cash.no-liquidation-audit.v1",
        1,
        canonical_sha256(liquidation_payload),
    )
    config = {
        "type": "default_cash_financial_dispatcher_config",
        "dispatcher_key": _CASH_DISPATCHER_KEY,
        "dispatcher_version": 1,
        "position_accounting_component": position,
        "financing_component": financing,
        "margin_component": margin,
        "liquidation_audit_component": liquidation,
        "snapshot_projection_key": "generic.cash.portfolio-snapshot.v1",
        "snapshot_projection_version": 1,
    }
    return FinancialDispatcherSpec(
        _CASH_DISPATCHER_KEY,
        1,
        canonical_sha256(config),
        position,
        financing,
        margin,
        liquidation,
        "generic.cash.portfolio-snapshot.v1",
        1,
    )


def _failure(
    spec: FinancialDispatcherSpec,
    source_event_id: str,
    input_hash: str,
    code: FinancialDispatchFailureCode,
    *subjects: str,
) -> FinancialDispatchOutcome:
    failure = FinancialDispatchFailure(
        spec,
        source_event_id,
        input_hash,
        code,
        tuple(subjects) or (code.value,),
    )
    return FinancialDispatchOutcome(spec, input_hash, failure=failure)


def _lot_state(
    values: dict[PositionBalanceKey, tuple[PositionLot, ...]],
) -> PositionLotState:
    return tuple(sorted(values.items(), key=lambda value: canonical_bytes(value[0])))


def _position_lot_books_from_ledger(
    state: LedgerState,
) -> dict[PositionBalanceKey, tuple[PositionLot, ...]]:
    return {
        value.key: value.lots
        for value in state.position_balances
        if value.lots
    }


class DefaultCashFinancialDispatcher:
    def __init__(self) -> None:
        self._spec = default_cash_financial_dispatcher_spec()

    @property
    def spec(self) -> FinancialDispatcherSpec:
        return self._spec

    def book_fill(
        self,
        plan: FillAccountingDispatchPlan,
        fill: Fill,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        payload = plan.position_payload
        input_payload = {
            "operation": "book_fill",
            "plan": plan,
            "fill": fill,
            "journal_hash": state_view.journal.journal_hash,
        }
        if (
            type(payload) is CashFillAccountingPlan
            and payload.cost_basis_policy.policy_version >= 2
        ):
            input_payload["ledger_state_hash"] = state_view.ledger_state.state_hash
        input_hash = canonical_sha256(input_payload)
        if (
            plan.position_accounting_component
            != self.spec.position_accounting_component
            or plan.expected_fill_id != fill.fill_id
            or plan.source_event_id == ""
            or plan.fill_journal_entry_id
            != getattr(payload, "fill_journal_entry_id", None)
            or plan.fill_recorded_at != getattr(payload, "fill_recorded_at", None)
        ):
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                str(fill.fill_id),
            )
        if type(payload) is not CashFillAccountingPlan:
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                type(payload).__name__,
            )

        if payload.cost_basis_policy.policy_version >= 2:
            lots_by_position = _position_lot_books_from_ledger(
                state_view.ledger_state
            )
            lots = lots_by_position.get(payload.position_key, ())
            if (
                not lots
                and state_view.ledger_state.position_quantity(
                    payload.position_key
                ).units
            ):
                return _failure(
                    self.spec,
                    plan.source_event_id,
                    input_hash,
                    FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                    "position_lot_books",
                    str(payload.position_key),
                )
        else:
            lots_by_position = dict(state_view.position_lot_books)
            lots = lots_by_position.get(payload.position_key, ())

        booked = CashInstrumentAccounting().book_fill(
            fill=fill,
            cash_key=payload.cash_key,
            position_key=payload.position_key,
            open_lots=lots,
            cost_basis_policy=payload.cost_basis_policy,
            notional_quantization=payload.notional_quantization,
            journal_entry_id=plan.fill_journal_entry_id,
            recorded_at=plan.fill_recorded_at,
        )
        if booked.result is None:
            failure = booked.failure
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                getattr(getattr(failure, "code", None), "value", "cash-accounting"),
                getattr(failure, "subject_id", str(fill.fill_id)),
            )

        lots_by_position[payload.position_key] = booked.result.open_lots
        if payload.cost_basis_policy.policy_version >= 2 and not booked.result.open_lots:
            lots_by_position.pop(payload.position_key, None)

        artifact = FinancialDispatchArtifact(
            "position_accounting",
            plan.source_event_id,
            plan.fill_recorded_at,
            self.spec.position_accounting_component.component_key,
            self.spec.position_accounting_component.component_version,
            self.spec.position_accounting_component.component_digest,
            input_hash,
            canonical_sha256(booked.result),
            booked.result,
        )
        result = FinancialDispatchResult(
            self.spec,
            plan.source_event_id,
            (booked.result.journal_entry,),
            _lot_state(lots_by_position),
            (artifact,),
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def book_fee(
        self,
        plan: FillAccountingDispatchPlan,
        fill: Fill,
        assessment: FinalFeeAssessmentResult,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        input_hash = canonical_sha256(
            {
                "operation": "book_fee",
                "plan": plan,
                "fill": fill,
                "assessment": assessment,
                "journal_hash": state_view.journal.journal_hash,
                "ledger_state_hash": state_view.ledger_state.state_hash,
            }
        )
        payload = plan.position_payload
        if (
            type(payload) is not CashFillAccountingPlan
            or payload.cost_basis_policy.policy_version < 2
            or plan.expected_fill_id != fill.fill_id
            or assessment.rule_set != plan.fee_plan.final_fee_rule_set
            or assessment.assessment.fee_assessment_id
            != plan.fee_plan.fee_assessment_id
            or assessment.assessment.assessment_time
            != plan.fee_plan.fee_assessment_time
            or assessment.basis.fills != (fill,)
        ):
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                str(fill.fill_id),
            )
        lots_by_position = _position_lot_books_from_ledger(state_view.ledger_state)
        open_lots = lots_by_position.get(payload.position_key, ())
        if (
            not open_lots
            and state_view.ledger_state.position_quantity(payload.position_key).units
        ):
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "position_lot_books",
                str(payload.position_key),
            )
        fee = plan.fee_plan
        charged = CashInstrumentAccounting().charge_fee(
            assessment=assessment.assessment,
            related_fill=fill,
            cash_key=fee.cash_key,
            open_lots=open_lots,
            cost_basis_policy=payload.cost_basis_policy,
            journal_entry_id=fee.fee_journal_entry_id,
            recorded_at=fee.fee_recorded_at,
        )
        if charged.result is None:
            failure = charged.failure
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                getattr(getattr(failure, "code", None), "value", "cash-accounting"),
                getattr(failure, "subject_id", str(fill.fill_id)),
            )
        lots_by_position[payload.position_key] = charged.result.open_lots
        if not charged.result.open_lots:
            lots_by_position.pop(payload.position_key, None)
        result = FinancialDispatchResult(
            self.spec,
            plan.source_event_id,
            (charged.result.journal_entry,),
            _lot_state(lots_by_position),
            (),
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def dispatch_scheduled_event(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        input_hash = canonical_sha256(
            {
                "operation": "dispatch_scheduled_event",
                "event": event,
                "journal_hash": state_view.journal.journal_hash,
            }
        )
        return _failure(
            self.spec,
            event.event_id,
            input_hash,
            FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
            event.operation_key,
        )

    def project_final_snapshot(
        self,
        plan: FinancialDispatchPlan,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        input_hash = canonical_sha256(
            {
                "operation": "project_final_snapshot",
                "plan": plan,
                "ledger_state_hash": state_view.ledger_state.state_hash,
            }
        )
        if plan.dispatcher_spec != self.spec:
            return _failure(
                self.spec,
                "engine-finalize",
                input_hash,
                FinancialDispatchFailureCode.DISPATCHER_SPEC_MISMATCH,
                plan.dispatcher_spec.spec_hash,
            )
        payload = plan.final_snapshot_payload
        required = (
            "resolved_marks",
            "valuations",
            "reporting_currency",
            "reporting_scale",
            "timestamp",
            "currency_valuation_graph_hash",
        )
        if any(not hasattr(payload, name) for name in required):
            return _failure(
                self.spec,
                "engine-finalize",
                input_hash,
                FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE,
                type(payload).__name__,
            )
        snapshot_payload: Any = payload
        projection = PortfolioSnapshotProjector().project(
            ledger_state=state_view.ledger_state,
            resolved_marks=snapshot_payload.resolved_marks,
            valuations=snapshot_payload.valuations,
            reporting_currency=snapshot_payload.reporting_currency,
            reporting_scale=snapshot_payload.reporting_scale,
            timestamp=snapshot_payload.timestamp,
            currency_valuation_graph_hash=(
                snapshot_payload.currency_valuation_graph_hash
            ),
        )
        if projection.snapshot is None:
            failure = projection.failure
            return _failure(
                self.spec,
                "engine-finalize",
                input_hash,
                FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE,
                getattr(getattr(failure, "code", None), "value", "snapshot"),
            )
        artifact = FinancialDispatchArtifact(
            "final_snapshot",
            "engine-finalize",
            SimulationInstant(
                snapshot_payload.timestamp,
                state_view.journal.entries[-1].recorded_at.phase,
                state_view.journal.entries[-1].recorded_at.source_sequence,
            ),
            self.spec.snapshot_projection_key,
            self.spec.snapshot_projection_version,
            self.spec.config_hash,
            input_hash,
            canonical_sha256(projection.snapshot),
            projection.snapshot,
        )
        result = FinancialDispatchResult(
            self.spec,
            "engine-finalize",
            (),
            state_view.position_lot_books,
            (artifact,),
            projection.snapshot,
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)


__all__ = [
    "CashFillAccountingPlan",
    "DefaultCashFinancialDispatcher",
    "FeeAccountingDispatchPlan",
    "FillAccountingDispatchPlan",
    "FinancialDispatchArtifact",
    "FinancialDispatchFailure",
    "FinancialDispatchFailureCode",
    "FinancialDispatchOutcome",
    "FinancialDispatchPlan",
    "FinancialDispatchResult",
    "FinancialDispatcherSpec",
    "FinancialEventDispatcher",
    "FinancialStateView",
    "ScheduledAccountEvent",
    "default_cash_financial_dispatcher_spec",
]
