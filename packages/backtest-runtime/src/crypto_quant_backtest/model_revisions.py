from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from crypto_quant_domain import SimulationInstant, UtcInstant, canonical_bytes, canonical_sha256


_SCHEMA_VERSION = 1


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    digest = text.removeprefix("sha256:")
    if (
        len(text) != 71
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{name} must be a sha256 content hash")
    return text


@dataclass(frozen=True, slots=True)
class ModelArtifactRef:
    model_key: str
    model_hash: str
    training_data_hash: str
    training_start: UtcInstant
    training_end: UtcInstant
    training_code_hash: str
    feature_schema_hash: str
    available_at: SimulationInstant
    revision_id: str
    supersedes_revision_id: str | None

    def __post_init__(self) -> None:
        _text("model_key", self.model_key)
        for name in (
            "model_hash",
            "training_data_hash",
            "training_code_hash",
            "feature_schema_hash",
        ):
            _hash(name, getattr(self, name))
        if type(self.training_start) is not UtcInstant:
            raise TypeError("training_start must be UtcInstant")
        if type(self.training_end) is not UtcInstant:
            raise TypeError("training_end must be UtcInstant")
        if self.training_start >= self.training_end:
            raise ValueError("training_start must be before training_end")
        if type(self.available_at) is not SimulationInstant:
            raise TypeError("available_at must be SimulationInstant")
        if self.training_end > self.available_at.instant:
            raise ValueError("training_end must not be after artifact availability")
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "model_artifact_ref",
            "schema_version": _SCHEMA_VERSION,
            "model_key": self.model_key,
            "model_hash": self.model_hash,
            "training_data_hash": self.training_data_hash,
            "training_start": self.training_start.to_canonical_dict(),
            "training_end": self.training_end.to_canonical_dict(),
            "training_code_hash": self.training_code_hash,
            "feature_schema_hash": self.feature_schema_hash,
            "available_at": self.available_at.to_canonical_dict(),
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
        }

    @property
    def artifact_ref_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "artifact_ref_hash": self.artifact_ref_hash}


class ModelRevisionTimeline:
    __slots__ = ("_artifacts", "_decision_instant", "_model_key", "_timeline_hash")

    def __init__(
        self,
        *,
        model_key: str,
        decision_instant: SimulationInstant,
        artifacts: Iterable[ModelArtifactRef],
    ) -> None:
        _text("model_key", model_key)
        if type(decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")
        visible_by_hash: dict[str, ModelArtifactRef] = {}
        for artifact in artifacts:
            if type(artifact) is not ModelArtifactRef:
                raise TypeError("artifacts must contain ModelArtifactRef")
            if artifact.model_key != model_key:
                continue
            if artifact.available_at > decision_instant:
                continue
            visible_by_hash[artifact.artifact_ref_hash] = artifact
        ordered = self._validate_and_order(tuple(visible_by_hash.values()))
        body = {
            "type": "model_revision_timeline",
            "schema_version": _SCHEMA_VERSION,
            "model_key": model_key,
            "decision_instant": decision_instant.to_canonical_dict(),
            "visible_artifacts": [item.to_canonical_dict() for item in ordered],
        }
        self._model_key = model_key
        self._decision_instant = decision_instant
        self._artifacts = ordered
        self._timeline_hash = canonical_sha256(body)

    @property
    def timeline_hash(self) -> str:
        return self._timeline_hash

    def select(self) -> ModelArtifactRef | None:
        return None if not self._artifacts else self._artifacts[-1]

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is ModelRevisionTimeline
            and self.timeline_hash == other.timeline_hash
        )

    def __hash__(self) -> int:
        return hash(self.timeline_hash)

    @staticmethod
    def _validate_and_order(
        artifacts: tuple[ModelArtifactRef, ...],
    ) -> tuple[ModelArtifactRef, ...]:
        identities: dict[str, set[str]] = {}
        for artifact in artifacts:
            identities.setdefault(artifact.revision_id, set()).add(
                artifact.artifact_ref_hash
            )
        if any(len(hashes) > 1 for hashes in identities.values()):
            raise ValueError("conflicting visible model revision identity")

        by_revision = {artifact.revision_id: artifact for artifact in artifacts}
        if any(
            artifact.supersedes_revision_id is not None
            and artifact.supersedes_revision_id not in by_revision
            for artifact in artifacts
        ):
            raise ValueError("visible model revision parent is missing")

        children: dict[str, list[str]] = {}
        roots: list[str] = []
        for artifact in artifacts:
            parent = artifact.supersedes_revision_id
            if parent is None:
                roots.append(artifact.revision_id)
            else:
                children.setdefault(parent, []).append(artifact.revision_id)
        if artifacts and (
            len(roots) != 1 or any(len(values) != 1 for values in children.values())
        ):
            raise ValueError("visible model revision chain conflicts")
        if not artifacts:
            return ()

        ordered_revisions: list[str] = []
        current = roots[0]
        while current not in ordered_revisions:
            ordered_revisions.append(current)
            next_values = children.get(current, [])
            if not next_values:
                break
            current = next_values[0]
        if len(ordered_revisions) != len(by_revision) or current in children:
            raise ValueError("visible model revision chain conflicts")
        ordered = tuple(by_revision[revision_id] for revision_id in ordered_revisions)

        if len({artifact.feature_schema_hash for artifact in ordered}) != 1:
            raise ValueError("visible model revision feature schema changes")
        if any(
            child.available_at <= parent.available_at
            for parent, child in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("visible model revision availability regresses")
        return ordered
