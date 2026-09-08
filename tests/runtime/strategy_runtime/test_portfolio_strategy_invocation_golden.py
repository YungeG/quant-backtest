from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from crypto_quant_backtest import invoke_portfolio_strategies
from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_trading import (
    AtomicDecisionBatchCollector,
    AtomicDecisionBatchResult,
    DecisionBatchFailure,
    DecisionBatchIssue,
    DecisionBatchIssueCode,
)

from ._fixtures import (
    DECISION_INSTANT,
    active_eligibility,
    instrument_catalog,
    registration,
    registrations_for,
    selected_models,
    valid_strategies,
    warmup_eligibility,
)
from tests.kernel.decisions._fixtures import CARRY, TREND
from tests.runtime.model_revisions._fixtures import timeline


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/runtime/portfolio-strategy-invocation-v1.json"


def _validation_hash(value: object) -> str | None:
    decision = getattr(value, "decision")
    failure = getattr(value, "failure")
    if decision is not None:
        return canonical_sha256(decision)
    if failure is not None:
        return canonical_sha256(failure)
    return None


def _invocation_refs(output: object) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": invocation.context.expectation.strategy_id,
            "sleeve_id": invocation.context.expectation.sleeve_id.value,
            "context_hash": invocation.context.context_hash,
            "strategy_artifact_hash": canonical_sha256(invocation.strategy_artifact),
            "observation_result_hashes": [
                value.result_hash for value in invocation.context.observation_results
            ],
            "observation_trace_hashes": [
                value.trace.trace_hash
                for value in invocation.context.observation_results
            ],
            "universe_selection_hash": invocation.context.universe.selection_hash,
            "window_result_hashes": [
                value.result_hash for value in invocation.context.windows
            ],
            "window_causality_hashes": [
                value.causality_trace.trace_hash for value in invocation.context.windows
            ],
            "before_state_hash": invocation.context.previous_state_hash,
            "before_input_instant": invocation.context.previous_input_instant,
            "before_checkpoint_hash": invocation.context.previous_checkpoint_hash,
            "before_output_hash": invocation.context.previous_output_hash,
            "after_state_hash": (
                None
                if invocation.state_transition is None
                else invocation.state_transition.after_state_hash
            ),
            "state_transition_hash": (
                None
                if invocation.state_transition is None
                else invocation.state_transition.transition_hash
            ),
            "before_random_stream_hashes": [
                value.stream_hash for value in invocation.context.random_streams
            ],
            "after_random_stream_hashes": [
                value.stream_hash for value in invocation.next_random_streams
            ],
            "model_timeline_hashes": [
                value.timeline_hash for value in invocation.context.model_timelines
            ],
            "model_artifact_ref_hashes": [
                value.select().artifact_ref_hash
                for value in invocation.context.model_timelines
                if value.select() is not None
            ],
            "validation_hash": (
                None
                if invocation.validation_result is None
                else _validation_hash(invocation.validation_result)
            ),
            "failure_code": (
                None
                if invocation.failure_code is None
                else invocation.failure_code.value
            ),
            "invocation_hash": invocation.invocation_hash,
        }
        for invocation in getattr(output, "invocations")
    ]


def _payload() -> dict[str, Any]:
    first_strategies = valid_strategies()
    first_registrations = registrations_for(first_strategies)
    active = invoke_portfolio_strategies(
        eligibility=active_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=tuple(reversed(first_registrations)),
    )
    repeated = invoke_portfolio_strategies(
        eligibility=active_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for(valid_strategies()),
    )
    warmup = invoke_portfolio_strategies(
        eligibility=warmup_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for(valid_strategies()),
    )
    batch_failure_registrations = registrations_for(valid_strategies())
    collector_failure = AtomicDecisionBatchResult.failed(
        DecisionBatchFailure(
            DECISION_INSTANT.instant,
            (
                DecisionBatchIssue(
                    DecisionBatchIssueCode.UNEXPECTED_SUBMISSION,
                    "collector-fixture",
                ),
            ),
            decision_instant=DECISION_INSTANT,
        )
    )
    with patch.object(
        AtomicDecisionBatchCollector,
        "collect",
        return_value=collector_failure,
    ):
        batch_failure = invoke_portfolio_strategies(
            eligibility=active_eligibility(),
            instrument_catalog=instrument_catalog(),
            registrations=batch_failure_registrations,
        )
    validation_strategies = valid_strategies()
    validation_strategies[1].mode = "validation"
    validation_failure = invoke_portfolio_strategies(
        eligibility=active_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for(validation_strategies),
    )

    assert active.batch_result is not None
    assert active.batch_result.batch is not None
    assert active.batch_result.state is not None
    assert batch_failure.batch_result is not None
    assert batch_failure.batch_result.failure is not None
    selected = selected_models()
    representative = registration(TREND, valid_strategies()[0])
    return {
        "schema_version": 1,
        "fixture_id": "portfolio-strategy-invocation-v1",
        "shared_authority": {
            "decision_instant": DECISION_INSTANT.to_canonical_dict(),
            "active_schedule_hash": active.eligibility.schedule_hash,
            "active_entry_hash": active.eligibility.entry.entry_hash,
            "active_eligibility_hash": active.eligibility.eligibility_hash,
            "warmup_schedule_hash": warmup.eligibility.schedule_hash,
            "warmup_entry_hash": warmup.eligibility.entry.entry_hash,
            "warmup_eligibility_hash": warmup.eligibility.eligibility_hash,
            "instrument_catalog_hash": canonical_sha256(instrument_catalog()),
            "observation_result_hashes": [
                value.result_hash for value in representative.observation_results
            ],
            "observation_trace_hashes": [
                value.trace.trace_hash for value in representative.observation_results
            ],
            "universe_selection_hash": representative.universe.selection_hash,
            "window_result_hashes": [
                value.result_hash for value in representative.windows
            ],
            "window_causality_hashes": [
                value.causality_trace.trace_hash for value in representative.windows
            ],
            "model_timeline_hash": timeline(DECISION_INSTANT).timeline_hash,
            "selected_model_artifact_hashes": [
                value.artifact_ref_hash for value in selected
            ],
        },
        "active": {
            "status": active.status.value,
            "invocations": _invocation_refs(active),
            "batch_hash": active.batch_result.batch_hash,
            "state_hash": active.batch_result.state_hash,
            "output_hash": active.output_hash,
            "handoff_hash": active.handoff_hash,
            "registration_order_parity": {
                "invocations_match": active.invocations == repeated.invocations,
                "batch_hash_matches": (
                    active.batch_result.batch_hash
                    == cast(Any, repeated.batch_result).batch_hash
                ),
                "state_hash_matches": (
                    active.batch_result.state_hash
                    == cast(Any, repeated.batch_result).state_hash
                ),
                "output_hash_matches": active.output_hash == repeated.output_hash,
                "handoff_hash_matches": active.handoff_hash == repeated.handoff_hash,
            },
        },
        "warmup": {
            "status": warmup.status.value,
            "invocations": _invocation_refs(warmup),
            "batch": None,
            "output_hash": warmup.output_hash,
            "handoff_hash": warmup.handoff_hash,
        },
        "validation_failure": {
            "status": validation_failure.status.value,
            "invocations": _invocation_refs(validation_failure),
            "batch": None,
            "output_hash": validation_failure.output_hash,
        },
        "atomic_batch_failure": {
            "status": batch_failure.status.value,
            "invocations": _invocation_refs(batch_failure),
            "batch": None,
            "state": None,
            "failure_hash": batch_failure.batch_result.failure.failure_hash,
            "before_strategy_state_hashes": [
                value.previous_state.state_hash for value in batch_failure_registrations
            ],
            "after_strategy_state_hashes": [
                invocation.state_transition.after_state_hash
                for invocation in batch_failure.invocations
                if invocation.state_transition is not None
            ],
            "before_random_stream_hashes": [
                stream.stream_hash
                for value in batch_failure_registrations
                for stream in value.random_streams
            ],
            "after_random_stream_hashes": [
                stream.stream_hash
                for invocation in batch_failure.invocations
                for stream in invocation.next_random_streams
            ],
            "output_hash": batch_failure.output_hash,
            "handoff_hash": batch_failure.handoff_hash,
        },
        "grade": {
            "decision_grade_eligible": active.decision_grade_eligible,
            "deployment_authorized": active.deployment_authorized,
        },
    }


def test_portfolio_strategy_invocation_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11I golden fixture: {FIXTURE}") from error

    assert json.loads(canonical_bytes(_payload())) == expected
