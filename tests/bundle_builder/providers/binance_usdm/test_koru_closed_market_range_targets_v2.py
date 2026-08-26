from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest
from crypto_quant_bundle_builder.binance_usdm_koru_closed_market_range_targets_v2 import (
    BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2,
    BinanceUsdmKoruClosedMarketRangeTargetsRequestV2,
    _trusted_result,
    build_binance_usdm_koru_closed_market_range_targets_v2,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruTradifiSourceProjectionResultV2,
    build_binance_usdm_koru_tradifi_source_projection_v2,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_closed_market_range_targets_v1 as target_v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v2 as source_v2_fixture,
)

_STRATEGY_REF = (
    "sha256:b5c153a127ad3ed4c1286ba4d2948fa52e581239f0d3bd01f3074c410eed9c81"
)
_PARAMETER_REFS = (
    "sha256:23911e260d3fe6e4fbc009851523bbb095209466e44c70b63ae2114e37f05f78",
    "sha256:f02521f9194c671a24c7a05bb0ebe3e11eac2cfddccd5b3c52e11f58b1bab9f9",
    "sha256:b577c11a94a1f4fed3247cf9bd3508de092be7d14a01dfd58e3805b1a4a69c43",
    "sha256:bd3c440d01a144317ddacad9814b0791e13079bc898c4e06dea455566ad7a14a",
    "sha256:cbcd7d3a81c71411abe0c2191b0f7b17209b3d55965361c8e6c0798b5c1e30e9",
    "sha256:bec582ad24da484a13c0fc960e4ae351c4cbd62f7806d07a03d579db04cdffc0",
    "sha256:aa46923df87d9ed25ee58fde6e4af0108d7e79e3ad7cfe17ac26d0dd9bf910d3",
    "sha256:e85e8a778fcdfdc4176f9fa6c395c86e47bd7a356309dc08b3074024bfa89911",
)


def _source(
    v1_source=None,
) -> BinanceUsdmKoruTradifiSourceProjectionResultV2:
    if v1_source is None:
        v1_source = target_v1_fixture._weekend_fragment()
    request = source_v2_fixture._from_v1_request(v1_source.request)
    outcome = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _build(source=None):
    source = _source() if source is None else source
    outcome = build_binance_usdm_koru_closed_market_range_targets_v2(
        BinanceUsdmKoruClosedMarketRangeTargetsRequestV2(source)
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _candidate(event) -> dict[str, Any]:
    return cast(dict[str, Any], dict(event.payload["candidate"]))


def _semantics(event) -> dict[str, Any]:
    candidate = _candidate(event)
    candidate.pop("evidence")
    return candidate


def test_v1_artifact_refs_remain_exact_and_v2_reuses_the_same_artifacts() -> None:
    v1 = target_v1_fixture._weekend_result()
    v2 = _build()

    assert v1.strategy.ref.content_hash == _STRATEGY_REF
    assert tuple(value.ref.content_hash for value in v1.parameters) == _PARAMETER_REFS
    assert canonical_bytes(v2.strategy) == canonical_bytes(v1.strategy)
    assert canonical_bytes(v2.parameters) == canonical_bytes(v1.parameters)


def test_v1_v2_decisions_match_while_target_and_projection_identities_are_v2() -> None:
    source = _source()
    v1 = target_v1_fixture._weekend_result()
    v2 = _build(source)

    assert tuple(stream.stream_key for stream in v2.streams) == tuple(
        f"binance_usdm.tradifi.target.koruusdt.closed_market_range.p{index:02d}.v2"
        for index in range(1, 9)
    )
    for v1_stream, v2_stream in zip(v1.streams, v2.streams, strict=True):
        assert tuple(map(_semantics, v2_stream.events)) == tuple(
            map(_semantics, v1_stream.events)
        )
        if v2_stream.events:
            assert tuple(event.event_id for event in v2_stream.events) != tuple(
                event.event_id for event in v1_stream.events
            )
        for event in v2_stream.events:
            candidate = _candidate(event)
            evidence = candidate["evidence"]
            projection = next(
                value
                for value in source.projection_events
                if value.event_id == evidence["projection_event_id"]
            )
            preimage = {
                "type": "binance_usdm_koru_closed_market_range_target_preimage_v2",
                "schema_version": 2,
                "stream_key": v2_stream.stream_key,
                "candidate": event.payload["candidate"],
            }
            assert event.event_id == (
                "binance-usdm-koru-closed-market-range-target-v2:"
                + canonical_sha256({"identity": "event", "preimage": preimage})
            )
            assert (
                event.source_key == "binance_usdm.koru.closed_market_range.targets.v2"
            )
            assert event.source_hash == canonical_sha256(
                {"identity": "source", "preimage": preimage}
            )
            assert evidence["source_fragment_digest"] == source.fragment_digest
            assert evidence["projection_event_hash"] == projection.event_hash
    assert [len(stream.events) for stream in v2.streams] == [2, 2, 2, 2, 0, 0, 0, 0]
    assert all(
        not stream.events or _candidate(stream.events[-1])["targets"][0]["value"] == "0"
        for stream in v2.streams
    )


def test_missing_projection_and_streaming_gap_evidence_are_retained_fail_closed() -> (
    None
):
    _, request = source_v2_fixture._request(trade_hour=19)
    outcome = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert outcome.result is not None
    source = outcome.result
    result = _build(source)

    missing = {
        value.hourly_boundary.epoch_nanoseconds for value in source.missing_boundaries
    }
    used = {
        _candidate(event)["evidence"]["projection_boundary"]
        for stream in result.streams
        for event in stream.events
    }
    assert missing
    assert missing.isdisjoint(used)
    assert result.missing_boundaries == source.missing_boundaries
    assert result.source_fragment_digest == source.fragment_digest
    assert result.aggregate_trade_boundary_index_request_hash == (
        source.aggregate_trade_boundary_index_request_hash
    )
    assert result.aggregate_trade_boundary_index_result_digest == (
        source.aggregate_trade_boundary_index_result_digest
    )
    assert result.aggregate_trade_streamed_reconstruction_digest == (
        source.aggregate_trade_streamed_reconstruction_digest
    )
    assert result.aggregate_trade_intra_day_raw_id_gap_stream == (
        source.aggregate_trade_intra_day_raw_id_gap_stream
    )
    assert result.aggregate_trade_cross_date_raw_id_gap_stream == (
        source.aggregate_trade_cross_date_raw_id_gap_stream
    )
    assert result.aggregate_trade_coverage_gaps == source.aggregate_trade_coverage_gaps

    empty = _build(_source(target_v1_fixture._base_fragment()))
    assert len(empty.streams) == 8
    assert all(
        stream.events == () and stream.manifest.event_count == 0
        for stream in empty.streams
    )


@pytest.mark.parametrize("tamper", ("source", "projection", "calendar"))
def test_v2_source_projection_and_calendar_tamper_are_rejected(tamper: str) -> None:
    source = _source()
    original: str | None = None
    if tamper == "source":
        object.__setattr__(source, "fragment_digest", "sha256:" + "0" * 64)
    elif tamper == "projection":
        event = source.projection_events[0]
        object.__setattr__(
            source,
            "projection_events",
            (
                replace(event, source_hash="sha256:" + "0" * 64),
                *source.projection_events[1:],
            ),
        )
    else:
        original = source.xkrx_calendar.content_hash
        object.__setattr__(source.xkrx_calendar, "content_hash", "sha256:" + "0" * 64)

    try:
        with pytest.raises(ValueError, match="exact accepted V2 result"):
            BinanceUsdmKoruClosedMarketRangeTargetsRequestV2(source)
    finally:
        if tamper == "calendar":
            assert original is not None
            object.__setattr__(source.xkrx_calendar, "content_hash", original)


def test_parameter_tamper_trusted_outcome_and_fresh_replay_fail_closed() -> None:
    source = _source()
    first = _build(source)
    second = _build(source)

    assert canonical_bytes(first) == canonical_bytes(second)
    assert _trusted_result(first) is not None
    assert (
        BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2(result=first).result is first
    )

    object.__setattr__(first.parameters[0], "max_hold_hours", 999)
    assert _trusted_result(first) is None
    with pytest.raises(ValueError, match="exact canonical V2 target result"):
        BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2(result=first)
