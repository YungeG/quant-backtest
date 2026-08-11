from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from tests.runtime.model_revisions._fixtures import (
    DECISION_AT_CORRECTION,
    DECISION_BEFORE_CORRECTION,
    DECISION_LATE,
    artifacts,
    failure_cases,
    select_model,
    timeline,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/model-revisions/walk-forward-model-revision-v1.json"
)


def _failure_controls() -> dict[str, bool]:
    controls: dict[str, bool] = {}
    for name, supplied, _ in failure_cases():
        try:
            timeline(DECISION_LATE, supplied_artifacts=supplied)
        except ValueError:
            controls[name] = True
        else:
            controls[name] = False
    current = artifacts()[0]
    attempts = {
        "invalid_model_hash": lambda: replace(current, model_hash="bad"),
        "invalid_training_window": lambda: replace(
            current, training_start=current.training_end
        ),
        "training_after_availability": lambda: replace(
            current,
            training_end=replace(current.available_at.instant, epoch_nanoseconds=101),
        ),
    }
    for name, attempt in attempts.items():
        try:
            attempt()
        except (TypeError, ValueError):
            controls[name] = True
        else:
            controls[name] = False
    return controls


def _payload() -> dict[str, object]:
    supplied = artifacts()
    before = timeline(
        DECISION_BEFORE_CORRECTION,
        supplied_artifacts=supplied[:1],
    )
    before_with_hidden = timeline(
        DECISION_BEFORE_CORRECTION,
        supplied_artifacts=tuple(reversed(supplied)),
    )
    corrected = timeline(DECISION_AT_CORRECTION)
    repeated = timeline(
        DECISION_AT_CORRECTION,
        supplied_artifacts=(supplied[1], supplied[0], supplied[0], supplied[3]),
    )
    empty = timeline(DECISION_LATE, supplied_artifacts=())
    return {
        "schema_version": 1,
        "fixture_id": "walk-forward-model-revision-v1",
        "before_correction": {
            "timeline_hash": before.timeline_hash,
            "selected": select_model(before).to_canonical_dict(),
        },
        "at_correction": {
            "timeline_hash": corrected.timeline_hash,
            "selected": select_model(corrected).to_canonical_dict(),
        },
        "future_and_unrelated_noninterference": {
            "timeline_hash_matches": before.timeline_hash
            == before_with_hidden.timeline_hash,
            "selection_hash_matches": select_model(before).artifact_ref_hash
            == select_model(before_with_hidden).artifact_ref_hash,
        },
        "input_repeat_parity": {
            "timeline_hash_matches": corrected.timeline_hash == repeated.timeline_hash,
            "selection_hash_matches": select_model(corrected).artifact_ref_hash
            == select_model(repeated).artifact_ref_hash,
        },
        "empty_success": {
            "timeline_hash": empty.timeline_hash,
            "selected": select_model(empty),
        },
        "failure_controls": _failure_controls(),
        "limitations": [
            "no_model_loading_or_inference",
            "no_training_or_candidate_selection",
            "no_strategy_state_mutation",
            "no_model-quality-claim",
            "no-deployment-authorization",
        ],
    }


def test_model_revision_timeline_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11H golden fixture: {error}") from error
    assert _payload() == expected
