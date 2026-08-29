from __future__ import annotations

import json
from dataclasses import replace
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
from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
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


def test_public_v2_nonempty_two_target_case_reaches_engine() -> None:
    bundle = fixture._nonempty_bundle()

    prepared = _prepare(bundle)

    assert prepared.failure is None and prepared.result is not None
    assert prepared.result.preparation_result.bundle_schema_version == 2
    assert len(prepared.result.execution_case.decision_cycles) == 2
    assert len(prepared.result.execution_case.bar_executions) == 2
    assert prepared.result.case_planning_result.market_data_preparation.bindings.execution_bindings[
        0
    ].stream_key.endswith(".v2")

    assert prepared.result.execution_input_envelope.schema_version == 7
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
    assert tuple(value.execution_time.epoch_nanoseconds for value in executed.result.fills) == (
        1_784_347_500_000_000_000,
        1_784_354_700_000_000_000,
    )
    assert len(executed.result.fee_assessments) == 2
    roles = tuple(value.role for value in executed.result.financial_artifacts)
    assert roles.count("funding_eligibility") == 1
    assert roles.count("funding_accounting") == 1
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
    assert sum(value.startswith("liquidation_audit.hourly.") for value in roles) == 3
    assert sum(value.startswith("margin_projection.hourly.") for value in roles) == 3
    assert executed.result.final_portfolio_snapshot.positions == ()


def test_schema6_materializer_rejects_batch_downgrade() -> None:
    prepared = _prepare(fixture._nonempty_bundle()).result
    assert prepared is not None

    with pytest.raises(ValueError, match="liquidation audit batch"):
        _materialize_execution_input_bundle_v6(
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
