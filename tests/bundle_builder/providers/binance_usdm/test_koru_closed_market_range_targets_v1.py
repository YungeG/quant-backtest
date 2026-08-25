from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal, localcontext
from functools import cache
from typing import Any, cast

import pytest
from crypto_quant_backtest import (
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
    TimelineEvent,
    TimelineSegment,
)
from crypto_quant_bundle_builder.binance_usdm_koru_closed_market_range_targets_v1 import (
    BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1,
    BinanceUsdmKoruClosedMarketRangeTargetsRequestV1,
    BinanceUsdmKoruClosedMarketRangeTargetsResultV1,
    BinanceUsdmKoruClosedMarketRangeTargetStreamResultV1,
    _BarPair,
    _closed_intervals,
    _exit,
    _formation_range_exceeds,
    _manifest,
    _parameter_bindings,
    _premium,
    _Projection,
    _projections,
    _strategy_binding,
    _strategy_pairs,
    _stream_events,
    _target_stream_digest,
    _trusted_result,
    build_binance_usdm_koru_closed_market_range_targets_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v1 import (
    BinanceUsdmKoruTradifiSourceProjectionResultV1,
    build_binance_usdm_koru_tradifi_source_projection_v1,
)
from crypto_quant_domain import (
    ArtifactRef,
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    PortfolioSnapshot,
    Price,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    SourceSequence,
    StrategySleeveId,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent
from crypto_quant_trading import (
    AllocationConstraintCode,
    CapitalAllocationPolicyRef,
    DecisionBatchExpectation,
    InstrumentSizingInput,
    PortfolioAllocator,
    PortfolioRiskAction,
    PortfolioRiskEvaluator,
    PortfolioRiskLimit,
    PortfolioRiskPolicy,
    PortfolioRiskScope,
    PositionSizer,
    PositionSizingPolicy,
    QuantityLattice,
    ResidualPositionPolicy,
    ResolvedMark,
    StrategyAllocation,
    StrategyOutputValidationContext,
    StrategyOutputValidator,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_price_bars_source_bounded_v1 as price_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as source_fixture,
)

_HOUR_MS = price_fixture.HOUR_MS
_HOUR_NS = _HOUR_MS * 1_000_000
_STRATEGY_ID = "koruusdt_closed_market_range_v1"
_SLEEVE_ID = StrategySleeveId("koruusdt-closed-market-range")
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_PARAMETER_FIELDS = (
    "formation_hours",
    "max_formation_range",
    "max_hold_hours",
    "entry_zone_fraction",
    "stop_range_multiple",
    "max_abs_premium",
    "max_trades_per_closed_interval",
    "position_notional_usdt",
)
_PARAMETER_ROWS = tuple(
    (str(formation), maximum, str(hold), "0.25", "1", "0.02", "1", "1000")
    for formation in (2, 3)
    for maximum in ("0.03", "0.05")
    for hold in (2, 4)
)


def _rows(day_start_ms: int, closes: dict[int, str]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (
            str(day_start_ms + hour * _HOUR_MS),
            "100.00000000",
            "101.00000000",
            "99.00000000",
            closes.get(hour, "100.00000000"),
            "0",
            str(day_start_ms + (hour + 1) * _HOUR_MS - 1),
            "0",
            "1",
            "0",
            "0",
            "0",
        )
        for hour in range(24)
    )


def _price_result(source_kind, utc_date: str, closes: dict[int, str]):
    day_start_ms = source_fixture._day_start_ms(utc_date)
    rows = _rows(day_start_ms, closes)
    archive, checksum = price_fixture.evidence(
        rows,
        member_name=f"KORUUSDT-1h-{utc_date}.csv",
        checksum_name=f"KORUUSDT-1h-{utc_date}.zip",
    )
    day_start_ns = day_start_ms * 1_000_000
    request = price_fixture.request_for(
        source_kind,
        archive,
        checksum,
        utc_date=utc_date,
        archive_available_at=day_start_ns + 24 * _HOUR_NS,
        acquired_at=day_start_ns + 48 * _HOUR_NS,
    )
    archive_url, checksum_url = request.urls
    capture = price_fixture.capture_binance_usdm_koru_price_bars_source_bounded_v1(
        request,
        price_fixture.Fetch(
            {archive_url: [(200, archive)], checksum_url: [(200, checksum)]}
        ),
    ).result
    assert capture is not None
    result = price_fixture.normalize_binance_usdm_koru_price_bars_source_bounded_v1(
        capture
    ).result
    assert result is not None
    return result


@cache
def _base_fragment() -> BinanceUsdmKoruTradifiSourceProjectionResultV1:
    return source_fixture._built()


@cache
def _weekend_fragment() -> BinanceUsdmKoruTradifiSourceProjectionResultV1:
    utc_date = "2026-07-18"
    day_start_ms = source_fixture._day_start_ms(utc_date)
    start = day_start_ms * 1_000_000
    end = start + 12 * _HOUR_NS
    trades = tuple(
        (day_start_ms + hour * _HOUR_MS + 5 * 60_000, "100.00000000")
        for hour in range(12)
    )
    request = source_fixture._request(trades, start_ns=start, end_ns=end)
    mark = (
        _price_result(
            price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE,
            "2026-07-17",
            {},
        ),
        _price_result(
            price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE,
            utc_date,
            {2: "99.50000000"},
        ),
    )
    index = (
        _price_result(
            price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
            "2026-07-17",
            {},
        ),
        _price_result(
            price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
            utc_date,
            {2: "99.50000000"},
        ),
    )
    outcome = build_binance_usdm_koru_tradifi_source_projection_v1(
        replace(request, mark_price_results=mark, index_price_results=index)
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _build(
    source: BinanceUsdmKoruTradifiSourceProjectionResultV1,
) -> BinanceUsdmKoruClosedMarketRangeTargetsResultV1:
    outcome = build_binance_usdm_koru_closed_market_range_targets_v1(
        BinanceUsdmKoruClosedMarketRangeTargetsRequestV1(source)
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


@cache
def _base_result() -> BinanceUsdmKoruClosedMarketRangeTargetsResultV1:
    return _build(_base_fragment())


@cache
def _weekend_result() -> BinanceUsdmKoruClosedMarketRangeTargetsResultV1:
    return _build(_weekend_fragment())


def _catalog() -> InstrumentCatalog:
    koru = CurrencyId("KORU")
    usdt = CurrencyId("USDT")
    return InstrumentCatalog(
        (koru, usdt),
        (
            InstrumentDefinition(
                _INSTRUMENT,
                InstrumentType.LINEAR_PERPETUAL,
                koru,
                usdt,
                usdt,
            ),
        ),
        (),
    )


def _context(decision_time: int) -> StrategyOutputValidationContext:
    return StrategyOutputValidationContext(
        _STRATEGY_ID,
        _SLEEVE_ID,
        UtcInstant(decision_time),
        _catalog(),
        (_INSTRUMENT,),
    )


def _market_event(
    name: str,
    completed_ns: int,
    payload: dict[str, object],
    *,
    actual_ns: int | None = None,
) -> MarketEvent:
    event_ns = completed_ns if actual_ns is None else actual_ns
    return MarketEvent(
        event_id=f"fixture:{name}:{completed_ns}:{event_ns}",
        stream_key=f"fixture.{name}",
        event_type=name,
        capability=MarketBundleCapability(f"fixture.{name}", 1),
        instrument_id=_INSTRUMENT,
        event_time=UtcInstant(event_ns),
        available_time=UtcInstant(event_ns),
        phase=TimelinePhase(0, "market_data"),
        source_sequence=SourceSequence(completed_ns // _HOUR_NS),
        revision_id=f"revision:{name}:{completed_ns}:{event_ns}",
        supersedes_revision_id=None,
        source_key=f"fixture.{name}",
        source_hash=canonical_sha256(
            {"name": name, "completed_ns": completed_ns, "event_ns": event_ns}
        ),
        payload=payload,
    )


def _pair(
    completed_hour: int,
    *,
    high: int = 101,
    low: int = 99,
    close: int = 100,
    index_close: int | None = None,
) -> _BarPair:
    completed_ns = completed_hour * _HOUR_NS
    common = {
        "price_purpose": "strategy",
        "interval": "1h",
        "price_scale": 8,
    }
    mark = _market_event(
        "mark_price",
        completed_ns,
        {
            **common,
            "source_kind": "mark_price",
            "high_units": high,
            "low_units": low,
            "close_units": close,
        },
    )
    index = _market_event(
        "index_price",
        completed_ns,
        {
            **common,
            "source_kind": "index_price",
            "high_units": high,
            "low_units": low,
            "close_units": close if index_close is None else index_close,
        },
    )
    return _BarPair(completed_ns, mark, index)


def _projection(
    boundary_hour: int,
    *,
    actual_ns: int | None = None,
    cutoff_ns: int | None = None,
) -> _Projection:
    boundary_ns = boundary_hour * _HOUR_NS
    actual = boundary_ns if actual_ns is None else actual_ns
    cutoff = boundary_ns + 8 * _HOUR_NS if cutoff_ns is None else cutoff_ns
    return _Projection(
        boundary_ns,
        cutoff,
        _market_event("projection", boundary_ns, {}, actual_ns=actual),
    )


def _parameter(index: int = 0):
    strategy = _strategy_binding()
    return strategy, _parameter_bindings(strategy.ref)[index]


def _events(
    *,
    entry_close: int = 99,
    entry_index_close: int | None = None,
    exit_close: int = 100,
    formation_high: int = 101,
    formation_low: int = 99,
    entry_fill_ns: int | None = None,
    entry_projection: bool = True,
    exit_projection: bool = True,
    extra_pairs: tuple[_BarPair, ...] = (),
) -> tuple[MarketEvent, ...]:
    strategy, parameter = _parameter()
    pairs = (
        _pair(1, high=formation_high, low=formation_low),
        _pair(2, high=formation_high, low=formation_low),
        _pair(
            3,
            high=formation_high,
            low=formation_low,
            close=entry_close,
            index_close=entry_index_close,
        ),
        _pair(5, close=exit_close),
        *extra_pairs,
    )
    projection_values = {}
    if entry_projection:
        projection_values[4 * _HOUR_NS] = _projection(
            4,
            actual_ns=4 * _HOUR_NS if entry_fill_ns is None else entry_fill_ns,
        )
    if exit_projection:
        projection_values[6 * _HOUR_NS] = _projection(6)
    return _stream_events(
        source=_base_fragment(),
        strategy_ref=strategy.ref,
        parameter=parameter,
        closed=((0, 12 * _HOUR_NS),),
        pairs={pair.completed_ns: pair for pair in pairs},
        projections=projection_values,
    )


def _candidate_payload(event: MarketEvent) -> Mapping[str, Any]:
    value = event.payload["candidate"]
    assert isinstance(value, Mapping)
    return cast(Mapping[str, Any], value)


def _evidence(event: MarketEvent) -> Mapping[str, Any]:
    value = _candidate_payload(event)["evidence"]
    assert isinstance(value, Mapping)
    return cast(Mapping[str, Any], value)


def _validated_units(event: MarketEvent) -> int:
    candidate, issues = PrecomputedTargetStreamAdapter()._decode(event)
    assert issues == [] and candidate is not None
    validated = StrategyOutputValidator().validate(
        candidate,
        _context(event.event_time.epoch_nanoseconds),
    )
    assert validated.failure is None and validated.decision is not None
    return validated.decision.target_snapshot.targets[0].units


def test_strategy_identity_is_fragment_independent_and_parameter_rows_are_frozen() -> (
    None
):
    base = _base_result()
    weekend = _weekend_result()

    assert canonical_bytes(base.strategy.envelope) == canonical_bytes(
        weekend.strategy.envelope
    )
    assert base.strategy.ref == weekend.strategy.ref
    strategy_payload = base.strategy.envelope.payload
    assert strategy_payload["required_synthetic_equity_usdt"] == "10000"
    assert strategy_payload["required_sleeve_allocation_fraction"] == "1"
    assert strategy_payload["target_exposure_fraction"] == "0.1"
    assert strategy_payload["position_notional_usdt"] == "1000"
    assert strategy_payload["future_preparation_binding"] == {
        "required_synthetic_equity_usdt": "10000",
        "required_sleeve_allocation_fraction": "1",
        "mismatch_action": "reject",
    }
    assert strategy_payload["rules"][
        "preparation_requires_exact_synthetic_equity_and_sleeve_allocation"
    ] is True
    forbidden = {
        "source_projection_fragment_ref",
        "calendar_refs",
        "unit_regime_ref",
        "source_fragment_digest",
    }
    assert forbidden.isdisjoint(strategy_payload)
    assert tuple(strategy_payload["parameter_schema"]) == _PARAMETER_FIELDS

    assert tuple(parameter.parameter_id for parameter in base.parameters) == tuple(
        f"p{index:02d}" for index in range(1, 9)
    )
    actual_rows = tuple(
        tuple(parameter.envelope.payload[field] for field in _PARAMETER_FIELDS)
        for parameter in base.parameters
    )
    assert actual_rows == _PARAMETER_ROWS
    assert all(type(value) is str for row in actual_rows for value in row)
    for parameter in base.parameters:
        payload = parameter.envelope.payload
        assert {
            "entry_fraction",
            "stop_distance_formation_widths",
            "max_absolute_entry_premium",
            "maximum_trades_per_closed_interval",
            "target_notional_usdt",
        }.isdisjoint(payload)
        assert parameter.ref == ArtifactRef.from_envelope(parameter.envelope)
    assert tuple(parameter.ref for parameter in base.parameters) == tuple(
        parameter.ref for parameter in weekend.parameters
    )
    assert tuple(canonical_bytes(value.envelope) for value in base.parameters) == tuple(
        canonical_bytes(value.envelope) for value in weekend.parameters
    )


@pytest.mark.parametrize(
    ("synthetic_equity_usdt", "sleeve_allocation_fraction"),
    (("9999", "1"), ("10001", "1"), ("10000", "0.5")),
)
def test_future_preparation_binding_rejects_other_equity_or_allocation(
    synthetic_equity_usdt: str, sleeve_allocation_fraction: str
) -> None:
    payload = _base_result().strategy.envelope.payload
    binding = cast(Mapping[str, object], payload["future_preparation_binding"])

    assert binding["mismatch_action"] == "reject"
    assert (
        synthetic_equity_usdt,
        sleeve_allocation_fraction,
    ) != (
        binding["required_synthetic_equity_usdt"],
        binding["required_sleeve_allocation_fraction"],
    )


def test_sealed_grid_emits_exact_artifacts_refs_streams_and_runtime_digests() -> None:
    result = _base_result()

    assert len(result.artifacts) == 9
    assert len(result.refs) == 9
    assert len(result.parameters) == 8
    assert len(result.streams) == 8
    assert tuple(stream.stream_key for stream in result.streams) == tuple(
        f"binance_usdm.tradifi.target.koruusdt.closed_market_range.p{index:02d}.v1"
        for index in range(1, 9)
    )
    parameter_map = {
        parameter.parameter_id: parameter.ref for parameter in result.parameters
    }
    assert parameter_map == {
        f"p{index:02d}": stream.parameter_ref
        for index, stream in enumerate(result.streams, 1)
    }
    assert all(
        PrecomputedTargetStream(stream.stream_key, stream.events).target_stream_digest
        == stream.target_stream_digest
        for stream in result.streams
    )
    assert canonical_bytes(result) == canonical_bytes(_build(_base_fragment()))
    assert _trusted_result(result) is not None


def test_half_hour_window_excludes_partial_bar_and_formation_is_exactly_n_bars() -> (
    None
):
    strategy, parameter = _parameter()
    pairs = tuple(_pair(hour, close=99 if hour == 4 else 100) for hour in range(1, 7))
    projections = {
        5 * _HOUR_NS: _projection(5),
        7 * _HOUR_NS: _projection(7),
    }
    events = _stream_events(
        source=_base_fragment(),
        strategy_ref=strategy.ref,
        parameter=parameter,
        closed=((_HOUR_NS // 2, 8 * _HOUR_NS),),
        pairs={pair.completed_ns: pair for pair in pairs},
        projections=projections,
    )

    assert len(events) == 2
    entry = _candidate_payload(events[0])
    assert entry["decision_time"] == 4 * _HOUR_NS
    assert tuple(entry["evidence"]["formation_mark_event_hashes"]) == (
        pairs[1].mark.event_hash,
        pairs[2].mark.event_hash,
    )
    assert (
        pairs[0].mark.event_hash not in entry["evidence"]["formation_mark_event_hashes"]
    )


def test_formation_requires_n_plus_one_and_range_zero_exact_or_above_limit() -> None:
    strategy, parameter = _parameter()
    formation_only = (_pair(1), _pair(2))
    assert (
        _stream_events(
            source=_base_fragment(),
            strategy_ref=strategy.ref,
            parameter=parameter,
            closed=((0, 3 * _HOUR_NS),),
            pairs={pair.completed_ns: pair for pair in formation_only},
            projections={},
        )
        == ()
    )
    assert _events()

    assert _formation_range_exceeds(200, 200, Decimal("0.03")) is False
    assert _formation_range_exceeds(203, 197, Decimal("0.03")) is False
    assert _formation_range_exceeds(204, 196, Decimal("0.03")) is True
    assert _events(formation_high=200, formation_low=200, entry_close=200) == ()
    assert _events(formation_high=203, formation_low=197, entry_close=197)
    assert _events(formation_high=204, formation_low=196, entry_close=196) == ()


@pytest.mark.parametrize(
    ("close", "expected_reason"),
    (
        (200, "closed_market_range_long_entry"),
        (201, "closed_market_range_long_entry"),
        (202, None),
        (203, "closed_market_range_short_entry"),
        (204, "closed_market_range_short_entry"),
        (199, None),
        (205, None),
    ),
)
def test_long_and_short_zone_bounds_reject_middle_and_outside_range(
    close: int, expected_reason: str | None
) -> None:
    events = _events(
        formation_high=204,
        formation_low=200,
        entry_close=close,
        exit_close=202,
    )
    assert (
        _candidate_payload(events[0])["reason"] if events else None
    ) == expected_reason


@pytest.mark.parametrize(
    ("side", "exit_close", "expected"),
    (
        (1, 100, "closed_market_range_long_midpoint_exit"),
        (1, 97, "closed_market_range_long_stop_exit"),
        (-1, 100, "closed_market_range_short_midpoint_exit"),
        (-1, 103, "closed_market_range_short_stop_exit"),
    ),
)
def test_both_sides_midpoint_and_stop_exits(
    side: int, exit_close: int, expected: str
) -> None:
    _, parameter = _parameter()
    pairs = (_pair(1), _pair(2), _pair(3), _pair(5, close=exit_close))
    value = _exit(
        parameter=parameter,
        interval_pairs=pairs,
        entry_index=2,
        entry_projection=_projection(4),
        side=side,
        high=101,
        low=99,
        width=2,
        projections={6 * _HOUR_NS: _projection(6)},
    )
    assert value is not None and value[2] == expected


def test_price_trigger_precedes_max_hold_and_last_safe_projection_is_boundary_exit() -> (
    None
):
    _, parameter = _parameter()
    entry = _projection(4)
    stop_at_hold = _pair(6, close=97)
    stop = _exit(
        parameter=parameter,
        interval_pairs=(_pair(1), _pair(2), _pair(3), stop_at_hold),
        entry_index=2,
        entry_projection=entry,
        side=1,
        high=101,
        low=99,
        width=2,
        projections={7 * _HOUR_NS: _projection(7)},
    )
    assert stop is not None and stop[2] == "closed_market_range_long_stop_exit"

    neutral = _pair(5, close=99)
    boundary = _exit(
        parameter=parameter,
        interval_pairs=(_pair(1), _pair(2), _pair(3), neutral),
        entry_index=2,
        entry_projection=entry,
        side=1,
        high=101,
        low=99,
        width=2,
        projections={6 * _HOUR_NS: _projection(6)},
    )
    assert boundary is not None and boundary[2] == "closed_market_range_boundary_exit"


@pytest.mark.parametrize(
    ("fill_ns", "expected_exit_hour"),
    (
        (4 * _HOUR_NS - 1, 4),
        (4 * _HOUR_NS, 5),
        (4 * _HOUR_NS + 1, 5),
    ),
)
def test_exit_bar_must_complete_strictly_after_actual_fill(
    fill_ns: int, expected_exit_hour: int
) -> None:
    _, parameter = _parameter()
    pairs = (_pair(1), _pair(2), _pair(3), _pair(4, close=100), _pair(5, close=100))
    value = _exit(
        parameter=parameter,
        interval_pairs=pairs,
        entry_index=2,
        entry_projection=_projection(4, actual_ns=fill_ns),
        side=1,
        high=101,
        low=99,
        width=2,
        projections={
            5 * _HOUR_NS: _projection(5),
            6 * _HOUR_NS: _projection(6),
        },
    )
    assert value is not None
    assert value[0].completed_ns == expected_exit_hour * _HOUR_NS


def test_missing_entry_or_exit_projection_fails_flat_and_only_one_trade_is_emitted() -> (
    None
):
    assert _events(entry_projection=False) == ()
    assert _events(exit_projection=False) == ()

    events = _events(extra_pairs=(_pair(7, close=99), _pair(9, close=100)))
    assert len(events) == 2
    assert _candidate_payload(events[0])["targets"][0]["value"] == "0.1"
    assert _candidate_payload(events[-1])["targets"][0]["value"] == "0"

    for stream in _weekend_result().streams:
        assert len(stream.events) in {0, 2}
        if stream.events:
            assert _candidate_payload(stream.events[-1])["targets"][0]["value"] == "0"


def test_premium_boundaries_and_nonpositive_closes_fail_closed() -> None:
    scale = 10**45
    with localcontext() as context:
        context.prec = 50
        positive = Decimal("0.02").exp() * scale
        negative = Decimal("-0.02").exp() * scale
    positive_floor = int(positive)
    negative_floor = int(negative)
    cases = (
        (positive_floor, scale, True, "0.02"),
        (positive_floor + 1, scale, False, None),
        (negative_floor + 1, scale, True, "-0.02"),
        (negative_floor, scale, False, None),
    )
    for close, index_close, accepted, evidence_text in cases:
        width = max(1, close // 50)
        events = _events(
            formation_high=close + width,
            formation_low=close,
            entry_close=close,
            entry_index_close=index_close,
            exit_close=close + width,
        )
        assert bool(events) is accepted
        if events:
            evidence = _evidence(events[0])
            assert evidence["entry_premium"] == evidence_text
            assert evidence["decision_premium"] == evidence_text

    with pytest.raises(ValueError, match="nonpositive_close"):
        _premium(_pair(3, close=0, index_close=100))
    with pytest.raises(ValueError, match="nonpositive_close"):
        _premium(_pair(3, close=100, index_close=0))


def test_exit_evidence_preserves_entry_premium_and_recomputes_decision_premium() -> (
    None
):
    events = _events(entry_close=99, entry_index_close=100, exit_close=100)
    entry_evidence = _evidence(events[0])
    exit_evidence = _evidence(events[1])

    assert entry_evidence["entry_premium"] == entry_evidence["decision_premium"]
    assert exit_evidence["entry_premium"] == entry_evidence["entry_premium"]
    assert exit_evidence["decision_premium"] == "0"
    assert exit_evidence["entry_premium"] != exit_evidence["decision_premium"]


def test_empty_stream_manifest_digest_and_projection_safety_are_exact() -> None:
    result = _base_result()
    assert all(stream.events == () for stream in result.streams)
    for stream in result.streams:
        assert stream.manifest == _manifest(stream.stream_key, ())
        assert stream.manifest.event_count == 0
        assert stream.manifest.content_hash == canonical_sha256(())
        assert stream.target_stream_digest == _target_stream_digest(
            stream.stream_key, ()
        )

    projections = _projections(_weekend_fragment())
    assert projections
    assert all(
        value.boundary_ns <= value.event.event_time.epoch_nanoseconds < value.cutoff_ns
        for value in projections.values()
    )


def test_candidate_times_cutoff_and_fill_drift_evidence_are_exact() -> None:
    fill = 4 * _HOUR_NS + 5 * 60 * 1_000_000_000
    events = _events(entry_fill_ns=fill)
    for event in events:
        candidate = _candidate_payload(event)
        evidence = _evidence(event)
        assert candidate["effective_time"] == candidate["decision_time"]
        assert candidate["decision_time"] == candidate["observed_through"]
        assert candidate["expires_at"] == evidence["projection_cutoff"]

    entry = _candidate_payload(events[0])
    evidence = _evidence(events[0])
    assert entry["decision_time"] == 3 * _HOUR_NS
    assert evidence["projection_actual_event_time"] == fill
    assert evidence["projection_actual_event_time"] > evidence["projection_boundary"]


@pytest.mark.parametrize(
    ("entry_close", "expected_units"),
    ((99, 100_000_000_000), (101, -100_000_000_000)),
)
def test_exposure_validator_uses_exact_scale_twelve_units(
    entry_close: int, expected_units: int
) -> None:
    events = _events(entry_close=entry_close)
    assert _validated_units(events[0]) == expected_units
    assert _validated_units(events[1]) == 0


def test_full_precomputed_adapter_injects_exact_generated_schedule_and_context() -> (
    None
):
    event = _events()[0]
    stream = PrecomputedTargetStream(event.stream_key, (event,))
    expectation = DecisionBatchExpectation(_STRATEGY_ID, _SLEEVE_ID)
    context = _context(event.event_time.epoch_nanoseconds)
    schedule = TargetStreamDecisionSchedule(
        event.event_time,
        TimelineSegment.ACTIVE_TRADING,
        (TargetStreamScheduleEntry(event.event_id, expectation, context),),
    )

    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream,
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, event),),
        schedule=schedule,
    )

    assert outcome.injection is not None
    assert outcome.injection.schedule_hash == schedule.schedule_hash
    assert outcome.injection.target_stream_digest == stream.target_stream_digest
    assert outcome.injection.source_event_ids == (event.event_id,)
    decision = outcome.injection.batch.decisions[0]
    assert decision.decision_time == event.event_time
    assert decision.target_snapshot.effective_time == decision.decision_time
    assert decision.target_snapshot.targets[0].units == 100_000_000_000


def test_adapter_allocator_risk_and_sizing_approve_frozen_1000_usdt_before_fill_drift() -> (
    None
):
    fill = 4 * _HOUR_NS + 5 * 60 * 1_000_000_000
    event = _events(entry_fill_ns=fill)[0]
    decision_time = event.event_time
    expectation = DecisionBatchExpectation(_STRATEGY_ID, _SLEEVE_ID)
    schedule = TargetStreamDecisionSchedule(
        decision_time,
        TimelineSegment.ACTIVE_TRADING,
        (
            TargetStreamScheduleEntry(
                event.event_id,
                expectation,
                _context(decision_time.epoch_nanoseconds),
            ),
        ),
    )
    injected = PrecomputedTargetStreamAdapter().inject(
        stream=PrecomputedTargetStream(event.stream_key, (event,)),
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, event),),
        schedule=schedule,
    )
    assert injected.injection is not None

    usdt = CurrencyId("USDT")
    money_scale = Scale(2)
    zero = Money(0, money_scale, "USDT")
    portfolio_snapshot = PortfolioSnapshot(
        account_id="account:synthetic-koru",
        timestamp=decision_time,
        reporting_currency=usdt,
        cash=(),
        positions=(),
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=Money(1_000_000, money_scale, "USDT"),
        valuation_marks=(),
        journal_state_hash="sha256:" + "1" * 64,
        valuation_mark_set_hash=canonical_sha256(()),
        valuation_staleness_report_hash="sha256:" + "2" * 64,
        currency_valuation_graph_hash="sha256:" + "3" * 64,
    )
    snapshot_hash = canonical_sha256(portfolio_snapshot)
    allocation = StrategyAllocation(
        strategy_id=_STRATEGY_ID,
        sleeve_id=_SLEEVE_ID,
        valuation_time=decision_time,
        valuation_currency=usdt,
        allocation_nav=Money(1_000_000, money_scale, "USDT"),
        policy_ref=CapitalAllocationPolicyRef(
            "capital.frozen-full-sleeve.v1", 1, "sha256:" + "4" * 64
        ),
        source_portfolio_snapshot_hash=snapshot_hash,
    )
    allocated = PortfolioAllocator().allocate(
        sleeve_state=injected.injection.state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=(allocation,),
        target_notional_scale=money_scale,
    )
    if allocated.failure is not None:
        assert AllocationConstraintCode.TARGET_NOT_EFFECTIVE not in {
            decision.code for decision in allocated.failure.decisions
        }
    assert allocated.allocation is not None
    assert allocated.allocation.net_targets[0].target_notional == Money(
        100_000, money_scale, "USDT"
    )

    risk_policy = PortfolioRiskPolicy.create(
        policy_key="portfolio.frozen-koru-target.v1",
        policy_version=1,
        valuation_currency=usdt,
        notional_scale=money_scale,
        limits=(
            PortfolioRiskLimit(
                "target.koru.absolute.v1",
                PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
                Money(100_000, money_scale, "USDT"),
                PortfolioRiskAction.REJECT,
                _INSTRUMENT,
            ),
            PortfolioRiskLimit(
                "aggregate.gross.v1",
                PortfolioRiskScope.GROSS_EXPOSURE,
                Money(100_000, money_scale, "USDT"),
                PortfolioRiskAction.REJECT,
                None,
            ),
            PortfolioRiskLimit(
                "aggregate.absolute-net.v1",
                PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
                Money(100_000, money_scale, "USDT"),
                PortfolioRiskAction.REJECT,
                None,
            ),
        ),
    )
    assessed = PortfolioRiskEvaluator().evaluate(
        allocation=allocated.allocation, policy=risk_policy
    )
    assert assessed.approved_target is not None
    assert assessed.approved_target.targets[0].approved_notional == Money(
        100_000, money_scale, "USDT"
    )

    quantity_scale = Scale(3)
    mark = ResolvedMark(
        instrument_id=_INSTRUMENT,
        quote_currency_id=usdt,
        price_purpose=PricePurpose.VALUATION,
        price=Price(10_000, money_scale, str(_INSTRUMENT), "USDT"),
        observed_at=decision_time,
        available_at=decision_time,
        resolved_at=decision_time,
        age_nanoseconds=0,
        stream_id="mark:koruusdt:valuation",
        source_event_id="event:koruusdt:decision-mark",
        revision_id="v1",
        stale_policy_key="stale.valuation.v1",
        stale_policy_version=1,
        stale_policy_hash="sha256:" + "5" * 64,
    )
    sized = PositionSizer().materialize(
        approved_target=assessed.approved_target,
        source_decision_batch_id=injected.injection.batch.decision_batch_id,
        policy=PositionSizingPolicy.create(
            policy_key="position-sizing.toward-zero.v1",
            policy_version=1,
            price_purpose=PricePurpose.VALUATION,
            rounding=RoundingPolicy.TOWARD_ZERO,
            residual_policy=ResidualPositionPolicy.HOLD_DUST,
        ),
        inputs=(
            InstrumentSizingInput(
                instrument_id=_INSTRUMENT,
                mark=mark,
                current_quantity=Quantity(0, quantity_scale, str(_INSTRUMENT)),
                lattice=QuantityLattice.create(
                    instrument_id=_INSTRUMENT,
                    lattice_key="quantity-lattice:koruusdt:v1",
                    lattice_version=1,
                    atomic_scale=quantity_scale,
                    step_units=1,
                    buy_lot_units=1,
                    sell_lot_units=1,
                    min_quantity_units=1,
                    min_notional=Money(1, money_scale, "USDT"),
                    odd_lot_close_permitted=False,
                ),
            ),
        ),
    )
    assert sized.normalized_target is not None
    assert sized.normalized_target.active_target.quantities == (
        (_INSTRUMENT, Quantity(10_000, quantity_scale, str(_INSTRUMENT))),
    )
    assert _evidence(event)["projection_actual_event_time"] == fill
    assert fill > decision_time.epoch_nanoseconds


def test_1000_usdt_artifact_identity_is_stable_while_fill_evidence_may_drift() -> None:
    base = _base_result().parameters[0]
    weekend = _weekend_result().parameters[0]
    entry = _candidate_payload(_weekend_result().streams[0].events[0])

    assert base.envelope.payload["position_notional_usdt"] == "1000"
    assert base.ref == weekend.ref
    assert canonical_bytes(base.envelope) == canonical_bytes(weekend.envelope)
    assert entry["effective_time"] == entry["decision_time"]
    assert (
        _evidence(_weekend_result().streams[0].events[0])[
            "projection_actual_event_time"
        ]
        > entry["effective_time"] + _HOUR_NS
    )


def test_event_manifest_result_tamper_and_trusted_outcome_fail_closed() -> None:
    result = _weekend_result()
    stream = result.streams[0]
    assert stream.events
    assert stream.manifest == _manifest(stream.stream_key, stream.events)
    assert stream.target_stream_digest == _target_stream_digest(
        stream.stream_key, stream.events
    )
    assert _trusted_result(result) is not None
    trusted_outcome = BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1(result=result)
    assert trusted_outcome.result is result

    candidate = dict(_candidate_payload(stream.events[0]))
    candidate["expires_at"] += 1
    tampered_event = replace(
        stream.events[0], payload={"schema_version": 1, "candidate": candidate}
    )
    tampered_events = (tampered_event, *stream.events[1:])
    tampered_stream = BinanceUsdmKoruClosedMarketRangeTargetStreamResultV1(
        parameter_ref=stream.parameter_ref,
        stream_key=stream.stream_key,
        events=tampered_events,
        manifest=_manifest(stream.stream_key, tampered_events),
        target_stream_digest=_target_stream_digest(stream.stream_key, tampered_events),
    )
    with pytest.raises(ValueError, match="target-generation result binding mismatch"):
        replace(result, streams=(tampered_stream, *result.streams[1:]))

    fresh = _build(_weekend_fragment())
    object.__setattr__(fresh, "result_digest", "sha256:" + "0" * 64)
    assert _trusted_result(fresh) is None
    with pytest.raises(ValueError, match="exact canonical target result"):
        BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV1(result=fresh)


def test_source_closed_interval_and_pair_maps_use_exact_completed_boundaries() -> None:
    source = _weekend_fragment()
    closed = _closed_intervals(source)
    pairs = _strategy_pairs(source)

    assert closed == (
        (
            source.request.timeline_window_start.epoch_nanoseconds,
            source.request.timeline_window_end_exclusive.epoch_nanoseconds,
        ),
    )
    assert tuple(sorted(pairs)) == tuple(
        source.request.timeline_window_start.epoch_nanoseconds + hour * _HOUR_NS
        for hour in range(12)
    )
