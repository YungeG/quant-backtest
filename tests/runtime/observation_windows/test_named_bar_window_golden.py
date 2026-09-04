from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import NamedBarWindowView
from crypto_quant_domain import UtcInstant, canonical_bytes

from tests.runtime.observation_windows._fixtures import backing_result, named_query, window
from tests.runtime.observations._causality_fixtures import DECISION_BEFORE_CORRECTION
from tests.runtime.observations._fixtures import query


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/observation-windows/named-bar-window-coverage-v1.json"
)


def _failure_controls() -> dict[str, bool]:
    backing = backing_result()
    named = named_query()
    result = window(NamedBarWindowView(query=named, backing_result=backing))
    attempts = {
        "invalid_definition_hash": lambda: replace(
            named.bar_definition,
            definition_hash="bad",
        ),
        "invalid_lookback": lambda: replace(named, lookback_count=0),
        "future_cutoff": lambda: replace(
            named,
            end_at_or_before=UtcInstant(201),
        ),
        "decision_mismatch": lambda: NamedBarWindowView(
            query=replace(named, decision_instant=DECISION_BEFORE_CORRECTION),
            backing_result=backing,
        ),
        "query_mismatch": lambda: NamedBarWindowView(
            query=replace(named, observation_query=query(dataset_key="bars.other")),
            backing_result=backing,
        ),
        "forged_count": lambda: replace(result, available_count=999),
        "forged_maximum": lambda: replace(result, max_event_time=UtcInstant(999)),
        "forged_grade": lambda: replace(result, decision_grade_eligible=True),
    }
    controls: dict[str, bool] = {}
    for name, attempt in attempts.items():
        try:
            attempt()
        except (TypeError, ValueError):
            controls[name] = True
        else:
            controls[name] = False
    return controls


def _payload() -> dict[str, object]:
    backing = backing_result()
    partial_query = named_query()
    partial_view = NamedBarWindowView(query=partial_query, backing_result=backing)
    full_view = NamedBarWindowView(
        query=named_query(lookback_count=1), backing_result=backing
    )
    cutoff_view = NamedBarWindowView(
        query=named_query(end_at_or_before=UtcInstant(100)),
        backing_result=backing,
    )
    empty_view = NamedBarWindowView(
        query=named_query(end_at_or_before=UtcInstant(0)),
        backing_result=backing,
    )
    changed_definition = replace(
        partial_query.bar_definition,
        version=2,
        definition_hash="sha256:" + "c" * 64,
    )
    changed_view = NamedBarWindowView(
        query=named_query(bar_definition=changed_definition),
        backing_result=backing,
    )
    repeated_view = NamedBarWindowView(
        query=named_query(),
        backing_result=backing,
    )
    partial = window(partial_view)
    return {
        "schema_version": 1,
        "fixture_id": "named-bar-window-coverage-v1",
        "partial_window": partial.to_canonical_dict(),
        "full_window": window(full_view).to_canonical_dict(),
        "cutoff_window": window(cutoff_view).to_canonical_dict(),
        "empty_window": window(empty_view).to_canonical_dict(),
        "definition_identity": {
            "baseline_view_hash": partial_view.view_hash,
            "changed_view_hash": changed_view.view_hash,
            "differs": partial_view.view_hash != changed_view.view_hash,
        },
        "repeat_parity": {
            "view_hash_matches": partial_view.view_hash == repeated_view.view_hash,
            "result_hash_matches": partial.result_hash
            == window(repeated_view).result_hash,
        },
        "failure_controls": _failure_controls(),
        "limitations": [
            "no_resampling_or_aggregation",
            "no_gap-reason-classification",
            "no_bar-completeness-claim",
            "no_strategy-invocation",
            "no_deployment-authorization",
        ],
    }


def test_named_bar_window_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11D golden fixture: {error}") from error
    assert json.loads(canonical_bytes(_payload())) == expected
