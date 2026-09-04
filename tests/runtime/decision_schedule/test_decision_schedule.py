from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import TimelineSegment, TimelineWindow
from crypto_quant_domain import SimulationInstant, SourceSequence, TimelinePhase, UtcInstant

from tests.runtime.decision_schedule._fixtures import (
    ACTIVE_INSTANT,
    LAST_ACTIVE,
    SAME_UTC_LATER,
    WARMUP_INSTANT,
    WINDOW,
    bar_window,
    entry,
    requirement,
    schedule,
)


def test_warmup_can_invoke_after_lookback_without_trading_authority() -> None:
    current = schedule()
    result = current.eligibility(current.entries[0], (bar_window(),))

    assert result.lookback_satisfied is True
    assert result.strategy_invocation_eligible is True
    assert result.trading_side_effects_authorized is False
    assert result.coverage[0].required_count == 1
    assert result.coverage[0].available_count == 2
    assert result.coverage[0].shortfall_count == 0


def test_active_authorizes_side_effects_only_when_lookback_is_satisfied() -> None:
    active = entry(ACTIVE_INSTANT, TimelineSegment.ACTIVE_TRADING)
    satisfied_schedule = schedule(entries=(active,))
    short_schedule = schedule(entries=(active,), requirements=(requirement(3),))
    evidence = bar_window(decision_instant=ACTIVE_INSTANT)

    satisfied = satisfied_schedule.eligibility(active, (evidence,))
    short = short_schedule.eligibility(active, (evidence,))

    assert satisfied.trading_side_effects_authorized is True
    assert short.lookback_satisfied is False
    assert short.strategy_invocation_eligible is False
    assert short.trading_side_effects_authorized is False
    assert short.coverage[0].shortfall_count == 1


def test_empty_requirements_are_satisfied_without_window_evidence() -> None:
    current = schedule(requirements=())
    result = current.eligibility(current.entries[0], ())

    assert result.lookback_satisfied is True
    assert result.strategy_invocation_eligible is True
    assert result.trading_side_effects_authorized is False
    assert result.coverage == ()


def test_full_instant_order_and_half_open_boundaries_are_exact() -> None:
    active = entry(ACTIVE_INSTANT, TimelineSegment.ACTIVE_TRADING)
    later = entry(SAME_UTC_LATER, TimelineSegment.ACTIVE_TRADING)
    last = entry(LAST_ACTIVE, TimelineSegment.ACTIVE_TRADING)
    current = schedule(entries=(entry(), active, later, last))

    assert current.entries == (entry(), active, later, last)
    assert active.decision_instant.instant == later.decision_instant.instant
    assert active.entry_hash != later.entry_hash
    with pytest.raises(ValueError, match="strictly increasing"):
        schedule(entries=(later, active))
    with pytest.raises(ValueError, match="half-open"):
        schedule(
            entries=(
                entry(
                    SimulationInstant(
                        WINDOW.end_exclusive,
                        TimelinePhase(20, "market_data"),
                        SourceSequence(1),
                    ),
                    TimelineSegment.ACTIVE_TRADING,
                ),
            )
        )
    with pytest.raises(ValueError, match="segment"):
        schedule(entries=(entry(ACTIVE_INSTANT, TimelineSegment.WARMUP),))


def test_requirements_are_canonical_and_unique() -> None:
    first = requirement()
    duplicate_key = replace(
        first,
        observation_query=replace(first.observation_query, dataset_key="bars.other"),
    )
    duplicate_identity = replace(first, requirement_key="other-key")

    with pytest.raises(ValueError, match="keys"):
        schedule(requirements=(first, duplicate_key))
    with pytest.raises(ValueError, match="selector/definition"):
        schedule(requirements=(first, duplicate_identity))
    with pytest.raises(ValueError, match="minimum_count"):
        replace(first, minimum_count=True)


def test_evidence_must_exact_cover_requirements_and_entry() -> None:
    current = schedule()
    current_entry = current.entries[0]
    evidence = bar_window()

    with pytest.raises(ValueError, match="exact-cover"):
        current.eligibility(current_entry, ())
    with pytest.raises(ValueError, match="unique"):
        current.eligibility(current_entry, (evidence, evidence))
    with pytest.raises(ValueError, match="Decision Instant"):
        current.eligibility(
            current_entry,
            (bar_window(decision_instant=ACTIVE_INSTANT),),
        )
    with pytest.raises(ValueError, match="exact schedule member"):
        current.eligibility(
            entry(ACTIVE_INSTANT, TimelineSegment.ACTIVE_TRADING),
            (evidence,),
        )


def test_derived_eligibility_values_fail_closed_under_replace() -> None:
    current = schedule()
    result = current.eligibility(current.entries[0], (bar_window(),))

    with pytest.raises(ValueError, match="lookback_satisfied"):
        replace(result, lookback_satisfied=False)
    with pytest.raises(ValueError, match="side_effects"):
        replace(result, trading_side_effects_authorized=True)
    with pytest.raises(ValueError, match="grade flags"):
        replace(result, deployment_authorized=True)
    with pytest.raises(ValueError, match="shortfall"):
        replace(result.coverage[0], shortfall_count=99)


def test_schedule_identity_binds_window_and_full_instant() -> None:
    baseline = schedule(requirements=())
    changed_window = schedule(
        requirements=(),
        window_value=TimelineWindow(UtcInstant(0), UtcInstant(249), UtcInstant(500)),
    )
    changed_instant = schedule(
        requirements=(),
        entries=(
            entry(
                SimulationInstant(
                    UtcInstant(200),
                    TimelinePhase(21, "later_market_data"),
                    SourceSequence(3),
                )
            ),
        ),
    )

    assert baseline.schedule_hash != changed_window.schedule_hash
    assert baseline.schedule_hash != changed_instant.schedule_hash
