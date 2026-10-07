from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    InputDecodeIssueCode,
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
    TimelineEvent,
    TimelineSegment,
)
from crypto_quant_domain import (
    CurrencyId, InstrumentCatalog, InstrumentDefinition, InstrumentId, InstrumentType,
    StrategySleeveId, UtcInstant, VenueId,
)
from crypto_quant_market_data import MarketBundleCapability
from crypto_quant_trading import DecisionBatchExpectation
from tests.runtime.target_stream._fixtures import (
    BTC,
    CARRY,
    DECISION_TIME,
    ETH,
    TREND,
    candidate_payload,
    context,
    empty_state,
    event,
    source_events,
    timeline_events,
)


def stream(events=None) -> PrecomputedTargetStream:
    return PrecomputedTargetStream(
        stream_key="targets",
        events=source_events() if events is None else events,
    )


def schedule(
    *, segment: TimelineSegment = TimelineSegment.ACTIVE_TRADING
) -> TargetStreamDecisionSchedule:
    return TargetStreamDecisionSchedule(
        decision_time=DECISION_TIME,
        segment=segment,
        entries=(
            TargetStreamScheduleEntry("target-trend", TREND, context(TREND)),
            TargetStreamScheduleEntry("target-carry", CARRY, context(CARRY)),
        ),
    )


def test_stream_digest_and_active_batch_are_input_order_independent() -> None:
    direct = stream()
    reversed_stream = stream(tuple(reversed(source_events())))
    adapter = PrecomputedTargetStreamAdapter()

    first = adapter.inject(
        stream=direct,
        timeline_events=timeline_events(),
        schedule=schedule(),
        prior_state=empty_state(),
    )
    second = adapter.inject(
        stream=reversed_stream,
        timeline_events=tuple(reversed(timeline_events())),
        schedule=TargetStreamDecisionSchedule(
            decision_time=DECISION_TIME,
            segment=TimelineSegment.ACTIVE_TRADING,
            entries=tuple(reversed(schedule().entries)),
        ),
        prior_state=empty_state(),
    )

    assert direct.target_stream_digest == reversed_stream.target_stream_digest
    assert first.injection is not None and second.injection is not None
    assert first.injection.batch.decision_batch_id == second.injection.batch.decision_batch_id
    assert first.injection.batch_hash == second.injection.batch_hash
    assert first.injection.state_hash == second.injection.state_hash
    assert first.injection.target_stream_digest == direct.target_stream_digest
    assert len(first.injection.batch.decisions) == 2


def test_multi_instrument_target_snapshot_uses_existing_public_value_path() -> None:
    """Input-only probe: does not grant CN multi-stock fills or fees."""
    candidate = candidate_payload(TREND, instrument_id=BTC, value="0.4")
    candidate["targets"] = [
        {"instrument_id": {"venue": BTC.venue.value, "stable_key": BTC.stable_key}, "value": "0.4"},
        {"instrument_id": {"venue": ETH.venue.value, "stable_key": ETH.stable_key}, "value": "0.6"},
    ]
    multi = event(
        "target-trend", TREND, instrument_id=BTC, value="0.4", source_sequence=1,
        payload_override={"schema_version": 1, "candidate": candidate},
    )
    carry = source_events()[1]
    result = PrecomputedTargetStreamAdapter().inject(
        stream=stream((multi, carry)),
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, multi),
                         TimelineEvent(TimelineSegment.ACTIVE_TRADING, carry)),
        schedule=schedule(), prior_state=empty_state(),
    )
    assert result.injection is not None and result.validation_failures == ()
    [decision] = [d for d in result.injection.batch.decisions if d.strategy_id == TREND.strategy_id]
    assert {t.instrument_id: t.units for t in decision.target_snapshot.targets} == {
        BTC: 400_000_000_000, ETH: 600_000_000_000,
    }

def test_empty_target_snapshot_is_cash_intent_not_a_fill() -> None:
    """A target value cannot prove liquidation of an existing position."""
    candidate = candidate_payload(TREND, instrument_id=BTC, value="0")
    candidate["targets"] = []
    empty = event(
        "target-trend", TREND, instrument_id=BTC, value="0", source_sequence=1,
        payload_override={"schema_version": 1, "candidate": candidate},
    )
    carry = source_events()[1]
    result = PrecomputedTargetStreamAdapter().inject(
        stream=stream((empty, carry)),
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, empty),
                         TimelineEvent(TimelineSegment.ACTIVE_TRADING, carry)),
        schedule=schedule(), prior_state=empty_state(),
    )
    assert result.injection is not None and result.validation_failures == ()
    [decision] = [d for d in result.injection.batch.decisions if d.strategy_id == TREND.strategy_id]
    assert decision.target_snapshot.targets == ()

def test_shsz_two_equity_targets_and_cash_target_are_input_only() -> None:
    """No CN fee, account, fill or next-open authority is supplied by this test."""
    sh = InstrumentId(VenueId("xshg"), "600272")
    sz = InstrumentId(VenueId("xshe"), "000705")
    cny = CurrencyId("CNY")
    cn_catalog = InstrumentCatalog(
        currencies=(cny,),
        instruments=tuple(InstrumentDefinition(iid, InstrumentType.EQUITY, None, cny, cny) for iid in (sh, sz)),
        symbol_timelines=(),
    )
    cn_schedule = replace(schedule(), entries=tuple(
        replace(entry, validation_context=replace(
            entry.validation_context, instrument_catalog=cn_catalog, universe=(sh, sz),
        )) for entry in schedule().entries
    ))
    equity = candidate_payload(TREND, instrument_id=sh, value="0.5")
    equity["targets"] = [
        {"instrument_id": {"venue": iid.venue.value, "stable_key": iid.stable_key}, "value": "0.5"}
        for iid in (sh, sz)
    ]
    cash = candidate_payload(CARRY, instrument_id=sh, value="0")
    cash["targets"] = []
    buys = event("target-trend", TREND, instrument_id=sh, value="0.5", source_sequence=1,
                 payload_override={"schema_version": 1, "candidate": equity})
    flat = event("target-carry", CARRY, instrument_id=sh, value="0", source_sequence=2,
                 payload_override={"schema_version": 1, "candidate": cash})
    result = PrecomputedTargetStreamAdapter().inject(
        stream=stream((buys, flat)),
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, buys),
                         TimelineEvent(TimelineSegment.ACTIVE_TRADING, flat)),
        schedule=cn_schedule, prior_state=empty_state(),
    )
    assert result.injection is not None and result.validation_failures == ()
    decisions = {item.strategy_id: item for item in result.injection.batch.decisions}
    assert {item.instrument_id: item.units for item in decisions[TREND.strategy_id].target_snapshot.targets} == {
        sh: 500_000_000_000, sz: 500_000_000_000,
    }
    assert decisions[CARRY.strategy_id].target_snapshot.targets == ()

def test_malformed_envelope_is_input_decode_failure_not_validation_failure() -> None:
    malformed = event(
        "target-trend",
        TREND,
        instrument_id=BTC,
        value="0.5",
        source_sequence=1,
        payload_override={"schema_version": 1, "unexpected": {}},
    )
    valid = source_events()[1]
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream((malformed, valid)),
        timeline_events=(
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, malformed),
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, valid),
        ),
        schedule=schedule(),
        prior_state=empty_state(),
    )

    assert outcome.decode_failure is not None
    assert outcome.validation_failures == ()
    assert outcome.injection is None
    assert {issue.code for issue in outcome.decode_failure.issues} == {
        InputDecodeIssueCode.MISSING_ENVELOPE_FIELD,
        InputDecodeIssueCode.UNKNOWN_ENVELOPE_FIELD,
    }


def test_decoded_candidate_validation_failure_is_preserved() -> None:
    invalid_payload = {
        "schema_version": 1,
        "candidate": {
            **candidate_payload(TREND, instrument_id=BTC, value="0.5"),
            "targets": [
                {
                    "instrument_id": {
                        "venue": BTC.venue.value,
                        "stable_key": BTC.stable_key,
                    },
                    "value": "0.1234567890123",
                }
            ],
        },
    }
    invalid = event(
        "target-trend",
        TREND,
        instrument_id=BTC,
        value="0.5",
        source_sequence=1,
        payload_override=invalid_payload,
    )
    valid = source_events()[1]
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream((invalid, valid)),
        timeline_events=(
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, invalid),
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, valid),
        ),
        schedule=schedule(),
        prior_state=empty_state(),
    )

    assert outcome.decode_failure is None
    assert outcome.injection is None
    assert len(outcome.validation_failures) == 1
    failure = outcome.validation_failures[0]
    assert failure.event_id == "target-trend"
    assert failure.validation_failure.candidate_payload_hash.startswith("sha256:")
    assert failure.validation_failure.issues


def test_missing_active_event_is_atomic_batch_failure() -> None:
    trend = source_events()[0]
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream(),
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, trend),),
        schedule=schedule(),
        prior_state=empty_state(),
    )

    assert outcome.batch_failure is not None
    assert outcome.injection is None
    assert outcome.decode_failure is None
    assert outcome.validation_failures == ()
    assert any(
        issue.subject_key == CARRY.sleeve_id.value
        for issue in outcome.batch_failure.issues
    )


def test_warmup_validates_then_suppresses_without_state_or_batch() -> None:
    prior_state = empty_state()
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream(),
        timeline_events=timeline_events(segment=TimelineSegment.WARMUP),
        schedule=schedule(segment=TimelineSegment.WARMUP),
        prior_state=prior_state,
    )

    assert outcome.suppression is not None
    assert outcome.suppression.prior_state_hash == prior_state.state_hash
    assert outcome.injection is None
    assert outcome.batch_failure is None
    assert outcome.validation_failures == ()


def test_mixed_segment_and_unexpected_event_fail_closed() -> None:
    trend, carry = source_events()
    mixed = (
        TimelineEvent(TimelineSegment.WARMUP, trend),
        TimelineEvent(TimelineSegment.ACTIVE_TRADING, carry),
    )
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream(),
        timeline_events=mixed,
        schedule=schedule(),
        prior_state=empty_state(),
    )
    assert outcome.decode_failure is not None
    assert InputDecodeIssueCode.TIMELINE_SEGMENT_MISMATCH in {
        issue.code for issue in outcome.decode_failure.issues
    }

    extra_expectation = DecisionBatchExpectation(
        "extra-v1", StrategySleeveId("extra.primary")
    )
    extra = event(
        "target-extra",
        extra_expectation,
        instrument_id=ETH,
        value="0.1",
        source_sequence=3,
    )
    extra_outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream((*source_events(), extra)),
        timeline_events=(
            *timeline_events(),
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, extra),
        ),
        schedule=schedule(),
        prior_state=empty_state(),
    )
    assert extra_outcome.decode_failure is not None
    assert InputDecodeIssueCode.UNEXPECTED_EVENT in {
        issue.code for issue in extra_outcome.decode_failure.issues
    }


def test_schedule_rejects_untrusted_context_mismatch() -> None:
    wrong = DecisionBatchExpectation("wrong-v1", TREND.sleeve_id)
    with pytest.raises(ValueError, match="context identity"):
        TargetStreamScheduleEntry("target-trend", wrong, context(TREND))

    with pytest.raises(ValueError, match="decision time"):
        TargetStreamDecisionSchedule(
            decision_time=UtcInstant(101),
            segment=TimelineSegment.ACTIVE_TRADING,
            entries=(TargetStreamScheduleEntry("target-trend", TREND, context(TREND)),),
        )


def test_wrong_stream_semantics_are_structured_decode_failures() -> None:
    trend = source_events()[0]
    wrong_capability = replace(
        trend, capability=MarketBundleCapability("precomputed_target_stream", 2)
    )
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream((wrong_capability, source_events()[1])),
        timeline_events=(
            TimelineEvent(TimelineSegment.ACTIVE_TRADING, wrong_capability),
            timeline_events()[1],
        ),
        schedule=schedule(),
        prior_state=empty_state(),
    )
    assert outcome.decode_failure is not None
    assert InputDecodeIssueCode.UNSUPPORTED_CAPABILITY in {
        issue.code for issue in outcome.decode_failure.issues
    }
