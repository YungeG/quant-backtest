from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import ModelArtifactRef, ModelRevisionTimeline
from crypto_quant_domain import SourceSequence, UtcInstant

from tests.runtime.model_revisions._fixtures import (
    DECISION_AT_CORRECTION,
    DECISION_BEFORE_CORRECTION,
    DECISION_LATE,
    MODEL_KEY,
    artifact,
    artifacts,
    failure_cases,
    select_model,
    timeline,
)


def test_point_in_time_model_revision_ignores_future_and_unrelated_conflicts() -> None:
    supplied = artifacts()
    baseline = timeline(
        DECISION_BEFORE_CORRECTION,
        supplied_artifacts=supplied[:1],
    )
    with_hidden = timeline(
        DECISION_BEFORE_CORRECTION,
        supplied_artifacts=tuple(reversed(supplied)),
    )

    assert baseline.timeline_hash == with_hidden.timeline_hash
    assert select_model(baseline) == supplied[0]
    assert select_model(with_hidden) == supplied[0]

    corrected = timeline(DECISION_AT_CORRECTION)
    selected = select_model(corrected)
    assert selected is not None
    assert selected.revision_id == "v2"
    assert selected.supersedes_revision_id == "v1"


@pytest.mark.parametrize(
    ("case_name", "supplied_artifacts", "message"),
    failure_cases(),
)
def test_visible_revision_chain_failures_are_deterministic(
    case_name: str,
    supplied_artifacts: tuple[ModelArtifactRef, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        timeline(DECISION_LATE, supplied_artifacts=supplied_artifacts)
    assert case_name


def test_empty_exact_duplicates_and_input_order_are_deterministic() -> None:
    empty = timeline(DECISION_LATE, supplied_artifacts=())
    assert select_model(empty) is None

    supplied = artifacts()[:2]
    forward = timeline(DECISION_LATE, supplied_artifacts=supplied)
    repeated = timeline(
        DECISION_LATE,
        supplied_artifacts=(supplied[1], supplied[0], supplied[0], supplied[1]),
    )
    assert forward.timeline_hash == repeated.timeline_hash
    assert forward == repeated
    assert hash(forward) == hash(repeated)
    assert select_model(forward) == select_model(repeated) == supplied[1]


def test_full_simulation_instant_enters_timeline_identity() -> None:
    before = timeline(DECISION_BEFORE_CORRECTION, supplied_artifacts=artifacts()[:1])
    earlier_sequence = timeline(
        replace(DECISION_BEFORE_CORRECTION, source_sequence=SourceSequence(1)),
        supplied_artifacts=artifacts()[:1],
    )

    assert select_model(before) == select_model(earlier_sequence)
    assert before.timeline_hash != earlier_sequence.timeline_hash


def test_model_artifact_ref_binds_full_training_provenance() -> None:
    current = artifacts()[0]
    assert list(current.to_canonical_dict()) == [
        "type",
        "schema_version",
        "model_key",
        "model_hash",
        "training_data_hash",
        "training_start",
        "training_end",
        "training_code_hash",
        "feature_schema_hash",
        "available_at",
        "revision_id",
        "supersedes_revision_id",
        "artifact_ref_hash",
    ]
    assert current.training_end <= current.available_at.instant


@pytest.mark.parametrize(
    ("field", "bad_value", "message"),
    (
        ("model_key", " ", "model_key"),
        ("model_hash", "bad", "sha256"),
        ("training_data_hash", "sha256:" + "G" * 64, "sha256"),
        ("training_code_hash", "sha256:" + "0" * 63, "sha256"),
        ("feature_schema_hash", "sha256:" + "0" * 65, "sha256"),
        ("revision_id", "", "revision_id"),
        ("supersedes_revision_id", " parent ", "supersedes_revision_id"),
        ("available_at", UtcInstant(100), "available_at"),
    ),
)
def test_model_artifact_ref_rejects_invalid_identity(
    field: str,
    bad_value: object,
    message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        replace(artifacts()[0], **{field: bad_value})


def test_model_artifact_ref_rejects_invalid_training_window() -> None:
    current = artifacts()[0]
    with pytest.raises(ValueError, match="before training_end"):
        replace(current, training_start=current.training_end)
    with pytest.raises(ValueError, match="after artifact availability"):
        replace(current, training_end=UtcInstant(101))


def test_timeline_revalidates_public_constructor_context() -> None:
    with pytest.raises(ValueError, match="model_key"):
        ModelRevisionTimeline(
            model_key=" ",
            decision_instant=DECISION_LATE,
            artifacts=(),
        )
    with pytest.raises(TypeError, match="ModelArtifactRef"):
        ModelRevisionTimeline(
            model_key=MODEL_KEY,
            decision_instant=DECISION_LATE,
            artifacts=(object(),),
        )
