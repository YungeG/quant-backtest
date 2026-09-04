"""Pure translators for CN A-share corporate-action cash payments and deliveries."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
import re
import unicodedata
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    DomainId,
    DomainIdKind,
    Money,
    PositionLot,
    PositionLotChange,
    Price,
    QuantizationPolicy,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
    round_ratio,
)
from .corporate_actions import (
    CnAShareCorporateActionEntitlement,
    CnAShareCorporateActionSourceRef,
)


_SCHEMA_VERSION = 1
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_TIME_ZONE = ZoneInfo("Asia/Shanghai")
_PAYMENT_PHASE = TimelinePhase(110, "corporate_action_payment")
_LISTING_PHASE = TimelinePhase(120, "corporate_action_listing")
_TRIGGER_SEQUENCE = SourceSequence(0)


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be non-empty canonical text")


def _canonical_hash(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _canonical_bool(name: str, value: bool) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")


def _local_trigger(local_day: date, phase: TimelinePhase) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant.from_datetime(
            datetime(
                local_day.year,
                local_day.month,
                local_day.day,
                9,
                30,
                tzinfo=_TIME_ZONE,
            )
        ),
        phase,
        _TRIGGER_SEQUENCE,
    )


def _payment_trigger(
    entitlement: CnAShareCorporateActionEntitlement,
) -> SimulationInstant | None:
    announcement = entitlement.query.announcement
    if announcement is None or announcement.payment_date is None:
        return None
    return _local_trigger(announcement.payment_date.value, _PAYMENT_PHASE)


def _listing_trigger(
    entitlement: CnAShareCorporateActionEntitlement,
) -> SimulationInstant | None:
    announcement = entitlement.query.announcement
    if announcement is None or announcement.listing_date is None:
        return None
    return _local_trigger(announcement.listing_date.value, _LISTING_PHASE)


def _entitlement_evidence_match(
    entitlement: CnAShareCorporateActionEntitlement,
    evidence: "CnAShareCashPaymentEvidence | CnAShareShareDeliveryEvidence",
) -> bool:
    announcement = entitlement.query.announcement
    if announcement is None:
        return False
    source_ids = (
        evidence.corporate_action_id,
        entitlement.entitlement_hash,
        evidence.event_id,
        evidence.event_hash,
        evidence.evidence_id,
        evidence.evidence_hash,
    )
    return (
        evidence.entitlement_hash == entitlement.entitlement_hash
        and evidence.corporate_action_id == announcement.corporate_action_id
        and evidence.event_id == entitlement.event_id
        and evidence.event_hash == entitlement.event_hash
        and len(set(source_ids)) == len(source_ids)
    )


def _failure_subject_ids(
    request: "CnAShareCashPaymentRequest | CnAShareShareDeliveryRequest",
    code: "CnAShareCorporateActionTranslationFailureCode",
    leg: str,
) -> tuple[str, str, str, str, str, str, str, str, str]:
    entitlement = request.entitlement
    evidence = request.evidence
    return (
        code.value,
        leg,
        evidence.corporate_action_id,
        entitlement.entitlement_hash,
        evidence.evidence_id,
        evidence.evidence_hash,
        entitlement.account_id,
        str(entitlement.position_key.instrument_id),
        str(request.journal_entry_id),
    )


def _make_cash_failure(
    request: "CnAShareCashPaymentRequest",
    code: "CnAShareCorporateActionTranslationFailureCode",
) -> "CnAShareCorporateActionTranslationFailure":
    return CnAShareCorporateActionTranslationFailure(
        code=code,
        subject_ids=_failure_subject_ids(request, code, "cash_payment"),
    )


def _make_share_failure(
    request: "CnAShareShareDeliveryRequest",
    code: "CnAShareCorporateActionTranslationFailureCode",
) -> "CnAShareCorporateActionTranslationFailure":
    return CnAShareCorporateActionTranslationFailure(
        code=code,
        subject_ids=_failure_subject_ids(request, code, "share_delivery"),
    )


def _journal_source_ids(
    entitlement: CnAShareCorporateActionEntitlement,
    evidence: "CnAShareCashPaymentEvidence | CnAShareShareDeliveryEvidence",
) -> tuple[str, ...]:
    return (
        evidence.corporate_action_id,
        entitlement.entitlement_hash,
        evidence.event_id,
        evidence.event_hash,
        evidence.evidence_id,
        evidence.evidence_hash,
    )


class CnAShareCorporateActionTaxDisposition(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    APPLIED = "applied"
    DEFERRED_UNSUPPORTED = "deferred_unsupported"


class CnAShareCorporateActionDeliveryStatus(str, Enum):
    CONFIRMED = "confirmed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class CnAShareCorporateActionTranslationFailureCode(str, Enum):
    CONTEXT_MISMATCH = "context_mismatch"
    ENTITLEMENT_EVIDENCE_MISMATCH = "entitlement_evidence_mismatch"
    UNSUPPORTED_ACTION_SCOPE = "unsupported_action_scope"
    UNSUPPORTED_DELIVERY_STATUS = "unsupported_delivery_status"
    UNSUPPORTED_TAX_DISPOSITION = "unsupported_tax_disposition"
    NONZERO_WITHHOLDING = "nonzero_withholding"
    UNSUPPORTED_AVAILABILITY = "unsupported_availability"
    TRIGGER_MISMATCH = "trigger_mismatch"
    EVIDENCE_NOT_AVAILABLE = "evidence_not_available"
    UNSUPPORTED_FRACTIONAL_SHARE = "unsupported_fractional_share"
    DELIVERED_VALUE_MISMATCH = "delivered_value_mismatch"
    EARLY_INVOCATION = "early_invocation"
    ELIGIBLE_LOT_CARDINALITY_MISMATCH = "eligible_lot_cardinality_mismatch"
    LOT_STATE_MISMATCH = "lot_state_mismatch"
    EXACT_COST_BASIS_MISMATCH = "exact_cost_basis_mismatch"
    UNIT_COST_QUANTIZATION_MISMATCH = "unit_cost_quantization_mismatch"


@dataclass(frozen=True, slots=True)
class CnAShareCashPaymentEvidence:
    evidence_id: str
    source_ref: CnAShareCorporateActionSourceRef
    entitlement_hash: str
    corporate_action_id: str
    event_id: str
    event_hash: str
    status: CnAShareCorporateActionDeliveryStatus
    trigger_at: SimulationInstant
    available_at: SimulationInstant
    gross_cash: Money
    withholding: Money
    net_cash: Money
    tax_disposition: CnAShareCorporateActionTaxDisposition
    tradable: bool
    withdrawable: bool
    margin_eligible: bool

    def __post_init__(self) -> None:
        _canonical_text("evidence_id", self.evidence_id)
        if not isinstance(self.source_ref, CnAShareCorporateActionSourceRef):
            raise TypeError("source_ref must be CnAShareCorporateActionSourceRef")
        _canonical_hash("entitlement_hash", self.entitlement_hash)
        _canonical_text("corporate_action_id", self.corporate_action_id)
        _canonical_text("event_id", self.event_id)
        _canonical_hash("event_hash", self.event_hash)
        if not isinstance(self.status, CnAShareCorporateActionDeliveryStatus):
            raise TypeError("status must be CnAShareCorporateActionDeliveryStatus")
        if not isinstance(self.trigger_at, SimulationInstant):
            raise TypeError("trigger_at must be SimulationInstant")
        if not isinstance(self.available_at, SimulationInstant):
            raise TypeError("available_at must be SimulationInstant")
        if not isinstance(self.gross_cash, Money):
            raise TypeError("gross_cash must be Money")
        if not isinstance(self.withholding, Money):
            raise TypeError("withholding must be Money")
        if not isinstance(self.net_cash, Money):
            raise TypeError("net_cash must be Money")
        if not isinstance(
            self.tax_disposition, CnAShareCorporateActionTaxDisposition
        ):
            raise TypeError(
                "tax_disposition must be CnAShareCorporateActionTaxDisposition"
            )
        _canonical_bool("tradable", self.tradable)
        _canonical_bool("withdrawable", self.withdrawable)
        _canonical_bool("margin_eligible", self.margin_eligible)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_cash_payment_evidence",
            "schema_version": _SCHEMA_VERSION,
            "evidence_id": self.evidence_id,
            "source_ref": self.source_ref,
            "entitlement_hash": self.entitlement_hash,
            "corporate_action_id": self.corporate_action_id,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "status": self.status,
            "trigger_at": self.trigger_at,
            "available_at": self.available_at,
            "gross_cash": self.gross_cash,
            "withholding": self.withholding,
            "net_cash": self.net_cash,
            "tax_disposition": self.tax_disposition,
            "tradable": self.tradable,
            "withdrawable": self.withdrawable,
            "margin_eligible": self.margin_eligible,
        }


@dataclass(frozen=True, slots=True)
class CnAShareShareDeliveryEvidence:
    evidence_id: str
    source_ref: CnAShareCorporateActionSourceRef
    entitlement_hash: str
    corporate_action_id: str
    event_id: str
    event_hash: str
    status: CnAShareCorporateActionDeliveryStatus
    trigger_at: SimulationInstant
    available_at: SimulationInstant
    delivered_bonus_quantity: Quantity
    delivered_capitalization_quantity: Quantity
    withholding: Money
    tax_disposition: CnAShareCorporateActionTaxDisposition
    sellable: bool

    def __post_init__(self) -> None:
        _canonical_text("evidence_id", self.evidence_id)
        if not isinstance(self.source_ref, CnAShareCorporateActionSourceRef):
            raise TypeError("source_ref must be CnAShareCorporateActionSourceRef")
        _canonical_hash("entitlement_hash", self.entitlement_hash)
        _canonical_text("corporate_action_id", self.corporate_action_id)
        _canonical_text("event_id", self.event_id)
        _canonical_hash("event_hash", self.event_hash)
        if not isinstance(self.status, CnAShareCorporateActionDeliveryStatus):
            raise TypeError("status must be CnAShareCorporateActionDeliveryStatus")
        if not isinstance(self.trigger_at, SimulationInstant):
            raise TypeError("trigger_at must be SimulationInstant")
        if not isinstance(self.available_at, SimulationInstant):
            raise TypeError("available_at must be SimulationInstant")
        if not isinstance(self.delivered_bonus_quantity, Quantity):
            raise TypeError("delivered_bonus_quantity must be Quantity")
        if not isinstance(self.delivered_capitalization_quantity, Quantity):
            raise TypeError("delivered_capitalization_quantity must be Quantity")
        if not isinstance(self.withholding, Money):
            raise TypeError("withholding must be Money")
        if not isinstance(
            self.tax_disposition, CnAShareCorporateActionTaxDisposition
        ):
            raise TypeError(
                "tax_disposition must be CnAShareCorporateActionTaxDisposition"
            )
        _canonical_bool("sellable", self.sellable)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_share_delivery_evidence",
            "schema_version": _SCHEMA_VERSION,
            "evidence_id": self.evidence_id,
            "source_ref": self.source_ref,
            "entitlement_hash": self.entitlement_hash,
            "corporate_action_id": self.corporate_action_id,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "status": self.status,
            "trigger_at": self.trigger_at,
            "available_at": self.available_at,
            "delivered_bonus_quantity": self.delivered_bonus_quantity,
            "delivered_capitalization_quantity": self.delivered_capitalization_quantity,
            "withholding": self.withholding,
            "tax_disposition": self.tax_disposition,
            "sellable": self.sellable,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCashPaymentRequest:
    entitlement: CnAShareCorporateActionEntitlement
    evidence: CnAShareCashPaymentEvidence
    cash_key: CashBalanceKey
    journal_entry_id: DomainId
    recorded_at: SimulationInstant

    def __post_init__(self) -> None:
        if not isinstance(self.entitlement, CnAShareCorporateActionEntitlement):
            raise TypeError("entitlement must be CnAShareCorporateActionEntitlement")
        if not isinstance(self.evidence, CnAShareCashPaymentEvidence):
            raise TypeError("evidence must be CnAShareCashPaymentEvidence")
        if not isinstance(self.cash_key, CashBalanceKey):
            raise TypeError("cash_key must be CashBalanceKey")
        if not isinstance(self.journal_entry_id, DomainId):
            raise TypeError("journal_entry_id must be DomainId")
        if not isinstance(self.recorded_at, SimulationInstant):
            raise TypeError("recorded_at must be SimulationInstant")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_cash_payment_request",
            "schema_version": _SCHEMA_VERSION,
            "entitlement": self.entitlement,
            "evidence": self.evidence,
            "cash_key": self.cash_key,
            "journal_entry_id": self.journal_entry_id,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class CnAShareShareDeliveryRequest:
    entitlement: CnAShareCorporateActionEntitlement
    evidence: CnAShareShareDeliveryEvidence
    open_lots: tuple[PositionLot, ...]
    unit_cost_quantization: QuantizationPolicy
    journal_entry_id: DomainId
    recorded_at: SimulationInstant

    def __post_init__(self) -> None:
        if not isinstance(self.entitlement, CnAShareCorporateActionEntitlement):
            raise TypeError("entitlement must be CnAShareCorporateActionEntitlement")
        if not isinstance(self.evidence, CnAShareShareDeliveryEvidence):
            raise TypeError("evidence must be CnAShareShareDeliveryEvidence")
        if not isinstance(self.open_lots, tuple):
            raise TypeError("open_lots must be a tuple")
        if not all(isinstance(value, PositionLot) for value in self.open_lots):
            raise TypeError("open_lots must contain PositionLot")
        if not isinstance(self.unit_cost_quantization, QuantizationPolicy):
            raise TypeError("unit_cost_quantization must be QuantizationPolicy")
        if not isinstance(self.journal_entry_id, DomainId):
            raise TypeError("journal_entry_id must be DomainId")
        if not isinstance(self.recorded_at, SimulationInstant):
            raise TypeError("recorded_at must be SimulationInstant")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_share_delivery_request",
            "schema_version": _SCHEMA_VERSION,
            "entitlement": self.entitlement,
            "evidence": self.evidence,
            "open_lots": self.open_lots,
            "unit_cost_quantization": self.unit_cost_quantization,
            "journal_entry_id": self.journal_entry_id,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionTranslationFailure:
    code: CnAShareCorporateActionTranslationFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.code, CnAShareCorporateActionTranslationFailureCode):
            raise TypeError("code must be CnAShareCorporateActionTranslationFailureCode")
        if not isinstance(self.subject_ids, tuple) or len(self.subject_ids) != 9:
            raise ValueError("subject_ids must contain exactly nine identities")
        for subject_id in self.subject_ids:
            _canonical_text("subject_id", subject_id)
        if self.subject_ids[0] != self.code.value:
            raise ValueError("first subject identity must match failure code")
        if self.subject_ids[1] not in ("cash_payment", "share_delivery"):
            raise ValueError("second subject identity must be a frozen leg")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_translation_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCashPaymentOutcome:
    request: CnAShareCashPaymentRequest
    journal_entry: AccountingJournalEntry | None
    failure: CnAShareCorporateActionTranslationFailure | None

    def __post_init__(self) -> None:
        if type(self.request) is not CnAShareCashPaymentRequest:
            raise TypeError("request must be CnAShareCashPaymentRequest")
        if (self.journal_entry is None) == (self.failure is None):
            raise ValueError("exactly one of journal_entry or failure required")
        expected_journal, expected_failure = _translate_cash_payment(self.request)
        if self.journal_entry is not None:
            if expected_journal != self.journal_entry:
                raise ValueError("forged journal entry")
            return
        if expected_failure != self.failure:
            raise ValueError("forged failure")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_cash_payment_outcome",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "journal_entry": self.journal_entry,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class CnAShareShareDeliveryOutcome:
    request: CnAShareShareDeliveryRequest
    journal_entry: AccountingJournalEntry | None
    failure: CnAShareCorporateActionTranslationFailure | None

    def __post_init__(self) -> None:
        if type(self.request) is not CnAShareShareDeliveryRequest:
            raise TypeError("request must be CnAShareShareDeliveryRequest")
        if (self.journal_entry is None) == (self.failure is None):
            raise ValueError("exactly one of journal_entry or failure required")
        expected_journal, expected_failure = _translate_share_delivery(self.request)
        if self.journal_entry is not None:
            if expected_journal != self.journal_entry:
                raise ValueError("forged journal entry")
            return
        if expected_failure != self.failure:
            raise ValueError("forged failure")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_share_delivery_outcome",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "journal_entry": self.journal_entry,
            "failure": self.failure,
        }


def _cny_scale_2(value: Money) -> bool:
    return value.currency == "CNY" and value.scale == Scale(2)


def _cash_request_context_mismatch(request: CnAShareCashPaymentRequest) -> bool:
    evidence = request.evidence
    return (
        request.journal_entry_id.kind is not DomainIdKind.JOURNAL
        or request.entitlement.account_id != request.cash_key.account_id
        or request.entitlement.position_key.venue_id != request.cash_key.venue_id
        or str(request.cash_key.currency_id) != "CNY"
        or not _cny_scale_2(evidence.gross_cash)
        or not _cny_scale_2(evidence.withholding)
        or not _cny_scale_2(evidence.net_cash)
    )


def _share_request_context_mismatch(request: CnAShareShareDeliveryRequest) -> bool:
    instrument_id = str(request.entitlement.position_key.instrument_id)
    return (
        request.journal_entry_id.kind is not DomainIdKind.JOURNAL
        or not _cny_scale_2(request.evidence.withholding)
        or request.evidence.delivered_bonus_quantity.instrument_id != instrument_id
        or request.evidence.delivered_capitalization_quantity.instrument_id
        != instrument_id
    )


def _translate_cash_payment(
    request: CnAShareCashPaymentRequest,
) -> tuple[AccountingJournalEntry | None, CnAShareCorporateActionTranslationFailure | None]:
    entitlement = request.entitlement
    evidence = request.evidence

    if _cash_request_context_mismatch(request):
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH,
        )

    if not _entitlement_evidence_match(entitlement, evidence):
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.ENTITLEMENT_EVIDENCE_MISMATCH,
        )

    if entitlement.gross_cash.units <= 0:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_ACTION_SCOPE,
        )

    if evidence.status is not CnAShareCorporateActionDeliveryStatus.CONFIRMED:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_DELIVERY_STATUS,
        )

    if evidence.tax_disposition is not CnAShareCorporateActionTaxDisposition.NOT_APPLICABLE:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_TAX_DISPOSITION,
        )

    if evidence.withholding.units != 0:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.NONZERO_WITHHOLDING,
        )

    if not (evidence.tradable and evidence.withdrawable and evidence.margin_eligible):
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_AVAILABILITY,
        )

    expected_trigger = _payment_trigger(entitlement)
    if expected_trigger is None or evidence.trigger_at != expected_trigger:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.TRIGGER_MISMATCH,
        )

    if evidence.available_at != evidence.trigger_at:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.EVIDENCE_NOT_AVAILABLE,
        )

    if evidence.gross_cash != entitlement.gross_cash or evidence.net_cash != evidence.gross_cash:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.DELIVERED_VALUE_MISMATCH,
        )

    if request.recorded_at < evidence.trigger_at:
        return None, _make_cash_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.EARLY_INVOCATION,
        )

    return (
        AccountingJournalEntry(
            journal_entry_id=request.journal_entry_id,
            entry_type=AccountingEntryType.CORPORATE_ACTION_CASH_PAID,
            account_id=entitlement.account_id,
            venue_id=entitlement.position_key.venue_id,
            effective_time=evidence.trigger_at.instant,
            recorded_at=request.recorded_at,
            source_ids=_journal_source_ids(entitlement, evidence),
            balance_changes=(BalanceChange(request.cash_key, evidence.net_cash),),
            realized_pnl=(),
            fees=(),
            financing=(),
            position_lot_changes=(),
        ),
        None,
    )


def _share_request_single_lot(lots: tuple[PositionLot, ...]) -> PositionLot | None:
    if len(lots) != 1:
        return None
    return lots[0]


def _share_lot_state_mismatch(
    entitlement: CnAShareCorporateActionEntitlement, lot: PositionLot
) -> bool:
    return (
        lot.position_key != entitlement.position_key
        or lot.quantity.units <= 0
        or lot.quantity.scale != Scale(0)
        or lot.unit_cost is None
        or lot.unit_cost.quote_currency != "CNY"
        or any(fee.currency != "CNY" for fee in lot.allocated_fees)
    )


def _exact_cost_basis_mismatch(lot: PositionLot) -> bool:
    if lot.unit_cost is None or lot.total_cost_basis is None:
        return True
    if lot.total_cost_basis.currency != "CNY" or lot.total_cost_basis.scale != Scale(2):
        return True
    if lot.total_cost_basis.units <= 0:
        return True
    return lot.unit_cost.quote_currency != "CNY" or lot.unit_cost.units <= 0


def _derive_unit_cost(
    lot: PositionLot,
    policy: QuantizationPolicy,
    delivered_units: int,
) -> Price:
    total_basis = lot.total_cost_basis
    if lot.unit_cost is None or total_basis is None:
        raise ValueError("unit cost and exact total basis are required")

    new_quantity = lot.quantity.units + delivered_units
    if new_quantity <= 0:
        raise ValueError("post-translation lot quantity must be positive")

    delta_scale = policy.target_scale.places - total_basis.scale.places
    if delta_scale >= 0:
        numerator = total_basis.units * (10 ** delta_scale)
        denominator = new_quantity
    else:
        numerator = total_basis.units
        denominator = new_quantity * (10 ** (-delta_scale))

    unit_cost_units = round_ratio(numerator, denominator, policy.rounding)
    if unit_cost_units <= 0:
        raise ValueError("derived unit cost must be strictly positive")

    return Price(
        unit_cost_units,
        policy.target_scale,
        str(lot.position_key.instrument_id),
        total_basis.currency,
    )


def _translate_share_delivery(
    request: CnAShareShareDeliveryRequest,
) -> tuple[AccountingJournalEntry | None, CnAShareCorporateActionTranslationFailure | None]:
    entitlement = request.entitlement
    evidence = request.evidence

    if _share_request_context_mismatch(request):
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH,
        )

    if not _entitlement_evidence_match(entitlement, evidence):
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.ENTITLEMENT_EVIDENCE_MISMATCH,
        )

    if entitlement.position_key.venue_id.value != "xshe" or (
        entitlement.bonus_quantity.units + entitlement.capitalization_quantity.units
    ) <= 0:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_ACTION_SCOPE,
        )

    if evidence.status is not CnAShareCorporateActionDeliveryStatus.CONFIRMED:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_DELIVERY_STATUS,
        )

    if evidence.tax_disposition is not CnAShareCorporateActionTaxDisposition.NOT_APPLICABLE:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_TAX_DISPOSITION,
        )

    if evidence.withholding.units != 0:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.NONZERO_WITHHOLDING,
        )

    if not evidence.sellable:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_AVAILABILITY,
        )

    expected_trigger = _listing_trigger(entitlement)
    if expected_trigger is None or evidence.trigger_at != expected_trigger:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.TRIGGER_MISMATCH,
        )

    if evidence.available_at != evidence.trigger_at:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.EVIDENCE_NOT_AVAILABLE,
        )

    if evidence.delivered_bonus_quantity.scale != Scale(0) or evidence.delivered_capitalization_quantity.scale != Scale(0):
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_FRACTIONAL_SHARE,
        )

    if (
        evidence.delivered_bonus_quantity != entitlement.bonus_quantity
        or evidence.delivered_capitalization_quantity != entitlement.capitalization_quantity
    ):
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.DELIVERED_VALUE_MISMATCH,
        )

    if request.recorded_at < evidence.trigger_at:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.EARLY_INVOCATION,
        )

    lot = _share_request_single_lot(request.open_lots)
    if lot is None:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.ELIGIBLE_LOT_CARDINALITY_MISMATCH,
        )

    if _share_lot_state_mismatch(entitlement, lot):
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.LOT_STATE_MISMATCH,
        )

    if _exact_cost_basis_mismatch(lot):
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.EXACT_COST_BASIS_MISMATCH,
        )

    delivered_units = (
        evidence.delivered_bonus_quantity.units
        + evidence.delivered_capitalization_quantity.units
    )

    current_unit_cost = lot.unit_cost
    if (
        current_unit_cost is None
        or request.unit_cost_quantization.target_scale != current_unit_cost.scale
    ):
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNIT_COST_QUANTIZATION_MISMATCH,
        )

    try:
        unit_cost = _derive_unit_cost(lot, request.unit_cost_quantization, delivered_units)
    except ValueError:
        return None, _make_share_failure(
            request,
            CnAShareCorporateActionTranslationFailureCode.UNIT_COST_QUANTIZATION_MISMATCH,
        )

    new_lot = replace(
        lot,
        quantity=Quantity(
            lot.quantity.units + delivered_units,
            lot.quantity.scale,
            lot.quantity.instrument_id,
        ),
        unit_cost=unit_cost,
        total_cost_basis=lot.total_cost_basis,
    )

    return (
        AccountingJournalEntry(
            journal_entry_id=request.journal_entry_id,
            entry_type=AccountingEntryType.CORPORATE_ACTION_POSITION_ADJUSTED,
            account_id=entitlement.account_id,
            venue_id=entitlement.position_key.venue_id,
            effective_time=evidence.trigger_at.instant,
            recorded_at=request.recorded_at,
            source_ids=_journal_source_ids(entitlement, evidence),
            balance_changes=(
                BalanceChange(
                    entitlement.position_key,
                    Quantity(
                        delivered_units,
                        lot.quantity.scale,
                        str(entitlement.position_key.instrument_id),
                    ),
                ),
            ),
            realized_pnl=(),
            fees=(),
            financing=(),
            position_lot_changes=(PositionLotChange(lot, new_lot),),
        ),
        None,
    )


def translate_corporate_action_cash_payment(
    request: CnAShareCashPaymentRequest,
) -> CnAShareCashPaymentOutcome:
    if not isinstance(request, CnAShareCashPaymentRequest):
        raise TypeError("request must be CnAShareCashPaymentRequest")
    journal_entry, failure = _translate_cash_payment(request)
    if failure is not None:
        return CnAShareCashPaymentOutcome(request=request, journal_entry=None, failure=failure)
    if journal_entry is None:
        raise RuntimeError("cash translation produced neither result nor failure")
    return CnAShareCashPaymentOutcome(
        request=request,
        journal_entry=journal_entry,
        failure=None,
    )


def translate_corporate_action_share_delivery(
    request: CnAShareShareDeliveryRequest,
) -> CnAShareShareDeliveryOutcome:
    if not isinstance(request, CnAShareShareDeliveryRequest):
        raise TypeError("request must be CnAShareShareDeliveryRequest")
    journal_entry, failure = _translate_share_delivery(request)
    if failure is not None:
        return CnAShareShareDeliveryOutcome(request=request, journal_entry=None, failure=failure)
    if journal_entry is None:
        raise RuntimeError("share translation produced neither result nor failure")
    return CnAShareShareDeliveryOutcome(
        request=request,
        journal_entry=journal_entry,
        failure=None,
    )
