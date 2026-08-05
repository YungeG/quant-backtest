"""Canonical Attempt evidence staging and atomic local publication."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path, PurePosixPath
import re
from typing import Final

from crypto_quant_domain import (
    ArtifactSchemaRegistration,
    CanonicalSchema,
    SchemaCatalog,
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
    prepare_read_only_directory,
    verify_read_only,
    write_file,
)
from .runner import (
    AttemptExecutionRecord,
    AttemptExecutionStatus,
    AttemptIdentity,
    BacktestRunOutcome,
)


_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")
_ATTEMPT_PATTERN = re.compile(r"attempt_[0-9a-f]{64}")


def _relative_path(name: str, value: object) -> str:
    text = _text(name, value)
    if "\\" in text:
        raise ValueError(f"{name} must use POSIX separators")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{name} must be canonical relative path")
    return text


def _exception_type(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


class EvidenceArtifactRole(str, Enum):
    REQUEST = "request"
    ENVIRONMENT = "environment"
    BUILD_ARTIFACT_MANIFEST = "build_artifact_manifest"
    MARKET_BUNDLE_REFERENCE = "market_bundle_reference"
    ENVIRONMENT_COMPATIBILITY = "environment_compatibility"
    ATTEMPT_EXECUTION_RECORD = "attempt_execution_record"
    ENGINE_EXECUTION_RESULT = "engine_execution_result"
    BLOCKED_REPORT = "blocked_report"
    FAILURE_REPORT = "failure_report"
    CANCELLATION_REPORT = "cancellation_report"


class EvidencePublicationStatus(str, Enum):
    READY_FOR_INTEGRITY = "READY_FOR_INTEGRITY"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EvidenceWriteFailureCode(str, Enum):
    RUN_LOCK_UNAVAILABLE = "run_lock_unavailable"
    SEMANTIC_RUN_CLOSED = "semantic_run_closed"
    STAGING_PREPARE_FAILED = "staging_prepare_failed"
    STAGING_EXISTS = "staging_exists"
    FINAL_DESTINATION_EXISTS = "final_destination_exists"
    ARTIFACT_WRITE_FAILED = "artifact_write_failed"
    MANIFEST_WRITE_FAILED = "manifest_write_failed"
    EVIDENCE_VERIFICATION_FAILED = "evidence_verification_failed"
    IMMUTABILITY_FAILED = "immutability_failed"
    ATOMIC_FINALIZE_FAILED = "atomic_finalize_failed"


@dataclass(frozen=True, slots=True)
class EvidenceArtifactEntry:
    relative_path: str
    role: EvidenceArtifactRole
    artifact_type: str
    schema_version: int
    content_hash: str
    source_hash: str
    byte_count: int

    def __post_init__(self) -> None:
        _relative_path("relative_path", self.relative_path)
        if not isinstance(self.role, EvidenceArtifactRole):
            raise TypeError("role must be EvidenceArtifactRole")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("evidence artifact schema_version must be 1")
        CanonicalSchema(self.artifact_type, self.schema_version)
        _hash("content_hash", self.content_hash)
        _hash("source_hash", self.source_hash)
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise ValueError("byte_count must be positive integer")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "role": self.role.value,
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "content_hash": self.content_hash,
            "source_hash": self.source_hash,
            "byte_count": self.byte_count,
        }


_COMMON_ROLES: Final[frozenset[EvidenceArtifactRole]] = frozenset(
    {
        EvidenceArtifactRole.REQUEST,
        EvidenceArtifactRole.ENVIRONMENT,
        EvidenceArtifactRole.BUILD_ARTIFACT_MANIFEST,
        EvidenceArtifactRole.MARKET_BUNDLE_REFERENCE,
        EvidenceArtifactRole.ENVIRONMENT_COMPATIBILITY,
        EvidenceArtifactRole.ATTEMPT_EXECUTION_RECORD,
    }
)
_BRANCH_ROLE: Final[dict[EvidencePublicationStatus, EvidenceArtifactRole]] = {
    EvidencePublicationStatus.READY_FOR_INTEGRITY: EvidenceArtifactRole.ENGINE_EXECUTION_RESULT,
    EvidencePublicationStatus.BLOCKED: EvidenceArtifactRole.BLOCKED_REPORT,
    EvidencePublicationStatus.FAILED: EvidenceArtifactRole.FAILURE_REPORT,
    EvidencePublicationStatus.CANCELLED: EvidenceArtifactRole.CANCELLATION_REPORT,
}
_STATUS_OUTCOME: Final[
    dict[EvidencePublicationStatus, BacktestRunOutcome | None]
] = {
    EvidencePublicationStatus.READY_FOR_INTEGRITY: None,
    EvidencePublicationStatus.BLOCKED: BacktestRunOutcome.BLOCKED,
    EvidencePublicationStatus.FAILED: BacktestRunOutcome.FAILED,
    EvidencePublicationStatus.CANCELLED: BacktestRunOutcome.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    semantic_run_id: str
    attempt_id: str
    status: EvidencePublicationStatus
    terminal_outcome: BacktestRunOutcome | None
    artifacts: tuple[EvidenceArtifactEntry, ...]
    market_bundle_ref_hash: str
    attempt_record_hash: str
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if _RUN_PATTERN.fullmatch(self.semantic_run_id) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if _ATTEMPT_PATTERN.fullmatch(self.attempt_id) is None:
            raise ValueError("attempt_id must use attempt_sha256 schema")
        if not isinstance(self.status, EvidencePublicationStatus):
            raise TypeError("status must be EvidencePublicationStatus")
        if self.terminal_outcome is not _STATUS_OUTCOME[self.status]:
            raise ValueError("terminal_outcome does not match publication status")
        if type(self.artifacts) is not tuple or not all(
            isinstance(value, EvidenceArtifactEntry) for value in self.artifacts
        ):
            raise TypeError("artifacts must contain EvidenceArtifactEntry")
        ordered = tuple(sorted(self.artifacts, key=lambda value: value.relative_path))
        paths = tuple(value.relative_path for value in ordered)
        roles = tuple(value.role for value in ordered)
        if len(set(paths)) != len(paths):
            raise ValueError("evidence artifact paths must be unique")
        if len(set(roles)) != len(roles):
            raise ValueError("evidence artifact roles must be unique")
        expected_roles = _COMMON_ROLES | {_BRANCH_ROLE[self.status]}
        if frozenset(roles) != expected_roles:
            raise ValueError("evidence artifacts do not exactly cover status roles")
        object.__setattr__(self, "artifacts", ordered)
        _hash("market_bundle_ref_hash", self.market_bundle_ref_hash)
        _hash("attempt_record_hash", self.attempt_record_hash)
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("Attempt evidence never authorizes deployment")

    def _identity_dict(self) -> dict[str, object]:
        return {
            "type": "evidence_manifest_identity",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "attempt_id": self.attempt_id,
            "status": self.status.value,
            "terminal_outcome": (
                self.terminal_outcome.value
                if self.terminal_outcome is not None
                else None
            ),
            "artifacts": self.artifacts,
            "market_bundle_ref_hash": self.market_bundle_ref_hash,
            "attempt_record_hash": self.attempt_record_hash,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self._identity_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            **self._identity_dict(),
            "manifest_hash": self.manifest_hash,
        }


@dataclass(frozen=True, slots=True)
class FinalizedAttemptEvidence:
    attempt: AttemptIdentity
    status: EvidencePublicationStatus
    terminal_outcome: BacktestRunOutcome | None
    manifest: EvidenceManifest
    manifest_source_hash: str
    relative_directory: str
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, AttemptIdentity):
            raise TypeError("attempt must be AttemptIdentity")
        if not isinstance(self.status, EvidencePublicationStatus):
            raise TypeError("status must be EvidencePublicationStatus")
        if self.terminal_outcome is not _STATUS_OUTCOME[self.status]:
            raise ValueError("terminal_outcome does not match publication status")
        if not isinstance(self.manifest, EvidenceManifest):
            raise TypeError("manifest must be EvidenceManifest")
        if self.manifest.semantic_run_id != self.attempt.semantic_run_id:
            raise ValueError("manifest semantic run does not match Attempt")
        if self.manifest.attempt_id != self.attempt.attempt_id:
            raise ValueError("manifest Attempt ID does not match Attempt")
        if self.manifest.status is not self.status:
            raise ValueError("manifest status does not match finalized evidence")
        if self.manifest.terminal_outcome is not self.terminal_outcome:
            raise ValueError("manifest outcome does not match finalized evidence")
        _hash("manifest_source_hash", self.manifest_source_hash)
        expected_directory = (
            f"runs/{self.attempt.semantic_run_id}/attempts/{self.attempt.attempt_id}"
        )
        if self.relative_directory != expected_directory:
            raise ValueError("relative_directory does not match Attempt layout")
        _relative_path("relative_directory", self.relative_directory)
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("Attempt evidence never authorizes deployment")

    @property
    def publication_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "finalized_attempt_evidence",
            "schema_version": 1,
            "attempt": self.attempt,
            "status": self.status.value,
            "terminal_outcome": (
                self.terminal_outcome.value
                if self.terminal_outcome is not None
                else None
            ),
            "manifest_hash": self.manifest.manifest_hash,
            "manifest_source_hash": self.manifest_source_hash,
            "relative_directory": self.relative_directory,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class EvidenceWriteFailure:
    attempt: AttemptIdentity
    code: EvidenceWriteFailureCode
    relative_subject: str
    exception_type: str | None
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, AttemptIdentity):
            raise TypeError("attempt must be AttemptIdentity")
        if not isinstance(self.code, EvidenceWriteFailureCode):
            raise TypeError("code must be EvidenceWriteFailureCode")
        _relative_path("relative_subject", self.relative_subject)
        if self.exception_type is not None:
            _text("exception_type", self.exception_type)
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("evidence failure never authorizes deployment")

    @property
    def outcome(self) -> BacktestRunOutcome:
        return BacktestRunOutcome.FAILED

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "evidence_write_failure",
            "schema_version": 1,
            "attempt": self.attempt,
            "code": self.code.value,
            "relative_subject": self.relative_subject,
            "exception_type": self.exception_type,
            "outcome": self.outcome.value,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class EvidencePublicationOutcome:
    finalized: FinalizedAttemptEvidence | None = None
    failure: EvidenceWriteFailure | None = None

    def __post_init__(self) -> None:
        if (self.finalized is None) == (self.failure is None):
            raise ValueError("evidence publication requires exactly one branch")
        if self.finalized is not None and not isinstance(
            self.finalized, FinalizedAttemptEvidence
        ):
            raise TypeError("finalized must be FinalizedAttemptEvidence")
        if self.failure is not None and not isinstance(
            self.failure, EvidenceWriteFailure
        ):
            raise TypeError("failure must be EvidenceWriteFailure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "evidence_publication_outcome",
            "finalized": self.finalized,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class _ArtifactPlan:
    relative_path: str
    role: EvidenceArtifactRole
    artifact_type: str
    payload: object


_ARTIFACT_CATALOG = SchemaCatalog(
    ArtifactSchemaRegistration(artifact_type, 1, lambda payload: payload)
    for artifact_type in (
        "attempt_execution_record",
        "backtest_request",
        "blocked_run_report",
        "build_artifact_manifest",
        "cancellation_report",
        "engine_execution_result",
        "environment_compatibility_report",
        "evidence_manifest",
        "failure_report",
        "market_bundle_ref",
        "resolved_backtest_environment",
    )
)


@dataclass(frozen=True, slots=True)
class _EvidencePaths:
    attempts: Path
    staging: Path
    final: Path
    attempts_relative: str
    staging_relative: str
    final_relative: str


class AttemptEvidenceWriter:
    """Publish one immutable local Attempt evidence directory."""

    def __init__(self, *, root: Path) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be pathlib.Path")
        self._root = root

    def publish(self, record: AttemptExecutionRecord) -> EvidencePublicationOutcome:
        if not isinstance(record, AttemptExecutionRecord):
            raise TypeError("record must be AttemptExecutionRecord")
        attempt = record.attempt
        try:
            with RunPublicationLock(
                root=self._root,
                semantic_run_id=attempt.semantic_run_id,
            ):
                canonical = (
                    self._root
                    / "runs"
                    / attempt.semantic_run_id
                    / "canonical"
                )
                if os.path.lexists(canonical):
                    return self._failure(
                        attempt,
                        EvidenceWriteFailureCode.SEMANTIC_RUN_CLOSED,
                        f"runs/{attempt.semantic_run_id}/canonical",
                    )
                return self._publish_locked(record)
        except FileExistsError as error:
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.RUN_LOCK_UNAVAILABLE,
                f"runs/{attempt.semantic_run_id}/.publication.lock",
                error,
            )
        except OSError as error:
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.STAGING_PREPARE_FAILED,
                f"runs/{attempt.semantic_run_id}/attempts",
                error,
            )

    def _publish_locked(
        self, record: AttemptExecutionRecord
    ) -> EvidencePublicationOutcome:
        attempt = record.attempt
        paths = self._paths(attempt)
        try:
            ensure_directory(paths.attempts)
        except OSError as error:
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.STAGING_PREPARE_FAILED,
                paths.attempts_relative,
                error,
            )
        if os.path.lexists(paths.final):
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.FINAL_DESTINATION_EXISTS,
                paths.final_relative,
            )
        if os.path.lexists(paths.staging):
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.STAGING_EXISTS,
                paths.staging_relative,
            )
        try:
            paths.staging.mkdir(parents=True, exist_ok=False)
        except OSError as error:
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.STAGING_PREPARE_FAILED,
                paths.staging_relative,
                error,
            )

        status = self._status(record)
        entries: list[EvidenceArtifactEntry] = []
        for plan in self._artifact_plans(record):
            try:
                result = _ARTIFACT_CATALOG.write_current(
                    plan.artifact_type, plan.payload
                )
                self._write_file(
                    paths.staging / plan.relative_path, result.source_bytes
                )
            except (OSError, TypeError, ValueError) as error:
                self._force_remove(paths.staging)
                return self._failure(
                    attempt,
                    EvidenceWriteFailureCode.ARTIFACT_WRITE_FAILED,
                    plan.relative_path,
                    error,
                )
            entries.append(
                EvidenceArtifactEntry(
                    relative_path=plan.relative_path,
                    role=plan.role,
                    artifact_type=plan.artifact_type,
                    schema_version=result.envelope.schema_version,
                    content_hash=result.envelope.content_hash,
                    source_hash=result.source_hash,
                    byte_count=len(result.source_bytes),
                )
            )

        try:
            manifest = EvidenceManifest(
                semantic_run_id=attempt.semantic_run_id,
                attempt_id=attempt.attempt_id,
                status=status,
                terminal_outcome=record.terminal_outcome,
                artifacts=tuple(entries),
                market_bundle_ref_hash=canonical_sha256(
                    record.resolved_request.environment.market_bundle_ref
                ),
                attempt_record_hash=canonical_sha256(record),
            )
            manifest_result = _ARTIFACT_CATALOG.write_current(
                "evidence_manifest", manifest
            )
            self._write_file(
                paths.staging / "evidence-manifest.json",
                manifest_result.source_bytes,
            )
        except (OSError, TypeError, ValueError) as error:
            self._force_remove(paths.staging)
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.MANIFEST_WRITE_FAILED,
                f"{paths.staging_relative}/evidence-manifest.json",
                error,
            )

        try:
            self._verify_directory(
                paths.staging, manifest, manifest_result.source_hash
            )
        except (OSError, TypeError, ValueError) as error:
            self._force_remove(paths.staging)
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.EVIDENCE_VERIFICATION_FAILED,
                paths.staging_relative,
                error,
            )
        try:
            self._prepare_read_only_directory(paths.staging)
        except OSError as error:
            self._force_remove(paths.staging)
            return self._failure(
                attempt,
                EvidenceWriteFailureCode.IMMUTABILITY_FAILED,
                paths.staging_relative,
                error,
            )
        try:
            # Cooperative readers hold the run lock; this filesystem requires
            # the source directory writable for rename.
            paths.staging.chmod(0o755)
            paths.staging.rename(paths.final)
            paths.final.chmod(0o555)
            self._verify_read_only(paths.final)
        except OSError as error:
            if os.path.lexists(paths.final):
                if not self._hide_and_remove(paths.final):
                    self._verify_directory(
                        paths.final, manifest, manifest_result.source_hash
                    )
                    self._verify_read_only(paths.final)
                    raise RuntimeError("Attempt publication rollback could not hide final")
                else:
                    return self._failure(
                        attempt,
                        EvidenceWriteFailureCode.ATOMIC_FINALIZE_FAILED,
                        paths.final_relative,
                        error,
                    )
            else:
                self._force_remove(paths.staging)
                return self._failure(
                    attempt,
                    EvidenceWriteFailureCode.ATOMIC_FINALIZE_FAILED,
                    paths.final_relative,
                    error,
                )
        try:
            self._fsync_directory(paths.attempts)
        except OSError as error:
            if self._hide_and_remove(paths.final):
                with suppress(OSError):
                    self._fsync_directory(paths.attempts)
                return self._failure(
                    attempt,
                    EvidenceWriteFailureCode.ATOMIC_FINALIZE_FAILED,
                    paths.final_relative,
                    error,
                )
            self._verify_directory(
                paths.final, manifest, manifest_result.source_hash
            )
            self._verify_read_only(paths.final)
            raise RuntimeError("Attempt publication rollback could not hide final")

        finalized = FinalizedAttemptEvidence(
            attempt=attempt,
            status=status,
            terminal_outcome=record.terminal_outcome,
            manifest=manifest,
            manifest_source_hash=manifest_result.source_hash,
            relative_directory=paths.final_relative,
        )
        return EvidencePublicationOutcome(finalized=finalized)

    def verify(
        self, finalized: FinalizedAttemptEvidence
    ) -> EvidencePublicationOutcome:
        if not isinstance(finalized, FinalizedAttemptEvidence):
            raise TypeError("finalized must be FinalizedAttemptEvidence")
        directory = self._root / finalized.relative_directory
        try:
            self._verify_directory(
                directory, finalized.manifest, finalized.manifest_source_hash
            )
            self._verify_read_only(directory)
        except (OSError, TypeError, ValueError) as error:
            return self._failure(
                finalized.attempt,
                EvidenceWriteFailureCode.EVIDENCE_VERIFICATION_FAILED,
                finalized.relative_directory,
                error,
            )
        return EvidencePublicationOutcome(finalized=finalized)

    @staticmethod
    def _status(record: AttemptExecutionRecord) -> EvidencePublicationStatus:
        return {
            AttemptExecutionStatus.READY_TO_FINALIZE: EvidencePublicationStatus.READY_FOR_INTEGRITY,
            AttemptExecutionStatus.BLOCKED: EvidencePublicationStatus.BLOCKED,
            AttemptExecutionStatus.FAILED: EvidencePublicationStatus.FAILED,
            AttemptExecutionStatus.CANCELLED: EvidencePublicationStatus.CANCELLED,
        }[record.status]

    def _paths(self, attempt: AttemptIdentity) -> _EvidencePaths:
        run_relative = PurePosixPath("runs") / attempt.semantic_run_id
        attempts_relative = run_relative / "attempts"
        staging_relative = attempts_relative / ".staging" / attempt.attempt_id
        final_relative = attempts_relative / attempt.attempt_id
        return _EvidencePaths(
            attempts=self._root / Path(str(attempts_relative)),
            staging=self._root / Path(str(staging_relative)),
            final=self._root / Path(str(final_relative)),
            attempts_relative=str(attempts_relative),
            staging_relative=str(staging_relative),
            final_relative=str(final_relative),
        )

    @staticmethod
    def _failure(
        attempt: AttemptIdentity,
        code: EvidenceWriteFailureCode,
        relative_subject: str,
        error: BaseException | None = None,
    ) -> EvidencePublicationOutcome:
        return EvidencePublicationOutcome(
            failure=EvidenceWriteFailure(
                attempt=attempt,
                code=code,
                relative_subject=relative_subject,
                exception_type=_exception_type(error) if error is not None else None,
            )
        )

    @staticmethod
    def _artifact_plans(record: AttemptExecutionRecord) -> tuple[_ArtifactPlan, ...]:
        resolved = record.resolved_request
        plans = [
            _ArtifactPlan(
                "request.json",
                EvidenceArtifactRole.REQUEST,
                "backtest_request",
                resolved.request,
            ),
            _ArtifactPlan(
                "environment.json",
                EvidenceArtifactRole.ENVIRONMENT,
                "resolved_backtest_environment",
                resolved.environment,
            ),
            _ArtifactPlan(
                "build-artifact-manifest.json",
                EvidenceArtifactRole.BUILD_ARTIFACT_MANIFEST,
                "build_artifact_manifest",
                resolved.build_artifact_manifest,
            ),
            _ArtifactPlan(
                "market-bundle-ref.json",
                EvidenceArtifactRole.MARKET_BUNDLE_REFERENCE,
                "market_bundle_ref",
                resolved.environment.market_bundle_ref,
            ),
            _ArtifactPlan(
                "environment-compatibility-report.json",
                EvidenceArtifactRole.ENVIRONMENT_COMPATIBILITY,
                "environment_compatibility_report",
                resolved.environment.compatibility_report,
            ),
            _ArtifactPlan(
                "attempt-execution-record.json",
                EvidenceArtifactRole.ATTEMPT_EXECUTION_RECORD,
                "attempt_execution_record",
                record,
            ),
        ]
        if record.ready_to_finalize is not None:
            plans.append(
                _ArtifactPlan(
                    "engine-execution-result.json",
                    EvidenceArtifactRole.ENGINE_EXECUTION_RESULT,
                    "engine_execution_result",
                    record.ready_to_finalize.engine_result,
                )
            )
        elif record.blocked_report is not None:
            plans.append(
                _ArtifactPlan(
                    "blocked-run-report.json",
                    EvidenceArtifactRole.BLOCKED_REPORT,
                    "blocked_run_report",
                    record.blocked_report,
                )
            )
        elif record.failed_report is not None:
            plans.append(
                _ArtifactPlan(
                    "failure-report.json",
                    EvidenceArtifactRole.FAILURE_REPORT,
                    "failure_report",
                    record.failed_report,
                )
            )
        else:
            plans.append(
                _ArtifactPlan(
                    "cancellation-report.json",
                    EvidenceArtifactRole.CANCELLATION_REPORT,
                    "cancellation_report",
                    record.cancelled_report,
                )
            )
        return tuple(sorted(plans, key=lambda value: value.relative_path))

    _write_file = staticmethod(write_file)

    @staticmethod
    def _verify_directory(
        directory: Path,
        manifest: EvidenceManifest,
        manifest_source_hash: str,
    ) -> None:
        if not directory.is_dir():
            raise ValueError("evidence directory is missing")
        expected_paths = {
            *(entry.relative_path for entry in manifest.artifacts),
            "evidence-manifest.json",
        }
        actual_paths = {
            path.name for path in directory.iterdir() if path.is_file()
        }
        if actual_paths != expected_paths or any(
            not path.is_file() for path in directory.iterdir()
        ):
            raise ValueError("evidence directory does not exactly match manifest")
        for entry in manifest.artifacts:
            source = (directory / entry.relative_path).read_bytes()
            result = _ARTIFACT_CATALOG.read(source)
            if result.envelope.artifact_type != entry.artifact_type:
                raise ValueError("artifact type does not match manifest")
            if result.envelope.schema_version != entry.schema_version:
                raise ValueError("artifact schema does not match manifest")
            if result.envelope.content_hash != entry.content_hash:
                raise ValueError("artifact content hash does not match manifest")
            if result.source_hash != entry.source_hash:
                raise ValueError("artifact source hash does not match manifest")
            if len(source) != entry.byte_count:
                raise ValueError("artifact byte count does not match manifest")
        manifest_source = (directory / "evidence-manifest.json").read_bytes()
        manifest_result = _ARTIFACT_CATALOG.read(manifest_source)
        if manifest_result.source_hash != manifest_source_hash:
            raise ValueError("manifest source hash does not match publication")
        if canonical_sha256(manifest_result.artifact) != canonical_sha256(manifest):
            raise ValueError("manifest payload does not match publication")

    _prepare_read_only_directory = staticmethod(prepare_read_only_directory)
    _verify_read_only = staticmethod(verify_read_only)
    _fsync_directory = staticmethod(fsync_directory)
    _force_remove = staticmethod(force_remove)
    _hide_and_remove = staticmethod(hide_and_remove)


__all__ = [
    "AttemptEvidenceWriter",
    "EvidenceArtifactEntry",
    "EvidenceArtifactRole",
    "EvidenceManifest",
    "EvidencePublicationOutcome",
    "EvidencePublicationStatus",
    "EvidenceWriteFailure",
    "EvidenceWriteFailureCode",
    "FinalizedAttemptEvidence",
]
