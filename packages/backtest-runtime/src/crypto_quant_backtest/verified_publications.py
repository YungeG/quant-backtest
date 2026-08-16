from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, PortfolioSnapshot

from .engine import ResolvedExecutionCase
from .execution_hash import CanonicalExecutionSummary
from .integrity import FinalizedCanonicalResult, ResultGrade
from .publication_refs import BacktestCanonicalPublicationRef

__all__ = ["VerifiedCompletedPublication"]


@dataclass(frozen=True, slots=True)
class VerifiedCompletedPublication:
    """Verified COMPLETED publication plus its already-bound execution evidence."""

    publication: FinalizedCanonicalResult
    execution_case: ResolvedExecutionCase

    def __post_init__(self) -> None:
        if type(self.publication) is not FinalizedCanonicalResult:
            raise TypeError("publication must be exact FinalizedCanonicalResult")
        if type(self.execution_case) is not ResolvedExecutionCase:
            raise TypeError("execution_case must be exact ResolvedExecutionCase")

        result = self.publication.result
        attempt = result.context.attempts.canonical_attempt
        engine_result = attempt.engine_result
        request = result.context.resolved_request.request
        if self.execution_case.case_hash != engine_result.case_hash:
            raise ValueError("execution_case does not bind completed execution result")
        if (
            self.execution_case.semantic_spec_hash
            != request.execution_case_semantic_hash
        ):
            raise ValueError("execution_case does not bind completed request semantics")
        if self.execution_case.target_stream.target_stream_digest != (
            engine_result.target_stream_digest
        ):
            raise ValueError("execution_case target stream does not bind execution result")
        if self.execution_case.target_stream.target_stream_digest != (
            request.target_stream_digest
        ):
            raise ValueError("execution_case target stream does not bind completed request")
        if not self.execution_case.verify_identity_manifest(result.semantic_run_id):
            raise ValueError("execution_case identity manifest is not verified")

        initial = self.execution_case.financial_state
        if engine_result.final_journal.entries[: len(initial.journal.entries)] != (
            initial.journal.entries
        ):
            raise ValueError("completed Journal does not preserve the run-start prefix")
        starting = initial.initial_snapshot
        ending = engine_result.final_portfolio_snapshot
        if (
            starting.account_id != ending.account_id
            or starting.reporting_currency != ending.reporting_currency
            or starting.reporting_currency != request.reporting_currency
        ):
            raise ValueError("run-boundary PortfolioSnapshot context mismatch")

    @property
    def source_publication_ref(self) -> BacktestCanonicalPublicationRef:
        envelope = ArtifactEnvelope.create(
            "canonical_publication_manifest", 1, self.publication.manifest
        )
        return BacktestCanonicalPublicationRef.from_artifact_ref(
            ArtifactRef.from_envelope(envelope)
        )

    @property
    def execution_summary(self) -> CanonicalExecutionSummary:
        return self.publication.result.context.attempts.canonical_attempt.summary

    @property
    def starting_snapshot(self) -> PortfolioSnapshot:
        return self.execution_case.financial_state.initial_snapshot

    @property
    def initial_journal_entry_count(self) -> int:
        return len(self.execution_case.financial_state.journal.entries)

    @property
    def source_execution_result_hash(self) -> str:
        return self.publication.result.execution_result_hash

    @property
    def result_grade(self) -> ResultGrade:
        return self.publication.result.result_grade
