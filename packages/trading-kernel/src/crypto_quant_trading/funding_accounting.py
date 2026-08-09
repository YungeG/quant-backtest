"""Exact linear funding settlement accounting and full-Journal replay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import gcd
import re
from typing import Any

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    IdentityNamespace,
    Money,
    PositionBalanceKey,
    PricePurpose,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
    derive_domain_id,
    round_ratio,
)

from .derivatives import LinearPerpetualContract
from .funding import FundingSlotId, LinearFundingEligibility
from .journal import AccountingJournal, JournalReplayCursor
from .ledger import (
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
)
from .marks import ResolvedMark, StaleMarkPolicy
from .ports import ProfileComponentRef, ProfilePortOutcome, ProfilePortType

_SCHEMA_VERSION = 1
_COMPONENT_KEY = "instrument.linear-perpetual.funding-accounting.v1"
_RATE_BASIS = "funding_fraction_of_notional"
_SHA256 = r"sha256:[0-9a-f]{64}"


def _require_text(name: str, value: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")


def _require_hash(name: str, value: str) -> None:
    if type(value) is not str or re.fullmatch(_SHA256, value) is None:
        raise ValueError(f"{name} must be a canonical sha256 hash")


def _require_simulation_instant(name: str, value: SimulationInstant) -> None:
    if type(value) is not SimulationInstant or type(value.instant) is not UtcInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")


def _require_position_key(value: PositionBalanceKey) -> None:
    if type(value) is not PositionBalanceKey:
        raise TypeError("position_key must be exact PositionBalanceKey")


def _require_registration(value: LedgerBalanceRegistration) -> None:
    if type(value) is not LedgerBalanceRegistration:
        raise TypeError(
            "settlement_cash_registration must be exact LedgerBalanceRegistration"
        )
    if type(value.scale) is not Scale:
        raise TypeError("settlement Cash registration Scale must be exact Scale")


def _require_quantization(value: QuantizationPolicy) -> None:
    if type(value) is not QuantizationPolicy:
        raise TypeError("payment_quantization must be exact QuantizationPolicy")
    if type(value.target_scale) is not Scale or type(value.rounding) is not RoundingPolicy:
        raise TypeError("payment_quantization fields must use exact domain types")


def _component_ref() -> ProfileComponentRef:
    digest = canonical_sha256(
        {
            "type": "linear_funding_accounting_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "algorithm_key": "linear-funding-settlement-accounting-v1",
            "application_key": "account_id+funding_slot_id",
            "settlement_id_kind": "settlement",
            "journal_id_kind": "journal",
            "identity_ordinal": 0,
            "rate_basis": _RATE_BASIS,
            "mark_purpose": "funding",
            "formula": "-(signed_quantity*multiplier*mark*rate)",
            "quantization": "one_round_ratio_per_application",
            "effective_time": "slot.target_funding_time",
            "recorded_at": "settlement.applied_at",
            "allowed_grade": "development",
        }
    )
    return ProfileComponentRef(ProfilePortType.FINANCING_MODEL, _COMPONENT_KEY, 1, digest)


@dataclass(frozen=True, slots=True)
class LinearFundingApplicationKey:
    account_id: str
    funding_slot_id: FundingSlotId
    value: str

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        if type(self.funding_slot_id) is not FundingSlotId:
            raise TypeError("funding_slot_id must be exact FundingSlotId")
        _require_text("value", self.value)
        if self.value != self._expected_value(self.account_id, self.funding_slot_id):
            raise ValueError("funding Application value must match semantic key")

    @staticmethod
    def _expected_value(account_id: str, funding_slot_id: FundingSlotId) -> str:
        digest = canonical_sha256(
            {
                "type": "linear_funding_application_semantic_key",
                "schema_version": _SCHEMA_VERSION,
                "account_id": account_id,
                "funding_slot_id": funding_slot_id,
            }
        )
        return "funding-application-v1:" + digest.removeprefix("sha256:")

    @classmethod
    def derive(
        cls, account_id: str, funding_slot_id: FundingSlotId
    ) -> LinearFundingApplicationKey:
        return cls(
            account_id,
            funding_slot_id,
            cls._expected_value(account_id, funding_slot_id),
        )

    @property
    def application_key_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_application_key",
            "schema_version": _SCHEMA_VERSION,
            "account_id": self.account_id,
            "slot_id": self.funding_slot_id,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingApplicationIdentity:
    application_key: LinearFundingApplicationKey
    identity_namespace: IdentityNamespace
    semantic_run_id: str
    settlement_id: DomainId
    journal_entry_id: DomainId

    def __post_init__(self) -> None:
        if type(self.application_key) is not LinearFundingApplicationKey:
            raise TypeError("application_key must be exact LinearFundingApplicationKey")
        if type(self.identity_namespace) is not IdentityNamespace:
            raise TypeError("identity_namespace must be exact IdentityNamespace")
        _require_text("semantic_run_id", self.semantic_run_id)
        if (self.settlement_id, self.journal_entry_id) != self._derived_ids(
            self.application_key, self.identity_namespace, self.semantic_run_id
        ):
            raise ValueError("application identity must use derived IDs")

    @staticmethod
    def _derived_ids(
        application_key: LinearFundingApplicationKey,
        identity_namespace: IdentityNamespace,
        semantic_run_id: str,
    ) -> tuple[DomainId, DomainId]:
        semantic_key = application_key.value.encode("utf-8")
        return (
            derive_domain_id(
                namespace=identity_namespace,
                kind=DomainIdKind.SETTLEMENT,
                semantic_run_id=semantic_run_id,
                semantic_key=semantic_key,
                ordinal=0,
            ),
            derive_domain_id(
                namespace=identity_namespace,
                kind=DomainIdKind.JOURNAL,
                semantic_run_id=semantic_run_id,
                semantic_key=semantic_key,
                ordinal=0,
            ),
        )

    @classmethod
    def derive(
        cls,
        application_key: LinearFundingApplicationKey,
        identity_namespace: IdentityNamespace,
        semantic_run_id: str,
    ) -> LinearFundingApplicationIdentity:
        settlement_id, journal_entry_id = cls._derived_ids(
            application_key, identity_namespace, semantic_run_id
        )
        return cls(
            application_key,
            identity_namespace,
            semantic_run_id,
            settlement_id,
            journal_entry_id,
        )

    @property
    def identity_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        namespace = self.identity_namespace
        return {
            "type": "linear_funding_application_identity",
            "schema_version": _SCHEMA_VERSION,
            "application_key": self.application_key,
            "identity_namespace": {
                "value": namespace.value,
                "version": namespace.version,
                "algorithm": namespace.algorithm,
            },
            "semantic_run_id": self.semantic_run_id,
            "settlement_id": self.settlement_id,
            "journal_entry_id": self.journal_entry_id,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingMarkEvidence:
    resolved_mark: ResolvedMark
    stale_policy: StaleMarkPolicy

    def __post_init__(self) -> None:
        if type(self.resolved_mark) is not ResolvedMark:
            raise TypeError("resolved_mark must be exact ResolvedMark")
        if type(self.stale_policy) is not StaleMarkPolicy:
            raise TypeError("stale_policy must be exact StaleMarkPolicy")

    @property
    def mark_evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_mark_evidence",
            "schema_version": _SCHEMA_VERSION,
            "resolved_mark": self.resolved_mark,
            "stale_policy": self.stale_policy,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingSettlementEvidence:
    application_key: LinearFundingApplicationKey
    effective_time: UtcInstant
    applied_at: SimulationInstant
    applied_rate: Rate
    event_id: str
    event_hash: str
    revision_id: str
    supersedes_revision_id: str | None
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        if type(self.application_key) is not LinearFundingApplicationKey:
            raise TypeError("application_key must be exact LinearFundingApplicationKey")
        if type(self.effective_time) is not UtcInstant:
            raise TypeError("effective_time must be exact UtcInstant")
        _require_simulation_instant("applied_at", self.applied_at)
        if type(self.applied_rate) is not Rate:
            raise TypeError("applied_rate must be exact Rate")
        _require_text("event_id", self.event_id)
        _require_hash("event_hash", self.event_hash)
        _require_text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _require_text("supersedes_revision_id", self.supersedes_revision_id)
        _require_text("source_key", self.source_key)
        _require_hash("source_hash", self.source_hash)

    @property
    def settlement_evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_settlement_evidence",
            "schema_version": _SCHEMA_VERSION,
            "application_key": self.application_key,
            "effective_time": self.effective_time,
            "applied_at": self.applied_at,
            "applied_rate": self.applied_rate,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class ExactLinearFundingCashFlow:
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
            raise ValueError("Funding cash flow must be GCD-reduced")

    @property
    def cash_flow_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "exact_linear_funding_cash_flow",
            "schema_version": _SCHEMA_VERSION,
            "currency_id": self.currency_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingSettlementRequest:
    eligibility: LinearFundingEligibility | None
    settlement_evidence: LinearFundingSettlementEvidence | None
    funding_mark_evidence: LinearFundingMarkEvidence | None
    application_identity: LinearFundingApplicationIdentity
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    settlement_cash_registration: LedgerBalanceRegistration
    payment_quantization: QuantizationPolicy

    def __post_init__(self) -> None:
        if type(self.eligibility) not in (type(None), LinearFundingEligibility):
            raise TypeError("eligibility must be exact LinearFundingEligibility or None")
        if type(self.settlement_evidence) not in (
            type(None),
            LinearFundingSettlementEvidence,
        ):
            raise TypeError(
                "settlement_evidence must be exact LinearFundingSettlementEvidence or None"
            )
        if type(self.funding_mark_evidence) not in (
            type(None),
            LinearFundingMarkEvidence,
        ):
            raise TypeError(
                "funding_mark_evidence must be exact LinearFundingMarkEvidence or None"
            )
        if type(self.application_identity) is not LinearFundingApplicationIdentity:
            raise TypeError(
                "application_identity must be exact LinearFundingApplicationIdentity"
            )
        _require_position_key(self.position_key)
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        _require_registration(self.settlement_cash_registration)
        _require_quantization(self.payment_quantization)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_settlement_request",
            "schema_version": _SCHEMA_VERSION,
            "eligibility": self.eligibility,
            "settlement_evidence": self.settlement_evidence,
            "funding_mark_evidence": self.funding_mark_evidence,
            "application_identity": self.application_identity,
            "position_key": self.position_key,
            "contract": self.contract,
            "settlement_cash_registration": self.settlement_cash_registration,
            "payment_quantization": self.payment_quantization,
        }


class LinearFundingSettlementFailureCode(str, Enum):
    MISSING_ELIGIBILITY = "missing_eligibility"
    MISSING_SETTLEMENT_EVIDENCE = "missing_settlement_evidence"
    MISSING_FUNDING_MARK = "missing_funding_mark"
    SLOT_CONTEXT_MISMATCH = "slot_context_mismatch"
    POSITION_CONTEXT_MISMATCH = "position_context_mismatch"
    UNSUPPORTED_RATE_BASIS = "unsupported_rate_basis"
    APPLIED_RATE_MISMATCH = "applied_rate_mismatch"
    INVALID_SETTLEMENT_EFFECTIVE_TIME = "invalid_settlement_effective_time"
    SETTLEMENT_EVIDENCE_NOT_AVAILABLE = "settlement_evidence_not_available"
    FUNDING_MARK_PURPOSE_MISMATCH = "funding_mark_purpose_mismatch"
    FUNDING_MARK_CONTEXT_MISMATCH = "funding_mark_context_mismatch"
    FUNDING_MARK_INSTANT_MISMATCH = "funding_mark_instant_mismatch"
    FUNDING_MARK_SCALE_MISMATCH = "funding_mark_scale_mismatch"
    NON_POSITIVE_FUNDING_MARK = "non_positive_funding_mark"
    FUNDING_MARK_POLICY_MISMATCH = "funding_mark_policy_mismatch"
    FUNDING_MARK_NOT_AVAILABLE = "funding_mark_not_available"
    SETTLEMENT_CASH_CONTEXT_MISMATCH = "settlement_cash_context_mismatch"
    QUANTIZATION_SCALE_MISMATCH = "quantization_scale_mismatch"


def _first_failure(
    request: LinearFundingSettlementRequest,
) -> LinearFundingSettlementFailureCode | None:
    eligibility = request.eligibility
    settlement = request.settlement_evidence
    mark_evidence = request.funding_mark_evidence
    if eligibility is None:
        return LinearFundingSettlementFailureCode.MISSING_ELIGIBILITY
    if settlement is None:
        return LinearFundingSettlementFailureCode.MISSING_SETTLEMENT_EVIDENCE
    if mark_evidence is None:
        return LinearFundingSettlementFailureCode.MISSING_FUNDING_MARK

    identity = request.application_identity
    application_key = identity.application_key
    slot = application_key.funding_slot_id
    if (
        eligibility.slot_id != slot
        or eligibility.request.slot_id != slot
        or settlement.application_key.funding_slot_id != slot
        or settlement.application_key != application_key
        or slot.instrument_id != request.contract.instrument.instrument_id
    ):
        return LinearFundingSettlementFailureCode.SLOT_CONTEXT_MISMATCH

    position_key = request.position_key
    position_state = eligibility.position_state
    if (
        application_key.account_id != position_key.account_id
        or position_key.venue_id != request.contract.instrument.instrument_id.venue
        or position_key.instrument_id != request.contract.instrument.instrument_id
        or eligibility.request.position_key != position_key
        or position_state.position_key != position_key
        or request.contract != eligibility.request.contract
        or request.contract != position_state.contract
    ):
        return LinearFundingSettlementFailureCode.POSITION_CONTEXT_MISMATCH
    if (
        eligibility.published_rate.basis != _RATE_BASIS
        or settlement.applied_rate.basis != _RATE_BASIS
    ):
        return LinearFundingSettlementFailureCode.UNSUPPORTED_RATE_BASIS
    if settlement.applied_rate != eligibility.published_rate:
        return LinearFundingSettlementFailureCode.APPLIED_RATE_MISMATCH
    if settlement.effective_time != slot.target_funding_time:
        return LinearFundingSettlementFailureCode.INVALID_SETTLEMENT_EFFECTIVE_TIME
    if settlement.applied_at < eligibility.captured_at:
        return LinearFundingSettlementFailureCode.SETTLEMENT_EVIDENCE_NOT_AVAILABLE

    mark = mark_evidence.resolved_mark
    policy = mark_evidence.stale_policy
    if (
        mark.price_purpose is not PricePurpose.FUNDING
        or policy.price_purpose is not PricePurpose.FUNDING
    ):
        return LinearFundingSettlementFailureCode.FUNDING_MARK_PURPOSE_MISMATCH
    if (
        mark.instrument_id != request.contract.instrument.instrument_id
        or mark.quote_currency_id != request.contract.instrument.settlement_currency
    ):
        return LinearFundingSettlementFailureCode.FUNDING_MARK_CONTEXT_MISMATCH
    if mark.resolved_at != slot.target_funding_time:
        return LinearFundingSettlementFailureCode.FUNDING_MARK_INSTANT_MISMATCH
    if mark.price.scale != request.contract.price_scale:
        return LinearFundingSettlementFailureCode.FUNDING_MARK_SCALE_MISMATCH
    if mark.price.units <= 0:
        return LinearFundingSettlementFailureCode.NON_POSITIVE_FUNDING_MARK
    expected_age = (
        mark.resolved_at.epoch_nanoseconds - mark.observed_at.epoch_nanoseconds
    )
    if (
        mark.stale_policy_key != policy.policy_key
        or mark.stale_policy_version != policy.policy_version
        or mark.stale_policy_hash != policy.policy_hash
        or mark.age_nanoseconds != expected_age
        or mark.age_nanoseconds > policy.max_age_nanoseconds
        or (mark.age_nanoseconds > 0 and not policy.allow_forward_fill)
    ):
        return LinearFundingSettlementFailureCode.FUNDING_MARK_POLICY_MISMATCH
    if mark.available_at > settlement.applied_at.instant:
        return LinearFundingSettlementFailureCode.FUNDING_MARK_NOT_AVAILABLE

    registration = request.settlement_cash_registration
    expected_cash_key = CashBalanceKey(
        application_key.account_id,
        position_key.venue_id,
        request.contract.instrument.settlement_currency,
    )
    if type(registration.key) is not CashBalanceKey or registration.key != expected_cash_key:
        return LinearFundingSettlementFailureCode.SETTLEMENT_CASH_CONTEXT_MISMATCH
    if request.payment_quantization.target_scale != registration.scale:
        return LinearFundingSettlementFailureCode.QUANTIZATION_SCALE_MISMATCH
    return None


def _exact_cash_flow(
    request: LinearFundingSettlementRequest,
) -> ExactLinearFundingCashFlow:
    eligibility = request.eligibility
    settlement = request.settlement_evidence
    mark_evidence = request.funding_mark_evidence
    if eligibility is None or settlement is None or mark_evidence is None:
        raise AssertionError("successful Funding accounting requires complete evidence")
    quantity = eligibility.position_state.quantity
    multiplier = request.contract.contract_multiplier
    mark = mark_evidence.resolved_mark.price
    rate = settlement.applied_rate
    numerator = -(quantity.units * multiplier.units * mark.units * rate.units)
    denominator = (
        quantity.scale.factor
        * multiplier.scale.factor
        * mark.scale.factor
        * rate.scale.factor
    )
    divisor = gcd(abs(numerator), denominator)
    return ExactLinearFundingCashFlow(
        request.contract.instrument.settlement_currency,
        numerator // divisor,
        denominator // divisor,
    )


def _payment(
    exact: ExactLinearFundingCashFlow, policy: QuantizationPolicy
) -> Money:
    return Money(
        round_ratio(
            exact.numerator * policy.target_scale.factor,
            exact.denominator,
            policy.rounding,
        ),
        policy.target_scale,
        str(exact.currency_id),
    )


def _application_body_hash(
    request: LinearFundingSettlementRequest,
    exact: ExactLinearFundingCashFlow,
    payment: Money,
) -> str:
    return canonical_sha256(
        {
            "type": "linear_funding_application_body",
            "schema_version": _SCHEMA_VERSION,
            "application_key": request.application_identity.application_key,
            "eligibility": request.eligibility,
            "settlement_evidence": request.settlement_evidence,
            "funding_mark_evidence": request.funding_mark_evidence,
            "position_key": request.position_key,
            "contract": request.contract,
            "settlement_cash_registration": request.settlement_cash_registration,
            "payment_quantization": request.payment_quantization,
            "exact_cash_flow": exact,
            "payment": payment,
        }
    )


def _source_ids(request: LinearFundingSettlementRequest) -> tuple[str, ...]:
    eligibility = request.eligibility
    settlement = request.settlement_evidence
    mark_evidence = request.funding_mark_evidence
    if eligibility is None or settlement is None or mark_evidence is None:
        raise AssertionError("successful Funding accounting requires complete evidence")
    identity = request.application_identity
    mark = mark_evidence.resolved_mark
    return tuple(
        sorted(
            set(
                (
                    identity.application_key.value,
                    identity.settlement_id.value,
                    eligibility.slot_id.value,
                    eligibility.eligibility_hash,
                    eligibility.publication_hash,
                    eligibility.event_id,
                    eligibility.event_hash,
                    eligibility.publication_revision_id,
                    eligibility.snapshot_hash,
                    eligibility.state_hash,
                    mark.mark_id,
                    mark_evidence.stale_policy.policy_hash,
                    settlement.event_id,
                    settlement.event_hash,
                    settlement.revision_id,
                    settlement.source_key,
                    settlement.source_hash,
                    request.request_hash,
                )
            )
        )
    )


def _entry_values(
    request: LinearFundingSettlementRequest,
) -> tuple[
    ExactLinearFundingCashFlow,
    Money,
    str,
    tuple[str, ...],
    tuple[BalanceChange, ...],
    tuple[Money, ...],
]:
    exact = _exact_cash_flow(request)
    payment = _payment(exact, request.payment_quantization)
    application_body_hash = _application_body_hash(request, exact, payment)
    changes: tuple[BalanceChange, ...] = ()
    financing: tuple[Money, ...] = ()
    if payment.units != 0:
        cash_key = request.settlement_cash_registration.key
        if type(cash_key) is not CashBalanceKey:
            raise AssertionError("successful Funding accounting requires Cash registration")
        changes = (BalanceChange(cash_key, payment),)
        financing = (payment,)
    return exact, payment, application_body_hash, _source_ids(request), changes, financing


@dataclass(frozen=True, slots=True)
class LinearFundingJournalEntry(AccountingJournalEntry):
    component_ref: ProfileComponentRef
    request: LinearFundingSettlementRequest
    request_hash: str
    application_key: LinearFundingApplicationKey
    settlement_id: DomainId
    exact_cash_flow: ExactLinearFundingCashFlow
    payment: Money
    application_body_hash: str

    def __post_init__(self) -> None:
        AccountingJournalEntry.__post_init__(self)
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Funding accounting component")
        if type(self.request) is not LinearFundingSettlementRequest:
            raise TypeError("request must be exact LinearFundingSettlementRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if _first_failure(self.request) is not None:
            raise ValueError("Funding Journal entry requires a successful Request")
        values = _entry_values(self.request)
        exact, payment, body_hash, source_ids, changes, financing = values
        settlement = self.request.settlement_evidence
        if settlement is None:
            raise AssertionError("successful Request requires Settlement evidence")
        expected = (
            self.request.application_identity.journal_entry_id,
            AccountingEntryType.FUNDING_APPLIED,
            self.application_key.account_id,
            self.request.position_key.venue_id,
            self.application_key.funding_slot_id.target_funding_time,
            settlement.applied_at,
            source_ids,
            changes,
            (),
            (),
            financing,
            self.request.application_identity.application_key,
            self.request.application_identity.settlement_id,
            exact,
            payment,
            body_hash,
        )
        actual = (
            self.journal_entry_id,
            self.entry_type,
            self.account_id,
            self.venue_id,
            self.effective_time,
            self.recorded_at,
            self.source_ids,
            self.balance_changes,
            self.realized_pnl,
            self.fees,
            self.financing,
            self.application_key,
            self.settlement_id,
            self.exact_cash_flow,
            self.payment,
            self.application_body_hash,
        )
        if actual != expected:
            raise ValueError("Funding Journal entry fields must match embedded Request")

    @property
    def funding_entry_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_journal_entry",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "application_key": self.application_key,
            "settlement_id": self.settlement_id,
            "exact_cash_flow": self.exact_cash_flow,
            "payment": self.payment,
            "application_body_hash": self.application_body_hash,
            "journal_entry": AccountingJournalEntry.to_canonical_dict(self),
        }


def _journal_entry(
    component_ref: ProfileComponentRef,
    request: LinearFundingSettlementRequest,
) -> LinearFundingJournalEntry:
    exact, payment, body_hash, source_ids, changes, financing = _entry_values(request)
    settlement = request.settlement_evidence
    if settlement is None:
        raise AssertionError("successful Request requires Settlement evidence")
    identity = request.application_identity
    return LinearFundingJournalEntry(
        journal_entry_id=identity.journal_entry_id,
        entry_type=AccountingEntryType.FUNDING_APPLIED,
        account_id=identity.application_key.account_id,
        venue_id=request.position_key.venue_id,
        effective_time=identity.application_key.funding_slot_id.target_funding_time,
        recorded_at=settlement.applied_at,
        source_ids=source_ids,
        balance_changes=changes,
        realized_pnl=(),
        fees=(),
        financing=financing,
        component_ref=component_ref,
        request=request,
        request_hash=request.request_hash,
        application_key=identity.application_key,
        settlement_id=identity.settlement_id,
        exact_cash_flow=exact,
        payment=payment,
        application_body_hash=body_hash,
    )


def _validate_settlement_evidence(
    component_ref: ProfileComponentRef,
    request: LinearFundingSettlementRequest,
    request_hash: str,
) -> None:
    if component_ref != _component_ref():
        raise ValueError("component_ref must match Funding accounting component")
    if type(request) is not LinearFundingSettlementRequest:
        raise TypeError("request must be exact LinearFundingSettlementRequest")
    if request_hash != request.request_hash:
        raise ValueError("request_hash must match embedded Request")


@dataclass(frozen=True, slots=True)
class LinearFundingSettlementResult:
    component_ref: ProfileComponentRef
    request: LinearFundingSettlementRequest
    request_hash: str
    application_key: LinearFundingApplicationKey
    exact_cash_flow: ExactLinearFundingCashFlow
    payment: Money
    journal_entry: LinearFundingJournalEntry

    def __post_init__(self) -> None:
        _validate_settlement_evidence(
            self.component_ref, self.request, self.request_hash
        )
        if _first_failure(self.request) is not None:
            raise ValueError("Result Request must have no business failure")
        expected_entry = _journal_entry(self.component_ref, self.request)
        expected = (
            self.request.application_identity.application_key,
            expected_entry.exact_cash_flow,
            expected_entry.payment,
            expected_entry,
        )
        if (
            self.application_key,
            self.exact_cash_flow,
            self.payment,
            self.journal_entry,
        ) != expected:
            raise ValueError("Result fields must match embedded Request")
        if type(self.journal_entry) is not LinearFundingJournalEntry:
            raise TypeError("journal_entry must be exact LinearFundingJournalEntry")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_settlement_result",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "application_key": self.application_key,
            "exact_cash_flow": self.exact_cash_flow,
            "payment": self.payment,
            "journal_entry": self.journal_entry,
        }


def _failure_subject_ids(
    request: LinearFundingSettlementRequest,
    code: LinearFundingSettlementFailureCode,
) -> tuple[str, ...]:
    eligibility = request.eligibility
    mark = request.funding_mark_evidence
    settlement = request.settlement_evidence
    identity = request.application_identity
    return (
        code.value,
        identity.application_key.value,
        identity.settlement_id.value,
        identity.journal_entry_id.value,
        eligibility.eligibility_hash
        if eligibility is not None
        else "missing-funding-eligibility",
        mark.resolved_mark.mark_id if mark is not None else "missing-funding-mark",
        settlement.event_id
        if settlement is not None
        else "missing-funding-settlement",
    )


@dataclass(frozen=True, slots=True)
class LinearFundingSettlementFailure:
    component_ref: ProfileComponentRef
    request: LinearFundingSettlementRequest
    request_hash: str
    code: LinearFundingSettlementFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_settlement_evidence(
            self.component_ref, self.request, self.request_hash
        )
        if type(self.code) is not LinearFundingSettlementFailureCode:
            raise TypeError("code must be exact LinearFundingSettlementFailureCode")
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be an exact tuple of strings")
        expected = _first_failure(self.request)
        if expected is None or self.code is not expected:
            raise ValueError("failure must match first Request failure")
        if self.subject_ids != _failure_subject_ids(self.request, self.code):
            raise ValueError("subject_ids must match embedded Request")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_settlement_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingAccounting:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref()

    def assess_financing(
        self, request: LinearFundingSettlementRequest, /
    ) -> ProfilePortOutcome[
        LinearFundingSettlementResult, LinearFundingSettlementFailure
    ]:
        if type(request) is not LinearFundingSettlementRequest:
            raise TypeError("request must be exact LinearFundingSettlementRequest")
        code = _first_failure(request)
        if code is not None:
            failure = LinearFundingSettlementFailure(
                self.component_ref,
                request,
                request.request_hash,
                code,
                _failure_subject_ids(request, code),
            )
            return ProfilePortOutcome.for_failure(self.component_ref, request, failure)
        entry = _journal_entry(self.component_ref, request)
        result = LinearFundingSettlementResult(
            self.component_ref,
            request,
            request.request_hash,
            request.application_identity.application_key,
            entry.exact_cash_flow,
            entry.payment,
            entry,
        )
        return ProfilePortOutcome.for_result(self.component_ref, request, result)


class LinearFundingJournalReplayFailureCode(str, Enum):
    UNAUTHORIZED_FUNDING_ENTRY = "unauthorized_funding_entry"
    DUPLICATE_FUNDING_APPLICATION = "duplicate_funding_application"
    CONFLICTING_FUNDING_APPLICATION = "conflicting_funding_application"


@dataclass(frozen=True, slots=True)
class LinearFundingJournalReplayRequest:
    journal: AccountingJournal
    ledger_schema: LedgerSchema

    def __post_init__(self) -> None:
        if type(self.journal) is not AccountingJournal:
            raise TypeError("journal must be exact AccountingJournal")
        if type(self.ledger_schema) is not LedgerSchema:
            raise TypeError("ledger_schema must be exact LedgerSchema")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_journal_replay_request",
            "schema_version": _SCHEMA_VERSION,
            "journal": self.journal,
            "ledger_schema": self.ledger_schema,
        }


type _ReplayFailure = tuple[LinearFundingJournalReplayFailureCode, tuple[str, ...]]
type _ReplaySuccess = tuple[
    JournalReplayCursor,
    tuple[LinearFundingApplicationKey, ...],
    tuple[DomainId, ...],
    LedgerState,
]


def _evaluate_replay(
    request: LinearFundingJournalReplayRequest,
) -> tuple[_ReplayFailure | None, _ReplaySuccess | None]:
    for index, entry in enumerate(request.journal.entries):
        if (
            entry.entry_type is AccountingEntryType.FUNDING_APPLIED
            and type(entry) is not LinearFundingJournalEntry
        ):
            code = LinearFundingJournalReplayFailureCode.UNAUTHORIZED_FUNDING_ENTRY
            return (
                code,
                (
                    code.value,
                    str(index),
                    entry.journal_entry_id.value,
                    entry.entry_type.value,
                ),
            ), None

    seen: dict[str, LinearFundingJournalEntry] = {}
    applications: list[LinearFundingApplicationKey] = []
    journal_ids: list[DomainId] = []
    for entry in request.journal.entries:
        if type(entry) is not LinearFundingJournalEntry:
            continue
        key = entry.application_key.value
        first = seen.get(key)
        if first is not None:
            code = (
                LinearFundingJournalReplayFailureCode.DUPLICATE_FUNDING_APPLICATION
                if first.application_body_hash == entry.application_body_hash
                else LinearFundingJournalReplayFailureCode.CONFLICTING_FUNDING_APPLICATION
            )
            return (
                code,
                (
                    code.value,
                    key,
                    first.journal_entry_id.value,
                    entry.journal_entry_id.value,
                ),
            ), None
        seen[key] = entry
        applications.append(entry.application_key)
        journal_ids.append(entry.journal_entry_id)

    ledger_state = GenericLedger(request.ledger_schema).project(request.journal)
    return None, (
        request.journal.cursor_at(request.journal.entry_count),
        tuple(applications),
        tuple(journal_ids),
        ledger_state,
    )


@dataclass(frozen=True, slots=True)
class LinearFundingJournalProjection:
    component_ref: ProfileComponentRef
    request: LinearFundingJournalReplayRequest
    request_hash: str
    journal_cursor: JournalReplayCursor
    application_keys: tuple[LinearFundingApplicationKey, ...]
    journal_entry_ids: tuple[DomainId, ...]
    ledger_state: LedgerState

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Funding accounting component")
        if type(self.request) is not LinearFundingJournalReplayRequest:
            raise TypeError("request must be exact LinearFundingJournalReplayRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if type(self.journal_cursor) is not JournalReplayCursor:
            raise TypeError("journal_cursor must be exact JournalReplayCursor")
        if type(self.application_keys) is not tuple or not all(
            type(value) is LinearFundingApplicationKey
            for value in self.application_keys
        ):
            raise TypeError("application_keys must contain exact Application Keys")
        if type(self.journal_entry_ids) is not tuple or not all(
            type(value) is DomainId and value.kind is DomainIdKind.JOURNAL
            for value in self.journal_entry_ids
        ):
            raise TypeError("journal_entry_ids must contain exact Journal Domain IDs")
        if type(self.ledger_state) is not LedgerState:
            raise TypeError("ledger_state must be exact LedgerState")
        failure, expected = _evaluate_replay(self.request)
        if failure is not None or expected is None:
            raise ValueError("Projection Request must replay successfully")
        if (
            self.journal_cursor,
            self.application_keys,
            self.journal_entry_ids,
            self.ledger_state,
        ) != expected:
            raise ValueError("Projection fields must match replayed Journal")

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_journal_projection",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "journal_cursor": self.journal_cursor,
            "application_keys": self.application_keys,
            "journal_entry_ids": self.journal_entry_ids,
            "ledger_state": self.ledger_state,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingJournalReplayFailure:
    component_ref: ProfileComponentRef
    request: LinearFundingJournalReplayRequest
    request_hash: str
    code: LinearFundingJournalReplayFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Funding accounting component")
        if type(self.request) is not LinearFundingJournalReplayRequest:
            raise TypeError("request must be exact LinearFundingJournalReplayRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if type(self.code) is not LinearFundingJournalReplayFailureCode:
            raise TypeError("code must be exact LinearFundingJournalReplayFailureCode")
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be an exact tuple of strings")
        expected, _ = _evaluate_replay(self.request)
        if expected != (self.code, self.subject_ids):
            raise ValueError("failure must match first Journal replay failure")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_journal_replay_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingJournalReplayOutcome:
    component_ref: ProfileComponentRef
    request_hash: str
    projection: LinearFundingJournalProjection | None
    failure: LinearFundingJournalReplayFailure | None

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match Funding accounting component")
        if type(self.request_hash) is not str:
            raise TypeError("request_hash must be exact string")
        if type(self.projection) not in (
            type(None),
            LinearFundingJournalProjection,
        ):
            raise TypeError("projection must be exact Projection or None")
        if type(self.failure) not in (
            type(None),
            LinearFundingJournalReplayFailure,
        ):
            raise TypeError("failure must be exact Replay Failure or None")
        values = tuple(
            value for value in (self.projection, self.failure) if value is not None
        )
        if len(values) != 1:
            raise ValueError("Outcome requires exactly one Projection or Failure")
        if values[0].request_hash != self.request_hash:
            raise ValueError("Outcome request_hash must match its value")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_journal_replay_outcome",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request_hash": self.request_hash,
            "projection": self.projection,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingJournalProjector:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref()

    def project(
        self, request: LinearFundingJournalReplayRequest, /
    ) -> LinearFundingJournalReplayOutcome:
        if type(request) is not LinearFundingJournalReplayRequest:
            raise TypeError("request must be exact LinearFundingJournalReplayRequest")
        failure, values = _evaluate_replay(request)
        if failure is not None:
            code, subject_ids = failure
            value = LinearFundingJournalReplayFailure(
                self.component_ref,
                request,
                request.request_hash,
                code,
                subject_ids,
            )
            return LinearFundingJournalReplayOutcome(
                self.component_ref, request.request_hash, None, value
            )
        if values is None:
            raise AssertionError("successful replay requires projection values")
        cursor, application_keys, journal_entry_ids, ledger_state = values
        projection = LinearFundingJournalProjection(
            self.component_ref,
            request,
            request.request_hash,
            cursor,
            application_keys,
            journal_entry_ids,
            ledger_state,
        )
        return LinearFundingJournalReplayOutcome(
            self.component_ref, request.request_hash, projection, None
        )
