from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path

import pytest
import crypto_quant_domain as domain
import crypto_quant_trading as trading
from crypto_quant_backtest import BacktestRuntime
from crypto_quant_backtest.analysis import AnalysisArtifactRef
from crypto_quant_backtest.analysis_derivation import BacktestAnalysisRuntime
from crypto_quant_backtest.cash_development_provider import (
    CashDevelopmentProviderInputs,
    CashDevelopmentRequestIntent,
    _CashCaseBuilder,
    _CaseInputs,
    _ProfileImplementation,
    _provider_build_manifest,
    _profile_ref,
    _simulation_ref,
)
from crypto_quant_backtest.cn_a_share_fixed_singleton_no_trade_profile_v2 import (
    create_cn_a_share_fixed_singleton_no_trade_authority_v2,
)
from crypto_quant_backtest.composition import (
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from crypto_quant_backtest.decision_schedule import (
    DecisionSchedule,
    DecisionScheduleEntry,
)
from crypto_quant_backtest.engine import (
    EngineCancellationRequest,
    EngineStage,
    ExecutionCaseIdentityFactory,
    ExecutionCaseSemanticSpec,
    ResolvedExecutionCase,
)
from crypto_quant_backtest.evidence_repository import BacktestEvidenceRepository
from crypto_quant_backtest.execution import BarOpenObservation
from crypto_quant_backtest.execution_inputs import (
    BacktestExecutionRequest,
    _materialize_execution_input_bundle_v5,
)
from crypto_quant_backtest.multi_resolution_market_data import (
    ExecutionDataBinding,
    ValuationDataBinding,
)
from crypto_quant_backtest.multi_resolution_preparation import (
    MarketDataCaseAuthority,
    _capture_market_bundle_reader_v1,
    prepare_multi_resolution_market_data_v1,
)
from crypto_quant_backtest.ports import SimulationPortType
from crypto_quant_backtest.publication_refs import BacktestCanonicalPublicationRef
from crypto_quant_backtest.resolution import (
    BacktestProfileRegistry,
    BacktestRequest,
    ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration,
    ProfileResolver,
    RequestedResultGrade,
    SimulationProfileRegistration,
    StrategyFamily,
)
from crypto_quant_backtest.target_stream import PrecomputedTargetStream
from crypto_quant_backtest.timeline import (
    DeterministicTimeline,
    TimelineSegment,
    TimelineWindow,
)
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    validate_market_bundle_v1,
)
from crypto_quant_market_data import (
    LocalMarketBundleReader,
    MarketBundleCapability,
    MarketEvent,
)

from tests.bundle_builder.providers.tushare.test_g12m_tushare_fixed_singleton_execution_bundle_v2 import (
    _result as _accepted_bundle_result,
)
from tests.runtime.test_durable_rebuild_facade import _Store

ROOT = Path(__file__).parents[3]
FIXTURE = (
    ROOT
    / "tests/fixtures/runtime/engine/"
    "g12m-tushare-market-engine-journey-v1.json"
)

_TARGET_STREAM = "todo140.tushare.market-engine.targets.v1"
_VALUATION_STREAM = "todo140.tushare.market-engine.valuation.v1"
_SOURCE_STREAM = "tushare_cn_a_share.daily.publication.xshe.000001.v1"
_EXECUTION_STREAM = "g12m.tushare.fixed-singleton.bar-open.v2"
_STREAM_KEYS = (
    _EXECUTION_STREAM,
    _TARGET_STREAM,
    _VALUATION_STREAM,
    _SOURCE_STREAM,
)
_PROFILE_PREFIX = "todo140.tushare.market-engine.development.v1"
_MARKET_KEY = f"{_PROFILE_PREFIX}.market"
_SIMULATION_KEY = f"{_PROFILE_PREFIX}.simulation"
_ACCOUNT_KEY = f"{_PROFILE_PREFIX}.account"
_LIMITATIONS = (
    "development_only",
    "fixed_singleton_source_bounded_market_journey",
    "zero_explicit_fee_economics",
    "bounded_forward_fill_valuation",
    "no_provider_or_deployment_qualification",
)
_CNY = domain.CurrencyId("CNY")
_SCALE = domain.Scale(2)
_INITIAL_CASH = domain.Money(10_000_000, _SCALE, "CNY")
_AGGREGATION_SPEC_HASH = (
    "sha256:324439214b2cb2fa64300c470a65e322de3c3dd7056381a73672db00677dbccb"
)


class _CountingStore(_Store):
    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def read(self, *, ref: domain.ArtifactRef) -> domain.ArtifactReadResult:
        self.reads += 1
        return super().read(ref=ref)


@dataclass(frozen=True, slots=True)
class _Journey:
    reader: LocalMarketBundleReader
    target_stream: PrecomputedTargetStream
    valuation_event: MarketEvent
    execution_case: ResolvedExecutionCase
    execution_request: BacktestExecutionRequest
    execution_input_source_hash: str
    publication_ref: BacktestCanonicalPublicationRef
    cached_publication_ref: BacktestCanonicalPublicationRef
    completed: object
    engine_result: object
    analysis_ref: AnalysisArtifactRef
    analysis: object


def _install_exact_test_artifact_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    original = BacktestRuntime._finalize_v3_attempt_locked

    def finalize(self, writer, record, claim):
        finalized = original(self, writer, record, claim)
        ready = record.ready_to_finalize
        if ready is not None:
            store = self._artifact_publisher
            for artifact_type, artifact in (
                ("evidence_manifest", finalized.manifest),
                ("backtest_request", ready.resolved_request.request),
                ("resolved_backtest_environment", ready.resolved_request.environment),
                ("build_artifact_manifest", ready.resolved_request.build_artifact_manifest),
                ("market_bundle_ref", ready.resolved_request.environment.market_bundle_ref),
                (
                    "environment_compatibility_report",
                    ready.resolved_request.environment.compatibility_report,
                ),
                ("attempt_execution_record", record),
                ("engine_execution_result", ready.engine_result),
            ):
                store.put_exact(artifact_type, artifact)
        return finalized

    monkeypatch.setattr(BacktestRuntime, "_finalize_v3_attempt_locked", finalize)


def _valuation_event(source: MarketEvent, available_at: domain.UtcInstant) -> MarketEvent:
    execution = source.payload["execution_reference"]
    bucket = execution["bucket"]
    source_hashes = (source.event_hash,)
    definition_body = {
        "type": "todo140_tushare_valuation_bar_definition",
        "schema_version": 1,
        "instrument_id": source.instrument_id,
        "price_purpose": domain.PricePurpose.VALUATION.value,
    }
    input_body = {
        "type": "todo140_tushare_valuation_projection",
        "schema_version": 1,
        "source_event_id": source.event_id,
        "source_event_hash": source.event_hash,
        "source_available_time": source.available_time,
        "projected_available_time": available_at,
    }
    aggregation_input_hash = domain.canonical_sha256(input_body)
    event_preimage = {
        **input_body,
        "aggregation_input_hash": aggregation_input_hash,
        "close_price": execution["close_price"],
    }
    event_identity = domain.canonical_sha256(event_preimage)

    def price(name: str) -> dict[str, int]:
        value = execution[name]
        return {"units": value["units"], "scale": value["scale"]}

    return MarketEvent(
        event_id=f"todo140-tushare-valuation-v1:{event_identity}",
        stream_key=_VALUATION_STREAM,
        event_type="bar",
        capability=MarketBundleCapability("price_bars", 1),
        instrument_id=source.instrument_id,
        event_time=domain.UtcInstant(bucket["interval_start"]["epoch_nanoseconds"]),
        available_time=available_at,
        phase=domain.TimelinePhase(20, "valuation_bar"),
        source_sequence=domain.SourceSequence(0),
        revision_id=f"todo140-tushare-valuation-revision-v1:{event_identity}",
        supersedes_revision_id=None,
        source_key="canonical-bar-aggregation-v1",
        source_hash=aggregation_input_hash,
        payload={
            "schema_version": 1,
            "bar_definition_key": "todo140.tushare.daily-valuation.v1",
            "bar_definition_version": 1,
            "bar_definition_hash": domain.canonical_sha256(definition_body),
            "source_stream_hash": domain.canonical_sha256(
                {
                    "stream_key": source.stream_key,
                    "source_event_hashes": source_hashes,
                }
            ),
            "bucket_plan_hash": domain.canonical_sha256(
                {"type": "todo140_single_bucket_plan", "bucket": bucket}
            ),
            "aggregation_spec_hash": _AGGREGATION_SPEC_HASH,
            "aggregation_code_hash": domain.canonical_sha256(
                {"type": "todo140_exact_source_projection", "version": 1}
            ),
            "aggregation_input_hash": aggregation_input_hash,
            "bucket_hash": bucket["bucket_hash"],
            "session_id": bucket["session_id"],
            "trading_date": bucket["trading_date"],
            "included_spans": bucket["included_spans"],
            "interval_start": bucket["interval_start"],
            "interval_end_exclusive": bucket["interval_end_exclusive"],
            "price_purpose": domain.PricePurpose.VALUATION.value,
            "price_scale": execution["close_price"]["scale"],
            "open": price("open_price"),
            "high": price("high_price"),
            "low": price("low_price"),
            "close": price("close_price"),
            "volume": None,
            "observation_count": 1,
            "source_event_hashes": source_hashes,
            "selected_source_set_hash": domain.canonical_sha256(source_hashes),
        },
    )


def _target_event(
    *,
    instrument: domain.InstrumentId,
    observed_through: domain.UtcInstant,
    decision_time: domain.UtcInstant,
    expires_at: domain.UtcInstant,
    source: MarketEvent,
) -> MarketEvent:
    evidence = {
        "accepted_source_event_id": source.event_id,
        "accepted_source_event_hash": source.event_hash,
        "accepted_source_available_time": source.available_time.epoch_nanoseconds,
        "provider_evidence_sets_profile_grade": False,
    }
    payload = {
        "schema_version": 1,
        "candidate": {
            "schema_version": 1,
            "strategy_id": "todo140-tushare-market-engine-v1",
            "sleeve_id": "todo140-tushare.primary",
            "decision_time": decision_time.epoch_nanoseconds,
            "observed_through": observed_through.epoch_nanoseconds,
            "effective_time": decision_time.epoch_nanoseconds,
            "expires_at": expires_at.epoch_nanoseconds,
            "targets": [
                {
                    "instrument_id": {
                        "venue": instrument.venue.value,
                        "stable_key": instrument.stable_key,
                    },
                    "value": "0.09024",
                }
            ],
            "confidence": "1",
            "reason": "Todo 140 deterministic market-backed engine journey",
            "evidence": evidence,
        },
    }
    identity = domain.canonical_sha256(
        {
            "type": "todo140_tushare_market_engine_target",
            "schema_version": 1,
            "decision_time": decision_time,
            "payload": payload,
        }
    )
    return MarketEvent(
        event_id=f"todo140-tushare-target-v1:{identity}",
        stream_key=_TARGET_STREAM,
        event_type="strategy_decision_candidate",
        capability=MarketBundleCapability("precomputed_target_stream", 1),
        instrument_id=None,
        event_time=decision_time,
        available_time=decision_time,
        phase=domain.TimelinePhase(30, "strategy_decision"),
        source_sequence=domain.SourceSequence(0),
        revision_id=f"todo140-tushare-target-revision-v1:{identity}",
        supersedes_revision_id=None,
        source_key="todo140.tushare.market-engine.targets.v1",
        source_hash=domain.canonical_sha256(payload),
        payload=payload,
    )


def _reader(tmp_path: Path) -> tuple[LocalMarketBundleReader, MarketEvent, MarketEvent]:
    accepted = _accepted_bundle_result()
    source = accepted.source_events[-2]
    execution = accepted.projection_events[-1]
    decision_time = domain.UtcInstant(source.available_time.epoch_nanoseconds + 1)
    assert decision_time < execution.available_time
    end_exclusive = domain.UtcInstant(execution.available_time.epoch_nanoseconds + 1)
    valuation = _valuation_event(source, decision_time)
    target = _target_event(
        instrument=accepted.instrument_catalog.instruments[0].instrument_id,
        observed_through=source.available_time,
        decision_time=decision_time,
        expires_at=end_exclusive,
        source=source,
    )
    events = (*accepted.source_events, *accepted.projection_events, valuation, target)
    validation = validate_market_bundle_v1(
        bundle_key="todo140-tushare-market-engine-journey-v1",
        schema_version=1,
        coverage_start=accepted.manifest.coverage_start,
        coverage_end_exclusive=end_exclusive,
        instrument_catalog_hash=accepted.instrument_catalog_hash,
        events=events,
    )
    assert validation.failure is None and validation.manifest is not None
    by_stream: dict[str, list[MarketEvent]] = {}
    for event in events:
        by_stream.setdefault(event.stream_key, []).append(event)
    payloads = {
        key: domain.canonical_bytes(
            tuple(sorted(values, key=lambda value: (value.ordering_key, value.event_id)))
        )
        for key, values in by_stream.items()
    }
    root = (tmp_path / "market").resolve()
    publication = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=validation.manifest,
        stream_payloads=payloads,
        retention_policy_ref="todo140.tushare.market-engine.journey.v1",
    )
    assert publication.failure is None and publication.result is not None
    reader = LocalMarketBundleReader.open(
        repository_root=root,
        bundle_ref=publication.result.bundle_ref,
    )
    assert domain.canonical_bytes(accepted.source_events) == payloads[_SOURCE_STREAM]
    assert domain.canonical_bytes(accepted.projection_events) == payloads[_EXECUTION_STREAM]
    return reader, target, valuation


def _order_capabilities() -> trading.OrderCapabilitySet:
    return trading.OrderCapabilitySet.create(
        capability_set_key="todo140.tushare.market-engine.capabilities.v1",
        capability_set_version=1,
        style_capabilities=(
            trading.OrderStyleCapability(
                domain.ExecutionStyle.MARKET,
                (trading.PriceConstraintShape.NONE,),
                (domain.TimeInForce.DAY,),
            ),
        ),
        supports_reduce_only=True,
        supported_position_effects=(
            domain.PositionEffect.AUTO,
            domain.PositionEffect.OPEN,
            domain.PositionEffect.CLOSE,
        ),
        declared_capability_keys=tuple(
            value.value for value in trading.OrderCapabilityKey
        ),
    )


def _resolved_mark(
    *,
    valuation: MarketEvent,
    price: domain.Price,
    observed_at: domain.UtcInstant,
    resolved_at: domain.UtcInstant,
    policy_key: str,
) -> trading.ResolvedMark:
    age = resolved_at.epoch_nanoseconds - observed_at.epoch_nanoseconds
    policy = trading.StaleMarkPolicy(
        policy_key,
        1,
        domain.PricePurpose.VALUATION,
        age,
        True,
    )
    return trading.ResolvedMark(
        instrument_id=valuation.instrument_id,
        quote_currency_id=_CNY,
        price_purpose=domain.PricePurpose.VALUATION,
        price=price,
        observed_at=observed_at,
        available_at=valuation.available_time,
        resolved_at=resolved_at,
        age_nanoseconds=age,
        stream_id=valuation.stream_key,
        source_event_id=valuation.event_id,
        revision_id=valuation.revision_id,
        stale_policy_key=policy.policy_key,
        stale_policy_version=policy.policy_version,
        stale_policy_hash=policy.policy_hash,
    )


def _case_values(
    reader: LocalMarketBundleReader,
    target: MarketEvent,
    valuation: MarketEvent,
) -> _CaseInputs:
    accepted_authority = create_cn_a_share_fixed_singleton_no_trade_authority_v2()
    instrument = accepted_authority.case.instrument_id
    definition = next(
        value
        for value in _accepted_bundle_result().instrument_catalog.instruments
        if value.instrument_id == instrument
    )
    execution = next(
        event
        for event in _accepted_bundle_result().projection_events
        if event.event_id
        == next(
            value.event_id
            for value in _accepted_bundle_result().projection_events
            if value.available_time > target.available_time
        )
    )
    observation = BarOpenObservation.from_event(execution)
    assert observation.open_price is not None
    observed_at = domain.UtcInstant(
        valuation.payload["interval_end_exclusive"]["epoch_nanoseconds"]
    )
    mark_price = domain.Price(
        valuation.payload["close"]["units"],
        domain.Scale(valuation.payload["close"]["scale"]),
        str(instrument),
        "CNY",
    )
    window = TimelineWindow(
        reader.manifest.coverage_start,
        target.event_time,
        reader.manifest.coverage_end_exclusive,
    )
    decision_mark = _resolved_mark(
        valuation=valuation,
        price=mark_price,
        observed_at=observed_at,
        resolved_at=target.event_time,
        policy_key="todo140.tushare.decision-valuation.v1",
    )
    final_mark = _resolved_mark(
        valuation=valuation,
        price=mark_price,
        observed_at=observed_at,
        resolved_at=window.end_exclusive,
        policy_key="todo140.tushare.final-valuation.v1",
    )
    mark_observation = trading.MarkObservation(
        instrument_id=instrument,
        quote_currency_id=_CNY,
        price_purpose=domain.PricePurpose.VALUATION,
        price=mark_price,
        observed_at=observed_at,
        available_at=valuation.available_time,
        stream_id=valuation.stream_key,
        source_event_id=valuation.event_id,
        revision_id=valuation.revision_id,
    )
    provider = CashDevelopmentProviderInputs(
        schema_version=1,
        build_artifact_manifest=accepted_authority.build_manifest,
        instrument_catalog=_accepted_bundle_result().instrument_catalog,
        strategy_id="todo140-tushare-market-engine-v1",
        sleeve_id=domain.StrategySleeveId("todo140-tushare.primary"),
        initial_cash=_INITIAL_CASH,
        quantity_lattice=trading.QuantityLattice.create(
            instrument_id=instrument,
            lattice_key="todo140.tushare.shares.v1",
            lattice_version=1,
            atomic_scale=domain.Scale(0),
            step_units=1,
            buy_lot_units=100,
            sell_lot_units=1,
            min_quantity_units=100,
            min_notional=domain.Money(100_000, _SCALE, "CNY"),
            odd_lot_close_permitted=True,
        ),
        decision_mark=mark_observation,
        final_mark=mark_observation,
        order_capabilities=_order_capabilities(),
    )
    intent = CashDevelopmentRequestIntent(
        schema_version=1,
        experiment_id="todo140:tushare-market-engine-journey-v1",
        timeline_window=window,
        execution_account_id=accepted_authority.execution_account_registration.account_id,
        reporting_currency=_CNY,
        master_random_seed=0,
    )
    timeline = DeterministicTimeline.open(
        reader=reader,
        stream_keys=_STREAM_KEYS,
        window=window,
    )
    assert type(timeline) is DeterministicTimeline
    return _CaseInputs(
        intent,
        provider,
        reader,
        definition,
        target,
        execution,
        observation.open_price,
        decision_mark,
        final_mark,
        timeline,
        PrecomputedTargetStream(_TARGET_STREAM, (target,)),
    )


def _registry(values: _CaseInputs, case: ResolvedExecutionCase) -> BacktestProfileRegistry:
    dispatcher = case.financial_dispatch_plan.dispatcher_spec
    actual_profile = {
        dispatcher.position_accounting_component.port_type: dispatcher.position_accounting_component,
        dispatcher.financing_component.port_type: dispatcher.financing_component,
        dispatcher.margin_component.port_type: dispatcher.margin_component,
    }
    market_components = tuple(
        sorted(
            (
                actual_profile.get(port)
                or _profile_ref(port, f"todo140.tushare.{port.value}.v1")
                for port in trading.ProfilePortType
            ),
            key=lambda value: value.port_type.value,
        )
    )
    actual_simulation = {
        case.execution_model.component_ref.port_type: case.execution_model.component_ref,
        case.closeout_policy.spec().component_ref.port_type: case.closeout_policy.spec().component_ref,
        case.bar_executions[0].slippage_model.component_ref.port_type: case.bar_executions[0].slippage_model.component_ref,
        dispatcher.liquidation_audit_component.port_type: dispatcher.liquidation_audit_component,
    }
    simulation_components = tuple(
        sorted(
            (
                actual_simulation.get(port)
                or _simulation_ref(port, f"todo140.tushare.{port.value}.v1")
                for port in SimulationPortType
            ),
            key=lambda value: value.port_type.value,
        )
    )
    market_impl = _ProfileImplementation("market", market_components)
    simulation_impl = _ProfileImplementation("simulation", simulation_components)
    account_impl = _ProfileImplementation("account", ())
    market = MarketSemanticsProfileRegistration(
        _MARKET_KEY,
        1,
        market_impl.profile_digest,
        market_impl,
        "xshe",
        (
            MarketBundleCapability("tushare_cn_a_share.daily-publications", 1),
            MarketBundleCapability("price_bars", 1),
        ),
        market_components,
        RequestedResultGrade.DEVELOPMENT,
        _LIMITATIONS,
        False,
    )
    simulation = SimulationProfileRegistration(
        _SIMULATION_KEY,
        1,
        simulation_impl.profile_digest,
        simulation_impl,
        "bar",
        (StrategyFamily.PRECOMPUTED_TARGET,),
        (
            MarketBundleCapability("bar_open", 1),
            MarketBundleCapability("precomputed_target_stream", 1),
        ),
        simulation_components,
        RequestedResultGrade.DEVELOPMENT,
        _LIMITATIONS,
        False,
    )
    account = ExecutionAccountProfileRegistration(
        _ACCOUNT_KEY,
        1,
        account_impl.profile_digest,
        account_impl,
        values.intent.execution_account_id,
        "xshe",
        "equity",
        "cash_only",
        (_CNY,),
        RequestedResultGrade.DEVELOPMENT,
        _LIMITATIONS,
        False,
    )
    return BacktestProfileRegistry((market,), (simulation,), (account,))


def _request(
    *,
    values: _CaseInputs,
    build_manifest,
    semantic_hash: str,
) -> BacktestRequest:
    return BacktestRequest(
        1,
        values.intent.experiment_id,
        values.intent.timeline_window,
        _MARKET_KEY,
        _SIMULATION_KEY,
        _ACCOUNT_KEY,
        values.intent.execution_account_id,
        _CNY,
        values.market_reader.bundle_ref,
        values.target_stream.target_stream_digest,
        semantic_hash,
        values.intent.master_random_seed,
        build_manifest.manifest_hash,
        StrategyFamily.PRECOMPUTED_TARGET,
        "bar",
        RequestedResultGrade.DEVELOPMENT,
    )


def _resolved(request, registry, reader, build_manifest):
    outcome = ProfileResolver().resolve(
        request=request,
        registry=registry,
        market_bundle_manifest=reader.manifest,
        build_artifact_manifest=build_manifest,
    )
    assert outcome.failure is None and outcome.resolved is not None
    return outcome.resolved


def _case_plan(case: ResolvedExecutionCase) -> _ExecutionCasePlan:
    return _ExecutionCasePlan(
        case.decision_cycles,
        case.bar_executions,
        case.financial_state,
        case.financial_dispatch_plan,
        case.execution_model,
        case.snapshot_plan,
        case.closeout_policy,
    )


def _build_case(
    builder: _CashCaseBuilder,
    spec: ExecutionCaseSemanticSpec,
    semantic_run_id: str,
) -> ResolvedExecutionCase:
    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=semantic_run_id,
        namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    case = builder.build(identities, spec.semantic_spec_hash)
    return replace(
        case,
        case_key="todo140.tushare.market-engine.journey.v1",
        case_version=1,
        identity_manifest=identities.manifest(),
        semantic_spec=spec,
    )


def _journey(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> _Journey:
    _install_exact_test_artifact_mirror(monkeypatch)
    reader, target, valuation = _reader(tmp_path)
    values = _case_values(reader, target, valuation)
    builder = _CashCaseBuilder(values)
    base_spec = replace(
        builder.semantic_spec(),
        spec_key="todo140.tushare.market-engine.execution-case.v1",
        spec_version=1,
    )
    provisional_case = builder.build(
        ExecutionCaseIdentityFactory(
            semantic_run_id="run_" + "0" * 64,
            namespace=base_spec.identity_namespace,
            identity_plan=base_spec.identity_plan,
        ),
        base_spec.semantic_spec_hash,
    )
    registry = _registry(values, provisional_case)
    build_manifest = replace(
        _provider_build_manifest(values.provider.build_artifact_manifest, registry),
        build_key="todo140.tushare.market-engine.build.v1",
    )
    provisional_request = _request(
        values=values,
        build_manifest=build_manifest,
        semantic_hash=base_spec.semantic_spec_hash,
    )
    provisional_resolved = _resolved(
        provisional_request,
        registry,
        reader,
        build_manifest,
    )
    provisional_case = _build_case(
        builder,
        base_spec,
        provisional_resolved.semantic_run_id,
    )
    schedule = DecisionSchedule(
        "todo140.tushare.market-engine.v1",
        1,
        values.intent.timeline_window,
        (DecisionScheduleEntry(target.timeline_instant, TimelineSegment.ACTIVE_TRADING),),
        (),
    )
    prepared = prepare_multi_resolution_market_data_v1(
        expected_bundle_ref=reader.bundle_ref,
        reader=reader,
        schedule=schedule,
        signal_binding_candidates=(),
        execution_binding_candidates=(
            ExecutionDataBinding(
                provisional_case.execution_model.component_ref.component_key,
                _EXECUTION_STREAM,
            ),
        ),
        valuation_binding_candidates=(
            ValuationDataBinding(values.instrument.instrument_id, _VALUATION_STREAM),
        ),
        signal_lineages=(),
        case_authority=MarketDataCaseAuthority(
            provisional_case.decision_cycles,
            provisional_case.bar_executions,
            provisional_case.execution_model,
            provisional_case.snapshot_plan,
            values.target_stream,
        ),
        resolved_request=provisional_resolved,
    )
    assert prepared.failure is None and prepared.prepared is not None
    preparation = prepared.prepared.preparation
    spec = _execution_case_semantic_spec_v3(
        base_spec=base_spec,
        execution_case_plan=_case_plan(provisional_case),
        market_data_preparation=preparation,
    )
    request = _request(
        values=values,
        build_manifest=build_manifest,
        semantic_hash=spec.semantic_spec_hash,
    )
    resolved = _resolved(request, registry, reader, build_manifest)
    case = _build_case(builder, spec, resolved.semantic_run_id)
    assert case.verify_identity_manifest(resolved.semantic_run_id)
    assert (
        _execution_case_semantic_spec_v3(
            base_spec=base_spec,
            execution_case_plan=_case_plan(case),
            market_data_preparation=preparation,
        )
        == spec
    )
    hydrated = _HydratedExecutionCaseInputs(
        spec,
        _STREAM_KEYS,
        values.target_stream,
        16,
        _case_plan(case),
    )
    envelope = _materialize_execution_input_bundle_v5(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=preparation,
    )
    store = _CountingStore()
    stored_ref = store.put_input(envelope)
    assert stored_ref == domain.ArtifactRef.from_envelope(envelope)
    execution_request = BacktestExecutionRequest(5, resolved.request, stored_ref)
    runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=reader,
        publication_root=tmp_path / "runs",
    )
    before_rejection = (tuple(store.values), store.puts, store.reads)
    with pytest.raises(RuntimeError, match="malformed_execution_request"):
        runtime.run_with_cancellation(
            execution_request,
            EngineCancellationRequest("todo140-cancel", "schema5-cancellation-forbidden"),
        )
    decision_grade_request = BacktestExecutionRequest(
        5,
        replace(
            resolved.request,
            result_grade_requested=RequestedResultGrade.DECISION_GRADE,
        ),
        stored_ref,
    )
    with pytest.raises(RuntimeError, match="malformed_execution_request"):
        runtime.run(decision_grade_request)
    retained = _capture_market_bundle_reader_v1(reader.bundle_ref, reader)
    assert retained is not None
    non_local_runtime = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=retained,
        publication_root=tmp_path / "non-local-runs",
    )
    with pytest.raises(RuntimeError, match="malformed_execution_request"):
        non_local_runtime.run(execution_request)
    assert (tuple(store.values), store.puts, store.reads) == before_rejection

    publication_ref = runtime.run(execution_request)
    assert type(publication_ref) is BacktestCanonicalPublicationRef
    cached_publication_ref = runtime.run(execution_request)
    assert cached_publication_ref == publication_ref
    repository = BacktestEvidenceRepository(store)
    completed = repository.load_completed(publication_ref)
    engine_results = tuple(
        value.artifact
        for ref, value in store.values.items()
        if ref.artifact_type == "engine_execution_result"
    )
    assert len(engine_results) == 1
    engine_result = engine_results[0]
    analysis_runtime = BacktestAnalysisRuntime(store)
    metric_profile_ref = analysis_runtime.publish_metric_profile()
    analysis_ref = analysis_runtime.derive(completed, metric_profile_ref)
    assert type(analysis_ref) is AnalysisArtifactRef
    analysis = repository.load_analysis(analysis_ref)
    return _Journey(
        reader,
        values.target_stream,
        valuation,
        case,
        execution_request,
        domain.canonical_sha256(envelope),
        publication_ref,
        cached_publication_ref,
        completed,
        engine_result,
        analysis_ref,
        analysis,
    )


def _identity(journey: _Journey) -> dict[str, object]:
    engine = journey.engine_result
    order = engine.order_streams[0].order
    fill = engine.fills[0]
    return {
        "type": "g12m_tushare_market_engine_journey_identity_v1",
        "schema_version": 1,
        "market_bundle_ref": journey.reader.bundle_ref,
        "market_bundle_content_hash": journey.reader.manifest.content_hash,
        "target_stream_digest": journey.target_stream.target_stream_digest,
        "valuation_event_hash": journey.valuation_event.event_hash,
        "execution_input_ref": journey.execution_request.execution_input_bundle_ref,
        "execution_input_source_hash": journey.execution_input_source_hash,
        "publication_ref": journey.publication_ref,
        "semantic_run_id": journey.completed.semantic_run_id,
        "execution_case_hash": journey.execution_case.case_hash,
        "execution_result_hash": journey.completed.source_execution_result_hash,
        "trace_hash": engine.trace.trace_hash,
        "analysis_ref": journey.analysis_ref,
        "timeline_event_count": sum(
            entry.stage is EngineStage.TIMELINE_EVENT for entry in engine.trace.entries
        ),
        "decision_batch_count": len(engine.decision_batches),
        "order_count": len(engine.order_streams),
        "fill_count": len(engine.fills),
        "fee_assessment_count": len(engine.fee_assessments),
        "trade_count": journey.analysis.trade_count,
        "order_side": order.intent.side.value,
        "order_quantity": order.intent.quantity,
        "fill_price": fill.price,
        "fee_amount": engine.fee_assessments[0].amount,
        "final_cash": engine.final_ledger_state.cash_balances[0].amount,
        "final_position": engine.final_ledger_state.position_balances[0].quantity,
        "final_equity": engine.final_portfolio_snapshot.equity,
        "result_grade": journey.completed.result_grade.value,
    }


def test_complete_tushare_market_engine_journey_replays_and_matches_golden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journey = _journey(tmp_path, monkeypatch)
    engine = journey.engine_result

    assert len(engine.decision_batches) == 1
    assert len(engine.order_streams) == 1
    assert len(engine.fills) == 1
    assert len(engine.fee_assessments) == 1
    assert engine.fee_assessments[0].amount.units == 0
    assert engine.final_ledger_state.position_balances[0].quantity.units > 0
    assert engine.final_portfolio_snapshot.positions
    assert journey.analysis.trade_count == 1
    assert journey.completed.result_grade.value == "development"
    assert journey.cached_publication_ref == journey.publication_ref

    actual = json.loads(domain.canonical_bytes(_identity(journey)))
    if not FIXTURE.exists():
        pytest.fail(json.dumps(actual, indent=2, ensure_ascii=False))
    assert actual == json.loads(FIXTURE.read_text())
