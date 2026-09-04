"""Sole-facade G12M Tushare fixed-singleton qualification route v2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import crypto_quant_domain as domain
import crypto_quant_trading as trading
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
)

from .analysis import AnalysisArtifactRefV2, VerifiedBacktestAnalysisV2
from .analysis_derivation import BacktestAnalysisRuntime
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_fixed_singleton_no_trade_profile_v2 import (
    create_cn_a_share_fixed_singleton_no_trade_authority_v2,
)
from .composition import (
    ExecutionCaseComposer,
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from .decision_schedule import DecisionSchedule, DecisionScheduleEntry
from .engine import (
    EngineStage,
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    ResolvedDecisionCycle,
    ResolvedFinancialState,
    SnapshotProjectionPlan,
)
from .evidence_repository import BacktestEvidenceRepository
from .execution import BarOpenObservation
from .execution_inputs import (
    BacktestExecutionRequest,
    _materialize_execution_input_bundle_v4,
)
from .facade import BacktestRuntime
from .financial_dispatch import FinancialDispatchPlan
from .multi_resolution_market_data import ExecutionDataBinding
from .multi_resolution_preparation import (
    MarketDataCaseAuthority,
    MultiResolutionMarketDataPreparation,
    _capture_market_bundle_reader_v1,
    prepare_multi_resolution_market_data_v1,
)
from .publication_refs import BacktestCanonicalPublicationRefV2
from .resolution import (
    BacktestProfileRegistry,
    BacktestRequest,
    ProfileResolver,
    RequestedResultGrade,
    StrategyFamily,
)
from .target_stream import (
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
)
from .timeline import (
    DeterministicTimeline,
    TimelineEvent,
    TimelineSegment,
    TimelineWindow,
)
from .verified_publications import (
    VerifiedCompletedPublicationV3,
    _VerifiedCompletedEvidenceV3,
)

_SCHEMA_VERSION = 2
_BUNDLE_KEY = "g12m-tushare-fixed-singleton-execution-bundle-v2"
_BUNDLE_MANIFEST_HASH = (
    "sha256:2ea4d3c58076312ff86ee175fac2f1173fb28f01e4e4d31ca372ca0d345e750b"
)
_BUNDLE_CONTENT_HASH = (
    "sha256:a0b6319c07aaa810ba490924f2267ebb93f72d5037432b30dd6a0a5bbb3fb8ff"
)
_CATALOG_HASH = (
    "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
)
_TARGET_STREAM_KEY = "cn-a-share-fixed-singleton-zero-target-v1"
_PROJECTION_STREAM_KEY = "g12m.tushare.fixed-singleton.bar-open.v2"
_SOURCE_STREAM_KEY = "tushare_cn_a_share.daily.publication.xshe.000001.v1"
_STREAM_KEYS = (_TARGET_STREAM_KEY, _PROJECTION_STREAM_KEY, _SOURCE_STREAM_KEY)
_CAPABILITIES = (
    MarketBundleCapability("bar_open", 1),
    MarketBundleCapability("precomputed_target_stream", 1),
    MarketBundleCapability("tushare_cn_a_share.daily-publications", 1),
)
_CNY = domain.CurrencyId("CNY")
_SCALE = domain.Scale(2)
_INITIAL_CASH = domain.Money(10_000_000, _SCALE, "CNY")
_IDENTITY_PLAN = (
    ExecutionCaseIdentityRule(
        "journal.initial.0",
        "g12m-tushare-fixed-singleton.initial-deposit.v2",
        0,
        domain.DomainIdKind.JOURNAL,
    ),
)
_NONCLAIMS = (
    "corporate_action_absence_not_claimed",
    "deployment_not_authorized",
    "historical_provider_availability_time_not_claimed",
    "live_eligibility_not_claimed",
    "provider_finality_or_completeness_not_claimed",
)


def _catalog(instrument: domain.InstrumentId) -> domain.InstrumentCatalog:
    return domain.InstrumentCatalog(
        currencies=(_CNY,),
        instruments=(
            domain.InstrumentDefinition(
                instrument,
                domain.InstrumentType.EQUITY,
                None,
                _CNY,
                _CNY,
            ),
        ),
        symbol_timelines=(),
    )


def _retained_events(
    market_reader: MarketBundleReader,
) -> tuple[
    MarketBundleRef,
    MarketBundleManifest,
    tuple[MarketEvent, ...],
    tuple[MarketEvent, ...],
    tuple[MarketEvent, ...],
]:
    expected_ref = MarketBundleRef(_BUNDLE_KEY, _BUNDLE_MANIFEST_HASH)
    retained = _capture_market_bundle_reader_v1(expected_ref, market_reader)
    if retained is None:
        raise ValueError("retained Local Reader Bundle cannot be captured exactly")
    manifest = retained.manifest
    if (
        retained.bundle_ref != expected_ref
        or manifest.bundle_key != _BUNDLE_KEY
        or manifest.schema_version != 1
        or manifest.instrument_catalog_hash != _CATALOG_HASH
        or manifest.capabilities != _CAPABILITIES
        or manifest.content_hash != _BUNDLE_CONTENT_HASH
        or tuple(value.stream_key for value in manifest.streams) != _STREAM_KEYS
        or tuple(value.event_count for value in manifest.streams) != (1, 19, 19)
        or MarketBundleRef.from_manifest(manifest) != expected_ref
    ):
        raise ValueError("market_reader does not retain the exact V2-02 manifest")
    target = retained.streams[_TARGET_STREAM_KEY]
    projections = retained.streams[_PROJECTION_STREAM_KEY]
    sources = retained.streams[_SOURCE_STREAM_KEY]
    if (
        len(target) != 1
        or len(projections) != 19
        or len(sources) != 19
        or any(type(value) is not MarketEvent for value in (*target, *projections, *sources))
        or any(value.timeline_instant >= target[0].timeline_instant for value in (*sources, *projections))
    ):
        raise ValueError("market_reader stream membership or causality mismatch")
    for event in projections:
        observation = BarOpenObservation.from_event(event)
        if observation.open_price is None:
            raise ValueError("bar_open projection must be a real observation")
    return expected_ref, manifest, sources, projections, target


def _registry(authority: object) -> BacktestProfileRegistry:
    return BacktestProfileRegistry(
        (authority.market_registration,),  # type: ignore[attr-defined]
        (authority.simulation_registration,),  # type: ignore[attr-defined]
        (authority.execution_account_registration,),  # type: ignore[attr-defined]
    )


def _request(
    *,
    authority: object,
    bundle_ref: MarketBundleRef,
    window: TimelineWindow,
    semantic_hash: str,
) -> BacktestRequest:
    return BacktestRequest(
        schema_version=1,
        experiment_id="g12m-tushare-fixed-singleton-route-v2",
        timeline_window=window,
        market_semantics_profile_key=authority.market_registration.profile_key,  # type: ignore[attr-defined]
        simulation_profile_key=authority.simulation_registration.profile_key,  # type: ignore[attr-defined]
        execution_account_profile_key=authority.execution_account_registration.profile_key,  # type: ignore[attr-defined]
        execution_account_id=authority.execution_account_registration.account_id,  # type: ignore[attr-defined]
        reporting_currency=_CNY,
        market_bundle_ref=bundle_ref,
        target_stream_digest=authority.target_commitment.target_stream_digest,  # type: ignore[attr-defined]
        execution_case_semantic_hash=semantic_hash,
        master_random_seed=0,
        build_artifact_manifest_hash=authority.build_manifest.manifest_hash,  # type: ignore[attr-defined]
        strategy_family=StrategyFamily.PRECOMPUTED_TARGET,
        engine_kind=authority.simulation_registration.engine_kind,  # type: ignore[attr-defined]
        result_grade_requested=RequestedResultGrade.DECISION_GRADE,
    )


def _resolved(
    *,
    request: BacktestRequest,
    registry: BacktestProfileRegistry,
    manifest: MarketBundleManifest,
    build_manifest: object,
):
    outcome = ProfileResolver().resolve(
        request=request,
        registry=registry,
        market_bundle_manifest=manifest,
        build_artifact_manifest=build_manifest,  # type: ignore[arg-type]
    )
    if outcome.failure is not None or outcome.resolved is None:
        raise ValueError("exact authority request did not resolve")
    return outcome.resolved


def _initial_financial_state(
    *,
    account_id: str,
    venue: domain.VenueId,
    decision_time: domain.UtcInstant,
    window: TimelineWindow,
    journal_id: domain.DomainId,
) -> ResolvedFinancialState:
    cash_key = domain.CashBalanceKey(account_id, venue, _CNY)
    schema = trading.LedgerSchema(
        (trading.LedgerBalanceRegistration(cash_key, _SCALE),)
    )
    entry = domain.AccountingJournalEntry(
        journal_entry_id=journal_id,
        entry_type=domain.AccountingEntryType.CAPITAL_DEPOSITED,
        account_id=account_id,
        venue_id=venue,
        effective_time=window.data_start,
        recorded_at=domain.SimulationInstant(
            window.data_start,
            domain.TimelinePhase(90, "accounting"),
            domain.SourceSequence(0),
        ),
        source_ids=("g12m-tushare-fixed-singleton:initial-capital",),
        balance_changes=(domain.BalanceChange(cash_key, _INITIAL_CASH),),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    journal = trading.AccountingJournal.from_entries((entry,))
    ledger = trading.GenericLedger(schema).project(journal)
    zero = domain.Money(0, _SCALE, "CNY")
    graph = trading.CurrencyValuationGraph(
        decision_time,
        domain.PricePurpose.VALUATION,
        (),
    )
    snapshot = domain.PortfolioSnapshot(
        account_id=account_id,
        timestamp=decision_time,
        reporting_currency=_CNY,
        cash=ledger.cash_balances,
        positions=ledger.position_balances,
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=_INITIAL_CASH,
        valuation_marks=(),
        journal_state_hash=ledger.state_hash,
        valuation_mark_set_hash=domain.canonical_sha256(()),
        valuation_staleness_report_hash=domain.canonical_sha256(()),
        currency_valuation_graph_hash=graph.graph_hash,
    )
    rules = trading.MarketSettlementRules.create(
        policy_key="g12m-tushare-fixed-singleton.cash-only.v2",
        policy_version=1,
        account_id=account_id,
        cash_rules=(
            trading.CashAvailabilityRule(
                cash_key,
                False,
                False,
                False,
                (
                    trading.CashReservationUse.CASH,
                    trading.CashReservationUse.FEE_RESERVE,
                ),
                (
                    trading.CashReservationUse.CASH,
                    trading.CashReservationUse.FEE_RESERVE,
                ),
                (trading.CashReservationUse.MARGIN,),
            ),
        ),
        position_rules=(),
    )
    return ResolvedFinancialState(
        journal=journal,
        ledger_schema=schema,
        initial_snapshot=snapshot,
        lot_books=(),
        order_streams=(),
        order_admissions=(),
        reservation_schedules=(),
        settlement_book=trading.SettlementBook(account_id),
        settlement_rules=rules,
    )


def _decision_cycle(
    *,
    target_stream: PrecomputedTargetStream,
    sizing_event: MarketEvent,
    authority: object,
    snapshot: domain.PortfolioSnapshot,
    window: TimelineWindow,
) -> tuple[ResolvedDecisionCycle, trading.InstrumentSizingInput]:
    event = target_stream.events[0]
    instrument = authority.case.instrument_id  # type: ignore[attr-defined]
    strategy_id = "cn-a-share-fixed-singleton-zero-target-v1"
    sleeve_id = domain.StrategySleeveId("cn-a-share-fixed-singleton.primary")
    expectation = trading.DecisionBatchExpectation(strategy_id, sleeve_id)
    schedule = TargetStreamDecisionSchedule(
        event.event_time,
        TimelineSegment.ACTIVE_TRADING,
        (
            TargetStreamScheduleEntry(
                event.event_id,
                expectation,
                trading.StrategyOutputValidationContext(
                    strategy_id,
                    sleeve_id,
                    event.event_time,
                    _catalog(instrument),
                    (instrument,),
                ),
            ),
        ),
    )
    allocation = trading.StrategyAllocation(
        strategy_id=strategy_id,
        sleeve_id=sleeve_id,
        valuation_time=event.event_time,
        valuation_currency=_CNY,
        allocation_nav=domain.Money(0, _SCALE, "CNY"),
        policy_ref=trading.CapitalAllocationPolicyRef(
            "g12m-tushare-fixed-singleton.zero-allocation.v2",
            1,
            domain.canonical_sha256({"allocation": "zero"}),
        ),
        source_portfolio_snapshot_hash=domain.canonical_sha256(snapshot),
    )
    maximum = _INITIAL_CASH
    risk = trading.PortfolioRiskPolicy.create(
        policy_key="g12m-tushare-fixed-singleton.zero-target-risk.v2",
        policy_version=1,
        valuation_currency=_CNY,
        notional_scale=_SCALE,
        limits=(
            trading.PortfolioRiskLimit(
                "target.zero-target.v2",
                trading.PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
                maximum,
                trading.PortfolioRiskAction.REJECT,
                instrument,
            ),
            trading.PortfolioRiskLimit(
                "gross.zero-target.v2",
                trading.PortfolioRiskScope.GROSS_EXPOSURE,
                maximum,
                trading.PortfolioRiskAction.REJECT,
                None,
            ),
            trading.PortfolioRiskLimit(
                "net.zero-target.v2",
                trading.PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
                maximum,
                trading.PortfolioRiskAction.REJECT,
                None,
            ),
        ),
    )
    sizing = trading.PositionSizingPolicy.create(
        policy_key="g12m-tushare-fixed-singleton.zero-sizing.v2",
        policy_version=1,
        price_purpose=domain.PricePurpose.EXECUTION_REFERENCE,
        rounding=domain.RoundingPolicy.TOWARD_ZERO,
        residual_policy=trading.ResidualPositionPolicy.FAIL,
    )
    observation = BarOpenObservation.from_event(sizing_event)
    if (
        sizing_event.stream_key != _PROJECTION_STREAM_KEY
        or sizing_event.instrument_id != instrument
        or observation.open_price is None
        or sizing_event.available_time >= event.available_time
    ):
        raise ValueError("sizing input must use the exact retained causal bar_open")
    stale_policy = trading.StaleMarkPolicy(
        "g12m-tushare-fixed-singleton.execution-reference.v2",
        1,
        domain.PricePurpose.EXECUTION_REFERENCE,
        event.event_time.epoch_nanoseconds - sizing_event.event_time.epoch_nanoseconds,
        False,
    )
    sizing_mark = trading.ResolvedMark(
        instrument_id=instrument,
        quote_currency_id=_CNY,
        price_purpose=domain.PricePurpose.EXECUTION_REFERENCE,
        price=observation.open_price,
        observed_at=sizing_event.event_time,
        available_at=sizing_event.available_time,
        resolved_at=event.event_time,
        age_nanoseconds=(
            event.event_time.epoch_nanoseconds
            - sizing_event.event_time.epoch_nanoseconds
        ),
        stream_id=sizing_event.stream_key,
        source_event_id=sizing_event.event_id,
        revision_id=sizing_event.revision_id,
        stale_policy_key=stale_policy.policy_key,
        stale_policy_version=stale_policy.policy_version,
        stale_policy_hash=stale_policy.policy_hash,
    )
    sizing_input = trading.InstrumentSizingInput(
        instrument,
        sizing_mark,
        domain.Quantity(0, domain.Scale(0), str(instrument)),
        trading.QuantityLattice.create(
            instrument_id=instrument,
            lattice_key="equity.cn-a-share.fixed-singleton.shares.v2",
            lattice_version=1,
            atomic_scale=domain.Scale(0),
            step_units=1,
            buy_lot_units=100,
            sell_lot_units=1,
            min_quantity_units=0,
            min_notional=domain.Money(0, _SCALE, "CNY"),
            odd_lot_close_permitted=True,
        ),
    )
    injection = PrecomputedTargetStreamAdapter().inject(
        stream=target_stream,
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, event),),
        schedule=schedule,
    )
    if injection.injection is None:
        raise ValueError("validated target stream did not inject")
    allocated = trading.PortfolioAllocator().allocate(
        sleeve_state=injection.injection.state,
        portfolio_snapshot=snapshot,
        allocations=(allocation,),
        target_notional_scale=_SCALE,
    )
    if allocated.allocation is None:
        raise ValueError("zero target did not allocate")
    approved = trading.PortfolioRiskEvaluator().evaluate(
        allocation=allocated.allocation,
        policy=risk,
    )
    if approved.approved_target is None:
        raise ValueError("zero target did not pass risk")
    normalized = trading.PositionSizer().materialize(
        approved_target=approved.approved_target,
        source_decision_batch_id=injection.injection.batch.decision_batch_id,
        policy=sizing,
        inputs=(sizing_input,),
    )
    if normalized.normalized_target is None:
        code = getattr(getattr(normalized, "failure", None), "code", "unknown")
        raise ValueError(f"zero target did not normalize: {code}")
    validity = trading.TargetValidity(
        normalized.normalized_target.normalized_target_id,
        normalized.normalized_target.normalized_target_hash,
        event.event_time,
        window.end_exclusive,
    )
    rebalance = trading.RebalancePolicy.create(
        policy_key="g12m-tushare-fixed-singleton.no-trade.v2",
        policy_version=1,
        execution_style=domain.ExecutionStyle.MARKET,
        time_in_force=domain.TimeInForce.DAY,
        urgency="normal",
        plan_valid_for_nanoseconds=1,
    )
    return ResolvedDecisionCycle(
        schedule=schedule,
        allocations=(allocation,),
        target_notional_scale=_SCALE,
        risk_policy=risk,
        sizing_policy=sizing,
        sizing_inputs=(sizing_input,),
        target_validity=validity,
        rebalance_policy=rebalance,
        planning_at=event.event_time,
        admissions=(),
    ), sizing_input


def _snapshot_plan(
    window: TimelineWindow,
    *,
    account_id: str,
    venue: domain.VenueId,
) -> SnapshotProjectionPlan:
    graph = trading.CurrencyValuationGraph(
        window.end_exclusive,
        domain.PricePurpose.VALUATION,
        (),
    )
    resolution = graph.resolve(_CNY, _CNY).resolution
    if resolution is None:
        raise ValueError("CNY self-valuation did not resolve")
    cash_key = domain.CashBalanceKey(account_id, venue, _CNY)
    valuation = trading.ReportingCurrencyValuation(
        trading.PortfolioValueRef(trading.PortfolioValueKind.CASH, cash_key),
        _INITIAL_CASH,
        _INITIAL_CASH,
        resolution,
        graph.graph_hash,
    )
    return SnapshotProjectionPlan(
        (),
        (valuation,),
        _CNY,
        _SCALE,
        window.end_exclusive,
        graph.graph_hash,
    )


def _plan(
    *,
    authority: object,
    cycle: ResolvedDecisionCycle,
    financial_state: ResolvedFinancialState,
    snapshot_plan: SnapshotProjectionPlan,
) -> _ExecutionCasePlan:
    return _ExecutionCasePlan(
        decision_cycles=(cycle,),
        bar_executions=(),
        financial_state=financial_state,
        financial_dispatch_plan=FinancialDispatchPlan(
            authority.financial_dispatcher_spec,  # type: ignore[attr-defined]
            (),
            snapshot_plan,
            ("final_snapshot",),
        ),
        execution_model=authority.execution_model,  # type: ignore[attr-defined]
        snapshot_plan=snapshot_plan,
        closeout_policy=authority.closeout_policy,  # type: ignore[attr-defined]
    )


def _base_spec(
    *,
    authority_hash: str,
    timeline: DeterministicTimeline,
    target_stream: PrecomputedTargetStream,
) -> ExecutionCaseSemanticSpec:
    return ExecutionCaseSemanticSpec(
        schema_version=1,
        spec_key="g12m.tushare.fixed-singleton.execution-case.v2",
        spec_version=2,
        case_key="g12m.tushare.fixed-singleton.no-trade.v2",
        case_version=2,
        identity_namespace=domain.IdentityNamespace("backtest", "1"),
        identity_plan=_IDENTITY_PLAN,
        timeline_semantic_hash=ExecutionCaseComposer.timeline_semantic_hash(timeline),
        target_stream_digest=target_stream.target_stream_digest,
        decision_inputs_hash=authority_hash,
        execution_inputs_hash=authority_hash,
        financial_inputs_hash=authority_hash,
        snapshot_inputs_hash=authority_hash,
        run_end_inputs_hash=authority_hash,
    )


def _route_body(values: dict[str, object]) -> dict[str, object]:
    completed = values["completed"]
    rich = values["completed_evidence"]
    analysis = values["analysis"]
    if type(completed) is not VerifiedCompletedPublicationV3:
        raise TypeError("completed must be exact VerifiedCompletedPublicationV3")
    if type(rich) is not _VerifiedCompletedEvidenceV3:
        raise TypeError("completed_evidence must be exact _VerifiedCompletedEvidenceV3")
    if type(analysis) is not VerifiedBacktestAnalysisV2:
        raise TypeError("analysis must be exact VerifiedBacktestAnalysisV2")
    return {
        "type": "g12m_tushare_fixed_singleton_route_result_v2",
        "schema_version": _SCHEMA_VERSION,
        "authority_hash": values["authority_hash"],
        "build_manifest_hash": values["build_manifest_hash"],
        "profile_digests": values["profile_digests"],
        "market_bundle_ref": values["market_bundle_ref"],
        "market_bundle_manifest": values["market_bundle_manifest"],
        "target_stream": values["target_stream"],
        "market_data_preparation": values["market_data_preparation"],
        "execution_sizing_input": values["execution_sizing_input"],
        "execution_input_envelope": values["execution_input_envelope"],
        "execution_request": values["execution_request"],
        "execution_input_source_hash": values["execution_input_source_hash"],
        "publication_ref": values["publication_ref"],
        "completed": {
            "semantic_run_id": completed.semantic_run_id,
            "execution_result_hash": completed.source_execution_result_hash,
            "result_grade": completed.result_grade.value,
            "rebuild_verification_ref": completed.rebuild_verification_ref,
            "proof_publication_manifest_ref": completed.proof_publication_manifest_ref,
        },
        "verified_evidence": {
            "static_verification_hash": rich.static_verification_hash,
            "execution_case_semantic_hash": rich.execution_case_semantic_hash,
            "execution_case_hash": rich.execution_case_hash,
            "trace_hash": rich.trace_hash,
        },
        "metric_profile_ref": values["metric_profile_ref"],
        "analysis_ref": values["analysis_ref"],
        "analysis": analysis,
        "nonclaims": values["nonclaims"],
        "live_eligible": False,
        "deployment_authorized": False,
    }


@dataclass(frozen=True, slots=True)
class _G12MTushareFixedSingletonRouteResultV2:
    authority_hash: str
    build_manifest_hash: str
    profile_digests: tuple[str, str, str]
    market_bundle_ref: MarketBundleRef
    market_bundle_manifest: MarketBundleManifest
    source_events: tuple[MarketEvent, ...]
    projection_events: tuple[MarketEvent, ...]
    target_stream: PrecomputedTargetStream
    market_data_preparation: MultiResolutionMarketDataPreparation
    execution_sizing_input: trading.InstrumentSizingInput
    execution_input_envelope: domain.ArtifactEnvelope
    execution_request: BacktestExecutionRequest
    execution_input_source_hash: str
    publication_ref: BacktestCanonicalPublicationRefV2
    completed: VerifiedCompletedPublicationV3
    completed_evidence: _VerifiedCompletedEvidenceV3
    metric_profile_ref: domain.ArtifactRef
    analysis_ref: AnalysisArtifactRefV2
    analysis: VerifiedBacktestAnalysisV2
    nonclaims: tuple[str, ...]
    route_hash: str

    def __post_init__(self) -> None:
        if type(self) is not _G12MTushareFixedSingletonRouteResultV2:
            raise TypeError("result must be exact G12M route result v2")
        authority = create_cn_a_share_fixed_singleton_no_trade_authority_v2()
        expected_profiles = (
            authority.market_registration.profile_digest,
            authority.simulation_registration.profile_digest,
            authority.execution_account_registration.profile_digest,
        )
        if (
            self.authority_hash != authority.authority_hash
            or self.build_manifest_hash != authority.build_manifest.manifest_hash
            or self.profile_digests != expected_profiles
            or self.market_bundle_ref
            != MarketBundleRef(_BUNDLE_KEY, _BUNDLE_MANIFEST_HASH)
            or MarketBundleRef.from_manifest(self.market_bundle_manifest)
            != self.market_bundle_ref
            or self.market_bundle_manifest.content_hash != _BUNDLE_CONTENT_HASH
            or self.nonclaims != _NONCLAIMS
        ):
            raise ValueError("route authority or Bundle identity mismatch")
        authority.validate_target_stream(self.target_stream)
        if (
            len(self.source_events) != 19
            or len(self.projection_events) != 19
            or any(type(value) is not MarketEvent for value in (*self.source_events, *self.projection_events))
            or any(value.stream_key != _SOURCE_STREAM_KEY for value in self.source_events)
            or any(value.stream_key != _PROJECTION_STREAM_KEY for value in self.projection_events)
            or any(
                value.timeline_instant >= self.target_stream.events[0].timeline_instant
                for value in (*self.source_events, *self.projection_events)
            )
        ):
            raise ValueError("route source/projection membership mismatch")
        preparation = self.market_data_preparation
        if (
            preparation.bindings.signal_bindings
            or preparation.bindings.valuation_bindings
            or preparation.signal_lineages
            or preparation.bindings.execution_bindings
            != (
                ExecutionDataBinding(
                    authority.execution_model.component_ref.component_key,
                    _PROJECTION_STREAM_KEY,
                ),
            )
            or len(preparation.decision_schedule.entries) != 1
            or preparation.decision_schedule.requirements
        ):
            raise ValueError("route PREP identity mismatch")
        sizing = self.execution_sizing_input
        selected_projection = self.projection_events[-1]
        selected_observation = BarOpenObservation.from_event(selected_projection)
        if (
            type(sizing) is not trading.InstrumentSizingInput
            or sizing.instrument_id != authority.case.instrument_id
            or sizing.mark.price_purpose is not domain.PricePurpose.EXECUTION_REFERENCE
            or sizing.mark.stream_id != _PROJECTION_STREAM_KEY
            or sizing.mark.source_event_id != selected_projection.event_id
            or sizing.mark.revision_id != selected_projection.revision_id
            or sizing.mark.observed_at != selected_projection.event_time
            or sizing.mark.available_at != selected_projection.available_time
            or sizing.mark.price != selected_observation.open_price
            or sizing.mark.stale_policy_key
            != "g12m-tushare-fixed-singleton.execution-reference.v2"
            or sizing.current_quantity.units != 0
        ):
            raise ValueError("route execution-reference sizing input mismatch")
        request = self.execution_request
        envelope = self.execution_input_envelope
        if (
            type(envelope) is not domain.ArtifactEnvelope
            or envelope.artifact_type != "backtest_execution_input_bundle"
            or envelope.schema_version != 4
            or type(request) is not BacktestExecutionRequest
            or request.schema_version != 4
            or request.execution_input_bundle_ref
            != domain.ArtifactRef.from_envelope(envelope)
            or self.execution_input_source_hash != domain.canonical_sha256(envelope)
            or request.request.market_bundle_ref != self.market_bundle_ref
            or request.request.target_stream_digest != self.target_stream.target_stream_digest
            or request.request.build_artifact_manifest_hash != self.build_manifest_hash
        ):
            raise ValueError("route execution request mismatch")
        if (
            type(self.publication_ref) is not BacktestCanonicalPublicationRefV2
            or type(self.completed) is not VerifiedCompletedPublicationV3
            or type(self.completed_evidence) is not _VerifiedCompletedEvidenceV3
            or self.completed != self.completed_evidence.completed
            or self.completed.source_publication_ref != self.publication_ref
            or self.completed_evidence.resolved_request.request != request.request
            or self.completed_evidence.market_bundle_ref != self.market_bundle_ref
            or self.completed_evidence.accepted_market_bundle_manifest_hash
            != self.market_bundle_ref.manifest_hash
            or self.completed.result_grade is not self.completed_evidence.integrity.result_grade
        ):
            raise ValueError("route completed evidence mismatch")
        engine = self.completed_evidence.first_engine_result
        timeline_entries = tuple(
            value for value in engine.trace.entries if value.stage is EngineStage.TIMELINE_EVENT
        )
        expected_events = tuple(
            sorted(
                (*self.source_events, *self.projection_events, *self.target_stream.events),
                key=lambda value: (value.ordering_key, value.event_id),
            )
        )
        if (
            len(timeline_entries) != 39
            or tuple((value.subject_id, value.evidence_hash) for value in timeline_entries)
            != tuple((value.event_id, value.event_hash) for value in expected_events)
            or len(engine.decision_batches) != 1
            or len(engine.allocations) != 1
            or len(engine.approved_targets) != 1
            or len(engine.normalized_targets) != 1
            or len(engine.order_plans) != 1
            or engine.order_plans[0].planned_orders
            or engine.order_plans[0].cancel_intents
            or engine.order_streams
            or engine.fills
            or engine.slippage_decisions
            or engine.fee_assessments
            or len(engine.final_journal.entries) != 1
            or engine.final_journal
            != self.completed.engine_context.financial_state.journal
            or self.completed.engine_context.financial_state.lot_books
            or self.completed.engine_context.financial_state.order_admissions
            or self.completed.engine_context.financial_state.reservation_schedules
            or self.completed.engine_context.financial_state.settlement_book.obligations
            or self.completed.engine_context.financial_state.settlement_book.events
        ):
            raise ValueError("route no-trade execution evidence mismatch")
        starting = self.completed.starting_snapshot
        ending = engine.final_portfolio_snapshot
        if (
            starting.cash != ending.cash
            or starting.positions != ending.positions
            or starting.realized_pnl != ending.realized_pnl
            or starting.unrealized_pnl != ending.unrealized_pnl
            or starting.fees != ending.fees
            or starting.financing != ending.financing
            or starting.equity != ending.equity
            or ending.valuation_marks
        ):
            raise ValueError("route final economic state mismatch")
        if (
            type(self.metric_profile_ref) is not domain.ArtifactRef
            or type(self.analysis_ref) is not AnalysisArtifactRefV2
            or type(self.analysis) is not VerifiedBacktestAnalysisV2
            or self.analysis.analysis_ref != self.analysis_ref
            or self.analysis.metric_profile_ref != self.metric_profile_ref
            or self.analysis.source_publication_ref != self.publication_ref
            or self.analysis.source_execution_result_hash
            != self.completed.source_execution_result_hash
            or self.analysis.trade_count != 0
            or self.analysis.simple_period_return != "0"
            or self.analysis.result_grade is not self.completed.result_grade
        ):
            raise ValueError("route analysis-v2 link mismatch")
        values = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "route_hash"}
        if self.route_hash != domain.canonical_sha256(_route_body(values)):
            raise ValueError("route_hash does not bind route result")

    def to_canonical_dict(self) -> dict[str, object]:
        values = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "route_hash"}
        return {**_route_body(values), "route_hash": self.route_hash}


def run_g12m_tushare_fixed_singleton_route_v2(
    *,
    market_reader: MarketBundleReader,
    artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher,
    publication_root: Path,
) -> _G12MTushareFixedSingletonRouteResultV2:
    if not isinstance(publication_root, Path):
        raise TypeError("publication_root must be pathlib.Path")
    authority = create_cn_a_share_fixed_singleton_no_trade_authority_v2()
    registry = _registry(authority)
    bundle_ref, manifest, sources, projections, target_events = _retained_events(
        market_reader
    )
    target_stream = PrecomputedTargetStream(_TARGET_STREAM_KEY, target_events)
    authority.validate_target_stream(target_stream)

    decision = authority.case.decision_time
    window = TimelineWindow(
        manifest.coverage_start,
        decision,
        domain.UtcInstant(decision.epoch_nanoseconds + 1),
    )
    provisional_id = domain.DomainId(domain.DomainIdKind.JOURNAL, "jnl_" + "0" * 64)
    provisional_financial = _initial_financial_state(
        account_id=authority.execution_account_registration.account_id,
        venue=authority.case.instrument_id.venue,
        decision_time=decision,
        window=window,
        journal_id=provisional_id,
    )
    provisional_cycle, _ = _decision_cycle(
        target_stream=target_stream,
        sizing_event=projections[-1],
        authority=authority,
        snapshot=provisional_financial.initial_snapshot,
        window=window,
    )
    snapshot_plan = _snapshot_plan(
        window,
        account_id=authority.execution_account_registration.account_id,
        venue=authority.case.instrument_id.venue,
    )
    provisional_plan = _plan(
        authority=authority,
        cycle=provisional_cycle,
        financial_state=provisional_financial,
        snapshot_plan=snapshot_plan,
    )
    provisional_request = _request(
        authority=authority,
        bundle_ref=bundle_ref,
        window=window,
        semantic_hash=authority.authority_hash,
    )
    provisional_resolved = _resolved(
        request=provisional_request,
        registry=registry,
        manifest=manifest,
        build_manifest=authority.build_manifest,
    )
    schedule = DecisionSchedule(
        "g12m-tushare-fixed-singleton.v2",
        1,
        window,
        (
            DecisionScheduleEntry(
                target_events[0].timeline_instant,
                TimelineSegment.ACTIVE_TRADING,
            ),
        ),
        (),
    )
    prepared = prepare_multi_resolution_market_data_v1(
        expected_bundle_ref=bundle_ref,
        reader=market_reader,
        schedule=schedule,
        signal_binding_candidates=(),
        execution_binding_candidates=(
            ExecutionDataBinding(
                authority.execution_model.component_ref.component_key,
                _PROJECTION_STREAM_KEY,
            ),
        ),
        valuation_binding_candidates=(),
        signal_lineages=(),
        case_authority=MarketDataCaseAuthority(
            (provisional_cycle,),
            (),
            authority.execution_model,
            snapshot_plan,
            target_stream,
        ),
        resolved_request=provisional_resolved,
    )
    if prepared.failure is not None or prepared.prepared is None:
        raise ValueError("exact V2-02 Bundle did not pass PREP")
    preparation = prepared.prepared.preparation
    timeline = DeterministicTimeline.open(
        reader=market_reader,
        stream_keys=_STREAM_KEYS,
        window=window,
    )
    if type(timeline) is not DeterministicTimeline:
        raise ValueError("exact V2-02 Bundle did not open deterministic Timeline")
    spec = _execution_case_semantic_spec_v3(
        base_spec=_base_spec(
            authority_hash=authority.authority_hash,
            timeline=timeline,
            target_stream=target_stream,
        ),
        execution_case_plan=provisional_plan,
        market_data_preparation=preparation,
    )
    final_request = _request(
        authority=authority,
        bundle_ref=bundle_ref,
        window=window,
        semantic_hash=spec.semantic_spec_hash,
    )
    resolved = _resolved(
        request=final_request,
        registry=registry,
        manifest=manifest,
        build_manifest=authority.build_manifest,
    )
    journal_id = ExecutionCaseIdentityFactory(
        semantic_run_id=resolved.semantic_run_id,
        namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    ).domain_id("journal.initial.0")
    actual_financial = _initial_financial_state(
        account_id=authority.execution_account_registration.account_id,
        venue=authority.case.instrument_id.venue,
        decision_time=decision,
        window=window,
        journal_id=journal_id,
    )
    actual_cycle, sizing_input = _decision_cycle(
        target_stream=target_stream,
        sizing_event=projections[-1],
        authority=authority,
        snapshot=actual_financial.initial_snapshot,
        window=window,
    )
    actual_plan = _plan(
        authority=authority,
        cycle=actual_cycle,
        financial_state=actual_financial,
        snapshot_plan=snapshot_plan,
    )
    recomputed_spec = _execution_case_semantic_spec_v3(
        base_spec=spec,
        execution_case_plan=actual_plan,
        market_data_preparation=preparation,
    )
    if recomputed_spec != spec or domain.canonical_bytes(recomputed_spec) != domain.canonical_bytes(spec):
        raise ValueError("derived journal identity changed execution semantics")
    hydrated = _HydratedExecutionCaseInputs(
        spec,
        _STREAM_KEYS,
        target_stream,
        16,
        actual_plan,
    )
    envelope = _materialize_execution_input_bundle_v4(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=preparation,
    )
    expected_ref = domain.ArtifactRef.from_envelope(envelope)
    stored_ref = artifact_publisher.put(envelope=envelope)
    if type(stored_ref) is not domain.ArtifactRef or stored_ref != expected_ref:
        raise ValueError("publisher did not retain exact schema-4 execution input")
    readback = artifact_reader.read(ref=stored_ref)
    source_bytes = domain.canonical_bytes(envelope)
    source_hash = domain.canonical_sha256(envelope)
    if (
        type(readback) is not domain.ArtifactReadResult
        or readback.envelope != envelope
        or readback.source_bytes != source_bytes
        or readback.source_hash != source_hash
        or domain.ArtifactRef.from_envelope(readback.envelope) != stored_ref
    ):
        raise ValueError("schema-4 execution input read-back mismatch")
    execution_request = BacktestExecutionRequest(4, resolved.request, stored_ref)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=artifact_reader,
        artifact_publisher=artifact_publisher,
        market_reader=market_reader,
        publication_root=publication_root,
    )
    publication_ref = runtime.run(execution_request)
    if type(publication_ref) is not BacktestCanonicalPublicationRefV2:
        raise ValueError("sole facade did not return canonical-v3 publication ref V2")
    repository = BacktestEvidenceRepository(artifact_reader)
    completed = repository.load_completed_v3(publication_ref)
    completed_evidence = repository.load_completed_evidence_v3(publication_ref)
    if completed != completed_evidence.completed:
        raise ValueError("lean and rich completed evidence disagree")
    analysis_runtime = BacktestAnalysisRuntime(artifact_publisher)
    metric_profile_ref = analysis_runtime.publish_metric_profile()
    analysis_ref = analysis_runtime.derive(completed, metric_profile_ref)
    if type(analysis_ref) is not AnalysisArtifactRefV2:
        raise ValueError("canonical-v3 route did not derive analysis v2")
    analysis = repository.load_analysis_v2(analysis_ref)
    values: dict[str, object] = {
        "authority_hash": authority.authority_hash,
        "build_manifest_hash": authority.build_manifest.manifest_hash,
        "profile_digests": (
            authority.market_registration.profile_digest,
            authority.simulation_registration.profile_digest,
            authority.execution_account_registration.profile_digest,
        ),
        "market_bundle_ref": bundle_ref,
        "market_bundle_manifest": manifest,
        "source_events": sources,
        "projection_events": projections,
        "target_stream": target_stream,
        "market_data_preparation": preparation,
        "execution_sizing_input": sizing_input,
        "execution_input_envelope": envelope,
        "execution_request": execution_request,
        "execution_input_source_hash": source_hash,
        "publication_ref": publication_ref,
        "completed": completed,
        "completed_evidence": completed_evidence,
        "metric_profile_ref": metric_profile_ref,
        "analysis_ref": analysis_ref,
        "analysis": analysis,
        "nonclaims": _NONCLAIMS,
    }
    return _G12MTushareFixedSingletonRouteResultV2(
        authority_hash=authority.authority_hash,
        build_manifest_hash=authority.build_manifest.manifest_hash,
        profile_digests=(
            authority.market_registration.profile_digest,
            authority.simulation_registration.profile_digest,
            authority.execution_account_registration.profile_digest,
        ),
        market_bundle_ref=bundle_ref,
        market_bundle_manifest=manifest,
        source_events=sources,
        projection_events=projections,
        target_stream=target_stream,
        market_data_preparation=preparation,
        execution_sizing_input=sizing_input,
        execution_input_envelope=envelope,
        execution_request=execution_request,
        execution_input_source_hash=source_hash,
        publication_ref=publication_ref,
        completed=completed,
        completed_evidence=completed_evidence,
        metric_profile_ref=metric_profile_ref,
        analysis_ref=analysis_ref,
        analysis=analysis,
        nonclaims=_NONCLAIMS,
        route_hash=domain.canonical_sha256(_route_body(values)),
    )
