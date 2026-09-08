from __future__ import annotations

from dataclasses import replace

from crypto_quant_backtest import (
    DecisionSchedule,
    DecisionScheduleEntry,
    LookbackRequirement,
    NamedBarWindowQuery,
    NamedBarWindowView,
    TimelineSegment,
    TimelineWindow,
)
from crypto_quant_domain import SimulationInstant, SourceSequence, TimelinePhase, UtcInstant

from tests.runtime.observation_windows._fixtures import backing_result, named_query, window


PHASE = TimelinePhase(20, "market_data")
WARMUP_INSTANT = SimulationInstant(UtcInstant(200), PHASE, SourceSequence(3))
ACTIVE_INSTANT = SimulationInstant(UtcInstant(250), PHASE, SourceSequence(1))
SAME_UTC_LATER = SimulationInstant(
    UtcInstant(250), TimelinePhase(60, "decision"), SourceSequence(1)
)
LAST_ACTIVE = SimulationInstant(UtcInstant(499), PHASE, SourceSequence(1))
WINDOW = TimelineWindow(UtcInstant(0), UtcInstant(250), UtcInstant(500))


def entry(
    instant: SimulationInstant = WARMUP_INSTANT,
    segment: TimelineSegment = TimelineSegment.WARMUP,
) -> DecisionScheduleEntry:
    return DecisionScheduleEntry(instant, segment)


def bar_window(
    *,
    minimum_query_count: int = 1,
    decision_instant: SimulationInstant = WARMUP_INSTANT,
):
    base = named_query(lookback_count=minimum_query_count)
    query_value = replace(base, decision_instant=decision_instant)
    backing = backing_result()
    if decision_instant != backing.decision_instant:
        backing = replace(
            backing,
            decision_instant=decision_instant,
            trace=replace(backing.trace, decision_instant=decision_instant),
        )
    return window(NamedBarWindowView(query=query_value, backing_result=backing))


def requirement(minimum_count: int = 1) -> LookbackRequirement:
    query_value: NamedBarWindowQuery = named_query(lookback_count=1)
    return LookbackRequirement(
        requirement_key="primary-bars",
        observation_query=query_value.observation_query,
        bar_definition=query_value.bar_definition,
        minimum_count=minimum_count,
    )


def schedule(
    *,
    entries: tuple[DecisionScheduleEntry, ...] | None = None,
    requirements: tuple[LookbackRequirement, ...] | None = None,
    window_value: TimelineWindow = WINDOW,
) -> DecisionSchedule:
    return DecisionSchedule(
        key="daily-close",
        version=1,
        window=window_value,
        entries=(entry(),) if entries is None else entries,
        requirements=(requirement(),) if requirements is None else requirements,
    )
