from __future__ import annotations

from datetime import date

import pytest

from crypto_quant_domain import (
    SessionId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
)


def test_simulation_instant_has_stable_total_order() -> None:
    market_data = TimelinePhase(rank=20, code="market_data")
    decision = TimelinePhase(rank=30, code="strategy_decision")
    instant = UtcInstant(epoch_nanoseconds=100)
    values = [
        SimulationInstant(instant, decision, SourceSequence(0)),
        SimulationInstant(instant, market_data, SourceSequence(2)),
        SimulationInstant(instant, market_data, SourceSequence(1)),
        SimulationInstant(UtcInstant(99), decision, SourceSequence(9)),
    ]

    assert sorted(values) == [values[3], values[2], values[1], values[0]]


def test_phase_code_breaks_rank_tie_deterministically() -> None:
    instant = UtcInstant(100)
    alpha = SimulationInstant(
        instant, TimelinePhase(rank=20, code="alpha"), SourceSequence(0)
    )
    beta = SimulationInstant(
        instant, TimelinePhase(rank=20, code="beta"), SourceSequence(0)
    )

    assert alpha < beta


def test_source_sequence_and_phase_validate() -> None:
    with pytest.raises(ValueError, match="SourceSequence"):
        SourceSequence(-1)
    with pytest.raises(ValueError, match="SourceSequence"):
        SourceSequence(2**63)
    with pytest.raises(ValueError, match="rank"):
        TimelinePhase(rank=-1, code="market_data")
    with pytest.raises(ValueError, match="canonical"):
        TimelinePhase(rank=1, code=" market_data ")


def test_trading_date_and_session_are_explicit_not_inferred_from_utc() -> None:
    trading_date = TradingDate(
        calendar_id="CN.XSHG", value=date(2024, 1, 2)
    )
    session = SessionId(calendar_id="CN.XSHG", value="night-2024-01-02")
    late_utc = UtcInstant(1704150000000000000)

    assert trading_date.value == date(2024, 1, 2)
    assert session.value == "night-2024-01-02"
    assert late_utc.to_canonical_dict()["epoch_nanoseconds"] != trading_date.value
    assert trading_date.to_canonical_dict() == {
        "type": "trading_date",
        "calendar_id": "CN.XSHG",
        "date": "2024-01-02",
    }
