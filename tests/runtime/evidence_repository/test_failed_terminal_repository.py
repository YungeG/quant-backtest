from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crypto_quant_backtest import (
    AttemptEvidenceWriter,
    BacktestEvidenceRepository,
    TerminalStatus,
)
from crypto_quant_domain import ArtifactEnvelope, ArtifactReadResult, ArtifactRef
from tests.runtime.evidence._fixtures import attempt_record


class _LocalStructuralReader:
    def __init__(self, root: Path) -> None:
        self._artifacts: dict[ArtifactRef, ArtifactReadResult] = {}
        self.read_refs: list[ArtifactRef] = []
        for path in root.rglob("*.json"):
            source = path.read_bytes()
            envelope = ArtifactEnvelope(**json.loads(source))
            ref = ArtifactRef.from_envelope(envelope)
            self._artifacts[ref] = ArtifactReadResult(
                envelope=envelope,
                artifact={"not": "semantic authority"},
                source_bytes=source,
                source_hash="sha256:" + hashlib.sha256(source).hexdigest(),
            )

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        self.read_refs.append(ref)
        return self._artifacts[ref]


def test_repository_loads_exact_reachable_failed_attempt_graph(tmp_path: Path) -> None:
    publication = AttemptEvidenceWriter(root=tmp_path).publish(
        attempt_record("failed")
    )
    assert publication.failure is None
    assert publication.finalized is not None
    finalized = publication.finalized
    assert finalized.status.value == "FAILED"
    assert finalized.terminal_outcome is not None
    assert finalized.terminal_outcome.value == "FAILED"

    root_envelope = ArtifactEnvelope.create(
        "evidence_manifest",
        1,
        finalized.manifest,
    )
    root_ref = ArtifactRef.from_envelope(root_envelope)
    reader = _LocalStructuralReader(tmp_path)

    terminal = BacktestEvidenceRepository(reader).load_terminal(root_ref)

    assert terminal.status is TerminalStatus.FAILED
    assert terminal.durable_evidence_ref == root_ref
    expected_refs = {
        root_ref,
        *(
            ArtifactRef(
                entry.artifact_type,
                entry.schema_version,
                entry.content_hash,
            )
            for entry in finalized.manifest.artifacts
        ),
    }
    assert set(reader.read_refs) == expected_refs
