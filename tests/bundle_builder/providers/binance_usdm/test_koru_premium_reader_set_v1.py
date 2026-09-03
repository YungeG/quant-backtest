from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    KoruMarkIndexPremiumParametersV1,
    KoruPremiumReaderSetBuildRequestV1,
    KoruPremiumRecipeAuthorityV1,
    build_koru_premium_reader_set_v1,
    canonical_koru_premium_payload_v1,
)
from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, canonical_bytes
from crypto_quant_market_data import KoruPremiumReaderSetV1

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_economics_bundle_v3 as economics_fixture,
)

_HASH = "sha256:" + "1" * 64


def _authority(source, number: int, entry: str) -> KoruPremiumRecipeAuthorityV1:
    premium_id = f"KORU-PRM-{number:02d}"
    recipe = __import__("crypto_quant_bundle_builder", fromlist=["x"]).KoruDirectionalTargetRecipeV1(
        family="mark_index_premium", recipe_id=premium_id, strategy_id=f"strategy-{premium_id}",
        sleeve_id=f"sleeve-{premium_id}", strategy_ref=ArtifactRef("strategy_definition", 1, _HASH),
        parameter_ref=ArtifactRef("strategy_parameter_set", 1, _HASH), target_stream_key=premium_id,
        instrument_id=source.source_events[0].instrument_id, target_exposure="0.25", bar_interval="1h",
        parameters=KoruMarkIndexPremiumParametersV1(entry, "5", 12),
    )
    strategy = ArtifactEnvelope.create("strategy_definition", 1, canonical_koru_premium_payload_v1(recipe, artifact_type="strategy_definition"))
    parameter = ArtifactEnvelope.create("strategy_parameter_set", 1, canonical_koru_premium_payload_v1(recipe, artifact_type="strategy_parameter_set"))
    return KoruPremiumRecipeAuthorityV1(replace(recipe, strategy_ref=ArtifactRef.from_envelope(strategy), parameter_ref=ArtifactRef.from_envelope(parameter)), strategy, parameter)


def _request(tmp_path: Path, authorities=None) -> KoruPremiumReaderSetBuildRequestV1:
    economics = economics_fixture._published(tmp_path / "economics")
    authorities = authorities or tuple(
        _authority(economics.request.source_projection, number, entry)
        for number, entry in enumerate(("20", "30", "40", "60"), 1)
    )
    return KoruPremiumReaderSetBuildRequestV1(economics, authorities, tmp_path / "overlays")


def test_builds_exact_four_reopenable_overlay_readers_and_replays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import crypto_quant_bundle_builder.koru_premium_reader_set_v1 as reader_set_builder

    calls = 0
    compile_once = reader_set_builder.compile_binance_usdm_koru_directional_targets_v1

    def counted_compile(request):
        nonlocal calls
        calls += 1
        return compile_once(request)

    monkeypatch.setattr(reader_set_builder, "compile_binance_usdm_koru_directional_targets_v1", counted_compile)
    first = build_koru_premium_reader_set_v1(_request(tmp_path))
    second = build_koru_premium_reader_set_v1(_request(tmp_path / "replay"))

    assert first.result is not None and second.result is not None
    assert calls == 2  # One compilation per public operation, never one per row.
    assert tuple(row.premium_id for row in first.result.bindings) == tuple(f"KORU-PRM-{number:02d}" for number in range(1, 5))
    assert canonical_bytes(first.result) == canonical_bytes(second.result)
    for row in first.result.bindings:
        reader = first.result.reader_for(row.premium_id)
        assert reader.bundle_ref == row.overlay_bundle_ref
        assert row.target_stream_key == row.premium_id


def test_rejects_reordered_duplicate_and_tampered_recipe_authorities(tmp_path: Path) -> None:
    request = _request(tmp_path)
    assert build_koru_premium_reader_set_v1(replace(request, recipe_authorities=request.recipe_authorities[::-1])).failure is not None
    assert build_koru_premium_reader_set_v1(replace(request, recipe_authorities=(request.recipe_authorities[0],) * 4)).failure is not None
    tampered = replace(request.recipe_authorities[0].recipe, target_stream_key="wrong")
    with pytest.raises(ValueError, match="frozen KORU premium scope"):
        KoruPremiumRecipeAuthorityV1(tampered, request.recipe_authorities[0].strategy_definition_envelope, request.recipe_authorities[0].strategy_parameter_set_envelope)


def test_reader_set_rejects_mixed_authority_and_omits_live_reader_from_identity(tmp_path: Path) -> None:
    outcome = build_koru_premium_reader_set_v1(_request(tmp_path))
    assert outcome.result is not None
    reader_set = outcome.result
    swapped = replace(reader_set.bindings[0], economics_authority_digest="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="shared premium authority"):
        KoruPremiumReaderSetV1((swapped, *reader_set.bindings[1:]))
    assert canonical_bytes(reader_set) == canonical_bytes(
        replace(reader_set, bindings=(replace(reader_set.bindings[0], reader=reader_set.bindings[1].reader), *reader_set.bindings[1:]))
    )
