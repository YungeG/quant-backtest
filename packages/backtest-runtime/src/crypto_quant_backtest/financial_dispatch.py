"""Profile-neutral financial dispatch contracts for the Bar Engine."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, cast, runtime_checkable

from crypto_quant_domain import (
    AccountingJournalEntry,
    CashBalanceKey,
    CurrencyId,
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
    ValuationMarkReference,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    CashInstrumentAccounting,
    CostBasisPolicy,
    FeeChargedJournalTranslator,
    FinalFeeAssessmentResult,
    FinalFeeRuleSet,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
    LinearAccountMarginProjection,
    LinearAccountMarginProjectionRequest,
    LinearAccountMarginProjector,
    LinearAccountMarginProjectorV2,
    LinearDerivativeAccounting,
    LinearDerivativeAccountingRequest,
    LinearDerivativeJournalEntry,
    LinearDerivativeLedgerProjection,
    LinearDerivativeLedgerProjector,
    LinearDerivativeLedgerReplayRequest,
    LinearFundingAccounting,
    LinearFundingApplicationIdentity,
    LinearFundingEligibilityPositionSnapshot,
    LinearFundingEligibilityRequest,
    LinearFundingEligibilityResolver,
    LinearFundingMarkEvidence,
    LinearFundingRatePublicationCandidate,
    LinearFundingSettlementEvidence,
    LinearFundingSettlementRequest,
    LinearInstrumentMarginModel,
    LinearInstrumentMarginModelV2,
    LinearInstrumentMarginRequest,
    LinearInstrumentMarginResult,
    LinearMarginLedgerEvidence,
    LinearMarginLeverageEvidence,
    LinearMarginMarkEvidence,
    LinearMarginReservationEvidence,
    LinearMarginRuleBook,
    LinearPerpetualContract,
    LinearPositionProjectionRequest,
    LinearPositionProjector,
    LinearPositionProjectorV2,
    LinearPositionValuationEvidence,
    PortfolioSnapshotProjector,
    ProfileComponentRef,
    ProfilePortType,
    ResolvedMark,
    ResourceReservationState,
    StaleMarkPolicy,
)

from .liquidation_audit import (
    ConservativeLinearLiquidationAuditModel,
    ConservativeLinearLiquidationAuditModelV2,
    LinearLiquidationAccountWindowEvidence,
    LinearLiquidationAuditRequest,
    LinearLiquidationMarkBarEvidence,
)
from .ports import SimulationComponentRef, SimulationPortType
from .resolution import RequestedResultGrade

_HASH_PREFIX = "sha256:"
_CASH_DISPATCHER_KEY = "generic.cash.financial-dispatcher.v1"
_TRADIFI_DISPATCHER_KEY = "crypto.binance_usdm.tradifi.linear-financial-dispatch.v1"
_TRADIFI_FINANCING_KEY = "crypto.binance_usdm.tradifi.linear-funding-composition.v1"
_TRADIFI_MARGIN_KEY = "crypto.binance_usdm.tradifi.linear-margin-composition.v1"
_TRADIFI_SNAPSHOT_KEY = "crypto.binance_usdm.tradifi.linear-snapshot.v1"


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
            (
                self.position_accounting_component,
                ProfilePortType.POSITION_ACCOUNTING_MODEL,
            ),
            (self.financing_component, ProfilePortType.FINANCING_MODEL),
            (self.margin_component, ProfilePortType.MARGIN_MODEL),
        )
        for component, port_type in expected:
            if not isinstance(component, ProfileComponentRef):
                raise TypeError("profile components must be ProfileComponentRef")
            if component.port_type is not port_type:
                raise ValueError("profile component port mismatch")
        if not isinstance(self.liquidation_audit_component, SimulationComponentRef):
            raise TypeError(
                "liquidation_audit_component must be SimulationComponentRef"
            )
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
class LinearMarginProjectionPlan:
    account_id: str
    venue_id: VenueId
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    ledger_schema: LedgerSchema
    settlement_cash_key: CashBalanceKey
    evaluated_at: SimulationInstant
    valuation_mark: ResolvedMark
    valuation_stale_policy: StaleMarkPolicy
    leverage_evidence: LinearMarginLeverageEvidence
    margin_rule_book: LinearMarginRuleBook
    margin_mark_evidence: LinearMarginMarkEvidence
    settlement_cash_registration: LedgerBalanceRegistration
    margin_quantization: QuantizationPolicy
    unrealized_pnl_quantization: QuantizationPolicy
    ledger_evidence_key: str
    reservation_evidence_key: str

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        if type(self.venue_id) is not VenueId:
            raise TypeError("venue_id must be exact VenueId")
        if type(self.position_key) is not PositionBalanceKey:
            raise TypeError("position_key must be exact PositionBalanceKey")
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        if type(self.ledger_schema) is not LedgerSchema:
            raise TypeError("ledger_schema must be exact LedgerSchema")
        if type(self.settlement_cash_key) is not CashBalanceKey:
            raise TypeError("settlement_cash_key must be exact CashBalanceKey")
        if type(self.evaluated_at) is not SimulationInstant:
            raise TypeError("evaluated_at must be exact SimulationInstant")
        if type(self.valuation_mark) is not ResolvedMark:
            raise TypeError("valuation_mark must be exact ResolvedMark")
        if type(self.valuation_stale_policy) is not StaleMarkPolicy:
            raise TypeError("valuation_stale_policy must be exact StaleMarkPolicy")
        if type(self.leverage_evidence) is not LinearMarginLeverageEvidence:
            raise TypeError(
                "leverage_evidence must be exact LinearMarginLeverageEvidence"
            )
        if type(self.margin_rule_book) is not LinearMarginRuleBook:
            raise TypeError("margin_rule_book must be exact LinearMarginRuleBook")
        if type(self.margin_mark_evidence) is not LinearMarginMarkEvidence:
            raise TypeError(
                "margin_mark_evidence must be exact LinearMarginMarkEvidence"
            )
        if type(self.settlement_cash_registration) is not LedgerBalanceRegistration:
            raise TypeError(
                "settlement_cash_registration must be exact LedgerBalanceRegistration"
            )
        for name in ("margin_quantization", "unrealized_pnl_quantization"):
            if type(getattr(self, name)) is not QuantizationPolicy:
                raise TypeError(f"{name} must be exact QuantizationPolicy")
        _text("ledger_evidence_key", self.ledger_evidence_key)
        _text("reservation_evidence_key", self.reservation_evidence_key)
        if (
            self.position_key.account_id != self.account_id
            or self.position_key.venue_id != self.venue_id
            or self.settlement_cash_key.account_id != self.account_id
            or self.settlement_cash_key.venue_id != self.venue_id
            or self.settlement_cash_registration.key != self.settlement_cash_key
            or self.contract.instrument.instrument_id != self.position_key.instrument_id
            or self.valuation_mark.instrument_id != self.position_key.instrument_id
            or self.margin_mark_evidence.resolved_mark.instrument_id
            != self.position_key.instrument_id
            or self.leverage_evidence.account_id != self.account_id
            or self.leverage_evidence.instrument_id != self.position_key.instrument_id
        ):
            raise ValueError("linear margin projection context mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "linear_margin_projection_plan",
            "schema_version": 1,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "position_key": self.position_key,
            "contract": self.contract,
            "ledger_schema": self.ledger_schema,
            "settlement_cash_key": self.settlement_cash_key,
            "evaluated_at": self.evaluated_at,
            "valuation_mark": self.valuation_mark,
            "valuation_stale_policy": self.valuation_stale_policy,
            "leverage_evidence": self.leverage_evidence,
            "margin_rule_book": self.margin_rule_book,
            "margin_mark_evidence": self.margin_mark_evidence,
            "settlement_cash_registration": self.settlement_cash_registration,
            "margin_quantization": self.margin_quantization,
            "unrealized_pnl_quantization": self.unrealized_pnl_quantization,
            "ledger_evidence_key": self.ledger_evidence_key,
            "reservation_evidence_key": self.reservation_evidence_key,
        }


@dataclass(frozen=True, slots=True)
class _ProductionSemanticAuthority:
    type_key: str
    fields: Mapping[str, object]

    def __post_init__(self) -> None:
        _text("type_key", self.type_key)
        if not isinstance(self.fields, Mapping):
            raise TypeError("fields must be a mapping")
        canonical_sha256(self.fields)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": self.type_key, "schema_version": 1, **self.fields}


def _v2_funding_artifact_roles(
    settlement_identity: LinearFundingApplicationIdentity, /
) -> tuple[str, str]:
    """Derive the V2 funding artifact roles from its settlement identity."""
    if type(settlement_identity) is not LinearFundingApplicationIdentity:
        raise TypeError("settlement_identity must be exact LinearFundingApplicationIdentity")
    settlement_id = settlement_identity.settlement_id.value
    return (
        f"funding_eligibility.{settlement_id}",
        f"funding_accounting.{settlement_id}",
    )


@dataclass(frozen=True, slots=True)
class LinearFundingAccountEventPlan:
    settlement_identity: LinearFundingApplicationIdentity
    recorded_at: SimulationInstant
    ledger_schema: LedgerSchema | None = None
    settlement_cash_key: CashBalanceKey | None = None
    position_key: PositionBalanceKey | None = None
    contract: LinearPerpetualContract | None = None
    eligibility_instant: SimulationInstant | None = None
    position_snapshot_available_at: SimulationInstant | None = None
    position_snapshot_id: str | None = None
    eligibility_series_id: str | None = None
    position_revision_id: str | None = None
    position_supersedes_revision_id: str | None = None
    publication_candidates: tuple[LinearFundingRatePublicationCandidate, ...] | None = (
        None
    )
    settlement_evidence: LinearFundingSettlementEvidence | None = None
    funding_mark_evidence: LinearFundingMarkEvidence | None = None
    settlement_cash_registration: LedgerBalanceRegistration | None = None
    payment_quantization: QuantizationPolicy | None = None
    funding_model_version: int | None = None
    funding_eligibility_role: str | None = None
    funding_accounting_role: str | None = None

    def __post_init__(self) -> None:
        if type(self.settlement_identity) is not LinearFundingApplicationIdentity:
            raise TypeError(
                "settlement_identity must be exact LinearFundingApplicationIdentity"
            )
        if type(self.recorded_at) is not SimulationInstant:
            raise TypeError("recorded_at must be exact SimulationInstant")
        full = (
            self.ledger_schema,
            self.settlement_cash_key,
            self.position_key,
            self.contract,
            self.eligibility_instant,
            self.position_snapshot_available_at,
            self.position_snapshot_id,
            self.eligibility_series_id,
            self.position_revision_id,
            self.publication_candidates,
            self.settlement_evidence,
            self.funding_mark_evidence,
            self.settlement_cash_registration,
            self.payment_quantization,
        )
        if all(value is None for value in full):
            if (
                self.position_supersedes_revision_id is not None
                or self.funding_model_version is not None
                or self.funding_eligibility_role is not None
                or self.funding_accounting_role is not None
            ):
                raise ValueError("legacy funding plan cannot set production authority")
            return
        if any(value is None for value in full):
            raise ValueError("production funding authority must be complete")
        if type(self.ledger_schema) is not LedgerSchema:
            raise TypeError("ledger_schema must be exact LedgerSchema")
        if type(self.settlement_cash_key) is not CashBalanceKey:
            raise TypeError("settlement_cash_key must be exact CashBalanceKey")
        if type(self.position_key) is not PositionBalanceKey:
            raise TypeError("position_key must be exact PositionBalanceKey")
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        if (
            type(self.eligibility_instant) is not SimulationInstant
            or type(self.position_snapshot_available_at) is not SimulationInstant
        ):
            raise TypeError("eligibility and snapshot times must be SimulationInstant")
        for name in (
            "position_snapshot_id",
            "eligibility_series_id",
            "position_revision_id",
        ):
            _text(name, getattr(self, name))
        if self.position_supersedes_revision_id is not None:
            _text(
                "position_supersedes_revision_id", self.position_supersedes_revision_id
            )
        if type(self.publication_candidates) is not tuple or not all(
            type(value) is LinearFundingRatePublicationCandidate
            for value in self.publication_candidates
        ):
            raise TypeError("publication_candidates must contain exact Candidates")
        if type(self.settlement_evidence) is not LinearFundingSettlementEvidence:
            raise TypeError("settlement_evidence must be exact Evidence")
        if type(self.funding_mark_evidence) is not LinearFundingMarkEvidence:
            raise TypeError("funding_mark_evidence must be exact Evidence")
        if type(self.settlement_cash_registration) is not LedgerBalanceRegistration:
            raise TypeError("settlement_cash_registration must be exact Registration")
        if type(self.payment_quantization) is not QuantizationPolicy:
            raise TypeError("payment_quantization must be exact QuantizationPolicy")
        if self.funding_model_version is None:
            if (
                self.funding_eligibility_role is not None
                or self.funding_accounting_role is not None
            ):
                raise ValueError("legacy funding plan cannot set V2 artifact roles")
        elif type(self.funding_model_version) is not int or self.funding_model_version != 2:
            raise ValueError("funding model version must be V2 when artifact roles exist")
        elif (
            self.funding_eligibility_role is None
            or self.funding_accounting_role is None
        ):
            raise ValueError("V2 funding artifact roles must be present")
        else:
            roles = _v2_funding_artifact_roles(self.settlement_identity)
            if (
                _text("funding_eligibility_role", self.funding_eligibility_role),
                _text("funding_accounting_role", self.funding_accounting_role),
            ) != roles:
                raise ValueError("V2 funding artifact roles must match settlement identity")
        position_key = cast(PositionBalanceKey, self.position_key)
        settlement_cash_key = cast(CashBalanceKey, self.settlement_cash_key)
        registration = cast(
            LedgerBalanceRegistration, self.settlement_cash_registration
        )
        contract = cast(LinearPerpetualContract, self.contract)
        settlement = cast(LinearFundingSettlementEvidence, self.settlement_evidence)
        if (
            position_key.account_id
            != self.settlement_identity.application_key.account_id
            or settlement_cash_key.account_id != position_key.account_id
            or settlement_cash_key.venue_id != position_key.venue_id
            or registration.key != settlement_cash_key
            or contract.instrument.instrument_id != position_key.instrument_id
            or settlement.application_key != self.settlement_identity.application_key
        ):
            raise ValueError("production funding context mismatch")

    @property
    def has_production_authority(self) -> bool:
        return self.ledger_schema is not None

    def production_semantic_authority(self) -> object | None:
        if not self.has_production_authority:
            return None
        return _ProductionSemanticAuthority(
            "linear_funding_account_event_semantic_authority",
            {
                "application_key": self.settlement_identity.application_key,
                "recorded_at": self.recorded_at,
                "ledger_schema": self.ledger_schema,
                "settlement_cash_key": self.settlement_cash_key,
                "position_key": self.position_key,
                "contract": self.contract,
                "eligibility_instant": self.eligibility_instant,
                "position_snapshot_available_at": self.position_snapshot_available_at,
                "position_snapshot_id": self.position_snapshot_id,
                "eligibility_series_id": self.eligibility_series_id,
                "position_revision_id": self.position_revision_id,
                "position_supersedes_revision_id": self.position_supersedes_revision_id,
                "publication_candidates": self.publication_candidates,
                "settlement_evidence": self.settlement_evidence,
                "funding_mark_evidence": self.funding_mark_evidence,
                "settlement_cash_registration": self.settlement_cash_registration,
                "payment_quantization": self.payment_quantization,
            },
        )

    def to_canonical_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "synthetic_funding_dispatch_payload",
            "settlement_identity": self.settlement_identity,
            "recorded_at": self.recorded_at,
        }
        if self.has_production_authority:
            payload.update(
                {
                    "ledger_schema": self.ledger_schema,
                    "settlement_cash_key": self.settlement_cash_key,
                    "position_key": self.position_key,
                    "contract": self.contract,
                    "eligibility_instant": self.eligibility_instant,
                    "position_snapshot_available_at": (
                        self.position_snapshot_available_at
                    ),
                    "position_snapshot_id": self.position_snapshot_id,
                    "eligibility_series_id": self.eligibility_series_id,
                    "position_revision_id": self.position_revision_id,
                    "position_supersedes_revision_id": (
                        self.position_supersedes_revision_id
                    ),
                    "publication_candidates": self.publication_candidates,
                    "settlement_evidence": self.settlement_evidence,
                    "funding_mark_evidence": self.funding_mark_evidence,
                    "settlement_cash_registration": self.settlement_cash_registration,
                    "payment_quantization": self.payment_quantization,
                    **(
                        {
                            "funding_model_version": self.funding_model_version,
                            "funding_eligibility_role": self.funding_eligibility_role,
                            "funding_accounting_role": self.funding_accounting_role,
                        }
                        if self.funding_model_version is not None
                        else {}
                    ),
                }
            )
        return payload


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
    projection_plan: LinearMarginProjectionPlan | None = None
    liquidation_bars: tuple[LinearLiquidationMarkBarEvidence, ...] | None = None
    requested_grade: RequestedResultGrade | None = None
    account_window_evidence_key: str | None = None
    interval_start_journal_hash: str | None = None
    interval_end_journal_hash: str | None = None
    interval_start_reservation_hash: str | None = None
    interval_end_reservation_hash: str | None = None
    window_start_at: UtcInstant | None = None

    def __post_init__(self) -> None:
        if (
            type(self.evaluated_at) is not SimulationInstant
            or type(self.audit_at) is not SimulationInstant
        ):
            raise TypeError("evaluation and audit times must be SimulationInstant")
        for name in (
            "valuation_price",
            "margin_price",
            "liquidation_low",
            "liquidation_high",
        ):
            if type(getattr(self, name)) is not Price:
                raise TypeError(f"{name} must be exact Price")
        if (
            type(self.interval_start) is not UtcInstant
            or type(self.interval_end_exclusive) is not UtcInstant
        ):
            raise TypeError("audit interval must use exact UtcInstant")
        if self.interval_end_exclusive <= self.interval_start:
            raise ValueError("audit interval must be non-empty")
        _text("role_suffix", self.role_suffix)
        authority = (
            self.projection_plan,
            self.liquidation_bars,
            self.requested_grade,
            self.account_window_evidence_key,
        )
        hashes = (
            self.interval_start_journal_hash,
            self.interval_end_journal_hash,
            self.interval_start_reservation_hash,
            self.interval_end_reservation_hash,
        )
        if (
            all(value is None for value in authority + hashes)
            and self.window_start_at is None
        ):
            return
        if any(value is None for value in authority):
            raise ValueError("production margin/liquidation authority must be complete")
        legacy_mode = self.window_start_at is None and all(
            value is not None for value in hashes
        )
        runtime_checkpoint_mode = self.window_start_at is not None and all(
            value is None for value in hashes
        )
        if legacy_mode == runtime_checkpoint_mode:
            raise ValueError(
                "production margin/liquidation authority requires exactly one account window mode"
            )
        if runtime_checkpoint_mode:
            if type(self.window_start_at) is not UtcInstant:
                raise TypeError("window_start_at must be exact UtcInstant")
            if self.window_start_at != self.interval_start:
                raise ValueError("window_start_at must equal interval_start")
        if type(self.projection_plan) is not LinearMarginProjectionPlan:
            raise TypeError("projection_plan must be exact LinearMarginProjectionPlan")
        if type(self.liquidation_bars) is not tuple or not all(
            type(value) is LinearLiquidationMarkBarEvidence
            for value in self.liquidation_bars
        ):
            raise TypeError("liquidation_bars must contain exact Evidence")
        if self.requested_grade is not RequestedResultGrade.DEVELOPMENT:
            raise ValueError("production liquidation audit requires development grade")
        _text("account_window_evidence_key", self.account_window_evidence_key)
        if legacy_mode:
            for name in (
                "interval_start_journal_hash",
                "interval_end_journal_hash",
                "interval_start_reservation_hash",
                "interval_end_reservation_hash",
            ):
                _hash(name, getattr(self, name))
        if (
            self.projection_plan.evaluated_at != self.evaluated_at
            or self.projection_plan.valuation_mark.price != self.valuation_price
            or self.projection_plan.margin_mark_evidence.resolved_mark.price
            != self.margin_price
            or any(
                value.interval_start > self.interval_start
                or value.interval_end_exclusive < self.interval_end_exclusive
                or value.low != self.liquidation_low
                or value.high != self.liquidation_high
                for value in self.liquidation_bars
            )
        ):
            raise ValueError("legacy and production margin authority mismatch")

    @property
    def has_production_authority(self) -> bool:
        return self.projection_plan is not None

    @property
    def uses_runtime_checkpoint(self) -> bool:
        return self.window_start_at is not None

    def production_semantic_authority(self) -> object | None:
        if not self.has_production_authority:
            return None
        payload: dict[str, object] = {
            "evaluated_at": self.evaluated_at,
            "valuation_price": self.valuation_price,
            "margin_price": self.margin_price,
            "interval_start": self.interval_start,
            "interval_end_exclusive": self.interval_end_exclusive,
            "liquidation_low": self.liquidation_low,
            "liquidation_high": self.liquidation_high,
            "audit_at": self.audit_at,
            "role_suffix": self.role_suffix,
            "projection_plan": self.projection_plan,
            "liquidation_bars": self.liquidation_bars,
            "requested_grade": cast(
                RequestedResultGrade, self.requested_grade
            ).value,
            "account_window_evidence_key": self.account_window_evidence_key,
        }
        if self.uses_runtime_checkpoint:
            payload["window_start_at"] = self.window_start_at
        else:
            payload.update(
                {
                    "interval_start_journal_hash": self.interval_start_journal_hash,
                    "interval_end_journal_hash": self.interval_end_journal_hash,
                    "interval_start_reservation_hash": self.interval_start_reservation_hash,
                    "interval_end_reservation_hash": self.interval_end_reservation_hash,
                }
            )
        return _ProductionSemanticAuthority(
            "linear_margin_liquidation_audit_semantic_authority", payload
        )

    def to_canonical_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
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
        if self.has_production_authority:
            payload.update(
                {
                    "projection_plan": self.projection_plan,
                    "liquidation_bars": self.liquidation_bars,
                    "requested_grade": cast(
                        RequestedResultGrade, self.requested_grade
                    ).value,
                    "account_window_evidence_key": self.account_window_evidence_key,
                }
            )
            if self.uses_runtime_checkpoint:
                payload["window_start_at"] = self.window_start_at
            else:
                payload.update(
                    {
                        "interval_start_journal_hash": self.interval_start_journal_hash,
                        "interval_end_journal_hash": self.interval_end_journal_hash,
                        "interval_start_reservation_hash": self.interval_start_reservation_hash,
                        "interval_end_reservation_hash": self.interval_end_reservation_hash,
                    }
                )
        return payload


@dataclass(frozen=True, slots=True)
class LinearMarginLiquidationAuditSubwindowPlan:
    """One exact state interval within a retained liquidation hour."""
    plan: LinearMarginLiquidationAuditPlan
    start_checkpoint: SimulationInstant
    start_side: str
    end_checkpoint: SimulationInstant
    end_side: str

    def __post_init__(self) -> None:
        if type(self.plan) is not LinearMarginLiquidationAuditPlan or not self.plan.has_production_authority:
            raise TypeError("subwindow plan requires production liquidation plan")
        if type(self.start_checkpoint) is not SimulationInstant or type(self.end_checkpoint) is not SimulationInstant:
            raise TypeError("subwindow checkpoints must be exact SimulationInstant")
        if self.start_side not in ("before", "after") or self.end_side not in ("before", "after"):
            raise ValueError("subwindow checkpoint side must be before or after")
        if (
            self.start_checkpoint > self.end_checkpoint
            or self.start_checkpoint.instant != self.plan.interval_start
            or self.end_checkpoint.instant != self.plan.interval_end_exclusive
        ):
            raise ValueError("subwindow checkpoints must bind its interval boundaries")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "linear_margin_liquidation_audit_subwindow_plan", "schema_version": 1,
                "plan": self.plan, "start_checkpoint": self.start_checkpoint,
                "start_side": self.start_side, "end_checkpoint": self.end_checkpoint,
                "end_side": self.end_side}


@dataclass(frozen=True, slots=True)
class LinearMarginLiquidationAuditBatchPlan:
    """Atomic retained-hour liquidation audit; children reuse its sole full bar."""
    audit_at: SimulationInstant
    liquidation_bar: LinearLiquidationMarkBarEvidence
    subwindows: tuple[LinearMarginLiquidationAuditSubwindowPlan, ...]

    def __post_init__(self) -> None:
        if type(self.audit_at) is not SimulationInstant or type(self.liquidation_bar) is not LinearLiquidationMarkBarEvidence:
            raise TypeError("batch audit time/bar must be exact")
        if type(self.subwindows) is not tuple or not self.subwindows or any(type(v) is not LinearMarginLiquidationAuditSubwindowPlan for v in self.subwindows):
            raise ValueError("batch subwindows must be nonempty exact tuple")
        suffixes = tuple(v.plan.role_suffix for v in self.subwindows)
        if len(set(suffixes)) != len(suffixes):
            raise ValueError("batch subwindow role suffixes must be unique")
        previous: UtcInstant | None = None
        for child in self.subwindows:
            plan = child.plan
            if (
                plan.audit_at != self.audit_at
                or plan.liquidation_bars != (self.liquidation_bar,)
                or (previous is not None and plan.interval_start != previous)
                or plan.interval_start < self.liquidation_bar.interval_start
                or plan.interval_end_exclusive > self.liquidation_bar.interval_end_exclusive
            ):
                raise ValueError("batch subwindows must contiguously reuse the retained bar")
            previous = plan.interval_end_exclusive

    def production_semantic_authority(self) -> object:
        return _ProductionSemanticAuthority("linear_margin_liquidation_audit_batch_semantic_authority", self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "linear_margin_liquidation_audit_batch_plan", "schema_version": 1,
                "audit_at": self.audit_at, "liquidation_bar": self.liquidation_bar,
                "subwindows": self.subwindows}


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
        object.__setattr__(
            self, "component_keys", _texts("component_keys", self.component_keys)
        )
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
        if type(self.payload) is LinearFundingAccountEventPlan:
            if self.payload.funding_model_version is None:
                expected_roles = ("funding_accounting", "funding_eligibility")
            else:
                expected_roles = tuple(
                    sorted(_v2_funding_artifact_roles(self.payload.settlement_identity))
                )
            if self.expected_artifact_roles != expected_roles:
                raise ValueError("funding artifact roles must match the funding plan")

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
            raise TypeError(
                "scheduled_account_events must contain ScheduledAccountEvent"
            )
        ordered = tuple(
            sorted(
                self.scheduled_account_events,
                key=lambda value: (canonical_bytes(value.event_at), value.event_id),
            )
        )
        if len({value.event_id for value in ordered}) != len(ordered):
            raise ValueError("scheduled Account Event IDs must be unique")
        object.__setattr__(self, "scheduled_account_events", ordered)
        scheduled_roles = tuple(
            role for event in ordered for role in event.expected_artifact_roles
        )
        if len(set(scheduled_roles)) != len(scheduled_roles):
            raise ValueError("scheduled Account Event artifact roles must be globally unique")
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
        if (
            not isinstance(key, PositionBalanceKey)
            or type(lots) is not tuple
            or not all(isinstance(value, PositionLot) for value in lots)
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
    checkpoints: Mapping[tuple[SimulationInstant, str], FinancialStateView] | None = None
    window_start_journal_hash: str | None = None
    window_start_reservation_state_hash: str | None = None
    window_start_journal: AccountingJournal | None = None
    window_start_ledger_state: LedgerState | None = None
    window_start_reservation_state: ResourceReservationState | None = None
    window_start_position_lot_books: PositionLotState | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.journal, AccountingJournal):
            raise TypeError("journal must be AccountingJournal")
        if not isinstance(self.ledger_state, LedgerState):
            raise TypeError("ledger_state must be LedgerState")
        if not isinstance(self.reservation_state, ResourceReservationState):
            raise TypeError("reservation_state must be ResourceReservationState")
        _validate_lot_state(self.position_lot_books)
        _validate_artifacts(self.artifacts)
        if (self.window_start_journal_hash is None) != (
            self.window_start_reservation_state_hash is None
        ):
            raise ValueError("window start checkpoint hashes must be supplied together")
        checkpoint = (
            self.window_start_journal,
            self.window_start_ledger_state,
            self.window_start_reservation_state,
            self.window_start_position_lot_books,
        )
        if any(value is not None for value in checkpoint) != all(
            value is not None for value in checkpoint
        ):
            raise ValueError("window start checkpoint state must be supplied together")
        if self.window_start_journal_hash is not None:
            _hash("window_start_journal_hash", self.window_start_journal_hash)
            _hash(
                "window_start_reservation_state_hash",
                self.window_start_reservation_state_hash,
            )
            if all(value is not None for value in checkpoint):
                if (
                    self.window_start_journal.journal_hash
                    != self.window_start_journal_hash
                    or self.window_start_reservation_state.state_hash
                    != self.window_start_reservation_state_hash
                ):
                    raise ValueError("window start checkpoint state/hash mismatch")
                _validate_lot_state(self.window_start_position_lot_books)


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
        if self.snapshot is not None and not isinstance(
            self.snapshot, PortfolioSnapshot
        ):
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
    return {value.key: value.lots for value in state.position_balances if value.lots}


def _linear_replay(
    journal: AccountingJournal,
    ledger_schema: LedgerSchema,
    position_key: PositionBalanceKey,
    contract: LinearPerpetualContract,
    settlement_cash_key: CashBalanceKey,
    expected_ledger_state: LedgerState,
) -> LinearDerivativeLedgerProjection:
    outcome = LinearDerivativeLedgerProjector().project(
        LinearDerivativeLedgerReplayRequest(
            journal,
            ledger_schema,
            position_key,
            contract,
            settlement_cash_key,
        )
    )
    if (
        outcome.result is None
        or outcome.result.ledger_state_hash != expected_ledger_state.state_hash
        or expected_ledger_state.position_quantity(position_key)
        != outcome.result.position_state.quantity
    ):
        raise ValueError("linear derivative replay contract/context mismatch")
    return outcome.result


def _margin_models(
    margin_component: ProfileComponentRef,
) -> tuple[
    LinearInstrumentMarginModel | LinearInstrumentMarginModelV2,
    LinearAccountMarginProjector | LinearAccountMarginProjectorV2,
]:
    if margin_component == LinearAccountMarginProjectorV2().component_ref:
        return LinearInstrumentMarginModelV2(), LinearAccountMarginProjectorV2()
    # Legacy V1 margin refs are composition-derived and vary with authority
    # digests; ProfileResolver has already bound them before dispatch.
    if (
        margin_component.port_type is ProfilePortType.MARGIN_MODEL
        and margin_component.component_key == _TRADIFI_MARGIN_KEY
        and margin_component.component_version == 1
    ):
        return LinearInstrumentMarginModel(), LinearAccountMarginProjector()
    raise ValueError("unsupported Binance USD-M TradFi margin component")


def _linear_margin_projection(
    plan: LinearMarginProjectionPlan,
    state: FinancialStateView,
    margin_component: ProfileComponentRef,
) -> LinearAccountMarginProjection:
    replay = _linear_replay(
        state.journal,
        plan.ledger_schema,
        plan.position_key,
        plan.contract,
        plan.settlement_cash_key,
        state.ledger_state,
    )
    position_valuations: tuple[LinearPositionValuationEvidence, ...] = ()
    margin_results: tuple[LinearInstrumentMarginResult, ...] = ()
    if replay.position_state.quantity.units != 0:
        margin = _margin_models(margin_component)[0].evaluate_margin(
            LinearInstrumentMarginRequest(
                plan.position_key,
                plan.contract,
                replay.position_state.quantity,
                plan.evaluated_at,
                plan.leverage_evidence,
                plan.margin_rule_book,
                plan.margin_mark_evidence,
                plan.settlement_cash_registration,
                plan.margin_quantization,
            )
        )
        if margin.result is None:
            raise ValueError("linear instrument margin evaluation failed")
        position_valuations = (
            LinearPositionValuationEvidence(
                replay.position_state,
                plan.valuation_mark,
                plan.valuation_stale_policy,
            ),
        )
        margin_results = (margin.result,)
    projected = _margin_models(margin_component)[1].project(
        LinearAccountMarginProjectionRequest(
            plan.account_id,
            plan.venue_id,
            plan.evaluated_at,
            LinearMarginLedgerEvidence(
                state.ledger_state,
                plan.evaluated_at,
                plan.evaluated_at,
                plan.ledger_evidence_key,
                state.ledger_state.state_hash,
            ),
            position_valuations,
            margin_results,
            LinearMarginReservationEvidence(
                state.reservation_state,
                plan.evaluated_at,
                plan.evaluated_at,
                plan.reservation_evidence_key,
                state.reservation_state.state_hash,
            ),
            plan.settlement_cash_registration,
            plan.unrealized_pnl_quantization,
        )
    )
    if projected.projection is None:
        raise ValueError("linear account margin projection failed")
    return projected.projection


def _derivative_snapshot(
    state: FinancialStateView,
    projection: LinearAccountMarginProjection,
    timestamp: UtcInstant,
    reporting_currency: CurrencyId,
    currency_valuation_graph_hash: str,
) -> PortfolioSnapshot:
    marks = tuple(
        ValuationMarkReference(
            value.resolved_mark.source_event_id,
            value.resolved_mark.instrument_id,
            value.resolved_mark.price_purpose,
            value.resolved_mark.observed_at,
        )
        for value in projection.request.position_valuations
    )
    return PortfolioSnapshot(
        projection.request.account_id,
        timestamp,
        reporting_currency,
        state.ledger_state.cash_balances,
        state.ledger_state.position_balances,
        projection.realized_pnl,
        projection.total_unrealized_pnl,
        projection.fees,
        projection.funding,
        projection.equity,
        marks,
        state.ledger_state.state_hash,
        canonical_sha256(marks),
        canonical_sha256(
            tuple(
                value.stale_policy for value in projection.request.position_valuations
            )
        ),
        currency_valuation_graph_hash,
        timestamp_instant=projection.request.evaluated_at,
    )


def _ordered_artifacts(
    roles: tuple[str, ...], artifacts: tuple[FinancialDispatchArtifact, ...]
) -> tuple[FinancialDispatchArtifact, ...]:
    by_role = {value.role: value for value in artifacts}
    if len(by_role) != len(artifacts) or set(by_role) != set(roles):
        raise ValueError("artifact role coverage mismatch")
    return tuple(by_role[role] for role in roles)


class BinanceUsdmTradifiLinearFinancialDispatcher:
    """Production fill/fee dispatcher for the exact Binance USD-M TradFi shape."""

    def __init__(self, spec: FinancialDispatcherSpec) -> None:
        if type(spec) is not FinancialDispatcherSpec:
            raise TypeError("spec must be exact FinancialDispatcherSpec")
        expected_position = LinearDerivativeAccounting().component_ref
        expected_liquidations = {
            ConservativeLinearLiquidationAuditModel().component_ref,
            ConservativeLinearLiquidationAuditModelV2().component_ref,
        }
        if (
            spec.dispatcher_key != _TRADIFI_DISPATCHER_KEY
            or spec.dispatcher_version != 1
            or spec.position_accounting_component != expected_position
            or spec.financing_component.component_key != _TRADIFI_FINANCING_KEY
            or spec.financing_component.component_version != 1
            or spec.liquidation_audit_component not in expected_liquidations
            or spec.snapshot_projection_key != _TRADIFI_SNAPSHOT_KEY
            or spec.snapshot_projection_version != 1
        ):
            raise ValueError("unsupported Binance USD-M TradFi dispatcher spec")
        _margin_models(spec.margin_component)
        for name, digest in (
            ("config_hash", spec.config_hash),
            (
                "position component digest",
                spec.position_accounting_component.component_digest,
            ),
            ("financing component digest", spec.financing_component.component_digest),
            ("margin component digest", spec.margin_component.component_digest),
            (
                "liquidation component digest",
                spec.liquidation_audit_component.component_digest,
            ),
        ):
            _hash(name, digest)
        canonical_sha256(spec)
        self._spec = spec

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
        input_hash = canonical_sha256(
            {
                "operation": "linear_book_fill",
                "plan": plan,
                "fill": fill,
                "journal_hash": state_view.journal.journal_hash,
            }
        )
        payload = plan.position_payload
        if (
            plan.position_accounting_component
            != self.spec.position_accounting_component
            or plan.expected_fill_id != fill.fill_id
            or type(payload) is not LinearDerivativeFillAccountingPlan
            or len(plan.expected_artifact_roles) != 1
        ):
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                str(fill.fill_id),
            )

        prior_fills: list[Fill] = []
        for entry in state_view.journal.entries:
            if isinstance(entry, LinearDerivativeJournalEntry):
                if type(entry) is not LinearDerivativeJournalEntry:
                    return _failure(
                        self.spec,
                        plan.source_event_id,
                        input_hash,
                        FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                        "position_projection",
                    )
                if entry.request.transition.before.position_key == payload.position_key:
                    if entry.request.transition.before.contract != payload.contract:
                        return _failure(
                            self.spec,
                            plan.source_event_id,
                            input_hash,
                            FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                            "contract_mismatch",
                        )
                    prior_fills.append(entry.request.transition.fill)
        position_projector = (
            LinearPositionProjectorV2()
            if self.spec.margin_component == LinearAccountMarginProjectorV2().component_ref
            else LinearPositionProjector()
        )
        projected = position_projector.project(
            LinearPositionProjectionRequest(
                payload.position_key,
                payload.contract,
                tuple(prior_fills) + (fill,),
            )
        )
        if projected.result is None:
            projection_failure = projected.failure
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                getattr(
                    getattr(projection_failure, "code", None),
                    "value",
                    "position_projection",
                ),
                str(fill.fill_id),
            )
        accounting = LinearDerivativeAccounting().translate_position_fact(
            LinearDerivativeAccountingRequest(
                projected.result.transitions[-1],
                payload.settlement_cash_registration,
                payload.pnl_quantization,
                plan.fill_journal_entry_id,
                plan.fill_recorded_at,
            )
        )
        if accounting.result is None:
            accounting_failure = accounting.failure
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                getattr(
                    getattr(accounting_failure, "code", None),
                    "value",
                    "position_accounting",
                ),
                str(fill.fill_id),
            )
        result_payload = accounting.result
        artifact = FinancialDispatchArtifact(
            plan.expected_artifact_roles[0],
            plan.source_event_id,
            plan.fill_recorded_at,
            self.spec.position_accounting_component.component_key,
            self.spec.position_accounting_component.component_version,
            self.spec.position_accounting_component.component_digest,
            input_hash,
            result_payload.result_hash,
            result_payload,
        )
        result = FinancialDispatchResult(
            self.spec,
            plan.source_event_id,
            (result_payload.journal_entry,),
            state_view.position_lot_books,
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
                "fee_plan": plan.fee_plan,
                "fill": fill,
                "assessment": assessment,
                "journal_hash": state_view.journal.journal_hash,
                "ledger_state_hash": state_view.ledger_state.state_hash,
                "dispatcher_spec": self.spec,
            }
        )
        fee = plan.fee_plan
        payload = plan.position_payload
        if (
            plan.position_accounting_component
            != self.spec.position_accounting_component
            or type(payload) is not LinearDerivativeFillAccountingPlan
            or plan.expected_fill_id != fill.fill_id
            or fee.cash_key != payload.settlement_cash_registration.key
            or assessment.rule_set != fee.final_fee_rule_set
            or assessment.assessment.fee_assessment_id != fee.fee_assessment_id
            or assessment.assessment.assessment_time != fee.fee_assessment_time
            or assessment.basis.fills != (fill,)
        ):
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                str(fill.fill_id),
            )
        translated = FeeChargedJournalTranslator().translate(
            result=assessment,
            cash_key=fee.cash_key,
            journal_entry_id=fee.fee_journal_entry_id,
            recorded_at=fee.fee_recorded_at,
        )
        if translated.result is None:
            translation_failure = translated.failure
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                getattr(
                    getattr(translation_failure, "code", None),
                    "value",
                    "fee_accounting",
                ),
                str(fill.fill_id),
            )
        result = FinancialDispatchResult(
            self.spec,
            plan.source_event_id,
            (translated.result.journal_entry,),
            state_view.position_lot_books,
            (),
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def dispatch_scheduled_event(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        input_authority: dict[str, object] = {
            "operation": "dispatch_scheduled_event",
            "event": event,
            "journal_hash": state_view.journal.journal_hash,
            "ledger_state_hash": state_view.ledger_state.state_hash,
            "reservation_state_hash": state_view.reservation_state.state_hash,
        }
        if (
            state_view.window_start_journal_hash is not None
            or state_view.window_start_reservation_state_hash is not None
        ):
            input_authority.update(
                {
                    "window_start_journal_hash": (
                        state_view.window_start_journal_hash
                    ),
                    "window_start_reservation_state_hash": (
                        state_view.window_start_reservation_state_hash
                    ),
                }
            )
        input_hash = canonical_sha256(input_authority)
        try:
            if event.operation_key == "funding":
                return self._funding(event, state_view, input_hash)
            if event.operation_key == "margin_liquidation_audit":
                return self._margin_audit(event, state_view, input_hash)
            if event.operation_key == "margin_liquidation_audit_batch":
                return self._margin_audit_batch(event, state_view, input_hash)
        except (TypeError, ValueError):
            return _failure(
                self.spec,
                event.event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                event.operation_key,
            )
        return _failure(
            self.spec,
            event.event_id,
            input_hash,
            FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
            event.operation_key,
        )

    def _funding(
        self,
        event: ScheduledAccountEvent,
        state: FinancialStateView,
        input_hash: str,
    ) -> FinancialDispatchOutcome:
        payload = event.payload
        if (
            type(payload) is not LinearFundingAccountEventPlan
            or not payload.has_production_authority
            or canonical_bytes(event.semantic_payload)
            != canonical_bytes(payload.production_semantic_authority())
            or event.component_keys != (self.spec.financing_component.component_key,)
        ):
            return _failure(
                self.spec,
                event.event_id,
                input_hash,
                FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                "funding_authority",
            )
        if payload.funding_model_version is None:
            eligibility_role, accounting_role = (
                "funding_eligibility",
                "funding_accounting",
            )
        else:
            eligibility_role, accounting_role = _v2_funding_artifact_roles(
                payload.settlement_identity
            )
            if (
                payload.funding_model_version != 2
                or (
                    payload.funding_eligibility_role,
                    payload.funding_accounting_role,
                )
                != (eligibility_role, accounting_role)
            ):
                return _failure(
                    self.spec,
                    event.event_id,
                    input_hash,
                    FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                    "funding_artifact_roles",
                )
        if event.expected_artifact_roles != tuple(
            sorted((accounting_role, eligibility_role))
        ):
            return _failure(
                self.spec,
                event.event_id,
                input_hash,
                FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                "funding_authority",
            )
        ledger_schema = cast(LedgerSchema, payload.ledger_schema)
        settlement_cash_key = cast(CashBalanceKey, payload.settlement_cash_key)
        position_key = cast(PositionBalanceKey, payload.position_key)
        contract = cast(LinearPerpetualContract, payload.contract)
        eligibility_instant = cast(SimulationInstant, payload.eligibility_instant)
        snapshot_available_at = cast(
            SimulationInstant, payload.position_snapshot_available_at
        )
        snapshot_id = cast(str, payload.position_snapshot_id)
        series_id = cast(str, payload.eligibility_series_id)
        revision_id = cast(str, payload.position_revision_id)
        publications = cast(
            tuple[LinearFundingRatePublicationCandidate, ...],
            payload.publication_candidates,
        )
        settlement_evidence = cast(
            LinearFundingSettlementEvidence, payload.settlement_evidence
        )
        funding_mark_evidence = cast(
            LinearFundingMarkEvidence, payload.funding_mark_evidence
        )
        settlement_registration = cast(
            LedgerBalanceRegistration, payload.settlement_cash_registration
        )
        payment_quantization = cast(QuantizationPolicy, payload.payment_quantization)
        replay = _linear_replay(
            state.journal,
            ledger_schema,
            position_key,
            contract,
            settlement_cash_key,
            state.ledger_state,
        )
        slot = payload.settlement_identity.application_key.funding_slot_id
        if (
            slot.instrument_id != position_key.instrument_id
            or slot.target_funding_time != event.event_at.instant
            or settlement_evidence.effective_time != event.event_at.instant
            or settlement_evidence.applied_at != event.event_at
        ):
            raise ValueError("funding event context mismatch")
        cutoff = LinearDerivativeLedgerProjector().project(
            LinearDerivativeLedgerReplayRequest(
                AccountingJournal(
                    tuple(
                        entry
                        for entry in state.journal.entries
                        if entry.recorded_at < eligibility_instant
                    )
                ),
                ledger_schema,
                position_key,
                contract,
                settlement_cash_key,
            )
        )
        if cutoff.result is None:
            raise ValueError("funding eligibility cutoff replay failed")
        snapshot = LinearFundingEligibilityPositionSnapshot(
            snapshot_id,
            series_id,
            revision_id,
            payload.position_supersedes_revision_id,
            slot,
            eligibility_instant,
            snapshot_available_at,
            cutoff.result.cursor,
            replay,
            cutoff.result.position_state,
        )
        eligibility_request = LinearFundingEligibilityRequest(
            slot,
            position_key,
            contract,
            eligibility_instant,
            publications,
            snapshot,
            event.event_at,
        )
        eligibility = LinearFundingEligibilityResolver().resolve(eligibility_request)
        if eligibility.result is None:
            raise ValueError("funding eligibility failed")
        settlement_request = LinearFundingSettlementRequest(
            eligibility.result,
            settlement_evidence,
            funding_mark_evidence,
            payload.settlement_identity,
            position_key,
            contract,
            settlement_registration,
            payment_quantization,
        )
        assessed = LinearFundingAccounting().assess_financing(settlement_request)
        if assessed.result is None:
            raise ValueError("funding accounting failed")
        artifacts = _ordered_artifacts(
            event.expected_artifact_roles,
            (
                FinancialDispatchArtifact(
                    eligibility_role,
                    event.event_id,
                    event.event_at,
                    eligibility.result.component_ref.component_key,
                    eligibility.result.component_ref.component_version,
                    eligibility.result.component_ref.component_digest,
                    eligibility_request.request_hash,
                    eligibility.result.eligibility_hash,
                    eligibility.result,
                ),
                FinancialDispatchArtifact(
                    accounting_role,
                    event.event_id,
                    payload.recorded_at,
                    self.spec.financing_component.component_key,
                    self.spec.financing_component.component_version,
                    self.spec.financing_component.component_digest,
                    settlement_request.request_hash,
                    assessed.result.result_hash,
                    assessed.result,
                ),
            ),
        )
        return FinancialDispatchOutcome(
            self.spec,
            input_hash,
            result=FinancialDispatchResult(
                self.spec,
                event.event_id,
                (assessed.result.journal_entry,),
                state.position_lot_books,
                artifacts,
            ),
        )

    def _margin_audit(
        self,
        event: ScheduledAccountEvent,
        state: FinancialStateView,
        input_hash: str,
    ) -> FinancialDispatchOutcome:
        payload = event.payload
        if type(payload) is not LinearMarginLiquidationAuditPlan:
            raise TypeError("invalid margin audit payload")
        expected_roles = tuple(
            sorted(
                (
                    f"margin_projection.{payload.role_suffix}",
                    f"liquidation_audit.{payload.role_suffix}",
                )
            )
        )
        if (
            not payload.has_production_authority
            or canonical_bytes(event.semantic_payload)
            != canonical_bytes(payload.production_semantic_authority())
            or event.component_keys
            != tuple(
                sorted(
                    (
                        self.spec.margin_component.component_key,
                        self.spec.liquidation_audit_component.component_key,
                    )
                )
            )
            or event.expected_artifact_roles != expected_roles
        ):
            return _failure(
                self.spec,
                event.event_id,
                input_hash,
                FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                "margin_liquidation_authority",
            )
        projection_plan = cast(LinearMarginProjectionPlan, payload.projection_plan)
        liquidation_bars = cast(
            tuple[LinearLiquidationMarkBarEvidence, ...], payload.liquidation_bars
        )
        requested_grade = cast(RequestedResultGrade, payload.requested_grade)
        account_window_key = cast(str, payload.account_window_evidence_key)
        end_journal_hash = state.journal.journal_hash
        end_reservation_hash = state.reservation_state.state_hash
        if payload.uses_runtime_checkpoint:
            start_journal_hash = state.window_start_journal_hash
            start_reservation_hash = state.window_start_reservation_state_hash
        else:
            start_journal_hash = payload.interval_start_journal_hash
            end_journal_hash = cast(str, payload.interval_end_journal_hash)
            start_reservation_hash = payload.interval_start_reservation_hash
            end_reservation_hash = cast(str, payload.interval_end_reservation_hash)
        stable_window = (
            start_journal_hash == end_journal_hash
            and start_reservation_hash == end_reservation_hash
        )
        if (
            payload.audit_at != event.event_at
            or start_journal_hash is None
            or start_reservation_hash is None
            or state.journal.journal_hash != end_journal_hash
            or state.reservation_state.state_hash != end_reservation_hash
            or (not payload.uses_runtime_checkpoint and not stable_window)
        ):
            raise ValueError("liquidation account window state attestation mismatch")
        projection_state = state
        if payload.uses_runtime_checkpoint and not stable_window:
            if (
                state.window_start_journal is None
                or state.window_start_ledger_state is None
                or state.window_start_reservation_state is None
                or state.window_start_position_lot_books is None
            ):
                raise ValueError("liquidation runtime checkpoint state is missing")
            projection_state = FinancialStateView(
                state.window_start_journal,
                state.window_start_ledger_state,
                state.window_start_reservation_state,
                state.window_start_position_lot_books,
                state.artifacts,
            )
        projection = _linear_margin_projection(
            projection_plan, projection_state, self.spec.margin_component
        )
        window_source: dict[str, object] = {
            "type": "linear_liquidation_account_window_source",
            "schema_version": 1,
            "interval_start": payload.interval_start,
            "interval_end_exclusive": payload.interval_end_exclusive,
            "available_at": event.event_at,
            "journal_hash_at_start": start_journal_hash,
            "journal_hash_at_end": end_journal_hash,
            "reservation_hash_at_start": start_reservation_hash,
            "reservation_hash_at_end": end_reservation_hash,
            "ledger_state_hash_at_end": state.ledger_state.state_hash,
        }
        if payload.uses_runtime_checkpoint:
            window_source["window_start_at"] = payload.window_start_at
        window = LinearLiquidationAccountWindowEvidence(
            projection,
            payload.interval_start,
            payload.interval_end_exclusive,
            event.event_at,
            account_window_key,
            canonical_sha256(window_source),
        )
        request = LinearLiquidationAuditRequest(
            window,
            liquidation_bars,
            payload.audit_at,
            requested_grade,
        )
        audit = (
            ConservativeLinearLiquidationAuditModelV2().audit_liquidation(request)
            if (
                self.spec.liquidation_audit_component
                == ConservativeLinearLiquidationAuditModelV2().component_ref
            )
            else ConservativeLinearLiquidationAuditModel().audit_liquidation(request)
        )
        if audit.result is None:
            raise ValueError("liquidation audit failed")
        projection_role = f"margin_projection.{payload.role_suffix}"
        audit_role = f"liquidation_audit.{payload.role_suffix}"
        artifacts = _ordered_artifacts(
            event.expected_artifact_roles,
            (
                FinancialDispatchArtifact(
                    projection_role,
                    event.event_id,
                    event.event_at,
                    projection.component_ref.component_key,
                    projection.component_ref.component_version,
                    projection.component_ref.component_digest,
                    projection.request_hash,
                    projection.projection_hash,
                    projection,
                ),
                FinancialDispatchArtifact(
                    audit_role,
                    event.event_id,
                    event.event_at,
                    audit.result.component_ref.component_key,
                    audit.result.component_ref.component_version,
                    audit.result.component_ref.component_digest,
                    request.request_hash,
                    audit.result.result_hash,
                    audit.result,
                ),
            ),
        )
        return FinancialDispatchOutcome(
            self.spec,
            input_hash,
            result=FinancialDispatchResult(
                self.spec,
                event.event_id,
                (),
                state.position_lot_books,
                artifacts,
            ),
        )

    def _margin_audit_batch(self, event: ScheduledAccountEvent, state: FinancialStateView, input_hash: str) -> FinancialDispatchOutcome:
        payload = event.payload
        if type(payload) is not LinearMarginLiquidationAuditBatchPlan:
            raise TypeError("invalid margin audit batch payload")
        expected_roles = tuple(sorted(role for child in payload.subwindows for role in
                                      (f"margin_projection.{child.plan.role_suffix}", f"liquidation_audit.{child.plan.role_suffix}")))
        if (canonical_bytes(event.semantic_payload) != canonical_bytes(payload.production_semantic_authority())
                or event.component_keys != tuple(sorted((self.spec.margin_component.component_key, self.spec.liquidation_audit_component.component_key)) )
                or event.expected_artifact_roles != expected_roles):
            return _failure(self.spec, event.event_id, input_hash, FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH, "margin_liquidation_batch_authority")
        checkpoints = state.checkpoints
        if checkpoints is None:
            raise ValueError("batch checkpoint map is missing")
        artifacts: list[FinancialDispatchArtifact] = []
        # Each child is evaluated through the old authority path; append only after all succeed.
        for child in payload.subwindows:
            start = checkpoints.get((child.start_checkpoint, child.start_side))
            end = checkpoints.get((child.end_checkpoint, child.end_side))
            if start is None or end is None:
                raise ValueError("batch checkpoint binding is missing")
            view = FinancialStateView(end.journal, end.ledger_state, end.reservation_state,
                end.position_lot_books, end.artifacts,
                window_start_journal_hash=start.journal.journal_hash,
                window_start_reservation_state_hash=start.reservation_state.state_hash,
                window_start_journal=start.journal, window_start_ledger_state=start.ledger_state,
                window_start_reservation_state=start.reservation_state,
                window_start_position_lot_books=start.position_lot_books)
            single = ScheduledAccountEvent(event.event_id, event.event_at, "margin_liquidation_audit",
                tuple(sorted((self.spec.margin_component.component_key, self.spec.liquidation_audit_component.component_key))), (), child.plan,
                child.plan.production_semantic_authority(), tuple(sorted((f"margin_projection.{child.plan.role_suffix}", f"liquidation_audit.{child.plan.role_suffix}"))))
            outcome = self._margin_audit(single, view, input_hash)
            if outcome.failure is not None or outcome.result is None:
                raise ValueError("batch child audit failed")
            artifacts.extend(outcome.result.artifacts)
        return FinancialDispatchOutcome(self.spec, input_hash, result=FinancialDispatchResult(self.spec, event.event_id, (), state.position_lot_books, _ordered_artifacts(event.expected_artifact_roles, tuple(artifacts))))

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
                "reservation_state_hash": state_view.reservation_state.state_hash,
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
        snapshot_plan = plan.final_snapshot_payload
        projection_plan = getattr(snapshot_plan, "linear_margin_projection_plan", None)
        margin_role = getattr(snapshot_plan, "margin_projection_artifact_role", None)
        snapshot_role = getattr(snapshot_plan, "final_snapshot_artifact_role", None)
        if (
            type(projection_plan) is not LinearMarginProjectionPlan
            or type(margin_role) is not str
            or type(snapshot_role) is not str
            or getattr(snapshot_plan, "timestamp", None)
            != projection_plan.evaluated_at.instant
            or getattr(snapshot_plan, "reporting_currency", None)
            != projection_plan.settlement_cash_key.currency_id
            or getattr(snapshot_plan, "reporting_scale", None)
            != projection_plan.settlement_cash_registration.scale
            or tuple(sorted((margin_role, snapshot_role)))
            != tuple(
                role
                for role in plan.expected_artifact_roles
                if role in {margin_role, snapshot_role}
            )
        ):
            return _failure(
                self.spec,
                "engine-finalize",
                input_hash,
                FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE,
                "derivative_snapshot_authority",
            )
        snapshot_payload = cast(Any, snapshot_plan)
        try:
            projection = _linear_margin_projection(
                projection_plan, state_view, self.spec.margin_component
            )
            expected_marks = (
                (projection_plan.valuation_mark,)
                if projection.request.position_valuations
                else ()
            )
            projected_money = (
                projection.wallet_balance,
                projection.realized_pnl,
                projection.fees,
                projection.funding,
                *(value.unrealized_pnl for value in projection.position_unrealized_pnl),
                projection.total_unrealized_pnl,
                projection.equity,
                projection.total_initial_margin,
                projection.total_maintenance_margin,
                projection.working_order_margin_reservation,
                projection.available_margin,
            )
            if snapshot_payload.resolved_marks != expected_marks or any(
                value.scale != snapshot_payload.reporting_scale
                for value in projected_money
            ):
                raise ValueError("derivative snapshot reporting authority mismatch")
            snapshot = _derivative_snapshot(
                state_view,
                projection,
                snapshot_payload.timestamp,
                snapshot_payload.reporting_currency,
                snapshot_payload.currency_valuation_graph_hash,
            )
            artifacts = _ordered_artifacts(
                tuple(sorted((margin_role, snapshot_role))),
                (
                    FinancialDispatchArtifact(
                        margin_role,
                        "engine-finalize",
                        projection.request.evaluated_at,
                        projection.component_ref.component_key,
                        projection.component_ref.component_version,
                        projection.component_ref.component_digest,
                        projection.request_hash,
                        projection.projection_hash,
                        projection,
                    ),
                    FinancialDispatchArtifact(
                        snapshot_role,
                        "engine-finalize",
                        projection.request.evaluated_at,
                        self.spec.snapshot_projection_key,
                        self.spec.snapshot_projection_version,
                        self.spec.config_hash,
                        input_hash,
                        canonical_sha256(snapshot),
                        snapshot,
                    ),
                ),
            )
        except (TypeError, ValueError):
            return _failure(
                self.spec,
                "engine-finalize",
                input_hash,
                FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE,
                "derivative_snapshot_projection",
            )
        return FinancialDispatchOutcome(
            self.spec,
            input_hash,
            result=FinancialDispatchResult(
                self.spec,
                "engine-finalize",
                (),
                state_view.position_lot_books,
                artifacts,
                snapshot,
            ),
        )


def financial_dispatcher_for_spec(
    spec: FinancialDispatcherSpec,
) -> FinancialEventDispatcher:
    if type(spec) is not FinancialDispatcherSpec:
        raise TypeError("spec must be exact FinancialDispatcherSpec")
    if spec == default_cash_financial_dispatcher_spec():
        return DefaultCashFinancialDispatcher()
    return BinanceUsdmTradifiLinearFinancialDispatcher(spec)


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
            lots_by_position = _position_lot_books_from_ledger(state_view.ledger_state)
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
        if (
            payload.cost_basis_policy.policy_version >= 2
            and not booked.result.open_lots
        ):
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


def financial_dispatcher_owns_fee_accounting(
    dispatcher: object,
    plan: FillAccountingDispatchPlan,
) -> bool:
    if type(plan) is not FillAccountingDispatchPlan:
        return False
    payload = plan.position_payload
    if type(payload) is CashFillAccountingPlan:
        return payload.cost_basis_policy.policy_version >= 2
    return (
        isinstance(dispatcher, BinanceUsdmTradifiLinearFinancialDispatcher)
        and type(payload) is LinearDerivativeFillAccountingPlan
    )


__all__ = [
    "BinanceUsdmTradifiLinearFinancialDispatcher",
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
    "LinearDerivativeFillAccountingPlan",
    "LinearFundingAccountEventPlan",
    "LinearMarginLiquidationAuditBatchPlan",
    "LinearMarginLiquidationAuditSubwindowPlan",
    "LinearMarginLiquidationAuditPlan",
    "LinearMarginProjectionPlan",
    "ScheduledAccountEvent",
    "default_cash_financial_dispatcher_spec",
    "financial_dispatcher_for_spec",
    "financial_dispatcher_owns_fee_accounting",
]
