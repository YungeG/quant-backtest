from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    InstrumentCatalog,
    InstrumentId,
    SimulationInstant,
    StrategyDecision,
    StrategyDecisionCandidate,
    StrategySleeveId,
    canonical_sha256,
)
from crypto_quant_trading import (
    AtomicDecisionBatchCollector,
    AtomicDecisionBatchResult,
    DecisionBatchExpectation,
    DecisionBatchSubmission,
    LatestSleeveDecisionState,
    StrategyOutputValidationContext,
    StrategyOutputValidator,
    StrategyValidationResult,
)

from .decision_schedule import WarmupEligibility
from .model_revisions import ModelArtifactRef, ModelRevisionTimeline
from .observation_windows import NamedBarWindowResult
from .observations import PointInTimeObservationQueryResult
from .random_streams import NamedRandomStream
from .resolution import BuildArtifactRef, BuildArtifactRole
from .strategy_state import StrategyCheckpoint, StrategyState, StrategyStateTransition
from .timeline import TimelineSegment
from .universe import UniverseSelection


_SCHEMA_VERSION = 1

__all__ = (
    "PortfolioStrategyInvocation",
    "PortfolioStrategyInvocationContext",
    "PortfolioStrategyInvocationFailureCode",
    "PortfolioStrategyInvocationOutput",
    "PortfolioStrategyInvocationStatus",
    "PortfolioStrategyRegistration",
    "invoke_portfolio_strategies",
)


def _sha256(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _typed_tuple(name: str, values: object, item_type: type) -> tuple[Any, ...]:
    if type(values) is not tuple or any(
        type(value) is not item_type for value in values
    ):
        raise TypeError(f"{name} must be tuple of {item_type.__name__}")
    return values


def _strategy_artifact(value: object) -> BuildArtifactRef:
    if type(value) is not BuildArtifactRef:
        raise TypeError("strategy_artifact must be BuildArtifactRef")
    if value.role is not BuildArtifactRole.DECISION_SOURCE:
        raise ValueError("strategy_artifact role must be DECISION_SOURCE")
    if not value.has_immutable_identity:
        raise ValueError("strategy_artifact requires immutable content identity")
    return value


def _strategy_object_artifact(strategy: object) -> BuildArtifactRef:
    try:
        value = getattr(strategy, "strategy_artifact")
    except Exception as error:
        raise TypeError("strategy must expose strategy_artifact") from error
    return _strategy_artifact(value)


def _model_timelines(name: str, values: object) -> tuple[ModelRevisionTimeline, ...]:
    timelines = _typed_tuple(name, values, ModelRevisionTimeline)
    selected: list[tuple[ModelArtifactRef, ModelRevisionTimeline]] = []
    for timeline in timelines:
        artifact = timeline.select()
        if artifact is None:
            raise ValueError(f"{name} must select terminal model artifacts")
        selected.append((artifact, timeline))
    ordered = tuple(
        timeline
        for _, timeline in sorted(
            selected,
            key=lambda pair: (pair[0].model_key, pair[1].timeline_hash),
        )
    )
    model_keys = [artifact.model_key for artifact, _ in selected]
    if len(model_keys) != len(set(model_keys)):
        raise ValueError("model timeline keys must be unique")
    return ordered


def _invocation_evidence(
    *,
    observations: object,
    windows: object,
    streams: object,
    timelines: object,
    sleeve_id: StrategySleeveId,
) -> tuple[
    tuple[PointInTimeObservationQueryResult, ...],
    tuple[NamedBarWindowResult, ...],
    tuple[NamedRandomStream, ...],
    tuple[ModelRevisionTimeline, ...],
]:
    ordered_observations = tuple(
        sorted(
            _typed_tuple(
                "observation_results",
                observations,
                PointInTimeObservationQueryResult,
            ),
            key=lambda value: (value.query.query_hash, value.result_hash),
        )
    )
    ordered_windows = tuple(
        sorted(
            _typed_tuple("windows", windows, NamedBarWindowResult),
            key=lambda value: (value.query.query_hash, value.result_hash),
        )
    )
    ordered_streams = tuple(
        sorted(
            _typed_tuple("random_streams", streams, NamedRandomStream),
            key=lambda value: (value.stream_key, value.stream_hash),
        )
    )
    ordered_timelines = _model_timelines("model_timelines", timelines)
    identities = (
        (
            "observation Queries",
            [value.query.query_hash for value in ordered_observations],
        ),
        ("window Queries", [value.query.query_hash for value in ordered_windows]),
        ("random stream keys", [value.stream_key for value in ordered_streams]),
    )
    duplicate = next(
        (name for name, values in identities if len(values) != len(set(values))),
        None,
    )
    if duplicate is not None:
        raise ValueError(f"{duplicate} must be unique")
    if any(value.strategy_id != sleeve_id for value in ordered_streams):
        raise ValueError("random stream Sleeve must match expectation")
    return (
        ordered_observations,
        ordered_windows,
        ordered_streams,
        ordered_timelines,
    )


@dataclass(frozen=True, slots=True)
class PortfolioStrategyRegistration:
    expectation: DecisionBatchExpectation
    strategy_artifact: BuildArtifactRef
    strategy: object
    observation_results: tuple[PointInTimeObservationQueryResult, ...]
    universe: UniverseSelection
    windows: tuple[NamedBarWindowResult, ...]
    previous_checkpoint: StrategyCheckpoint
    random_streams: tuple[NamedRandomStream, ...]
    model_timelines: tuple[ModelRevisionTimeline, ...]
    previous_output: PortfolioStrategyInvocationOutput | None = field(
        default=None, kw_only=True
    )

    def __post_init__(self) -> None:
        if type(self.expectation) is not DecisionBatchExpectation:
            raise TypeError("expectation must be DecisionBatchExpectation")
        artifact = _strategy_artifact(self.strategy_artifact)
        if self.strategy is None:
            raise TypeError("strategy must be an object")
        if _strategy_object_artifact(self.strategy) != artifact:
            raise ValueError("strategy artifact must match executed strategy")
        if type(self.universe) is not UniverseSelection:
            raise TypeError("universe must be UniverseSelection")
        if type(self.previous_checkpoint) is not StrategyCheckpoint:
            raise TypeError("previous_checkpoint must be StrategyCheckpoint")
        if self.previous_state.strategy_id != self.expectation.sleeve_id:
            raise ValueError("previous state Sleeve must match expectation")
        observations, windows, streams, timelines = _invocation_evidence(
            observations=self.observation_results,
            windows=self.windows,
            streams=self.random_streams,
            timelines=self.model_timelines,
            sleeve_id=self.expectation.sleeve_id,
        )
        if self.previous_output is None:
            if any(value.counter != 0 for value in streams):
                raise ValueError(
                    "genesis random streams must start at counter zero or use a "
                    "prior invocation handoff"
                )
        else:
            if type(self.previous_output) is not PortfolioStrategyInvocationOutput:
                raise TypeError(
                    "previous_output must be PortfolioStrategyInvocationOutput or None"
                )
            if self.previous_output.status not in {
                PortfolioStrategyInvocationStatus.WARMUP_SUCCEEDED,
                PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED,
            }:
                raise ValueError(
                    "previous output must be a successful invocation handoff"
                )
            matching = tuple(
                value
                for value in self.previous_output.invocations
                if value.context.expectation == self.expectation
            )
            if len(matching) != 1:
                raise ValueError(
                    "previous output must exact-cover registration expectation"
                )
            previous_invocation = matching[0]
            transition = previous_invocation.state_transition
            if transition is None:  # pragma: no cover - successful output validates
                raise ValueError("previous invocation must contain a state transition")
            if (
                self.previous_checkpoint.checkpoint_key
                != previous_invocation.invocation_hash
                or self.previous_checkpoint.captured_at != transition.occurred_at
                or self.previous_checkpoint.state != transition.after_state
            ):
                raise ValueError("previous checkpoint must match previous invocation")
            if streams != previous_invocation.next_random_streams:
                raise ValueError(
                    "random streams must match previous invocation handoff"
                )
        object.__setattr__(self, "observation_results", observations)
        object.__setattr__(self, "windows", windows)
        object.__setattr__(self, "random_streams", streams)
        object.__setattr__(self, "model_timelines", timelines)

    @property
    def previous_state(self) -> StrategyState:
        return self.previous_checkpoint.state

    @property
    def previous_input_instant(self) -> SimulationInstant:
        return self.previous_checkpoint.captured_at

    @property
    def previous_checkpoint_hash(self) -> str:
        return self.previous_checkpoint.checkpoint_hash

    @property
    def previous_output_hash(self) -> str | None:
        return (
            None if self.previous_output is None else self.previous_output.output_hash
        )


@dataclass(frozen=True, slots=True)
class PortfolioStrategyInvocationContext:
    expectation: DecisionBatchExpectation
    eligibility: WarmupEligibility
    observation_results: tuple[PointInTimeObservationQueryResult, ...]
    universe: UniverseSelection
    windows: tuple[NamedBarWindowResult, ...]
    previous_target: StrategyDecision | None
    previous_state_hash: str
    previous_input_instant: SimulationInstant
    previous_checkpoint_hash: str
    previous_output_hash: str | None
    random_streams: tuple[NamedRandomStream, ...]
    model_timelines: tuple[ModelRevisionTimeline, ...]
    instrument_catalog_hash: str

    def __post_init__(self) -> None:
        if type(self.expectation) is not DecisionBatchExpectation:
            raise TypeError("expectation must be DecisionBatchExpectation")
        if type(self.eligibility) is not WarmupEligibility:
            raise TypeError("eligibility must be WarmupEligibility")
        if type(self.universe) is not UniverseSelection:
            raise TypeError("universe must be UniverseSelection")
        observations, windows, streams, timelines = _invocation_evidence(
            observations=self.observation_results,
            windows=self.windows,
            streams=self.random_streams,
            timelines=self.model_timelines,
            sleeve_id=self.expectation.sleeve_id,
        )
        if (
            self.previous_target is not None
            and type(self.previous_target) is not StrategyDecision
        ):
            raise TypeError("previous_target must be StrategyDecision or None")
        if self.previous_target is not None:
            if (
                self.previous_target.target_snapshot.sleeve_id
                != self.expectation.sleeve_id
            ):
                raise ValueError("previous_target Sleeve must match expectation")
            decision_instant = self.eligibility.entry.decision_instant
            if (
                self.previous_target.decision_instant >= decision_instant
                if self.previous_target.decision_instant is not None
                else self.previous_target.decision_time >= decision_instant.instant
            ):
                raise ValueError("previous_target must be before decision instant")
        _sha256("previous_state_hash", self.previous_state_hash)
        if type(self.previous_input_instant) is not SimulationInstant:
            raise TypeError("previous_input_instant must be SimulationInstant")
        if self.previous_input_instant >= self.eligibility.entry.decision_instant:
            raise ValueError("previous strategy input must be before decision instant")
        _sha256("previous_checkpoint_hash", self.previous_checkpoint_hash)
        if self.previous_output_hash is not None:
            _sha256("previous_output_hash", self.previous_output_hash)
        _sha256("instrument_catalog_hash", self.instrument_catalog_hash)
        _context_evidence(self, observations, windows, timelines)
        object.__setattr__(self, "observation_results", observations)
        object.__setattr__(self, "windows", windows)
        object.__setattr__(self, "random_streams", streams)
        object.__setattr__(self, "model_timelines", timelines)

    def _body(self) -> dict[str, object]:
        return {
            "type": "portfolio_strategy_invocation_context",
            "schema_version": _SCHEMA_VERSION,
            "expectation": self.expectation,
            "schedule_hash": self.eligibility.schedule_hash,
            "entry": self.eligibility.entry,
            "eligibility_hash": self.eligibility.eligibility_hash,
            "observation_results": [
                {
                    "query_hash": value.query.query_hash,
                    "result_hash": value.result_hash,
                    "trace_hash": value.trace.trace_hash,
                }
                for value in self.observation_results
            ],
            "universe_selection_hash": self.universe.selection_hash,
            "window_results": [
                {
                    "query_hash": value.query.query_hash,
                    "result_hash": value.result_hash,
                    "causality_trace_hash": value.causality_trace.trace_hash,
                }
                for value in self.windows
            ],
            "previous_target_hash": (
                None
                if self.previous_target is None
                else canonical_sha256(self.previous_target)
            ),
            "previous_state_hash": self.previous_state_hash,
            "previous_input_instant": self.previous_input_instant,
            "previous_checkpoint_hash": self.previous_checkpoint_hash,
            "previous_output_hash": self.previous_output_hash,
            "random_stream_hashes": [
                value.stream_hash for value in self.random_streams
            ],
            "model_selections": [
                _model_selection_dict(value) for value in self.model_timelines
            ],
            "instrument_catalog_hash": self.instrument_catalog_hash,
        }

    @property
    def context_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "context_hash": self.context_hash}


class PortfolioStrategyInvocationFailureCode(str, Enum):
    CALLBACK_FAILED = "callback_failed"
    INVALID_OUTPUT = "invalid_output"
    INVALID_STATE = "invalid_state"
    INVALID_RANDOM_STREAMS = "invalid_random_streams"


@dataclass(frozen=True, slots=True)
class PortfolioStrategyInvocation:
    context: PortfolioStrategyInvocationContext
    strategy_artifact: BuildArtifactRef
    validation_result: StrategyValidationResult | None
    state_transition: StrategyStateTransition | None
    next_random_streams: tuple[NamedRandomStream, ...]
    failure_code: PortfolioStrategyInvocationFailureCode | None

    def __post_init__(self) -> None:
        if type(self.context) is not PortfolioStrategyInvocationContext:
            raise TypeError("context must be PortfolioStrategyInvocationContext")
        _strategy_artifact(self.strategy_artifact)
        result = self.validation_result
        if result is not None and type(result) is not StrategyValidationResult:
            raise TypeError(
                "validation_result must be StrategyValidationResult or None"
            )
        transition = self.state_transition
        if transition is not None and type(transition) is not StrategyStateTransition:
            raise TypeError("state_transition must be StrategyStateTransition or None")
        streams = tuple(
            sorted(
                _typed_tuple(
                    "next_random_streams",
                    self.next_random_streams,
                    NamedRandomStream,
                ),
                key=lambda value: (value.stream_key, value.stream_hash),
            )
        )
        if self.failure_code is not None and not isinstance(
            self.failure_code, PortfolioStrategyInvocationFailureCode
        ):
            raise TypeError("invalid failure_code")

        expectation = self.context.expectation
        if result is not None and result.decision is not None:
            decision = result.decision
            if (
                decision.strategy_id != expectation.strategy_id
                or decision.target_snapshot.sleeve_id != expectation.sleeve_id
                or decision.decision_time
                != self.context.eligibility.entry.decision_instant.instant
                or decision.decision_instant
                != self.context.eligibility.entry.decision_instant
            ):
                raise ValueError("validation result must match invocation context")
        if transition is not None:
            if (
                transition.transition_key
                != f"{expectation.strategy_id}:{expectation.sleeve_id.value}"
                or transition.occurred_at
                != self.context.eligibility.entry.decision_instant
                or transition.before_state_hash != self.context.previous_state_hash
                or transition.before_state.strategy_id != expectation.sleeve_id
            ):
                raise ValueError("state transition must match invocation context")
        if transition is None and streams:
            raise ValueError("random stream evidence requires a state transition")

        if self.failure_code in {
            PortfolioStrategyInvocationFailureCode.CALLBACK_FAILED,
            PortfolioStrategyInvocationFailureCode.INVALID_OUTPUT,
        } and (result is not None or transition is not None or streams):
            raise ValueError("callback/output failure cannot claim completed evidence")
        if (
            self.failure_code is PortfolioStrategyInvocationFailureCode.INVALID_STATE
            and (result is None or transition is not None or streams)
        ):
            raise ValueError("invalid state requires validation evidence only")
        if (
            self.failure_code
            is PortfolioStrategyInvocationFailureCode.INVALID_RANDOM_STREAMS
            and (result is None or streams)
        ):
            raise ValueError(
                "invalid RNG output requires validation and state evidence"
            )
        if self.failure_code is None and result is None:
            if transition is not None or streams:
                raise ValueError("uninvoked record cannot claim completed evidence")
        elif self.failure_code is None and result is not None:
            if transition is None:
                raise ValueError(
                    "completed callback requires state transition evidence"
                )
            _next_streams(self.context.random_streams, streams)
        elif (
            self.failure_code
            is PortfolioStrategyInvocationFailureCode.INVALID_RANDOM_STREAMS
        ):
            if transition is None:
                raise ValueError("invalid RNG output requires valid state evidence")
        object.__setattr__(self, "next_random_streams", streams)

    def _body(self) -> dict[str, object]:
        return {
            "type": "portfolio_strategy_invocation",
            "schema_version": _SCHEMA_VERSION,
            "context": self.context,
            "strategy_artifact": self.strategy_artifact,
            "validation_result": _validation_dict(self.validation_result),
            "state_transition": self.state_transition,
            "next_random_stream_hashes": [
                value.stream_hash for value in self.next_random_streams
            ],
            "failure_code": None
            if self.failure_code is None
            else self.failure_code.value,
        }

    @property
    def invocation_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "invocation_hash": self.invocation_hash}


class PortfolioStrategyInvocationStatus(str, Enum):
    INELIGIBLE = "ineligible"
    INVOCATION_FAILED = "invocation_failed"
    VALIDATION_FAILED = "validation_failed"
    WARMUP_SUCCEEDED = "warmup_succeeded"
    BATCH_FAILED = "batch_failed"
    ACTIVE_SUCCEEDED = "active_succeeded"


@dataclass(frozen=True, slots=True)
class PortfolioStrategyInvocationOutput:
    eligibility: WarmupEligibility
    instrument_catalog_hash: str
    status: PortfolioStrategyInvocationStatus
    invocations: tuple[PortfolioStrategyInvocation, ...]
    batch_result: AtomicDecisionBatchResult | None
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if type(self.eligibility) is not WarmupEligibility:
            raise TypeError("eligibility must be WarmupEligibility")
        _sha256("instrument_catalog_hash", self.instrument_catalog_hash)
        if not isinstance(self.status, PortfolioStrategyInvocationStatus):
            raise TypeError("status must be PortfolioStrategyInvocationStatus")
        invocations = _typed_tuple(
            "invocations", self.invocations, PortfolioStrategyInvocation
        )
        if not invocations:
            raise ValueError("invocations must exact-cover nonempty registrations")
        if (
            self.batch_result is not None
            and type(self.batch_result) is not AtomicDecisionBatchResult
        ):
            raise TypeError("batch_result must be AtomicDecisionBatchResult or None")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G11I grade flags must remain false")
        keys = tuple(
            (
                value.context.expectation.strategy_id,
                value.context.expectation.sleeve_id.value,
            )
            for value in invocations
        )
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("invocations must use canonical unique expectation order")
        if any(
            value.context.eligibility != self.eligibility
            or value.context.instrument_catalog_hash != self.instrument_catalog_hash
            for value in invocations
        ):
            raise ValueError("invocation Context must match output authority")

        uninvoked = tuple(
            value
            for value in invocations
            if value.validation_result is None and value.failure_code is None
        )
        callback_failures = tuple(
            value for value in invocations if value.failure_code is not None
        )
        validation_failures = tuple(
            value
            for value in invocations
            if value.validation_result is not None
            and value.validation_result.failure is not None
        )
        valid = tuple(
            value
            for value in invocations
            if value.failure_code is None
            and value.validation_result is not None
            and value.validation_result.decision is not None
            and value.state_transition is not None
        )
        eligible = self.eligibility.strategy_invocation_eligible
        warmup = self.eligibility.entry.segment is TimelineSegment.WARMUP
        active = self.eligibility.entry.segment is TimelineSegment.ACTIVE_TRADING

        invalid = {
            PortfolioStrategyInvocationStatus.INELIGIBLE: bool(
                eligible
                or len(uninvoked) != len(invocations)
                or self.batch_result is not None
            ),
            PortfolioStrategyInvocationStatus.INVOCATION_FAILED: bool(
                not eligible
                or not callback_failures
                or uninvoked
                or self.batch_result is not None
            ),
            PortfolioStrategyInvocationStatus.VALIDATION_FAILED: bool(
                not eligible
                or callback_failures
                or uninvoked
                or not validation_failures
                or self.batch_result is not None
            ),
            PortfolioStrategyInvocationStatus.WARMUP_SUCCEEDED: bool(
                not eligible
                or not warmup
                or len(valid) != len(invocations)
                or validation_failures
                or self.batch_result is not None
            ),
            PortfolioStrategyInvocationStatus.BATCH_FAILED: bool(
                not eligible
                or not active
                or len(valid) != len(invocations)
                or validation_failures
                or self.batch_result is None
                or self.batch_result.failure is None
            ),
            PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED: bool(
                not eligible
                or not active
                or len(valid) != len(invocations)
                or validation_failures
                or self.batch_result is None
                or self.batch_result.batch is None
                or self.batch_result.state is None
            ),
        }[self.status]
        if invalid:
            raise ValueError(f"invalid {self.status.value} authority shape")
        _batch_exact_cover(self)

    @property
    def handoff_hash(self) -> str | None:
        if self.status is not PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED:
            return None
        result = self.batch_result
        if result is None or result.batch is None or result.state is None:
            raise ValueError("active success requires atomic batch and state")
        return canonical_sha256(
            {
                "type": "portfolio_strategy_handoff",
                "schema_version": _SCHEMA_VERSION,
                "entry": self.eligibility.entry,
                "eligibility_hash": self.eligibility.eligibility_hash,
                "instrument_catalog_hash": self.instrument_catalog_hash,
                "invocation_hashes": [
                    value.invocation_hash for value in self.invocations
                ],
                "batch_hash": result.batch_hash,
                "decision_state_hash": result.state_hash,
            }
        )

    def _body(self) -> dict[str, object]:
        return {
            "type": "portfolio_strategy_invocation_output",
            "schema_version": _SCHEMA_VERSION,
            "status": self.status.value,
            "schedule_hash": self.eligibility.schedule_hash,
            "entry": self.eligibility.entry,
            "eligibility_hash": self.eligibility.eligibility_hash,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "invocations": self.invocations,
            "batch_result": _batch_dict(self.batch_result),
            "handoff_hash": self.handoff_hash,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def output_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "output_hash": self.output_hash}


@dataclass(slots=True)
class _StagedInvocation:
    registration: PortfolioStrategyRegistration
    context: PortfolioStrategyInvocationContext
    candidate: StrategyDecisionCandidate | None = None
    transition: StrategyStateTransition | None = None
    next_random_streams: tuple[NamedRandomStream, ...] = ()
    failure_code: PortfolioStrategyInvocationFailureCode | None = None
    validation_result: StrategyValidationResult | None = None


def invoke_portfolio_strategies(
    *,
    eligibility: WarmupEligibility,
    instrument_catalog: InstrumentCatalog,
    registrations: tuple[PortfolioStrategyRegistration, ...],
    prior_decision_state: LatestSleeveDecisionState | None = None,
) -> PortfolioStrategyInvocationOutput:
    if type(eligibility) is not WarmupEligibility:
        raise TypeError("eligibility must be WarmupEligibility")
    if type(instrument_catalog) is not InstrumentCatalog:
        raise TypeError("instrument_catalog must be InstrumentCatalog")
    _typed_tuple("registrations", registrations, PortfolioStrategyRegistration)
    if not registrations:
        raise ValueError("registrations must be nonempty")
    if (
        prior_decision_state is not None
        and type(prior_decision_state) is not LatestSleeveDecisionState
    ):
        raise TypeError(
            "prior_decision_state must be LatestSleeveDecisionState or None"
        )
    decision_instant = eligibility.entry.decision_instant
    decision_time = decision_instant.instant
    if prior_decision_state is not None and prior_decision_state.as_of is not None:
        if (
            prior_decision_state.as_of_instant >= decision_instant
            if prior_decision_state.as_of_instant is not None
            else prior_decision_state.as_of >= decision_time
        ):
            raise ValueError("prior_decision_state must be before decision instant")

    ordered = tuple(
        sorted(
            registrations,
            key=lambda value: (
                value.expectation.strategy_id,
                value.expectation.sleeve_id.value,
            ),
        )
    )
    if len({value.expectation.sleeve_id for value in ordered}) != len(ordered):
        raise ValueError("registrations must use unique Sleeves")
    _validate_previous_handoffs(ordered, prior_decision_state)

    catalog_hash = canonical_sha256(instrument_catalog)
    known_instruments = {
        definition.instrument_id for definition in instrument_catalog.instruments
    }
    previous_targets = {
        value.target_snapshot.sleeve_id: value
        for value in (
            () if prior_decision_state is None else prior_decision_state.decisions
        )
    }
    staged: list[_StagedInvocation] = []
    for registration in ordered:
        _cross_evidence(registration, known_instruments)
        staged.append(
            _StagedInvocation(
                registration=registration,
                context=PortfolioStrategyInvocationContext(
                    expectation=registration.expectation,
                    eligibility=eligibility,
                    observation_results=registration.observation_results,
                    universe=registration.universe,
                    windows=registration.windows,
                    previous_target=previous_targets.get(
                        registration.expectation.sleeve_id
                    ),
                    previous_state_hash=registration.previous_state.state_hash,
                    previous_input_instant=registration.previous_input_instant,
                    previous_checkpoint_hash=registration.previous_checkpoint_hash,
                    previous_output_hash=registration.previous_output_hash,
                    random_streams=registration.random_streams,
                    model_timelines=registration.model_timelines,
                    instrument_catalog_hash=catalog_hash,
                ),
            )
        )

    if not eligibility.strategy_invocation_eligible:
        return _output(
            eligibility,
            catalog_hash,
            PortfolioStrategyInvocationStatus.INELIGIBLE,
            _records(staged),
            None,
        )

    for item in staged:
        try:
            decide = getattr(item.registration.strategy, "decide")
            if not callable(decide):
                raise TypeError("strategy decide must be callable")
            raw = decide(
                context=item.context,
                previous_state=item.registration.previous_state,
            )
        except Exception:
            item.failure_code = PortfolioStrategyInvocationFailureCode.CALLBACK_FAILED
            continue
        if (
            type(raw) is not tuple
            or len(raw) != 3
            or type(raw[0]) is not StrategyDecisionCandidate
        ):
            item.failure_code = PortfolioStrategyInvocationFailureCode.INVALID_OUTPUT
            continue
        candidate, after_state, next_streams = raw
        item.candidate = candidate
        if type(after_state) is not StrategyState:
            item.failure_code = PortfolioStrategyInvocationFailureCode.INVALID_STATE
            continue
        try:
            item.transition = _transition(item.registration, eligibility, after_state)
        except (TypeError, ValueError):
            item.failure_code = PortfolioStrategyInvocationFailureCode.INVALID_STATE
            continue
        if type(next_streams) is not tuple or any(
            type(value) is not NamedRandomStream for value in next_streams
        ):
            item.failure_code = (
                PortfolioStrategyInvocationFailureCode.INVALID_RANDOM_STREAMS
            )
            continue
        try:
            item.next_random_streams = _next_streams(
                item.registration.random_streams,
                next_streams,
            )
        except (TypeError, ValueError):
            item.failure_code = (
                PortfolioStrategyInvocationFailureCode.INVALID_RANDOM_STREAMS
            )

    validator = StrategyOutputValidator()
    submissions: list[DecisionBatchSubmission] = []
    for item in staged:
        if item.candidate is None:
            continue
        item.validation_result = validator.validate(
            item.candidate,
            StrategyOutputValidationContext(
                expected_strategy_id=item.registration.expectation.strategy_id,
                expected_sleeve_id=item.registration.expectation.sleeve_id,
                decision_time=eligibility.entry.decision_instant.instant,
                instrument_catalog=instrument_catalog,
                universe=item.registration.universe.instruments,
                decision_instant=decision_instant,
            ),
        )
        submissions.append(
            DecisionBatchSubmission(
                expectation=item.registration.expectation,
                result=item.validation_result,
            )
        )

    if any(item.failure_code is not None for item in staged):
        return _output(
            eligibility,
            catalog_hash,
            PortfolioStrategyInvocationStatus.INVOCATION_FAILED,
            _records(staged),
            None,
        )
    if any(
        item.validation_result is not None
        and item.validation_result.failure is not None
        for item in staged
    ):
        return _output(
            eligibility,
            catalog_hash,
            PortfolioStrategyInvocationStatus.VALIDATION_FAILED,
            _records(staged),
            None,
        )
    if eligibility.entry.segment is TimelineSegment.WARMUP:
        return _output(
            eligibility,
            catalog_hash,
            PortfolioStrategyInvocationStatus.WARMUP_SUCCEEDED,
            _records(staged),
            None,
        )

    batch_result = AtomicDecisionBatchCollector().collect(
        decision_time=decision_time,
        expected=tuple(value.expectation for value in ordered),
        submissions=tuple(submissions),
        prior_state=prior_decision_state,
        decision_instant=decision_instant,
    )
    succeeded = batch_result.failure is None
    return _output(
        eligibility,
        catalog_hash,
        (
            PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED
            if succeeded
            else PortfolioStrategyInvocationStatus.BATCH_FAILED
        ),
        _records(staged),
        batch_result,
    )


def _validate_previous_handoffs(
    registrations: tuple[PortfolioStrategyRegistration, ...],
    prior_decision_state: LatestSleeveDecisionState | None,
) -> None:
    for registration in registrations:
        previous_output = registration.previous_output
        if (
            previous_output is None
            or previous_output.status
            is not PortfolioStrategyInvocationStatus.ACTIVE_SUCCEEDED
        ):
            continue
        result = previous_output.batch_result
        if result is None or result.state is None:  # pragma: no cover - validated
            raise ValueError("active previous output requires decision state")
        if prior_decision_state != result.state:
            raise ValueError(
                "prior decision state must match previous invocation handoff"
            )


def _model_selection_dict(timeline: ModelRevisionTimeline) -> dict[str, str]:
    artifact = timeline.select()
    if artifact is None:  # pragma: no cover - constructor rejects empty timelines
        raise ValueError("model timeline must select a terminal artifact")
    return {
        "timeline_hash": timeline.timeline_hash,
        "artifact_ref_hash": artifact.artifact_ref_hash,
    }


def _context_evidence(
    context: PortfolioStrategyInvocationContext,
    observations: tuple[PointInTimeObservationQueryResult, ...],
    windows: tuple[NamedBarWindowResult, ...],
    timelines: tuple[ModelRevisionTimeline, ...],
) -> None:
    instant = context.eligibility.entry.decision_instant
    if context.universe.query.decision_instant != instant:
        raise ValueError("Universe Decision Instant must match eligibility entry")
    if any(value.decision_instant != instant for value in observations):
        raise ValueError("observation Decision Instant must match eligibility entry")
    if any(value.query.decision_instant != instant for value in windows):
        raise ValueError("window Decision Instant must match eligibility entry")
    selected = [value.select() for value in timelines]
    if any(value is None or value.available_at > instant for value in selected):
        raise ValueError("model artifact cannot be available after eligibility entry")
    if {value.result_hash for value in windows} != {
        value.window_result_hash for value in context.eligibility.coverage
    }:
        raise ValueError("window evidence must match eligibility coverage")
    traces = {value.trace.trace_hash for value in observations}
    if any(value.causality_trace.trace_hash not in traces for value in windows):
        raise ValueError("window causality must reference observation results")


def _cross_evidence(
    registration: PortfolioStrategyRegistration,
    known_instruments: set[InstrumentId],
) -> None:
    if not set(registration.universe.instruments) <= known_instruments:
        raise ValueError("Universe contains Instrument outside catalog")


def _transition(
    registration: PortfolioStrategyRegistration,
    eligibility: WarmupEligibility,
    after_state: StrategyState,
) -> StrategyStateTransition:
    before_state = registration.previous_state
    if after_state.strategy_id != registration.expectation.sleeve_id:
        raise ValueError("returned StrategyState Sleeve must match expectation")
    if after_state.state_schema != before_state.state_schema:
        raise ValueError("returned StrategyState schema must match previous state")
    return StrategyStateTransition(
        transition_key=(
            f"{registration.expectation.strategy_id}:"
            f"{registration.expectation.sleeve_id.value}"
        ),
        occurred_at=eligibility.entry.decision_instant,
        before_state=before_state,
        after_state=after_state,
    )


def _next_streams(
    before: tuple[NamedRandomStream, ...],
    after: tuple[NamedRandomStream, ...],
) -> tuple[NamedRandomStream, ...]:
    ordered = tuple(
        sorted(after, key=lambda value: (value.stream_key, value.stream_hash))
    )
    before_by_key = {value.stream_key: value for value in before}
    after_by_key = {value.stream_key: value for value in ordered}
    if len(after_by_key) != len(ordered) or set(before_by_key) != set(after_by_key):
        raise ValueError("returned random stream keys must match previous streams")
    for key, previous in before_by_key.items():
        current = after_by_key[key]
        if (
            current.master_random_seed != previous.master_random_seed
            or current.strategy_id != previous.strategy_id
            or current.algorithm != previous.algorithm
            or current.algorithm_version != previous.algorithm_version
            or current.counter < previous.counter
        ):
            raise ValueError("returned random stream continuity is invalid")
    return ordered


def _records(
    staged: list[_StagedInvocation],
) -> tuple[PortfolioStrategyInvocation, ...]:
    return tuple(
        PortfolioStrategyInvocation(
            context=value.context,
            strategy_artifact=value.registration.strategy_artifact,
            validation_result=value.validation_result,
            state_transition=value.transition,
            next_random_streams=value.next_random_streams,
            failure_code=value.failure_code,
        )
        for value in staged
    )


def _batch_exact_cover(output: PortfolioStrategyInvocationOutput) -> None:
    result = output.batch_result
    if result is None:
        return
    decision_instant = output.eligibility.entry.decision_instant
    decision_time = decision_instant.instant
    if result.failure is not None:
        if (
            result.failure.decision_time != decision_time
            or result.failure.decision_instant != decision_instant
        ):
            raise ValueError("batch failure must match output decision instant")
        return
    batch = result.batch
    state = result.state
    if batch is None or state is None:  # pragma: no cover - result validates its shape
        raise ValueError("successful batch result requires batch and state")
    if (
        batch.decision_time != decision_time
        or batch.decision_instant != decision_instant
        or state.as_of != decision_time
        or state.as_of_instant != decision_instant
    ):
        raise ValueError("batch result must match output decision instant")

    invocation_decisions = {
        (
            value.context.expectation.strategy_id,
            value.context.expectation.sleeve_id,
        ): value.validation_result.decision
        for value in output.invocations
        if value.validation_result is not None
        and value.validation_result.decision is not None
    }
    batch_decisions = {
        (value.strategy_id, value.target_snapshot.sleeve_id): value
        for value in batch.decisions
    }
    if invocation_decisions != batch_decisions:
        raise ValueError("batch must exact-cover invocation decisions")
    expected_batch_id = "decision-batch-v2:" + canonical_sha256(
        {
            "type": "decision_batch_identity",
            "schema_version": 2,
            "decision_instant": decision_instant.to_canonical_dict(),
            "decisions": [
                value.to_canonical_dict()
                for value in sorted(
                    batch.decisions,
                    key=lambda value: (
                        value.target_snapshot.sleeve_id,
                        value.strategy_id,
                    ),
                )
            ],
        }
    )
    if batch.decision_batch_id != expected_batch_id:
        raise ValueError("batch identity must match invocation decisions")
    state_decisions = {
        (value.strategy_id, value.target_snapshot.sleeve_id): value
        for value in state.decisions
    }
    if any(
        state_decisions.get(key) != value for key, value in batch_decisions.items()
    ):
        raise ValueError("decision state must contain the atomic batch")
    for key in state_decisions.keys() - batch_decisions.keys():
        previous = state_decisions[key]
        if (
            previous.decision_instant >= decision_instant
            if previous.decision_instant is not None
            else previous.decision_time >= decision_time
        ):
            raise ValueError("unscheduled decision state must be from a prior instant")


def _output(
    eligibility: WarmupEligibility,
    catalog_hash: str,
    status: PortfolioStrategyInvocationStatus,
    invocations: tuple[PortfolioStrategyInvocation, ...],
    batch_result: AtomicDecisionBatchResult | None,
) -> PortfolioStrategyInvocationOutput:
    return PortfolioStrategyInvocationOutput(
        eligibility=eligibility,
        instrument_catalog_hash=catalog_hash,
        status=status,
        invocations=invocations,
        batch_result=batch_result,
    )


def _validation_dict(
    value: StrategyValidationResult | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {"decision": value.decision, "failure": value.failure}


def _batch_dict(value: AtomicDecisionBatchResult | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {"batch": value.batch, "state": value.state, "failure": value.failure}
