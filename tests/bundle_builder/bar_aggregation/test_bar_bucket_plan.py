from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from crypto_quant_bundle_builder import BarBucket, BarBucketPlan, BarDefinition
from crypto_quant_domain import (
    PricePurpose,
    Scale,
    SessionId,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability


def definition() -> BarDefinition:
    return BarDefinition(
        key="explicit-price-bars",
        version=3,
        output_stream_key="bars.explicit",
        aggregation_kind="explicit_bucket_price_ohlc",
        source_stream_key="synthetic.prices",
        source_event_type="synthetic_price_point.v1",
        source_capability=MarketBundleCapability("synthetic_prices", 1),
        price_purpose=PricePurpose.VALUATION,
        price_scale=Scale(4),
        volume_semantics="none",
        empty_interval_policy="omit",
        output_phase=TimelinePhase(20, "bar.close"),
    )


def bucket(
    *,
    calendar_id: str,
    session: str,
    trading_date: date,
    spans: tuple[tuple[int, int], ...],
) -> BarBucket:
    included = tuple((UtcInstant(start), UtcInstant(end)) for start, end in spans)
    return BarBucket(
        session_id=SessionId(calendar_id, session),
        trading_date=TradingDate(calendar_id, trading_date),
        included_spans=included,
        interval_start=included[0][0],
        interval_end_exclusive=included[-1][1],
    )


def plan(
    buckets: tuple[BarBucket, ...],
    *,
    coverage_start: int = 0,
    coverage_end: int = 1_000,
) -> BarBucketPlan:
    selected = definition()
    return BarBucketPlan(
        plan_key="caller-resolved-plan",
        coverage_start=UtcInstant(coverage_start),
        coverage_end_exclusive=UtcInstant(coverage_end),
        bar_definition_key=selected.key,
        bar_definition_version=selected.version,
        bar_definition_hash=selected.definition_hash,
        buckets=buckets,
    )


def test_bucket_hash_binds_exact_session_date_and_disjoint_spans() -> None:
    value = bucket(
        calendar_id="xshg",
        session="2025-01-02.day",
        trading_date=date(2025, 1, 2),
        spans=((100, 200), (300, 400)),
    )
    body = {
        "type": "bar_bucket",
        "schema_version": 1,
        "session_id": value.session_id.to_canonical_dict(),
        "trading_date": value.trading_date.to_canonical_dict(),
        "included_spans": [
            {
                "start": UtcInstant(100).to_canonical_dict(),
                "end_exclusive": UtcInstant(200).to_canonical_dict(),
            },
            {
                "start": UtcInstant(300).to_canonical_dict(),
                "end_exclusive": UtcInstant(400).to_canonical_dict(),
            },
        ],
        "interval_start": UtcInstant(100).to_canonical_dict(),
        "interval_end_exclusive": UtcInstant(400).to_canonical_dict(),
    }

    assert value.bucket_hash == canonical_sha256(body)
    assert value.to_canonical_dict() == {**body, "bucket_hash": value.bucket_hash}


def test_plan_preserves_exact_caller_order_and_nonrecursive_bucket_bodies() -> None:
    morning = bucket(
        calendar_id="xshg",
        session="2025-01-02.day",
        trading_date=date(2025, 1, 2),
        spans=((100, 200),),
    )
    afternoon = bucket(
        calendar_id="xshg",
        session="2025-01-02.day",
        trading_date=date(2025, 1, 2),
        spans=((300, 400),),
    )
    value = plan((morning, afternoon))
    body = {
        "type": "bar_bucket_plan",
        "schema_version": 1,
        "plan_key": value.plan_key,
        "coverage_start": UtcInstant(0).to_canonical_dict(),
        "coverage_end_exclusive": UtcInstant(1_000).to_canonical_dict(),
        "bar_definition_key": value.bar_definition_key,
        "bar_definition_version": value.bar_definition_version,
        "bar_definition_hash": value.bar_definition_hash,
        "buckets": [morning._canonical_body(), afternoon._canonical_body()],
    }

    assert value.buckets == (morning, afternoon)
    assert value.bucket_plan_hash == canonical_sha256(body)
    assert "bucket_hash" not in value.to_canonical_dict()["buckets"][0]
    with pytest.raises(ValueError, match="ordered"):
        replace(value, buckets=(afternoon, morning))


def test_a_share_lunch_can_be_separate_buckets_or_one_disjoint_session_bucket() -> None:
    morning = bucket(
        calendar_id="xshg",
        session="2025-01-02.day",
        trading_date=date(2025, 1, 2),
        spans=((100, 200),),
    )
    afternoon = bucket(
        calendar_id="xshg",
        session="2025-01-02.day",
        trading_date=date(2025, 1, 2),
        spans=((300, 400),),
    )
    separate = plan((morning, afternoon))
    session = plan(
        (
            bucket(
                calendar_id="xshg",
                session="2025-01-02.day",
                trading_date=date(2025, 1, 2),
                spans=((100, 200), (300, 400)),
            ),
        )
    )

    assert len(separate.buckets) == 2
    assert len(session.buckets) == 1
    assert session.buckets[0].included_spans[0][1] == UtcInstant(200)
    assert session.buckets[0].included_spans[1][0] == UtcInstant(300)
    assert separate.bucket_plan_hash != session.bucket_plan_hash


def test_utc_day_and_night_session_trading_date_are_exact_caller_facts() -> None:
    utc_day = bucket(
        calendar_id="utc-24x7",
        session="2025-01-02",
        trading_date=date(2025, 1, 2),
        spans=((0, 500),),
    )
    night = bucket(
        calendar_id="synthetic-night",
        session="2025-01-02.night",
        trading_date=date(2025, 1, 3),
        spans=((500, 900),),
    )
    value = plan((utc_day, night), coverage_end=900)

    assert value.buckets[0].trading_date.value == date(2025, 1, 2)
    assert value.buckets[1].trading_date.value == date(2025, 1, 3)
    assert value.buckets[1].interval_start == UtcInstant(500)
    assert value.buckets[1].interval_end_exclusive == UtcInstant(900)


def test_empty_plan_is_valid_and_no_bucket_is_derived() -> None:
    value = plan(())

    assert value.buckets == ()
    assert len(value.buckets) == 0


def test_half_open_bucket_invariants_reject_invalid_or_forged_layouts() -> None:
    with pytest.raises(ValueError, match="non-empty tuple"):
        BarBucket(
            SessionId("xshg", "day"),
            TradingDate("xshg", date(2025, 1, 2)),
            (),
            UtcInstant(0),
            UtcInstant(1),
        )
    with pytest.raises(ValueError, match="non-empty half-open"):
        bucket(
            calendar_id="xshg",
            session="day",
            trading_date=date(2025, 1, 2),
            spans=((100, 100),),
        )
    with pytest.raises(ValueError, match="ordered and disjoint"):
        bucket(
            calendar_id="xshg",
            session="day",
            trading_date=date(2025, 1, 2),
            spans=((100, 200), (199, 300)),
        )
    current = bucket(
        calendar_id="xshg",
        session="day",
        trading_date=date(2025, 1, 2),
        spans=((100, 200),),
    )
    with pytest.raises(ValueError, match="first span"):
        replace(current, interval_start=UtcInstant(99))
    with pytest.raises(ValueError, match="final span"):
        replace(current, interval_end_exclusive=UtcInstant(201))
    with pytest.raises(ValueError, match="calendar_id"):
        replace(
            current,
            trading_date=TradingDate("xshe", date(2025, 1, 2)),
        )


def test_plan_rejects_outside_coverage_overlap_and_definition_identity_forgery() -> (
    None
):
    first = bucket(
        calendar_id="test",
        session="one",
        trading_date=date(2025, 1, 2),
        spans=((100, 300),),
    )
    overlap = bucket(
        calendar_id="test",
        session="two",
        trading_date=date(2025, 1, 2),
        spans=((200, 400),),
    )
    with pytest.raises(ValueError, match="non-overlapping"):
        plan((first, overlap))
    with pytest.raises(ValueError, match="inside plan coverage"):
        plan((first,), coverage_start=101)
    with pytest.raises(ValueError, match="non-empty half-open"):
        plan((), coverage_start=1, coverage_end=1)
    current = plan((first,))
    with pytest.raises(ValueError, match="positive"):
        replace(current, bar_definition_version=True)
    with pytest.raises(ValueError, match="sha256"):
        replace(current, bar_definition_hash="forged")
