"""Runtime-only simulated-register projection for ADR 0012 dividend actions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    Money,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import FinalFeeAssessmentResult, LedgerState
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCorporateActionSourceRef,
    CnAShareRegisteredPositionSnapshot,
)

from .cn_a_share_dividend_profile_v2 import CnAShareDividendProfileV2
from .financial_dispatch import (
    DefaultCashFinancialDispatcher,
    FillAccountingDispatchPlan,
    FinancialDispatchArtifact,
    FinancialDispatchFailure,
    FinancialDispatchFailureCode,
    FinancialDispatchOutcome,
    FinancialDispatchPlan,
    FinancialDispatchResult,
    FinancialDispatcherSpec,
    FinancialStateView,
    ScheduledAccountEvent,
    default_cash_financial_dispatcher_spec,
)


_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SOURCE_KEY = "tushare.000703.simulated-register.v2"
_REGISTER_SERIES_ID = "tushare.000703.simulated-ledger-register.v2"


def _action(profile: CnAShareDividendProfileV2, action_id: str) -> tuple[int, object]:
    if type(action_id) is not str:
        raise TypeError("action_id must be str")
    matches = tuple(
        (index, value)
        for index, value in enumerate(profile.actions)
        if value.action_id == action_id
    )
    if len(matches) != 1:
        raise ValueError("action_id must identify exactly one profile action")
    return matches[0]


def _record_close(
    profile: CnAShareDividendProfileV2, action_id: str
) -> SimulationInstant:
    index, action = _action(profile, action_id)
    try:
        local = datetime.strptime(action.record_date, "%Y%m%d").replace(
            hour=15,
            tzinfo=_SHANGHAI,
        )
    except ValueError as error:
        raise ValueError("action record_date is invalid") from error
    phase_rank, phase_code = profile.simulated_register_policy.record_close_phase
    return SimulationInstant(
        UtcInstant.from_datetime(local),
        TimelinePhase(phase_rank, phase_code),
        SourceSequence(index),
    )


def _identity(
    profile: CnAShareDividendProfileV2,
    action_id: str,
    record_close_at: SimulationInstant,
    ledger_state: LedgerState,
) -> str:
    return canonical_sha256(
        {
            "type": "cn_a_share_dividend_simulated_register_projection",
            "schema_version": 2,
            "profile_hash": profile.profile_hash,
            "action_id": action_id,
            "record_close_at": record_close_at,
            "ledger_state_hash": ledger_state.state_hash,
            "registered_quantity": ledger_state.position_quantity(
                profile.simulated_register_policy.position_key
            ),
        }
    )


def _snapshot(
    profile: CnAShareDividendProfileV2,
    action_id: str,
    record_close_at: SimulationInstant,
    ledger_state: LedgerState,
) -> CnAShareRegisteredPositionSnapshot:
    policy = profile.simulated_register_policy
    identity = _identity(profile, action_id, record_close_at, ledger_state)
    source = CnAShareCorporateActionSourceRef(_SOURCE_KEY, identity)
    return CnAShareRegisteredPositionSnapshot(
        f"tushare.000703.simulated-register:{identity}",
        _REGISTER_SERIES_ID,
        f"tushare.000703.simulated-register-revision:{identity}",
        None,
        policy.account_id,
        policy.position_key,
        record_close_at,
        record_close_at,
        ledger_state.position_quantity(policy.position_key),
        source,
    )


@dataclass(frozen=True, slots=True)
class CnAShareDividendRegisterProjectionV2:
    profile: CnAShareDividendProfileV2
    action_id: str
    record_close_at: SimulationInstant
    ledger_state: LedgerState
    snapshot: CnAShareRegisteredPositionSnapshot
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.profile) is not CnAShareDividendProfileV2:
            raise TypeError("profile must be exact CnAShareDividendProfileV2")
        if type(self.record_close_at) is not SimulationInstant:
            raise TypeError("record_close_at must be exact SimulationInstant")
        if type(self.ledger_state) is not LedgerState:
            raise TypeError("ledger_state must be exact LedgerState")
        if type(self.snapshot) is not CnAShareRegisteredPositionSnapshot:
            raise TypeError("snapshot must be exact CnAShareRegisteredPositionSnapshot")
        if self.record_close_at != _record_close(self.profile, self.action_id):
            raise ValueError("record_close_at does not match profile action boundary")
        expected = _snapshot(
            self.profile,
            self.action_id,
            self.record_close_at,
            self.ledger_state,
        )
        if self.snapshot != expected:
            raise ValueError("simulated register snapshot identity mismatch")
        if (
            type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("register projection must retain development qualification")

    @property
    def ledger_state_hash(self) -> str:
        return self.ledger_state.state_hash

    @property
    def projection_hash(self) -> str:
        return _identity(
            self.profile,
            self.action_id,
            self.record_close_at,
            self.ledger_state,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_register_projection_v2",
            "schema_version": 2,
            "profile_hash": self.profile.profile_hash,
            "action_id": self.action_id,
            "record_close_at": self.record_close_at,
            "ledger_state_hash": self.ledger_state_hash,
            "snapshot": self.snapshot,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
            "projection_hash": self.projection_hash,
        }


def project_tushare_000703_dividend_register_v2(
    profile: CnAShareDividendProfileV2,
    action_id: str,
    record_close_at: SimulationInstant,
    ledger_state: LedgerState,
    /,
) -> CnAShareDividendRegisterProjectionV2:
    if type(profile) is not CnAShareDividendProfileV2:
        raise TypeError("profile must be exact CnAShareDividendProfileV2")
    if type(record_close_at) is not SimulationInstant:
        raise TypeError("record_close_at must be exact SimulationInstant")
    if type(ledger_state) is not LedgerState:
        raise TypeError("ledger_state must be exact LedgerState")
    return CnAShareDividendRegisterProjectionV2(
        profile,
        action_id,
        record_close_at,
        ledger_state,
        _snapshot(profile, action_id, record_close_at, ledger_state),
        True,
        False,
        False,
        False,
    )


_COMPONENT_KEY = "equity.cn_a_share.tushare-dividend-action.v2"
_RECORD_OPERATION = "cn_a_share.tushare_dividend.record_register.v2"
_ENTITLEMENT_OPERATION = "cn_a_share.tushare_dividend.ex_date_entitlement.v2"
_PAYMENT_OPERATION = "cn_a_share.tushare_dividend.cash_payment.v2"
_RECORD_ROLE_PREFIX = "tushare_dividend_register:"
_ENTITLEMENT_ROLE_PREFIX = "tushare_dividend_entitlement:"
_PAYMENT_ROLE_PREFIX = "tushare_dividend_cash_payment:"
_CNY = CurrencyId("CNY")


def _event_hash(
    profile: CnAShareDividendProfileV2, action_id: str, purpose: str
) -> str:
    return canonical_sha256(
        {
            "type": "cn_a_share_tushare_dividend_scheduled_event",
            "schema_version": 2,
            "profile_hash": profile.profile_hash,
            "action_id": action_id,
            "purpose": purpose,
        }
    )


def _entitlement_at(
    profile: CnAShareDividendProfileV2, action_id: str
) -> SimulationInstant:
    index, action = _action(profile, action_id)
    try:
        local = datetime.strptime(action.ex_date, "%Y%m%d").replace(
            hour=9,
            minute=30,
            tzinfo=_SHANGHAI,
        )
    except ValueError as error:
        raise ValueError("action ex_date is invalid") from error
    return SimulationInstant(
        UtcInstant.from_datetime(local),
        TimelinePhase(105, "corporate_action_entitlement"),
        SourceSequence(index),
    )


def _payment_at(
    profile: CnAShareDividendProfileV2, action_id: str
) -> SimulationInstant:
    index, action = _action(profile, action_id)
    try:
        local = datetime.strptime(action.payment_date, "%Y%m%d").replace(
            hour=9,
            minute=30,
            tzinfo=_SHANGHAI,
        )
    except ValueError as error:
        raise ValueError("action payment_date is invalid") from error
    return SimulationInstant(
        UtcInstant.from_datetime(local),
        TimelinePhase(110, "corporate_action_payment"),
        SourceSequence(index),
    )


def _component_digest(profile: CnAShareDividendProfileV2) -> str:
    return canonical_sha256(
        {
            "type": "cn_a_share_tushare_dividend_action_component",
            "schema_version": 2,
            "component_key": _COMPONENT_KEY,
            "component_version": 2,
            "profile_hash": profile.profile_hash,
        }
    )


def _cash_key(profile: CnAShareDividendProfileV2) -> CashBalanceKey:
    policy = profile.simulated_register_policy
    return CashBalanceKey(policy.account_id, VenueId("xshe"), _CNY)


@dataclass(frozen=True, slots=True)
class CnAShareDividendRecordEventV2:
    profile_hash: str
    action_id: str
    action_index: int
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.profile_hash) is not str or not self.profile_hash.startswith("sha256:"):
            raise ValueError("profile_hash must be canonical sha256")
        if type(self.action_id) is not str or not self.action_id:
            raise ValueError("action_id must be canonical text")
        if type(self.action_index) is not int or self.action_index < 0:
            raise ValueError("action_index must be nonnegative int")
        if (
            type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("event must retain development qualification")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_record_event_v2",
            "schema_version": 2,
            "profile_hash": self.profile_hash,
            "action_id": self.action_id,
            "action_index": self.action_index,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class CnAShareDividendEntitlementEventV2:
    profile_hash: str
    action_id: str
    action_index: int
    record_event_id: str
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.profile_hash) is not str or not self.profile_hash.startswith("sha256:"):
            raise ValueError("profile_hash must be canonical sha256")
        if type(self.action_id) is not str or not self.action_id:
            raise ValueError("action_id must be canonical text")
        if type(self.action_index) is not int or self.action_index < 0:
            raise ValueError("action_index must be nonnegative int")
        if type(self.record_event_id) is not str or not self.record_event_id:
            raise ValueError("record_event_id must be canonical text")
        if (
            type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("event must retain development qualification")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_entitlement_event_v2",
            "schema_version": 2,
            "profile_hash": self.profile_hash,
            "action_id": self.action_id,
            "action_index": self.action_index,
            "record_event_id": self.record_event_id,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class CnAShareDividendPaymentEventV2:
    profile_hash: str
    action_id: str
    action_index: int
    entitlement_event_id: str
    journal_entry_id: DomainId
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.profile_hash) is not str or not self.profile_hash.startswith("sha256:"):
            raise ValueError("profile_hash must be canonical sha256")
        if type(self.action_id) is not str or not self.action_id:
            raise ValueError("action_id must be canonical text")
        if type(self.action_index) is not int or self.action_index < 0:
            raise ValueError("action_index must be nonnegative int")
        if type(self.entitlement_event_id) is not str or not self.entitlement_event_id:
            raise ValueError("entitlement_event_id must be canonical text")
        if type(self.journal_entry_id) is not DomainId or self.journal_entry_id.kind is not DomainIdKind.JOURNAL:
            raise TypeError("journal_entry_id must be exact Journal DomainId")
        if (
            type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("event must retain development qualification")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_payment_event_v2",
            "schema_version": 2,
            "profile_hash": self.profile_hash,
            "action_id": self.action_id,
            "action_index": self.action_index,
            "entitlement_event_id": self.entitlement_event_id,
            "journal_entry_id": self.journal_entry_id,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def build_tushare_000703_dividend_scheduled_events_v2(
    profile: CnAShareDividendProfileV2, /
) -> tuple[ScheduledAccountEvent, ...]:
    if type(profile) is not CnAShareDividendProfileV2:
        raise TypeError("profile must be exact CnAShareDividendProfileV2")
    events: list[ScheduledAccountEvent] = []
    for index, action in enumerate(profile.actions):
        record_hash = _event_hash(profile, action.action_id, "record")
        entitlement_hash = _event_hash(profile, action.action_id, "entitlement")
        payment_hash = _event_hash(profile, action.action_id, "payment")
        record_id = f"tushare.000703.dividend.record:{record_hash}"
        entitlement_id = f"tushare.000703.dividend.entitlement:{entitlement_hash}"
        payment_id = f"tushare.000703.dividend.payment:{payment_hash}"
        journal_id = DomainId(
            DomainIdKind.JOURNAL,
            "jnl_" + payment_hash.removeprefix("sha256:"),
        )
        qualifications = (True, False, False, False)
        record_payload = CnAShareDividendRecordEventV2(
            profile.profile_hash,
            action.action_id,
            index,
            *qualifications,
        )
        entitlement_payload = CnAShareDividendEntitlementEventV2(
            profile.profile_hash,
            action.action_id,
            index,
            record_id,
            *qualifications,
        )
        payment_payload = CnAShareDividendPaymentEventV2(
            profile.profile_hash,
            action.action_id,
            index,
            entitlement_id,
            journal_id,
            *qualifications,
        )
        events.extend(
            (
                ScheduledAccountEvent(
                    record_id,
                    _record_close(profile, action.action_id),
                    _RECORD_OPERATION,
                    (_COMPONENT_KEY,),
                    (),
                    record_payload,
                    record_payload,
                    (_RECORD_ROLE_PREFIX + action.action_id,),
                ),
                ScheduledAccountEvent(
                    entitlement_id,
                    _entitlement_at(profile, action.action_id),
                    _ENTITLEMENT_OPERATION,
                    (_COMPONENT_KEY,),
                    (),
                    entitlement_payload,
                    entitlement_payload,
                    (_ENTITLEMENT_ROLE_PREFIX + action.action_id,),
                ),
                ScheduledAccountEvent(
                    payment_id,
                    _payment_at(profile, action.action_id),
                    _PAYMENT_OPERATION,
                    (_COMPONENT_KEY,),
                    ((f"journal.tushare_dividend.{index}", journal_id),),
                    payment_payload,
                    payment_payload,
                    (_PAYMENT_ROLE_PREFIX + action.action_id,),
                ),
            )
        )
    return tuple(
        sorted(events, key=lambda event: (event.event_at, event.event_id))
    )


@dataclass(frozen=True, slots=True)
class CnAShareDividendCashEntitlementV2:
    profile_hash: str
    action_id: str
    register_projection_hash: str
    entitlement_at: SimulationInstant
    gross_cash: Money
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.profile_hash) is not str or not self.profile_hash.startswith("sha256:"):
            raise ValueError("profile_hash must be canonical sha256")
        if type(self.action_id) is not str or not self.action_id:
            raise ValueError("action_id must be canonical text")
        if type(self.register_projection_hash) is not str or not self.register_projection_hash.startswith("sha256:"):
            raise ValueError("register_projection_hash must be canonical sha256")
        if type(self.entitlement_at) is not SimulationInstant:
            raise TypeError("entitlement_at must be exact SimulationInstant")
        if (
            type(self.gross_cash) is not Money
            or self.gross_cash.currency != "CNY"
            or self.gross_cash.scale != Scale(2)
            or self.gross_cash.units < 0
        ):
            raise ValueError("cash entitlement must be nonnegative CNY-cent money")
        if (
            type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("cash entitlement must retain development qualification")

    @property
    def entitlement_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_cash_entitlement_v2",
            "schema_version": 2,
            "profile_hash": self.profile_hash,
            "action_id": self.action_id,
            "register_projection_hash": self.register_projection_hash,
            "entitlement_at": self.entitlement_at,
            "gross_cash": self.gross_cash,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class CnAShareDividendCashPaymentV2:
    profile_hash: str
    action_id: str
    register_projection_hash: str
    entitlement_hash: str
    payment_at: SimulationInstant
    gross_cash: Money
    net_cash: Money
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.profile_hash) is not str or not self.profile_hash.startswith("sha256:"):
            raise ValueError("profile_hash must be canonical sha256")
        if type(self.action_id) is not str or not self.action_id:
            raise ValueError("action_id must be canonical text")
        if type(self.register_projection_hash) is not str or not self.register_projection_hash.startswith("sha256:"):
            raise ValueError("register_projection_hash must be canonical sha256")
        if type(self.entitlement_hash) is not str or not self.entitlement_hash.startswith("sha256:"):
            raise ValueError("entitlement_hash must be canonical sha256")
        if type(self.payment_at) is not SimulationInstant:
            raise TypeError("payment_at must be exact SimulationInstant")
        for value in (self.gross_cash, self.net_cash):
            if type(value) is not Money or value.currency != "CNY" or value.scale != Scale(2) or value.units < 0:
                raise ValueError("cash payment must be nonnegative CNY-cent money")
        if self.net_cash != self.gross_cash:
            raise ValueError("development cash payment cannot apply withholding")
        if (
            type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("cash payment must retain development qualification")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_cash_payment_v2",
            "schema_version": 2,
            "profile_hash": self.profile_hash,
            "action_id": self.action_id,
            "register_projection_hash": self.register_projection_hash,
            "entitlement_hash": self.entitlement_hash,
            "payment_at": self.payment_at,
            "gross_cash": self.gross_cash,
            "net_cash": self.net_cash,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _dispatcher_spec(profile: CnAShareDividendProfileV2) -> FinancialDispatcherSpec:
    base = default_cash_financial_dispatcher_spec()
    return FinancialDispatcherSpec(
        "equity.cn_a_share.tushare-dividend-financial-dispatch.v2",
        2,
        canonical_sha256(
            {
                "type": "cn_a_share_tushare_dividend_financial_dispatcher",
                "schema_version": 2,
                "profile_hash": profile.profile_hash,
                "base_spec_hash": base.spec_hash,
                "component_digest": _component_digest(profile),
            }
        ),
        base.position_accounting_component,
        base.financing_component,
        base.margin_component,
        base.liquidation_audit_component,
        base.snapshot_projection_key,
        base.snapshot_projection_version,
    )


def _dispatch_failure(
    spec: FinancialDispatcherSpec,
    event: ScheduledAccountEvent,
    input_hash: str,
    code: FinancialDispatchFailureCode,
    *subjects: str,
) -> FinancialDispatchOutcome:
    return FinancialDispatchOutcome(
        spec,
        input_hash,
        failure=FinancialDispatchFailure(
            spec,
            event.event_id,
            input_hash,
            code,
            tuple(subjects) or (code.value,),
        ),
    )


class CnAShareDividendFinancialDispatcherV2:
    def __init__(self, profile: CnAShareDividendProfileV2) -> None:
        if type(profile) is not CnAShareDividendProfileV2:
            raise TypeError("profile must be exact CnAShareDividendProfileV2")
        self._profile = profile
        self._delegate = DefaultCashFinancialDispatcher()
        self._spec = _dispatcher_spec(profile)

    @property
    def spec(self) -> FinancialDispatcherSpec:
        return self._spec

    def _rebind(self, outcome: FinancialDispatchOutcome) -> FinancialDispatchOutcome:
        if outcome.failure is not None:
            failure = outcome.failure
            return FinancialDispatchOutcome(
                self.spec,
                outcome.input_hash,
                failure=FinancialDispatchFailure(
                    self.spec,
                    failure.source_event_id,
                    failure.input_hash,
                    failure.code,
                    failure.subject_ids,
                ),
            )
        result = outcome.result
        if result is None:
            raise ValueError("financial dispatcher outcome is invalid")
        return FinancialDispatchOutcome(
            self.spec,
            outcome.input_hash,
            result=FinancialDispatchResult(
                self.spec,
                result.source_event_id,
                result.journal_entries,
                result.position_lot_books,
                result.artifacts,
                result.snapshot,
            ),
        )

    def book_fill(
        self,
        plan: FillAccountingDispatchPlan,
        fill: object,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        return self._rebind(self._delegate.book_fill(plan, fill, state_view))

    def book_fee(
        self,
        plan: FillAccountingDispatchPlan,
        fill: object,
        assessment: FinalFeeAssessmentResult,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        return self._rebind(self._delegate.book_fee(plan, fill, assessment, state_view))

    def dispatch_scheduled_event(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        input_hash = canonical_sha256(
            {
                "operation": "dispatch_tushare_000703_dividend_v2",
                "event": event,
                "journal_hash": state_view.journal.journal_hash,
                "ledger_state_hash": state_view.ledger_state.state_hash,
                "artifact_hashes": tuple(value.artifact_hash for value in state_view.artifacts),
            }
        )
        expected = {
            value.event_id: value
            for value in build_tushare_000703_dividend_scheduled_events_v2(self._profile)
        }
        if expected.get(event.event_id) != event:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                event.operation_key,
            )
        if any(
            artifact.role in event.expected_artifact_roles
            for artifact in state_view.artifacts
        ):
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.ARTIFACT_COVERAGE_MISMATCH,
                event.event_id,
            )
        if event.operation_key == _RECORD_OPERATION:
            return self._record(event, state_view, input_hash)
        if event.operation_key == _ENTITLEMENT_OPERATION:
            return self._entitlement(event, state_view, input_hash)
        if event.operation_key == _PAYMENT_OPERATION:
            return self._payment(event, state_view, input_hash)
        return _dispatch_failure(
            self.spec,
            event,
            input_hash,
            FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
            event.operation_key,
        )

    def _artifact(
        self,
        role: str,
        event: ScheduledAccountEvent,
        input_hash: str,
        payload: object,
    ) -> FinancialDispatchArtifact:
        return FinancialDispatchArtifact(
            role,
            event.event_id,
            event.event_at,
            _COMPONENT_KEY,
            2,
            _component_digest(self._profile),
            input_hash,
            canonical_sha256(payload),
            payload,
        )

    def _record(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        input_hash: str,
    ) -> FinancialDispatchOutcome:
        payload = event.payload
        if type(payload) is not CnAShareDividendRecordEventV2:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                "record_payload",
            )
        try:
            projection = project_tushare_000703_dividend_register_v2(
                self._profile,
                payload.action_id,
                event.event_at,
                state_view.ledger_state,
            )
        except (TypeError, ValueError) as error:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                type(error).__name__,
            )
        artifact = self._artifact(
            _RECORD_ROLE_PREFIX + projection.action_id,
            event,
            input_hash,
            projection,
        )
        return FinancialDispatchOutcome(
            self.spec,
            input_hash,
            result=FinancialDispatchResult(
                self.spec,
                event.event_id,
                (),
                state_view.position_lot_books,
                (artifact,),
            ),
        )

    def _entitlement(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        input_hash: str,
    ) -> FinancialDispatchOutcome:
        payload = event.payload
        if type(payload) is not CnAShareDividendEntitlementEventV2:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                "entitlement_payload",
            )
        action_id = payload.action_id
        matches = tuple(
            artifact
            for artifact in state_view.artifacts
            if artifact.role == _RECORD_ROLE_PREFIX + action_id
            and artifact.source_event_id == payload.record_event_id
            and artifact.occurred_at == _record_close(self._profile, action_id)
            and artifact.component_key == _COMPONENT_KEY
            and artifact.component_version == 2
            and artifact.component_digest == _component_digest(self._profile)
            and type(artifact.payload) is CnAShareDividendRegisterProjectionV2
        )
        if len(matches) != 1:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "missing_register_projection",
            )
        projection = matches[0].payload
        if projection.profile != self._profile or projection.action_id != action_id:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "register_projection_identity",
            )
        quantity = projection.snapshot.registered_quantity
        if quantity.scale != Scale(0) or quantity.units < 0:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "registered_quantity_precision_or_sign",
            )
        _, action = _action(self._profile, action_id)
        gross = Money(
            quantity.units * action.cash_per_share.units,
            Scale(2),
            "CNY",
        )
        entitlement = CnAShareDividendCashEntitlementV2(
            self._profile.profile_hash,
            action_id,
            projection.projection_hash,
            event.event_at,
            gross,
            True,
            False,
            False,
            False,
        )
        artifact = self._artifact(
            _ENTITLEMENT_ROLE_PREFIX + action_id,
            event,
            input_hash,
            entitlement,
        )
        return FinancialDispatchOutcome(
            self.spec,
            input_hash,
            result=FinancialDispatchResult(
                self.spec,
                event.event_id,
                (),
                state_view.position_lot_books,
                (artifact,),
            ),
        )

    def _payment(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        input_hash: str,
    ) -> FinancialDispatchOutcome:
        payload = event.payload
        if type(payload) is not CnAShareDividendPaymentEventV2:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                "payment_payload",
            )
        action_id = payload.action_id
        journal_entry_id = payload.journal_entry_id
        matches = tuple(
            artifact
            for artifact in state_view.artifacts
            if artifact.role == _ENTITLEMENT_ROLE_PREFIX + action_id
            and artifact.source_event_id == payload.entitlement_event_id
            and artifact.occurred_at == _entitlement_at(self._profile, action_id)
            and artifact.component_key == _COMPONENT_KEY
            and artifact.component_version == 2
            and artifact.component_digest == _component_digest(self._profile)
            and type(artifact.payload) is CnAShareDividendCashEntitlementV2
        )
        if len(matches) != 1:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "missing_cash_entitlement",
            )
        entitlement = matches[0].payload
        if (
            entitlement.profile_hash != self._profile.profile_hash
            or entitlement.action_id != action_id
            or entitlement.entitlement_at != _entitlement_at(self._profile, action_id)
        ):
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "cash_entitlement_identity",
            )
        register_matches = tuple(
            artifact
            for artifact in state_view.artifacts
            if artifact.role == _RECORD_ROLE_PREFIX + action_id
            and artifact.source_event_id
            == f"tushare.000703.dividend.record:{_event_hash(self._profile, action_id, 'record')}"
            and artifact.occurred_at == _record_close(self._profile, action_id)
            and artifact.component_key == _COMPONENT_KEY
            and artifact.component_version == 2
            and artifact.component_digest == _component_digest(self._profile)
            and type(artifact.payload) is CnAShareDividendRegisterProjectionV2
        )
        if len(register_matches) != 1:
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "missing_register_projection",
            )
        projection = register_matches[0].payload
        quantity = projection.snapshot.registered_quantity
        _, action = _action(self._profile, action_id)
        expected_gross = Money(
            quantity.units * action.cash_per_share.units,
            Scale(2),
            "CNY",
        )
        if (
            projection.profile != self._profile
            or projection.action_id != action_id
            or quantity.scale != Scale(0)
            or quantity.units < 0
            or entitlement.register_projection_hash != projection.projection_hash
            or entitlement.gross_cash != expected_gross
        ):
            return _dispatch_failure(
                self.spec,
                event,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "cash_entitlement_evidence",
            )
        gross = entitlement.gross_cash
        payment = CnAShareDividendCashPaymentV2(
            self._profile.profile_hash,
            action_id,
            entitlement.register_projection_hash,
            entitlement.entitlement_hash,
            event.event_at,
            gross,
            gross,
            True,
            False,
            False,
            False,
        )
        entries = ()
        if gross.units:
            entries = (
                AccountingJournalEntry(
                    journal_entry_id=journal_entry_id,
                    entry_type=AccountingEntryType.CORPORATE_ACTION_CASH_PAID,
                    account_id=self._profile.simulated_register_policy.account_id,
                    venue_id=VenueId("xshe"),
                    effective_time=event.event_at.instant,
                    recorded_at=event.event_at,
                    source_ids=(
                        self._profile.source_snapshot_hash,
                        self._profile.source_response_sha256,
                        self._profile.source_action_set_hash,
                        action.source_row_sha256,
                        entitlement.register_projection_hash,
                        entitlement.entitlement_hash,
                        event.event_id,
                    ),
                    balance_changes=(BalanceChange(_cash_key(self._profile), gross),),
                    realized_pnl=(),
                    fees=(),
                    financing=(),
                    position_lot_changes=(),
                ),
            )
        artifact = self._artifact(
            _PAYMENT_ROLE_PREFIX + action_id,
            event,
            input_hash,
            payment,
        )
        return FinancialDispatchOutcome(
            self.spec,
            input_hash,
            result=FinancialDispatchResult(
                self.spec,
                event.event_id,
                entries,
                state_view.position_lot_books,
                (artifact,),
            ),
        )

    def project_final_snapshot(
        self,
        plan: FinancialDispatchPlan,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        return self._rebind(
            self._delegate.project_final_snapshot(
                replace(plan, dispatcher_spec=self._delegate.spec),
                state_view,
            )
        )
