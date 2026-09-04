from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    ObservationCausalityFailure,
    ObservationCausalityFailureCode,
    ObservationQuery,
    ObservationQueryFailure,
    ObservationQueryFailureCode,
    RevisionedObservationRecord,
)

from tests.runtime.observations._causality_fixtures import (
    DECISION_AT_CORRECTION,
    DECISION_BEFORE_CORRECTION,
    DECISION_LATE,
    causality_failure_cases,
    point_in_time_view,
    precedence_records,
    records,
    run_query,
)
from tests.runtime.observations._fixtures import (
    BARS_V2,
    INSTRUMENT_B,
    OHLCV,
    query,
)


def test_full_instant_cutoff_selects_latest_revision_without_hidden_interference() -> None:
    supplied = records()
    baseline = point_in_time_view(
        DECISION_BEFORE_CORRECTION,
        supplied_records=supplied[:2],
    )
    with_hidden_records = point_in_time_view(
        DECISION_BEFORE_CORRECTION,
        supplied_records=tuple(reversed(supplied)),
    )

    baseline_outcome = run_query(baseline)
    hidden_outcome = run_query(with_hidden_records)
    assert baseline.view_hash == with_hidden_records.view_hash
    assert baseline_outcome.to_canonical_dict() == hidden_outcome.to_canonical_dict()
    assert baseline_outcome.result is not None
    assert [event.event_id for event in baseline_outcome.result.events] == [
        "bar-a-v1",
        "bar-b-v1",
    ]

    corrected = run_query(point_in_time_view(DECISION_AT_CORRECTION))
    assert corrected.failure is None
    assert corrected.result is not None
    assert [event.event_id for event in corrected.result.events] == [
        "bar-b-v1",
        "bar-a-v2",
    ]
    trace = corrected.result.trace
    assert list(trace.selected_observation_keys) == ["bar-b", "bar-a"]
    assert list(trace.selected_revision_ids) == ["source-v1", "source-v2"]
    assert trace.event_count == 2
    assert trace.max_event_time.epoch_nanoseconds == 140
    assert trace.max_available_instant == DECISION_AT_CORRECTION
    assert len(trace.candidate_record_hashes) == 3


@pytest.mark.parametrize(
    ("unauthorized", "expected_code"),
    (
        (query(dataset_key="trades"), ObservationQueryFailureCode.DATASET_NOT_AUTHORIZED),
        (
            query(instrument_id=INSTRUMENT_B),
            ObservationQueryFailureCode.INSTRUMENT_NOT_AUTHORIZED,
        ),
        (
            query(purpose=replace(OHLCV, key="bar.typical-price")),
            ObservationQueryFailureCode.PURPOSE_NOT_AUTHORIZED,
        ),
        (
            query(capability=BARS_V2),
            ObservationQueryFailureCode.CAPABILITY_NOT_AUTHORIZED,
        ),
    ),
)
def test_authorization_precedes_revision_inspection(
    unauthorized: ObservationQuery,
    expected_code: ObservationQueryFailureCode,
) -> None:
    outcome = run_query(point_in_time_view(DECISION_LATE), unauthorized)

    assert outcome.result is None
    assert type(outcome.failure) is ObservationQueryFailure
    assert outcome.failure.code is expected_code


@pytest.mark.parametrize(
    ("case_name", "supplied_records", "expected_code"),
    causality_failure_cases(),
)
def test_illegal_revision_sets_fail_closed_with_structured_evidence(
    case_name: str,
    supplied_records: tuple[RevisionedObservationRecord, ...],
    expected_code: ObservationCausalityFailureCode,
) -> None:
    outcome = run_query(
        point_in_time_view(DECISION_LATE, supplied_records=supplied_records)
    )

    assert outcome.result is None, case_name
    assert type(outcome.failure) is ObservationCausalityFailure
    assert outcome.failure.code is expected_code
    assert outcome.failure.observation_keys
    assert outcome.failure.revision_ids
    assert outcome.failure.candidate_record_hashes


def test_failure_precedence_and_input_order_are_deterministic() -> None:
    supplied = precedence_records()
    forward = run_query(point_in_time_view(DECISION_LATE, supplied_records=supplied))
    reversed_outcome = run_query(
        point_in_time_view(DECISION_LATE, supplied_records=tuple(reversed(supplied)))
    )

    assert forward.to_canonical_dict() == reversed_outcome.to_canonical_dict()
    assert type(forward.failure) is ObservationCausalityFailure
    assert forward.failure.code is ObservationCausalityFailureCode.REVISION_ID_CONFLICT


def test_empty_and_exact_duplicate_inputs_remain_successful_and_deterministic() -> None:
    empty_query = query(dataset_key="bars.empty")
    empty = run_query(
        point_in_time_view(
            DECISION_LATE,
            supplied_records=(),
            allowed_queries=(query(), empty_query),
        ),
        empty_query,
    )
    assert empty.failure is None
    assert empty.result is not None
    assert not empty.result.events
    assert empty.result.trace.event_count == 0
    assert empty.result.trace.max_event_time is None
    assert empty.result.trace.max_available_instant is None

    supplied = records()[:2]
    once = point_in_time_view(DECISION_LATE, supplied_records=supplied)
    repeated = point_in_time_view(
        DECISION_LATE,
        supplied_records=(*reversed(supplied), supplied[0], supplied[1]),
    )
    assert once.view_hash == repeated.view_hash
    assert run_query(once).outcome_hash == run_query(repeated).outcome_hash


def test_result_rejects_forged_causality_trace_and_time_context() -> None:
    outcome = run_query(point_in_time_view(DECISION_AT_CORRECTION))
    assert outcome.result is not None
    forged_trace = replace(
        outcome.result.trace,
        dataset_hash="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="dataset_hash"):
        replace(outcome.result, trace=forged_trace)

    with pytest.raises(ValueError, match="future"):
        replace(outcome.result, decision_instant=DECISION_BEFORE_CORRECTION)

    wrong_context_trace = replace(
        outcome.result.trace,
        view_hash="sha256:" + "f" * 64,
    )
    with pytest.raises(ValueError, match="trace context"):
        replace(outcome.result, trace=wrong_context_trace)

    with pytest.raises(ValueError, match="observation keys must be unique"):
        replace(
            outcome.result.trace,
            selected_observation_keys=("bar-b", "bar-b"),
        )
