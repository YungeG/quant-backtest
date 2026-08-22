from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    ArtifactDecodeError,
    ArtifactEnvelope,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactReadResult,
    ArtifactRef,
    ArtifactRetentionUnavailableError,
    ArtifactSchemaRegistration,
    CurrencyId,
    SchemaCatalog,
    canonical_bytes,
    canonical_sha256,
)

from .analysis import (
    AnalysisArtifactRef,
    AnalysisArtifactRefV2,
    BacktestAnalysis,
    BacktestAnalysisV2,
    BacktestMetricProfile,
    VerifiedBacktestAnalysis,
    VerifiedBacktestAnalysisV2,
)
from .engine import ResolvedExecutionCase
from .execution_inputs import (
    _read_fill,
    _read_financial_state,
    _read_journal,
    _read_portfolio_snapshot,
)
from .integrity import AttemptConsistencySet, EngineExecutionContext, ResultGrade
from .ports import ArtifactEnvelopeReader
from .publication_refs import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
)
from .resolution import ResolvedBacktestRequest
from .runner import AttemptIdentity, InputOrigin
from .verified_publications import (
    TerminalStatus,
    VerifiedCompletedPublicationV2,
    VerifiedCompletedPublicationV3,
    VerifiedExecutionSummary,
    VerifiedTerminalPublication,
)

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RUN = re.compile(r"run_[0-9a-f]{64}\Z")
_ATTEMPT = re.compile(r"attempt_[0-9a-f]{64}\Z")

_EVIDENCE_COMMON_LAYOUT = {
    "request": ("request.json", "backtest_request", 1),
    "environment": ("environment.json", "resolved_backtest_environment", 1),
    "build_artifact_manifest": (
        "build-artifact-manifest.json",
        "build_artifact_manifest",
        1,
    ),
    "market_bundle_reference": ("market-bundle-ref.json", "market_bundle_ref", 1),
    "environment_compatibility": (
        "environment-compatibility-report.json",
        "environment_compatibility_report",
        1,
    ),
    "attempt_execution_record": (
        "attempt-execution-record.json",
        "attempt_execution_record",
        1,
    ),
}
_EVIDENCE_BRANCH_LAYOUT = {
    "READY_FOR_INTEGRITY": (
        "engine_execution_result",
        "engine-execution-result.json",
        "engine_execution_result",
        1,
    ),
    "BLOCKED": (
        "blocked_report",
        "blocked-run-report.json",
        "blocked_run_report",
        1,
    ),
    "FAILED": ("failure_report", "failure-report.json", "failure_report", 1),
    "CANCELLED": (
        "cancellation_report",
        "cancellation-report.json",
        "cancellation_report",
        1,
    ),
}


class BacktestEvidenceFailureCode(str, Enum):
    PORT_REF_TYPE_MISMATCH = "PORT_REF_TYPE_MISMATCH"
    PORT_REF_NOT_FOUND = "PORT_REF_NOT_FOUND"
    PORT_EVIDENCE_TAMPERED = "PORT_EVIDENCE_TAMPERED"
    PORT_MANIFEST_INVALID = "PORT_MANIFEST_INVALID"
    PORT_RETENTION_UNAVAILABLE = "PORT_RETENTION_UNAVAILABLE"
    PORT_TERMINAL_NOT_ANALYZABLE = "PORT_TERMINAL_NOT_ANALYZABLE"
    PORT_ANALYSIS_LINK_MISMATCH = "PORT_ANALYSIS_LINK_MISMATCH"
    PORT_STATIC_PROOF_MISMATCH = "PORT_STATIC_PROOF_MISMATCH"
    PORT_COMPLETED_VERSION_MISMATCH = "PORT_COMPLETED_VERSION_MISMATCH"
    PORT_ANALYSIS_VERSION_MISMATCH = "PORT_ANALYSIS_VERSION_MISMATCH"


class _StaticProofMismatch(ValueError):
    pass


class _CompletedVersionMismatch(ValueError):
    pass


class _AnalysisVersionMismatch(ValueError):
    pass


class BacktestEvidenceError(Exception):
    def __init__(self, code: BacktestEvidenceFailureCode, message: str) -> None:
        if type(code) is not BacktestEvidenceFailureCode:
            raise TypeError("code must be exact BacktestEvidenceFailureCode")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class _PublicationEntry:
    relative_path: str
    artifact_ref: ArtifactRef
    source_hash: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class _EvidenceEntry:
    relative_path: str
    role: str
    artifact_ref: ArtifactRef
    source_hash: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class _CanonicalManifest:
    semantic_run_id: str
    publication_kind: str
    publication_id: str
    artifacts: tuple[_PublicationEntry, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _CanonicalManifestV2:
    semantic_run_id: str
    publication_kind: str
    publication_id: str
    artifacts: tuple[_PublicationEntry, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _CanonicalAttempt:
    semantic_run_id: str
    attempt_id: str
    evidence_manifest_hash: str
    evidence_manifest_source_hash: str
    evidence_publication_hash: str
    engine_result_artifact_content_hash: str
    consistency_set_hash: str
    execution_result_hash: str
    execution_case_semantic_hash: str
    execution_case_hash: str
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _CanonicalAttemptV2:
    attempt: AttemptIdentity
    consistency_set_hash: str
    execution_result_hash: str
    execution_case_semantic_hash: str
    execution_case_hash: str
    trace_hash: str
    market_bundle_manifest_hash: str
    rebuild_verification_ref: ArtifactRef
    rebuild_verification_source_hash: str
    proof_publication_manifest_ref: ArtifactRef
    proof_publication_manifest_source_hash: str
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _CompletedResult:
    semantic_run_id: str
    request_hash: str
    attempt_id: str
    evidence_manifest_hash: str
    evidence_manifest_ref: ArtifactRef
    canonical_attempt_ref_hash: str
    integrity_report_hash: str
    consistency_set_hash: str
    execution_result_hash: str
    result_grade: ResultGrade
    resolved_request: Mapping[str, Any]
    attempt_consistency_set: Mapping[str, Any]
    execution_hash_check: Mapping[str, Any]
    engine_context: Mapping[str, Any]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _CompletedResultV3:
    semantic_run_id: str
    request_hash: str
    resolved_request_hash: str
    execution_result_hash: str
    consistency_set_hash: str
    attempt_id: str
    evidence_manifest_ref: ArtifactRef
    canonical_attempt_ref_hash: str
    integrity_report_hash: str
    rebuild_verification_ref: ArtifactRef
    proof_publication_manifest_ref: ArtifactRef
    result_grade: ResultGrade
    engine_context: Mapping[str, Any]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _IntegrityReport:
    semantic_run_id: str
    result_grade: ResultGrade | None
    canonical_attempt_ref_hash: str | None
    context_hash: str
    context: Mapping[str, Any]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _IntegrityReportV2:
    semantic_run_id: str
    result_grade: ResultGrade | None
    canonical_attempt_ref_hash: str | None
    context_hash: str
    context: Mapping[str, Any]
    issues: tuple[Mapping[str, Any], ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _EvidenceManifest:
    semantic_run_id: str
    attempt_id: str
    status: str
    terminal_outcome: str | None
    manifest_hash: str
    artifacts: tuple[_EvidenceEntry, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _EngineSummary:
    case_hash: str
    target_stream_digest: str
    fills: Sequence[Any]
    final_journal: Mapping[str, Any]
    final_portfolio_snapshot: Mapping[str, Any]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ResolutionFailure:
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _DecodedAnalysis:
    analysis: BacktestAnalysis


@dataclass(frozen=True, slots=True)
class _DecodedAnalysisV2:
    analysis: BacktestAnalysisV2


@dataclass(frozen=True, slots=True)
class _DecodedMetricProfile:
    profile: BacktestMetricProfile


@dataclass(frozen=True, slots=True)
class _IntegrityEvaluation:
    evaluation_id: str
    semantic_run_id: str
    outcome: str
    integrity_report_hash: str
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _DecodedEvidenceChild:
    artifact_type: str
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _Loaded:
    artifact: object
    source_bytes: bytes
    source_hash: str


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if not all(type(key) is str for key in value):
        raise TypeError(f"{name} keys must be str")
    return value


def _exact(name: str, value: object, fields: frozenset[str]) -> Mapping[str, Any]:
    data = _mapping(name, value)
    if set(data) != fields:
        raise ValueError(f"{name} must contain exactly {', '.join(sorted(fields))}")
    return data


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _run(value: object) -> str:
    if type(value) is not str or _RUN.fullmatch(value) is None:
        raise ValueError("semantic_run_id must use run_sha256 schema")
    return value


def _attempt(value: object) -> str:
    if type(value) is not str or _ATTEMPT.fullmatch(value) is None:
        raise ValueError("attempt_id must use attempt_sha256 schema")
    return value


def _false(name: str, value: object) -> None:
    if type(value) is not bool or value:
        raise ValueError(f"{name} must be false")


def _artifact_ref(value: object, artifact_type: str, version: int) -> ArtifactRef:
    data = _exact(
        "artifact_ref",
        value,
        frozenset({"type", "artifact_type", "schema_version", "content_hash"}),
    )
    if data["type"] != "artifact_ref":
        raise ValueError("artifact ref type mismatch")
    ref = ArtifactRef(
        _text("artifact_type", data["artifact_type"]),
        data["schema_version"],
        _hash("content_hash", data["content_hash"]),
    )
    if ref.artifact_type != artifact_type or ref.schema_version != version:
        raise ValueError(f"artifact ref must target {artifact_type}@{version}")
    return ref


def _publication_ref(value: object) -> BacktestCanonicalPublicationRef:
    data = _exact(
        "source_publication_ref", value, frozenset({"type", "artifact_ref"})
    )
    if data["type"] != "backtest_canonical_publication_ref":
        raise ValueError("source publication ref type mismatch")
    return BacktestCanonicalPublicationRef.from_artifact_ref(
        _artifact_ref(data["artifact_ref"], "canonical_publication_manifest", 1)
    )


def _publication_entry(value: object) -> _PublicationEntry:
    data = _exact(
        "publication entry",
        value,
        frozenset(
            {
                "relative_path",
                "artifact_type",
                "schema_version",
                "content_hash",
                "source_hash",
                "byte_count",
            }
        ),
    )
    artifact_type = _text("artifact_type", data["artifact_type"])
    version = data["schema_version"]
    if type(version) is not int or version not in {1, 2, 3}:
        raise ValueError("publication entry schema version must be 1, 2, or 3")
    byte_count = data["byte_count"]
    if type(byte_count) is not int or byte_count <= 0:
        raise ValueError("publication byte_count must be positive")
    return _PublicationEntry(
        _text("relative_path", data["relative_path"]),
        ArtifactRef(artifact_type, version, _hash("content_hash", data["content_hash"])),
        _hash("source_hash", data["source_hash"]),
        byte_count,
    )


def _read_canonical_manifest(value: object) -> _CanonicalManifest:
    data = _exact(
        "canonical publication manifest",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "publication_kind",
                "publication_id",
                "artifacts",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "canonical_publication_manifest" or data["schema_version"] != 1:
        raise ValueError("manifest must be canonical_publication_manifest@1")
    _false("deployment_authorized", data["deployment_authorized"])
    kind = data["publication_kind"]
    if kind not in {"canonical", "integrity_evaluation"}:
        raise ValueError("unsupported publication kind")
    if not isinstance(data["artifacts"], (tuple, list)):
        raise TypeError("manifest artifacts must be a sequence")
    artifacts = tuple(_publication_entry(item) for item in data["artifacts"])
    paths = tuple(item.relative_path for item in artifacts)
    if len(paths) != len(set(paths)) or paths != tuple(sorted(paths)):
        raise ValueError("manifest entries must be unique and canonically ordered")
    return _CanonicalManifest(
        _run(data["semantic_run_id"]),
        kind,
        _text("publication_id", data["publication_id"]),
        artifacts,
        data,
    )


def _read_canonical_manifest_v2(value: object) -> _CanonicalManifestV2:
    data = _exact(
        "canonical publication manifest v2",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "publication_kind",
                "publication_id",
                "artifacts",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "canonical_publication_manifest" or data["schema_version"] != 2:
        raise ValueError("manifest must be canonical_publication_manifest@2")
    _false("deployment_authorized", data["deployment_authorized"])
    kind = data["publication_kind"]
    if kind not in {"canonical", "integrity_evaluation"}:
        raise ValueError("unsupported publication kind")
    if not isinstance(data["artifacts"], (tuple, list)):
        raise TypeError("manifest artifacts must be a sequence")
    artifacts = tuple(_publication_entry(item) for item in data["artifacts"])
    paths = tuple(item.relative_path for item in artifacts)
    if len(paths) != len(set(paths)) or paths != tuple(sorted(paths)):
        raise ValueError("manifest entries must be unique and canonically ordered")
    publication_id = _text("publication_id", data["publication_id"])
    if kind == "canonical" and publication_id != "canonical-v3":
        raise ValueError("completed v3 manifest must use canonical-v3")
    if kind == "integrity_evaluation" and not publication_id.startswith("evaluation_"):
        raise ValueError("evaluation v2 publication id mismatch")
    return _CanonicalManifestV2(
        _run(data["semantic_run_id"]),
        kind,
        publication_id,
        artifacts,
        data,
    )


def _read_attempt_identity_value(value: object) -> AttemptIdentity:
    data = _exact(
        "attempt identity",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "attempt_id",
                "ordinal",
                "parent_attempt_id",
            }
        ),
    )
    if data["type"] != "attempt_identity" or data["schema_version"] != 1:
        raise ValueError("attempt identity must be attempt_identity@1")
    return AttemptIdentity(
        semantic_run_id=_run(data["semantic_run_id"]),
        ordinal=data["ordinal"],
        parent_attempt_id=data["parent_attempt_id"],
        attempt_id=_attempt(data["attempt_id"]),
    )


def _read_attempt_identity(value: object) -> tuple[str, str]:
    data = _exact(
        "attempt identity",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "attempt_id",
                "ordinal",
                "parent_attempt_id",
            }
        ),
    )
    if data["type"] != "attempt_identity" or data["schema_version"] != 1:
        raise ValueError("attempt identity must be attempt_identity@1")
    if type(data["ordinal"]) is not int or data["ordinal"] <= 0:
        raise ValueError("attempt ordinal must be positive")
    parent = data["parent_attempt_id"]
    if parent is not None:
        _attempt(parent)
    return _run(data["semantic_run_id"]), _attempt(data["attempt_id"])


def _read_canonical_attempt(value: object) -> _CanonicalAttempt:
    fields = frozenset(
        {
            "type",
            "schema_version",
            "attempt",
            "evidence_manifest_hash",
            "evidence_manifest_source_hash",
            "evidence_publication_hash",
            "engine_result_artifact_content_hash",
            "consistency_set_hash",
            "execution_result_hash",
            "execution_case_semantic_hash",
            "execution_case_hash",
            "trace_hash",
            "trace_level",
            "market_bundle_manifest_hash",
            "market_bundle_retention_proof_hash",
            "deterministic_rebuild_evidence_hash",
            "deployment_authorized",
        }
    )
    data = _exact("canonical attempt ref", value, fields)
    if data["type"] != "canonical_attempt_ref" or data["schema_version"] != 1:
        raise ValueError("canonical attempt must be canonical_attempt_ref@1")
    _false("deployment_authorized", data["deployment_authorized"])
    semantic_run_id, attempt_id = _read_attempt_identity(data["attempt"])
    for name in fields - {
        "type",
        "schema_version",
        "attempt",
        "trace_level",
        "market_bundle_retention_proof_hash",
        "deployment_authorized",
    }:
        _hash(name, data[name])
    if data["trace_level"] not in {"summary", "full_trace", "microstructure_trace"}:
        raise ValueError("invalid trace level")
    optional = data["market_bundle_retention_proof_hash"]
    if optional is not None:
        _hash("market_bundle_retention_proof_hash", optional)
    return _CanonicalAttempt(
        semantic_run_id,
        attempt_id,
        data["evidence_manifest_hash"],
        data["evidence_manifest_source_hash"],
        data["evidence_publication_hash"],
        data["engine_result_artifact_content_hash"],
        data["consistency_set_hash"],
        data["execution_result_hash"],
        data["execution_case_semantic_hash"],
        data["execution_case_hash"],
        data,
    )


def _read_canonical_attempt_v2(value: object) -> _CanonicalAttemptV2:
    data = _exact(
        "canonical attempt ref v2",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "attempt",
                "consistency_set_hash",
                "execution_result_hash",
                "execution_case_semantic_hash",
                "execution_case_hash",
                "trace_hash",
                "trace_level",
                "market_bundle_manifest_hash",
                "rebuild_verification_ref",
                "rebuild_verification_source_hash",
                "proof_publication_manifest_ref",
                "proof_publication_manifest_source_hash",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "canonical_attempt_ref" or data["schema_version"] != 2:
        raise ValueError("canonical attempt must be canonical_attempt_ref@2")
    _false("deployment_authorized", data["deployment_authorized"])
    if data["trace_level"] != "full_trace":
        raise ValueError("canonical v2 trace level must be full_trace")
    return _CanonicalAttemptV2(
        _read_attempt_identity_value(data["attempt"]),
        _hash("consistency_set_hash", data["consistency_set_hash"]),
        _hash("execution_result_hash", data["execution_result_hash"]),
        _hash(
            "execution_case_semantic_hash",
            data["execution_case_semantic_hash"],
        ),
        _hash("execution_case_hash", data["execution_case_hash"]),
        _hash("trace_hash", data["trace_hash"]),
        _hash("market_bundle_manifest_hash", data["market_bundle_manifest_hash"]),
        _artifact_ref(
            data["rebuild_verification_ref"],
            "deterministic_rebuild_verification",
            1,
        ),
        _hash(
            "rebuild_verification_source_hash",
            data["rebuild_verification_source_hash"],
        ),
        _artifact_ref(
            data["proof_publication_manifest_ref"],
            "deterministic_rebuild_verification_publication_manifest",
            1,
        ),
        _hash(
            "proof_publication_manifest_source_hash",
            data["proof_publication_manifest_source_hash"],
        ),
        data,
    )


def _read_completed_result(value: object) -> _CompletedResult:
    fields = frozenset(
        {
            "type",
            "schema_version",
            "semantic_run_id",
            "outcome",
            "request_hash",
            "resolved_request",
            "attempt_consistency_set",
            "execution_hash_check",
            "execution_result_hash",
            "consistency_set_hash",
            "attempt_id",
            "evidence_manifest_hash",
            "canonical_evidence_manifest_ref",
            "canonical_attempt_ref_hash",
            "integrity_report_hash",
            "integrity",
            "result_grade",
            "engine_execution_context",
            "deployment_authorized",
        }
    )
    data = _exact("completed result v2", value, fields)
    if data["type"] != "completed_backtest_result" or data["schema_version"] != 2:
        raise ValueError("completed result must be completed_backtest_result@2")
    if data["outcome"] != "COMPLETED":
        raise ValueError("completed result outcome must be COMPLETED")
    _false("deployment_authorized", data["deployment_authorized"])
    integrity = _exact("result integrity", data["integrity"], frozenset({"blocking", "limitations"}))
    if integrity["blocking"] not in ((), []):
        raise ValueError("completed result integrity must be nonblocking")
    return _CompletedResult(
        _run(data["semantic_run_id"]),
        _hash("request_hash", data["request_hash"]),
        _attempt(data["attempt_id"]),
        _hash("evidence_manifest_hash", data["evidence_manifest_hash"]),
        _artifact_ref(data["canonical_evidence_manifest_ref"], "evidence_manifest", 1),
        _hash("canonical_attempt_ref_hash", data["canonical_attempt_ref_hash"]),
        _hash("integrity_report_hash", data["integrity_report_hash"]),
        _hash("consistency_set_hash", data["consistency_set_hash"]),
        _hash("execution_result_hash", data["execution_result_hash"]),
        ResultGrade(data["result_grade"]),
        _mapping("resolved_request", data["resolved_request"]),
        _mapping("attempt_consistency_set", data["attempt_consistency_set"]),
        _mapping("execution_hash_check", data["execution_hash_check"]),
        _mapping("engine_execution_context", data["engine_execution_context"]),
        data,
    )


def _read_completed_result_v3(value: object) -> _CompletedResultV3:
    data = _exact(
        "completed result v3",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "outcome",
                "request_hash",
                "resolved_request_hash",
                "execution_result_hash",
                "consistency_set_hash",
                "attempt_id",
                "evidence_manifest_ref",
                "canonical_attempt_ref_hash",
                "integrity_report_hash",
                "rebuild_verification_ref",
                "proof_publication_manifest_ref",
                "result_grade",
                "engine_execution_context",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "completed_backtest_result" or data["schema_version"] != 3:
        raise ValueError("completed result must be completed_backtest_result@3")
    if data["outcome"] != "COMPLETED" or data["result_grade"] != "decision_grade":
        raise ValueError("completed result v3 outcome/grade mismatch")
    _false("deployment_authorized", data["deployment_authorized"])
    return _CompletedResultV3(
        _run(data["semantic_run_id"]),
        _hash("request_hash", data["request_hash"]),
        _hash("resolved_request_hash", data["resolved_request_hash"]),
        _hash("execution_result_hash", data["execution_result_hash"]),
        _hash("consistency_set_hash", data["consistency_set_hash"]),
        _attempt(data["attempt_id"]),
        _artifact_ref(data["evidence_manifest_ref"], "evidence_manifest", 1),
        _hash("canonical_attempt_ref_hash", data["canonical_attempt_ref_hash"]),
        _hash("integrity_report_hash", data["integrity_report_hash"]),
        _artifact_ref(
            data["rebuild_verification_ref"],
            "deterministic_rebuild_verification",
            1,
        ),
        _artifact_ref(
            data["proof_publication_manifest_ref"],
            "deterministic_rebuild_verification_publication_manifest",
            1,
        ),
        ResultGrade(data["result_grade"]),
        _mapping("engine_execution_context", data["engine_execution_context"]),
        data,
    )


def _read_completed_result_v1(value: object) -> _DecodedEvidenceChild:
    data = _mapping("completed result v1", value)
    required = {
        "type",
        "schema_version",
        "semantic_run_id",
        "outcome",
        "deployment_authorized",
    }
    if not required <= set(data):
        raise ValueError("completed result v1 missing required fields")
    if data["type"] != "completed_backtest_result" or data["schema_version"] != 1:
        raise ValueError("completed result v1 tag mismatch")
    if data["outcome"] != "COMPLETED":
        raise ValueError("completed result v1 outcome mismatch")
    _run(data["semantic_run_id"])
    _false("deployment_authorized", data["deployment_authorized"])
    return _DecodedEvidenceChild("completed_backtest_result", data)


def _read_integrity_report(value: object) -> _IntegrityReport:
    data = _exact(
        "integrity report",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "context",
                "context_hash",
                "requested_grade",
                "result_grade",
                "issues",
                "canonical_attempt_ref_hash",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "integrity_report" or data["schema_version"] != 1:
        raise ValueError("integrity report must be integrity_report@1")
    _false("deployment_authorized", data["deployment_authorized"])
    context = _exact(
        "integrity context",
        data["context"],
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "resolved_request",
                "attempt_consistency_set",
                "execution_hash_check",
                "rebuild_evidence",
            }
        ),
    )
    if context["type"] != "integrity_evaluation_context" or context["schema_version"] != 1:
        raise ValueError("integrity context tag mismatch")
    semantic_run_id = _run(data["semantic_run_id"])
    if context["semantic_run_id"] != semantic_run_id:
        raise ValueError("integrity context semantic run mismatch")
    result_grade = None if data["result_grade"] is None else ResultGrade(data["result_grade"])
    canonical_ref_hash = data["canonical_attempt_ref_hash"]
    if canonical_ref_hash is not None:
        _hash("canonical_attempt_ref_hash", canonical_ref_hash)
    return _IntegrityReport(
        semantic_run_id,
        result_grade,
        canonical_ref_hash,
        _hash("context_hash", data["context_hash"]),
        context,
        data,
    )


def _read_integrity_report_v2(value: object) -> _IntegrityReportV2:
    data = _exact(
        "integrity report v2",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "context",
                "context_hash",
                "requested_grade",
                "result_grade",
                "issues",
                "canonical_attempt_ref_hash",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "integrity_report" or data["schema_version"] != 2:
        raise ValueError("integrity report must be integrity_report@2")
    if data["requested_grade"] != "decision_grade":
        raise ValueError("integrity report v2 must request decision grade")
    _false("deployment_authorized", data["deployment_authorized"])
    context = _exact(
        "integrity context v2",
        data["context"],
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "resolved_request_hash",
                "attempt_consistency_set_hash",
                "execution_hash_check_hash",
                "rebuild_verification_ref",
                "proof_publication_manifest_ref",
                "comparison_outcome",
            }
        ),
    )
    if (
        context["type"] != "integrity_evaluation_context"
        or context["schema_version"] != 2
        or context["comparison_outcome"] not in {"equal", "mismatch"}
    ):
        raise ValueError("integrity context v2 tag/outcome mismatch")
    semantic_run_id = _run(data["semantic_run_id"])
    if context["semantic_run_id"] != semantic_run_id:
        raise ValueError("integrity context semantic run mismatch")
    for name in (
        "resolved_request_hash",
        "attempt_consistency_set_hash",
        "execution_hash_check_hash",
    ):
        _hash(name, context[name])
    _artifact_ref(
        context["rebuild_verification_ref"],
        "deterministic_rebuild_verification",
        1,
    )
    _artifact_ref(
        context["proof_publication_manifest_ref"],
        "deterministic_rebuild_verification_publication_manifest",
        1,
    )
    issues_value = data["issues"]
    if not isinstance(issues_value, (tuple, list)):
        raise TypeError("integrity issues must be a sequence")
    issues = tuple(_mapping("integrity issue", value) for value in issues_value)
    grade = None if data["result_grade"] is None else ResultGrade(data["result_grade"])
    canonical_hash = data["canonical_attempt_ref_hash"]
    if canonical_hash is not None:
        _hash("canonical_attempt_ref_hash", canonical_hash)
    if bool(issues) == (grade is not None or canonical_hash is not None):
        raise ValueError("integrity report v2 terminal branch mismatch")
    return _IntegrityReportV2(
        semantic_run_id,
        grade,
        canonical_hash,
        _hash("context_hash", data["context_hash"]),
        context,
        issues,
        data,
    )


def _evidence_entry(value: object) -> _EvidenceEntry:
    data = _exact(
        "evidence entry",
        value,
        frozenset(
            {
                "relative_path",
                "role",
                "artifact_type",
                "schema_version",
                "content_hash",
                "source_hash",
                "byte_count",
            }
        ),
    )
    role = _text("role", data["role"])
    artifact_type = _text("artifact_type", data["artifact_type"])
    if data["schema_version"] != 1:
        raise ValueError("evidence children must use schema version 1")
    byte_count = data["byte_count"]
    if type(byte_count) is not int or byte_count <= 0:
        raise ValueError("evidence byte_count must be positive")
    return _EvidenceEntry(
        _text("relative_path", data["relative_path"]),
        role,
        ArtifactRef(artifact_type, 1, _hash("content_hash", data["content_hash"])),
        _hash("source_hash", data["source_hash"]),
        byte_count,
    )


def _read_evidence_manifest(value: object) -> _EvidenceManifest:
    data = _exact(
        "evidence manifest",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "semantic_run_id",
                "attempt_id",
                "status",
                "terminal_outcome",
                "artifacts",
                "market_bundle_ref_hash",
                "attempt_record_hash",
                "deployment_authorized",
                "manifest_hash",
            }
        ),
    )
    if data["type"] != "evidence_manifest_identity" or data["schema_version"] != 1:
        raise ValueError("evidence manifest identity tag mismatch")
    _false("deployment_authorized", data["deployment_authorized"])
    status = data["status"]
    outcomes = {
        "READY_FOR_INTEGRITY": None,
        "BLOCKED": "BLOCKED",
        "FAILED": "FAILED",
        "CANCELLED": "CANCELLED",
    }
    if status not in outcomes or data["terminal_outcome"] != outcomes[status]:
        raise ValueError("evidence status/outcome mismatch")
    if not isinstance(data["artifacts"], (tuple, list)):
        raise TypeError("evidence artifacts must be a sequence")
    artifacts = tuple(_evidence_entry(item) for item in data["artifacts"])
    paths = tuple(item.relative_path for item in artifacts)
    roles = tuple(item.role for item in artifacts)
    if (
        paths != tuple(sorted(paths))
        or len(paths) != len(set(paths))
        or len(roles) != len(set(roles))
    ):
        raise ValueError("evidence entries must be unique and canonically ordered")
    branch = _EVIDENCE_BRANCH_LAYOUT[status]
    expected_layout = {
        **_EVIDENCE_COMMON_LAYOUT,
        branch[0]: branch[1:],
    }
    actual_layout = {
        item.role: (
            item.relative_path,
            item.artifact_ref.artifact_type,
            item.artifact_ref.schema_version,
        )
        for item in artifacts
    }
    if actual_layout != expected_layout:
        raise ValueError("evidence role/path/schema layout mismatch")
    identity = dict(data)
    manifest_hash = _hash("manifest_hash", identity.pop("manifest_hash"))
    if canonical_sha256(identity) != manifest_hash:
        raise ValueError("evidence manifest hash mismatch")
    _hash("market_bundle_ref_hash", data["market_bundle_ref_hash"])
    _hash("attempt_record_hash", data["attempt_record_hash"])
    return _EvidenceManifest(
        _run(data["semantic_run_id"]),
        _attempt(data["attempt_id"]),
        status,
        data["terminal_outcome"],
        manifest_hash,
        artifacts,
        data,
    )


def _read_engine_summary(value: object) -> _EngineSummary:
    fields = frozenset(
        {
            "type",
            "schema_version",
            "case_hash",
            "target_stream_digest",
            "trace",
            "decision_batches",
            "allocations",
            "approved_targets",
            "normalized_targets",
            "order_plans",
            "order_streams",
            "fills",
            "slippage_decisions",
            "fee_assessments",
            "final_journal",
            "final_ledger_state",
            "final_portfolio_snapshot",
            "run_end_report",
            "financial_artifacts",
        }
    )
    data = _exact("engine execution result", value, fields)
    if data["type"] != "engine_execution_result" or data["schema_version"] != 1:
        raise ValueError("engine result must be engine_execution_result@1")
    fills = data["fills"]
    if not isinstance(fills, (tuple, list)):
        raise TypeError("engine fills must be a sequence")
    return _EngineSummary(
        _hash("case_hash", data["case_hash"]),
        _hash("target_stream_digest", data["target_stream_digest"]),
        fills,
        _mapping("final_journal", data["final_journal"]),
        _mapping("final_portfolio_snapshot", data["final_portfolio_snapshot"]),
        data,
    )


def _read_resolution_failure(value: object) -> _ResolutionFailure:
    data = _exact(
        "resolution failure",
        value,
        frozenset({"type", "code", "request_hash", "subjects", "compatibility_report"}),
    )
    if data["type"] != "backtest_resolution_failure":
        raise ValueError("resolution failure type mismatch")
    if data["code"] not in {"profile_not_found", "incompatible_environment"}:
        raise ValueError("unsupported resolution failure code")
    _hash("request_hash", data["request_hash"])
    subjects = data["subjects"]
    if not isinstance(subjects, (tuple, list)) or any(
        type(item) is not str or not item for item in subjects
    ):
        raise TypeError("resolution failure subjects must be canonical text")
    if tuple(subjects) != tuple(sorted(set(subjects))):
        raise ValueError("resolution failure subjects must be unique and sorted")
    report = data["compatibility_report"]
    if data["code"] == "profile_not_found" and report is not None:
        raise ValueError("profile-not-found failure cannot carry compatibility report")
    if data["code"] == "incompatible_environment":
        report_data = _mapping("compatibility_report", report)
        compatible = report_data.get("compatible")
        if (
            report_data.get("type") != "environment_compatibility_report"
            or type(compatible) is not bool
            or compatible
        ):
            raise ValueError("incompatible failure requires failed compatibility report")
    return _ResolutionFailure(data)


def _read_analysis(value: object) -> _DecodedAnalysis:
    data = _exact(
        "backtest analysis",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "metric_profile_ref",
                "source_publication_ref",
                "source_execution_result_hash",
                "simple_period_return",
                "trade_count",
                "result_grade",
            }
        ),
    )
    if data["type"] != "backtest_analysis" or data["schema_version"] != 1:
        raise ValueError("analysis must be backtest_analysis@1")
    analysis = BacktestAnalysis(
        _artifact_ref(data["metric_profile_ref"], "backtest_metric_profile", 1),
        _publication_ref(data["source_publication_ref"]),
        data["source_execution_result_hash"],
        data["simple_period_return"],
        data["trade_count"],
        ResultGrade(data["result_grade"]),
    )
    if canonical_bytes(analysis) != canonical_bytes(data):
        raise ValueError("analysis did not reconstruct exactly")
    return _DecodedAnalysis(analysis)


def _read_analysis_v2(value: object) -> _DecodedAnalysisV2:
    data = _exact(
        "backtest analysis v2",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "metric_profile_ref",
                "source_publication_ref",
                "source_execution_result_hash",
                "simple_period_return",
                "trade_count",
                "result_grade",
            }
        ),
    )
    if data["type"] != "backtest_analysis" or data["schema_version"] != 2:
        raise ValueError("analysis must be backtest_analysis@2")
    publication_data = _exact(
        "source publication ref v2",
        data["source_publication_ref"],
        frozenset({"type", "artifact_ref"}),
    )
    if publication_data["type"] != "backtest_canonical_publication_ref_v2":
        raise ValueError("analysis v2 source publication ref type mismatch")
    publication_ref = BacktestCanonicalPublicationRefV2.from_artifact_ref(
        _artifact_ref(
            publication_data["artifact_ref"],
            "canonical_publication_manifest",
            2,
        )
    )
    analysis = BacktestAnalysisV2(
        _artifact_ref(data["metric_profile_ref"], "backtest_metric_profile", 1),
        publication_ref,
        data["source_execution_result_hash"],
        data["simple_period_return"],
        data["trade_count"],
        ResultGrade(data["result_grade"]),
    )
    if canonical_bytes(analysis) != canonical_bytes(data):
        raise ValueError("analysis v2 did not reconstruct exactly")
    return _DecodedAnalysisV2(analysis)


def _read_metric_profile(value: object) -> _DecodedMetricProfile:
    data = _mapping("metric profile", value)
    version = data.get("profile_version")
    if type(version) is not int:
        raise TypeError("metric profile version must be int")
    profile = BacktestMetricProfile(
        _text("profile_key", data.get("profile_key")),
        version,
    )
    if canonical_bytes(profile) != canonical_bytes(data):
        raise ValueError("metric profile did not reconstruct exactly")
    return _DecodedMetricProfile(profile)


def _read_integrity_evaluation(value: object) -> _IntegrityEvaluation:
    data = _exact(
        "integrity evaluation record",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "evaluation_id",
                "semantic_run_id",
                "outcome",
                "integrity_report_hash",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "integrity_evaluation_record" or data["schema_version"] != 1:
        raise ValueError("integrity evaluation must be integrity_evaluation_record@1")
    _text("evaluation_id", data["evaluation_id"])
    if data["outcome"] not in {"BLOCKED", "FAILED"}:
        raise ValueError("invalid integrity evaluation outcome")
    _false("deployment_authorized", data["deployment_authorized"])
    return _IntegrityEvaluation(
        _text("evaluation_id", data["evaluation_id"]),
        _run(data["semantic_run_id"]),
        data["outcome"],
        _hash("integrity_report_hash", data["integrity_report_hash"]),
        data,
    )


def _read_integrity_evaluation_v2(value: object) -> _IntegrityEvaluation:
    data = _exact(
        "integrity evaluation record v2",
        value,
        frozenset(
            {
                "type",
                "schema_version",
                "evaluation_id",
                "semantic_run_id",
                "outcome",
                "integrity_report_hash",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "integrity_evaluation_record" or data["schema_version"] != 2:
        raise ValueError("integrity evaluation must be integrity_evaluation_record@2")
    evaluation_id = _text("evaluation_id", data["evaluation_id"])
    if not evaluation_id.startswith("evaluation_"):
        raise ValueError("integrity evaluation v2 id mismatch")
    if data["outcome"] not in {"BLOCKED", "FAILED"}:
        raise ValueError("invalid integrity evaluation v2 outcome")
    _false("deployment_authorized", data["deployment_authorized"])
    return _IntegrityEvaluation(
        evaluation_id,
        _run(data["semantic_run_id"]),
        data["outcome"],
        _hash("integrity_report_hash", data["integrity_report_hash"]),
        data,
    )


def _read_attempt_record(value: object) -> _DecodedEvidenceChild:
    data = _exact(
        "attempt execution record",
        value,
        frozenset(
            {
                "type",
                "status",
                "terminal_outcome",
                "ready_to_finalize",
                "blocked_report",
                "failed_report",
                "cancelled_report",
            }
        ),
    )
    if data["type"] != "attempt_execution_record":
        raise ValueError("attempt record type mismatch")
    if data["status"] not in {"READY_TO_FINALIZE", "BLOCKED", "FAILED", "CANCELLED"}:
        raise ValueError("invalid attempt record status")
    return _DecodedEvidenceChild("attempt_execution_record", data)


def _read_backtest_request(value: object) -> _DecodedEvidenceChild:
    fields = frozenset(
        {
            "type",
            "schema_version",
            "experiment_id",
            "market_bundle_ref",
            "market_semantics_profile_key",
            "simulation_profile_key",
            "execution_account_profile_key",
            "execution_account_id",
            "strategy_family",
            "engine_kind",
            "timeline_window",
            "reporting_currency",
            "result_grade_requested",
            "master_random_seed",
            "build_artifact_manifest_hash",
            "target_stream_digest",
            "execution_case_semantic_hash",
        }
    )
    data = _exact("backtest request", value, fields)
    if data["type"] != "backtest_request" or data["schema_version"] != 1:
        raise ValueError("backtest request tag mismatch")
    return _DecodedEvidenceChild("backtest_request", data)


def _read_build_manifest(value: object) -> _DecodedEvidenceChild:
    data = _exact(
        "build artifact manifest",
        value,
        frozenset({"type", "identity", "manifest_hash", "provenance"}),
    )
    if data["type"] != "build_artifact_manifest":
        raise ValueError("build artifact manifest type mismatch")
    _hash("manifest_hash", data["manifest_hash"])
    return _DecodedEvidenceChild("build_artifact_manifest", data)


def _read_market_bundle_ref(value: object) -> _DecodedEvidenceChild:
    data = _exact(
        "market bundle ref", value, frozenset({"type", "bundle_key", "manifest_hash"})
    )
    if data["type"] != "market_bundle_ref":
        raise ValueError("market bundle ref type mismatch")
    _text("bundle_key", data["bundle_key"])
    _hash("manifest_hash", data["manifest_hash"])
    return _DecodedEvidenceChild("market_bundle_ref", data)


def _read_environment(value: object) -> _DecodedEvidenceChild:
    data = _exact(
        "resolved environment",
        value,
        frozenset(
            {
                "type",
                "market_semantics",
                "simulation",
                "execution_account",
                "market_bundle_ref",
                "compatibility_report",
                "limitations",
                "deployment_authorized",
            }
        ),
    )
    if data["type"] != "resolved_backtest_environment":
        raise ValueError("resolved environment type mismatch")
    _false("deployment_authorized", data["deployment_authorized"])
    return _DecodedEvidenceChild("resolved_backtest_environment", data)


def _read_compatibility(value: object) -> _DecodedEvidenceChild:
    data = _exact(
        "environment compatibility report",
        value,
        frozenset(
            {
                "type",
                "request_hash",
                "market_bundle_manifest_hash",
                "profile_digests",
                "checks",
                "compatible",
                "failed_codes",
                "allowed_grade",
                "limitations",
            }
        ),
    )
    if data["type"] != "environment_compatibility_report" or type(data["compatible"]) is not bool:
        raise ValueError("environment compatibility report mismatch")
    return _DecodedEvidenceChild("environment_compatibility_report", data)


def _read_attempt_issue_report(value: object, artifact_type: str, payload_type: str) -> _DecodedEvidenceChild:
    data = _exact(
        artifact_type,
        value,
        frozenset(
            {
                "type",
                "attempt",
                "resolved_request",
                "input_origin",
                "execution_case_hash",
                "issue",
                "trace_hash",
            }
        ),
    )
    if data["type"] != payload_type:
        raise ValueError(f"{artifact_type} type mismatch")
    return _DecodedEvidenceChild(artifact_type, data)


def _read_blocked_report(value: object) -> _DecodedEvidenceChild:
    return _read_attempt_issue_report(value, "blocked_run_report", "blocked_attempt_report")


def _read_failure_report(value: object) -> _DecodedEvidenceChild:
    return _read_attempt_issue_report(value, "failure_report", "failed_attempt_report")


def _read_cancellation_report(value: object) -> _DecodedEvidenceChild:
    data = _exact(
        "cancellation report",
        value,
        frozenset(
            {
                "type",
                "attempt",
                "resolved_request",
                "input_origin",
                "execution_case_hash",
                "cancellation",
            }
        ),
    )
    if data["type"] != "cancelled_attempt_report":
        raise ValueError("cancellation report type mismatch")
    return _DecodedEvidenceChild("cancellation_report", data)


def _read_durable_verification(value: object):
    from ._durable_rebuild import _read_verification

    return _read_verification(value)


def _read_durable_proof_manifest(value: object):
    from ._durable_rebuild import _read_proof_manifest

    return _read_proof_manifest(value)


_CATALOG = SchemaCatalog(
    (
        ArtifactSchemaRegistration("canonical_publication_manifest", 1, _read_canonical_manifest),
        ArtifactSchemaRegistration("canonical_publication_manifest", 2, _read_canonical_manifest_v2),
        ArtifactSchemaRegistration("canonical_attempt_ref", 1, _read_canonical_attempt),
        ArtifactSchemaRegistration("canonical_attempt_ref", 2, _read_canonical_attempt_v2),
        ArtifactSchemaRegistration("completed_backtest_result", 1, _read_completed_result_v1),
        ArtifactSchemaRegistration("completed_backtest_result", 2, _read_completed_result),
        ArtifactSchemaRegistration("completed_backtest_result", 3, _read_completed_result_v3),
        ArtifactSchemaRegistration("evidence_manifest", 1, _read_evidence_manifest),
        ArtifactSchemaRegistration("engine_execution_result", 1, _read_engine_summary),
        ArtifactSchemaRegistration("backtest_resolution_failure", 1, _read_resolution_failure),
        ArtifactSchemaRegistration("backtest_analysis", 1, _read_analysis),
        ArtifactSchemaRegistration("backtest_analysis", 2, _read_analysis_v2),
        ArtifactSchemaRegistration("backtest_metric_profile", 1, _read_metric_profile),
        ArtifactSchemaRegistration("integrity_report", 1, _read_integrity_report),
        ArtifactSchemaRegistration("integrity_report", 2, _read_integrity_report_v2),
        ArtifactSchemaRegistration(
            "deterministic_rebuild_verification",
            1,
            _read_durable_verification,
        ),
        ArtifactSchemaRegistration(
            "deterministic_rebuild_verification_publication_manifest",
            1,
            _read_durable_proof_manifest,
        ),
        ArtifactSchemaRegistration("integrity_evaluation_record", 1, _read_integrity_evaluation),
        ArtifactSchemaRegistration("integrity_evaluation_record", 2, _read_integrity_evaluation_v2),
        ArtifactSchemaRegistration("attempt_execution_record", 1, _read_attempt_record),
        ArtifactSchemaRegistration("backtest_request", 1, _read_backtest_request),
        ArtifactSchemaRegistration("blocked_run_report", 1, _read_blocked_report),
        ArtifactSchemaRegistration("build_artifact_manifest", 1, _read_build_manifest),
        ArtifactSchemaRegistration("cancellation_report", 1, _read_cancellation_report),
        ArtifactSchemaRegistration("environment_compatibility_report", 1, _read_compatibility),
        ArtifactSchemaRegistration("failure_report", 1, _read_failure_report),
        ArtifactSchemaRegistration("market_bundle_ref", 1, _read_market_bundle_ref),
        ArtifactSchemaRegistration("resolved_backtest_environment", 1, _read_environment),
    )
)


class BacktestEvidenceRepository:
    def __init__(self, reader: ArtifactEnvelopeReader) -> None:
        self._reader = reader

    def _read_expected(
        self,
        ref: ArtifactRef,
        expected_type: str,
        expected_version: int,
        *,
        root: bool,
    ) -> _Loaded:
        if type(ref) is not ArtifactRef:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "exact ArtifactRef required",
            )
        if ref.artifact_type != expected_type or ref.schema_version != expected_version:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                f"ref must target {expected_type}@{expected_version}",
            )
        try:
            provider_result = self._reader.read(ref=ref)
        except ArtifactNotFoundError as error:
            code = (
                BacktestEvidenceFailureCode.PORT_REF_NOT_FOUND
                if root
                else BacktestEvidenceFailureCode.PORT_RETENTION_UNAVAILABLE
            )
            raise BacktestEvidenceError(code, str(error)) from error
        except ArtifactRetentionUnavailableError as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_RETENTION_UNAVAILABLE, str(error)
            ) from error
        except ArtifactIntegrityError as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED, str(error)
            ) from error
        if type(provider_result) is not ArtifactReadResult:
            raise TypeError("reader must return exact ArtifactReadResult")
        try:
            parsed = _CATALOG.read(provider_result.source_bytes)
        except ArtifactIntegrityError as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED, str(error)
            ) from error
        except ArtifactDecodeError as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID, str(error)
            ) from error
        parsed_ref = ArtifactRef.from_envelope(parsed.envelope)
        if parsed_ref != ref:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED,
                "requested ref does not bind source bytes",
            )
        return _Loaded(parsed.artifact, parsed.source_bytes, parsed.source_hash)

    def _read_entry(self, entry: _PublicationEntry | _EvidenceEntry) -> _Loaded:
        loaded = self._read_expected(
            entry.artifact_ref,
            entry.artifact_ref.artifact_type,
            entry.artifact_ref.schema_version,
            root=False,
        )
        if loaded.source_hash != entry.source_hash:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID,
                "manifest source hash does not bind child source bytes",
            )
        if len(loaded.source_bytes) != entry.byte_count:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID,
                "manifest byte count does not bind child source bytes",
            )
        return loaded

    def _read_evidence_children(
        self, evidence: _EvidenceManifest
    ) -> dict[str, _Loaded]:
        children = {
            entry.role: self._read_entry(entry) for entry in evidence.artifacts
        }
        common: dict[str, _DecodedEvidenceChild] = {}
        for role in _EVIDENCE_COMMON_LAYOUT:
            artifact = children[role].artifact
            if type(artifact) is not _DecodedEvidenceChild:
                raise TypeError(f"wrong {role} decoder result")
            common[role] = artifact

        request = common["request"].raw
        environment = common["environment"].raw
        build = common["build_artifact_manifest"].raw
        market = common["market_bundle_reference"].raw
        compatibility = common["environment_compatibility"].raw
        record = common["attempt_execution_record"].raw

        if canonical_sha256(market) != evidence.raw["market_bundle_ref_hash"]:
            raise ValueError("evidence market bundle ref hash mismatch")
        if canonical_sha256(record) != evidence.raw["attempt_record_hash"]:
            raise ValueError("evidence attempt record hash mismatch")
        if canonical_bytes(request["market_bundle_ref"]) != canonical_bytes(market):
            raise ValueError("request market bundle ref mismatch")
        if canonical_bytes(environment["market_bundle_ref"]) != canonical_bytes(market):
            raise ValueError("environment market bundle ref mismatch")
        if compatibility["market_bundle_manifest_hash"] != market["manifest_hash"]:
            raise ValueError("compatibility market bundle manifest mismatch")
        if canonical_bytes(environment["compatibility_report"]) != canonical_bytes(
            compatibility
        ):
            raise ValueError("environment compatibility report mismatch")
        if compatibility["request_hash"] != canonical_sha256(request):
            raise ValueError("compatibility request hash mismatch")
        if request["build_artifact_manifest_hash"] != build["manifest_hash"]:
            raise ValueError("request build manifest hash mismatch")

        record_status = {
            "READY_FOR_INTEGRITY": "READY_TO_FINALIZE",
            "BLOCKED": "BLOCKED",
            "FAILED": "FAILED",
            "CANCELLED": "CANCELLED",
        }[evidence.status]
        if (
            record["status"] != record_status
            or record["terminal_outcome"] != evidence.terminal_outcome
        ):
            raise ValueError("attempt record status/outcome mismatch")
        record_branch = {
            "READY_FOR_INTEGRITY": "ready_to_finalize",
            "BLOCKED": "blocked_report",
            "FAILED": "failed_report",
            "CANCELLED": "cancelled_report",
        }[evidence.status]
        branch_values = {
            name: record[name]
            for name in (
                "ready_to_finalize",
                "blocked_report",
                "failed_report",
                "cancelled_report",
            )
        }
        if branch_values[record_branch] is None or any(
            value is not None
            for name, value in branch_values.items()
            if name != record_branch
        ):
            raise ValueError("attempt record branch mismatch")
        branch_role = _EVIDENCE_BRANCH_LAYOUT[evidence.status][0]
        branch_artifact = children[branch_role].artifact
        if type(branch_artifact) is _EngineSummary or type(branch_artifact) is _DecodedEvidenceChild:
            branch_raw = branch_artifact.raw
        else:
            raise TypeError("wrong evidence branch decoder result")
        nested_branch = _mapping("attempt record branch", branch_values[record_branch])
        resolved = _mapping(
            "attempt record resolved request", nested_branch["resolved_request"]
        )
        if resolved["semantic_run_id"] != evidence.semantic_run_id:
            raise ValueError("attempt record semantic run mismatch")
        if canonical_bytes(resolved["request"]) != canonical_bytes(request):
            raise ValueError("attempt record request mismatch")
        if canonical_bytes(resolved["environment"]) != canonical_bytes(environment):
            raise ValueError("attempt record environment mismatch")
        if resolved["build_artifact_manifest_hash"] != build["manifest_hash"]:
            raise ValueError("attempt record build manifest mismatch")
        if evidence.status == "READY_FOR_INTEGRITY":
            nested_branch = _mapping(
                "ready-to-finalize engine result", nested_branch["engine_result"]
            )
        if canonical_bytes(nested_branch) != canonical_bytes(branch_raw):
            raise ValueError("attempt record branch artifact mismatch")
        return children

    def load_completed(
        self, ref: BacktestCanonicalPublicationRef
    ) -> VerifiedCompletedPublicationV2:
        if type(ref) is not BacktestCanonicalPublicationRef:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "exact BacktestCanonicalPublicationRef required",
            )
        try:
            return self._load_completed(ref, root=True)
        except BacktestEvidenceError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID, str(error)
            ) from error

    def _load_completed(
        self, ref: BacktestCanonicalPublicationRef, *, root: bool
    ) -> VerifiedCompletedPublicationV2:
        loaded_manifest = self._read_expected(
            ref.artifact_ref,
            "canonical_publication_manifest",
            1,
            root=root,
        )
        manifest = loaded_manifest.artifact
        if type(manifest) is not _CanonicalManifest:
            raise TypeError("catalog returned wrong canonical manifest type")
        if (
            manifest.publication_kind != "canonical"
            or manifest.publication_id != "canonical-v2"
        ):
            raise ValueError("completed publication must be canonical/canonical-v2")
        expected = {
            "canonical-attempt-ref.json": ("canonical_attempt_ref", 1),
            "integrity.json": ("integrity_report", 1),
            "result.json": ("completed_backtest_result", 2),
        }
        entries = {entry.relative_path: entry for entry in manifest.artifacts}
        if set(entries) != set(expected):
            raise ValueError("completed manifest does not exact-cover children")
        for path, (artifact_type, version) in expected.items():
            child_ref = entries[path].artifact_ref
            if child_ref.artifact_type != artifact_type or child_ref.schema_version != version:
                raise ValueError(f"completed manifest {path} schema mismatch")

        attempt_loaded = self._read_entry(entries["canonical-attempt-ref.json"])
        integrity_loaded = self._read_entry(entries["integrity.json"])
        result_loaded = self._read_entry(entries["result.json"])
        attempt = attempt_loaded.artifact
        integrity = integrity_loaded.artifact
        result = result_loaded.artifact
        if type(attempt) is not _CanonicalAttempt:
            raise TypeError("wrong canonical attempt decoder result")
        if type(integrity) is not _IntegrityReport:
            raise TypeError("wrong integrity report decoder result")
        if type(result) is not _CompletedResult:
            raise TypeError("wrong completed result decoder result")

        if result.canonical_attempt_ref_hash != canonical_sha256(attempt.raw):
            raise ValueError("completed result canonical attempt hash mismatch")
        if result.integrity_report_hash != canonical_sha256(integrity.raw):
            raise ValueError("completed result integrity report hash mismatch")
        if integrity.context_hash != canonical_sha256(integrity.context):
            raise ValueError("integrity context hash mismatch")
        if integrity.canonical_attempt_ref_hash != result.canonical_attempt_ref_hash:
            raise ValueError("integrity canonical attempt hash mismatch")
        if integrity.result_grade is not result.result_grade:
            raise ValueError("result grade mismatch")
        if not (
            manifest.semantic_run_id
            == result.semantic_run_id
            == attempt.semantic_run_id
            == integrity.semantic_run_id
        ):
            raise ValueError("completed semantic run mismatch")

        resolved_request = _mapping(
            "integrity resolved request", integrity.context["resolved_request"]
        )
        if canonical_bytes(result.resolved_request) != canonical_bytes(resolved_request):
            raise ValueError("completed resolved request mismatch")
        request = _mapping("resolved request request", resolved_request["request"])
        if result.request_hash != canonical_sha256(request):
            raise ValueError("completed request hash mismatch")
        if resolved_request["semantic_run_id"] != result.semantic_run_id:
            raise ValueError("resolved request semantic run mismatch")
        if result.attempt_id != attempt.attempt_id:
            raise ValueError("completed attempt id mismatch")

        context_consistency = _mapping(
            "context attempt consistency set", integrity.context["attempt_consistency_set"]
        )
        if canonical_bytes(result.attempt_consistency_set) != canonical_bytes(
            context_consistency
        ):
            raise ValueError("completed attempt consistency set mismatch")
        if result.consistency_set_hash != canonical_sha256(context_consistency):
            raise ValueError("completed consistency set hash mismatch")
        if attempt.consistency_set_hash != result.consistency_set_hash:
            raise ValueError("canonical attempt consistency set hash mismatch")
        context_hash_check = _mapping(
            "context execution hash check", integrity.context["execution_hash_check"]
        )
        if canonical_bytes(result.execution_hash_check) != canonical_bytes(
            context_hash_check
        ):
            raise ValueError("completed execution hash check mismatch")
        consistency = _mapping("execution hash consistency", context_hash_check["consistency"])
        if context_hash_check.get("mismatch") is not None:
            raise ValueError("completed execution hash check cannot contain mismatch")
        if consistency["execution_result_hash"] != result.execution_result_hash:
            raise ValueError("execution hash consistency mismatch")
        if attempt.execution_result_hash != result.execution_result_hash:
            raise ValueError("canonical attempt execution hash mismatch")

        rebuild = _mapping("rebuild evidence", integrity.context["rebuild_evidence"])
        if rebuild["semantic_run_id"] != result.semantic_run_id:
            raise ValueError("rebuild semantic run mismatch")
        if rebuild["request_hash"] != result.request_hash:
            raise ValueError("rebuild request hash mismatch")
        if rebuild["execution_case_hash"] != attempt.execution_case_hash:
            raise ValueError("rebuild case hash mismatch")
        if rebuild["execution_case_semantic_hash"] != attempt.execution_case_semantic_hash:
            raise ValueError("rebuild semantic hash mismatch")
        if rebuild["execution_case_semantic_hash"] != request["execution_case_semantic_hash"]:
            raise ValueError("rebuild request semantic hash mismatch")
        if rebuild["target_stream_digest"] != request["target_stream_digest"]:
            raise ValueError("rebuild request target stream mismatch")
        if rebuild["execution_result_hash"] != result.execution_result_hash:
            raise ValueError("rebuild execution result hash mismatch")
        if attempt.raw["deterministic_rebuild_evidence_hash"] != canonical_sha256(rebuild):
            raise ValueError("canonical attempt rebuild evidence hash mismatch")

        evidence_loaded = self._read_expected(
            result.evidence_manifest_ref,
            "evidence_manifest",
            1,
            root=False,
        )
        evidence = evidence_loaded.artifact
        if type(evidence) is not _EvidenceManifest:
            raise TypeError("wrong evidence manifest decoder result")
        if (
            evidence.status != "READY_FOR_INTEGRITY"
            or evidence.terminal_outcome is not None
        ):
            raise ValueError("completed evidence is not ready for integrity")
        if evidence.semantic_run_id != result.semantic_run_id:
            raise ValueError("evidence semantic run mismatch")
        if evidence.attempt_id != result.attempt_id:
            raise ValueError("evidence attempt id mismatch")
        if evidence.manifest_hash != result.evidence_manifest_hash:
            raise ValueError("result evidence manifest hash mismatch")
        if evidence.manifest_hash != attempt.evidence_manifest_hash:
            raise ValueError("canonical attempt evidence manifest hash mismatch")
        if evidence_loaded.source_hash != attempt.evidence_manifest_source_hash:
            raise ValueError("canonical attempt evidence source hash mismatch")
        finalized_identity = {
            "type": "finalized_attempt_evidence",
            "schema_version": 1,
            "attempt": attempt.raw["attempt"],
            "status": evidence.status,
            "terminal_outcome": evidence.terminal_outcome,
            "manifest_hash": evidence.manifest_hash,
            "manifest_source_hash": evidence_loaded.source_hash,
            "relative_directory": (
                f"runs/{evidence.semantic_run_id}/attempts/{evidence.attempt_id}"
            ),
            "deployment_authorized": False,
        }
        if canonical_sha256(finalized_identity) != attempt.evidence_publication_hash:
            raise ValueError("canonical evidence publication hash mismatch")
        finalized_hashes = context_consistency["finalized_evidence_hashes"]
        if attempt.evidence_publication_hash not in finalized_hashes:
            raise ValueError("canonical evidence publication hash is not retained")

        evidence_children = self._read_evidence_children(evidence)
        engine_entry = next(
            entry
            for entry in evidence.artifacts
            if entry.role == "engine_execution_result"
        )
        if (
            engine_entry.artifact_ref.content_hash
            != attempt.engine_result_artifact_content_hash
        ):
            raise ValueError("engine result content hash mismatch")
        engine = evidence_children["engine_execution_result"].artifact
        if type(engine) is not _EngineSummary:
            raise TypeError("wrong engine summary decoder result")
        if engine.case_hash != attempt.execution_case_hash:
            raise ValueError("engine result case hash mismatch")
        if engine.target_stream_digest != rebuild["target_stream_digest"]:
            raise ValueError("engine result target stream mismatch")
        summary_raw = dict(engine.raw)
        summary_raw["type"] = "canonical_execution_summary"
        del summary_raw["case_hash"]
        del summary_raw["target_stream_digest"]
        if canonical_sha256(summary_raw) != result.execution_result_hash:
            raise ValueError("canonical execution summary hash mismatch")

        engine_context = _exact(
            "engine execution context",
            result.engine_context,
            frozenset(
                {
                    "type",
                    "schema_version",
                    "semantic_run_id",
                    "semantic_spec_hash",
                    "case_hash",
                    "target_stream_digest",
                    "identity_manifest_hash",
                    "financial_state",
                }
            ),
        )
        if (
            engine_context["type"] != "engine_execution_context"
            or engine_context["schema_version"] != 1
        ):
            raise ValueError("engine execution context tag mismatch")
        if engine_context["semantic_run_id"] != result.semantic_run_id:
            raise ValueError("engine context semantic run mismatch")
        if engine_context["semantic_spec_hash"] != attempt.execution_case_semantic_hash:
            raise ValueError("engine context semantic hash mismatch")
        if engine_context["case_hash"] != engine.case_hash:
            raise ValueError("engine context case hash mismatch")
        if engine_context["target_stream_digest"] != engine.target_stream_digest:
            raise ValueError("engine context target stream mismatch")
        engine_context_value = EngineExecutionContext(
            result.semantic_run_id,
            engine_context["semantic_spec_hash"],
            engine_context["case_hash"],
            engine_context["target_stream_digest"],
            _hash("identity_manifest_hash", engine_context["identity_manifest_hash"]),
            _read_financial_state(engine_context["financial_state"]),
        )
        if canonical_bytes(engine_context_value) != canonical_bytes(engine_context):
            raise ValueError("engine context did not reconstruct exactly")

        fills = tuple(_read_fill(item) for item in engine.fills)
        final_journal = _read_journal(engine.final_journal)
        final_snapshot = _read_portfolio_snapshot(engine.final_portfolio_snapshot)
        summary = VerifiedExecutionSummary(fills, final_journal, final_snapshot)
        request_currency = _exact(
            "request reporting currency",
            request["reporting_currency"],
            frozenset({"type", "value"}),
        )
        if request_currency["type"] != "currency_id":
            raise ValueError("request reporting currency type mismatch")
        reporting_currency = CurrencyId(request_currency["value"])
        if engine_context_value.target_stream_digest != rebuild["target_stream_digest"]:
            raise ValueError("engine context rebuild target mismatch")
        return VerifiedCompletedPublicationV2(
            ref,
            result.semantic_run_id,
            result.execution_result_hash,
            result.result_grade,
            reporting_currency,
            engine_context_value,
            summary,
        )

    def load_completed_v3(
        self, ref: BacktestCanonicalPublicationRefV2
    ) -> VerifiedCompletedPublicationV3:
        if type(ref) is not BacktestCanonicalPublicationRefV2:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "exact BacktestCanonicalPublicationRefV2 required",
            )
        try:
            return self._load_completed_v3(ref, root=True)
        except BacktestEvidenceError:
            raise
        except _CompletedVersionMismatch as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_COMPLETED_VERSION_MISMATCH,
                str(error),
            ) from error
        except _StaticProofMismatch as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_STATIC_PROOF_MISMATCH,
                str(error),
            ) from error
        except (KeyError, TypeError, ValueError) as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID, str(error)
            ) from error

    def _load_completed_v3(
        self,
        ref: BacktestCanonicalPublicationRefV2,
        *,
        root: bool,
    ) -> VerifiedCompletedPublicationV3:
        from ._durable_rebuild import (
            DeterministicRebuildVerificationPublicationManifestV1,
            DeterministicRebuildVerificationV1,
            RebuildComparisonOutcome,
            _read_evidence_role,
            _read_ref,
            _validate_manifest_binding,
            _validate_verification_structure,
        )
        from .evidence import (
            EvidenceArtifactRole,
            EvidenceManifest,
            EvidencePublicationStatus,
            FinalizedAttemptEvidence,
        )
        from .execution_hash import ExecutionResultHasher
        from .runner import AttemptExecutionRecord

        loaded_manifest = self._read_expected(
            ref.artifact_ref,
            "canonical_publication_manifest",
            2,
            root=root,
        )
        manifest = loaded_manifest.artifact
        if type(manifest) is not _CanonicalManifestV2:
            raise TypeError("catalog returned wrong canonical manifest v2 type")
        if (
            manifest.publication_kind != "canonical"
            or manifest.publication_id != "canonical-v3"
        ):
            raise _CompletedVersionMismatch(
                "completed v3 publication must be canonical/canonical-v3"
            )
        expected = {
            "canonical-attempt-ref.json": ("canonical_attempt_ref", 2),
            "integrity.json": ("integrity_report", 2),
            "proof-publication-manifest.json": (
                "deterministic_rebuild_verification_publication_manifest",
                1,
            ),
            "rebuild-verification.json": (
                "deterministic_rebuild_verification",
                1,
            ),
            "result.json": ("completed_backtest_result", 3),
        }
        entries = {entry.relative_path: entry for entry in manifest.artifacts}
        if set(entries) != set(expected):
            raise _CompletedVersionMismatch(
                "completed v3 manifest does not exact-cover children"
            )
        for path, (artifact_type, version) in expected.items():
            child_ref = entries[path].artifact_ref
            if (
                child_ref.artifact_type != artifact_type
                or child_ref.schema_version != version
            ):
                raise _CompletedVersionMismatch(
                    f"completed v3 manifest {path} schema mismatch"
                )

        loaded = {path: self._read_entry(entry) for path, entry in entries.items()}
        attempt = loaded["canonical-attempt-ref.json"].artifact
        integrity = loaded["integrity.json"].artifact
        proof_manifest = loaded["proof-publication-manifest.json"].artifact
        verification = loaded["rebuild-verification.json"].artifact
        result = loaded["result.json"].artifact
        if (
            type(attempt) is not _CanonicalAttemptV2
            or type(integrity) is not _IntegrityReportV2
            or type(result) is not _CompletedResultV3
            or type(verification) is not DeterministicRebuildVerificationV1
            or type(proof_manifest)
            is not DeterministicRebuildVerificationPublicationManifestV1
        ):
            raise _CompletedVersionMismatch("completed v3 decoder type mismatch")
        verification_ref = entries["rebuild-verification.json"].artifact_ref
        proof_manifest_ref = entries[
            "proof-publication-manifest.json"
        ].artifact_ref
        try:
            _validate_manifest_binding(
                verification,
                verification_ref,
                loaded["rebuild-verification.json"].source_bytes,
                loaded["rebuild-verification.json"].source_hash,
                proof_manifest,
            )
            _validate_verification_structure(verification, self._reader)
        except Exception as error:
            raise _StaticProofMismatch("durable proof static graph mismatch") from error

        if (
            attempt.rebuild_verification_ref != verification_ref
            or attempt.rebuild_verification_source_hash
            != loaded["rebuild-verification.json"].source_hash
            or attempt.proof_publication_manifest_ref != proof_manifest_ref
            or attempt.proof_publication_manifest_source_hash
            != loaded["proof-publication-manifest.json"].source_hash
            or result.rebuild_verification_ref != verification_ref
            or result.proof_publication_manifest_ref != proof_manifest_ref
            or integrity.context["rebuild_verification_ref"]
            != verification_ref.to_canonical_dict()
            or integrity.context["proof_publication_manifest_ref"]
            != proof_manifest_ref.to_canonical_dict()
        ):
            raise _StaticProofMismatch("completed v3 proof reference mismatch")
        if not (
            manifest.semantic_run_id
            == verification.semantic_run_id
            == attempt.attempt.semantic_run_id
            == integrity.semantic_run_id
            == result.semantic_run_id
        ):
            raise ValueError("completed v3 semantic run mismatch")
        first = AttemptIdentity.first(verification.semantic_run_id)
        second = AttemptIdentity.retry(first, next_ordinal=2)
        if (
            tuple(value.attempt for value in verification.attempts)
            != (first, second)
            or attempt.attempt != first
            or result.attempt_id != first.attempt_id
        ):
            raise _StaticProofMismatch("completed v3 canonical Attempt mismatch")
        if any(
            comparison.outcome is not RebuildComparisonOutcome.EQUAL
            for comparison in verification.comparisons
        ):
            raise _StaticProofMismatch("completed v3 proof contains mismatch")

        attempt_hashes = []
        finalized_attempts = []
        resolved_request = None
        for verification_entry in verification.attempts:
            manifest_read = _read_ref(
                self._reader,
                verification_entry.evidence_manifest_ref,
                EvidenceManifest,
            )
            evidence_manifest = manifest_read.artifact
            record_read = _read_evidence_role(
                self._reader,
                evidence_manifest,
                EvidenceArtifactRole.ATTEMPT_EXECUTION_RECORD,
                AttemptExecutionRecord,
            )
            record = record_read.artifact
            if record.ready_to_finalize is None:
                raise _StaticProofMismatch("Attempt record is not ready")
            finalized = FinalizedAttemptEvidence(
                attempt=verification_entry.attempt,
                status=EvidencePublicationStatus.READY_FOR_INTEGRITY,
                terminal_outcome=None,
                manifest=evidence_manifest,
                manifest_source_hash=manifest_read.source_hash,
                relative_directory=(
                    f"runs/{verification.semantic_run_id}/attempts/"
                    f"{verification_entry.attempt.attempt_id}"
                ),
            )
            attempt_hashes.append(
                ExecutionResultHasher.bind(record.ready_to_finalize, finalized)
            )
            finalized_attempts.append(finalized)
            if resolved_request is None:
                resolved_request = record.ready_to_finalize.resolved_request
            elif resolved_request != record.ready_to_finalize.resolved_request:
                raise _StaticProofMismatch("Attempt resolved roots mismatch")
        if resolved_request is None:
            raise _StaticProofMismatch("resolved request is unavailable")
        attempts = AttemptConsistencySet(
            resolved_request,
            tuple(attempt_hashes),
            tuple(finalized_attempts),
        )
        execution_check = ExecutionResultHasher.check_same_semantic_run(
            tuple(attempt_hashes)
        )
        if (
            result.request_hash != verification.request_hash
            or result.resolved_request_hash != canonical_sha256(resolved_request)
            or integrity.context["resolved_request_hash"]
            != result.resolved_request_hash
            or result.consistency_set_hash != attempts.consistency_set_hash
            or attempt.consistency_set_hash != attempts.consistency_set_hash
            or integrity.context["attempt_consistency_set_hash"]
            != attempts.consistency_set_hash
            or integrity.context["execution_hash_check_hash"]
            != canonical_sha256(execution_check)
        ):
            raise _StaticProofMismatch("completed v3 static root hash mismatch")
        if (
            result.canonical_attempt_ref_hash != canonical_sha256(attempt.raw)
            or integrity.canonical_attempt_ref_hash
            != result.canonical_attempt_ref_hash
            or result.integrity_report_hash != canonical_sha256(integrity.raw)
            or integrity.context_hash != canonical_sha256(integrity.context)
            or integrity.context["comparison_outcome"] != "equal"
            or integrity.issues
            or integrity.result_grade is not ResultGrade.DECISION_GRADE
            or result.result_grade is not ResultGrade.DECISION_GRADE
        ):
            raise _StaticProofMismatch("completed v3 Integrity link mismatch")
        first_entry = verification.attempts[0]
        if (
            result.evidence_manifest_ref != first_entry.evidence_manifest_ref
            or attempt.execution_result_hash != first_entry.execution_result_hash
            or result.execution_result_hash != first_entry.execution_result_hash
            or attempt.execution_case_semantic_hash != verification.semantic_spec_hash
            or attempt.execution_case_hash != first_entry.execution_case_hash
            or attempt.trace_hash != first_entry.trace_hash
            or attempt.market_bundle_manifest_hash
            != verification.market_bundle_ref.manifest_hash
        ):
            raise _StaticProofMismatch("completed v3 canonical execution mismatch")

        engine_context = _exact(
            "engine execution context",
            result.engine_context,
            frozenset(
                {
                    "type",
                    "schema_version",
                    "semantic_run_id",
                    "semantic_spec_hash",
                    "case_hash",
                    "target_stream_digest",
                    "identity_manifest_hash",
                    "financial_state",
                }
            ),
        )
        if (
            engine_context["type"] != "engine_execution_context"
            or engine_context["schema_version"] != 1
        ):
            raise ValueError("engine execution context tag mismatch")
        engine_context_value = EngineExecutionContext(
            result.semantic_run_id,
            engine_context["semantic_spec_hash"],
            engine_context["case_hash"],
            engine_context["target_stream_digest"],
            _hash("identity_manifest_hash", engine_context["identity_manifest_hash"]),
            _read_financial_state(engine_context["financial_state"]),
        )
        first_hash = attempt_hashes[0]
        engine = first_hash.engine_result
        if (
            engine_context_value.semantic_spec_hash != verification.semantic_spec_hash
            or engine_context_value.case_hash != first_entry.execution_case_hash
            or engine_context_value.target_stream_digest
            != verification.target_stream_digest
            or canonical_bytes(engine_context_value)
            != canonical_bytes(engine_context)
        ):
            raise ValueError("completed v3 engine context mismatch")
        summary = VerifiedExecutionSummary(
            tuple(engine.fills),
            engine.final_journal,
            engine.final_portfolio_snapshot,
        )
        return VerifiedCompletedPublicationV3(
            ref,
            result.semantic_run_id,
            result.execution_result_hash,
            result.result_grade,
            resolved_request.request.reporting_currency,
            engine_context_value,
            summary,
            verification_ref,
            proof_manifest_ref,
        )

    def _verify_terminal_attempt_context(
        self,
        ref: ArtifactRef,
        *,
        expected_attempt: AttemptIdentity,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        input_origin: InputOrigin,
    ) -> VerifiedTerminalPublication:
        if type(ref) is not ArtifactRef or ref.artifact_type != "evidence_manifest":
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "exact evidence manifest ref required",
            )
        if type(expected_attempt) is not AttemptIdentity:
            raise TypeError("expected_attempt must be exact AttemptIdentity")
        if type(resolved_request) is not ResolvedBacktestRequest:
            raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
        if type(execution_case) is not ResolvedExecutionCase:
            raise TypeError("execution_case must be exact ResolvedExecutionCase")
        if type(input_origin) is not InputOrigin:
            raise TypeError("input_origin must be exact InputOrigin")
        try:
            loaded = self._read_expected(ref, "evidence_manifest", 1, root=True)
            evidence = loaded.artifact
            if type(evidence) is not _EvidenceManifest:
                raise TypeError("wrong evidence manifest decoder result")
            children = self._read_evidence_children(evidence)
            record_artifact = children["attempt_execution_record"].artifact
            if type(record_artifact) is not _DecodedEvidenceChild:
                raise TypeError("wrong attempt record decoder result")
            record = record_artifact.raw
            branch_name = {
                "READY_FOR_INTEGRITY": "ready_to_finalize",
                "BLOCKED": "blocked_report",
                "FAILED": "failed_report",
                "CANCELLED": "cancelled_report",
            }[evidence.status]
            branch = _mapping("attempt terminal branch", record[branch_name])
            branch_resolved = _mapping(
                "attempt terminal resolved request", branch["resolved_request"]
            )
            branch_request = _mapping(
                "attempt terminal public request", branch_resolved["request"]
            )
            if (
                evidence.semantic_run_id != resolved_request.semantic_run_id
                or evidence.attempt_id != expected_attempt.attempt_id
                or canonical_bytes(branch["attempt"])
                != canonical_bytes(expected_attempt)
                or canonical_bytes(branch_resolved)
                != canonical_bytes(resolved_request)
                or canonical_sha256(branch_request)
                != canonical_sha256(resolved_request.request)
                or branch_resolved["semantic_run_id"]
                != resolved_request.semantic_run_id
                or branch["execution_case_hash"] != execution_case.case_hash
                or branch["input_origin"] != input_origin.value
                or resolved_request.request.execution_case_semantic_hash
                != execution_case.semantic_spec_hash
                or branch_request["execution_case_semantic_hash"]
                != execution_case.semantic_spec_hash
            ):
                raise ValueError("terminal Attempt context mismatch")
            if evidence.status == "READY_FOR_INTEGRITY":
                raise BacktestEvidenceError(
                    BacktestEvidenceFailureCode.PORT_TERMINAL_NOT_ANALYZABLE,
                    "completed evidence is not terminal",
                )
            return VerifiedTerminalPublication(
                TerminalStatus(evidence.status),
                ref,
            )
        except BacktestEvidenceError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID,
                str(error),
            ) from error

    def load_terminal(self, ref: ArtifactRef) -> VerifiedTerminalPublication:
        if type(ref) is not ArtifactRef:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "exact ArtifactRef required",
            )
        allowed = {
            ("backtest_resolution_failure", 1),
            ("evidence_manifest", 1),
            ("canonical_publication_manifest", 1),
            ("canonical_publication_manifest", 2),
        }
        if (ref.artifact_type, ref.schema_version) not in allowed:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "unsupported terminal ref type",
            )
        try:
            return self._load_terminal(ref)
        except BacktestEvidenceError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID, str(error)
            ) from error

    def _load_terminal(self, ref: ArtifactRef) -> VerifiedTerminalPublication:
        if ref.artifact_type == "backtest_resolution_failure":
            loaded = self._read_expected(
                ref, "backtest_resolution_failure", 1, root=True
            )
            if type(loaded.artifact) is not _ResolutionFailure:
                raise TypeError("wrong resolution failure decoder result")
            return VerifiedTerminalPublication(TerminalStatus.BLOCKED, ref)
        if ref.artifact_type == "evidence_manifest":
            loaded = self._read_expected(ref, "evidence_manifest", 1, root=True)
            evidence = loaded.artifact
            if type(evidence) is not _EvidenceManifest:
                raise TypeError("wrong evidence manifest decoder result")
            self._read_evidence_children(evidence)
            if evidence.status == "READY_FOR_INTEGRITY":
                raise BacktestEvidenceError(
                    BacktestEvidenceFailureCode.PORT_TERMINAL_NOT_ANALYZABLE,
                    "completed evidence is not terminal",
                )
            return VerifiedTerminalPublication(TerminalStatus(evidence.status), ref)

        loaded = self._read_expected(
            ref,
            "canonical_publication_manifest",
            ref.schema_version,
            root=True,
        )
        manifest = loaded.artifact
        if ref.schema_version == 2:
            return self._load_terminal_v2(ref, manifest)
        if type(manifest) is not _CanonicalManifest:
            raise TypeError("wrong canonical manifest decoder result")
        entries = {entry.relative_path: entry for entry in manifest.artifacts}
        if manifest.publication_kind == "integrity_evaluation":
            expected = {
                "integrity.json": ("integrity_report", 1),
                "evaluation-outcome.json": ("integrity_evaluation_record", 1),
            }
        elif manifest.publication_kind == "canonical":
            if manifest.publication_id not in {"canonical", "canonical-v2"}:
                raise ValueError("unsupported canonical publication id")
            expected = {
                "canonical-attempt-ref.json": ("canonical_attempt_ref", 1),
                "integrity.json": ("integrity_report", 1),
                "result.json": (
                    "completed_backtest_result",
                    2 if manifest.publication_id == "canonical-v2" else 1,
                ),
            }
        else:  # pragma: no cover - semantic decoder already rejects this
            raise ValueError("unsupported publication kind")
        if set(entries) != set(expected):
            raise ValueError("terminal manifest does not exact-cover children")
        children: dict[str, object] = {}
        for path, (artifact_type, version) in expected.items():
            if (
                entries[path].artifact_ref.artifact_type != artifact_type
                or entries[path].artifact_ref.schema_version != version
            ):
                raise ValueError(f"terminal manifest {path} schema mismatch")
            children[path] = self._read_entry(entries[path]).artifact
        if manifest.publication_kind == "canonical":
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_TERMINAL_NOT_ANALYZABLE,
                "completed canonical publication is not terminal",
            )
        integrity = children["integrity.json"]
        outcome = children["evaluation-outcome.json"]
        if type(integrity) is not _IntegrityReport or type(outcome) is not _IntegrityEvaluation:
            raise TypeError("integrity evaluation child decoder mismatch")
        if outcome.evaluation_id != manifest.publication_id:
            raise ValueError("integrity evaluation publication id mismatch")
        if outcome.semantic_run_id != manifest.semantic_run_id:
            raise ValueError("integrity evaluation semantic run mismatch")
        if integrity.semantic_run_id != manifest.semantic_run_id:
            raise ValueError("integrity report semantic run mismatch")
        if outcome.integrity_report_hash != canonical_sha256(integrity.raw):
            raise ValueError("integrity evaluation report hash mismatch")
        return VerifiedTerminalPublication(TerminalStatus(outcome.outcome), ref)

    def _load_terminal_v2(
        self,
        ref: ArtifactRef,
        manifest: object,
    ) -> VerifiedTerminalPublication:
        from ._durable_rebuild import (
            DeterministicRebuildVerificationPublicationManifestV1,
            DeterministicRebuildVerificationV1,
            RebuildComparisonOutcome,
            _validate_manifest_binding,
            _validate_verification_structure,
        )

        if type(manifest) is not _CanonicalManifestV2:
            raise TypeError("wrong canonical manifest v2 decoder result")
        if manifest.publication_kind == "canonical":
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_TERMINAL_NOT_ANALYZABLE,
                "completed canonical-v3 publication is not terminal",
            )
        expected = {
            "evaluation-outcome.json": ("integrity_evaluation_record", 2),
            "integrity.json": ("integrity_report", 2),
            "proof-publication-manifest.json": (
                "deterministic_rebuild_verification_publication_manifest",
                1,
            ),
            "rebuild-verification.json": (
                "deterministic_rebuild_verification",
                1,
            ),
        }
        entries = {entry.relative_path: entry for entry in manifest.artifacts}
        if set(entries) != set(expected):
            raise ValueError("evaluation v2 manifest does not exact-cover children")
        for path, (artifact_type, version) in expected.items():
            child = entries[path].artifact_ref
            if child.artifact_type != artifact_type or child.schema_version != version:
                raise ValueError(f"evaluation v2 manifest {path} schema mismatch")
        children = {path: self._read_entry(entry) for path, entry in entries.items()}
        integrity = children["integrity.json"].artifact
        outcome = children["evaluation-outcome.json"].artifact
        verification = children["rebuild-verification.json"].artifact
        proof = children["proof-publication-manifest.json"].artifact
        if (
            type(integrity) is not _IntegrityReportV2
            or type(outcome) is not _IntegrityEvaluation
            or type(verification) is not DeterministicRebuildVerificationV1
            or type(proof)
            is not DeterministicRebuildVerificationPublicationManifestV1
        ):
            raise TypeError("evaluation v2 child decoder mismatch")
        try:
            verification_ref = entries["rebuild-verification.json"].artifact_ref
            _validate_manifest_binding(
                verification,
                verification_ref,
                children["rebuild-verification.json"].source_bytes,
                children["rebuild-verification.json"].source_hash,
                proof,
            )
            _validate_verification_structure(verification, self._reader)
        except Exception as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_STATIC_PROOF_MISMATCH,
                "evaluation v2 static proof mismatch",
            ) from error
        proof_ref = entries["proof-publication-manifest.json"].artifact_ref
        comparison_mismatches = tuple(
            value
            for value in verification.comparisons
            if value.outcome is RebuildComparisonOutcome.MISMATCH
        )
        expected_comparison_outcome = (
            "mismatch" if comparison_mismatches else "equal"
        )
        expected_issue_codes: tuple[str, ...] = ()
        if verification.comparisons[0].outcome is RebuildComparisonOutcome.MISMATCH:
            expected_issue_codes += ("execution_hash_mismatch",)
        if any(
            value.outcome is RebuildComparisonOutcome.MISMATCH
            for value in verification.comparisons[1:]
        ):
            expected_issue_codes += ("deterministic_rebuild_mismatch",)
        if not expected_issue_codes:
            expected_issue_codes = ("environment_limitation",)
        expected_id = "evaluation_" + canonical_sha256(
            {
                "type": "integrity_evaluation_identity_v2",
                "semantic_run_id": integrity.semantic_run_id,
                "integrity_report_hash": canonical_sha256(integrity.raw),
                "outcome": outcome.outcome,
            }
        ).removeprefix("sha256:")
        issue_codes = tuple(value.get("code") for value in integrity.issues)
        expected_outcome = (
            "FAILED"
            if any(
                value
                in {"execution_hash_mismatch", "deterministic_rebuild_mismatch"}
                for value in issue_codes
            )
            else "BLOCKED"
        )
        if (
            not integrity.issues
            or integrity.result_grade is not None
            or integrity.canonical_attempt_ref_hash is not None
            or issue_codes != expected_issue_codes
            or integrity.context_hash != canonical_sha256(integrity.context)
            or integrity.context["rebuild_verification_ref"]
            != verification_ref.to_canonical_dict()
            or integrity.context["proof_publication_manifest_ref"]
            != proof_ref.to_canonical_dict()
            or integrity.context["comparison_outcome"]
            != expected_comparison_outcome
            or (expected_outcome == "FAILED") != bool(comparison_mismatches)
            or outcome.outcome != expected_outcome
            or outcome.evaluation_id != expected_id
            or outcome.evaluation_id != manifest.publication_id
            or outcome.semantic_run_id != manifest.semantic_run_id
            or integrity.semantic_run_id != manifest.semantic_run_id
            or outcome.integrity_report_hash != canonical_sha256(integrity.raw)
        ):
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_STATIC_PROOF_MISMATCH,
                "evaluation v2 terminal link mismatch",
            )
        return VerifiedTerminalPublication(TerminalStatus(outcome.outcome), ref)

    def load_analysis(self, ref: AnalysisArtifactRef) -> VerifiedBacktestAnalysis:
        if type(ref) is not AnalysisArtifactRef:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "exact AnalysisArtifactRef required",
            )
        try:
            return self._load_analysis(ref)
        except BacktestEvidenceError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID, str(error)
            ) from error

    def _load_analysis(self, ref: AnalysisArtifactRef) -> VerifiedBacktestAnalysis:
        loaded = self._read_expected(
            ref.artifact_ref, "backtest_analysis", 1, root=True
        )
        decoded = loaded.artifact
        if type(decoded) is not _DecodedAnalysis:
            raise TypeError("wrong analysis decoder result")
        analysis = decoded.analysis
        profile_loaded = self._read_expected(
            analysis.metric_profile_ref,
            "backtest_metric_profile",
            1,
            root=False,
        )
        profile = profile_loaded.artifact
        if type(profile) is not _DecodedMetricProfile:
            raise TypeError("wrong metric profile decoder result")
        accepted_profile = BacktestMetricProfile(
            "simple_period_return.fill_count.v1", 1
        )
        accepted_ref = ArtifactRef.from_envelope(
            ArtifactEnvelope.create("backtest_metric_profile", 1, accepted_profile)
        )
        if profile.profile != accepted_profile or analysis.metric_profile_ref != accepted_ref:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_ANALYSIS_LINK_MISMATCH,
                "analysis metric profile disagreement",
            )
        try:
            completed = self._load_completed(
                analysis.source_publication_ref, root=False
            )
        except BacktestEvidenceError:
            raise
        disagreements = (
            completed.source_publication_ref != analysis.source_publication_ref,
            completed.source_execution_result_hash
            != analysis.source_execution_result_hash,
            completed.result_grade is not analysis.result_grade,
        )
        if any(disagreements):
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_ANALYSIS_LINK_MISMATCH,
                "analysis source link disagreement",
            )
        return VerifiedBacktestAnalysis(ref, analysis)

    def load_analysis_v2(
        self, ref: AnalysisArtifactRefV2
    ) -> VerifiedBacktestAnalysisV2:
        if type(ref) is not AnalysisArtifactRefV2:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH,
                "exact AnalysisArtifactRefV2 required",
            )
        try:
            return self._load_analysis_v2(ref)
        except BacktestEvidenceError:
            raise
        except _AnalysisVersionMismatch as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_ANALYSIS_VERSION_MISMATCH,
                str(error),
            ) from error
        except (KeyError, TypeError, ValueError) as error:
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID, str(error)
            ) from error

    def _load_analysis_v2(
        self, ref: AnalysisArtifactRefV2
    ) -> VerifiedBacktestAnalysisV2:
        loaded = self._read_expected(
            ref.artifact_ref, "backtest_analysis", 2, root=True
        )
        decoded = loaded.artifact
        if type(decoded) is not _DecodedAnalysisV2:
            raise _AnalysisVersionMismatch("wrong analysis v2 decoder result")
        analysis = decoded.analysis
        profile_loaded = self._read_expected(
            analysis.metric_profile_ref,
            "backtest_metric_profile",
            1,
            root=False,
        )
        profile = profile_loaded.artifact
        if type(profile) is not _DecodedMetricProfile:
            raise TypeError("wrong metric profile decoder result")
        accepted_profile = BacktestMetricProfile(
            "simple_period_return.fill_count.v1", 1
        )
        accepted_ref = ArtifactRef.from_envelope(
            ArtifactEnvelope.create(
                "backtest_metric_profile", 1, accepted_profile
            )
        )
        if (
            profile.profile != accepted_profile
            or analysis.metric_profile_ref != accepted_ref
        ):
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_ANALYSIS_LINK_MISMATCH,
                "analysis metric profile disagreement",
            )
        completed = self._load_completed_v3(
            analysis.source_publication_ref, root=False
        )
        if (
            completed.source_publication_ref != analysis.source_publication_ref
            or completed.source_execution_result_hash
            != analysis.source_execution_result_hash
            or completed.result_grade is not analysis.result_grade
        ):
            raise BacktestEvidenceError(
                BacktestEvidenceFailureCode.PORT_ANALYSIS_LINK_MISMATCH,
                "analysis source link disagreement",
            )
        return VerifiedBacktestAnalysisV2(ref, analysis)


__all__ = [
    "BacktestEvidenceError",
    "BacktestEvidenceFailureCode",
    "BacktestEvidenceRepository",
]
