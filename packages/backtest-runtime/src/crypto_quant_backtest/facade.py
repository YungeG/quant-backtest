"""Public Backtest execution facade."""

from __future__ import annotations

from collections.abc import Mapping
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

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .composition import _HydratedExecutionCaseInputs, _compose_execution_case_v3
from .engine import EngineCancellationRequest, ResolvedExecutionCase
from .evidence import AttemptEvidenceWriter, FinalizedAttemptEvidence
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
    CanonicalResultCacheHit,
    InputOrigin,
    _read_canonical_artifact,
    _read_canonical_cache_hit_v2,
)

_STORAGE_RUNNER_ISSUES = frozenset({"canonical_cache_invalid", "run_lock_unavailable"})
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
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
        if type(request) is BacktestExecutionRequest and request.schema_version == 3:
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
        retained_reader = _capture_market_bundle_reader_v1(
            request.request.market_bundle_ref,
            self._market_reader,
        )
        if retained_reader is None:
            raise RuntimeError(
                "execution input hydration failed: prepared_market_data_replay_mismatch"
            )
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

        target_stream = self._target_stream_v3(bundle, retained_reader)
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

        writer = AttemptEvidenceWriter(root=self._publication_root)
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
    def _target_stream_v3(bundle, retained_reader):
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
            return PrecomputedTargetStream(bundle.target_stream_key, tuple(events))
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
        if execution_case.identity_manifest is None:
            raise RuntimeError("execution_case is missing identity_manifest")
        engine_context = EngineExecutionContext(
            semantic_run_id=resolved.semantic_run_id,
            semantic_spec_hash=execution_case.semantic_spec_hash,
            case_hash=execution_case.case_hash,
            target_stream_digest=execution_case.target_stream.target_stream_digest,
            identity_manifest_hash=execution_case.identity_manifest.manifest_hash,
            financial_state=execution_case.financial_state,
        )
        publication = CanonicalResultPublisher(root=self._publication_root).publish_v2(
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
            child_path = self._contained_manifest_child(
                directory,
                directory_root,
                entry["relative_path"],
            )
            _, envelope, source_hash = _read_canonical_artifact(
                child_path,
                entry["artifact_type"],
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
