from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    CurrencyId,
    Fill,
    PortfolioSnapshot,
)
from crypto_quant_trading import AccountingJournal

from .engine import ResolvedExecutionCase
from .execution_hash import CanonicalExecutionSummary
from .integrity import (
    EngineExecutionContext,
    FinalizedCanonicalResult,
    FinalizedCanonicalResultV2,
    ResultGrade,
)
from .publication_refs import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
)

__all__ = [
    "TerminalStatus",
    "VerifiedCompletedPublication",
    "VerifiedCompletedPublicationV2",
    "VerifiedCompletedPublicationV3",
    "VerifiedExecutionSummary",
    "VerifiedTerminalPublication",
]

_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")
_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


class TerminalStatus(str, Enum):
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class VerifiedTerminalPublication:
    """Verified TERMINAL publication view."""

    status: TerminalStatus
    durable_evidence_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.status) is not TerminalStatus:
            raise TypeError("status must be exact TerminalStatus")
        if type(self.durable_evidence_ref) is not ArtifactRef:
            raise TypeError("durable_evidence_ref must be exact ArtifactRef")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "durable_evidence_ref": self.durable_evidence_ref,
        }


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


@dataclass(frozen=True, slots=True)
class VerifiedExecutionSummary:
    fills: tuple[Fill, ...]
    final_journal: AccountingJournal
    final_portfolio_snapshot: PortfolioSnapshot

    def __post_init__(self) -> None:
        if type(self.fills) is not tuple or not all(
            type(value) is Fill for value in self.fills
        ):
            raise TypeError("fills must contain exact Fill values")
        if type(self.final_journal) is not AccountingJournal:
            raise TypeError("final_journal must be exact AccountingJournal")
        if type(self.final_portfolio_snapshot) is not PortfolioSnapshot:
            raise TypeError(
                "final_portfolio_snapshot must be exact PortfolioSnapshot"
            )


@dataclass(frozen=True, slots=True)
class VerifiedCompletedPublicationV2:
    """Lean verified view of one analysis-ready v2 COMPLETED publication."""

    source_publication_ref: BacktestCanonicalPublicationRef
    semantic_run_id: str
    source_execution_result_hash: str
    result_grade: ResultGrade
    reporting_currency: CurrencyId
    engine_context: EngineExecutionContext
    execution_summary: VerifiedExecutionSummary

    def __post_init__(self) -> None:
        if type(self.source_publication_ref) is not BacktestCanonicalPublicationRef:
            raise TypeError(
                "source_publication_ref must be exact BacktestCanonicalPublicationRef"
            )
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if (
            type(self.source_execution_result_hash) is not str
            or _HASH_PATTERN.fullmatch(self.source_execution_result_hash) is None
        ):
            raise ValueError("source_execution_result_hash must use sha256 schema")
        if type(self.result_grade) is not ResultGrade:
            raise TypeError("result_grade must be exact ResultGrade")
        if type(self.reporting_currency) is not CurrencyId:
            raise TypeError("reporting_currency must be exact CurrencyId")
        if type(self.engine_context) is not EngineExecutionContext:
            raise TypeError("engine_context must be exact EngineExecutionContext")
        if type(self.execution_summary) is not VerifiedExecutionSummary:
            raise TypeError(
                "execution_summary must be exact VerifiedExecutionSummary"
            )
        if self.engine_context.semantic_run_id != self.semantic_run_id:
            raise ValueError("engine context semantic run mismatch")

        initial = self.engine_context.financial_state
        final_journal = self.execution_summary.final_journal
        if final_journal.entries[: len(initial.journal.entries)] != (
            initial.journal.entries
        ):
            raise ValueError("completed Journal does not preserve the run-start prefix")
        starting = initial.initial_snapshot
        ending = self.execution_summary.final_portfolio_snapshot
        if (
            starting.account_id != ending.account_id
            or starting.reporting_currency != ending.reporting_currency
            or starting.reporting_currency != self.reporting_currency
        ):
            raise ValueError("run-boundary PortfolioSnapshot context mismatch")

    @classmethod
    def from_finalized(
        cls, publication: FinalizedCanonicalResultV2
    ) -> VerifiedCompletedPublicationV2:
        if type(publication) is not FinalizedCanonicalResultV2:
            raise TypeError("publication must be exact FinalizedCanonicalResultV2")
        result = publication.result
        summary = result.context.attempts.canonical_attempt.summary
        manifest_envelope = ArtifactEnvelope.create(
            "canonical_publication_manifest", 1, publication.manifest
        )
        return cls(
            source_publication_ref=BacktestCanonicalPublicationRef.from_artifact_ref(
                ArtifactRef.from_envelope(manifest_envelope)
            ),
            semantic_run_id=result.semantic_run_id,
            source_execution_result_hash=result.execution_result_hash,
            result_grade=result.result_grade,
            reporting_currency=result.context.resolved_request.request.reporting_currency,
            engine_context=result.engine_context,
            execution_summary=VerifiedExecutionSummary(
                fills=summary.fills,
                final_journal=summary.final_journal,
                final_portfolio_snapshot=summary.final_portfolio_snapshot,
            ),
        )

    @property
    def starting_snapshot(self) -> PortfolioSnapshot:
        return self.engine_context.financial_state.initial_snapshot

    @property
    def initial_journal_entry_count(self) -> int:
        return len(self.engine_context.financial_state.journal.entries)


@dataclass(frozen=True, slots=True)
class VerifiedCompletedPublicationV3:
    """Lean verified view of one analysis-ready canonical-v3 publication."""

    source_publication_ref: BacktestCanonicalPublicationRefV2
    semantic_run_id: str
    source_execution_result_hash: str
    result_grade: ResultGrade
    reporting_currency: CurrencyId
    engine_context: EngineExecutionContext
    execution_summary: VerifiedExecutionSummary
    rebuild_verification_ref: ArtifactRef
    proof_publication_manifest_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.source_publication_ref) is not BacktestCanonicalPublicationRefV2:
            raise TypeError(
                "source_publication_ref must be exact BacktestCanonicalPublicationRefV2"
            )
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if (
            type(self.source_execution_result_hash) is not str
            or _HASH_PATTERN.fullmatch(self.source_execution_result_hash) is None
        ):
            raise ValueError("source_execution_result_hash must use sha256 schema")
        if type(self.result_grade) is not ResultGrade:
            raise TypeError("result_grade must be exact ResultGrade")
        if self.result_grade is not ResultGrade.DECISION_GRADE:
            raise ValueError("canonical-v3 result_grade must be decision_grade")
        if type(self.reporting_currency) is not CurrencyId:
            raise TypeError("reporting_currency must be exact CurrencyId")
        if type(self.engine_context) is not EngineExecutionContext:
            raise TypeError("engine_context must be exact EngineExecutionContext")
        if type(self.execution_summary) is not VerifiedExecutionSummary:
            raise TypeError(
                "execution_summary must be exact VerifiedExecutionSummary"
            )
        for name, ref, artifact_type in (
            (
                "rebuild_verification_ref",
                self.rebuild_verification_ref,
                "deterministic_rebuild_verification",
            ),
            (
                "proof_publication_manifest_ref",
                self.proof_publication_manifest_ref,
                "deterministic_rebuild_verification_publication_manifest",
            ),
        ):
            if (
                type(ref) is not ArtifactRef
                or ref.artifact_type != artifact_type
                or ref.schema_version != 1
            ):
                raise ValueError(f"{name} must target {artifact_type}@1")
        if self.engine_context.semantic_run_id != self.semantic_run_id:
            raise ValueError("engine context semantic run mismatch")

        initial = self.engine_context.financial_state
        final_journal = self.execution_summary.final_journal
        if final_journal.entries[: len(initial.journal.entries)] != (
            initial.journal.entries
        ):
            raise ValueError("completed Journal does not preserve the run-start prefix")
        starting = initial.initial_snapshot
        ending = self.execution_summary.final_portfolio_snapshot
        if (
            starting.account_id != ending.account_id
            or starting.reporting_currency != ending.reporting_currency
            or starting.reporting_currency != self.reporting_currency
        ):
            raise ValueError("run-boundary PortfolioSnapshot context mismatch")

    @property
    def starting_snapshot(self) -> PortfolioSnapshot:
        return self.engine_context.financial_state.initial_snapshot

    @property
    def initial_journal_entry_count(self) -> int:
        return len(self.engine_context.financial_state.journal.entries)
