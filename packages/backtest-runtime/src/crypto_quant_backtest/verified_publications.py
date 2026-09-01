from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    ArtifactEnvelope,
    ArtifactRef,
    CurrencyId,
    Fill,
    PortfolioSnapshot,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleRef
from crypto_quant_trading import AccountingJournal

from .engine import (
    EngineExecutionResult,
    ExecutionTrace,
    ExecutionTraceEntry,
    ResolvedExecutionCase,
)
from .evidence import (
    EvidenceArtifactEntry,
    EvidenceManifest,
    FinalizedAttemptEvidence,
)
from .execution_hash import (
    AttemptExecutionHash,
    CanonicalExecutionSummary,
)
from .execution_inputs import _read_journal_entry
from .integrity import (
    EngineExecutionContext,
    FinalizedCanonicalResult,
    FinalizedCanonicalResultV2,
    IntegrityIssueCode,
    ResultGrade,
)
from .publication_refs import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
)
from .resolution import ResolvedBacktestRequest
from .runner import AttemptIdentity, ReadyToFinalizeAttempt

__all__ = [
    "TerminalStatus",
    "VerifiedCanonicalJournalEntryEvidenceV1",
    "VerifiedCanonicalJournalEvidenceV1",
    "VerifiedCompletedPublication",
    "VerifiedCompletedPublicationV2",
    "VerifiedCompletedPublicationV3",
    "VerifiedExecutionSummary",
    "VerifiedResearchCompletedPublicationV1",
    "VerifiedResearchExecutionSummaryV1",
    "VerifiedTerminalPublication",
]

_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")
_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_BASE_JOURNAL_ENTRY_FIELDS = frozenset(
    {
        "type",
        "journal_entry_id",
        "entry_type",
        "account_id",
        "venue_id",
        "effective_time",
        "recorded_at",
        "source_ids",
        "balance_changes",
        "realized_pnl",
        "fees",
        "financing",
    }
)
_DERIVATIVE_JOURNAL_ENTRY_FIELDS = frozenset(
    {
        "type",
        "schema_version",
        "component_ref",
        "request",
        "request_hash",
        "exact_realized_pnl",
        "journal_entry",
    }
)
_FUNDING_JOURNAL_ENTRY_FIELDS = frozenset(
    {
        "type",
        "schema_version",
        "component_ref",
        "request",
        "request_hash",
        "application_key",
        "settlement_id",
        "exact_cash_flow",
        "payment",
        "application_body_hash",
        "journal_entry",
    }
)
_JOURNAL_GENESIS_HASH = canonical_sha256(
    {"type": "accounting_journal_genesis", "schema_version": 1}
)


def _exact_mapping(
    name: str, value: object, fields: frozenset[str]
) -> dict[str, object]:
    if type(value) is not dict or not all(type(key) is str for key in value):
        raise TypeError(f"{name} must be an exact mapping")
    if set(value) != fields:
        raise ValueError(f"{name} fields do not match the verified schema")
    return value


def _decode_canonical_journal_entry_payload(
    payload: bytes,
) -> tuple[AccountingJournalEntry, str]:
    if type(payload) is not bytes:
        raise TypeError("canonical_payload must be exact bytes")
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("canonical_payload must contain canonical JSON") from error
    if canonical_bytes(raw) != payload:
        raise ValueError("canonical_payload bytes are not canonical")
    if type(raw) is not dict:
        raise TypeError("journal entry payload must be an exact mapping")

    entry_type = raw.get("type")
    outer: dict[str, object] | None = None
    if entry_type == "accounting_journal_entry":
        inner = _exact_mapping(
            "base accounting journal entry", raw, _BASE_JOURNAL_ENTRY_FIELDS
        )
        required_entry_type = None
    elif entry_type == "linear_derivative_journal_entry":
        outer = _exact_mapping(
            "linear derivative journal entry",
            raw,
            _DERIVATIVE_JOURNAL_ENTRY_FIELDS,
        )
        if type(outer["schema_version"]) is not int or outer["schema_version"] != 1:
            raise ValueError("linear derivative journal entry must use schema version 1")
        inner = _exact_mapping(
            "nested base accounting journal entry",
            outer["journal_entry"],
            _BASE_JOURNAL_ENTRY_FIELDS,
        )
        required_entry_type = AccountingEntryType.FILL_BOOKED
    elif entry_type == "linear_funding_journal_entry":
        outer = _exact_mapping(
            "linear funding journal entry", raw, _FUNDING_JOURNAL_ENTRY_FIELDS
        )
        if type(outer["schema_version"]) is not int or outer["schema_version"] != 2:
            raise ValueError("linear funding journal entry must use schema version 2")
        inner = _exact_mapping(
            "nested base accounting journal entry",
            outer["journal_entry"],
            _BASE_JOURNAL_ENTRY_FIELDS,
        )
        required_entry_type = AccountingEntryType.FUNDING_APPLIED
    else:
        raise ValueError("journal entry type/version is not evidence-allowlisted")

    if entry_type != "accounting_journal_entry":
        if outer is None:
            raise AssertionError("specialized journal entry requires outer payload")
        request = outer["request"]
        if type(request) is not dict:
            raise TypeError("journal entry request must be an exact mapping")
        request_hash = outer["request_hash"]
        if (
            type(request_hash) is not str
            or _HASH_PATTERN.fullmatch(request_hash) is None
            or request_hash != canonical_sha256(request)
        ):
            raise ValueError("journal entry request_hash does not bind raw request")

    journal_entry = _read_journal_entry(inner)
    if type(journal_entry) is not AccountingJournalEntry:
        raise TypeError("decoded journal_entry must be exact AccountingJournalEntry")
    if canonical_bytes(journal_entry) != canonical_bytes(inner):
        raise ValueError("nested journal_entry does not canonically bind the base entry")
    if required_entry_type is not None and journal_entry.entry_type is not required_entry_type:
        raise ValueError("specialized journal entry has the wrong base entry type")
    return journal_entry, canonical_sha256(raw)


def _next_journal_hash(previous_hash: str, entry_hash: str) -> str:
    return canonical_sha256(
        {
            "type": "accounting_journal_link",
            "schema_version": 1,
            "previous_hash": previous_hash,
            "entry_hash": entry_hash,
        }
    )


class TerminalStatus(str, Enum):
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class VerifiedCanonicalJournalEntryEvidenceV1:
    """Evidence-only view of one canonical allowlisted journal entry."""

    canonical_payload: bytes
    journal_entry: AccountingJournalEntry
    entry_hash: str

    def __post_init__(self) -> None:
        if type(self) is not VerifiedCanonicalJournalEntryEvidenceV1:
            raise TypeError("journal entry evidence must be exact")
        decoded, entry_hash = _decode_canonical_journal_entry_payload(
            self.canonical_payload
        )
        if type(self.journal_entry) is not AccountingJournalEntry:
            raise TypeError("journal_entry must be exact AccountingJournalEntry")
        if self.journal_entry != decoded:
            raise ValueError("journal_entry does not bind canonical_payload")
        if self.entry_hash != entry_hash:
            raise ValueError("entry_hash does not bind canonical_payload")

    @classmethod
    def from_canonical_payload(
        cls, payload: object
    ) -> VerifiedCanonicalJournalEntryEvidenceV1:
        canonical_payload = canonical_bytes(payload)
        journal_entry, entry_hash = _decode_canonical_journal_entry_payload(
            canonical_payload
        )
        return cls(canonical_payload, journal_entry, entry_hash)


@dataclass(frozen=True, slots=True)
class VerifiedCanonicalJournalEvidenceV1:
    """Evidence-only canonical journal; intentionally provides no replay API."""

    entries: tuple[VerifiedCanonicalJournalEntryEvidenceV1, ...]
    journal_hash: str

    def __post_init__(self) -> None:
        if type(self) is not VerifiedCanonicalJournalEvidenceV1:
            raise TypeError("journal evidence must be exact")
        if type(self.entries) is not tuple or not all(
            type(entry) is VerifiedCanonicalJournalEntryEvidenceV1
            for entry in self.entries
        ):
            raise TypeError("entries must contain exact verified journal evidence")
        if type(self.journal_hash) is not str or _HASH_PATTERN.fullmatch(
            self.journal_hash
        ) is None:
            raise ValueError("journal_hash must use sha256 schema")

        previous_key = None
        seen_ids: set[str] = set()
        computed_hash = _JOURNAL_GENESIS_HASH
        for entry in self.entries:
            entry.__post_init__()
            journal_entry = entry.journal_entry
            key = (journal_entry.recorded_at, journal_entry.journal_entry_id.value)
            if previous_key is not None and key <= previous_key:
                raise ValueError("journal entries must use strict stable order")
            previous_key = key
            journal_entry_id = journal_entry.journal_entry_id.value
            if journal_entry_id in seen_ids:
                raise ValueError("journal entry identities must be unique")
            seen_ids.add(journal_entry_id)
            computed_hash = _next_journal_hash(computed_hash, entry.entry_hash)
        if computed_hash != self.journal_hash:
            raise ValueError("journal_hash does not bind canonical entry chain")


@dataclass(frozen=True, slots=True)
class VerifiedResearchExecutionSummaryV1:
    fills: tuple[Fill, ...]
    final_journal: VerifiedCanonicalJournalEvidenceV1
    final_portfolio_snapshot: PortfolioSnapshot

    def __post_init__(self) -> None:
        if type(self) is not VerifiedResearchExecutionSummaryV1:
            raise TypeError("research execution summary must be exact")
        if type(self.fills) is not tuple or not all(
            type(fill) is Fill for fill in self.fills
        ):
            raise TypeError("fills must contain exact Fill values")
        if type(self.final_journal) is not VerifiedCanonicalJournalEvidenceV1:
            raise TypeError("final_journal must be exact verified journal evidence")
        if type(self.final_portfolio_snapshot) is not PortfolioSnapshot:
            raise TypeError("final_portfolio_snapshot must be exact PortfolioSnapshot")


@dataclass(frozen=True, slots=True)
class VerifiedResearchCompletedPublicationV1:
    """Analysis-ready V1 publication with evidence-only journal semantics."""

    source_publication_ref: BacktestCanonicalPublicationRef
    semantic_run_id: str
    source_execution_result_hash: str
    result_grade: ResultGrade
    reporting_currency: CurrencyId
    engine_context: EngineExecutionContext
    execution_summary: VerifiedResearchExecutionSummaryV1

    def __post_init__(self) -> None:
        if type(self) is not VerifiedResearchCompletedPublicationV1:
            raise TypeError("research completed publication must be exact")
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
        if type(self.execution_summary) is not VerifiedResearchExecutionSummaryV1:
            raise TypeError(
                "execution_summary must be exact VerifiedResearchExecutionSummaryV1"
            )
        if self.engine_context.semantic_run_id != self.semantic_run_id:
            raise ValueError("engine context semantic run mismatch")
        initial = self.engine_context.financial_state
        initial_entries = initial.journal.entries
        final_entries = self.execution_summary.final_journal.entries
        if len(final_entries) < len(initial_entries) or any(
            evidence.canonical_payload != canonical_bytes(entry)
            for evidence, entry in zip(
                final_entries[: len(initial_entries)], initial_entries, strict=True
            )
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
        engine_context = result.engine_context
        if type(engine_context) is not EngineExecutionContext:
            raise ValueError("finalized publication must preserve engine context")
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
            engine_context=engine_context,
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


@dataclass(frozen=True, slots=True)
class _VerifiedArtifactIdentity:
    """Exact immutable identity of one artifact read from the verified graph."""

    ref: ArtifactRef
    source_hash: str
    body_hash: str

    def __post_init__(self) -> None:
        if type(self) is not _VerifiedArtifactIdentity:
            raise TypeError("artifact identity must be exact _VerifiedArtifactIdentity")
        if type(self.ref) is not ArtifactRef:
            raise TypeError("artifact identity ref must be exact ArtifactRef")
        for name in ("source_hash", "body_hash"):
            value = getattr(self, name)
            if type(value) is not str or _HASH_PATTERN.fullmatch(value) is None:
                raise ValueError(f"artifact identity {name} must use sha256 schema")
        if self.body_hash != self.ref.content_hash:
            raise ValueError("artifact identity body hash must match ref content hash")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref,
            "source_hash": self.source_hash,
            "body_hash": self.body_hash,
        }


@dataclass(frozen=True, slots=True)
class _VerifiedIntegrityArtifactIdentity:
    """Exact integrity artifact identity and its projected decision fields."""

    artifact: _VerifiedArtifactIdentity
    context_hash: str
    result_grade: ResultGrade
    issue_codes: tuple[IntegrityIssueCode, ...]

    def __post_init__(self) -> None:
        if type(self) is not _VerifiedIntegrityArtifactIdentity:
            raise TypeError(
                "integrity identity must be exact _VerifiedIntegrityArtifactIdentity"
            )
        if type(self.artifact) is not _VerifiedArtifactIdentity:
            raise TypeError("integrity artifact must be exact _VerifiedArtifactIdentity")
        if (
            type(self.context_hash) is not str
            or _HASH_PATTERN.fullmatch(self.context_hash) is None
        ):
            raise ValueError("integrity context_hash must use sha256 schema")
        if type(self.result_grade) is not ResultGrade:
            raise TypeError("integrity result_grade must be exact ResultGrade")
        if type(self.issue_codes) is not tuple or not all(
            type(value) is IntegrityIssueCode for value in self.issue_codes
        ):
            raise TypeError("integrity issue_codes must contain exact values")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "artifact": self.artifact,
            "context_hash": self.context_hash,
            "result_grade": self.result_grade.value,
            "issue_codes": tuple(value.value for value in self.issue_codes),
        }


@dataclass(frozen=True, slots=True)
class _VerifiedCompletedEvidenceV3:
    """Typed projection of the verified static canonical-v3 graph."""

    completed: VerifiedCompletedPublicationV3
    resolved_request: ResolvedBacktestRequest
    ready_attempts: tuple[ReadyToFinalizeAttempt, ReadyToFinalizeAttempt]
    attempt_hashes: tuple[AttemptExecutionHash, AttemptExecutionHash]
    finalized_attempts: tuple[FinalizedAttemptEvidence, FinalizedAttemptEvidence]
    first_attempt: AttemptIdentity
    retry_attempt: AttemptIdentity
    canonical_root: _VerifiedArtifactIdentity
    canonical_attempt: _VerifiedArtifactIdentity
    integrity: _VerifiedIntegrityArtifactIdentity
    completed_result: _VerifiedArtifactIdentity
    rebuild_verification: _VerifiedArtifactIdentity
    proof_publication_manifest: _VerifiedArtifactIdentity
    evidence_manifests: tuple[_VerifiedArtifactIdentity, _VerifiedArtifactIdentity]
    accepted_market_bundle_ref: MarketBundleRef
    accepted_market_bundle_manifest_hash: str
    execution_result_hash: str
    execution_case_semantic_hash: str
    execution_case_hash: str
    trace_hash: str
    static_verification_hash: str

    def __post_init__(self) -> None:
        self._validate_self()

    @classmethod
    def create(
        cls,
        *,
        completed: VerifiedCompletedPublicationV3,
        resolved_request: ResolvedBacktestRequest,
        ready_attempts: tuple[ReadyToFinalizeAttempt, ReadyToFinalizeAttempt],
        attempt_hashes: tuple[AttemptExecutionHash, AttemptExecutionHash],
        finalized_attempts: tuple[FinalizedAttemptEvidence, FinalizedAttemptEvidence],
        first_attempt: AttemptIdentity,
        retry_attempt: AttemptIdentity,
        canonical_root: _VerifiedArtifactIdentity,
        canonical_attempt: _VerifiedArtifactIdentity,
        integrity: _VerifiedIntegrityArtifactIdentity,
        completed_result: _VerifiedArtifactIdentity,
        rebuild_verification: _VerifiedArtifactIdentity,
        proof_publication_manifest: _VerifiedArtifactIdentity,
        evidence_manifests: tuple[_VerifiedArtifactIdentity, _VerifiedArtifactIdentity],
        accepted_market_bundle_ref: MarketBundleRef,
        accepted_market_bundle_manifest_hash: str,
        execution_result_hash: str,
        execution_case_semantic_hash: str,
        execution_case_hash: str,
        trace_hash: str,
    ) -> _VerifiedCompletedEvidenceV3:
        values = {
            "completed": completed,
            "resolved_request": resolved_request,
            "ready_attempts": ready_attempts,
            "attempt_hashes": attempt_hashes,
            "finalized_attempts": finalized_attempts,
            "first_attempt": first_attempt,
            "retry_attempt": retry_attempt,
            "canonical_root": canonical_root,
            "canonical_attempt": canonical_attempt,
            "integrity": integrity,
            "completed_result": completed_result,
            "rebuild_verification": rebuild_verification,
            "proof_publication_manifest": proof_publication_manifest,
            "evidence_manifests": evidence_manifests,
            "accepted_market_bundle_ref": accepted_market_bundle_ref,
            "accepted_market_bundle_manifest_hash": (
                accepted_market_bundle_manifest_hash
            ),
            "execution_result_hash": execution_result_hash,
            "execution_case_semantic_hash": execution_case_semantic_hash,
            "execution_case_hash": execution_case_hash,
            "trace_hash": trace_hash,
        }
        return cls(**values, static_verification_hash=canonical_sha256(cls._body(values)))

    @staticmethod
    def _completed_body(
        completed: VerifiedCompletedPublicationV3,
    ) -> dict[str, object]:
        return {
            "source_publication_ref": completed.source_publication_ref,
            "semantic_run_id": completed.semantic_run_id,
            "source_execution_result_hash": completed.source_execution_result_hash,
            "result_grade": completed.result_grade.value,
            "reporting_currency": completed.reporting_currency,
            "engine_context": completed.engine_context,
            "execution_summary": {
                "fills": completed.execution_summary.fills,
                "final_journal": completed.execution_summary.final_journal,
                "final_portfolio_snapshot": (
                    completed.execution_summary.final_portfolio_snapshot
                ),
            },
            "rebuild_verification_ref": completed.rebuild_verification_ref,
            "proof_publication_manifest_ref": (
                completed.proof_publication_manifest_ref
            ),
        }

    @classmethod
    def _body(cls, values: dict[str, object]) -> dict[str, object]:
        completed = values["completed"]
        if type(completed) is not VerifiedCompletedPublicationV3:
            raise TypeError("completed must be exact VerifiedCompletedPublicationV3")
        return {
            "type": "verified_completed_evidence_v3",
            "schema_version": 1,
            **values,
            "completed": cls._completed_body(completed),
        }

    def _values(self) -> dict[str, object]:
        return {
            "completed": self.completed,
            "resolved_request": self.resolved_request,
            "ready_attempts": self.ready_attempts,
            "attempt_hashes": self.attempt_hashes,
            "finalized_attempts": self.finalized_attempts,
            "first_attempt": self.first_attempt,
            "retry_attempt": self.retry_attempt,
            "canonical_root": self.canonical_root,
            "canonical_attempt": self.canonical_attempt,
            "integrity": self.integrity,
            "completed_result": self.completed_result,
            "rebuild_verification": self.rebuild_verification,
            "proof_publication_manifest": self.proof_publication_manifest,
            "evidence_manifests": self.evidence_manifests,
            "accepted_market_bundle_ref": self.accepted_market_bundle_ref,
            "accepted_market_bundle_manifest_hash": (
                self.accepted_market_bundle_manifest_hash
            ),
            "execution_result_hash": self.execution_result_hash,
            "execution_case_semantic_hash": self.execution_case_semantic_hash,
            "execution_case_hash": self.execution_case_hash,
            "trace_hash": self.trace_hash,
        }

    @staticmethod
    def _validate_artifact(
        name: str,
        identity: object,
        artifact_type: str,
        schema_version: int,
    ) -> None:
        if type(identity) is not _VerifiedArtifactIdentity:
            raise TypeError(f"{name} must be exact _VerifiedArtifactIdentity")
        identity.__post_init__()
        if (
            identity.ref.artifact_type != artifact_type
            or identity.ref.schema_version != schema_version
        ):
            raise ValueError(f"{name} must target {artifact_type}@{schema_version}")

    @staticmethod
    def _validate_trace(trace: object) -> None:
        if type(trace) is not ExecutionTrace:
            raise TypeError("Attempt trace must be exact ExecutionTrace")
        if type(trace.entries) is not tuple or not all(
            type(entry) is ExecutionTraceEntry for entry in trace.entries
        ):
            raise TypeError("Attempt trace entries must be exact ExecutionTraceEntry")
        for entry in trace.entries:
            entry.__post_init__()
        trace.__post_init__()

    def _validate_self(self) -> None:
        if type(self) is not _VerifiedCompletedEvidenceV3:
            raise TypeError("completed evidence must be exact _VerifiedCompletedEvidenceV3")
        if type(self.completed) is not VerifiedCompletedPublicationV3:
            raise TypeError("completed must be exact VerifiedCompletedPublicationV3")
        if type(self.resolved_request) is not ResolvedBacktestRequest:
            raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
        for name, values, expected_type in (
            ("ready_attempts", self.ready_attempts, ReadyToFinalizeAttempt),
            ("attempt_hashes", self.attempt_hashes, AttemptExecutionHash),
            ("finalized_attempts", self.finalized_attempts, FinalizedAttemptEvidence),
            ("evidence_manifests", self.evidence_manifests, _VerifiedArtifactIdentity),
        ):
            if (
                type(values) is not tuple
                or len(values) != 2
                or not all(type(value) is expected_type for value in values)
            ):
                raise TypeError(f"{name} must contain exactly two exact values")
        if type(self.first_attempt) is not AttemptIdentity:
            raise TypeError("first_attempt must be exact AttemptIdentity")
        if type(self.retry_attempt) is not AttemptIdentity:
            raise TypeError("retry_attempt must be exact AttemptIdentity")
        if type(self.integrity) is not _VerifiedIntegrityArtifactIdentity:
            raise TypeError("integrity must be exact _VerifiedIntegrityArtifactIdentity")
        self.integrity.__post_init__()
        if type(self.accepted_market_bundle_ref) is not MarketBundleRef:
            raise TypeError("accepted_market_bundle_ref must be exact MarketBundleRef")
        for name in (
            "accepted_market_bundle_manifest_hash",
            "execution_result_hash",
            "execution_case_semantic_hash",
            "execution_case_hash",
            "trace_hash",
            "static_verification_hash",
        ):
            value = getattr(self, name)
            if type(value) is not str or _HASH_PATTERN.fullmatch(value) is None:
                raise ValueError(f"{name} must use sha256 schema")

        for name, identity, artifact_type, schema_version in (
            (
                "canonical_root",
                self.canonical_root,
                "canonical_publication_manifest",
                2,
            ),
            (
                "canonical_attempt",
                self.canonical_attempt,
                "canonical_attempt_ref",
                2,
            ),
            ("integrity", self.integrity.artifact, "integrity_report", 2),
            (
                "completed_result",
                self.completed_result,
                "completed_backtest_result",
                3,
            ),
            (
                "rebuild_verification",
                self.rebuild_verification,
                "deterministic_rebuild_verification",
                1,
            ),
            (
                "proof_publication_manifest",
                self.proof_publication_manifest,
                "deterministic_rebuild_verification_publication_manifest",
                1,
            ),
        ):
            self._validate_artifact(name, identity, artifact_type, schema_version)
        for identity in self.evidence_manifests:
            self._validate_artifact("evidence_manifest", identity, "evidence_manifest", 1)

        first = AttemptIdentity.first(self.completed.semantic_run_id)
        retry = AttemptIdentity.retry(first, next_ordinal=2)
        expected_attempts = (first, retry)
        if (self.first_attempt, self.retry_attempt) != expected_attempts:
            raise ValueError("first/retry Attempts are not canonical")
        if (
            tuple(value.attempt for value in self.ready_attempts) != expected_attempts
            or tuple(value.attempt for value in self.attempt_hashes)
            != expected_attempts
            or tuple(value.attempt for value in self.finalized_attempts)
            != expected_attempts
        ):
            raise ValueError("Attempt evidence must use canonical first/retry order")

        for ready, attempt_hash, finalized, evidence_identity in zip(
            self.ready_attempts,
            self.attempt_hashes,
            self.finalized_attempts,
            self.evidence_manifests,
            strict=True,
        ):
            if type(ready.resolved_request) is not ResolvedBacktestRequest:
                raise TypeError("Attempt resolved request must be exact")
            if type(ready.engine_result) is not EngineExecutionResult:
                raise TypeError("Attempt engine result must be exact")
            if type(attempt_hash.engine_result) is not EngineExecutionResult:
                raise TypeError("execution hash engine result must be exact")
            if type(attempt_hash.summary) is not CanonicalExecutionSummary:
                raise TypeError("execution hash summary must be exact")
            self._validate_trace(ready.engine_result.trace)
            self._validate_trace(attempt_hash.engine_result.trace)
            if type(finalized.manifest) is not EvidenceManifest:
                raise TypeError("finalized manifest must be exact EvidenceManifest")
            if (
                type(finalized.manifest.artifacts) is not tuple
                or not all(
                    type(value) is EvidenceArtifactEntry
                    for value in finalized.manifest.artifacts
                )
            ):
                raise TypeError("finalized manifest artifacts must be exact")
            if finalized.status.value != "READY_FOR_INTEGRITY":
                raise ValueError("finalized Attempt must be ready for integrity")
            if ready.resolved_request != self.resolved_request:
                raise ValueError("Attempt resolved roots mismatch")
            if evidence_identity.source_hash != finalized.manifest_source_hash:
                raise ValueError("evidence manifest source identity mismatch")

        first_hash, retry_hash = self.attempt_hashes
        engines = (first_hash.engine_result, retry_hash.engine_result)
        if self.resolved_request.semantic_run_id != self.completed.semantic_run_id:
            raise ValueError("completed semantic run mismatch")
        if self.canonical_root.ref != self.completed.source_publication_ref.artifact_ref:
            raise ValueError("completed root publication identity mismatch")
        if self.rebuild_verification.ref != self.completed.rebuild_verification_ref:
            raise ValueError("completed rebuild verification identity mismatch")
        if (
            self.proof_publication_manifest.ref
            != self.completed.proof_publication_manifest_ref
        ):
            raise ValueError("completed proof manifest identity mismatch")
        if (
            self.accepted_market_bundle_ref
            != self.resolved_request.request.market_bundle_ref
            or self.accepted_market_bundle_ref
            != self.resolved_request.environment.market_bundle_ref
            or self.accepted_market_bundle_manifest_hash
            != self.accepted_market_bundle_ref.manifest_hash
        ):
            raise ValueError("accepted market Bundle identity mismatch")
        if (
            self.execution_result_hash != self.completed.source_execution_result_hash
            or any(
                value.execution_result_hash != self.execution_result_hash
                for value in self.attempt_hashes
            )
        ):
            raise ValueError("completed execution result hash mismatch")
        if (
            self.execution_case_semantic_hash
            != self.resolved_request.request.execution_case_semantic_hash
            or self.execution_case_semantic_hash
            != self.completed.engine_context.semantic_spec_hash
        ):
            raise ValueError("completed execution semantic hash mismatch")
        if (
            self.execution_case_hash != self.completed.engine_context.case_hash
            or any(engine.case_hash != self.execution_case_hash for engine in engines)
            or any(
                value.execution_case_hash != self.execution_case_hash
                for value in self.ready_attempts
            )
        ):
            raise ValueError("completed execution case hash mismatch")
        if any(engine.trace.trace_hash != self.trace_hash for engine in engines):
            raise ValueError("completed trace hash mismatch")
        first_engine = engines[0]
        if self.completed.execution_summary != VerifiedExecutionSummary(
            first_engine.fills,
            first_engine.final_journal,
            first_engine.final_portfolio_snapshot,
        ):
            raise ValueError("completed execution summary mismatch")
        if (
            self.completed.reporting_currency
            != self.resolved_request.request.reporting_currency
            or self.completed.engine_context.target_stream_digest
            != first_engine.target_stream_digest
            or self.integrity.result_grade is not self.completed.result_grade
        ):
            raise ValueError("completed result/context mismatch")
        if canonical_sha256(self._body(self._values())) != self.static_verification_hash:
            raise ValueError("static_verification_hash does not bind canonical body")

    @property
    def first_trace(self) -> ExecutionTrace:
        self._validate_self()
        return self.attempt_hashes[0].engine_result.trace

    @property
    def first_engine_result(self) -> EngineExecutionResult:
        self._validate_self()
        return self.attempt_hashes[0].engine_result

    @property
    def market_bundle_ref(self) -> MarketBundleRef:
        self._validate_self()
        return self.accepted_market_bundle_ref

    def to_canonical_dict(self) -> dict[str, object]:
        self._validate_self()
        return {
            **self._body(self._values()),
            "static_verification_hash": self.static_verification_hash,
        }
