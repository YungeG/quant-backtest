from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from tests.runtime.observations._causality_fixtures import (
    DECISION_AT_CORRECTION,
    DECISION_BEFORE_CORRECTION,
    DECISION_LATE,
    causality_failure_cases,
    point_in_time_view,
    precedence_records,
    records,
    run_query,
)
from tests.runtime.observations._fixtures import (
    BARS_V2,
    INSTRUMENT_B,
    OHLCV,
    query,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/observations/observation-revision-causality-v1.json"
)


def _forgery_controls() -> dict[str, bool]:
    outcome = run_query(point_in_time_view(DECISION_AT_CORRECTION))
    if outcome.result is None:
        raise AssertionError("fixture correction must succeed")
    controls: dict[str, bool] = {}
    attempts = {
        "dataset_hash": lambda: replace(
            outcome.result,
            trace=replace(
                outcome.result.trace,
                dataset_hash="sha256:" + "0" * 64,
            ),
        ),
        "future_result": lambda: replace(
            outcome.result,
            decision_instant=DECISION_BEFORE_CORRECTION,
        ),
        "trace_context": lambda: replace(
            outcome.result,
            trace=replace(
                outcome.result.trace,
                view_hash="sha256:" + "f" * 64,
            ),
        ),
    }
    for name, attempt in attempts.items():
        try:
            attempt()
        except ValueError:
            controls[name] = True
        else:
            controls[name] = False
    return controls


def _payload() -> dict[str, object]:
    supplied = records()
    before = point_in_time_view(
        DECISION_BEFORE_CORRECTION,
        supplied_records=supplied[:2],
    )
    before_with_hidden = point_in_time_view(
        DECISION_BEFORE_CORRECTION,
        supplied_records=tuple(reversed(supplied)),
    )
    corrected = point_in_time_view(DECISION_AT_CORRECTION)
    before_outcome = run_query(before)
    hidden_outcome = run_query(before_with_hidden)
    corrected_outcome = run_query(corrected)
    empty_query = query(dataset_key="bars.empty")
    empty_outcome = run_query(
        point_in_time_view(
            DECISION_LATE,
            supplied_records=(),
            allowed_queries=(query(), empty_query),
        ),
        empty_query,
    )
    authorization_failures = (
        run_query(point_in_time_view(DECISION_LATE), query(dataset_key="trades")),
        run_query(point_in_time_view(DECISION_LATE), query(instrument_id=INSTRUMENT_B)),
        run_query(
            point_in_time_view(DECISION_LATE),
            query(purpose=replace(OHLCV, key="bar.typical-price")),
        ),
        run_query(point_in_time_view(DECISION_LATE), query(capability=BARS_V2)),
    )
    causality_failures = {
        name: run_query(
            point_in_time_view(DECISION_LATE, supplied_records=case_records)
        ).to_canonical_dict()
        for name, case_records, _ in causality_failure_cases()
    }
    precedence = precedence_records()
    precedence_forward = run_query(
        point_in_time_view(DECISION_LATE, supplied_records=precedence)
    )
    precedence_reversed = run_query(
        point_in_time_view(
            DECISION_LATE,
            supplied_records=tuple(reversed(precedence)),
        )
    )
    repeated = point_in_time_view(
        DECISION_AT_CORRECTION,
        supplied_records=(*reversed(supplied), supplied[0], supplied[1]),
    )
    return {
        "schema_version": 1,
        "fixture_id": "observation-revision-causality-v1",
        "before_correction": before_outcome.to_canonical_dict(),
        "at_correction": corrected_outcome.to_canonical_dict(),
        "empty_success": empty_outcome.to_canonical_dict(),
        "authorization_failures": [
            outcome.to_canonical_dict() for outcome in authorization_failures
        ],
        "causality_failures": causality_failures,
        "future_and_unauthorized_noninterference": {
            "view_hash_matches": before.view_hash == before_with_hidden.view_hash,
            "outcome_hash_matches": before_outcome.outcome_hash
            == hidden_outcome.outcome_hash,
        },
        "input_order_repeat_parity": {
            "view_hash_matches": corrected.view_hash == repeated.view_hash,
            "outcome_hash_matches": corrected_outcome.outcome_hash
            == run_query(repeated).outcome_hash,
            "failure_precedence_matches": precedence_forward.outcome_hash
            == precedence_reversed.outcome_hash,
        },
        "forgery_controls": _forgery_controls(),
        "limitations": [
            "no_universe_semantics",
            "no_window_or_gap_classification",
            "no_strategy_invocation",
            "no_aggregate_decision_audit",
        ],
    }


def test_point_in_time_observation_view_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11B golden fixture: {error}") from error
    assert _payload() == expected
