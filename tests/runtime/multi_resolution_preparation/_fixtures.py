from __future__ import annotations

from dataclasses import replace

from crypto_quant_backtest import (
    BarDefinitionRef,
    DecisionSchedule,
    DecisionScheduleEntry,
    LookbackRequirement,
    ObservationPurposeRef,
    ObservationQuery,
    PrecomputedTargetStream,
    ProfileResolver,
    TimelineSegment,
    TimelineWindow,
)
from crypto_quant_backtest.multi_resolution_market_data import (
    ExecutionDataBinding,
    SignalBarBinding,
    ValuationDataBinding,
)
from crypto_quant_domain import (
    PricePurpose,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketBundleCapability, MarketEvent

from tests.bundle_builder.bar_aggregation.test_bar_aggregation import aggregate, bucket, event, plan
from tests.runtime.engine._fixtures import (
    BTC,
    bar_event,
    bar_execution,
    decision_cycle,
    execution_model,
    snapshot_plan,
    target_event,
)
from tests.runtime.resolution._fixtures import build_manifest, profile_registry, request


def _g12g_bar(start: int, stop: int, *, stream_key: str, instrument_id=BTC) -> tuple[MarketEvent, object]:
    outcome = aggregate(
        (event(start, event_time=start + 1, available_time=start + 2, price_units=10_000),),
        bucket_plan=plan(bucket(start, stop)),
    )
    assert outcome.result is not None
    generated = outcome.result.generated_events[0]
    definition = outcome.result.aggregation_manifest.bar_definition
    return replace(generated, stream_key=stream_key, instrument_id=instrument_id), definition


def prepared_inputs():
    signal_event, definition = _g12g_bar(0, 50, stream_key="bars.signal")
    valuation_event, _ = _g12g_bar(290, 295, stream_key="bars.valuation")
    valuation_event = replace(
        valuation_event,
        event_id="valuation:300",
        revision_id="rev-1",
    )
    reader = InMemoryMarketBundleReader.build(
        bundle_key="fixture.preparation.bundle.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash="sha256:" + "91" * 32,
        capabilities=(
            signal_event.capability,
            bar_event().capability,
            target_event().capability,
        ),
        streams={
            "bars.signal": (signal_event,),
            "bars.open": (bar_event(),),
            "bars.valuation": (valuation_event,),
            "targets": (target_event(),),
        },
    )
    query = ObservationQuery(
        "bars.signal",
        BTC,
        ObservationPurposeRef("bar.ohlcv", 1),
        MarketBundleCapability("price_bars", 1),
    )
    requirement = LookbackRequirement(
        "primary-bars",
        query,
        BarDefinitionRef(definition.key, definition.version, definition.definition_hash),
        1,
    )
    entry = DecisionScheduleEntry(
        SimulationInstant(
            UtcInstant(100),
            TimelinePhase(20, "decision"),
            SourceSequence(0),
        ),
        TimelineSegment.ACTIVE_TRADING,
    )
    schedule = DecisionSchedule(
        "providerless.preparation.v1",
        1,
        TimelineWindow(UtcInstant(0), UtcInstant(90), UtcInstant(300)),
        (entry,),
        (requirement,),
    )
    signal_binding = SignalBarBinding(
        requirement.requirement_hash,
        "bars.signal",
        PricePurpose.VALUATION,
        signal_event.payload["aggregation_input_hash"],
    )
    execution_binding = ExecutionDataBinding(
        execution_model().component_ref.component_key,
        "bars.open",
    )
    valuation_binding = ValuationDataBinding(BTC, "bars.valuation")
    from crypto_quant_backtest.multi_resolution_preparation import (
        MarketDataCaseAuthority,
        SignalObservationLineageBinding,
    )

    mark = replace(
        snapshot_plan().resolved_marks[0],
        observed_at=UtcInstant(290),
        available_at=UtcInstant(295),
        age_nanoseconds=10,
        stream_id="bars.valuation",
        source_event_id=valuation_event.event_id,
        revision_id=valuation_event.revision_id,
    )
    authority = MarketDataCaseAuthority(
        decision_cycles=(decision_cycle(),),
        bar_executions=(bar_execution(),),
        execution_model=execution_model(),
        snapshot_plan=replace(snapshot_plan(), resolved_marks=(mark,)),
        target_stream=PrecomputedTargetStream("targets", (target_event(),)),
    )
    manifest = build_manifest()
    resolved_outcome = ProfileResolver().resolve(
        request=replace(
            request(manifest, bundle=reader.manifest),
            market_bundle_ref=reader.bundle_ref,
        ),
        registry=profile_registry(
            extra_market_capabilities=(MarketBundleCapability("price_bars", 1),)
        ),
        market_bundle_manifest=reader.manifest,
        build_artifact_manifest=manifest,
    )
    assert resolved_outcome.resolved is not None
    return {
        "expected_bundle_ref": reader.bundle_ref,
        "reader": reader,
        "schedule": schedule,
        "signal_binding_candidates": (signal_binding,),
        "execution_binding_candidates": (execution_binding,),
        "valuation_binding_candidates": (valuation_binding,),
        "signal_lineages": (
            SignalObservationLineageBinding(
                requirement.requirement_hash,
                signal_event.event_id,
                signal_event.event_hash,
                "opaque:signal:0",
            ),
        ),
        "case_authority": authority,
        "resolved_request": resolved_outcome.resolved,
    }
