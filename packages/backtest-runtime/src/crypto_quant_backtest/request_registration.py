from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import ArtifactRef


@dataclass(frozen=True, slots=True)
class BacktestRequestRef:
    """Nominal persisted coordinate for one immutable BacktestRequest@1."""

    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.artifact_ref) is not ArtifactRef:
            raise TypeError("artifact_ref must be exact ArtifactRef")
        if (
            self.artifact_ref.artifact_type != "backtest_request"
            or self.artifact_ref.schema_version != 1
        ):
            raise ValueError("artifact_ref must reference backtest_request@1")

    @classmethod
    def from_artifact_ref(cls, artifact_ref: ArtifactRef) -> BacktestRequestRef:
        return cls(artifact_ref)

    def to_artifact_ref(self) -> ArtifactRef:
        return self.artifact_ref

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_request_ref",
            "artifact_ref": self.artifact_ref,
        }
