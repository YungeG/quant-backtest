from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from crypto_quant_domain import ArtifactRef


@dataclass(frozen=True, slots=True)
class BacktestCanonicalPublicationRef:
    """Nominal reference to a canonical Backtest publication manifest."""

    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.artifact_ref) is not ArtifactRef:
            raise TypeError("artifact_ref must be ArtifactRef")
        if self.artifact_ref.artifact_type != "canonical_publication_manifest":
            raise ValueError("artifact_ref must reference canonical_publication_manifest")
        if self.artifact_ref.schema_version != 1:
            raise ValueError("artifact_ref schema_version must be 1")

    @classmethod
    def from_artifact_ref(
        cls, artifact_ref: ArtifactRef
    ) -> BacktestCanonicalPublicationRef:
        return cls(artifact_ref)

    def to_artifact_ref(self) -> ArtifactRef:
        return self.artifact_ref

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_canonical_publication_ref",
            "artifact_ref": self.artifact_ref,
        }


RunPublicationRef: TypeAlias = BacktestCanonicalPublicationRef | ArtifactRef
