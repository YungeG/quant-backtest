from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    BAR_CLOSE_CAPABILITY, BAR_CLOSE_EVENT_TYPE, BarCloseCandidate, BarCloseObservation,
    BarLiquidityEvidence, NextBarCloseFailure, NextBarCloseFailureCode,
    NextBarCloseRequest, NextEligibleBarCloseModel, NoEligibleBarAction,
)
from crypto_quant_domain import SourceSequence, TimelinePhase, TimeInForce, UtcInstant
from crypto_quant_market_data import MarketEvent
from tests.runtime.execution._fixtures import accepted_journey, execution_approvals


def _event(instant: int, *, available: int | None = None) -> MarketEvent:
    order = accepted_journey()["order"]
    return MarketEvent(
        event_id=f"bar-close:{instant}", stream_key="bars.close", event_type=BAR_CLOSE_EVENT_TYPE,
        capability=BAR_CLOSE_CAPABILITY, instrument_id=order.intent.instrument_id,
        event_time=UtcInstant(instant), available_time=UtcInstant(instant if available is None else available),
        phase=TimelinePhase(60, "bar_close"), source_sequence=SourceSequence(1), revision_id="rev-1",
        supersedes_revision_id=None, source_key="synthetic.bar-close.v1", source_hash="sha256:" + "73" * 32,
        payload={"schema_version": 1, "bar_kind": "real", "close_price": {"units": 3_100_000, "scale": 2, "quote_currency": "USD"},
                 "interval_start": UtcInstant(instant - 300_000_000_000).to_canonical_dict(),
                 "interval_end_exclusive": UtcInstant(instant).to_canonical_dict()}, 
    )


def _candidate(instant: int = 300) -> BarCloseCandidate:
    event = _event(instant)
    market, risk = execution_approvals()
    return BarCloseCandidate(BarCloseObservation.from_event(event), market, risk,
        BarLiquidityEvidence.create(evidence_key="test", evidence_version=1, market_event=event,
            evaluated_at=event.available_time, approved=True, reason_code=None, source_hash="sha256:" + "74" * 32),
        replace(__import__("tests.runtime.execution._fixtures", fromlist=["candidate"]).candidate().market_state,
            source_event_id=event.event_id, available_at=event.available_time))


def _model() -> NextEligibleBarCloseModel:
    return NextEligibleBarCloseModel.create(actions=tuple((tif, NoEligibleBarAction.EXPIRE if tif in {TimeInForce.DAY, TimeInForce.IOC, TimeInForce.FOK} else NoEligibleBarAction.KEEP_ACTIVE) for tif in TimeInForce))


def test_close_fills_only_real_closed_bar_after_order_state() -> None:
    stream = accepted_journey()["accepted_stream"]
    outcome = _model().simulate_execution(NextBarCloseRequest(stream, _candidate(), False))
    assert outcome.result is not None and outcome.result.reference_price is not None
    assert outcome.result.reference_price.mark.price.units == 3_100_000
    same_candidate = _candidate()
    same = _model().simulate_execution(NextBarCloseRequest(stream, replace(
        same_candidate, observation=BarCloseObservation.from_event(_event(stream.state.updated_at.instant.epoch_nanoseconds)),
        market_rule_approval=None, pretrade_risk_approval=None, liquidity_evidence=None, market_state=None), False))
    assert isinstance(same.failure, NextBarCloseFailure)
    assert same.failure.code is NextBarCloseFailureCode.SAME_BAR_FORBIDDEN


def test_close_payload_timing_and_window_tif_fail_closed() -> None:
    with pytest.raises(ValueError, match="available"):
        BarCloseObservation.from_event(_event(300, available=301))
    valid = BarCloseObservation.from_event(_event(300))
    malformed = replace(
        valid.event,
        payload={
            **valid.event.payload,
            "interval_start": UtcInstant(1).to_canonical_dict(),
        },
    )
    with pytest.raises(ValueError, match="exact available"):
        BarCloseObservation(malformed, valid.kind, valid.close_price)
    stream = accepted_journey()["accepted_stream"]
    day = _model().simulate_execution(NextBarCloseRequest(stream, None, True)).result
    assert day is not None and day.action is NoEligibleBarAction.EXPIRE
