"""Deterministic Integrity evaluation for finalized backtest Attempts."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    ArtifactSchemaRegistration,
    CanonicalSchema,
    SchemaCatalog,
    canonical_bytes,
    canonical_sha256,
)

from ._publication import (
    RunPublicationLock,
    canonical_hash as _hash,
    canonical_text as _text,
    ensure_directory,
    force_remove,
    fsync_directory,
    hide_and_remove,
    optional_canonical_hash as _optional_hash,
    prepare_read_only_directory,
    verify_read_only,
    write_file,
)
from .engine import ResolvedFinancialState
from .evidence import (
    AttemptEvidenceWriter,
    EvidenceArtifactRole,
    EvidencePublicationStatus,
    FinalizedAttemptEvidence,
)
from .execution_hash import (
    AttemptExecutionHash,
    ExecutionHashCheck,
    ExecutionHashMismatch,
    ExecutionResultHasher,
)
from .resolution import RequestedResultGrade, ResolvedBacktestRequest
from .runner import AttemptIdentity, BacktestRunOutcome


_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")


class IntegrityIssueSeverity(str, Enum):
    BLOCKING = "blocking"
    LIMITATION = "limitation"


class IntegrityIssueCode(str, Enum):
    INSUFFICIENT_ATTEMPTS = "insufficient_attempts"
    EXECUTION_HASH_MISMATCH = "execution_hash_mismatch"
    DEVELOPMENT_PROFILE = "development_profile"
    DEVELOPMENT_BUILD = "development_build"
    ENVIRONMENT_LIMITATION = "environment_limitation"
    SUMMARY_TRACE = "summary_trace"
    BUNDLE_RETENTION_UNPROVEN = "bundle_retention_unproven"
    DETERMINISTIC_REBUILD_UNPROVEN = "deterministic_rebuild_unproven"


class IntegrityTraceLevel(str, Enum):
    SUMMARY = "summary"
    FULL_TRACE = "full_trace"
    MICROSTRUCTURE_TRACE = "microstructure_trace"


class ResultGrade(str, Enum):
    DEVELOPMENT = "development"
    DECISION_GRADE = "decision_grade"


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    code: IntegrityIssueCode
    severity: IntegrityIssueSeverity
    subject_keys: tuple[str, ...]
    evidence_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, IntegrityIssueCode):
            raise TypeError("code must be IntegrityIssueCode")
        if not isinstance(self.severity, IntegrityIssueSeverity):
            raise TypeError("severity must be IntegrityIssueSeverity")
        if type(self.subject_keys) is not tuple or not self.subject_keys:
            raise ValueError("subject_keys must be a nonempty tuple")
        subjects = tuple(sorted({_text("subject_key", value) for value in self.subject_keys}))
        if len(subjects) != len(self.subject_keys):
            raise ValueError("subject_keys must be unique")
        object.__setattr__(self, "subject_keys", subjects)
        if type(self.evidence_hashes) is not tuple:
            raise TypeError("evidence_hashes must be tuple")
        hashes = tuple(sorted({_hash("evidence_hash", value) for value in self.evidence_hashes}))
        if len(hashes) != len(self.evidence_hashes):
            raise ValueError("evidence_hashes must be unique")
        object.__setattr__(self, "evidence_hashes", hashes)

    @property
    def issue_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "subject_keys": self.subject_keys,
            "evidence_hashes": self.evidence_hashes,
        }


def _validate_execution_evidence_binding(
    attempt_hash: AttemptExecutionHash,
    finalized: FinalizedAttemptEvidence,
) -> None:
    entries = tuple(
        entry
        for entry in finalized.manifest.artifacts
        if entry.role is EvidenceArtifactRole.ENGINE_EXECUTION_RESULT
    )
    if len(entries) != 1:
        raise ValueError("finalized evidence must contain one Engine result")
    entry = entries[0]
    expected_content_hash = ArtifactEnvelope.create(
        "engine_execution_result",
        1,
        attempt_hash.engine_result,
    ).content_hash
    if (
        entry.relative_path != "engine-execution-result.json"
        or entry.artifact_type != "engine_execution_result"
        or entry.schema_version != 1
        or entry.content_hash != attempt_hash.engine_result_artifact_content_hash
        or entry.content_hash != expected_content_hash
    ):
        raise ValueError("Attempt execution hash does not bind finalized evidence")


@dataclass(frozen=True, slots=True)
class AttemptConsistencySet:
    resolved_request: ResolvedBacktestRequest
    attempt_hashes: tuple[AttemptExecutionHash, ...]
    finalized_attempts: tuple[FinalizedAttemptEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        if type(self.attempt_hashes) is not tuple or not self.attempt_hashes:
            raise ValueError("attempt_hashes must be a nonempty tuple")
        if not all(isinstance(value, AttemptExecutionHash) for value in self.attempt_hashes):
            raise TypeError("attempt_hashes must contain AttemptExecutionHash")
        if type(self.finalized_attempts) is not tuple or not self.finalized_attempts:
            raise ValueError("finalized_attempts must be a nonempty tuple")
        if not all(
            isinstance(value, FinalizedAttemptEvidence)
            for value in self.finalized_attempts
        ):
            raise TypeError("finalized_attempts must contain FinalizedAttemptEvidence")
        hashes = tuple(
            sorted(
                self.attempt_hashes,
                key=lambda value: (
                    value.attempt.ordinal,
                    value.attempt.attempt_id,
                ),
            )
        )
        finalized = tuple(
            sorted(
                self.finalized_attempts,
                key=lambda value: (
                    value.attempt.ordinal,
                    value.attempt.attempt_id,
                ),
            )
        )
        if len({value.attempt.attempt_id for value in hashes}) != len(hashes):
            raise ValueError("Attempt hashes must be unique")
        if len({value.attempt.attempt_id for value in finalized}) != len(finalized):
            raise ValueError("finalized Attempts must be unique")
        by_attempt = {value.attempt.attempt_id: value for value in finalized}
        if {value.attempt.attempt_id for value in hashes} != set(by_attempt):
            raise ValueError("Attempt hashes and finalized evidence must exact-cover")
        for value in hashes:
            evidence = by_attempt[value.attempt.attempt_id]
            if value.attempt.semantic_run_id != self.resolved_request.semantic_run_id:
                raise ValueError("Attempt hash semantic run mismatch")
            if evidence.status is not EvidencePublicationStatus.READY_FOR_INTEGRITY:
                raise ValueError("Attempt evidence is not READY_FOR_INTEGRITY")
            if value.evidence_manifest_hash != evidence.manifest.manifest_hash:
                raise ValueError("Attempt hash evidence manifest mismatch")
            _validate_execution_evidence_binding(value, evidence)
        object.__setattr__(self, "attempt_hashes", hashes)
        object.__setattr__(self, "finalized_attempts", finalized)

    @property
    def semantic_run_id(self) -> str:
        return self.resolved_request.semantic_run_id

    @property
    def canonical_attempt(self) -> AttemptExecutionHash:
        return self.attempt_hashes[0]

    @property
    def canonical_evidence(self) -> FinalizedAttemptEvidence:
        attempt_id = self.canonical_attempt.attempt.attempt_id
        return next(
            value
            for value in self.finalized_attempts
            if value.attempt.attempt_id == attempt_id
        )

    @property
    def consistency_set_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "attempt_consistency_set",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "resolved_request_hash": canonical_sha256(self.resolved_request),
            "attempts": tuple(value.to_ref() for value in self.attempt_hashes),
            "finalized_evidence_hashes": tuple(
                value.publication_hash for value in self.finalized_attempts
            ),
        }


@dataclass(frozen=True, slots=True)
class DeterministicRebuildEvidence:
    semantic_run_id: str
    request_hash: str
    environment_hash: str
    build_artifact_manifest_hash: str
    market_bundle_manifest_hash: str
    market_bundle_retention_proof_hash: str | None
    target_stream_digest: str
    execution_case_semantic_hash: str
    execution_case_hash: str
    trace_hash: str
    trace_level: IntegrityTraceLevel
    execution_result_hash: str
    deterministic_rebuild_proof_hash: str | None

    def __post_init__(self) -> None:
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        for name in (
            "request_hash",
            "environment_hash",
            "build_artifact_manifest_hash",
            "market_bundle_manifest_hash",
            "target_stream_digest",
            "execution_case_semantic_hash",
            "execution_case_hash",
            "trace_hash",
            "execution_result_hash",
        ):
            _hash(name, getattr(self, name))
        _optional_hash(
            "market_bundle_retention_proof_hash",
            self.market_bundle_retention_proof_hash,
        )
        _optional_hash(
            "deterministic_rebuild_proof_hash",
            self.deterministic_rebuild_proof_hash,
        )
        if not isinstance(self.trace_level, IntegrityTraceLevel):
            raise TypeError("trace_level must be IntegrityTraceLevel")

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "deterministic_rebuild_evidence",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "request_hash": self.request_hash,
            "environment_hash": self.environment_hash,
            "build_artifact_manifest_hash": self.build_artifact_manifest_hash,
            "market_bundle_manifest_hash": self.market_bundle_manifest_hash,
            "market_bundle_retention_proof_hash": self.market_bundle_retention_proof_hash,
            "target_stream_digest": self.target_stream_digest,
            "execution_case_semantic_hash": self.execution_case_semantic_hash,
            "execution_case_hash": self.execution_case_hash,
            "trace_hash": self.trace_hash,
            "trace_level": self.trace_level.value,
            "execution_result_hash": self.execution_result_hash,
            "deterministic_rebuild_proof_hash": self.deterministic_rebuild_proof_hash,
        }


@dataclass(frozen=True, slots=True)
class CanonicalAttemptRef:
    attempt: AttemptIdentity
    evidence_manifest_hash: str
    evidence_manifest_source_hash: str
    evidence_publication_hash: str
    engine_result_artifact_content_hash: str
    consistency_set_hash: str
    execution_result_hash: str
    execution_case_semantic_hash: str
    execution_case_hash: str
    trace_hash: str
    trace_level: IntegrityTraceLevel
    market_bundle_manifest_hash: str
    market_bundle_retention_proof_hash: str | None
    deterministic_rebuild_evidence_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, AttemptIdentity):
            raise TypeError("attempt must be AttemptIdentity")
        for name in (
            "evidence_manifest_hash",
            "evidence_manifest_source_hash",
            "evidence_publication_hash",
            "engine_result_artifact_content_hash",
            "consistency_set_hash",
            "execution_result_hash",
            "execution_case_semantic_hash",
            "execution_case_hash",
            "trace_hash",
            "market_bundle_manifest_hash",
            "deterministic_rebuild_evidence_hash",
        ):
            _hash(name, getattr(self, name))
        _optional_hash(
            "market_bundle_retention_proof_hash",
            self.market_bundle_retention_proof_hash,
        )
        if not isinstance(self.trace_level, IntegrityTraceLevel):
            raise TypeError("trace_level must be IntegrityTraceLevel")

    @property
    def reference_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "canonical_attempt_ref",
            "schema_version": 1,
            "attempt": self.attempt,
            "evidence_manifest_hash": self.evidence_manifest_hash,
            "evidence_manifest_source_hash": self.evidence_manifest_source_hash,
            "evidence_publication_hash": self.evidence_publication_hash,
            "engine_result_artifact_content_hash": (
                self.engine_result_artifact_content_hash
            ),
            "consistency_set_hash": self.consistency_set_hash,
            "execution_result_hash": self.execution_result_hash,
            "execution_case_semantic_hash": self.execution_case_semantic_hash,
            "execution_case_hash": self.execution_case_hash,
            "trace_hash": self.trace_hash,
            "trace_level": self.trace_level.value,
            "market_bundle_manifest_hash": self.market_bundle_manifest_hash,
            "market_bundle_retention_proof_hash": self.market_bundle_retention_proof_hash,
            "deterministic_rebuild_evidence_hash": self.deterministic_rebuild_evidence_hash,
            "deployment_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class IntegrityEvaluationContext:
    resolved_request: ResolvedBacktestRequest
    attempts: AttemptConsistencySet
    execution_hash_check: ExecutionHashCheck
    rebuild_evidence: DeterministicRebuildEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        if not isinstance(self.attempts, AttemptConsistencySet):
            raise TypeError("attempts must be AttemptConsistencySet")
        if self.attempts.resolved_request != self.resolved_request:
            raise ValueError("Attempt set does not bind resolved Request")
        if not isinstance(self.execution_hash_check, ExecutionHashCheck):
            raise TypeError("execution_hash_check must be ExecutionHashCheck")
        expected_check = ExecutionResultHasher.check_same_semantic_run(
            self.attempts.attempt_hashes
        )
        if self.execution_hash_check != expected_check:
            raise ValueError("execution hash check does not bind Attempt set")
        if not isinstance(self.rebuild_evidence, DeterministicRebuildEvidence):
            raise TypeError("rebuild_evidence must be DeterministicRebuildEvidence")
        self._validate_rebuild_evidence()

    def _validate_rebuild_evidence(self) -> None:
        rebuild = self.rebuild_evidence
        request = self.resolved_request
        expected = {
            "semantic_run_id": request.semantic_run_id,
            "request_hash": canonical_sha256(request.request),
            "environment_hash": request.environment.environment_hash,
            "build_artifact_manifest_hash": request.build_artifact_manifest.manifest_hash,
            "market_bundle_manifest_hash": request.environment.market_bundle_ref.manifest_hash,
            "target_stream_digest": request.request.target_stream_digest,
            "execution_case_semantic_hash": request.request.execution_case_semantic_hash,
        }
        for name, value in expected.items():
            if getattr(rebuild, name) != value:
                raise ValueError(f"rebuild evidence {name} mismatch")
        execution_binding = (
            rebuild.execution_case_hash,
            rebuild.trace_hash,
            rebuild.execution_result_hash,
        )
        eligible_bindings = {
            (
                value.engine_result.case_hash,
                value.engine_result.trace.trace_hash,
                value.execution_result_hash,
            )
            for value in self.attempts.attempt_hashes
        }
        if execution_binding not in eligible_bindings:
            raise ValueError("rebuild evidence execution binding mismatch")

    @property
    def context_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "integrity_evaluation_context",
            "schema_version": 1,
            "semantic_run_id": self.resolved_request.semantic_run_id,
            "resolved_request": self.resolved_request,
            "attempt_consistency_set": self.attempts,
            "execution_hash_check": self.execution_hash_check,
            "rebuild_evidence": self.rebuild_evidence,
        }


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    context: IntegrityEvaluationContext
    result_grade: ResultGrade | None
    issues: tuple[IntegrityIssue, ...]
    canonical_attempt_ref: CanonicalAttemptRef | None = None
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.context, IntegrityEvaluationContext):
            raise TypeError("context must be IntegrityEvaluationContext")
        if self.result_grade is not None and not isinstance(
            self.result_grade, ResultGrade
        ):
            raise TypeError("result_grade must be ResultGrade or None")
        if type(self.issues) is not tuple or not all(
            isinstance(value, IntegrityIssue) for value in self.issues
        ):
            raise TypeError("issues must contain IntegrityIssue")
        issues = tuple(
            sorted(self.issues, key=lambda value: (value.severity.value, value.code.value))
        )
        if len({value.code for value in issues}) != len(issues):
            raise ValueError("Integrity issue codes must be unique")
        object.__setattr__(self, "issues", issues)
        blocking = tuple(
            value for value in issues if value.severity is IntegrityIssueSeverity.BLOCKING
        )
        if blocking and self.result_grade is not None:
            raise ValueError("blocking report cannot have result grade")
        if not blocking and self.result_grade is None:
            raise ValueError("nonblocking report requires result grade")
        expected_grade = (
            ResultGrade.DECISION_GRADE
            if self.requested_grade is RequestedResultGrade.DECISION_GRADE
            else ResultGrade.DEVELOPMENT
        )
        if not blocking and self.result_grade is not expected_grade:
            raise ValueError("result grade does not match requested grade")
        if blocking and self.canonical_attempt_ref is not None:
            raise ValueError("blocking report cannot publish canonical Attempt ref")
        if not blocking and not isinstance(
            self.canonical_attempt_ref, CanonicalAttemptRef
        ):
            raise ValueError("nonblocking report requires canonical Attempt ref")
        if (
            self.canonical_attempt_ref is not None
            and self.canonical_attempt_ref.attempt.semantic_run_id
            != self.semantic_run_id
        ):
            raise ValueError("canonical Attempt ref semantic run mismatch")
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("Integrity never authorizes deployment")

    @property
    def semantic_run_id(self) -> str:
        return self.context.resolved_request.semantic_run_id

    @property
    def context_hash(self) -> str:
        return self.context.context_hash

    @property
    def requested_grade(self) -> RequestedResultGrade:
        return self.context.resolved_request.request.result_grade_requested

    @property
    def blocking_issues(self) -> tuple[IntegrityIssue, ...]:
        return tuple(
            value
            for value in self.issues
            if value.severity is IntegrityIssueSeverity.BLOCKING
        )

    @property
    def limitations(self) -> tuple[IntegrityIssue, ...]:
        return tuple(
            value
            for value in self.issues
            if value.severity is IntegrityIssueSeverity.LIMITATION
        )

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "integrity_report",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "context": self.context,
            "context_hash": self.context_hash,
            "requested_grade": self.requested_grade.value,
            "result_grade": self.result_grade.value if self.result_grade else None,
            "issues": self.issues,
            "canonical_attempt_ref_hash": (
                self.canonical_attempt_ref.reference_hash
                if self.canonical_attempt_ref is not None
                else None
            ),
            "deployment_authorized": self.deployment_authorized,
        }


class IntegrityEvaluator:
    def evaluate(self, context: IntegrityEvaluationContext) -> IntegrityReport:
        if not isinstance(context, IntegrityEvaluationContext):
            raise TypeError("context must be IntegrityEvaluationContext")
        request = context.resolved_request
        decision_grade = (
            request.request.result_grade_requested
            is RequestedResultGrade.DECISION_GRADE
        )
        conditional_severity = (
            IntegrityIssueSeverity.BLOCKING
            if decision_grade
            else IntegrityIssueSeverity.LIMITATION
        )
        issues: list[IntegrityIssue] = []
        if len(context.attempts.attempt_hashes) < 2:
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.INSUFFICIENT_ATTEMPTS,
                    IntegrityIssueSeverity.BLOCKING,
                    (request.semantic_run_id,),
                )
            )
        if isinstance(context.execution_hash_check.mismatch, ExecutionHashMismatch):
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.EXECUTION_HASH_MISMATCH,
                    IntegrityIssueSeverity.BLOCKING,
                    tuple(
                        value.attempt_id
                        for value in context.execution_hash_check.mismatch.attempts
                    ),
                    (context.execution_hash_check.mismatch.mismatch_hash,),
                )
            )
        environment = request.environment
        profiles = (
            environment.market_semantics,
            environment.simulation,
            environment.execution_account,
        )
        if any(
            value.grade is RequestedResultGrade.DEVELOPMENT
            or not value.decision_grade_eligible
            for value in profiles
        ):
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.DEVELOPMENT_PROFILE,
                    conditional_severity,
                    tuple(value.profile_key for value in profiles),
                    tuple(value.profile_digest for value in profiles),
                )
            )
        if not request.build_artifact_manifest.decision_grade_eligible:
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.DEVELOPMENT_BUILD,
                    conditional_severity,
                    request.build_artifact_manifest.limitations
                    or ("build_artifact_manifest",),
                    (request.build_artifact_manifest.manifest_hash,),
                )
            )
        if environment.limitations:
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.ENVIRONMENT_LIMITATION,
                    conditional_severity,
                    environment.limitations,
                    (environment.environment_hash,),
                )
            )
        rebuild = context.rebuild_evidence
        if rebuild.trace_level is IntegrityTraceLevel.SUMMARY:
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.SUMMARY_TRACE,
                    conditional_severity,
                    (rebuild.trace_level.value,),
                    (rebuild.trace_hash,),
                )
            )
        if rebuild.market_bundle_retention_proof_hash is None:
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.BUNDLE_RETENTION_UNPROVEN,
                    conditional_severity,
                    (rebuild.market_bundle_manifest_hash,),
                )
            )
        if rebuild.deterministic_rebuild_proof_hash is None:
            issues.append(
                IntegrityIssue(
                    IntegrityIssueCode.DETERMINISTIC_REBUILD_UNPROVEN,
                    conditional_severity,
                    (rebuild.evidence_hash,),
                )
            )
        blocking = any(
            value.severity is IntegrityIssueSeverity.BLOCKING for value in issues
        )
        canonical_ref = None if blocking else self._canonical_attempt_ref(context)
        grade = None
        if not blocking:
            grade = (
                ResultGrade.DECISION_GRADE
                if decision_grade
                else ResultGrade.DEVELOPMENT
            )
        return IntegrityReport(
            context=context,
            result_grade=grade,
            issues=tuple(issues),
            canonical_attempt_ref=canonical_ref,
        )

    @staticmethod
    def _canonical_attempt_ref(
        context: IntegrityEvaluationContext,
    ) -> CanonicalAttemptRef:
        attempt_hash = context.attempts.canonical_attempt
        evidence = context.attempts.canonical_evidence
        rebuild = context.rebuild_evidence
        return CanonicalAttemptRef(
            attempt=attempt_hash.attempt,
            evidence_manifest_hash=evidence.manifest.manifest_hash,
            evidence_manifest_source_hash=evidence.manifest_source_hash,
            evidence_publication_hash=evidence.publication_hash,
            engine_result_artifact_content_hash=(
                attempt_hash.engine_result_artifact_content_hash
            ),
            consistency_set_hash=context.attempts.consistency_set_hash,
            execution_result_hash=attempt_hash.execution_result_hash,
            execution_case_semantic_hash=(
                context.resolved_request.request.execution_case_semantic_hash
            ),
            execution_case_hash=attempt_hash.engine_result.case_hash,
            trace_hash=attempt_hash.engine_result.trace.trace_hash,
            trace_level=rebuild.trace_level,
            market_bundle_manifest_hash=rebuild.market_bundle_manifest_hash,
            market_bundle_retention_proof_hash=(
                rebuild.market_bundle_retention_proof_hash
            ),
            deterministic_rebuild_evidence_hash=rebuild.evidence_hash,
        )


class CanonicalPublicationFailureCode(str, Enum):
    RUN_LOCK_UNAVAILABLE = "run_lock_unavailable"
    SEMANTIC_RUN_CLOSED = "semantic_run_closed"
    ATTEMPT_SET_MISMATCH = "attempt_set_mismatch"
    ATTEMPT_EVIDENCE_INVALID = "attempt_evidence_invalid"
    INVALID_INTEGRITY_CONTEXT = "invalid_integrity_context"
    STAGING_PREPARE_FAILED = "staging_prepare_failed"
    STAGING_EXISTS = "staging_exists"
    FINAL_DESTINATION_EXISTS = "final_destination_exists"
    ARTIFACT_WRITE_FAILED = "artifact_write_failed"
    MANIFEST_WRITE_FAILED = "manifest_write_failed"
    PUBLICATION_VERIFICATION_FAILED = "publication_verification_failed"
    IMMUTABILITY_FAILED = "immutability_failed"
    ATOMIC_FINALIZE_FAILED = "atomic_finalize_failed"


@dataclass(frozen=True, slots=True)
class _PublicationArtifactEntry:
    relative_path: str
    artifact_type: str
    schema_version: int
    content_hash: str
    source_hash: str
    byte_count: int

    def __post_init__(self) -> None:
        _text("relative_path", self.relative_path)
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or len(path.parts) != 1:
            raise ValueError("publication artifact path must be a file name")
        CanonicalSchema(self.artifact_type, self.schema_version)
        if self.schema_version not in {1, 2}:
            raise ValueError("publication artifact schema_version must be 1 or 2")
        if self.schema_version == 2 and self.artifact_type != "completed_backtest_result":
            raise ValueError(
                "publication artifact schema_version 2 is reserved for completed Result"
            )
        _hash("content_hash", self.content_hash)
        _hash("source_hash", self.source_hash)
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise ValueError("byte_count must be positive integer")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "content_hash": self.content_hash,
            "source_hash": self.source_hash,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True, slots=True)
class CanonicalPublicationManifest:
    semantic_run_id: str
    publication_kind: str
    publication_id: str
    artifacts: tuple[_PublicationArtifactEntry, ...]
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if self.publication_kind not in {"canonical", "integrity_evaluation"}:
            raise ValueError("unsupported publication_kind")
        _text("publication_id", self.publication_id)
        if type(self.artifacts) is not tuple or not self.artifacts:
            raise ValueError("artifacts must be a nonempty tuple")
        if not all(
            isinstance(value, _PublicationArtifactEntry) for value in self.artifacts
        ):
            raise TypeError("artifacts must contain publication entries")
        ordered = tuple(sorted(self.artifacts, key=lambda value: value.relative_path))
        if len({value.relative_path for value in ordered}) != len(ordered):
            raise ValueError("publication artifact paths must be unique")
        expected = (
            {
                "canonical-attempt-ref.json",
                "integrity.json",
                "result.json",
            }
            if self.publication_kind == "canonical"
            else {"integrity.json", "evaluation-outcome.json"}
        )
        if {value.relative_path for value in ordered} != expected:
            raise ValueError("publication manifest does not exact-cover files")
        object.__setattr__(self, "artifacts", ordered)
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("publication manifest never authorizes deployment")

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "canonical_publication_manifest",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "publication_kind": self.publication_kind,
            "publication_id": self.publication_id,
            "artifacts": self.artifacts,
            "deployment_authorized": self.deployment_authorized,
        }


def _publication_entry(
    relative_path: str,
    artifact_type: str,
    payload: object,
    schema_version: int = 1,
) -> _PublicationArtifactEntry:
    envelope = ArtifactEnvelope.create(artifact_type, schema_version, payload)
    source = canonical_bytes(envelope)
    return _PublicationArtifactEntry(
        relative_path=relative_path,
        artifact_type=artifact_type,
        schema_version=schema_version,
        content_hash=envelope.content_hash,
        source_hash=f"sha256:{hashlib.sha256(source).hexdigest()}",
        byte_count=len(source),
    )


def _publication_source_hash(artifact_type: str, payload: object, schema_version: int = 1) -> str:
    source = canonical_bytes(ArtifactEnvelope.create(artifact_type, schema_version, payload))
    return f"sha256:{hashlib.sha256(source).hexdigest()}"


@dataclass(frozen=True, slots=True)
class CompletedBacktestResult:
    context: IntegrityEvaluationContext
    canonical_attempt_ref: CanonicalAttemptRef
    integrity_report: IntegrityReport
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.context, IntegrityEvaluationContext):
            raise TypeError("context must be IntegrityEvaluationContext")
        if not isinstance(self.canonical_attempt_ref, CanonicalAttemptRef):
            raise TypeError("canonical_attempt_ref must be CanonicalAttemptRef")
        if not isinstance(self.integrity_report, IntegrityReport):
            raise TypeError("integrity_report must be IntegrityReport")
        if self.integrity_report.context != self.context:
            raise ValueError("Integrity report does not bind Result context")
        if self.integrity_report.blocking_issues:
            raise ValueError("Completed Result cannot bind blocking Integrity")
        if self.integrity_report.canonical_attempt_ref != self.canonical_attempt_ref:
            raise ValueError("Integrity report does not bind canonical Attempt ref")
        if (
            self.canonical_attempt_ref.consistency_set_hash
            != self.context.attempts.consistency_set_hash
        ):
            raise ValueError("canonical Attempt ref does not bind consistency set")
        if (
            self.context.attempts.canonical_attempt.attempt
            != self.canonical_attempt_ref.attempt
        ):
            raise ValueError("canonical Attempt ref does not bind canonical Attempt")
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("Completed backtest never authorizes deployment")

    @property
    def semantic_run_id(self) -> str:
        return self.context.resolved_request.semantic_run_id

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.context.resolved_request.request)

    @property
    def consistency_set_hash(self) -> str:
        return self.context.attempts.consistency_set_hash

    @property
    def outcome(self) -> BacktestRunOutcome:
        return BacktestRunOutcome.COMPLETED

    @property
    def execution_result_hash(self) -> str:
        return self.canonical_attempt_ref.execution_result_hash

    @property
    def canonical_attempt_ref_hash(self) -> str:
        return self.canonical_attempt_ref.reference_hash

    @property
    def integrity_report_hash(self) -> str:
        return self.integrity_report.report_hash

    @property
    def result_grade(self) -> ResultGrade:
        grade = self.integrity_report.result_grade
        if grade is None:
            raise RuntimeError("Completed Result Integrity grade is missing")
        return grade

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "completed_backtest_result",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "outcome": self.outcome.value,
            "request_hash": self.request_hash,
            "resolved_request": self.context.resolved_request,
            "attempt_consistency_set": self.context.attempts,
            "execution_hash_check": self.context.execution_hash_check,
            "execution_result_hash": self.execution_result_hash,
            "consistency_set_hash": self.consistency_set_hash,
            "attempt_id": self.canonical_attempt_ref.attempt.attempt_id,
            "evidence_manifest_hash": (
                self.canonical_attempt_ref.evidence_manifest_hash
            ),
            "canonical_attempt_ref_hash": self.canonical_attempt_ref_hash,
            "integrity_report_hash": self.integrity_report_hash,
            "integrity": {
                "blocking": self.integrity_report.blocking_issues,
                "limitations": self.integrity_report.limitations,
            },
            "result_grade": self.result_grade.value,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class EngineExecutionContext:
    semantic_run_id: str
    semantic_spec_hash: str
    case_hash: str
    target_stream_digest: str
    identity_manifest_hash: str
    financial_state: ResolvedFinancialState

    def __post_init__(self) -> None:
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        _hash("semantic_spec_hash", self.semantic_spec_hash)
        _hash("case_hash", self.case_hash)
        _hash("target_stream_digest", self.target_stream_digest)
        _hash("identity_manifest_hash", self.identity_manifest_hash)
        if type(self.financial_state) is not ResolvedFinancialState:
            raise TypeError("financial_state must be exact ResolvedFinancialState")

    @property
    def context_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_execution_context",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "semantic_spec_hash": self.semantic_spec_hash,
            "case_hash": self.case_hash,
            "target_stream_digest": self.target_stream_digest,
            "identity_manifest_hash": self.identity_manifest_hash,
            "financial_state": self.financial_state,
        }


@dataclass(frozen=True, slots=True)
class CompletedBacktestResultV2(CompletedBacktestResult):
    engine_context: EngineExecutionContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context, IntegrityEvaluationContext):
            raise TypeError("context must be IntegrityEvaluationContext")
        if not isinstance(self.canonical_attempt_ref, CanonicalAttemptRef):
            raise TypeError("canonical_attempt_ref must be CanonicalAttemptRef")
        if not isinstance(self.integrity_report, IntegrityReport):
            raise TypeError("integrity_report must be IntegrityReport")
        if self.integrity_report.context != self.context:
            raise ValueError("Integrity report does not bind Result context")
        if self.integrity_report.blocking_issues:
            raise ValueError("Completed Result cannot bind blocking Integrity")
        if self.integrity_report.canonical_attempt_ref != self.canonical_attempt_ref:
            raise ValueError("Integrity report does not bind canonical Attempt ref")
        if (
            self.canonical_attempt_ref.consistency_set_hash
            != self.context.attempts.consistency_set_hash
        ):
            raise ValueError("canonical Attempt ref does not bind consistency set")
        if (
            self.context.attempts.canonical_attempt.attempt
            != self.canonical_attempt_ref.attempt
        ):
            raise ValueError("canonical Attempt ref does not bind canonical Attempt")
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("Completed backtest never authorizes deployment")
        if type(self.engine_context) is not EngineExecutionContext:
            raise TypeError("engine_context must be exact EngineExecutionContext")
        execution = self.context.attempts.canonical_attempt.engine_result
        request = self.context.resolved_request.request
        engine_context = self.engine_context
        if engine_context.semantic_run_id != self.semantic_run_id:
            raise ValueError("engine context semantic run mismatch")
        if engine_context.semantic_spec_hash != request.execution_case_semantic_hash:
            raise ValueError("engine context semantic hash mismatch")
        if engine_context.target_stream_digest != request.target_stream_digest:
            raise ValueError("engine context target digest does not bind request")
        if engine_context.case_hash != execution.case_hash:
            raise ValueError("engine context case hash does not bind execution result")
        if engine_context.target_stream_digest != execution.target_stream_digest:
            raise ValueError("engine context target digest does not bind execution result")
        initial = engine_context.financial_state
        if execution.final_journal.entries[: len(initial.journal.entries)] != initial.journal.entries:
            raise ValueError("completed Journal does not preserve the run-start prefix")
        starting = initial.initial_snapshot
        ending = execution.final_portfolio_snapshot
        if (
            starting.account_id != ending.account_id
            or starting.reporting_currency != ending.reporting_currency
            or starting.reporting_currency != request.reporting_currency
        ):
            raise ValueError("run-boundary PortfolioSnapshot context mismatch")

    @property
    def canonical_evidence_manifest_ref(self) -> ArtifactRef:
        evidence = self.context.attempts.canonical_evidence
        envelope = ArtifactEnvelope.create("evidence_manifest", 1, evidence.manifest)
        ref = ArtifactRef.from_envelope(envelope)
        if (
            evidence.manifest.manifest_hash
            != self.canonical_attempt_ref.evidence_manifest_hash
        ):
            raise ValueError("canonical evidence manifest hash mismatch")
        if (
            evidence.manifest_source_hash
            != self.canonical_attempt_ref.evidence_manifest_source_hash
        ):
            raise ValueError("canonical evidence manifest source hash mismatch")
        return ref

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "completed_backtest_result",
            "schema_version": 2,
            "semantic_run_id": self.semantic_run_id,
            "outcome": self.outcome.value,
            "request_hash": self.request_hash,
            "resolved_request": self.context.resolved_request,
            "attempt_consistency_set": self.context.attempts,
            "execution_hash_check": self.context.execution_hash_check,
            "execution_result_hash": self.execution_result_hash,
            "consistency_set_hash": self.consistency_set_hash,
            "attempt_id": self.canonical_attempt_ref.attempt.attempt_id,
            "evidence_manifest_hash": (
                self.canonical_attempt_ref.evidence_manifest_hash
            ),
            "canonical_evidence_manifest_ref": self.canonical_evidence_manifest_ref,
            "canonical_attempt_ref_hash": self.canonical_attempt_ref_hash,
            "integrity_report_hash": self.integrity_report_hash,
            "integrity": {
                "blocking": self.integrity_report.blocking_issues,
                "limitations": self.integrity_report.limitations,
            },
            "result_grade": self.result_grade.value,
            "engine_execution_context": self.engine_context,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class IntegrityEvaluationRecord:
    report: IntegrityReport
    outcome: BacktestRunOutcome
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.report, IntegrityReport):
            raise TypeError("report must be IntegrityReport")
        if not self.report.blocking_issues:
            raise ValueError("Integrity evaluation requires blocking issues")
        expected = (
            BacktestRunOutcome.FAILED
            if any(
                value.code is IntegrityIssueCode.EXECUTION_HASH_MISMATCH
                for value in self.report.blocking_issues
            )
            else BacktestRunOutcome.BLOCKED
        )
        if self.outcome is not expected:
            raise ValueError("evaluation outcome does not match Integrity issues")
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("Integrity evaluation never authorizes deployment")

    @property
    def evaluation_id(self) -> str:
        digest = canonical_sha256(
            {
                "type": "integrity_evaluation_identity_v1",
                "semantic_run_id": self.report.semantic_run_id,
                "report_hash": self.report.report_hash,
                "outcome": self.outcome.value,
            }
        )
        return f"evaluation_{digest.removeprefix('sha256:')}"

    @property
    def record_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "integrity_evaluation_record",
            "schema_version": 1,
            "evaluation_id": self.evaluation_id,
            "semantic_run_id": self.report.semantic_run_id,
            "outcome": self.outcome.value,
            "integrity_report_hash": self.report.report_hash,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class FinalizedCanonicalResult:
    canonical_attempt_ref: CanonicalAttemptRef
    integrity_report: IntegrityReport
    result: CompletedBacktestResult
    manifest: CanonicalPublicationManifest
    manifest_source_hash: str
    relative_directory: str

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_attempt_ref, CanonicalAttemptRef):
            raise TypeError("canonical_attempt_ref must be CanonicalAttemptRef")
        if not isinstance(self.integrity_report, IntegrityReport):
            raise TypeError("integrity_report must be IntegrityReport")
        if not isinstance(self.result, CompletedBacktestResult):
            raise TypeError("result must be CompletedBacktestResult")
        if not isinstance(self.manifest, CanonicalPublicationManifest):
            raise TypeError("manifest must be CanonicalPublicationManifest")
        if self.manifest.publication_kind != "canonical":
            raise ValueError("manifest must be canonical publication")
        expected_entries = tuple(
            sorted(
                (
                    _publication_entry(
                        "canonical-attempt-ref.json",
                        "canonical_attempt_ref",
                        self.canonical_attempt_ref,
                    ),
                    _publication_entry(
                        "integrity.json",
                        "integrity_report",
                        self.integrity_report,
                    ),
                    _publication_entry(
                        "result.json",
                        "completed_backtest_result",
                        self.result,
                    ),
                ),
                key=lambda value: value.relative_path,
            )
        )
        if self.manifest.artifacts != expected_entries:
            raise ValueError("publication manifest source hashes do not bind Result")
        if self.result.canonical_attempt_ref_hash != self.canonical_attempt_ref.reference_hash:
            raise ValueError("Result does not bind canonical Attempt ref")
        if self.result.integrity_report_hash != self.integrity_report.report_hash:
            raise ValueError("Result does not bind Integrity report")
        if self.integrity_report.canonical_attempt_ref != self.canonical_attempt_ref:
            raise ValueError("Integrity report does not bind canonical Attempt ref")
        if self.result.semantic_run_id != self.manifest.semantic_run_id:
            raise ValueError("Result and manifest semantic run mismatch")
        _hash("manifest_source_hash", self.manifest_source_hash)
        if self.manifest_source_hash != _publication_source_hash(
            "canonical_publication_manifest",
            self.manifest,
        ):
            raise ValueError("publication manifest source hash mismatch")
        expected = f"runs/{self.result.semantic_run_id}/canonical"
        if self.relative_directory != expected:
            raise ValueError("relative_directory does not match canonical layout")

    @property
    def publication_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "finalized_canonical_result",
            "schema_version": 1,
            "semantic_run_id": self.result.semantic_run_id,
            "canonical_attempt_ref_hash": self.canonical_attempt_ref.reference_hash,
            "integrity_report_hash": self.integrity_report.report_hash,
            "result_hash": self.result.result_hash,
            "publication_manifest_hash": self.manifest.manifest_hash,
            "publication_manifest_source_hash": self.manifest_source_hash,
            "relative_directory": self.relative_directory,
            "deployment_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class FinalizedCanonicalResultV2:
    canonical_attempt_ref: CanonicalAttemptRef
    integrity_report: IntegrityReport
    result: CompletedBacktestResultV2
    manifest: CanonicalPublicationManifest
    manifest_source_hash: str
    relative_directory: str

    def __post_init__(self) -> None:
        if type(self.canonical_attempt_ref) is not CanonicalAttemptRef:
            raise TypeError("canonical_attempt_ref must be exact CanonicalAttemptRef")
        if type(self.integrity_report) is not IntegrityReport:
            raise TypeError("integrity_report must be exact IntegrityReport")
        if type(self.result) is not CompletedBacktestResultV2:
            raise TypeError("result must be exact CompletedBacktestResultV2")
        if type(self.manifest) is not CanonicalPublicationManifest:
            raise TypeError("manifest must be exact CanonicalPublicationManifest")
        expected_entries = tuple(sorted((
            _publication_entry("canonical-attempt-ref.json", "canonical_attempt_ref", self.canonical_attempt_ref),
            _publication_entry("integrity.json", "integrity_report", self.integrity_report),
            _publication_entry("result.json", "completed_backtest_result", self.result, 2),
        ), key=lambda value: value.relative_path))
        if self.manifest.artifacts != expected_entries:
            raise ValueError("publication manifest source hashes do not bind Result")
        if self.manifest.publication_kind != "canonical" or self.manifest.publication_id != "canonical-v2":
            raise ValueError("manifest must be canonical-v2 publication")
        if self.result.canonical_attempt_ref_hash != self.canonical_attempt_ref.reference_hash:
            raise ValueError("Result does not bind canonical Attempt ref")
        if self.result.integrity_report_hash != self.integrity_report.report_hash:
            raise ValueError("Result does not bind Integrity report")
        if self.result.semantic_run_id != self.manifest.semantic_run_id:
            raise ValueError("Result and manifest semantic run mismatch")
        _hash("manifest_source_hash", self.manifest_source_hash)
        if self.manifest_source_hash != _publication_source_hash("canonical_publication_manifest", self.manifest):
            raise ValueError("publication manifest source hash mismatch")
        if self.relative_directory != f"runs/{self.result.semantic_run_id}/canonical-v2":
            raise ValueError("relative_directory does not match canonical-v2 layout")

    @property
    def publication_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "finalized_canonical_result",
            "schema_version": 2,
            "semantic_run_id": self.result.semantic_run_id,
            "canonical_attempt_ref_hash": self.canonical_attempt_ref.reference_hash,
            "integrity_report_hash": self.integrity_report.report_hash,
            "result_hash": self.result.result_hash,
            "publication_manifest_hash": self.manifest.manifest_hash,
            "publication_manifest_source_hash": self.manifest_source_hash,
            "relative_directory": self.relative_directory,
            "deployment_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class FinalizedIntegrityEvaluation:
    report: IntegrityReport
    record: IntegrityEvaluationRecord
    manifest: CanonicalPublicationManifest
    manifest_source_hash: str
    relative_directory: str

    def __post_init__(self) -> None:
        if not isinstance(self.report, IntegrityReport):
            raise TypeError("report must be IntegrityReport")
        if not isinstance(self.record, IntegrityEvaluationRecord):
            raise TypeError("record must be IntegrityEvaluationRecord")
        if self.record.report != self.report:
            raise ValueError("evaluation record does not bind report")
        if not isinstance(self.manifest, CanonicalPublicationManifest):
            raise TypeError("manifest must be CanonicalPublicationManifest")
        if self.manifest.publication_kind != "integrity_evaluation":
            raise ValueError("manifest must be Integrity evaluation publication")
        expected_entries = tuple(
            sorted(
                (
                    _publication_entry(
                        "integrity.json",
                        "integrity_report",
                        self.report,
                    ),
                    _publication_entry(
                        "evaluation-outcome.json",
                        "integrity_evaluation_record",
                        self.record,
                    ),
                ),
                key=lambda value: value.relative_path,
            )
        )
        if self.manifest.artifacts != expected_entries:
            raise ValueError("publication manifest source hashes do not bind evaluation")
        _hash("manifest_source_hash", self.manifest_source_hash)
        if self.manifest_source_hash != _publication_source_hash(
            "canonical_publication_manifest",
            self.manifest,
        ):
            raise ValueError("publication manifest source hash mismatch")
        expected = (
            f"runs/{self.report.semantic_run_id}/integrity-evaluations/"
            f"{self.record.evaluation_id}"
        )
        if self.relative_directory != expected:
            raise ValueError("relative_directory does not match evaluation layout")

    @property
    def publication_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "finalized_integrity_evaluation",
            "schema_version": 1,
            "semantic_run_id": self.report.semantic_run_id,
            "evaluation_id": self.record.evaluation_id,
            "outcome": self.record.outcome.value,
            "integrity_report_hash": self.report.report_hash,
            "evaluation_record_hash": self.record.record_hash,
            "publication_manifest_hash": self.manifest.manifest_hash,
            "publication_manifest_source_hash": self.manifest_source_hash,
            "relative_directory": self.relative_directory,
            "deployment_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class CanonicalPublicationFailure:
    semantic_run_id: str
    code: CanonicalPublicationFailureCode
    relative_subject: str
    exception_type: str | None = None
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if not isinstance(self.code, CanonicalPublicationFailureCode):
            raise TypeError("code must be CanonicalPublicationFailureCode")
        _text("relative_subject", self.relative_subject)
        if self.exception_type is not None:
            _text("exception_type", self.exception_type)
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("Publication failure never authorizes deployment")

    @property
    def outcome(self) -> BacktestRunOutcome:
        return BacktestRunOutcome.FAILED

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "canonical_publication_failure",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "code": self.code.value,
            "relative_subject": self.relative_subject,
            "exception_type": self.exception_type,
            "outcome": self.outcome.value,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class CanonicalPublicationOutcome:
    finalized_result: FinalizedCanonicalResult | None = None
    finalized_evaluation: FinalizedIntegrityEvaluation | None = None
    failure: CanonicalPublicationFailure | None = None

    def __post_init__(self) -> None:
        branches = (
            self.finalized_result,
            self.finalized_evaluation,
            self.failure,
        )
        if sum(map(bool, branches)) != 1:
            raise ValueError("publication outcome requires exactly one branch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "canonical_publication_outcome",
            "schema_version": 1,
            "finalized_result": self.finalized_result,
            "finalized_evaluation": self.finalized_evaluation,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class CanonicalPublicationOutcomeV2:
    finalized_result_v2: FinalizedCanonicalResultV2 | None = None
    finalized_evaluation: FinalizedIntegrityEvaluation | None = None
    failure: CanonicalPublicationFailure | None = None

    def __post_init__(self) -> None:
        if sum(map(bool, (self.finalized_result_v2, self.finalized_evaluation, self.failure))) != 1:
            raise ValueError("publication outcome requires exactly one branch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "canonical_publication_outcome",
            "schema_version": 2,
            "finalized_result": self.finalized_result_v2,
            "finalized_evaluation": self.finalized_evaluation,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class _PublicationPlan:
    relative_path: str
    artifact_type: str
    payload: object
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class _PublishedDirectory:
    manifest: CanonicalPublicationManifest
    manifest_source_hash: str
    relative_directory: str


_PUBLICATION_CATALOG = SchemaCatalog(
    (
        *(
            ArtifactSchemaRegistration(artifact_type, 1, lambda payload: payload)
            for artifact_type in (
                "canonical_attempt_ref",
                "canonical_publication_manifest",
                "completed_backtest_result",
                "integrity_evaluation_record",
                "integrity_report",
            )
        ),
        ArtifactSchemaRegistration(
            "completed_backtest_result", 2, lambda payload: payload
        ),
    )
)


class _AttemptSetMismatch(ValueError):
    pass


class _AttemptEvidenceInvalid(ValueError):
    pass


class CanonicalResultPublisher:
    """Publish one canonical Result or durable blocking Integrity evaluation."""

    FILESYSTEM_MODEL = "trusted_local_cooperative_single_writer_v1"

    def __init__(
        self,
        *,
        root: Path,
        filesystem_model: str = FILESYSTEM_MODEL,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be pathlib.Path")
        if filesystem_model != self.FILESYSTEM_MODEL:
            raise ValueError(
                "v1 requires trusted cooperative single-writer local filesystem"
            )
        self._root = root

    def publish(
        self,
        *,
        resolved_request: ResolvedBacktestRequest,
        attempt_hashes: tuple[AttemptExecutionHash, ...],
        finalized_attempts: tuple[FinalizedAttemptEvidence, ...],
        rebuild_evidence: DeterministicRebuildEvidence,
    ) -> CanonicalPublicationOutcome:
        if not isinstance(resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        semantic_run_id = resolved_request.semantic_run_id
        try:
            with RunPublicationLock(
                root=self._root,
                semantic_run_id=semantic_run_id,
            ):
                return self._publish_locked(
                    resolved_request,
                    attempt_hashes,
                    finalized_attempts,
                    rebuild_evidence,
                )
        except FileExistsError as error:
            return CanonicalPublicationOutcome(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.RUN_LOCK_UNAVAILABLE,
                    f"runs/{semantic_run_id}/.publication.lock",
                    error,
                )
            )
        except OSError as error:
            return CanonicalPublicationOutcome(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.STAGING_PREPARE_FAILED,
                    f"runs/{semantic_run_id}",
                    error,
                )
            )

    def publish_v2(
        self,
        *,
        resolved_request: ResolvedBacktestRequest,
        attempt_hashes: tuple[AttemptExecutionHash, ...],
        finalized_attempts: tuple[FinalizedAttemptEvidence, ...],
        rebuild_evidence: DeterministicRebuildEvidence,
        engine_context: EngineExecutionContext,
    ) -> CanonicalPublicationOutcomeV2:
        if type(engine_context) is not EngineExecutionContext:
            raise TypeError("engine_context must be exact EngineExecutionContext")
        if not isinstance(resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        semantic_run_id = resolved_request.semantic_run_id
        try:
            with RunPublicationLock(
                root=self._root,
                semantic_run_id=semantic_run_id,
            ):
                return self._publish_v2_locked(
                    resolved_request,
                    attempt_hashes,
                    finalized_attempts,
                    rebuild_evidence,
                    engine_context,
                )
        except FileExistsError as error:
            return CanonicalPublicationOutcomeV2(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.RUN_LOCK_UNAVAILABLE,
                    f"runs/{semantic_run_id}/.publication.lock",
                    error,
                )
            )
        except OSError as error:
            return CanonicalPublicationOutcomeV2(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.STAGING_PREPARE_FAILED,
                    f"runs/{semantic_run_id}",
                    error,
                )
            )

    def _publish_locked(
        self,
        resolved_request: ResolvedBacktestRequest,
        attempt_hashes: tuple[AttemptExecutionHash, ...],
        finalized_attempts: tuple[FinalizedAttemptEvidence, ...],
        rebuild_evidence: DeterministicRebuildEvidence,
    ) -> CanonicalPublicationOutcome:
        semantic_run_id = resolved_request.semantic_run_id
        canonical = self._root / "runs" / semantic_run_id / "canonical"
        if os.path.lexists(canonical):
            return CanonicalPublicationOutcome(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.SEMANTIC_RUN_CLOSED,
                    f"runs/{semantic_run_id}/canonical",
                )
            )
        try:
            self._verify_attempt_set(
                semantic_run_id,
                attempt_hashes,
                finalized_attempts,
            )
        except _AttemptSetMismatch as error:
            return CanonicalPublicationOutcome(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.ATTEMPT_SET_MISMATCH,
                    f"runs/{semantic_run_id}/attempts",
                    error,
                )
            )
        except _AttemptEvidenceInvalid as error:
            return CanonicalPublicationOutcome(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.ATTEMPT_EVIDENCE_INVALID,
                    f"runs/{semantic_run_id}/attempts",
                    error,
                )
            )
        try:
            attempts = AttemptConsistencySet(
                resolved_request,
                attempt_hashes,
                finalized_attempts,
            )
            check = ExecutionResultHasher.check_same_semantic_run(attempt_hashes)
            context = IntegrityEvaluationContext(
                resolved_request,
                attempts,
                check,
                rebuild_evidence,
            )
            report = IntegrityEvaluator().evaluate(context)
        except (TypeError, ValueError) as error:
            return CanonicalPublicationOutcome(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.INVALID_INTEGRITY_CONTEXT,
                    f"runs/{semantic_run_id}/attempts",
                    error,
                )
            )
        if report.blocking_issues:
            return self._publish_evaluation(report)
        return self._publish_canonical(resolved_request, attempts, report)

    def _publish_canonical(
        self,
        resolved_request: ResolvedBacktestRequest,
        attempts: AttemptConsistencySet,
        report: IntegrityReport,
    ) -> CanonicalPublicationOutcome:
        reference = report.canonical_attempt_ref
        grade = report.result_grade
        if reference is None or grade is None:
            return CanonicalPublicationOutcome(
                failure=self._failure(
                    resolved_request.semantic_run_id,
                    CanonicalPublicationFailureCode.INVALID_INTEGRITY_CONTEXT,
                    "integrity-report",
                )
            )
        result = CompletedBacktestResult(
            context=report.context,
            canonical_attempt_ref=reference,
            integrity_report=report,
        )
        relative = f"runs/{resolved_request.semantic_run_id}/canonical"
        publication = self._publish_directory(
            semantic_run_id=resolved_request.semantic_run_id,
            publication_kind="canonical",
            publication_id="canonical",
            relative_directory=relative,
            plans=(
                _PublicationPlan(
                    "canonical-attempt-ref.json",
                    "canonical_attempt_ref",
                    reference,
                ),
                _PublicationPlan("integrity.json", "integrity_report", report),
                _PublicationPlan(
                    "result.json",
                    "completed_backtest_result",
                    result,
                ),
            ),
        )
        if isinstance(publication, CanonicalPublicationFailure):
            return CanonicalPublicationOutcome(failure=publication)
        return CanonicalPublicationOutcome(
            finalized_result=FinalizedCanonicalResult(
                reference,
                report,
                result,
                publication.manifest,
                publication.manifest_source_hash,
                publication.relative_directory,
            )
        )

    def _publish_v2_locked(
        self,
        resolved_request: ResolvedBacktestRequest,
        attempt_hashes: tuple[AttemptExecutionHash, ...],
        finalized_attempts: tuple[FinalizedAttemptEvidence, ...],
        rebuild_evidence: DeterministicRebuildEvidence,
        engine_context: EngineExecutionContext,
    ) -> CanonicalPublicationOutcomeV2:
        semantic_run_id = resolved_request.semantic_run_id
        canonical = self._root / "runs" / semantic_run_id / "canonical-v2"
        if os.path.lexists(canonical):
            return CanonicalPublicationOutcomeV2(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.SEMANTIC_RUN_CLOSED,
                    f"runs/{semantic_run_id}/canonical-v2",
                )
            )
        try:
            self._verify_attempt_set(
                semantic_run_id,
                attempt_hashes,
                finalized_attempts,
            )
        except _AttemptSetMismatch as error:
            return CanonicalPublicationOutcomeV2(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.ATTEMPT_SET_MISMATCH,
                    f"runs/{semantic_run_id}/attempts",
                    error,
                )
            )
        except _AttemptEvidenceInvalid as error:
            return CanonicalPublicationOutcomeV2(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.ATTEMPT_EVIDENCE_INVALID,
                    f"runs/{semantic_run_id}/attempts",
                    error,
                )
            )
        try:
            attempts = AttemptConsistencySet(
                resolved_request,
                attempt_hashes,
                finalized_attempts,
            )
            check = ExecutionResultHasher.check_same_semantic_run(attempt_hashes)
            context = IntegrityEvaluationContext(
                resolved_request,
                attempts,
                check,
                rebuild_evidence,
            )
            report = IntegrityEvaluator().evaluate(context)
        except (TypeError, ValueError) as error:
            return CanonicalPublicationOutcomeV2(
                failure=self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.INVALID_INTEGRITY_CONTEXT,
                    f"runs/{semantic_run_id}/attempts",
                    error,
                )
            )
        if report.blocking_issues:
            outcome = self._publish_evaluation(report)
            return CanonicalPublicationOutcomeV2(
                finalized_evaluation=outcome.finalized_evaluation,
                failure=outcome.failure,
            )
        return self._publish_canonical_v2(resolved_request, attempts, report, engine_context)

    def _publish_canonical_v2(
        self,
        resolved_request: ResolvedBacktestRequest,
        attempts: AttemptConsistencySet,
        report: IntegrityReport,
        engine_context: EngineExecutionContext,
    ) -> CanonicalPublicationOutcomeV2:
        reference = report.canonical_attempt_ref
        grade = report.result_grade
        if reference is None or grade is None:
            return CanonicalPublicationOutcomeV2(
                failure=self._failure(
                    resolved_request.semantic_run_id,
                    CanonicalPublicationFailureCode.INVALID_INTEGRITY_CONTEXT,
                    "integrity-report",
                )
            )
        result = CompletedBacktestResultV2(
            context=report.context,
            canonical_attempt_ref=reference,
            integrity_report=report,
            engine_context=engine_context,
        )
        relative = f"runs/{resolved_request.semantic_run_id}/canonical-v2"
        publication = self._publish_directory(
            semantic_run_id=resolved_request.semantic_run_id,
            publication_kind="canonical",
            publication_id="canonical-v2",
            relative_directory=relative,
            plans=(
                _PublicationPlan(
                    "canonical-attempt-ref.json", "canonical_attempt_ref", reference
                ),
                _PublicationPlan("integrity.json", "integrity_report", report),
                _PublicationPlan(
                    "result.json", "completed_backtest_result", result, 2
                ),
            ),
        )
        if isinstance(publication, CanonicalPublicationFailure):
            return CanonicalPublicationOutcomeV2(failure=publication)
        return CanonicalPublicationOutcomeV2(
            finalized_result_v2=FinalizedCanonicalResultV2(
                reference,
                report,
                result,
                publication.manifest,
                publication.manifest_source_hash,
                publication.relative_directory,
            )
        )

    def _publish_evaluation(
        self,
        report: IntegrityReport,
    ) -> CanonicalPublicationOutcome:
        outcome = (
            BacktestRunOutcome.FAILED
            if any(
                value.code is IntegrityIssueCode.EXECUTION_HASH_MISMATCH
                for value in report.blocking_issues
            )
            else BacktestRunOutcome.BLOCKED
        )
        record = IntegrityEvaluationRecord(report, outcome)
        relative = (
            f"runs/{report.semantic_run_id}/integrity-evaluations/"
            f"{record.evaluation_id}"
        )
        publication = self._publish_directory(
            semantic_run_id=report.semantic_run_id,
            publication_kind="integrity_evaluation",
            publication_id=record.evaluation_id,
            relative_directory=relative,
            plans=(
                _PublicationPlan("integrity.json", "integrity_report", report),
                _PublicationPlan(
                    "evaluation-outcome.json",
                    "integrity_evaluation_record",
                    record,
                ),
            ),
        )
        if isinstance(publication, CanonicalPublicationFailure):
            return CanonicalPublicationOutcome(failure=publication)
        return CanonicalPublicationOutcome(
            finalized_evaluation=FinalizedIntegrityEvaluation(
                report,
                record,
                publication.manifest,
                publication.manifest_source_hash,
                publication.relative_directory,
            )
        )

    def _verify_attempt_set(
        self,
        semantic_run_id: str,
        attempt_hashes: tuple[AttemptExecutionHash, ...],
        finalized_attempts: tuple[FinalizedAttemptEvidence, ...],
    ) -> None:
        if type(finalized_attempts) is not tuple:
            raise TypeError("finalized_attempts must be tuple")
        if type(attempt_hashes) is not tuple:
            raise TypeError("attempt_hashes must be tuple")
        by_attempt = {
            value.attempt.attempt_id: value for value in attempt_hashes
        }
        if len(by_attempt) != len(attempt_hashes):
            raise _AttemptEvidenceInvalid("Attempt execution hashes are not unique")
        supplied: set[str] = set()
        writer = AttemptEvidenceWriter(root=self._root)
        for finalized in finalized_attempts:
            verification = writer.verify(finalized)
            if verification.finalized is None:
                raise _AttemptEvidenceInvalid(
                    "finalized Attempt evidence verification failed"
                )
            attempt_id = finalized.attempt.attempt_id
            supplied.add(attempt_id)
            try:
                _validate_execution_evidence_binding(
                    by_attempt[attempt_id],
                    finalized,
                )
            except (KeyError, TypeError, ValueError) as error:
                raise _AttemptEvidenceInvalid(
                    "Attempt execution hash verification failed"
                ) from error
        try:
            eligible = self._eligible_attempt_ids(semantic_run_id)
        except (OSError, TypeError, ValueError, KeyError) as error:
            raise _AttemptEvidenceInvalid(
                "eligible Attempt evidence could not be read"
            ) from error
        if supplied != eligible:
            raise _AttemptSetMismatch(
                "eligible Attempt set was not exact-covered"
            )

    def _eligible_attempt_ids(self, semantic_run_id: str) -> set[str]:
        attempts = self._root / "runs" / semantic_run_id / "attempts"
        if not attempts.is_dir():
            return set()
        eligible: set[str] = set()
        for directory in attempts.iterdir():
            if directory.name == ".staging" or not directory.is_dir():
                continue
            source = (directory / "evidence-manifest.json").read_bytes()
            try:
                decoded = json.loads(source)
            except json.JSONDecodeError as error:
                raise ValueError("Attempt manifest is not valid JSON") from error
            envelope = ArtifactEnvelope(**decoded)
            if source != canonical_bytes(envelope):
                raise ValueError("evidence manifest source is not canonical")
            if envelope.artifact_type != "evidence_manifest":
                raise ValueError("Attempt manifest artifact type mismatch")
            payload = envelope.payload
            if payload["semantic_run_id"] != semantic_run_id:
                raise ValueError("Attempt manifest semantic run mismatch")
            if payload["status"] == EvidencePublicationStatus.READY_FOR_INTEGRITY.value:
                eligible.add(payload["attempt_id"])
        return eligible

    def _publish_directory(
        self,
        *,
        semantic_run_id: str,
        publication_kind: str,
        publication_id: str,
        relative_directory: str,
        plans: tuple[_PublicationPlan, ...],
    ) -> _PublishedDirectory | CanonicalPublicationFailure:
        final = self._root / relative_directory
        staging = final.with_name(f".{final.name}.staging")
        if os.path.lexists(final):
            return self._failure(
                semantic_run_id,
                CanonicalPublicationFailureCode.FINAL_DESTINATION_EXISTS,
                relative_directory,
            )
        if os.path.lexists(staging):
            return self._failure(
                semantic_run_id,
                CanonicalPublicationFailureCode.STAGING_EXISTS,
                str(PurePosixPath(relative_directory).with_name(staging.name)),
            )
        try:
            ensure_directory(final.parent)
            staging.mkdir(parents=False, exist_ok=False)
        except OSError as error:
            return self._failure(
                semantic_run_id,
                CanonicalPublicationFailureCode.STAGING_PREPARE_FAILED,
                relative_directory,
                error,
            )
        entries: list[_PublicationArtifactEntry] = []
        payloads: dict[str, object] = {}
        try:
            for plan in plans:
                result = _PUBLICATION_CATALOG.write_version(
                    plan.artifact_type,
                    plan.schema_version,
                    plan.payload,
                )
                self._write_file(staging / plan.relative_path, result.source_bytes)
                entries.append(
                    _PublicationArtifactEntry(
                        plan.relative_path,
                        plan.artifact_type,
                        result.envelope.schema_version,
                        result.envelope.content_hash,
                        result.source_hash,
                        len(result.source_bytes),
                    )
                )
                payloads[plan.relative_path] = plan.payload
        except (OSError, TypeError, ValueError) as error:
            self._force_remove(staging)
            return self._failure(
                semantic_run_id,
                CanonicalPublicationFailureCode.ARTIFACT_WRITE_FAILED,
                relative_directory,
                error,
            )
        try:
            manifest = CanonicalPublicationManifest(
                semantic_run_id,
                publication_kind,
                publication_id,
                tuple(entries),
            )
            result = _PUBLICATION_CATALOG.write_version(
                "canonical_publication_manifest",
                1,
                manifest,
            )
            self._write_file(
                staging / "publication-manifest.json",
                result.source_bytes,
            )
        except (OSError, TypeError, ValueError) as error:
            self._force_remove(staging)
            return self._failure(
                semantic_run_id,
                CanonicalPublicationFailureCode.MANIFEST_WRITE_FAILED,
                relative_directory,
                error,
            )
        try:
            self._verify_directory(staging, manifest, result.source_hash, payloads)
        except (OSError, TypeError, ValueError, KeyError) as error:
            self._force_remove(staging)
            return self._failure(
                semantic_run_id,
                CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED,
                relative_directory,
                error,
            )
        try:
            self._prepare_read_only_directory(staging)
        except OSError as error:
            self._force_remove(staging)
            return self._failure(
                semantic_run_id,
                CanonicalPublicationFailureCode.IMMUTABILITY_FAILED,
                relative_directory,
                error,
            )
        try:
            staging.rename(final)
            self._verify_read_only(final)
        except OSError as error:
            if os.path.lexists(final):
                if not self._hide_and_remove(final):
                    self._verify_directory(
                        final, manifest, result.source_hash, payloads
                    )
                    self._verify_read_only(final)
                    raise RuntimeError("publication rollback could not hide final")
                else:
                    return self._failure(
                        semantic_run_id,
                        CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                        relative_directory,
                        error,
                    )
            else:
                self._force_remove(staging)
                return self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                    relative_directory,
                    error,
                )
        try:
            self._fsync_directory(final.parent)
        except OSError as error:
            if self._hide_and_remove(final):
                with suppress(OSError):
                    self._fsync_directory(final.parent)
                return self._failure(
                    semantic_run_id,
                    CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                    relative_directory,
                    error,
                )
            self._verify_directory(final, manifest, result.source_hash, payloads)
            self._verify_read_only(final)
            raise RuntimeError("publication rollback could not hide final")
        return _PublishedDirectory(manifest, result.source_hash, relative_directory)

    _write_file = staticmethod(write_file)
    _prepare_read_only_directory = staticmethod(prepare_read_only_directory)

    @staticmethod
    def _verify_directory(
        directory: Path,
        manifest: CanonicalPublicationManifest,
        manifest_source_hash: str,
        payloads: dict[str, object],
    ) -> None:
        expected = {
            *(value.relative_path for value in manifest.artifacts),
            "publication-manifest.json",
        }
        actual = {value.name for value in directory.iterdir() if value.is_file()}
        if actual != expected or any(not value.is_file() for value in directory.iterdir()):
            raise ValueError("publication directory does not exact-cover manifest")
        for entry in manifest.artifacts:
            source = (directory / entry.relative_path).read_bytes()
            result = _PUBLICATION_CATALOG.read(source)
            if result.envelope.artifact_type != entry.artifact_type:
                raise ValueError("artifact type does not match publication manifest")
            if result.envelope.content_hash != entry.content_hash:
                raise ValueError("artifact content hash does not match publication manifest")
            if result.source_hash != entry.source_hash or len(source) != entry.byte_count:
                raise ValueError("artifact source does not match publication manifest")
            if canonical_sha256(result.artifact) != canonical_sha256(
                payloads[entry.relative_path]
            ):
                raise ValueError("artifact payload does not match publication")
        source = (directory / "publication-manifest.json").read_bytes()
        result = _PUBLICATION_CATALOG.read(source)
        if result.source_hash != manifest_source_hash:
            raise ValueError("manifest source hash does not match publication")
        if canonical_sha256(result.artifact) != canonical_sha256(manifest):
            raise ValueError("manifest payload does not match publication")

    _verify_read_only = staticmethod(verify_read_only)
    _fsync_directory = staticmethod(fsync_directory)
    _force_remove = staticmethod(force_remove)
    _hide_and_remove = staticmethod(hide_and_remove)

    @staticmethod
    def _failure(
        semantic_run_id: str,
        code: CanonicalPublicationFailureCode,
        relative_subject: str,
        error: BaseException | None = None,
    ) -> CanonicalPublicationFailure:
        failure = CanonicalPublicationFailure(
            semantic_run_id,
            code,
            relative_subject,
            (
                f"{type(error).__module__}.{type(error).__qualname__}"
                if error is not None
                else None
            ),
        )
        return failure


__all__ = [
    "AttemptConsistencySet",
    "CanonicalAttemptRef",
    "CanonicalPublicationFailure",
    "CanonicalPublicationFailureCode",
    "CanonicalPublicationManifest",
    "CanonicalPublicationOutcome",
    "CanonicalPublicationOutcomeV2",
    "CanonicalResultPublisher",
    "CompletedBacktestResult",
    "CompletedBacktestResultV2",
    "DeterministicRebuildEvidence",
    "EngineExecutionContext",
    "FinalizedCanonicalResult",
    "FinalizedCanonicalResultV2",
    "FinalizedIntegrityEvaluation",
    "IntegrityEvaluationContext",
    "IntegrityEvaluationRecord",
    "IntegrityEvaluator",
    "IntegrityIssue",
    "IntegrityIssueCode",
    "IntegrityIssueSeverity",
    "IntegrityReport",
    "IntegrityTraceLevel",
    "ResultGrade",
]
