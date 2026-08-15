from __future__ import annotations

from crypto_quant_backtest import (
    BarDefinitionRef,
    NamedBarWindowQuery,
    NamedBarWindowView,
    ObservationPurposeRef,
    ObservationQuery,
    ObservationRecord,
    PointInTimeObservationView,
    RevisionedObservationRecord,
)
from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)

from tests.bundle_builder.bar_aggregation.test_bar_aggregation import (
    aggregate,
    bucket,
    event,
    plan,
)


def test_named_bar_window_consumes_exact_g12g_bars_without_resampling() -> None:
    source_events = (
        event(0, event_time=110, available_time=120, price_units=100),
        event(
            1,
            event_time=210,
            available_time=220,
            price_units=300,
            record_key="second",
        ),
        event(
            2,
            event_time=210,
            available_time=350,
            price_units=400,
            record_key="second",
            supersedes_revision_id="revision-1",
        ),
    )
    aggregation = aggregate(
        source_events,
        bucket_plan=plan(bucket(100, 200), bucket(200, 300)),
    )
    assert aggregation.result is not None
    generated = aggregation.result.generated_events
    definition = aggregation.result.aggregation_manifest.bar_definition
    observation_query = ObservationQuery(
        dataset_key=definition.output_stream_key,
        instrument_id=generated[0].instrument_id,
        purpose=ObservationPurposeRef("bar.ohlcv", 1),
        capability=generated[0].capability,
    )
    records = tuple(
        RevisionedObservationRecord(
            observation_key=(
                f"{bar.instrument_id.stable_key}:{bar.payload['bucket_hash']}"
            ),
            record=ObservationRecord(
                purpose=observation_query.purpose,
                event=bar,
            ),
        )
        for bar in generated
    )
    decision_instant = SimulationInstant(
        UtcInstant(500), TimelinePhase(99, "decision"), SourceSequence(0)
    )
    point_in_time = PointInTimeObservationView(
        allowed_queries=(observation_query,),
        records=records,
        decision_instant=decision_instant,
    )
    backing = point_in_time.query(observation_query)
    assert backing.result is not None
    named_query = NamedBarWindowQuery(
        observation_query=observation_query,
        bar_definition=BarDefinitionRef(
            key=definition.key,
            version=definition.version,
            definition_hash=definition.definition_hash,
        ),
        decision_instant=decision_instant,
        lookback_count=2,
        end_at_or_before=None,
    )

    result = NamedBarWindowView(
        query=named_query, backing_result=backing.result
    ).window()

    expected = (generated[0], generated[2])
    assert result.events == expected
    assert tuple(bar.event_type for bar in result.events) == ("bar", "bar")
    assert tuple(bar.event_time for bar in result.events) == tuple(
        bar.event_time for bar in expected
    )
    assert tuple(bar.payload for bar in result.events) == tuple(
        bar.payload for bar in expected
    )
    expected_definition_fields = {
        "bar_definition_key": named_query.bar_definition.key,
        "bar_definition_version": named_query.bar_definition.version,
        "bar_definition_hash": named_query.bar_definition.definition_hash,
    }
    for bar in result.events:
        assert {
            key: bar.payload[key] for key in expected_definition_fields
        } == expected_definition_fields
