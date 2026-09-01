from __future__ import annotations

from dataclasses import replace

import pytest
from crypto_quant_backtest import (
    BinanceUsdmTradifiLinearFinancialDispatcher,
    DeterministicBarEngine,
)
from crypto_quant_backtest.engine import EngineFailureCode
from crypto_quant_backtest.financial_dispatch import (
    LinearMarginLiquidationAuditBatchPlan,
)
from crypto_quant_backtest.timeline import DeterministicTimeline
from crypto_quant_domain import SourceSequence, canonical_sha256
from crypto_quant_market_data import InMemoryMarketBundleReader

from tests.runtime.providers import (
    test_binance_usdm_tradifi_preparation_v2 as koru_fixture,
)
from tests.runtime.providers import test_binance_usdm_tradifi_provider as koru_provider

_SYNTHETIC_EVENT_COUNT = 6_001


@pytest.fixture(scope="module")
def schema7_case():
    prepared = koru_provider._prepare(koru_fixture._raw_scale8_two_funding_bundle())
    assert prepared.failure is None and prepared.result is not None
    return prepared.result.execution_case


def _expanded_timeline(case):
    reader = case.timeline.reader
    assert isinstance(reader, InMemoryMarketBundleReader)
    stream_key = next(key for key in case.timeline.stream_keys if reader.streams[key])
    template = reader.streams[stream_key][0]
    synthetic_events = tuple(
        replace(
            template,
            event_id=f"schema7-checkpoint-smoke-{index}",
            event_time=case.timeline.window.trading_start,
            available_time=case.timeline.window.trading_start,
            source_sequence=SourceSequence(1_000_000 + index),
            revision_id=f"schema7-checkpoint-smoke-{index}",
            supersedes_revision_id=None,
            source_key=f"schema7-checkpoint-smoke-{index}",
            source_hash=canonical_sha256({"synthetic_event": index}),
            payload={},
        )
        for index in range(_SYNTHETIC_EVENT_COUNT)
    )
    streams = {key: events for key, events in reader.streams.items() if events}
    streams[stream_key] = (*streams[stream_key], *synthetic_events)
    expanded_reader = InMemoryMarketBundleReader.build(
        bundle_key=reader.manifest.bundle_key,
        schema_version=reader.manifest.schema_version,
        coverage_start=reader.manifest.coverage_start,
        coverage_end_exclusive=reader.manifest.coverage_end_exclusive,
        instrument_catalog_hash=reader.manifest.instrument_catalog_hash,
        capabilities=reader.manifest.capabilities,
        streams=streams,
    )
    timeline = DeterministicTimeline.open(
        reader=expanded_reader,
        stream_keys=case.timeline.stream_keys,
        window=case.timeline.window,
    )
    assert isinstance(timeline, DeterministicTimeline)
    return replace(case, timeline=timeline, timeline_batch_size=128)


def _required_bindings(case) -> frozenset[tuple[object, str]]:
    return frozenset(
        binding
        for event in case.financial_dispatch_plan.scheduled_account_events
        if type(event.payload) is LinearMarginLiquidationAuditBatchPlan
        for child in event.payload.subwindows
        for binding in (
            (child.start_checkpoint, child.start_side),
            (child.end_checkpoint, child.end_side),
        )
    )


def test_schema7_batch_checkpoint_capture_scales_with_declared_bindings(
    schema7_case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct_view_calls = 0
    state_view = DeterministicBarEngine._financial_state_view

    def count_direct_views(state, window_start_checkpoint=None, checkpoints=None):
        nonlocal direct_view_calls
        if window_start_checkpoint is None and checkpoints is None:
            direct_view_calls += 1
        return state_view(state, window_start_checkpoint, checkpoints)

    monkeypatch.setattr(
        DeterministicBarEngine,
        "_financial_state_view",
        staticmethod(count_direct_views),
    )
    delegate = BinanceUsdmTradifiLinearFinancialDispatcher(
        schema7_case.financial_dispatch_plan.dispatcher_spec
    )
    baseline = DeterministicBarEngine(delegate).run(schema7_case)
    assert baseline.result is not None
    baseline_direct_view_calls = direct_view_calls
    direct_view_calls = 0
    case = _expanded_timeline(schema7_case)
    expected_bindings = _required_bindings(case)
    checkpoint_spy: list[frozenset[tuple[object, str]]] = []

    class CapturingDispatcher:
        @property
        def spec(self):
            return delegate.spec

        def book_fill(self, *args):
            return delegate.book_fill(*args)

        def book_fee(self, *args):
            return delegate.book_fee(*args)

        def dispatch_scheduled_event(self, event, state):
            if type(event.payload) is LinearMarginLiquidationAuditBatchPlan:
                assert state.checkpoints is not None
                checkpoint_spy.append(frozenset(state.checkpoints))
            return delegate.dispatch_scheduled_event(event, state)

        def project_final_snapshot(self, *args):
            return delegate.project_final_snapshot(*args)

    outcome = DeterministicBarEngine(CapturingDispatcher()).run(case)

    assert outcome.result is not None
    assert direct_view_calls <= baseline_direct_view_calls + len(expected_bindings)
    assert checkpoint_spy
    assert all(bindings <= expected_bindings for bindings in checkpoint_spy)
    assert set().union(*checkpoint_spy) == expected_bindings
    assert max(map(len, checkpoint_spy)) <= len(expected_bindings)
    assert outcome.result.financial_artifacts == baseline.result.financial_artifacts
    assert outcome.result.final_journal == baseline.result.final_journal
    assert outcome.result.final_ledger_state == baseline.result.final_ledger_state
    assert outcome.result.final_portfolio_snapshot == baseline.result.final_portfolio_snapshot
    assert replace(
        outcome.result.run_end_report,
        run_end_evidence_hash=baseline.result.run_end_report.run_end_evidence_hash,
        timeline_cursor_hash=baseline.result.run_end_report.timeline_cursor_hash,
        closeout_outcome_hash=baseline.result.run_end_report.closeout_outcome_hash,
    ) == baseline.result.run_end_report


def test_schema7_batch_missing_checkpoint_binding_fails_closed(schema7_case) -> None:
    event = next(
        event
        for event in schema7_case.financial_dispatch_plan.scheduled_account_events
        if type(event.payload) is LinearMarginLiquidationAuditBatchPlan
    )
    payload = event.payload
    child = payload.subwindows[0]
    missing_child = replace(
        child,
        start_checkpoint=replace(
            child.start_checkpoint,
            source_sequence=SourceSequence(9_000_000),
        ),
    )
    missing_payload = replace(
        payload,
        subwindows=(missing_child, *payload.subwindows[1:]),
    )
    missing_event = replace(
        event,
        payload=missing_payload,
        semantic_payload=missing_payload.production_semantic_authority(),
    )
    missing_case = replace(
        schema7_case,
        financial_dispatch_plan=replace(
            schema7_case.financial_dispatch_plan,
            scheduled_account_events=tuple(
                missing_event if value.event_id == event.event_id else value
                for value in schema7_case.financial_dispatch_plan.scheduled_account_events
            ),
        ),
    )

    outcome = DeterministicBarEngine().run(missing_case)

    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    assert set(outcome.engine_failure.subject_keys) == {
        "profile_component_failure",
        "batch_checkpoint_binding_missing",
        child.plan.role_suffix,
        "start",
    }
