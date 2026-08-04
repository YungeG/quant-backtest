from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import (
    DeterministicTimeline,
    TimelineCursor,
    TimelineEvent,
    TimelineWindow,
)
from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256
from tests.runtime.timeline._fixtures import timeline_reader


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/runtime/deterministic-multi-stream-timeline-v1.json"


def collect(
    size: int,
) -> tuple[DeterministicTimeline, list[TimelineEvent], TimelineCursor]:
    result = DeterministicTimeline.open(
        reader=timeline_reader(),
        stream_keys=("universe", "bars", "corporate_actions"),
        window=TimelineWindow(
            data_start=UtcInstant(100),
            trading_start=UtcInstant(200),
            end_exclusive=UtcInstant(500),
        ),
    )
    assert isinstance(result, DeterministicTimeline)
    cursor = result.open_cursor(batch_size=size)
    events: list[TimelineEvent] = []
    while True:
        outcome = result.read_batch(cursor)
        assert outcome.failure is None and outcome.batch is not None
        events.extend(outcome.batch.events)
        cursor = outcome.batch.next_cursor
        if outcome.batch.window_complete:
            return result, events, cursor


def test_deterministic_timeline_matches_canonical_golden() -> None:
    timeline, events, cursor = collect(2)
    parity_hashes = {}
    for size in (1, 2, 10):
        _, sized_events, sized_cursor = collect(size)
        parity_hashes[str(size)] = canonical_sha256(
            {
                "events": sized_events,
                "source_positions": sized_cursor.streams,
            }
        )

    try:
        actual = json.loads(
            canonical_bytes(
                {
                    "fixture_id": "deterministic-multi-stream-timeline-v1",
                    "timeline_id": timeline.timeline_id,
                    "window": timeline.window,
                    "events": events,
                    "final_cursor": cursor,
                    "output_batch_size_parity_hashes": parity_hashes,
                }
            )
        )
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError("timeline golden fixture is not valid JSON") from error

    assert actual == expected
    assert len(set(parity_hashes.values())) == 1
