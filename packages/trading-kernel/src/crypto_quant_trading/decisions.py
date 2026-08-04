from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from crypto_quant_domain import (
    DecisionBatch,
    StrategyDecision,
    StrategySleeveId,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .validation import StrategyValidationResult


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


@dataclass(frozen=True, slots=True, order=True)
class DecisionBatchExpectation:
    strategy_id: str
    sleeve_id: StrategySleeveId

    def __post_init__(self) -> None:
        _canonical_text("strategy_id", self.strategy_id)
        if not isinstance(self.sleeve_id, StrategySleeveId):
            raise TypeError("sleeve_id must be StrategySleeveId")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "decision_batch_expectation",
            "strategy_id": self.strategy_id,
            "sleeve_id": self.sleeve_id.to_canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class DecisionBatchSubmission:
    expectation: DecisionBatchExpectation
    result: StrategyValidationResult

    def __post_init__(self) -> None:
        if not isinstance(self.expectation, DecisionBatchExpectation):
            raise TypeError("expectation must be DecisionBatchExpectation")
        if not isinstance(self.result, StrategyValidationResult):
            raise TypeError("result must be StrategyValidationResult")


class DecisionBatchIssueCode(str, Enum):
    EMPTY_EXPECTATION = "empty_expectation"
    DUPLICATE_EXPECTED_SLEEVE = "duplicate_expected_sleeve"
    MISSING_SUBMISSION = "missing_submission"
    DUPLICATE_SUBMISSION = "duplicate_submission"
    UNEXPECTED_SUBMISSION = "unexpected_submission"
    VALIDATION_FAILED = "validation_failed"
    STRATEGY_ID_MISMATCH = "strategy_id_mismatch"
    SLEEVE_ID_MISMATCH = "sleeve_id_mismatch"
    DECISION_TIME_MISMATCH = "decision_time_mismatch"
    PRIOR_STATE_NOT_BEFORE_DECISION = "prior_state_not_before_decision"


@dataclass(frozen=True, slots=True)
class DecisionBatchIssue:
    code: DecisionBatchIssueCode
    subject_key: str
    evidence_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, DecisionBatchIssueCode):
            raise TypeError("code must be DecisionBatchIssueCode")
        _canonical_text("subject_key", self.subject_key)
        if self.evidence_hash is not None and _SHA256.fullmatch(
            self.evidence_hash
        ) is None:
            raise ValueError("evidence_hash must be canonical sha256")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "decision_batch_issue",
            "code": self.code.value,
            "subject_key": self.subject_key,
            "evidence_hash": self.evidence_hash,
        }


def _issue_key(issue: DecisionBatchIssue) -> tuple[str, str, str]:
    return (issue.code.value, issue.subject_key, issue.evidence_hash or "")


@dataclass(frozen=True, slots=True)
class DecisionBatchFailure:
    decision_time: UtcInstant
    issues: tuple[DecisionBatchIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.decision_time, UtcInstant):
            raise TypeError("decision_time must be UtcInstant")
        if not isinstance(self.issues, tuple) or not self.issues:
            raise ValueError("issues must be a non-empty tuple")
        if not all(isinstance(issue, DecisionBatchIssue) for issue in self.issues):
            raise TypeError("issues must contain DecisionBatchIssue")
        object.__setattr__(self, "issues", tuple(sorted(set(self.issues), key=_issue_key)))

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "decision_batch_failure",
            "decision_time": self.decision_time.to_canonical_dict(),
            "issues": [issue.to_canonical_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class LatestSleeveDecisionState:
    as_of: UtcInstant | None
    decisions: tuple[StrategyDecision, ...]

    def __post_init__(self) -> None:
        if self.as_of is not None and not isinstance(self.as_of, UtcInstant):
            raise TypeError("as_of must be UtcInstant or None")
        if not isinstance(self.decisions, tuple):
            raise TypeError("decisions must be a tuple")
        if not all(isinstance(value, StrategyDecision) for value in self.decisions):
            raise TypeError("decisions must contain StrategyDecision")
        if bool(self.decisions) != (self.as_of is not None):
            raise ValueError("empty state requires no as_of and non-empty state requires as_of")
        if self.as_of is not None and any(
            decision.decision_time > self.as_of for decision in self.decisions
        ):
            raise ValueError("state cannot contain a decision after as_of")
        sleeve_ids = [decision.target_snapshot.sleeve_id for decision in self.decisions]
        if len(set(sleeve_ids)) != len(sleeve_ids):
            raise ValueError("state cannot contain duplicate Sleeve decisions")
        object.__setattr__(
            self,
            "decisions",
            tuple(
                sorted(
                    self.decisions,
                    key=lambda value: (
                        value.target_snapshot.sleeve_id,
                        value.strategy_id,
                    ),
                )
            ),
        )

    @classmethod
    def empty(cls) -> LatestSleeveDecisionState:
        return cls(as_of=None, decisions=())

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "latest_sleeve_decision_state",
            "as_of": self.as_of.to_canonical_dict() if self.as_of is not None else None,
            "decisions": [decision.to_canonical_dict() for decision in self.decisions],
        }


@dataclass(frozen=True, slots=True)
class AtomicDecisionBatchResult:
    batch: DecisionBatch | None
    state: LatestSleeveDecisionState | None
    failure: DecisionBatchFailure | None

    def __post_init__(self) -> None:
        success = self.batch is not None and self.state is not None and self.failure is None
        failed = self.batch is None and self.state is None and self.failure is not None
        if not success and not failed:
            raise ValueError("result requires batch/state success or failure only")
        if self.batch is not None and not isinstance(self.batch, DecisionBatch):
            raise TypeError("batch must be DecisionBatch or None")
        if self.state is not None and not isinstance(
            self.state, LatestSleeveDecisionState
        ):
            raise TypeError("state must be LatestSleeveDecisionState or None")
        if self.failure is not None and not isinstance(
            self.failure, DecisionBatchFailure
        ):
            raise TypeError("failure must be DecisionBatchFailure or None")

    @property
    def batch_hash(self) -> str | None:
        return canonical_sha256(self.batch) if self.batch is not None else None

    @property
    def state_hash(self) -> str | None:
        return self.state.state_hash if self.state is not None else None

    @classmethod
    def succeeded(
        cls, batch: DecisionBatch, state: LatestSleeveDecisionState
    ) -> AtomicDecisionBatchResult:
        return cls(batch=batch, state=state, failure=None)

    @classmethod
    def failed(cls, failure: DecisionBatchFailure) -> AtomicDecisionBatchResult:
        return cls(batch=None, state=None, failure=failure)


class AtomicDecisionBatchCollector:
    def collect(
        self,
        *,
        decision_time: UtcInstant,
        expected: tuple[DecisionBatchExpectation, ...],
        submissions: tuple[DecisionBatchSubmission, ...],
        prior_state: LatestSleeveDecisionState | None = None,
    ) -> AtomicDecisionBatchResult:
        if not isinstance(decision_time, UtcInstant):
            raise TypeError("decision_time must be UtcInstant")
        if not isinstance(expected, tuple) or not all(
            isinstance(value, DecisionBatchExpectation) for value in expected
        ):
            raise TypeError("expected must be a tuple of DecisionBatchExpectation")
        if not isinstance(submissions, tuple) or not all(
            isinstance(value, DecisionBatchSubmission) for value in submissions
        ):
            raise TypeError("submissions must be a tuple of DecisionBatchSubmission")
        if prior_state is not None and not isinstance(
            prior_state, LatestSleeveDecisionState
        ):
            raise TypeError("prior_state must be LatestSleeveDecisionState or None")

        state = prior_state or LatestSleeveDecisionState.empty()
        issues: list[DecisionBatchIssue] = []
        expected_by_sleeve: dict[StrategySleeveId, DecisionBatchExpectation] = {}
        expected_counts: dict[StrategySleeveId, int] = defaultdict(int)
        for expectation in expected:
            expected_counts[expectation.sleeve_id] += 1
            expected_by_sleeve.setdefault(expectation.sleeve_id, expectation)

        if not expected:
            issues.append(
                DecisionBatchIssue(
                    DecisionBatchIssueCode.EMPTY_EXPECTATION, "decision_batch"
                )
            )
        for sleeve_id, count in expected_counts.items():
            if count > 1:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.DUPLICATE_EXPECTED_SLEEVE,
                        sleeve_id.value,
                    )
                )

        submissions_by_sleeve: dict[
            StrategySleeveId, list[DecisionBatchSubmission]
        ] = defaultdict(list)
        for submission in submissions:
            sleeve_id = submission.expectation.sleeve_id
            submissions_by_sleeve[sleeve_id].append(submission)
            registered = expected_by_sleeve.get(sleeve_id)
            if registered is None:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.UNEXPECTED_SUBMISSION,
                        sleeve_id.value,
                    )
                )
            elif submission.expectation.strategy_id != registered.strategy_id:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.STRATEGY_ID_MISMATCH,
                        sleeve_id.value,
                    )
                )

        decisions: list[StrategyDecision] = []
        for sleeve_id, expectation in expected_by_sleeve.items():
            matching = submissions_by_sleeve.get(sleeve_id, [])
            if not matching:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.MISSING_SUBMISSION, sleeve_id.value
                    )
                )
                continue
            if len(matching) > 1:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.DUPLICATE_SUBMISSION, sleeve_id.value
                    )
                )
                continue
            submission = matching[0]
            if submission.expectation.strategy_id != expectation.strategy_id:
                continue
            result = submission.result
            if result.failure is not None:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.VALIDATION_FAILED,
                        sleeve_id.value,
                        canonical_sha256(result.failure),
                    )
                )
                continue
            decision = cast(StrategyDecision, result.decision)
            if decision.strategy_id != expectation.strategy_id:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.STRATEGY_ID_MISMATCH, sleeve_id.value
                    )
                )
            if decision.target_snapshot.sleeve_id != expectation.sleeve_id:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.SLEEVE_ID_MISMATCH, sleeve_id.value
                    )
                )
            if decision.decision_time != decision_time:
                issues.append(
                    DecisionBatchIssue(
                        DecisionBatchIssueCode.DECISION_TIME_MISMATCH, sleeve_id.value
                    )
                )
            decisions.append(decision)

        if state.as_of is not None and state.as_of >= decision_time:
            issues.append(
                DecisionBatchIssue(
                    DecisionBatchIssueCode.PRIOR_STATE_NOT_BEFORE_DECISION,
                    "prior_state",
                    state.state_hash,
                )
            )

        if issues:
            return AtomicDecisionBatchResult.failed(
                DecisionBatchFailure(decision_time, tuple(issues))
            )

        ordered_decisions = tuple(
            sorted(
                decisions,
                key=lambda value: (
                    value.target_snapshot.sleeve_id,
                    value.strategy_id,
                ),
            )
        )
        identity_payload = {
            "type": "decision_batch_identity",
            "schema_version": 1,
            "decision_time": decision_time.to_canonical_dict(),
            "decisions": [value.to_canonical_dict() for value in ordered_decisions],
        }
        batch = DecisionBatch(
            decision_batch_id=f"decision-batch-v1:{canonical_sha256(identity_payload)}",
            decision_time=decision_time,
            decisions=ordered_decisions,
        )
        latest = {
            value.target_snapshot.sleeve_id: value for value in state.decisions
        }
        latest.update(
            {value.target_snapshot.sleeve_id: value for value in ordered_decisions}
        )
        updated_state = LatestSleeveDecisionState(
            as_of=decision_time, decisions=tuple(latest.values())
        )
        return AtomicDecisionBatchResult.succeeded(batch, updated_state)
