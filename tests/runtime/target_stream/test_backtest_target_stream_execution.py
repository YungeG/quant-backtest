from __future__ import annotations

import json
from dataclasses import fields, replace
from hashlib import sha256
from inspect import Parameter, signature
from pathlib import Path

import pytest

import crypto_quant_backtest as backtest
import crypto_quant_backtest.target_repository as target_repository
from crypto_quant_backtest.execution_inputs import (
    _DecodedExecutionInputBundleV6,
    _EXECUTION_INPUT_CATALOG,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactReadResult,
    ArtifactRef,
    ArtifactRetentionUnavailableError,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader

from tests.runtime.providers.test_cash_development_provider import (
    _inputs,
    _intent,
    bar_event,
    catalog,
    target_event,
)


class _Cas:
    def __init__(self) -> None:
        self.values: dict[ArtifactRef, ArtifactEnvelope] = {}
        self.reads: dict[ArtifactRef, int] = {}

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = envelope
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        self.reads[ref] = self.reads.get(ref, 0) + 1
        try:
            envelope = self.values[ref]
        except KeyError as error:
            raise ArtifactNotFoundError(ref.content_hash) from error
        source = canonical_bytes(envelope)
        return ArtifactReadResult(
            envelope,
            None,
            source,
            canonical_sha256(envelope),
        )


class _FailingReader:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        raise self.error


class _FailingPublisher:
    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        raise OSError("storage unavailable")


class _WrongRefPublisher:
    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        return ArtifactRef("backtest_target_stream", 1, "sha256:" + "f" * 64)


def _context(digit: str = "a") -> ArtifactRef:
    return ArtifactRef(
        "target_materialization_evidence",
        1,
        "sha256:" + digit * 64,
    )


def _stream() -> backtest.PrecomputedTargetStream:
    return backtest.PrecomputedTargetStream("targets", (target_event(),))


def _market_reader() -> InMemoryMarketBundleReader:
    bar = bar_event()
    return InMemoryMarketBundleReader.build(
        bundle_key="cash-development-market-only-v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash=canonical_sha256(catalog()),
        capabilities=(bar.capability,),
        streams={"bars.open": (bar,)},
    )


def _published(store: _Cas, *, context: ArtifactRef | None = None):
    return backtest.BacktestTargetStreamRepository(
        reader=store,
        publisher=store,
    ).publish(context or _context(), _stream())


def test_backtest_target_stream_repository_golden_and_context_identity() -> None:
    store = _Cas()
    first = _published(store)
    second = _published(store, context=_context("b"))
    repository = backtest.BacktestTargetStreamRepository(reader=store)
    loaded = repository.load(first)
    loaded_second = repository.load(second)

    assert first.artifact_ref.content_hash == (
        "sha256:dcd4dd5c76957e1d2d13b7c3d85a2f55d3f6eee9a4ded58715a2f80fa580085d"
    )
    assert first != second
    assert loaded.ref == first
    assert loaded.producer_context_ref == _context()
    assert loaded.target_stream == _stream()
    assert loaded.digest == _stream().target_stream_digest
    assert loaded_second.digest == loaded.digest
    assert tuple(field.name for field in fields(backtest.VerifiedBacktestTargetStream)) == (
        "ref",
        "producer_context_ref",
        "target_stream",
        "digest",
    )


@pytest.mark.parametrize(
    ("reader", "code"),
    (
        (
            _FailingReader(ArtifactNotFoundError("missing")),
            backtest.BacktestTargetStreamFailureCode.NOT_FOUND,
        ),
        (
            _FailingReader(ArtifactRetentionUnavailableError("retained")),
            backtest.BacktestTargetStreamFailureCode.RETENTION_UNAVAILABLE,
        ),
        (
            _FailingReader(ArtifactIntegrityError("tampered")),
            backtest.BacktestTargetStreamFailureCode.TAMPERED,
        ),
        (
            _FailingReader(RuntimeError("unexpected storage failure")),
            backtest.BacktestTargetStreamFailureCode.RETENTION_UNAVAILABLE,
        ),
    ),
)
def test_target_repository_missing_retention_and_tamper_fail_closed(
    reader: _FailingReader,
    code: backtest.BacktestTargetStreamFailureCode,
) -> None:
    ref = backtest.BacktestTargetStreamRef(
        ArtifactRef("backtest_target_stream", 1, "sha256:" + "1" * 64)
    )
    with pytest.raises(backtest.BacktestTargetStreamError) as raised:
        backtest.BacktestTargetStreamRepository(reader=reader).load(ref)
    assert raised.value.code is code


def test_target_repository_publish_failures_are_fail_closed() -> None:
    for publisher, code in (
        (
            _FailingPublisher(),
            backtest.BacktestTargetStreamFailureCode.RETENTION_UNAVAILABLE,
        ),
        (
            _WrongRefPublisher(),
            backtest.BacktestTargetStreamFailureCode.CONTEXT_MISMATCH,
        ),
    ):
        with pytest.raises(backtest.BacktestTargetStreamError) as raised:
            backtest.BacktestTargetStreamRepository(
                reader=_Cas(), publisher=publisher
            ).publish(_context(), _stream())
        assert raised.value.code is code


def test_target_repository_load_maps_context_digest_and_malformed_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Cas()
    ref = _published(store)
    repository = backtest.BacktestTargetStreamRepository(reader=store)

    monkeypatch.setattr(target_repository, "_artifact_ref", lambda value: _context("b"))
    with pytest.raises(backtest.BacktestTargetStreamError) as raised:
        repository.load(ref)
    assert (
        raised.value.code
        is backtest.BacktestTargetStreamFailureCode.CONTEXT_MISMATCH
    )
    monkeypatch.undo()

    changed_event = replace(target_event(), source_hash="sha256:" + "9" * 64)
    changed_stream = backtest.PrecomputedTargetStream("targets", (changed_event,))
    monkeypatch.setattr(
        target_repository,
        "_read_precomputed_target_stream",
        lambda value: changed_stream,
    )
    with pytest.raises(backtest.BacktestTargetStreamError) as raised:
        repository.load(ref)
    assert raised.value.code is backtest.BacktestTargetStreamFailureCode.DIGEST_MISMATCH
    monkeypatch.undo()

    malformed = ArtifactEnvelope.create(
        "backtest_target_stream",
        1,
        {
            "producer_context_ref": _context(),
            "target_stream": {
                **_stream().to_canonical_dict(),
                "unexpected": True,
            },
        },
    )
    malformed_ref = ArtifactRef.from_envelope(malformed)
    store.values[malformed_ref] = malformed
    with pytest.raises(backtest.BacktestTargetStreamError) as raised:
        repository.load(backtest.BacktestTargetStreamRef(malformed_ref))
    assert raised.value.code is backtest.BacktestTargetStreamFailureCode.TAMPERED


def test_target_repository_ref_context_and_digest_failures_are_nominal() -> None:
    store = _Cas()
    ref = _published(store)
    with pytest.raises(backtest.BacktestTargetStreamError) as raised:
        backtest.BacktestTargetStreamRepository(reader=store).load(
            ref.artifact_ref  # type: ignore[arg-type]
        )
    assert raised.value.code is backtest.BacktestTargetStreamFailureCode.REF_TYPE_MISMATCH

    with pytest.raises(ValueError, match="ref does not bind"):
        backtest.VerifiedBacktestTargetStream(
            backtest.BacktestTargetStreamRef(
                ArtifactRef("backtest_target_stream", 1, "sha256:" + "2" * 64)
            ),
            _context(),
            _stream(),
            _stream().target_stream_digest,
        )
    with pytest.raises(ValueError, match="digest does not bind"):
        backtest.VerifiedBacktestTargetStream(
            ref,
            _context(),
            _stream(),
            "sha256:" + "3" * 64,
        )


def test_equal_streams_with_distinct_producer_refs_have_equal_semantic_run_identity(
    tmp_path: Path,
) -> None:
    store = _Cas()
    first_ref = _published(store, context=_context("a"))
    second_ref = _published(store, context=_context("b"))
    first = backtest.prepare_cash_target_stream_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        target_stream_ref=first_ref,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_market_reader(),
        publication_root=tmp_path / "first",
    )
    second = backtest.prepare_cash_target_stream_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        target_stream_ref=second_ref,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_market_reader(),
        publication_root=tmp_path / "second",
    )
    assert first_ref != second_ref
    assert first.execution_request.request.target_stream_digest == (
        second.execution_request.request.target_stream_digest
    )
    assert first.execution_request.request == second.execution_request.request
    assert first.semantic_run_id == second.semantic_run_id
    assert first.execution_request.execution_input_bundle_ref == (
        second.execution_request.execution_input_bundle_ref
    )


def test_timeline_v2_merges_market_and_embedded_target_and_resumes() -> None:
    timeline = backtest.DeterministicTimelineV2.open(
        reader=_market_reader(),
        stream_keys=("bars.open",),
        target_stream=_stream(),
        window=_intent().timeline_window,
    )
    assert type(timeline) is backtest.DeterministicTimelineV2
    cursor = timeline.open_cursor(batch_size=1)
    first = timeline.read_batch(cursor)
    assert first.failure is None and first.batch is not None
    assert tuple(item.event.event_id for item in first.batch.events) == (
        target_event().event_id,
    )
    resumed = timeline.resume_cursor(first.batch.next_cursor)
    assert resumed == first.batch.next_cursor
    with pytest.raises(backtest.TimelineCursorError, match="identity"):
        timeline.resume_cursor(
            replace(
                resumed,
                target_stream_digest="sha256:" + "f" * 64,
            )
        )
    second = timeline.read_batch(resumed)
    assert second.failure is None and second.batch is not None
    assert tuple(item.event.event_id for item in second.batch.events) == (
        bar_event().event_id,
    )
    assert second.batch.window_complete
    assert second.batch.next_cursor.target_position == 1
    assert timeline.timeline_id == canonical_sha256(
        {
            "type": "deterministic_timeline_config_v2",
            "market_bundle_ref": timeline.reader.bundle_ref,
            "market_stream_keys": ("bars.open",),
            "target_stream_digest": _stream().target_stream_digest,
            "window": _intent().timeline_window,
        }
    )


def test_v6_addition_preserves_existing_bundle_request_and_publication_baselines() -> None:
    root = Path(__file__).resolve().parents[3]
    fixture_hashes = {
        "tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json": (
            "09578ac47f997bc4bf55119d31e97dbcad3eb71e90d93a5ef7c8e6669bd66be2"
        ),
        "tests/fixtures/runtime/bt-gap02c-execution-closure-v2.json": (
            "c082042640382dde2dad61f758058ab93c3ba741ed19df0256d7989a157eced1"
        ),
        "tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v3.json": (
            "ac17536771914f599b3ea58f936049208f29b3f707815456e5b763d0762e5179"
        ),
        "tests/fixtures/runtime/execution-input-bundle-v4/equity.json": (
            "58d2dab674acace62c2a8cf92393c01385b76cf92dec33c0c4f014bb4c0a012c"
        ),
        "tests/fixtures/runtime/engine/g12m-tushare-market-engine-journey-v1.json": (
            "63a1df61db13093af30e64820f382d7abe33315f0d28fe5a87ab2a9eb26b0759"
        ),
        "tests/fixtures/runtime/bt-gap04-publication-ref-v1.json": (
            "9cbe91becf64053fdb44cb884a8cfd621e020e8ce54e4f5f6f76411f275e3c79"
        ),
    }
    for relative, expected in fixture_hashes.items():
        assert sha256((root / relative).read_bytes()).hexdigest() == expected

    v1 = json.loads(
        (
            root
            / "tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json"
        ).read_text()
    )
    assert canonical_bytes(v1["materializer_arguments"]["request"]).decode() == v1[
        "request_identity"
    ]["expected_canonical_utf8"]
    assert canonical_bytes(ArtifactEnvelope(**v1["bundle"]["envelope"])).decode() == v1[
        "bundle"
    ]["expected_canonical_utf8"]

    for relative in (
        "tests/fixtures/runtime/bt-gap02c-execution-closure-v2.json",
        "tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v3.json",
    ):
        fixture = json.loads((root / relative).read_text())
        envelope = ArtifactEnvelope(**fixture["bundle"]["envelope"])
        expected = fixture["bundle"].get("expected_canonical_utf8")
        assert canonical_bytes(envelope) == (
            expected.encode()
            if expected is not None
            else canonical_bytes(fixture["bundle"]["envelope"])
        )

    v4_path = root / "tests/fixtures/runtime/execution-input-bundle-v4/equity.json"
    assert canonical_bytes(json.loads(v4_path.read_text())) == v4_path.read_bytes()

    v5 = json.loads(
        (
            root
            / "tests/fixtures/runtime/engine/g12m-tushare-market-engine-journey-v1.json"
        ).read_text()
    )
    assert v5["execution_input_ref"]["schema_version"] == 5
    assert v5["execution_input_ref"]["content_hash"] == (
        "sha256:336e7bf273ca4649af5b67f375fffe0c2a091254ee0620fd9ad98101d0b01c42"
    )
    assert v5["execution_input_source_hash"] == (
        "sha256:3b5e32b62967b1f9c4c752f77995363a9155d2e7c66ae4fd4ddf3d03ecd8b87b"
    )

    publication = json.loads(
        (root / "tests/fixtures/runtime/bt-gap04-publication-ref-v1.json").read_text()
    )
    assert canonical_bytes(publication["completed"]["ref"]) == publication[
        "completed"
    ]["expected_canonical_utf8"].encode()
    for terminal in publication["terminals"]:
        assert canonical_bytes(terminal["ref"]) == terminal[
            "expected_canonical_utf8"
        ].encode()


def test_bundle_v6_round_trip_embeds_value_and_keeps_v1_v5_catalog_entries(
    tmp_path: Path,
) -> None:
    store = _Cas()
    target_ref = _published(store)
    prepared = backtest.prepare_cash_target_stream_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        target_stream_ref=target_ref,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_market_reader(),
        publication_root=tmp_path,
    )
    envelope = store.values[prepared.execution_request.execution_input_bundle_ref]
    decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope)).artifact

    assert prepared.execution_request.schema_version == 6
    assert envelope.artifact_type == "backtest_execution_input_bundle"
    assert envelope.schema_version == 6
    assert type(decoded) is _DecodedExecutionInputBundleV6
    assert decoded.target_stream == _stream()
    assert decoded.timeline_stream_keys == ("bars.open",)
    assert "target_stream" in envelope.payload
    assert "target_stream_ref" not in envelope.payload
    assert "target_stream_key" not in envelope.payload
    registrations = {
        registration.schema_version: registration.payload_reader.__name__
        for registration in _EXECUTION_INPUT_CATALOG.registrations
        if registration.artifact_type == "backtest_execution_input_bundle"
    }
    assert tuple(registrations) == (1, 2, 3, 4, 5, 6)
    assert tuple(registrations[index] for index in range(1, 6)) == (
        "_read_execution_input_payload",
        "_read_execution_input_payload_v2",
        "_read_execution_input_payload_v3",
        "_read_execution_input_payload_v4",
        "_read_execution_input_payload_v5",
    )


def test_cash_target_preparation_run_analysis_replay_needs_no_target_rematerialization(
    tmp_path: Path,
) -> None:
    store = _Cas()
    target_ref = _published(store)
    prepared = backtest.prepare_cash_target_stream_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        target_stream_ref=target_ref,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_market_reader(),
        publication_root=tmp_path,
    )
    assert store.reads[target_ref.artifact_ref] == 1
    del store.values[target_ref.artifact_ref]

    first = prepared.runtime.run(prepared.execution_request)
    second = prepared.runtime.run(prepared.execution_request)

    assert type(first) is backtest.BacktestCanonicalPublicationRef
    assert second == first
    assert store.reads[target_ref.artifact_ref] == 1
    completed = backtest.BacktestEvidenceRepository(store).load_completed(first)
    profile = backtest.BacktestMetricProfile(
        "simple_period_return.fill_count.v1", 1
    )
    profile_ref = store.put(
        envelope=ArtifactEnvelope.create("backtest_metric_profile", 1, profile)
    )
    analysis_ref = backtest.BacktestAnalysisRuntime(store).derive(
        completed, profile_ref
    )
    analysis = backtest.BacktestEvidenceRepository(store).load_analysis(
        analysis_ref
    )
    assert analysis.simple_period_return == "-0.1"
    assert analysis.trade_count == 1


def test_bundle_v6_target_tamper_fails_before_attempt(tmp_path: Path) -> None:
    store = _Cas()
    target_ref = _published(store)
    prepared = backtest.prepare_cash_target_stream_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        target_stream_ref=target_ref,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_market_reader(),
        publication_root=tmp_path,
    )
    original_ref = prepared.execution_request.execution_input_bundle_ref
    original = store.values[original_ref]
    payload = dict(original.payload)
    target = dict(payload["target_stream"])
    event = dict(target["events"][0])
    event["source_hash"] = "sha256:" + "9" * 64
    target["events"] = (event,)
    payload["target_stream"] = target
    tampered = ArtifactEnvelope.create(
        "backtest_execution_input_bundle", 6, payload
    )
    tampered_ref = store.put(envelope=tampered)
    request = replace(
        prepared.execution_request,
        execution_input_bundle_ref=tampered_ref,
    )

    with pytest.raises(RuntimeError, match="target_binding_mismatch"):
        prepared.runtime.run(request)
    assert not (tmp_path / "runs").exists()


def test_target_stream_public_root_boundary_is_exact() -> None:
    names = (
        "BacktestTargetStreamRef",
        "BacktestTargetStreamRepository",
        "VerifiedBacktestTargetStream",
        "BacktestTargetStreamFailureCode",
        "BacktestTargetStreamError",
        "DeterministicTimelineV2",
        "TimelineCursorV2",
        "materialize_execution_input_bundle_v6",
        "prepare_cash_target_stream_backtest",
    )
    assert all(name in backtest.__all__ for name in names)
    assert not hasattr(backtest, "read_precomputed_target_stream")
    assert "_read_precomputed_target_stream" not in backtest.__all__
    assert tuple(field.name for field in fields(backtest.BacktestTargetStreamRef)) == (
        "artifact_ref",
    )
    parameters = tuple(
        signature(backtest.prepare_cash_target_stream_backtest).parameters.values()
    )
    assert tuple(parameter.name for parameter in parameters) == (
        "request_intent",
        "provider_inputs",
        "target_stream_ref",
        "artifact_reader",
        "artifact_publisher",
        "market_reader",
        "publication_root",
    )
    assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters)
