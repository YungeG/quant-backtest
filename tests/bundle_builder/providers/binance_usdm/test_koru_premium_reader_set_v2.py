from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    KoruMarkIndexPremiumParametersV1,
    KoruPremiumReaderSetBuildRequestV1,
    KoruPremiumReaderSetBuildRequestV2,
    KoruPremiumRecipeAuthorityV1,
    build_koru_premium_reader_set_v1,
    build_koru_premium_reader_set_v2,
    canonical_koru_premium_payload_v1,
)
from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, canonical_bytes
from crypto_quant_market_data import KoruPremiumReaderSetV2, LocalMarketBundleReader

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_builder_v4 as v4_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_economics_bundle_v3 as v3_fixture,
)

_HASH = "sha256:" + "1" * 64


def _authority(source, number: int, entry: str) -> KoruPremiumRecipeAuthorityV1:
    premium_id = f"KORU-PRM-{number:02d}"
    recipe = __import__("crypto_quant_bundle_builder", fromlist=["x"]).KoruDirectionalTargetRecipeV1(
        family="mark_index_premium",
        recipe_id=premium_id,
        strategy_id=f"strategy-{premium_id}",
        sleeve_id=f"sleeve-{premium_id}",
        strategy_ref=ArtifactRef("strategy_definition", 1, _HASH),
        parameter_ref=ArtifactRef("strategy_parameter_set", 1, _HASH),
        target_stream_key=premium_id,
        instrument_id=source.source_events[0].instrument_id,
        target_exposure="0.25",
        bar_interval="1h",
        parameters=KoruMarkIndexPremiumParametersV1(entry, "5", 12),
    )
    strategy = ArtifactEnvelope.create(
        "strategy_definition", 1,
        canonical_koru_premium_payload_v1(recipe, artifact_type="strategy_definition"),
    )
    parameter = ArtifactEnvelope.create(
        "strategy_parameter_set", 1,
        canonical_koru_premium_payload_v1(recipe, artifact_type="strategy_parameter_set"),
    )
    return KoruPremiumRecipeAuthorityV1(
        replace(
            recipe,
            strategy_ref=ArtifactRef.from_envelope(strategy),
            parameter_ref=ArtifactRef.from_envelope(parameter),
        ),
        strategy,
        parameter,
    )


def _request(tmp_path: Path, authorities=None) -> KoruPremiumReaderSetBuildRequestV2:
    source, authority, authority_ref = v4_fixture._source_and_authority()
    economics = v4_fixture._economics(tmp_path / "economics", source, authority, authority_ref)
    authorities = authorities or tuple(
        _authority(source, number, entry)
        for number, entry in enumerate(("20", "30", "40", "60"), 1)
    )
    return KoruPremiumReaderSetBuildRequestV2(economics, authorities, tmp_path / "overlays")


def test_builds_four_v2_rows_compiles_once_reopens_and_replays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import crypto_quant_bundle_builder.koru_premium_reader_set_v2 as reader_set_builder

    calls = 0
    compile_once = reader_set_builder.compile_binance_usdm_koru_directional_targets_v2

    def counted_compile(request):
        nonlocal calls
        calls += 1
        return compile_once(request)

    monkeypatch.setattr(reader_set_builder, "compile_binance_usdm_koru_directional_targets_v2", counted_compile)
    first = build_koru_premium_reader_set_v2(_request(tmp_path))
    second = build_koru_premium_reader_set_v2(_request(tmp_path / "replay"))

    assert first.result is not None and second.result is not None
    assert calls == 2
    assert tuple(row.premium_id for row in first.result.bindings) == tuple(
        f"KORU-PRM-{number:02d}" for number in range(1, 5)
    )
    assert canonical_bytes(first.result) == canonical_bytes(second.result)
    for row in first.result.bindings:
        reader = first.result.reader_for(row.premium_id)
        assert reader.bundle_ref == row.overlay_bundle_ref
        assert row.target_stream_key == row.premium_id
        assert row.source_projection_authority_ref.schema_version == 3
        assert row.compiler_result_ref.schema_version == 2


def test_rejects_v1_substitution_reordered_duplicate_and_tampered_rows(tmp_path: Path) -> None:
    request = _request(tmp_path)
    with pytest.raises(TypeError, match="economics_bundle"):
        KoruPremiumReaderSetBuildRequestV2(
            v3_fixture._published(tmp_path / "v3-economics"),
            request.recipe_authorities,
            tmp_path / "overlays",
        )
    assert build_koru_premium_reader_set_v2(
        replace(request, recipe_authorities=request.recipe_authorities[::-1])
    ).failure is not None
    assert build_koru_premium_reader_set_v2(
        replace(request, recipe_authorities=(request.recipe_authorities[0],) * 4)
    ).failure is not None
    with pytest.raises(ValueError, match="frozen KORU premium scope"):
        KoruPremiumRecipeAuthorityV1(
            replace(request.recipe_authorities[0].recipe, target_stream_key="wrong"),
            request.recipe_authorities[0].strategy_definition_envelope,
            request.recipe_authorities[0].strategy_parameter_set_envelope,
        )


def test_rejects_v1_bindings_and_reader_replacements(tmp_path: Path) -> None:
    outcome = build_koru_premium_reader_set_v2(_request(tmp_path))
    assert outcome.result is not None
    reader_set = outcome.result
    v1_economics = v3_fixture._published(tmp_path / "v1-economics")
    v1_authorities = tuple(
        _authority(v1_economics.request.source_projection, number, entry)
        for number, entry in enumerate(("20", "30", "40", "60"), 1)
    )
    v1 = build_koru_premium_reader_set_v1(
        KoruPremiumReaderSetBuildRequestV1(
            v1_economics, v1_authorities, tmp_path / "v1-overlays"
        )
    )
    assert v1.result is not None
    with pytest.raises(TypeError, match="bindings"):
        KoruPremiumReaderSetV2(v1.result.bindings)
    with pytest.raises(ValueError, match="premium_reader_binding"):
        replace(reader_set.bindings[0], reader=reader_set.bindings[1].reader)
    substitute = LocalMarketBundleReader(reader_set.bindings[0].reader._delegate)
    with pytest.raises(ValueError, match="premium_reader_binding"):
        replace(reader_set.bindings[0], reader=substitute)
