from __future__ import annotations

from dataclasses import replace
from enum import Enum
import json
from pathlib import Path

import pytest

from crypto_quant_backtest import (
    BacktestCanonicalPublicationRef,
    BacktestEvidenceRepository,
    BacktestExecutionRequest,
    BacktestProfileRegistry,
    BacktestRuntime,
    AttemptEvidenceWriter,
    AttemptIdentity,
    DeterministicBarEngine,
    EngineCancellation,
    EngineCancellationRequest,
    EngineExecutionOutcome,
    EngineFailure,
    EngineFailureCode,
    ExecutionTrace,
    TerminalStatus,
)
from crypto_quant_backtest.performance_observations import BoundedPerformanceRecorder
from crypto_quant_backtest.multi_resolution_preparation import (
    _capture_market_bundle_reader_v1,
)
from crypto_quant_backtest.resolution import ProfileResolver
from crypto_quant_backtest.runner import AuditableBacktestRunner
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader
from tests.runtime.test_prep_runtime_fanin import (
    _ArtifactStore,
    _executable_contract,
    _registry,
)


class _FatalReader:
    def __init__(self, source: InMemoryMarketBundleReader, fatal: BaseException) -> None:
        self.bundle_ref = source.bundle_ref
        self.manifest = source.manifest
        self._fatal = fatal

    def validate_requirements(
        self, *, required_capabilities=(), required_streams=()
    ):
        raise self._fatal

    def open_cursor(self, stream_key, *, batch_size):
        raise self._fatal

    def read_batch(self, cursor):
        raise self._fatal

    def resume(self, cursor, *, batch_size):
        raise self._fatal

    def resume_cursor(self, cursor, *, batch_size=None):
        raise self._fatal


class _SequenceEngine:
    def __init__(self, branches: tuple[str, ...], cancellation=None) -> None:
        self.branches = branches
        self.cancellation = cancellation
        self.calls = 0

    def run(self, case, *, cancellation=None):
        branch = self.branches[self.calls]
        self.calls += 1
        if branch == "ready":
            return DeterministicBarEngine().run(case)
        if branch == "cancelled":
            assert self.cancellation is not None
            return EngineExecutionOutcome(
                cancellation=EngineCancellation(
                    case_hash=case.case_hash,
                    request=self.cancellation,
                    processed_timeline_events=1,
                    trace_hash=ExecutionTrace().trace_hash,
                )
            )
        code = (
            EngineFailureCode.TIMELINE_FAILURE
            if branch == "blocked"
            else EngineFailureCode.ACCOUNTING_FAILURE
        )
        return EngineExecutionOutcome(
            engine_failure=EngineFailure(
                code=code,
                case_hash=case.case_hash,
                trace_hash=ExecutionTrace().trace_hash,
                subject_keys=(branch,),
                evidence_hashes=(canonical_sha256({"branch": branch}),),
            )
        )


def _install_engine(monkeypatch: pytest.MonkeyPatch, engine) -> None:
    def for_v2(cls, *, publication_root):
        return cls(
            engine=engine,
            publication_root=publication_root,
            canonical_publication_version=2,
        )

    monkeypatch.setattr(AuditableBacktestRunner, "for_v2", classmethod(for_v2))


def _runtime(
    root: Path,
    store: _ArtifactStore,
    prepared,
    *,
    registry=None,
    market_reader=None,
) -> BacktestRuntime:
    return BacktestRuntime(
        registry=_registry(prepared) if registry is None else registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=(
            prepared.verified_reader if market_reader is None else market_reader
        ),
        publication_root=root,
    )


def _mutated_transport(envelope, transport, mutator):
    payload = json.loads(canonical_bytes(envelope).decode())["payload"]
    mutator(payload)
    changed = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)
    return changed, replace(
        transport,
        execution_input_bundle_ref=ArtifactRef.from_envelope(changed),
    )


def test_v3_build_binding_precedes_reader_resolution_and_all_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    changed_build = replace(
        resolved.build_artifact_manifest,
        dependency_lock_hash="sha256:" + "0" * 64,
    )
    payload = dict(envelope.payload)
    payload["build_artifact_manifest"] = changed_build
    changed = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)
    changed_transport = replace(
        transport, execution_input_bundle_ref=ArtifactRef.from_envelope(changed)
    )
    store = _ArtifactStore(changed)
    fatal = AssertionError("Reader must not be touched")
    reader = _FatalReader(prepared.verified_reader, fatal)
    calls = {"resolve": 0, "publish": 0, "timeline": 0, "engine": 0}

    def forbidden(*args, **kwargs):
        raise AssertionError("post-validation side effect")

    def resolve(*args, **kwargs):
        calls["resolve"] += 1
        return forbidden()

    monkeypatch.setattr(ProfileResolver, "resolve", resolve)
    monkeypatch.setattr(BacktestRuntime, "_publish_resolution_failure", forbidden)
    monkeypatch.setattr(BacktestRuntime, "_execute_case", forbidden)

    with pytest.raises(RuntimeError, match="build_binding_mismatch"):
        _runtime(tmp_path, store, prepared, market_reader=reader).run(changed_transport)

    assert calls == {"resolve": 0, "publish": 0, "timeline": 0, "engine": 0}
    assert store.puts == 0
    assert not (tmp_path / "runs").exists()


def test_v3_target_digest_precedes_profile_and_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    wrong_request = replace(
        resolved.request,
        target_stream_digest="sha256:" + "0" * 64,
    )
    payload = json.loads(canonical_bytes(envelope).decode())["payload"]
    payload["request_hash"] = wrong_request.request_hash
    changed = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)
    changed_transport = BacktestExecutionRequest(
        3,
        wrong_request,
        ArtifactRef.from_envelope(changed),
    )
    store = _ArtifactStore(changed)

    def forbidden(*args, **kwargs):
        raise AssertionError("resolution/preparation must not start")

    monkeypatch.setattr(ProfileResolver, "resolve", forbidden)
    monkeypatch.setattr(
        "crypto_quant_backtest.facade._prepare_multi_resolution_market_data_from_retained_v1",
        forbidden,
    )
    monkeypatch.setattr(BacktestRuntime, "_publish_resolution_failure", forbidden)
    monkeypatch.setattr(BacktestRuntime, "_execute_case", forbidden)

    with pytest.raises(RuntimeError, match="target_binding_mismatch"):
        _runtime(
            tmp_path,
            store,
            prepared,
            registry=BacktestProfileRegistry((), (), ()),
        ).run(changed_transport)

    assert store.puts == 0
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("fatal", [KeyboardInterrupt("capture"), SystemExit("capture")])
def test_capture_reader_preserves_baseexception_from_reader(fatal) -> None:
    prepared, _, _, _, _ = _executable_contract()
    reader = _FatalReader(prepared.verified_reader, fatal)

    with pytest.raises(type(fatal)) as raised:
        _capture_market_bundle_reader_v1(
            prepared.verified_reader.bundle_ref,
            reader,
        )

    assert raised.value is fatal


def test_capture_reader_preserves_baseexception_from_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, _, _, _, _ = _executable_contract()
    fatal = KeyboardInterrupt("telemetry")

    def fail_record(*args, **kwargs):
        raise fatal

    monkeypatch.setattr(
        "crypto_quant_backtest.multi_resolution_preparation._record",
        fail_record,
    )
    wrong_ref = replace(
        prepared.verified_reader.bundle_ref,
        bundle_key="wrong.bundle",
    )
    with pytest.raises(KeyboardInterrupt) as raised:
        _capture_market_bundle_reader_v1(
            wrong_ref,
            prepared.verified_reader,
            BoundedPerformanceRecorder(),
        )
    assert raised.value is fatal


def test_facade_dispatch_rejects_constructor_bypassed_schema_without_equality_or_io(
    tmp_path: Path,
) -> None:
    prepared, resolved, _, envelope, _ = _executable_contract()
    secret = "SECRET-schema-token-/private/path"

    class EvilInt(int):
        def __eq__(self, other):
            raise RuntimeError(secret)

    store = _ArtifactStore(envelope)
    forged = object.__new__(BacktestExecutionRequest)
    object.__setattr__(forged, "schema_version", EvilInt(3))
    object.__setattr__(forged, "request", resolved.request)
    object.__setattr__(forged, "execution_input_bundle_ref", ArtifactRef.from_envelope(envelope))

    with pytest.raises(RuntimeError, match="malformed_execution_request") as raised:
        _runtime(tmp_path, store, prepared).run(forged)

    assert secret not in str(raised.value)
    assert store.reads == 0
    assert store.puts == 0
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("terminal", ["blocked", "failed", "cancelled"])
def test_v3_retry_terminal_is_idempotent_after_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal: str,
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    store = _ArtifactStore(envelope)
    cancellation = (
        EngineCancellationRequest("bar-open-1", "operator_cancelled")
        if terminal == "cancelled"
        else None
    )
    engine = _SequenceEngine(("ready", terminal), cancellation)
    _install_engine(monkeypatch, engine)
    runtime = _runtime(tmp_path, store, prepared)
    first = (
        runtime.run_with_cancellation(transport, cancellation)
        if cancellation is not None
        else runtime.run(transport)
    )
    assert engine.calls == 2

    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)

    def forbidden_publish(*args, **kwargs):
        raise AssertionError("existing terminal evidence must not be republished")

    monkeypatch.setattr(AttemptEvidenceWriter, "_publish_locked", forbidden_publish)
    restarted = _runtime(tmp_path, store, prepared)
    second = (
        restarted.run_with_cancellation(transport, cancellation)
        if cancellation is not None
        else restarted.run(transport)
    )

    assert second == first
    assert type(second) is ArtifactRef
    assert no_engine.calls == 0
    terminal_result = BacktestEvidenceRepository(store).load_terminal(second)
    assert terminal_result.status is TerminalStatus[terminal.upper()]


def test_v3_restart_reuses_attempt_one_ready_and_runs_only_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    store = _ArtifactStore(envelope)
    first_engine = _SequenceEngine(("ready",))
    _install_engine(monkeypatch, first_engine)
    fatal = KeyboardInterrupt("crash-after-attempt-one")

    def crash_retry(*args, **kwargs):
        raise fatal

    monkeypatch.setattr(
        AuditableBacktestRunner,
        "_retry_from_recovered_v3_locked",
        crash_retry,
    )
    with pytest.raises(KeyboardInterrupt) as raised:
        _runtime(tmp_path, store, prepared).run(transport)
    assert raised.value is fatal
    assert first_engine.calls == 1

    monkeypatch.undo()
    retry_engine = _SequenceEngine(("ready",))
    _install_engine(monkeypatch, retry_engine)
    publish_calls = 0
    original_publish = AttemptEvidenceWriter._publish_locked

    def publish(self, record):
        nonlocal publish_calls
        publish_calls += 1
        return original_publish(self, record)

    monkeypatch.setattr(AttemptEvidenceWriter, "_publish_locked", publish)
    result = _runtime(tmp_path, store, prepared).run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    assert result.artifact_ref.artifact_type == "canonical_publication_manifest"
    assert retry_engine.calls == 1
    assert publish_calls == 1


def test_v3_restart_finalizes_two_ready_attempts_without_engine_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    store = _ArtifactStore(envelope)
    engine = _SequenceEngine(("ready", "ready"))
    _install_engine(monkeypatch, engine)
    fatal = SystemExit("crash-before-canonical")

    def crash_publish(*args, **kwargs):
        raise fatal

    monkeypatch.setattr(BacktestRuntime, "_publish_canonical", crash_publish)
    with pytest.raises(SystemExit) as raised:
        _runtime(tmp_path, store, prepared).run(transport)
    assert raised.value is fatal
    assert engine.calls == 2

    monkeypatch.undo()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)

    def forbidden_publish(*args, **kwargs):
        raise AssertionError("READY evidence must not be republished")

    monkeypatch.setattr(AttemptEvidenceWriter, "_publish_locked", forbidden_publish)
    result = _runtime(tmp_path, store, prepared).run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    assert result.artifact_ref.artifact_type == "canonical_publication_manifest"
    assert no_engine.calls == 0


def test_v3_attempt_graph_corruption_fails_closed_without_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    store = _ArtifactStore(envelope)
    first_engine = _SequenceEngine(("ready",))
    _install_engine(monkeypatch, first_engine)

    def crash_retry(*args, **kwargs):
        raise KeyboardInterrupt("crash")

    monkeypatch.setattr(
        AuditableBacktestRunner,
        "_retry_from_recovered_v3_locked",
        crash_retry,
    )
    with pytest.raises(KeyboardInterrupt):
        _runtime(tmp_path, store, prepared).run(transport)
    attempts = tmp_path / "runs" / resolved.semantic_run_id / "attempts"
    (attempts / ("attempt_" + "0" * 64)).mkdir()

    monkeypatch.undo()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)
    with pytest.raises(RuntimeError, match="Attempt graph"):
        _runtime(tmp_path, store, prepared).run(transport)
    assert no_engine.calls == 0


def test_v3_recovered_finalization_is_byte_identical_to_uninterrupted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()

    normal_store = _ArtifactStore(envelope)
    normal_engine = _SequenceEngine(("ready", "ready"))
    _install_engine(monkeypatch, normal_engine)
    normal_root = tmp_path / "normal"
    normal = _runtime(normal_root, normal_store, prepared).run(transport)
    assert normal_engine.calls == 2

    monkeypatch.undo()
    recovered_store = _ArtifactStore(envelope)
    recovered_engine = _SequenceEngine(("ready", "ready"))
    _install_engine(monkeypatch, recovered_engine)
    recovered_root = tmp_path / "recovered"
    fatal = SystemExit("crash-before-canonical")

    def crash_publish(*args, **kwargs):
        raise fatal

    monkeypatch.setattr(BacktestRuntime, "_publish_canonical", crash_publish)
    with pytest.raises(SystemExit):
        _runtime(recovered_root, recovered_store, prepared).run(transport)

    monkeypatch.undo()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)
    recovered = _runtime(recovered_root, recovered_store, prepared).run(transport)

    assert recovered == normal
    assert no_engine.calls == 0
    normal_canonical = normal_root / "runs" / resolved.semantic_run_id / "canonical-v2"
    recovered_canonical = (
        recovered_root / "runs" / resolved.semantic_run_id / "canonical-v2"
    )
    assert {
        path.name: path.read_bytes() for path in normal_canonical.iterdir()
    } == {
        path.name: path.read_bytes() for path in recovered_canonical.iterdir()
    }


def test_v3_target_is_reconstructed_once_before_timeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    store = _ArtifactStore(envelope)
    target_opens = 0
    original_open = InMemoryMarketBundleReader.open_cursor

    def open_cursor(self, stream_key, *, batch_size):
        nonlocal target_opens
        if stream_key == "targets":
            target_opens += 1
        return original_open(self, stream_key, batch_size=batch_size)

    monkeypatch.setattr(InMemoryMarketBundleReader, "open_cursor", open_cursor)
    result = _runtime(tmp_path, store, prepared).run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    # Original Reader capture, one retained target reconstruction, then two Engine
    # Timeline cursors. Hydration performs no second target reconstruction.
    assert target_opens == 4


def test_v3_attempt_graph_rejects_retry_ordinal_gap_before_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    store = _ArtifactStore(envelope)
    first = AttemptIdentity.first(
        resolved.semantic_run_id
    )
    second = AttemptIdentity.retry(
        first, next_ordinal=2
    )
    attempts = tmp_path / "runs" / resolved.semantic_run_id / "attempts"
    (attempts / ".staging").mkdir(parents=True)
    (attempts / second.attempt_id).mkdir()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)

    with pytest.raises(RuntimeError, match="ordinal gap"):
        _runtime(tmp_path, store, prepared).run(transport)

    assert no_engine.calls == 0
