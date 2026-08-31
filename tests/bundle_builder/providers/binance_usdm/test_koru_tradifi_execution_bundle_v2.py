from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest
from crypto_quant_backtest import (
    BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
    TimelineWindow,
    build_binance_usdm_koru_tradifi_development_profile_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_closed_market_range_targets_v2 import (
    BinanceUsdmKoruClosedMarketRangeTargetsRequestV2,
    build_binance_usdm_koru_closed_market_range_targets_v2,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_execution_bundle_v2 import (
    BinanceUsdmKoruTradifiExecutionBundleOutcomeV2,
    BinanceUsdmKoruTradifiExecutionBundleRequestV2,
    _trusted_result,
    build_binance_usdm_koru_tradifi_execution_bundle_v2,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v2 import (
    build_binance_usdm_koru_source_profile_authority_v2,
    build_binance_usdm_koru_tradifi_source_projection_v2,
)
from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import EventCursor, MarketBundleRef

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_closed_market_range_targets_v1 as target_v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_funding_rate_history_source_bounded_v1 as funding_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v1 as bundle_v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as source_v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v2 as source_v2_fixture,
)


def _source(
    v1_source=None,
    funding_times: tuple[int, ...] | None = None,
    funding_mark_price: str = "20.00000000",
):
    v1_source = target_v1_fixture._weekend_fragment() if v1_source is None else v1_source
    source_request = v1_source.request
    if funding_times is None:
        funding_times = (
            source_request.timeline_window_start.epoch_nanoseconds // 1_000_000,
        )
    source_request = replace(
        source_request,
        funding_result=source_v1_fixture._funding_result(
            funding_fixture.compact(
                [
                    funding_fixture.row(value, mark_price=funding_mark_price)
                    for value in funding_times
                ]
            )
        ),
    )
    outcome = build_binance_usdm_koru_tradifi_source_projection_v2(
        source_v2_fixture._from_v1_request(source_request)
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _target(source):
    outcome = build_binance_usdm_koru_closed_market_range_targets_v2(
        BinanceUsdmKoruClosedMarketRangeTargetsRequestV2(source)
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _profile(source):
    envelope, ref = build_binance_usdm_koru_source_profile_authority_v2(source)
    composed_ns = max(
        event.payload.get("acquired_at_epoch_nanoseconds", 0)
        for event in source.source_events
    ) + 1
    outcome = build_binance_usdm_koru_tradifi_development_profile_v1(
        BinanceUsdmKoruTradifiDevelopmentProfileRequestV1(
            TimelineWindow(
                source.request.timeline_window_start,
                source.request.timeline_window_start,
                source.request.timeline_window_end_exclusive,
            ),
            SimulationInstant(
                UtcInstant(composed_ns),
                TimelinePhase(200, "profile_composition"),
                SourceSequence(0),
            ),
            "account-1",
            source.xkrx_calendar_ref,
            source.arcx_calendar_ref,
            source.post_adjustment_unit_regime_ref,
            envelope,
            ref,
            source.source_events,
        )
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _request(source=None, target=None, wire=None):
    source = _source() if source is None else source
    target = _target(source) if target is None else target
    profile = _profile(source)
    wire = profile.profile_composition_request_wire if wire is None else wire
    return BinanceUsdmKoruTradifiExecutionBundleRequestV2(
        source_projection=source,
        target_result=target,
        source_profile_authority_envelope=(
            profile.request.source_profile_authority_envelope
        ),
        source_profile_authority_ref=profile.source_profile_authority_ref,
        profile_composition_request_wire=wire,
        profile_composition_request_hash=canonical_sha256(wire),
        execution_account_id="account-1",
        initial_equity=bundle_v1_fixture._REQUIRED_EQUITY,
        sleeve_allocation_fraction="1",
    )


def _build(source=None):
    outcome = build_binance_usdm_koru_tradifi_execution_bundle_v2(_request(source))
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _raw_scale8_two_funding_bundle():
    source = target_v1_fixture._raw_scale8_weekend_fragment()
    start = source.request.timeline_window_start.epoch_nanoseconds // 1_000_000
    return _build(
        _source(
            source,
            (start + 18_000_000, start + 21_600_000),
            funding_mark_price="20.00000001",
        )
    )


def test_v1_final_bundle_golden_hashes_remain_exact() -> None:
    empty = bundle_v1_fixture._empty_result()
    nonempty = bundle_v1_fixture._nonempty_result()

    assert (
        empty.bundle_ref.manifest_hash
        == "sha256:cf2de51983e006a8599ef0f33ea77d7be798e2cf6cdc156bcd36f85a4cc321c6"
    )
    assert (
        empty.result_digest
        == "sha256:f47df6f604fadabb7c11604bbee2aaecdf7c5bf883b91e4e05c2228b9228770e"
    )
    assert (
        canonical_sha256(empty)
        == "sha256:4a79f36527a4cea917c57cca146e036d6b71dbfe5e3e2c7442516a5d084a308f"
    )
    assert (
        nonempty.bundle_ref.manifest_hash
        == "sha256:a204fb00716b5c82244b739e9af80717bc11da9dd8e5ce954f3efa0b772e2e13"
    )
    assert (
        nonempty.result_digest
        == "sha256:e5be3af315b2ac4a7ab83ae75d4382e7841e02854bc88563f2f2fae9b3c87ec4"
    )
    assert (
        canonical_sha256(nonempty)
        == "sha256:3e04d49d13ea80584b90bd4a19a207d97b8d22a15ef6579cdd52c9a6829ad16a"
    )


def test_v2_exact_covers_streams_and_uses_v2_bundle_and_authority_identities() -> None:
    result = _build()
    source = result.source_projection
    target = result.target_result
    expected = {
        *(value.stream_key for value in source.stream_manifests),
        *(value.stream_key for value in target.streams),
        "binance_usdm.tradifi.preparation_authority.v2",
        "binance_usdm.tradifi.price_purpose.authority.koruusdt.v2",
        "binance_usdm.tradifi.account.authority.koruusdt.v2",
    }

    assert len(target.streams) == 8
    assert set(result.streams) == expected
    assert {value.stream_key for value in result.manifest.streams} == expected
    assert result.manifest.schema_version == 2
    assert result.bundle_ref.bundle_key == result.manifest.bundle_key
    assert "development-v2-" in result.bundle_ref.bundle_key
    assert result.preparation_authority_event.event_type.endswith("_v2")
    assert result.price_purpose_authority_event.event_type.endswith("_v2")
    assert result.request.to_canonical_dict()["limitations"] == (
        "selected_source_events_form_the_executable_stream",
        "full_raw_data_is_retained_transitively_in_source_snapshots",
        "v2_projection_target_and_authority_identities",
        "development_only",
    )


def test_v1_v2_profile_account_and_artifact_semantics_match_with_distinct_identities() -> (
    None
):
    v1_source = target_v1_fixture._weekend_fragment()
    v1 = bundle_v1_fixture._build(v1_source, target_v1_fixture._weekend_result())
    v2 = _build(_source(v1_source))

    assert canonical_bytes(v2.authority_artifacts[:3]) == canonical_bytes(
        v1.authority_artifacts
    )
    assert canonical_bytes(v2.authority_refs[:3]) == canonical_bytes(v1.authority_refs)
    assert v2.authority_artifacts[3] == (
        v2.request.source_profile_authority_envelope
    )
    assert v2.authority_refs[3] == v2.request.source_profile_authority_ref
    assert canonical_bytes(v2.strategy_artifact) == canonical_bytes(v1.strategy_artifact)
    assert canonical_bytes(v2.parameter_artifacts) == canonical_bytes(
        v1.parameter_artifacts
    )
    v1_account = dict(v1.account_authority_event.payload)
    v2_account = dict(v2.account_authority_event.payload)
    assert v1_account.pop("schema_version") == 1
    assert v2_account.pop("schema_version") == 2
    assert v1_account.pop("profile_composition_request_hash") == (
        v1.request.profile_composition_request_hash
    )
    assert v2_account.pop("profile_composition_request_hash") == (
        v2.request.profile_composition_request_hash
    )
    assert v2_account == v1_account
    assert v2.account_authority_event.stream_key != v1.account_authority_event.stream_key
    assert v2.account_authority_event.event_id != v1.account_authority_event.event_id
    assert v2.preparation_authority_event.stream_key != (
        v1.preparation_authority_event.stream_key
    )
    assert v2.price_purpose_authority_event.stream_key != (
        v1.price_purpose_authority_event.stream_key
    )


def test_empty_and_nonempty_target_streams_replay_through_reader() -> None:
    empty = _build(_source(target_v1_fixture._base_fragment()))
    assert all(value.events == () for value in empty.target_result.streams)
    for value in empty.target_result.streams:
        cursor = empty.reader.open_cursor(value.stream_key, batch_size=1)
        assert isinstance(cursor, EventCursor) and cursor.exhausted

    nonempty = _build()
    target = next(value for value in nonempty.target_result.streams if value.events)
    cursor = nonempty.reader.open_cursor(target.stream_key, batch_size=1)
    batch, cursor = nonempty.reader.read_batch(cursor)
    assert batch == target.events[:1]
    assert cursor.position == 1


def test_authorities_bind_streaming_digests_gaps_targets_profile_and_exact_refs() -> None:
    result = _build()
    source = result.source_projection
    target = result.target_result
    preparation = result.preparation_authority_event.payload
    derived_envelope, derived_ref = build_binance_usdm_koru_source_profile_authority_v2(
        source
    )
    assert result.request.source_profile_authority_envelope == derived_envelope
    assert result.request.source_profile_authority_ref == derived_ref
    assert preparation["source_profile_authority_envelope"] == (
        derived_envelope.to_canonical_dict()
    )
    assert preparation["source_profile_authority_ref"] == derived_ref.to_canonical_dict()
    assert derived_envelope.payload["execution_projection_stream_manifest"] == (
        source.projection_stream_manifest.to_canonical_dict()
    )
    assert derived_envelope.payload["execution_projection_event_bindings"]
    assert source.projection_stream_manifest.stream_key not in {
        value["stream_key"]
        for value in derived_envelope.payload["source_stream_manifests"]
    }
    price = result.price_purpose_authority_event.payload
    common = {
        "source_fragment_digest": source.fragment_digest,
        "target_result_digest": target.result_digest,
        "aggregate_trade_boundary_index_request_hash": (
            source.aggregate_trade_boundary_index_request_hash
        ),
        "aggregate_trade_boundary_index_result_digest": (
            source.aggregate_trade_boundary_index_result_digest
        ),
        "aggregate_trade_streamed_reconstruction_digest": (
            source.aggregate_trade_streamed_reconstruction_digest
        ),
        "profile_composition_request_hash": result.request.profile_composition_request_hash,
    }
    for key, value in common.items():
        assert preparation[key] == price[key] == value
    assert preparation["aggregate_trade_intra_day_raw_id_gap_stream"] == (
        source.aggregate_trade_intra_day_raw_id_gap_stream.to_canonical_dict()
    )
    assert preparation["aggregate_trade_cross_date_raw_id_gap_stream"] == (
        source.aggregate_trade_cross_date_raw_id_gap_stream.to_canonical_dict()
    )
    assert preparation["aggregate_trade_coverage_gaps"] == tuple(
        value.to_canonical_dict() for value in source.aggregate_trade_coverage_gaps
    )
    assert preparation["missing_boundaries"] == tuple(
        value.to_canonical_dict() for value in source.missing_boundaries
    )
    assert preparation["strategy_definition_ref"] == result.strategy_ref.to_canonical_dict()
    assert preparation["xkrx_calendar_ref"] == result.authority_refs[0].to_canonical_dict()
    assert preparation["arcx_calendar_ref"] == result.authority_refs[1].to_canonical_dict()
    assert preparation["post_adjustment_unit_regime_ref"] == (
        result.authority_refs[2].to_canonical_dict()
    )
    bindings = cast(
        tuple[dict[str, Any], ...], preparation["parameter_target_bindings"]
    )
    assert len(bindings) == 8
    assert len({value["parameter_ref"]["content_hash"] for value in bindings}) == 8
    assert {value["target_stream_key"] for value in bindings} == {
        value.stream_key for value in target.streams
    }
    assert preparation["required_initial_equity"] == (
        bundle_v1_fixture._REQUIRED_EQUITY.to_canonical_dict()
    )
    assert preparation["required_sleeve_allocation_fraction"] == "1"
    assert preparation["required_position_notional_usdt"] == "1000"


def test_executable_aggregate_source_count_is_bounded_by_selected_boundaries_not_raw_rows() -> (
    None
):
    hour_ns = source_v1_fixture._HOUR_NS
    day_start = source_v1_fixture.aggregate_fixture.DAY_START_MS
    v1_request = source_v1_fixture._request(
        (
            (day_start + 20 * (hour_ns // 1_000_000) + 10_000, "12.340"),
            (day_start + 20 * (hour_ns // 1_000_000) + 20_000, "12.341"),
            (day_start + 22 * (hour_ns // 1_000_000) + 30_000, "12.342"),
        ),
        funding_raw=funding_fixture.compact(
            [funding_fixture.row(day_start + 20 * (hour_ns // 1_000_000))]
        ),
    )
    source_outcome = build_binance_usdm_koru_tradifi_source_projection_v2(
        source_v2_fixture._from_v1_request(v1_request)
    )
    assert source_outcome.result is not None
    result = _build(source_outcome.result)
    index = result.source_projection.request.aggregate_trade_boundary_index_result
    selected_ids = {value.event_id for value in index.selected_source_events}
    executable = tuple(
        value for value in result.events if value.event_id in selected_ids
    )

    assert len(executable) == len(selected_ids) == 2
    assert len(executable) <= len(index.request.boundaries)
    assert len(executable) < index.streamed_row_count == 3
    assert selected_ids == {
        value.source_event_id for value in result.source_projection.projection_lineage
    }


@pytest.mark.parametrize(
    "tamper", ("boundary", "source", "target", "profile", "gap")
)
def test_request_boundary_source_target_profile_and_gap_tamper_fail_closed(
    tamper: str,
) -> None:
    source = _source()
    target = _target(source)
    wire = bundle_v1_fixture._profile_wire(source)
    if tamper == "boundary":
        index = source.request.aggregate_trade_boundary_index_result
        object.__setattr__(index, "result_digest", "sha256:" + "0" * 64)
    elif tamper == "source":
        object.__setattr__(source, "fragment_digest", "sha256:" + "0" * 64)
    elif tamper == "target":
        object.__setattr__(target, "result_digest", "sha256:" + "0" * 64)
    elif tamper == "profile":
        wire["required_market_state_keys"] = ["tampered"]
    else:
        gap = source.aggregate_trade_intra_day_raw_id_gap_stream
        object.__setattr__(gap, "chain_digest", "sha256:" + "0" * 64)

    with pytest.raises((TypeError, ValueError), match=".+"):
        _request(source, target, wire)


def test_result_ref_digest_and_reader_replay_are_trusted_and_tamper_evident() -> None:
    first = _build()
    second = _build()

    assert canonical_bytes(first) == canonical_bytes(second)
    assert _trusted_result(first) is not None
    assert BinanceUsdmKoruTradifiExecutionBundleOutcomeV2(result=first).result is first
    for stream in first.manifest.streams:
        cursor = first.reader.open_cursor(stream.stream_key, batch_size=3)
        replayed = []
        while not cursor.exhausted:
            batch, cursor = first.reader.read_batch(cursor)
            replayed.extend(batch)
        assert tuple(replayed) == first.streams[stream.stream_key]

    object.__setattr__(
        second,
        "bundle_ref",
        MarketBundleRef(second.bundle_ref.bundle_key, "sha256:" + "0" * 64),
    )
    assert _trusted_result(second) is None
    with pytest.raises(ValueError, match="exact canonical V2"):
        BinanceUsdmKoruTradifiExecutionBundleOutcomeV2(result=second)

    third = _build()
    object.__setattr__(third, "result_digest", "sha256:" + "0" * 64)
    assert _trusted_result(third) is None
