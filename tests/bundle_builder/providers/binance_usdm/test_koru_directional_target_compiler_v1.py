from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import crypto_quant_bundle_builder as bundle_builder
import pytest
from crypto_quant_bundle_builder import (
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetCompileFailureCodeV1,
    KoruDirectionalTargetCompileOutcomeV1,
    KoruDirectionalTargetCompileRequestV1,
    KoruDirectionalTargetCompileResultV1,
    KoruDirectionalTargetRecipeV1,
    KoruMarkIndexPremiumParametersV1,
    compile_binance_usdm_koru_directional_targets_v1,
)
from crypto_quant_bundle_builder import (
    binance_usdm_koru_directional_target_compiler_v1 as target_compiler,
)
from crypto_quant_bundle_builder.binance_usdm_koru_directional_target_compiler_v1 import (
    KoruDirectionalUnsupportedParametersV1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v2 import (
    build_binance_usdm_koru_tradifi_source_projection_v2,
)
from crypto_quant_domain import ArtifactRef, UtcInstant

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v2 as v2_fixture,
)

_HASH = "sha256:" + "1" * 64


def _source(trade_hour: int = 22):
    _, request = v2_fixture._request(trade_hour=trade_hour)
    outcome = build_binance_usdm_koru_tradifi_source_projection_v2(request)
    assert outcome.result is not None
    return outcome.result


def _recipe(source, *, family: str = "mark_index_premium", key: str = "target.a"):
    parameters = (
        KoruMarkIndexPremiumParametersV1("20", "5", 12)
        if family == "mark_index_premium"
        else KoruDirectionalUnsupportedParametersV1(family)
    )
    return KoruDirectionalTargetRecipeV1(
        family=family,
        recipe_id="recipe-" + key,
        strategy_id="strategy-" + key,
        sleeve_id="sleeve-a",
        strategy_ref=ArtifactRef("strategy_definition", 1, _HASH),
        parameter_ref=ArtifactRef("strategy_parameter_set", 1, _HASH),
        target_stream_key=key,
        instrument_id=source.source_events[0].instrument_id,
        target_exposure="0.25",
        bar_interval="1h",
        parameters=parameters,
    )


def _request(source, recipes):
    return KoruDirectionalTargetCompileRequestV1(
        source,
        ArtifactRef("binance_usdm_koru_source_projection", 2, source.fragment_digest),
        source.fragment_digest,
        KoruDirectionalDiscoveryScopeV1(),
        recipes,
    )


def _values(outcome):
    assert outcome.result is not None
    return tuple(
        event.payload["candidate"]["targets"][0]["value"]
        for event in outcome.result.streams[0].events
    )


def test_premium_flat_and_causal_boundary_evidence() -> None:
    source = _source()
    outcome = compile_binance_usdm_koru_directional_targets_v1(
        _request(source, (_recipe(source),))
    )

    assert outcome.failure is None
    assert _values(outcome) == ("0", "0", "0")
    result = outcome.result
    assert result is not None
    event = result.streams[0].events[0]
    candidate = event.payload["candidate"]
    assert isinstance(candidate, Mapping)
    assert candidate["effective_time"] == event.event_time.epoch_nanoseconds
    evidence = candidate["evidence"]
    assert isinstance(evidence, Mapping)
    assert len(evidence["source_events"]) == 3


@pytest.mark.parametrize(("mark_close", "expected"), (("12.00000000", "0.25"), ("13.00000000", "-0.25")))
def test_premium_long_and_short_flatten_at_terminal(mark_close: str, expected: str, monkeypatch) -> None:
    def premium_prices(source_kind, utc_date):
        rows = list(v1_fixture._price_rows(v1_fixture._day_start_ms(utc_date)))
        if source_kind.value == "mark_price":
            high, low = (
                ("12.50000000", "11.50000000")
                if mark_close == "12.00000000"
                else ("13.50000000", "12.00000000")
            )
            rows = [(row[0], row[1], high, low, mark_close, *row[5:]) for row in rows]
        archive, checksum = v1_fixture.price_fixture.evidence(
            tuple(rows),
            member_name=f"KORUUSDT-1h-{utc_date}.csv",
            checksum_name=f"KORUUSDT-1h-{utc_date}.zip",
        )
        day_start_ns = v1_fixture._day_start_ms(utc_date) * 1_000_000
        request = v1_fixture.price_fixture.request_for(
            source_kind, archive, checksum, utc_date=utc_date,
            archive_available_at=day_start_ns + v1_fixture._DAY_NS,
            acquired_at=day_start_ns + 2 * v1_fixture._DAY_NS,
        )
        archive_url, checksum_url = request.urls
        capture = v1_fixture.price_fixture.capture_binance_usdm_koru_price_bars_source_bounded_v1(
            request, v1_fixture.price_fixture.Fetch({archive_url: [(200, archive)], checksum_url: [(200, checksum)]})
        ).result
        assert capture is not None
        result = v1_fixture.price_fixture.normalize_binance_usdm_koru_price_bars_source_bounded_v1(capture).result
        assert result is not None
        return result

    monkeypatch.setattr(v1_fixture, "_price_result", premium_prices)
    source = _source()
    outcome = compile_binance_usdm_koru_directional_targets_v1(_request(source, (_recipe(source),)))

    assert outcome.failure is None
    assert _values(outcome) == (expected, expected, "0")
    assert outcome.result is not None
    terminal = outcome.result.streams[0].events[-1]
    assert terminal.event_time.epoch_nanoseconds + v1_fixture._HOUR_NS == source.request.timeline_window_end_exclusive.epoch_nanoseconds
    terminal_candidate = terminal.payload["candidate"]
    assert isinstance(terminal_candidate, Mapping)
    terminal_evidence = terminal_candidate["evidence"]
    assert isinstance(terminal_evidence, Mapping)
    assert len(terminal_evidence["source_events"]) == 2

    source_without_next_boundary = _source(20)
    missing_boundary = compile_binance_usdm_koru_directional_targets_v1(
        _request(source_without_next_boundary, (_recipe(source_without_next_boundary),))
    )
    assert missing_boundary.failure is not None
    assert (
        missing_boundary.failure.code
        is KoruDirectionalTargetCompileFailureCodeV1.NEXT_BOUNDARY_EVIDENCE_MISSING
    )


def test_source_ref_binding_and_root_exports() -> None:
    scope = KoruDirectionalDiscoveryScopeV1()
    with pytest.raises(ValueError, match="frozen discovery interval"):
        KoruDirectionalDiscoveryScopeV1(
            scope.discovery_start,
            scope.discovery_end_exclusive,
            UtcInstant(scope.holdout_start.epoch_nanoseconds + v1_fixture._HOUR_NS),
        )

    source = _source()
    request = _request(source, (_recipe(source),))
    object.__setattr__(
        request,
        "source_projection_ref",
        ArtifactRef("binance_usdm_koru_source_projection", 2, _HASH),
    )
    outcome = compile_binance_usdm_koru_directional_targets_v1(request)

    assert outcome.failure is not None
    assert outcome.failure.code is KoruDirectionalTargetCompileFailureCodeV1.INVALID_REQUEST
    from crypto_quant_bundle_builder.binance_usdm_koru_directional_target_compiler_v1 import (
        __all__ as compiler_exports,
    )

    assert all(hasattr(bundle_builder, name) for name in compiler_exports)


def test_result_replays_request_and_rejects_duplicate_streams() -> None:
    source = _source()
    outcome = compile_binance_usdm_koru_directional_targets_v1(_request(source, (_recipe(source),)))
    assert outcome.result is not None

    with pytest.raises(ValueError, match="exactly replay"):
        KoruDirectionalTargetCompileResultV1(
            outcome.result.request, outcome.result.streams + outcome.result.streams
        )

    stream = outcome.result.streams[0]
    object.__setattr__(stream, "target_stream_digest", _HASH)
    with pytest.raises(ValueError, match="exact replayed compilation"):
        KoruDirectionalTargetCompileOutcomeV1(result=outcome.result)


def test_missing_immediate_boundary_rejects_later_lineage_while_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    decision = min(
        event.event_time.epoch_nanoseconds
        for event in source.source_events
        if event.payload.get("source_kind") == "mark_price"
    )
    immediate = decision + v1_fixture._HOUR_NS
    assert any(
        lineage.hourly_boundary.epoch_nanoseconds > immediate
        for lineage in source.projection_lineage
    )
    object.__setattr__(
        source,
        "projection_lineage",
        tuple(
            lineage
            for lineage in source.projection_lineage
            if lineage.hourly_boundary.epoch_nanoseconds != immediate
        ),
    )
    monkeypatch.setattr(target_compiler, "_trusted_source", lambda _: source)

    outcome = compile_binance_usdm_koru_directional_targets_v1(
        _request(source, (_recipe(source),))
    )

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is KoruDirectionalTargetCompileFailureCodeV1.NEXT_BOUNDARY_EVIDENCE_MISSING
    )


def test_failures_and_recipe_ordering() -> None:
    source = _source()
    premium = _recipe(source, key="target.z")
    earlier = _recipe(source, key="target.a")
    unordered = _request(source, (premium, earlier))
    outcome = compile_binance_usdm_koru_directional_targets_v1(unordered)
    assert outcome.failure is not None
    assert outcome.failure.code is KoruDirectionalTargetCompileFailureCodeV1.INVALID_REQUEST

    breakout = _recipe(source, family="breakout")
    outcome = compile_binance_usdm_koru_directional_targets_v1(_request(source, (breakout,)))
    assert outcome.failure is not None
    assert outcome.failure.code is KoruDirectionalTargetCompileFailureCodeV1.CALENDAR_AVAILABILITY_UNPROVEN

    funding = _recipe(source, family="funding_carry")
    outcome = compile_binance_usdm_koru_directional_targets_v1(_request(source, (funding,)))
    assert outcome.failure is not None
    assert outcome.failure.code is KoruDirectionalTargetCompileFailureCodeV1.UNSUPPORTED_RECIPE_FAMILY

    holdout_source = replace(
        source.request,
        timeline_window_end_exclusive=KoruDirectionalDiscoveryScopeV1().holdout_start,
    )
    # A tampered accepted projection is rejected before any target is emitted.
    object.__setattr__(source, "request", holdout_source)
    try:
        outcome = compile_binance_usdm_koru_directional_targets_v1(_request(source, (_recipe(source),)))
        assert outcome.failure is not None
        assert outcome.failure.code in {
            KoruDirectionalTargetCompileFailureCodeV1.SOURCE_PROJECTION_INVALID,
            KoruDirectionalTargetCompileFailureCodeV1.HOLDOUT_SOURCE_INPUT,
        }
    finally:
        object.__setattr__(source, "request", v2_fixture._request(trade_hour=22)[1])
