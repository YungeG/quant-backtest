from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import (
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
    TimelineEvent,
    TimelineSegment,
)
from crypto_quant_domain import canonical_bytes
from tests.runtime.target_stream._fixtures import (
    BTC,
    CARRY,
    DECISION_TIME,
    TREND,
    candidate_payload,
    context,
    empty_state,
    event,
    source_events,
    timeline_events,
)


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/runtime/precomputed-target-stream-injection-v1.json"


def make_stream(events=None) -> PrecomputedTargetStream:
    return PrecomputedTargetStream(
        stream_key="targets",
        events=source_events() if events is None else events,
    )


def make_schedule(segment: TimelineSegment) -> TargetStreamDecisionSchedule:
    return TargetStreamDecisionSchedule(
        decision_time=DECISION_TIME,
        segment=segment,
        entries=(
            TargetStreamScheduleEntry("target-carry", CARRY, context(CARRY)),
            TargetStreamScheduleEntry("target-trend", TREND, context(TREND)),
        ),
    )


def test_precomputed_target_stream_matches_canonical_golden() -> None:
    stream = make_stream(tuple(reversed(source_events())))
    adapter = PrecomputedTargetStreamAdapter()
    active = adapter.inject(
        stream=stream,
        timeline_events=tuple(reversed(timeline_events())),
        schedule=make_schedule(TimelineSegment.ACTIVE_TRADING),
        prior_state=empty_state(),
    )
    warmup = adapter.inject(
        stream=stream,
        timeline_events=timeline_events(segment=TimelineSegment.WARMUP),
        schedule=make_schedule(TimelineSegment.WARMUP),
        prior_state=empty_state(),
    )

    invalid_candidate = candidate_payload(TREND, instrument_id=BTC, value="0.5")
    invalid_candidate["decision_time"] = 101
    invalid_event = event(
        "target-trend",
        TREND,
        instrument_id=BTC,
        value="0.5",
        source_sequence=1,
        payload_override={"schema_version": 1, "candidate": invalid_candidate},
    )
    carry = source_events()[1]
    invalid = adapter.inject(
        stream=make_stream((invalid_event, carry)),
        timeline_events=(
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, invalid_event),
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, carry),
        ),
        schedule=make_schedule(TimelineSegment.ACTIVE_TRADING),
        prior_state=empty_state(),
    )

    actual = json.loads(
        canonical_bytes(
            {
                "fixture_id": "precomputed-target-stream-injection-v1",
                "target_stream_digest": stream.target_stream_digest,
                "active": active,
                "warmup": warmup,
                "candidate_validation_failure": invalid,
            }
        )
    )
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected
