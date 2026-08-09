"""Exact linear-perpetual transition accounting and journal replay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import gcd
from typing import Any

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    InstrumentId,
    Money,
    PositionBalanceKey,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_sha256,
    round_ratio,
)

from .derivatives import (
    LinearPerpetualContract,
    LinearPositionState,
    LinearPositionTransition,
)
from .journal import AccountingJournal, JournalReplayCursor
from .ledger import GenericLedger, LedgerBalanceRegistration, LedgerSchema
from .ports import ProfileComponentRef, ProfilePortOutcome, ProfilePortType

_SCHEMA_VERSION = 1
_COMPONENT_KEY = "instrument.linear-perpetual.accounting.v1"
_ALGORITHM_KEY = "linear-perpetual-transition-accounting-v1"


def _require_currency(name: str, value: CurrencyId) -> None:
    if type(value) is not CurrencyId or type(value.value) is not str:
        raise TypeError(f"{name} must be exact CurrencyId")


def _require_venue(name: str, value: VenueId) -> None:
    if type(value) is not VenueId or type(value.value) is not str:
        raise TypeError(f"{name} must be exact VenueId")


def _require_cash_key(name: str, value: CashBalanceKey) -> None:
    if type(value) is not CashBalanceKey or type(value.account_id) is not str:
        raise TypeError(f"{name} must be exact CashBalanceKey")
    _require_venue(f"{name} venue", value.venue_id)
    _require_currency(f"{name} currency", value.currency_id)


def _require_position_key(name: str, value: PositionBalanceKey) -> None:
    if type(value) is not PositionBalanceKey or type(value.account_id) is not str:
        raise TypeError(f"{name} must be exact PositionBalanceKey")
    _require_venue(f"{name} venue", value.venue_id)
    if type(value.instrument_id) is not InstrumentId:
        raise TypeError(f"{name} instrument must be exact InstrumentId")
    _require_venue(f"{name} instrument venue", value.instrument_id.venue)
    if type(value.instrument_id.stable_key) is not str:
        raise TypeError(f"{name} instrument key must be exact string")


def _require_scale(name: str, value: Scale) -> None:
    if type(value) is not Scale or type(value.places) is not int:
        raise TypeError(f"{name} must be exact Scale")


def _require_registration(value: LedgerBalanceRegistration) -> None:
    if type(value) is not LedgerBalanceRegistration:
        raise TypeError("registration must be exact LedgerBalanceRegistration")
    if type(value.key) is CashBalanceKey:
        _require_cash_key("registration key", value.key)
    elif type(value.key) is PositionBalanceKey:
        _require_position_key("registration key", value.key)
    else:
        raise TypeError("registration key must be exact CashBalanceKey or PositionBalanceKey")
    _require_scale("registration scale", value.scale)


def _require_quantization(value: QuantizationPolicy) -> None:
    if type(value) is not QuantizationPolicy or type(value.version) is not str:
        raise TypeError("pnl_quantization must be exact QuantizationPolicy")
    _require_scale("pnl_quantization target_scale", value.target_scale)
    if type(value.rounding) is not RoundingPolicy:
        raise TypeError("pnl_quantization rounding must be exact RoundingPolicy")


def _require_domain_id(name: str, value: DomainId, kind: DomainIdKind) -> None:
    if (
        type(value) is not DomainId
        or type(value.kind) is not DomainIdKind
        or type(value.value) is not str
    ):
        raise TypeError(f"{name} must be exact DomainId")
    if value.kind is not kind:
        raise ValueError(f"{name} must use {kind.value} kind")


def _require_simulation_instant(value: SimulationInstant) -> None:
    if type(value) is not SimulationInstant:
        raise TypeError("recorded_at must be exact SimulationInstant")
    if type(value.instant) is not UtcInstant or type(value.instant.epoch_nanoseconds) is not int:
        raise TypeError("recorded_at instant must be exact UtcInstant")
    if (
        type(value.phase) is not TimelinePhase
        or type(value.phase.rank) is not int
        or type(value.phase.code) is not str
    ):
        raise TypeError("recorded_at phase must be exact TimelinePhase")
    if (
        type(value.source_sequence) is not SourceSequence
        or type(value.source_sequence.value) is not int
    ):
        raise TypeError("recorded_at sequence must be exact SourceSequence")


def _component_ref() -> ProfileComponentRef:
    digest = canonical_sha256(
        {
            "type": "linear_derivative_accounting_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "algorithm_key": _ALGORITHM_KEY,
            "exact_pnl_formula": (
                "sign(before_quantity_units)*closed_quantity_units*multiplier_units*"
                "(exit_price_units*basis_denominator-basis_numerator*price_scale_factor)/"
                "(quantity_scale_factor*multiplier_scale_factor*price_scale_factor*"
                "basis_denominator)"
            ),
            "money_boundary": (
                "round_ratio(exact_numerator*target_scale_factor,exact_denominator,rounding)"
            ),
            "quantization_scope": "per_transition",
            "journal_entry_type": "linear_derivative_journal_entry",
            "position_effect": "after_minus_before",
            "cash_effect": "nonzero_quantized_realized_pnl_only",
            "excluded_effects": (
                "principal_notional",
                "fees",
                "funding",
                "unrealized_pnl",
            ),
            "allowed_grade": "development",
        }
    )
    return ProfileComponentRef(
        ProfilePortType.POSITION_ACCOUNTING_MODEL,
        _COMPONENT_KEY,
        1,
        digest,
    )


@dataclass(frozen=True, slots=True)
class ExactLinearRealizedPnl:
    currency: CurrencyId
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.currency) is not CurrencyId or type(self.currency.value) is not str:
            raise TypeError("currency must be exact CurrencyId")
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("numerator and denominator must be exact integers")
        if self.denominator <= 0:
            raise ValueError("denominator must be positive")
        if gcd(abs(self.numerator), self.denominator) != 1:
            raise ValueError("realized profit/loss must be GCD-reduced")

    @property
    def pnl_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "exact_linear_realized_pnl",
            "schema_version": _SCHEMA_VERSION,
            "currency": self.currency,
            "numerator": self.numerator,
            "denominator": self.denominator,
        }


def _exact_pnl(transition: LinearPositionTransition) -> ExactLinearRealizedPnl:
    contract = transition.before.contract
    currency = contract.instrument.settlement_currency
    if transition.closed_quantity.units == 0:
        return ExactLinearRealizedPnl(currency, 0, 1)
    basis = transition.before.average_entry_basis
    if basis is None:
        raise AssertionError("closed transition requires prior entry basis")
    sign = 1 if transition.before.quantity.units > 0 else -1
    numerator = (
        sign
        * transition.closed_quantity.units
        * contract.contract_multiplier.units
        * (
            transition.fill.price.units * basis.denominator
            - basis.numerator * contract.price_scale.factor
        )
    )
    denominator = (
        contract.quantity_scale.factor
        * contract.contract_multiplier.scale.factor
        * contract.price_scale.factor
        * basis.denominator
    )
    divisor = gcd(abs(numerator), denominator)
    return ExactLinearRealizedPnl(
        currency,
        numerator // divisor,
        denominator // divisor,
    )


def _quantized_pnl(
    exact: ExactLinearRealizedPnl, policy: QuantizationPolicy
) -> Money:
    return Money(
        round_ratio(
            exact.numerator * policy.target_scale.factor,
            exact.denominator,
            policy.rounding,
        ),
        policy.target_scale,
        str(exact.currency),
    )


@dataclass(frozen=True, slots=True)
class LinearDerivativeAccountingRequest:
    transition: LinearPositionTransition
    settlement_cash_registration: LedgerBalanceRegistration
    pnl_quantization: QuantizationPolicy
    journal_entry_id: DomainId
    recorded_at: SimulationInstant

    def __post_init__(self) -> None:
        if type(self.transition) is not LinearPositionTransition:
            raise TypeError("transition must be exact LinearPositionTransition")
        _require_registration(self.settlement_cash_registration)
        _require_quantization(self.pnl_quantization)
        _require_domain_id(
            "journal_entry_id", self.journal_entry_id, DomainIdKind.JOURNAL
        )
        _require_simulation_instant(self.recorded_at)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_accounting_request",
            "schema_version": _SCHEMA_VERSION,
            "transition": self.transition,
            "settlement_cash_registration": self.settlement_cash_registration,
            "pnl_quantization": self.pnl_quantization,
            "journal_entry_id": self.journal_entry_id,
            "recorded_at": self.recorded_at,
        }


class LinearDerivativeAccountingFailureCode(str, Enum):
    SETTLEMENT_CONTEXT_MISMATCH = "settlement_context_mismatch"
    QUANTIZATION_SCALE_MISMATCH = "quantization_scale_mismatch"
    RECORDED_BEFORE_EXECUTION = "recorded_before_execution"


def _first_accounting_failure(
    request: LinearDerivativeAccountingRequest,
) -> LinearDerivativeAccountingFailureCode | None:
    transition = request.transition
    fill = transition.fill
    registration = request.settlement_cash_registration
    expected_key = CashBalanceKey(
        fill.account_id,
        fill.venue_id,
        transition.before.contract.instrument.settlement_currency,
    )
    if type(registration.key) is not CashBalanceKey or registration.key != expected_key:
        return LinearDerivativeAccountingFailureCode.SETTLEMENT_CONTEXT_MISMATCH
    if request.pnl_quantization.target_scale != registration.scale:
        return LinearDerivativeAccountingFailureCode.QUANTIZATION_SCALE_MISMATCH
    if request.recorded_at.instant < fill.execution_time:
        return LinearDerivativeAccountingFailureCode.RECORDED_BEFORE_EXECUTION
    return None


def _failure_subject_ids(
    request: LinearDerivativeAccountingRequest,
    code: LinearDerivativeAccountingFailureCode,
) -> tuple[str, ...]:
    fill = request.transition.fill
    return (
        code.value,
        str(fill.fill_id),
        request.journal_entry_id.value,
        fill.account_id,
        str(request.transition.before.position_key.instrument_id),
        str(request.transition.before.contract.instrument.settlement_currency),
    )


def _entry_values(
    request: LinearDerivativeAccountingRequest,
) -> tuple[
    ExactLinearRealizedPnl,
    tuple[str, ...],
    tuple[BalanceChange, ...],
    tuple[Money, ...],
]:
    transition = request.transition
    exact = _exact_pnl(transition)
    money = _quantized_pnl(exact, request.pnl_quantization)
    position_delta = Quantity(
        transition.after.quantity.units - transition.before.quantity.units,
        transition.before.contract.quantity_scale,
        str(transition.before.position_key.instrument_id),
    )
    changes: list[BalanceChange] = [
        BalanceChange(transition.before.position_key, position_delta)
    ]
    realized: tuple[Money, ...] = ()
    if money.units != 0:
        cash_key = request.settlement_cash_registration.key
        if type(cash_key) is not CashBalanceKey:
            raise AssertionError("successful accounting requires Cash registration")
        changes.append(BalanceChange(cash_key, money))
        realized = (money,)
    source_ids = tuple(
        sorted(
            (
                str(transition.fill.fill_id),
                str(transition.fill.order_id),
                transition.transition_hash,
                request.request_hash,
            )
        )
    )
    return exact, source_ids, tuple(changes), realized


@dataclass(frozen=True, slots=True)
class LinearDerivativeJournalEntry(AccountingJournalEntry):
    component_ref: ProfileComponentRef
    request: LinearDerivativeAccountingRequest
    request_hash: str
    exact_realized_pnl: ExactLinearRealizedPnl

    def __post_init__(self) -> None:
        AccountingJournalEntry.__post_init__(self)
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match derivative accounting component")
        if type(self.request) is not LinearDerivativeAccountingRequest:
            raise TypeError("request must be exact LinearDerivativeAccountingRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if _first_accounting_failure(self.request) is not None:
            raise ValueError("Journal entry requires a successful Request")
        exact, source_ids, changes, realized = _entry_values(self.request)
        expected = (
            self.request.journal_entry_id,
            AccountingEntryType.FILL_BOOKED,
            self.request.transition.fill.account_id,
            self.request.transition.fill.venue_id,
            self.request.transition.fill.execution_time,
            self.request.recorded_at,
            source_ids,
            changes,
            realized,
            (),
            (),
            exact,
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
            self.exact_realized_pnl,
        )
        if actual != expected:
            raise ValueError("Journal entry fields must match embedded Request")

    @property
    def derivative_entry_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_journal_entry",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "exact_realized_pnl": self.exact_realized_pnl,
            "journal_entry": AccountingJournalEntry.to_canonical_dict(self),
        }


def _journal_entry(
    component_ref: ProfileComponentRef,
    request: LinearDerivativeAccountingRequest,
) -> LinearDerivativeJournalEntry:
    exact, source_ids, changes, realized = _entry_values(request)
    transition = request.transition
    return LinearDerivativeJournalEntry(
        journal_entry_id=request.journal_entry_id,
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id=transition.fill.account_id,
        venue_id=transition.fill.venue_id,
        effective_time=transition.fill.execution_time,
        recorded_at=request.recorded_at,
        source_ids=source_ids,
        balance_changes=changes,
        realized_pnl=realized,
        fees=(),
        financing=(),
        component_ref=component_ref,
        request=request,
        request_hash=request.request_hash,
        exact_realized_pnl=exact,
    )


def _validate_accounting_evidence(
    component_ref: ProfileComponentRef,
    request: LinearDerivativeAccountingRequest,
    request_hash: str,
) -> None:
    if component_ref != _component_ref():
        raise ValueError("component_ref must match derivative accounting component")
    if type(request) is not LinearDerivativeAccountingRequest:
        raise TypeError("request must be exact LinearDerivativeAccountingRequest")
    if request_hash != request.request_hash:
        raise ValueError("request_hash must match embedded Request")


@dataclass(frozen=True, slots=True)
class LinearDerivativeAccountingResult:
    component_ref: ProfileComponentRef
    request: LinearDerivativeAccountingRequest
    request_hash: str
    journal_entry: LinearDerivativeJournalEntry

    def __post_init__(self) -> None:
        _validate_accounting_evidence(
            self.component_ref, self.request, self.request_hash
        )
        if type(self.journal_entry) is not LinearDerivativeJournalEntry:
            raise TypeError("journal_entry must be exact LinearDerivativeJournalEntry")
        if self.journal_entry != _journal_entry(self.component_ref, self.request):
            raise ValueError("journal_entry must match embedded Request")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_accounting_result",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "journal_entry": self.journal_entry,
        }


@dataclass(frozen=True, slots=True)
class LinearDerivativeAccountingFailure:
    component_ref: ProfileComponentRef
    request: LinearDerivativeAccountingRequest
    request_hash: str
    code: LinearDerivativeAccountingFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_accounting_evidence(
            self.component_ref, self.request, self.request_hash
        )
        if type(self.code) is not LinearDerivativeAccountingFailureCode:
            raise TypeError("code must be exact LinearDerivativeAccountingFailureCode")
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be an exact tuple of strings")
        expected = _first_accounting_failure(self.request)
        if expected is None or self.code is not expected:
            raise ValueError("failure must match first Request failure")
        if self.subject_ids != _failure_subject_ids(self.request, self.code):
            raise ValueError("subject_ids must match embedded Request")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_accounting_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class LinearDerivativeAccounting:
    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref()

    def translate_position_fact(
        self, request: LinearDerivativeAccountingRequest, /
    ) -> ProfilePortOutcome[
        LinearDerivativeAccountingResult, LinearDerivativeAccountingFailure
    ]:
        if type(request) is not LinearDerivativeAccountingRequest:
            raise TypeError("request must be exact LinearDerivativeAccountingRequest")
        code = _first_accounting_failure(request)
        if code is not None:
            failure = LinearDerivativeAccountingFailure(
                self.component_ref,
                request,
                request.request_hash,
                code,
                _failure_subject_ids(request, code),
            )
            return ProfilePortOutcome.for_failure(self.component_ref, request, failure)
        result = LinearDerivativeAccountingResult(
            self.component_ref,
            request,
            request.request_hash,
            _journal_entry(self.component_ref, request),
        )
        return ProfilePortOutcome.for_result(self.component_ref, request, result)


class LinearDerivativeLedgerReplayFailureCode(str, Enum):
    REPLAY_CONTEXT_MISMATCH = "replay_context_mismatch"
    UNSUPPORTED_TARGET_POSITION_ENTRY = "unsupported_target_position_entry"
    ENTRY_CONTEXT_MISMATCH = "entry_context_mismatch"
    DUPLICATE_FILL_ID = "duplicate_fill_id"
    TRANSITION_LINEAGE_MISMATCH = "transition_lineage_mismatch"
    LEDGER_POSITION_MISMATCH = "ledger_position_mismatch"


@dataclass(frozen=True, slots=True)
class LinearDerivativeLedgerReplayRequest:
    journal: AccountingJournal
    ledger_schema: LedgerSchema
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    settlement_cash_key: CashBalanceKey

    def __post_init__(self) -> None:
        if type(self.journal) is not AccountingJournal or type(
            self.journal.entries
        ) is not tuple:
            raise TypeError("journal must be exact AccountingJournal")
        if type(self.ledger_schema) is not LedgerSchema or type(
            self.ledger_schema.registrations
        ) is not tuple:
            raise TypeError("ledger_schema must be exact LedgerSchema")
        for registration in self.ledger_schema.registrations:
            _require_registration(registration)
        _require_position_key("position_key", self.position_key)
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        _require_cash_key("settlement_cash_key", self.settlement_cash_key)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_ledger_replay_request",
            "schema_version": _SCHEMA_VERSION,
            "journal": self.journal,
            "ledger_schema": self.ledger_schema,
            "position_key": self.position_key,
            "contract": self.contract,
            "settlement_cash_key": self.settlement_cash_key,
        }


def _flat_state(request: LinearDerivativeLedgerReplayRequest) -> LinearPositionState:
    return LinearPositionState(
        request.position_key,
        request.contract,
        Quantity(
            0,
            request.contract.quantity_scale,
            str(request.position_key.instrument_id),
        ),
        None,
    )


def _add_exact(
    left: ExactLinearRealizedPnl,
    right: ExactLinearRealizedPnl,
) -> ExactLinearRealizedPnl:
    if left.currency != right.currency:
        raise ValueError("exact realized profit/loss currency mismatch")
    numerator = (
        left.numerator * right.denominator
        + right.numerator * left.denominator
    )
    denominator = left.denominator * right.denominator
    divisor = gcd(abs(numerator), denominator)
    return ExactLinearRealizedPnl(
        left.currency,
        numerator // divisor,
        denominator // divisor,
    )


def _schema_registration(
    schema: LedgerSchema,
    key: CashBalanceKey | PositionBalanceKey,
) -> LedgerBalanceRegistration | None:
    return next(
        (registration for registration in schema.registrations if registration.key == key),
        None,
    )


def _replay_context_matches(request: LinearDerivativeLedgerReplayRequest) -> bool:
    instrument = request.contract.instrument
    position_registration = _schema_registration(
        request.ledger_schema, request.position_key
    )
    cash_registration = _schema_registration(
        request.ledger_schema, request.settlement_cash_key
    )
    return (
        request.position_key.account_id == request.settlement_cash_key.account_id
        and request.position_key.venue_id == instrument.instrument_id.venue
        and request.position_key.instrument_id == instrument.instrument_id
        and request.settlement_cash_key.venue_id == request.position_key.venue_id
        and request.settlement_cash_key.currency_id == instrument.settlement_currency
        and position_registration is not None
        and position_registration.scale == request.contract.quantity_scale
        and cash_registration is not None
    )


type _ReplayFailureValue = tuple[
    LinearDerivativeLedgerReplayFailureCode,
    DomainId | None,
    DomainId | None,
]
type _ReplaySuccessValue = tuple[
    JournalReplayCursor,
    LinearPositionState,
    ExactLinearRealizedPnl,
    Money,
    tuple[DomainId, ...],
    str,
]


def _evaluate_replay(
    request: LinearDerivativeLedgerReplayRequest,
) -> tuple[_ReplayFailureValue | None, _ReplaySuccessValue | None]:
    if not _replay_context_matches(request):
        return (
            LinearDerivativeLedgerReplayFailureCode.REPLAY_CONTEXT_MISMATCH,
            None,
            None,
        ), None

    seen_fills: set[DomainId] = set()
    for entry in request.journal.entries:
        if isinstance(entry, LinearDerivativeJournalEntry):
            if type(entry) is not LinearDerivativeJournalEntry:
                return (
                    LinearDerivativeLedgerReplayFailureCode.UNSUPPORTED_TARGET_POSITION_ENTRY,
                    entry.journal_entry_id,
                    None,
                ), None
            fill_id = entry.request.transition.fill.fill_id
            if fill_id in seen_fills:
                return (
                    LinearDerivativeLedgerReplayFailureCode.DUPLICATE_FILL_ID,
                    entry.journal_entry_id,
                    fill_id,
                ), None
            seen_fills.add(fill_id)

    state = _flat_state(request)
    exact = ExactLinearRealizedPnl(
        request.contract.instrument.settlement_currency, 0, 1
    )
    cash_registration = request.ledger_schema.registration_for(
        request.settlement_cash_key
    )
    realized_units = 0
    journal_ids: list[DomainId] = []
    previous_execution = None
    for entry in request.journal.entries:
        affects_target = any(
            change.key == request.position_key for change in entry.balance_changes
        )
        if type(entry) is not LinearDerivativeJournalEntry:
            if affects_target:
                return (
                    LinearDerivativeLedgerReplayFailureCode.UNSUPPORTED_TARGET_POSITION_ENTRY,
                    entry.journal_entry_id,
                    None,
                ), None
            continue
        transition = entry.request.transition
        targets_position = transition.before.position_key == request.position_key
        if not targets_position:
            if affects_target:
                return (
                    LinearDerivativeLedgerReplayFailureCode.ENTRY_CONTEXT_MISMATCH,
                    entry.journal_entry_id,
                    transition.fill.fill_id,
                ), None
            continue
        if (
            entry.component_ref != _component_ref()
            or transition.before.contract != request.contract
            or entry.request.settlement_cash_registration.key
            != request.settlement_cash_key
            or entry.request.settlement_cash_registration.scale
            != cash_registration.scale
            or entry.request.pnl_quantization.target_scale != cash_registration.scale
        ):
            return (
                LinearDerivativeLedgerReplayFailureCode.ENTRY_CONTEXT_MISMATCH,
                entry.journal_entry_id,
                transition.fill.fill_id,
            ), None
        if (
            transition.before != state
            or (
                previous_execution is not None
                and transition.fill.execution_time < previous_execution
            )
        ):
            return (
                LinearDerivativeLedgerReplayFailureCode.TRANSITION_LINEAGE_MISMATCH,
                entry.journal_entry_id,
                transition.fill.fill_id,
            ), None
        state = transition.after
        exact = _add_exact(exact, entry.exact_realized_pnl)
        if entry.realized_pnl:
            realized_units += entry.realized_pnl[0].units
        journal_ids.append(entry.journal_entry_id)
        previous_execution = transition.fill.execution_time

    ledger_state = GenericLedger(request.ledger_schema).project(request.journal)
    if ledger_state.position_quantity(request.position_key) != state.quantity:
        return (
            LinearDerivativeLedgerReplayFailureCode.LEDGER_POSITION_MISMATCH,
            None,
            None,
        ), None
    return None, (
        request.journal.cursor_at(request.journal.entry_count),
        state,
        exact,
        Money(
            realized_units,
            cash_registration.scale,
            str(request.settlement_cash_key.currency_id),
        ),
        tuple(journal_ids),
        ledger_state.state_hash,
    )


@dataclass(frozen=True, slots=True)
class LinearDerivativeLedgerProjection:
    request: LinearDerivativeLedgerReplayRequest
    request_hash: str
    cursor: JournalReplayCursor
    position_state: LinearPositionState
    exact_realized_pnl: ExactLinearRealizedPnl
    realized_pnl: Money
    journal_entry_ids: tuple[DomainId, ...]
    ledger_state_hash: str

    def __post_init__(self) -> None:
        if type(self.request) is not LinearDerivativeLedgerReplayRequest:
            raise TypeError("request must be exact LinearDerivativeLedgerReplayRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if type(self.cursor) is not JournalReplayCursor:
            raise TypeError("cursor must be exact JournalReplayCursor")
        if type(self.position_state) is not LinearPositionState:
            raise TypeError("position_state must be exact LinearPositionState")
        if type(self.exact_realized_pnl) is not ExactLinearRealizedPnl:
            raise TypeError("exact_realized_pnl must be exact ExactLinearRealizedPnl")
        if type(self.realized_pnl) is not Money:
            raise TypeError("realized_pnl must be exact Money")
        if type(self.journal_entry_ids) is not tuple:
            raise TypeError("journal_entry_ids must be an exact tuple of DomainId")
        for value in self.journal_entry_ids:
            _require_domain_id("journal_entry_id", value, DomainIdKind.JOURNAL)
        failure, expected = _evaluate_replay(self.request)
        if failure is not None or expected is None:
            raise ValueError("Projection Request must replay successfully")
        if (
            self.cursor,
            self.position_state,
            self.exact_realized_pnl,
            self.realized_pnl,
            self.journal_entry_ids,
            self.ledger_state_hash,
        ) != expected:
            raise ValueError("Projection fields must match replayed Journal")

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_ledger_projection",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_hash": self.request_hash,
            "cursor": self.cursor,
            "position_state": self.position_state,
            "exact_realized_pnl": self.exact_realized_pnl,
            "realized_pnl": self.realized_pnl,
            "journal_entry_ids": self.journal_entry_ids,
            "ledger_state_hash": self.ledger_state_hash,
        }


@dataclass(frozen=True, slots=True)
class LinearDerivativeLedgerReplayFailure:
    request: LinearDerivativeLedgerReplayRequest
    request_hash: str
    code: LinearDerivativeLedgerReplayFailureCode
    journal_entry_id: DomainId | None
    fill_id: DomainId | None

    def __post_init__(self) -> None:
        if type(self.request) is not LinearDerivativeLedgerReplayRequest:
            raise TypeError("request must be exact LinearDerivativeLedgerReplayRequest")
        if self.request_hash != self.request.request_hash:
            raise ValueError("request_hash must match embedded Request")
        if type(self.code) is not LinearDerivativeLedgerReplayFailureCode:
            raise TypeError("code must be exact LinearDerivativeLedgerReplayFailureCode")
        if self.journal_entry_id is not None:
            _require_domain_id(
                "journal_entry_id", self.journal_entry_id, DomainIdKind.JOURNAL
            )
        if self.fill_id is not None:
            _require_domain_id("fill_id", self.fill_id, DomainIdKind.FILL)
        expected, _ = _evaluate_replay(self.request)
        if expected != (self.code, self.journal_entry_id, self.fill_id):
            raise ValueError("failure must match first replay failure")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_ledger_replay_failure",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "journal_entry_id": self.journal_entry_id,
            "fill_id": self.fill_id,
        }


@dataclass(frozen=True, slots=True)
class LinearDerivativeLedgerReplayOutcome:
    request_hash: str
    result: LinearDerivativeLedgerProjection | None
    failure: LinearDerivativeLedgerReplayFailure | None

    def __post_init__(self) -> None:
        if type(self.request_hash) is not str:
            raise TypeError("request_hash must be exact string")
        if type(self.result) not in (type(None), LinearDerivativeLedgerProjection):
            raise TypeError("result must be exact LinearDerivativeLedgerProjection or None")
        if type(self.failure) not in (
            type(None),
            LinearDerivativeLedgerReplayFailure,
        ):
            raise TypeError(
                "failure must be exact LinearDerivativeLedgerReplayFailure or None"
            )
        values = tuple(
            value for value in (self.result, self.failure) if value is not None
        )
        if len(values) != 1:
            raise ValueError("Outcome requires exactly one result or failure")
        if values[0].request_hash != self.request_hash:
            raise ValueError("Outcome request_hash must match its value")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_derivative_ledger_replay_outcome",
            "schema_version": _SCHEMA_VERSION,
            "request_hash": self.request_hash,
            "result": self.result,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class LinearDerivativeLedgerProjector:
    def project(
        self, request: LinearDerivativeLedgerReplayRequest, /
    ) -> LinearDerivativeLedgerReplayOutcome:
        if type(request) is not LinearDerivativeLedgerReplayRequest:
            raise TypeError("request must be exact LinearDerivativeLedgerReplayRequest")
        failure, values = _evaluate_replay(request)
        if failure is not None:
            code, journal_entry_id, fill_id = failure
            value = LinearDerivativeLedgerReplayFailure(
                request,
                request.request_hash,
                code,
                journal_entry_id,
                fill_id,
            )
            return LinearDerivativeLedgerReplayOutcome(
                request.request_hash, None, value
            )
        if values is None:
            raise AssertionError("successful replay requires values")
        cursor, state, exact, realized, journal_ids, ledger_hash = values
        result = LinearDerivativeLedgerProjection(
            request,
            request.request_hash,
            cursor,
            state,
            exact,
            realized,
            journal_ids,
            ledger_hash,
        )
        return LinearDerivativeLedgerReplayOutcome(
            request.request_hash, result, None
        )
