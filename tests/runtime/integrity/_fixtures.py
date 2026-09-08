from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import (
    AttemptConsistencySet,
    AttemptEvidenceWriter,
    AttemptIdentity,
    ArtifactInstallMode,
    AuditableBacktestRunner,
    BacktestProfileRegistry,
    AttemptExecutionHash,
    DeterministicRebuildEvidence,
    ExecutionCaseComposer,
    ExecutionResultHasher,
    FinalizedAttemptEvidence,
    IntegrityTraceLevel,
    ExecutionTrace,
    InputOrigin,
    ProfileResolver,
    RequestedResultGrade,
    SourceTreeState,
)
from crypto_quant_domain import canonical_sha256
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder, reader
from tests.runtime.execution_hash._fixtures import publish_ready, ready_branch
from tests.runtime.resolution._fixtures import build_manifest, profile_registry, request


def _publish_resolved_case(root, resolved, case) -> AttemptConsistencySet:
    runner = AuditableBacktestRunner(publication_root=root)
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
    first_publication = AttemptEvidenceWriter(root=root).publish(first)
    second_publication = AttemptEvidenceWriter(root=root).publish(second)
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None
    hashes = (
        ExecutionResultHasher.bind(
            ready_branch(first), first_publication.finalized
        ),
        ExecutionResultHasher.bind(
            ready_branch(second), second_publication.finalized
        ),
    )
    return AttemptConsistencySet(
        resolved,
        hashes,
        (first_publication.finalized, second_publication.finalized),
    )


def decision_grade_attempts(root: Path) -> AttemptConsistencySet:
    registry = profile_registry()
    decision_registry = BacktestProfileRegistry(
        market_semantics_profiles=(
            replace(
                registry.market_semantics_profiles[0],
                grade=RequestedResultGrade.DECISION_GRADE,
                limitations=(),
                decision_grade_eligible=True,
            ),
        ),
        simulation_profiles=(
            replace(
                registry.simulation_profiles[0],
                grade=RequestedResultGrade.DECISION_GRADE,
                limitations=(),
                decision_grade_eligible=True,
            ),
        ),
        execution_account_profiles=(
            replace(
                registry.execution_account_profiles[0],
                grade=RequestedResultGrade.DECISION_GRADE,
                limitations=(),
                decision_grade_eligible=True,
            ),
        ),
    )
    builder = SyntheticExecutionCaseBuilder()
    spec = builder.semantic_spec()
    manifest = build_manifest()
    bundle = reader().manifest
    requested = replace(
        request(
            manifest,
            bundle=bundle,
            grade=RequestedResultGrade.DECISION_GRADE,
        ),
        execution_case_semantic_hash=spec.semantic_spec_hash,
        target_stream_digest=spec.target_stream_digest,
    )
    resolution = ProfileResolver().resolve(
        request=requested,
        registry=decision_registry,
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert resolution.resolved is not None
    case = ExecutionCaseComposer().compose(
        resolved_request=resolution.resolved,
        builder=builder,
    )
    return _publish_resolved_case(root, resolution.resolved, case)


def editable_build_attempts(root: Path) -> AttemptConsistencySet:
    builder = SyntheticExecutionCaseBuilder()
    spec = builder.semantic_spec()
    manifest = build_manifest(
        runtime_mode=ArtifactInstallMode.EDITABLE,
        runtime_content_hash=None,
        runtime_source_state=SourceTreeState.DIRTY,
    )
    bundle = reader().manifest
    requested = replace(
        request(manifest, bundle=bundle),
        execution_case_semantic_hash=spec.semantic_spec_hash,
        target_stream_digest=spec.target_stream_digest,
    )
    resolution = ProfileResolver().resolve(
        request=requested,
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert resolution.resolved is not None
    case = ExecutionCaseComposer().compose(
        resolved_request=resolution.resolved,
        builder=builder,
    )
    return _publish_resolved_case(root, resolution.resolved, case)


def one_attempt(root: Path) -> AttemptConsistencySet:
    record, publication = publish_ready(root, ordinal=1)
    assert publication.finalized is not None
    attempt_hash = ExecutionResultHasher.bind(
        ready_branch(record), publication.finalized
    )
    return AttemptConsistencySet(
        record.resolved_request,
        (attempt_hash,),
        (publication.finalized,),
    )


def two_attempts(
    root: Path,
) -> tuple[
    AttemptConsistencySet,
    tuple[AttemptExecutionHash, AttemptExecutionHash],
    tuple[FinalizedAttemptEvidence, FinalizedAttemptEvidence],
]:
    first_record, first_publication = publish_ready(root, ordinal=1)
    second_record, second_publication = publish_ready(root, ordinal=2)
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None
    first_hash = ExecutionResultHasher.bind(
        ready_branch(first_record), first_publication.finalized
    )
    second_hash = ExecutionResultHasher.bind(
        ready_branch(second_record), second_publication.finalized
    )
    finalized = (first_publication.finalized, second_publication.finalized)
    hashes = (first_hash, second_hash)
    return (
        AttemptConsistencySet(
            first_record.resolved_request,
            hashes,
            finalized,
        ),
        hashes,
        finalized,
    )


def mismatched_attempts(root: Path) -> AttemptConsistencySet:
    first_record, first_publication = publish_ready(root, ordinal=1)
    first_result = ready_branch(first_record).engine_result
    first_entry = first_result.trace.entries[0]
    changed_result = replace(
        first_result,
        trace=ExecutionTrace(
            (
                replace(
                    first_entry,
                    evidence_hash=canonical_sha256({"trace": "changed"}),
                ),
                *first_result.trace.entries[1:],
            )
        ),
    )
    second_record, second_publication = publish_ready(
        root,
        ordinal=2,
        result=changed_result,
    )
    assert first_publication.finalized is not None
    assert second_publication.finalized is not None
    hashes = (
        ExecutionResultHasher.bind(
            ready_branch(first_record), first_publication.finalized
        ),
        ExecutionResultHasher.bind(
            ready_branch(second_record), second_publication.finalized
        ),
    )
    return AttemptConsistencySet(
        first_record.resolved_request,
        hashes,
        (first_publication.finalized, second_publication.finalized),
    )


def rebuild_evidence(
    attempts: AttemptConsistencySet,
    *,
    trace_level: IntegrityTraceLevel = IntegrityTraceLevel.SUMMARY,
    bundle_retained: bool = False,
    deterministic_rebuild: bool = False,
) -> DeterministicRebuildEvidence:
    canonical = attempts.canonical_attempt
    resolved = canonical.engine_result
    request = attempts.resolved_request
    return DeterministicRebuildEvidence(
        semantic_run_id=attempts.semantic_run_id,
        request_hash=canonical_sha256(request.request),
        environment_hash=request.environment.environment_hash,
        build_artifact_manifest_hash=request.build_artifact_manifest.manifest_hash,
        market_bundle_manifest_hash=request.environment.market_bundle_ref.manifest_hash,
        market_bundle_retention_proof_hash=(
            canonical_sha256({"bundle": "retained"}) if bundle_retained else None
        ),
        target_stream_digest=request.request.target_stream_digest,
        execution_case_semantic_hash=request.request.execution_case_semantic_hash,
        execution_case_hash=resolved.case_hash,
        trace_hash=resolved.trace.trace_hash,
        trace_level=trace_level,
        execution_result_hash=canonical.execution_result_hash,
        deterministic_rebuild_proof_hash=(
            canonical_sha256({"rebuild": "verified"})
            if deterministic_rebuild
            else None
        ),
    )


__all__ = [
    "decision_grade_attempts",
    "editable_build_attempts",
    "mismatched_attempts",
    "one_attempt",
    "rebuild_evidence",
    "two_attempts",
]
