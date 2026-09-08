from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from crypto_quant_backtest import (
    AttemptConsistencySet,
    AttemptEvidenceWriter,
    AttemptIdentity,
    AuditableBacktestRunner,
    CanonicalPublicationOutcome,
    CanonicalResultPublisher,
    DeterministicBarEngine,
    EngineCancellationRequest,
    EngineExecutionOutcome,
    ExecutionResultHasher,
    ExecutionTrace,
    InputOrigin,
    ResolvedExecutionCase,
)
from crypto_quant_domain import canonical_sha256
from crypto_quant_market_data import InputValidationFailure
from tests.runtime.execution_hash._fixtures import ready_branch
from tests.runtime.integrity._fixtures import rebuild_evidence
from tests.runtime.runner._fixtures import resolved_request_and_case


def _directory_bytes(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


@dataclass(frozen=True, slots=True)
class G07CompletedJourney:
    case: ResolvedExecutionCase
    attempts: AttemptConsistencySet
    publication: CanonicalPublicationOutcome
    engine_calls: tuple[ResolvedExecutionCase, ...]
    canonical_existed_before: bool
    input_hashes_before: dict[str, str]
    input_hashes_after: dict[str, str]
    attempt_bytes_before: dict[str, bytes]
    attempt_bytes_after: dict[str, bytes]


@dataclass(frozen=True, slots=True)
class G07MismatchJourney:
    attempts: AttemptConsistencySet
    publication: CanonicalPublicationOutcome
    canonical_directory: Path
    evaluation_directory: Path
    input_hashes_before: dict[str, str]
    input_hashes_after: dict[str, str]
    attempt_bytes_before: dict[str, bytes]
    attempt_bytes_after: dict[str, bytes]


class _RecordingDelegateEngine:
    def __init__(self) -> None:
        self._delegate = DeterministicBarEngine()
        self.calls: list[ResolvedExecutionCase] = []

    def run(
        self,
        case: ResolvedExecutionCase | InputValidationFailure,
        *,
        cancellation: EngineCancellationRequest | None = None,
    ) -> EngineExecutionOutcome:
        if isinstance(case, ResolvedExecutionCase):
            self.calls.append(case)
        return self._delegate.run(case, cancellation=cancellation)


class _SequenceEngine:
    def __init__(self, outcomes: tuple[EngineExecutionOutcome, ...]) -> None:
        self._outcomes = outcomes
        self._index = 0

    def run(self, case, *, cancellation=None):
        outcome = self._outcomes[self._index]
        self._index += 1
        return outcome


def _input_hashes(
    case: ResolvedExecutionCase,
    attempts: AttemptConsistencySet,
) -> dict[str, str]:
    return {
        "execution_case": canonical_sha256(case),
        "resolved_request": canonical_sha256(attempts.resolved_request),
        "attempt_consistency_set": attempts.consistency_set_hash,
        "first_engine_result": canonical_sha256(
            attempts.attempt_hashes[0].engine_result
        ),
        "second_engine_result": canonical_sha256(
            attempts.attempt_hashes[1].engine_result
        ),
    }


def completed_journey(root: Path) -> G07CompletedJourney:
    resolved, case = resolved_request_and_case()
    engine = _RecordingDelegateEngine()
    runner = AuditableBacktestRunner(engine=engine, publication_root=root)
    first = runner.execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    second = runner.retry_from_start(
        previous=first,
        resolved_request=resolved,
        execution_case=case,
        next_attempt_ordinal=2,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    writer = AttemptEvidenceWriter(root=root)
    first_publication = writer.publish(first)
    second_publication = writer.publish(second)
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None
    finalized = (first_publication.finalized, second_publication.finalized)
    hashes = (
        ExecutionResultHasher.bind(ready_branch(first), finalized[0]),
        ExecutionResultHasher.bind(ready_branch(second), finalized[1]),
    )
    attempts = AttemptConsistencySet(resolved, hashes, finalized)
    attempts_directory = root / "runs" / resolved.semantic_run_id / "attempts"
    before = _directory_bytes(attempts_directory)
    input_hashes_before = _input_hashes(case, attempts)
    canonical = root / "runs" / resolved.semantic_run_id / "canonical"
    canonical_existed_before = canonical.exists()
    publication = CanonicalResultPublisher(root=root).publish(
        resolved_request=resolved,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    return G07CompletedJourney(
        case=case,
        attempts=attempts,
        publication=publication,
        engine_calls=tuple(engine.calls),
        canonical_existed_before=canonical_existed_before,
        input_hashes_before=input_hashes_before,
        input_hashes_after=_input_hashes(case, attempts),
        attempt_bytes_before=before,
        attempt_bytes_after=_directory_bytes(attempts_directory),
    )


def mismatch_journey(root: Path) -> G07MismatchJourney:
    resolved, case = resolved_request_and_case()
    baseline = DeterministicBarEngine().run(case)
    assert baseline.result is not None
    first_trace_entry = baseline.result.trace.entries[0]
    changed_result = replace(
        baseline.result,
        trace=ExecutionTrace(
            (
                replace(
                    first_trace_entry,
                    evidence_hash=canonical_sha256({"g07": "mismatch"}),
                ),
                *baseline.result.trace.entries[1:],
            )
        ),
    )
    runner = AuditableBacktestRunner(
        engine=_SequenceEngine(
            (baseline, EngineExecutionOutcome(result=changed_result))
        ),
        publication_root=root,
    )
    first = runner.execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    second = runner.retry_from_start(
        previous=first,
        resolved_request=resolved,
        execution_case=case,
        next_attempt_ordinal=2,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    writer = AttemptEvidenceWriter(root=root)
    first_publication = writer.publish(first)
    second_publication = writer.publish(second)
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None
    finalized = (first_publication.finalized, second_publication.finalized)
    hashes = (
        ExecutionResultHasher.bind(ready_branch(first), finalized[0]),
        ExecutionResultHasher.bind(ready_branch(second), finalized[1]),
    )
    attempts = AttemptConsistencySet(resolved, hashes, finalized)
    attempts_directory = root / "runs" / resolved.semantic_run_id / "attempts"
    before = _directory_bytes(attempts_directory)
    input_hashes_before = _input_hashes(case, attempts)
    publication = CanonicalResultPublisher(root=root).publish(
        resolved_request=resolved,
        attempt_hashes=hashes,
        finalized_attempts=finalized,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    assert publication.finalized_evaluation is not None
    canonical = root / "runs" / resolved.semantic_run_id / "canonical"
    evaluation = root / publication.finalized_evaluation.relative_directory
    return G07MismatchJourney(
        attempts=attempts,
        publication=publication,
        canonical_directory=canonical,
        evaluation_directory=evaluation,
        input_hashes_before=input_hashes_before,
        input_hashes_after=_input_hashes(case, attempts),
        attempt_bytes_before=before,
        attempt_bytes_after=_directory_bytes(attempts_directory),
    )
