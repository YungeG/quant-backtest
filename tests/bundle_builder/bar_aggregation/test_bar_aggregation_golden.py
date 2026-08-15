from __future__ import annotations

from datetime import date
from pathlib import Path
import json

from crypto_quant_bundle_builder import BarBucket, BarBucketPlan
from crypto_quant_domain import (
    InstrumentId,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
)
from crypto_quant_domain import canonical_bytes
from tests.bundle_builder.bar_aggregation.test_bar_aggregation import (
    aggregate,
    event,
    manifest,
    plan as source_plan,
)

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / (
    "tests/fixtures/market_data/bar_aggregation/"
    "canonical-bar-aggregation-v1.expected.json"
)


def bucket(
    *,
    calendar_id: str,
    session: str,
    trading_date: date,
    spans: tuple[tuple[int, int], ...],
) -> BarBucket:
    included_spans = tuple((UtcInstant(start), UtcInstant(end)) for start, end in spans)
    return BarBucket(
        session_id=SessionId(calendar_id, session),
        trading_date=TradingDate(calendar_id, trading_date),
        included_spans=included_spans,
        interval_start=included_spans[0][0],
        interval_end_exclusive=included_spans[-1][1],
    )


def plan() -> BarBucketPlan:
    return source_plan(
        bucket(
            calendar_id="xshg",
            session="2025-01-02.day",
            trading_date=date(2025, 1, 2),
            spans=((100, 200),),
        ),
        bucket(
            calendar_id="xshg",
            session="2025-01-02.day",
            trading_date=date(2025, 1, 2),
            spans=((300, 400),),
        ),
        bucket(
            calendar_id="xshg",
            session="2025-01-02.day",
            trading_date=date(2025, 1, 2),
            spans=((500, 600), (700, 800)),
        ),
        bucket(
            calendar_id="xshg",
            session="2025-01-02.day",
            trading_date=date(2025, 1, 2),
            spans=((820, 860),),
        ),
        bucket(
            calendar_id="utc-24x7",
            session="2025-01-02",
            trading_date=date(2025, 1, 2),
            spans=((880, 930),),
        ),
        bucket(
            calendar_id="synthetic-night",
            session="2025-01-02.night",
            trading_date=date(2025, 1, 3),
            spans=((940, 980),),
        ),
    )


def _payload() -> dict[str, object]:
    out_of_plan_instrument = InstrumentId(VenueId("test"), "out-of-plan")
    post_close_instrument = InstrumentId(VenueId("test"), "post-close")
    utc_instrument = InstrumentId(VenueId("test"), "utc-live")
    night_instrument = InstrumentId(VenueId("test"), "night-close")
    events = (
        # A-share separate lunch buckets and late root.
        event(
            0,
            event_time=150,
            available_time=200,
            price_units=101,
            record_key="morning-close-root",
        ),
        # selected out-of-plan chain (root + correction)
        event(
            5,
            event_time=250,
            available_time=260,
            price_units=401,
            record_key="out-of-plan-root",
            instrument_id=out_of_plan_instrument,
        ),
        event(
            6,
            event_time=250,
            available_time=300,
            price_units=402,
            record_key="out-of-plan-root",
            instrument_id=out_of_plan_instrument,
            supersedes_revision_id="revision-5",
        ),
        event(
            1,
            event_time=350,
            available_time=450,
            price_units=202,
            record_key="afternoon-late-root",
        ),
        # post-close + same-UTC grouped revisions.
        event(
            2,
            event_time=520,
            available_time=540,
            price_units=303,
            record_key="disjoint-post-close",
            instrument_id=post_close_instrument,
        ),
        event(
            3,
            event_time=520,
            available_time=900,
            price_units=304,
            record_key="disjoint-post-close",
            instrument_id=post_close_instrument,
            supersedes_revision_id="revision-2",
        ),
        event(
            4,
            event_time=520,
            available_time=900,
            price_units=305,
            record_key="disjoint-post-close",
            instrument_id=post_close_instrument,
            supersedes_revision_id="revision-3",
        ),
        # UTC24x7 and night-session facts
        event(
            7,
            event_time=890,
            available_time=900,
            price_units=501,
            record_key="utc-24x7-root",
            instrument_id=utc_instrument,
        ),
        event(
            8,
            event_time=950,
            available_time=980,
            price_units=601,
            record_key="night-close-root",
            instrument_id=night_instrument,
        ),
    )
    return {
        "schema_version": 1,
        "fixture_id": "canonical-bar-aggregation-v1",
        "result": aggregate(
            events,
            bucket_plan=plan(),
            source_manifest=manifest(events),
        ).result.to_canonical_dict(),
    }


def test_bar_aggregation_fixture_matches_static_golden_and_repeats_exactly() -> None:
    try:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G12G golden fixture: {error}") from error

    first = json.loads(canonical_bytes(_payload()))
    second = json.loads(canonical_bytes(_payload()))
    assert first == second
    assert first == expected
