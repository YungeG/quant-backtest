from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from crypto_quant_backtest import (
    BacktestCanonicalPublicationRef,
    BacktestEvidenceRepository,
    BacktestRuntime,
)
from crypto_quant_backtest.composition import (
    ExecutionCaseComposer,
    _HydratedExecutionCaseInputs,
    _compose_execution_case_v3,
    _execution_case_semantic_spec_v3,
)
from crypto_quant_backtest.execution_inputs import (
    BacktestExecutionRequest,
    _hydrate_execution_inputs_v3,
    _materialize_execution_input_bundle_v3,
)
from crypto_quant_backtest.multi_resolution_preparation import (
    MultiResolutionMarketDataPreparation,
)
from crypto_quant_backtest.resolution import ProfileResolver
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
    hydrated = replace(hydrated, execution_case_semantic_spec=spec)
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
    calls = {"resolve": 0, "timeline": 0, "shared": 0}
    timeline_readers: list[object] = []
    original_resolve = ProfileResolver.resolve
    original_open = DeterministicTimeline.open
    original_shared = AuditableBacktestRunner._execute_verified

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

    monkeypatch.setattr(ProfileResolver, "resolve", resolve)
    monkeypatch.setattr(DeterministicTimeline, "open", open_timeline)
    monkeypatch.setattr(AuditableBacktestRunner, "_execute_verified", execute_shared)

    result = runtime.run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    assert store.reads == 1
    assert calls == {"resolve": 1, "timeline": 1, "shared": 2}
    assert len(timeline_readers) == 1
    assert timeline_readers[0] is not prepared.verified_reader
    completed = BacktestEvidenceRepository(store).load_completed(result)
    assert completed.semantic_run_id == resolved.semantic_run_id


def test_v3_cache_hit_still_finishes_replay_before_cache_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    runtime, store = _runtime(tmp_path, envelope, prepared)
    first = runtime.run(transport)
    shared_calls = 0
    original_shared = AuditableBacktestRunner._execute_verified

    def execute_shared(self, *args, **kwargs):
        nonlocal shared_calls
        shared_calls += 1
        return original_shared(self, *args, **kwargs)

    monkeypatch.setattr(AuditableBacktestRunner, "_execute_verified", execute_shared)
    second = runtime.run(transport)

    assert second == first
    assert store.reads == 2
    assert shared_calls == 1


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
    calls = {"timeline": 0, "shared": 0}

    def forbidden_timeline(**kwargs):
        calls["timeline"] += 1
        raise AssertionError("Timeline must not open")

    def forbidden_shared(*args, **kwargs):
        calls["shared"] += 1
        raise AssertionError("cache/Attempt/Engine path must not start")

    monkeypatch.setattr(DeterministicTimeline, "open", forbidden_timeline)
    monkeypatch.setattr(AuditableBacktestRunner, "_execute_verified", forbidden_shared)

    with pytest.raises(RuntimeError) as raised:
        runtime.run(transport)

    assert "SECRET" not in str(raised.value)
    assert calls == {"timeline": 0, "shared": 0}
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
