from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from crypto_quant_backtest import (
    DeterministicBarEngine,
    DeterministicTimeline,
    FinancialDispatchArtifact,
    FinancialDispatchFailure,
    FinancialDispatchFailureCode,
    FinancialDispatchOutcome,
    FinancialDispatchPlan,
    FinancialDispatchResult,
    FinancialStateView,
    FillAccountingDispatchPlan,
    MarkToMarketCloseoutPolicy,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
    PositionLotBook,
    ResolvedExecutionCase,
    ResolvedFinancialState,
    ScheduledAccountEvent,
    SnapshotProjectionPlan,
)
from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareAccountScopeDeclaration,
    CnAShareAnnouncementRevisionSetDeclaration,
    CnAShareExecutionAccountProfile,
    CnAShareIdentityHistoryDeclaration,
    CnAShareInstrumentScopeDeclaration,
    CnAShareMarketSemanticsProfile,
    CnAShareProfileComposer,
    CnAShareProfileCompositionFailureCode,
    CnAShareProfileCompositionRequest,
    CnAShareRegisterRevisionSetDeclaration,
    CnAShareResolvedProfile,
    CnAShareSimulationProfile,
)
from crypto_quant_backtest.financial_dispatch import DefaultCashFinancialDispatcher
from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    InstrumentDefinition,
    InstrumentType,
    Money,
    PortfolioSnapshot,
    PositionBalanceKey,
    PositionLotChange,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TimeInForce,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketBundleCapability, MarketEvent
from crypto_quant_trading import (
    AccountingJournal,
    CashAvailabilityRule,
    CurrencyValuationGraph,
    CashReservationUse,
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
    MarketSettlementRules,
    PortfolioValueKind,
    PortfolioValueRef,
    PositionAvailabilityRule,
    ReportingCurrencyValuation,
    ResolvedMark,
    ResourceReservationState,
    SettlementBook,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareBoard,
    CnAShareCashPaymentOutcome,
    CnAShareCashPaymentRequest,
    CnAShareCorporateActionTaxDisposition,
    CnAShareInstrumentRuleContext,
    CnAShareListingPhase,
    CnAShareOrderRuleBook,
    CnAShareRiskClass,
    CnAShareShareDeliveryOutcome,
    CnAShareShareDeliveryRequest,
    translate_corporate_action_cash_payment,
    translate_corporate_action_share_delivery,
)
from tests.kernel.profiles.cn_a_share import _commission_tax_fixtures as fee_fixtures
from tests.kernel.profiles.cn_a_share import _corporate_action_accounting_fixtures as accounting_fixtures
from tests.kernel.profiles.cn_a_share import _corporate_action_fixtures as action_fixtures
from tests.kernel.profiles.cn_a_share import test_order_rules as order_fixtures


_CNY = CurrencyId("CNY")
_MONEY_SCALE = Scale(2)
_SHARE_SCALE = Scale(0)
_SOURCE_SNAPSHOT = "sha256:" + "9" * 64
_SOURCE_MANIFEST = "sha256:" + "a" * 64
_CASH_ROLE = "corporate_action_cash_payment"
_SHARE_ROLE = "corporate_action_share_delivery"
_FINAL_ROLE = "final_snapshot"


def _failure(
    spec,
    source_event_id: str,
    input_hash: str,
    code: FinancialDispatchFailureCode,
    *subjects: str,
) -> FinancialDispatchOutcome:
    failure = FinancialDispatchFailure(spec, source_event_id, input_hash, code, tuple(subjects) or (code.value,))
    return FinancialDispatchOutcome(spec, input_hash, failure=failure)


def _rebind(outcome: FinancialDispatchOutcome, spec) -> FinancialDispatchOutcome:
    if outcome.failure is not None:
        failure = outcome.failure
        rebound_failure = FinancialDispatchFailure(
            spec,
            failure.source_event_id,
            failure.input_hash,
            failure.code,
            failure.subject_ids,
        )
        return FinancialDispatchOutcome(spec, outcome.input_hash, failure=rebound_failure)
    result = outcome.result
    if result is None:
        raise ValueError("invalid dispatcher outcome")
    rebound_result = FinancialDispatchResult(
        spec,
        result.source_event_id,
        result.journal_entries,
        result.position_lot_books,
        result.artifacts,
        result.snapshot,
    )
    return FinancialDispatchOutcome(spec, outcome.input_hash, result=rebound_result)


class CnAShareDevelopmentFinancialDispatcher:
    CASH_PAYMENT_OPERATION_KEY = "cn_a_share.corporate_action.cash_payment.v1"
    SHARE_DELIVERY_OPERATION_KEY = "cn_a_share.corporate_action.share_delivery.v1"
    CASH_PAYMENT_PHASE = 110
    SHARE_DELIVERY_PHASE = 120

    def __init__(self, resolved_profile: CnAShareResolvedProfile | None = None) -> None:
        if resolved_profile is None:
            outcome = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
            if outcome.result is None:
                raise ValueError(f"A-share profile composition failed: {outcome.failure!r}")
            resolved_profile = outcome.result
        if type(resolved_profile) is not CnAShareResolvedProfile:
            raise TypeError("resolved_profile must be exact CnAShareResolvedProfile")
        self._profile = resolved_profile
        self._delegate = DefaultCashFinancialDispatcher()

    @property
    def spec(self):
        return self._profile.financial_dispatcher_spec

    def book_fill(self, plan: FillAccountingDispatchPlan, fill, state_view: FinancialStateView, /) -> FinancialDispatchOutcome:
        return _rebind(self._delegate.book_fill(plan, fill, state_view), self.spec)

    def book_fee(self, plan: FillAccountingDispatchPlan, fill, assessment, state_view: FinancialStateView, /) -> FinancialDispatchOutcome:
        return _rebind(self._delegate.book_fee(plan, fill, assessment, state_view), self.spec)

    def dispatch_scheduled_event(self, event: ScheduledAccountEvent, state_view: FinancialStateView, /) -> FinancialDispatchOutcome:
        input_hash = canonical_sha256({"operation": "dispatch_cn_a_share_corporate_action", "event": event, "journal_hash": state_view.journal.journal_hash, "ledger_state_hash": state_view.ledger_state.state_hash})
        if event.operation_key == self.CASH_PAYMENT_OPERATION_KEY:
            return self._cash(event, state_view, input_hash)
        if event.operation_key == self.SHARE_DELIVERY_OPERATION_KEY:
            return self._share(event, state_view, input_hash)
        return _failure(self.spec, event.event_id, input_hash, FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH, event.operation_key)

    def _cash(self, event: ScheduledAccountEvent, state: FinancialStateView, input_hash: str) -> FinancialDispatchOutcome:
        request = event.payload
        if (
            type(request) is not CnAShareCashPaymentRequest
            or event.event_at.phase.rank != self.CASH_PAYMENT_PHASE
            or event.event_at != request.evidence.trigger_at
            or event.component_keys != (self._corporate_action_component_key(),)
            or ("journal.corporate_action.cash.0", request.journal_entry_id) not in event.identity_bindings
            or request.request_hash not in {value.request_hash for value in self._profile.request.cash_payment_requests}
        ):
            return _failure(self.spec, event.event_id, input_hash, FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH, self.CASH_PAYMENT_OPERATION_KEY)
        outcome = translate_corporate_action_cash_payment(request)
        if outcome.failure is not None:
            return _failure(self.spec, event.event_id, input_hash, FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE, outcome.failure.code.value)
        artifact = self._artifact(_CASH_ROLE, event, input_hash, outcome.outcome_hash, outcome)
        # G08G freezes both entries at one recorded_at and orders share ID 7 before cash ID 8.
        # Emit the payment artifact now; the listing event appends the canonical immutable batch.
        result = FinancialDispatchResult(self.spec, event.event_id, (), state.position_lot_books, (artifact,))
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def _share(self, event: ScheduledAccountEvent, state: FinancialStateView, input_hash: str) -> FinancialDispatchOutcome:
        request = event.payload
        if (
            type(request) is not CnAShareShareDeliveryRequest
            or event.event_at.phase.rank != self.SHARE_DELIVERY_PHASE
            or event.event_at != request.evidence.trigger_at
            or event.component_keys != (self._corporate_action_component_key(),)
            or ("journal.corporate_action.share.0", request.journal_entry_id) not in event.identity_bindings
            or request.request_hash not in {value.request_hash for value in self._profile.request.share_delivery_requests}
        ):
            return _failure(self.spec, event.event_id, input_hash, FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH, self.SHARE_DELIVERY_OPERATION_KEY)
        current_lots = tuple(
            lot
            for key, lots in state.position_lot_books
            if key == request.entitlement.position_key
            for lot in lots
        )
        if current_lots != request.open_lots:
            return _failure(self.spec, event.event_id, input_hash, FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH, "current_lot_state")
        share = translate_corporate_action_share_delivery(request)
        cash = tuple(translate_corporate_action_cash_payment(value) for value in self._profile.request.cash_payment_requests)
        if share.failure is not None or any(value.failure is not None for value in cash):
            failure = share.failure or next(value.failure for value in cash if value.failure is not None)
            assert failure is not None
            return _failure(self.spec, event.event_id, input_hash, FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE, failure.code.value)
        if share.journal_entry is None or any(value.journal_entry is None for value in cash):
            raise ValueError("successful translators require journal entries")
        lot_change = share.journal_entry.position_lot_changes[0]
        if lot_change.after is None:
            raise ValueError("share delivery must retain the target lot")
        lot_books = dict(state.position_lot_books)
        lot_books[request.entitlement.position_key] = (lot_change.after,)
        artifact = self._artifact(_SHARE_ROLE, event, input_hash, share.outcome_hash, share)
        entries = (share.journal_entry, *(value.journal_entry for value in cash if value.journal_entry is not None))
        result = FinancialDispatchResult(
            self.spec,
            event.event_id,
            entries,
            tuple(sorted(lot_books.items(), key=lambda value: canonical_bytes(value[0]))),
            (artifact,),
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def _corporate_action_component_key(self) -> str:
        return next(value.component_key for value in self._profile.market_semantics.component_manifest if value.port_type.value == "corporate_action_model")

    def _artifact(self, role: str, event: ScheduledAccountEvent, input_hash: str, result_hash: str, payload: object) -> FinancialDispatchArtifact:
        component = next(value for value in self._profile.market_semantics.component_manifest if value.port_type.value == "corporate_action_model")
        return FinancialDispatchArtifact(role, event.event_id, event.event_at, component.component_key, component.component_version, component.component_digest, input_hash, result_hash, payload)

    def project_final_snapshot(self, plan: FinancialDispatchPlan, state_view: FinancialStateView, /) -> FinancialDispatchOutcome:
        generic_plan = replace(plan, dispatcher_spec=self._delegate.spec)
        outcome = self._delegate.project_final_snapshot(generic_plan, state_view)
        rebound = _rebind(outcome, self.spec)
        if rebound.result is None:
            return rebound
        artifacts = tuple(replace(value, role=_FINAL_ROLE, component_digest=self.spec.config_hash) for value in rebound.result.artifacts)
        result = replace(rebound.result, artifacts=artifacts)
        return FinancialDispatchOutcome(self.spec, rebound.input_hash, result=result)


@dataclass(frozen=True, slots=True)
class _BalanceChangeView:
    authority: BalanceChange

    @property
    def delta(self):
        return self.authority.value

    def __getattr__(self, name: str):
        return getattr(self.authority, name)

    def to_canonical_dict(self) -> dict[str, object]:
        return self.authority.to_canonical_dict()


@dataclass(frozen=True, slots=True)
class _JournalEntryView:
    authority: AccountingJournalEntry

    @property
    def balance_changes(self) -> tuple[_BalanceChangeView, ...]:
        return tuple(_BalanceChangeView(value) for value in self.authority.balance_changes)

    def __getattr__(self, name: str):
        return getattr(self.authority, name)

    def to_canonical_dict(self) -> dict[str, object]:
        return self.authority.to_canonical_dict()


@dataclass(frozen=True, slots=True)
class _OutcomeView:
    authority: CnAShareCashPaymentOutcome | CnAShareShareDeliveryOutcome

    @property
    def failure(self):
        return self.authority.failure

    @property
    def journal_entry(self):
        return None if self.authority.journal_entry is None else _JournalEntryView(self.authority.journal_entry)

    @property
    def outcome_hash(self) -> str:
        return self.authority.outcome_hash

    def __getattr__(self, name: str):
        return getattr(self.authority, name)

    def to_canonical_dict(self) -> dict[str, object]:
        return self.authority.to_canonical_dict()


@dataclass(frozen=True, slots=True)
class CnAShareDevelopmentJourneyResult:
    resolved_profile: CnAShareResolvedProfile
    execution_case_hash: str
    trace_hash: str
    operation_keys: tuple[str, ...]
    event_phases: tuple[int, ...]
    cash_payment_outcome: object
    share_delivery_outcome: object
    final_journal_hash: str
    final_ledger_state: object
    final_lot_book_hash: str
    final_portfolio_snapshot: PortfolioSnapshot
    full_replay_ledger_hash: str
    prefix_resume_ledger_hash: str
    full_replay_lot_book_hash: str
    prefix_resume_lot_book_hash: str
    decision_grade_eligible: bool
    deployment_authorized: bool

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_development_journey_result", "schema_version": 1,
            "resolved_profile": self.resolved_profile, "execution_case_hash": self.execution_case_hash,
            "trace_hash": self.trace_hash, "operation_keys": self.operation_keys,
            "event_phases": self.event_phases, "cash_payment_outcome": self.cash_payment_outcome,
            "share_delivery_outcome": self.share_delivery_outcome, "final_journal_hash": self.final_journal_hash,
            "final_ledger_state": self.final_ledger_state, "final_lot_book_hash": self.final_lot_book_hash,
            "final_portfolio_snapshot": self.final_portfolio_snapshot,
            "full_replay_ledger_hash": self.full_replay_ledger_hash,
            "prefix_resume_ledger_hash": self.prefix_resume_ledger_hash,
            "full_replay_lot_book_hash": self.full_replay_lot_book_hash,
            "prefix_resume_lot_book_hash": self.prefix_resume_lot_book_hash,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _context() -> CnAShareInstrumentRuleContext:
    return CnAShareInstrumentRuleContext(CnAShareBoard.MAIN, CnAShareRiskClass.STANDARD, CnAShareListingPhase.SEASONED, "development.cn-a-share.instrument-scope.v1", "sha256:" + "5" * 64)


def _scoped_action_key(entitlement) -> str:
    announcement = entitlement.query.announcement
    assert announcement is not None
    return f"{entitlement.position_key.venue_id.value}|{entitlement.position_key.instrument_id}|{announcement.corporate_action_id}"


def _scoped_snapshot_key(entitlement) -> str:
    snapshot = entitlement.query.snapshot
    assert snapshot is not None
    return f"{snapshot.account_id}|{snapshot.position_key}|{snapshot.snapshot_id}"


def _scoped_revision_key(entitlement) -> str:
    snapshot = entitlement.query.snapshot
    assert snapshot is not None
    return f"{snapshot.account_id}|{snapshot.position_key}|{snapshot.register_series_id}|{snapshot.revision_id}"


def _base_request(venue: str = "xshe") -> CnAShareProfileCompositionRequest:
    entitlement = accounting_fixtures.entitlement(venue)
    cash = accounting_fixtures.cash_request(entitlement)
    share = accounting_fixtures.share_request(entitlement)
    announcement = entitlement.query.announcement
    snapshot = entitlement.query.snapshot
    assert announcement is not None and snapshot is not None
    instrument = entitlement.query.instrument
    coverage_from = action_fixtures.local_instant(date(2026, 7, 6), 0)
    coverage_to = action_fixtures.local_instant(date(2026, 7, 31), 0)
    available_at = entitlement.captured_at
    instrument_scope = CnAShareInstrumentScopeDeclaration(
        instrument, _context(), coverage_from, coverage_to, available_at,
        True, True, False, False, False, False, False, False, False, False,
        _SOURCE_SNAPSHOT, _SOURCE_MANIFEST,
    )
    account_scope = CnAShareAccountScopeDeclaration(
        entitlement.account_id, entitlement.position_key.venue_id, coverage_from, coverage_to,
        available_at, True, True, False, False, False, _SOURCE_SNAPSHOT, _SOURCE_MANIFEST,
    )
    announcement_set = CnAShareAnnouncementRevisionSetDeclaration(
        entitlement.position_key.venue_id, instrument.instrument_id, announcement.corporate_action_id,
        ((announcement.revision_id, announcement.supersedes_revision_id, announcement.candidate_hash),),
        announcement.revision_id, False, coverage_from, coverage_to, available_at,
        _SOURCE_SNAPSHOT, _SOURCE_MANIFEST,
    )
    register_set = CnAShareRegisterRevisionSetDeclaration(
        entitlement.account_id, entitlement.position_key, snapshot.register_series_id,
        ((snapshot.revision_id, snapshot.supersedes_revision_id, snapshot.snapshot_hash),),
        snapshot.revision_id, coverage_from, coverage_to, available_at,
        _SOURCE_SNAPSHOT, _SOURCE_MANIFEST,
    )
    history = CnAShareIdentityHistoryDeclaration(
        ((_scoped_action_key(entitlement), announcement.candidate_hash),),
        ((_scoped_snapshot_key(entitlement), snapshot.snapshot_hash),),
        ((_scoped_revision_key(entitlement), snapshot.snapshot_hash),),
        coverage_from, coverage_to, available_at, _SOURCE_SNAPSHOT, _SOURCE_MANIFEST,
    )
    order_band = replace(order_fixtures._main_band(venue), effective_from=date(2026, 7, 6), effective_to_exclusive=date(2026, 7, 31))
    order_book = CnAShareOrderRuleBook("equity.cn_a_share.cash.order-rules.development.v1", 1, (order_band,))
    market_book = fee_fixtures.market_rule_book()
    tax_book = fee_fixtures.tax_rule_book()
    composed_at = SimulationInstant(action_fixtures.local_instant(date(2026, 7, 20), 18), TimelinePhase(200, "profile_composition"), SourceSequence(0))
    return CnAShareProfileCompositionRequest(
        instrument_scope, account_scope, announcement_set, register_set, history,
        entitlement.calendar, order_book, market_book, tax_book, entitlement.rule_book,
        (entitlement,), (cash,), (share,),
        __import__("crypto_quant_backtest").TimelineWindow(coverage_from, coverage_from, coverage_to),
        composed_at,
    )


def _apply_failure(request: CnAShareProfileCompositionRequest, code: CnAShareProfileCompositionFailureCode) -> CnAShareProfileCompositionRequest:
    if code is CnAShareProfileCompositionFailureCode.MISSING_INSTRUMENT_SCOPE: return replace(request, instrument_scope=None)
    if code is CnAShareProfileCompositionFailureCode.MISSING_ACCOUNT_SCOPE: return replace(request, account_scope=None)
    if code is CnAShareProfileCompositionFailureCode.MISSING_ANNOUNCEMENT_REVISION_SET: return replace(request, announcement_revision_set=None)
    if code is CnAShareProfileCompositionFailureCode.MISSING_REGISTER_REVISION_SET: return replace(request, register_revision_set=None)
    if code is CnAShareProfileCompositionFailureCode.MISSING_IDENTITY_HISTORY: return replace(request, identity_history=None)
    if code is CnAShareProfileCompositionFailureCode.INSTRUMENT_SCOPE_MISMATCH:
        assert request.instrument_scope is not None
        return replace(request, instrument_scope=replace(request.instrument_scope, is_stock_connect=True))
    if code is CnAShareProfileCompositionFailureCode.ACCOUNT_SCOPE_MISMATCH:
        assert request.account_scope is not None
        return replace(request, account_scope=replace(request.account_scope, authorizes_available_margin_use=True))
    if code is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH:
        assert request.account_scope is not None
        return replace(request, account_scope=replace(request.account_scope, account_id="account-b"))
    if code is CnAShareProfileCompositionFailureCode.REVISION_CLOSURE_MISMATCH:
        assert request.announcement_revision_set is not None
        return replace(request, announcement_revision_set=replace(request.announcement_revision_set, is_cancelled=True))
    if code is CnAShareProfileCompositionFailureCode.CROSS_QUERY_IDENTITY_CONFLICT:
        assert request.identity_history is not None
        key = request.identity_history.corporate_action_hashes[0][0]
        return replace(request, identity_history=replace(request.identity_history, corporate_action_hashes=request.identity_history.corporate_action_hashes + ((key, "sha256:" + "f" * 64),)))
    if code is CnAShareProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH:
        assert request.instrument_scope is not None
        return replace(request, instrument_scope=replace(request.instrument_scope, coverage_to_exclusive=UtcInstant(request.timeline_window.end_exclusive.epoch_nanoseconds - 1)))
    if code is CnAShareProfileCompositionFailureCode.EVIDENCE_NOT_AVAILABLE:
        assert request.instrument_scope is not None
        later = SimulationInstant(UtcInstant(request.composed_at.instant.epoch_nanoseconds + 1), request.composed_at.phase, request.composed_at.source_sequence)
        return replace(request, instrument_scope=replace(request.instrument_scope, available_at=later))
    if code is CnAShareProfileCompositionFailureCode.UNSUPPORTED_TAX_DISPOSITION:
        cash = request.cash_payment_requests[0]
        return replace(request, cash_payment_requests=(replace(cash, evidence=replace(cash.evidence, tax_disposition=CnAShareCorporateActionTaxDisposition.APPLIED)),))
    if code is CnAShareProfileCompositionFailureCode.UNSUPPORTED_XSHG_SHARE_DELIVERY:
        return _base_request("xshg")
    if code is CnAShareProfileCompositionFailureCode.COMPONENT_IDENTITY_CONFLICT:
        assert request.identity_history is not None
        return replace(request, identity_history=replace(request.identity_history, source_manifest_hash="sha256:" + "b" * 64))
    raise AssertionError(code)


def build_cn_a_share_resolved_request(*, failure_codes: tuple[CnAShareProfileCompositionFailureCode, ...] = ()) -> CnAShareProfileCompositionRequest:
    if type(failure_codes) is not tuple or not all(type(value) is CnAShareProfileCompositionFailureCode for value in failure_codes):
        raise TypeError("failure_codes must contain exact failure codes")
    request = _base_request()
    for code in reversed(sorted(set(failure_codes), key=lambda value: tuple(CnAShareProfileCompositionFailureCode).index(value))):
        request = _apply_failure(request, code)
    return request


def _opening_entry(share: CnAShareShareDeliveryRequest) -> AccountingJournalEntry:
    lot = share.open_lots[0]
    return AccountingJournalEntry(
        accounting_fixtures.journal_id("6"), AccountingEntryType.FILL_BOOKED,
        share.entitlement.account_id, share.entitlement.position_key.venue_id,
        lot.opened_at,
        SimulationInstant(lot.opened_at, TimelinePhase(40, "accounting"), SourceSequence(0)),
        (lot.source_id,), (BalanceChange(lot.position_key, lot.quantity),), (), (), (),
        position_lot_changes=(PositionLotChange(None, lot),),
    )


def _ledger_schema(cash: CnAShareCashPaymentRequest, share: CnAShareShareDeliveryRequest) -> LedgerSchema:
    return LedgerSchema((LedgerBalanceRegistration(cash.cash_key, _MONEY_SCALE), LedgerBalanceRegistration(share.entitlement.position_key, _SHARE_SCALE)))


def _settlement_rules(cash: CnAShareCashPaymentRequest, share: CnAShareShareDeliveryRequest) -> MarketSettlementRules:
    return MarketSettlementRules.create(
        policy_key="equity.cn_a_share.cash.settlement.development.v1", policy_version=1,
        account_id=share.entitlement.account_id,
        cash_rules=(CashAvailabilityRule(cash.cash_key, False, False, False, (CashReservationUse.CASH, CashReservationUse.FEE_RESERVE), (CashReservationUse.CASH, CashReservationUse.FEE_RESERVE), (CashReservationUse.MARGIN,)),),
        position_rules=(PositionAvailabilityRule(share.entitlement.position_key, False),),
    )


def _initial_snapshot(journal: AccountingJournal, schema: LedgerSchema, account_id: str, timestamp: UtcInstant) -> PortfolioSnapshot:
    ledger = GenericLedger(schema).project(journal)
    zero = Money(0, _MONEY_SCALE, "CNY")
    graph = CurrencyValuationGraph(timestamp, PricePurpose.VALUATION, ())
    return PortfolioSnapshot(account_id, timestamp, _CNY, ledger.cash_balances, ledger.position_balances, zero, zero, zero, zero, zero, (), ledger.state_hash, canonical_sha256(()), canonical_sha256(()), graph.graph_hash)


def _snapshot_plan(share: CnAShareShareDeliveryRequest, cash: CnAShareCashPaymentRequest, timestamp: UtcInstant) -> SnapshotProjectionPlan:
    instrument = share.entitlement.position_key.instrument_id
    price = Price(1_000, _MONEY_SCALE, str(instrument), "CNY")
    mark = ResolvedMark(instrument, _CNY, PricePurpose.VALUATION, price, UtcInstant(timestamp.epoch_nanoseconds - 1), UtcInstant(timestamp.epoch_nanoseconds - 1), timestamp, 1, "cn-a-share.valuation", "cn-a-share-final-mark", "revision-1", "cn-a-share.valuation.no-stale.v1", 1, "sha256:" + "e" * 64)
    graph = CurrencyValuationGraph(timestamp, PricePurpose.VALUATION, ())
    resolution = graph.resolve(_CNY, _CNY).resolution
    assert resolution is not None
    quantization = QuantizationPolicy("cn-a-share-position-value-v1", _MONEY_SCALE, RoundingPolicy.HALF_EVEN)
    market_value = Money(710_000, _MONEY_SCALE, "CNY")
    unrealized = Money(-40_000, _MONEY_SCALE, "CNY")
    valuations = (
        ReportingCurrencyValuation(PortfolioValueRef(PortfolioValueKind.CASH, cash.cash_key), Money(7_000, _MONEY_SCALE, "CNY"), Money(7_000, _MONEY_SCALE, "CNY"), resolution, graph.graph_hash),
        ReportingCurrencyValuation(PortfolioValueRef(PortfolioValueKind.POSITION_MARKET_VALUE, share.entitlement.position_key), market_value, market_value, resolution, graph.graph_hash, quantization),
        ReportingCurrencyValuation(PortfolioValueRef(PortfolioValueKind.UNREALIZED_PNL, share.entitlement.position_key), unrealized, unrealized, resolution, graph.graph_hash),
    )
    return SnapshotProjectionPlan((mark,), valuations, _CNY, _MONEY_SCALE, timestamp, graph.graph_hash)


def _event(event_id: str, request: CnAShareCashPaymentRequest | CnAShareShareDeliveryRequest, operation: str, component_key: str, binding_key: str, role: str) -> tuple[ScheduledAccountEvent, MarketEvent]:
    scheduled = ScheduledAccountEvent(event_id, request.evidence.trigger_at, operation, (component_key,), ((binding_key, request.journal_entry_id),), request, request, (role,))
    market = MarketEvent(event_id, "cn-a-share.account.events", "account_financial_event", MarketBundleCapability("account.financial-event", 1), request.entitlement.position_key.instrument_id, request.evidence.trigger_at.instant, request.evidence.trigger_at.instant, request.evidence.trigger_at.phase, request.evidence.trigger_at.source_sequence, "revision-1", None, "development.cn-a-share.account-events.v1", "sha256:" + "d" * 64, {"operation_key": operation})
    return scheduled, market


def build_cn_a_share_execution_case(*, resolved_profile: CnAShareResolvedProfile | None = None) -> ResolvedExecutionCase:
    if resolved_profile is None:
        outcome = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
        if outcome.result is None: raise ValueError(f"A-share profile composition failed: {outcome.failure!r}")
        resolved_profile = outcome.result
    request = resolved_profile.request
    cash = request.cash_payment_requests[0]; share = request.share_delivery_requests[0]
    component = next(value for value in resolved_profile.market_semantics.component_manifest if value.port_type.value == "corporate_action_model")
    cash_event, cash_market = _event("cn-a-share-cash-payment", cash, CnAShareDevelopmentFinancialDispatcher.CASH_PAYMENT_OPERATION_KEY, component.component_key, "journal.corporate_action.cash.0", _CASH_ROLE)
    share_event, share_market = _event("cn-a-share-share-delivery", share, CnAShareDevelopmentFinancialDispatcher.SHARE_DELIVERY_OPERATION_KEY, component.component_key, "journal.corporate_action.share.0", _SHARE_ROLE)
    end = UtcInstant(share.evidence.trigger_at.instant.epoch_nanoseconds + 1)
    reader = InMemoryMarketBundleReader.build(
        bundle_key="equity.cn_a_share.development-journey.v1", schema_version=1,
        coverage_start=request.timeline_window.data_start, coverage_end_exclusive=end,
        instrument_catalog_hash=canonical_sha256(request.instrument_scope.instrument if request.instrument_scope else ()),
        capabilities=(MarketBundleCapability("account.financial-event", 1),),
        streams={"cn-a-share.account.events": (cash_market, share_market)},
    )
    timeline = DeterministicTimeline.open(reader=reader, stream_keys=("cn-a-share.account.events",), window=__import__("crypto_quant_backtest").TimelineWindow(request.timeline_window.data_start, request.timeline_window.trading_start, end))
    if not isinstance(timeline, DeterministicTimeline): raise ValueError("A-share development Timeline failed")
    opening = _opening_entry(share); journal = AccountingJournal.from_entries((opening,)); schema = _ledger_schema(cash, share)
    initial = _initial_snapshot(journal, schema, share.entitlement.account_id, request.timeline_window.trading_start)
    financial = ResolvedFinancialState(journal, schema, initial, (PositionLotBook(share.entitlement.position_key, share.open_lots),), (), (), (), SettlementBook(share.entitlement.account_id), _settlement_rules(cash, share))
    snapshot = _snapshot_plan(share, cash, end)
    execution_model = NextEligibleBarOpenModel.create(actions=tuple((value, action) for value, action in ((TimeInForce.DAY, NoEligibleBarAction.EXPIRE), (TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE), (TimeInForce.IOC, NoEligibleBarAction.EXPIRE), (TimeInForce.FOK, NoEligibleBarAction.EXPIRE), (TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE))))
    return ResolvedExecutionCase(
        "equity.cn_a_share.development-journey.execution-case.v1", 1,
        canonical_sha256({"profile_digest": resolved_profile.profile_digest, "events": (cash_event, share_event)}),
        timeline, 1, __import__("crypto_quant_backtest").PrecomputedTargetStream("targets", ()), (), (), financial,
        FinancialDispatchPlan(resolved_profile.financial_dispatcher_spec, (cash_event, share_event), snapshot, tuple(sorted((_CASH_ROLE, _SHARE_ROLE, _FINAL_ROLE)))),
        execution_model, snapshot, MarkToMarketCloseoutPolicy(),
    )


def _lot_hash(state) -> str:
    return canonical_sha256(tuple((balance.key, balance.lots) for balance in state.position_balances if balance.lots))


def run_cn_a_share_development_journey() -> CnAShareDevelopmentJourneyResult:
    composition = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    if composition.result is None: raise ValueError(f"A-share profile composition failed: {composition.failure!r}")
    profile = composition.result
    case = build_cn_a_share_execution_case(resolved_profile=profile)
    outcome = DeterministicBarEngine(CnAShareDevelopmentFinancialDispatcher(profile)).run(case)
    if outcome.result is None: raise ValueError(f"A-share development Journey failed: {outcome!r}")
    engine = outcome.result
    cash_artifact = next(value for value in engine.financial_artifacts if value.role == _CASH_ROLE)
    share_artifact = next(value for value in engine.financial_artifacts if value.role == _SHARE_ROLE)
    cash_outcome = cash_artifact.payload; share_outcome = share_artifact.payload
    if type(cash_outcome) is not CnAShareCashPaymentOutcome or type(share_outcome) is not CnAShareShareDeliveryOutcome:
        raise ValueError("Journey artifacts do not contain G08G outcomes")
    ledger = GenericLedger(case.financial_state.ledger_schema)
    full = ledger.project(engine.final_journal)
    prefix = ledger.project(engine.final_journal, stop=engine.final_journal.cursor_at(2))
    resumed = ledger.resume(engine.final_journal, prefix)
    return CnAShareDevelopmentJourneyResult(
        profile, case.case_hash, engine.trace.trace_hash,
        (CnAShareDevelopmentFinancialDispatcher.CASH_PAYMENT_OPERATION_KEY, CnAShareDevelopmentFinancialDispatcher.SHARE_DELIVERY_OPERATION_KEY),
        (CnAShareDevelopmentFinancialDispatcher.CASH_PAYMENT_PHASE, CnAShareDevelopmentFinancialDispatcher.SHARE_DELIVERY_PHASE),
        _OutcomeView(cash_outcome), _OutcomeView(share_outcome), engine.final_journal.journal_hash, engine.final_ledger_state,
        _lot_hash(engine.final_ledger_state), engine.final_portfolio_snapshot,
        full.state_hash, resumed.state_hash, _lot_hash(full), _lot_hash(resumed), False, False,
    )


__all__ = [
    "CnAShareDevelopmentFinancialDispatcher", "CnAShareDevelopmentJourneyResult",
    "build_cn_a_share_resolved_request", "build_cn_a_share_execution_case",
    "run_cn_a_share_development_journey",
]
