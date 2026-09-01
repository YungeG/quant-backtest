from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import crypto_quant_backtest.binance_usdm_tradifi_provider as provider
import pytest
from crypto_quant_backtest import (
    BinanceUsdmTradifiBarBacktestFailureCode,
    BinanceUsdmTradifiBarBacktestIntent,
    BinanceUsdmTradifiBarBacktestResult,
    DeterministicBarEngine,
    prepare_binance_usdm_tradifi_bar_backtest,
)
from crypto_quant_backtest.binance_usdm_tradifi_case_planner import (
    _candidate_rows,
    _margin_audits,
)
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG,
    _materialize_execution_input_bundle_v6,
)
from crypto_quant_bundle_builder import (
    binance_usdm_koru_tradifi_execution_bundle_v2 as execution_bundle_v2,
)
from crypto_quant_bundle_builder import (
    binance_usdm_koru_tradifi_source_projection_v2 as source_projection_v2,
)
from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_closed_market_range_targets_v1 as target_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as source_fixture,
)
from tests.runtime.providers import test_binance_usdm_tradifi_preparation_v2 as fixture


def _prepare(bundle, parameter_index: int = 0, store=None):
    return prepare_binance_usdm_tradifi_bar_backtest(
        BinanceUsdmTradifiBarBacktestIntent(
            fixture._intent(bundle, parameter_index),
            fixture.BinanceUsdmTradifiProviderInputs(
                fixture.build_manifest(), fixture._EQUITY
            ),
        ),
        store or fixture._Store(bundle),
        bundle.reader,
    )


def _raw_scale8_six_fill_bundle(entry_close: str = "18.10000001"):
    utc_date = "2026-07-17"
    start = source_fixture._day_start_ms(utc_date) * 1_000_000
    end = start + 240 * target_fixture._HOUR_NS
    trades = tuple(
        (
            start // 1_000_000
            + hour * target_fixture._HOUR_MS
            + 5 * 60_000,
            "18.28000000",
        )
        for hour in range(240)
    )
    request = source_fixture._request(trades, start_ns=start, end_ns=end)
    prices = {
        "open_price": "18.28000001",
        "high_price": "18.50000001",
        "low_price": "18.00000001",
        "close_price": "18.28000001",
    }

    price_dates = tuple(
        str(
            datetime.fromtimestamp(
                value.requested_day_start.epoch_nanoseconds / 1_000_000_000,
                UTC,
            ).date()
        )
        for value in request.mark_price_results
    )

    def price_results(source_kind):
        return tuple(
            target_fixture._price_result(
                source_kind,
                date,
                {2: entry_close, 22: entry_close}
                if date in (utc_date, "2026-07-18", "2026-07-24", "2026-07-25")
                else {},
                **prices,
            )
            for date in price_dates
        )

    outcome = target_fixture.build_binance_usdm_koru_tradifi_source_projection_v1(
        replace(
            request,
            mark_price_results=price_results(
                target_fixture.price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
            ),
            index_price_results=price_results(
                target_fixture.price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE
            ),
        )
    )
    assert outcome.failure is None and outcome.result is not None
    start_ms = start // 1_000_000
    source = fixture.bundle_v2_fixture._source(
        outcome.result,
        tuple(
            start_ms + hour * target_fixture._HOUR_MS + 30 * 60_000
            for hour in range(4, 240, 20)
        ),
        funding_mark_price="20.00000001",
    )
    return fixture.bundle_v2_fixture._build(source)


def test_public_v2_raw_scale8_short_batches_reach_engine() -> None:
    prepared = _prepare(_raw_scale8_six_fill_bundle("18.40000001"))

    assert prepared.failure is None and prepared.result is not None
    case = prepared.result.execution_case
    assert tuple(
        cycle.admissions[0].order.intent.side.value for cycle in case.decision_cycles
    ) == ("sell", "buy", "sell", "buy", "sell", "buy")

    executed = DeterministicBarEngine().run(case)

    assert executed.engine_failure is None, executed.engine_failure
    assert executed.result is not None
    assert executed.result.final_portfolio_snapshot.positions == ()


def test_public_v2_raw_scale8_six_fills_with_interior_funding_reaches_engine() -> None:
    prepared = _prepare(_raw_scale8_six_fill_bundle())

    assert prepared.failure is None and prepared.result is not None
    case = prepared.result.execution_case
    assert len(case.decision_cycles) == len(case.bar_executions) == 6
    assert tuple(
        cycle.admissions[0].order.intent.side.value for cycle in case.decision_cycles
    ) == ("buy", "sell", "buy", "sell", "buy", "sell")
    funding_at = {
        event.event_at.instant
        for event in case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "funding"
    }
    batches = tuple(
        event.payload
        for event in case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "margin_liquidation_audit_batch"
    )
    assert len(funding_at) == 12
    assert len(batches) > 8
    assert any(
        len(batch.subwindows) == 2
        and batch.subwindows[0].plan.interval_end_exclusive in funding_at
        for batch in batches
    )

    executed = DeterministicBarEngine().run(case)

    assert executed.engine_failure is None, executed.engine_failure
    assert executed.result is not None
    assert len(executed.result.fills) == 6
    assert executed.result.final_portfolio_snapshot.positions == ()


def test_public_v2_raw_scale8_bundle_reaches_engine() -> None:
    bundle = fixture._raw_scale8_two_funding_bundle()
    source_events = bundle.source_projection.source_events
    raw_bars = tuple(
        event
        for event in source_events
        if event.payload.get("source_kind") == "mark_price"
    )
    raw_funding = tuple(
        event
        for event in source_events
        if event.stream_key == "binance_usdm.funding_history.publications.koruusdt.v1"
    )
    aggregate_trades = tuple(
        event
        for event in source_events
        if event.stream_key
        == "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1"
    )
    assert raw_bars and raw_funding and aggregate_trades
    assert all(event.payload["price_scale"] == 8 for event in raw_bars)
    assert all(
        event.payload[key] % 1_000_000
        for event in raw_bars
        for key in ("open_units", "high_units", "low_units", "close_units")
    )
    assert all(event.payload["mark_price_scale"] == 8 for event in raw_funding)
    assert all(event.payload["mark_price_units"] % 1_000_000 for event in raw_funding)
    assert all(event.payload["price"] == "100.00000000" for event in aggregate_trades)

    prepared = _prepare(bundle)

    assert prepared.failure is None and prepared.result is not None
    assert prepared.result.preparation_result.bundle_schema_version == 2
    assert len(prepared.result.execution_case.decision_cycles) == 2
    assert len(prepared.result.execution_case.bar_executions) == 2
    assert prepared.result.case_planning_result.market_data_preparation.bindings.execution_bindings[
        0
    ].stream_key.endswith(".v2")

    assert prepared.result.execution_input_envelope.schema_version == 8
    assert prepared.result.execution_input_ref.content_hash == (
        prepared.result.execution_input_envelope.content_hash
    )
    decoded = _EXECUTION_INPUT_CATALOG.read(
        canonical_bytes(prepared.result.execution_input_envelope)
    ).artifact
    assert decoded.execution_case_plan.decision_cycles == (
        prepared.result.execution_case.decision_cycles
    )
    assert canonical_bytes(decoded.execution_case_plan.bar_executions) == canonical_bytes(
        prepared.result.execution_case.bar_executions
    )
    assert canonical_bytes(
        decoded.execution_case_plan.financial_dispatch_plan
    ) == canonical_bytes(prepared.result.execution_case.financial_dispatch_plan)

    executed = DeterministicBarEngine().run(prepared.result.execution_case)

    assert executed.engine_failure is None and executed.result is not None
    assert len(executed.result.fills) == 2
    assert tuple(value.liquidity for value in executed.result.fills) == (
        "taker",
        "taker",
    )
    assert tuple(
        (value.reference_price.units, value.reference_price.scale.places)
        for value in executed.result.fills
    ) == ((10_000, 2), (10_000, 2))
    assert tuple(
        (value.price.units, value.price.scale.places)
        for value in executed.result.fills
    ) == ((10_005, 2), (9_995, 2))
    assert tuple(value.execution_time.epoch_nanoseconds for value in executed.result.fills) == (
        1_784_347_500_000_000_000,
        1_784_354_700_000_000_000,
    )
    assert len(executed.result.fee_assessments) == 2
    roles = tuple(value.role for value in executed.result.financial_artifacts)
    funding_events = tuple(
        event
        for event in prepared.result.execution_case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "funding"
    )
    resolutions = (
        prepared.result.preparation_result.resolved_profile.request.funding_sources
    )
    assert len(funding_events) == len(resolutions) == 2
    assert {event.event_id for event in funding_events} == {
        resolution.selected_record.event_id for resolution in resolutions
    }
    assert len({role for event in funding_events for role in event.expected_artifact_roles}) == 4
    assert tuple(event.expected_artifact_roles for event in funding_events) == tuple(
        tuple(
            sorted(
                (
                    f"funding_accounting.{event.payload.settlement_identity.settlement_id.value}",
                    f"funding_eligibility.{event.payload.settlement_identity.settlement_id.value}",
                )
            )
        )
        for event in funding_events
    )
    for event in funding_events:
        payload = event.payload
        assert payload.funding_mark_evidence.resolved_mark.price.scale.places == 8
        assert payload.funding_mark_evidence.resolved_mark.price.units % 1_000_000
        assert payload.settlement_evidence.event_id == event.event_id
        assert payload.settlement_evidence.application_key == payload.settlement_identity.application_key
        assert event.expected_artifact_roles == tuple(
            sorted((payload.funding_accounting_role, payload.funding_eligibility_role))
        )
    assert sum(role.startswith("funding_eligibility.") for role in roles) == 2
    assert sum(role.startswith("funding_accounting.") for role in roles) == 2
    funding_artifacts = tuple(
        artifact
        for artifact in executed.result.financial_artifacts
        if artifact.source_event_id in {event.event_id for event in funding_events}
    )
    assert len(funding_artifacts) == 4
    assert {artifact.role for artifact in funding_artifacts} == {
        role for event in funding_events for role in event.expected_artifact_roles
    }
    assert all(
        artifact.payload.position_state.quantity.units != 0
        for artifact in funding_artifacts
        if artifact.role.startswith("funding_eligibility.")
    )
    batches = tuple(
        event.payload
        for event in prepared.result.execution_case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "margin_liquidation_audit_batch"
    )
    assert len(batches) == 3
    assert all(
        child.plan.liquidation_bars == (batch.liquidation_bar,)
        for batch in batches
        for child in batch.subwindows
    )
    assert all(
        price.scale.places == 8 and price.units % 1_000_000
        for batch in batches
        for price in (batch.liquidation_bar.low, batch.liquidation_bar.high)
    )
    assert sum(value.startswith("liquidation_audit.hourly.") for value in roles) == 3
    assert sum(value.startswith("margin_projection.hourly.") for value in roles) == 3
    margin_marks = tuple(
        price
        for artifact in executed.result.financial_artifacts
        if artifact.role.startswith("margin_projection.hourly.")
        for valuation in artifact.payload.request.position_valuations
        for result in artifact.payload.request.margin_results
        for price in (
            valuation.resolved_mark.price,
            result.request.margin_mark_evidence.resolved_mark.price,
        )
    )
    assert margin_marks and all(
        mark.scale.places == 8 and mark.units % 1_000_000 for mark in margin_marks
    )
    assert executed.result.final_portfolio_snapshot.positions == ()


def test_public_raw_scale8_preparation_replays_after_v2_authority_cache_reset() -> None:
    def prepare_after_cache_reset():
        source_projection_v2._reset_trusted_result_cache_for_test()
        execution_bundle_v2._reset_trusted_result_cache_for_test()
        fixture._raw_scale8_two_funding_bundle.cache_clear()
        bundle = fixture._raw_scale8_two_funding_bundle()
        assert execution_bundle_v2._trusted_result(bundle) is not None
        prepared = _prepare(bundle)
        assert source_projection_v2._trusted_result_cache_stats_for_test()[1] > 0
        assert execution_bundle_v2._trusted_result_cache_stats_for_test()[1] > 0
        return prepared

    first = prepare_after_cache_reset()
    second = prepare_after_cache_reset()

    assert first.failure is None and first.result is not None
    assert second.failure is None and second.result is not None
    assert canonical_bytes(first.result.execution_input_envelope) == canonical_bytes(
        second.result.execution_input_envelope
    )
    assert canonical_bytes(first.result.execution_case) == canonical_bytes(
        second.result.execution_case
    )


def test_v2_funding_roles_reject_absence_and_forgery() -> None:
    prepared = _prepare(fixture._two_funding_bundle())
    assert prepared.result is not None
    event = next(
        value
        for value in prepared.result.execution_case.financial_dispatch_plan.scheduled_account_events
        if value.operation_key == "funding"
    )
    payload = event.payload

    with pytest.raises(ValueError, match="V2 funding artifact roles"):
        replace(
            payload,
            funding_eligibility_role="funding_eligibility.forged",
            funding_accounting_role="funding_accounting.forged",
        )
    with pytest.raises(ValueError, match="V2 funding artifact roles must be present"):
        replace(
            payload,
            funding_eligibility_role=None,
            funding_accounting_role=None,
        )
    with pytest.raises(ValueError, match="V2 funding evidence version must be 2"):
        replace(payload, funding_evidence_version=None)
    with pytest.raises(ValueError, match="funding artifact roles must match"):
        replace(
            event,
            expected_artifact_roles=(
                "funding_accounting.forged",
                "funding_eligibility.forged",
            ),
        )


def test_schema6_materializer_rejects_batch_downgrade() -> None:
    prepared = _prepare(fixture._nonempty_bundle()).result
    assert prepared is not None

    with pytest.raises(ValueError, match="thin funding evidence|liquidation audit batch"):
        _materialize_execution_input_bundle_v6(
            resolved_request=prepared.case_planning_result.resolved_request,
            hydrated_inputs=prepared.case_planning_result.hydrated_inputs,
            market_data_preparation=prepared.case_planning_result.market_data_preparation,
        )


def test_schema7_rejects_thin_funding_authority() -> None:
    from crypto_quant_backtest.execution_inputs import (
        _materialize_execution_input_bundle_v7,
    )

    prepared = _prepare(fixture._nonempty_bundle()).result
    assert prepared is not None

    with pytest.raises(ValueError, match="thin funding evidence"):
        _materialize_execution_input_bundle_v7(
            resolved_request=prepared.case_planning_result.resolved_request,
            hydrated_inputs=prepared.case_planning_result.hydrated_inputs,
            market_data_preparation=prepared.case_planning_result.market_data_preparation,
        )


def test_public_v2_empty_case_runs_flat_and_replays_canonically() -> None:
    bundle = fixture._empty_bundle()

    first = _prepare(bundle, 7)
    second = _prepare(bundle, 7)

    assert first.failure is None and first.result is not None
    assert second.failure is None and second.result is not None
    assert first.outcome_hash == second.outcome_hash
    assert canonical_bytes(first) == canonical_bytes(second)

    assert first.result.execution_case.decision_cycles == ()
    assert first.result.execution_case.bar_executions == ()


def test_public_result_rejects_schema6_envelope_from_another_plan() -> None:
    nonempty = _prepare(fixture._nonempty_bundle()).result
    empty = _prepare(fixture._empty_bundle(), 7).result
    assert nonempty is not None and empty is not None

    with pytest.raises(ValueError, match="execution input"):
        BinanceUsdmTradifiBarBacktestResult(
            nonempty.intent,
            nonempty.preparation_result,
            nonempty.case_planning_result,
            empty.execution_input_envelope,
            empty.execution_input_ref,
        )


def test_liquidation_windows_split_at_interior_funding_event() -> None:
    result = _prepare(fixture._nonempty_bundle()).result
    assert result is not None
    rows = _candidate_rows(result.preparation_result)
    entry_at = rows[0][4].event_time
    interior = UtcInstant(entry_at.epoch_nanoseconds + 100)
    funding = (
        SimpleNamespace(
            event_at=SimulationInstant(
                interior,
                TimelinePhase(120, "funding_accounting"),
                SourceSequence(0),
            )
        ),
    )

    audits = _margin_audits(result.preparation_result, rows, funding)

    split = next(audit.payload for audit in audits if len(audit.payload.subwindows) == 2)
    first, second = split.subwindows
    assert first.plan.liquidation_bars == second.plan.liquidation_bars == (
        split.liquidation_bar,
    )
    assert first.plan.interval_end_exclusive == second.plan.interval_start == interior
    assert first.end_checkpoint == second.start_checkpoint == funding[0].event_at
    assert (first.end_side, second.start_side) == ("before", "after")


def test_liquidation_window_checkpoint_starts_at_entry_projection_without_ns_shift() -> None:
    result = _prepare(fixture._nonempty_bundle()).result
    assert result is not None
    rows = _candidate_rows(result.preparation_result)
    entry_at = rows[0][4].event_time
    funding = (
        SimpleNamespace(
            event_at=SimulationInstant(
                entry_at,
                TimelinePhase(120, "funding_accounting"),
                SourceSequence(0),
            )
        ),
    )

    audits = _margin_audits(result.preparation_result, rows, funding)

    first = audits[0].payload.subwindows[0]
    assert first.plan.window_start_at == entry_at
    assert first.start_checkpoint == rows[0][4].timeline_instant
    assert first.start_side == "after"


def test_public_reports_canonical_value_error_from_case_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_):
        raise ValueError("liquidation subwindow start has no timeline event")

    monkeypatch.setattr(provider, "plan_binance_usdm_tradifi_case_v1", fail)

    outcome = _prepare(fixture._nonempty_bundle())

    assert outcome.result is None and outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiBarBacktestFailureCode.CASE_PLANNING_FAILED
    )
    assert outcome.failure.subject == "liquidation_subwindow_start_has_no_timeline_event"


def test_public_v2_preserves_stage_a_authority_failure_code() -> None:
    bundle = fixture._nonempty_bundle()
    payload = json.loads(canonical_bytes(bundle.account_authority_event.payload))
    payload["account_id"] = "other-account"
    tampered = fixture._with_events(
        bundle,
        replace(bundle.account_authority_event, payload=payload),
    )

    outcome = _prepare(tampered, store=fixture._Store(bundle))

    assert outcome.result is None and outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiBarBacktestFailureCode.PREPARATION_AUTHORITY_INVALID
    )
    assert outcome.failure.subject == "account_event_contract"


def test_public_provider_has_no_builder_network_or_clock_dependency() -> None:
    source = (
        Path(__file__).parents[3]
        / "packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_tradifi_provider.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "crypto_quant_bundle_builder",
        "requests",
        "urllib",
        "socket",
        "datetime.now",
        "time.time",
    ):
        assert forbidden not in source
