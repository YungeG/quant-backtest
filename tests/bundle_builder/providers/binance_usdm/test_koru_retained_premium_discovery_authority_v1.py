from __future__ import annotations

from dataclasses import replace
from functools import cache

import crypto_quant_bundle_builder as builder
import crypto_quant_bundle_builder.koru_retained_premium_discovery_authority_v1 as premium_authority
import pytest
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    Money,
    Scale,
    UtcInstant,
    canonical_sha256,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v2 as execution_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v2 as source_fixture,
)

_HASH = "sha256:" + "a" * 64


def _source():
    _, request = source_fixture._request()
    outcome = builder.build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert outcome.result is not None
    return outcome.result


@cache
def _economics():
    return execution_fixture._build()


def _recipe(source=None, premium_id: str = "KORU-PRM-01", entry_bps: str = "20"):
    source = _source() if source is None else source
    placeholder = ArtifactRef("strategy_definition", 1, _HASH)
    recipe = builder.KoruDirectionalTargetRecipeV1(
        family="mark_index_premium",
        recipe_id=premium_id,
        strategy_id="strategy-" + premium_id,
        sleeve_id="sleeve-" + premium_id,
        strategy_ref=placeholder,
        parameter_ref=ArtifactRef("strategy_parameter_set", 1, _HASH),
        target_stream_key=premium_id,
        instrument_id=source.source_events[0].instrument_id,
        target_exposure="0.25",
        bar_interval="1h",
        parameters=builder.KoruMarkIndexPremiumParametersV1(entry_bps, "5", 12),
    )
    strategy = ArtifactEnvelope.create(
        "strategy_definition",
        1,
        builder.canonical_koru_premium_payload_v1(
            recipe, artifact_type="strategy_definition"
        ),
    )
    parameters = ArtifactEnvelope.create(
        "strategy_parameter_set",
        1,
        builder.canonical_koru_premium_payload_v1(
            recipe, artifact_type="strategy_parameter_set"
        ),
    )
    recipe = replace(
        recipe,
        strategy_ref=ArtifactRef.from_envelope(strategy),
        parameter_ref=ArtifactRef.from_envelope(parameters),
    )
    return recipe, strategy, parameters


def test_recipe_authority_exactly_binds_both_envelopes_and_rejects_tampering() -> None:
    recipe, strategy, parameters = _recipe()
    authority = builder.build_koru_premium_recipe_authority_v1(
        recipe, strategy, parameters
    )

    assert authority.strategy_ref == ArtifactRef.from_envelope(strategy)
    assert authority.parameter_ref == ArtifactRef.from_envelope(parameters)
    assert authority.premium_id == authority.premium_key == "KORU-PRM-01"

    tampered_strategy_payload = dict(strategy.payload)
    tampered_strategy_payload["entry_premium_bps"] = "30"
    tampered_strategy = ArtifactEnvelope.create(
        "strategy_definition", 1, tampered_strategy_payload
    )
    tampered_strategy_recipe = replace(
        recipe, strategy_ref=ArtifactRef.from_envelope(tampered_strategy)
    )
    with pytest.raises(ValueError, match="payload"):
        builder.build_koru_premium_recipe_authority_v1(
            tampered_strategy_recipe, tampered_strategy, parameters
        )

    tampered_parameter_payload = dict(parameters.payload)
    tampered_parameter_payload["entry_premium_bps"] = "30"
    tampered_parameter = ArtifactEnvelope.create(
        "strategy_parameter_set", 1, tampered_parameter_payload
    )
    tampered_parameter_recipe = replace(
        recipe, parameter_ref=ArtifactRef.from_envelope(tampered_parameter)
    )
    with pytest.raises(ValueError, match="payload"):
        builder.build_koru_premium_recipe_authority_v1(
            tampered_parameter_recipe, strategy, tampered_parameter
        )

    wrong_ref_recipe = replace(
        recipe, strategy_ref=ArtifactRef.from_envelope(parameters)
    )
    with pytest.raises(ValueError, match="refs"):
        builder.build_koru_premium_recipe_authority_v1(
            wrong_ref_recipe, strategy, parameters
        )


def _authority_request(source, targets, start, end, *, economics=None):
    source_request = source.request
    profile_wire = (
        {} if economics is None else economics.request.profile_composition_request_wire
    )
    return builder.KoruRetainedPremiumDiscoveryAuthorityRequestV1(
        start,
        end,
        source_request.instrument_catalog_hash,
        source_request.projection_scale,
        source_request.aggregate_trade_boundary_index_result,
        source_request.mark_price_results,
        source_request.index_price_results,
        source_request.funding_result,
        source_request.authority_result,
        targets,
        profile_wire,
        canonical_sha256(profile_wire),
        "account-1",
        Money(1_000_000_000_000, Scale(8), "USDT"),
        "1",
    )


def _declaration_authority():
    economics = _economics()
    source = economics.source_projection
    request = _authority_request(
        source,
        economics.target_result,
        source.request.timeline_window_start,
        source.request.timeline_window_end_exclusive,
    )
    envelope, ref = builder.build_binance_usdm_koru_source_profile_authority_v2(source)
    return builder.KoruRetainedPremiumDiscoveryAuthorityResultV1(
        request,
        source,
        ArtifactRef("binance_usdm_koru_source_projection", 2, source.fragment_digest),
        source.fragment_digest,
        envelope,
        ref,
        economics.bundle_ref,
        economics.bundle_ref.manifest_hash,
        economics.result_digest,
    )


def test_declaration_seals_four_ordered_rows_and_canonically_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _declaration_authority()
    source = authority.source_projection
    rows = tuple(
        builder.build_koru_premium_recipe_authority_v1(
            *_recipe(source, premium_id, entry)
        )
        for premium_id, entry in zip(
            ("KORU-PRM-01", "KORU-PRM-02", "KORU-PRM-03", "KORU-PRM-04"),
            ("20", "30", "40", "60"),
            strict=True,
        )
    )
    # The full-scope guard is covered separately; use the reduced existing V2
    # fixture solely to exercise declaration row invariants.
    monkeypatch.setattr(
        premium_authority,
        "build_binance_usdm_koru_tradifi_source_projection_v2",
        lambda _: builder.BinanceUsdmKoruTradifiSourceProjectionOutcomeV2(
            result=source
        ),
    )
    monkeypatch.setattr(premium_authority, "_scope_is_exact", lambda *_: True)

    declaration = builder.build_koru_premium_discovery_declaration_v1(authority, rows)
    assert tuple(row.premium_id for row in declaration.rows) == (
        "KORU-PRM-01",
        "KORU-PRM-02",
        "KORU-PRM-03",
        "KORU-PRM-04",
    )
    assert declaration == builder.build_koru_premium_discovery_declaration_v1(
        authority, rows
    )
    assert authority.legacy_v2_economics_declared_non_strategy

    with pytest.raises(ValueError, match="canonical premium rows"):
        builder.build_koru_premium_discovery_declaration_v1(authority, rows[::-1])
    with pytest.raises(ValueError, match="canonical premium rows"):
        builder.build_koru_premium_discovery_declaration_v1(authority, rows[:1] * 4)
    wrong_entry = builder.build_koru_premium_recipe_authority_v1(
        *_recipe(source, "KORU-PRM-01", "30")
    )
    with pytest.raises(ValueError, match="thresholds"):
        builder.build_koru_premium_discovery_declaration_v1(
            authority, (wrong_entry, *rows[1:])
        )


def test_retained_authority_wires_full_scope_source_and_economics_builders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    economics = _economics()
    source = economics.source_projection
    scope = builder.KoruDirectionalDiscoveryScopeV1()
    request = _authority_request(
        source,
        economics.target_result,
        scope.discovery_start,
        scope.discovery_end_exclusive,
        economics=economics,
    )
    source_requests = []
    economics_requests = []

    def source_builder(value):
        source_requests.append(value)
        return builder.BinanceUsdmKoruTradifiSourceProjectionOutcomeV2(result=source)

    def economics_builder(value):
        economics_requests.append(value)
        return builder.BinanceUsdmKoruTradifiExecutionBundleOutcomeV2(result=economics)

    monkeypatch.setattr(
        premium_authority,
        "build_binance_usdm_koru_tradifi_source_projection_v2",
        source_builder,
    )
    monkeypatch.setattr(
        premium_authority,
        "build_binance_usdm_koru_tradifi_execution_bundle_v2",
        economics_builder,
    )

    outcome = builder.build_koru_retained_premium_discovery_authority_v1(request)

    assert outcome.failure is None
    assert outcome.result is not None
    assert len(source_requests) == 2  # Initial build plus result replay.
    assert all(
        type(value) is builder.BinanceUsdmKoruTradifiSourceProjectionRequestV2
        for value in source_requests
    )
    assert all(
        value.timeline_window_start == scope.discovery_start
        for value in source_requests
    )
    assert all(
        value.timeline_window_end_exclusive == scope.discovery_end_exclusive
        for value in source_requests
    )
    assert len(economics_requests) == 1
    assert economics_requests[0].source_projection == source
    assert (
        economics_requests[0].source_projection.fragment_digest
        == source.fragment_digest
    )
    assert outcome.result.source_projection is source
    assert outcome.result.source_fragment_digest == source.fragment_digest
    assert outcome.result.source_projection_ref == ArtifactRef(
        "binance_usdm_koru_source_projection", 2, source.fragment_digest
    )
    assert outcome.result.legacy_v2_economics_bundle_ref == economics.bundle_ref
    assert (
        outcome.result.legacy_v2_economics_bundle_digest
        == economics.bundle_ref.manifest_hash
    )
    assert outcome.result.legacy_v2_economics_result_digest == economics.result_digest


def test_retained_authority_rejects_subwindow_and_holdout_before_building(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, source_request = source_fixture._request()
    source = _source()
    targets = builder.build_binance_usdm_koru_closed_market_range_targets_v2(
        builder.BinanceUsdmKoruClosedMarketRangeTargetsRequestV2(source)
    ).result
    assert targets is not None
    base = {
        "instrument_catalog_hash": source_request.instrument_catalog_hash,
        "projection_scale": source_request.projection_scale,
        "aggregate_trade_boundary_index_result": source_request.aggregate_trade_boundary_index_result,
        "mark_price_results": source_request.mark_price_results,
        "index_price_results": source_request.index_price_results,
        "funding_result": source_request.funding_result,
        "authority_result": source_request.authority_result,
        "legacy_v2_economics_target_result": targets,
        "profile_composition_request_wire": {},
        "profile_composition_request_hash": canonical_sha256({}),
        "execution_account_id": "account-1",
        "initial_equity": Money(1_000_000_000_000, Scale(8), "USDT"),
        "sleeve_allocation_fraction": "1",
    }
    source_calls = []
    economics_calls = []
    monkeypatch.setattr(
        premium_authority,
        "build_binance_usdm_koru_tradifi_source_projection_v2",
        lambda value: source_calls.append(value),
    )
    monkeypatch.setattr(
        premium_authority,
        "build_binance_usdm_koru_tradifi_execution_bundle_v2",
        lambda value: economics_calls.append(value),
    )
    scope = builder.KoruDirectionalDiscoveryScopeV1()
    for start, end in (
        (scope.discovery_start, source_request.timeline_window_end_exclusive),
        (
            scope.holdout_start,
            UtcInstant(scope.holdout_start.epoch_nanoseconds + 3_600_000_000_000),
        ),
    ):
        outcome = builder.build_koru_retained_premium_discovery_authority_v1(
            builder.KoruRetainedPremiumDiscoveryAuthorityRequestV1(
                timeline_window_start=start,
                timeline_window_end_exclusive=end,
                **base,
            )
        )
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is (
            builder.KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.DISCOVERY_SCOPE_INVALID
        )
    assert source_calls == []
    assert economics_calls == []
