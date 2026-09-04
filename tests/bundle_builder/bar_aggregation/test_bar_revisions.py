from __future__ import annotations

from crypto_quant_bundle_builder import BarAggregationFailureCode
from crypto_quant_bundle_builder.bar_aggregation import (
    _revision_chains,
    _source_observations,
)
from crypto_quant_domain import (
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
)

from tests.bundle_builder.bar_aggregation.test_bar_aggregation import (
    INSTRUMENT,
    OTHER_INSTRUMENT,
    aggregate,
    assert_failure,
    bucket,
    definition,
    event,
    plan,
)


def test_pre_close_correction_collapses_into_one_root_bar() -> None:
    root = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
    )
    child = event(
        1,
        event_time=110,
        available_time=150,
        price_units=200,
        record_key="one",
        supersedes_revision_id=root.revision_id,
    )

    outcome = aggregate((root, child))

    assert outcome.failure is None
    assert outcome.result is not None
    assert len(outcome.result.generated_events) == 1
    bar = outcome.result.generated_events[0]
    assert bar.available_time == UtcInstant(200)
    assert bar.supersedes_revision_id is None
    assert bar.payload["close"] == {"units": 200, "scale": 4}
    assert bar.payload["source_event_hashes"] == (child.event_hash,)
    assert outcome.result.aggregation_manifest.output_root_count == 1
    assert outcome.result.aggregation_manifest.output_revision_count == 1


def test_post_close_correction_emits_immediate_child_even_when_ohlc_is_unchanged() -> (
    None
):
    root = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
    )
    child = event(
        1,
        event_time=110,
        available_time=250,
        price_units=100,
        record_key="one",
        supersedes_revision_id=root.revision_id,
    )

    outcome = aggregate((root, child))

    assert outcome.failure is None
    assert outcome.result is not None
    first, second = outcome.result.generated_events
    assert first.available_time == UtcInstant(200)
    assert second.available_time == UtcInstant(250)
    assert (
        first.payload["close"]
        == second.payload["close"]
        == {
            "units": 100,
            "scale": 4,
        }
    )
    assert first.payload["source_event_hashes"] == (root.event_hash,)
    assert second.payload["source_event_hashes"] == (child.event_hash,)
    assert second.supersedes_revision_id == first.revision_id
    assert second.revision_id != first.revision_id
    assert tuple(bar.source_sequence for bar in (first, second)) == (
        SourceSequence(0),
        SourceSequence(1),
    )
    assert outcome.result.aggregation_manifest.output_root_count == 1
    assert outcome.result.aggregation_manifest.output_revision_count == 2


def test_same_utc_source_changes_are_grouped_before_one_bar_revision() -> None:
    first_root = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
    )
    second_root = event(
        1,
        event_time=120,
        available_time=130,
        price_units=300,
        record_key="two",
    )
    first_child = event(
        2,
        event_time=110,
        available_time=250,
        price_units=200,
        record_key="one",
        supersedes_revision_id=first_root.revision_id,
    )
    second_child = event(
        3,
        event_time=120,
        available_time=250,
        price_units=400,
        record_key="two",
        supersedes_revision_id=second_root.revision_id,
    )

    outcome = aggregate((first_root, second_root, first_child, second_child))

    assert outcome.failure is None
    assert outcome.result is not None
    assert len(outcome.result.generated_events) == 2
    first, second = outcome.result.generated_events
    assert second.available_time == UtcInstant(250)
    assert second.supersedes_revision_id == first.revision_id
    assert second.payload["source_event_hashes"] == (
        first_child.event_hash,
        second_child.event_hash,
    )
    assert second.payload["open"] == {"units": 200, "scale": 4}
    assert second.payload["close"] == {"units": 400, "scale": 4}


def test_same_chain_same_utc_changes_are_grouped_without_intermediate_bar_leaks() -> (
    None
):
    root = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
        source_sequence=1,
    )
    # Child 1: Same UTC available_time, but higher phase
    child_one = event(
        1,
        event_time=110,
        available_time=120,
        price_units=200,
        record_key="one",
        supersedes_revision_id=root.revision_id,
        phase=TimelinePhase(11, "source.update"),
        source_sequence=1,
    )
    # Child 2: Same UTC available_time, same phase, but higher source_sequence
    child_two = event(
        2,
        event_time=110,
        available_time=120,
        price_units=300,
        record_key="one",
        supersedes_revision_id=child_one.revision_id,
        phase=TimelinePhase(11, "source.update"),
        source_sequence=2,
    )

    outcome = aggregate((root, child_one, child_two))

    assert outcome.failure is None
    assert outcome.result is not None
    assert len(outcome.result.generated_events) == 1
    bar = outcome.result.generated_events[0]
    assert bar.available_time == UtcInstant(200)  # At bucket close
    assert bar.supersedes_revision_id is None
    assert bar.payload["close"] == {"units": 300, "scale": 4}
    assert bar.payload["source_event_hashes"] == (child_two.event_hash,)
    assert outcome.result.aggregation_manifest.output_root_count == 1
    assert outcome.result.aggregation_manifest.output_revision_count == 1


def test_equal_full_instant_revision_fails_chain_validation() -> None:
    bucket_plan = plan(bucket(100, 200))
    root = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
        phase=TimelinePhase(11, "source.update"),
        source_sequence=2,
    )
    child = event(
        1,
        event_time=110,
        available_time=120,
        price_units=200,
        record_key="one",
        supersedes_revision_id=root.revision_id,
        phase=TimelinePhase(11, "source.update"),
        source_sequence=2,
    )
    selected, _, selection_failure = _source_observations(
        source_events=(root, child),
        source_stream_key="synthetic.prices",
        definition=definition(),
        bucket_plan=bucket_plan,
    )
    assert selection_failure is None
    assert selected is not None

    chains, failure = _revision_chains(
        selected=selected,
        source_stream_key="synthetic.prices",
        bucket_plan=bucket_plan,
    )

    assert chains is None
    assert_failure(failure, BarAggregationFailureCode.REVISION_CHAIN_INVALID)


def test_backward_full_instant_revisions_fail_chain_validation() -> None:
    parent = event(
        1,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
        phase=TimelinePhase(11, "source.update"),
        source_sequence=2,
    )
    earlier_phase_child = event(
        0,
        event_time=110,
        available_time=120,
        price_units=200,
        record_key="one",
        supersedes_revision_id=parent.revision_id,
        phase=TimelinePhase(10, "source"),
        source_sequence=2,
    )
    earlier_sequence_child = event(
        0,
        event_time=110,
        available_time=120,
        price_units=300,
        record_key="one",
        supersedes_revision_id=parent.revision_id,
        phase=TimelinePhase(11, "source.update"),
        source_sequence=1,
    )

    for child in (earlier_phase_child, earlier_sequence_child):
        assert_failure(
            aggregate((child, parent)),
            BarAggregationFailureCode.REVISION_CHAIN_INVALID,
        )


def test_output_sequence_is_global_and_deterministic_after_candidate_sorting() -> None:
    events = (
        event(
            0,
            event_time=110,
            available_time=120,
            price_units=100,
            instrument_id=OTHER_INSTRUMENT,
        ),
        event(
            1,
            event_time=120,
            available_time=130,
            price_units=200,
            instrument_id=INSTRUMENT,
        ),
    )

    outcome = aggregate(events)

    assert outcome.failure is None
    assert outcome.result is not None
    bars = outcome.result.generated_events
    assert tuple(bar.source_sequence for bar in bars) == (
        SourceSequence(0),
        SourceSequence(1),
    )
    assert tuple(bar.instrument_id for bar in bars) == tuple(
        sorted((INSTRUMENT, OTHER_INSTRUMENT), key=canonical_bytes)
    )


def test_late_root_waits_for_first_nonempty_visible_state() -> None:
    root = event(
        0,
        event_time=110,
        available_time=250,
        price_units=100,
        record_key="one",
    )
    child = event(
        1,
        event_time=110,
        available_time=300,
        price_units=200,
        record_key="one",
        supersedes_revision_id=root.revision_id,
    )

    outcome = aggregate((root, child))

    assert outcome.failure is None
    assert outcome.result is not None
    first, second = outcome.result.generated_events
    assert first.available_time == UtcInstant(250)
    assert first.supersedes_revision_id is None
    assert second.available_time == UtcInstant(300)
    assert second.supersedes_revision_id == first.revision_id


def test_cycle_and_multiple_roots_fail_chain_validation() -> None:
    cycle_a = event(
        0,
        event_time=110,
        price_units=100,
        record_key="one",
        supersedes_revision_id="revision-1",
    )
    cycle_b = event(
        1,
        event_time=110,
        price_units=200,
        record_key="one",
        supersedes_revision_id="revision-0",
    )
    assert_failure(
        aggregate((cycle_a, cycle_b)),
        BarAggregationFailureCode.REVISION_CHAIN_INVALID,
    )

    root_a = event(0, event_time=110, price_units=100, record_key="one")
    root_b = event(1, event_time=110, price_units=200, record_key="one")
    assert_failure(
        aggregate((root_a, root_b)),
        BarAggregationFailureCode.REVISION_CHAIN_INVALID,
    )


def test_out_of_plan_chain_validation_is_enforced() -> None:
    out_of_plan = event(0, event_time=500, price_units=100)
    fork_a = event(
        1,
        event_time=500,
        price_units=200,
        supersedes_revision_id=out_of_plan.revision_id,
    )
    fork_b = event(
        2,
        event_time=500,
        price_units=300,
        supersedes_revision_id=out_of_plan.revision_id,
    )

    assert_failure(
        aggregate((out_of_plan, fork_a, fork_b)),
        BarAggregationFailureCode.REVISION_CHAIN_INVALID,
    )
