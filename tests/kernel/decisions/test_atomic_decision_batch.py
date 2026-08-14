from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    StrategySleeveId,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    AtomicDecisionBatchCollector,
    DecisionBatchExpectation,
    DecisionBatchIssueCode,
    DecisionBatchSubmission,
    LatestSleeveDecisionState,
    StrategyValidationFailure,
    StrategyValidationIssue,
    StrategyValidationIssueCode,
    StrategyValidationResult,
)

from ._fixtures import (
    BTC,
    CARRY,
    ETH,
    TREND,
    decision,
    simulation_instant,
    submission,
)


def issue_codes(result: object) -> set[DecisionBatchIssueCode]:
    failure = getattr(result, "failure")
    assert failure is not None
    return {issue.code for issue in failure.issues}


def test_complete_batch_is_atomic_and_input_order_independent() -> None:
    collector = AtomicDecisionBatchCollector()
    first = collector.collect(
        decision_time=UtcInstant(100),
        expected=(TREND, CARRY),
        submissions=(
            submission(TREND, instrument_id=BTC),
            submission(CARRY, instrument_id=ETH, units=-250_000_000_000),
        ),
    )
    reordered = collector.collect(
        decision_time=UtcInstant(100),
        expected=(CARRY, TREND),
        submissions=(
            submission(CARRY, instrument_id=ETH, units=-250_000_000_000),
            submission(TREND, instrument_id=BTC),
        ),
    )

    assert first.failure is None
    assert first.batch is not None
    assert first.state is not None
    assert reordered.batch is not None
    assert reordered.state is not None
    assert first.batch == reordered.batch
    assert first.batch_hash == reordered.batch_hash
    assert first.state_hash == reordered.state_hash
    assert first.batch.decision_batch_id.startswith("decision-batch-v1:sha256:")
    assert [
        item.target_snapshot.sleeve_id for item in first.batch.decisions
    ] == [CARRY.sleeve_id, TREND.sleeve_id]


def test_exact_batches_chain_same_utc_and_preserve_unscheduled_sleeves() -> None:
    collector = AtomicDecisionBatchCollector()
    first_instant = simulation_instant(sequence=1)
    later_instant = simulation_instant(sequence=2)
    first = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=first_instant,
        expected=(TREND, CARRY),
        submissions=(
            submission(TREND, decision_instant=first_instant),
            submission(CARRY, instrument_id=ETH, decision_instant=first_instant),
        ),
    )
    reordered = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=first_instant,
        expected=(CARRY, TREND),
        submissions=(
            submission(CARRY, instrument_id=ETH, decision_instant=first_instant),
            submission(TREND, decision_instant=first_instant),
        ),
    )
    assert first.batch is not None and first.state is not None
    assert reordered.batch is not None and reordered.state is not None
    same_payload_later = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=later_instant,
        expected=(TREND, CARRY),
        submissions=(
            submission(TREND, decision_instant=later_instant),
            submission(CARRY, instrument_id=ETH, decision_instant=later_instant),
        ),
    )
    assert same_payload_later.batch is not None

    later = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=later_instant,
        expected=(TREND,),
        submissions=(submission(TREND, decision_instant=later_instant),),
        prior_state=first.state,
    )

    assert later.failure is None
    assert later.batch is not None and later.state is not None
    assert first.batch == reordered.batch
    assert first.batch_hash == reordered.batch_hash
    assert first.state_hash == reordered.state_hash
    assert first.batch.decision_batch_id.startswith("decision-batch-v2:sha256:")
    assert (
        first.batch.decision_batch_id
        != same_payload_later.batch.decision_batch_id
    )
    assert first.batch_hash != same_payload_later.batch_hash
    assert first.batch.decision_batch_id != later.batch.decision_batch_id
    assert first.batch_hash != later.batch_hash
    assert first.state_hash != later.state_hash
    assert canonical_sha256(
        decision(TREND, decision_instant=first_instant)
    ) != canonical_sha256(decision(TREND, decision_instant=later_instant))
    by_sleeve = {
        value.target_snapshot.sleeve_id: value for value in later.state.decisions
    }
    assert by_sleeve[TREND.sleeve_id].decision_instant == later_instant
    assert by_sleeve[CARRY.sleeve_id].decision_instant == first_instant


def test_exact_instant_mismatches_and_ambiguous_prior_state_fail_closed() -> None:
    collector = AtomicDecisionBatchCollector()
    first_instant = simulation_instant(sequence=1)
    later_instant = simulation_instant(sequence=2)
    first = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=first_instant,
        expected=(TREND,),
        submissions=(submission(TREND, decision_instant=first_instant),),
    )
    later = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=later_instant,
        expected=(TREND,),
        submissions=(submission(TREND, decision_instant=later_instant),),
        prior_state=first.state,
    )
    assert first.state is not None and later.state is not None

    replayed = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=later_instant,
        expected=(CARRY,),
        submissions=(submission(CARRY, decision_instant=first_instant),),
        prior_state=first.state,
    )
    equal = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=first_instant,
        expected=(CARRY,),
        submissions=(submission(CARRY, decision_instant=first_instant),),
        prior_state=first.state,
    )
    earlier = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=first_instant,
        expected=(CARRY,),
        submissions=(submission(CARRY, decision_instant=first_instant),),
        prior_state=later.state,
    )
    legacy_same_utc = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=later_instant,
        expected=(CARRY,),
        submissions=(submission(CARRY, decision_instant=later_instant),),
        prior_state=LatestSleeveDecisionState(
            as_of=UtcInstant(100), decisions=(decision(TREND),)
        ),
    )
    downgrade = collector.collect(
        decision_time=UtcInstant(101),
        expected=(TREND,),
        submissions=(submission(TREND, decision_time=101),),
        prior_state=first.state,
    )

    assert issue_codes(replayed) == {
        DecisionBatchIssueCode.DECISION_INSTANT_MISMATCH
    }
    assert replayed.failure is not None
    assert replayed.failure.decision_instant == later_instant
    assert issue_codes(equal) == {
        DecisionBatchIssueCode.PRIOR_STATE_NOT_BEFORE_DECISION
    }
    assert issue_codes(earlier) == {
        DecisionBatchIssueCode.PRIOR_STATE_NOT_BEFORE_DECISION
    }
    assert issue_codes(legacy_same_utc) == {
        DecisionBatchIssueCode.PRIOR_STATE_NOT_BEFORE_DECISION
    }
    assert issue_codes(downgrade) == {
        DecisionBatchIssueCode.PRIOR_STATE_INSTANT_MODE_MISMATCH
    }
    assert all(
        result.batch is None and result.state is None
        for result in (replayed, equal, earlier, legacy_same_utc, downgrade)
    )

    with pytest.raises(ValueError, match="decision_instant instant"):
        collector.collect(
            decision_time=UtcInstant(101),
            decision_instant=first_instant,
            expected=(TREND,),
            submissions=(),
        )
    with pytest.raises(ValueError, match="as_of_instant instant"):
        LatestSleeveDecisionState(
            as_of=UtcInstant(101),
            decisions=(decision(TREND, decision_instant=first_instant),),
            as_of_instant=first_instant,
        )
    with pytest.raises(ValueError, match="same-UTC decisions require decision_instant"):
        LatestSleeveDecisionState(
            as_of=UtcInstant(100),
            decisions=(decision(TREND),),
            as_of_instant=first_instant,
        )


def test_validation_failure_produces_neither_partial_batch_nor_state() -> None:
    validation_failure = StrategyValidationFailure(
        candidate_payload_hash="sha256:" + "a" * 64,
        issues=(
            StrategyValidationIssue(
                code=StrategyValidationIssueCode.UNKNOWN_INSTRUMENT,
                path="$.targets[0].instrument_id",
                subject_key="unknown",
            ),
        ),
    )
    result = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(TREND, CARRY),
        submissions=(
            submission(TREND),
            DecisionBatchSubmission(
                expectation=CARRY,
                result=StrategyValidationResult.invalid(validation_failure),
            ),
        ),
    )

    assert result.batch is None
    assert result.state is None
    assert issue_codes(result) == {DecisionBatchIssueCode.VALIDATION_FAILED}
    assert result.failure is not None
    assert result.failure.issues[0].evidence_hash == canonical_sha256(
        validation_failure
    )


def test_missing_duplicate_and_unexpected_submissions_fail_together() -> None:
    unexpected = DecisionBatchExpectation(
        "mean-reversion-v1", StrategySleeveId("mean-reversion.primary")
    )
    result = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(TREND, CARRY),
        submissions=(
            submission(TREND),
            submission(TREND),
            submission(unexpected),
        ),
    )

    assert result.batch is None
    assert result.state is None
    assert issue_codes(result) == {
        DecisionBatchIssueCode.DUPLICATE_SUBMISSION,
        DecisionBatchIssueCode.MISSING_SUBMISSION,
        DecisionBatchIssueCode.UNEXPECTED_SUBMISSION,
    }


def test_empty_and_duplicate_expectations_fail_closed() -> None:
    collector = AtomicDecisionBatchCollector()

    empty = collector.collect(
        decision_time=UtcInstant(100), expected=(), submissions=()
    )
    duplicate = collector.collect(
        decision_time=UtcInstant(100),
        expected=(TREND, TREND),
        submissions=(submission(TREND),),
    )

    assert issue_codes(empty) == {DecisionBatchIssueCode.EMPTY_EXPECTATION}
    assert issue_codes(duplicate) == {
        DecisionBatchIssueCode.DUPLICATE_EXPECTED_SLEEVE
    }
    assert empty.batch is empty.state is None
    assert duplicate.batch is duplicate.state is None


def test_submission_identity_and_decision_time_mismatch_fail_closed() -> None:
    wrong_strategy = DecisionBatchExpectation("other-v1", TREND.sleeve_id)
    wrong_sleeve_decision = replace(
        decision(CARRY),
        target_snapshot=replace(
            decision(CARRY).target_snapshot,
            sleeve_id=TREND.sleeve_id,
        ),
    )
    result = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(TREND, CARRY),
        submissions=(
            submission(wrong_strategy),
            DecisionBatchSubmission(
                expectation=CARRY,
                result=StrategyValidationResult.valid(wrong_sleeve_decision),
            ),
        ),
    )
    wrong_time = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(TREND,),
        submissions=(submission(TREND, decision_time=101),),
    )

    assert issue_codes(result) == {
        DecisionBatchIssueCode.STRATEGY_ID_MISMATCH,
        DecisionBatchIssueCode.SLEEVE_ID_MISMATCH,
    }
    assert issue_codes(wrong_time) == {
        DecisionBatchIssueCode.DECISION_TIME_MISMATCH
    }


def test_new_instant_replaces_scheduled_sleeve_and_preserves_other_sleeves() -> None:
    collector = AtomicDecisionBatchCollector()
    initial = collector.collect(
        decision_time=UtcInstant(100),
        expected=(TREND, CARRY),
        submissions=(submission(TREND), submission(CARRY, instrument_id=ETH)),
    )
    assert initial.state is not None

    updated = collector.collect(
        decision_time=UtcInstant(200),
        expected=(TREND,),
        submissions=(submission(TREND, decision_time=200, units=750_000_000_000),),
        prior_state=initial.state,
    )

    assert updated.failure is None
    assert updated.batch is not None
    assert updated.state is not None
    by_sleeve = {
        item.target_snapshot.sleeve_id: item for item in updated.state.decisions
    }
    assert by_sleeve[TREND.sleeve_id].decision_time == UtcInstant(200)
    assert by_sleeve[CARRY.sleeve_id].decision_time == UtcInstant(100)
    assert len(updated.batch.decisions) == 1


def test_same_or_future_prior_state_cannot_be_used_to_patch_an_instant() -> None:
    prior = LatestSleeveDecisionState(
        as_of=UtcInstant(100), decisions=(decision(TREND),)
    )

    same = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(CARRY,),
        submissions=(submission(CARRY),),
        prior_state=prior,
    )
    future = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(99),
        expected=(CARRY,),
        submissions=(submission(CARRY, decision_time=99),),
        prior_state=prior,
    )

    assert issue_codes(same) == {
        DecisionBatchIssueCode.PRIOR_STATE_NOT_BEFORE_DECISION
    }
    assert issue_codes(future) == {
        DecisionBatchIssueCode.PRIOR_STATE_NOT_BEFORE_DECISION
    }


def test_state_and_submission_values_are_immutable_data_not_callbacks() -> None:
    result = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(TREND,),
        submissions=(submission(TREND),),
    )

    assert result.state is not None
    assert isinstance(result.state.decisions, tuple)
    assert isinstance(submission(TREND).result, StrategyValidationResult)
