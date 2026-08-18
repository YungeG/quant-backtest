"""Public Backtest execution facade."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
from typing import NoReturn

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InputValidationFailure, MarketBundleReader

from ._publication import RunPublicationLock, verify_read_only
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .composition import _HydratedExecutionCaseInputs, _compose_execution_case_v3
from .engine import EngineCancellationRequest, ResolvedExecutionCase
from .evidence import (
    AttemptEvidenceWriter,
    EvidenceArtifactEntry,
    EvidenceArtifactRole,
    EvidenceManifest,
    EvidencePublicationStatus,
    FinalizedAttemptEvidence,
)
from .evidence_repository import BacktestEvidenceRepository
from .execution_hash import AttemptExecutionHash, ExecutionResultHasher
from .execution_inputs import (
    BacktestExecutionRequest,
    _ExecutionInputsHydrationFailureV3,
    _hydrate_execution_inputs,
    _hydrate_execution_inputs_v3_from_decoded,
    _read_execution_inputs_v3,
)
from .integrity import (
    CanonicalResultPublisher,
    DeterministicRebuildEvidence,
    EngineExecutionContext,
    IntegrityTraceLevel,
)
from .multi_resolution_preparation import (
    MarketDataCaseAuthority,
    MultiResolutionMarketDataPreparation,
    _capture_market_bundle_reader_v1,
    _prepare_multi_resolution_market_data_from_retained_v1,
)
from .publication_refs import BacktestCanonicalPublicationRef
from .resolution import BacktestProfileRegistry, ProfileResolver, ResolvedBacktestRequest
from .target_stream import PrecomputedTargetStream
from .runner import (
    AttemptExecutionRecord,
    AttemptIdentity,
    AttemptIssueSource,
    AuditableBacktestRunner,
    BacktestRunOutcome,
    CanonicalResultCacheHit,
    InputOrigin,
    ReadyToFinalizeAttempt,
    _read_canonical_artifact,
    _read_canonical_cache_hit_v2,
)

_STORAGE_RUNNER_ISSUES = frozenset({"canonical_cache_invalid", "run_lock_unavailable"})
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
@dataclass(frozen=True, slots=True)
class _RecoveredAttemptState:
    attempt: AttemptIdentity
    evidence: FinalizedAttemptEvidence
    record_payload: dict[str, object]
    engine_payload: dict[str, object] | None
    engine_content_hash: str | None


_MANIFEST_ENTRY_KEYS = frozenset(
    {
        "relative_path",
        "artifact_type",
        "schema_version",
        "content_hash",
        "source_hash",
        "byte_count",
    }
)


class BacktestRuntime:
    """Resolve, execute, verify, and publish one public Backtest request."""

    def __init__(
        self,
        *,
        registry: BacktestProfileRegistry,
        artifact_reader: ArtifactEnvelopeReader,
        artifact_publisher: ArtifactEnvelopePublisher,
        market_reader: MarketBundleReader,
        publication_root: Path,
    ) -> None:
        if type(registry) is not BacktestProfileRegistry:
            raise TypeError("registry must be exact BacktestProfileRegistry")
        if not callable(getattr(artifact_publisher, "put", None)):
            raise TypeError("artifact_publisher must provide put")
        if not isinstance(publication_root, Path):
            raise TypeError("publication_root must be pathlib.Path")
        self._registry = registry
        self._artifact_reader = artifact_reader
        self._artifact_publisher = artifact_publisher
        self._market_reader = market_reader
        self._publication_root = publication_root

    def run(
        self, request: BacktestExecutionRequest
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        return self._run(request, cancellation=None)

    def run_with_cancellation(
        self,
        request: BacktestExecutionRequest,
        cancellation: EngineCancellationRequest,
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        if type(cancellation) is not EngineCancellationRequest:
            raise TypeError("cancellation must be exact EngineCancellationRequest")
        return self._run(request, cancellation=cancellation)

    def _run(
        self,
        request: BacktestExecutionRequest,
        *,
        cancellation: EngineCancellationRequest | None,
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        if type(request) is BacktestExecutionRequest:
            try:
                schema_version = request.schema_version
            except Exception:
                raise RuntimeError(
                    "execution input hydration failed: malformed_execution_request"
                ) from None
            if type(schema_version) is not int:
                raise RuntimeError(
                    "execution input hydration failed: malformed_execution_request"
                )
            if schema_version == 3:
                return self._run_v3(request, cancellation=cancellation)
        return self._run_legacy(request, cancellation=cancellation)

    def _run_legacy(
        self,
        request: BacktestExecutionRequest,
        *,
        cancellation: EngineCancellationRequest | None,
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        hydrated = self._hydrate(request)
        resolution = self._resolve(
            request,
            market_bundle_manifest=self._market_reader.manifest,
            build_artifact_manifest=hydrated.build_artifact_manifest,
        )
        if resolution.failure is not None:
            return self._publish_resolution_failure(resolution.failure)
        resolved = resolution.resolved
        if resolved is None:
            raise RuntimeError("Backtest request resolution returned no result")

        execution_case = self._hydrate(request, resolved).execution_case
        if execution_case is None:
            raise RuntimeError("execution input bundle is not executable")
        return self._execute_case(
            resolved,
            execution_case,
            cancellation=cancellation,
            market_data_preparation=None,
        )

    def _run_v3(
        self,
        request: BacktestExecutionRequest,
        *,
        cancellation: EngineCancellationRequest | None,
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        bundle, failure = _read_execution_inputs_v3(
            self._artifact_reader,
            request,
        )
        if failure is not None or bundle is None:
            self._raise_v3_hydration_failure(failure)
        if (
            bundle.build_artifact_manifest.manifest_hash
            != request.request.build_artifact_manifest_hash
        ):
            raise RuntimeError(
                "execution input hydration failed: build_binding_mismatch"
            )
        retained_reader = _capture_market_bundle_reader_v1(
            request.request.market_bundle_ref,
            self._market_reader,
        )
        if retained_reader is None:
            raise RuntimeError(
                "execution input hydration failed: target_binding_mismatch"
            )
        target_stream = self._target_stream_v3(bundle, retained_reader, request)
        resolution = self._resolve(
            request,
            market_bundle_manifest=retained_reader.manifest,
            build_artifact_manifest=bundle.build_artifact_manifest,
        )
        if resolution.failure is not None:
            return self._publish_resolution_failure(resolution.failure)
        resolved = resolution.resolved
        if resolved is None:
            raise RuntimeError("Backtest request resolution returned no result")

        plan = bundle.execution_case_plan
        authority = MarketDataCaseAuthority(
            decision_cycles=plan.decision_cycles,
            bar_executions=plan.bar_executions,
            execution_model=plan.execution_model,
            snapshot_plan=plan.snapshot_plan,
            target_stream=target_stream,
        )
        embedded = bundle.market_data_preparation
        preparation_outcome = _prepare_multi_resolution_market_data_from_retained_v1(
            expected_bundle_ref=request.request.market_bundle_ref,
            reader=retained_reader,
            schedule=embedded.decision_schedule,
            signal_binding_candidates=embedded.bindings.signal_bindings,
            execution_binding_candidates=embedded.bindings.execution_bindings,
            valuation_binding_candidates=embedded.bindings.valuation_bindings,
            signal_lineages=embedded.signal_lineages,
            case_authority=authority,
            resolved_request=resolved,
        )
        prepared = preparation_outcome.prepared
        if prepared is None:
            raise RuntimeError(
                "execution input hydration failed: prepared_market_data_replay_mismatch"
            )
        hydrated = _hydrate_execution_inputs_v3_from_decoded(
            bundle,
            request,
            market_reader=retained_reader,
            resolved_request=resolved,
            prepared_market_data=prepared,
            target_stream=target_stream,
        )
        if hydrated.failure is not None or hydrated.result is None:
            self._raise_v3_hydration_failure(hydrated.failure)
        values = hydrated.result
        execution_case = _compose_execution_case_v3(
            resolved_request=resolved,
            market_reader=retained_reader,
            hydrated_inputs=_HydratedExecutionCaseInputs(
                values.execution_case_semantic_spec,
                values.timeline_stream_keys,
                values.target_stream,
                values.timeline_batch_size,
                values.execution_case_plan,
            ),
            market_data_preparation=values.market_data_preparation,
        )
        return self._execute_case(
            resolved,
            execution_case,
            cancellation=cancellation,
            market_data_preparation=prepared.preparation,
        )

    def _execute_case(
        self,
        resolved: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        *,
        cancellation: EngineCancellationRequest | None,
        market_data_preparation: MultiResolutionMarketDataPreparation | None,
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        input_origin = self._input_origin(resolved)
        runner = AuditableBacktestRunner.for_v2(publication_root=self._publication_root)
        if market_data_preparation is not None:
            runner._verify_v3_contract(
                resolved_request=resolved,
                execution_case=execution_case,
                input_origin=input_origin,
                market_data_preparation=market_data_preparation,
            )
            try:
                with RunPublicationLock(
                    root=self._publication_root,
                    semantic_run_id=resolved.semantic_run_id,
                ):
                    return self._execute_case_v3_locked(
                        resolved,
                        execution_case,
                        runner=runner,
                        input_origin=input_origin,
                        market_data_preparation=market_data_preparation,
                        cancellation=cancellation,
                    )
            except OSError as error:
                raise RuntimeError("Backtest storage failed: run_lock_unavailable") from error

        terminal_ref = self._existing_terminal_ref(resolved)
        if terminal_ref is not None:
            return terminal_ref
        if cancellation is not None:
            canonical_directory = (
                self._publication_root
                / "runs"
                / resolved.semantic_run_id
                / "canonical-v2"
            )
            if canonical_directory.exists():
                _read_canonical_cache_hit_v2(
                    root=self._publication_root,
                    resolved_request=resolved,
                    input_origin=input_origin,
                    execution_case=execution_case,
                )
                raise RuntimeError("completed semantic run cannot be cancelled")

        attempt = AttemptIdentity.first(resolved.semantic_run_id)
        if market_data_preparation is None:
            first = runner.execute(
                resolved_request=resolved,
                execution_case=execution_case,
                attempt=attempt,
                input_origin=input_origin,
                cancellation=cancellation,
            )
        else:
            first = runner._execute_verified(
                resolved_request=resolved,
                execution_case=execution_case,
                attempt=attempt,
                input_origin=input_origin,
                cancellation=cancellation,
            )
        cached = self._cache_ref(first)
        if cached is not None:
            return cached
        self._raise_runner_storage_failure(first)

        writer = self._attempt_writer()
        first_evidence = self._publish_attempt(writer, first)
        if first.ready_to_finalize is None:
            return self._evidence_ref(first_evidence)
        first_hash = ExecutionResultHasher.bind(
            first.ready_to_finalize,
            first_evidence,
        )

        if market_data_preparation is None:
            second = runner.retry_from_start(
                previous=first,
                resolved_request=resolved,
                execution_case=execution_case,
                next_attempt_ordinal=2,
                input_origin=input_origin,
                cancellation=cancellation,
            )
        else:
            second = runner._retry_from_start_verified(
                previous=first,
                resolved_request=resolved,
                execution_case=execution_case,
                next_attempt_ordinal=2,
                input_origin=input_origin,
                market_data_preparation=market_data_preparation,
                cancellation=cancellation,
            )
        cached = self._cache_ref(second)
        if cached is not None:
            return cached
        self._raise_runner_storage_failure(second)

        second_evidence = self._publish_attempt(writer, second)
        if second.ready_to_finalize is None:
            return self._evidence_ref(second_evidence)
        second_hash = ExecutionResultHasher.bind(
            second.ready_to_finalize,
            second_evidence,
        )
        return self._publish_canonical(
            resolved,
            execution_case,
            (first_hash, second_hash),
            (first_evidence, second_evidence),
        )

    def _execute_case_v3_locked(
        self,
        resolved: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        *,
        runner: AuditableBacktestRunner,
        input_origin: InputOrigin,
        market_data_preparation: MultiResolutionMarketDataPreparation,
        cancellation: EngineCancellationRequest | None,
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        first_attempt = AttemptIdentity.first(resolved.semantic_run_id)
        canonical = (
            self._publication_root
            / "runs"
            / resolved.semantic_run_id
            / "canonical-v2"
        )
        if os.path.lexists(canonical):
            cached_record = runner._execute_verified_locked(
                resolved_request=resolved,
                execution_case=execution_case,
                attempt=first_attempt,
                input_origin=input_origin,
                cancellation=cancellation,
            )
            cached = self._cache_ref(cached_record)
            if cached is not None:
                return cached
            self._raise_runner_storage_failure(cached_record)
            raise RuntimeError("canonical cache did not return a verified result")

        recovered = self._recover_attempt_graph(
            resolved,
            execution_case,
            input_origin,
        )
        first_state = recovered[0] if recovered else None
        second_state = recovered[1] if len(recovered) == 2 else None
        terminal = next(
            (
                value
                for value in reversed(recovered)
                if value.evidence.status
                in {
                    EvidencePublicationStatus.BLOCKED,
                    EvidencePublicationStatus.FAILED,
                    EvidencePublicationStatus.CANCELLED,
                }
            ),
            None,
        )
        if terminal is not None:
            return self._verified_terminal_ref(terminal.evidence)

        writer = self._attempt_writer()
        first_record: AttemptExecutionRecord | None = None
        first_evidence: FinalizedAttemptEvidence
        first_hash: AttemptExecutionHash | None = None
        if first_state is None:
            first_record = runner._execute_verified_locked(
                resolved_request=resolved,
                execution_case=execution_case,
                attempt=first_attempt,
                input_origin=input_origin,
                cancellation=cancellation,
            )
            cached = self._cache_ref(first_record)
            if cached is not None:
                return cached
            self._raise_runner_storage_failure(first_record)
            first_evidence = self._publish_attempt_locked(writer, first_record)
            if first_record.ready_to_finalize is None:
                return self._evidence_ref(first_evidence)
            first_hash = ExecutionResultHasher.bind(
                first_record.ready_to_finalize,
                first_evidence,
            )
        else:
            first_evidence = first_state.evidence

        if second_state is not None:
            if first_state is None:
                raise RuntimeError("Attempt graph has an ordinal gap")
            return self._publish_recovered_canonical_locked(
                resolved,
                execution_case,
                (first_state, second_state),
            )

        second_record = runner._retry_from_recovered_v3_locked(
            previous_attempt=first_evidence.attempt,
            resolved_request=resolved,
            execution_case=execution_case,
            input_origin=input_origin,
            market_data_preparation=market_data_preparation,
            cancellation=cancellation,
        )
        cached = self._cache_ref(second_record)
        if cached is not None:
            return cached
        self._raise_runner_storage_failure(second_record)
        second_evidence = self._publish_attempt_locked(writer, second_record)
        if second_record.ready_to_finalize is None:
            return self._evidence_ref(second_evidence)
        second_hash = ExecutionResultHasher.bind(
            second_record.ready_to_finalize,
            second_evidence,
        )
        if first_hash is None:
            if first_state is None or first_state.engine_payload is None:
                raise RuntimeError("Attempt graph READY evidence is incomplete")
            if canonical_bytes(first_state.engine_payload) != canonical_bytes(
                second_record.ready_to_finalize.engine_result
            ):
                raise RuntimeError("Attempt graph execution results are inconsistent")
            recovered_ready = ReadyToFinalizeAttempt(
                attempt=first_state.attempt,
                resolved_request=resolved,
                input_origin=input_origin,
                execution_case_hash=execution_case.case_hash,
                engine_result=second_record.ready_to_finalize.engine_result,
            )
            first_hash = ExecutionResultHasher.bind(
                recovered_ready,
                first_evidence,
            )
        return self._publish_canonical(
            resolved,
            execution_case,
            (first_hash, second_hash),
            (first_evidence, second_evidence),
            locked=True,
        )

    def _publish_attempt_locked(
        self,
        writer: AttemptEvidenceWriter,
        record: AttemptExecutionRecord,
    ) -> FinalizedAttemptEvidence:
        outcome = writer._publish_locked(record)
        if outcome.failure is not None:
            raise RuntimeError(
                "Attempt evidence publication failed: "
                f"{outcome.failure.code.value}"
            )
        if outcome.finalized is None:
            raise RuntimeError("Attempt evidence publication returned no result")
        self._mirror_evidence_graph(outcome.finalized)
        return outcome.finalized

    def _verified_terminal_ref(
        self,
        evidence: FinalizedAttemptEvidence,
    ) -> ArtifactRef:
        self._mirror_evidence_graph(evidence)
        ref = self._evidence_ref(evidence)
        terminal = BacktestEvidenceRepository(reader=self._artifact_reader).load_terminal(
            ref
        )
        if terminal.durable_evidence_ref != ref:
            raise RuntimeError("terminal evidence verification returned wrong ref")
        return ref

    def _publish_recovered_canonical_locked(
        self,
        resolved: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        recovered: tuple[_RecoveredAttemptState, _RecoveredAttemptState],
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        if any(value.engine_payload is None for value in recovered):
            raise RuntimeError("Attempt graph READY evidence is incomplete")
        first, second = recovered
        if first.engine_payload is None or second.engine_payload is None:
            raise RuntimeError("Attempt graph READY evidence is incomplete")
        publication = self._canonical_publisher()._publish_v2_recovered_locked(
            resolved_request=resolved,
            attempts=(
                (
                    first.attempt,
                    first.evidence,
                    first.engine_payload,
                    first.engine_content_hash,
                ),
                (
                    second.attempt,
                    second.evidence,
                    second.engine_payload,
                    second.engine_content_hash,
                ),
            ),
            engine_context=self._engine_context(resolved, execution_case),
        )
        if publication.failure is not None:
            raise RuntimeError(
                "canonical publication failed: "
                f"{publication.failure.code.value}"
            )
        relative = publication.relative_directory
        if relative is None:
            raise RuntimeError("canonical publication returned no result")
        ref = self._mirror_publication_graph(relative)
        return BacktestCanonicalPublicationRef.from_artifact_ref(ref)

    def _recover_attempt_graph(
        self,
        resolved: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        input_origin: InputOrigin,
    ) -> tuple[_RecoveredAttemptState, ...]:
        attempts_directory = (
            self._publication_root
            / "runs"
            / resolved.semantic_run_id
            / "attempts"
        )
        if not attempts_directory.exists():
            return ()
        if not attempts_directory.is_dir():
            raise RuntimeError("Attempt graph root is not a directory")
        first = AttemptIdentity.first(resolved.semantic_run_id)
        second = AttemptIdentity.retry(first, next_ordinal=2)
        expected = {
            first.attempt_id: first,
            second.attempt_id: second,
        }
        children = tuple(attempts_directory.iterdir())
        staging = attempts_directory / ".staging"
        if staging in children:
            if not staging.is_dir() or any(staging.iterdir()):
                raise RuntimeError("Attempt graph staging is inconsistent")
            children = tuple(value for value in children if value != staging)
        if any(not value.is_dir() or value.name not in expected for value in children):
            raise RuntimeError("Attempt graph contains an unexpected node")
        states = {
            value.name: self._recover_attempt_state(
                value,
                expected[value.name],
                resolved,
                execution_case,
                input_origin,
            )
            for value in children
        }
        if second.attempt_id in states and first.attempt_id not in states:
            raise RuntimeError("Attempt graph has an ordinal gap")
        ordered = tuple(
            states[value.attempt_id]
            for value in (first, second)
            if value.attempt_id in states
        )
        if ordered and ordered[0].evidence.status is not EvidencePublicationStatus.READY_FOR_INTEGRITY:
            if len(ordered) != 1:
                raise RuntimeError("Attempt graph continues after terminal Attempt")
        if len(ordered) == 2 and ordered[1].attempt.parent_attempt_id != ordered[0].attempt.attempt_id:
            raise RuntimeError("Attempt graph parent link mismatch")
        return ordered

    def _recover_attempt_state(
        self,
        directory: Path,
        attempt: AttemptIdentity,
        resolved: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        input_origin: InputOrigin,
    ) -> _RecoveredAttemptState:
        try:
            verify_read_only(directory)
            manifest_payload, _, manifest_source_hash = _read_canonical_artifact(
                directory / "evidence-manifest.json",
                "evidence_manifest",
            )
            artifact_values = manifest_payload["artifacts"]
            if type(artifact_values) is not tuple or not all(
                isinstance(value, Mapping) for value in artifact_values
            ):
                raise ValueError("Attempt manifest artifacts are invalid")
            entries = tuple(
                EvidenceArtifactEntry(
                    relative_path=self._manifest_relative_path(value["relative_path"]),
                    role=EvidenceArtifactRole(value["role"]),
                    artifact_type=self._manifest_text(
                        "artifact_type", value["artifact_type"]
                    ),
                    schema_version=self._manifest_int(
                        "schema_version", value["schema_version"], positive=True
                    ),
                    content_hash=self._canonical_hash(
                        "content_hash", value["content_hash"]
                    ),
                    source_hash=self._canonical_hash(
                        "source_hash", value["source_hash"]
                    ),
                    byte_count=self._manifest_int(
                        "byte_count", value["byte_count"], positive=True
                    ),
                )
                for value in artifact_values
            )
            status = EvidencePublicationStatus(manifest_payload["status"])
            terminal_outcome = manifest_payload["terminal_outcome"]
            deployment_authorized = manifest_payload["deployment_authorized"]
            if type(deployment_authorized) is not bool:
                raise ValueError("Attempt deployment flag is invalid")
            manifest = EvidenceManifest(
                semantic_run_id=self._manifest_text(
                    "semantic_run_id", manifest_payload["semantic_run_id"]
                ),
                attempt_id=self._manifest_text(
                    "attempt_id", manifest_payload["attempt_id"]
                ),
                status=status,
                terminal_outcome=(
                    None
                    if terminal_outcome is None
                    else BacktestRunOutcome(terminal_outcome)
                ),
                artifacts=entries,
                market_bundle_ref_hash=self._canonical_hash(
                    "market_bundle_ref_hash",
                    manifest_payload["market_bundle_ref_hash"],
                ),
                attempt_record_hash=self._canonical_hash(
                    "attempt_record_hash", manifest_payload["attempt_record_hash"]
                ),
                deployment_authorized=deployment_authorized,
            )
            if (
                manifest.semantic_run_id != resolved.semantic_run_id
                or manifest.attempt_id != attempt.attempt_id
                or manifest.manifest_hash != manifest_payload["manifest_hash"]
            ):
                raise ValueError("manifest identity mismatch")
            expected_files = {value.relative_path for value in entries} | {
                "evidence-manifest.json"
            }
            if {value.name for value in directory.iterdir()} != expected_files:
                raise ValueError("Attempt file coverage mismatch")
            payloads: dict[str, dict[str, object]] = {}
            for entry in entries:
                payload, envelope, source_hash = _read_canonical_artifact(
                    directory / entry.relative_path,
                    entry.artifact_type,
                )
                if (
                    envelope.schema_version != entry.schema_version
                    or envelope.content_hash != entry.content_hash
                    or source_hash != entry.source_hash
                    or len(canonical_bytes(envelope)) != entry.byte_count
                ):
                    raise ValueError("Attempt artifact binding mismatch")
                payloads[entry.relative_path] = payload
            record = payloads["attempt-execution-record.json"]
            branch_name = {
                EvidencePublicationStatus.READY_FOR_INTEGRITY: "ready_to_finalize",
                EvidencePublicationStatus.BLOCKED: "blocked_report",
                EvidencePublicationStatus.FAILED: "failed_report",
                EvidencePublicationStatus.CANCELLED: "cancelled_report",
            }[status]
            branch = record.get(branch_name)
            if not isinstance(branch, Mapping):
                raise ValueError("Attempt record branch mismatch")
            if (
                canonical_bytes(branch.get("attempt")) != canonical_bytes(attempt)
                or canonical_sha256(branch.get("resolved_request"))
                != canonical_sha256(resolved)
                or branch.get("input_origin") != input_origin.value
                or branch.get("execution_case_hash") != execution_case.case_hash
            ):
                raise ValueError("Attempt record context mismatch")
            expected_record_status = {
                EvidencePublicationStatus.READY_FOR_INTEGRITY: "READY_TO_FINALIZE",
                EvidencePublicationStatus.BLOCKED: "BLOCKED",
                EvidencePublicationStatus.FAILED: "FAILED",
                EvidencePublicationStatus.CANCELLED: "CANCELLED",
            }[status]
            if record.get("status") != expected_record_status:
                raise ValueError("Attempt record status mismatch")
            evidence = FinalizedAttemptEvidence(
                attempt=attempt,
                status=status,
                terminal_outcome=manifest.terminal_outcome,
                manifest=manifest,
                manifest_source_hash=manifest_source_hash,
                relative_directory=(
                    f"runs/{resolved.semantic_run_id}/attempts/{attempt.attempt_id}"
                ),
            )
            engine_payload = payloads.get("engine-execution-result.json")
            engine_entry = next(
                (
                    value
                    for value in entries
                    if value.role is EvidenceArtifactRole.ENGINE_EXECUTION_RESULT
                ),
                None,
            )
            if status is EvidencePublicationStatus.READY_FOR_INTEGRITY:
                if engine_payload is None or engine_entry is None:
                    raise ValueError("READY Attempt lacks Engine result")
                trace = engine_payload.get("trace")
                if (
                    engine_payload.get("case_hash") != execution_case.case_hash
                    or engine_payload.get("target_stream_digest")
                    != resolved.request.target_stream_digest
                    or not isinstance(trace, Mapping)
                    or canonical_bytes(branch.get("engine_result"))
                    != canonical_bytes(engine_payload)
                ):
                    raise ValueError("Engine result context mismatch")
            return _RecoveredAttemptState(
                attempt,
                evidence,
                record,
                engine_payload,
                engine_entry.content_hash if engine_entry is not None else None,
            )
        except (KeyError, OSError, TypeError, ValueError) as error:
            raise RuntimeError("Attempt graph verification failed") from error


    def _resolve(
        self,
        request: BacktestExecutionRequest,
        *,
        market_bundle_manifest,
        build_artifact_manifest,
    ):
        return ProfileResolver().resolve(
            request=request.request,
            registry=self._registry,
            market_bundle_manifest=market_bundle_manifest,
            build_artifact_manifest=build_artifact_manifest,
        )

    def _publish_resolution_failure(self, failure) -> ArtifactRef:
        envelope = ArtifactEnvelope.create(
            "backtest_resolution_failure",
            1,
            failure,
        )
        return self._put_verified(envelope)

    @staticmethod
    def _target_stream_v3(bundle, retained_reader, request):
        try:
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
            target_stream = PrecomputedTargetStream(
                bundle.target_stream_key, tuple(events)
            )
            if (
                target_stream.target_stream_digest
                != request.request.target_stream_digest
                or bundle.execution_case_semantic_spec.target_stream_digest
                != request.request.target_stream_digest
            ):
                raise ValueError("target digest mismatch")
            return target_stream
        except Exception:
            raise RuntimeError(
                "execution input hydration failed: target_binding_mismatch"
            ) from None

    @staticmethod
    def _raise_v3_hydration_failure(failure) -> NoReturn:
        code = (
            failure.code.value
            if type(failure) is _ExecutionInputsHydrationFailureV3
            else "execution_input_decode_failed"
        )
        raise RuntimeError(f"execution input hydration failed: {code}")

    def _hydrate(
        self,
        request: BacktestExecutionRequest,
        resolved_request: ResolvedBacktestRequest | None = None,
    ):
        outcome = _hydrate_execution_inputs(
            self._artifact_reader,
            request,
            market_reader=self._market_reader,
            resolved_request=resolved_request,
        )
        if outcome.failure is not None:
            raise RuntimeError(
                "execution input hydration failed: "
                f"{outcome.failure.code.value}: {outcome.failure.message}"
            )
        if outcome.result is None:
            raise RuntimeError("execution input hydration returned no result")
        return outcome.result

    def _existing_terminal_ref(
        self,
        resolved: ResolvedBacktestRequest,
    ) -> ArtifactRef | None:
        attempt = AttemptIdentity.first(resolved.semantic_run_id)
        attempt_directory = (
            self._publication_root
            / "runs"
            / resolved.semantic_run_id
            / "attempts"
            / attempt.attempt_id
        )
        if not attempt_directory.exists():
            return None
        manifest_path = attempt_directory / "evidence-manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError("terminal Attempt is incomplete")
        payload, envelope, _ = _read_canonical_artifact(
            manifest_path,
            "evidence_manifest",
        )
        if (
            payload.get("semantic_run_id") != resolved.semantic_run_id
            or payload.get("attempt_id") != attempt.attempt_id
        ):
            raise RuntimeError("terminal Attempt identity mismatch")
        status = payload.get("status")
        if status == "READY_FOR_INTEGRITY":
            return None
        if status not in {"BLOCKED", "FAILED", "CANCELLED"}:
            raise RuntimeError("Attempt evidence has unsupported terminal status")
        ref = ArtifactRef.from_envelope(envelope)
        terminal = BacktestEvidenceRepository(
            reader=self._artifact_reader
        ).load_terminal(ref)
        if terminal.durable_evidence_ref != ref:
            raise RuntimeError("terminal evidence verification returned wrong ref")
        return ref

    @staticmethod
    def _input_origin(resolved: ResolvedBacktestRequest) -> InputOrigin:
        return (
            InputOrigin.PRECOMPUTED_TARGET_STREAM
            if resolved.request.strategy_family.value == "precomputed_target"
            else InputOrigin.RUNTIME_STRATEGY
        )

    @staticmethod
    def _raise_runner_storage_failure(record: AttemptExecutionRecord) -> None:
        report = record.failed_report
        if (
            report is not None
            and report.issue.source is AttemptIssueSource.RUNNER_CONTRACT
            and report.issue.code in _STORAGE_RUNNER_ISSUES
        ):
            raise RuntimeError(f"Backtest storage failed: {report.issue.code}")

    def _publish_attempt(
        self,
        writer: AttemptEvidenceWriter,
        record: AttemptExecutionRecord,
    ) -> FinalizedAttemptEvidence:
        outcome = writer.publish(record)
        if outcome.failure is not None:
            raise RuntimeError(
                "Attempt evidence publication failed: "
                f"{outcome.failure.code.value}"
            )
        if outcome.finalized is None:
            raise RuntimeError("Attempt evidence publication returned no result")
        self._mirror_evidence_graph(outcome.finalized)
        return outcome.finalized

    @staticmethod
    def _evidence_ref(evidence: FinalizedAttemptEvidence) -> ArtifactRef:
        return ArtifactRef.from_envelope(
            ArtifactEnvelope.create("evidence_manifest", 1, evidence.manifest)
        )

    def _cache_ref(
        self, record: AttemptExecutionRecord
    ) -> BacktestCanonicalPublicationRef | None:
        cache_hit = record.cache_hit
        if cache_hit is None:
            return None
        self._mirror_cached_attempt_evidence(cache_hit)
        ref = self._mirror_publication_graph(cache_hit.relative_directory)
        return BacktestCanonicalPublicationRef.from_artifact_ref(ref)

    def _publish_canonical(
        self,
        resolved: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt_hashes: tuple[AttemptExecutionHash, AttemptExecutionHash],
        evidence: tuple[FinalizedAttemptEvidence, FinalizedAttemptEvidence],
        *,
        locked: bool = False,
    ) -> BacktestCanonicalPublicationRef | ArtifactRef:
        canonical = attempt_hashes[0]
        result = canonical.engine_result
        rebuild = DeterministicRebuildEvidence(
            semantic_run_id=resolved.semantic_run_id,
            request_hash=canonical_sha256(resolved.request),
            environment_hash=resolved.environment.environment_hash,
            build_artifact_manifest_hash=resolved.build_artifact_manifest.manifest_hash,
            market_bundle_manifest_hash=resolved.environment.market_bundle_ref.manifest_hash,
            market_bundle_retention_proof_hash=None,
            target_stream_digest=resolved.request.target_stream_digest,
            execution_case_semantic_hash=resolved.request.execution_case_semantic_hash,
            execution_case_hash=result.case_hash,
            trace_hash=result.trace.trace_hash,
            trace_level=IntegrityTraceLevel.FULL_TRACE,
            execution_result_hash=canonical.execution_result_hash,
            deterministic_rebuild_proof_hash=None,
        )
        engine_context = self._engine_context(resolved, execution_case)
        publisher = self._canonical_publisher()
        if locked:
            publication = publisher._publish_v2_locked(
                resolved,
                attempt_hashes,
                evidence,
                rebuild,
                engine_context,
            )
        else:
            publication = publisher.publish_v2(
                resolved_request=resolved,
                attempt_hashes=attempt_hashes,
                finalized_attempts=evidence,
                rebuild_evidence=rebuild,
                engine_context=engine_context,
            )
        if publication.failure is not None:
            raise RuntimeError(
                "canonical publication failed: "
                f"{publication.failure.code.value}"
            )
        finalized = publication.finalized_result_v2 or publication.finalized_evaluation
        if finalized is None:
            raise RuntimeError("canonical publication returned no result")
        ref = self._mirror_publication_graph(finalized.relative_directory)
        if publication.finalized_result_v2 is not None:
            return BacktestCanonicalPublicationRef.from_artifact_ref(ref)
        return ref

    def _attempt_writer(self) -> AttemptEvidenceWriter:
        return AttemptEvidenceWriter(root=self._publication_root)

    def _canonical_publisher(self) -> CanonicalResultPublisher:
        return CanonicalResultPublisher(root=self._publication_root)

    @staticmethod
    def _engine_context(
        resolved: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
    ) -> EngineExecutionContext:
        if execution_case.identity_manifest is None:
            raise RuntimeError("execution_case is missing identity_manifest")
        return EngineExecutionContext(
            semantic_run_id=resolved.semantic_run_id,
            semantic_spec_hash=execution_case.semantic_spec_hash,
            case_hash=execution_case.case_hash,
            target_stream_digest=execution_case.target_stream.target_stream_digest,
            identity_manifest_hash=execution_case.identity_manifest.manifest_hash,
            financial_state=execution_case.financial_state,
        )

    def _mirror_evidence_graph(self, evidence: FinalizedAttemptEvidence) -> None:
        ref = self._mirror_manifest_graph(
            relative_directory=evidence.relative_directory,
            manifest_name="evidence-manifest.json",
            manifest_type="evidence_manifest",
        )
        if ref != self._evidence_ref(evidence):
            raise ValueError("publisher-visible evidence ref does not bind manifest")

    def _mirror_cached_attempt_evidence(
        self,
        cache_hit: CanonicalResultCacheHit,
    ) -> None:
        canonical_directory = self._publication_root / cache_hit.relative_directory
        reference_payload, _, _ = _read_canonical_artifact(
            canonical_directory / "canonical-attempt-ref.json",
            "canonical_attempt_ref",
        )
        if canonical_sha256(reference_payload) != cache_hit.canonical_attempt_ref_hash:
            raise ValueError("canonical Attempt ref does not match verified cache hit")
        attempt = cache_hit.canonical_attempt
        self._mirror_manifest_graph(
            relative_directory=(
                f"runs/{attempt.semantic_run_id}/attempts/{attempt.attempt_id}"
            ),
            manifest_name="evidence-manifest.json",
            manifest_type="evidence_manifest",
            expected_manifest_hash=self._canonical_hash(
                "evidence_manifest_hash",
                reference_payload.get("evidence_manifest_hash"),
            ),
            expected_manifest_source_hash=self._canonical_hash(
                "evidence_manifest_source_hash",
                reference_payload.get("evidence_manifest_source_hash"),
            ),
        )

    def _mirror_publication_graph(self, relative_directory: str) -> ArtifactRef:
        return self._mirror_manifest_graph(
            relative_directory=relative_directory,
            manifest_name="publication-manifest.json",
            manifest_type="canonical_publication_manifest",
        )

    def _mirror_manifest_graph(
        self,
        *,
        relative_directory: str,
        manifest_name: str,
        manifest_type: str,
        expected_manifest_hash: str | None = None,
        expected_manifest_source_hash: str | None = None,
    ) -> ArtifactRef:
        directory = self._publication_root / relative_directory
        manifest_payload, manifest_envelope, manifest_source_hash = (
            _read_canonical_artifact(
                directory / manifest_name,
                manifest_type,
            )
        )
        if (
            expected_manifest_hash is not None
            and manifest_payload.get("manifest_hash") != expected_manifest_hash
        ):
            raise ValueError(
                "evidence manifest hash does not match canonical Attempt ref"
            )
        if (
            expected_manifest_source_hash is not None
            and manifest_source_hash != expected_manifest_source_hash
        ):
            raise ValueError(
                "evidence manifest source hash does not match canonical Attempt ref"
            )
        directory_root = directory.resolve(strict=True)
        for entry in self._manifest_artifacts(manifest_payload):
            relative_path = self._manifest_relative_path(entry["relative_path"])
            artifact_type = self._manifest_text(
                "artifact_type", entry["artifact_type"]
            )
            child_path = self._contained_manifest_child(
                directory,
                directory_root,
                relative_path,
            )
            _, envelope, source_hash = _read_canonical_artifact(
                child_path,
                artifact_type,
            )
            if (
                envelope.schema_version != entry["schema_version"]
                or envelope.content_hash != entry["content_hash"]
                or source_hash != entry["source_hash"]
                or len(canonical_bytes(envelope)) != entry["byte_count"]
            ):
                raise ValueError("artifact source does not match manifest entry")
            self._put_verified(envelope)
        return self._put_verified(manifest_envelope)

    @classmethod
    def _manifest_artifacts(
        cls,
        manifest_payload: dict[str, object],
    ) -> tuple[dict[str, object], ...]:
        artifacts = manifest_payload.get("artifacts")
        if type(artifacts) is not tuple:
            raise ValueError("manifest artifacts must be canonical tuple")
        entries: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        for value in artifacts:
            if not isinstance(value, Mapping):
                raise ValueError("manifest artifact entry must be canonical mapping")
            if not _MANIFEST_ENTRY_KEYS.issubset(value.keys()):
                raise ValueError("manifest artifact entry is incomplete")
            relative_path = cls._manifest_relative_path(value["relative_path"])
            if relative_path in seen_paths:
                raise ValueError("manifest artifact paths must be unique")
            seen_paths.add(relative_path)
            artifact_type = cls._manifest_text("artifact_type", value["artifact_type"])
            schema_version = cls._manifest_int(
                "schema_version",
                value["schema_version"],
                positive=True,
            )
            content_hash = cls._canonical_hash("content_hash", value["content_hash"])
            source_hash = cls._canonical_hash("source_hash", value["source_hash"])
            byte_count = cls._manifest_int(
                "byte_count",
                value["byte_count"],
                positive=True,
            )
            try:
                ArtifactRef(artifact_type, schema_version, content_hash)
            except (TypeError, ValueError) as error:
                raise ValueError("manifest artifact ref is invalid") from error
            entries.append(
                {
                    "relative_path": relative_path,
                    "artifact_type": artifact_type,
                    "schema_version": schema_version,
                    "content_hash": content_hash,
                    "source_hash": source_hash,
                    "byte_count": byte_count,
                }
            )
        return tuple(entries)

    @staticmethod
    def _manifest_text(name: str, value: object) -> str:
        if type(value) is not str:
            raise ValueError(f"manifest {name} must be str")
        return value

    @classmethod
    def _manifest_relative_path(cls, value: object) -> str:
        text = cls._manifest_text("relative_path", value)
        path = PurePosixPath(text)
        if (
            not text
            or text == "."
            or "\\" in text
            or path.is_absolute()
            or path.as_posix() != text
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError(
                "manifest relative_path must be normalized relative POSIX path"
            )
        return text

    @staticmethod
    def _manifest_int(name: str, value: object, *, positive: bool) -> int:
        if type(value) is not int:
            raise ValueError(f"manifest {name} must be int")
        if positive and value <= 0:
            raise ValueError(f"manifest {name} must be positive")
        if not positive and value < 0:
            raise ValueError(f"manifest {name} must be nonnegative")
        return value

    @staticmethod
    def _canonical_hash(name: str, value: object) -> str:
        if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError(f"manifest {name} must be canonical sha256")
        return value

    @staticmethod
    def _contained_manifest_child(
        directory: Path,
        directory_root: Path,
        relative_path: str,
    ) -> Path:
        path = directory / relative_path
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise ValueError("manifest artifact path is not resolvable") from error
        if not resolved.is_relative_to(directory_root):
            raise ValueError("manifest artifact path escapes publication directory")
        return path

    def _put_verified(self, envelope: ArtifactEnvelope) -> ArtifactRef:
        expected_ref = ArtifactRef.from_envelope(envelope)
        stored_ref = self._artifact_publisher.put(envelope=envelope)
        if type(stored_ref) is not ArtifactRef:
            raise TypeError("publisher.put must return exact ArtifactRef")
        if stored_ref != expected_ref:
            raise ValueError("publisher.put returned ref does not bind envelope")
        return stored_ref


__all__ = ["BacktestRuntime"]
