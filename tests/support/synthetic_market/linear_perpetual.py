"""Development-only synthetic linear-perpetual financial composition."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, cast

from crypto_quant_backtest import (
    BAR_OPEN_CAPABILITY,
    BAR_OPEN_EVENT_TYPE,
    BacktestProfileRegistry,
    BarLiquidityEvidence,
    BuildArtifactRole,
    ConservativeLinearLiquidationAuditModel,
    DeterministicTimeline,
    ExecutionAccountProfileRegistration,
    ExecutionCaseComposer,
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    FeeAccountingDispatchPlan,
    FillAccountingDispatchPlan,
    FinancialDispatchArtifact,
    FinancialDispatcherSpec,
    FinancialDispatchFailure,
    FinancialDispatchFailureCode,
    FinancialDispatchOutcome,
    FinancialDispatchPlan,
    FinancialDispatchResult,
    FinancialStateView,
    LinearLiquidationAccountWindowEvidence,
    LinearLiquidationAuditRequest,
    LinearLiquidationMarkBarEvidence,
    MarketSemanticsProfileRegistration,
    MarkToMarketCloseoutPolicy,
    PositionLotBook,
    PrecomputedTargetStream,
    ProfileResolver,
    RequestedResultGrade,
    ResolvedBacktestRequest,
    ResolvedBarExecution,
    ResolvedExecutionCase,
    ResolvedFinancialState,
    ResolvedOrderAdmission,
    ScheduledAccountEvent,
    SimulationProfileRegistration,
    SlippageApplicabilityEnvelope,
    SlippageMarketState,
    SnapshotProjectionPlan,
    StrategyFamily,
    TimelineWindow,
)
from crypto_quant_backtest.financial_dispatch import (
    LinearDerivativeFillAccountingPlan as SyntheticLinearFillPayload,
)
from crypto_quant_backtest.financial_dispatch import (
    LinearFundingAccountEventPlan as SyntheticFundingDispatchPayload,
)
from crypto_quant_backtest.financial_dispatch import (
    LinearMarginLiquidationAuditPlan as SyntheticMarginAuditPayload,
)
from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    DomainIdKind,
    Fill,
    IdentityNamespace,
    InstrumentDefinition,
    InstrumentType,
    Money,
    Order,
    OrderEvent,
    OrderEventType,
    OrderSide,
    PortfolioSnapshot,
    PositionEffect,
    Price,
    PricePurpose,
    Quantity,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    ValuationMarkReference,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketEvent,
)
from crypto_quant_trading import (
    AccountingJournal,
    FinalFeeAssessmentResult,
    FundingSlotId,
    LedgerBalanceRegistration,
    LinearAccountMarginProjection,
    LinearAccountMarginProjectionRequest,
    LinearAccountMarginProjector,
    LinearDerivativeAccounting,
    LinearDerivativeAccountingRequest,
    LinearDerivativeJournalEntry,
    LinearDerivativeLedgerProjector,
    LinearDerivativeLedgerReplayRequest,
    LinearFundingAccounting,
    LinearFundingApplicationIdentity,
    LinearFundingApplicationKey,
    LinearFundingEligibilityPositionSnapshot,
    LinearFundingEligibilityRequest,
    LinearFundingEligibilityResolver,
    LinearFundingMarkEvidence,
    LinearFundingPublicationStatus,
    LinearFundingRatePublicationCandidate,
    LinearFundingSettlementEvidence,
    LinearFundingSettlementRequest,
    LinearInstrumentMarginModel,
    LinearInstrumentMarginRequest,
    LinearMarginLedgerEvidence,
    LinearMarginLeverageEvidence,
    LinearMarginMarkEvidence,
    LinearMarginReservationEvidence,
    LinearMarginRuleBook,
    LinearMarginRuleInterval,
    LinearMarginTier,
    LinearPerpetualContract,
    LinearPositionProjectionRequest,
    LinearPositionProjector,
    LinearPositionValuationEvidence,
    OrderEventRecord,
    OrderEventStream,
    OrderReservationSchedule,
    OrderReservationUpdate,
    ProfileComponentRef,
    ProfilePortType,
    ReservationCommitment,
    ResolvedMark,
    SettlementBook,
    StaleMarkPolicy,
)

from tests.kernel.market_rules import _fixtures as market_rules
from tests.runtime.engine import _fixtures as cash
from tests.runtime.resolution import _fixtures as resolution_fixtures

PROFILE_KEY = "synthetic.linear-perpetual.development.v1"
LIMITATIONS = (
    "bar-extremes-do-not-identify-intrabar-path-or-liquidation-time",
    "synthetic_market_profile",
)
ACCOUNT_EVENT_CAPABILITY = MarketBundleCapability("account.financial-event", 1)
DISPATCH_PHASE = TimelinePhase(110, "account_financial_dispatch")
SETTLEMENT_REGISTRATION = LedgerBalanceRegistration(cash.CASH_KEY, cash.MONEY_SCALE)
CONTRACT = LinearPerpetualContract(
    instrument=InstrumentDefinition(
        cash.BTC,
        InstrumentType.LINEAR_PERPETUAL,
        CurrencyId("BTC"),
        cash.USD,
        cash.USD,
    ),
    quantity_scale=cash.QUANTITY_SCALE,
    price_scale=cash.MONEY_SCALE,
    contract_multiplier=Rate(1, Scale(0), "base_quantity_per_contract"),
)


def _sim(nanoseconds: int, phase: TimelinePhase, sequence: int = 0) -> SimulationInstant:
    return SimulationInstant(UtcInstant(nanoseconds), phase, SourceSequence(sequence))


def _domain(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def _component(port_type: ProfilePortType, key: str, implementation: object) -> ProfileComponentRef:
    ref = implementation.component_ref
    if ref.port_type is not port_type:
        raise AssertionError("component port mismatch")
    return ref


def dispatcher_spec() -> FinancialDispatcherSpec:
    position = _component(
        ProfilePortType.POSITION_ACCOUNTING_MODEL,
        "linear",
        LinearDerivativeAccounting(),
    )
    financing = _component(
        ProfilePortType.FINANCING_MODEL,
        "linear",
        LinearFundingAccounting(),
    )
    margin = _component(
        ProfilePortType.MARGIN_MODEL,
        "linear",
        LinearInstrumentMarginModel(),
    )
    liquidation = ConservativeLinearLiquidationAuditModel().component_ref
    config = {
        "type": "synthetic_linear_financial_dispatcher_config",
        "profile_key": PROFILE_KEY,
        "position": position,
        "financing": financing,
        "margin": margin,
        "liquidation": liquidation,
        "limitations": LIMITATIONS,
    }
    return FinancialDispatcherSpec(
        f"{PROFILE_KEY}.financial-dispatcher",
        1,
        canonical_sha256(config),
        position,
        financing,
        margin,
        liquidation,
        f"{PROFILE_KEY}.portfolio-snapshot",
        1,
    )


@dataclass(frozen=True, slots=True)
class SyntheticLinearPerpetualDevelopmentProfile:
    market_semantics: object
    simulation: object
    execution_account: object
    financial_dispatcher: FinancialDispatcherSpec
    profile_key: str = PROFILE_KEY
    profile_version: int = 1
    grade: str = "development"
    limitations: tuple[str, ...] = LIMITATIONS
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if self.profile_key != PROFILE_KEY or self.profile_version != 1:
            raise ValueError("invalid synthetic linear Profile identity")
        if self.grade != "development" or self.limitations != LIMITATIONS:
            raise ValueError("synthetic linear Profile must remain development-only")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("synthetic linear Profile cannot authorize deployment")
        if self.financial_dispatcher != dispatcher_spec():
            raise ValueError("synthetic linear dispatcher spec mismatch")

    @classmethod
    def _create(cls) -> SyntheticLinearPerpetualDevelopmentProfile:
        from tests.support.synthetic_market import SyntheticCashDevelopmentProfile

        base = SyntheticCashDevelopmentProfile._create()
        return cls(
            base.market_semantics,
            base.simulation,
            base.execution_account,
            dispatcher_spec(),
        )

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_linear_perpetual_development_profile",
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "grade": self.grade,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
            "market_semantics": self.market_semantics,
            "simulation": self.simulation,
            "execution_account": self.execution_account,
            "financial_dispatcher": self.financial_dispatcher,
        }


@dataclass(frozen=True, slots=True)
class SyntheticLinearFillSemantics:
    position_key: object
    contract: LinearPerpetualContract
    settlement_cash_registration: LedgerBalanceRegistration
    pnl_quantization: QuantizationPolicy

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_linear_fill_semantics",
            "position_key": self.position_key,
            "contract": self.contract,
            "settlement_cash_registration": self.settlement_cash_registration,
            "pnl_quantization": self.pnl_quantization,
        }


@dataclass(frozen=True, slots=True)
class SyntheticFundingDispatchSemantics:
    target_funding_time: UtcInstant
    applied_rate: Rate
    funding_price: Price
    recorded_at: SimulationInstant

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_funding_dispatch_semantics",
            "target_funding_time": self.target_funding_time,
            "applied_rate": self.applied_rate,
            "funding_price": self.funding_price,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class SyntheticAccountEventPayload:
    event_key: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "synthetic_account_event_payload", "event_key": self.event_key}


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


def _replay(journal: AccountingJournal):
    outcome = LinearDerivativeLedgerProjector().project(
        LinearDerivativeLedgerReplayRequest(
            journal,
            cash.ledger_schema(),
            cash.POSITION_KEY,
            CONTRACT,
            cash.CASH_KEY,
        )
    )
    if outcome.result is None:
        raise ValueError("synthetic linear Journal replay failed")
    return outcome.result


def _resolved_mark(
    purpose: PricePurpose,
    price: Price,
    evaluated_at: SimulationInstant,
    suffix: str,
) -> tuple[ResolvedMark, StaleMarkPolicy]:
    policy = StaleMarkPolicy(
        f"{PROFILE_KEY}.{purpose.value}.{suffix}",
        1,
        purpose,
        100,
        True,
    )
    resolved = ResolvedMark(
        instrument_id=cash.BTC,
        quote_currency_id=cash.USD,
        price_purpose=purpose,
        price=price,
        observed_at=UtcInstant(evaluated_at.instant.epoch_nanoseconds - 2),
        available_at=UtcInstant(evaluated_at.instant.epoch_nanoseconds - 1),
        resolved_at=evaluated_at.instant,
        age_nanoseconds=2,
        stream_id=f"{PROFILE_KEY}.{purpose.value}.stream",
        source_event_id=f"{purpose.value}:{suffix}",
        revision_id="revision-1",
        stale_policy_key=policy.policy_key,
        stale_policy_version=policy.policy_version,
        stale_policy_hash=policy.policy_hash,
    )
    return resolved, policy


def _margin_rule_book() -> LinearMarginRuleBook:
    tier_scale = Scale(2)
    tiers = (
        LinearMarginTier(
            "synthetic-linear-tier-1",
            Money(0, tier_scale, "USD"),
            Money(25_000, tier_scale, "USD"),
            Rate(20, Scale(0), "notional_per_initial_margin"),
            Rate(1, Scale(2), "maintenance_margin_fraction_of_notional"),
            Money(0, tier_scale, "USD"),
        ),
        LinearMarginTier(
            "synthetic-linear-tier-2",
            Money(25_000, tier_scale, "USD"),
            None,
            Rate(10, Scale(0), "notional_per_initial_margin"),
            Rate(2, Scale(2), "maintenance_margin_fraction_of_notional"),
            Money(250, tier_scale, "USD"),
        ),
    )
    interval = LinearMarginRuleInterval(
        "synthetic-linear-margin-interval",
        UtcInstant(0),
        None,
        _sim(1, TimelinePhase(10, "margin_rule")),
        tiers,
        f"{PROFILE_KEY}.margin-rules",
        "sha256:" + "a1" * 32,
    )
    return LinearMarginRuleBook.create(
        rule_book_key=f"{PROFILE_KEY}.margin-rules",
        rule_book_version=1,
        instrument_id=cash.BTC,
        settlement_currency_id=cash.USD,
        tier_scale=tier_scale,
        intervals=(interval,),
    )


def _margin_projection(
    state: FinancialStateView,
    evaluated_at: SimulationInstant,
    valuation_price: Price,
    margin_price: Price,
) -> LinearAccountMarginProjection:
    replay = _replay(state.journal)
    valuation_mark, valuation_policy = _resolved_mark(
        PricePurpose.VALUATION,
        valuation_price,
        evaluated_at,
        str(evaluated_at.instant.epoch_nanoseconds),
    )
    margin_mark, margin_policy = _resolved_mark(
        PricePurpose.MARGIN,
        margin_price,
        evaluated_at,
        str(evaluated_at.instant.epoch_nanoseconds),
    )
    margin_request = LinearInstrumentMarginRequest(
        cash.POSITION_KEY,
        CONTRACT,
        replay.position_state.quantity,
        evaluated_at,
        LinearMarginLeverageEvidence(
            cash.ACCOUNT,
            cash.BTC,
            Rate(10, Scale(0), "notional_per_initial_margin"),
            UtcInstant(0),
            None,
            _sim(1, TimelinePhase(10, "leverage")),
            f"{PROFILE_KEY}.leverage",
            "sha256:" + "b2" * 32,
        ),
        _margin_rule_book(),
        LinearMarginMarkEvidence(margin_mark, margin_policy),
        SETTLEMENT_REGISTRATION,
        QuantizationPolicy(
            f"{PROFILE_KEY}.margin-ceiling",
            cash.MONEY_SCALE,
            RoundingPolicy.CEILING,
        ),
    )
    margin = LinearInstrumentMarginModel().evaluate_margin(margin_request)
    if margin.result is None:
        raise ValueError("synthetic linear margin evaluation failed")
    request = LinearAccountMarginProjectionRequest(
        cash.ACCOUNT,
        cash.VENUE,
        evaluated_at,
        LinearMarginLedgerEvidence(
            state.ledger_state,
            evaluated_at,
            evaluated_at,
            f"{PROFILE_KEY}.ledger",
            state.ledger_state.state_hash,
        ),
        (
            LinearPositionValuationEvidence(
                replay.position_state,
                valuation_mark,
                valuation_policy,
            ),
        ),
        (margin.result,),
        LinearMarginReservationEvidence(
            state.reservation_state,
            evaluated_at,
            evaluated_at,
            f"{PROFILE_KEY}.reservations",
            state.reservation_state.state_hash,
        ),
        SETTLEMENT_REGISTRATION,
        QuantizationPolicy(
            f"{PROFILE_KEY}.unrealized-half-even",
            cash.MONEY_SCALE,
            RoundingPolicy.HALF_EVEN,
        ),
    )
    projected = LinearAccountMarginProjector().project(request)
    if projected.projection is None:
        raise ValueError("synthetic linear account margin projection failed")
    return projected.projection


def _portfolio_snapshot(
    state: FinancialStateView,
    projection: LinearAccountMarginProjection,
    timestamp: UtcInstant,
) -> PortfolioSnapshot:
    valuation = projection.request.position_valuations[0].resolved_mark
    marks = (
        ValuationMarkReference(
            valuation.source_event_id,
            valuation.instrument_id,
            valuation.price_purpose,
            valuation.observed_at,
        ),
    )
    return PortfolioSnapshot(
        cash.ACCOUNT,
        timestamp,
        cash.USD,
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
            tuple(value.stale_policy for value in projection.request.position_valuations)
        ),
        canonical_sha256({"type": "synthetic-linear-usd-valuation-graph"}),
    )


class SyntheticLinearFinancialDispatcher:
    def __init__(self) -> None:
        self._spec = dispatcher_spec()

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
        if (
            plan.position_accounting_component != self.spec.position_accounting_component
            or plan.expected_fill_id != fill.fill_id
            or type(plan.position_payload) is not SyntheticLinearFillPayload
        ):
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                str(fill.fill_id),
            )
        payload = plan.position_payload
        prior_fills = tuple(
            entry.request.transition.fill
            for entry in state_view.journal.entries
            if type(entry) is LinearDerivativeJournalEntry
        )
        projected = LinearPositionProjector().project(
            LinearPositionProjectionRequest(
                payload.position_key,
                payload.contract,
                prior_fills + (fill,),
            )
        )
        if projected.result is None:
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "position_projection",
            )
        transition = projected.result.transitions[-1]
        accounting = LinearDerivativeAccounting().translate_position_fact(
            LinearDerivativeAccountingRequest(
                transition,
                payload.settlement_cash_registration,
                payload.pnl_quantization,
                plan.fill_journal_entry_id,
                plan.fill_recorded_at,
            )
        )
        if accounting.result is None:
            return _failure(
                self.spec,
                plan.source_event_id,
                input_hash,
                FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                "position_accounting",
            )
        role = plan.expected_artifact_roles[0]
        artifact = FinancialDispatchArtifact(
            role,
            plan.source_event_id,
            plan.fill_recorded_at,
            self.spec.position_accounting_component.component_key,
            self.spec.position_accounting_component.component_version,
            self.spec.position_accounting_component.component_digest,
            input_hash,
            accounting.result.result_hash,
            accounting.result,
        )
        result = FinancialDispatchResult(
            self.spec,
            plan.source_event_id,
            (accounting.result.journal_entry,),
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
        return _failure(
            self.spec,
            plan.source_event_id,
            canonical_sha256({"operation": "book_fee"}),
            FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
            "book_fee_not_implemented",
        )

    def dispatch_scheduled_event(
        self,
        event: ScheduledAccountEvent,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        input_hash = canonical_sha256(
            {
                "operation": event.operation_key,
                "event": event,
                "journal_hash": state_view.journal.journal_hash,
            }
        )
        try:
            if event.operation_key == "funding":
                return self._funding(event, state_view, input_hash)
            if event.operation_key == "margin_liquidation_audit":
                return self._margin_audit(event, state_view, input_hash)
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
        if type(payload) is not SyntheticFundingDispatchPayload:
            raise TypeError("invalid funding payload")
        target = event.event_at.instant
        eligibility_at = _sim(
            target.epoch_nanoseconds,
            TimelinePhase(100, "funding_eligibility"),
        )
        replay = _replay(state.journal)
        slot = FundingSlotId.derive(cash.BTC, target)
        snapshot = LinearFundingEligibilityPositionSnapshot(
            f"{event.event_id}.position-snapshot",
            f"{PROFILE_KEY}.position-series",
            "revision-1",
            None,
            slot,
            eligibility_at,
            _sim(target.epoch_nanoseconds, TimelinePhase(105, "position_snapshot")),
            replay.cursor,
            replay,
            replay.position_state,
        )
        publication = LinearFundingRatePublicationCandidate(
            slot,
            LinearFundingPublicationStatus.FINAL_RATE,
            Rate(1, Scale(4), "funding_fraction_of_notional"),
            f"{event.event_id}.publication",
            "sha256:" + "c3" * 32,
            UtcInstant(target.epoch_nanoseconds - 1),
            _sim(target.epoch_nanoseconds, TimelinePhase(50, "funding_publication")),
            "revision-1",
            None,
            f"{PROFILE_KEY}.funding-publication",
            "sha256:" + "d4" * 32,
        )
        eligibility_request = LinearFundingEligibilityRequest(
            slot,
            cash.POSITION_KEY,
            CONTRACT,
            eligibility_at,
            (publication,),
            snapshot,
            event.event_at,
        )
        eligibility = LinearFundingEligibilityResolver().resolve(eligibility_request)
        if eligibility.result is None:
            raise ValueError(f"funding eligibility failed: {eligibility.failure!r}")
        policy = StaleMarkPolicy(
            f"{PROFILE_KEY}.funding-mark",
            1,
            PricePurpose.FUNDING,
            100,
            True,
        )
        funding_mark = LinearFundingMarkEvidence(
            ResolvedMark(
                cash.BTC,
                cash.USD,
                PricePurpose.FUNDING,
                Price(10_000, cash.MONEY_SCALE, str(cash.BTC), "USD"),
                UtcInstant(target.epoch_nanoseconds - 2),
                UtcInstant(target.epoch_nanoseconds - 1),
                target,
                2,
                f"{PROFILE_KEY}.funding-mark.stream",
                f"{event.event_id}.funding-mark",
                "revision-1",
                policy.policy_key,
                policy.policy_version,
                policy.policy_hash,
            ),
            policy,
        )
        identity = payload.settlement_identity
        settlement = LinearFundingSettlementEvidence(
            identity.application_key,
            target,
            event.event_at,
            eligibility.result.published_rate,
            f"{event.event_id}.settlement",
            "sha256:" + "e5" * 32,
            "revision-1",
            None,
            f"{PROFILE_KEY}.funding-settlement",
            "sha256:" + "f6" * 32,
        )
        request = LinearFundingSettlementRequest(
            eligibility.result,
            settlement,
            funding_mark,
            identity,
            cash.POSITION_KEY,
            CONTRACT,
            SETTLEMENT_REGISTRATION,
            QuantizationPolicy(
                f"{PROFILE_KEY}.funding-half-even",
                cash.MONEY_SCALE,
                RoundingPolicy.HALF_EVEN,
            ),
        )
        assessed = LinearFundingAccounting().assess_financing(request)
        if assessed.result is None:
            raise ValueError("funding accounting failed")
        artifacts = (
            FinancialDispatchArtifact(
                "funding_eligibility",
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
                "funding_accounting",
                event.event_id,
                payload.recorded_at,
                self.spec.financing_component.component_key,
                self.spec.financing_component.component_version,
                self.spec.financing_component.component_digest,
                request.request_hash,
                assessed.result.result_hash,
                assessed.result,
            ),
        )
        result = FinancialDispatchResult(
            self.spec,
            event.event_id,
            (assessed.result.journal_entry,),
            state.position_lot_books,
            artifacts,
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def _margin_audit(
        self,
        event: ScheduledAccountEvent,
        state: FinancialStateView,
        input_hash: str,
    ) -> FinancialDispatchOutcome:
        payload = event.payload
        if type(payload) is not SyntheticMarginAuditPayload:
            raise TypeError("invalid margin audit payload")
        projection = _margin_projection(
            state,
            payload.evaluated_at,
            payload.valuation_price,
            payload.margin_price,
        )
        window = LinearLiquidationAccountWindowEvidence(
            projection,
            payload.interval_start,
            payload.interval_end_exclusive,
            event.event_at,
            f"{PROFILE_KEY}.account-window.{payload.role_suffix}",
            state.ledger_state.state_hash,
        )
        bar = LinearLiquidationMarkBarEvidence(
            f"liquidation-bar.{payload.role_suffix}",
            cash.BTC,
            PricePurpose.LIQUIDATION,
            payload.interval_start,
            payload.interval_end_exclusive,
            payload.liquidation_low,
            payload.liquidation_high,
            _sim(payload.interval_end_exclusive.epoch_nanoseconds, TimelinePhase(40, "bar_closed")),
            event.event_at,
            f"{PROFILE_KEY}.liquidation.stream",
            f"{event.event_id}.bar",
            "revision-1",
            None,
            f"{PROFILE_KEY}.liquidation-source",
            "sha256:" + "ab" * 32,
        )
        request = LinearLiquidationAuditRequest(
            window,
            (bar,),
            payload.audit_at,
            RequestedResultGrade.DEVELOPMENT,
        )
        audit = ConservativeLinearLiquidationAuditModel().audit_liquidation(request)
        if audit.result is None:
            raise ValueError("liquidation audit failed")
        artifacts = (
            FinancialDispatchArtifact(
                f"margin_projection.{payload.role_suffix}",
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
                f"liquidation_audit.{payload.role_suffix}",
                event.event_id,
                event.event_at,
                audit.result.component_ref.component_key,
                audit.result.component_ref.component_version,
                audit.result.component_ref.component_digest,
                request.request_hash,
                audit.result.result_hash,
                audit.result,
            ),
        )
        result = FinancialDispatchResult(
            self.spec,
            event.event_id,
            (),
            state.position_lot_books,
            artifacts,
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def project_final_snapshot(
        self,
        plan: FinancialDispatchPlan,
        state_view: FinancialStateView,
        /,
    ) -> FinancialDispatchOutcome:
        input_hash = canonical_sha256(
            {
                "operation": "linear_final_snapshot",
                "plan": plan,
                "ledger_hash": state_view.ledger_state.state_hash,
            }
        )
        snapshot_plan = plan.final_snapshot_payload
        if type(snapshot_plan) is not SnapshotProjectionPlan:
            return _failure(
                self.spec,
                "engine-finalize",
                input_hash,
                FinancialDispatchFailureCode.SNAPSHOT_PROJECTION_FAILURE,
                type(snapshot_plan).__name__,
            )
        valuation = snapshot_plan.resolved_marks[0]
        projection = _margin_projection(
            state_view,
            _sim(snapshot_plan.timestamp.epoch_nanoseconds, TimelinePhase(90, "final_projection")),
            valuation.price,
            valuation.price,
        )
        snapshot = _portfolio_snapshot(state_view, projection, snapshot_plan.timestamp)
        roles = ("margin_projection.final", "final_snapshot")
        artifacts = (
            FinancialDispatchArtifact(
                roles[0],
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
                roles[1],
                "engine-finalize",
                projection.request.evaluated_at,
                self.spec.snapshot_projection_key,
                self.spec.snapshot_projection_version,
                self.spec.config_hash,
                input_hash,
                canonical_sha256(snapshot),
                snapshot,
            ),
        )
        result = FinancialDispatchResult(
            self.spec,
            "engine-finalize",
            (),
            state_view.position_lot_books,
            artifacts,
            snapshot,
        )
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)


@dataclass(frozen=True, slots=True)
class JourneyIds:
    deposit_journal_id: DomainId
    order_ids: tuple[DomainId, ...]
    fill_ids: tuple[DomainId, ...]
    fill_journal_ids: tuple[DomainId, ...]
    fee_ids: tuple[DomainId, ...]
    fee_journal_ids: tuple[DomainId, ...]
    funding_identity: LinearFundingApplicationIdentity


@dataclass(frozen=True, slots=True)
class JourneyEventIds:
    admission_event_ids: tuple[tuple[str, ...], ...]
    fill_event_ids: tuple[str, ...]


def fixed_ids() -> JourneyIds:
    funding_identity = LinearFundingApplicationIdentity.derive(
        LinearFundingApplicationKey.derive(
            cash.ACCOUNT,
            FundingSlotId.derive(cash.BTC, UtcInstant(300)),
        ),
        IdentityNamespace("synthetic-linear-journey", "1"),
        "synthetic-linear-journey-run",
    )
    return JourneyIds(
        _domain(DomainIdKind.JOURNAL, "0"),
        tuple(_domain(DomainIdKind.ORDER, value) for value in ("1", "2", "3")),
        tuple(_domain(DomainIdKind.FILL, value) for value in ("4", "5", "6")),
        tuple(_domain(DomainIdKind.JOURNAL, value) for value in ("7", "8", "9")),
        tuple(_domain(DomainIdKind.FEE, value) for value in ("a", "b", "c")),
        tuple(_domain(DomainIdKind.JOURNAL, value) for value in ("d", "e", "f")),
        funding_identity,
    )


def fixed_event_ids() -> JourneyEventIds:
    return JourneyEventIds(
        tuple(
            tuple(
                f"linear-order-{order_index}:{event_index}:{plan.event_type.value}"
                for event_index, plan in enumerate(cash.admission().event_plan)
            )
            for order_index in range(1, 4)
        ),
        tuple(f"linear-order-{index}:fill" for index in range(1, 4)),
    )


def _order(
    order_id: DomainId,
    index: int,
    side: OrderSide,
    quantity_units: int,
) -> Order:
    base, _ = cash.expected_order()
    intent = replace(
        base.intent,
        side=side,
        quantity=Quantity(quantity_units, cash.QUANTITY_SCALE, str(cash.BTC)),
        reduce_only=False,
        position_effect=PositionEffect.AUTO,
        reason=f"synthetic linear journey order {index}",
        parent_id=f"synthetic-linear-plan:{index}",
    )
    return Order(
        order_id,
        cash.ACCOUNT,
        intent,
        _sim(10 + index * 10, cash.ORDER_PHASE, 1),
    )


def _pretrade(order: Order, price_units: int, market_time: int):
    base = cash.pretrade_plan(
        order,
        price_units=price_units,
        market_time=199,
        same_instant=True,
    )
    return replace(
        base,
        order_rule_timeline=market_rules.timeline(
            intervals=(market_rules.interval(start=0, stop=1_000),)
        ),
        notional_evidence=market_rules.reference_notional_evidence(
            price_units=price_units,
            available_at=market_time,
        ),
        market_rule_evaluated_at=UtcInstant(market_time),
        fee_estimated_at=UtcInstant(market_time),
        resource_commitment=ReservationCommitment(
            fee_reserve=base.resource_commitment.fee_reserve,
            order_capacity_units=1,
        ),
        pretrade_evaluated_at=UtcInstant(market_time),
    )


def _admission(
    order: Order,
    index: int,
    bar_time: int,
    event_ids: tuple[str, ...],
) -> ResolvedOrderAdmission:
    base = cash.admission()
    event_types = tuple(value.event_type for value in base.event_plan)
    if len(event_ids) != len(base.event_plan):
        raise ValueError("admission Event IDs must exact-cover the event plan")
    plans = tuple(
        replace(
            value,
            event_id=event_ids[event_index],
            occurred_at=_sim(
                order.created_at.instant.epoch_nanoseconds + event_index,
                cash.ORDER_PHASE,
                event_index + 1,
            ),
        )
        for event_index, value in enumerate(base.event_plan)
    )
    pretrade = _pretrade(order, 10_000, bar_time)
    admission = ResolvedOrderAdmission(
        order,
        base.capability_set,
        base.translation_mapping,
        UtcInstant(order.created_at.instant.epoch_nanoseconds + 1),
        pretrade,
        plans,
    )
    assert tuple(value.event_type for value in admission.event_plan) == event_types
    return admission


def _stream(admission: ResolvedOrderAdmission) -> OrderEventStream:
    records: list[OrderEventRecord] = []
    cause = admission.order.intent.parent_id
    for plan in admission.event_plan:
        event = OrderEvent(
            plan.event_id,
            admission.order.order_id,
            cause,
            plan.event_type,
            plan.occurred_at,
            evidence_id=plan.external_evidence_id or canonical_sha256(plan),
        )
        records.append(OrderEventRecord(event, None))
        cause = event.event_id
    return OrderEventStream.from_records(admission.order, records)


def _reservation(admission: ResolvedOrderAdmission) -> OrderReservationSchedule:
    accepted = admission.event_plan[-1]
    commitment = ReservationCommitment(order_capacity_units=1)
    update = OrderReservationUpdate(
        admission.order.order_id,
        accepted.event_id,
        OrderEventType.ORDER_ACCEPTED,
        admission.order.intent.quantity,
        commitment,
        canonical_sha256(commitment),
    )
    return OrderReservationSchedule(
        admission.order.order_id,
        canonical_sha256({"order": admission.order.intent}),
        (update,),
    )


def _bar_event(index: int, time: int, price_units: int) -> MarketEvent:
    instant = UtcInstant(time)
    return MarketEvent(
        f"linear-bar-{index}",
        "linear.bars.open",
        BAR_OPEN_EVENT_TYPE,
        BAR_OPEN_CAPABILITY,
        cash.BTC,
        instant,
        instant,
        cash.BAR_PHASE,
        SourceSequence(index),
        "revision-1",
        None,
        f"{PROFILE_KEY}.bar-open",
        canonical_sha256({"bar": index, "price": price_units}),
        {
            "schema_version": 1,
            "bar_kind": "real",
            "open_price": {
                "units": price_units,
                "scale": cash.MONEY_SCALE.places,
                "quote_currency": "USD",
            },
        },
    )


def _account_event(event_id: str, time: int, sequence: int) -> MarketEvent:
    instant = UtcInstant(time)
    return MarketEvent(
        event_id,
        "linear.account.events",
        "account_financial_event",
        ACCOUNT_EVENT_CAPABILITY,
        cash.BTC,
        instant,
        instant,
        DISPATCH_PHASE,
        SourceSequence(sequence),
        "revision-1",
        None,
        f"{PROFILE_KEY}.account-events",
        canonical_sha256({"event_id": event_id, "time": time}),
        {"schema_version": 1, "event_key": event_id},
    )


def _slippage(index: int, bar_time: int):
    model = cash.slippage_model()
    envelope = SlippageApplicabilityEnvelope.create(
        envelope_key=f"{PROFILE_KEY}.slippage.{index}",
        envelope_version=1,
        instrument_id=cash.BTC,
        valid_from=UtcInstant(bar_time - 10),
        valid_to_exclusive=UtcInstant(bar_time + 10),
        maximum_quantity=Quantity(5_000, cash.QUANTITY_SCALE, str(cash.BTC)),
        allowed_market_state_keys=("normal",),
    )
    return replace(model, applicability_envelope=envelope)


def _fill_plan(ids: JourneyIds, index: int, bar_time: int) -> FillAccountingDispatchPlan:
    spec = dispatcher_spec()
    payload = SyntheticLinearFillPayload(
        cash.POSITION_KEY,
        CONTRACT,
        SETTLEMENT_REGISTRATION,
        QuantizationPolicy(
            f"{PROFILE_KEY}.realized-half-even",
            cash.MONEY_SCALE,
            RoundingPolicy.HALF_EVEN,
        ),
    )
    fee_rules = cash.final_fee_rule_set()
    return FillAccountingDispatchPlan(
        f"linear-bar-{index + 1}",
        ids.fill_ids[index],
        spec.position_accounting_component,
        payload,
        SyntheticLinearFillSemantics(
            payload.position_key,
            payload.contract,
            payload.settlement_cash_registration,
            payload.pnl_quantization,
        ),
        ids.fill_journal_ids[index],
        _sim(bar_time + 10, cash.ACCOUNTING_PHASE, 1),
        FeeAccountingDispatchPlan(
            cash.CASH_KEY,
            fee_rules,
            ids.fee_ids[index],
            UtcInstant(bar_time + 11),
            ids.fee_journal_ids[index],
            _sim(bar_time + 12, cash.ACCOUNTING_PHASE, 3),
        ),
        (f"position_accounting.{index + 1}",),
    )


def _bar_execution(
    ids: JourneyIds,
    admission: ResolvedOrderAdmission,
    index: int,
    bar_time: int,
    price_units: int,
    fill_event_id: str,
) -> ResolvedBarExecution:
    event = _bar_event(index + 1, bar_time, price_units)
    plan = _pretrade(admission.order, price_units, bar_time)
    return ResolvedBarExecution(
        event.event_id,
        admission.order.order_id,
        plan,
        BarLiquidityEvidence.create(
            evidence_key=f"{PROFILE_KEY}.liquidity.{index + 1}",
            evidence_version=1,
            market_event=event,
            evaluated_at=event.available_time,
            approved=True,
            reason_code=None,
            source_hash=event.event_hash,
        ),
        SlippageMarketState(
            "normal",
            event.available_time,
            event.available_time,
            event.event_id,
            event.revision_id,
            event.event_hash,
        ),
        _slippage(index + 1, bar_time),
        ids.fill_ids[index],
        fill_event_id,
        _sim(bar_time, TimelinePhase(70, "fill"), 1),
        _fill_plan(ids, index, bar_time),
    )


def _funding_event(ids: JourneyIds) -> ScheduledAccountEvent:
    at = _sim(300, DISPATCH_PHASE, 1)
    identity = ids.funding_identity
    expected_key = LinearFundingApplicationKey.derive(
        cash.ACCOUNT,
        FundingSlotId.derive(cash.BTC, at.instant),
    )
    if identity.application_key != expected_key:
        raise ValueError("funding identity does not match the Journey slot")
    return ScheduledAccountEvent(
        "linear-funding-300",
        at,
        "funding",
        (dispatcher_spec().financing_component.component_key,),
        (
            ("settlement.funding.0", identity.settlement_id),
            ("journal.funding.0", identity.journal_entry_id),
        ),
        SyntheticFundingDispatchPayload(identity, _sim(301, cash.ACCOUNTING_PHASE, 1)),
        SyntheticFundingDispatchSemantics(
            at.instant,
            Rate(1, Scale(4), "funding_fraction_of_notional"),
            Price(10_000, cash.MONEY_SCALE, str(cash.BTC), "USD"),
            _sim(301, cash.ACCOUNTING_PHASE, 1),
        ),
        ("funding_eligibility", "funding_accounting"),
    )


def _margin_event(
    suffix: str,
    event_time: int,
    evaluated_time: int,
    low_units: int,
    high_units: int,
) -> ScheduledAccountEvent:
    at = _sim(event_time, DISPATCH_PHASE, 2 if suffix == "long" else 3)
    payload = SyntheticMarginAuditPayload(
        _sim(evaluated_time, TimelinePhase(90, "margin_projection"), 0),
        Price(10_000, cash.MONEY_SCALE, str(cash.BTC), "USD"),
        Price(10_000, cash.MONEY_SCALE, str(cash.BTC), "USD"),
        UtcInstant(evaluated_time),
        UtcInstant(evaluated_time + 20),
        Price(low_units, cash.MONEY_SCALE, str(cash.BTC), "USD"),
        Price(high_units, cash.MONEY_SCALE, str(cash.BTC), "USD"),
        at,
        suffix,
    )
    return ScheduledAccountEvent(
        f"linear-{suffix}-audit-{event_time}",
        at,
        "margin_liquidation_audit",
        (
            dispatcher_spec().margin_component.component_key,
            dispatcher_spec().liquidation_audit_component.component_key,
        ),
        (),
        payload,
        payload,
        (f"margin_projection.{suffix}", f"liquidation_audit.{suffix}"),
    )


def snapshot_plan() -> SnapshotProjectionPlan:
    mark, _ = _resolved_mark(
        PricePurpose.VALUATION,
        Price(10_000, cash.MONEY_SCALE, str(cash.BTC), "USD"),
        _sim(800, TimelinePhase(90, "final_projection")),
        "final",
    )
    return SnapshotProjectionPlan(
        (mark,),
        (),
        cash.USD,
        cash.MONEY_SCALE,
        UtcInstant(800),
        canonical_sha256({"type": "synthetic-linear-usd-valuation-graph"}),
    )


def _build_execution_case(
    ids: JourneyIds,
    event_ids: JourneyEventIds,
    *,
    batch_size: int,
    semantic_spec_hash: str,
    final_sell_quantity_units: int = 3_000,
) -> ResolvedExecutionCase:
    orders = (
        _order(ids.order_ids[0], 1, OrderSide.BUY, 3_000),
        _order(ids.order_ids[1], 2, OrderSide.SELL, 1_000),
        _order(ids.order_ids[2], 3, OrderSide.SELL, final_sell_quantity_units),
    )
    bar_times = (200, 400, 600)
    admissions = tuple(
        _admission(
            order,
            index + 1,
            bar_times[index],
            event_ids.admission_event_ids[index],
        )
        for index, order in enumerate(orders)
    )
    streams = tuple(_stream(value) for value in admissions)
    schedules = tuple(_reservation(value) for value in admissions)
    bars = tuple(
        _bar_execution(
            ids,
            admissions[index],
            index,
            bar_times[index],
            10_000,
            event_ids.fill_event_ids[index],
        )
        for index in range(3)
    )
    scheduled = (
        _funding_event(ids),
        _margin_event("long", 350, 320, 8_000, 11_000),
        _margin_event("short", 650, 620, 9_000, 12_000),
    )
    bar_events = tuple(
        _bar_event(index + 1, bar_times[index], 10_000) for index in range(3)
    )
    account_events = tuple(
        _account_event(
            value.event_id,
            value.event_at.instant.epoch_nanoseconds,
            index + 1,
        )
        for index, value in enumerate(scheduled)
    )
    reader = InMemoryMarketBundleReader.build(
        bundle_key=f"{PROFILE_KEY}.bundle",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(801),
        instrument_catalog_hash=canonical_sha256(CONTRACT.instrument),
        capabilities=(
            cash.TARGET_STREAM_CAPABILITY,
            BAR_OPEN_CAPABILITY,
            ACCOUNT_EVENT_CAPABILITY,
        ),
        streams={
            "linear.bars.open": bar_events,
            "linear.account.events": account_events,
        },
    )
    timeline = DeterministicTimeline.open(
        reader=reader,
        stream_keys=("linear.account.events", "linear.bars.open"),
        window=TimelineWindow(UtcInstant(0), UtcInstant(100), UtcInstant(800)),
    )
    if not isinstance(timeline, DeterministicTimeline):
        raise AssertionError("synthetic linear Timeline failed")
    financial = ResolvedFinancialState(
        cash.initial_journal(ids.deposit_journal_id),
        cash.ledger_schema(),
        cash.initial_snapshot(ids.deposit_journal_id),
        (PositionLotBook(cash.POSITION_KEY),),
        streams,
        admissions,
        schedules,
        SettlementBook(cash.ACCOUNT),
        cash.empty_settlement_rules(),
    )
    final_plan = snapshot_plan()
    expected_roles = tuple(
        sorted(
            (
                "position_accounting.1",
                "position_accounting.2",
                "position_accounting.3",
                "funding_eligibility",
                "funding_accounting",
                "margin_projection.long",
                "liquidation_audit.long",
                "margin_projection.short",
                "liquidation_audit.short",
                "margin_projection.final",
                "final_snapshot",
            )
        )
    )
    return ResolvedExecutionCase(
        f"{PROFILE_KEY}.engine",
        1,
        semantic_spec_hash,
        timeline,
        batch_size,
        PrecomputedTargetStream("targets", ()),
        (),
        bars,
        financial,
        FinancialDispatchPlan(dispatcher_spec(), scheduled, final_plan, expected_roles),
        cash.execution_model(),
        final_plan,
        MarkToMarketCloseoutPolicy(),
    )


def build_execution_case(
    *, batch_size: int = 1, final_sell_quantity_units: int = 3_000
) -> ResolvedExecutionCase:
    return _build_execution_case(
        fixed_ids(),
        fixed_event_ids(),
        batch_size=batch_size,
        semantic_spec_hash="sha256:" + "9a" * 32,
        final_sell_quantity_units=final_sell_quantity_units,
    )


def _funding_application_key() -> LinearFundingApplicationKey:
    return LinearFundingApplicationKey.derive(
        cash.ACCOUNT,
        FundingSlotId.derive(cash.BTC, UtcInstant(300)),
    )


@dataclass(frozen=True, slots=True)
class SyntheticLinearExecutionCaseBuilder:
    batch_size: int = 1

    def identity_plan(self) -> tuple[ExecutionCaseIdentityRule, ...]:
        rules: list[ExecutionCaseIdentityRule] = [
            ExecutionCaseIdentityRule(
                "journal.initial.0",
                "engine.linear.deposit",
                0,
                DomainIdKind.JOURNAL,
            )
        ]
        for index in range(3):
            rules.extend(
                (
                    ExecutionCaseIdentityRule(
                        f"order.initial.{index}",
                        "engine.linear.order",
                        index,
                        DomainIdKind.ORDER,
                    ),
                    ExecutionCaseIdentityRule(
                        f"fill.{index}",
                        "engine.linear.fill",
                        index,
                        DomainIdKind.FILL,
                    ),
                    ExecutionCaseIdentityRule(
                        f"journal.fill.{index}",
                        "engine.linear.fill-journal",
                        index,
                        DomainIdKind.JOURNAL,
                    ),
                    ExecutionCaseIdentityRule(
                        f"fee.{index}",
                        "engine.linear.fee",
                        index,
                        DomainIdKind.FEE,
                    ),
                    ExecutionCaseIdentityRule(
                        f"journal.fee.{index}",
                        "engine.linear.fee-journal",
                        index,
                        DomainIdKind.JOURNAL,
                    ),
                    ExecutionCaseIdentityRule(
                        f"order-event.fill.{index}",
                        "engine.linear.order-event.fill",
                        index,
                    ),
                )
            )
            rules.extend(
                ExecutionCaseIdentityRule(
                    f"order-event.initial.{index}.{event_index}",
                    f"engine.linear.order-event.{plan.event_type.value}",
                    index * 10 + event_index,
                )
                for event_index, plan in enumerate(cash.admission().event_plan)
            )
        funding_key = _funding_application_key().value
        rules.extend(
            (
                ExecutionCaseIdentityRule(
                    "settlement.funding.0",
                    funding_key,
                    0,
                    DomainIdKind.SETTLEMENT,
                ),
                ExecutionCaseIdentityRule(
                    "journal.funding.0",
                    funding_key,
                    0,
                    DomainIdKind.JOURNAL,
                ),
            )
        )
        return tuple(rules)

    def semantic_spec(self) -> ExecutionCaseSemanticSpec:
        return ExecutionCaseComposer.semantic_spec_from_case(
            build_execution_case(batch_size=self.batch_size),
            spec_key=f"{PROFILE_KEY}.execution-case",
            spec_version=1,
            identity_namespace=IdentityNamespace("backtest", "1"),
            identity_plan=self.identity_plan(),
        )

    def build(
        self,
        identities: ExecutionCaseIdentityFactory,
        semantic_spec_hash: str,
    ) -> ResolvedExecutionCase:
        funding_identity = LinearFundingApplicationIdentity.derive(
            _funding_application_key(),
            identities.namespace,
            identities.semantic_run_id,
        )
        settlement_id = identities.domain_id("settlement.funding.0")
        funding_journal_id = identities.domain_id("journal.funding.0")
        if (
            settlement_id != funding_identity.settlement_id
            or funding_journal_id != funding_identity.journal_entry_id
        ):
            raise ValueError("Funding identities must use the canonical derivation")
        ids = JourneyIds(
            identities.domain_id("journal.initial.0"),
            tuple(
                identities.domain_id(f"order.initial.{index}") for index in range(3)
            ),
            tuple(identities.domain_id(f"fill.{index}") for index in range(3)),
            tuple(identities.domain_id(f"journal.fill.{index}") for index in range(3)),
            tuple(identities.domain_id(f"fee.{index}") for index in range(3)),
            tuple(identities.domain_id(f"journal.fee.{index}") for index in range(3)),
            funding_identity,
        )
        event_ids = JourneyEventIds(
            tuple(
                tuple(
                    identities.event_id(
                        f"order-event.initial.{index}.{event_index}"
                    )
                    for event_index, _ in enumerate(cash.admission().event_plan)
                )
                for index in range(3)
            ),
            tuple(
                identities.event_id(f"order-event.fill.{index}")
                for index in range(3)
            ),
        )
        return _build_execution_case(
            ids,
            event_ids,
            batch_size=self.batch_size,
            semantic_spec_hash=semantic_spec_hash,
        )


def _require_profile(
    profile: SyntheticLinearPerpetualDevelopmentProfile,
) -> SyntheticLinearPerpetualDevelopmentProfile:
    if not isinstance(profile, SyntheticLinearPerpetualDevelopmentProfile):
        raise TypeError("profile must be SyntheticLinearPerpetualDevelopmentProfile")
    if (
        profile.profile_key != PROFILE_KEY
        or profile.grade != "development"
        or profile.decision_grade_eligible
        or profile.deployment_authorized
    ):
        raise ValueError("invalid synthetic linear development Profile")
    return profile


def _profile_registry(
    profile: SyntheticLinearPerpetualDevelopmentProfile,
) -> BacktestProfileRegistry:
    market = cast(Any, profile.market_semantics)
    simulation = cast(Any, profile.simulation)
    account = cast(Any, profile.execution_account)
    return BacktestProfileRegistry(
        market_semantics_profiles=(
            MarketSemanticsProfileRegistration(
                f"{PROFILE_KEY}.market",
                1,
                market.profile_digest,
                market,
                account.venue_id,
                (BAR_OPEN_CAPABILITY, ACCOUNT_EVENT_CAPABILITY),
                market.component_manifest,
                RequestedResultGrade.DEVELOPMENT,
                LIMITATIONS,
                False,
            ),
        ),
        simulation_profiles=(
            SimulationProfileRegistration(
                f"{PROFILE_KEY}.simulation",
                1,
                simulation.profile_digest,
                simulation,
                "bar",
                (StrategyFamily.PRECOMPUTED_TARGET,),
                (BAR_OPEN_CAPABILITY,),
                simulation.component_manifest,
                RequestedResultGrade.DEVELOPMENT,
                LIMITATIONS,
                False,
            ),
        ),
        execution_account_profiles=(
            ExecutionAccountProfileRegistration(
                f"{PROFILE_KEY}.account",
                1,
                account.profile_digest,
                account,
                account.account_id,
                account.venue_id,
                "linear_perpetual",
                "synthetic_single_collateral",
                (cash.USD,),
                RequestedResultGrade.DEVELOPMENT,
                LIMITATIONS,
                False,
            ),
        ),
    )


def build_synthetic_linear_perpetual_resolved_request(
    profile: SyntheticLinearPerpetualDevelopmentProfile,
    *,
    timeline_batch_size: int = 1,
) -> ResolvedBacktestRequest:
    resolved_profile = _require_profile(profile)
    builder = SyntheticLinearExecutionCaseBuilder(timeline_batch_size)
    spec = builder.semantic_spec()
    template = build_execution_case(batch_size=timeline_batch_size)
    manifest = resolution_fixtures.build_manifest()
    manifest = replace(
        manifest,
        artifacts=tuple(
            replace(
                artifact,
                artifact_key=artifact.artifact_key.replace(
                    "synthetic.cash.development.v1",
                    PROFILE_KEY,
                ),
            )
            if artifact.role is BuildArtifactRole.PROFILE_COMPONENT
            else artifact
            for artifact in manifest.artifacts
        ),
    )
    request = replace(
        resolution_fixtures.request(manifest, bundle=template.timeline.reader.manifest),
        timeline_window=template.timeline.window,
        market_semantics_profile_key=f"{PROFILE_KEY}.market",
        simulation_profile_key=f"{PROFILE_KEY}.simulation",
        execution_account_profile_key=f"{PROFILE_KEY}.account",
        execution_account_id=cash.ACCOUNT,
        target_stream_digest=template.target_stream.target_stream_digest,
        execution_case_semantic_hash=spec.semantic_spec_hash,
        result_grade_requested=RequestedResultGrade.DEVELOPMENT,
    )
    outcome = ProfileResolver().resolve(
        request=request,
        registry=_profile_registry(resolved_profile),
        market_bundle_manifest=template.timeline.reader.manifest,
        build_artifact_manifest=manifest,
    )
    if outcome.resolved is None:
        raise ValueError(f"synthetic linear resolution failed: {outcome.failure!r}")
    return outcome.resolved


def build_synthetic_linear_perpetual_execution_case(
    profile: SyntheticLinearPerpetualDevelopmentProfile,
    *,
    timeline_batch_size: int = 1,
    resolved_request: ResolvedBacktestRequest | None = None,
) -> ResolvedExecutionCase:
    _require_profile(profile)
    resolved = resolved_request or build_synthetic_linear_perpetual_resolved_request(
        profile,
        timeline_batch_size=timeline_batch_size,
    )
    return ExecutionCaseComposer().compose(
        resolved_request=resolved,
        builder=SyntheticLinearExecutionCaseBuilder(timeline_batch_size),
    )


__all__ = [
    "CONTRACT",
    "LIMITATIONS",
    "PROFILE_KEY",
    "SyntheticLinearExecutionCaseBuilder",
    "SyntheticLinearFinancialDispatcher",
    "SyntheticLinearPerpetualDevelopmentProfile",
    "build_execution_case",
    "build_synthetic_linear_perpetual_execution_case",
    "build_synthetic_linear_perpetual_resolved_request",
    "dispatcher_spec",
]
