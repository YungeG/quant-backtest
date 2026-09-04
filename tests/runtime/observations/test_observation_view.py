from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    ObservationQueryFailure,
    ObservationQueryFailureCode,
    ObservationQueryOutcome,
    ObservationQueryResult,
    ObservationRecord,
    ObservationView,
)

from tests.runtime.observations._fixtures import (
    BARS_V1,
    BARS_V2,
    EXECUTION_REFERENCE,
    INSTRUMENT_A,
    INSTRUMENT_B,
    OHLCV,
    event,
    query,
    record,
    view,
)


def test_authorized_query_returns_only_exact_records_in_stable_order() -> None:
    observation_view = view()

    outcome = observation_view.query(query())

    assert outcome.failure is None
    assert outcome.result is not None
    assert [item.event_id for item in outcome.result.events] == ["bar-1", "bar-2"]
    assert outcome.result.query == query()
    assert outcome.result.view_hash == observation_view.view_hash
    assert not hasattr(observation_view, "to_canonical_dict")
    for forbidden in ("bundle_ref", "manifest", "reader", "cursor", "ledger", "records"):
        assert not hasattr(observation_view, forbidden)


def test_authorization_failure_precedence_uses_only_the_allowlist() -> None:
    observation_view = view()
    cases = (
        (
            query(
                dataset_key="bars.5m",
                instrument_id=INSTRUMENT_B,
                purpose=EXECUTION_REFERENCE,
                capability=BARS_V2,
            ),
            ObservationQueryFailureCode.DATASET_NOT_AUTHORIZED,
        ),
        (
            query(
                instrument_id=INSTRUMENT_B,
                purpose=EXECUTION_REFERENCE,
                capability=BARS_V2,
            ),
            ObservationQueryFailureCode.INSTRUMENT_NOT_AUTHORIZED,
        ),
        (
            query(purpose=replace(OHLCV, key="bar.typical-price"), capability=BARS_V2),
            ObservationQueryFailureCode.PURPOSE_NOT_AUTHORIZED,
        ),
        (
            query(capability=BARS_V2),
            ObservationQueryFailureCode.CAPABILITY_NOT_AUTHORIZED,
        ),
    )

    for requested, expected_code in cases:
        outcome = observation_view.query(requested)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected_code
        assert outcome.failure.query == requested
        assert outcome.failure.view_hash == observation_view.view_hash


def test_hidden_records_do_not_change_view_or_authorized_result_identity() -> None:
    allowed = (query(),)
    visible = record(
        "bar-visible",
        available_time=100,
        source_sequence=1,
        close_units=10_100,
    )
    hidden = record(
        "bar-hidden",
        instrument_id=INSTRUMENT_B,
        available_time=90,
        source_sequence=2,
        close_units=20_000,
    )
    baseline = ObservationView(allowed_queries=allowed, records=(visible,))
    with_hidden = ObservationView(
        allowed_queries=tuple(reversed(allowed)),
        records=(hidden, visible, hidden),
    )

    baseline_outcome = baseline.query(query())
    hidden_outcome = with_hidden.query(query())
    assert baseline.view_hash == with_hidden.view_hash
    assert baseline_outcome.to_canonical_dict() == hidden_outcome.to_canonical_dict()
    assert baseline_outcome.outcome_hash == hidden_outcome.outcome_hash


def test_same_event_requires_explicit_purpose_record_and_authorization() -> None:
    shared_event = event(
        "shared",
        available_time=100,
        source_sequence=1,
        close_units=10_100,
    )
    ohlcv_record = record(
        "shared",
        available_time=100,
        source_sequence=1,
        close_units=10_100,
    )
    execution_record = replace(ohlcv_record, purpose=EXECUTION_REFERENCE)
    observation_view = ObservationView(
        allowed_queries=(query(), query(purpose=EXECUTION_REFERENCE)),
        records=(execution_record, ohlcv_record),
    )

    ohlcv = observation_view.query(query())
    execution = observation_view.query(query(purpose=EXECUTION_REFERENCE))

    assert ohlcv.result is not None
    assert len(ohlcv.result.events) == 1
    assert ohlcv.result.events[0] == shared_event
    assert execution.result is not None
    assert len(execution.result.events) == 1
    assert execution.result.events[0] == shared_event
    unauthorized = ObservationView(
        allowed_queries=(query(),), records=(execution_record, ohlcv_record)
    ).query(query(purpose=EXECUTION_REFERENCE))
    assert unauthorized.failure is not None
    assert unauthorized.failure.code is ObservationQueryFailureCode.PURPOSE_NOT_AUTHORIZED


def test_authorized_empty_query_succeeds_without_inventing_coverage_semantics() -> None:
    outcome = view().query(query(dataset_key="bars.empty"))

    assert outcome.failure is None
    assert outcome.result is not None
    assert not outcome.result.events


def test_exact_duplicates_collapse_but_authorized_identity_conflicts_fail() -> None:
    allowed = (query(),)
    original = record(
        "bar-1",
        available_time=100,
        source_sequence=1,
        close_units=10_100,
    )
    duplicate_view = ObservationView(
        allowed_queries=(query(), query()), records=(original, original)
    )
    outcome = duplicate_view.query(query())
    assert outcome.result is not None
    assert len(outcome.result.events) == 1

    conflicting = record(
        "bar-1",
        available_time=100,
        source_sequence=1,
        close_units=99_999,
    )
    with pytest.raises(ValueError, match="conflicting authorized observation record"):
        ObservationView(allowed_queries=allowed, records=(original, conflicting))


def test_result_record_and_failure_constructors_reject_forged_context() -> None:
    successful = view().query(query())
    assert successful.result is not None
    result = successful.result
    wrong_instrument = event(
        "wrong-instrument",
        instrument_id=INSTRUMENT_B,
        available_time=100,
        source_sequence=1,
        close_units=20_000,
    )
    with pytest.raises(ValueError, match="event context"):
        ObservationQueryResult(
            view_hash=result.view_hash,
            query=result.query,
            events=(wrong_instrument,),
        )
    with pytest.raises(ValueError, match="canonical order"):
        ObservationQueryResult(
            view_hash=result.view_hash,
            query=result.query,
            events=tuple(reversed(result.events)),
        )
    instrumentless = replace(
        event(
            "global",
            available_time=100,
            source_sequence=1,
            close_units=10_100,
        ),
        instrument_id=None,
    )
    with pytest.raises(ValueError, match="require one Instrument"):
        ObservationRecord(purpose=OHLCV, event=instrumentless)
    with pytest.raises(ValueError, match="sha256 content hash"):
        ObservationQueryFailure(
            view_hash="sha256:" + "A" * 64,
            query=query(),
            code=ObservationQueryFailureCode.DATASET_NOT_AUTHORIZED,
        )


def test_outcome_requires_exactly_one_result_or_failure() -> None:
    successful = view().query(query())
    failed = view().query(query(capability=BARS_V2))
    assert successful.result is not None
    assert failed.failure is not None

    with pytest.raises(ValueError, match="exactly one"):
        ObservationQueryOutcome(result=successful.result, failure=failed.failure)
    with pytest.raises(ValueError, match="exactly one"):
        ObservationQueryOutcome(result=None, failure=None)
