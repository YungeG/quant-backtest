from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from crypto_quant_backtest import (
    BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1,
    BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
    BinanceUsdmProfileComposer,
    TimelineWindow,
    build_binance_usdm_koru_tradifi_development_profile_v1,
    decode_binance_usdm_tradifi_profile_composition_request_v1,
)
from crypto_quant_backtest.binance_usdm_koru_tradifi_development_profile_v1 import (
    _funding_resolutions,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v2 import (
    build_binance_usdm_koru_source_profile_authority_v2,
    build_binance_usdm_koru_tradifi_source_projection_v2,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_funding_rate_history_source_bounded_v1 as funding_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as source_v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v2 as source_v2_fixture,
)
from tests.runtime.profiles.binance_usdm._fixtures import (
    composition_request as ordinary_composition_request,
)


def _source():
    start_ms = (
        source_v1_fixture.aggregate_fixture.DAY_START_MS
        + 20 * source_v1_fixture.price_fixture.HOUR_MS
    )
    v1_request = source_v1_fixture._request(
        ((start_ms + 30 * 60_000, "12.340"),),
        funding_raw=funding_fixture.compact(
            [funding_fixture.row(start_ms, mark_price="20.39013424")]
        ),
    )
    outcome = build_binance_usdm_koru_tradifi_source_projection_v2(
        source_v2_fixture._from_v1_request(v1_request)
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


@pytest.fixture(scope="module")
def trusted_profile():
    source = _source()
    envelope, ref = build_binance_usdm_koru_source_profile_authority_v2(source)
    composed_ns = max(
        event.payload.get("acquired_at_epoch_nanoseconds", 0)
        for event in source.source_events
    ) + 1
    request = BinanceUsdmKoruTradifiDevelopmentProfileRequestV1(
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
    outcome = build_binance_usdm_koru_tradifi_development_profile_v1(request)
    assert outcome.failure is None and outcome.result is not None
    return source, request, outcome.result


def test_builds_from_real_trusted_source_projection_and_exact_wire_replay(
    trusted_profile,
) -> None:
    source, _, result = trusted_profile
    profile = result.profile_composition_request
    funding_manifest = next(
        value
        for value in source.stream_manifests
        if value.stream_key
        == "binance_usdm.funding_history.publications.koruusdt.v1"
    )
    execution_manifest = next(
        value
        for value in source.stream_manifests
        if value.stream_key
        == "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1"
    )

    assert profile.raw_exact_valuation is True
    assert (
        result.financial_dispatcher_spec.margin_component.component_key
        == "account.linear-perpetual.raw-valuation-margin-projection.v2"
    )
    assert len(profile.funding_sources) == funding_manifest.event_count == 1
    assert {value.model_key for value in profile.funding_sources} == {
        "crypto.binance_usdm.funding-sources.v2"
    }
    funding_mark = profile.funding_sources[0].funding_mark_evidence.resolved_mark.price
    assert funding_mark.units == 2_039_013_424
    assert funding_mark.scale.places == 8
    assert len(
        {value.query.application_key for value in profile.funding_sources}
    ) == funding_manifest.event_count
    assert profile.account_profile is not None
    assert profile.account_profile.position_mode == "one_way"
    assert profile.account_profile.asset_mode == "single_asset"
    assert profile.account_profile.margin_type == "CROSSED"
    assert profile.account_profile.active_band.maker_commission_rate == "0.00020000"
    assert profile.account_profile.active_band.taker_commission_rate == "0.00050000"
    assert profile.account_profile.active_band.max_notional_value == "10000.00000000"
    assert profile.admitted_maximum_quantity.units == 1_000_000
    execution = next(
        value
        for value in profile.price_purposes
        if value.query.price_purpose.value == "execution_reference"
    )
    coverage = execution.active_coverages[0]
    assert len(execution.visible_source_records) == execution_manifest.event_count
    assert coverage.coverage_from == execution.visible_source_records[0].trade_at
    assert coverage.coverage_to_exclusive.epoch_nanoseconds == (
        execution.visible_source_records[-1].trade_at.epoch_nanoseconds + 1
    )
    assert result.source_authority_verified is True
    assert result.source_profile_authority_ref == result.request.source_profile_authority_ref
    assert result.source_profile_authority_hash == (
        result.request.source_profile_authority_envelope.content_hash
    )
    assert (
        decode_binance_usdm_tradifi_profile_composition_request_v1(
            result.profile_composition_request_wire,
            result.profile_composition_request_hash,
        )
        == profile
    )
    assert result.result_digest == canonical_sha256(result._body())


def test_koru_factory_resolves_all_120_actual_raw_funding_marks(
    trusted_profile,
) -> None:
    _, request, result = trusted_profile
    normalized = funding_fixture.normalize(funding_fixture.RAW).result
    assert normalized is not None
    first = normalized.events[0].event_time
    last = normalized.events[-1].event_time
    factory_request = SimpleNamespace(
        account_id=request.account_id,
        composed_at=SimulationInstant(
            UtcInstant(funding_fixture.ACQUIRED_AT + 1),
            TimelinePhase(200, "profile_composition"),
            SourceSequence(0),
        ),
        timeline_window=TimelineWindow(
            first,
            first,
            UtcInstant(last.epoch_nanoseconds + 1),
        ),
    )

    resolutions = _funding_resolutions(
        factory_request,
        normalized.events,
        result.profile_composition_request.order_rules,
    )

    assert len(resolutions) == 120
    assert {value.model_key for value in resolutions} == {
        "crypto.binance_usdm.funding-sources.v2"
    }
    assert [value.mark_observation.price.units for value in resolutions] == [
        int(event.payload["raw_mark_price"].replace(".", ""))
        for event in normalized.events
    ]
    assert {value.mark_observation.price.scale.places for value in resolutions} == {8}


def test_authority_and_source_tamper_fail_closed(trusted_profile) -> None:
    _, request, _ = trusted_profile
    payload = dict(request.source_profile_authority_envelope.payload)
    payload["source_fragment_digest"] = "sha256:" + "0" * 64
    envelope = ArtifactEnvelope.create(
        "binance_usdm_koru_source_profile_authority", 2, payload
    )
    wrong_authority = replace(request)
    object.__setattr__(
        wrong_authority, "source_profile_authority_envelope", envelope
    )
    event = request.source_events[0]
    tampered_event = replace(event, source_hash="sha256:" + "0" * 64)
    wrong_event = replace(
        request,
        source_events=(tampered_event, *request.source_events[1:]),
    )

    for candidate, expected in (
        (
            wrong_authority,
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.INVALID_REQUEST,
        ),
        (
            wrong_event,
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
        ),
    ):
        outcome = build_binance_usdm_koru_tradifi_development_profile_v1(candidate)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected


@pytest.mark.parametrize(
    "mutation",
    ("missing_manifest", "manifest_shape", "binding_hash"),
)
def test_execution_projection_authority_shape_tamper_fails_closed(
    trusted_profile, mutation: str
) -> None:
    _, request, _ = trusted_profile
    payload = json.loads(canonical_bytes(request.source_profile_authority_envelope.payload))
    if mutation == "missing_manifest":
        del payload["execution_projection_stream_manifest"]
    elif mutation == "manifest_shape":
        payload["execution_projection_stream_manifest"]["capability"]["extra"] = True
    else:
        payload["execution_projection_event_bindings"][0]["event_hash"] = "invalid"
    envelope = ArtifactEnvelope.create(
        "binance_usdm_koru_source_profile_authority", 2, payload
    )
    candidate = replace(
        request,
        source_profile_authority_envelope=envelope,
        source_profile_authority_ref=ArtifactRef.from_envelope(envelope),
    )

    outcome = build_binance_usdm_koru_tradifi_development_profile_v1(candidate)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID
    )


def test_calendar_unit_timeline_and_trading_start_tamper_fail_closed(
    trusted_profile,
) -> None:
    _, request, _ = trusted_profile
    wrong_calendar = replace(
        request,
        xkrx_calendar_ref=ArtifactRef(
            "xkrx_regular_session_calendar", 1, "sha256:" + "1" * 64
        ),
    )
    wrong_unit = replace(
        request,
        post_adjustment_unit_regime_ref=ArtifactRef(
            "binance_usdm_tradifi_post_adjustment_unit_regime",
            1,
            "sha256:" + "2" * 64,
        ),
    )
    shifted = UtcInstant(request.timeline_window.data_start.epoch_nanoseconds + 1)
    wrong_trading_start = replace(
        request,
        timeline_window=TimelineWindow(
            request.timeline_window.data_start,
            shifted,
            request.timeline_window.end_exclusive,
        ),
    )

    for candidate, expected in (
        (wrong_calendar, BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID),
        (wrong_unit, BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID),
        (wrong_trading_start, BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.TIMELINE_INVALID),
    ):
        outcome = build_binance_usdm_koru_tradifi_development_profile_v1(candidate)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected


def test_fabricated_incomplete_source_cover_is_rejected(trusted_profile) -> None:
    _, request, _ = trusted_profile
    incomplete = replace(request, source_events=request.source_events[:-1])
    outcome = build_binance_usdm_koru_tradifi_development_profile_v1(incomplete)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID
    )


def test_ordinary_profile_hash_remains_unchanged() -> None:
    ordinary = BinanceUsdmProfileComposer().compose(ordinary_composition_request())
    assert ordinary.result is not None
    assert ordinary.result.profile_digest == (
        "sha256:5f0ab193c16122b85f12779cce233da2d9e9d239cff2f2239c6e0ae5bdb5b583"
    )
