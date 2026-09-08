from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import UniverseKind

from tests.runtime.universe._fixtures import (
    DECISION_AT_CORRECTION,
    DECISION_BEFORE_CORRECTION,
    DECISION_LATE,
    INSTRUMENT_A,
    failure_cases,
    revision,
    revisions,
    select_universe,
    view,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/universe/point-in-time-universe-membership-v1.json"
)


def _failure_controls() -> dict[str, bool]:
    controls: dict[str, bool] = {}
    for name, supplied, _ in failure_cases():
        try:
            view(DECISION_LATE, supplied_revisions=supplied)
        except ValueError:
            controls[name] = True
        else:
            controls[name] = False
    current = revisions()[0]
    attempts = {
        "invalid_listing_interval": lambda: replace(
            current, delisted_at=current.listed_at
        ),
        "invalid_membership_interval": lambda: replace(
            current, member_until=current.member_from
        ),
        "membership_after_delisting": lambda: replace(
            current,
            delisted_at=replace(current.listed_at, epoch_nanoseconds=150),
            member_until=None,
        ),
        "invalid_source_hash": lambda: replace(current, source_hash="bad"),
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
    supplied = revisions()
    before = view(
        DECISION_BEFORE_CORRECTION,
        supplied_revisions=supplied[:2],
    )
    before_with_hidden = view(
        DECISION_BEFORE_CORRECTION,
        supplied_revisions=tuple(reversed(supplied)),
    )
    corrected = view(DECISION_AT_CORRECTION)
    repeated = view(
        DECISION_BEFORE_CORRECTION,
        supplied_revisions=(supplied[1], supplied[0], supplied[0]),
    )
    static_revision = revision(
        "static-a",
        "v1",
        kind=UniverseKind.STATIC,
        instrument_id=INSTRUMENT_A,
        listed_at=0,
        delisted_at=None,
        member_from=0,
        member_until=None,
        available_time=0,
        source_sequence=1,
        supersedes_revision_id=None,
    )
    static_view = view(
        DECISION_LATE,
        supplied_revisions=(static_revision,),
        kind=UniverseKind.STATIC,
    )
    empty = view(DECISION_LATE, supplied_revisions=())
    before_selection = select_universe(before)
    hidden_selection = select_universe(before_with_hidden)
    corrected_selection = select_universe(corrected)
    repeated_selection = select_universe(repeated)
    return {
        "schema_version": 1,
        "fixture_id": "point-in-time-universe-membership-v1",
        "before_correction": {
            "view_hash": before.view_hash,
            "selection": before_selection.to_canonical_dict(),
        },
        "at_correction": {
            "view_hash": corrected.view_hash,
            "selection": corrected_selection.to_canonical_dict(),
        },
        "future_and_unrelated_noninterference": {
            "view_hash_matches": before.view_hash == before_with_hidden.view_hash,
            "selection_hash_matches": before_selection.selection_hash
            == hidden_selection.selection_hash,
        },
        "input_repeat_parity": {
            "view_hash_matches": before.view_hash == repeated.view_hash,
            "selection_hash_matches": before_selection.selection_hash
            == repeated_selection.selection_hash,
        },
        "static_universe": select_universe(static_view).to_canonical_dict(),
        "empty_success": select_universe(empty).to_canonical_dict(),
        "failure_controls": _failure_controls(),
        "limitations": [
            "no_universe-completeness-claim",
            "no_survivorship-safety-claim",
            "no_bar-window-semantics",
            "no_strategy-invocation",
            "no_deployment-authorization",
        ],
    }


def test_point_in_time_universe_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11C golden fixture: {error}") from error
    assert _payload() == expected
