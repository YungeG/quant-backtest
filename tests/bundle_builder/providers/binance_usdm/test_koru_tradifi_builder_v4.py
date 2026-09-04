from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from crypto_quant_bundle_builder import (
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetCompileRequestV2,
    KoruTradifiEconomicsBundleRequestV4,
    KoruTradifiEconomicsTermsV4,
    KoruTradifiSourceProjectionContentIdentityV3,
    KoruTradifiTargetOverlayRequestV4,
    SourceProjectionV3,
    build_binance_usdm_koru_source_profile_authority_v3,
    build_binance_usdm_koru_tradifi_source_projection_v3,
    compile_binance_usdm_koru_directional_targets_v2,
    create_binance_usdm_koru_tradifi_source_projection_authority_v3,
    publish_koru_tradifi_economics_bundle_v4,
    publish_koru_tradifi_target_overlay_v4,
)
from crypto_quant_domain import ArtifactRef, canonical_bytes

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_directional_target_compiler_v1 as recipe_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_economics_bundle_v3 as economics_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v3 as source_fixture,
)


def _source_and_authority():
    outcome = build_binance_usdm_koru_tradifi_source_projection_v3(source_fixture._request())
    assert outcome.result is not None
    authority, ref = create_binance_usdm_koru_tradifi_source_projection_authority_v3(outcome.result)
    return outcome.result, authority, ref


def _compiler(source, authority, authority_ref, *, two_targets: bool = False):
    recipes = (recipe_fixture._recipe(source),)
    if two_targets:
        recipes += (recipe_fixture._recipe(source, key="target.z"),)
    outcome = compile_binance_usdm_koru_directional_targets_v2(
        KoruDirectionalTargetCompileRequestV2(
            source,
            authority_ref,
            authority.content_hash,
            KoruDirectionalDiscoveryScopeV1(),
            recipes,
        )
    )
    assert outcome.result is not None
    return outcome.result


def _economics(tmp_path: Path, source, authority, authority_ref):
    identity = KoruTradifiSourceProjectionContentIdentityV3(
        authority_ref,
        authority.content_hash,
        source.fragment_digest,
        source.request.request_hash,
    )
    outcome = publish_koru_tradifi_economics_bundle_v4(
        KoruTradifiEconomicsBundleRequestV4(
            source,
            identity,
            KoruTradifiEconomicsTermsV4.from_source_projection(source, execution_account_id="account-1"),
            economics_fixture._MemoryArtifactStore(),
            tmp_path,
        )
    )
    assert outcome.result is not None
    return outcome.result


def _events(reader, stream_key):
    cursor = reader.open_cursor(stream_key, batch_size=64)
    events = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    return tuple(events)


def test_v4_authority_chain_copies_economics_bytes_and_adds_one_target(tmp_path: Path) -> None:
    source, source_authority, source_authority_ref = _source_and_authority()
    compiler = _compiler(source, source_authority, source_authority_ref, two_targets=True)
    economics = _economics(tmp_path / "economics", source, source_authority, source_authority_ref)
    target = compiler.streams[0]
    overlay = publish_koru_tradifi_target_overlay_v4(
        KoruTradifiTargetOverlayRequestV4(
            economics,
            compiler,
            ArtifactRef("koru_directional_target_compile_result", 2, compiler.result_digest),
            ArtifactRef("koru_directional_discovery_scope", 1, compiler.request.scope.scope_digest),
            target.target_stream_key,
            tmp_path / "overlay",
        )
    ).result

    assert overlay is not None
    assert len(compiler.streams) == 2
    assert _events(overlay.reader, target.target_stream_key) == target.events
    for event in target.events:
        candidate = event.payload["candidate"]
        assert isinstance(candidate, Mapping)
        evidence_payload = candidate["evidence"]
        assert isinstance(evidence_payload, Mapping)
        evidence = evidence_payload["source_events"]
        assert isinstance(evidence, tuple)
        assert len(evidence) == (
            2
            if event.event_time.epoch_nanoseconds + 3_600_000_000_000
            == source.request.timeline_window_end_exclusive.epoch_nanoseconds
            else 3
        )
        assert isinstance(evidence[0], Mapping)
        assert isinstance(evidence[1], Mapping)
        assert evidence[0]["event_time"] == event.event_time.epoch_nanoseconds
        assert evidence[1]["event_time"] == event.event_time.epoch_nanoseconds
    assert compiler.streams[1].target_stream_key not in {
        stream.stream_key for stream in overlay.manifest.streams
    }
    assert {
        stream.stream_key for stream in overlay.manifest.streams
    } - {stream.stream_key for stream in economics.manifest.streams} == {
        target.target_stream_key,
        "binance_usdm.tradifi.target_overlay_authority.koruusdt.v4",
    }
    for stream in economics.manifest.streams:
        assert canonical_bytes(_events(overlay.reader, stream.stream_key)) == canonical_bytes(
            _events(economics.reader, stream.stream_key)
        )
    payload = overlay.authority_event.payload
    assert payload["source_projection_authority_ref"] == source_authority_ref.to_canonical_dict()
    assert payload["source_fragment_digest"] == source.fragment_digest
    assert payload["aggregate_trade_boundary_index_result_digest"] == source.aggregate_trade_boundary_index_result_digest
    assert payload["compiler_result_ref"] == ArtifactRef(
        "koru_directional_target_compile_result", 2, compiler.result_digest
    ).to_canonical_dict()
    assert payload["economics_bundle_ref"] == economics.bundle_ref.to_canonical_dict()


def test_v4_replay_and_tampered_authority_bindings_fail_closed(tmp_path: Path) -> None:
    source, source_authority, source_authority_ref = _source_and_authority()
    compiler = _compiler(source, source_authority, source_authority_ref)
    economics = _economics(tmp_path / "economics", source, source_authority, source_authority_ref)
    request = KoruTradifiTargetOverlayRequestV4(
        economics,
        compiler,
        ArtifactRef("koru_directional_target_compile_result", 2, compiler.result_digest),
        ArtifactRef("koru_directional_discovery_scope", 1, compiler.request.scope.scope_digest),
        compiler.streams[0].target_stream_key,
        tmp_path / "overlay",
    )
    first = publish_koru_tradifi_target_overlay_v4(request)
    second = publish_koru_tradifi_target_overlay_v4(request)
    assert first.result is not None and second.result is not None
    assert canonical_bytes(first.result) == canonical_bytes(second.result)

    with pytest.raises(ValueError, match="compiler_result_ref"):
        replace(request, compiler_result_ref=ArtifactRef("koru_directional_target_compile_result", 1, compiler.result_digest))
    with pytest.raises(ValueError, match="source_projection_authority"):
        KoruDirectionalTargetCompileRequestV2(
            source,
            ArtifactRef(source_authority_ref.artifact_type, source_authority_ref.schema_version, "sha256:" + "0" * 64),
            source_authority.content_hash,
            KoruDirectionalDiscoveryScopeV1(),
            (recipe_fixture._recipe(source),),
        )


def test_v4_rejects_v2_source_and_keeps_v2_v3_sentinels() -> None:
    v2_source = economics_fixture._source()
    with pytest.raises(TypeError, match="SourceProjectionV3"):
        KoruDirectionalTargetCompileRequestV2(
            cast(SourceProjectionV3, v2_source),
            ArtifactRef("binance_usdm_koru_source_projection", 2, v2_source.fragment_digest),
            "sha256:" + "0" * 64,
            KoruDirectionalDiscoveryScopeV1(),
            (recipe_fixture._recipe(v2_source),),
        )
    source, _, _ = _source_and_authority()
    with pytest.raises(ValueError, match="source_projection_authority"):
        KoruDirectionalTargetCompileRequestV2(
            source,
            ArtifactRef("binance_usdm_koru_source_projection", 2, source.fragment_digest),
            source.fragment_digest,
            KoruDirectionalDiscoveryScopeV1(),
            (recipe_fixture._recipe(source),),
        )
    profile, profile_ref = build_binance_usdm_koru_source_profile_authority_v3(source)
    assert profile.schema_version == 3
    assert profile_ref.content_hash == profile.content_hash
    assert profile.payload["source_projection_authority_ref"]["schema_version"] == 3
    assert economics_fixture.v1_fixture._empty_result().manifest.schema_version == 1
    assert economics_fixture.v2_fixture._build().manifest.schema_version == 2
