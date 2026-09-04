from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from inspect import Parameter, signature
from pathlib import Path
from typing import get_args, get_type_hints

import crypto_quant_backtest
import pytest
from crypto_quant_backtest import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
    BacktestExecutionRequest,
    BacktestProfileRegistry,
    BacktestRuntime,
    materialize_execution_input_bundle_v2,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)

from tests.runtime.evidence._fixtures import attempt_record
from tests.runtime.resolution._fixtures import profile_registry
from tests.runtime.runner._fixtures import resolved_request_and_case

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _ROOT / "tests/fixtures/runtime/bt-gap02-public-facade-v1.json"
_FIXTURE_SHA256 = "0f3f70a457f1a54939b1ecdf6cf860671c0dfcaa20a56297540a3266141c9b91"
_PRESERVED = {
    "bt_gap02a_production_composition_v2": _ROOT
    / "tests/fixtures/runtime/bt-gap02a-production-composition-v2.json",
    "bt_gap02b_execution_input_bundle_v1": _ROOT
    / "tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json",
    "bt_gap02c_execution_closure_v2": _ROOT
    / "tests/fixtures/runtime/bt-gap02c-execution-closure-v2.json",
    "bt_gap04_publication_ref_v1": _ROOT
    / "tests/fixtures/runtime/bt-gap04-publication-ref-v1.json",
}


@dataclass(frozen=True, slots=True)
class _Reader:
    envelope: ArtifactEnvelope
    error: Exception | None = None

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        if self.error is not None:
            raise self.error
        assert ref == ArtifactRef.from_envelope(self.envelope)
        return ArtifactReadResult(
            envelope=self.envelope,
            artifact={"not": "semantic authority"},
            source_bytes=canonical_bytes(self.envelope),
            source_hash=canonical_sha256(self.envelope),
        )


class _RecordingPublisher:
    def __init__(self, returned_ref: ArtifactRef | None = None) -> None:
        self.returned_ref = returned_ref
        self.envelopes: list[ArtifactEnvelope] = []

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        self.envelopes.append(envelope)
        return self.returned_ref or ArtifactRef.from_envelope(envelope)


class _CasPublisher(_RecordingPublisher):
    def __init__(self) -> None:
        super().__init__()
        self.by_ref: dict[ArtifactRef, ArtifactEnvelope] = {}

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = super().put(envelope=envelope)
        self.by_ref[ref] = envelope
        return ref


def _request() -> tuple[BacktestExecutionRequest, object]:
    resolved, case = resolved_request_and_case()
    envelope = materialize_execution_input_bundle_v2(
        resolved_request=resolved,
        execution_case=case,
    )
    return (
        BacktestExecutionRequest(
            schema_version=2,
            request=resolved.request,
            execution_input_bundle_ref=ArtifactRef.from_envelope(envelope),
        ),
        (envelope, case.timeline.reader),
    )


def _runtime(
    publication_root: Path,
    *,
    error: Exception | None = None,
    publisher: _RecordingPublisher | None = None,
) -> BacktestRuntime:
    request, authorities = _request()
    del request
    envelope, market_reader = authorities
    return BacktestRuntime(
        registry=profile_registry(),
        artifact_reader=_Reader(envelope, error),
        artifact_publisher=publisher or _RecordingPublisher(),
        market_reader=market_reader,
        publication_root=publication_root,
    )


def _load_envelope(path: Path) -> ArtifactEnvelope:
    return ArtifactEnvelope(**json.loads(path.read_text(encoding="utf-8")))


def _write_envelope(path: Path, envelope: ArtifactEnvelope) -> None:
    path.write_bytes(canonical_bytes(envelope))


def _entry(relative_path: str, envelope: ArtifactEnvelope) -> dict[str, object]:
    source = canonical_bytes(envelope)
    return {
        "relative_path": relative_path,
        "artifact_type": envelope.artifact_type,
        "schema_version": envelope.schema_version,
        "content_hash": envelope.content_hash,
        "source_hash": canonical_sha256(envelope),
        "byte_count": len(source),
    }


def _child_envelope() -> ArtifactEnvelope:
    return ArtifactEnvelope.create("backtest_resolution_failure", 1, {"code": "x"})


def _write_manifest(directory: Path, entries: tuple[dict[str, object], ...]) -> None:
    envelope = ArtifactEnvelope.create(
        "canonical_publication_manifest",
        1,
        {"artifacts": entries},
    )
    _write_envelope(directory / "publication-manifest.json", envelope)


def test_contract_fixture_freezes_one_public_facade_and_preserves_v1_bytes() -> None:
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert fixture["fixture_id"] == "bt-gap02-public-facade-v1"
    assert fixture["platform_contract"]["public_root_symbol"] == "crypto_quant_backtest.BacktestRuntime"
    for name, path in _PRESERVED.items():
        assert sha256(path.read_bytes()).hexdigest() == fixture[
            "preserved_fixture_sha256"
        ][name]


def test_public_facade_hides_orchestration_and_returns_only_direct_refs() -> None:
    assert crypto_quant_backtest.BacktestRuntime is BacktestRuntime
    assert "BacktestRuntime" in crypto_quant_backtest.__all__
    init_parameters = tuple(signature(BacktestRuntime).parameters.values())
    assert [value.name for value in init_parameters] == [
        "registry",
        "artifact_reader",
        "artifact_publisher",
        "market_reader",
        "publication_root",
    ]
    assert all(value.kind is Parameter.KEYWORD_ONLY for value in init_parameters)
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["composition_only_dependencies"] == [
        value.name for value in init_parameters
    ]
    assert "constructor_keyword_only" not in fixture
    run_parameters = tuple(signature(BacktestRuntime.run).parameters.values())
    assert [value.name for value in run_parameters] == ["self", "request"]
    assert get_args(get_type_hints(BacktestRuntime.run)["return"]) == (
        BacktestCanonicalPublicationRef,
        BacktestCanonicalPublicationRefV2,
        ArtifactRef,
    )
    assert {
        name
        for name, value in vars(BacktestRuntime).items()
        if callable(value) and not name.startswith("_")
    } == {"run", "run_with_cancellation"}


def test_completed_run_is_durable_cache_stable_and_preserves_experiment_id(
    tmp_path: Path,
) -> None:
    request, authorities = _request()
    envelope, market_reader = authorities
    publisher = _RecordingPublisher()
    runtime = BacktestRuntime(
        registry=profile_registry(),
        artifact_reader=_Reader(envelope),
        artifact_publisher=publisher,
        market_reader=market_reader,
        publication_root=tmp_path,
    )

    first = runtime.run(request)
    second = runtime.run(request)

    assert type(first) is BacktestCanonicalPublicationRef
    assert second == first
    assert first.artifact_ref.artifact_type == "canonical_publication_manifest"
    run_root = tmp_path / "runs"
    attempt_requests = tuple(run_root.rglob("attempts/*/request.json"))
    assert len(attempt_requests) == 2
    for path in attempt_requests:
        source = json.loads(path.read_text(encoding="utf-8"))
        assert source["payload"]["experiment_id"] == request.request.experiment_id
    assert len(tuple(run_root.rglob("canonical-v2/publication-manifest.json"))) == 1
    canonical_manifests = [
        envelope
        for envelope in publisher.envelopes
        if envelope.artifact_type == "canonical_publication_manifest"
    ]
    assert [ArtifactRef.from_envelope(value) for value in canonical_manifests] == [
        first.artifact_ref,
        first.artifact_ref,
    ]
    assert [value.artifact_type for value in publisher.envelopes[-4:]] == [
        "canonical_attempt_ref",
        "integrity_report",
        "completed_backtest_result",
        "canonical_publication_manifest",
    ]


def test_cache_hit_with_fresh_publisher_mirrors_attempt_and_canonical_graphs(
    tmp_path: Path,
) -> None:
    request, authorities = _request()
    envelope, market_reader = authorities
    first_runtime = BacktestRuntime(
        registry=profile_registry(),
        artifact_reader=_Reader(envelope),
        artifact_publisher=_CasPublisher(),
        market_reader=market_reader,
        publication_root=tmp_path,
    )
    first = first_runtime.run(request)
    publisher_b = _CasPublisher()
    second_runtime = BacktestRuntime(
        registry=profile_registry(),
        artifact_reader=_Reader(envelope),
        artifact_publisher=publisher_b,
        market_reader=market_reader,
        publication_root=tmp_path,
    )

    second = second_runtime.run(request)

    assert second == first
    assert type(second) is BacktestCanonicalPublicationRef
    canonical_dir = next((tmp_path / "runs").glob("*/canonical-v2"))
    canonical_attempt_ref = _load_envelope(canonical_dir / "canonical-attempt-ref.json")
    attempt_id = canonical_attempt_ref.payload["attempt"]["attempt_id"]
    attempt_dir = canonical_dir.parent / "attempts" / attempt_id
    evidence_manifest = _load_envelope(attempt_dir / "evidence-manifest.json")
    publication_manifest = _load_envelope(canonical_dir / "publication-manifest.json")
    assert (
        evidence_manifest.payload["manifest_hash"]
        == canonical_attempt_ref.payload["evidence_manifest_hash"]
    )
    assert (
        canonical_sha256(evidence_manifest)
        == canonical_attempt_ref.payload["evidence_manifest_source_hash"]
    )
    expected_attempt = [
        _load_envelope(attempt_dir / entry["relative_path"])
        for entry in evidence_manifest.payload["artifacts"]
    ] + [evidence_manifest]
    expected_canonical = [
        _load_envelope(canonical_dir / entry["relative_path"])
        for entry in publication_manifest.payload["artifacts"]
    ] + [publication_manifest]
    assert publisher_b.envelopes == expected_attempt + expected_canonical
    assert [
        publisher_b.by_ref[ArtifactRef.from_envelope(value)]
        for value in expected_attempt
    ] == expected_attempt
    assert [
        publisher_b.by_ref[ArtifactRef.from_envelope(value)]
        for value in expected_canonical
    ] == expected_canonical


def test_manifest_structural_gate_rejects_collision_type_and_hash() -> None:
    entry = _entry("child.json", _child_envelope())
    bad_cases = [
        {"artifacts": [entry]},
        {"artifacts": ("not-a-mapping",)},
        {"artifacts": (entry, entry)},
        {
            "artifacts": (
                {key: value for key, value in entry.items() if key != "byte_count"},
            )
        },
        {"artifacts": ({**entry, "artifact_type": 1},)},
        {"artifacts": ({**entry, "artifact_type": "Bad"},)},
        {"artifacts": ({**entry, "schema_version": True},)},
        {"artifacts": ({**entry, "content_hash": "sha256:" + "A" * 64},)},
        {"artifacts": ({**entry, "source_hash": "sha256:" + "A" * 64},)},
        {"artifacts": ({**entry, "byte_count": 0},)},
    ]

    for payload in bad_cases:
        with pytest.raises(ValueError):
            BacktestRuntime._manifest_artifacts(payload)


@pytest.mark.parametrize(
    "relative_path",
    ("", "/child.json", "child\\x.json", ".", "a/..", "a//b.json", "a/./b.json"),
)
def test_manifest_structural_gate_rejects_unsafe_paths(relative_path: str) -> None:
    entry = {**_entry("child.json", _child_envelope()), "relative_path": relative_path}

    with pytest.raises(ValueError, match="relative_path"):
        BacktestRuntime._manifest_artifacts({"artifacts": (entry,)})


def test_manifest_mirror_rejects_malformed_entry_before_child_read(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "publication"
    directory.mkdir()
    entry = {
        **_entry("missing-child.json", _child_envelope()),
        "source_hash": "sha256:" + "A" * 64,
    }
    _write_manifest(directory, (entry,))
    publisher = _RecordingPublisher()

    with pytest.raises(ValueError, match="source_hash"):
        _runtime(tmp_path, publisher=publisher)._mirror_manifest_graph(
            relative_directory="publication",
            manifest_name="publication-manifest.json",
            manifest_type="canonical_publication_manifest",
        )

    assert publisher.envelopes == []


def test_manifest_mirror_rejects_symlink_escape(tmp_path: Path) -> None:
    directory = tmp_path / "publication"
    directory.mkdir()
    child = _child_envelope()
    outside = tmp_path / "outside.json"
    _write_envelope(outside, child)
    (directory / "child.json").symlink_to(outside)
    _write_manifest(directory, (_entry("child.json", child),))
    publisher = _RecordingPublisher()

    with pytest.raises(ValueError, match="escapes"):
        _runtime(tmp_path, publisher=publisher)._mirror_manifest_graph(
            relative_directory="publication",
            manifest_name="publication-manifest.json",
            manifest_type="canonical_publication_manifest",
        )

    assert publisher.envelopes == []


def test_resolution_failure_returns_publisher_stashed_blocked_ref(
    tmp_path: Path,
) -> None:
    request, authorities = _request()
    envelope, market_reader = authorities
    publisher = _RecordingPublisher()
    runtime = BacktestRuntime(
        registry=BacktestProfileRegistry((), (), ()),
        artifact_reader=_Reader(envelope),
        artifact_publisher=publisher,
        market_reader=market_reader,
        publication_root=tmp_path,
    )

    ref = runtime.run(request)

    assert type(ref) is ArtifactRef
    assert ref.artifact_type == "backtest_resolution_failure"
    assert ref.schema_version == 1
    assert [ArtifactRef.from_envelope(value) for value in publisher.envelopes] == [ref]
    assert publisher.envelopes[0].payload["code"] == "profile_not_found"
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("branch", ("blocked", "failed", "cancelled"))
def test_terminal_attempts_map_to_bare_durable_evidence_refs(
    tmp_path: Path,
    branch: str,
) -> None:
    publication = crypto_quant_backtest.AttemptEvidenceWriter(root=tmp_path).publish(
        attempt_record(branch)
    )
    assert publication.finalized is not None

    ref = BacktestRuntime._evidence_ref(publication.finalized)

    assert type(ref) is ArtifactRef
    assert ref.artifact_type == "evidence_manifest"
    assert ref.schema_version == 1


def test_malformed_provider_and_storage_failures_stay_exceptions(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="malformed_execution_request"):
        _runtime(tmp_path).run(object())  # type: ignore[arg-type]

    request, _ = _request()
    with pytest.raises(RuntimeError, match="execution_input_unavailable"):
        _runtime(tmp_path / "provider", error=OSError("provider unavailable")).run(
            request
        )
    assert not (tmp_path / "provider" / "runs").exists()

    wrong = ArtifactRef("backtest_resolution_failure", 1, "sha256:" + "3" * 64)
    with pytest.raises(ValueError, match="returned ref does not bind envelope"):
        _runtime(
            tmp_path / "wrong-publisher",
            publisher=_RecordingPublisher(wrong),
        ).run(request)

    publication_file = tmp_path / "publication-file"
    publication_file.write_text("not a directory", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Backtest storage failed"):
        _runtime(publication_file).run(request)
