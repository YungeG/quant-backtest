from __future__ import annotations

from dataclasses import replace

import pytest
from crypto_quant_bundle_builder import (
    binance_usdm_koru_aggtrade_boundary_index_v1 as boundary_index,
)
from crypto_quant_bundle_builder.binance_usdm_koru_aggtrade_boundary_index_v1 import (
    BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1,
    BinanceUsdmKoruExecutionBoundaryV1,
    build_binance_usdm_koru_aggregate_trade_boundary_index_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v1 import (
    build_binance_usdm_koru_tradifi_source_projection_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2,
    BinanceUsdmKoruTradifiSourceProjectionOutcomeV2,
    BinanceUsdmKoruTradifiSourceProjectionRequestV2,
    build_binance_usdm_koru_tradifi_source_projection_v2,
)
from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketStreamManifest

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_aggtrades_source_bounded_v1 as aggregate_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as v1_fixture,
)

_HOUR_NS = v1_fixture._HOUR_NS
_V1_PROJECTION_STREAM = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v1"
)
_V2_PROJECTION_STREAM = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v2"
)
_V1_PROJECTION_SOURCE = (
    "binance_usdm.tradifi.first_retained_aggregate_trade_projection.koruusdt.1h.v1"
)
_V2_PROJECTION_SOURCE = (
    "binance_usdm.tradifi.first_retained_aggregate_trade_projection.koruusdt.1h.v2"
)
_IDENTITY_LIMITATION = (
    (
        "v2_bar_open_event_stream_revision_source_and_manifest_identities_are_versioned_"
        "and_intentionally_differ_from_v1"
    ),
)


def _from_v1_request(
    v1_request: v1_fixture.BinanceUsdmKoruTradifiSourceProjectionRequestV1,
) -> BinanceUsdmKoruTradifiSourceProjectionRequestV2:
    v1_result = build_binance_usdm_koru_tradifi_source_projection_v1(v1_request).result
    assert v1_result is not None
    resolved = (*v1_result.projection_lineage, *v1_result.missing_boundaries)
    index_request = BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1(
        captures=tuple(value.capture for value in v1_request.aggregate_trade_results),
        timeline_window_start=v1_request.timeline_window_start,
        timeline_window_end_exclusive=v1_request.timeline_window_end_exclusive,
        boundaries=tuple(
            BinanceUsdmKoruExecutionBoundaryV1(
                value.hourly_boundary,
                value.next_cash_market_open_or_window_end,
            )
            for value in sorted(
                resolved, key=lambda item: item.hourly_boundary.epoch_nanoseconds
            )
        ),
    )
    boundary_outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(
        index_request
    )
    assert boundary_outcome.result is not None
    return BinanceUsdmKoruTradifiSourceProjectionRequestV2(
        timeline_window_start=v1_request.timeline_window_start,
        timeline_window_end_exclusive=v1_request.timeline_window_end_exclusive,
        instrument_catalog_hash=v1_request.instrument_catalog_hash,
        projection_scale=v1_request.projection_scale,
        aggregate_trade_boundary_index_result=boundary_outcome.result,
        mark_price_results=v1_request.mark_price_results,
        index_price_results=v1_request.index_price_results,
        funding_result=v1_request.funding_result,
        authority_result=v1_request.authority_result,
    )


def _request(
    trade_hour: int = 22,
) -> tuple[
    v1_fixture.BinanceUsdmKoruTradifiSourceProjectionRequestV1,
    BinanceUsdmKoruTradifiSourceProjectionRequestV2,
]:
    trade = (
        aggregate_fixture.DAY_START_MS
        + trade_hour * (_HOUR_NS // 1_000_000)
        + 30 * 60_000
    )
    v1_request = v1_fixture._request(((trade, "12.340"),))
    return v1_request, _from_v1_request(v1_request)


def _built():
    _, request = _request()
    outcome = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def _projection_preimage(lineage, index) -> dict[str, object]:
    return {
        "type": "binance_usdm_koru_first_retained_trade_projection_preimage_v2",
        "schema_version": 2,
        "hourly_boundary": lineage.hourly_boundary,
        "next_cash_market_open_or_window_end": (
            lineage.next_cash_market_open_or_window_end
        ),
        "source_event_id": lineage.source_event_id,
        "source_event_hash": lineage.source_event_hash,
        "source_revision_id": lineage.source_revision_id,
        "source_event_time": lineage.source_event_time,
        "source_available_time": lineage.source_available_time,
        "source_key": lineage.source_key,
        "source_hash": lineage.source_hash,
        "source_record_hash": lineage.source_record_hash,
        "source_snapshot_id": lineage.source_snapshot_id,
        "source_snapshot_hash": lineage.source_snapshot_hash,
        "boundary_index_request_hash": index.request.request_hash,
        "boundary_index_result_digest": index.result_digest,
        "boundary_index_lineage_hash": lineage.boundary_index_lineage_hash,
        "open_price": {
            "units": lineage.open_price_units,
            "scale": lineage.open_price_scale,
            "quote_currency": "USDT",
        },
    }


def _rebuilt_boundary_request(
    request: BinanceUsdmKoruTradifiSourceProjectionRequestV2,
    boundaries: tuple[BinanceUsdmKoruExecutionBoundaryV1, ...],
) -> BinanceUsdmKoruTradifiSourceProjectionRequestV2:
    current = request.aggregate_trade_boundary_index_result.request
    index_request = BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1(
        captures=current.captures,
        timeline_window_start=current.timeline_window_start,
        timeline_window_end_exclusive=current.timeline_window_end_exclusive,
        boundaries=boundaries,
    )
    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(index_request)
    assert outcome.failure is None
    assert outcome.result is not None
    return replace(request, aggregate_trade_boundary_index_result=outcome.result)


def test_streaming_projection_matches_v1_semantics_without_extra_aggregate_rows() -> (
    None
):
    v1_request, request = _request()
    v1 = build_binance_usdm_koru_tradifi_source_projection_v1(v1_request).result
    v2 = build_binance_usdm_koru_tradifi_source_projection_v2(request).result
    assert v1 is not None
    assert v2 is not None

    assert tuple(
        (event.payload, event.event_time, event.available_time, event.phase)
        for event in v2.projection_events
    ) == tuple(
        (event.payload, event.event_time, event.available_time, event.phase)
        for event in v1.projection_events
    )
    shared_lineage_fields = (
        "hourly_boundary",
        "next_cash_market_open_or_window_end",
        "source_event_id",
        "source_event_hash",
        "source_revision_id",
        "source_event_time",
        "source_available_time",
        "source_key",
        "source_hash",
        "aggregate_trade_id",
        "first_trade_id",
        "last_trade_id",
        "source_record_hash",
        "source_snapshot_id",
        "source_snapshot_hash",
        "source_provenance_hash",
        "source_member_hash",
        "source_request_hash",
        "source_capture_hash",
        "open_price_units",
        "open_price_scale",
    )
    assert tuple(
        tuple(getattr(value, field) for field in shared_lineage_fields)
        for value in v2.projection_lineage
    ) == tuple(
        tuple(getattr(value, field) for field in shared_lineage_fields)
        for value in v1.projection_lineage
    )

    index = request.aggregate_trade_boundary_index_result
    selected_v1 = tuple(
        next(event for event in v1.source_events if event.event_id == selected.event_id)
        for selected in index.selected_source_events
    )
    assert index.selected_source_events == selected_v1
    assert tuple(
        (event.event_id, event.event_hash, event.payload, canonical_bytes(event))
        for event in index.selected_source_events
    ) == tuple(
        (event.event_id, event.event_hash, event.payload, canonical_bytes(event))
        for event in selected_v1
    )
    aggregate_ids = {event.event_id for event in index.selected_source_events}
    assert (
        tuple(event for event in v2.source_events if event.event_id in aggregate_ids)
        == selected_v1
    )
    assert len(aggregate_ids) == 1

    for v1_event, v2_event, lineage in zip(
        v1.projection_events, v2.projection_events, v2.projection_lineage, strict=True
    ):
        preimage = _projection_preimage(lineage, index)
        event_identity = canonical_sha256(
            {
                "type": "binance_usdm_koru_first_retained_trade_projection_event_identity_v2",
                "projection": preimage,
            }
        )
        revision_identity = canonical_sha256(
            {
                "type": "binance_usdm_koru_first_retained_trade_projection_revision_identity_v2",
                "projection": preimage,
            }
        )
        source_identity = canonical_sha256(
            {
                "type": "binance_usdm_koru_first_retained_trade_projection_source_identity_v2",
                "projection": preimage,
            }
        )
        assert v2_event.event_id == (
            "binance-usdm-koru-first-retained-trade-bar-open-v2:" + event_identity
        )
        assert v2_event.stream_key == _V2_PROJECTION_STREAM
        assert v2_event.revision_id == revision_identity
        assert v2_event.source_key == _V2_PROJECTION_SOURCE
        assert v2_event.source_hash == source_identity
        assert v2_event.event_id != v1_event.event_id
        assert v2_event.event_hash != v1_event.event_hash
        assert v2_event.stream_key != v1_event.stream_key
        assert v2_event.revision_id != v1_event.revision_id
        assert v2_event.source_key != v1_event.source_key
        assert v2_event.source_hash != v1_event.source_hash

    assert v1.projection_stream_manifest.stream_key == _V1_PROJECTION_STREAM
    assert v2.projection_stream_manifest == MarketStreamManifest.from_events(
        _V2_PROJECTION_STREAM, v2.projection_events
    )
    assert (
        v2.projection_stream_manifest.stream_key
        != v1.projection_stream_manifest.stream_key
    )
    assert (
        v2.projection_stream_manifest.content_hash
        != v1.projection_stream_manifest.content_hash
    )
    assert v1.projection_events[0].source_key == _V1_PROJECTION_SOURCE
    assert v2.to_canonical_dict()["limitations"] == _IDENTITY_LIMITATION
    assert all(
        lineage.boundary_index_request_hash == index.request.request_hash
        and lineage.boundary_index_result_digest == index.result_digest
        for lineage in v2.projection_lineage
    )


def test_unselected_aggregate_rows_are_not_materialized_as_source_events() -> None:
    start_ms = aggregate_fixture.DAY_START_MS
    v1_request = v1_fixture._request(
        (
            (start_ms + 20 * (_HOUR_NS // 1_000_000) + 10_000, "12.340"),
            (start_ms + 20 * (_HOUR_NS // 1_000_000) + 20_000, "12.341"),
            (start_ms + 22 * (_HOUR_NS // 1_000_000) + 30_000, "12.342"),
        )
    )
    request = _from_v1_request(v1_request)
    result = build_binance_usdm_koru_tradifi_source_projection_v2(request).result
    assert result is not None
    all_aggregate_ids = {
        event.event_id for event in v1_request.aggregate_trade_results[0].events
    }
    selected_ids = {
        event.event_id
        for event in request.aggregate_trade_boundary_index_result.selected_source_events
    }
    retained_ids = {
        event.event_id
        for event in result.source_events
        if event.event_id in all_aggregate_ids
    }
    assert len(all_aggregate_ids) == 3
    assert len(selected_ids) == 2
    assert retained_ids == selected_ids


def test_mixed_retained_missing_prefix_matches_v1_and_keeps_gap_evidence() -> None:
    retained_price = v1_fixture.retained_price_fixture
    retained_aggregate = v1_fixture.retained_aggregate_fixture
    aug24_start_ms = retained_price.DAY_START_MS
    start = (aug24_start_ms - 2 * (_HOUR_NS // 1_000_000)) * 1_000_000
    end = (aug24_start_ms + 11 * (_HOUR_NS // 1_000_000)) * 1_000_000
    v1_request = v1_fixture._request(
        (
            (aug24_start_ms - 90 * 60_000, "12.340"),
            (aug24_start_ms + 7 * (_HOUR_NS // 1_000_000) + 1_000, "12.350"),
        ),
        start_ns=start,
        end_ns=end,
    )
    retained_rows = tuple(
        {
            **row,
            "a": row["a"] + 5,
            "f": row["f"] + 20,
            "l": row["l"] + 20,
        }
        for row in retained_aggregate.ROWS
    )
    evidence = retained_aggregate.evidence_for(retained_rows)
    retained_capture = retained_aggregate.capture(evidence).result
    assert retained_capture is not None
    retained_result = retained_aggregate.normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
        retained_capture
    ).result
    assert retained_result is not None
    mixed = replace(
        v1_request,
        aggregate_trade_results=(
            v1_request.aggregate_trade_results[0],
            retained_result,
        ),
        mark_price_results=(
            v1_request.mark_price_results[0],
            retained_price.retained_result(v1_fixture._KIND.MARK_PRICE),
        ),
        index_price_results=(
            v1_request.index_price_results[0],
            retained_price.retained_result(v1_fixture._KIND.INDEX_PRICE),
        ),
    )
    v1 = build_binance_usdm_koru_tradifi_source_projection_v1(mixed).result
    request = _from_v1_request(mixed)
    v2 = build_binance_usdm_koru_tradifi_source_projection_v2(request).result
    assert v1 is not None
    assert v2 is not None
    assert tuple(
        (value.hourly_boundary, value.next_cash_market_open_or_window_end, value.reason)
        for value in v2.missing_boundaries
    ) == tuple(
        (value.hourly_boundary, value.next_cash_market_open_or_window_end, value.reason)
        for value in v1.missing_boundaries
    )
    assert v2.aggregate_trade_coverage_gaps == (
        request.aggregate_trade_boundary_index_result.aggregate_id_coverage_gaps
    )
    assert len(v2.aggregate_trade_coverage_gaps) == 1
    aggregate_ids = {
        event.event_id
        for event in request.aggregate_trade_boundary_index_result.selected_source_events
    }
    assert aggregate_ids == {value.source_event_id for value in v2.projection_lineage}


def test_missing_boundaries_and_development_evidence_replay_exactly() -> None:
    v1_request, request = _request(trade_hour=19)
    v1 = build_binance_usdm_koru_tradifi_source_projection_v1(v1_request).result
    first = build_binance_usdm_koru_tradifi_source_projection_v2(request).result
    second = build_binance_usdm_koru_tradifi_source_projection_v2(request).result
    assert v1 is not None
    assert first is not None
    assert second is not None
    assert tuple(
        (value.hourly_boundary, value.next_cash_market_open_or_window_end, value.reason)
        for value in first.missing_boundaries
    ) == tuple(
        (value.hourly_boundary, value.next_cash_market_open_or_window_end, value.reason)
        for value in v1.missing_boundaries
    )
    assert canonical_bytes(first) == canonical_bytes(second)
    assert first.development_only is True
    assert first.decision_grade_eligible is first.deployment_authorized is False
    index = request.aggregate_trade_boundary_index_result
    assert (
        first.aggregate_trade_boundary_index_request_hash == index.request.request_hash
    )
    assert first.aggregate_trade_boundary_index_result_digest == index.result_digest
    assert (
        first.aggregate_trade_streamed_reconstruction_digest
        == index.streamed_reconstruction_digest
    )
    assert first.aggregate_trade_intra_day_raw_id_gap_stream == (
        index.intra_day_raw_id_gap_stream
    )
    assert first.aggregate_trade_cross_date_raw_id_gap_stream == (
        index.cross_date_raw_id_gap_stream
    )
    assert first.aggregate_trade_coverage_gaps == index.aggregate_id_coverage_gaps


def test_repeated_projection_builds_reuse_certified_boundary_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, request = _request(trade_hour=19)
    streaming_build = boundary_index._build
    scan_count = 0

    def counted_build(value):
        nonlocal scan_count
        scan_count += 1
        return streaming_build(value)

    monkeypatch.setattr(boundary_index, "_build", counted_build)
    first = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    second = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert first.result is not None
    assert second.result is not None
    assert scan_count == 0

    index = request.aggregate_trade_boundary_index_result
    object.__setattr__(index, "streamed_row_count", index.streamed_row_count + 1)
    failed = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2.AGGREGATE_TRADES_INVALID
    )
    assert scan_count == 1


def test_calendar_exact_cover_rejects_fresh_trusted_boundary_indexes() -> None:
    _, request = _request()
    boundaries = request.aggregate_trade_boundary_index_result.request.boundaries
    wrong_cutoff = replace(
        boundaries[0],
        cutoff=UtcInstant(boundaries[0].boundary.epoch_nanoseconds + 1),
    )
    candidates = (
        _rebuilt_boundary_request(request, boundaries[:-1]),
        _rebuilt_boundary_request(request, (wrong_cutoff, *boundaries[1:])),
    )

    for candidate in candidates:
        failed = build_binance_usdm_koru_tradifi_source_projection_v2(candidate)
        assert failed.result is None
        assert failed.failure is not None
        assert failed.failure.code is (
            BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2.AGGREGATE_TRADES_INVALID
        )
        assert failed.failure.subject == "aggregate_trade_boundary_index_request"


def test_boundary_index_digest_and_duplicate_tamper_fail_closed() -> None:
    _, request = _request()
    index = request.aggregate_trade_boundary_index_result
    object.__setattr__(index, "result_digest", "sha256:" + "0" * 64)
    failed = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2.AGGREGATE_TRADES_INVALID
    )

    _, request = _request()
    index = request.aggregate_trade_boundary_index_result
    object.__setattr__(
        index,
        "selected_source_events",
        (*index.selected_source_events, index.selected_source_events[0]),
    )
    failed = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2.AGGREGATE_TRADES_INVALID
    )


def test_price_funding_authority_and_outcome_tamper_fail_closed() -> None:
    _, request = _request()
    price = request.mark_price_results[0]
    object.__setattr__(price, "projected_row_count", 0)
    failed = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2.PRICE_BARS_INVALID
    )

    _, request = _request()
    object.__setattr__(request.funding_result, "regular_count", 0)
    failed = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2.FUNDING_INVALID
    )

    _, request = _request()
    object.__setattr__(
        request.authority_result.xkrx_calendar,
        "content_hash",
        "sha256:" + "0" * 64,
    )
    failed = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is (
        BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2.AUTHORITY_INVALID
    )

    result = _built()
    object.__setattr__(result, "fragment_digest", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="exact canonical"):
        BinanceUsdmKoruTradifiSourceProjectionOutcomeV2(result=result)
