from __future__ import annotations

from collections.abc import Mapping

from crypto_quant_backtest import (
    StrategyCheckpoint,
    StrategyState,
    StrategyStateTransition,
)
from crypto_quant_domain import (
    CanonicalSchema,
    SimulationInstant,
    SourceSequence,
    StrategySleeveId,
    TimelinePhase,
    UtcInstant,
)


STRATEGY_ID = StrategySleeveId("portfolio.momentum")
STATE_SCHEMA = CanonicalSchema("strategy.portfolio-momentum.state", 1)
DECISION_PHASE = TimelinePhase(80, "strategy_decision")
FIRST_DECISION = SimulationInstant(UtcInstant(100), DECISION_PHASE, SourceSequence(1))
SECOND_DECISION = SimulationInstant(UtcInstant(200), DECISION_PHASE, SourceSequence(1))


def state(values: Mapping[str, object]) -> StrategyState:
    return StrategyState(
        strategy_id=STRATEGY_ID,
        state_schema=STATE_SCHEMA,
        values=values,
    )


def advance(current: StrategyState, occurred_at: SimulationInstant) -> tuple[
    StrategyStateTransition, StrategyState
]:
    count = current.values["count"]
    history = current.values["history"]
    if type(count) is not int or not isinstance(history, tuple):
        raise AssertionError("fixture state shape changed")
    updated = state(
        {
            "history": (*history, occurred_at.instant.epoch_nanoseconds),
            "count": count + 1,
        }
    )
    return (
        StrategyStateTransition(
            transition_key=f"decision-{count + 1}",
            occurred_at=occurred_at,
            before_state=current,
            after_state=updated,
        ),
        updated,
    )


def checkpoint(current: StrategyState) -> StrategyCheckpoint:
    return StrategyCheckpoint(
        checkpoint_key="warmup-complete",
        captured_at=FIRST_DECISION,
        state=current,
    )
