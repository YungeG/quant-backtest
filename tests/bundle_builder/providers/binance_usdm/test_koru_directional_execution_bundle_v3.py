from __future__ import annotations

from dataclasses import replace

import pytest
from crypto_quant_bundle_builder import (
    BinanceUsdmKoruDirectionalExecutionBundleRequestV3,
    KoruDirectionalDiscoveryScopeV1,
    build_binance_usdm_koru_directional_execution_bundle_v3,
    compile_binance_usdm_koru_directional_targets_v1,
)
from crypto_quant_domain import ArtifactRef, canonical_bytes

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_directional_target_compiler_v1 as compiler_fixture,
)


def _compiled():
    source = compiler_fixture._source()
    outcome = compile_binance_usdm_koru_directional_targets_v1(
        compiler_fixture._request(source, (compiler_fixture._recipe(source),))
    )
    assert outcome.result is not None
    return outcome.result


def _request():
    result = _compiled()
    return BinanceUsdmKoruDirectionalExecutionBundleRequestV3(
        result,
        ArtifactRef("koru_directional_target_compile_result", 1, result.result_digest),
        ArtifactRef("koru_directional_discovery_scope", 1, result.request.scope.scope_digest),
        result.streams[0].target_stream_key,
    )


def test_publishes_exact_compiler_target_bytes_and_authority_bindings() -> None:
    outcome = build_binance_usdm_koru_directional_execution_bundle_v3(_request())
    assert outcome.result is not None
    bundle = outcome.result
    target = bundle.selected_stream
    payload = bundle.preparation_authority_event.payload

    assert bundle.streams[target.target_stream_key] == target.events
    assert payload["target_events"] == tuple(event.to_canonical_dict() for event in target.events)
    assert payload["target_stream_manifest"] == target.manifest.to_canonical_dict()
    assert payload["target_stream_digest"] == target.target_stream_digest
    assert payload["compiler_result_digest"] == bundle.compiler_result.result_digest
    assert payload["scope_digest"] == KoruDirectionalDiscoveryScopeV1().scope_digest
    assert canonical_bytes(payload["scope"]) == canonical_bytes(KoruDirectionalDiscoveryScopeV1())


def test_replay_and_tampered_result_or_bare_ref_fail_closed() -> None:
    request = _request()
    first = build_binance_usdm_koru_directional_execution_bundle_v3(request)
    second = build_binance_usdm_koru_directional_execution_bundle_v3(request)
    assert first.result is not None and second.result is not None
    assert canonical_bytes(first.result) == canonical_bytes(second.result)

    with pytest.raises(ValueError, match="compiler_result_ref"):
        replace(
            request,
            compiler_result_ref=ArtifactRef(
                "koru_directional_target_compile_result", 1, "sha256:" + "0" * 64
            ),
        )

    object.__setattr__(request.compiler_result, "result_digest", "sha256:" + "0" * 64)
    assert build_binance_usdm_koru_directional_execution_bundle_v3(request).failure is not None
