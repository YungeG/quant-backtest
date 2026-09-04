from __future__ import annotations

from dataclasses import fields, replace

import pytest

from crypto_quant_backtest.performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
)
from crypto_quant_backtest.multi_resolution_preparation import (
    MarketDataPreparationFailure,
    MarketDataPreparationFailureCode,
    MarketDataPreparationOutcome,
    MultiResolutionMarketDataPreparation,
    PreparedMultiResolutionMarketData,
    SignalObservationLineageBinding,
    prepare_multi_resolution_market_data_v1,
)
from crypto_quant_domain import canonical_sha256
from crypto_quant_market_data import EventCursor

from ._fixtures import prepared_inputs


def test_canonical_values_have_exact_fields_order_and_derived_hashes() -> None:
    values = prepared_inputs()
    lineage = values["signal_lineages"][0]
    assert tuple(field.name for field in fields(lineage)) == (
        "requirement_hash", "event_id", "event_hash", "observation_key"
    )
    preparation = MultiResolutionMarketDataPreparation(
        values["schedule"],
        __import__(
            "crypto_quant_backtest.multi_resolution_market_data",
            fromlist=["MultiResolutionMarketDataBindings"],
        ).MultiResolutionMarketDataBindings(
            values["signal_binding_candidates"],
            values["execution_binding_candidates"],
            values["valuation_binding_candidates"],
        ),
        values["signal_lineages"],
    )
    assert tuple(field.name for field in fields(preparation)) == (
        "decision_schedule", "bindings", "signal_lineages"
    )
    assert preparation.decision_schedule_hash == preparation.decision_schedule.schedule_hash
    assert preparation.signal_lineage_hash == canonical_sha256(
        {
            "type": "signal_observation_lineage_set",
            "schema_version": 1,
            "signal_lineages": [lineage.to_canonical_dict()],
        }
    )
    assert preparation.preparation_hash == canonical_sha256(preparation._canonical_body())


def test_lineage_rejects_duplicate_requirement_event_and_conflicting_event_hash() -> None:
    values = prepared_inputs()
    row = values["signal_lineages"][0]
    bindings_type = __import__(
        "crypto_quant_backtest.multi_resolution_market_data",
        fromlist=["MultiResolutionMarketDataBindings"],
    ).MultiResolutionMarketDataBindings
    bindings = bindings_type(
        values["signal_binding_candidates"],
        values["execution_binding_candidates"],
        values["valuation_binding_candidates"],
    )
    with pytest.raises(ValueError, match="duplicate"):
        MultiResolutionMarketDataPreparation(values["schedule"], bindings, (row, row))
    other_requirement = replace(row, requirement_hash="sha256:" + "a" * 64)
    conflicting = replace(other_requirement, event_hash="sha256:" + "b" * 64)
    with pytest.raises(ValueError, match="Event hash"):
        MultiResolutionMarketDataPreparation(
            values["schedule"], bindings, (row, conflicting)
        )


def test_failure_and_outcome_are_exact_structural_values() -> None:
    failure = MarketDataPreparationFailure(
        MarketDataPreparationFailureCode.SIGNAL_LINEAGE_MISMATCH,
        0,
        1,
        2,
        3,
    )
    assert tuple(field.name for field in fields(failure)) == (
        "code", "role_position", "schedule_entry_position", "requirement_position", "event_position"
    )
    assert failure.failure_hash == canonical_sha256(failure._canonical_body())
    outcome = MarketDataPreparationOutcome(None, failure)
    assert outcome.prepared is None and outcome.failure is failure
    with pytest.raises(ValueError, match="exactly one"):
        MarketDataPreparationOutcome(None, None)


def test_success_captures_immutable_reader_replays_matrix_and_records_six_operations() -> None:
    values = prepared_inputs()
    recorder = BoundedPerformanceRecorder()
    outcome = prepare_multi_resolution_market_data_v1(**values, recorder=recorder)

    assert outcome.failure is None
    assert type(outcome.prepared) is PreparedMultiResolutionMarketData
    prepared = outcome.prepared
    assert prepared is not None
    assert prepared.verified_reader is not values["reader"]
    assert prepared.verified_reader.bundle_ref == values["reader"].bundle_ref
    assert prepared.verified_reader.manifest == values["reader"].manifest
    assert dict(prepared.verified_reader.streams) == dict(values["reader"].streams)
    assert len(prepared.eligibilities) == 1
    assert prepared.eligibilities[0].strategy_invocation_eligible
    operations = {cell.operation for cell in recorder.snapshot()}
    assert {
        PerformanceOperation.LOOKUP_STREAMS,
        PerformanceOperation.HYDRATE_INPUTS,
        PerformanceOperation.VERIFY_REPLAY,
        PerformanceOperation.PROJECT_POINT_IN_TIME,
        PerformanceOperation.BUILD_WINDOW,
        PerformanceOperation.EVALUATE_LOOKBACK,
    } <= operations


class ZeroProgressReader:
    def __init__(self, reader):
        self.reader = reader

    @property
    def bundle_ref(self):
        return self.reader.bundle_ref

    @property
    def manifest(self):
        return self.reader.manifest

    def validate_requirements(self, **kwargs):
        return self.reader.validate_requirements(**kwargs)

    def open_cursor(self, stream_key, *, batch_size):
        return self.reader.open_cursor(stream_key, batch_size=batch_size)

    def read_batch(self, cursor):
        return (), cursor

    def resume_cursor(self, cursor, *, batch_size=None):
        return self.reader.resume_cursor(cursor, batch_size=batch_size)


def test_reader_zero_progress_fails_structurally_without_partial_output() -> None:
    values = prepared_inputs()
    values["reader"] = ZeroProgressReader(values["reader"])
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.prepared is None
    assert outcome.failure is not None
    assert outcome.failure.code is MarketDataPreparationFailureCode.BUNDLE_READER_MISMATCH


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            lambda values: values.update(signal_binding_candidates=()),
            MarketDataPreparationFailureCode.SIGNAL_BINDING_MISMATCH,
        ),
        (
            lambda values: values.update(signal_lineages=()),
            MarketDataPreparationFailureCode.SIGNAL_LINEAGE_MISMATCH,
        ),
        (
            lambda values: values.update(execution_binding_candidates=()),
            MarketDataPreparationFailureCode.EXECUTION_PROFILE_BINDING_MISMATCH,
        ),
        (
            lambda values: values.update(valuation_binding_candidates=()),
            MarketDataPreparationFailureCode.VALUATION_PROFILE_BINDING_MISMATCH,
        ),
    ],
)
def test_role_and_lineage_failures_are_closed_and_atomic(change, code) -> None:
    values = prepared_inputs()
    change(values)
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.prepared is None
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_failure_precedence_selects_valuation_before_lineage() -> None:
    values = prepared_inputs()
    values["valuation_binding_candidates"] = ()
    values["signal_lineages"] = ()
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.failure is not None
    assert outcome.failure.code is MarketDataPreparationFailureCode.VALUATION_PROFILE_BINDING_MISMATCH


def test_strict_execution_and_valuation_source_identity_fail_closed() -> None:
    values = prepared_inputs()
    authority = values["case_authority"]
    execution = authority.bar_executions[0]
    wrong_state = replace(execution.market_state, revision_id="wrong-revision")
    values["case_authority"] = replace(
        authority,
        bar_executions=(replace(execution, market_state=wrong_state),),
    )
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.failure is not None
    assert outcome.failure.code is MarketDataPreparationFailureCode.EXECUTION_PROFILE_BINDING_MISMATCH

    values = prepared_inputs()
    authority = values["case_authority"]
    mark = replace(authority.snapshot_plan.resolved_marks[0], revision_id="wrong-revision")
    values["case_authority"] = replace(
        authority,
        snapshot_plan=replace(authority.snapshot_plan, resolved_marks=(mark,)),
    )
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.failure is not None
    assert outcome.failure.code is MarketDataPreparationFailureCode.VALUATION_PROFILE_BINDING_MISMATCH


def test_forged_lineage_hash_fails_before_point_in_time_projection() -> None:
    values = prepared_inputs()
    row = values["signal_lineages"][0]
    values["signal_lineages"] = (replace(row, event_hash="sha256:" + "f" * 64),)
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.failure is not None
    assert outcome.failure.code is MarketDataPreparationFailureCode.SIGNAL_LINEAGE_MISMATCH


def test_recorder_failure_cannot_change_authoritative_success(monkeypatch) -> None:
    values = prepared_inputs()
    expected = prepare_multi_resolution_market_data_v1(**values)

    def fail_record(self, **kwargs):
        raise RuntimeError("secret-recorder-failure")

    monkeypatch.setattr(BoundedPerformanceRecorder, "record", fail_record)
    observed = prepare_multi_resolution_market_data_v1(
        **values, recorder=BoundedPerformanceRecorder()
    )
    assert observed == expected


def test_target_timeline_must_follow_full_decision_instant() -> None:
    values = prepared_inputs()
    entry = values["schedule"].entries[0]
    later_phase = replace(
        entry,
        decision_instant=replace(
            entry.decision_instant,
            phase=replace(entry.decision_instant.phase, rank=40, code="late-decision"),
        ),
    )
    values["schedule"] = replace(values["schedule"], entries=(later_phase,))
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.failure is not None
    assert outcome.failure.code is MarketDataPreparationFailureCode.DECISION_CYCLE_ELIGIBILITY_MISMATCH
