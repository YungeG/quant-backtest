from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from re import compile as compile_pattern
from typing import Iterable

from crypto_quant_domain import (
    ArtifactEnvelope,
    DecisionBatch,
    FeeAssessment,
    Fill,
    PortfolioSnapshot,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    ApprovedPortfolioTarget,
    LedgerState,
    NormalizedPortfolioTarget,
    OrderEventStream,
    OrderPlan,
    PortfolioAllocation,
)

from .engine import EngineExecutionResult, ExecutionTrace
from .evidence import (
    EvidenceArtifactRole,
    EvidencePublicationStatus,
    FinalizedAttemptEvidence,
)
from .run_end import RunEndReport
from .runner import AttemptIdentity, ReadyToFinalizeAttempt
from .slippage import SlippageDecision


_SHA256_PATTERN = compile_pattern(r"sha256:[0-9a-f]{64}")
_RUN_PATTERN = compile_pattern(r"run_[0-9a-f]{64}")
_ATTEMPT_PATTERN = compile_pattern(r"attempt_[0-9a-f]{64}")


def _hash(name: str, value: object) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")


@dataclass(frozen=True, slots=True)
class CanonicalExecutionSummary:
    """Attempt-independent canonical view of authoritative Engine output."""

    result: EngineExecutionResult

    def __post_init__(self) -> None:
        if not isinstance(self.result, EngineExecutionResult):
            raise TypeError("result must be EngineExecutionResult")

    @classmethod
    def from_result(cls, result: EngineExecutionResult) -> CanonicalExecutionSummary:
        return cls(result)

    @property
    def trace(self) -> ExecutionTrace:
        return self.result.trace

    @property
    def decision_batches(self) -> tuple[DecisionBatch, ...]:
        return self.result.decision_batches

    @property
    def allocations(self) -> tuple[PortfolioAllocation, ...]:
        return self.result.allocations

    @property
    def approved_targets(self) -> tuple[ApprovedPortfolioTarget, ...]:
        return self.result.approved_targets

    @property
    def normalized_targets(self) -> tuple[NormalizedPortfolioTarget, ...]:
        return self.result.normalized_targets

    @property
    def order_plans(self) -> tuple[OrderPlan, ...]:
        return self.result.order_plans

    @property
    def order_streams(self) -> tuple[OrderEventStream, ...]:
        return self.result.order_streams

    @property
    def fills(self) -> tuple[Fill, ...]:
        return self.result.fills

    @property
    def slippage_decisions(self) -> tuple[SlippageDecision, ...]:
        return self.result.slippage_decisions

    @property
    def fee_assessments(self) -> tuple[FeeAssessment, ...]:
        return self.result.fee_assessments

    @property
    def final_journal(self) -> AccountingJournal:
        return self.result.final_journal

    @property
    def final_ledger_state(self) -> LedgerState:
        return self.result.final_ledger_state

    @property
    def final_portfolio_snapshot(self) -> PortfolioSnapshot:
        return self.result.final_portfolio_snapshot

    @property
    def run_end_report(self) -> RunEndReport:
        return self.result.run_end_report

    @property
    def execution_result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        summary = self.result.to_canonical_dict()
        summary["type"] = "canonical_execution_summary"
        del summary["case_hash"]
        del summary["target_stream_digest"]
        return summary


class ExecutionHashEvidenceErrorCode(str, Enum):
    EVIDENCE_NOT_READY = "evidence_not_ready"
    ATTEMPT_MISMATCH = "attempt_mismatch"
    ENGINE_ARTIFACT_MISSING = "engine_artifact_missing"
    ENGINE_ARTIFACT_MISMATCH = "engine_artifact_mismatch"
    EMPTY_ATTEMPT_SET = "empty_attempt_set"
    SEMANTIC_RUN_MISMATCH = "semantic_run_mismatch"
    DUPLICATE_ATTEMPT_CONFLICT = "duplicate_attempt_conflict"


class ExecutionHashEvidenceError(ValueError):
    def __init__(
        self,
        code: ExecutionHashEvidenceErrorCode,
        subject_keys: Iterable[str] = (),
    ) -> None:
        if not isinstance(code, ExecutionHashEvidenceErrorCode):
            raise TypeError("code must be ExecutionHashEvidenceErrorCode")
        subjects = tuple(sorted(set(subject_keys)))
        if not all(type(value) is str and value for value in subjects):
            raise TypeError("subject_keys must contain nonempty strings")
        self.code = code
        self.subject_keys = subjects
        super().__init__(code.value)

    @property
    def error_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_hash_evidence_error",
            "schema_version": 1,
            "code": self.code.value,
            "subject_keys": self.subject_keys,
        }


@dataclass(frozen=True, slots=True)
class ExecutionHashAttemptRef:
    semantic_run_id: str
    attempt_id: str
    evidence_manifest_hash: str
    execution_result_hash: str

    def __post_init__(self) -> None:
        if (
            type(self.semantic_run_id) is not str
            or _RUN_PATTERN.fullmatch(self.semantic_run_id) is None
        ):
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if (
            type(self.attempt_id) is not str
            or _ATTEMPT_PATTERN.fullmatch(self.attempt_id) is None
        ):
            raise ValueError("attempt_id must use attempt_sha256 schema")
        _hash("evidence_manifest_hash", self.evidence_manifest_hash)
        _hash("execution_result_hash", self.execution_result_hash)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "semantic_run_id": self.semantic_run_id,
            "attempt_id": self.attempt_id,
            "evidence_manifest_hash": self.evidence_manifest_hash,
            "execution_result_hash": self.execution_result_hash,
        }


@dataclass(frozen=True, slots=True)
class AttemptExecutionHash:
    attempt: AttemptIdentity
    evidence_manifest_hash: str
    engine_result_artifact_content_hash: str
    engine_result: EngineExecutionResult
    summary: CanonicalExecutionSummary

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, AttemptIdentity):
            raise TypeError("attempt must be AttemptIdentity")
        _hash("evidence_manifest_hash", self.evidence_manifest_hash)
        _hash(
            "engine_result_artifact_content_hash",
            self.engine_result_artifact_content_hash,
        )
        if not isinstance(self.engine_result, EngineExecutionResult):
            raise TypeError("engine_result must be EngineExecutionResult")
        if not isinstance(self.summary, CanonicalExecutionSummary):
            raise TypeError("summary must be CanonicalExecutionSummary")
        expected = CanonicalExecutionSummary.from_result(self.engine_result)
        if self.summary != expected:
            raise ValueError("summary does not match EngineExecutionResult")

    @property
    def execution_result_hash(self) -> str:
        return self.summary.execution_result_hash

    def to_ref(self) -> ExecutionHashAttemptRef:
        return ExecutionHashAttemptRef(
            semantic_run_id=self.attempt.semantic_run_id,
            attempt_id=self.attempt.attempt_id,
            evidence_manifest_hash=self.evidence_manifest_hash,
            execution_result_hash=self.execution_result_hash,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "attempt_execution_hash",
            "schema_version": 1,
            "attempt": self.attempt,
            "evidence_manifest_hash": self.evidence_manifest_hash,
            "engine_result_artifact_content_hash": (
                self.engine_result_artifact_content_hash
            ),
            "summary": self.summary,
            "execution_result_hash": self.execution_result_hash,
        }


@dataclass(frozen=True, slots=True)
class ExecutionHashConsistency:
    semantic_run_id: str
    execution_result_hash: str
    attempts: tuple[ExecutionHashAttemptRef, ...]

    def __post_init__(self) -> None:
        _validate_attempt_refs(self.semantic_run_id, self.attempts)
        _hash("execution_result_hash", self.execution_result_hash)
        if any(
            attempt.execution_result_hash != self.execution_result_hash
            for attempt in self.attempts
        ):
            raise ValueError("consistent Attempt refs must share execution hash")

    @property
    def consistency_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_hash_consistency",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "execution_result_hash": self.execution_result_hash,
            "attempts": self.attempts,
        }


@dataclass(frozen=True, slots=True)
class ExecutionHashMismatch:
    semantic_run_id: str
    attempts: tuple[ExecutionHashAttemptRef, ...]

    def __post_init__(self) -> None:
        _validate_attempt_refs(self.semantic_run_id, self.attempts)
        if len({attempt.execution_result_hash for attempt in self.attempts}) < 2:
            raise ValueError("mismatch requires at least two execution hashes")

    @property
    def mismatch_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_hash_mismatch",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "attempts": self.attempts,
        }


def _validate_attempt_refs(
    semantic_run_id: str, attempts: tuple[ExecutionHashAttemptRef, ...]
) -> None:
    if type(semantic_run_id) is not str or _RUN_PATTERN.fullmatch(semantic_run_id) is None:
        raise ValueError("semantic_run_id must use run_sha256 schema")
    if type(attempts) is not tuple or not attempts or not all(
        isinstance(value, ExecutionHashAttemptRef) for value in attempts
    ):
        raise TypeError("attempts must be a nonempty tuple of refs")
    if attempts != tuple(sorted(attempts, key=lambda value: value.attempt_id)):
        raise ValueError("Attempt refs must use canonical order")
    if len({value.attempt_id for value in attempts}) != len(attempts):
        raise ValueError("Attempt refs must be unique")
    if any(value.semantic_run_id != semantic_run_id for value in attempts):
        raise ValueError("Attempt refs must share semantic run")


@dataclass(frozen=True, slots=True)
class ExecutionHashCheck:
    consistency: ExecutionHashConsistency | None = None
    mismatch: ExecutionHashMismatch | None = None

    def __post_init__(self) -> None:
        if (self.consistency is None) == (self.mismatch is None):
            raise ValueError("execution hash check requires exactly one branch")
        if self.consistency is not None and not isinstance(
            self.consistency, ExecutionHashConsistency
        ):
            raise TypeError("consistency must be ExecutionHashConsistency")
        if self.mismatch is not None and not isinstance(
            self.mismatch, ExecutionHashMismatch
        ):
            raise TypeError("mismatch must be ExecutionHashMismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_hash_check",
            "schema_version": 1,
            "consistency": self.consistency,
            "mismatch": self.mismatch,
        }


class ExecutionResultHasher:
    """Binds authoritative Engine output to immutable Attempt evidence."""

    @staticmethod
    def bind(
        ready: ReadyToFinalizeAttempt,
        finalized: FinalizedAttemptEvidence,
    ) -> AttemptExecutionHash:
        if not isinstance(ready, ReadyToFinalizeAttempt):
            raise TypeError("ready must be ReadyToFinalizeAttempt")
        if not isinstance(finalized, FinalizedAttemptEvidence):
            raise TypeError("finalized must be FinalizedAttemptEvidence")
        if finalized.status is not EvidencePublicationStatus.READY_FOR_INTEGRITY:
            raise ExecutionHashEvidenceError(
                ExecutionHashEvidenceErrorCode.EVIDENCE_NOT_READY,
                (finalized.status.value,),
            )
        if finalized.attempt != ready.attempt:
            raise ExecutionHashEvidenceError(
                ExecutionHashEvidenceErrorCode.ATTEMPT_MISMATCH,
                (ready.attempt.attempt_id, finalized.attempt.attempt_id),
            )
        entries = tuple(
            entry
            for entry in finalized.manifest.artifacts
            if entry.role is EvidenceArtifactRole.ENGINE_EXECUTION_RESULT
        )
        if len(entries) != 1:
            raise ExecutionHashEvidenceError(
                ExecutionHashEvidenceErrorCode.ENGINE_ARTIFACT_MISSING,
                (finalized.manifest.manifest_hash,),
            )
        entry = entries[0]
        expected_content_hash = ArtifactEnvelope.create(
            "engine_execution_result", 1, ready.engine_result
        ).content_hash
        if (
            entry.relative_path != "engine-execution-result.json"
            or entry.artifact_type != "engine_execution_result"
            or entry.schema_version != 1
            or entry.content_hash != expected_content_hash
        ):
            raise ExecutionHashEvidenceError(
                ExecutionHashEvidenceErrorCode.ENGINE_ARTIFACT_MISMATCH,
                (entry.content_hash, expected_content_hash),
            )
        summary = CanonicalExecutionSummary.from_result(ready.engine_result)
        return AttemptExecutionHash(
            attempt=ready.attempt,
            evidence_manifest_hash=finalized.manifest.manifest_hash,
            engine_result_artifact_content_hash=entry.content_hash,
            engine_result=ready.engine_result,
            summary=summary,
        )

    @staticmethod
    def check_same_semantic_run(
        attempts: Iterable[AttemptExecutionHash | ExecutionHashAttemptRef],
    ) -> ExecutionHashCheck:
        try:
            supplied = tuple(attempts)
        except TypeError as error:
            raise TypeError("attempts must be iterable") from error
        if not supplied:
            raise ExecutionHashEvidenceError(
                ExecutionHashEvidenceErrorCode.EMPTY_ATTEMPT_SET
            )
        if not all(
            isinstance(value, (AttemptExecutionHash, ExecutionHashAttemptRef))
            for value in supplied
        ):
            raise TypeError("attempts contain invalid values")
        refs = tuple(
            value.to_ref() if isinstance(value, AttemptExecutionHash) else value
            for value in supplied
        )
        semantic_runs = {value.semantic_run_id for value in refs}
        if len(semantic_runs) != 1:
            raise ExecutionHashEvidenceError(
                ExecutionHashEvidenceErrorCode.SEMANTIC_RUN_MISMATCH,
                semantic_runs,
            )
        by_attempt: dict[str, ExecutionHashAttemptRef] = {}
        for ref in refs:
            existing = by_attempt.get(ref.attempt_id)
            if existing is not None and existing != ref:
                raise ExecutionHashEvidenceError(
                    ExecutionHashEvidenceErrorCode.DUPLICATE_ATTEMPT_CONFLICT,
                    (ref.attempt_id,),
                )
            by_attempt[ref.attempt_id] = ref
        ordered = tuple(sorted(by_attempt.values(), key=lambda value: value.attempt_id))
        semantic_run_id = ordered[0].semantic_run_id
        hashes = {value.execution_result_hash for value in ordered}
        if len(hashes) == 1:
            return ExecutionHashCheck(
                consistency=ExecutionHashConsistency(
                    semantic_run_id=semantic_run_id,
                    execution_result_hash=ordered[0].execution_result_hash,
                    attempts=ordered,
                )
            )
        return ExecutionHashCheck(
            mismatch=ExecutionHashMismatch(
                semantic_run_id=semantic_run_id,
                attempts=ordered,
            )
        )


__all__ = [
    "AttemptExecutionHash",
    "CanonicalExecutionSummary",
    "ExecutionHashAttemptRef",
    "ExecutionHashCheck",
    "ExecutionHashConsistency",
    "ExecutionHashEvidenceError",
    "ExecutionHashEvidenceErrorCode",
    "ExecutionHashMismatch",
    "ExecutionResultHasher",
]
