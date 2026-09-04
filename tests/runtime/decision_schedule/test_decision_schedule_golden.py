from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import TimelineSegment
from crypto_quant_domain import canonical_bytes

from tests.runtime.decision_schedule._fixtures import (
    ACTIVE_INSTANT,
    SAME_UTC_LATER,
    bar_window,
    entry,
    requirement,
    schedule,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/decision-schedule/decision-schedule-warmup-eligibility-v1.json"
)


def _failure_controls() -> dict[str, bool]:
    current = schedule()
    current_entry = current.entries[0]
    evidence = bar_window()
    result = current.eligibility(current_entry, (evidence,))
    attempts = {
        "unsorted_entries": lambda: schedule(
            entries=(
                entry(SAME_UTC_LATER, TimelineSegment.ACTIVE_TRADING),
                entry(ACTIVE_INSTANT, TimelineSegment.ACTIVE_TRADING),
            )
        ),
        "wrong_segment": lambda: schedule(
            entries=(entry(ACTIVE_INSTANT, TimelineSegment.WARMUP),)
        ),
        "missing_evidence": lambda: current.eligibility(current_entry, ()),
        "duplicate_evidence": lambda: current.eligibility(
            current_entry, (evidence, evidence)
        ),
        "forged_lookback": lambda: replace(result, lookback_satisfied=False),
        "forged_side_effects": lambda: replace(
            result, trading_side_effects_authorized=True
        ),
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
    warmup = schedule()
    warmup_result = warmup.eligibility(warmup.entries[0], (bar_window(),))
    active_entry = entry(ACTIVE_INSTANT, TimelineSegment.ACTIVE_TRADING)
    active = schedule(entries=(active_entry,))
    active_result = active.eligibility(
        active_entry,
        (bar_window(decision_instant=ACTIVE_INSTANT),),
    )
    short = schedule(entries=(active_entry,), requirements=(requirement(3),))
    short_result = short.eligibility(
        active_entry,
        (bar_window(decision_instant=ACTIVE_INSTANT),),
    )
    empty = schedule(requirements=())
    empty_result = empty.eligibility(empty.entries[0], ())
    repeated = schedule()
    repeated_result = repeated.eligibility(repeated.entries[0], (bar_window(),))
    return {
        "schema_version": 1,
        "fixture_id": "decision-schedule-warmup-eligibility-v1",
        "warmup_schedule": warmup.to_canonical_dict(),
        "warmup_eligibility": warmup_result.to_canonical_dict(),
        "active_eligibility": active_result.to_canonical_dict(),
        "short_eligibility": short_result.to_canonical_dict(),
        "empty_requirement_eligibility": empty_result.to_canonical_dict(),
        "same_utc_distinct_entries": {
            "active": active_entry.to_canonical_dict(),
            "later": entry(
                SAME_UTC_LATER, TimelineSegment.ACTIVE_TRADING
            ).to_canonical_dict(),
            "hashes_differ": active_entry.entry_hash
            != entry(SAME_UTC_LATER, TimelineSegment.ACTIVE_TRADING).entry_hash,
        },
        "repeat_parity": {
            "schedule_hash_matches": warmup.schedule_hash == repeated.schedule_hash,
            "eligibility_hash_matches": warmup_result.eligibility_hash
            == repeated_result.eligibility_hash,
        },
        "failure_controls": _failure_controls(),
        "limitations": [
            "no_calendar_or_session_expansion",
            "no_timeline_reader_or_clock",
            "no_gap-reason-classification",
            "no_strategy-invocation",
            "no_warmup_trading-side-effects",
            "no_deployment-authorization",
        ],
    }


def test_decision_schedule_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11E golden fixture: {error}") from error
    assert json.loads(canonical_bytes(_payload())) == expected
