from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import ObservationView

from tests.runtime.observations._fixtures import (
    BARS_V2,
    EXECUTION_REFERENCE,
    INSTRUMENT_B,
    OHLCV,
    query,
    record,
    view,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/observations/observation-view-capability-isolation-v1.json"
)


def _payload() -> dict[str, object]:
    observation_view = view()
    successful = observation_view.query(query())
    empty = observation_view.query(query(dataset_key="bars.empty"))
    failures = (
        observation_view.query(query(dataset_key="bars.5m")),
        observation_view.query(query(instrument_id=INSTRUMENT_B)),
        observation_view.query(query(purpose=replace(OHLCV, key="bar.typical-price"))),
        observation_view.query(query(capability=BARS_V2)),
    )
    reordered = ObservationView(
        allowed_queries=(
            query(purpose=EXECUTION_REFERENCE),
            query(dataset_key="bars.empty"),
            query(),
        ),
        records=(
            record(
                "hidden",
                instrument_id=INSTRUMENT_B,
                available_time=90,
                source_sequence=3,
                close_units=20_000,
            ),
            record("bar-1", available_time=100, source_sequence=1, close_units=10_100),
            record("bar-2", available_time=200, source_sequence=2, close_units=10_200),
            record(
                "bar-1",
                purpose=EXECUTION_REFERENCE,
                available_time=100,
                source_sequence=1,
                close_units=10_100,
            ),
        ),
    )
    return {
        "schema_version": 1,
        "fixture_id": "observation-view-capability-isolation-v1",
        "view_hash": observation_view.view_hash,
        "successful": successful.to_canonical_dict(),
        "empty": empty.to_canonical_dict(),
        "failures": [outcome.to_canonical_dict() for outcome in failures],
        "input_order_parity": {
            "view_hash": reordered.view_hash,
            "outcome_hash": reordered.query(query()).outcome_hash,
            "matches": reordered.view_hash == observation_view.view_hash
            and reordered.query(query()).outcome_hash == successful.outcome_hash,
        },
        "limitations": [
            "decision_time_visibility_owned_by_g11b",
            "no_strategy_invocation",
            "no_universe_or_window_semantics",
            "no_result_cache",
        ],
    }


def test_observation_view_matches_static_golden() -> None:
    assert _payload() == json.loads(FIXTURE.read_text(encoding="utf-8"))
