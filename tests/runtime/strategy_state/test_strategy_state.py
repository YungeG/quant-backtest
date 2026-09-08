from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

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

from tests.runtime.strategy_state._fixtures import (
    DECISION_PHASE,
    FIRST_DECISION,
    SECOND_DECISION,
    STATE_SCHEMA,
    STRATEGY_ID,
    advance,
    checkpoint,
    state,
)


class _CanonicalLookingObject:
    def to_canonical_dict(self) -> dict[str, object]:
        return {"looks": "canonical"}


def test_canonical_state_checkpoint_restore_matches_uninterrupted_continuation() -> None:
    caller_values = {"history": [], "count": 0}
    initial = state(caller_values)
    reordered = state({"count": 0, "history": []})
    caller_values["history"].append(999)
    caller_values["count"] = 999

    assert initial.state_hash == reordered.state_hash
    assert list(initial.values) == ["count", "history"]
    assert initial.values["count"] == 0
    assert not initial.values["history"]
    with pytest.raises(TypeError):
        initial.values["count"] = 1

    first_transition, after_first = advance(initial, FIRST_DECISION)
    saved = checkpoint(after_first)
    uninterrupted_transition, uninterrupted = advance(after_first, SECOND_DECISION)
    restored_transition, restored = advance(saved.restore(), SECOND_DECISION)

    assert first_transition.before_state_hash == initial.state_hash
    assert first_transition.after_state_hash == after_first.state_hash
    assert saved.state_hash == after_first.state_hash
    assert saved.restore() is after_first
    assert restored.state_hash == uninterrupted.state_hash
    assert restored_transition.transition_hash == uninterrupted_transition.transition_hash


def test_nested_values_are_deeply_frozen_in_canonical_key_order() -> None:
    nested_list = [{"z": 1, "a": 2}]
    frozen = state({"outer": {"z": nested_list, "a": "  value  "}})
    nested_list[0]["a"] = 999

    outer = frozen.values["outer"]
    assert list(outer) == ["a", "z"]
    assert outer["a"] == "  value  "
    assert list(outer["z"][0]) == ["a", "z"]
    assert outer["z"][0]["a"] == 2
    with pytest.raises(TypeError):
        outer["z"][0]["a"] = 3


@pytest.mark.parametrize(
    "unsupported",
    (
        1.0,
        Decimal("1"),
        datetime(2025, 1, 1),
        b"state",
        {"set"},
        frozenset({"set"}),
        lambda: None,
        _CanonicalLookingObject(),
        StrategySleeveId("nested.identity"),
    ),
)
def test_state_rejects_non_json_and_runtime_values(unsupported: object) -> None:
    with pytest.raises(TypeError, match="unsupported StrategyState value"):
        state({"unsupported": unsupported})


@pytest.mark.parametrize("bad_key", ("", " padded ", 1))
def test_state_rejects_noncanonical_mapping_keys(bad_key: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        state({bad_key: 1})


def test_state_rejects_noncanonical_unicode_and_cycles() -> None:
    with pytest.raises(ValueError, match="NFC"):
        state({"value": "e\u0301"})

    cycle: list[object] = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="cyclic StrategyState"):
        state({"cycle": cycle})


def test_transition_binds_strategy_schema_instant_and_before_after_hashes() -> None:
    before = state({"count": 0, "history": []})
    after = state({"count": 1, "history": [100]})
    transition = StrategyStateTransition(
        transition_key="decision-1",
        occurred_at=FIRST_DECISION,
        before_state=before,
        after_state=after,
    )
    no_op = replace(transition, after_state=before)

    assert transition.before_state_hash == before.state_hash
    assert transition.after_state_hash == after.state_hash
    assert no_op.before_state_hash == no_op.after_state_hash
    assert list(transition.to_canonical_dict()) == [
        "type",
        "schema_version",
        "transition_key",
        "occurred_at",
        "strategy_id",
        "state_schema",
        "before_state_hash",
        "after_state_hash",
        "transition_hash",
    ]

    other_strategy = replace(
        after,
        strategy_id=StrategySleeveId("portfolio.value"),
    )
    with pytest.raises(ValueError, match="Strategy identity"):
        replace(transition, after_state=other_strategy)

    other_schema = replace(
        after,
        state_schema=CanonicalSchema(STATE_SCHEMA.name, 2),
    )
    with pytest.raises(ValueError, match="state schema"):
        replace(transition, after_state=other_schema)


def test_checkpoint_uses_full_simulation_instant_and_embeds_exact_state() -> None:
    current = state({"count": 1, "history": [100]})
    baseline = StrategyCheckpoint(
        checkpoint_key="warmup-complete",
        captured_at=FIRST_DECISION,
        state=current,
    )
    later_sequence = replace(
        baseline,
        captured_at=SimulationInstant(
            FIRST_DECISION.instant,
            DECISION_PHASE,
            SourceSequence(2),
        ),
    )
    later_phase = replace(
        baseline,
        captured_at=SimulationInstant(
            FIRST_DECISION.instant,
            TimelinePhase(81, "post_strategy_decision"),
            SourceSequence(1),
        ),
    )

    assert baseline.checkpoint_hash != later_sequence.checkpoint_hash
    assert baseline.checkpoint_hash != later_phase.checkpoint_hash
    assert baseline.to_canonical_dict()["state"] == current.to_canonical_dict()
    assert baseline.restore() is current
    with pytest.raises(TypeError, match="state must be StrategyState"):
        replace(baseline, state=object())
    with pytest.raises(TypeError, match="captured_at"):
        replace(baseline, captured_at=UtcInstant(100))
