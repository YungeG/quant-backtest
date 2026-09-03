from __future__ import annotations

from dataclasses import replace

import pytest
from crypto_quant_bundle_builder import (
    KoruDirectionalDiscoveryScopeV1,
    KoruTradifiTargetOverlayRequestV3,
    compile_binance_usdm_koru_directional_targets_v1,
    publish_koru_tradifi_target_overlay_v3,
)
from crypto_quant_domain import ArtifactRef, canonical_bytes

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_directional_target_compiler_v1 as compiler_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_economics_bundle_v3 as economics_fixture,
)


def _compiled(source):
    outcome = compile_binance_usdm_koru_directional_targets_v1(
        compiler_fixture._request(source, (compiler_fixture._recipe(source),))
    )
    assert outcome.result is not None
    return outcome.result


def _request(tmp_path):
    economics = economics_fixture._published(tmp_path / "economics")
    result = _compiled(economics.request.source_projection)
    return KoruTradifiTargetOverlayRequestV3(
        economics,
        result,
        ArtifactRef("koru_directional_target_compile_result", 1, result.result_digest),
        ArtifactRef("koru_directional_discovery_scope", 1, result.request.scope.scope_digest),
        result.streams[0].target_stream_key,
        tmp_path / "overlay",
    )


def _events(reader, stream_key):
    cursor = reader.open_cursor(stream_key, batch_size=64)
    events = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    return tuple(events)


def test_overlay_publishes_exact_compiler_target_bytes_and_separate_authority_bindings(tmp_path) -> None:
    request = _request(tmp_path)
    outcome = publish_koru_tradifi_target_overlay_v3(request)

    assert outcome.result is not None
    overlay = outcome.result
    target = overlay.selected_stream
    payload = overlay.authority_event.payload

    assert _events(overlay.reader, target.target_stream_key) == target.events
    assert payload["target_events"] == tuple(event.to_canonical_dict() for event in target.events)
    assert payload["target_stream_manifest"] == target.manifest.to_canonical_dict()
    assert payload["target_stream_digest"] == target.target_stream_digest
    assert payload["compiler_result_digest"] == overlay.request.compiler_result.result_digest
    assert payload["scope_digest"] == KoruDirectionalDiscoveryScopeV1().scope_digest
    assert canonical_bytes(payload["scope"]) == canonical_bytes(KoruDirectionalDiscoveryScopeV1())
    assert payload["economics_bundle_ref"] == request.economics_bundle.bundle_ref.to_canonical_dict()
    assert all(".target." not in stream.stream_key for stream in request.economics_bundle.manifest.streams)


def test_overlay_replay_and_mismatched_compiler_bindings_fail_closed(tmp_path) -> None:
    request = _request(tmp_path)
    first = publish_koru_tradifi_target_overlay_v3(request)
    second = publish_koru_tradifi_target_overlay_v3(request)
    assert first.result is not None and second.result is not None
    assert canonical_bytes(first.result) == canonical_bytes(second.result)

    with pytest.raises(ValueError, match="compiler_result_ref"):
        replace(
            request,
            compiler_result_ref=ArtifactRef(
                "koru_directional_target_compile_result", 1, "sha256:" + "0" * 64
            ),
        )
