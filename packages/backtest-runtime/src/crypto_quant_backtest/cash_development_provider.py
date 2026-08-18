from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import unicodedata

import crypto_quant_domain as domain
import crypto_quant_trading as trading
from crypto_quant_market_data import MarketBundleReader, MarketEvent

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .composition import ExecutionCaseComposer
from .engine import (
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    OrderEventPlan,
    PositionLotBook,
    ResolvedBarExecution,
    ResolvedDecisionCycle,
    ResolvedExecutionCase,
    ResolvedFinancialState,
    ResolvedOrderAdmission,
    ResolvedPreTradePlan,
    SnapshotProjectionPlan,
)
from .execution import (
    BAR_OPEN_CAPABILITY,
    BAR_OPEN_EVENT_TYPE,
    BarLiquidityEvidence,
    BarOpenObservation,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
)
from .execution_inputs import (
    BacktestExecutionRequest,
    _DecodedExecutionInputBundleV2,
    _EXECUTION_INPUT_CATALOG,
    materialize_execution_input_bundle_v2,
)
from .facade import BacktestRuntime
from .financial_dispatch import (
    CashFillAccountingPlan,
    FeeAccountingDispatchPlan,
    FillAccountingDispatchPlan,
    FinancialDispatchPlan,
    default_cash_financial_dispatcher_spec,
)
from .model_revisions import ModelRevisionTimeline
from .ports import SimulationComponentRef, SimulationPortType
from .request_registration import BacktestRequestRef
from .resolution import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    BacktestRequest,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration,
    ModelRequestBinding,
    ProfileResolver,
    RequestedResultGrade,
    SimulationProfileRegistration,
    SourceTreeState,
    StrategyFamily,
)
from .run_end import MarkToMarketCloseoutPolicy
from .slippage import (
    DeterministicBpsSlippageModel,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageLimitation,
    SlippageMarketState,
)
from .target_stream import (
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    TARGET_STREAM_CAPABILITY,
    TARGET_STREAM_EVENT_TYPE,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
)
from .timeline import DeterministicTimeline, TimelineEvent, TimelineSegment, TimelineWindow

_RUN_ID_PATTERN = re.compile(r"run_[0-9a-f]{64}\Z")
_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PROFILE_PREFIX = "cash.precomputed_target.development.v1"
_MARKET_KEY = f"{_PROFILE_PREFIX}.market"
_SIMULATION_KEY = f"{_PROFILE_PREFIX}.simulation"
_ACCOUNT_KEY = f"{_PROFILE_PREFIX}.account"
_TARGET_STREAM = "targets"
_BAR_STREAM = "bars.open"
_TARGET_CAPABILITY = TARGET_STREAM_CAPABILITY
_TARGET_EVENT_TYPE = TARGET_STREAM_EVENT_TYPE
_LIMITATIONS = ("development_only", "single_cash_spot_full_fill")


class ModelPreparationFailure(ValueError):
    def __init__(self, code: str) -> None:
        if code not in {
            "MODEL_TIMELINE_INVALID",
            "MODEL_ARTIFACT_UNAVAILABLE",
            "MODEL_BINDING_MISMATCH",
        }:
            raise ValueError("unknown model preparation failure")
        self.code = code
        super().__init__(code)


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if not value or value.strip() != value or unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be non-empty canonical text")
    return value


def _sim(instant: domain.UtcInstant, rank: int, code: str, sequence: int) -> domain.SimulationInstant:
    return domain.SimulationInstant(instant, domain.TimelinePhase(rank, code), domain.SourceSequence(sequence))


def _profile_ref(port: trading.ProfilePortType, key: str) -> trading.ProfileComponentRef:
    payload = {"type": "cash_development_profile_component", "port_type": port.value, "key": key, "version": 1}
    return trading.ProfileComponentRef(port, key, 1, domain.canonical_sha256(payload))


def _simulation_ref(port: SimulationPortType, key: str) -> SimulationComponentRef:
    payload = {"type": "cash_development_simulation_component", "port_type": port.value, "key": key, "version": 1}
    return SimulationComponentRef(port, key, 1, domain.canonical_sha256(payload))


@dataclass(frozen=True, slots=True)
class CashDevelopmentRequestIntent:
    schema_version: int
    experiment_id: str | None
    timeline_window: TimelineWindow
    execution_account_id: str
    reporting_currency: domain.CurrencyId
    master_random_seed: int

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("CashDevelopmentRequestIntent schema_version must be 1")
        if self.experiment_id is not None:
            _canonical_text("experiment_id", self.experiment_id)
        if type(self.timeline_window) is not TimelineWindow:
            raise TypeError("timeline_window must be exact TimelineWindow")
        _canonical_text("execution_account_id", self.execution_account_id)
        if type(self.reporting_currency) is not domain.CurrencyId:
            raise TypeError("reporting_currency must be exact CurrencyId")
        if type(self.master_random_seed) is not int or self.master_random_seed < 0:
            raise ValueError("master_random_seed must be non-negative integer")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cash_development_request_intent", "schema_version": self.schema_version, "experiment_id": self.experiment_id, "timeline_window": self.timeline_window, "execution_account_id": self.execution_account_id, "reporting_currency": self.reporting_currency, "master_random_seed": self.master_random_seed}


@dataclass(frozen=True, slots=True)
class CashDevelopmentProviderInputs:
    schema_version: int
    build_artifact_manifest: BuildArtifactManifest
    instrument_catalog: domain.InstrumentCatalog
    strategy_id: str
    sleeve_id: domain.StrategySleeveId
    initial_cash: domain.Money
    quantity_lattice: trading.QuantityLattice
    decision_mark: trading.MarkObservation
    final_mark: trading.MarkObservation
    order_capabilities: trading.OrderCapabilitySet

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("CashDevelopmentProviderInputs schema_version must be 1")
        expected = (("build_artifact_manifest", self.build_artifact_manifest, BuildArtifactManifest), ("instrument_catalog", self.instrument_catalog, domain.InstrumentCatalog), ("sleeve_id", self.sleeve_id, domain.StrategySleeveId), ("initial_cash", self.initial_cash, domain.Money), ("quantity_lattice", self.quantity_lattice, trading.QuantityLattice), ("decision_mark", self.decision_mark, trading.MarkObservation), ("final_mark", self.final_mark, trading.MarkObservation), ("order_capabilities", self.order_capabilities, trading.OrderCapabilitySet))
        for name, value, expected_type in expected:
            if type(value) is not expected_type:
                raise TypeError(f"{name} must be exact {expected_type.__name__}")
        _canonical_text("strategy_id", self.strategy_id)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cash_development_provider_inputs", "schema_version": self.schema_version, "build_artifact_manifest": self.build_artifact_manifest, "instrument_catalog": self.instrument_catalog, "strategy_id": self.strategy_id, "sleeve_id": self.sleeve_id, "initial_cash": self.initial_cash, "quantity_lattice": self.quantity_lattice, "decision_mark": self.decision_mark, "final_mark": self.final_mark, "order_capabilities": self.order_capabilities}


@dataclass(frozen=True, slots=True)
class PreparedBacktestExecution:
    request_ref: BacktestRequestRef
    semantic_run_id: str
    execution_request: BacktestExecutionRequest
    runtime: BacktestRuntime

    def __post_init__(self) -> None:
        if type(self.request_ref) is not BacktestRequestRef:
            raise TypeError("request_ref must be exact BacktestRequestRef")
        if type(self.semantic_run_id) is not str or _RUN_ID_PATTERN.fullmatch(self.semantic_run_id) is None:
            raise ValueError("semantic_run_id must be canonical run identity")
        if type(self.execution_request) is not BacktestExecutionRequest:
            raise TypeError("execution_request must be exact BacktestExecutionRequest")
        if type(self.runtime) is not BacktestRuntime:
            raise TypeError("runtime must be exact BacktestRuntime")


@dataclass(frozen=True, slots=True)
class PreparedModelBoundBacktestExecution:
    request_ref: BacktestRequestRef
    semantic_run_id: str
    execution_request: BacktestExecutionRequest
    runtime: BacktestRuntime
    model_binding: ModelRequestBinding

    def __post_init__(self) -> None:
        base = PreparedBacktestExecution(
            self.request_ref,
            self.semantic_run_id,
            self.execution_request,
            self.runtime,
        )
        if type(self.model_binding) is not ModelRequestBinding:
            raise TypeError("model_binding must be exact ModelRequestBinding")
        if base.execution_request.request.model_binding != self.model_binding:
            raise ValueError("prepared model binding does not match request")


@dataclass(frozen=True, slots=True)
class _ProfileImplementation:
    kind: str
    components: tuple[object, ...]

    @property
    def component_manifest(self) -> tuple[object, ...]:
        return self.components

    @property
    def profile_digest(self) -> str:
        return domain.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": f"cash_development_{self.kind}_profile", "schema_version": 1, "component_manifest": self.components}


@dataclass(frozen=True, slots=True)
class _Ids:
    deposit: domain.DomainId
    order: domain.DomainId
    fill: domain.DomainId
    fill_journal: domain.DomainId
    fee: domain.DomainId
    fee_journal: domain.DomainId
    admission_events: tuple[str, ...]
    fill_event: str


@dataclass(frozen=True, slots=True)
class _CaseInputs:
    intent: CashDevelopmentRequestIntent
    provider: CashDevelopmentProviderInputs
    market_reader: MarketBundleReader
    instrument: domain.InstrumentDefinition
    target_event: MarketEvent
    bar_event: MarketEvent
    bar_price: domain.Price
    decision_mark: trading.ResolvedMark
    final_mark: trading.ResolvedMark
    timeline: DeterministicTimeline
    target_stream: PrecomputedTargetStream


@dataclass(frozen=True, slots=True)
class _CashCaseBuilder:
    values: _CaseInputs

    @staticmethod
    def identity_plan() -> tuple[ExecutionCaseIdentityRule, ...]:
        event_types = (domain.OrderEventType.ORDER_INTENT_CREATED, domain.OrderEventType.ORDER_CAPABILITY_APPROVED, domain.OrderEventType.ORDER_TRANSLATED, domain.OrderEventType.MARKET_RULE_APPROVED, domain.OrderEventType.FEE_RESERVATION_ESTIMATED, domain.OrderEventType.PRE_TRADE_RISK_APPROVED, domain.OrderEventType.ORDER_SUBMITTED, domain.OrderEventType.ORDER_ACCEPTED)
        return (
            ExecutionCaseIdentityRule("journal.initial.0", "cash-development.deposit", 0, domain.DomainIdKind.JOURNAL),
            ExecutionCaseIdentityRule("order.0.0", "cash-development.order", 0, domain.DomainIdKind.ORDER),
            ExecutionCaseIdentityRule("fill.0", "cash-development.fill", 0, domain.DomainIdKind.FILL),
            ExecutionCaseIdentityRule("journal.fill.0", "cash-development.fill-journal", 0, domain.DomainIdKind.JOURNAL),
            ExecutionCaseIdentityRule("fee.0", "cash-development.fee", 0, domain.DomainIdKind.FEE),
            ExecutionCaseIdentityRule("journal.fee.0", "cash-development.fee-journal", 0, domain.DomainIdKind.JOURNAL),
            *(ExecutionCaseIdentityRule(f"order-event.0.0.{i}", f"cash-development.order-event.{value.value}", i) for i, value in enumerate(event_types)),
            ExecutionCaseIdentityRule("order-event.fill.0", "cash-development.order-event.fill", 0),
        )

    @staticmethod
    def _placeholder_ids() -> _Ids:
        def value(kind: domain.DomainIdKind, digit: str) -> domain.DomainId:
            return domain.DomainId(kind, f"{kind.prefix}_{digit * 64}")
        return _Ids(value(domain.DomainIdKind.JOURNAL, "0"), value(domain.DomainIdKind.ORDER, "1"), value(domain.DomainIdKind.FILL, "2"), value(domain.DomainIdKind.JOURNAL, "3"), value(domain.DomainIdKind.FEE, "4"), value(domain.DomainIdKind.JOURNAL, "5"), tuple(f"cash-development:event:{i}" for i in range(8)), "cash-development:event:fill")

    def semantic_spec(self) -> ExecutionCaseSemanticSpec:
        case = _build_case(self.values, self._placeholder_ids(), "sha256:" + "0" * 64)
        return ExecutionCaseComposer.semantic_spec_from_case(case, spec_key="cash.precomputed-target.execution-case.v1", spec_version=1, identity_namespace=domain.IdentityNamespace("backtest", "1"), identity_plan=self.identity_plan())

    def build(self, identities: ExecutionCaseIdentityFactory, semantic_spec_hash: str) -> ResolvedExecutionCase:
        ids = _Ids(identities.domain_id("journal.initial.0"), identities.domain_id("order.0.0"), identities.domain_id("fill.0"), identities.domain_id("journal.fill.0"), identities.domain_id("fee.0"), identities.domain_id("journal.fee.0"), tuple(identities.event_id(f"order-event.0.0.{i}") for i in range(8)), identities.event_id("order-event.fill.0"))
        return _build_case(self.values, ids, semantic_spec_hash)


def _events(reader: MarketBundleReader, stream_key: str) -> tuple[MarketEvent, ...]:
    cursor = reader.open_cursor(stream_key, batch_size=16)
    if not hasattr(cursor, "exhausted"):
        raise ValueError(f"cannot open required stream {stream_key}")
    result: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        result.extend(batch)
    if any(type(value) is not MarketEvent for value in result):
        raise TypeError("market reader streams must contain exact MarketEvent")
    return tuple(result)


def _resolved_mark(
    observation: trading.MarkObservation,
    requested_at: domain.UtcInstant,
    key: str,
    *,
    max_age_nanoseconds: int = 0,
    allow_forward_fill: bool = False,
) -> trading.ResolvedMark:
    policy = trading.StaleMarkPolicy(
        key,
        1,
        domain.PricePurpose.VALUATION,
        max_age_nanoseconds,
        allow_forward_fill,
    )
    outcome = trading.MarkResolver().resolve((observation,), instrument_id=observation.instrument_id, price_purpose=domain.PricePurpose.VALUATION, requested_at=requested_at, stale_policy=policy)
    if outcome.resolved_mark is None:
        raise ValueError(f"{key} observation cannot resolve at required instant")
    return outcome.resolved_mark


def _case_inputs(intent: CashDevelopmentRequestIntent, provider: CashDevelopmentProviderInputs, reader: MarketBundleReader) -> _CaseInputs:
    if type(intent) is not CashDevelopmentRequestIntent or type(provider) is not CashDevelopmentProviderInputs:
        raise TypeError("request_intent and provider_inputs must be exact public values")
    if len(provider.instrument_catalog.instruments) != 1:
        raise ValueError("cash development provider requires exactly one instrument")
    instrument = provider.instrument_catalog.instruments[0]
    if instrument.instrument_type is not domain.InstrumentType.SPOT:
        raise ValueError("cash development provider requires one SPOT instrument")
    if instrument.quote_currency != intent.reporting_currency or instrument.settlement_currency != intent.reporting_currency:
        raise ValueError("spot quote, settlement, and reporting currencies must match")
    if provider.initial_cash.units <= 0 or provider.initial_cash.currency != str(intent.reporting_currency):
        raise ValueError("initial_cash must be positive reporting currency")
    if provider.quantity_lattice.instrument_id != instrument.instrument_id:
        raise ValueError("quantity_lattice must bind the sole instrument")
    if reader.manifest.instrument_catalog_hash != domain.canonical_sha256(provider.instrument_catalog):
        raise ValueError("instrument_catalog does not bind MarketBundle manifest")
    target_events, bar_events = _events(reader, _TARGET_STREAM), _events(reader, _BAR_STREAM)
    if len(target_events) != 1 or len(bar_events) != 1:
        raise ValueError("cash development provider requires exactly one target and one bar")
    target, bar = target_events[0], bar_events[0]
    if target.stream_key != _TARGET_STREAM or target.event_type != _TARGET_EVENT_TYPE or target.capability != _TARGET_CAPABILITY:
        raise ValueError("target event does not satisfy cash provider contract")
    if bar.stream_key != _BAR_STREAM or bar.event_type != BAR_OPEN_EVENT_TYPE or bar.capability != BAR_OPEN_CAPABILITY or bar.instrument_id != instrument.instrument_id:
        raise ValueError("bar event does not satisfy cash provider contract")
    if not (intent.timeline_window.data_start <= target.event_time < bar.event_time < intent.timeline_window.end_exclusive):
        raise ValueError("target and bar ordering does not satisfy one-fill contract")
    observation = BarOpenObservation.from_event(bar)
    if observation.open_price is None:
        raise ValueError("cash provider requires one real bar open")
    decision_observation = provider.decision_mark
    if (
        decision_observation.instrument_id != instrument.instrument_id
        or decision_observation.quote_currency_id != intent.reporting_currency
        or decision_observation.price_purpose is not domain.PricePurpose.VALUATION
        or decision_observation.observed_at != target.event_time
        or decision_observation.available_at != target.event_time
    ):
        raise ValueError("decision MarkObservation does not satisfy exact valuation contract")
    final_observation = provider.final_mark
    boundary = intent.timeline_window.end_exclusive
    if (
        final_observation.instrument_id != instrument.instrument_id
        or final_observation.quote_currency_id != intent.reporting_currency
        or final_observation.price_purpose is not domain.PricePurpose.VALUATION
        or final_observation.observed_at >= boundary
        or final_observation.available_at > boundary
    ):
        raise ValueError("final MarkObservation does not satisfy bounded close contract")
    decision = _resolved_mark(
        decision_observation,
        target.event_time,
        "cash-development.decision-mark.v1",
    )
    final_age = boundary.epoch_nanoseconds - final_observation.observed_at.epoch_nanoseconds
    final = _resolved_mark(
        final_observation,
        boundary,
        "cash-development.final-mark.v1",
        max_age_nanoseconds=final_age,
        allow_forward_fill=True,
    )
    timeline = DeterministicTimeline.open(reader=reader, stream_keys=(_BAR_STREAM, _TARGET_STREAM), window=intent.timeline_window)
    if type(timeline) is not DeterministicTimeline:
        raise ValueError("MarketBundle cannot open deterministic cash timeline")
    return _CaseInputs(intent, provider, reader, instrument, target, bar, observation.open_price, decision, final, timeline, PrecomputedTargetStream(_TARGET_STREAM, (target,)))


def _cash_keys(values: _CaseInputs) -> tuple[domain.CashBalanceKey, domain.PositionBalanceKey]:
    venue = values.instrument.instrument_id.venue
    return domain.CashBalanceKey(values.intent.execution_account_id, venue, values.intent.reporting_currency), domain.PositionBalanceKey(values.intent.execution_account_id, venue, values.instrument.instrument_id)


def _ledger(values: _CaseInputs, ids: _Ids) -> tuple[trading.AccountingJournal, trading.LedgerSchema, domain.PortfolioSnapshot, trading.MarketSettlementRules]:
    cash_key, position_key = _cash_keys(values)
    money_scale = values.provider.initial_cash.scale
    schema = trading.LedgerSchema((trading.LedgerBalanceRegistration(cash_key, money_scale), trading.LedgerBalanceRegistration(position_key, values.provider.quantity_lattice.atomic_scale)))
    entry = domain.AccountingJournalEntry(ids.deposit, domain.AccountingEntryType.CAPITAL_DEPOSITED, values.intent.execution_account_id, values.instrument.instrument_id.venue, values.intent.timeline_window.data_start, _sim(values.intent.timeline_window.data_start, 90, "accounting", 1), ("cash-development:initial-capital",), (domain.BalanceChange(cash_key, values.provider.initial_cash),), (), (), ())
    journal = trading.AccountingJournal.from_entries((entry,))
    state = trading.GenericLedger(schema).project(journal)
    zero = domain.Money(0, money_scale, str(values.intent.reporting_currency))
    graph = trading.CurrencyValuationGraph(values.target_event.event_time, domain.PricePurpose.VALUATION, ())
    snapshot = domain.PortfolioSnapshot(values.intent.execution_account_id, values.target_event.event_time, values.intent.reporting_currency, state.cash_balances, state.position_balances, zero, zero, zero, zero, values.provider.initial_cash, (), state.state_hash, domain.canonical_sha256(()), domain.canonical_sha256(()), graph.graph_hash)
    settlement = trading.MarketSettlementRules.create(policy_key="cash-development.immediate-settlement.v1", policy_version=1, account_id=values.intent.execution_account_id, cash_rules=(trading.CashAvailabilityRule(cash_key, False, False, False, (trading.CashReservationUse.CASH, trading.CashReservationUse.FEE_RESERVE), (trading.CashReservationUse.CASH, trading.CashReservationUse.FEE_RESERVE), (trading.CashReservationUse.MARGIN,)),), position_rules=(trading.PositionAvailabilityRule(position_key, False),))
    return journal, schema, snapshot, settlement


def _schedule(values: _CaseInputs) -> TargetStreamDecisionSchedule:
    expectation = trading.DecisionBatchExpectation(values.provider.strategy_id, values.provider.sleeve_id)
    context = trading.StrategyOutputValidationContext(values.provider.strategy_id, values.provider.sleeve_id, values.target_event.event_time, values.provider.instrument_catalog, (values.instrument.instrument_id,))
    return TargetStreamDecisionSchedule(values.target_event.event_time, TimelineSegment.ACTIVE_TRADING, (TargetStreamScheduleEntry(values.target_event.event_id, expectation, context),))


def _policies(values: _CaseInputs, snapshot: domain.PortfolioSnapshot) -> tuple[tuple[trading.StrategyAllocation, ...], trading.PortfolioRiskPolicy, trading.PositionSizingPolicy, tuple[trading.InstrumentSizingInput, ...], trading.RebalancePolicy]:
    allocation_ref = trading.CapitalAllocationPolicyRef("cash-development.capital.v1", 1, domain.canonical_sha256({"initial_cash": values.provider.initial_cash}))
    allocations = (trading.StrategyAllocation(values.provider.strategy_id, values.provider.sleeve_id, values.target_event.event_time, values.intent.reporting_currency, values.provider.initial_cash, allocation_ref, domain.canonical_sha256(snapshot)),)
    risk = trading.PortfolioRiskPolicy.create(policy_key="cash-development.portfolio-risk.v1", policy_version=1, valuation_currency=values.intent.reporting_currency, notional_scale=values.provider.initial_cash.scale, limits=(trading.PortfolioRiskLimit("cash-development.target-cap.v1", trading.PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL, values.provider.initial_cash, trading.PortfolioRiskAction.REJECT, values.instrument.instrument_id), trading.PortfolioRiskLimit("cash-development.gross-cap.v1", trading.PortfolioRiskScope.GROSS_EXPOSURE, values.provider.initial_cash, trading.PortfolioRiskAction.REJECT, None), trading.PortfolioRiskLimit("cash-development.net-cap.v1", trading.PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE, values.provider.initial_cash, trading.PortfolioRiskAction.REJECT, None)))
    sizing_policy = trading.PositionSizingPolicy.create(policy_key="cash-development.sizing.v1", policy_version=1, price_purpose=domain.PricePurpose.VALUATION, rounding=domain.RoundingPolicy.TOWARD_ZERO, residual_policy=trading.ResidualPositionPolicy.FAIL)
    current = domain.Quantity(0, values.provider.quantity_lattice.atomic_scale, str(values.instrument.instrument_id))
    sizing_inputs = (trading.InstrumentSizingInput(values.instrument.instrument_id, values.decision_mark, current, values.provider.quantity_lattice),)
    rebalance = trading.RebalancePolicy.create(policy_key="cash-development.rebalance.v1", policy_version=1, execution_style=domain.ExecutionStyle.MARKET, time_in_force=domain.TimeInForce.DAY, urgency="normal", plan_valid_for_nanoseconds=None)
    return allocations, risk, sizing_policy, sizing_inputs, rebalance


def _translation_mapping() -> trading.OrderTranslationMapping:
    canonical = ("instrument_id", "side", "quantity", "execution_style", "price_constraint", "time_in_force", "reduce_only", "position_effect", "urgency", "reason", "parent_id")
    target = ("instrument", "direction", "amount", "order_style", "price_terms", "tif", "reduce_only", "position_effect", "urgency", "reason", "parent_reference")
    return trading.OrderTranslationMapping.create(translator_key="cash-development.translation.v1", translator_version=1, target_profile_id=_PROFILE_PREFIX, field_rules=tuple(trading.OrderTranslationFieldRule(a, b) for a, b in zip(canonical, target, strict=True)))


def _order_rules(values: _CaseInputs, price: domain.Price) -> trading.OrderRuleTimeline:
    component = _profile_ref(trading.ProfilePortType.ORDER_RULE_MODEL, "cash-development.order-rules.v1")
    snapshot = trading.OrderRuleSnapshot.create(component_ref=component, instrument_id=values.instrument.instrument_id, session_id=domain.SessionId("cash-development", "single-window"), session_state=trading.MarketSessionState.OPEN, quantity_lattice=values.provider.quantity_lattice, price_scale=price.scale, price_tick_units=1, lower_price_limit=None, upper_price_limit=None, permitted_sides=(domain.OrderSide.BUY, domain.OrderSide.SELL), permitted_position_effects=(domain.PositionEffect.AUTO, domain.PositionEffect.OPEN, domain.PositionEffect.CLOSE), reduce_only_required=False, notional_rounding=domain.RoundingPolicy.TOWARD_ZERO, supplemental_decisions=())
    interval = trading.OrderRuleInterval.create(effective_from=values.intent.timeline_window.data_start, effective_to_exclusive=values.intent.timeline_window.end_exclusive, snapshot=snapshot)
    return trading.OrderRuleTimeline.create(timeline_key="cash-development.order-rules.v1", timeline_version=1, instrument_id=values.instrument.instrument_id, intervals=(interval,))


def _notional(price: domain.Price, at: domain.UtcInstant) -> trading.OrderRuleNotionalEvidence:
    return trading.OrderRuleNotionalEvidence(trading.NotionalPriceBasis.SUPPLIED_REFERENCE, price, domain.canonical_sha256({"type": "cash_development_reference_price", "price": price, "available_at": at}), at)


def _zero_reservation_rules(values: _CaseInputs) -> trading.FeeReservationRuleSet:
    scale, currency = values.provider.initial_cash.scale, values.intent.reporting_currency
    quant = domain.QuantizationPolicy("cash-development.fee-reservation.v1", scale, domain.RoundingPolicy.CEILING)
    refs = (_profile_ref(trading.ProfilePortType.FEE_ASSESSMENT_POLICY, "cash-development.market-fee.v1"), _profile_ref(trading.ProfilePortType.TAX_POLICY, "cash-development.tax.v1"), trading.AccountFeeScheduleRef("cash-development.account-fee.v1", 1, domain.canonical_sha256({"fee": 0})))
    rules = tuple(trading.FeeReservationChargeRule(source, f"zero-{source.value}", trading.FeeReservationBasis.ORDER_NOTIONAL, trading.FeeReservationApplicability.NOT_APPLICABLE, domain.Rate(0, domain.Scale(4), "fee_fraction"), None, quant) for source in trading.FeeReservationRuleSource)
    return trading.FeeReservationRuleSet.create(market_fee_policy_ref=refs[0], tax_policy_ref=refs[1], account_fee_schedule_ref=refs[2], reservation_currency=currency, reservation_scale=scale, charge_rules=rules, minimums=())


def _zero_final_fee_rules(values: _CaseInputs) -> trading.FinalFeeRuleSet:
    scale, currency = values.provider.initial_cash.scale, values.intent.reporting_currency
    quant = domain.QuantizationPolicy("cash-development.final-fee.v1", scale, domain.RoundingPolicy.HALF_EVEN)
    market = _profile_ref(trading.ProfilePortType.FEE_ASSESSMENT_POLICY, "cash-development.market-fee.v1")
    tax = _profile_ref(trading.ProfilePortType.TAX_POLICY, "cash-development.tax.v1")
    account = trading.AccountFeeScheduleRef("cash-development.account-fee.v1", 1, domain.canonical_sha256({"fee": 0}))
    rules = tuple(trading.FinalFeeChargeRule(source, f"zero-{source.value}-{basis.value}", basis, trading.FinalFeeCalculationBasis.NOTIONAL_RATE, trading.FinalFeeApplicability.NOT_APPLICABLE, domain.Rate(0, domain.Scale(4), "fee_fraction"), None, quant) for basis in domain.FeeBasisType for source in trading.FinalFeeRuleSource)
    return trading.FinalFeeRuleSet.create(market_fee_policy_ref=market, tax_policy_ref=tax, account_fee_schedule_ref=account, assessment_currency=currency, assessment_scale=scale, charge_rules=rules, minimums=())


def _resources(values: _CaseInputs, journal: trading.AccountingJournal, schema: trading.LedgerSchema, settlement_rules: trading.MarketSettlementRules) -> tuple[trading.ResourceReservationState, trading.AvailabilityState]:
    reservations = trading.ResourceReservationBook(values.intent.execution_account_id).project((), ())
    settlement = trading.SettlementBook(values.intent.execution_account_id).project()
    availability = trading.AvailabilityProjection().project(trading.GenericLedger(schema).project(journal), settlement, reservations, settlement_rules)
    return reservations, availability


def _planned_order(values: _CaseInputs, ids: _Ids, snapshot: domain.PortfolioSnapshot, journal: trading.AccountingJournal, schema: trading.LedgerSchema, settlement_rules: trading.MarketSettlementRules) -> tuple[domain.Order, trading.TargetValidity, tuple[trading.StrategyAllocation, ...], trading.PortfolioRiskPolicy, trading.PositionSizingPolicy, tuple[trading.InstrumentSizingInput, ...], trading.RebalancePolicy]:
    schedule = _schedule(values)
    injected = PrecomputedTargetStreamAdapter().inject(stream=values.target_stream, timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, values.target_event),), schedule=schedule)
    if injected.injection is None:
        raise ValueError("target event cannot produce one decision batch")
    allocations, risk, sizing_policy, sizing_inputs, rebalance = _policies(values, snapshot)
    allocated = trading.PortfolioAllocator().allocate(sleeve_state=injected.injection.state, portfolio_snapshot=snapshot, allocations=allocations, target_notional_scale=values.provider.initial_cash.scale)
    if allocated.allocation is None:
        raise ValueError("target allocation failed")
    approved = trading.PortfolioRiskEvaluator().evaluate(allocation=allocated.allocation, policy=risk)
    if approved.approved_target is None:
        raise ValueError("target risk evaluation failed")
    sized = trading.PositionSizer().materialize(approved_target=approved.approved_target, source_decision_batch_id=injected.injection.batch.decision_batch_id, policy=sizing_policy, inputs=sizing_inputs)
    if sized.normalized_target is None:
        raise ValueError("target sizing failed")
    candidate = values.target_event.payload.get("candidate")
    expires = candidate.get("expires_at") if hasattr(candidate, "get") else None
    if isinstance(expires, bool) or not isinstance(expires, int):
        raise ValueError("target candidate expires_at must be integer")
    validity = trading.TargetValidity(sized.normalized_target.normalized_target_id, sized.normalized_target.normalized_target_hash, values.target_event.event_time, domain.UtcInstant(expires))
    reservations, availability = _resources(values, journal, schema, settlement_rules)
    planned = trading.RebalanceCoordinator().coordinate(target=sized.normalized_target, target_validity=validity, portfolio_snapshot=snapshot, working_orders=(), reservations=reservations, availability=availability, policy=rebalance, as_of=values.target_event.event_time)
    if planned.decision is None or len(planned.decision.plan.planned_orders) != 1:
        raise ValueError("cash provider target must produce exactly one order")
    planned_order = planned.decision.plan.planned_orders[0]
    if (
        planned_order.intent.side is not domain.OrderSide.BUY
        or planned_order.intent.quantity.units <= 0
    ):
        raise ValueError("cash provider target must be one positive long order")
    order = domain.Order(ids.order, values.intent.execution_account_id, planned_order.intent, _sim(values.target_event.event_time, 80, "order_admission", 1))
    return order, validity, allocations, risk, sizing_policy, sizing_inputs, rebalance


def _account_risk(values: _CaseInputs) -> trading.AccountRiskPolicy:
    return trading.AccountRiskPolicy.create(policy_key="cash-development.account-risk.v1", policy_version=1, account_id=values.intent.execution_account_id, venue_id=values.instrument.instrument_id.venue, allowed_sides=(domain.OrderSide.BUY, domain.OrderSide.SELL), allowed_position_effects=(domain.PositionEffect.AUTO, domain.PositionEffect.OPEN, domain.PositionEffect.CLOSE), allowed_reduce_only_values=(False, True), fee_reserve_funding_source=trading.FeeReserveFundingSource.TRADABLE_CASH, order_capacity_limit=1, exposure_capacity_limits=(trading.ExposureCapacityLimit(values.provider.initial_cash),))


def _pretrade(values: _CaseInputs, order: domain.Order, price: domain.Price, at: domain.UtcInstant) -> ResolvedPreTradePlan:
    capability = trading.OrderCapabilityValidator().validate(order.intent, values.provider.order_capabilities)
    if capability.approval is None:
        # The engine needs the same well-formed plan even when capability is deliberately absent.
        permissive = trading.OrderCapabilitySet.create(capability_set_key="cash-development.internal-capabilities.v1", capability_set_version=1, style_capabilities=(trading.OrderStyleCapability(domain.ExecutionStyle.MARKET, (trading.PriceConstraintShape.NONE,), (domain.TimeInForce.DAY,)),), supports_reduce_only=True, supported_position_effects=(domain.PositionEffect.AUTO, domain.PositionEffect.OPEN, domain.PositionEffect.CLOSE), declared_capability_keys=tuple(value.value for value in trading.OrderCapabilityKey))
        capability = trading.OrderCapabilityValidator().validate(order.intent, permissive)
    if capability.approval is None:
        raise RuntimeError("permissive cash capability set did not approve order")
    translated = trading.OrderTranslator().translate(order, capability.approval, _translation_mapping(), at)
    if translated.executable_spec is None:
        raise ValueError("cash order translation failed")
    timeline = _order_rules(values, price)
    evidence = _notional(price, at)
    market = trading.MarketRuleEvaluator().evaluate(trading.OrderRuleEvaluationInput(translated.executable_spec, at, evidence), timeline)
    if market.approval is None:
        raise ValueError("cash order market-rule evaluation failed")
    fee_rules = _zero_reservation_rules(values)
    fee = trading.FeeReservationEstimator().estimate(market.approval, fee_rules, at)
    if fee.proposal is None:
        raise ValueError("cash fee reservation failed")
    notional = market.approval.calculated_notional
    commitment = trading.ReservationCommitment(
        cash=(notional,),
        fee_reserve=fee.proposal.commitment.fee_reserve,
        order_capacity_units=1,
        exposure_capacity=(notional,),
    )
    return ResolvedPreTradePlan(timeline, evidence, at, fee_rules, at, commitment, "cash-development.resource-requirement.v1", 1, domain.canonical_sha256(commitment), _account_risk(values), at)


def _admission(values: _CaseInputs, order: domain.Order, ids: _Ids) -> ResolvedOrderAdmission:
    event_types = (domain.OrderEventType.ORDER_INTENT_CREATED, domain.OrderEventType.ORDER_CAPABILITY_APPROVED, domain.OrderEventType.ORDER_TRANSLATED, domain.OrderEventType.MARKET_RULE_APPROVED, domain.OrderEventType.FEE_RESERVATION_ESTIMATED, domain.OrderEventType.PRE_TRADE_RISK_APPROVED, domain.OrderEventType.ORDER_SUBMITTED, domain.OrderEventType.ORDER_ACCEPTED)
    plans = tuple(OrderEventPlan(value, ids.admission_events[i], _sim(values.target_event.event_time, 80, "order_admission", i + 1), f"cash-development:{value.value}" if value in {domain.OrderEventType.ORDER_SUBMITTED, domain.OrderEventType.ORDER_ACCEPTED} else None) for i, value in enumerate(event_types))
    return ResolvedOrderAdmission(order, values.provider.order_capabilities, _translation_mapping(), values.target_event.event_time, _pretrade(values, order, values.decision_mark.price, values.target_event.event_time), plans)


def _final_snapshot(values: _CaseInputs, order: domain.Order) -> SnapshotProjectionPlan:
    cash_key, position_key = _cash_keys(values)
    fill_notional = values.bar_price.notional(order.intent.quantity, result_scale=values.provider.initial_cash.scale, rounding=domain.RoundingPolicy.HALF_EVEN)
    market_value = values.final_mark.price.notional(order.intent.quantity, result_scale=values.provider.initial_cash.scale, rounding=domain.RoundingPolicy.HALF_EVEN)
    cash = values.provider.initial_cash - fill_notional
    unrealized = market_value - fill_notional
    graph = trading.CurrencyValuationGraph(values.intent.timeline_window.end_exclusive, domain.PricePurpose.VALUATION, ())
    resolution = graph.resolve(values.intent.reporting_currency, values.intent.reporting_currency).resolution
    if resolution is None:
        raise ValueError("reporting currency self-resolution failed")
    quant = domain.QuantizationPolicy("cash-development.position-value.v1", values.provider.initial_cash.scale, domain.RoundingPolicy.HALF_EVEN)
    valuations = (trading.ReportingCurrencyValuation(trading.PortfolioValueRef(trading.PortfolioValueKind.CASH, cash_key), cash, cash, resolution, graph.graph_hash), trading.ReportingCurrencyValuation(trading.PortfolioValueRef(trading.PortfolioValueKind.POSITION_MARKET_VALUE, position_key), market_value, market_value, resolution, graph.graph_hash, quant), trading.ReportingCurrencyValuation(trading.PortfolioValueRef(trading.PortfolioValueKind.UNREALIZED_PNL, position_key), unrealized, unrealized, resolution, graph.graph_hash))
    return SnapshotProjectionPlan((values.final_mark,), valuations, values.intent.reporting_currency, values.provider.initial_cash.scale, values.intent.timeline_window.end_exclusive, graph.graph_hash)


@dataclass(frozen=True, slots=True)
class _CashAccountingSemantics:
    cash_key: domain.CashBalanceKey
    position_key: domain.PositionBalanceKey
    cost_basis_policy: trading.CostBasisPolicy
    notional_quantization: domain.QuantizationPolicy

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cash_development_accounting_semantics", "cash_key": self.cash_key, "position_key": self.position_key, "cost_basis_policy": self.cost_basis_policy, "notional_quantization": self.notional_quantization}


def _accounting_plan(values: _CaseInputs, ids: _Ids) -> FillAccountingDispatchPlan:
    cash_key, position_key = _cash_keys(values)
    policy = trading.CostBasisPolicy("cash-development.cost-basis.v1", 1, trading.CostBasisMethod.FIFO, domain.RoundingPolicy.HALF_EVEN)
    quant = domain.QuantizationPolicy("cash-development.notional.v1", values.provider.initial_cash.scale, domain.RoundingPolicy.HALF_EVEN)
    fees = _zero_final_fee_rules(values)
    recorded = _sim(values.bar_event.event_time, 90, "accounting", 1)
    fee_recorded = _sim(values.bar_event.event_time, 90, "accounting", 2)
    payload = CashFillAccountingPlan(cash_key, position_key, policy, quant, ids.fill_journal, recorded, fees, ids.fee, values.bar_event.event_time, ids.fee_journal, fee_recorded)
    spec = default_cash_financial_dispatcher_spec()
    return FillAccountingDispatchPlan(values.bar_event.event_id, ids.fill, spec.position_accounting_component, payload, _CashAccountingSemantics(cash_key, position_key, policy, quant), ids.fill_journal, recorded, FeeAccountingDispatchPlan(cash_key, fees, ids.fee, values.bar_event.event_time, ids.fee_journal, fee_recorded), ("position_accounting",))


def _slippage(values: _CaseInputs, quantity: domain.Quantity) -> DeterministicBpsSlippageModel:
    return DeterministicBpsSlippageModel(_simulation_ref(SimulationPortType.SLIPPAGE_MODEL, "zero_slippage.development.v1"), SlippageCalibrationRef("cash-development.zero-slippage.v1", 1, domain.canonical_sha256({"basis_points": 0})), SlippageApplicabilityEnvelope.create(envelope_key="cash-development.zero-slippage.v1", envelope_version=1, instrument_id=values.instrument.instrument_id, valid_from=values.bar_event.event_time, valid_to_exclusive=values.intent.timeline_window.end_exclusive, maximum_quantity=quantity, allowed_market_state_keys=("normal",)), 0, domain.Scale(0), domain.RoundingPolicy.HALF_UP, (SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,))


def _build_case(values: _CaseInputs, ids: _Ids, semantic_hash: str) -> ResolvedExecutionCase:
    journal, schema, initial_snapshot, settlement_rules = _ledger(values, ids)
    order, validity, allocations, risk, sizing_policy, sizing_inputs, rebalance = _planned_order(values, ids, initial_snapshot, journal, schema, settlement_rules)
    admission = _admission(values, order, ids)
    cycle = ResolvedDecisionCycle(_schedule(values), allocations, values.provider.initial_cash.scale, risk, sizing_policy, sizing_inputs, validity, rebalance, values.target_event.event_time, (admission,))
    bar_execution = ResolvedBarExecution(values.bar_event.event_id, ids.order, _pretrade(values, order, values.bar_price, values.bar_event.event_time), BarLiquidityEvidence.create(evidence_key="cash-development.full-liquidity.v1", evidence_version=1, market_event=values.bar_event, evaluated_at=values.bar_event.event_time, approved=True, reason_code=None, source_hash=values.bar_event.event_hash), SlippageMarketState("normal", values.bar_event.event_time, values.bar_event.available_time, values.bar_event.event_id, values.bar_event.revision_id, values.bar_event.event_hash), _slippage(values, order.intent.quantity), ids.fill, ids.fill_event, _sim(values.bar_event.event_time, 70, "fill", 1), _accounting_plan(values, ids))
    snapshot_plan = _final_snapshot(values, order)
    financial_state = ResolvedFinancialState(journal, schema, initial_snapshot, (PositionLotBook(_cash_keys(values)[1]),), (), (), (), trading.SettlementBook(values.intent.execution_account_id), settlement_rules)
    dispatch = FinancialDispatchPlan(default_cash_financial_dispatcher_spec(), (), snapshot_plan, ("final_snapshot", "position_accounting"))
    execution_model = NextEligibleBarOpenModel.create(actions=((domain.TimeInForce.DAY, NoEligibleBarAction.EXPIRE), (domain.TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE), (domain.TimeInForce.IOC, NoEligibleBarAction.EXPIRE), (domain.TimeInForce.FOK, NoEligibleBarAction.EXPIRE), (domain.TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE)))
    return ResolvedExecutionCase("cash.precomputed-target.development.v1", 1, semantic_hash, values.timeline, 1, values.target_stream, (cycle,), (bar_execution,), financial_state, dispatch, execution_model, snapshot_plan, MarkToMarketCloseoutPolicy())


def _registry(values: _CaseInputs, case: ResolvedExecutionCase) -> BacktestProfileRegistry:
    dispatcher = default_cash_financial_dispatcher_spec()
    actual_profile = {dispatcher.position_accounting_component.port_type: dispatcher.position_accounting_component, dispatcher.financing_component.port_type: dispatcher.financing_component, dispatcher.margin_component.port_type: dispatcher.margin_component}
    market_components = tuple(sorted((actual_profile.get(port) or _profile_ref(port, f"cash-development.{port.value}.v1") for port in trading.ProfilePortType), key=lambda value: value.port_type.value))
    actual_simulation = {case.execution_model.component_ref.port_type: case.execution_model.component_ref, case.closeout_policy.spec().component_ref.port_type: case.closeout_policy.spec().component_ref, case.bar_executions[0].slippage_model.component_ref.port_type: case.bar_executions[0].slippage_model.component_ref, dispatcher.liquidation_audit_component.port_type: dispatcher.liquidation_audit_component}
    simulation_components = tuple(sorted((actual_simulation.get(port) or _simulation_ref(port, f"cash-development.{port.value}.v1") for port in SimulationPortType), key=lambda value: value.port_type.value))
    market_impl, simulation_impl, account_impl = _ProfileImplementation("market", market_components), _ProfileImplementation("simulation", simulation_components), _ProfileImplementation("account", ())
    market = MarketSemanticsProfileRegistration(_MARKET_KEY, 1, market_impl.profile_digest, market_impl, values.instrument.instrument_id.venue.value, (BAR_OPEN_CAPABILITY, _TARGET_CAPABILITY), market_components, RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False)
    simulation = SimulationProfileRegistration(_SIMULATION_KEY, 1, simulation_impl.profile_digest, simulation_impl, "bar", (StrategyFamily.PRECOMPUTED_TARGET,), (BAR_OPEN_CAPABILITY, _TARGET_CAPABILITY), simulation_components, RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False)
    account = ExecutionAccountProfileRegistration(_ACCOUNT_KEY, 1, account_impl.profile_digest, account_impl, values.intent.execution_account_id, values.instrument.instrument_id.venue.value, "cash", "none", (values.intent.reporting_currency,), RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False)
    return BacktestProfileRegistry((market,), (simulation,), (account,))


def _provider_build_manifest(
    base: BuildArtifactManifest,
    registry: BacktestProfileRegistry,
) -> BuildArtifactManifest:
    registrations = (
        *registry.market_semantics_profiles,
        *registry.simulation_profiles,
        *registry.execution_account_profiles,
    )
    provider_refs = tuple(
        BuildArtifactRef(
            role=BuildArtifactRole.PROFILE_COMPONENT,
            artifact_key=value.profile_key,
            artifact_version=str(value.profile_version),
            install_mode=ArtifactInstallMode.WHEEL,
            source_tree_state=SourceTreeState.CLEAN,
            content_hash=value.profile_digest,
            source_snapshot_hash=None,
        )
        for value in registrations
    )
    expected_by_key = {value.artifact_key: value for value in provider_refs}
    conflicts = tuple(
        sorted(
            {
                value.artifact_key
                for value in base.artifacts
                if value.artifact_key in expected_by_key
                and value != expected_by_key[value.artifact_key]
            }
        )
    )
    if conflicts:
        raise ValueError(
            "caller build manifest conflicts with provider profile keys: "
            + ", ".join(conflicts)
        )
    artifacts = tuple(
        value
        for value in base.artifacts
        if value.artifact_key not in expected_by_key
    ) + provider_refs
    return replace(base, artifacts=artifacts)


def _publish(publisher: ArtifactEnvelopePublisher, envelope: domain.ArtifactEnvelope) -> domain.ArtifactRef:
    ref = publisher.put(envelope=envelope)
    expected = domain.ArtifactRef.from_envelope(envelope)
    if type(ref) is not domain.ArtifactRef or ref != expected:
        raise ValueError("publisher returned ref does not bind envelope")
    return ref


def _verify_published(
    reader: ArtifactEnvelopeReader,
    ref: domain.ArtifactRef,
    envelope: domain.ArtifactEnvelope,
) -> None:
    try:
        result = reader.read(ref=ref)
    except Exception as error:
        raise ValueError("published artifact readback unavailable") from error
    if type(result) is not domain.ArtifactReadResult:
        raise TypeError("artifact reader must return exact ArtifactReadResult")
    expected_bytes = domain.canonical_bytes(envelope)
    if (
        result.envelope != envelope
        or result.source_bytes != expected_bytes
        or result.source_hash != domain.canonical_sha256(envelope)
        or domain.ArtifactRef.from_envelope(result.envelope) != ref
    ):
        raise ValueError("published artifact readback does not bind envelope")


def _prepare_cash_development_backtest(
    *,
    request_intent: CashDevelopmentRequestIntent,
    provider_inputs: CashDevelopmentProviderInputs,
    artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader,
    publication_root: Path,
    model_binding: ModelRequestBinding | None,
) -> PreparedBacktestExecution:
    if type(request_intent) is not CashDevelopmentRequestIntent or type(provider_inputs) is not CashDevelopmentProviderInputs:
        raise TypeError("request_intent and provider_inputs must be exact public values")
    if not callable(getattr(artifact_reader, "read", None)) or not callable(getattr(artifact_publisher, "put", None)):
        raise TypeError("artifact reader and publisher must satisfy structural ports")
    if not isinstance(publication_root, Path):
        raise TypeError("publication_root must be pathlib.Path")
    values = _case_inputs(request_intent, provider_inputs, market_reader)
    builder = _CashCaseBuilder(values)
    spec = builder.semantic_spec()
    provisional = _build_case(values, builder._placeholder_ids(), spec.semantic_spec_hash)
    registry = _registry(values, provisional)
    build_manifest = _provider_build_manifest(
        provider_inputs.build_artifact_manifest,
        registry,
    )
    request = BacktestRequest(
        schema_version=1,
        experiment_id=request_intent.experiment_id,
        timeline_window=request_intent.timeline_window,
        market_semantics_profile_key=_MARKET_KEY,
        simulation_profile_key=_SIMULATION_KEY,
        execution_account_profile_key=_ACCOUNT_KEY,
        execution_account_id=request_intent.execution_account_id,
        reporting_currency=request_intent.reporting_currency,
        market_bundle_ref=market_reader.bundle_ref,
        target_stream_digest=spec.target_stream_digest,
        execution_case_semantic_hash=spec.semantic_spec_hash,
        master_random_seed=request_intent.master_random_seed,
        build_artifact_manifest_hash=build_manifest.manifest_hash,
        strategy_family=StrategyFamily.PRECOMPUTED_TARGET,
        engine_kind="bar",
        result_grade_requested=RequestedResultGrade.DEVELOPMENT,
        model_binding=model_binding,
    )
    outcome = ProfileResolver().resolve(request=request, registry=registry, market_bundle_manifest=market_reader.manifest, build_artifact_manifest=build_manifest)
    if outcome.resolved is None:
        raise ValueError(f"cash development request cannot resolve: {outcome.failure.code.value if outcome.failure else 'unknown'}")
    case = ExecutionCaseComposer().compose(resolved_request=outcome.resolved, builder=builder)
    bundle = materialize_execution_input_bundle_v2(resolved_request=outcome.resolved, execution_case=case)
    decoded_bundle = _EXECUTION_INPUT_CATALOG.read(domain.canonical_bytes(bundle))
    if (
        decoded_bundle.envelope != bundle
        or type(decoded_bundle.artifact) is not _DecodedExecutionInputBundleV2
    ):
        raise ValueError("execution input bundle does not round-trip existing catalog")
    request_envelope = domain.ArtifactEnvelope.create("backtest_request", 1, request)
    request_artifact_ref = _publish(artifact_publisher, request_envelope)
    bundle_ref = _publish(artifact_publisher, bundle)
    _verify_published(artifact_reader, request_artifact_ref, request_envelope)
    _verify_published(artifact_reader, bundle_ref, bundle)
    request_ref = BacktestRequestRef.from_artifact_ref(request_artifact_ref)
    execution_request = BacktestExecutionRequest(2, request, bundle_ref)
    runtime = BacktestRuntime(registry=registry, artifact_reader=artifact_reader, artifact_publisher=artifact_publisher, market_reader=market_reader, publication_root=publication_root)
    return PreparedBacktestExecution(request_ref, outcome.resolved.semantic_run_id, execution_request, runtime)


def prepare_cash_development_backtest(
    *,
    request_intent: CashDevelopmentRequestIntent,
    provider_inputs: CashDevelopmentProviderInputs,
    artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader,
    publication_root: Path,
) -> PreparedBacktestExecution:
    return _prepare_cash_development_backtest(
        request_intent=request_intent,
        provider_inputs=provider_inputs,
        artifact_reader=artifact_reader,
        artifact_publisher=artifact_publisher,
        market_reader=market_reader,
        publication_root=publication_root,
        model_binding=None,
    )


def prepare_model_bound_cash_development_backtest(
    *,
    request_intent: CashDevelopmentRequestIntent,
    provider_inputs: CashDevelopmentProviderInputs,
    model_timeline: ModelRevisionTimeline,
    expected_model_key: str,
    expected_artifact_ref_hash: str,
    artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader,
    publication_root: Path,
) -> PreparedModelBoundBacktestExecution:
    if (
        type(request_intent) is not CashDevelopmentRequestIntent
        or type(provider_inputs) is not CashDevelopmentProviderInputs
    ):
        raise TypeError("request_intent and provider_inputs must be exact public values")
    if type(model_timeline) is not ModelRevisionTimeline:
        raise ModelPreparationFailure("MODEL_TIMELINE_INVALID")
    try:
        _canonical_text("expected_model_key", expected_model_key)
    except (TypeError, ValueError) as error:
        raise ModelPreparationFailure("MODEL_BINDING_MISMATCH") from error
    if (
        type(expected_artifact_ref_hash) is not str
        or _HASH_PATTERN.fullmatch(expected_artifact_ref_hash) is None
    ):
        raise ModelPreparationFailure("MODEL_BINDING_MISMATCH")
    selected = model_timeline.select()
    if selected is None:
        raise ModelPreparationFailure("MODEL_ARTIFACT_UNAVAILABLE")
    if (
        selected.model_key != expected_model_key
        or selected.artifact_ref_hash != expected_artifact_ref_hash
    ):
        raise ModelPreparationFailure("MODEL_BINDING_MISMATCH")
    binding = ModelRequestBinding(
        strategy_id=provider_inputs.strategy_id,
        input_name="primary_model",
        model_key=selected.model_key,
        timeline_hash=model_timeline.timeline_hash,
        artifact_ref_hash=selected.artifact_ref_hash,
    )
    prepared = _prepare_cash_development_backtest(
        request_intent=request_intent,
        provider_inputs=provider_inputs,
        artifact_reader=artifact_reader,
        artifact_publisher=artifact_publisher,
        market_reader=market_reader,
        publication_root=publication_root,
        model_binding=binding,
    )
    return PreparedModelBoundBacktestExecution(
        prepared.request_ref,
        prepared.semantic_run_id,
        prepared.execution_request,
        prepared.runtime,
        binding,
    )
