from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from crypto_quant_backtest import (
    AttemptEvidenceWriter,
    AttemptIdentity,
    BacktestCanonicalPublicationRef,
    BacktestEvidenceRepository,
    BacktestRuntime,
    EngineExecutionOutcome,
    EngineFailure,
    EngineFailureCode,
    ExecutionTrace,
    TerminalStatus,
)
from crypto_quant_backtest.composition import (
    ExecutionCaseComposer,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
    _compose_execution_case_v3,
    _execution_case_semantic_spec_v3,
)
from crypto_quant_backtest.engine import ExecutionCaseIdentityFactory
from crypto_quant_backtest.execution_inputs import (
    BacktestExecutionRequest,
    _hydrate_execution_inputs_v3,
    _materialize_execution_input_bundle_v3,
)
from crypto_quant_backtest.multi_resolution_preparation import (
    MultiResolutionMarketDataPreparation,
)
from crypto_quant_backtest.resolution import ProfileResolver
from crypto_quant_backtest.run_end import MarkToMarketCloseoutPolicy
import crypto_quant_backtest.runner as runner_module
from crypto_quant_backtest.runner import AuditableBacktestRunner
from crypto_quant_backtest.timeline import DeterministicTimeline
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactNotFoundError,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.runtime.execution_inputs.test_multi_resolution_bundle_v3 import _contract
from tests.runtime.resolution._fixtures import profile_registry


class _ArtifactStore:
    def __init__(self, envelope: ArtifactEnvelope) -> None:
        self._input = envelope
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}
        self.reads = 0
        self.puts = 0

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        self.reads += 1
        if ref == ArtifactRef.from_envelope(self._input):
            envelope = self._input
            source = canonical_bytes(envelope)
            return ArtifactReadResult(
                envelope=envelope,
                artifact=object(),
                source_bytes=source,
                source_hash=canonical_sha256(envelope),
            )
        try:
            return self.values[ref]
        except KeyError as error:
            raise ArtifactNotFoundError(ref.content_hash) from error

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        self.puts += 1
        ref = ArtifactRef.from_envelope(envelope)
        source = canonical_bytes(envelope)
        self.values[ref] = ArtifactReadResult(
            envelope=envelope,
            artifact=object(),
            source_bytes=source,
            source_hash=canonical_sha256(envelope),
        )
        return ref


def _registry(prepared):
    return profile_registry(
        extra_market_capabilities=tuple(
            capability
            for capability in prepared.verified_reader.manifest.capabilities
            if capability.key == "price_bars"
        )
    )


def _executable_contract():
    prepared, resolved, hydrated, _, _ = _contract()
    timeline = DeterministicTimeline.open(
        reader=prepared.verified_reader,
        stream_keys=hydrated.timeline_stream_keys,
        window=resolved.request.timeline_window,
    )
    assert type(timeline) is DeterministicTimeline
    base_spec = replace(
        hydrated.execution_case_semantic_spec,
        timeline_semantic_hash=ExecutionCaseComposer.timeline_semantic_hash(timeline),
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=base_spec,
        execution_case_plan=hydrated.execution_case_plan,
        market_data_preparation=prepared.preparation,
    )
    request = replace(
        resolved.request,
        execution_case_semantic_hash=spec.semantic_spec_hash,
    )
    outcome = ProfileResolver().resolve(
        request=request,
        registry=_registry(prepared),
        market_bundle_manifest=prepared.verified_reader.manifest,
        build_artifact_manifest=resolved.build_artifact_manifest,
    )
    assert outcome.resolved is not None
    resolved = outcome.resolved
    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=resolved.semantic_run_id,
        namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    rebuilt = SyntheticExecutionCaseBuilder().build(
        identities,
        spec.semantic_spec_hash,
    )
    assert type(rebuilt.closeout_policy) is MarkToMarketCloseoutPolicy
    plan = _ExecutionCasePlan(
        rebuilt.decision_cycles,
        rebuilt.bar_executions,
        rebuilt.financial_state,
        rebuilt.financial_dispatch_plan,
        rebuilt.execution_model,
        hydrated.execution_case_plan.snapshot_plan,
        rebuilt.closeout_policy,
    )
    assert _execution_case_semantic_spec_v3(
        base_spec=spec,
        execution_case_plan=plan,
        market_data_preparation=prepared.preparation,
    ) == spec
    hydrated = replace(
        hydrated,
        execution_case_semantic_spec=spec,
        execution_case_plan=plan,
    )
    envelope = _materialize_execution_input_bundle_v3(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    transport = BacktestExecutionRequest(
        3,
        resolved.request,
        ArtifactRef.from_envelope(envelope),
    )
    return prepared, resolved, hydrated, envelope, transport


def _runtime(tmp_path: Path, envelope: ArtifactEnvelope, prepared):
    store = _ArtifactStore(envelope)
    runtime = BacktestRuntime(
        registry=_registry(prepared),
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=prepared.verified_reader,
        publication_root=tmp_path,
    )
    return runtime, store


def test_v3_runtime_is_one_read_one_resolve_and_reuses_one_retained_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    runtime, store = _runtime(tmp_path, envelope, prepared)
    calls = {"resolve": 0, "timeline": 0, "shared": 0, "engine": 0}
    timeline_readers: list[object] = []
    original_resolve = ProfileResolver.resolve
    original_open = DeterministicTimeline.open
    original_shared = AuditableBacktestRunner._execute_verified_locked
    original_engine = AuditableBacktestRunner._execute_engine

    def resolve(self, **kwargs):
        calls["resolve"] += 1
        assert store.reads == 1
        return original_resolve(self, **kwargs)

    def open_timeline(*, reader, stream_keys, window):
        calls["timeline"] += 1
        assert store.reads == 1
        assert calls["resolve"] == 1
        timeline_readers.append(reader)
        return original_open(reader=reader, stream_keys=stream_keys, window=window)

    def execute_shared(self, *args, **kwargs):
        calls["shared"] += 1
        assert calls["timeline"] == 1
        return original_shared(self, *args, **kwargs)

    def execute_engine(self, *args, **kwargs):
        calls["engine"] += 1
        return original_engine(self, *args, **kwargs)

    monkeypatch.setattr(ProfileResolver, "resolve", resolve)
    monkeypatch.setattr(DeterministicTimeline, "open", open_timeline)
    monkeypatch.setattr(AuditableBacktestRunner, "_execute_verified_locked", execute_shared)
    monkeypatch.setattr(AuditableBacktestRunner, "_execute_engine", execute_engine)

    result = runtime.run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    assert store.reads == 1
    assert calls == {"resolve": 1, "timeline": 1, "shared": 2, "engine": 2}
    assert len(timeline_readers) == 1
    assert timeline_readers[0] is not prepared.verified_reader
    completed = BacktestEvidenceRepository(store).load_completed(result)
    assert completed.semantic_run_id == resolved.semantic_run_id
    attempt_requests = tuple(
        (tmp_path / "runs" / resolved.semantic_run_id / "attempts").glob("*/request.json")
    )
    assert len(attempt_requests) == 2


def test_v3_cache_hit_still_finishes_replay_before_cache_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    runtime, store = _runtime(tmp_path, envelope, prepared)
    first = runtime.run(transport)
    shared_calls = 0
    cache_calls = 0
    original_shared = AuditableBacktestRunner._execute_verified_locked
    original_cache = runner_module._read_canonical_cache_hit_v2

    def execute_shared(self, *args, **kwargs):
        nonlocal shared_calls
        shared_calls += 1
        return original_shared(self, *args, **kwargs)

    def read_cache(**kwargs):
        nonlocal cache_calls
        cache_calls += 1
        return original_cache(**kwargs)

    monkeypatch.setattr(AuditableBacktestRunner, "_execute_verified_locked", execute_shared)
    monkeypatch.setattr(runner_module, "_read_canonical_cache_hit_v2", read_cache)
    second = runtime.run(transport)

    assert second == first
    assert store.reads > 2  # input reads plus mandatory repository cache replay
    assert shared_calls == 1
    assert cache_calls == 1


def test_v3_structural_failure_leaves_no_timeline_attempt_cache_or_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    payload = json.loads(canonical_bytes(envelope).decode())["payload"]
    payload["market_data_preparation"]["bindings"]["execution_bindings"][0][
        "stream_key"
    ] = "SECRET-provider-token-/private/path"
    malformed = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)
    transport = replace(
        transport,
        execution_input_bundle_ref=ArtifactRef.from_envelope(malformed),
    )
    runtime, store = _runtime(tmp_path, malformed, prepared)
    calls = {"timeline": 0, "shared": 0, "attempt": 0, "evidence": 0, "cache": 0}

    def forbidden_timeline(**kwargs):
        calls["timeline"] += 1
        raise AssertionError("Timeline must not open")

    def forbidden_shared(*args, **kwargs):
        calls["shared"] += 1
        raise AssertionError("cache/Attempt/Engine path must not start")

    def forbidden_attempt(*args, **kwargs):
        calls["attempt"] += 1
        raise AssertionError("Attempt must not be created")

    def forbidden_evidence(*args, **kwargs):
        calls["evidence"] += 1
        raise AssertionError("evidence must not be written")

    def forbidden_cache(**kwargs):
        calls["cache"] += 1
        raise AssertionError("cache must not be read")

    monkeypatch.setattr(DeterministicTimeline, "open", forbidden_timeline)
    monkeypatch.setattr(AuditableBacktestRunner, "_execute_verified_locked", forbidden_shared)
    monkeypatch.setattr(AttemptIdentity, "first", staticmethod(forbidden_attempt))
    monkeypatch.setattr(AttemptEvidenceWriter, "publish", forbidden_evidence)
    monkeypatch.setattr(runner_module, "_read_canonical_cache_hit_v2", forbidden_cache)

    with pytest.raises(RuntimeError) as raised:
        runtime.run(transport)

    assert "SECRET" not in str(raised.value)
    assert calls == {
        "timeline": 0,
        "shared": 0,
        "attempt": 0,
        "evidence": 0,
        "cache": 0,
    }
    assert store.puts == 0
    assert not (tmp_path / "runs").exists()


def test_runner_v3_contract_recomputes_role_spec_before_shared_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    hydrated = _hydrate_execution_inputs_v3(
        _ArtifactStore(envelope),
        transport,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
    )
    assert hydrated.result is not None
    values = hydrated.result
    case = _compose_execution_case_v3(
        resolved_request=resolved,
        market_reader=prepared.verified_reader,
        hydrated_inputs=_HydratedExecutionCaseInputs(
            values.execution_case_semantic_spec,
            values.timeline_stream_keys,
            values.target_stream,
            values.timeline_batch_size,
            values.execution_case_plan,
        ),
        market_data_preparation=values.market_data_preparation,
    )
    runner = AuditableBacktestRunner.for_v2(publication_root=tmp_path)
    runner._verify_v3_contract(
        resolved_request=resolved,
        execution_case=case,
        input_origin=runner._expected_input_origin(resolved),
        market_data_preparation=prepared.preparation,
    )

    changed = MultiResolutionMarketDataPreparation(
        prepared.preparation.decision_schedule,
        prepared.preparation.bindings,
        (
            replace(
                prepared.preparation.signal_lineages[0],
                observation_key="changed",
            ),
        ),
    )
    with pytest.raises(RuntimeError, match="execution case semantic spec mismatch"):
        runner._verify_v3_contract(
            resolved_request=resolved,
            execution_case=case,
            input_origin=runner._expected_input_origin(resolved),
            market_data_preparation=changed,
        )


def test_v3_transport_and_provider_failures_are_secret_safe_and_atomic(
    tmp_path: Path,
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    runtime, store = _runtime(tmp_path / "wrong-ref", envelope, prepared)
    forged = object.__new__(BacktestExecutionRequest)
    object.__setattr__(forged, "schema_version", 3)
    object.__setattr__(forged, "request", resolved.request)
    object.__setattr__(
        forged,
        "execution_input_bundle_ref",
        ArtifactRef("evidence_manifest", 3, "sha256:" + "0" * 64),
    )

    with pytest.raises(RuntimeError, match="wrong_execution_input_bundle_ref"):
        runtime.run(forged)

    assert store.reads == 0
    assert store.puts == 0
    assert not (tmp_path / "wrong-ref" / "runs").exists()

    secret = "SECRET-provider-token-/private/path"

    class _FailingStore(_ArtifactStore):
        def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
            self.reads += 1
            raise OSError(secret)

    failing_store = _FailingStore(envelope)
    failing_runtime = BacktestRuntime(
        registry=_registry(prepared),
        artifact_reader=failing_store,
        artifact_publisher=failing_store,
        market_reader=prepared.verified_reader,
        publication_root=tmp_path / "provider",
    )
    with pytest.raises(RuntimeError, match="execution_input_unavailable") as raised:
        failing_runtime.run(transport)

    assert secret not in str(raised.value)
    assert failing_store.reads == 1
    assert failing_store.puts == 0
    assert not (tmp_path / "provider" / "runs").exists()


def test_v3_blocked_terminal_closes_as_repository_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    runtime, store = _runtime(tmp_path, envelope, prepared)

    class _BlockingEngine:
        calls = 0

        def run(self, case, *, cancellation=None):
            self.calls += 1
            evidence_hash = canonical_sha256({"type": "blocked-v3-test"})
            return EngineExecutionOutcome(
                engine_failure=EngineFailure(
                    code=EngineFailureCode.TIMELINE_FAILURE,
                    case_hash=case.case_hash,
                    trace_hash=ExecutionTrace().trace_hash,
                    subject_keys=("timeline",),
                    evidence_hashes=(evidence_hash,),
                )
            )

    engine = _BlockingEngine()

    def for_v2(cls, *, publication_root):
        return cls(
            engine=engine,
            publication_root=publication_root,
            canonical_publication_version=2,
        )

    monkeypatch.setattr(AuditableBacktestRunner, "for_v2", classmethod(for_v2))

    result = runtime.run(transport)

    assert type(result) is ArtifactRef
    assert result.artifact_type == "evidence_manifest"
    assert engine.calls == 1
    terminal = BacktestEvidenceRepository(store).load_terminal(result)
    assert terminal.status is TerminalStatus.BLOCKED
    assert terminal.durable_evidence_ref == result
