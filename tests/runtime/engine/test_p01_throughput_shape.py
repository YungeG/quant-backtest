from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest
from crypto_quant_backtest import (
    DeterministicBarEngine,
    DeterministicTimeline,
    TimelineWindow,
    financial_dispatch,
)
from crypto_quant_backtest.binance_usdm_tradifi_case_planner import (
    plan_binance_usdm_tradifi_case_v1,
)
from crypto_quant_domain import SourceSequence, canonical_sha256
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleManifest,
    MarketStreamManifest,
)
from crypto_quant_trading import (
    LinearFundingAccounting,
    LinearFundingEligibilityResolver,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_funding_rate_history_source_bounded_v1 as funding_fixture,
)
from tests.runtime.providers import (
    test_binance_usdm_tradifi_preparation as v1_preparation_fixture,
)
from tests.runtime.providers import (
    test_binance_usdm_tradifi_preparation_v2 as preparation_fixture,
)
from tests.runtime.providers import (
    test_binance_usdm_tradifi_provider as provider_fixture,
)

_FUNDING_STREAM = "binance_usdm.funding_history.publications.koruusdt.v1"


def _reader_with_actual_funding_history(bundle):
    funding = funding_fixture.normalize(funding_fixture.RAW).result
    assert funding is not None and len(funding.events) == 120
    streams = {**bundle.streams, _FUNDING_STREAM: funding.events}
    declared_manifests = {
        item.stream_key: item for item in bundle.manifest.streams
    }
    manifests = tuple(
        MarketStreamManifest.from_events(stream_key, events)
        if events
        else declared_manifests[stream_key]
        for stream_key, events in streams.items()
    )
    coverage_start = min(
        event.event_time for events in streams.values() for event in events
    )
    coverage_end = max(
        event.event_time for events in streams.values() for event in events
    )
    manifest = MarketBundleManifest.build(
        bundle_key=bundle.manifest.bundle_key,
        schema_version=bundle.manifest.schema_version,
        coverage_start=coverage_start,
        coverage_end_exclusive=type(coverage_end)(coverage_end.epoch_nanoseconds + 1),
        instrument_catalog_hash=bundle.manifest.instrument_catalog_hash,
        capabilities=tuple(sorted({item.capability for item in manifests})),
        streams=manifests,
    )
    reader = InMemoryMarketBundleReader(
        type(bundle.bundle_ref).from_manifest(manifest), manifest, streams
    )
    return reader, TimelineWindow(coverage_start, coverage_start, manifest.coverage_end_exclusive)


def _expand_fan_in_reader(
    reader: InMemoryMarketBundleReader, stream_keys: tuple[str, ...]
):
    """Add valid no-op members only to planner-selected timeline streams."""
    streams = {key: tuple(events) for key, events in reader.streams.items()}
    for index in range(6_001):
        stream_key = stream_keys[index % len(stream_keys)]
        template = streams[stream_key][0]
        streams[stream_key] += (
            replace(
                template,
                event_id=f"p01-fan-in-diagnostic-{index}",
                event_time=reader.manifest.coverage_start,
                available_time=reader.manifest.coverage_start,
                source_sequence=SourceSequence(10_000_000 + index),
                revision_id=f"p01-fan-in-diagnostic-{index}",
                supersedes_revision_id=None,
                source_key=f"p01-fan-in-diagnostic-{index}",
                source_hash=canonical_sha256({"diagnostic_event": index}),
                payload={},
            ),
        )
    streams = {
        stream_key: tuple(sorted(events, key=lambda event: event.ordering_key))
        for stream_key, events in streams.items()
    }
    declared = {item.stream_key: item for item in reader.manifest.streams}
    manifests = tuple(
        MarketStreamManifest.from_events(stream_key, events)
        if events
        else MarketStreamManifest(
            stream_key,
            declared[stream_key].event_type,
            declared[stream_key].capability,
            0,
            canonical_sha256(()),
        )
        for stream_key, events in streams.items()
    )
    manifest = MarketBundleManifest.build(
        bundle_key=reader.manifest.bundle_key,
        schema_version=reader.manifest.schema_version,
        coverage_start=reader.manifest.coverage_start,
        coverage_end_exclusive=reader.manifest.coverage_end_exclusive,
        instrument_catalog_hash=reader.manifest.instrument_catalog_hash,
        capabilities=reader.manifest.capabilities,
        streams=manifests,
    )
    return InMemoryMarketBundleReader(
        type(reader.bundle_ref).from_manifest(manifest), manifest, streams
    )


def test_19_stream_heap_fan_in_scales_by_events_plus_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads = Counter()
    head = DeterministicTimeline._head

    def count_head(self, *args):
        reads["head"] += 1
        return head(self, *args)

    monkeypatch.setattr(DeterministicTimeline, "_head", count_head)
    prepared = provider_fixture._prepare(
        preparation_fixture._raw_scale8_two_funding_bundle()
    ).result
    assert prepared is not None
    reader, window = _reader_with_actual_funding_history(
        preparation_fixture._nonempty_bundle()
    )
    assert len(reader.manifest.streams) == 19
    assert sum(bool(events) for events in reader.streams.values()) == 15
    engine_streams = prepared.execution_case.timeline.stream_keys
    expanded = _expand_fan_in_reader(reader, engine_streams)
    timeline = DeterministicTimeline.open(
        reader=expanded,
        stream_keys=engine_streams,
        window=window,
    )
    assert isinstance(timeline, DeterministicTimeline)
    cursor = timeline.open_cursor(batch_size=128)
    emitted = []
    while not cursor.window_complete:
        outcome = timeline.read_batch(cursor)
        assert outcome.failure is None and outcome.batch is not None
        emitted.extend(outcome.batch.events)
        cursor = outcome.batch.next_cursor

    expected = tuple(
        sorted(
            (
                event
                for stream_key in engine_streams
                for event in expanded.streams[stream_key]
                if event.available_time < window.end_exclusive
            ),
            key=lambda event: event.ordering_key,
        )
    )
    assert tuple(item.event for item in emitted) == expected
    # The old scan would call _head once per active stream per emitted event.
    assert reads["head"] < len(expected) + 1_000


def test_p01_engine_throughput_shape_uses_counter_only_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counter-only split diagnostic; 120 funding rows are fan-in only, not a synthetic run."""
    active_counts: Counter[str] = Counter()
    timeline_head = DeterministicTimeline._head
    timeline_read = DeterministicTimeline.read_batch
    timeline_resume = DeterministicTimeline.resume_cursor
    state_view = DeterministicBarEngine._financial_state_view
    replay = financial_dispatch._linear_replay
    eligibility = LinearFundingEligibilityResolver.resolve
    accounting = LinearFundingAccounting.assess_financing

    def count_head(self, *args):
        active_counts["timeline_head"] += 1
        return timeline_head(self, *args)

    def count_read(self, *args):
        active_counts["timeline_read_batch"] += 1
        return timeline_read(self, *args)

    def count_resume(self, *args, **kwargs):
        active_counts["timeline_resume"] += 1
        return timeline_resume(self, *args, **kwargs)

    def count_state_view(state, window_start_checkpoint=None, checkpoints=None):
        active_counts["checkpoint_views"] += 1
        return state_view(state, window_start_checkpoint, checkpoints)

    def count_replay(*args):
        active_counts["linear_replay"] += 1
        return replay(*args)

    def count_eligibility(self, *args):
        active_counts["funding_eligibility"] += 1
        return eligibility(self, *args)

    def count_accounting(self, *args):
        active_counts["funding_accounting"] += 1
        return accounting(self, *args)

    monkeypatch.setattr(DeterministicTimeline, "_head", count_head)
    monkeypatch.setattr(DeterministicTimeline, "read_batch", count_read)
    monkeypatch.setattr(DeterministicTimeline, "resume_cursor", count_resume)
    monkeypatch.setattr(
        DeterministicBarEngine, "_financial_state_view", staticmethod(count_state_view)
    )
    monkeypatch.setattr(financial_dispatch, "_linear_replay", count_replay)
    monkeypatch.setattr(LinearFundingEligibilityResolver, "resolve", count_eligibility)
    monkeypatch.setattr(LinearFundingAccounting, "assess_financing", count_accounting)

    baseline_preparation = v1_preparation_fixture._resolve(0).result
    assert baseline_preparation is not None
    baseline = plan_binance_usdm_tradifi_case_v1(baseline_preparation)
    baseline_keys = tuple(
        key for key in baseline.execution_case.timeline.stream_keys if key != _FUNDING_STREAM
    )
    assert len(baseline_keys) == 3
    baseline_timeline = DeterministicTimeline.open(
        reader=baseline.execution_case.timeline.reader,
        stream_keys=baseline_keys,
        window=baseline.execution_case.timeline.window,
    )
    assert isinstance(baseline_timeline, DeterministicTimeline)
    baseline_case = replace(
        baseline.execution_case,
        timeline=baseline_timeline,
        financial_dispatch_plan=replace(
            baseline.execution_case.financial_dispatch_plan,
            scheduled_account_events=(),
            expected_artifact_roles=tuple(
                role
                for role in baseline.execution_case.financial_dispatch_plan.expected_artifact_roles
                if not role.startswith("funding_")
            ),
        ),
    )
    baseline_outcome = DeterministicBarEngine().run(baseline_case)
    assert baseline_outcome.result is not None
    baseline_counts = active_counts.copy()

    active_counts.clear()
    reader, window = _reader_with_actual_funding_history(
        preparation_fixture._nonempty_bundle()
    )
    assert len(reader.manifest.streams) == 19
    assert sum(bool(events) for events in reader.streams.values()) == 15
    assert sum(not events for events in reader.streams.values()) == 4
    assert len(reader.streams[_FUNDING_STREAM]) == 120
    fan_in = DeterministicTimeline.open(
        reader=reader,
        stream_keys=(
            _FUNDING_STREAM,
            "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
            "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v2",
            "binance_usdm.tradifi.target.koruusdt.closed_market_range.p01.v2",
        ),
        window=window,
    )
    assert isinstance(fan_in, DeterministicTimeline)
    cursor = fan_in.open_cursor(batch_size=128)
    while not cursor.window_complete:
        outcome = fan_in.read_batch(cursor)
        assert outcome.failure is None and outcome.batch is not None
        cursor = outcome.batch.next_cursor
    fan_in_counts = active_counts.copy()

    active_counts.clear()
    dispatched = provider_fixture._prepare(
        preparation_fixture._raw_scale8_two_funding_bundle()
    ).result
    assert dispatched is not None
    dispatch_outcome = DeterministicBarEngine().run(dispatched.execution_case)
    assert dispatch_outcome.result is not None
    dispatch_counts = active_counts.copy()

    print(
        {
            "baseline": dict(baseline_counts),
            "fan_in_declared_19_stream_120_funding": dict(fan_in_counts),
            "two_funding_dispatch": dict(dispatch_counts),
        }
    )
    assert baseline_counts["funding_eligibility"] == 0
    assert baseline_counts["funding_accounting"] == 0
    assert fan_in_counts["funding_eligibility"] == 0
    assert fan_in_counts["funding_accounting"] == 0
    assert fan_in_counts["timeline_head"] > baseline_counts["timeline_head"]
    assert dispatch_counts["linear_replay"] > baseline_counts["linear_replay"]
    assert dispatch_counts["funding_eligibility"] == 2
    assert dispatch_counts["funding_accounting"] == 2
    assert dispatch_counts["checkpoint_views"] > dispatch_counts["funding_accounting"]
