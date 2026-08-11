from __future__ import annotations

from crypto_quant_backtest import ModelArtifactRef, ModelRevisionTimeline
from crypto_quant_domain import SimulationInstant, SourceSequence, TimelinePhase, UtcInstant


MODEL_PHASE = TimelinePhase(70, "model_availability")
DECISION_BEFORE_CORRECTION = SimulationInstant(
    UtcInstant(200), MODEL_PHASE, SourceSequence(2)
)
DECISION_AT_CORRECTION = SimulationInstant(
    UtcInstant(200), MODEL_PHASE, SourceSequence(3)
)
DECISION_LATE = SimulationInstant(UtcInstant(500), MODEL_PHASE, SourceSequence(9))
MODEL_KEY = "portfolio.momentum.alpha"
FEATURE_SCHEMA_HASH = "sha256:" + "f" * 64


def content_hash(label: str) -> str:
    return "sha256:" + label.encode().hex().ljust(64, "0")[:64]


def artifact(
    revision_id: str,
    *,
    model_key: str = MODEL_KEY,
    supersedes_revision_id: str | None,
    training_start: int,
    training_end: int,
    available_time: int,
    source_sequence: int,
    model_label: str | None = None,
    feature_schema_hash: str = FEATURE_SCHEMA_HASH,
) -> ModelArtifactRef:
    label = revision_id if model_label is None else model_label
    return ModelArtifactRef(
        model_key=model_key,
        model_hash=content_hash(f"model-{label}"),
        training_data_hash=content_hash(f"data-{label}"),
        training_start=UtcInstant(training_start),
        training_end=UtcInstant(training_end),
        training_code_hash=content_hash("training-code-v1"),
        feature_schema_hash=feature_schema_hash,
        available_at=SimulationInstant(
            UtcInstant(available_time), MODEL_PHASE, SourceSequence(source_sequence)
        ),
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
    )


def artifacts() -> tuple[ModelArtifactRef, ...]:
    return (
        artifact(
            "v1",
            supersedes_revision_id=None,
            training_start=0,
            training_end=90,
            available_time=100,
            source_sequence=1,
        ),
        artifact(
            "v2",
            supersedes_revision_id="v1",
            training_start=100,
            training_end=190,
            available_time=200,
            source_sequence=3,
        ),
        artifact(
            "v2",
            supersedes_revision_id="v1",
            training_start=100,
            training_end=190,
            available_time=200,
            source_sequence=4,
            model_label="v2-conflict",
        ),
        artifact(
            "orphan",
            model_key="portfolio.value.alpha",
            supersedes_revision_id="missing",
            training_start=0,
            training_end=90,
            available_time=100,
            source_sequence=1,
        ),
    )


def timeline(
    decision_instant: SimulationInstant,
    *,
    supplied_artifacts: tuple[ModelArtifactRef, ...] | None = None,
) -> ModelRevisionTimeline:
    return ModelRevisionTimeline(
        model_key=MODEL_KEY,
        decision_instant=decision_instant,
        artifacts=artifacts() if supplied_artifacts is None else supplied_artifacts,
    )


def select_model(timeline_value: ModelRevisionTimeline) -> ModelArtifactRef | None:
    selector = getattr(timeline_value, "select")
    return selector()


def failure_cases() -> tuple[tuple[str, tuple[ModelArtifactRef, ...], str], ...]:
    root = artifact(
        "v1",
        supersedes_revision_id=None,
        training_start=0,
        training_end=90,
        available_time=100,
        source_sequence=1,
    )
    return (
        (
            "revision_identity_conflict",
            (
                root,
                artifact(
                    "v1",
                    supersedes_revision_id=None,
                    training_start=0,
                    training_end=90,
                    available_time=101,
                    source_sequence=1,
                    model_label="v1-conflict",
                ),
            ),
            "conflicting visible model revision identity",
        ),
        (
            "missing_parent",
            (
                artifact(
                    "v2",
                    supersedes_revision_id="v1",
                    training_start=0,
                    training_end=90,
                    available_time=100,
                    source_sequence=1,
                ),
            ),
            "parent is missing",
        ),
        (
            "fork",
            (
                root,
                artifact(
                    "v2a",
                    supersedes_revision_id="v1",
                    training_start=100,
                    training_end=190,
                    available_time=200,
                    source_sequence=1,
                ),
                artifact(
                    "v2b",
                    supersedes_revision_id="v1",
                    training_start=100,
                    training_end=190,
                    available_time=201,
                    source_sequence=1,
                ),
            ),
            "chain conflicts",
        ),
        (
            "cycle",
            (
                artifact(
                    "v1",
                    supersedes_revision_id="v2",
                    training_start=0,
                    training_end=90,
                    available_time=100,
                    source_sequence=1,
                ),
                artifact(
                    "v2",
                    supersedes_revision_id="v1",
                    training_start=100,
                    training_end=190,
                    available_time=200,
                    source_sequence=1,
                ),
            ),
            "chain conflicts",
        ),
        (
            "multiple_roots",
            (
                root,
                artifact(
                    "v2",
                    supersedes_revision_id=None,
                    training_start=100,
                    training_end=190,
                    available_time=200,
                    source_sequence=1,
                ),
            ),
            "chain conflicts",
        ),
        (
            "feature_schema_change",
            (
                root,
                artifact(
                    "v2",
                    supersedes_revision_id="v1",
                    training_start=100,
                    training_end=190,
                    available_time=200,
                    source_sequence=1,
                    feature_schema_hash="sha256:" + "e" * 64,
                ),
            ),
            "feature schema changes",
        ),
        (
            "availability_regression",
            (
                artifact(
                    "v1",
                    supersedes_revision_id=None,
                    training_start=0,
                    training_end=190,
                    available_time=200,
                    source_sequence=2,
                ),
                artifact(
                    "v2",
                    supersedes_revision_id="v1",
                    training_start=0,
                    training_end=190,
                    available_time=200,
                    source_sequence=1,
                ),
            ),
            "availability regresses",
        ),
    )
