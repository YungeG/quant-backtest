from __future__ import annotations

from dataclasses import fields, replace

import pytest

from crypto_quant_backtest import (
    BarDefinitionRef,
    LookbackRequirement,
    ObservationPurposeRef,
    ObservationQuery,
    ObservationRecord,
    PointInTimeObservationView,
    RevisionedObservationRecord,
)
from crypto_quant_backtest.multi_resolution_market_data import (
    SignalBarBinding,
    SignalBarVerificationFailureCode,
    verify_visible_signal_bars,
)
from crypto_quant_domain import PricePurpose, SimulationInstant, SourceSequence, TimelinePhase, UtcInstant
from crypto_quant_market_data import MarketBundleCapability, MarketEvent

from tests.bundle_builder.bar_aggregation.test_bar_aggregation import aggregate, bucket, event, plan


def context():
    aggregation = aggregate((event(0, event_time=110, available_time=120, price_units=100),), bucket_plan=plan(bucket(100, 200)))
    assert aggregation.result is not None
    bar = aggregation.result.generated_events[0]
    definition = aggregation.result.aggregation_manifest.bar_definition
    query = ObservationQuery(
        definition.output_stream_key,
        bar.instrument_id,
        ObservationPurposeRef("bar.ohlcv", 1),
        bar.capability,
    )
    requirement = LookbackRequirement(
        "primary-bars",
        query,
        BarDefinitionRef(definition.key, definition.version, definition.definition_hash),
        1,
    )
    binding = SignalBarBinding(
        requirement.requirement_hash,
        definition.output_stream_key,
        PricePurpose.VALUATION,
        aggregation.result.aggregation_manifest.aggregation_input_hash,
    )
    stream_manifest = aggregation.result.aggregation_manifest.output_stream_manifest
    assert stream_manifest is not None
    return requirement, binding, stream_manifest, bar


def visible_result(*events: MarketEvent, decision_ns: int = 500):
    requirement, _, _, _ = context()
    records = tuple(
        RevisionedObservationRecord(
            f"opaque-lineage:{item.event_id}",
            ObservationRecord(requirement.observation_query.purpose, item),
        )
        for item in events
    )
    view = PointInTimeObservationView(
        allowed_queries=(requirement.observation_query,),
        records=records,
        decision_instant=SimulationInstant(UtcInstant(decision_ns), TimelinePhase(99, "decision"), SourceSequence(0)),
    )
    outcome = view.query(requirement.observation_query)
    assert outcome.result is not None
    return outcome.result


def forge(value, **changes):
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged, field.name, changes.get(field.name, getattr(value, field.name))
        )
    return forged


def malformed(bar: MarketEvent, **payload_changes: object) -> MarketEvent:
    payload = dict(bar.payload)
    payload.update(payload_changes)
    return replace(bar, payload=payload)


def test_visible_canonical_g12g_bar_is_verified_after_visibility() -> None:
    requirement, binding, stream_manifest, bar = context()

    outcome = verify_visible_signal_bars(requirement, binding, stream_manifest, visible_result(bar))

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.events == (bar,)
    assert outcome.result.events[0] is not bar
    assert outcome.result.events[0].instrument_id is not bar.instrument_id
    assert outcome.result.events[0].event_time is not bar.event_time


def test_malformed_future_bar_cannot_change_earlier_verification() -> None:
    requirement, binding, stream_manifest, bar = context()
    future = replace(
        malformed(bar, schema_version=2),
        event_id="future-event",
        revision_id="future-revision",
        available_time=UtcInstant(400),
        source_sequence=SourceSequence(1),
    )

    outcome = verify_visible_signal_bars(requirement, binding, stream_manifest, visible_result(bar, future, decision_ns=300))

    assert outcome.result is not None
    assert outcome.result.events == (bar,)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda bar: replace(bar, event_type="trade"),
        lambda bar: replace(bar, source_key="wrong"),
        lambda bar: malformed(bar, schema_version=True),
        lambda bar: malformed(bar, aggregation_spec_hash="sha256:" + "0" * 64),
        lambda bar: malformed(bar, price_scale=True),
        lambda bar: malformed(bar, open={"units": 1, "scale": 4, "extra": 0}),
        lambda bar: malformed(bar, low={"units": 200, "scale": 4}),
        lambda bar: malformed(
            bar,
            session_id={"type": "session_id", "calendar_id": "test", "value": " bad "},
        ),
        lambda bar: malformed(
            bar,
            trading_date={"type": "trading_date", "calendar_id": "test", "date": "bad-date"},
        ),
        lambda bar: malformed(bar, included_spans=()),
        lambda bar: malformed(
            bar,
            included_spans=(
                {
                    "start": bar.payload["interval_start"],
                    "end_exclusive": bar.payload["interval_start"],
                },
            ),
        ),
        lambda bar: malformed(bar, volume={"units": 0, "scale": 4}),
        lambda bar: malformed(
            bar, observation_count=bar.payload["observation_count"] + 1
        ),
        lambda bar: malformed(bar, source_event_hashes=()),
        lambda bar: malformed(
            bar, source_event_hashes=("not-a-hash",)
        ),
        lambda bar: malformed(bar, selected_source_set_hash="sha256:" + "0" * 64),
        lambda bar: malformed(bar, bucket_hash="sha256:" + "0" * 64),
    ],
)
def test_exact_g12g_payload_and_nested_grammar_fail_closed(mutate) -> None:
    requirement, binding, stream_manifest, bar = context()
    changed = mutate(bar)

    outcome = verify_visible_signal_bars(requirement, binding, stream_manifest, visible_result(changed))

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is SignalBarVerificationFailureCode.MALFORMED_G12G_PAYLOAD


def test_forged_point_in_time_event_and_causality_authority_are_rejected() -> None:
    requirement, binding, stream_manifest, bar = context()
    backing = visible_result(bar)

    forged_stream_event = forge(bar, stream_key="other")
    with pytest.raises(ValueError, match="context"):
        verify_visible_signal_bars(
            requirement,
            binding,
            stream_manifest,
            forge(backing, events=(forged_stream_event,)),
        )

    forged_capability_event = forge(
        bar, capability=MarketBundleCapability("other", 1)
    )
    with pytest.raises(ValueError, match="context"):
        verify_visible_signal_bars(
            requirement,
            binding,
            stream_manifest,
            forge(backing, events=(forged_capability_event,)),
        )

    forged_event_time = forge(bar.event_time, epoch_nanoseconds=True)
    with pytest.raises(TypeError, match="integer"):
        verify_visible_signal_bars(
            requirement,
            binding,
            stream_manifest,
            forge(backing, events=(forge(bar, event_time=forged_event_time),)),
        )

    forged_trace = forge(backing.trace, event_count=2)
    with pytest.raises(ValueError, match="event_count"):
        verify_visible_signal_bars(
            requirement,
            binding,
            stream_manifest,
            forge(backing, trace=forged_trace),
        )


def test_selected_stream_manifest_must_match_binding_requirement_and_bar_contract() -> None:
    requirement, binding, stream_manifest, bar = context()

    with pytest.raises(ValueError, match="stream_manifest"):
        verify_visible_signal_bars(
            requirement,
            binding,
            replace(stream_manifest, event_type="trade"),
            visible_result(bar),
        )


def test_failure_precedence_definition_then_aggregation_lineage() -> None:
    requirement, binding, stream_manifest, bar = context()
    for wrong_definition in (
        malformed(bar, bar_definition_key="wrong"),
        malformed(bar, bar_definition_version=2),
        malformed(bar, bar_definition_hash="sha256:" + "8" * 64),
    ):
        definition_outcome = verify_visible_signal_bars(
            requirement,
            binding,
            stream_manifest,
            visible_result(wrong_definition),
        )
        assert definition_outcome.failure is not None
        assert (
            definition_outcome.failure.code
            is SignalBarVerificationFailureCode.BAR_DEFINITION_MISMATCH
        )

    wrong_lineage = malformed(bar, aggregation_input_hash="sha256:" + "9" * 64)
    lineage_outcome = verify_visible_signal_bars(requirement, binding, stream_manifest, visible_result(wrong_lineage))
    assert lineage_outcome.failure is not None
    assert lineage_outcome.failure.code is SignalBarVerificationFailureCode.AGGREGATION_LINEAGE_MISMATCH

    wrong_source_hash = replace(bar, source_hash="sha256:" + "7" * 64)
    source_hash_outcome = verify_visible_signal_bars(
        requirement,
        binding,
        stream_manifest,
        visible_result(wrong_source_hash),
    )
    assert source_hash_outcome.failure is not None
    assert (
        source_hash_outcome.failure.code
        is SignalBarVerificationFailureCode.AGGREGATION_LINEAGE_MISMATCH
    )
