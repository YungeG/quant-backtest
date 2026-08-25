from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest
from crypto_quant_backtest.execution import BarOpenObservation
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v1 import (
    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1,
    BinanceUsdmKoruTradifiSourceProjectionOutcomeV1,
    BinanceUsdmKoruTradifiSourceProjectionRequestV1,
    BinanceUsdmKoruTradifiSourceProjectionResultV1,
    _stream_manifests,
    build_binance_usdm_koru_tradifi_source_projection_v1,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    Scale,
    SourceSequence,
    UtcInstant,
    canonical_bytes,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_aggtrades_source_bounded_v1 as aggregate_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_funding_rate_history_source_bounded_v1 as funding_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_price_bars_source_bounded_v1 as price_fixture,
)
from tests.bundle_builder.providers.tradifi import (
    test_koru_tradifi_calendar_unit_authority_v1 as authority_fixture,
)

_KIND = price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1
_HOUR_NS = price_fixture.HOUR_MS * 1_000_000
_DAY_NS = 24 * _HOUR_NS
_DAY_MS = _DAY_NS // 1_000_000
_CATALOG_HASH = "sha256:" + "1" * 64
_BASE_DATE = date.fromisoformat(price_fixture.UTC_DATE)


def _day_start_ms(utc_date: str) -> int:
    return (
        price_fixture.DAY_START_MS
        + (date.fromisoformat(utc_date) - _BASE_DATE).days * _DAY_MS
    )


def _utc_date(timestamp_ms: int) -> str:
    days = timestamp_ms // _DAY_MS
    return (date(1970, 1, 1) + timedelta(days=days)).isoformat()


def _window_dates(start_ns: int, end_ns: int) -> tuple[str, ...]:
    first = start_ns // _DAY_NS
    last = (end_ns - 1) // _DAY_NS
    return tuple(
        (date(1970, 1, 1) + timedelta(days=days)).isoformat()
        for days in range(first, last + 1)
    )


def _price_rows(
    day_start_ms: int = price_fixture.DAY_START_MS,
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (
            str(day_start_ms + hour * price_fixture.HOUR_MS),
            "12.34000000",
            "12.50000000",
            "12.25000000",
            "12.45000000",
            "0",
            str(day_start_ms + (hour + 1) * price_fixture.HOUR_MS - 1),
            "0",
            "1",
            "0",
            "0",
            "0",
        )
        for hour in range(24)
    )


def _aggregate_result(
    trades: tuple[tuple[int, str], ...],
    *,
    utc_date: str = aggregate_fixture.UTC_DATE,
    sequence_start: int = 0,
):
    rows = tuple(
        (
            str(700 + sequence_start + index),
            price,
            "1.250",
            str(900 + 2 * (sequence_start + index)),
            str(901 + 2 * (sequence_start + index)),
            str(timestamp),
            "true",
        )
        for index, (timestamp, price) in enumerate(trades)
    )
    archive, checksum = aggregate_fixture.evidence(
        rows,
        member_name=f"KORUUSDT-aggTrades-{utc_date}.csv",
        checksum_name=f"KORUUSDT-aggTrades-{utc_date}.zip",
    )
    day_start_ns = _day_start_ms(utc_date) * 1_000_000
    request = aggregate_fixture.request_for(
        archive,
        checksum,
        utc_date=utc_date,
        archive_available_at=day_start_ns + _DAY_NS,
        acquired_at=day_start_ns + 2 * _DAY_NS,
    )
    archive_url, checksum_url = request.urls
    captured = (
        aggregate_fixture.capture_binance_usdm_koru_aggregate_trades_source_bounded_v1(
            request,
            aggregate_fixture.Fetch(
                {archive_url: [(200, archive)], checksum_url: [(200, checksum)]}
            ),
        ).result
    )
    assert captured is not None
    result = aggregate_fixture.normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
        captured
    ).result
    assert result is not None
    return result


def _price_result(
    source_kind: price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1,
    utc_date: str,
):
    rows = _price_rows(_day_start_ms(utc_date))
    archive, checksum = price_fixture.evidence(
        rows,
        member_name=f"KORUUSDT-1h-{utc_date}.csv",
        checksum_name=f"KORUUSDT-1h-{utc_date}.zip",
    )
    day_start_ns = _day_start_ms(utc_date) * 1_000_000
    request = price_fixture.request_for(
        source_kind,
        archive,
        checksum,
        utc_date=utc_date,
        archive_available_at=day_start_ns + _DAY_NS,
        acquired_at=day_start_ns + 2 * _DAY_NS,
    )
    archive_url, checksum_url = request.urls
    captured = price_fixture.capture_binance_usdm_koru_price_bars_source_bounded_v1(
        request,
        price_fixture.Fetch(
            {archive_url: [(200, archive)], checksum_url: [(200, checksum)]}
        ),
    ).result
    assert captured is not None
    result = price_fixture.normalize_binance_usdm_koru_price_bars_source_bounded_v1(
        captured
    ).result
    assert result is not None
    return result


def _funding_result(raw: bytes = funding_fixture.RAW):
    result = funding_fixture.normalize(raw).result
    assert result is not None
    return result


def _request(
    trades: tuple[tuple[int, str], ...],
    *,
    start_hour: int = 20,
    end_hour: int = 23,
    start_ns: int | None = None,
    end_ns: int | None = None,
    funding_raw: bytes = funding_fixture.RAW,
) -> BinanceUsdmKoruTradifiSourceProjectionRequestV1:
    start = (
        aggregate_fixture.DAY_START_NS + start_hour * _HOUR_NS
        if start_ns is None
        else start_ns
    )
    end = (
        aggregate_fixture.DAY_START_NS + end_hour * _HOUR_NS
        if end_ns is None
        else end_ns
    )
    aggregate_results = []
    sequence_start = 0
    for utc_date in _window_dates(start, end):
        daily_trades = tuple(
            trade for trade in trades if _utc_date(trade[0]) == utc_date
        )
        assert daily_trades
        aggregate_results.append(
            _aggregate_result(
                daily_trades,
                utc_date=utc_date,
                sequence_start=sequence_start,
            )
        )
        sequence_start += len(daily_trades)
    first_completed = max(
        ((start + _HOUR_NS - 1) // _HOUR_NS) * _HOUR_NS,
        1_784_113_200_000_000_000,
    )
    price_dates = tuple(
        dict.fromkeys(
            _utc_date((completed - _HOUR_NS) // 1_000_000)
            for completed in range(first_completed, end, _HOUR_NS)
        )
    )
    return BinanceUsdmKoruTradifiSourceProjectionRequestV1(
        timeline_window_start=UtcInstant(start),
        timeline_window_end_exclusive=UtcInstant(end),
        instrument_catalog_hash=_CATALOG_HASH,
        projection_scale=Scale(8),
        aggregate_trade_results=tuple(aggregate_results),
        mark_price_results=tuple(
            _price_result(_KIND.MARK_PRICE, utc_date) for utc_date in price_dates
        ),
        index_price_results=tuple(
            _price_result(_KIND.INDEX_PRICE, utc_date) for utc_date in price_dates
        ),
        funding_result=_funding_result(funding_raw),
        authority_result=authority_fixture._result(),
    )


def _built():
    trade = aggregate_fixture.DAY_START_MS + 22 * price_fixture.HOUR_MS + 30 * 60_000
    outcome = build_binance_usdm_koru_tradifi_source_projection_v1(
        _request(((trade, "12.340"),))
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def _price_strategy_events(
    result: BinanceUsdmKoruTradifiSourceProjectionResultV1, source_kind: str
):
    return tuple(
        event
        for event in result.source_events
        if event.payload.get("source_kind") == source_kind
        and event.payload.get("price_purpose") == "strategy"
    )


def test_first_retained_trade_projects_distinct_boundaries_and_decodes() -> None:
    result = _built()
    assert len(result.projection_events) == 3
    assert len(result.projection_lineage) == 3
    assert result.missing_boundaries == ()
    assert len({event.event_id for event in result.projection_events}) == 3
    assert tuple(event.source_sequence.value for event in result.projection_events) == (
        0,
        1,
        2,
    )
    assert len({lineage.source_event_id for lineage in result.projection_lineage}) == 1
    for event in result.projection_events:
        observation = BarOpenObservation.from_event(event)
        assert observation.open_price is not None
        assert observation.open_price.units == 1_234_000_000
        assert int(observation.open_price.scale) == 8
        assert set(event.payload) == {"schema_version", "bar_kind", "open_price"}
        assert event.event_time == event.available_time

    mark = _price_strategy_events(result, _KIND.MARK_PRICE.value)
    index = _price_strategy_events(result, _KIND.INDEX_PRICE.value)
    assert tuple(event.event_time.epoch_nanoseconds for event in mark) == tuple(
        aggregate_fixture.DAY_START_NS + hour * _HOUR_NS for hour in (20, 21, 22)
    )
    assert tuple(event.payload["open_time_milliseconds"] for event in mark) == tuple(
        aggregate_fixture.DAY_START_MS + hour * price_fixture.HOUR_MS
        for hour in (19, 20, 21)
    )
    assert tuple(event.event_time for event in mark) == tuple(
        event.event_time for event in index
    )


def test_price_cover_uses_completed_instants_for_fractional_half_open_window() -> None:
    start = aggregate_fixture.DAY_START_NS + 20 * _HOUR_NS + _HOUR_NS // 2
    end = aggregate_fixture.DAY_START_NS + 22 * _HOUR_NS + _HOUR_NS // 2
    trade = aggregate_fixture.DAY_START_MS + 21 * price_fixture.HOUR_MS + 15 * 60_000
    result = build_binance_usdm_koru_tradifi_source_projection_v1(
        _request(((trade, "12.340"),), start_ns=start, end_ns=end)
    ).result
    assert result is not None
    mark = _price_strategy_events(result, _KIND.MARK_PRICE.value)
    index = _price_strategy_events(result, _KIND.INDEX_PRICE.value)
    expected_completed = tuple(
        UtcInstant(aggregate_fixture.DAY_START_NS + hour * _HOUR_NS)
        for hour in (21, 22)
    )
    assert tuple(event.event_time for event in mark) == expected_completed
    assert tuple(event.event_time for event in index) == expected_completed
    assert tuple(event.payload["open_time_milliseconds"] for event in mark) == (
        aggregate_fixture.DAY_START_MS + 20 * price_fixture.HOUR_MS,
        aggregate_fixture.DAY_START_MS + 21 * price_fixture.HOUR_MS,
    )
    assert all(start <= event.event_time.epoch_nanoseconds < end for event in mark)


def test_price_cover_crosses_midnight_from_prior_open_date() -> None:
    start = aggregate_fixture.DAY_START_NS + 23 * _HOUR_NS + _HOUR_NS // 2
    end = aggregate_fixture.DAY_START_NS + 24 * _HOUR_NS + _HOUR_NS // 2
    trades = (
        (
            aggregate_fixture.DAY_START_MS + 23 * price_fixture.HOUR_MS + 45 * 60_000,
            "12.340",
        ),
        (
            aggregate_fixture.DAY_START_MS + 24 * price_fixture.HOUR_MS + 10 * 60_000,
            "12.350",
        ),
    )
    request = _request(trades, start_ns=start, end_ns=end)
    assert tuple(
        value.capture.request.utc_date for value in request.mark_price_results
    ) == ("2026-07-16",)
    result = build_binance_usdm_koru_tradifi_source_projection_v1(request).result
    assert result is not None
    mark = _price_strategy_events(result, _KIND.MARK_PRICE.value)
    index = _price_strategy_events(result, _KIND.INDEX_PRICE.value)
    assert tuple(event.event_time for event in mark) == (
        UtcInstant(aggregate_fixture.DAY_START_NS + 24 * _HOUR_NS),
    )
    assert tuple(event.payload["open_time_milliseconds"] for event in mark) == (
        aggregate_fixture.DAY_START_MS + 23 * price_fixture.HOUR_MS,
    )
    assert tuple(event.event_time for event in mark) == tuple(
        event.event_time for event in index
    )


def test_price_cover_respects_july_15_authorized_open_floor() -> None:
    july_15_start_ms = _day_start_ms("2026-07-15")
    start = july_15_start_ms * 1_000_000 + 10 * _HOUR_NS
    before_first_completion = _request(
        ((july_15_start_ms + 10 * price_fixture.HOUR_MS + 30 * 60_000, "12.330"),),
        start_ns=start,
        end_ns=start + _HOUR_NS,
    )
    assert before_first_completion.mark_price_results == ()
    assert before_first_completion.index_price_results == ()
    empty = build_binance_usdm_koru_tradifi_source_projection_v1(
        before_first_completion
    ).result
    assert empty is not None
    assert _price_strategy_events(empty, _KIND.MARK_PRICE.value) == ()
    assert _price_strategy_events(empty, _KIND.INDEX_PRICE.value) == ()

    end = july_15_start_ms * 1_000_000 + 12 * _HOUR_NS
    trade = july_15_start_ms + 11 * price_fixture.HOUR_MS + 15 * 60_000
    result = build_binance_usdm_koru_tradifi_source_projection_v1(
        _request(((trade, "12.340"),), start_ns=start, end_ns=end)
    ).result
    assert result is not None
    mark = _price_strategy_events(result, _KIND.MARK_PRICE.value)
    index = _price_strategy_events(result, _KIND.INDEX_PRICE.value)
    assert tuple(event.event_time for event in mark) == (UtcInstant(start + _HOUR_NS),)
    assert tuple(event.payload["open_time_milliseconds"] for event in mark) == (
        july_15_start_ms + 10 * price_fixture.HOUR_MS,
    )
    assert tuple(event.event_time for event in mark) == tuple(
        event.event_time for event in index
    )


def test_missing_trade_and_next_cash_open_emit_evidence_not_placeholder() -> None:
    before = aggregate_fixture.DAY_START_MS + 19 * price_fixture.HOUR_MS
    missing = build_binance_usdm_koru_tradifi_source_projection_v1(
        _request(((before, "12.340"),))
    ).result
    assert missing is not None
    assert missing.projection_events == ()
    assert len(missing.missing_boundaries) == 3
    assert {value.reason for value in missing.missing_boundaries} == {
        "missing_retained_aggregate_trade"
    }
    assert missing.projection_stream_manifest.event_count == 0

    arcx_open = (
        aggregate_fixture.DAY_START_MS + 13 * price_fixture.HOUR_MS + 30 * 60_000
    )
    excluded = build_binance_usdm_koru_tradifi_source_projection_v1(
        _request(((arcx_open, "12.340"),), start_hour=13, end_hour=14)
    ).result
    assert excluded is not None
    assert excluded.projection_events == ()
    assert tuple(value.reason for value in excluded.missing_boundaries) == (
        "no_safe_fill_before_cash_market_open",
    )


def test_both_cash_calendars_suppress_boundaries() -> None:
    at_midnight = aggregate_fixture.DAY_START_MS
    xkrx = build_binance_usdm_koru_tradifi_source_projection_v1(
        _request(((at_midnight, "12.340"),), start_hour=0, end_hour=1)
    ).result
    assert xkrx is not None
    assert xkrx.projection_events == xkrx.missing_boundaries == ()

    at_fourteen = aggregate_fixture.DAY_START_MS + 14 * price_fixture.HOUR_MS
    arcx = build_binance_usdm_koru_tradifi_source_projection_v1(
        _request(((at_fourteen, "12.340"),), start_hour=14, end_hour=15)
    ).result
    assert arcx is not None
    assert arcx.projection_events == arcx.missing_boundaries == ()


def test_source_events_and_canonically_equal_authority_values_replay() -> None:
    request = _request(
        (
            (
                aggregate_fixture.DAY_START_MS
                + 22 * price_fixture.HOUR_MS
                + 30 * 60_000,
                "12.340",
            ),
        )
    )
    aggregate_event = request.aggregate_trade_results[0].events[0]
    source_bytes = canonical_bytes(aggregate_event)
    result = build_binance_usdm_koru_tradifi_source_projection_v1(request).result
    assert result is not None
    retained = next(
        event
        for event in result.source_events
        if event.event_id == aggregate_event.event_id
    )
    assert retained is aggregate_event
    assert canonical_bytes(retained) == source_bytes
    authority = request.authority_result
    envelopes = tuple(
        ArtifactEnvelope(
            value.artifact_type,
            value.schema_version,
            value.payload,
            value.content_hash,
        )
        for value in authority.artifacts
    )
    refs = tuple(
        ArtifactRef(value.artifact_type, value.schema_version, value.content_hash)
        for value in authority.refs
    )
    replayed = replace(
        result,
        xkrx_calendar=envelopes[0],
        arcx_calendar=envelopes[1],
        post_adjustment_unit_regime=envelopes[2],
        xkrx_calendar_ref=refs[0],
        arcx_calendar_ref=refs[1],
        post_adjustment_unit_regime_ref=refs[2],
    )
    assert replayed.xkrx_calendar is not authority.xkrx_calendar
    assert replayed.xkrx_calendar_ref is not authority.xkrx_calendar_ref
    assert canonical_bytes(replayed) == canonical_bytes(result)
    with pytest.raises(ValueError, match="binding mismatch"):
        replace(
            replayed,
            xkrx_calendar_ref=ArtifactRef(
                refs[0].artifact_type,
                refs[0].schema_version,
                "sha256:" + "0" * 64,
            ),
        )
    assert result.decision_grade_eligible is result.deployment_authorized is False


def test_replay_digest_and_projection_lineage_are_golden() -> None:
    first = _built()
    replay = _built()
    assert canonical_bytes(first) == canonical_bytes(replay)
    assert (
        first.fragment_digest
        == replay.fragment_digest
        == ("sha256:de6c5dc9a27029b8ea6d1cbf0eb6fe6040078afae472e94e89ad27441e16dd5b")
    )
    assert all(
        lineage.projection_event_hash == event.event_hash
        for lineage, event in zip(
            first.projection_lineage, first.projection_events, strict=True
        )
    )


def test_stream_manifest_rejects_duplicate_ids_and_ordering_keys() -> None:
    source = _price_strategy_events(_built(), _KIND.MARK_PRICE.value)[0]
    with pytest.raises(ValueError, match="duplicate_event_id"):
        _stream_manifests((source, source), ())

    collision = replace(
        source,
        event_id=source.event_id + ":ordering-collision",
        source_sequence=SourceSequence(source.source_sequence.value),
    )
    assert collision.event_id != source.event_id
    assert collision.available_time == source.available_time
    assert collision.source_sequence == source.source_sequence
    assert collision.ordering_key == source.ordering_key
    with pytest.raises(ValueError, match="duplicate_ordering_key"):
        _stream_manifests((source, collision), ())


def test_outcome_attestation_rejects_object_level_tamper_and_stale_digest() -> None:
    nested = _built()
    object.__setattr__(nested.request, "instrument_catalog_hash", "sha256:" + "2" * 64)
    with pytest.raises(ValueError, match="exact canonical"):
        BinanceUsdmKoruTradifiSourceProjectionOutcomeV1(result=nested)

    event = _built()
    object.__setattr__(
        event.projection_events[0],
        "event_id",
        event.projection_events[0].event_id + ":forged",
    )
    with pytest.raises(ValueError, match="exact canonical"):
        BinanceUsdmKoruTradifiSourceProjectionOutcomeV1(result=event)

    lineage = _built()
    object.__setattr__(
        lineage.projection_lineage[0],
        "source_event_id",
        lineage.projection_lineage[0].source_event_id + ":forged",
    )
    with pytest.raises(ValueError, match="exact canonical"):
        BinanceUsdmKoruTradifiSourceProjectionOutcomeV1(result=lineage)

    digest = _built()
    object.__setattr__(digest, "fragment_digest", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="exact canonical"):
        BinanceUsdmKoruTradifiSourceProjectionOutcomeV1(result=digest)


def test_date_context_and_price_grid_mutations_fail_closed() -> None:
    request = _request(
        (
            (
                aggregate_fixture.DAY_START_MS
                + 22 * price_fixture.HOUR_MS
                + 30 * 60_000,
                "12.340",
            ),
        )
    )
    duplicate_date = replace(
        request,
        aggregate_trade_results=(
            request.aggregate_trade_results[0],
            request.aggregate_trade_results[0],
        ),
    )
    failed = build_binance_usdm_koru_tradifi_source_projection_v1(duplicate_date)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AGGREGATE_TRADES_INVALID
    )

    short_mark = price_fixture.normalize(_KIND.MARK_PRICE, _price_rows()[:3]).result
    assert short_mark is not None
    gap = replace(request, mark_price_results=(short_mark,))
    failed = build_binance_usdm_koru_tradifi_source_projection_v1(gap)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.PRICE_BARS_INVALID
    )

    event = request.aggregate_trade_results[0].events[0]
    object.__setattr__(event, "stream_key", "mutated.source.context")
    failed = build_binance_usdm_koru_tradifi_source_projection_v1(request)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.AGGREGATE_TRADES_INVALID
    )


def test_special_and_missing_funding_rate_types_fail_executable_fragment() -> None:
    funding_time = aggregate_fixture.DAY_START_MS + 20 * price_fixture.HOUR_MS
    for rate_type in ("Special", None):
        raw = funding_fixture.compact(
            [funding_fixture.row(funding_time, rate_type=rate_type)]
        )
        request = _request(
            (
                (
                    aggregate_fixture.DAY_START_MS
                    + 22 * price_fixture.HOUR_MS
                    + 30 * 60_000,
                    "12.340",
                ),
            ),
            funding_raw=raw,
        )
        failed = build_binance_usdm_koru_tradifi_source_projection_v1(request)
        assert failed.result is None
        assert failed.failure is not None
        assert failed.failure.code is (
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV1.FUNDING_INVALID
        )
