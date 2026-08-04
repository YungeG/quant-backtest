from __future__ import annotations

import copy
import time
from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    DeterministicTimeline,
    TimelineCursor,
    TimelineCursorError,
    TimelineFailureCode,
    TimelineSegment,
    TimelineWindow,
)
from crypto_quant_domain import UtcInstant
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    InputValidationFailure,
    MarketBundleReader,
    MarketEvent,
)
from tests.runtime.timeline._fixtures import BARS, UNIVERSE, event, timeline_reader


def window() -> TimelineWindow:
    return TimelineWindow(
        data_start=UtcInstant(100),
        trading_start=UtcInstant(200),
        end_exclusive=UtcInstant(500),
    )


def open_timeline(
    reader: MarketBundleReader | None = None,
    *,
    stream_keys: tuple[str, ...] = ("bars", "universe", "corporate_actions"),
) -> DeterministicTimeline:
    result = DeterministicTimeline.open(
        reader=timeline_reader() if reader is None else reader,
        stream_keys=stream_keys,
        window=window(),
    )
    assert isinstance(result, DeterministicTimeline)
    return result


def collect(
    timeline: DeterministicTimeline, *, batch_size: int
) -> tuple[list[tuple[str, str]], TimelineCursor]:
    cursor = timeline.open_cursor(batch_size=batch_size)
    events: list[tuple[str, str]] = []
    while True:
        outcome = timeline.read_batch(cursor)
        assert outcome.failure is None
        assert outcome.batch is not None
        events.extend(
            (item.event.event_id, item.segment.value) for item in outcome.batch.events
        )
        cursor = outcome.batch.next_cursor
        if outcome.batch.window_complete:
            return events, cursor


def test_merge_is_order_independent_and_preserves_window_boundaries() -> None:
    expected = [
        ("universe-warmup", TimelineSegment.WARMUP.value),
        ("bar-warmup", TimelineSegment.WARMUP.value),
        ("corporate-action-active", TimelineSegment.ACTIVE_TRADING.value),
        ("universe-active", TimelineSegment.ACTIVE_TRADING.value),
        ("bar-active", TimelineSegment.ACTIVE_TRADING.value),
    ]

    results = []
    for size, streams in (
        (1, ("bars", "universe", "corporate_actions")),
        (2, ("corporate_actions", "bars", "universe")),
        (10, ("universe", "corporate_actions", "bars")),
    ):
        timeline = open_timeline(stream_keys=streams)
        result, cursor = collect(timeline, batch_size=size)
        results.append(result)
        assert cursor.window_complete
        assert {item.stream_key: item.cursor.position for item in cursor.streams} == {
            "bars": 3,
            "corporate_actions": 1,
            "universe": 2,
        }

    assert results == [expected, expected, expected]


def test_cursor_is_immediately_complete_when_first_event_is_end_exclusive() -> None:
    reader = InMemoryMarketBundleReader.build(
        bundle_key="end-only.timeline.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash="sha256:" + "ab" * 32,
        capabilities=(BARS,),
        streams={
            "bars": (
                event(
                    "at-end",
                    stream_key="bars",
                    capability=BARS,
                    available_time=500,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=1,
                ),
            )
        },
    )
    timeline = open_timeline(reader, stream_keys=("bars",))
    cursor = timeline.open_cursor(batch_size=2)

    outcome = timeline.read_batch(cursor)

    assert outcome.failure is None and outcome.batch is not None
    assert not outcome.batch.events
    assert outcome.batch.window_complete
    assert outcome.batch.next_cursor.streams[0].cursor.position == 0


def test_prefix_resume_with_a_different_output_batch_size_is_exact() -> None:
    timeline = open_timeline()
    first = timeline.read_batch(timeline.open_cursor(batch_size=2))
    assert first.failure is None and first.batch is not None
    assert [item.event.event_id for item in first.batch.events] == [
        "universe-warmup",
        "bar-warmup",
    ]

    resumed = timeline.resume_cursor(first.batch.next_cursor, batch_size=10)
    remainder: list[str] = []
    while True:
        outcome = timeline.read_batch(resumed)
        assert outcome.failure is None and outcome.batch is not None
        remainder.extend(item.event.event_id for item in outcome.batch.events)
        resumed = outcome.batch.next_cursor
        if outcome.batch.window_complete:
            break

    full, _ = collect(timeline, batch_size=10)
    assert [item[0] for item in full] == [
        "universe-warmup",
        "bar-warmup",
        *remainder,
    ]


def test_window_and_stream_selection_fail_closed() -> None:
    with pytest.raises(ValueError, match="data_start"):
        TimelineWindow(
            data_start=UtcInstant(200),
            trading_start=UtcInstant(100),
            end_exclusive=UtcInstant(500),
        )
    with pytest.raises(ValueError, match="at least one"):
        DeterministicTimeline.open(
            reader=timeline_reader(), stream_keys=(), window=window()
        )
    with pytest.raises(ValueError, match="unique"):
        DeterministicTimeline.open(
            reader=timeline_reader(),
            stream_keys=("bars", "bars"),
            window=window(),
        )


def test_missing_stream_preserves_input_validation_failure() -> None:
    result = DeterministicTimeline.open(
        reader=timeline_reader(),
        stream_keys=("bars", "missing"),
        window=window(),
    )
    assert isinstance(result, InputValidationFailure)
    assert [issue.subject_key for issue in result.issues] == ["missing"]


def test_duplicate_global_ordering_key_fails_closed() -> None:
    duplicate_reader = InMemoryMarketBundleReader.build(
        bundle_key="duplicate.timeline.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash="sha256:" + "ab" * 32,
        capabilities=(BARS, UNIVERSE),
        streams={
            "bars": (
                event(
                    "duplicate-bars",
                    stream_key="bars",
                    capability=BARS,
                    available_time=200,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=7,
                ),
            ),
            "universe": (
                event(
                    "duplicate-universe",
                    stream_key="universe",
                    capability=UNIVERSE,
                    available_time=200,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=7,
                ),
            ),
        },
    )
    timeline = open_timeline(duplicate_reader, stream_keys=("bars", "universe"))

    outcome = timeline.read_batch(timeline.open_cursor(batch_size=10))

    assert outcome.batch is None
    assert outcome.failure is not None
    assert outcome.failure.code is TimelineFailureCode.DUPLICATE_ORDERING_KEY
    assert outcome.failure.subject_keys == ("bars", "universe")


class CorruptingReader:
    def __init__(self, delegate: InMemoryMarketBundleReader) -> None:
        self.delegate = delegate

    @property
    def bundle_ref(self):  # type: ignore[no-untyped-def]
        return self.delegate.bundle_ref

    @property
    def manifest(self):  # type: ignore[no-untyped-def]
        return self.delegate.manifest

    def validate_requirements(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.delegate.validate_requirements(**kwargs)

    def open_cursor(self, stream_key: str, *, batch_size: int):  # type: ignore[no-untyped-def]
        return self.delegate.open_cursor(stream_key, batch_size=batch_size)

    def resume_cursor(
        self, cursor: EventCursor, *, batch_size: int | None = None
    ) -> EventCursor:
        return self.delegate.resume_cursor(cursor, batch_size=batch_size)

    def read_batch(
        self, cursor: EventCursor
    ) -> tuple[tuple[MarketEvent, ...], EventCursor]:
        batch, next_cursor = self.delegate.read_batch(cursor)
        if not batch:
            return batch, next_cursor
        corrupted = copy.copy(batch[0])
        object.__setattr__(corrupted, "source_sequence", None)
        return (corrupted,), next_cursor


def test_reader_event_without_typed_source_sequence_fails_closed() -> None:
    reader = CorruptingReader(timeline_reader())
    timeline = open_timeline(reader, stream_keys=("bars",))

    outcome = timeline.read_batch(timeline.open_cursor(batch_size=1))

    assert outcome.batch is None
    assert outcome.failure is not None
    assert outcome.failure.code is TimelineFailureCode.MISSING_SOURCE_SEQUENCE


class ReorderingReader(CorruptingReader):
    def read_batch(
        self, cursor: EventCursor
    ) -> tuple[tuple[MarketEvent, ...], EventCursor]:
        events = tuple(reversed(self.delegate.streams[cursor.stream_manifest.stream_key]))
        if cursor.exhausted:
            return (), cursor
        next_cursor = EventCursor(
            bundle_ref=cursor.bundle_ref,
            stream_manifest=cursor.stream_manifest,
            position=cursor.position + 1,
            batch_size=cursor.batch_size,
        )
        return (events[cursor.position],), next_cursor


def test_reader_order_regression_fails_closed() -> None:
    base = InMemoryMarketBundleReader.build(
        bundle_key="regression.timeline.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash="sha256:" + "ab" * 32,
        capabilities=(BARS,),
        streams={
            "bars": (
                event(
                    "first",
                    stream_key="bars",
                    capability=BARS,
                    available_time=200,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=1,
                ),
                event(
                    "second",
                    stream_key="bars",
                    capability=BARS,
                    available_time=300,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=2,
                ),
            )
        },
    )
    timeline = open_timeline(ReorderingReader(base), stream_keys=("bars",))

    outcome = timeline.read_batch(timeline.open_cursor(batch_size=10))

    assert outcome.batch is None
    assert outcome.failure is not None
    assert outcome.failure.code is TimelineFailureCode.ORDER_REGRESSION


def test_cursor_from_another_window_is_rejected() -> None:
    timeline = open_timeline()
    cursor = timeline.open_cursor(batch_size=1)
    forged = replace(cursor, window_hash="sha256:" + "0" * 64)

    with pytest.raises(TimelineCursorError, match="window"):
        timeline.read_batch(forged)


def test_timeline_does_not_read_wall_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden() -> float:
        raise AssertionError("wall clock read")

    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    events, _ = collect(open_timeline(), batch_size=2)
    assert len(events) == 5
