"""Private deterministic rebuild verification and durable proof publication."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    ArtifactSchemaRegistration,
    SchemaCatalog,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    InputValidationFailure,
    LocalMarketBundleReader,
    MarketBundleIntegrityError,
    MarketBundleRef,
)

from ._publication import (
    RunPublicationLock,
    ensure_directory,
    force_remove,
    fsync_directory,
    prepare_read_only_directory,
    verify_read_only,
    write_file,
)
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .composition import _compose_execution_case_v3, _HydratedExecutionCaseInputs
from .engine import DeterministicBarEngine, EngineExecutionResult, ResolvedExecutionCase
from .evidence import (
    EvidenceArtifactRole,
    EvidenceManifest,
    EvidencePublicationStatus,
    FinalizedAttemptEvidence,
)
from .execution_hash import AttemptExecutionHash, CanonicalExecutionSummary
from .execution_inputs import (
    BacktestExecutionRequest,
    _DecodedExecutionInputBundleV3,
    _ExecutionInputsHydrationFailureCodeV3,
    _ExecutionInputsHydrationFailureV3,
    _hydrate_execution_inputs_v3_from_decoded,
    _hydrate_execution_inputs_v4_from_decoded,
    _hydrate_execution_inputs_v6_from_decoded,
    _hydrate_execution_inputs_v7_from_decoded,
    _read_execution_inputs_v3_from_snapshot,
    _read_execution_inputs_v4_from_snapshot,
    _read_execution_inputs_v6_from_snapshot,
    _read_execution_inputs_v7_from_snapshot,
)
from .integrity import AttemptConsistencySet, CanonicalPublicationFailureCode
from .multi_resolution_preparation import (
    MarketDataCaseAuthority,
    PreparedMultiResolutionMarketData,
    _capture_market_bundle_reader_v1,
    _prepare_multi_resolution_market_data_from_retained_v1,
)
from .resolution import (
    BacktestProfileRegistry,
    BacktestRequest,
    BuildArtifactManifest,
    EnvironmentCompatibilityReport,
    ProfileResolver,
    ResolvedBacktestEnvironment,
    ResolvedBacktestRequest,
)
from .runner import AttemptExecutionRecord, AttemptIdentity
from .target_stream import PrecomputedTargetStream

_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")
_PROOF_PATTERN = re.compile(r"proof_[0-9a-f]{64}")
_PUBLICATION_PATTERN = re.compile(r"proof_publication_[0-9a-f]{64}")

_VERIFICATION_TYPE: Final = "deterministic_rebuild_verification"
_PROOF_MANIFEST_TYPE: Final = (
    "deterministic_rebuild_verification_publication_manifest"
)
_VERIFICATION_PATH: Final = "verification.json"
_MANIFEST_PATH: Final = "proof-publication-manifest.json"
_RETRIEVABILITY: Final = "verified"
_CLAIM: Final = "same_accepted_build_current_local_inputs"
_REBUILD_SUBJECT: Final = "verifier_rebuild"


class RebuildComparisonOutcome(str, Enum):
    EQUAL = "equal"
    MISMATCH = "mismatch"


class RebuildDivergenceSubject(str, Enum):
    REQUEST_HASH = "request_hash"
    NORMALIZED_REQUEST_HASH = "normalized_request_hash"
    RESOLVED_ENVIRONMENT_HASH = "resolved_environment_hash"
    BUILD_ARTIFACT_MANIFEST_HASH = "build_artifact_manifest_hash"
    EXECUTION_INPUT_CONTENT_HASH = "execution_input_content_hash"
    EXECUTION_INPUT_SOURCE_HASH = "execution_input_source_hash"
    MARKET_BUNDLE_PUBLICATION_SOURCE_HASH = (
        "market_bundle_publication_source_hash"
    )
    MARKET_BUNDLE_RETENTION_SOURCE_HASH = "market_bundle_retention_source_hash"
    PREPARATION_HASH = "preparation_hash"
    TARGET_STREAM_DIGEST = "target_stream_digest"
    SEMANTIC_SPEC_HASH = "semantic_spec_hash"
    IDENTITY_MANIFEST_HASH = "identity_manifest_hash"
    EXECUTION_CASE_HASH = "execution_case_hash"
    TRACE_HASH = "trace_hash"
    EXECUTION_RESULT_HASH = "execution_result_hash"


_COMPARISON_SUBJECTS: Final = tuple(RebuildDivergenceSubject)
_COMPARISON_IDS: Final = (
    "attempt_1_vs_attempt_2",
    "attempt_1_vs_rebuild",
    "attempt_2_vs_rebuild",
)


class DurableRebuildFailureCode(str, Enum):
    EXECUTION_INPUT_UNAVAILABLE = "execution_input_unavailable"
    EXECUTION_INPUT_TAMPERED = "execution_input_tampered"
    EXECUTION_INPUT_DECODE_FAILED = "execution_input_decode_failed"
    LOCAL_REOPEN_UNAVAILABLE = "local_reopen_unavailable"
    LOCAL_REOPEN_TAMPERED = "local_reopen_tampered"
    PREPARATION_MISMATCH = "preparation_mismatch"
    RESOLUTION_MISMATCH = "resolution_mismatch"
    COMPOSITION_MISMATCH = "composition_mismatch"
    REBUILD_EXECUTION_FAILED = "rebuild_execution_failed"
    PROOF_CONSTRUCTION_FAILED = "proof_construction_failed"
    PROOF_MIRROR_FAILED = "proof_mirror_failed"
    CACHE_LOCAL_PROOF_MISMATCH = "cache_local_proof_mismatch"
    CACHE_STATIC_GRAPH_MISMATCH = "cache_static_graph_mismatch"
    RECOVERY_UNSAFE = "recovery_unsafe"
    RECOVERY_CLEANUP_FAILED = "recovery_cleanup_failed"


def _relative_path(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value or "\\" in value:
        raise ValueError(f"{name} must be a canonical relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{name} must be a canonical relative path")
    return value


class DurableRebuildError(RuntimeError):
    """Private failure carrying only a frozen code and relative subject."""

    def __init__(
        self,
        code: DurableRebuildFailureCode | CanonicalPublicationFailureCode,
        relative_subject: str,
    ) -> None:
        if type(code) not in {
            DurableRebuildFailureCode,
            CanonicalPublicationFailureCode,
        }:
            raise TypeError("code must be an exact durable or publication failure code")
        self.code = code
        self.relative_subject = _relative_path("relative_subject", relative_subject)
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class RebuildComparisonV1:
    comparison_id: str
    left_subject: str
    right_subject: str
    outcome: RebuildComparisonOutcome
    first_divergence: RebuildDivergenceSubject | None
    left_hash: str
    right_hash: str

    def __post_init__(self) -> None:
        if self.comparison_id not in _COMPARISON_IDS:
            raise ValueError("unsupported comparison_id")
        _canonical_text("left_subject", self.left_subject)
        _canonical_text("right_subject", self.right_subject)
        if not isinstance(self.outcome, RebuildComparisonOutcome):
            raise TypeError("outcome must be RebuildComparisonOutcome")
        if self.first_divergence is not None and not isinstance(
            self.first_divergence, RebuildDivergenceSubject
        ):
            raise TypeError("first_divergence must be RebuildDivergenceSubject or None")
        _canonical_hash("left_hash", self.left_hash)
        _canonical_hash("right_hash", self.right_hash)
        if self.outcome is RebuildComparisonOutcome.EQUAL:
            if self.first_divergence is not None or self.left_hash != self.right_hash:
                raise ValueError("equal comparison must have null divergence and equal hashes")
        elif self.first_divergence is None or self.left_hash == self.right_hash:
            raise ValueError("mismatch comparison requires unequal hashes and divergence")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "comparison_id": self.comparison_id,
            "left_subject": self.left_subject,
            "right_subject": self.right_subject,
            "outcome": self.outcome.value,
            "first_divergence": (
                None if self.first_divergence is None else self.first_divergence.value
            ),
            "left_hash": self.left_hash,
            "right_hash": self.right_hash,
        }


@dataclass(frozen=True, slots=True)
class _AttemptVerificationEntryV1:
    attempt: AttemptIdentity
    evidence_manifest_ref: ArtifactRef
    evidence_manifest_hash: str
    evidence_manifest_source_hash: str
    evidence_publication_hash: str
    engine_result_ref: ArtifactRef
    execution_case_hash: str
    trace_hash: str
    execution_result_hash: str

    def __post_init__(self) -> None:
        if type(self.attempt) is not AttemptIdentity:
            raise TypeError("attempt must be exact AttemptIdentity")
        if type(self.evidence_manifest_ref) is not ArtifactRef or (
            self.evidence_manifest_ref.artifact_type != "evidence_manifest"
            or self.evidence_manifest_ref.schema_version != 1
        ):
            raise ValueError("evidence_manifest_ref must target evidence_manifest@1")
        if type(self.engine_result_ref) is not ArtifactRef or (
            self.engine_result_ref.artifact_type != "engine_execution_result"
            or self.engine_result_ref.schema_version != 1
        ):
            raise ValueError("engine_result_ref must target engine_execution_result@1")
        for name in (
            "evidence_manifest_hash",
            "evidence_manifest_source_hash",
            "evidence_publication_hash",
            "execution_case_hash",
            "trace_hash",
            "execution_result_hash",
        ):
            _canonical_hash(name, getattr(self, name))

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "evidence_manifest_ref": self.evidence_manifest_ref,
            "evidence_manifest_hash": self.evidence_manifest_hash,
            "evidence_manifest_source_hash": self.evidence_manifest_source_hash,
            "evidence_publication_hash": self.evidence_publication_hash,
            "engine_result_ref": self.engine_result_ref,
            "execution_case_hash": self.execution_case_hash,
            "trace_hash": self.trace_hash,
            "execution_result_hash": self.execution_result_hash,
        }


@dataclass(frozen=True, slots=True)
class _FreshRebuildObservationV1:
    preparation_hash: str
    target_stream_digest: str
    semantic_spec_hash: str
    identity_manifest_hash: str
    execution_case_hash: str
    trace_level: str
    trace_hash: str
    execution_result_hash: str

    def __post_init__(self) -> None:
        for name in (
            "preparation_hash",
            "target_stream_digest",
            "semantic_spec_hash",
            "identity_manifest_hash",
            "execution_case_hash",
            "trace_hash",
            "execution_result_hash",
        ):
            _canonical_hash(name, getattr(self, name))
        if self.trace_level != "full_trace":
            raise ValueError("trace_level must be full_trace")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "preparation_hash": self.preparation_hash,
            "target_stream_digest": self.target_stream_digest,
            "semantic_spec_hash": self.semantic_spec_hash,
            "identity_manifest_hash": self.identity_manifest_hash,
            "execution_case_hash": self.execution_case_hash,
            "trace_level": self.trace_level,
            "trace_hash": self.trace_hash,
            "execution_result_hash": self.execution_result_hash,
        }


@dataclass(frozen=True, slots=True)
class DeterministicRebuildVerificationV1:
    semantic_run_id: str
    request_hash: str
    normalized_request_hash: str
    resolved_environment_hash: str
    build_artifact_manifest_hash: str
    execution_input_bundle_ref: ArtifactRef
    execution_input_source_hash: str
    market_bundle_ref: MarketBundleRef
    market_bundle_publication: Mapping[str, object]
    market_bundle_publication_source_hash: str
    market_bundle_retention_proof: Mapping[str, object]
    market_bundle_retention_source_hash: str
    retrievability: str
    preparation_hash: str
    target_stream_digest: str
    semantic_spec_hash: str
    identity_manifest_hash: str
    execution_case_hash: str
    attempts: tuple[_AttemptVerificationEntryV1, ...]
    fresh_rebuild: _FreshRebuildObservationV1
    comparisons: tuple[RebuildComparisonV1, ...]
    claim: str

    def __post_init__(self) -> None:
        _validate_verification(self)
        object.__setattr__(
            self,
            "market_bundle_publication",
            _freeze_mapping(self.market_bundle_publication),
        )
        object.__setattr__(
            self,
            "market_bundle_retention_proof",
            _freeze_mapping(self.market_bundle_retention_proof),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": _VERIFICATION_TYPE,
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "request_hash": self.request_hash,
            "normalized_request_hash": self.normalized_request_hash,
            "resolved_environment_hash": self.resolved_environment_hash,
            "build_artifact_manifest_hash": self.build_artifact_manifest_hash,
            "execution_input_bundle_ref": self.execution_input_bundle_ref,
            "execution_input_source_hash": self.execution_input_source_hash,
            "market_bundle_ref": self.market_bundle_ref,
            "market_bundle_publication": self.market_bundle_publication,
            "market_bundle_publication_source_hash": (
                self.market_bundle_publication_source_hash
            ),
            "market_bundle_retention_proof": self.market_bundle_retention_proof,
            "market_bundle_retention_source_hash": (
                self.market_bundle_retention_source_hash
            ),
            "retrievability": self.retrievability,
            "preparation_hash": self.preparation_hash,
            "target_stream_digest": self.target_stream_digest,
            "semantic_spec_hash": self.semantic_spec_hash,
            "identity_manifest_hash": self.identity_manifest_hash,
            "execution_case_hash": self.execution_case_hash,
            "attempts": self.attempts,
            "fresh_rebuild": self.fresh_rebuild,
            "comparisons": self.comparisons,
            "claim": self.claim,
        }


@dataclass(frozen=True, slots=True)
class _PublicationArtifactEntryV1:
    relative_path: str
    artifact_type: str
    schema_version: int
    content_hash: str
    source_hash: str
    byte_count: int

    def __post_init__(self) -> None:
        _relative_path("relative_path", self.relative_path)
        if self.relative_path != _VERIFICATION_PATH:
            raise ValueError("proof manifest may list only verification.json")
        if self.artifact_type != _VERIFICATION_TYPE or self.schema_version != 1:
            raise ValueError("proof manifest entry must target verification@1")
        _canonical_hash("content_hash", self.content_hash)
        _canonical_hash("source_hash", self.source_hash)
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
class DeterministicRebuildVerificationPublicationManifestV1:
    semantic_run_id: str
    proof_id: str
    publication_id: str
    artifacts: tuple[_PublicationArtifactEntryV1, ...]
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        _canonical_run(self.semantic_run_id)
        if type(self.proof_id) is not str or _PROOF_PATTERN.fullmatch(self.proof_id) is None:
            raise ValueError("proof_id must use proof_sha256 schema")
        if (
            type(self.publication_id) is not str
            or _PUBLICATION_PATTERN.fullmatch(self.publication_id) is None
        ):
            raise ValueError("publication_id must use proof_publication_sha256 schema")
        if type(self.artifacts) is not tuple or len(self.artifacts) != 1 or not all(
            type(entry) is _PublicationArtifactEntryV1 for entry in self.artifacts
        ):
            raise ValueError("artifacts must contain exactly one verification entry")
        if tuple(sorted(self.artifacts, key=lambda entry: entry.relative_path)) != self.artifacts:
            raise ValueError("artifacts must be sorted by relative_path")
        if type(self.deployment_authorized) is not bool or self.deployment_authorized:
            raise ValueError("proof publication never authorizes deployment")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": _PROOF_MANIFEST_TYPE,
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "proof_id": self.proof_id,
            "publication_id": self.publication_id,
            "artifacts": self.artifacts,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class VerifiedDurableRebuildObservationV1:
    verification: DeterministicRebuildVerificationV1
    verification_envelope: ArtifactEnvelope
    verification_ref: ArtifactRef
    verification_source_bytes: bytes
    verification_source_hash: str
    publication_manifest: DeterministicRebuildVerificationPublicationManifestV1
    publication_manifest_envelope: ArtifactEnvelope
    publication_manifest_ref: ArtifactRef
    publication_manifest_source_bytes: bytes
    publication_manifest_source_hash: str

    def __post_init__(self) -> None:
        if type(self.verification) is not DeterministicRebuildVerificationV1:
            raise TypeError("verification must be exact verification V1")
        if type(self.publication_manifest) is not DeterministicRebuildVerificationPublicationManifestV1:
            raise TypeError("publication_manifest must be exact proof manifest V1")
        _validate_artifact_binding(
            self.verification,
            self.verification_envelope,
            self.verification_ref,
            self.verification_source_bytes,
            self.verification_source_hash,
            _VERIFICATION_TYPE,
        )
        _validate_artifact_binding(
            self.publication_manifest,
            self.publication_manifest_envelope,
            self.publication_manifest_ref,
            self.publication_manifest_source_bytes,
            self.publication_manifest_source_hash,
            _PROOF_MANIFEST_TYPE,
        )
        _validate_manifest_binding(
            self.verification,
            self.verification_ref,
            self.verification_source_bytes,
            self.verification_source_hash,
            self.publication_manifest,
        )


@dataclass(frozen=True, slots=True)
class _FreshRebuildResultV1:
    resolved_request: ResolvedBacktestRequest
    prepared_market_data: PreparedMultiResolutionMarketData
    execution_case: ResolvedExecutionCase
    engine_result: EngineExecutionResult

    def __post_init__(self) -> None:
        if type(self.resolved_request) is not ResolvedBacktestRequest:
            raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
        if type(self.prepared_market_data) is not PreparedMultiResolutionMarketData:
            raise TypeError("prepared_market_data must be exact prepared market data")
        if type(self.execution_case) is not ResolvedExecutionCase:
            raise TypeError("execution_case must be exact ResolvedExecutionCase")
        if type(self.engine_result) is not EngineExecutionResult:
            raise TypeError("engine_result must be exact EngineExecutionResult")
        if self.engine_result.case_hash != self.execution_case.case_hash:
            raise ValueError("engine result does not bind rebuilt execution case")
        if (
            self.engine_result.target_stream_digest
            != self.execution_case.target_stream.target_stream_digest
        ):
            raise ValueError("engine result target stream mismatch")


class DurableRebuildVerifierV1:
    """Construct one verification from one verifier-owned fresh recomputation."""

    def __init__(
        self,
        *,
        artifact_reader: ArtifactEnvelopeReader,
        market_reader: LocalMarketBundleReader,
        profile_registry: BacktestProfileRegistry,
    ) -> None:
        if not callable(getattr(artifact_reader, "read", None)):
            raise TypeError("artifact_reader must satisfy ArtifactEnvelopeReader")
        if type(market_reader) is not LocalMarketBundleReader:
            raise TypeError("market_reader must be exact LocalMarketBundleReader")
        if type(profile_registry) is not BacktestProfileRegistry:
            raise TypeError("profile_registry must be exact BacktestProfileRegistry")
        self._artifact_reader = artifact_reader
        self._market_reader = market_reader
        self._profile_registry = profile_registry

    def verify(
        self,
        *,
        request: BacktestExecutionRequest,
        resolved_request: ResolvedBacktestRequest,
        prepared_market_data: PreparedMultiResolutionMarketData,
        execution_case: ResolvedExecutionCase,
        attempts: AttemptConsistencySet,
    ) -> DeterministicRebuildVerificationV1:
        subject = _run_subject_from_request(request)
        if (
            type(request) is not BacktestExecutionRequest
            or request.schema_version not in {3, 4, 6, 7}
        ):
            raise DurableRebuildError(
                DurableRebuildFailureCode.PROOF_CONSTRUCTION_FAILED, subject
            )
        if type(resolved_request) is not ResolvedBacktestRequest:
            raise DurableRebuildError(
                DurableRebuildFailureCode.PROOF_CONSTRUCTION_FAILED, subject
            )
        subject = f"runs/{resolved_request.semantic_run_id}/rebuild-proofs"
        if (
            type(prepared_market_data) is not PreparedMultiResolutionMarketData
            or type(execution_case) is not ResolvedExecutionCase
            or type(attempts) is not AttemptConsistencySet
        ):
            raise DurableRebuildError(
                DurableRebuildFailureCode.PROOF_CONSTRUCTION_FAILED, subject
            )
        try:
            if (
                request.request != resolved_request.request
                or attempts.resolved_request != resolved_request
                or execution_case.case_hash
                not in {value.engine_result.case_hash for value in attempts.attempt_hashes}
            ):
                raise ValueError("production roots do not bind")
            _validate_exact_attempt_pair(attempts, resolved_request.semantic_run_id)
            execution_source, decoded_inputs = self._read_fresh_execution_inputs(
                request, subject
            )
            (
                reopened,
                publication_bytes,
                publication_source_hash,
                _publication_hash,
                retention_bytes,
                retention_source_hash,
                _retention_hash,
            ) = self._fresh_reopen(subject)
            publication = _decode_g12d_publication(
                publication_bytes,
                publication_source_hash,
                resolved_request.request.market_bundle_ref,
            )
            retention = _decode_g12d_retention(
                retention_bytes,
                retention_source_hash,
                resolved_request.request.market_bundle_ref,
            )
            _validate_g12d_pair(publication, retention)
            fresh_resolved, fresh_prepared, fresh_case = self._recompute(
                request=request,
                decoded=decoded_inputs,
                reopened=reopened,
                subject=subject,
            )
            entries, records = _build_attempt_entries(
                attempts,
                self._artifact_reader,
                resolved_request.semantic_run_id,
            )
            self._validate_recomputed_roots(
                fresh_resolved,
                fresh_prepared,
                fresh_case,
                resolved_request,
                prepared_market_data,
                execution_case,
                decoded_inputs,
                reopened,
                records,
                subject,
            )
            try:
                outcome = DeterministicBarEngine().run(fresh_case)
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    DurableRebuildFailureCode.REBUILD_EXECUTION_FAILED, subject
                ) from None
            if outcome.result is None:
                raise DurableRebuildError(
                    DurableRebuildFailureCode.REBUILD_EXECUTION_FAILED, subject
                )
            rebuilt = _FreshRebuildResultV1(
                fresh_resolved,
                fresh_prepared,
                fresh_case,
                outcome.result,
            )
            fresh = _fresh_observation(rebuilt)
            verification = _build_verification(
                resolved_request=resolved_request,
                prepared_market_data=prepared_market_data,
                execution_case=execution_case,
                execution_source=execution_source,
                publication=publication,
                publication_source_hash=publication_source_hash,
                retention=retention,
                retention_source_hash=retention_source_hash,
                attempts=entries,
                fresh=fresh,
            )
            _validate_verification_structure(verification, self._artifact_reader)
            return verification
        except DurableRebuildError:
            raise
        except Exception:  # noqa: BLE001
            raise DurableRebuildError(
                DurableRebuildFailureCode.PROOF_CONSTRUCTION_FAILED, subject
            ) from None

    def _read_fresh_execution_inputs(
        self,
        request: BacktestExecutionRequest,
        subject: str,
    ) -> tuple[ArtifactReadResult, _DecodedExecutionInputBundleV3]:
        source, decoded, failure = _read_execution_inputs_with_source(
            self._artifact_reader, request
        )
        if failure is not None or decoded is None:
            code = {
                _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_UNAVAILABLE: (
                    DurableRebuildFailureCode.EXECUTION_INPUT_UNAVAILABLE
                ),
                _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_TAMPERED: (
                    DurableRebuildFailureCode.EXECUTION_INPUT_TAMPERED
                ),
            }.get(
                failure.code if failure is not None else None,
                DurableRebuildFailureCode.EXECUTION_INPUT_DECODE_FAILED,
            )
            raise DurableRebuildError(code, subject)
        if source is None:
            raise DurableRebuildError(
                DurableRebuildFailureCode.EXECUTION_INPUT_UNAVAILABLE, subject
            )
        return source, decoded

    def _fresh_reopen(
        self, subject: str
    ) -> tuple[LocalMarketBundleReader, bytes, str, str, bytes, str, str]:
        try:
            return self._market_reader._reopen_with_provenance_v1()
        except MarketBundleIntegrityError as error:
            code = (
                DurableRebuildFailureCode.LOCAL_REOPEN_UNAVAILABLE
                if getattr(type(error), "_durable_reopen_kind_v1", None)
                == "unavailable"
                else DurableRebuildFailureCode.LOCAL_REOPEN_TAMPERED
            )
            raise DurableRebuildError(code, subject) from None
        except Exception:  # noqa: BLE001
            raise DurableRebuildError(
                DurableRebuildFailureCode.LOCAL_REOPEN_TAMPERED, subject
            ) from None

    def _recompute(
        self,
        *,
        request: BacktestExecutionRequest,
        decoded: _DecodedExecutionInputBundleV3,
        reopened: LocalMarketBundleReader,
        subject: str,
    ) -> tuple[
        ResolvedBacktestRequest,
        PreparedMultiResolutionMarketData,
        ResolvedExecutionCase,
    ]:
        retained = _capture_market_bundle_reader_v1(
            request.request.market_bundle_ref, reopened
        )
        if retained is None:
            raise DurableRebuildError(
                DurableRebuildFailureCode.COMPOSITION_MISMATCH, subject
            )
        try:
            target_stream = _target_stream_v3(decoded, retained, request)
        except Exception:  # noqa: BLE001
            raise DurableRebuildError(
                DurableRebuildFailureCode.COMPOSITION_MISMATCH, subject
            ) from None
        try:
            resolution = ProfileResolver().resolve(
                request=request.request,
                registry=self._profile_registry,
                market_bundle_manifest=retained.manifest,
                build_artifact_manifest=decoded.build_artifact_manifest,
            )
            if resolution.failure is not None or resolution.resolved is None:
                raise ValueError("fresh resolution failed")
            resolved = resolution.resolved
        except Exception:  # noqa: BLE001
            raise DurableRebuildError(
                DurableRebuildFailureCode.RESOLUTION_MISMATCH, subject
            ) from None
        plan = decoded.execution_case_plan
        authority = MarketDataCaseAuthority(
            decision_cycles=plan.decision_cycles,
            bar_executions=plan.bar_executions,
            execution_model=plan.execution_model,
            snapshot_plan=plan.snapshot_plan,
            target_stream=target_stream,
        )
        embedded = decoded.market_data_preparation
        try:
            preparation = _prepare_multi_resolution_market_data_from_retained_v1(
                expected_bundle_ref=request.request.market_bundle_ref,
                reader=retained,
                schedule=embedded.decision_schedule,
                signal_binding_candidates=embedded.bindings.signal_bindings,
                execution_binding_candidates=embedded.bindings.execution_bindings,
                valuation_binding_candidates=embedded.bindings.valuation_bindings,
                signal_lineages=embedded.signal_lineages,
                case_authority=authority,
                resolved_request=resolved,
            )
            if preparation.prepared is None:
                raise ValueError("fresh preparation failed")
            prepared = preparation.prepared
        except Exception:  # noqa: BLE001
            raise DurableRebuildError(
                DurableRebuildFailureCode.PREPARATION_MISMATCH, subject
            ) from None
        hydrate = {
            3: _hydrate_execution_inputs_v3_from_decoded,
            4: _hydrate_execution_inputs_v4_from_decoded,
            6: _hydrate_execution_inputs_v6_from_decoded,
            7: _hydrate_execution_inputs_v7_from_decoded,
        }[request.schema_version]
        hydrated = hydrate(
            decoded,
            request,
            market_reader=retained,
            resolved_request=resolved,
            prepared_market_data=prepared,
            target_stream=target_stream,
            bindings_verified=True,
        )
        if hydrated.failure is not None or hydrated.result is None:
            raise DurableRebuildError(
                DurableRebuildFailureCode.COMPOSITION_MISMATCH, subject
            )
        values = hydrated.result
        try:
            case = _compose_execution_case_v3(
                resolved_request=resolved,
                market_reader=retained,
                hydrated_inputs=_HydratedExecutionCaseInputs(
                    values.execution_case_semantic_spec,
                    values.timeline_stream_keys,
                    values.target_stream,
                    values.timeline_batch_size,
                    values.execution_case_plan,
                ),
                market_data_preparation=values.market_data_preparation,
            )
        except Exception:  # noqa: BLE001
            raise DurableRebuildError(
                DurableRebuildFailureCode.COMPOSITION_MISMATCH, subject
            ) from None
        # Engine execution is deliberately performed only after all roots bind.
        return resolved, prepared, case

    @staticmethod
    def _validate_recomputed_roots(
        fresh_resolved: ResolvedBacktestRequest,
        fresh_prepared: PreparedMultiResolutionMarketData,
        fresh_case: ResolvedExecutionCase,
        resolved: ResolvedBacktestRequest,
        prepared: PreparedMultiResolutionMarketData,
        execution_case: ResolvedExecutionCase,
        decoded: _DecodedExecutionInputBundleV3,
        reopened: LocalMarketBundleReader,
        records: tuple[AttemptExecutionRecord, ...],
        subject: str,
    ) -> None:
        if (
            fresh_resolved != resolved
            or decoded.build_artifact_manifest != resolved.build_artifact_manifest
            or decoded.semantic_run_id != resolved.semantic_run_id
            or reopened.bundle_ref != resolved.request.market_bundle_ref
            or any(
                record.ready_to_finalize is None
                or record.ready_to_finalize.resolved_request != fresh_resolved
                for record in records
            )
        ):
            raise DurableRebuildError(
                DurableRebuildFailureCode.RESOLUTION_MISMATCH, subject
            )
        if (
            fresh_prepared.preparation != prepared.preparation
            or decoded.market_data_preparation != fresh_prepared.preparation
        ):
            raise DurableRebuildError(
                DurableRebuildFailureCode.PREPARATION_MISMATCH, subject
            )
        if (
            fresh_case.case_hash != execution_case.case_hash
            or fresh_case.semantic_spec_hash != execution_case.semantic_spec_hash
            or fresh_case.identity_manifest != execution_case.identity_manifest
            or fresh_case.identity_manifest is None
            or fresh_case.semantic_spec is None
            or not fresh_case.verify_identity_manifest(
                resolved.semantic_run_id
            )
            or any(
                record.ready_to_finalize is None
                or record.ready_to_finalize.execution_case_hash
                != fresh_case.case_hash
                or record.ready_to_finalize.engine_result.case_hash
                != fresh_case.case_hash
                or record.ready_to_finalize.engine_result.target_stream_digest
                != fresh_case.target_stream.target_stream_digest
                for record in records
            )
        ):
            raise DurableRebuildError(
                DurableRebuildFailureCode.COMPOSITION_MISMATCH, subject
            )


def _target_stream_v3(
    bundle: _DecodedExecutionInputBundleV3,
    retained_reader: InMemoryMarketBundleReader,
    request: BacktestExecutionRequest,
) -> PrecomputedTargetStream:
    """Current exact facade target-stream algorithm; DRP-03 will share this helper."""

    failure = retained_reader.validate_requirements(
        required_streams=bundle.timeline_stream_keys
    )
    cursor = retained_reader.open_cursor(
        bundle.target_stream_key,
        batch_size=bundle.timeline_batch_size,
    )
    if failure is not None or isinstance(cursor, InputValidationFailure):
        raise ValueError("target unavailable")
    events = []
    while not cursor.exhausted:
        previous_position = cursor.position
        batch, cursor = retained_reader.read_batch(cursor)
        if not batch or cursor.position != previous_position + len(batch):
            raise ValueError("target cursor did not advance")
        events.extend(batch)
    target_stream = PrecomputedTargetStream(bundle.target_stream_key, tuple(events))
    if (
        target_stream.target_stream_digest != request.request.target_stream_digest
        or bundle.execution_case_semantic_spec.target_stream_digest
        != request.request.target_stream_digest
    ):
        raise ValueError("target digest mismatch")
    return target_stream


@dataclass(frozen=True, slots=True)
class _ProofPathsV1:
    run: Path
    parent: Path
    staging: Path
    final: Path
    run_relative: str
    parent_relative: str
    staging_relative: str
    final_relative: str


class DurableRebuildPublisherV1:
    """Publish one proof final beneath an already-held exact Run lock."""

    _ensure_directory = staticmethod(ensure_directory)
    _force_remove = staticmethod(force_remove)
    _fsync_directory = staticmethod(fsync_directory)
    _prepare_read_only_directory = staticmethod(prepare_read_only_directory)
    _verify_read_only = staticmethod(verify_read_only)
    _write_file = staticmethod(write_file)
    _rename = staticmethod(os.rename)

    def __init__(
        self, *, root: Path, artifact_reader: ArtifactEnvelopeReader
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be pathlib.Path")
        if not callable(getattr(artifact_reader, "read", None)):
            raise TypeError("artifact_reader must satisfy ArtifactEnvelopeReader")
        self._root = root
        self._artifact_reader = artifact_reader

    def publish(
        self,
        *,
        lock: RunPublicationLock,
        verification: DeterministicRebuildVerificationV1,
    ) -> VerifiedDurableRebuildObservationV1:
        if type(verification) is not DeterministicRebuildVerificationV1:
            raise DurableRebuildError(
                DurableRebuildFailureCode.PROOF_CONSTRUCTION_FAILED,
                "runs/invalid/rebuild-proofs",
            )
        preparation_subject = (
            f"runs/{verification.semantic_run_id}/rebuild-proofs"
        )
        try:
            _validate_verification_structure(verification, self._artifact_reader)
            verification_write = _ARTIFACT_CATALOG.write_current(
                _VERIFICATION_TYPE, verification
            )
            verification_ref = ArtifactRef.from_envelope(
                verification_write.envelope
            )
            manifest = _proof_manifest(
                verification,
                verification_ref,
                verification_write.source_hash,
                len(verification_write.source_bytes),
            )
            manifest_write = _ARTIFACT_CATALOG.write_current(
                _PROOF_MANIFEST_TYPE, manifest
            )
            paths = self._paths(verification.semantic_run_id, manifest.proof_id)
        except Exception:  # noqa: BLE001
            raise DurableRebuildError(
                CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED,
                preparation_subject,
            ) from None
        self._require_lock(lock, paths)
        expected = (verification_write.source_bytes, manifest_write.source_bytes)
        created_staging = False

        try:
            try:
                self._prepare_parent(paths, lock)
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.STAGING_PREPARE_FAILED,
                    paths.parent_relative,
                ) from None
            if os.path.lexists(paths.staging):
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.STAGING_EXISTS,
                    paths.staging_relative,
                )
            if os.path.lexists(paths.final):
                try:
                    observation = self._read_directory(
                        paths.final, expected, require_read_only=True
                    )
                except Exception:  # noqa: BLE001
                    raise DurableRebuildError(
                        CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED,
                        paths.final_relative,
                    ) from None
                try:
                    self._fsync_directory(paths.final)
                    self._fsync_directory(paths.parent)
                except Exception:  # noqa: BLE001
                    raise DurableRebuildError(
                        CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                        paths.final_relative,
                    ) from None
                return observation
            try:
                paths.staging.mkdir(mode=0o755, exist_ok=False)
                created_staging = True
                self._fsync_directory(paths.parent)
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.STAGING_PREPARE_FAILED,
                    paths.staging_relative,
                ) from None
            try:
                self._write_file(paths.staging / _VERIFICATION_PATH, expected[0])
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.ARTIFACT_WRITE_FAILED,
                    f"{paths.staging_relative}/{_VERIFICATION_PATH}",
                ) from None
            try:
                self._write_file(paths.staging / _MANIFEST_PATH, expected[1])
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.MANIFEST_WRITE_FAILED,
                    f"{paths.staging_relative}/{_MANIFEST_PATH}",
                ) from None
            try:
                self._read_directory(paths.staging, expected, require_read_only=False)
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED,
                    paths.staging_relative,
                ) from None
            try:
                self._prepare_read_only_directory(paths.staging)
                self._verify_exact_modes(paths.staging)
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.IMMUTABILITY_FAILED,
                    paths.staging_relative,
                ) from None
            if os.path.lexists(paths.final):
                created_staging = False
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.FINAL_DESTINATION_EXISTS,
                    paths.final_relative,
                )
            try:
                self._rename(paths.staging, paths.final)
                created_staging = False
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                    paths.final_relative,
                ) from None
            try:
                self._read_directory(paths.final, expected, require_read_only=True)
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED,
                    paths.final_relative,
                ) from None
            try:
                self._fsync_directory(paths.final)
                self._fsync_directory(paths.parent)
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                    paths.final_relative,
                ) from None
            try:
                return self._read_directory(
                    paths.final, expected, require_read_only=True
                )
            except Exception:  # noqa: BLE001
                raise DurableRebuildError(
                    CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED,
                    paths.final_relative,
                ) from None
        except DurableRebuildError:
            if created_staging and os.path.lexists(paths.staging):
                try:
                    self._force_remove(paths.staging)
                    self._fsync_directory(paths.parent)
                except Exception:  # noqa: BLE001,S110
                    pass
            raise

    def _prepare_parent(self, paths: _ProofPathsV1, lock: RunPublicationLock) -> None:
        self._require_lock(lock, paths)
        _require_directory(paths.run)
        self._ensure_directory(paths.parent)
        _require_directory(paths.parent)

    def _require_lock(self, lock: RunPublicationLock, paths: _ProofPathsV1) -> None:
        if type(lock) is not RunPublicationLock or lock._held is not True:
            raise DurableRebuildError(
                CanonicalPublicationFailureCode.RUN_LOCK_UNAVAILABLE,
                f"{paths.run_relative}/.publication.lock",
            )
        if (
            lock.run_directory != paths.run
            or lock.path != paths.run / ".publication.lock"
            or not os.path.lexists(lock.path)
        ):
            raise DurableRebuildError(
                CanonicalPublicationFailureCode.RUN_LOCK_UNAVAILABLE,
                f"{paths.run_relative}/.publication.lock",
            )
        info = lock.path.lstat()
        if not stat.S_ISREG(info.st_mode) or lock.path.is_symlink():
            raise DurableRebuildError(
                CanonicalPublicationFailureCode.RUN_LOCK_UNAVAILABLE,
                f"{paths.run_relative}/.publication.lock",
            )

    def _read_directory(
        self,
        directory: Path,
        expected: tuple[bytes, bytes],
        *,
        require_read_only: bool,
    ) -> VerifiedDurableRebuildObservationV1:
        _require_directory(directory)
        children = {child.name: child for child in directory.iterdir()}
        if set(children) != {_VERIFICATION_PATH, _MANIFEST_PATH}:
            raise ValueError("proof directory has invalid coverage")
        for child in children.values():
            info = child.lstat()
            if child.is_symlink() or not stat.S_ISREG(info.st_mode):
                raise ValueError("proof artifact must be a regular file")
        verification_bytes = children[_VERIFICATION_PATH].read_bytes()
        manifest_bytes = children[_MANIFEST_PATH].read_bytes()
        if (verification_bytes, manifest_bytes) != expected:
            raise ValueError("proof final bytes do not match expected publication")
        verification_read = _ARTIFACT_CATALOG.read(verification_bytes)
        manifest_read = _ARTIFACT_CATALOG.read(manifest_bytes)
        if type(verification_read.artifact) is not DeterministicRebuildVerificationV1:
            raise TypeError("wrong verification decoder result")
        if type(manifest_read.artifact) is not DeterministicRebuildVerificationPublicationManifestV1:
            raise TypeError("wrong proof manifest decoder result")
        verification_ref = ArtifactRef.from_envelope(verification_read.envelope)
        manifest_ref = ArtifactRef.from_envelope(manifest_read.envelope)
        _validate_verification_structure(
            verification_read.artifact, self._artifact_reader
        )
        _validate_manifest_binding(
            verification_read.artifact,
            verification_ref,
            verification_bytes,
            verification_read.source_hash,
            manifest_read.artifact,
        )
        if require_read_only:
            self._verify_read_only(directory)
            self._verify_exact_modes(directory)
        return VerifiedDurableRebuildObservationV1(
            verification=verification_read.artifact,
            verification_envelope=verification_read.envelope,
            verification_ref=verification_ref,
            verification_source_bytes=verification_bytes,
            verification_source_hash=verification_read.source_hash,
            publication_manifest=manifest_read.artifact,
            publication_manifest_envelope=manifest_read.envelope,
            publication_manifest_ref=manifest_ref,
            publication_manifest_source_bytes=manifest_bytes,
            publication_manifest_source_hash=manifest_read.source_hash,
        )

    @staticmethod
    def _verify_exact_modes(directory: Path) -> None:
        if stat.S_IMODE(directory.stat().st_mode) != 0o555:
            raise PermissionError("proof directory mode must be 0555")
        if any(stat.S_IMODE(path.stat().st_mode) != 0o444 for path in directory.iterdir()):
            raise PermissionError("proof artifact mode must be 0444")

    def _paths(self, semantic_run_id: str, proof_id: str) -> _ProofPathsV1:
        _canonical_run(semantic_run_id)
        if _PROOF_PATTERN.fullmatch(proof_id) is None:
            raise ValueError("invalid proof_id")
        run_relative = f"runs/{semantic_run_id}"
        parent_relative = f"{run_relative}/rebuild-proofs"
        staging_relative = f"{parent_relative}/.{proof_id}.staging"
        final_relative = f"{parent_relative}/{proof_id}"
        return _ProofPathsV1(
            run=self._root / Path(run_relative),
            parent=self._root / Path(parent_relative),
            staging=self._root / Path(staging_relative),
            final=self._root / Path(final_relative),
            run_relative=run_relative,
            parent_relative=parent_relative,
            staging_relative=staging_relative,
            final_relative=final_relative,
        )


def _read_verification(value: object) -> DeterministicRebuildVerificationV1:
    data = _exact_mapping(
        "verification",
        value,
        {
            "type",
            "schema_version",
            "semantic_run_id",
            "request_hash",
            "normalized_request_hash",
            "resolved_environment_hash",
            "build_artifact_manifest_hash",
            "execution_input_bundle_ref",
            "execution_input_source_hash",
            "market_bundle_ref",
            "market_bundle_publication",
            "market_bundle_publication_source_hash",
            "market_bundle_retention_proof",
            "market_bundle_retention_source_hash",
            "retrievability",
            "preparation_hash",
            "target_stream_digest",
            "semantic_spec_hash",
            "identity_manifest_hash",
            "execution_case_hash",
            "attempts",
            "fresh_rebuild",
            "comparisons",
            "claim",
        },
    )
    if data["type"] != _VERIFICATION_TYPE or data["schema_version"] != 1:
        raise ValueError("verification must be deterministic_rebuild_verification@1")
    return DeterministicRebuildVerificationV1(
        semantic_run_id=data["semantic_run_id"],
        request_hash=data["request_hash"],
        normalized_request_hash=data["normalized_request_hash"],
        resolved_environment_hash=data["resolved_environment_hash"],
        build_artifact_manifest_hash=data["build_artifact_manifest_hash"],
        execution_input_bundle_ref=_read_artifact_ref(data["execution_input_bundle_ref"]),
        execution_input_source_hash=data["execution_input_source_hash"],
        market_bundle_ref=_read_market_bundle_ref(data["market_bundle_ref"]),
        market_bundle_publication=_exact_mapping(
            "market_bundle_publication", data["market_bundle_publication"], _PUBLICATION_FIELDS
        ),
        market_bundle_publication_source_hash=data[
            "market_bundle_publication_source_hash"
        ],
        market_bundle_retention_proof=_exact_mapping(
            "market_bundle_retention_proof", data["market_bundle_retention_proof"], _RETENTION_FIELDS
        ),
        market_bundle_retention_source_hash=data[
            "market_bundle_retention_source_hash"
        ],
        retrievability=data["retrievability"],
        preparation_hash=data["preparation_hash"],
        target_stream_digest=data["target_stream_digest"],
        semantic_spec_hash=data["semantic_spec_hash"],
        identity_manifest_hash=data["identity_manifest_hash"],
        execution_case_hash=data["execution_case_hash"],
        attempts=tuple(_read_attempt_entry(value) for value in _exact_list("attempts", data["attempts"])),
        fresh_rebuild=_read_fresh(data["fresh_rebuild"]),
        comparisons=tuple(_read_comparison(value) for value in _exact_list("comparisons", data["comparisons"])),
        claim=data["claim"],
    )


def _read_proof_manifest(
    value: object,
) -> DeterministicRebuildVerificationPublicationManifestV1:
    data = _exact_mapping(
        "proof publication manifest",
        value,
        {
            "type",
            "schema_version",
            "semantic_run_id",
            "proof_id",
            "publication_id",
            "artifacts",
            "deployment_authorized",
        },
    )
    if data["type"] != _PROOF_MANIFEST_TYPE or data["schema_version"] != 1:
        raise ValueError("wrong proof publication manifest schema")
    return DeterministicRebuildVerificationPublicationManifestV1(
        semantic_run_id=data["semantic_run_id"],
        proof_id=data["proof_id"],
        publication_id=data["publication_id"],
        artifacts=tuple(
            _read_publication_entry(entry)
            for entry in _exact_list("artifacts", data["artifacts"])
        ),
        deployment_authorized=data["deployment_authorized"],
    )


_ARTIFACT_CATALOG = SchemaCatalog(
    (
        ArtifactSchemaRegistration(_VERIFICATION_TYPE, 1, _read_verification),
        ArtifactSchemaRegistration(_PROOF_MANIFEST_TYPE, 1, _read_proof_manifest),
    )
)


_ATTEMPT_ENTRY_FIELDS: Final = {
    "attempt",
    "evidence_manifest_ref",
    "evidence_manifest_hash",
    "evidence_manifest_source_hash",
    "evidence_publication_hash",
    "engine_result_ref",
    "execution_case_hash",
    "trace_hash",
    "execution_result_hash",
}
_FRESH_FIELDS: Final = {
    "preparation_hash",
    "target_stream_digest",
    "semantic_spec_hash",
    "identity_manifest_hash",
    "execution_case_hash",
    "trace_level",
    "trace_hash",
    "execution_result_hash",
}
_COMPARISON_FIELDS: Final = {
    "comparison_id",
    "left_subject",
    "right_subject",
    "outcome",
    "first_divergence",
    "left_hash",
    "right_hash",
}
_PUBLICATION_FIELDS: Final = {
    "type",
    "schema_version",
    "bundle_ref",
    "manifest_relative_path",
    "stream_relative_paths",
    "stream_payload_hashes",
    "retention_proof_relative_path",
    "retention_proof_hash",
    "retention_policy_ref",
    "publication_hash",
}
_RETENTION_FIELDS: Final = {
    "type",
    "schema_version",
    "bundle_ref",
    "retention_policy_ref",
    "manifest_relative_path",
    "manifest_source_hash",
    "stream_relative_paths",
    "stream_payload_hashes",
    "publication_relative_path",
    "proof_hash",
}


def _read_attempt_entry(value: object) -> _AttemptVerificationEntryV1:
    data = _exact_mapping("attempt entry", value, _ATTEMPT_ENTRY_FIELDS)
    return _AttemptVerificationEntryV1(
        attempt=_read_attempt_identity(data["attempt"]),
        evidence_manifest_ref=_read_artifact_ref(data["evidence_manifest_ref"]),
        evidence_manifest_hash=data["evidence_manifest_hash"],
        evidence_manifest_source_hash=data["evidence_manifest_source_hash"],
        evidence_publication_hash=data["evidence_publication_hash"],
        engine_result_ref=_read_artifact_ref(data["engine_result_ref"]),
        execution_case_hash=data["execution_case_hash"],
        trace_hash=data["trace_hash"],
        execution_result_hash=data["execution_result_hash"],
    )


def _read_fresh(value: object) -> _FreshRebuildObservationV1:
    data = _exact_mapping("fresh rebuild", value, _FRESH_FIELDS)
    return _FreshRebuildObservationV1(**data)  # type: ignore[arg-type]


def _read_comparison(value: object) -> RebuildComparisonV1:
    data = _exact_mapping("comparison", value, _COMPARISON_FIELDS)
    divergence = data["first_divergence"]
    return RebuildComparisonV1(
        comparison_id=data["comparison_id"],
        left_subject=data["left_subject"],
        right_subject=data["right_subject"],
        outcome=RebuildComparisonOutcome(data["outcome"]),
        first_divergence=(
            None if divergence is None else RebuildDivergenceSubject(divergence)
        ),
        left_hash=data["left_hash"],
        right_hash=data["right_hash"],
    )


def _read_publication_entry(value: object) -> _PublicationArtifactEntryV1:
    data = _exact_mapping(
        "proof publication entry",
        value,
        {
            "relative_path",
            "artifact_type",
            "schema_version",
            "content_hash",
            "source_hash",
            "byte_count",
        },
    )
    return _PublicationArtifactEntryV1(**data)  # type: ignore[arg-type]


def _read_attempt_identity(value: object) -> AttemptIdentity:
    data = _exact_mapping(
        "attempt identity",
        value,
        {
            "type",
            "schema_version",
            "semantic_run_id",
            "ordinal",
            "parent_attempt_id",
            "attempt_id",
        },
    )
    if data["type"] != "attempt_identity" or data["schema_version"] != 1:
        raise ValueError("attempt identity must be attempt_identity@1")
    return AttemptIdentity(
        semantic_run_id=data["semantic_run_id"],
        ordinal=data["ordinal"],
        parent_attempt_id=data["parent_attempt_id"],
        attempt_id=data["attempt_id"],
    )


def _read_artifact_ref(value: object) -> ArtifactRef:
    data = _exact_mapping(
        "artifact ref",
        value,
        {"type", "artifact_type", "schema_version", "content_hash"},
    )
    if data["type"] != "artifact_ref":
        raise ValueError("artifact ref type mismatch")
    return ArtifactRef(data["artifact_type"], data["schema_version"], data["content_hash"])


def _read_market_bundle_ref(value: object) -> MarketBundleRef:
    data = _exact_mapping(
        "market bundle ref", value, {"type", "bundle_key", "manifest_hash"}
    )
    if data["type"] != "market_bundle_ref":
        raise ValueError("market bundle ref type mismatch")
    return MarketBundleRef(data["bundle_key"], data["manifest_hash"])


def _build_verification(
    *,
    resolved_request: ResolvedBacktestRequest,
    prepared_market_data: PreparedMultiResolutionMarketData,
    execution_case: ResolvedExecutionCase,
    execution_source: ArtifactReadResult,
    publication: Mapping[str, object],
    publication_source_hash: str,
    retention: Mapping[str, object],
    retention_source_hash: str,
    attempts: tuple[_AttemptVerificationEntryV1, ...],
    fresh: _FreshRebuildObservationV1,
) -> DeterministicRebuildVerificationV1:
    request = resolved_request.request
    return DeterministicRebuildVerificationV1(
        semantic_run_id=resolved_request.semantic_run_id,
        request_hash=request.request_hash,
        normalized_request_hash=canonical_sha256(resolved_request.normalized_request),
        resolved_environment_hash=canonical_sha256(resolved_request.environment),
        build_artifact_manifest_hash=resolved_request.build_artifact_manifest.manifest_hash,
        execution_input_bundle_ref=ArtifactRef.from_envelope(execution_source.envelope),
        execution_input_source_hash=execution_source.source_hash,
        market_bundle_ref=request.market_bundle_ref,
        market_bundle_publication=publication,
        market_bundle_publication_source_hash=publication_source_hash,
        market_bundle_retention_proof=retention,
        market_bundle_retention_source_hash=retention_source_hash,
        retrievability=_RETRIEVABILITY,
        preparation_hash=canonical_sha256(prepared_market_data.preparation),
        target_stream_digest=execution_case.target_stream.target_stream_digest,
        semantic_spec_hash=execution_case.semantic_spec_hash,
        identity_manifest_hash=_identity_manifest_hash(execution_case),
        execution_case_hash=execution_case.case_hash,
        attempts=attempts,
        fresh_rebuild=fresh,
        comparisons=_build_comparisons(
            attempts,
            fresh,
            common=(
                request.request_hash,
                canonical_sha256(resolved_request.normalized_request),
                canonical_sha256(resolved_request.environment),
                resolved_request.build_artifact_manifest.manifest_hash,
                execution_source.envelope.content_hash,
                execution_source.source_hash,
                publication_source_hash,
                retention_source_hash,
                canonical_sha256(prepared_market_data.preparation),
                execution_case.target_stream.target_stream_digest,
                execution_case.semantic_spec_hash,
                _identity_manifest_hash(execution_case),
            ),
        ),
        claim=_CLAIM,
    )


def _fresh_observation(rebuilt: _FreshRebuildResultV1) -> _FreshRebuildObservationV1:
    case = rebuilt.execution_case
    return _FreshRebuildObservationV1(
        preparation_hash=canonical_sha256(rebuilt.prepared_market_data.preparation),
        target_stream_digest=case.target_stream.target_stream_digest,
        semantic_spec_hash=case.semantic_spec_hash,
        identity_manifest_hash=_identity_manifest_hash(case),
        execution_case_hash=case.case_hash,
        trace_level="full_trace",
        trace_hash=rebuilt.engine_result.trace.trace_hash,
        execution_result_hash=CanonicalExecutionSummary.from_result(
            rebuilt.engine_result
        ).execution_result_hash,
    )


def _build_attempt_entries(
    attempts: AttemptConsistencySet,
    reader: ArtifactEnvelopeReader,
    semantic_run_id: str,
) -> tuple[
    tuple[_AttemptVerificationEntryV1, ...], tuple[AttemptExecutionRecord, ...]
]:
    finalized_by_id = {
        evidence.attempt.attempt_id: evidence for evidence in attempts.finalized_attempts
    }
    values = tuple(
        _attempt_entry(
            attempt_hash,
            finalized_by_id[attempt_hash.attempt.attempt_id],
            reader,
        )
        for attempt_hash in sorted(
            attempts.attempt_hashes,
            key=lambda value: (value.attempt.ordinal, value.attempt.attempt_id),
        )
    )
    entries = tuple(value[0] for value in values)
    if any(entry.attempt.semantic_run_id != semantic_run_id for entry in entries):
        raise ValueError("Attempt semantic run mismatch")
    return entries, tuple(value[1] for value in values)


def _attempt_entry(
    attempt_hash: AttemptExecutionHash,
    evidence: FinalizedAttemptEvidence,
    reader: ArtifactEnvelopeReader,
) -> tuple[_AttemptVerificationEntryV1, AttemptExecutionRecord]:
    if (
        type(attempt_hash) is not AttemptExecutionHash
        or type(evidence) is not FinalizedAttemptEvidence
        or evidence.status is not EvidencePublicationStatus.READY_FOR_INTEGRITY
        or evidence.attempt != attempt_hash.attempt
    ):
        raise ValueError("Attempt evidence binding mismatch")
    manifest_envelope = ArtifactEnvelope.create("evidence_manifest", 1, evidence.manifest)
    manifest_ref = ArtifactRef.from_envelope(manifest_envelope)
    manifest_read = _read_ref(reader, manifest_ref, EvidenceManifest)
    if (
        manifest_read.artifact != evidence.manifest
        or manifest_read.source_hash != evidence.manifest_source_hash
        or evidence.manifest.manifest_hash != attempt_hash.evidence_manifest_hash
        or evidence.publication_hash != canonical_sha256(evidence)
        or evidence.manifest.semantic_run_id != evidence.attempt.semantic_run_id
        or evidence.manifest.attempt_id != evidence.attempt.attempt_id
    ):
        raise ValueError("evidence manifest binding mismatch")
    record_entry = _one_role(evidence.manifest, EvidenceArtifactRole.ATTEMPT_EXECUTION_RECORD)
    record_ref = ArtifactRef(
        record_entry.artifact_type,
        record_entry.schema_version,
        record_entry.content_hash,
    )
    record_read = _read_ref(reader, record_ref, AttemptExecutionRecord)
    record = record_read.artifact
    if (
        record.attempt != evidence.attempt
        or record.ready_to_finalize is None
        or record.ready_to_finalize.attempt != evidence.attempt
        or record.ready_to_finalize.engine_result != attempt_hash.engine_result
        or canonical_sha256(record) != evidence.manifest.attempt_record_hash
        or record_read.source_hash != record_entry.source_hash
        or len(record_read.source_bytes) != record_entry.byte_count
    ):
        raise ValueError("attempt record binding mismatch")
    engine_entry = _one_role(evidence.manifest, EvidenceArtifactRole.ENGINE_EXECUTION_RESULT)
    engine_ref = ArtifactRef(
        engine_entry.artifact_type,
        engine_entry.schema_version,
        engine_entry.content_hash,
    )
    engine_read = _read_ref(reader, engine_ref, EngineExecutionResult)
    engine = engine_read.artifact
    if (
        engine != attempt_hash.engine_result
        or engine_ref.content_hash != attempt_hash.engine_result_artifact_content_hash
        or engine_read.source_hash != engine_entry.source_hash
        or len(engine_read.source_bytes) != engine_entry.byte_count
        or engine.case_hash != record.execution_case_hash
        or engine.trace.trace_hash != attempt_hash.engine_result.trace.trace_hash
        or CanonicalExecutionSummary.from_result(engine).execution_result_hash
        != attempt_hash.execution_result_hash
    ):
        raise ValueError("engine result binding mismatch")
    return (
        _AttemptVerificationEntryV1(
            attempt=evidence.attempt,
            evidence_manifest_ref=manifest_ref,
            evidence_manifest_hash=evidence.manifest.manifest_hash,
            evidence_manifest_source_hash=evidence.manifest_source_hash,
            evidence_publication_hash=evidence.publication_hash,
            engine_result_ref=engine_ref,
            execution_case_hash=engine.case_hash,
            trace_hash=engine.trace.trace_hash,
            execution_result_hash=attempt_hash.execution_result_hash,
        ),
        record,
    )


def _validate_verification_structure(
    verification: DeterministicRebuildVerificationV1,
    reader: ArtifactEnvelopeReader,
) -> None:
    _validate_verification(verification)
    first = AttemptIdentity.first(verification.semantic_run_id)
    second = AttemptIdentity.retry(first, next_ordinal=2)
    if tuple(entry.attempt for entry in verification.attempts) != (first, second):
        raise ValueError("verification Attempt pair mismatch")

    required_roles: tuple[tuple[EvidenceArtifactRole, type[object]], ...] = (
        (EvidenceArtifactRole.REQUEST, BacktestRequest),
        (EvidenceArtifactRole.ENVIRONMENT, ResolvedBacktestEnvironment),
        (EvidenceArtifactRole.BUILD_ARTIFACT_MANIFEST, BuildArtifactManifest),
        (EvidenceArtifactRole.MARKET_BUNDLE_REFERENCE, MarketBundleRef),
        (
            EvidenceArtifactRole.ENVIRONMENT_COMPATIBILITY,
            EnvironmentCompatibilityReport,
        ),
        (EvidenceArtifactRole.ATTEMPT_EXECUTION_RECORD, AttemptExecutionRecord),
        (EvidenceArtifactRole.ENGINE_EXECUTION_RESULT, EngineExecutionResult),
    )
    graphs: list[
        tuple[
            EvidenceManifest,
            dict[EvidenceArtifactRole, ArtifactReadResult],
            AttemptExecutionRecord,
            EngineExecutionResult,
        ]
    ] = []
    for verification_entry in verification.attempts:
        manifest_read = _read_ref(
            reader, verification_entry.evidence_manifest_ref, EvidenceManifest
        )
        manifest = manifest_read.artifact
        if (
            manifest.semantic_run_id != verification_entry.attempt.semantic_run_id
            or manifest.attempt_id != verification_entry.attempt.attempt_id
            or manifest.manifest_hash != verification_entry.evidence_manifest_hash
            or manifest_read.source_hash
            != verification_entry.evidence_manifest_source_hash
        ):
            raise ValueError("verification evidence manifest mismatch")
        role_reads = {
            role: _read_evidence_role(reader, manifest, role, expected_type)
            for role, expected_type in required_roles
        }
        record_read = role_reads[EvidenceArtifactRole.ATTEMPT_EXECUTION_RECORD]
        engine_read = role_reads[EvidenceArtifactRole.ENGINE_EXECUTION_RESULT]
        record = record_read.artifact
        engine = engine_read.artifact
        if (
            type(record) is not AttemptExecutionRecord
            or record.attempt != verification_entry.attempt
            or record.ready_to_finalize is None
            or record.ready_to_finalize.attempt != verification_entry.attempt
            or canonical_sha256(record) != manifest.attempt_record_hash
        ):
            raise ValueError("verification attempt record mismatch")
        expected_evidence = FinalizedAttemptEvidence(
            attempt=verification_entry.attempt,
            status=EvidencePublicationStatus.READY_FOR_INTEGRITY,
            terminal_outcome=None,
            manifest=manifest,
            manifest_source_hash=verification_entry.evidence_manifest_source_hash,
            relative_directory=(
                f"runs/{verification_entry.attempt.semantic_run_id}/attempts/"
                f"{verification_entry.attempt.attempt_id}"
            ),
        )
        if expected_evidence.publication_hash != verification_entry.evidence_publication_hash:
            raise ValueError("verification evidence publication mismatch")
        engine_entry = _one_role(
            manifest, EvidenceArtifactRole.ENGINE_EXECUTION_RESULT
        )
        expected_engine_ref = ArtifactRef(
            engine_entry.artifact_type,
            engine_entry.schema_version,
            engine_entry.content_hash,
        )
        if expected_engine_ref != verification_entry.engine_result_ref:
            raise ValueError("verification engine ref mismatch")
        if (
            type(engine) is not EngineExecutionResult
            or record.ready_to_finalize.engine_result != engine
            or engine.case_hash != verification_entry.execution_case_hash
            or engine.trace.trace_hash != verification_entry.trace_hash
            or CanonicalExecutionSummary.from_result(engine).execution_result_hash
            != verification_entry.execution_result_hash
        ):
            raise ValueError("verification engine hashes mismatch")
        graphs.append((manifest, role_reads, record, engine))

    common_roles = (
        EvidenceArtifactRole.REQUEST,
        EvidenceArtifactRole.ENVIRONMENT,
        EvidenceArtifactRole.BUILD_ARTIFACT_MANIFEST,
        EvidenceArtifactRole.MARKET_BUNDLE_REFERENCE,
        EvidenceArtifactRole.ENVIRONMENT_COMPATIBILITY,
    )
    for role in common_roles:
        first_entry = _one_role(graphs[0][0], role)
        second_entry = _one_role(graphs[1][0], role)
        if (
            first_entry.artifact_type,
            first_entry.schema_version,
            first_entry.content_hash,
            first_entry.source_hash,
            first_entry.byte_count,
            graphs[0][1][role].artifact,
        ) != (
            second_entry.artifact_type,
            second_entry.schema_version,
            second_entry.content_hash,
            second_entry.source_hash,
            second_entry.byte_count,
            graphs[1][1][role].artifact,
        ):
            raise ValueError("Attempt common evidence roots mismatch")

    first_record = graphs[0][2]
    second_record = graphs[1][2]
    if first_record.ready_to_finalize is None or second_record.ready_to_finalize is None:
        raise ValueError("Attempt records are not ready")
    resolved = first_record.ready_to_finalize.resolved_request
    if second_record.ready_to_finalize.resolved_request != resolved:
        raise ValueError("Attempt resolved roots mismatch")
    common_request = graphs[0][1][EvidenceArtifactRole.REQUEST].artifact
    common_environment = graphs[0][1][EvidenceArtifactRole.ENVIRONMENT].artifact
    common_build = graphs[0][1][EvidenceArtifactRole.BUILD_ARTIFACT_MANIFEST].artifact
    common_market = graphs[0][1][EvidenceArtifactRole.MARKET_BUNDLE_REFERENCE].artifact
    common_compatibility = graphs[0][1][
        EvidenceArtifactRole.ENVIRONMENT_COMPATIBILITY
    ].artifact
    if (
        type(common_request) is not BacktestRequest
        or type(common_environment) is not ResolvedBacktestEnvironment
        or type(common_build) is not BuildArtifactManifest
        or type(common_market) is not MarketBundleRef
        or type(common_compatibility) is not EnvironmentCompatibilityReport
        or resolved.request != common_request
        or resolved.environment != common_environment
        or resolved.build_artifact_manifest != common_build
        or resolved.environment.market_bundle_ref != common_market
        or resolved.environment.compatibility_report != common_compatibility
        or resolved.semantic_run_id != verification.semantic_run_id
        or resolved.request.request_hash != verification.request_hash
        or canonical_sha256(resolved.normalized_request)
        != verification.normalized_request_hash
        or canonical_sha256(resolved.environment)
        != verification.resolved_environment_hash
        or resolved.build_artifact_manifest.manifest_hash
        != verification.build_artifact_manifest_hash
        or resolved.environment.market_bundle_ref != verification.market_bundle_ref
    ):
        raise ValueError("verification common evidence binding mismatch")

    execution_request = BacktestExecutionRequest(
        schema_version=verification.execution_input_bundle_ref.schema_version,
        request=common_request,
        execution_input_bundle_ref=verification.execution_input_bundle_ref,
    )
    execution_read, decoded, failure = _read_execution_inputs_with_source(
        reader, execution_request
    )
    if failure is not None or decoded is None:
        raise ValueError("verification execution input read-back failed")
    if execution_read is None:
        raise ValueError("verification execution input source unavailable")
    if (
        ArtifactRef.from_envelope(execution_read.envelope)
        != verification.execution_input_bundle_ref
        or execution_read.source_hash != verification.execution_input_source_hash
        or decoded.request_hash != verification.request_hash
        or decoded.semantic_run_id != verification.semantic_run_id
        or decoded.build_artifact_manifest != common_build
        or canonical_sha256(decoded.market_data_preparation)
        != verification.preparation_hash
        or decoded.execution_case_semantic_spec.target_stream_digest
        != verification.target_stream_digest
        or decoded.execution_case_semantic_spec.semantic_spec_hash
        != verification.semantic_spec_hash
        or first_record.ready_to_finalize.execution_case_hash
        != verification.execution_case_hash
        or second_record.ready_to_finalize.execution_case_hash
        != verification.execution_case_hash
    ):
        raise ValueError("verification execution input common roots mismatch")

    expected = _build_comparisons(
        verification.attempts,
        verification.fresh_rebuild,
        common=(
            verification.request_hash,
            verification.normalized_request_hash,
            verification.resolved_environment_hash,
            verification.build_artifact_manifest_hash,
            verification.execution_input_bundle_ref.content_hash,
            verification.execution_input_source_hash,
            verification.market_bundle_publication_source_hash,
            verification.market_bundle_retention_source_hash,
            verification.preparation_hash,
            verification.target_stream_digest,
            verification.semantic_spec_hash,
            verification.identity_manifest_hash,
        ),
    )
    if verification.comparisons != expected:
        raise ValueError("verification comparisons mismatch")


def _read_execution_inputs_with_source(
    reader: ArtifactEnvelopeReader,
    request: BacktestExecutionRequest,
) -> tuple[
    ArtifactReadResult | None,
    _DecodedExecutionInputBundleV3 | None,
    _ExecutionInputsHydrationFailureV3 | None,
]:
    if type(request) is not BacktestExecutionRequest or request.schema_version not in {
        3,
        4,
        6,
        7,
    }:
        return (
            None,
            None,
            _ExecutionInputsHydrationFailureV3(
                _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
            ),
        )
    read_inputs = {
        3: _read_execution_inputs_v3_from_snapshot,
        4: _read_execution_inputs_v4_from_snapshot,
        6: _read_execution_inputs_v6_from_snapshot,
        7: _read_execution_inputs_v7_from_snapshot,
    }[request.schema_version]
    try:
        source = reader.read(ref=request.execution_input_bundle_ref)
    except Exception:  # noqa: BLE001 - exact decoder owns redacted classification
        decoded, failure = read_inputs(reader, request)
        return None, decoded, failure
    if type(source) is not ArtifactReadResult:
        source_result: ArtifactReadResult | None = None
    else:
        source_result = source

    class CapturedReader:
        @staticmethod
        def read(*, ref: ArtifactRef) -> ArtifactReadResult:
            if ref != request.execution_input_bundle_ref:
                raise ValueError("captured execution input ref mismatch")
            return source  # type: ignore[return-value]

    decoded, failure = read_inputs(CapturedReader(), request)
    return source_result, decoded, failure


def _read_evidence_role(
    reader: ArtifactEnvelopeReader,
    manifest: EvidenceManifest,
    role: EvidenceArtifactRole,
    expected_type: type[object],
) -> ArtifactReadResult:
    entry = _one_role(manifest, role)
    ref = ArtifactRef(entry.artifact_type, entry.schema_version, entry.content_hash)
    result = _read_ref(reader, ref, expected_type)
    if (
        result.source_hash != entry.source_hash
        or len(result.source_bytes) != entry.byte_count
        or result.envelope.artifact_type != entry.artifact_type
        or result.envelope.schema_version != entry.schema_version
        or result.envelope.content_hash != entry.content_hash
        or ArtifactEnvelope.create(
            entry.artifact_type, entry.schema_version, result.artifact
        )
        != result.envelope
    ):
        raise ValueError("evidence entry source/envelope binding mismatch")
    return result

def _validate_verification(verification: DeterministicRebuildVerificationV1) -> None:
    _canonical_run(verification.semantic_run_id)
    for name in (
        "request_hash",
        "normalized_request_hash",
        "resolved_environment_hash",
        "build_artifact_manifest_hash",
        "execution_input_source_hash",
        "market_bundle_publication_source_hash",
        "market_bundle_retention_source_hash",
        "preparation_hash",
        "target_stream_digest",
        "semantic_spec_hash",
        "identity_manifest_hash",
        "execution_case_hash",
    ):
        _canonical_hash(name, getattr(verification, name))
    if type(verification.execution_input_bundle_ref) is not ArtifactRef or (
        verification.execution_input_bundle_ref.artifact_type
        != "backtest_execution_input_bundle"
        or verification.execution_input_bundle_ref.schema_version not in {3, 4, 6, 7}
    ):
        raise ValueError("execution_input_bundle_ref must target schema 3, 4, 6, or 7")
    if type(verification.market_bundle_ref) is not MarketBundleRef:
        raise TypeError("market_bundle_ref must be exact MarketBundleRef")
    publication = _validate_g12d_mapping(
        verification.market_bundle_publication,
        verification.market_bundle_publication_source_hash,
        verification.market_bundle_ref,
        publication=True,
    )
    retention = _validate_g12d_mapping(
        verification.market_bundle_retention_proof,
        verification.market_bundle_retention_source_hash,
        verification.market_bundle_ref,
        publication=False,
    )
    _validate_g12d_pair(publication, retention)
    if verification.retrievability != _RETRIEVABILITY or verification.claim != _CLAIM:
        raise ValueError("verification constants mismatch")
    if type(verification.attempts) is not tuple or len(verification.attempts) != 2 or not all(
        type(entry) is _AttemptVerificationEntryV1 for entry in verification.attempts
    ):
        raise ValueError("verification must contain exactly two Attempt entries")
    if tuple(sorted(verification.attempts, key=lambda entry: (entry.attempt.ordinal, entry.attempt.attempt_id))) != verification.attempts:
        raise ValueError("Attempt entries must be canonically ordered")
    if type(verification.fresh_rebuild) is not _FreshRebuildObservationV1:
        raise TypeError("fresh_rebuild must be exact fresh observation")
    if type(verification.comparisons) is not tuple or len(verification.comparisons) != 3 or not all(
        type(value) is RebuildComparisonV1 for value in verification.comparisons
    ):
        raise ValueError("verification must contain exactly three comparisons")
    if tuple(value.comparison_id for value in verification.comparisons) != _COMPARISON_IDS:
        raise ValueError("comparison order mismatch")


def _build_comparisons(
    attempts: tuple[_AttemptVerificationEntryV1, ...],
    fresh: _FreshRebuildObservationV1,
    *,
    common: tuple[str, ...],
) -> tuple[RebuildComparisonV1, ...]:
    if len(attempts) != 2 or len(common) != 12:
        raise ValueError("comparison roots are incomplete")
    first, second = attempts

    def vector(entry: _AttemptVerificationEntryV1) -> tuple[str, ...]:
        return (
            *common,
            entry.execution_case_hash,
            entry.trace_hash,
            entry.execution_result_hash,
        )

    fresh_vector = (
        *common[:8],
        fresh.preparation_hash,
        fresh.target_stream_digest,
        fresh.semantic_spec_hash,
        fresh.identity_manifest_hash,
        fresh.execution_case_hash,
        fresh.trace_hash,
        fresh.execution_result_hash,
    )
    return (
        _compare(
            _COMPARISON_IDS[0],
            first.attempt.attempt_id,
            second.attempt.attempt_id,
            vector(first),
            vector(second),
        ),
        _compare(
            _COMPARISON_IDS[1],
            first.attempt.attempt_id,
            _REBUILD_SUBJECT,
            vector(first),
            fresh_vector,
        ),
        _compare(
            _COMPARISON_IDS[2],
            second.attempt.attempt_id,
            _REBUILD_SUBJECT,
            vector(second),
            fresh_vector,
        ),
    )


def _compare(
    comparison_id: str,
    left_subject: str,
    right_subject: str,
    left: tuple[str, ...],
    right: tuple[str, ...],
) -> RebuildComparisonV1:
    for subject, left_hash, right_hash in zip(_COMPARISON_SUBJECTS, left, right, strict=True):
        if left_hash != right_hash:
            return RebuildComparisonV1(
                comparison_id,
                left_subject,
                right_subject,
                RebuildComparisonOutcome.MISMATCH,
                subject,
                left_hash,
                right_hash,
            )
    return RebuildComparisonV1(
        comparison_id,
        left_subject,
        right_subject,
        RebuildComparisonOutcome.EQUAL,
        None,
        left[-1],
        right[-1],
    )


def _proof_manifest(
    verification: DeterministicRebuildVerificationV1,
    verification_ref: ArtifactRef,
    verification_source_hash: str,
    byte_count: int,
) -> DeterministicRebuildVerificationPublicationManifestV1:
    proof_id = "proof_" + canonical_sha256(
        {
            "type": "deterministic_rebuild_proof_identity",
            "schema_version": 1,
            "semantic_run_id": verification.semantic_run_id,
            "verification_ref": verification_ref,
        }
    ).removeprefix("sha256:")
    publication_id = "proof_publication_" + canonical_sha256(
        {
            "type": "deterministic_rebuild_proof_publication_identity",
            "schema_version": 1,
            "proof_id": proof_id,
            "verification_source_hash": verification_source_hash,
        }
    ).removeprefix("sha256:")
    return DeterministicRebuildVerificationPublicationManifestV1(
        semantic_run_id=verification.semantic_run_id,
        proof_id=proof_id,
        publication_id=publication_id,
        artifacts=(
            _PublicationArtifactEntryV1(
                relative_path=_VERIFICATION_PATH,
                artifact_type=_VERIFICATION_TYPE,
                schema_version=1,
                content_hash=verification_ref.content_hash,
                source_hash=verification_source_hash,
                byte_count=byte_count,
            ),
        ),
    )


def _validate_manifest_binding(
    verification: DeterministicRebuildVerificationV1,
    verification_ref: ArtifactRef,
    verification_source_bytes: bytes,
    verification_source_hash: str,
    manifest: DeterministicRebuildVerificationPublicationManifestV1,
) -> None:
    expected = _proof_manifest(
        verification,
        verification_ref,
        verification_source_hash,
        len(verification_source_bytes),
    )
    if manifest != expected:
        raise ValueError("proof publication manifest binding mismatch")


def _validate_artifact_binding(
    artifact: object,
    envelope: ArtifactEnvelope,
    ref: ArtifactRef,
    source_bytes: bytes,
    source_hash: str,
    artifact_type: str,
) -> None:
    if type(envelope) is not ArtifactEnvelope or type(ref) is not ArtifactRef:
        raise TypeError("artifact envelope/ref must be exact values")
    if (
        envelope.artifact_type != artifact_type
        or envelope.schema_version != 1
        or ArtifactRef.from_envelope(envelope) != ref
        or source_bytes != canonical_bytes(envelope)
        or source_hash != _source_hash(source_bytes)
        or ArtifactEnvelope.create(artifact_type, 1, artifact) != envelope
    ):
        raise ValueError("artifact envelope/ref/source binding mismatch")


def _decode_g12d_publication(
    source: bytes, source_hash: str, ref: MarketBundleRef
) -> Mapping[str, object]:
    value = _decode_canonical_json(source)
    return _validate_g12d_mapping(value, source_hash, ref, publication=True)


def _decode_g12d_retention(
    source: bytes, source_hash: str, ref: MarketBundleRef
) -> Mapping[str, object]:
    value = _decode_canonical_json(source)
    return _validate_g12d_mapping(value, source_hash, ref, publication=False)


def _validate_g12d_mapping(
    value: object,
    source_hash: str,
    ref: MarketBundleRef,
    *,
    publication: bool,
) -> Mapping[str, object]:
    fields = _PUBLICATION_FIELDS if publication else _RETENTION_FIELDS
    name = "market bundle publication" if publication else "market bundle retention"
    data = _exact_mapping(name, value, fields)
    expected_type = "market_bundle_publication" if publication else "market_bundle_retention_proof"
    if data["type"] != expected_type or data["schema_version"] != 1:
        raise ValueError(f"{name} constants mismatch")
    if _read_market_bundle_ref(data["bundle_ref"]) != ref:
        raise ValueError(f"{name} bundle ref mismatch")
    if canonical_bytes(data) != canonical_bytes(value) or _source_hash(canonical_bytes(data)) != source_hash:
        raise ValueError(f"{name} source hash mismatch")
    hash_field = "publication_hash" if publication else "proof_hash"
    body_hash = data[hash_field]
    _canonical_hash(hash_field, body_hash)
    without_hash = {key: child for key, child in data.items() if key != hash_field}
    if canonical_sha256(without_hash) != body_hash:
        raise ValueError(f"{name} body hash mismatch")
    manifest_path = _relative_path(
        "manifest_relative_path", data["manifest_relative_path"]
    )
    linked_path_key = (
        "retention_proof_relative_path"
        if publication
        else "publication_relative_path"
    )
    linked_path = _relative_path(linked_path_key, data[linked_path_key])
    exact_root = (
        f"bundles/{ref.bundle_key}/"
        f"{ref.manifest_hash.removeprefix('sha256:')}"
    )
    if manifest_path != f"{exact_root}/manifest.json" or linked_path != (
        f"{exact_root}/retention-proof.json"
        if publication
        else f"{exact_root}/publication.json"
    ):
        raise ValueError(f"{name} relative root mismatch")
    stream_paths = tuple(
        _relative_path("stream_relative_path", child)
        for child in _exact_list("stream_relative_paths", data["stream_relative_paths"])
    )
    stream_hashes = tuple(
        _canonical_hash("stream_payload_hash", child)
        for child in _exact_list("stream_payload_hashes", data["stream_payload_hashes"])
    )
    expected_stream_paths = tuple(
        f"{exact_root}/streams/{index:03d}.payload"
        for index in range(len(stream_paths))
    )
    if (
        not stream_paths
        or len(stream_paths) != len(stream_hashes)
        or stream_paths != expected_stream_paths
    ):
        raise ValueError(f"{name} stream coverage mismatch")
    _canonical_text("retention_policy_ref", data["retention_policy_ref"])
    if publication:
        _canonical_hash("retention_proof_hash", data["retention_proof_hash"])
    else:
        if (
            _canonical_hash("manifest_source_hash", data["manifest_source_hash"])
            != ref.manifest_hash
        ):
            raise ValueError("market bundle retention manifest hash mismatch")
    return _freeze_mapping(data)


def _validate_g12d_pair(
    publication: Mapping[str, object], retention: Mapping[str, object]
) -> None:
    if (
        publication["bundle_ref"] != retention["bundle_ref"]
        or publication["retention_policy_ref"] != retention["retention_policy_ref"]
        or publication["manifest_relative_path"] != retention["manifest_relative_path"]
        or publication["stream_relative_paths"] != retention["stream_relative_paths"]
        or publication["stream_payload_hashes"] != retention["stream_payload_hashes"]
        or publication["retention_proof_hash"] != retention["proof_hash"]
        or publication["retention_proof_relative_path"].removesuffix("retention-proof.json")
        != retention["publication_relative_path"].removesuffix("publication.json")
    ):
        raise ValueError("G12D publication/retention binding mismatch")


def _read_ref(
    reader: ArtifactEnvelopeReader,
    ref: ArtifactRef,
    expected_type: type[object],
) -> ArtifactReadResult:
    result = reader.read(ref=ref)
    if type(result) is not ArtifactReadResult or type(result.artifact) is not expected_type:
        raise TypeError("artifact reader returned wrong exact type")
    if (
        ArtifactRef.from_envelope(result.envelope) != ref
        or result.source_bytes != canonical_bytes(result.envelope)
        or result.source_hash != _source_hash(result.source_bytes)
        or ArtifactEnvelope.create(
            ref.artifact_type, ref.schema_version, result.artifact
        )
        != result.envelope
    ):
        raise ValueError("artifact reader source binding mismatch")
    return result


def _one_role(manifest: EvidenceManifest, role: EvidenceArtifactRole):
    entries = tuple(entry for entry in manifest.artifacts if entry.role is role)
    if len(entries) != 1:
        raise ValueError("evidence role coverage mismatch")
    return entries[0]


def _validate_exact_attempt_pair(
    attempts: AttemptConsistencySet, semantic_run_id: str
) -> None:
    first = AttemptIdentity.first(semantic_run_id)
    second = AttemptIdentity.retry(first, next_ordinal=2)
    if tuple(value.attempt for value in attempts.attempt_hashes) != (first, second):
        raise ValueError("Attempt hashes must be exact first/retry pair")
    if tuple(value.attempt for value in attempts.finalized_attempts) != (first, second):
        raise ValueError("finalized evidence must be exact first/retry pair")


def _identity_manifest_hash(case: ResolvedExecutionCase) -> str:
    if case.identity_manifest is None:
        raise ValueError("execution case requires identity manifest")
    return case.identity_manifest.manifest_hash


def _decode_canonical_json(source: bytes) -> object:
    if type(source) is not bytes:
        raise TypeError("source must be exact bytes")
    value = json.loads(
        source.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
        parse_float=_reject_json_number,
        parse_constant=_reject_json_number,
    )
    if canonical_bytes(value) != source:
        raise ValueError("source must be canonical JSON bytes")
    return value


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = child
    return value


def _reject_json_number(value: str) -> object:
    raise ValueError(f"invalid JSON number: {value}")


def _exact_mapping(
    name: str, value: object, fields: set[str]
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"{name} must contain exact fields")
    return dict(value)


def _exact_list(name: str, value: object) -> list[object]:
    if type(value) not in {list, tuple}:
        raise TypeError(f"{name} must be a sequence")
    return list(value)


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    def freeze(child: object) -> object:
        if isinstance(child, Mapping):
            return MappingProxyType({key: freeze(item) for key, item in child.items()})
        if type(child) in {list, tuple}:
            return tuple(freeze(item) for item in child)
        return child

    return freeze(value)  # type: ignore[return-value]


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{name} must be canonical text")
    return value


def _canonical_hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256 identity")
    return value


def _canonical_run(value: object) -> str:
    if type(value) is not str or _RUN_PATTERN.fullmatch(value) is None:
        raise ValueError("semantic_run_id must use run_sha256 schema")
    return value


def _source_hash(source: bytes) -> str:
    return "sha256:" + hashlib.sha256(source).hexdigest()


def _request_run_hint(request: object) -> str:
    try:
        value = request.request.request_hash  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return "invalid"
    if type(value) is str and _HASH_PATTERN.fullmatch(value):
        return "run_" + value.removeprefix("sha256:")
    return "invalid"


def _run_subject_from_request(request: object) -> str:
    return f"runs/{_request_run_hint(request)}/rebuild-proofs"


def _require_directory(path: Path) -> None:
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(info.st_mode):
        raise ValueError("required path is not an exact directory")



__all__: list[str] = []
