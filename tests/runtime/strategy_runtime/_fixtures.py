from __future__ import annotations

from dataclasses import dataclass, replace

from crypto_quant_backtest import (
    ArtifactInstallMode,
    BuildArtifactRef,
    BuildArtifactRole,
    ModelArtifactRef,
    ModelRevisionTimeline,
    NamedBarWindowResult,
    NamedRandomStream,
    PointInTimeObservationQueryResult,
    PortfolioStrategyInvocationContext,
    PortfolioStrategyInvocationOutput,
    PortfolioStrategyRegistration,
    SourceTreeState,
    StrategyCheckpoint,
    StrategyState,
    TimelineSegment,
    TimelineWindow,
    UniverseSelection,
)
from crypto_quant_domain import (
    InstrumentCatalog,
    InstrumentId,
    SimulationInstant,
    SourceSequence,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import AtomicDecisionBatchCollector, DecisionBatchExpectation
from tests.kernel.decisions._fixtures import CARRY, TREND, submission
from tests.kernel.validation._fixtures import BTC, ETH, catalog
from tests.runtime.decision_schedule._fixtures import (
    ACTIVE_INSTANT,
    WARMUP_INSTANT,
    bar_window,
    entry,
    requirement,
    schedule,
)
from tests.runtime.model_revisions._fixtures import select_model, timeline
from tests.runtime.observation_windows._fixtures import backing_result
from tests.runtime.random_streams._fixtures import stream
from tests.runtime.strategy_state._fixtures import STATE_SCHEMA
from tests.runtime.universe._fixtures import revision, select_universe, view


GENESIS_INSTANT = SimulationInstant(
    UtcInstant(0),
    TimelinePhase(0, "genesis"),
    SourceSequence(0),
)
DECISION_INSTANT = WARMUP_INSTANT
SAME_UTC_LATER = SimulationInstant(
    DECISION_INSTANT.instant,
    TimelinePhase(60, "decision"),
    SourceSequence(1),
)


def instrument_catalog() -> InstrumentCatalog:
    return catalog()


def active_eligibility(decision_instant: SimulationInstant = DECISION_INSTANT):
    active_entry = entry(decision_instant, TimelineSegment.ACTIVE_TRADING)
    current = schedule(
        entries=(active_entry,),
        window_value=TimelineWindow(UtcInstant(0), UtcInstant(200), UtcInstant(500)),
    )
    return current.eligibility(
        active_entry,
        (bar_window(decision_instant=decision_instant),),
    )


def same_utc_active_eligibilities():
    entries = (
        entry(DECISION_INSTANT, TimelineSegment.ACTIVE_TRADING),
        entry(SAME_UTC_LATER, TimelineSegment.ACTIVE_TRADING),
    )
    current = schedule(
        entries=entries,
        window_value=TimelineWindow(UtcInstant(0), UtcInstant(200), UtcInstant(500)),
    )
    return tuple(
        current.eligibility(
            current_entry,
            (bar_window(decision_instant=current_entry.decision_instant),),
        )
        for current_entry in entries
    )


def warmup_eligibility():
    current = schedule()
    return current.eligibility(current.entries[0], (bar_window(),))


def ineligible_eligibility():
    current_entry = entry(DECISION_INSTANT, TimelineSegment.ACTIVE_TRADING)
    current = schedule(
        entries=(current_entry,),
        requirements=(requirement(3),),
        window_value=TimelineWindow(UtcInstant(0), UtcInstant(200), UtcInstant(500)),
    )
    return current.eligibility(
        current_entry,
        (bar_window(decision_instant=DECISION_INSTANT),),
    )


def universe_selection(
    decision_instant: SimulationInstant = DECISION_INSTANT,
) -> UniverseSelection:
    roots = (
        revision(
            "btc-membership",
            "btc-v1",
            instrument_id=BTC,
            listed_at=0,
            delisted_at=None,
            member_from=0,
            member_until=None,
            available_time=100,
            source_sequence=1,
            supersedes_revision_id=None,
        ),
        revision(
            "eth-membership",
            "eth-v1",
            instrument_id=ETH,
            listed_at=0,
            delisted_at=None,
            member_from=0,
            member_until=None,
            available_time=100,
            source_sequence=1,
            supersedes_revision_id=None,
        ),
    )
    return select_universe(view(decision_instant, supplied_revisions=roots))


def state_for(
    expectation: DecisionBatchExpectation, *, count: int = 0
) -> StrategyState:
    return StrategyState(
        strategy_id=expectation.sleeve_id,
        state_schema=STATE_SCHEMA,
        values={"count": count, "history": ()},
    )


def stream_for(
    expectation: DecisionBatchExpectation, *, counter: int = 0
) -> NamedRandomStream:
    return stream(strategy_id=expectation.sleeve_id, counter=counter)


def candidate_for(
    expectation: DecisionBatchExpectation,
    instrument_id: InstrumentId,
    value: str,
    *,
    context_hash: str,
    decision_instant: SimulationInstant = DECISION_INSTANT,
) -> StrategyDecisionCandidate:
    decision_time = decision_instant.instant.epoch_nanoseconds
    return StrategyDecisionCandidate(
        StrategyDecisionPayload(
            {
                "schema_version": 1,
                "strategy_id": expectation.strategy_id,
                "sleeve_id": expectation.sleeve_id.value,
                "decision_time": decision_time,
                "observed_through": 150,
                "effective_time": decision_time,
                "expires_at": 300,
                "targets": (
                    {
                        "instrument_id": {
                            "venue": instrument_id.venue.value,
                            "stable_key": instrument_id.stable_key,
                        },
                        "value": value,
                    },
                ),
                "confidence": None,
                "reason": "scheduled rebalance",
                "evidence": {"context_hash": context_hash},
            }
        )
    )


def strategy_artifact(expectation: DecisionBatchExpectation) -> BuildArtifactRef:
    return BuildArtifactRef(
        role=BuildArtifactRole.DECISION_SOURCE,
        artifact_key=f"{expectation.strategy_id}.strategy",
        artifact_version="1",
        install_mode=ArtifactInstallMode.WHEEL,
        source_tree_state=SourceTreeState.CLEAN,
        content_hash=canonical_sha256(
            {
                "type": "recording_strategy_fixture",
                "implementation_version": 1,
                "strategy_id": expectation.strategy_id,
            }
        ),
        source_snapshot_hash=None,
    )


def observation_results(
    decision_instant: SimulationInstant = DECISION_INSTANT,
) -> tuple[PointInTimeObservationQueryResult, ...]:
    result = backing_result()
    if result.decision_instant != decision_instant:
        result = replace(
            result,
            decision_instant=decision_instant,
            trace=replace(result.trace, decision_instant=decision_instant),
        )
    return (result,)


def windows(
    decision_instant: SimulationInstant = DECISION_INSTANT,
) -> tuple[NamedBarWindowResult, ...]:
    return (bar_window(decision_instant=decision_instant),)


def selected_models(
    decision_instant: SimulationInstant = DECISION_INSTANT,
) -> tuple[ModelArtifactRef, ...]:
    selected = select_model(timeline(decision_instant))
    assert selected is not None
    return (selected,)


def selected_model_timelines(
    decision_instant: SimulationInstant = DECISION_INSTANT,
) -> tuple[ModelRevisionTimeline, ...]:
    return (timeline(decision_instant),)


@dataclass
class RecordingStrategy:
    expectation: DecisionBatchExpectation
    strategy_artifact: BuildArtifactRef
    instrument_id: InstrumentId
    value: str
    call_order: list[str]
    mode: str = "valid"
    calls: int = 0
    state_increment: int = 1
    stream_draws: int = 1

    def decide(
        self,
        *,
        context: PortfolioStrategyInvocationContext,
        previous_state: StrategyState,
    ) -> object:
        self.calls += 1
        self.call_order.append(self.expectation.strategy_id)
        if self.mode == "callback":
            raise RuntimeError("unstable callback detail must not enter identity")
        if self.mode == "output":
            return object()

        candidate_instrument = (
            InstrumentId(self.instrument_id.venue, "linear_perpetual:unknown-usdt")
            if self.mode == "validation"
            else self.instrument_id
        )
        candidate = candidate_for(
            self.expectation,
            candidate_instrument,
            self.value,
            context_hash=context.context_hash,
            decision_instant=context.eligibility.entry.decision_instant,
        )
        count = previous_state.values["count"]
        if type(count) is not int:
            raise AssertionError("fixture state shape changed")
        after_state: object = StrategyState(
            strategy_id=previous_state.strategy_id,
            state_schema=previous_state.state_schema,
            values={
                "count": count + self.state_increment,
                "history": (
                    *previous_state.values["history"],
                    context.eligibility.entry.decision_instant.instant
                    .epoch_nanoseconds,
                ),
            },
        )
        if self.mode == "state":
            after_state = object()
        drawn_streams = context.random_streams
        for _ in range(self.stream_draws):
            drawn_streams = tuple(
                random_stream.draw_u64()[1] for random_stream in drawn_streams
            )
        next_streams: object = object() if self.mode == "streams" else drawn_streams
        return candidate, after_state, next_streams


def registration(
    expectation: DecisionBatchExpectation,
    strategy: object,
    *,
    decision_instant: SimulationInstant = DECISION_INSTANT,
    previous_checkpoint: StrategyCheckpoint | None = None,
    previous_output: PortfolioStrategyInvocationOutput | None = None,
    random_streams: tuple[NamedRandomStream, ...] | None = None,
) -> PortfolioStrategyRegistration:
    checkpoint = previous_checkpoint or StrategyCheckpoint(
        checkpoint_key=f"genesis:{expectation.sleeve_id.value}",
        captured_at=GENESIS_INSTANT,
        state=state_for(expectation),
    )
    return PortfolioStrategyRegistration(
        expectation=expectation,
        strategy_artifact=strategy_artifact(expectation),
        strategy=strategy,
        observation_results=observation_results(decision_instant),
        universe=universe_selection(decision_instant),
        windows=windows(decision_instant),
        previous_checkpoint=checkpoint,
        random_streams=(
            (stream_for(expectation),) if random_streams is None else random_streams
        ),
        model_timelines=selected_model_timelines(decision_instant),
        previous_output=previous_output,
    )


def valid_strategies(
    call_order: list[str] | None = None,
) -> tuple[RecordingStrategy, RecordingStrategy]:
    order = [] if call_order is None else call_order
    return (
        RecordingStrategy(TREND, strategy_artifact(TREND), BTC, "0.5", order),
        RecordingStrategy(CARRY, strategy_artifact(CARRY), ETH, "-0.25", order),
    )


def registrations_for(
    strategies: tuple[RecordingStrategy, RecordingStrategy],
) -> tuple[PortfolioStrategyRegistration, ...]:
    trend, carry = strategies
    return registration(TREND, trend), registration(CARRY, carry)


def with_mismatched_universe(
    registration_value: PortfolioStrategyRegistration,
) -> PortfolioStrategyRegistration:
    universe = registration_value.universe
    return replace(
        registration_value,
        universe=replace(
            universe,
            query=replace(universe.query, decision_instant=ACTIVE_INSTANT),
        ),
    )


def same_time_prior_decision_state():
    result = AtomicDecisionBatchCollector().collect(
        decision_time=DECISION_INSTANT.instant,
        expected=(CARRY, TREND),
        submissions=(
            submission(CARRY, decision_time=200, instrument_id=ETH),
            submission(TREND, decision_time=200, instrument_id=BTC),
        ),
    )
    assert result.state is not None
    return result.state
