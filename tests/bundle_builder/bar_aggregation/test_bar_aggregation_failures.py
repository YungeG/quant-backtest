from __future__ import annotations

from dataclasses import replace

import crypto_quant_bundle_builder.bar_aggregation as aggregation_module
from crypto_quant_bundle_builder import (
    BarAggregationFailureCode,
    aggregate_bars_v1,
)
from crypto_quant_domain import PricePurpose, TimelinePhase, UtcInstant

from tests.bundle_builder.bar_aggregation.test_bar_aggregation import (
    CODE_HASH,
    OTHER_INSTRUMENT,
    OUTPUT_PHASE,
    aggregate,
    assert_failure,
    bucket,
    definition,
    event,
    manifest,
    plan,
)


def test_all_nine_failure_codes_are_atomic(monkeypatch) -> None:
    events = (event(0, event_time=110, price_units=100),)
    source_mismatch = aggregate(
        events,
        source_manifest=manifest(events + (event(1, event_time=120, price_units=200),)),
    )
    other_definition = replace(definition(), version=2)
    definition_mismatch = aggregate(
        events,
        bucket_plan=plan(bucket(100, 200), value=other_definition),
    )
    unknown_source = replace(definition(), source_stream_key="unknown")
    stream_mismatch = aggregate(
        events,
        bucket_plan=plan(bucket(100, 200), value=unknown_source),
        bar_definition=unknown_source,
    )
    coverage_mismatch = aggregate(
        events,
        bucket_plan=replace(
            plan(bucket(100, 200)), coverage_end_exclusive=UtcInstant(900)
        ),
    )
    tie_events = (
        event(0, event_time=110, price_units=100, record_key="one"),
        event(1, event_time=110, price_units=200, record_key="two"),
    )
    source_event_tie_invalid = aggregate(tie_events)
    source_event_invalid = aggregate(
        (replace(events[0], payload={"price_units": 100}),)
    )
    revision_invalid = aggregate(
        (
            event(
                0,
                event_time=110,
                available_time=120,
                price_units=100,
                supersedes_revision_id="missing",
            ),
        )
    )
    causality_invalid = aggregate(
        (
            event(
                0,
                event_time=110,
                available_time=200,
                price_units=100,
                phase=OUTPUT_PHASE,
            ),
        )
    )

    real_validator = aggregation_module.validate_market_bundle_v1
    validation_count = 0

    # Use a valid structured G12C failure on the second validation call.
    def reject_second_validation(**kwargs):
        nonlocal validation_count
        validation_count += 1
        if validation_count == 2:
            duplicate = kwargs["events"] + (kwargs["events"][-1],)
            return real_validator(**{**kwargs, "events": duplicate})
        return real_validator(**kwargs)

    validation_count = 0
    monkeypatch.setattr(
        aggregation_module, "validate_market_bundle_v1", reject_second_validation
    )
    output_invalid = aggregate(events)

    invalid_input = aggregate_bars_v1(
        source_manifest=None,  # type: ignore[arg-type]
        source_events=(),
        bucket_plan=None,  # type: ignore[arg-type]
        definition=None,  # type: ignore[arg-type]
        aggregation_code_hash=CODE_HASH,
    )
    outcomes = (
        (invalid_input, BarAggregationFailureCode.INVALID_INPUT),
        (source_mismatch, BarAggregationFailureCode.SOURCE_BUNDLE_MISMATCH),
        (
            definition_mismatch,
            BarAggregationFailureCode.DEFINITION_BUCKET_PLAN_MISMATCH,
        ),
        (stream_mismatch, BarAggregationFailureCode.SOURCE_STREAM_MISMATCH),
        (coverage_mismatch, BarAggregationFailureCode.SOURCE_COVERAGE_UNALIGNED),
        (source_event_invalid, BarAggregationFailureCode.SOURCE_EVENT_INVALID),
        (source_event_tie_invalid, BarAggregationFailureCode.SOURCE_EVENT_INVALID),
        (revision_invalid, BarAggregationFailureCode.REVISION_CHAIN_INVALID),
        (causality_invalid, BarAggregationFailureCode.OUTPUT_CAUSALITY_INVALID),
        (output_invalid, BarAggregationFailureCode.OUTPUT_VALIDATION_FAILED),
    )

    for outcome, code in outcomes:
        assert_failure(outcome, code)
        assert outcome.result is None


def test_failure_precedence_is_global_not_input_position_order(monkeypatch) -> None:
    events = (event(0, event_time=110, price_units=100),)
    other_definition = replace(definition(), version=2, source_stream_key="unknown")
    source_before_definition = aggregate(
        events,
        source_manifest=manifest(events + (event(1, event_time=120, price_units=200),)),
        bucket_plan=plan(bucket(100, 200), value=other_definition),
        bar_definition=other_definition,
    )
    assert_failure(
        source_before_definition,
        BarAggregationFailureCode.SOURCE_BUNDLE_MISMATCH,
    )

    unaligned_unknown = replace(
        plan(bucket(100, 200), value=other_definition),
        coverage_end_exclusive=UtcInstant(900),
    )
    definition_before_stream = aggregate(
        events,
        bucket_plan=unaligned_unknown,
    )
    assert_failure(
        definition_before_stream,
        BarAggregationFailureCode.DEFINITION_BUCKET_PLAN_MISMATCH,
    )

    unknown_definition = replace(definition(), source_stream_key="unknown")
    stream_before_coverage = aggregate(
        events,
        bucket_plan=replace(
            plan(bucket(100, 200), value=unknown_definition),
            coverage_end_exclusive=UtcInstant(900),
        ),
        bar_definition=unknown_definition,
    )
    assert_failure(
        stream_before_coverage,
        BarAggregationFailureCode.SOURCE_STREAM_MISMATCH,
    )

    malformed = replace(
        event(0, event_time=120, available_time=130, price_units=200),
        payload={"price_units": 200},
    )
    coverage_before_source_event = aggregate(
        (malformed,),
        bucket_plan=replace(
            plan(bucket(100, 200)), coverage_end_exclusive=UtcInstant(900)
        ),
    )
    assert_failure(
        coverage_before_source_event,
        BarAggregationFailureCode.SOURCE_COVERAGE_UNALIGNED,
    )

    missing_parent = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        supersedes_revision_id="missing",
    )
    causal = event(
        1,
        event_time=120,
        available_time=200,
        price_units=400,
        phase=OUTPUT_PHASE,
    )
    malformed_one = replace(
        event(1, event_time=120, available_time=130, price_units=200),
        payload={"price_units": 200},
    )
    malformed_two = replace(
        event(2, event_time=130, available_time=140, price_units=300),
        payload={"price_units": 300},
    )
    earliest_source_event = aggregate(
        (event(0, event_time=110, price_units=100), malformed_one, malformed_two)
    )
    assert_failure(
        earliest_source_event,
        BarAggregationFailureCode.SOURCE_EVENT_INVALID,
    )
    assert earliest_source_event.failure is not None
    assert earliest_source_event.failure.input_position == 1

    missing_parent_two = event(
        2,
        event_time=120,
        available_time=130,
        price_units=200,
        supersedes_revision_id="missing2",
    )
    earliest_revision = aggregate(
        (
            missing_parent,
            event(1, event_time=115, available_time=125, price_units=150),
            missing_parent_two,
        )
    )
    assert_failure(
        earliest_revision,
        BarAggregationFailureCode.REVISION_CHAIN_INVALID,
    )
    assert earliest_revision.failure is not None
    assert earliest_revision.failure.input_position == 0

    causal_three = event(
        3,
        event_time=130,
        available_time=220,
        price_units=400,
        phase=OUTPUT_PHASE,
    )
    earliest_causality = aggregate(
        (
            event(0, event_time=100, price_units=100),
            causal,
            event(2, event_time=125, available_time=210, price_units=200),
            causal_three,
        )
    )
    assert_failure(
        earliest_causality,
        BarAggregationFailureCode.OUTPUT_CAUSALITY_INVALID,
    )
    assert earliest_causality.failure is not None
    assert earliest_causality.failure.input_position == 1
    source_event_before_revision = aggregate((missing_parent, malformed_one))
    assert_failure(
        source_event_before_revision,
        BarAggregationFailureCode.SOURCE_EVENT_INVALID,
    )
    assert source_event_before_revision.failure is not None
    assert source_event_before_revision.failure.input_position == 1

    root = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
    )
    fork_one = event(
        1,
        event_time=110,
        available_time=130,
        price_units=200,
        record_key="one",
        supersedes_revision_id=root.revision_id,
    )
    fork_two = event(
        2,
        event_time=110,
        available_time=140,
        price_units=300,
        record_key="one",
        supersedes_revision_id=root.revision_id,
    )

    revision_before_causality = aggregate(
        (
            root,
            fork_one,
            fork_two,
            event(
                3,
                event_time=120,
                available_time=200,
                price_units=400,
                phase=OUTPUT_PHASE,
            ),
        )
    )
    assert_failure(
        revision_before_causality,
        BarAggregationFailureCode.REVISION_CHAIN_INVALID,
    )
    assert revision_before_causality.failure is not None
    assert revision_before_causality.failure.input_position == 1

    causal_events = (
        event(
            10,
            event_time=110,
            available_time=200,
            price_units=100,
            record_key="one",
            phase=TimelinePhase(21, "bar.post_close"),
        ),
        event(
            11,
            event_time=120,
            available_time=200,
            price_units=200,
            record_key="two",
            phase=TimelinePhase(21, "bar.post_close"),
        ),
    )
    validation_count = 0
    real_validator = aggregation_module.validate_market_bundle_v1

    def reject_second_validation(**kwargs):
        nonlocal validation_count
        validation_count += 1
        if validation_count == 2:
            duplicate = kwargs["events"] + (kwargs["events"][-1],)
            return real_validator(**{**kwargs, "events": duplicate})
        return real_validator(**kwargs)

    monkeypatch.setattr(
        aggregation_module, "validate_market_bundle_v1", reject_second_validation
    )
    causality_before_output = aggregate(causal_events)
    assert_failure(
        causality_before_output,
        BarAggregationFailureCode.OUTPUT_CAUSALITY_INVALID,
    )
    assert causality_before_output.failure is not None
    assert causality_before_output.failure.input_position == 0
    assert validation_count == 1


def test_revision_identity_forgery_and_purpose_change_fail_closed() -> None:
    root = event(
        0,
        event_time=110,
        available_time=120,
        price_units=100,
        record_key="one",
    )
    changed_instrument = event(
        1,
        event_time=110,
        available_time=130,
        price_units=200,
        record_key="one",
        instrument_id=OTHER_INSTRUMENT,
        supersedes_revision_id=root.revision_id,
    )
    changed_purpose = event(
        1,
        event_time=110,
        available_time=130,
        price_units=200,
        record_key="one",
        purpose=PricePurpose.MARGIN,
        supersedes_revision_id=root.revision_id,
    )
    changed_time = event(
        1,
        event_time=115,
        available_time=130,
        price_units=200,
        record_key="one",
        supersedes_revision_id=root.revision_id,
    )
    duplicate_identity = replace(
        event(1, event_time=120, available_time=130, price_units=200),
        revision_id=root.revision_id,
    )
    changed_bucket = event(
        1,
        event_time=210,
        available_time=220,
        price_units=200,
        record_key="one",
        supersedes_revision_id=root.revision_id,
    )
    out_of_plan_root = event(
        0, event_time=50, available_time=60, price_units=100, record_key="oop"
    )
    in_plan_revision = event(
        1,
        event_time=110,
        available_time=120,
        price_units=200,
        record_key="oop",
        supersedes_revision_id=out_of_plan_root.revision_id,
    )
    for events in (
        (root, changed_instrument),
        (root, changed_purpose),
        (root, changed_time),
        (root, duplicate_identity),
        (root, changed_bucket),
        (out_of_plan_root, in_plan_revision),
    ):
        assert_failure(
            aggregate(events), BarAggregationFailureCode.REVISION_CHAIN_INVALID
        )
