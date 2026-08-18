from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    BarLiquidityEvidence,
    PrecomputedTargetStream,
    TimelineSegment,
)
from crypto_quant_backtest.multi_resolution_market_data import ValuationDataBinding
from crypto_quant_backtest.multi_resolution_preparation import (
    MarketDataPreparationFailureCode,
    SignalObservationLineageBinding,
    prepare_multi_resolution_market_data_v1,
)
from crypto_quant_backtest.performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
    PerformanceOutcome,
    _PerformanceObservation,
)
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    InstrumentId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_market_data import EventCursor, InMemoryMarketBundleReader

from tests.runtime.engine._fixtures import (
    bar_event,
    target_event,
    warmup_cycle,
    warmup_target_event,
)

from ._fixtures import _g12g_bar, bind_reader, prepared_inputs, rebuild_reader


def _assert_failure(values, code):
    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.prepared is None
    assert outcome.failure is not None
    assert outcome.failure.code is code
    return outcome.failure


@pytest.mark.parametrize(
    "signal_event",
    [
        replace(
            bar_event(),
            event_id="wrong-signal-capability",
            stream_key="bars.signal",
            source_sequence=SourceSequence(7),
        ),
        replace(
            prepared_inputs()["reader"].streams["bars.signal"][0],
            event_type="trade",
        ),
    ],
)
def test_wrong_signal_manifest_capability_or_event_type_is_structured_stream_failure(
    signal_event,
) -> None:
    values = prepared_inputs()
    reader = rebuild_reader(values, **{"bars.signal": (signal_event,)})
    bind_reader(values, reader)

    failure = _assert_failure(
        values, MarketDataPreparationFailureCode.STREAM_MANIFEST_MISMATCH
    )
    assert failure.role_position == 0
    assert failure.requirement_position == 0


class MutatingReader:
    def __init__(self, reader, mode):
        self.reader = reader
        self.mode = mode

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
        batch, successor = self.reader.read_batch(cursor)
        if self.mode == "cursor":
            other = next(
                value
                for value in self.reader.manifest.streams
                if value.stream_key != successor.stream_manifest.stream_key
                and value.event_count >= successor.position
            )
            successor = EventCursor(
                successor.bundle_ref,
                other,
                successor.position,
                successor.batch_size,
            )
        elif self.mode == "count":
            successor = EventCursor(
                successor.bundle_ref,
                successor.stream_manifest,
                cursor.position,
                successor.batch_size,
            )
        elif self.mode == "content":
            batch = (replace(batch[0], source_hash="sha256:" + "e" * 64), *batch[1:])
        return batch, successor

    def resume_cursor(self, cursor, *, batch_size=None):
        return self.reader.resume_cursor(cursor, batch_size=batch_size)


@pytest.mark.parametrize("mode", ["cursor", "count", "content"])
def test_reader_substitution_count_and_hash_fail_closed(mode) -> None:
    values = prepared_inputs()
    values["reader"] = MutatingReader(values["reader"], mode)
    _assert_failure(values, MarketDataPreparationFailureCode.BUNDLE_READER_MISMATCH)


def test_future_malformed_signal_is_bounded_but_does_not_affect_earlier_decision() -> None:
    values = prepared_inputs()
    current = values["reader"].streams["bars.signal"][0]
    future, _ = _g12g_bar(50, 80, stream_key="bars.signal")
    payload = dict(future.payload)
    payload["schema_version"] = 2
    future = replace(
        future,
        event_id="future-malformed",
        available_time=UtcInstant(150),
        source_sequence=SourceSequence(9),
        payload=payload,
    )
    reader = rebuild_reader(values, **{"bars.signal": (current, future)})
    bind_reader(values, reader)
    requirement_hash = values["schedule"].requirements[0].requirement_hash
    values["signal_lineages"] = (
        values["signal_lineages"][0],
        SignalObservationLineageBinding(
            requirement_hash, future.event_id, future.event_hash, "opaque:future"
        ),
    )

    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.failure is None


def test_end_exclusive_signal_is_excluded_from_lineage_cover() -> None:
    values = prepared_inputs()
    current = values["reader"].streams["bars.signal"][0]
    end_event = replace(
        current,
        event_id="at-end-exclusive",
        available_time=UtcInstant(300),
        source_sequence=SourceSequence(10),
    )
    reader = rebuild_reader(values, **{"bars.signal": (current, end_event)})
    bind_reader(values, reader)

    outcome = prepare_multi_resolution_market_data_v1(**values)
    assert outcome.failure is None


def test_revision_parent_outside_bounded_interval_fails_lineage() -> None:
    values = prepared_inputs()
    parent, definition = _g12g_bar(0, 40, stream_key="bars.signal")
    correction = replace(
        parent,
        event_id="bounded-correction",
        revision_id="rev-2",
        supersedes_revision_id=parent.revision_id,
        available_time=UtcInstant(60),
        source_sequence=SourceSequence(2),
    )
    reader = rebuild_reader(values, **{"bars.signal": (parent, correction)})
    bind_reader(values, reader)
    schedule = values["schedule"]
    requirement = replace(
        schedule.requirements[0],
        bar_definition=replace(
            schedule.requirements[0].bar_definition,
            key=definition.key,
            version=definition.version,
            definition_hash=definition.definition_hash,
        ),
    )
    values["schedule"] = replace(
        schedule,
        window=replace(schedule.window, data_start=UtcInstant(50)),
        requirements=(requirement,),
    )
    binding = values["signal_binding_candidates"][0]
    values["signal_binding_candidates"] = (
        replace(
            binding,
            requirement_hash=requirement.requirement_hash,
            aggregation_input_hash=parent.payload["aggregation_input_hash"],
        ),
    )
    values["signal_lineages"] = (
        SignalObservationLineageBinding(
            requirement.requirement_hash,
            correction.event_id,
            correction.event_hash,
            "opaque:bounded",
        ),
    )

    _assert_failure(values, MarketDataPreparationFailureCode.SIGNAL_LINEAGE_MISMATCH)


def test_f1_malformed_precedes_definition_mismatch_across_visible_events() -> None:
    values = prepared_inputs()
    original = values["reader"].streams["bars.signal"][0]
    definition_payload = dict(original.payload)
    definition_payload["bar_definition_key"] = "wrong-definition"
    wrong_definition = replace(original, payload=definition_payload)
    malformed_payload = dict(original.payload)
    malformed_payload["schema_version"] = 2
    malformed = replace(
        original,
        event_id="later-malformed",
        available_time=UtcInstant(60),
        source_sequence=SourceSequence(3),
        payload=malformed_payload,
    )
    reader = rebuild_reader(
        values, **{"bars.signal": (wrong_definition, malformed)}
    )
    bind_reader(values, reader)
    requirement_hash = values["schedule"].requirements[0].requirement_hash
    values["signal_lineages"] = (
        SignalObservationLineageBinding(
            requirement_hash,
            wrong_definition.event_id,
            wrong_definition.event_hash,
            "opaque:first",
        ),
        SignalObservationLineageBinding(
            requirement_hash,
            malformed.event_id,
            malformed.event_hash,
            "opaque:second",
        ),
    )

    failure = _assert_failure(values, MarketDataPreparationFailureCode.SIGNAL_BAR_FAILURE)
    assert failure.event_position == 1


def test_orphan_execution_and_warmup_only_execution_authority_fail_cycle_closure() -> None:
    values = prepared_inputs()
    authority = values["case_authority"]
    orphan = replace(
        authority.bar_executions[0],
        order_id=DomainId(DomainIdKind.ORDER, "ord_" + "9" * 64),
    )
    values["case_authority"] = replace(authority, bar_executions=(orphan,))
    _assert_failure(
        values, MarketDataPreparationFailureCode.DECISION_CYCLE_ELIGIBILITY_MISMATCH
    )

    values = prepared_inputs()
    schedule = values["schedule"]
    values["schedule"] = replace(
        schedule,
        entries=(
            replace(
                schedule.entries[0],
                decision_instant=SimulationInstant(
                    UtcInstant(50),
                    TimelinePhase(25, "warmup-decision"),
                    SourceSequence(0),
                ),
                segment=TimelineSegment.WARMUP,
            ),
        ),
    )
    reader = rebuild_reader(values, targets=(warmup_target_event(),))
    bind_reader(values, reader)
    authority = values["case_authority"]
    values["case_authority"] = replace(
        authority,
        decision_cycles=(warmup_cycle(),),
        target_stream=PrecomputedTargetStream("targets", (warmup_target_event(),)),
    )
    _assert_failure(
        values, MarketDataPreparationFailureCode.DECISION_CYCLE_ELIGIBILITY_MISMATCH
    )


def test_execution_event_instrument_must_match_admitted_order() -> None:
    values = prepared_inputs()
    original = values["reader"].streams["bars.open"][0]
    foreign = replace(
        original,
        instrument_id=InstrumentId(original.instrument_id.venue, "cash:eth-usd"),
    )
    reader = rebuild_reader(values, **{"bars.open": (foreign,)})
    bind_reader(values, reader)
    authority = values["case_authority"]
    execution = authority.bar_executions[0]
    evidence = BarLiquidityEvidence.create(
        evidence_key=execution.liquidity_evidence.evidence_key,
        evidence_version=execution.liquidity_evidence.evidence_version,
        market_event=foreign,
        evaluated_at=foreign.available_time,
        approved=True,
        reason_code=None,
        source_hash=execution.liquidity_evidence.source_hash,
    )
    state = replace(
        execution.market_state,
        evidence_hash=foreign.event_hash,
    )
    values["case_authority"] = replace(
        authority,
        bar_executions=(
            replace(execution, liquidity_evidence=evidence, market_state=state),
        ),
    )

    _assert_failure(
        values, MarketDataPreparationFailureCode.EXECUTION_PROFILE_BINDING_MISMATCH
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda mark: replace(mark, source_event_id="missing-valuation"),
        lambda mark: replace(mark, revision_id="wrong-revision"),
        lambda mark: replace(mark, stream_id="bars.signal"),
        lambda mark: replace(
            mark,
            available_at=UtcInstant(294),
            age_nanoseconds=mark.resolved_at.epoch_nanoseconds
            - mark.observed_at.epoch_nanoseconds,
        ),
    ],
)
def test_valuation_identity_matrix_fails_closed(change) -> None:
    values = prepared_inputs()
    authority = values["case_authority"]
    mark = change(authority.snapshot_plan.resolved_marks[0])
    values["case_authority"] = replace(
        authority,
        snapshot_plan=replace(authority.snapshot_plan, resolved_marks=(mark,)),
    )
    _assert_failure(
        values, MarketDataPreparationFailureCode.VALUATION_PROFILE_BINDING_MISMATCH
    )


def test_valuation_price_is_not_inferred_from_bar_close() -> None:
    values = prepared_inputs()
    authority = values["case_authority"]
    mark = authority.snapshot_plan.resolved_marks[0]
    changed = replace(mark, price=replace(mark.price, units=mark.price.units + 123))
    values["case_authority"] = replace(
        authority,
        snapshot_plan=replace(authority.snapshot_plan, resolved_marks=(changed,)),
    )
    assert prepare_multi_resolution_market_data_v1(**values).failure is None


def test_explicit_signal_valuation_stream_reuse_succeeds_and_lookup_counts_roles() -> None:
    values = prepared_inputs()
    reader = values["reader"]
    signal = reader.streams["bars.signal"][0]
    valuation = replace(
        reader.streams["bars.valuation"][0], stream_key="bars.signal"
    )
    streams = dict(reader.streams)
    streams.pop("bars.valuation")
    streams["bars.signal"] = (signal, valuation)
    reused = InMemoryMarketBundleReader.build(
        bundle_key=reader.manifest.bundle_key,
        schema_version=reader.manifest.schema_version,
        coverage_start=reader.manifest.coverage_start,
        coverage_end_exclusive=reader.manifest.coverage_end_exclusive,
        instrument_catalog_hash=reader.manifest.instrument_catalog_hash,
        capabilities=reader.manifest.capabilities,
        streams=streams,
    )
    bind_reader(values, reused)
    requirement_hash = values["schedule"].requirements[0].requirement_hash
    values["signal_lineages"] = (
        values["signal_lineages"][0],
        SignalObservationLineageBinding(
            requirement_hash,
            valuation.event_id,
            valuation.event_hash,
            "opaque:valuation-future",
        ),
    )
    values["valuation_binding_candidates"] = (ValuationDataBinding(valuation.instrument_id, "bars.signal"),)
    authority = values["case_authority"]
    mark = replace(authority.snapshot_plan.resolved_marks[0], stream_id="bars.signal")
    values["case_authority"] = replace(
        authority,
        snapshot_plan=replace(authority.snapshot_plan, resolved_marks=(mark,)),
    )
    recorder = BoundedPerformanceRecorder()

    outcome = prepare_multi_resolution_market_data_v1(**values, recorder=recorder)
    assert outcome.failure is None
    lookup = next(
        value
        for value in recorder.snapshot()
        if value.operation is PerformanceOperation.LOOKUP_STREAMS
    )
    assert lookup.call_count == 1
    assert lookup.input_count == 4
    assert lookup.output_count == 4


def test_performance_operations_are_only_f2_and_saturate_without_changing_result() -> None:
    values = prepared_inputs()
    expected = prepare_multi_resolution_market_data_v1(**values)
    recorder = BoundedPerformanceRecorder()
    maximum = 2**63 - 1
    operations = (
        PerformanceOperation.LOOKUP_STREAMS,
        PerformanceOperation.HYDRATE_INPUTS,
        PerformanceOperation.VERIFY_REPLAY,
        PerformanceOperation.PROJECT_POINT_IN_TIME,
        PerformanceOperation.BUILD_WINDOW,
        PerformanceOperation.EVALUATE_LOOKBACK,
    )
    for operation in operations:
        recorder._cells[(operation, PerformanceOutcome.SUCCEEDED)] = _PerformanceObservation(
            operation,
            PerformanceOutcome.SUCCEEDED,
            maximum,
            maximum,
            maximum,
            maximum,
        )

    observed = prepare_multi_resolution_market_data_v1(**values, recorder=recorder)
    assert observed == expected
    assert {value.operation for value in recorder.snapshot()} == set(operations)
    for value in recorder.snapshot():
        assert value.call_count == maximum
        assert value.total_duration_ns == maximum
        assert value.input_count == maximum
        assert value.output_count == maximum


def test_lineage_failure_positions_and_hash_are_canonical_across_caller_order() -> None:
    values = prepared_inputs()
    first = values["reader"].streams["bars.signal"][0]
    second = replace(
        first,
        event_id="z-second-signal",
        available_time=UtcInstant(60),
        source_sequence=SourceSequence(4),
    )
    reader = rebuild_reader(values, **{"bars.signal": (first, second)})
    bind_reader(values, reader)
    requirement_hash = values["schedule"].requirements[0].requirement_hash
    rows = (
        SignalObservationLineageBinding(
            requirement_hash, first.event_id, "sha256:" + "1" * 64, "opaque:first"
        ),
        SignalObservationLineageBinding(
            requirement_hash, second.event_id, "sha256:" + "2" * 64, "opaque:second"
        ),
    )
    values["signal_lineages"] = rows
    first_failure = _assert_failure(
        values, MarketDataPreparationFailureCode.SIGNAL_LINEAGE_MISMATCH
    )
    values["signal_lineages"] = tuple(reversed(rows))
    second_failure = _assert_failure(
        values, MarketDataPreparationFailureCode.SIGNAL_LINEAGE_MISMATCH
    )
    assert first_failure == second_failure
    assert first_failure.failure_hash == second_failure.failure_hash
