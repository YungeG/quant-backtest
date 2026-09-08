from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from crypto_quant_backtest import (
    ModelRevisionTimeline,
    PortfolioStrategyInvocationFailureCode,
    PortfolioStrategyInvocationStatus,
    StrategyCheckpoint,
    invoke_portfolio_strategies,
)
from crypto_quant_trading import (
    AtomicDecisionBatchCollector,
    AtomicDecisionBatchResult,
    DecisionBatchFailure,
    DecisionBatchIssue,
    DecisionBatchIssueCode,
)

from ._fixtures import (
    DECISION_INSTANT,
    SAME_UTC_LATER,
    active_eligibility,
    ineligible_eligibility,
    instrument_catalog,
    registration,
    registrations_for,
    same_time_prior_decision_state,
    same_utc_active_eligibilities,
    selected_models,
    state_for,
    strategy_artifact,
    stream_for,
    valid_strategies,
    warmup_eligibility,
    with_mismatched_universe,
)
from tests.kernel.decisions._fixtures import CARRY, TREND
from tests.runtime.model_revisions._fixtures import MODEL_KEY, artifact


def _invoke_active(strategies: Any):
    return invoke_portfolio_strategies(
        eligibility=active_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for(strategies),
    )


def test_active_two_sleeve_invocation_validates_then_collects_once() -> None:
    first_order: list[str] = []
    first_strategies = valid_strategies(first_order)
    first_registrations = registrations_for(first_strategies)
    first = invoke_portfolio_strategies(
        eligibility=active_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=tuple(reversed(first_registrations)),
    )

    second_order: list[str] = []
    second_strategies = valid_strategies(second_order)
    second = _invoke_active(second_strategies)

    assert first.status is PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED
    assert first_order == second_order == ["carry-v1", "trend-v1"]
    assert first.batch_result is not None
    assert first.batch_result.failure is None
    assert first.batch_result.batch is not None
    assert first.batch_result.state is not None
    assert len(first.batch_result.batch.decisions) == 2
    assert first.invocations == second.invocations
    assert first.batch_result.batch_hash == second.batch_result.batch_hash
    assert first.batch_result.state_hash == second.batch_result.state_hash
    assert first.output_hash == second.output_hash
    assert first.handoff_hash == second.handoff_hash
    assert first.handoff_hash is not None


def test_same_utc_active_entries_continue_with_one_atomic_handoff_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_eligibility, later_eligibility = same_utc_active_eligibilities()
    trend, carry = valid_strategies()
    original = AtomicDecisionBatchCollector.collect
    collector_observations: list[tuple[int, int, int]] = []

    def track(
        self: AtomicDecisionBatchCollector, **kwargs: Any
    ) -> AtomicDecisionBatchResult:
        collector_observations.append(
            (trend.calls, carry.calls, len(kwargs["submissions"]))
        )
        return original(self, **kwargs)

    monkeypatch.setattr(AtomicDecisionBatchCollector, "collect", track)
    first = invoke_portfolio_strategies(
        eligibility=first_eligibility,
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for((trend, carry)),
    )
    assert first.status is PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED
    assert first.batch_result is not None
    assert first.batch_result.batch is not None
    assert first.batch_result.state is not None
    first_by_sleeve = {
        value.context.expectation.sleeve_id: value for value in first.invocations
    }
    trend_transition = first_by_sleeve[TREND.sleeve_id].state_transition
    assert trend_transition is not None

    continuation_checkpoint = StrategyCheckpoint(
        checkpoint_key=first_by_sleeve[TREND.sleeve_id].invocation_hash,
        captured_at=first_eligibility.entry.decision_instant,
        state=trend_transition.after_state,
    )
    blocked_strategy = valid_strategies()[0]
    blocked_registration = registration(
        TREND,
        blocked_strategy,
        decision_instant=later_eligibility.entry.decision_instant,
        previous_checkpoint=continuation_checkpoint,
        previous_output=first,
        random_streams=first_by_sleeve[TREND.sleeve_id].next_random_streams,
    )
    with pytest.raises(ValueError, match="prior decision state must match"):
        invoke_portfolio_strategies(
            eligibility=later_eligibility,
            instrument_catalog=instrument_catalog(),
            registrations=(blocked_registration,),
        )
    assert blocked_strategy.calls == 0

    second = invoke_portfolio_strategies(
        eligibility=later_eligibility,
        instrument_catalog=instrument_catalog(),
        registrations=(
            registration(
                TREND,
                trend,
                decision_instant=later_eligibility.entry.decision_instant,
                previous_checkpoint=continuation_checkpoint,
                previous_output=first,
                random_streams=first_by_sleeve[TREND.sleeve_id].next_random_streams,
            ),
        ),
        prior_decision_state=first.batch_result.state,
    )

    assert second.status is PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED
    assert collector_observations == [(1, 1, 2), (2, 1, 1)]
    assert second.batch_result is not None
    assert second.batch_result.batch is not None
    assert second.batch_result.state is not None
    assert (
        second.batch_result.batch.decision_instant
        == later_eligibility.entry.decision_instant
    )
    assert second.invocations[0].context.previous_target is not None
    assert (
        second.invocations[0].context.previous_target.decision_instant
        == first_eligibility.entry.decision_instant
    )
    assert (
        second.invocations[0].context.previous_input_instant
        == first_eligibility.entry.decision_instant
    )
    assert (
        second.invocations[0].context.previous_checkpoint_hash
        == continuation_checkpoint.checkpoint_hash
    )
    by_sleeve = {
        value.target_snapshot.sleeve_id: value
        for value in second.batch_result.state.decisions
    }
    assert (
        by_sleeve[TREND.sleeve_id].decision_instant
        == later_eligibility.entry.decision_instant
    )
    assert (
        by_sleeve[CARRY.sleeve_id].decision_instant
        == first_eligibility.entry.decision_instant
    )
    assert len(second.batch_result.batch.decisions) == 1
    forged_state = replace(
        second.batch_result.state,
        decisions=(
            by_sleeve[TREND.sleeve_id],
            replace(
                by_sleeve[CARRY.sleeve_id],
                decision_instant=later_eligibility.entry.decision_instant,
            ),
        ),
    )
    with pytest.raises(ValueError, match="unscheduled decision state"):
        replace(
            second,
            batch_result=replace(second.batch_result, state=forged_state),
        )
    assert first.handoff_hash is not None
    assert second.handoff_hash is not None
    assert second.handoff_hash != first.handoff_hash


def test_warmup_invokes_without_decision_batch_handoff() -> None:
    strategies = valid_strategies()
    output = invoke_portfolio_strategies(
        eligibility=warmup_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for(strategies),
    )

    assert output.status is PortfolioStrategyInvocationStatus.WARMUP_SUCCEEDED
    assert [strategy.calls for strategy in strategies] == [1, 1]
    assert output.batch_result is None
    assert output.handoff_hash is None
    assert all(
        invocation.validation_result is not None
        and invocation.validation_result.failure is None
        and invocation.state_transition is not None
        and invocation.next_random_streams[0].counter == 1
        for invocation in output.invocations
    )


def test_ineligible_binds_context_evidence_without_callbacks() -> None:
    strategies = valid_strategies()
    registrations = registrations_for(strategies)
    output = invoke_portfolio_strategies(
        eligibility=ineligible_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=tuple(reversed(registrations)),
    )
    repeated = invoke_portfolio_strategies(
        eligibility=ineligible_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations,
    )

    assert output.status is PortfolioStrategyInvocationStatus.INELIGIBLE
    assert [strategy.calls for strategy in strategies] == [0, 0]
    assert len(output.invocations) == 2
    assert all(
        invocation.validation_result is None
        and invocation.state_transition is None
        and invocation.next_random_streams == ()
        and invocation.failure_code is None
        for invocation in output.invocations
    )
    assert output.output_hash == repeated.output_hash
    assert output.batch_result is None
    assert output.handoff_hash is None

    changed_state = list(registrations)
    changed_state[0] = replace(
        changed_state[0],
        previous_checkpoint=replace(
            changed_state[0].previous_checkpoint,
            state=state_for(changed_state[0].expectation, count=9),
        ),
    )
    changed_stream = list(registrations)
    changed_stream[0] = replace(
        changed_stream[0],
        random_streams=(
            replace(stream_for(changed_stream[0].expectation), master_random_seed=43),
        ),
    )
    assert (
        output.output_hash
        != invoke_portfolio_strategies(
            eligibility=ineligible_eligibility(),
            instrument_catalog=instrument_catalog(),
            registrations=tuple(changed_state),
        ).output_hash
    )
    assert (
        output.output_hash
        != invoke_portfolio_strategies(
            eligibility=ineligible_eligibility(),
            instrument_catalog=instrument_catalog(),
            registrations=tuple(changed_stream),
        ).output_hash
    )


@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_failure_code"),
    [
        (
            "callback",
            PortfolioStrategyInvocationStatus.INVOCATION_FAILED,
            PortfolioStrategyInvocationFailureCode.CALLBACK_FAILED,
        ),
        (
            "output",
            PortfolioStrategyInvocationStatus.INVOCATION_FAILED,
            PortfolioStrategyInvocationFailureCode.INVALID_OUTPUT,
        ),
        (
            "state",
            PortfolioStrategyInvocationStatus.INVOCATION_FAILED,
            PortfolioStrategyInvocationFailureCode.INVALID_STATE,
        ),
        (
            "streams",
            PortfolioStrategyInvocationStatus.INVOCATION_FAILED,
            PortfolioStrategyInvocationFailureCode.INVALID_RANDOM_STREAMS,
        ),
        (
            "validation",
            PortfolioStrategyInvocationStatus.VALIDATION_FAILED,
            None,
        ),
    ],
)
def test_failure_priority_preserves_attempted_evidence_without_authority(
    mode: str,
    expected_status: PortfolioStrategyInvocationStatus,
    expected_failure_code: PortfolioStrategyInvocationFailureCode | None,
) -> None:
    strategies = valid_strategies()
    if mode != "validation":
        strategies[0].mode = "validation"
    strategies[1].mode = mode
    registrations = registrations_for(strategies)
    before_state_hashes = tuple(
        registration.previous_state.state_hash for registration in registrations
    )
    before_stream_hashes = tuple(
        registration.random_streams[0].stream_hash for registration in registrations
    )

    output = _invoke_active(strategies)

    assert output.status is expected_status
    assert [strategy.calls for strategy in strategies] == [1, 1]
    assert output.batch_result is None
    assert output.handoff_hash is None
    assert before_state_hashes == tuple(
        registration.previous_state.state_hash for registration in registrations
    )
    assert before_stream_hashes == tuple(
        registration.random_streams[0].stream_hash for registration in registrations
    )
    if expected_failure_code is None:
        assert all(invocation.failure_code is None for invocation in output.invocations)
        assert all(
            invocation.validation_result is not None
            and invocation.state_transition is not None
            and invocation.next_random_streams
            for invocation in output.invocations
        )
    else:
        failed = next(
            invocation
            for invocation in output.invocations
            if invocation.failure_code is expected_failure_code
        )
        assert any(
            invocation.validation_result is not None
            and invocation.validation_result.failure is not None
            for invocation in output.invocations
        )
        if mode in {"callback", "output"}:
            assert failed.validation_result is None
            assert failed.state_transition is None
        elif mode == "state":
            assert failed.validation_result is not None
            assert failed.state_transition is None
        else:
            assert failed.validation_result is not None
            assert failed.state_transition is not None
            assert failed.next_random_streams == ()


def test_invalid_cross_evidence_and_duplicate_sleeve_reject_before_callbacks() -> None:
    strategies = valid_strategies()
    registrations = registrations_for(strategies)

    with pytest.raises(ValueError, match="Universe Decision Instant"):
        invoke_portfolio_strategies(
            eligibility=active_eligibility(),
            instrument_catalog=instrument_catalog(),
            registrations=(
                with_mismatched_universe(registrations[0]),
                registrations[1],
            ),
        )
    with pytest.raises(ValueError, match="unique Sleeves"):
        invoke_portfolio_strategies(
            eligibility=active_eligibility(),
            instrument_catalog=instrument_catalog(),
            registrations=(registrations[0], registrations[0]),
        )

    assert [strategy.calls for strategy in strategies] == [0, 0]


@pytest.mark.parametrize("eligibility", [active_eligibility, warmup_eligibility])
def test_same_time_prior_state_rejects_before_any_callback(eligibility: Any) -> None:
    strategies = valid_strategies()
    with pytest.raises(ValueError, match="prior_decision_state must be before"):
        invoke_portfolio_strategies(
            eligibility=eligibility(),
            instrument_catalog=instrument_catalog(),
            registrations=registrations_for(strategies),
            prior_decision_state=same_time_prior_decision_state(),
        )
    assert [strategy.calls for strategy in strategies] == [0, 0]


def test_future_same_utc_strategy_checkpoint_rejects_before_callback() -> None:
    strategy = valid_strategies()[0]
    future = StrategyCheckpoint(
        checkpoint_key="future-same-utc",
        captured_at=SAME_UTC_LATER,
        state=state_for(TREND, count=999),
    )
    current = registration(TREND, strategy, previous_checkpoint=future)

    with pytest.raises(ValueError, match="previous strategy input must be before"):
        invoke_portfolio_strategies(
            eligibility=active_eligibility(DECISION_INSTANT),
            instrument_catalog=instrument_catalog(),
            registrations=(current,),
        )
    assert strategy.calls == 0


def test_restored_future_state_cannot_replace_its_checkpoint_authority() -> None:
    strategy = valid_strategies()[0]
    future = StrategyCheckpoint(
        checkpoint_key="future-same-utc",
        captured_at=SAME_UTC_LATER,
        state=state_for(TREND, count=999),
    )
    current = registration(TREND, strategy)

    with pytest.raises(
        TypeError, match="previous_checkpoint must be StrategyCheckpoint"
    ):
        replace(current, previous_checkpoint=future.restore())
    assert strategy.calls == 0


def test_advanced_random_streams_require_prior_invocation_handoff() -> None:
    future_strategy = valid_strategies()[0]
    future = invoke_portfolio_strategies(
        eligibility=active_eligibility(SAME_UTC_LATER),
        instrument_catalog=instrument_catalog(),
        registrations=(
            registration(
                TREND,
                future_strategy,
                decision_instant=SAME_UTC_LATER,
            ),
        ),
    )
    current_strategy = valid_strategies()[0]

    with pytest.raises(ValueError, match="prior invocation handoff"):
        registration(
            TREND,
            current_strategy,
            random_streams=future.invocations[0].next_random_streams,
        )
    assert current_strategy.calls == 0


def test_batch_failure_retains_attempted_state_and_rng_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_collect(self: object, **kwargs: Any) -> AtomicDecisionBatchResult:
        return AtomicDecisionBatchResult.failed(
            DecisionBatchFailure(
                kwargs["decision_time"],
                (
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.UNEXPECTED_SUBMISSION,
                        "collector-fixture",
                    ),
                ),
                decision_instant=kwargs["decision_instant"],
            )
        )

    monkeypatch.setattr(AtomicDecisionBatchCollector, "collect", fail_collect)
    first_strategies = valid_strategies()
    first = _invoke_active(first_strategies)
    changed_strategies = valid_strategies()
    changed_strategies[0].state_increment = 999
    changed_strategies[0].stream_draws = 2
    changed = _invoke_active(changed_strategies)

    assert first.status is PortfolioStrategyInvocationStatus.BATCH_FAILED
    assert first.batch_result is not None and first.batch_result.failure is not None
    assert first.handoff_hash is None
    assert all(
        invocation.state_transition is not None and invocation.next_random_streams
        for invocation in first.invocations
    )
    assert first.output_hash != changed.output_hash

    attempted = next(
        value
        for value in first.invocations
        if value.context.expectation == TREND
    )
    assert attempted.state_transition is not None
    checkpoint = StrategyCheckpoint(
        checkpoint_key=attempted.invocation_hash,
        captured_at=attempted.state_transition.occurred_at,
        state=attempted.state_transition.after_state,
    )
    continuation = valid_strategies()[0]
    with pytest.raises(ValueError, match="successful invocation handoff"):
        registration(
            TREND,
            continuation,
            previous_checkpoint=checkpoint,
            previous_output=first,
            random_streams=attempted.next_random_streams,
        )
    assert continuation.calls == 0


@pytest.mark.parametrize("non_callable", [False, True])
def test_decide_lookup_and_callability_are_failure_isolated(non_callable: bool) -> None:
    strategies = valid_strategies()
    registrations = list(registrations_for(strategies))
    current = registrations[0]

    class BrokenStrategy:
        strategy_artifact = current.strategy_artifact

        @property
        def decide(self) -> object:
            if non_callable:
                return object()
            raise RuntimeError("descriptor failure")

    registrations[0] = replace(current, strategy=BrokenStrategy())
    output = invoke_portfolio_strategies(
        eligibility=active_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=tuple(registrations),
    )

    assert output.status is PortfolioStrategyInvocationStatus.INVOCATION_FAILED
    assert PortfolioStrategyInvocationFailureCode.CALLBACK_FAILED in {
        invocation.failure_code for invocation in output.invocations
    }
    assert strategies[1].calls == 1


def test_public_records_reject_forged_handoff_relationships() -> None:
    first = _invoke_active(valid_strategies())
    changed_strategies = valid_strategies()
    changed_strategies[0].value = "0.75"
    changed = _invoke_active(changed_strategies)
    carry, trend = first.invocations

    with pytest.raises(ValueError, match="exact-cover nonempty"):
        replace(first, invocations=())
    with pytest.raises(ValueError, match="Context must match"):
        replace(first, eligibility=warmup_eligibility())
    with pytest.raises(ValueError, match="exact-cover invocation decisions"):
        replace(first, batch_result=changed.batch_result)
    with pytest.raises(ValueError, match="validation result"):
        replace(carry, validation_result=trend.validation_result)
    with pytest.raises(ValueError, match="state transition"):
        replace(carry, state_transition=trend.state_transition)
    with pytest.raises(ValueError, match="random stream"):
        replace(carry, next_random_streams=trend.next_random_streams)
    with pytest.raises(ValueError, match="warmup_succeeded"):
        replace(
            first,
            status=PortfolioStrategyInvocationStatus.WARMUP_SUCCEEDED,
            batch_result=None,
        )


def test_registration_binds_executed_artifact_and_model_timeline_proof() -> None:
    strategies = valid_strategies()
    current = registrations_for(strategies)[0]

    with pytest.raises(ValueError, match="artifact must match"):
        replace(current, strategy_artifact=strategy_artifact(CARRY))
    with pytest.raises(TypeError, match="ModelRevisionTimeline"):
        replace(
            current,
            model_timelines=(selected_models()[0],),  # type: ignore[arg-type]
        )

    orphan = artifact(
        "orphan",
        supersedes_revision_id="missing",
        training_start=0,
        training_end=90,
        available_time=100,
        source_sequence=1,
    )
    with pytest.raises(ValueError, match="parent is missing"):
        ModelRevisionTimeline(
            model_key=MODEL_KEY,
            decision_instant=active_eligibility().entry.decision_instant,
            artifacts=(orphan,),
        )

    output = _invoke_active(strategies)
    selection = output.invocations[0].context.to_canonical_dict()["model_selections"]
    assert selection == [
        {
            "timeline_hash": current.model_timelines[0].timeline_hash,
            "artifact_ref_hash": selected_models()[0].artifact_ref_hash,
        }
    ]


def test_collector_runtime_call_count_is_active_success_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = AtomicDecisionBatchCollector.collect
    invalid_prior = same_time_prior_decision_state()
    calls = 0

    def track(
        self: AtomicDecisionBatchCollector, **kwargs: Any
    ) -> AtomicDecisionBatchResult:
        nonlocal calls
        calls += 1
        return original(self, **kwargs)

    monkeypatch.setattr(AtomicDecisionBatchCollector, "collect", track)
    _invoke_active(valid_strategies())
    assert calls == 1

    invoke_portfolio_strategies(
        eligibility=warmup_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for(valid_strategies()),
    )
    invoke_portfolio_strategies(
        eligibility=ineligible_eligibility(),
        instrument_catalog=instrument_catalog(),
        registrations=registrations_for(valid_strategies()),
    )
    validation_strategies = valid_strategies()
    validation_strategies[0].mode = "validation"
    _invoke_active(validation_strategies)
    with pytest.raises(ValueError, match="prior_decision_state"):
        invoke_portfolio_strategies(
            eligibility=active_eligibility(),
            instrument_catalog=instrument_catalog(),
            registrations=registrations_for(valid_strategies()),
            prior_decision_state=invalid_prior,
        )
    assert calls == 1
