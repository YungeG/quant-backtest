from __future__ import annotations

from crypto_quant_backtest import (
    ObservationCausalityFailureCode,
    ObservationQuery,
    ObservationRecord,
    PointInTimeObservationQueryOutcome,
    PointInTimeObservationView,
    RevisionedObservationRecord,
)
from crypto_quant_domain import SimulationInstant, SourceSequence, TimelinePhase, UtcInstant
from crypto_quant_market_data import MarketEvent

from tests.runtime.observations._fixtures import BARS_V1, INSTRUMENT_A, OHLCV, query


MARKET_PHASE = TimelinePhase(20, "market_data")
DECISION_BEFORE_CORRECTION = SimulationInstant(
    UtcInstant(200), MARKET_PHASE, SourceSequence(2)
)
DECISION_AT_CORRECTION = SimulationInstant(
    UtcInstant(200), MARKET_PHASE, SourceSequence(3)
)
DECISION_LATE = SimulationInstant(UtcInstant(500), MARKET_PHASE, SourceSequence(9))


def revision(
    observation_key: str,
    event_id: str,
    *,
    event_time: int,
    available_time: int,
    source_sequence: int,
    revision_id: str,
    supersedes_revision_id: str | None,
    close_units: int,
    dataset_key: str = "bars.1m",
) -> RevisionedObservationRecord:
    event = MarketEvent(
        event_id=event_id,
        stream_key=dataset_key,
        event_type="bar",
        capability=BARS_V1,
        instrument_id=INSTRUMENT_A,
        event_time=UtcInstant(event_time),
        available_time=UtcInstant(available_time),
        phase=MARKET_PHASE,
        source_sequence=SourceSequence(source_sequence),
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
        source_key=f"fixture.{dataset_key}",
        source_hash="sha256:" + event_id.encode().hex().ljust(64, "0")[:64],
        payload={"close": {"scale": 2, "units": close_units}},
    )
    return RevisionedObservationRecord(
        observation_key=observation_key,
        record=ObservationRecord(purpose=OHLCV, event=event),
    )


def records() -> tuple[RevisionedObservationRecord, ...]:
    return (
        revision(
            "bar-a",
            "bar-a-v1",
            event_time=90,
            available_time=100,
            source_sequence=1,
            revision_id="source-v1",
            supersedes_revision_id=None,
            close_units=10_100,
        ),
        revision(
            "bar-b",
            "bar-b-v1",
            event_time=140,
            available_time=150,
            source_sequence=1,
            revision_id="source-v1",
            supersedes_revision_id=None,
            close_units=20_100,
        ),
        revision(
            "bar-a",
            "bar-a-v2",
            event_time=90,
            available_time=200,
            source_sequence=3,
            revision_id="source-v2",
            supersedes_revision_id="source-v1",
            close_units=10_200,
        ),
        revision(
            "bar-a",
            "bar-a-v2-conflict",
            event_time=90,
            available_time=200,
            source_sequence=4,
            revision_id="source-v2",
            supersedes_revision_id="source-v1",
            close_units=99_999,
        ),
        revision(
            "bar-a",
            "unauthorized-conflict",
            event_time=90,
            available_time=100,
            source_sequence=1,
            revision_id="source-v2",
            supersedes_revision_id="missing",
            close_units=77_777,
            dataset_key="trades",
        ),
    )


def point_in_time_view(
    decision_instant: SimulationInstant,
    *,
    supplied_records: tuple[RevisionedObservationRecord, ...] | None = None,
    allowed_queries: tuple[ObservationQuery, ...] | None = None,
) -> PointInTimeObservationView:
    return PointInTimeObservationView(
        allowed_queries=(query(),) if allowed_queries is None else allowed_queries,
        records=records() if supplied_records is None else supplied_records,
        decision_instant=decision_instant,
    )


def run_query(
    view: PointInTimeObservationView, observation_query: ObservationQuery | None = None
) -> PointInTimeObservationQueryOutcome:
    query_method = getattr(view, "query")
    return query_method(query() if observation_query is None else observation_query)


def causality_failure_cases() -> tuple[
    tuple[
        str,
        tuple[RevisionedObservationRecord, ...],
        ObservationCausalityFailureCode,
    ],
    ...,
]:
    return (
        (
            "revision_id_conflict",
            (
                revision(
                    "conflict",
                    "conflict-a",
                    event_time=90,
                    available_time=100,
                    source_sequence=1,
                    revision_id="v1",
                    supersedes_revision_id=None,
                    close_units=100,
                ),
                revision(
                    "conflict",
                    "conflict-b",
                    event_time=90,
                    available_time=101,
                    source_sequence=1,
                    revision_id="v1",
                    supersedes_revision_id=None,
                    close_units=101,
                ),
            ),
            ObservationCausalityFailureCode.REVISION_ID_CONFLICT,
        ),
        (
            "revision_parent_missing",
            (
                revision(
                    "missing",
                    "missing-v2",
                    event_time=90,
                    available_time=100,
                    source_sequence=1,
                    revision_id="v2",
                    supersedes_revision_id="v1",
                    close_units=102,
                ),
            ),
            ObservationCausalityFailureCode.REVISION_PARENT_MISSING,
        ),
        (
            "revision_chain_conflict",
            (
                revision(
                    "branch",
                    "branch-v1",
                    event_time=90,
                    available_time=100,
                    source_sequence=1,
                    revision_id="v1",
                    supersedes_revision_id=None,
                    close_units=100,
                ),
                revision(
                    "branch",
                    "branch-v2a",
                    event_time=90,
                    available_time=101,
                    source_sequence=1,
                    revision_id="v2a",
                    supersedes_revision_id="v1",
                    close_units=101,
                ),
                revision(
                    "branch",
                    "branch-v2b",
                    event_time=90,
                    available_time=102,
                    source_sequence=1,
                    revision_id="v2b",
                    supersedes_revision_id="v1",
                    close_units=102,
                ),
            ),
            ObservationCausalityFailureCode.REVISION_CHAIN_CONFLICT,
        ),
        (
            "revision_context_mismatch",
            (
                revision(
                    "context",
                    "context-v1",
                    event_time=90,
                    available_time=100,
                    source_sequence=1,
                    revision_id="v1",
                    supersedes_revision_id=None,
                    close_units=100,
                ),
                revision(
                    "context",
                    "context-v2",
                    event_time=91,
                    available_time=101,
                    source_sequence=1,
                    revision_id="v2",
                    supersedes_revision_id="v1",
                    close_units=101,
                ),
            ),
            ObservationCausalityFailureCode.REVISION_CONTEXT_MISMATCH,
        ),
        (
            "revision_availability_regression",
            (
                revision(
                    "regression",
                    "regression-v1",
                    event_time=90,
                    available_time=200,
                    source_sequence=2,
                    revision_id="v1",
                    supersedes_revision_id=None,
                    close_units=100,
                ),
                revision(
                    "regression",
                    "regression-v2",
                    event_time=90,
                    available_time=200,
                    source_sequence=1,
                    revision_id="v2",
                    supersedes_revision_id="v1",
                    close_units=101,
                ),
            ),
            ObservationCausalityFailureCode.REVISION_AVAILABILITY_REGRESSION,
        ),
    )


def precedence_records() -> tuple[RevisionedObservationRecord, ...]:
    conflict = causality_failure_cases()[0][1]
    missing = causality_failure_cases()[1][1]
    return (*conflict, *missing)
