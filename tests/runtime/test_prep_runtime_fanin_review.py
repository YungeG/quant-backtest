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
import crypto_quant_backtest.execution_inputs as execution_inputs_module
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
def test_v3_exact_retry_terminal_remains_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal: str,
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    cancellation = (
        EngineCancellationRequest("bar-open-1", "operator_cancelled")
        if terminal == "cancelled"
        else None
    )
    engine = _SequenceEngine(("ready", terminal), cancellation)
    _install_engine(monkeypatch, engine)
    runtime = _runtime(tmp_path, _ArtifactStore(envelope), prepared)
    first = (
        runtime.run_with_cancellation(transport, cancellation)
        if cancellation is not None
        else runtime.run(transport)
    )
    assert engine.calls == 2

    monkeypatch.undo()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)
    restart_store = _ArtifactStore(envelope)
    restarted = _runtime(tmp_path, restart_store, prepared)
    second = (
        restarted.run_with_cancellation(transport, cancellation)
        if cancellation is not None
        else restarted.run(transport)
    )

    assert second == first
    assert type(second) is ArtifactRef
    assert no_engine.calls == 0
    loaded = BacktestEvidenceRepository(restart_store).load_terminal(second)
    assert loaded.status is TerminalStatus[terminal.upper()]


def _assert_v3_restart_fails_closed(
    *,
    root: Path,
    envelope: ArtifactEnvelope,
    transport: BacktestExecutionRequest,
    prepared,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)
    with pytest.raises(RuntimeError, match="restart state"):
        _runtime(root, _ArtifactStore(envelope), prepared).run(transport)
    assert no_engine.calls == 0


def test_v3_crash_before_engine_leaves_claim_and_restart_runs_no_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    fatal = KeyboardInterrupt("before-engine")

    def crash(*args, **kwargs):
        raise fatal

    monkeypatch.setattr(AuditableBacktestRunner, "_execute_verified_locked", crash)
    with pytest.raises(KeyboardInterrupt) as raised:
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert raised.value is fatal
    _assert_v3_restart_fails_closed(
        root=tmp_path,
        envelope=envelope,
        transport=transport,
        prepared=prepared,
        monkeypatch=monkeypatch,
    )


def test_v3_crash_inside_engine_leaves_claim_and_restart_runs_no_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    fatal = SystemExit("inside-engine")

    class _FatalEngine:
        calls = 0

        def run(self, case, *, cancellation=None):
            self.calls += 1
            raise fatal

    engine = _FatalEngine()
    _install_engine(monkeypatch, engine)
    with pytest.raises(SystemExit) as raised:
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert raised.value is fatal
    assert engine.calls == 1
    _assert_v3_restart_fails_closed(
        root=tmp_path,
        envelope=envelope,
        transport=transport,
        prepared=prepared,
        monkeypatch=monkeypatch,
    )


def test_v3_crash_after_engine_before_evidence_fails_closed_on_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    engine = _SequenceEngine(("ready",))
    _install_engine(monkeypatch, engine)
    fatal = KeyboardInterrupt("after-engine")

    def crash_finalize(*args, **kwargs):
        raise fatal

    monkeypatch.setattr(AttemptEvidenceWriter, "_finalize_v3_locked", crash_finalize)
    with pytest.raises(KeyboardInterrupt):
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert engine.calls == 1
    _assert_v3_restart_fails_closed(
        root=tmp_path,
        envelope=envelope,
        transport=transport,
        prepared=prepared,
        monkeypatch=monkeypatch,
    )


def test_v3_evidence_write_failure_keeps_claim_and_restart_runs_no_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    engine = _SequenceEngine(("ready",))
    _install_engine(monkeypatch, engine)

    def fail_write(*args, **kwargs):
        raise OSError("mapping-write-failed")

    monkeypatch.setattr(AttemptEvidenceWriter, "_write_file", staticmethod(fail_write))
    with pytest.raises(RuntimeError, match="Attempt evidence publication failed"):
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert engine.calls == 1
    _assert_v3_restart_fails_closed(
        root=tmp_path,
        envelope=envelope,
        transport=transport,
        prepared=prepared,
        monkeypatch=monkeypatch,
    )


def test_v3_crash_after_first_ready_fails_closed_without_retry_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    engine = _SequenceEngine(("ready",))
    _install_engine(monkeypatch, engine)
    original_claim = AttemptEvidenceWriter._claim_v3_locked
    calls = 0

    def claim(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("after-first-ready")
        return original_claim(self, *args, **kwargs)

    monkeypatch.setattr(AttemptEvidenceWriter, "_claim_v3_locked", claim)
    with pytest.raises(KeyboardInterrupt):
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert engine.calls == 1
    _assert_v3_restart_fails_closed(
        root=tmp_path,
        envelope=envelope,
        transport=transport,
        prepared=prepared,
        monkeypatch=monkeypatch,
    )


def test_v3_crash_after_second_ready_fails_closed_without_engine_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    engine = _SequenceEngine(("ready", "ready"))
    _install_engine(monkeypatch, engine)

    def crash_publish(*args, **kwargs):
        raise SystemExit("after-second-ready")

    monkeypatch.setattr(BacktestRuntime, "_publish_canonical", crash_publish)
    with pytest.raises(SystemExit):
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert engine.calls == 2
    _assert_v3_restart_fails_closed(
        root=tmp_path,
        envelope=envelope,
        transport=transport,
        prepared=prepared,
        monkeypatch=monkeypatch,
    )


def test_v3_crash_after_canonical_publication_returns_verified_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    engine = _SequenceEngine(("ready", "ready"))
    _install_engine(monkeypatch, engine)
    fatal = SystemExit("after-canonical")
    original_mirror = BacktestRuntime._mirror_publication_graph

    def crash_mirror(self, relative_directory):
        canonical = self._publication_root / relative_directory
        if canonical.name == "canonical-v2":
            raise fatal
        return original_mirror(self, relative_directory)

    monkeypatch.setattr(BacktestRuntime, "_mirror_publication_graph", crash_mirror)
    with pytest.raises(SystemExit):
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert engine.calls == 2

    monkeypatch.undo()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)
    result = _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert type(result) is BacktestCanonicalPublicationRef
    assert no_engine.calls == 0


def test_v3_claims_are_nonmirrored_and_uninterrupted_bytes_remain_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    store = _ArtifactStore(envelope)
    engine = _SequenceEngine(("ready", "ready"))
    _install_engine(monkeypatch, engine)
    result = _runtime(tmp_path, store, prepared).run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    attempts = tmp_path / "runs" / resolved.semantic_run_id / "attempts"
    assert not tuple(attempts.rglob("*.claim"))
    for manifest_path in attempts.glob("attempt_*/evidence-manifest.json"):
        payload = json.loads(manifest_path.read_text())["payload"]
        assert all("claim" not in entry["relative_path"] for entry in payload["artifacts"])
    assert all("claim" not in ref.artifact_type for ref in store.values)


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
    # Original capture, one retained target reconstruction, then two Engine cursors.
    assert target_opens == 4


def test_v3_completed_restart_cannot_be_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    engine = _SequenceEngine(("ready", "ready"))
    _install_engine(monkeypatch, engine)
    _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)
    assert engine.calls == 2

    monkeypatch.undo()
    no_engine = _SequenceEngine(())
    _install_engine(monkeypatch, no_engine)
    cancellation = EngineCancellationRequest("bar-open-1", "operator_cancelled")
    with pytest.raises(RuntimeError, match="completed semantic run cannot be cancelled"):
        _runtime(tmp_path, _ArtifactStore(envelope), prepared).run_with_cancellation(
            transport, cancellation
        )
    assert no_engine.calls == 0


@pytest.mark.parametrize("schema", [True, 0, 4])
def test_ingress_rejects_noncanonical_schema_before_ref_or_io(
    tmp_path: Path, schema
) -> None:
    prepared, resolved, _, envelope, _ = _executable_contract()
    secret = "SECRET-ref-/private/path"

    class EvilRef:
        @property
        def artifact_type(self):
            raise RuntimeError(secret)

    forged = object.__new__(BacktestExecutionRequest)
    object.__setattr__(forged, "schema_version", schema)
    object.__setattr__(forged, "request", resolved.request)
    object.__setattr__(forged, "execution_input_bundle_ref", EvilRef())
    store = _ArtifactStore(envelope)

    with pytest.raises(RuntimeError, match="malformed_execution_request") as raised:
        _runtime(tmp_path, store, prepared).run(forged)

    assert secret not in str(raised.value)
    assert store.reads == 0
    assert store.puts == 0


def test_v3_ingress_snapshot_survives_artifact_reader_mutation(
    tmp_path: Path,
) -> None:
    prepared, resolved, _, envelope, transport = _executable_contract()
    original_ref = transport.execution_input_bundle_ref

    class MutatingStore(_ArtifactStore):
        def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
            object.__setattr__(transport, "schema_version", 1)
            object.__setattr__(
                transport,
                "request",
                replace(
                    resolved.request,
                    target_stream_digest="sha256:" + "0" * 64,
                ),
            )
            object.__setattr__(
                transport,
                "execution_input_bundle_ref",
                ArtifactRef("evidence_manifest", 1, "sha256:" + "0" * 64),
            )
            assert ref == original_ref
            return super().read(ref=ref)

    store = MutatingStore(envelope)
    result = _runtime(tmp_path, store, prepared).run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    assert store.reads == 1


def test_v3_public_request_is_deep_rebuilt_once_before_artifact_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    calls = 0
    original = execution_inputs_module._rebuild_backtest_request_v3

    def rebuild(value):
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(
        execution_inputs_module,
        "_rebuild_backtest_request_v3",
        rebuild,
    )
    result = _runtime(tmp_path, _ArtifactStore(envelope), prepared).run(transport)

    assert type(result) is BacktestCanonicalPublicationRef
    assert calls == 1


def test_v3_semantic_run_binding_precedes_simultaneous_preparation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, _, envelope, transport = _executable_contract()
    payload = json.loads(canonical_bytes(envelope).decode())["payload"]
    payload["semantic_run_id"] = "run_" + "0" * 64
    changed = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)
    changed_transport = replace(
        transport,
        execution_input_bundle_ref=ArtifactRef.from_envelope(changed),
    )
    store = _ArtifactStore(changed)

    def forbidden(*args, **kwargs):
        raise AssertionError("preparation must not start")

    monkeypatch.setattr(
        "crypto_quant_backtest.facade._prepare_multi_resolution_market_data_from_retained_v1",
        forbidden,
    )
    with pytest.raises(RuntimeError, match="request_binding_mismatch"):
        _runtime(tmp_path, store, prepared).run(changed_transport)

    assert store.puts == 0
    assert not (tmp_path / "runs").exists()
