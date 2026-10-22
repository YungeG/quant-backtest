"""Native clock regression with synthetic financial preparation, no Engine run."""
from dataclasses import replace

import pytest
import crypto_quant_domain as d
from crypto_quant_backtest.cn_a_share_portfolio_standard_native_state_v1 import (
    _native_signal_target_v1, _native_rebalance_plan_v1,
)
from tests.runtime.providers.test_cn_a_share_portfolio_standard_native_state_v1 import _live_prefix, _target


def test_native_profile_phase50_rejected_before_coordinator45_and_original_clock_is_compatible():
    source, batch, book, streams, schedules, rules = _live_prefix()
    event = _target(source, 1)
    original = source.signal_marks[1]
    def signal_at(phase):
        at = d.SimulationInstant(original.at.instant, replace(original.at.phase, rank=phase), original.at.source_sequence)
        marks = replace(original, at=at, marks=tuple(replace(mark, resolved_at_instant=at) for mark in original.marks))
        inputs = replace(source, signal_marks=(source.signal_marks[0], marks))
        target = replace(event, phase=at.phase, source_sequence=at.source_sequence)
        return _native_signal_target_v1(inputs=inputs, journal=batch.journal, event=target), inputs
    at = d.SimulationInstant(event.event_time, d.TimelinePhase(45, "cn_standard_native"), d.SourceSequence(0))
    late, late_inputs = signal_at(50)
    assert late.normalized_target.materialized_instant is not None
    assert late.normalized_target.materialized_instant.phase.rank == 50
    with pytest.raises(ValueError, match="native rebalance source account or full-clock mismatch"):
        _native_rebalance_plan_v1(inputs=late_inputs, signal=late, journal=batch.journal,
            settlement_book=book, order_streams=streams, reservation_schedules=schedules,
            market_rules=rules, at=at)
    assert original.at.phase.rank < 45
    early, early_inputs = signal_at(original.at.phase.rank)
    plan = _native_rebalance_plan_v1(inputs=early_inputs, signal=early, journal=batch.journal,
        settlement_book=book, order_streams=streams, reservation_schedules=schedules,
        market_rules=rules, at=at)
    assert len(plan.planned_orders) == 2
    assert late.snapshot.equity == early.snapshot.equity
    assert tuple(t.decision.final_quantity for t in late.normalized_target.targets) == tuple(t.decision.final_quantity for t in early.normalized_target.targets)
    assert len(batch.fills) == 2  # planner generated no additional fills
