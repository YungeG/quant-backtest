import hashlib
import pytest
from pathlib import Path
from crypto_quant_backtest import BacktestEvidenceRepository, BacktestEvidenceError, BacktestEvidenceFailureCode, TerminalStatus
from crypto_quant_domain import ArtifactReadResult, ArtifactEnvelope, ArtifactRef, ArtifactNotFoundError, ArtifactRetentionUnavailableError, ArtifactIntegrityError, canonical_sha256, canonical_bytes

def test_architecture():
    src = (Path(__file__).parent.parent.parent.parent / "packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py").read_text()
    assert "__new__" not in src
    assert "__getattr__" not in src
    assert "crypto_quant_platform" not in src
    assert "res.artifact" not in src

class MockReader:
    def __init__(self):
        self.artifacts = {}
        self.raise_on_read = None
        self.track_reads = []
    def put(self, ref, bytes, envelope):
        self.artifacts[ref] = ArtifactReadResult(envelope=envelope, artifact=object(), source_bytes=bytes, source_hash=f"sha256:{hashlib.sha256(bytes).hexdigest()}")
    def read(self, *, ref):
        self.track_reads.append(ref)
        if self.raise_on_read:
            raise self.raise_on_read
        if ref not in self.artifacts:
            raise ArtifactNotFoundError("not found")
        return self.artifacts[ref]

def test_source_bytes_authority():
    r = MockReader()
    repo = BacktestEvidenceRepository(r)
    payload = {
        "type": "backtest_resolution_failure",
        "code": "profile_not_found",
        "request_hash": "sha256:" + "1" * 64,
        "subjects": [],
        "compatibility_report": None,
    }
    env = ArtifactEnvelope.create("backtest_resolution_failure", 1, payload)
    r.put(ArtifactRef.from_envelope(env), canonical_bytes(env), env)

    loaded = repo._read_expected(
        ArtifactRef.from_envelope(env),
        "backtest_resolution_failure",
        1,
        root=True,
    )
    assert canonical_bytes(loaded.artifact.raw) == canonical_bytes(payload)

def test_domain_error_mapping():
    r = MockReader()
    repo = BacktestEvidenceRepository(r)
    ref = ArtifactRef("canonical_publication_manifest", 1, "sha256:" + "0"*64)
    with pytest.raises(BacktestEvidenceError) as e:
        repo._read_expected(ref, "canonical_publication_manifest", 1, root=True)
    assert e.value.code == BacktestEvidenceFailureCode.PORT_REF_NOT_FOUND

    with pytest.raises(BacktestEvidenceError) as e:
        repo._read_expected(ref, "canonical_publication_manifest", 1, root=False)
    assert e.value.code == BacktestEvidenceFailureCode.PORT_RETENTION_UNAVAILABLE

from crypto_quant_backtest.publication_refs import BacktestCanonicalPublicationRef
from crypto_quant_backtest.analysis import AnalysisArtifactRef

def test_tamper_precedence():
    r = MockReader()
    repo = BacktestEvidenceRepository(r)
    ref = ArtifactRef("canonical_publication_manifest", 1, "sha256:" + "0"*64)
    r.raise_on_read = ArtifactIntegrityError("tampered")
    with pytest.raises(BacktestEvidenceError) as e:
        repo._read_expected(ref, "canonical_publication_manifest", 1, root=True)
    assert e.value.code == BacktestEvidenceFailureCode.PORT_EVIDENCE_TAMPERED

def test_type_precedence():
    r = MockReader()
    repo = BacktestEvidenceRepository(r)
    ref = ArtifactRef("evidence_manifest", 1, "sha256:" + "0"*64)
    with pytest.raises(BacktestEvidenceError) as e:
        repo._read_expected(ref, "canonical_publication_manifest", 1, root=True)
    assert e.value.code == BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH

from crypto_quant_backtest import EngineExecutionContext
from crypto_quant_domain import CurrencyId
from tests.runtime.integration._fixtures import completed_journey
from tests.runtime.integrity._fixtures import rebuild_evidence
from crypto_quant_backtest import CanonicalResultPublisher, BacktestMetricProfile, BacktestAnalysisRuntime

class LocalReader:
    def __init__(self, root):
        self.d={}
        for p in Path(root).rglob('*.json'):
            b=p.read_bytes()
            import json
            e=ArtifactEnvelope(**json.loads(b))
            self.d[ArtifactRef.from_envelope(e)]=ArtifactReadResult(envelope=e, artifact=object(), source_bytes=b, source_hash='sha256:'+hashlib.sha256(b).hexdigest())
    def read(self, *, ref):
        try:
            return self.d[ref]
        except KeyError as error:
            raise ArtifactNotFoundError(str(ref)) from error

def _setup_completed(tmp_path: Path):
    j = completed_journey(tmp_path)
    c = j.case
    x = EngineExecutionContext(j.attempts.semantic_run_id, c.semantic_spec_hash, c.case_hash, c.target_stream.target_stream_digest, c.identity_manifest.manifest_hash, c.financial_state)
    o = CanonicalResultPublisher(root=tmp_path).publish_v2(resolved_request=j.attempts.resolved_request, attempt_hashes=j.attempts.attempt_hashes, finalized_attempts=j.attempts.finalized_attempts, rebuild_evidence=rebuild_evidence(j.attempts), engine_context=x)
    ref = BacktestCanonicalPublicationRef.from_artifact_ref(ArtifactRef.from_envelope(ArtifactEnvelope.create('canonical_publication_manifest',1,o.finalized_result_v2.manifest)))
    return tmp_path, j, ref, o.finalized_result_v2

def test_completed(tmp_path: Path):
    root, j, ref, f = _setup_completed(tmp_path)
    r = LocalReader(root)
    v = BacktestEvidenceRepository(r).load_completed(ref)
    assert v.source_publication_ref == ref
    assert v.semantic_run_id == j.attempts.semantic_run_id
    assert v.reporting_currency == CurrencyId("USD")

def test_terminal(tmp_path: Path):
    # we can construct a fake terminal failure
    r = MockReader()
    repo = BacktestEvidenceRepository(r)
    env = ArtifactEnvelope.create("backtest_resolution_failure", 1, {"type": "backtest_resolution_failure", "code": "profile_not_found", "request_hash": "sha256:"+"1"*64, "subjects": [], "compatibility_report": None})
    ref = ArtifactRef.from_envelope(env)
    r.put(ref, canonical_bytes(env), env)
    term = repo.load_terminal(ref)
    assert term.status == TerminalStatus.BLOCKED
    assert term.durable_evidence_ref == ref

class P:
    def __init__(self,r): self.r=r
    def put(self,*,envelope):
        self.r.d[ArtifactRef.from_envelope(envelope)] = ArtifactReadResult(envelope=envelope, artifact=object(), source_bytes=canonical_bytes(envelope), source_hash='sha256:'+hashlib.sha256(canonical_bytes(envelope)).hexdigest())
        return ArtifactRef.from_envelope(envelope)

def test_analysis(tmp_path: Path):
    root, j, ref, f = _setup_completed(tmp_path)
    r = LocalReader(root)
    repo = BacktestEvidenceRepository(r)
    comp = repo.load_completed(ref)
    profile = BacktestMetricProfile('simple_period_return.fill_count.v1',1)
    pe = ArtifactEnvelope.create('backtest_metric_profile',1,profile)
    P(r).put(envelope=pe)
    ar = BacktestAnalysisRuntime(P(r)).derive(comp, ArtifactRef.from_envelope(pe))
    analysis = repo.load_analysis(ar)
    assert analysis.trade_count == 1

def test_child_retention_missing(tmp_path: Path):
    root, j, ref, f = _setup_completed(tmp_path)
    r = LocalReader(root)
    # remove the engine_execution_result from the mock reader
    for k in list(r.d.keys()):
        if k.artifact_type == "engine_execution_result":
            del r.d[k]

    with pytest.raises(BacktestEvidenceError) as e:
        BacktestEvidenceRepository(r).load_completed(ref)
    assert e.value.code == BacktestEvidenceFailureCode.PORT_RETENTION_UNAVAILABLE

def _mutate_root_child(reader, publication_ref, artifact_type, mutator):
    import copy
    import json
    root_result = reader.d[publication_ref.artifact_ref]
    root_json = json.loads(root_result.source_bytes)
    entry = next(
        value
        for value in root_json["payload"]["artifacts"]
        if value["artifact_type"] == artifact_type
    )
    old_ref = ArtifactRef(
        entry["artifact_type"], entry["schema_version"], entry["content_hash"]
    )
    child_json = json.loads(reader.d[old_ref].source_bytes)
    mutator(child_json["payload"])
    child_env = ArtifactEnvelope.create(
        old_ref.artifact_type, old_ref.schema_version, child_json["payload"]
    )
    child_source = canonical_bytes(child_env)
    child_ref = ArtifactRef.from_envelope(child_env)
    reader.d[child_ref] = ArtifactReadResult(
        envelope=child_env,
        artifact=object(),
        source_bytes=child_source,
        source_hash="sha256:" + hashlib.sha256(child_source).hexdigest(),
    )
    entry["content_hash"] = child_ref.content_hash
    entry["source_hash"] = "sha256:" + hashlib.sha256(child_source).hexdigest()
    entry["byte_count"] = len(child_source)
    root_env = ArtifactEnvelope.create(
        "canonical_publication_manifest", 1, root_json["payload"]
    )
    root_source = canonical_bytes(root_env)
    new_root_ref = ArtifactRef.from_envelope(root_env)
    reader.d[new_root_ref] = ArtifactReadResult(
        envelope=root_env,
        artifact=object(),
        source_bytes=root_source,
        source_hash="sha256:" + hashlib.sha256(root_source).hexdigest(),
    )
    return BacktestCanonicalPublicationRef.from_artifact_ref(new_root_ref)

@pytest.mark.parametrize(
    ("artifact_type", "mutator", "message"),
    [
        (
            "completed_backtest_result",
            lambda payload: payload.__setitem__("attempt_id", "attempt_" + "0" * 64),
            "completed attempt id mismatch",
        ),
        (
            "completed_backtest_result",
            lambda payload: payload.__setitem__("request_hash", "sha256:" + "0" * 64),
            "completed request hash mismatch",
        ),
        (
            "completed_backtest_result",
            lambda payload: payload.__setitem__("execution_result_hash", "sha256:" + "0" * 64),
            "execution hash consistency mismatch",
        ),
        (
            "canonical_attempt_ref",
            lambda payload: payload.__setitem__("consistency_set_hash", "sha256:" + "0" * 64),
            "completed result canonical attempt hash mismatch",
        ),
        (
            "integrity_report",
            lambda payload: payload.__setitem__("context_hash", "sha256:" + "0" * 64),
            "completed result integrity report hash mismatch",
        ),
    ],
)
def test_completed_cross_link_tamper(
    tmp_path: Path, artifact_type, mutator, message
):
    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    mutated_ref = _mutate_root_child(reader, ref, artifact_type, mutator)
    with pytest.raises(BacktestEvidenceError, match=message) as error:
        BacktestEvidenceRepository(reader).load_completed(mutated_ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID

def _mutate_root_graph(reader, publication_ref, mutate_attempt):
    import json

    root_json = json.loads(reader.d[publication_ref.artifact_ref].source_bytes)
    entries = {
        entry["relative_path"]: entry for entry in root_json["payload"]["artifacts"]
    }
    payloads = {}
    for path, entry in entries.items():
        ref = ArtifactRef(
            entry["artifact_type"], entry["schema_version"], entry["content_hash"]
        )
        payloads[path] = json.loads(reader.d[ref].source_bytes)["payload"]

    mutate_attempt(payloads["canonical-attempt-ref.json"])
    attempt_hash = canonical_sha256(payloads["canonical-attempt-ref.json"])
    payloads["integrity.json"]["canonical_attempt_ref_hash"] = attempt_hash
    payloads["result.json"]["canonical_attempt_ref_hash"] = attempt_hash
    payloads["result.json"]["integrity_report_hash"] = canonical_sha256(
        payloads["integrity.json"]
    )
    for path, payload in payloads.items():
        entry = entries[path]
        envelope = ArtifactEnvelope.create(
            entry["artifact_type"], entry["schema_version"], payload
        )
        source = canonical_bytes(envelope)
        child_ref = ArtifactRef.from_envelope(envelope)
        reader.d[child_ref] = ArtifactReadResult(
            envelope=envelope,
            artifact=object(),
            source_bytes=source,
            source_hash="sha256:" + hashlib.sha256(source).hexdigest(),
        )
        entry["content_hash"] = child_ref.content_hash
        entry["source_hash"] = "sha256:" + hashlib.sha256(source).hexdigest()
        entry["byte_count"] = len(source)
    root_envelope = ArtifactEnvelope.create(
        "canonical_publication_manifest", 1, root_json["payload"]
    )
    root_source = canonical_bytes(root_envelope)
    root_ref = ArtifactRef.from_envelope(root_envelope)
    reader.d[root_ref] = ArtifactReadResult(
        envelope=root_envelope,
        artifact=object(),
        source_bytes=root_source,
        source_hash="sha256:" + hashlib.sha256(root_source).hexdigest(),
    )
    return BacktestCanonicalPublicationRef.from_artifact_ref(root_ref)


def _mutate_root_manifest(reader, publication_ref, mutator):
    import json
    root_json = json.loads(reader.d[publication_ref.artifact_ref].source_bytes)
    mutator(root_json["payload"])
    env = ArtifactEnvelope.create(
        "canonical_publication_manifest", 1, root_json["payload"]
    )
    source = canonical_bytes(env)
    ref = ArtifactRef.from_envelope(env)
    reader.d[ref] = ArtifactReadResult(
        envelope=env,
        artifact=object(),
        source_bytes=source,
        source_hash="sha256:" + hashlib.sha256(source).hexdigest(),
    )
    return BacktestCanonicalPublicationRef.from_artifact_ref(ref)

def test_evidence_manifest_binds_roles_to_exact_paths_and_types(tmp_path: Path):
    import json

    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    evidence_ref = next(
        value for value in reader.d if value.artifact_type == "evidence_manifest"
    )
    payload = json.loads(reader.d[evidence_ref].source_bytes)["payload"]
    payload["artifacts"][0]["role"], payload["artifacts"][1]["role"] = (
        payload["artifacts"][1]["role"],
        payload["artifacts"][0]["role"],
    )
    envelope = ArtifactEnvelope.create("evidence_manifest", 1, payload)
    source = canonical_bytes(envelope)
    mutated_ref = ArtifactRef.from_envelope(envelope)
    reader.d[mutated_ref] = ArtifactReadResult(
        envelope=envelope,
        artifact=object(),
        source_bytes=source,
        source_hash="sha256:" + hashlib.sha256(source).hexdigest(),
    )
    with pytest.raises(BacktestEvidenceError) as error:
        BacktestEvidenceRepository(reader)._read_expected(
            mutated_ref, "evidence_manifest", 1, root=True
        )
    assert error.value.code == BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("market_bundle_ref_hash", "market bundle ref hash mismatch"),
        ("attempt_record_hash", "attempt record hash mismatch"),
    ],
)
def test_evidence_manifest_recomputes_child_identity_hashes(
    tmp_path: Path, field: str, message: str
):
    from dataclasses import replace

    from crypto_quant_backtest.evidence_repository import _EvidenceManifest

    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    repository = BacktestEvidenceRepository(reader)
    evidence_ref = next(
        value for value in reader.d if value.artifact_type == "evidence_manifest"
    )
    evidence = repository._read_expected(
        evidence_ref, "evidence_manifest", 1, root=True
    ).artifact
    assert type(evidence) is _EvidenceManifest
    tampered_raw = dict(evidence.raw)
    tampered_raw[field] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match=message):
        repository._read_evidence_children(replace(evidence, raw=tampered_raw))


def test_completed_recomputes_evidence_publication_hash(tmp_path: Path):
    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    mutated_ref = _mutate_root_graph(
        reader,
        ref,
        lambda payload: payload.__setitem__(
            "evidence_publication_hash", "sha256:" + "0" * 64
        ),
    )
    with pytest.raises(
        BacktestEvidenceError, match="evidence publication hash mismatch"
    ) as error:
        BacktestEvidenceRepository(reader).load_completed(mutated_ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda payload: payload["artifacts"][0].__setitem__(
                "source_hash", "sha256:" + "0" * 64
            ),
            "source hash",
        ),
        (
            lambda payload: payload["artifacts"][0].__setitem__("byte_count", 1),
            "byte count",
        ),
        (
            lambda payload: payload["artifacts"][0].__setitem__("schema_version", 2),
            "schema mismatch",
        ),
        (
            lambda payload: payload["artifacts"].append(payload["artifacts"][0]),
            "payload reader failed",
        ),
    ],
)
def test_completed_manifest_entry_validation(tmp_path: Path, mutator, message):
    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    mutated_ref = _mutate_root_manifest(reader, ref, mutator)
    with pytest.raises(BacktestEvidenceError, match=message) as error:
        BacktestEvidenceRepository(reader).load_completed(mutated_ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID


def test_integrity_evaluation_manifest_binds_evaluation_id():
    import json

    fixture_path = (
        Path(__file__).parents[2]
        / "fixtures/runtime/integrity-canonical-result-publication-v1.json"
    )
    fixture = json.loads(fixture_path.read_text())["blocked"]
    reader = MockReader()
    for artifact_type, payload in (
        ("integrity_report", fixture["integrity_report"]),
        ("integrity_evaluation_record", fixture["evaluation_record"]),
    ):
        envelope = ArtifactEnvelope.create(artifact_type, 1, payload)
        reader.put(ArtifactRef.from_envelope(envelope), canonical_bytes(envelope), envelope)
    manifest = dict(fixture["publication_manifest"])
    manifest["publication_id"] = "evaluation-other"
    root_envelope = ArtifactEnvelope.create(
        "canonical_publication_manifest", 1, manifest
    )
    root_ref = ArtifactRef.from_envelope(root_envelope)
    reader.put(root_ref, canonical_bytes(root_envelope), root_envelope)
    with pytest.raises(
        BacktestEvidenceError, match="integrity evaluation publication id mismatch"
    ) as error:
        BacktestEvidenceRepository(reader).load_terminal(root_ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID


def test_terminal_rejects_unknown_canonical_publication_id(tmp_path: Path):
    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    mutated_ref = _mutate_root_manifest(
        reader,
        ref,
        lambda payload: payload.__setitem__("publication_id", "canonical-other"),
    )
    with pytest.raises(
        BacktestEvidenceError, match="unsupported canonical publication id"
    ) as error:
        BacktestEvidenceRepository(reader).load_terminal(mutated_ref.artifact_ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID


def test_completed_terminal_checks_retention_before_analyzability(tmp_path: Path):
    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    result_ref = next(
        value for value in reader.d if value.artifact_type == "completed_backtest_result" and value.schema_version == 2
    )
    del reader.d[result_ref]
    with pytest.raises(BacktestEvidenceError) as error:
        BacktestEvidenceRepository(reader).load_terminal(ref.artifact_ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_RETENTION_UNAVAILABLE


def test_completed_evidence_terminal_checks_retention_before_analyzability(tmp_path: Path):
    root, j, ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    evidence_ref = next(value for value in reader.d if value.artifact_type == "evidence_manifest")
    engine_ref = next(value for value in reader.d if value.artifact_type == "engine_execution_result")
    del reader.d[engine_ref]
    with pytest.raises(BacktestEvidenceError) as error:
        BacktestEvidenceRepository(reader).load_terminal(evidence_ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_RETENTION_UNAVAILABLE


def test_resolution_failure_is_semantically_decoded():
    reader = MockReader()
    payload = {
        "type": "backtest_resolution_failure",
        "code": "made_up",
        "request_hash": "sha256:" + "1" * 64,
        "subjects": [],
        "compatibility_report": None,
    }
    env = ArtifactEnvelope.create("backtest_resolution_failure", 1, payload)
    ref = ArtifactRef.from_envelope(env)
    reader.put(ref, canonical_bytes(env), env)
    with pytest.raises(BacktestEvidenceError) as error:
        BacktestEvidenceRepository(reader).load_terminal(ref)
    assert error.value.code == BacktestEvidenceFailureCode.PORT_MANIFEST_INVALID


def _put_envelope(reader, envelope):
    source = canonical_bytes(envelope)
    reader.d[ArtifactRef.from_envelope(envelope)] = ArtifactReadResult(
        envelope=envelope,
        artifact=object(),
        source_bytes=source,
        source_hash="sha256:" + hashlib.sha256(source).hexdigest(),
    )


def test_analysis_link_and_retention_precedence(tmp_path: Path):
    root, j, publication_ref, f = _setup_completed(tmp_path)
    reader = LocalReader(root)
    repo = BacktestEvidenceRepository(reader)
    completed = repo.load_completed(publication_ref)
    profile = BacktestMetricProfile("simple_period_return.fill_count.v1", 1)
    profile_env = ArtifactEnvelope.create("backtest_metric_profile", 1, profile)
    _put_envelope(reader, profile_env)
    analysis_ref = BacktestAnalysisRuntime(P(reader)).derive(
        completed, ArtifactRef.from_envelope(profile_env)
    )
    original = reader.d[analysis_ref.artifact_ref].envelope.payload
    tampered = dict(original)
    tampered["source_execution_result_hash"] = "sha256:" + "0" * 64
    tampered_env = ArtifactEnvelope.create("backtest_analysis", 1, tampered)
    _put_envelope(reader, tampered_env)
    with pytest.raises(BacktestEvidenceError) as error:
        repo.load_analysis(AnalysisArtifactRef(ArtifactRef.from_envelope(tampered_env)))
    assert error.value.code == BacktestEvidenceFailureCode.PORT_ANALYSIS_LINK_MISMATCH

    missing_source = dict(original)
    missing_source["source_publication_ref"] = BacktestCanonicalPublicationRef.from_artifact_ref(
        ArtifactRef("canonical_publication_manifest", 1, "sha256:" + "0" * 64)
    ).to_canonical_dict()
    missing_env = ArtifactEnvelope.create("backtest_analysis", 1, missing_source)
    _put_envelope(reader, missing_env)
    with pytest.raises(BacktestEvidenceError) as error:
        repo.load_analysis(AnalysisArtifactRef(ArtifactRef.from_envelope(missing_env)))
    assert error.value.code == BacktestEvidenceFailureCode.PORT_RETENTION_UNAVAILABLE


def test_repository_fixture_is_frozen():
    fixture = Path(__file__).parents[2] / "fixtures/runtime/bt-gap03-repository-contract-v1.json"
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == "e72648ac1c33812f610f988295391b0d82932ecfc26f4db9a8f3cf98e07b42e5"
