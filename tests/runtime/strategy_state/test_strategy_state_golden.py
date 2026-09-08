from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import StrategyCheckpoint, StrategyStateTransition
from crypto_quant_domain import (
    CanonicalSchema,
    SimulationInstant,
    SourceSequence,
    StrategySleeveId,
)

from tests.runtime.strategy_state._fixtures import (
    DECISION_PHASE,
    FIRST_DECISION,
    SECOND_DECISION,
    STATE_SCHEMA,
    advance,
    checkpoint,
    state,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/strategy-state/strategy-state-checkpoint-v1.json"
)


def _failure_controls() -> dict[str, bool]:
    initial = state({"count": 0, "history": []})
    _, after = advance(initial, FIRST_DECISION)
    transition = StrategyStateTransition(
        transition_key="decision-1",
        occurred_at=FIRST_DECISION,
        before_state=initial,
        after_state=after,
    )
    saved = checkpoint(after)
    cycle: list[object] = []
    cycle.append(cycle)
    attempts = {
        "unsupported_runtime_value": lambda: state({"bad": object()}),
        "cyclic_value": lambda: state({"cycle": cycle}),
        "cross_strategy_transition": lambda: replace(
            transition,
            after_state=replace(
                after,
                strategy_id=StrategySleeveId("portfolio.value"),
            ),
        ),
        "schema_change_transition": lambda: replace(
            transition,
            after_state=replace(
                after,
                state_schema=CanonicalSchema(STATE_SCHEMA.name, 2),
            ),
        ),
        "wrong_checkpoint_state": lambda: replace(saved, state=object()),
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
    initial = state({"history": [], "count": 0})
    reordered = state({"count": 0, "history": []})
    first_transition, after_first = advance(initial, FIRST_DECISION)
    saved = checkpoint(after_first)
    uninterrupted_transition, uninterrupted = advance(after_first, SECOND_DECISION)
    restored_transition, restored = advance(saved.restore(), SECOND_DECISION)
    later_sequence = StrategyCheckpoint(
        checkpoint_key=saved.checkpoint_key,
        captured_at=SimulationInstant(
            FIRST_DECISION.instant,
            DECISION_PHASE,
            SourceSequence(2),
        ),
        state=after_first,
    )
    repeated = checkpoint(state({"count": 1, "history": [100]}))
    return {
        "schema_version": 1,
        "fixture_id": "strategy-state-checkpoint-v1",
        "initial_state": initial.to_canonical_dict(),
        "first_transition": first_transition.to_canonical_dict(),
        "checkpoint": saved.to_canonical_dict(),
        "final_state": uninterrupted.to_canonical_dict(),
        "input_order_parity": {
            "state_hash_matches": initial.state_hash == reordered.state_hash,
            "checkpoint_hash_matches": saved.checkpoint_hash
            == repeated.checkpoint_hash,
        },
        "full_instant_identity": {
            "baseline_checkpoint_hash": saved.checkpoint_hash,
            "later_sequence_checkpoint_hash": later_sequence.checkpoint_hash,
            "differs": saved.checkpoint_hash != later_sequence.checkpoint_hash,
        },
        "restore_continuation_parity": {
            "state_hash_matches": restored.state_hash == uninterrupted.state_hash,
            "transition_hash_matches": restored_transition.transition_hash
            == uninterrupted_transition.transition_hash,
            "restore_returns_exact_state": saved.restore() is after_first,
        },
        "failure_controls": _failure_controls(),
        "limitations": [
            "no_financial_account_state",
            "no_random_stream_state",
            "no_model_lookup",
            "no_strategy_invocation",
            "no_engine_checkpoint",
        ],
    }


def test_strategy_state_checkpoint_matches_static_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G11F golden fixture: {error}") from error
    actual = json.loads(json.dumps(_payload(), sort_keys=True, default=dict))
    assert actual == expected
