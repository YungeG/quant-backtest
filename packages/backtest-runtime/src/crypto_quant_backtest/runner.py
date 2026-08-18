"""Auditable Attempt execution and pre-publication outcome mapping."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Protocol
import unicodedata

from crypto_quant_domain import ArtifactEnvelope, canonical_bytes, canonical_sha256
from crypto_quant_market_data import InputValidationFailure

from ._publication import RunPublicationLock, verify_read_only
from .composition import (
    ExecutionCaseComposer,
    _execution_case_semantic_spec_from_case_v3,
)
from .engine import (
    DeterministicBarEngine,
    EngineCancellation,
    EngineCancellationRequest,
    EngineExecutionOutcome,
    EngineExecutionResult,
    EngineFailure,
    EngineFailureCode,
    ResolvedExecutionCase,
)
from .multi_resolution_preparation import MultiResolutionMarketDataPreparation
from .resolution import ResolvedBacktestRequest, StrategyFamily


_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")
_ATTEMPT_PATTERN = re.compile(r"attempt_[0-9a-f]{64}")


def _text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256 identity")
    return value


def _canonical_texts(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    checked = tuple(sorted(_text(name, value) for value in values))
    if len(set(checked)) != len(checked):
        raise ValueError(f"{name} must be unique")
    return checked


def _canonical_hashes(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    checked = tuple(sorted(_hash(name, value) for value in values))
    if len(set(checked)) != len(checked):
        raise ValueError(f"{name} must be unique")
    return checked


def _source_hash(source: bytes) -> str:
    return f"sha256:{hashlib.sha256(source).hexdigest()}"


def _read_canonical_artifact(
    path: Path,
    expected_artifact_type: str,
) -> tuple[dict[str, object], ArtifactEnvelope, str]:
    source = path.read_bytes()
    try:
        decoded = json.loads(source)
    except json.JSONDecodeError as error:
        raise ValueError("canonical artifact is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("canonical artifact must be a JSON object")
    envelope = ArtifactEnvelope(**decoded)
    if source != canonical_bytes(envelope):
        raise ValueError("canonical artifact source bytes are not canonical")
    if envelope.artifact_type != expected_artifact_type:
        raise ValueError("canonical artifact type mismatch")
    return dict(envelope.payload), envelope, _source_hash(source)


class InputOrigin(str, Enum):
    PRECOMPUTED_TARGET_STREAM = "precomputed_target_stream"
    RUNTIME_STRATEGY = "runtime_strategy"


class BacktestRunOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptExecutionStatus(str, Enum):
    CACHE_HIT = "CACHE_HIT"
    READY_TO_FINALIZE = "READY_TO_FINALIZE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptIssueSource(str, Enum):
    INPUT_VALIDATION = "input_validation"
    ENGINE_FAILURE = "engine_failure"
    RUNNER_CONTRACT = "runner_contract"
    ENGINE_EXCEPTION = "engine_exception"


@dataclass(frozen=True, slots=True)
class AttemptIdentity:
    semantic_run_id: str
    ordinal: int
    parent_attempt_id: str | None
    attempt_id: str

    def __post_init__(self) -> None:
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if type(self.ordinal) is not int or self.ordinal <= 0:
            raise ValueError("ordinal must be positive integer")
        if self.ordinal == 1 and self.parent_attempt_id is not None:
            raise ValueError("first Attempt cannot have a parent")
        if self.ordinal > 1:
            if (
                type(self.parent_attempt_id) is not str
                or _ATTEMPT_PATTERN.fullmatch(self.parent_attempt_id) is None
            ):
                raise ValueError("retry Attempt requires canonical parent_attempt_id")
        expected = self._derive_id(
            self.semantic_run_id, self.ordinal, self.parent_attempt_id
        )
        if self.attempt_id != expected:
            raise ValueError(
                "attempt_id does not match semantic run, ordinal, and parent"
            )

    @classmethod
    def first(cls, semantic_run_id: str) -> AttemptIdentity:
        return cls(
            semantic_run_id=semantic_run_id,
            ordinal=1,
            parent_attempt_id=None,
            attempt_id=cls._derive_id(semantic_run_id, 1, None),
        )

    @classmethod
    def retry(
        cls, previous: AttemptIdentity, *, next_ordinal: int
    ) -> AttemptIdentity:
        if not isinstance(previous, AttemptIdentity):
            raise TypeError("previous must be AttemptIdentity")
        if type(next_ordinal) is not int or next_ordinal <= previous.ordinal:
            raise ValueError("next Attempt ordinal must be greater than previous")
        return cls(
            semantic_run_id=previous.semantic_run_id,
            ordinal=next_ordinal,
            parent_attempt_id=previous.attempt_id,
            attempt_id=cls._derive_id(
                previous.semantic_run_id, next_ordinal, previous.attempt_id
            ),
        )

    @staticmethod
    def _derive_id(
        semantic_run_id: str, ordinal: int, parent_attempt_id: str | None
    ) -> str:
        digest = canonical_sha256(
            {
                "type": "attempt_identity_v1",
                "semantic_run_id": semantic_run_id,
                "ordinal": ordinal,
                "parent_attempt_id": parent_attempt_id,
            }
        )
        return "attempt_" + digest.removeprefix("sha256:")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "attempt_identity",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "ordinal": self.ordinal,
            "parent_attempt_id": self.parent_attempt_id,
            "attempt_id": self.attempt_id,
        }


@dataclass(frozen=True, slots=True)
class AttemptIssue:
    source: AttemptIssueSource
    code: str
    subject_keys: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    source_hash: str
    source_evidence: InputValidationFailure | EngineFailure | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, AttemptIssueSource):
            raise TypeError("source must be AttemptIssueSource")
        _text("code", self.code)
        subjects = _canonical_texts("subject_key", self.subject_keys)
        hashes = _canonical_hashes("evidence_hash", self.evidence_hashes)
        _hash("source_hash", self.source_hash)
        if self.source_evidence is not None:
            if not isinstance(
                self.source_evidence, (InputValidationFailure, EngineFailure)
            ):
                raise TypeError("source_evidence has unsupported type")
            if canonical_sha256(self.source_evidence) != self.source_hash:
                raise ValueError("source_hash does not match source_evidence")
        if self.source is AttemptIssueSource.INPUT_VALIDATION and not isinstance(
            self.source_evidence, InputValidationFailure
        ):
            raise ValueError("input-validation issue requires exact source evidence")
        if self.source is AttemptIssueSource.ENGINE_FAILURE and not isinstance(
            self.source_evidence, EngineFailure
        ):
            raise ValueError("engine-failure issue requires exact source evidence")
        if self.source in {
            AttemptIssueSource.RUNNER_CONTRACT,
            AttemptIssueSource.ENGINE_EXCEPTION,
        } and self.source_evidence is not None:
            raise ValueError("runner issue cannot carry engine/input source evidence")
        object.__setattr__(self, "subject_keys", subjects)
        object.__setattr__(self, "evidence_hashes", hashes)

    @property
    def issue_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "attempt_issue",
            "source": self.source.value,
            "code": self.code,
            "subject_keys": self.subject_keys,
            "evidence_hashes": self.evidence_hashes,
            "source_hash": self.source_hash,
            "source_evidence": self.source_evidence,
        }


def _validate_attempt_context(
    attempt: AttemptIdentity,
    resolved_request: ResolvedBacktestRequest,
    input_origin: InputOrigin,
    execution_case_hash: str,
) -> None:
    if not isinstance(attempt, AttemptIdentity):
        raise TypeError("attempt must be AttemptIdentity")
    if not isinstance(resolved_request, ResolvedBacktestRequest):
        raise TypeError("resolved_request must be ResolvedBacktestRequest")
    if attempt.semantic_run_id != resolved_request.semantic_run_id:
        raise ValueError("Attempt semantic run does not match resolved request")
    if not isinstance(input_origin, InputOrigin):
        raise TypeError("input_origin must be InputOrigin")
    _hash("execution_case_hash", execution_case_hash)


@dataclass(frozen=True, slots=True)
class _AttemptIssueReport:
    attempt: AttemptIdentity
    resolved_request: ResolvedBacktestRequest
    input_origin: InputOrigin
    execution_case_hash: str
    issue: AttemptIssue
    trace_hash: str | None = None

    def __post_init__(self) -> None:
        _validate_attempt_context(
            self.attempt,
            self.resolved_request,
            self.input_origin,
            self.execution_case_hash,
        )
        if not isinstance(self.issue, AttemptIssue):
            raise TypeError("issue must be AttemptIssue")
        if self.trace_hash is not None:
            _hash("trace_hash", self.trace_hash)

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self)

    def _canonical_dict(self, report_type: str) -> dict[str, object]:
        return {
            "type": report_type,
            "attempt": self.attempt,
            "resolved_request": self.resolved_request,
            "input_origin": self.input_origin.value,
            "execution_case_hash": self.execution_case_hash,
            "issue": self.issue,
            "trace_hash": self.trace_hash,
        }


class BlockedAttemptReport(_AttemptIssueReport):
    __slots__ = ()

    def to_canonical_dict(self) -> dict[str, object]:
        return self._canonical_dict("blocked_attempt_report")


class FailedAttemptReport(_AttemptIssueReport):
    __slots__ = ()

    def to_canonical_dict(self) -> dict[str, object]:
        return self._canonical_dict("failed_attempt_report")


@dataclass(frozen=True, slots=True)
class CancelledAttemptReport:
    attempt: AttemptIdentity
    resolved_request: ResolvedBacktestRequest
    input_origin: InputOrigin
    execution_case_hash: str
    cancellation: EngineCancellation

    def __post_init__(self) -> None:
        _validate_attempt_context(
            self.attempt,
            self.resolved_request,
            self.input_origin,
            self.execution_case_hash,
        )
        if not isinstance(self.cancellation, EngineCancellation):
            raise TypeError("cancellation must be EngineCancellation")
        if self.cancellation.case_hash != self.execution_case_hash:
            raise ValueError("cancellation does not match execution case")

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cancelled_attempt_report",
            "attempt": self.attempt,
            "resolved_request": self.resolved_request,
            "input_origin": self.input_origin.value,
            "execution_case_hash": self.execution_case_hash,
            "cancellation": self.cancellation,
        }


@dataclass(frozen=True, slots=True)
class ReadyToFinalizeAttempt:
    attempt: AttemptIdentity
    resolved_request: ResolvedBacktestRequest
    input_origin: InputOrigin
    execution_case_hash: str
    engine_result: EngineExecutionResult

    def __post_init__(self) -> None:
        _validate_attempt_context(
            self.attempt,
            self.resolved_request,
            self.input_origin,
            self.execution_case_hash,
        )
        if not isinstance(self.engine_result, EngineExecutionResult):
            raise TypeError("engine_result must be EngineExecutionResult")
        if self.engine_result.case_hash != self.execution_case_hash:
            raise ValueError("Engine result does not match execution case")
        if (
            self.engine_result.target_stream_digest
            != self.resolved_request.request.target_stream_digest
        ):
            raise ValueError("Engine result target stream does not match request")

    @property
    def ready_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "ready_to_finalize_attempt",
            "attempt": self.attempt,
            "resolved_request": self.resolved_request,
            "input_origin": self.input_origin.value,
            "execution_case_hash": self.execution_case_hash,
            "engine_result": self.engine_result,
        }


@dataclass(frozen=True, slots=True)
class CanonicalResultCacheHit:
    canonical_attempt: AttemptIdentity
    resolved_request: ResolvedBacktestRequest
    input_origin: InputOrigin
    execution_case_hash: str
    execution_result_hash: str
    canonical_attempt_ref_hash: str
    integrity_report_hash: str
    result_hash: str
    publication_manifest_hash: str
    publication_manifest_source_hash: str
    result_grade: str
    relative_directory: str
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        _validate_attempt_context(
            self.canonical_attempt,
            self.resolved_request,
            self.input_origin,
            self.execution_case_hash,
        )
        for name in (
            "execution_result_hash",
            "canonical_attempt_ref_hash",
            "integrity_report_hash",
            "result_hash",
            "publication_manifest_hash",
            "publication_manifest_source_hash",
        ):
            _hash(name, getattr(self, name))
        if self.result_grade not in {"development", "decision_grade"}:
            raise ValueError("result_grade is unsupported")
        expected = f"runs/{self.canonical_attempt.semantic_run_id}/canonical"
        expected_v2 = f"runs/{self.canonical_attempt.semantic_run_id}/canonical-v2"
        if self.relative_directory not in {expected, expected_v2}:
            raise ValueError("relative_directory does not match canonical layout")
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("cache hit never authorizes deployment")

    @property
    def outcome(self) -> BacktestRunOutcome:
        return BacktestRunOutcome.COMPLETED

    @property
    def cache_hit_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "canonical_result_cache_hit",
            "schema_version": 1,
            "canonical_attempt": self.canonical_attempt,
            "resolved_request_hash": canonical_sha256(self.resolved_request),
            "input_origin": self.input_origin.value,
            "execution_case_hash": self.execution_case_hash,
            "execution_result_hash": self.execution_result_hash,
            "canonical_attempt_ref_hash": self.canonical_attempt_ref_hash,
            "integrity_report_hash": self.integrity_report_hash,
            "result_hash": self.result_hash,
            "publication_manifest_hash": self.publication_manifest_hash,
            "publication_manifest_source_hash": self.publication_manifest_source_hash,
            "result_grade": self.result_grade,
            "relative_directory": self.relative_directory,
            "outcome": self.outcome.value,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class AttemptExecutionRecord:
    cache_hit: CanonicalResultCacheHit | None = None
    ready_to_finalize: ReadyToFinalizeAttempt | None = None
    blocked_report: BlockedAttemptReport | None = None
    failed_report: FailedAttemptReport | None = None
    cancelled_report: CancelledAttemptReport | None = None

    def __post_init__(self) -> None:
        branches = (
            self.cache_hit is not None,
            self.ready_to_finalize is not None,
            self.blocked_report is not None,
            self.failed_report is not None,
            self.cancelled_report is not None,
        )
        if sum(branches) != 1:
            raise ValueError("Attempt execution requires exactly one branch")
        expected_types = (
            (self.cache_hit, CanonicalResultCacheHit),
            (self.ready_to_finalize, ReadyToFinalizeAttempt),
            (self.blocked_report, BlockedAttemptReport),
            (self.failed_report, FailedAttemptReport),
            (self.cancelled_report, CancelledAttemptReport),
        )
        for value, expected in expected_types:
            if value is not None and not isinstance(value, expected):
                raise TypeError("Attempt execution branch has invalid type")

    @property
    def status(self) -> AttemptExecutionStatus:
        if self.cache_hit is not None:
            return AttemptExecutionStatus.CACHE_HIT
        if self.ready_to_finalize is not None:
            return AttemptExecutionStatus.READY_TO_FINALIZE
        if self.blocked_report is not None:
            return AttemptExecutionStatus.BLOCKED
        if self.failed_report is not None:
            return AttemptExecutionStatus.FAILED
        return AttemptExecutionStatus.CANCELLED

    @property
    def terminal_outcome(self) -> BacktestRunOutcome | None:
        if self.cache_hit is not None:
            return BacktestRunOutcome.COMPLETED
        if self.blocked_report is not None:
            return BacktestRunOutcome.BLOCKED
        if self.failed_report is not None:
            return BacktestRunOutcome.FAILED
        if self.cancelled_report is not None:
            return BacktestRunOutcome.CANCELLED
        return None

    @property
    def attempt(self) -> AttemptIdentity:
        if self.cache_hit is not None:
            return self.cache_hit.canonical_attempt
        for branch in (
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.attempt
        raise RuntimeError("Attempt execution has no branch")

    @property
    def resolved_request(self) -> ResolvedBacktestRequest:
        for branch in (
            self.cache_hit,
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.resolved_request
        raise RuntimeError("Attempt execution has no branch")

    @property
    def input_origin(self) -> InputOrigin:
        for branch in (
            self.cache_hit,
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.input_origin
        raise RuntimeError("Attempt execution has no branch")

    @property
    def execution_case_hash(self) -> str:
        for branch in (
            self.cache_hit,
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.execution_case_hash
        raise RuntimeError("Attempt execution has no branch")

    def to_canonical_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "attempt_execution_record",
            "status": self.status.value,
            "terminal_outcome": (
                self.terminal_outcome.value
                if self.terminal_outcome is not None
                else None
            ),
            "ready_to_finalize": self.ready_to_finalize,
            "blocked_report": self.blocked_report,
            "failed_report": self.failed_report,
            "cancelled_report": self.cancelled_report,
        }
        if self.cache_hit is not None:
            payload["cache_hit"] = self.cache_hit
        return payload


def _read_canonical_cache_hit(
    *,
    root: Path,
    resolved_request: ResolvedBacktestRequest,
    input_origin: InputOrigin,
    execution_case_hash: str,
) -> CanonicalResultCacheHit:
    return _read_canonical_cache_hit_version(
        root=root,
        resolved_request=resolved_request,
        input_origin=input_origin,
        execution_case_hash=execution_case_hash,
        directory_name="canonical",
        publication_id="canonical",
        result_schema_version=1,
        expected_engine_context=None,
    )


def _read_canonical_cache_hit_v2(
    *,
    root: Path,
    resolved_request: ResolvedBacktestRequest,
    input_origin: InputOrigin,
    execution_case: ResolvedExecutionCase,
) -> CanonicalResultCacheHit:
    identity_manifest = execution_case.identity_manifest
    if identity_manifest is None:
        raise ValueError("execution case identity manifest is required")
    expected_engine_context = {
        "type": "engine_execution_context",
        "schema_version": 1,
        "semantic_run_id": resolved_request.semantic_run_id,
        "semantic_spec_hash": execution_case.semantic_spec_hash,
        "case_hash": execution_case.case_hash,
        "target_stream_digest": execution_case.target_stream.target_stream_digest,
        "identity_manifest_hash": identity_manifest.manifest_hash,
        "financial_state": execution_case.financial_state,
    }
    return _read_canonical_cache_hit_version(
        root=root,
        resolved_request=resolved_request,
        input_origin=input_origin,
        execution_case_hash=execution_case.case_hash,
        directory_name="canonical-v2",
        publication_id="canonical-v2",
        result_schema_version=2,
        expected_engine_context=expected_engine_context,
    )


def _read_canonical_cache_hit_version(
    *,
    root: Path,
    resolved_request: ResolvedBacktestRequest,
    input_origin: InputOrigin,
    execution_case_hash: str,
    directory_name: str,
    publication_id: str,
    result_schema_version: int,
    expected_engine_context: Mapping[str, object] | None,
) -> CanonicalResultCacheHit:
    semantic_run_id = resolved_request.semantic_run_id
    relative = f"runs/{semantic_run_id}/{directory_name}"
    directory = root / relative
    if not directory.is_dir():
        raise ValueError("canonical publication is not a directory")
    verify_read_only(directory)
    expected_files = {
        "canonical-attempt-ref.json",
        "integrity.json",
        "result.json",
        "publication-manifest.json",
    }
    if {path.name for path in directory.iterdir()} != expected_files:
        raise ValueError("canonical publication file coverage mismatch")
    artifact_specs = {
        "canonical-attempt-ref.json": ("canonical_attempt_ref", 1),
        "integrity.json": ("integrity_report", 1),
        "result.json": ("completed_backtest_result", result_schema_version),
    }
    artifacts = {
        name: _read_canonical_artifact(directory / name, artifact_type)
        for name, (artifact_type, _) in artifact_specs.items()
    }
    manifest_payload, _, manifest_source_hash = _read_canonical_artifact(
        directory / "publication-manifest.json",
        "canonical_publication_manifest",
    )
    manifest_authorized = manifest_payload.get("deployment_authorized")
    if (
        manifest_payload.get("semantic_run_id") != semantic_run_id
        or manifest_payload.get("publication_kind") != "canonical"
        or manifest_payload.get("publication_id") != publication_id
        or type(manifest_authorized) is not bool
        or manifest_authorized
    ):
        raise ValueError("canonical publication manifest identity mismatch")
    manifest_entries = manifest_payload.get("artifacts")
    if not isinstance(manifest_entries, tuple) or not all(
        isinstance(value, Mapping) for value in manifest_entries
    ):
        raise ValueError("canonical publication manifest entries are invalid")
    entries = tuple(dict(value) for value in manifest_entries)
    paths = tuple(value.get("relative_path") for value in entries)
    if len(set(paths)) != len(paths):
        raise ValueError("canonical publication manifest paths are not unique")
    by_path = {value["relative_path"]: value for value in entries}
    if set(by_path) != set(artifact_specs):
        raise ValueError("canonical publication manifest does not exact-cover")
    for name, (expected_type, expected_version) in artifact_specs.items():
        _, envelope, source_hash = artifacts[name]
        entry = by_path[name]
        if (
            envelope.schema_version != expected_version
            or entry.get("artifact_type") != expected_type
            or entry.get("schema_version") != expected_version
            or entry.get("content_hash") != envelope.content_hash
            or entry.get("source_hash") != source_hash
            or entry.get("byte_count") != (directory / name).stat().st_size
        ):
            raise ValueError("canonical publication artifact binding mismatch")

    reference_payload = artifacts["canonical-attempt-ref.json"][0]
    integrity_payload = artifacts["integrity.json"][0]
    result_payload = artifacts["result.json"][0]
    reference_hash = canonical_sha256(reference_payload)
    integrity_hash = canonical_sha256(integrity_payload)
    result_hash = canonical_sha256(result_payload)
    authorization_values = (
        reference_payload.get("deployment_authorized"),
        integrity_payload.get("deployment_authorized"),
        result_payload.get("deployment_authorized"),
    )
    result_integrity = result_payload.get("integrity")
    attempt_payload = reference_payload.get("attempt")
    if not isinstance(result_integrity, Mapping):
        raise ValueError("canonical Result integrity summary is invalid")
    if not isinstance(attempt_payload, Mapping):
        raise ValueError("canonical Attempt payload is invalid")
    result_grade_value = result_payload.get("result_grade")
    integrity_grade_value = integrity_payload.get("result_grade")
    actual_engine_context = result_payload.get("engine_execution_context")
    if (
        result_payload.get("schema_version") != result_schema_version
        or (
            expected_engine_context is None
            and actual_engine_context is not None
        )
        or (
            expected_engine_context is not None
            and canonical_sha256(actual_engine_context)
            != canonical_sha256(expected_engine_context)
        )
    ):
        raise ValueError("canonical Result schema context mismatch")
    requested_grade = integrity_payload.get("requested_grade")
    expected_grade = resolved_request.request.result_grade_requested.value
    if (
        any(type(value) is not bool or value for value in authorization_values)
        or result_payload.get("outcome") != BacktestRunOutcome.COMPLETED.value
        or result_payload.get("semantic_run_id") != semantic_run_id
        or integrity_payload.get("semantic_run_id") != semantic_run_id
        or result_payload.get("canonical_attempt_ref_hash") != reference_hash
        or integrity_payload.get("canonical_attempt_ref_hash") != reference_hash
        or result_payload.get("integrity_report_hash") != integrity_hash
        or result_payload.get("request_hash")
        != canonical_sha256(resolved_request.request)
        or canonical_sha256(result_payload.get("resolved_request"))
        != canonical_sha256(resolved_request)
        or result_grade_value != integrity_grade_value
        or result_grade_value != expected_grade
        or requested_grade != expected_grade
        or result_grade_value
        not in {"development", "decision_grade"}
        or (
            result_grade_value == "decision_grade"
            and requested_grade != "decision_grade"
        )
        or result_integrity.get("blocking") not in ((), [])
        or result_payload.get("execution_result_hash")
        != reference_payload.get("execution_result_hash")
        or result_payload.get("consistency_set_hash")
        != reference_payload.get("consistency_set_hash")
        or result_payload.get("attempt_id") != attempt_payload.get("attempt_id")
        or result_payload.get("evidence_manifest_hash")
        != reference_payload.get("evidence_manifest_hash")
    ):
        raise ValueError("canonical Result trust chain mismatch")
    canonical_attempt = AttemptIdentity(
        semantic_run_id=attempt_payload["semantic_run_id"],
        ordinal=attempt_payload["ordinal"],
        parent_attempt_id=attempt_payload["parent_attempt_id"],
        attempt_id=attempt_payload["attempt_id"],
    )
    if (
        canonical_attempt.semantic_run_id != semantic_run_id
        or reference_payload.get("execution_case_hash") != execution_case_hash
    ):
        raise ValueError("canonical cache identity mismatch")
    execution_result_hash = reference_payload.get("execution_result_hash")
    result_grade = result_grade_value
    if not isinstance(execution_result_hash, str) or not isinstance(
        result_grade, str
    ):
        raise ValueError("canonical cache result fields are invalid")
    return CanonicalResultCacheHit(
        canonical_attempt=canonical_attempt,
        resolved_request=resolved_request,
        input_origin=input_origin,
        execution_case_hash=execution_case_hash,
        execution_result_hash=execution_result_hash,
        canonical_attempt_ref_hash=reference_hash,
        integrity_report_hash=integrity_hash,
        result_hash=result_hash,
        publication_manifest_hash=canonical_sha256(manifest_payload),
        publication_manifest_source_hash=manifest_source_hash,
        result_grade=result_grade,
        relative_directory=relative,
    )


class _Engine(Protocol):
    @abstractmethod
    def run(
        self,
        case: ResolvedExecutionCase | InputValidationFailure,
        *,
        cancellation: EngineCancellationRequest | None = None,
    ) -> EngineExecutionOutcome:
        pass


_ORIGIN_SENSITIVE_CODES = frozenset(
    {
        EngineFailureCode.TARGET_INPUT_DECODE,
        EngineFailureCode.TARGET_VALIDATION,
        EngineFailureCode.DECISION_BATCH,
    }
)
_BLOCKED_ENGINE_CODES = frozenset(
    {
        EngineFailureCode.TIMELINE_FAILURE,
        EngineFailureCode.POSITION_SIZING,
        EngineFailureCode.CAPABILITY_REJECTED,
        EngineFailureCode.TRANSLATION_REJECTED,
        EngineFailureCode.MARKET_RULE_REJECTED,
        EngineFailureCode.MARKET_RULE_DATA_FAILURE,
        EngineFailureCode.FEE_RESERVATION,
        EngineFailureCode.PRETRADE_REJECTED,
        EngineFailureCode.EXECUTION_FAILURE,
        EngineFailureCode.SLIPPAGE_FAILURE,
        EngineFailureCode.FEE_ASSESSMENT_FAILURE,
        EngineFailureCode.SNAPSHOT_PROJECTION_FAILURE,
        EngineFailureCode.RUN_END_TERMINATED,
        EngineFailureCode.MISSING_SCHEDULED_EVENT,
    }
)
_FAILED_ENGINE_CODES = frozenset(
    {
        EngineFailureCode.ALLOCATION,
        EngineFailureCode.PORTFOLIO_RISK,
        EngineFailureCode.REBALANCE,
        EngineFailureCode.ORDER_PLAN_MISMATCH,
        EngineFailureCode.PRETRADE_CONTRACT_FAILURE,
        EngineFailureCode.FILL_CONSTRUCTION,
        EngineFailureCode.ACCOUNTING_FAILURE,
        EngineFailureCode.FINANCIAL_DISPATCH_FAILURE,
        EngineFailureCode.FEE_ACCOUNTING_FAILURE,
        EngineFailureCode.CASE_EVIDENCE_MISMATCH,
    }
)
if _ORIGIN_SENSITIVE_CODES | _BLOCKED_ENGINE_CODES | _FAILED_ENGINE_CODES != frozenset(
    EngineFailureCode
):
    raise RuntimeError("Engine failure outcome mapping is not exhaustive")


class AuditableBacktestRunner:
    def __init__(
        self,
        *,
        engine: _Engine | None = None,
        publication_root: Path | None = None,
        canonical_publication_version: int = 1,
    ) -> None:
        if publication_root is not None and not isinstance(publication_root, Path):
            raise TypeError("publication_root must be Path or None")
        if canonical_publication_version not in {1, 2}:
            raise ValueError("canonical_publication_version must be 1 or 2")
        self._engine: _Engine = engine or DeterministicBarEngine()
        self._publication_root = publication_root
        self._canonical_publication_version = canonical_publication_version

    @classmethod
    def for_v2(cls, *, publication_root: Path) -> AuditableBacktestRunner:
        return cls(
            publication_root=publication_root,
            canonical_publication_version=2,
        )

    @staticmethod
    def classify_engine_failure(
        code: EngineFailureCode, input_origin: InputOrigin
    ) -> BacktestRunOutcome:
        if not isinstance(code, EngineFailureCode):
            raise TypeError("code must be EngineFailureCode")
        if not isinstance(input_origin, InputOrigin):
            raise TypeError("input_origin must be InputOrigin")
        if code in _ORIGIN_SENSITIVE_CODES:
            if input_origin is InputOrigin.PRECOMPUTED_TARGET_STREAM:
                return BacktestRunOutcome.BLOCKED
            return BacktestRunOutcome.FAILED
        if code in _BLOCKED_ENGINE_CODES:
            return BacktestRunOutcome.BLOCKED
        if code in _FAILED_ENGINE_CODES:
            return BacktestRunOutcome.FAILED
        raise RuntimeError(f"Engine failure code is not classified: {code.value}")

    def execute(
        self,
        *,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt: AttemptIdentity,
        input_origin: InputOrigin,
        cancellation: EngineCancellationRequest | None = None,
    ) -> AttemptExecutionRecord:
        if not isinstance(resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        if not isinstance(execution_case, ResolvedExecutionCase):
            raise TypeError("execution_case must be ResolvedExecutionCase")
        if not isinstance(attempt, AttemptIdentity):
            raise TypeError("attempt must be AttemptIdentity")
        if attempt.semantic_run_id != resolved_request.semantic_run_id:
            raise ValueError("Attempt semantic run does not match resolved request")
        if not isinstance(input_origin, InputOrigin):
            raise TypeError("input_origin must be InputOrigin")
        if cancellation is not None and not isinstance(
            cancellation, EngineCancellationRequest
        ):
            raise TypeError("cancellation must be EngineCancellationRequest or None")

        contract_issue = self._contract_issue(
            resolved_request, execution_case, input_origin
        )
        if contract_issue is not None:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                contract_issue,
            )
        return self._execute_verified(
            resolved_request=resolved_request,
            execution_case=execution_case,
            attempt=attempt,
            input_origin=input_origin,
            cancellation=cancellation,
        )

    def _execute_verified(
        self,
        *,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt: AttemptIdentity,
        input_origin: InputOrigin,
        cancellation: EngineCancellationRequest | None,
    ) -> AttemptExecutionRecord:
        if self._publication_root is None:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                self._runner_issue(
                    "publication_root_required",
                    (resolved_request.semantic_run_id,),
                ),
            )
        try:
            with RunPublicationLock(
                root=self._publication_root,
                semantic_run_id=resolved_request.semantic_run_id,
            ):
                return self._execute_verified_locked(
                    resolved_request=resolved_request,
                    execution_case=execution_case,
                    attempt=attempt,
                    input_origin=input_origin,
                    cancellation=cancellation,
                )
        except OSError:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                self._runner_issue(
                    "run_lock_unavailable",
                    (resolved_request.semantic_run_id,),
                ),
            )

    def _execute_verified_locked(
        self,
        *,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt: AttemptIdentity,
        input_origin: InputOrigin,
        cancellation: EngineCancellationRequest | None,
    ) -> AttemptExecutionRecord:
        root = self._publication_root
        if root is None:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                self._runner_issue(
                    "publication_root_required",
                    (resolved_request.semantic_run_id,),
                ),
            )
        relative_canonical = (
            "canonical-v2"
            if self._canonical_publication_version == 2
            else "canonical"
        )
        canonical = (
            root
            / "runs"
            / resolved_request.semantic_run_id
            / relative_canonical
        )
        if os.path.lexists(canonical):
            try:
                if self._canonical_publication_version == 2:
                    cache_hit = _read_canonical_cache_hit_v2(
                        root=root,
                        resolved_request=resolved_request,
                        input_origin=input_origin,
                        execution_case=execution_case,
                    )
                else:
                    cache_hit = _read_canonical_cache_hit(
                        root=root,
                        resolved_request=resolved_request,
                        input_origin=input_origin,
                        execution_case_hash=execution_case.case_hash,
                    )
            except (OSError, TypeError, ValueError, KeyError) as error:
                return self._failed_record(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    self._runner_issue(
                        "canonical_cache_invalid",
                        (
                            resolved_request.semantic_run_id,
                            f"{type(error).__module__}.{type(error).__qualname__}",
                        ),
                    ),
                )
            return AttemptExecutionRecord(cache_hit=cache_hit)
        return self._execute_engine(
            resolved_request,
            execution_case,
            attempt,
            input_origin,
            cancellation,
        )

    def _execute_engine(
        self,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt: AttemptIdentity,
        input_origin: InputOrigin,
        cancellation: EngineCancellationRequest | None,
    ) -> AttemptExecutionRecord:
        try:
            outcome = self._engine.run(execution_case, cancellation=cancellation)
        except Exception as error:
            exception_type = f"{type(error).__module__}.{type(error).__qualname__}"
            source_hash = canonical_sha256(
                {
                    "type": "unhandled_engine_exception_v1",
                    "exception_type": exception_type,
                }
            )
            issue = AttemptIssue(
                source=AttemptIssueSource.ENGINE_EXCEPTION,
                code="unhandled_engine_exception",
                subject_keys=(exception_type,),
                evidence_hashes=(source_hash,),
                source_hash=source_hash,
            )
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                issue,
            )
        if not isinstance(outcome, EngineExecutionOutcome):
            issue = self._runner_issue(
                "invalid_engine_outcome",
                (type(outcome).__qualname__,),
            )
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                issue,
            )
        return self._map_outcome(
            resolved_request,
            execution_case,
            attempt,
            input_origin,
            cancellation,
            outcome,
        )

    def retry_from_start(
        self,
        *,
        previous: AttemptExecutionRecord,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        next_attempt_ordinal: int,
        input_origin: InputOrigin,
        cancellation: EngineCancellationRequest | None = None,
    ) -> AttemptExecutionRecord:
        if not isinstance(previous, AttemptExecutionRecord):
            raise TypeError("previous must be AttemptExecutionRecord")
        if previous.cache_hit is not None:
            return previous
        if previous.resolved_request.semantic_run_id != resolved_request.semantic_run_id:
            raise ValueError("retry must remain in the previous Semantic Run")
        if canonical_sha256(previous.resolved_request) != canonical_sha256(
            resolved_request
        ):
            raise ValueError("retry must reuse the same resolved request")
        if previous.execution_case_hash != execution_case.case_hash:
            raise ValueError("retry must reuse the same initial execution case")
        if previous.input_origin is not input_origin:
            raise ValueError("retry must preserve InputOrigin")
        attempt = AttemptIdentity.retry(
            previous.attempt, next_ordinal=next_attempt_ordinal
        )
        return self.execute(
            resolved_request=resolved_request,
            execution_case=execution_case,
            attempt=attempt,
            input_origin=input_origin,
            cancellation=cancellation,
        )

    def _retry_from_start_verified(
        self,
        *,
        previous: AttemptExecutionRecord,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        next_attempt_ordinal: int,
        input_origin: InputOrigin,
        market_data_preparation: MultiResolutionMarketDataPreparation,
        cancellation: EngineCancellationRequest | None = None,
    ) -> AttemptExecutionRecord:
        self._verify_v3_contract(
            resolved_request=resolved_request,
            execution_case=execution_case,
            input_origin=input_origin,
            market_data_preparation=market_data_preparation,
        )
        if not isinstance(previous, AttemptExecutionRecord):
            raise TypeError("previous must be AttemptExecutionRecord")
        if previous.cache_hit is not None:
            return previous
        if previous.resolved_request.semantic_run_id != resolved_request.semantic_run_id:
            raise ValueError("retry must remain in the previous Semantic Run")
        if canonical_sha256(previous.resolved_request) != canonical_sha256(
            resolved_request
        ):
            raise ValueError("retry must reuse the same resolved request")
        if previous.execution_case_hash != execution_case.case_hash:
            raise ValueError("retry must reuse the same initial execution case")
        if previous.input_origin is not input_origin:
            raise ValueError("retry must preserve InputOrigin")
        attempt = AttemptIdentity.retry(
            previous.attempt, next_ordinal=next_attempt_ordinal
        )
        return self._execute_verified(
            resolved_request=resolved_request,
            execution_case=execution_case,
            attempt=attempt,
            input_origin=input_origin,
            cancellation=cancellation,
        )

    def _map_outcome(
        self,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt: AttemptIdentity,
        input_origin: InputOrigin,
        cancellation_request: EngineCancellationRequest | None,
        outcome: EngineExecutionOutcome,
    ) -> AttemptExecutionRecord:
        if outcome.result is not None:
            if outcome.result.case_hash != execution_case.case_hash:
                return self._failed_record(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    self._runner_issue(
                        "engine_result_case_mismatch",
                        (outcome.result.case_hash, execution_case.case_hash),
                    ),
                )
            return AttemptExecutionRecord(
                ready_to_finalize=ReadyToFinalizeAttempt(
                    attempt=attempt,
                    resolved_request=resolved_request,
                    input_origin=input_origin,
                    execution_case_hash=execution_case.case_hash,
                    engine_result=outcome.result,
                )
            )
        if outcome.input_validation_failure is not None:
            input_failure = outcome.input_validation_failure
            if input_failure.bundle_ref != resolved_request.request.market_bundle_ref:
                return self._failed_record(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    self._runner_issue(
                        "input_validation_bundle_mismatch",
                        (
                            input_failure.bundle_ref.manifest_hash,
                            resolved_request.request.market_bundle_ref.manifest_hash,
                        ),
                    ),
                )
            issue = AttemptIssue(
                source=AttemptIssueSource.INPUT_VALIDATION,
                code="market_bundle_input_validation",
                subject_keys=tuple(
                    f"{value.code.value}:{value.subject_key}"
                    for value in input_failure.issues
                ),
                evidence_hashes=(input_failure.failure_hash,),
                source_hash=input_failure.failure_hash,
                source_evidence=input_failure,
            )
            return AttemptExecutionRecord(
                blocked_report=BlockedAttemptReport(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    issue,
                )
            )
        if outcome.engine_failure is not None:
            engine_failure = outcome.engine_failure
            if engine_failure.case_hash != execution_case.case_hash:
                return self._failed_record(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    self._runner_issue(
                        "engine_failure_case_mismatch",
                        (engine_failure.case_hash, execution_case.case_hash),
                    ),
                )
            issue = AttemptIssue(
                source=AttemptIssueSource.ENGINE_FAILURE,
                code=engine_failure.code.value,
                subject_keys=engine_failure.subject_keys,
                evidence_hashes=engine_failure.evidence_hashes,
                source_hash=engine_failure.failure_hash,
                source_evidence=engine_failure,
            )
            mapped = self.classify_engine_failure(engine_failure.code, input_origin)
            if mapped is BacktestRunOutcome.BLOCKED:
                return AttemptExecutionRecord(
                    blocked_report=BlockedAttemptReport(
                        attempt,
                        resolved_request,
                        input_origin,
                        execution_case.case_hash,
                        issue,
                        engine_failure.trace_hash,
                    )
                )
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                issue,
                engine_failure.trace_hash,
            )
        cancellation = outcome.cancellation
        if cancellation is None:
            raise RuntimeError("Engine outcome has no branch")
        if cancellation.case_hash != execution_case.case_hash:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                self._runner_issue(
                    "engine_cancellation_case_mismatch",
                    (cancellation.case_hash, execution_case.case_hash),
                ),
            )
        if cancellation_request is None or cancellation.request != cancellation_request:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                self._runner_issue(
                    "engine_cancellation_request_mismatch",
                    (cancellation.request.request_hash,),
                ),
                cancellation.trace_hash,
            )
        return AttemptExecutionRecord(
            cancelled_report=CancelledAttemptReport(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                cancellation,
            )
        )

    @staticmethod
    def _expected_input_origin(resolved_request: ResolvedBacktestRequest) -> InputOrigin:
        if not isinstance(resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        return (
            InputOrigin.PRECOMPUTED_TARGET_STREAM
            if resolved_request.request.strategy_family
            is StrategyFamily.PRECOMPUTED_TARGET
            else InputOrigin.RUNTIME_STRATEGY
        )

    @classmethod
    def _verify_v3_contract(
        cls,
        *,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        input_origin: InputOrigin,
        market_data_preparation: MultiResolutionMarketDataPreparation,
    ) -> None:
        if type(resolved_request) is not ResolvedBacktestRequest:
            raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
        if type(execution_case) is not ResolvedExecutionCase:
            raise TypeError("execution_case must be exact ResolvedExecutionCase")
        if type(input_origin) is not InputOrigin:
            raise TypeError("input_origin must be exact InputOrigin")
        if type(market_data_preparation) is not MultiResolutionMarketDataPreparation:
            raise TypeError(
                "market_data_preparation must be exact MultiResolutionMarketDataPreparation"
            )
        spec = execution_case.semantic_spec
        if spec is None:
            raise RuntimeError("execution case semantic spec mismatch")
        try:
            recomputed = _execution_case_semantic_spec_from_case_v3(
                case=execution_case,
                market_data_preparation=market_data_preparation,
                spec_key=spec.spec_key,
                spec_version=spec.spec_version,
                identity_namespace=spec.identity_namespace,
                identity_plan=spec.identity_plan,
            )
        except (TypeError, ValueError):
            recomputed = None
        request = resolved_request.request
        if (
            recomputed != spec
            or request.execution_case_semantic_hash
            != execution_case.semantic_spec_hash
        ):
            raise RuntimeError("execution case semantic spec mismatch")
        manifest = execution_case.identity_manifest
        if manifest is None or not execution_case.verify_identity_manifest(
            resolved_request.semantic_run_id
        ):
            raise RuntimeError("execution case identity manifest mismatch")
        if request.target_stream_digest != execution_case.target_stream.target_stream_digest:
            raise RuntimeError("target stream digest mismatch")
        if input_origin is not cls._expected_input_origin(resolved_request):
            raise RuntimeError("input origin mismatch")

    @staticmethod
    def _contract_issue(
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        input_origin: InputOrigin,
    ) -> AttemptIssue | None:
        request = resolved_request.request
        spec = execution_case.semantic_spec
        if (
            spec is None
            or request.execution_case_semantic_hash
            != execution_case.semantic_spec_hash
        ):
            return AuditableBacktestRunner._runner_issue(
                "execution_case_semantic_spec_mismatch",
                (
                    request.execution_case_semantic_hash,
                    execution_case.semantic_spec_hash,
                ),
            )
        try:
            recomputed = ExecutionCaseComposer.semantic_spec_from_case(
                execution_case,
                spec_key=spec.spec_key,
                spec_version=spec.spec_version,
                identity_namespace=spec.identity_namespace,
                identity_plan=spec.identity_plan,
            )
        except (TypeError, ValueError):
            recomputed = None
        if recomputed != spec:
            return AuditableBacktestRunner._runner_issue(
                "execution_case_semantic_spec_mismatch",
                (request.execution_case_semantic_hash, execution_case.case_hash),
            )
        manifest = execution_case.identity_manifest
        if manifest is None:
            return AuditableBacktestRunner._runner_issue(
                "execution_case_identity_manifest_missing",
                (request.execution_case_semantic_hash, execution_case.case_hash),
            )
        if not execution_case.verify_identity_manifest(
            resolved_request.semantic_run_id
        ):
            return AuditableBacktestRunner._runner_issue(
                "execution_case_identity_manifest_mismatch",
                (resolved_request.semantic_run_id, manifest.manifest_hash),
            )
        if request.target_stream_digest != execution_case.target_stream.target_stream_digest:
            return AuditableBacktestRunner._runner_issue(
                "target_stream_digest_mismatch",
                (
                    request.target_stream_digest,
                    execution_case.target_stream.target_stream_digest,
                ),
            )
        expected_origin = (
            InputOrigin.PRECOMPUTED_TARGET_STREAM
            if request.strategy_family is StrategyFamily.PRECOMPUTED_TARGET
            else InputOrigin.RUNTIME_STRATEGY
        )
        if input_origin is not expected_origin:
            return AuditableBacktestRunner._runner_issue(
                "input_origin_mismatch",
                (request.strategy_family.value, input_origin.value),
            )
        return None

    @staticmethod
    def _runner_issue(code: str, subjects: tuple[str, ...]) -> AttemptIssue:
        payload = {
            "type": "auditable_runner_contract_issue_v1",
            "code": code,
            "subject_keys": tuple(sorted(subjects)),
        }
        source_hash = canonical_sha256(payload)
        return AttemptIssue(
            source=AttemptIssueSource.RUNNER_CONTRACT,
            code=code,
            subject_keys=subjects,
            evidence_hashes=(source_hash,),
            source_hash=source_hash,
        )

    @staticmethod
    def _failed_record(
        attempt: AttemptIdentity,
        resolved_request: ResolvedBacktestRequest,
        input_origin: InputOrigin,
        execution_case_hash: str,
        issue: AttemptIssue,
        trace_hash: str | None = None,
    ) -> AttemptExecutionRecord:
        return AttemptExecutionRecord(
            failed_report=FailedAttemptReport(
                attempt,
                resolved_request,
                input_origin,
                execution_case_hash,
                issue,
                trace_hash,
            )
        )


__all__ = [
    "AttemptExecutionRecord",
    "AttemptExecutionStatus",
    "AttemptIdentity",
    "AttemptIssue",
    "AttemptIssueSource",
    "AuditableBacktestRunner",
    "BacktestRunOutcome",
    "BlockedAttemptReport",
    "CancelledAttemptReport",
    "CanonicalResultCacheHit",
    "FailedAttemptReport",
    "InputOrigin",
    "ReadyToFinalizeAttempt",
]
