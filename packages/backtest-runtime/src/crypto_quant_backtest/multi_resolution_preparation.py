from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .decision_schedule import (
    DecisionSchedule,
    DecisionScheduleEntry,
    LookbackRequirement,
    WarmupEligibility,
)
from .engine import (
    OrderEventPlan,
    ResolvedBarExecution,
    ResolvedDecisionCycle,
    ResolvedMark,
    ResolvedOrderAdmission,
    ResolvedPreTradePlan,
    SnapshotProjectionPlan,
)
from .execution import (
    BarLiquidityEvidence,
    NextBarOpenApplicability,
    NextEligibleBarOpenModel,
)
from .multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
    SignalBarBinding,
    ValuationDataBinding,
    _clock,
    _malformed,
    _record_observation,
    construct_multi_resolution_market_data_bindings,
    validate_schedule_signal_exact_cover,
    verify_visible_signal_bars,
)
from .observation_windows import (
    BarDefinitionRef,
    NamedBarWindowQuery,
    NamedBarWindowResult,
    NamedBarWindowView,
)
from .observations import (
    ObservationPurposeRef,
    ObservationQuery,
    ObservationRecord,
    PointInTimeObservationView,
    RevisionedObservationRecord,
)
from .performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
    PerformanceOutcome,
)
from .ports import SimulationComponentRef, SimulationPortType
from .resolution import ResolvedBacktestRequest
from .slippage import (
    DeterministicBpsSlippageModel,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageMarketState,
)
from .target_stream import (
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
)
from .timeline import TimelineEvent, TimelineSegment, TimelineWindow


_SCHEMA_VERSION = 1
_ROLE_SIGNAL = 0
_ROLE_EXECUTION = 1
_ROLE_VALUATION = 2
_CAPTURE_BATCH_SIZE = 128
_BAR_CAPABILITY = MarketBundleCapability("price_bars", 1)


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if (
        len(text) != 71
        or not text.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in text[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 hash")
    return text


def _optional_position(name: str, value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer or None")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _utc(value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError("instant must be exact UtcInstant")
    return UtcInstant(value.epoch_nanoseconds)


def _phase(value: object) -> TimelinePhase:
    if type(value) is not TimelinePhase:
        raise TypeError("phase must be exact TimelinePhase")
    return TimelinePhase(value.rank, value.code)


def _sequence(value: object) -> SourceSequence:
    if type(value) is not SourceSequence:
        raise TypeError("source_sequence must be exact SourceSequence")
    return SourceSequence(value.value)


def _instant(value: object) -> SimulationInstant:
    if type(value) is not SimulationInstant:
        raise TypeError("decision instant must be exact SimulationInstant")
    return SimulationInstant(_utc(value.instant), _phase(value.phase), _sequence(value.source_sequence))


def _instrument(value: object) -> InstrumentId:
    if type(value) is not InstrumentId or type(value.venue) is not VenueId:
        raise TypeError("instrument_id must be exact InstrumentId")
    return InstrumentId(VenueId(value.venue.value), value.stable_key)


def _capability(value: object) -> MarketBundleCapability:
    if type(value) is not MarketBundleCapability:
        raise TypeError("capability must be exact MarketBundleCapability")
    return MarketBundleCapability(value.key, value.version)


def _event(value: object) -> MarketEvent:
    if type(value) is not MarketEvent:
        raise TypeError("Reader batches must contain exact MarketEvent")
    return MarketEvent(
        event_id=value.event_id,
        stream_key=value.stream_key,
        event_type=value.event_type,
        capability=_capability(value.capability),
        instrument_id=None if value.instrument_id is None else _instrument(value.instrument_id),
        event_time=_utc(value.event_time),
        available_time=_utc(value.available_time),
        phase=_phase(value.phase),
        source_sequence=_sequence(value.source_sequence),
        revision_id=value.revision_id,
        supersedes_revision_id=value.supersedes_revision_id,
        source_key=value.source_key,
        source_hash=value.source_hash,
        payload=value.payload,
    )


def _stream_manifest(value: object) -> MarketStreamManifest:
    if type(value) is not MarketStreamManifest:
        raise TypeError("manifest streams must be exact MarketStreamManifest")
    return MarketStreamManifest(
        value.stream_key,
        value.event_type,
        _capability(value.capability),
        value.event_count,
        value.content_hash,
    )


def _manifest(value: object) -> MarketBundleManifest:
    if type(value) is not MarketBundleManifest:
        raise TypeError("Reader manifest must be exact MarketBundleManifest")
    if type(value.capabilities) is not tuple or type(value.streams) is not tuple:
        raise TypeError("Reader manifest collections must be exact tuples")
    return MarketBundleManifest(
        value.bundle_key,
        value.schema_version,
        _utc(value.coverage_start),
        _utc(value.coverage_end_exclusive),
        value.instrument_catalog_hash,
        tuple(_capability(item) for item in value.capabilities),
        tuple(_stream_manifest(item) for item in value.streams),
        value.content_hash,
    )


def _bundle_ref(value: object) -> MarketBundleRef:
    if type(value) is not MarketBundleRef:
        raise TypeError("bundle ref must be exact MarketBundleRef")
    return MarketBundleRef(value.bundle_key, value.manifest_hash)


def _query(value: object) -> ObservationQuery:
    if type(value) is not ObservationQuery:
        raise TypeError("observation_query must be exact ObservationQuery")
    purpose = value.purpose
    if type(purpose) is not ObservationPurposeRef:
        raise TypeError("purpose must be exact ObservationPurposeRef")
    return ObservationQuery(
        value.dataset_key,
        _instrument(value.instrument_id),
        ObservationPurposeRef(purpose.key, purpose.version),
        _capability(value.capability),
    )


def _requirement(value: object) -> LookbackRequirement:
    if type(value) is not LookbackRequirement:
        raise TypeError("requirements must contain exact LookbackRequirement")
    definition = value.bar_definition
    if type(definition) is not BarDefinitionRef:
        raise TypeError("bar_definition must be exact BarDefinitionRef")
    return LookbackRequirement(
        value.requirement_key,
        _query(value.observation_query),
        BarDefinitionRef(definition.key, definition.version, definition.definition_hash),
        value.minimum_count,
    )


def _schedule(value: object) -> DecisionSchedule:
    if type(value) is not DecisionSchedule:
        raise TypeError("schedule must be exact DecisionSchedule")
    window = value.window
    if type(window) is not TimelineWindow:
        raise TypeError("schedule window must be exact TimelineWindow")
    if type(value.entries) is not tuple or type(value.requirements) is not tuple:
        raise TypeError("schedule collections must be exact tuples")
    entries = []
    for entry in value.entries:
        if type(entry) is not DecisionScheduleEntry or type(entry.segment) is not TimelineSegment:
            raise TypeError("entries must contain exact DecisionScheduleEntry")
        entries.append(DecisionScheduleEntry(_instant(entry.decision_instant), entry.segment))
    return DecisionSchedule(
        value.key,
        value.version,
        TimelineWindow(_utc(window.data_start), _utc(window.trading_start), _utc(window.end_exclusive)),
        tuple(entries),
        tuple(_requirement(item) for item in value.requirements),
    )


@dataclass(frozen=True, slots=True)
class SignalObservationLineageBinding:
    requirement_hash: str
    event_id: str
    event_hash: str
    observation_key: str

    def __post_init__(self) -> None:
        _hash("requirement_hash", self.requirement_hash)
        _text("event_id", self.event_id)
        _hash("event_hash", self.event_hash)
        _text("observation_key", self.observation_key)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "signal_observation_lineage_binding",
            "schema_version": _SCHEMA_VERSION,
            "requirement_hash": self.requirement_hash,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "observation_key": self.observation_key,
        }


def _lineage(value: object) -> SignalObservationLineageBinding:
    if type(value) is not SignalObservationLineageBinding:
        raise TypeError("signal_lineages must contain exact SignalObservationLineageBinding")
    return SignalObservationLineageBinding(
        value.requirement_hash,
        value.event_id,
        value.event_hash,
        value.observation_key,
    )


@dataclass(frozen=True, slots=True)
class MultiResolutionMarketDataPreparation:
    decision_schedule: DecisionSchedule
    bindings: MultiResolutionMarketDataBindings
    signal_lineages: tuple[SignalObservationLineageBinding, ...]

    def __post_init__(self) -> None:
        schedule = _schedule(self.decision_schedule)
        if type(self.bindings) is not MultiResolutionMarketDataBindings:
            raise TypeError("bindings must be exact MultiResolutionMarketDataBindings")
        bindings = MultiResolutionMarketDataBindings(
            self.bindings.signal_bindings,
            self.bindings.execution_bindings,
            self.bindings.valuation_bindings,
        )
        if type(self.signal_lineages) is not tuple:
            raise TypeError("signal_lineages must be an exact tuple")
        lineages = tuple(
            sorted(
                (_lineage(value) for value in self.signal_lineages),
                key=lambda value: (
                    value.requirement_hash,
                    value.event_id,
                    value.event_hash,
                    value.observation_key,
                ),
            )
        )
        identities = tuple((value.requirement_hash, value.event_id) for value in lineages)
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate signal lineage requirement/Event identity")
        event_hashes: dict[str, str] = {}
        for value in lineages:
            previous = event_hashes.setdefault(value.event_id, value.event_hash)
            if previous != value.event_hash:
                raise ValueError("inconsistent Event hash in signal lineage")
        object.__setattr__(self, "decision_schedule", schedule)
        object.__setattr__(self, "bindings", bindings)
        object.__setattr__(self, "signal_lineages", lineages)

    @property
    def decision_schedule_hash(self) -> str:
        return self.decision_schedule.schedule_hash

    @property
    def signal_lineage_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "signal_observation_lineage_set",
                "schema_version": _SCHEMA_VERSION,
                "signal_lineages": [value.to_canonical_dict() for value in self.signal_lineages],
            }
        )

    def _canonical_body(self) -> dict[str, object]:
        rebuilt = MultiResolutionMarketDataPreparation(
            self.decision_schedule, self.bindings, self.signal_lineages
        )
        return {
            "type": "multi_resolution_market_data_preparation",
            "schema_version": _SCHEMA_VERSION,
            "decision_schedule": rebuilt.decision_schedule.to_canonical_dict(),
            "bindings": rebuilt.bindings.to_canonical_dict(),
            "signal_lineages": [value.to_canonical_dict() for value in rebuilt.signal_lineages],
        }

    @property
    def preparation_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            **self._canonical_body(),
            "decision_schedule_hash": self.decision_schedule_hash,
            "signal_lineage_hash": self.signal_lineage_hash,
            "preparation_hash": self.preparation_hash,
        }


@dataclass(frozen=True, slots=True)
class MarketDataCaseAuthority:
    decision_cycles: tuple[ResolvedDecisionCycle, ...]
    bar_executions: tuple[ResolvedBarExecution, ...]
    execution_model: NextEligibleBarOpenModel
    snapshot_plan: SnapshotProjectionPlan
    target_stream: PrecomputedTargetStream

    def __post_init__(self) -> None:
        if type(self.decision_cycles) is not tuple or any(
            type(value) is not ResolvedDecisionCycle for value in self.decision_cycles
        ):
            raise TypeError("decision_cycles must contain exact ResolvedDecisionCycle")
        if type(self.bar_executions) is not tuple or any(
            type(value) is not ResolvedBarExecution for value in self.bar_executions
        ):
            raise TypeError("bar_executions must contain exact ResolvedBarExecution")
        if type(self.execution_model) is not NextEligibleBarOpenModel:
            raise TypeError("execution_model must be exact NextEligibleBarOpenModel")
        if type(self.snapshot_plan) is not SnapshotProjectionPlan:
            raise TypeError("snapshot_plan must be exact SnapshotProjectionPlan")
        if type(self.target_stream) is not PrecomputedTargetStream:
            raise TypeError("target_stream must be exact PrecomputedTargetStream")


def _component_ref(value: object) -> SimulationComponentRef:
    if type(value) is not SimulationComponentRef:
        raise TypeError("component ref must be exact SimulationComponentRef")
    return SimulationComponentRef(
        value.port_type,
        value.component_key,
        value.component_version,
        value.component_digest,
    )


def _target_schedule(value: object) -> TargetStreamDecisionSchedule:
    if type(value) is not TargetStreamDecisionSchedule:
        raise TypeError("cycle schedule must be exact TargetStreamDecisionSchedule")
    entries = []
    for entry in value.entries:
        if type(entry) is not TargetStreamScheduleEntry:
            raise TypeError("cycle schedule entries must be exact TargetStreamScheduleEntry")
        entries.append(
            TargetStreamScheduleEntry(
                entry.event_id,
                entry.expectation,
                entry.validation_context,
            )
        )
    return TargetStreamDecisionSchedule(
        _utc(value.decision_time),
        value.segment,
        tuple(entries),
    )


def _pretrade_plan(value: object) -> ResolvedPreTradePlan:
    if type(value) is not ResolvedPreTradePlan:
        raise TypeError("pretrade_plan must be exact ResolvedPreTradePlan")
    return ResolvedPreTradePlan(
        value.order_rule_timeline,
        value.notional_evidence,
        _utc(value.market_rule_evaluated_at),
        value.fee_reservation_rule_set,
        _utc(value.fee_estimated_at),
        value.resource_commitment,
        value.requirement_source_key,
        value.requirement_source_version,
        value.requirement_source_hash,
        value.account_risk_policy,
        _utc(value.pretrade_evaluated_at),
    )


def _admission(value: object) -> ResolvedOrderAdmission:
    if type(value) is not ResolvedOrderAdmission:
        raise TypeError("admissions must contain exact ResolvedOrderAdmission")
    event_plan = []
    for event in value.event_plan:
        if type(event) is not OrderEventPlan:
            raise TypeError("admission event_plan must contain exact OrderEventPlan")
        event_plan.append(
            OrderEventPlan(
                event.event_type,
                event.event_id,
                _instant(event.occurred_at),
                event.external_evidence_id,
            )
        )
    return ResolvedOrderAdmission(
        value.order,
        value.capability_set,
        value.translation_mapping,
        _utc(value.translation_time),
        _pretrade_plan(value.pretrade_plan),
        tuple(event_plan),
    )


def _decision_cycle(value: object) -> ResolvedDecisionCycle:
    if type(value) is not ResolvedDecisionCycle:
        raise TypeError("decision_cycles must contain exact ResolvedDecisionCycle")
    return ResolvedDecisionCycle(
        _target_schedule(value.schedule),
        value.allocations,
        value.target_notional_scale,
        value.risk_policy,
        value.sizing_policy,
        value.sizing_inputs,
        value.target_validity,
        value.rebalance_policy,
        _utc(value.planning_at),
        tuple(_admission(item) for item in value.admissions),
    )


def _liquidity_evidence(value: object) -> BarLiquidityEvidence:
    if type(value) is not BarLiquidityEvidence:
        raise TypeError("liquidity_evidence must be exact BarLiquidityEvidence")
    return BarLiquidityEvidence(
        value.evidence_key,
        value.evidence_version,
        value.market_event_id,
        value.market_event_hash,
        _utc(value.evaluated_at),
        value.approved,
        value.reason_code,
        value.source_hash,
        value.evidence_id,
    )


def _market_state(value: object) -> SlippageMarketState:
    if type(value) is not SlippageMarketState:
        raise TypeError("market_state must be exact SlippageMarketState")
    return SlippageMarketState(
        value.state_key,
        _utc(value.observed_at),
        _utc(value.available_at),
        value.source_event_id,
        value.revision_id,
        value.evidence_hash,
    )


def _slippage_model(value: object) -> DeterministicBpsSlippageModel:
    if type(value) is not DeterministicBpsSlippageModel:
        raise TypeError("slippage_model must be exact DeterministicBpsSlippageModel")
    calibration = value.calibration_ref
    if type(calibration) is not SlippageCalibrationRef:
        raise TypeError("calibration_ref must be exact SlippageCalibrationRef")
    envelope = value.applicability_envelope
    if type(envelope) is not SlippageApplicabilityEnvelope:
        raise TypeError("applicability_envelope must be exact SlippageApplicabilityEnvelope")
    return DeterministicBpsSlippageModel(
        _component_ref(value.component_ref),
        SlippageCalibrationRef(
            calibration.calibration_key,
            calibration.calibration_version,
            calibration.calibration_digest,
        ),
        SlippageApplicabilityEnvelope(
            envelope.envelope_key,
            envelope.envelope_version,
            _instrument(envelope.instrument_id),
            _utc(envelope.valid_from),
            _utc(envelope.valid_to_exclusive),
            envelope.maximum_quantity,
            envelope.allowed_market_state_keys,
            envelope.config_hash,
        ),
        value.basis_points_units,
        value.basis_points_scale,
        value.rounding,
        value.limitations,
    )


def _bar_execution(value: object) -> ResolvedBarExecution:
    if type(value) is not ResolvedBarExecution:
        raise TypeError("bar_executions must contain exact ResolvedBarExecution")
    return ResolvedBarExecution(
        value.event_id,
        value.order_id,
        _pretrade_plan(value.pretrade_plan),
        _liquidity_evidence(value.liquidity_evidence),
        _market_state(value.market_state),
        _slippage_model(value.slippage_model),
        value.fill_id,
        value.fill_event_id,
        _instant(value.fill_event_at),
        value.accounting_plan,
    )


def _execution_model(value: object) -> NextEligibleBarOpenModel:
    if type(value) is not NextEligibleBarOpenModel:
        raise TypeError("execution_model must be exact NextEligibleBarOpenModel")
    applicability = value.applicability
    if type(applicability) is not NextBarOpenApplicability:
        raise TypeError("execution applicability must be exact NextBarOpenApplicability")
    return NextEligibleBarOpenModel(
        _component_ref(value.component_ref),
        NextBarOpenApplicability(applicability.tif_actions),
    )


def _resolved_mark(value: object) -> ResolvedMark:
    if type(value) is not ResolvedMark:
        raise TypeError("resolved_marks must contain exact ResolvedMark")
    return ResolvedMark(
        _instrument(value.instrument_id),
        value.quote_currency_id,
        value.price_purpose,
        value.price,
        _utc(value.observed_at),
        _utc(value.available_at),
        _utc(value.resolved_at),
        value.age_nanoseconds,
        value.stream_id,
        value.source_event_id,
        value.revision_id,
        value.stale_policy_key,
        value.stale_policy_version,
        value.stale_policy_hash,
        available_at_instant=(
            None
            if value.available_at_instant is None
            else _instant(value.available_at_instant)
        ),
        resolved_at_instant=(
            None
            if value.resolved_at_instant is None
            else _instant(value.resolved_at_instant)
        ),
    )


def _snapshot_plan(value: object) -> SnapshotProjectionPlan:
    if type(value) is not SnapshotProjectionPlan:
        raise TypeError("snapshot_plan must be exact SnapshotProjectionPlan")
    return SnapshotProjectionPlan(
        tuple(_resolved_mark(item) for item in value.resolved_marks),
        value.valuations,
        value.reporting_currency,
        value.reporting_scale,
        _utc(value.timestamp),
        value.currency_valuation_graph_hash,
    )


def _target_stream(value: object) -> PrecomputedTargetStream:
    if type(value) is not PrecomputedTargetStream:
        raise TypeError("target_stream must be exact PrecomputedTargetStream")
    return PrecomputedTargetStream(
        value.stream_key,
        tuple(_event(item) for item in value.events),
    )


def _case_authority(value: object) -> MarketDataCaseAuthority:
    if type(value) is not MarketDataCaseAuthority:
        raise TypeError("case_authority must be exact MarketDataCaseAuthority")
    return MarketDataCaseAuthority(
        tuple(_decision_cycle(item) for item in value.decision_cycles),
        tuple(_bar_execution(item) for item in value.bar_executions),
        _execution_model(value.execution_model),
        _snapshot_plan(value.snapshot_plan),
        _target_stream(value.target_stream),
    )


class MarketDataPreparationFailureCode(str, Enum):
    BUNDLE_READER_MISMATCH = "bundle_reader_mismatch"
    SIGNAL_BINDING_MISMATCH = "signal_binding_mismatch"
    STREAM_MANIFEST_MISMATCH = "stream_manifest_mismatch"
    EXECUTION_PROFILE_BINDING_MISMATCH = "execution_profile_binding_mismatch"
    VALUATION_PROFILE_BINDING_MISMATCH = "valuation_profile_binding_mismatch"
    SIGNAL_LINEAGE_MISMATCH = "signal_lineage_mismatch"
    POINT_IN_TIME_FAILURE = "point_in_time_failure"
    SIGNAL_BAR_FAILURE = "signal_bar_failure"
    WINDOW_CONSTRUCTION_FAILURE = "window_construction_failure"
    DECISION_CYCLE_ELIGIBILITY_MISMATCH = "decision_cycle_eligibility_mismatch"


@dataclass(frozen=True, slots=True)
class MarketDataPreparationFailure:
    code: MarketDataPreparationFailureCode
    role_position: int | None
    schedule_entry_position: int | None
    requirement_position: int | None
    event_position: int | None

    def __post_init__(self) -> None:
        if type(self.code) is not MarketDataPreparationFailureCode:
            raise TypeError("code must be exact MarketDataPreparationFailureCode")
        for name in (
            "role_position",
            "schedule_entry_position",
            "requirement_position",
            "event_position",
        ):
            _optional_position(name, getattr(self, name))

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "market_data_preparation_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "role_position": self.role_position,
            "schedule_entry_position": self.schedule_entry_position,
            "requirement_position": self.requirement_position,
            "event_position": self.event_position,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class PreparedMultiResolutionMarketData:
    preparation: MultiResolutionMarketDataPreparation
    eligibilities: tuple[WarmupEligibility, ...]
    verified_reader: InMemoryMarketBundleReader

    def __post_init__(self) -> None:
        if type(self.preparation) is not MultiResolutionMarketDataPreparation:
            raise TypeError("preparation must be exact MultiResolutionMarketDataPreparation")
        if type(self.eligibilities) is not tuple or any(
            type(value) is not WarmupEligibility for value in self.eligibilities
        ):
            raise TypeError("eligibilities must contain exact WarmupEligibility")
        if type(self.verified_reader) is not InMemoryMarketBundleReader:
            raise TypeError("verified_reader must be exact InMemoryMarketBundleReader")


@dataclass(frozen=True, slots=True)
class MarketDataPreparationOutcome:
    prepared: PreparedMultiResolutionMarketData | None
    failure: MarketDataPreparationFailure | None

    def __post_init__(self) -> None:
        if (self.prepared is None) == (self.failure is None):
            raise ValueError("exactly one prepared or failure is required")
        if self.prepared is not None and type(self.prepared) is not PreparedMultiResolutionMarketData:
            raise TypeError("prepared must be exact PreparedMultiResolutionMarketData or None")
        if self.failure is not None and type(self.failure) is not MarketDataPreparationFailure:
            raise TypeError("failure must be exact MarketDataPreparationFailure or None")


def _failure(
    code: MarketDataPreparationFailureCode,
    role: int | None = None,
    entry: int | None = None,
    requirement: int | None = None,
    event: int | None = None,
) -> MarketDataPreparationOutcome:
    return MarketDataPreparationOutcome(
        None,
        MarketDataPreparationFailure(code, role, entry, requirement, event),
    )


def _record(
    recorder: BoundedPerformanceRecorder | None,
    operation: PerformanceOperation,
    outcome: PerformanceOutcome,
    start: int | None,
    input_count: int,
    output_count: int,
) -> None:
    if recorder is None:
        return
    end = _clock()
    if start is not None and end is not None and end >= start:
        _record_observation(
            recorder,
            operation,
            outcome,
            end - start,
            input_count,
            output_count,
        )


def _capture_reader(
    expected_bundle_ref: MarketBundleRef,
    reader: MarketBundleReader,
    resolved_request: ResolvedBacktestRequest,
    recorder: BoundedPerformanceRecorder | None,
) -> InMemoryMarketBundleReader | None:
    start = None if recorder is None else _clock()
    try:
        ref = _bundle_ref(reader.bundle_ref)
        manifest = _manifest(reader.manifest)
        if (
            ref != MarketBundleRef.from_manifest(manifest)
            or ref != expected_bundle_ref
            or ref != resolved_request.request.market_bundle_ref
            or ref != resolved_request.environment.market_bundle_ref
        ):
            raise ValueError("bundle identity mismatch")
        streams: dict[str, tuple[MarketEvent, ...]] = {}
        for stream_manifest in manifest.streams:
            opened = reader.open_cursor(stream_manifest.stream_key, batch_size=_CAPTURE_BATCH_SIZE)
            if type(opened) is not EventCursor:
                raise ValueError("stream cursor did not open")
            cursor = EventCursor(
                _bundle_ref(opened.bundle_ref),
                _stream_manifest(opened.stream_manifest),
                opened.position,
                opened.batch_size,
            )
            if (
                cursor.bundle_ref != ref
                or cursor.stream_manifest != stream_manifest
                or cursor.position != 0
                or cursor.batch_size != _CAPTURE_BATCH_SIZE
            ):
                raise ValueError("initial cursor mismatch")
            events: list[MarketEvent] = []
            while not cursor.exhausted:
                batch_value = reader.read_batch(cursor)
                if type(batch_value) is not tuple or len(batch_value) != 2:
                    raise TypeError("read_batch must return an exact pair")
                batch, successor_value = batch_value
                if type(batch) is not tuple or not batch:
                    raise ValueError("non-exhausted Reader made no progress")
                if type(successor_value) is not EventCursor:
                    raise TypeError("Reader successor must be exact EventCursor")
                successor = EventCursor(
                    _bundle_ref(successor_value.bundle_ref),
                    _stream_manifest(successor_value.stream_manifest),
                    successor_value.position,
                    successor_value.batch_size,
                )
                copied = tuple(_event(item) for item in batch)
                if (
                    successor.bundle_ref != ref
                    or successor.stream_manifest != stream_manifest
                    or successor.batch_size != cursor.batch_size
                    or successor.position != cursor.position + len(copied)
                    or successor.position > stream_manifest.event_count
                ):
                    raise ValueError("Reader cursor successor mismatch")
                events.extend(copied)
                cursor = successor
            captured = tuple(events)
            if (
                len(captured) != stream_manifest.event_count
                or canonical_sha256(captured) != stream_manifest.content_hash
                or any(
                    item.stream_key != stream_manifest.stream_key
                    or item.event_type != stream_manifest.event_type
                    or item.capability != stream_manifest.capability
                    for item in captured
                )
            ):
                raise ValueError("captured stream does not match manifest")
            streams[stream_manifest.stream_key] = captured
        retained = InMemoryMarketBundleReader(ref, manifest, streams)
    except BaseException:
        _record(
            recorder,
            PerformanceOperation.HYDRATE_INPUTS,
            PerformanceOutcome.FAILED,
            start,
            0,
            0,
        )
        return None
    _record(
        recorder,
        PerformanceOperation.HYDRATE_INPUTS,
        PerformanceOutcome.SUCCEEDED,
        start,
        sum(value.event_count for value in manifest.streams),
        sum(len(value) for value in retained.streams.values()),
    )
    return retained


def _stream_lookup(
    reader: InMemoryMarketBundleReader,
    keys: tuple[str, ...],
    recorder: BoundedPerformanceRecorder | None,
) -> dict[str, MarketStreamManifest] | None:
    start = None if recorder is None else _clock()
    manifests = {value.stream_key: value for value in reader.manifest.streams}
    found_count = sum(key in manifests for key in keys)
    succeeded = found_count == len(keys)
    _record(
        recorder,
        PerformanceOperation.LOOKUP_STREAMS,
        PerformanceOutcome.SUCCEEDED if succeeded else PerformanceOutcome.FAILED,
        start,
        len(keys),
        found_count,
    )
    return ({key: manifests[key] for key in keys} if succeeded else None)


def _signal_manifest_failure(
    schedule: DecisionSchedule,
    bindings: tuple[SignalBarBinding, ...],
    manifests: dict[str, MarketStreamManifest],
) -> int | None:
    requirements = {value.requirement_hash: value for value in schedule.requirements}
    failures = []
    for position, binding in enumerate(bindings):
        requirement = requirements[binding.requirement_hash]
        manifest = manifests[binding.stream_key]
        if (
            manifest.event_type != "bar"
            or manifest.capability != _BAR_CAPABILITY
            or manifest.capability != requirement.observation_query.capability
        ):
            failures.append(position)
    return min(failures) if failures else None


def _valid_valuation_bar(event: MarketEvent, manifest: MarketStreamManifest) -> bool:
    try:
        payload = event.payload
        query = ObservationQuery(
            event.stream_key,
            _instrument(event.instrument_id),
            ObservationPurposeRef("valuation.bar", 1),
            event.capability,
        )
        definition_key = _text("bar_definition_key", payload["bar_definition_key"])
        definition_version = payload["bar_definition_version"]
        if type(definition_version) is not int:
            return False
        definition_hash = _hash("bar_definition_hash", payload["bar_definition_hash"])
        aggregation_input_hash = _hash(
            "aggregation_input_hash", payload["aggregation_input_hash"]
        )
        requirement = LookbackRequirement(
            "valuation-bar",
            query,
            BarDefinitionRef(definition_key, definition_version, definition_hash),
            1,
        )
        binding = SignalBarBinding(
            requirement.requirement_hash,
            event.stream_key,
            PricePurpose.VALUATION,
            aggregation_input_hash,
        )
        return (
            event.capability == _BAR_CAPABILITY
            and payload["price_purpose"] == PricePurpose.VALUATION.value
            and event.source_hash == aggregation_input_hash
            and not _malformed(requirement, binding, manifest, event)
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _execution_failure(
    bindings: MultiResolutionMarketDataBindings,
    manifests: dict[str, MarketStreamManifest],
    reader: InMemoryMarketBundleReader,
    authority: MarketDataCaseAuthority,
    resolved: ResolvedBacktestRequest,
) -> tuple[int | None, int | None] | None:
    model = authority.execution_model
    profile_ref = next(
        (
            value
            for value in resolved.environment.simulation.component_manifest
            if value.port_type is SimulationPortType.EXECUTION_MODEL
        ),
        None,
    )
    if profile_ref != model.component_ref or len(bindings.execution_bindings) != 1:
        return 0, None
    binding = bindings.execution_bindings[0]
    if binding.profile_binding_key != model.component_ref.component_key:
        return 0, None
    manifest = manifests[binding.stream_key]
    requirements = model.spec().required_capabilities
    if len(requirements) != 1 or not all(
        manifest.capability.key == value.capability_key
        and manifest.capability.version >= value.minimum_version
        for value in requirements
    ):
        return 0, None
    events = {value.event_id: value for value in reader.streams[binding.stream_key]}
    admissions_by_order: dict[object, list[ResolvedOrderAdmission]] = {}
    for cycle in authority.decision_cycles:
        for admission in cycle.admissions:
            admissions_by_order.setdefault(admission.order.order_id, []).append(admission)
    for position, execution in enumerate(authority.bar_executions):
        event = events.get(execution.event_id)
        evidence = execution.liquidity_evidence
        state = execution.market_state
        admissions = admissions_by_order.get(execution.order_id, [])
        if event is None or (
            evidence.market_event_id != event.event_id
            or evidence.market_event_hash != event.event_hash
            or evidence.evaluated_at != event.available_time
            or execution.pretrade_plan.market_rule_evaluated_at != event.available_time
            or state.source_event_id != event.event_id
            or state.revision_id != event.revision_id
            or state.observed_at != event.event_time
            or state.available_at != event.available_time
            or state.evidence_hash != event.event_hash
            or (
                len(admissions) == 1
                and event.instrument_id != admissions[0].order.intent.instrument_id
            )
        ):
            return 0, position
    return None


def _valuation_failure(
    bindings: MultiResolutionMarketDataBindings,
    manifests: dict[str, MarketStreamManifest],
    reader: InMemoryMarketBundleReader,
    authority: MarketDataCaseAuthority,
) -> tuple[int | None, int | None] | None:
    marks = authority.snapshot_plan.resolved_marks
    if len(bindings.valuation_bindings) != len({value.instrument_id for value in marks}):
        return 0, None
    by_instrument = {value.instrument_id: value for value in bindings.valuation_bindings}
    all_events = {
        event.event_id: event
        for values in reader.streams.values()
        for event in values
    }
    for position, mark in enumerate(marks):
        if type(mark) is not ResolvedMark:
            return position, None
        binding = by_instrument.get(mark.instrument_id)
        event = all_events.get(mark.source_event_id)
        if (
            mark.price_purpose is not PricePurpose.VALUATION
            or binding is None
            or event is None
            or binding.stream_key != mark.stream_id
        ):
            return position, None
        manifest = manifests[binding.stream_key]
        if (
            event.stream_key != binding.stream_key
            or event.instrument_id != mark.instrument_id
            or event.revision_id != mark.revision_id
            or event.available_time != mark.available_at
            or (
                mark.available_at_instant is not None
                and event.timeline_instant != mark.available_at_instant
            )
            or not _valid_valuation_bar(event, manifest)
        ):
            return position, None
    return None


def _lineage_records(
    schedule: DecisionSchedule,
    bindings: MultiResolutionMarketDataBindings,
    lineages: tuple[SignalObservationLineageBinding, ...],
    reader: InMemoryMarketBundleReader,
) -> tuple[dict[str, tuple[RevisionedObservationRecord, ...]] | None, tuple[int, int] | None]:
    requirements = {value.requirement_hash: value for value in schedule.requirements}
    binding_by_requirement = {
        value.requirement_hash: value for value in bindings.signal_bindings
    }
    rows_by_requirement: dict[str, list[SignalObservationLineageBinding]] = {}
    event_hashes: dict[str, str] = {}
    identities: set[tuple[str, str]] = set()
    for position, row in enumerate(lineages):
        if row.requirement_hash not in requirements:
            return None, (0, position)
        identity = (row.requirement_hash, row.event_id)
        previous = event_hashes.setdefault(row.event_id, row.event_hash)
        if identity in identities or previous != row.event_hash:
            return None, (0, position)
        identities.add(identity)
        rows_by_requirement.setdefault(row.requirement_hash, []).append(row)
    records: dict[str, tuple[RevisionedObservationRecord, ...]] = {}
    start = schedule.window.data_start
    end = schedule.window.end_exclusive
    for requirement_position, requirement in enumerate(schedule.requirements):
        binding = binding_by_requirement[requirement.requirement_hash]
        expected = tuple(
            event
            for event in reader.streams[binding.stream_key]
            if event.event_type == "bar"
            and event.instrument_id == requirement.observation_query.instrument_id
            and event.capability == requirement.observation_query.capability
            and start <= event.available_time < end
        )
        expected_by_id = {value.event_id: value for value in expected}
        rows = tuple(rows_by_requirement.get(requirement.requirement_hash, ()))
        if {value.event_id for value in rows} != set(expected_by_id) or len(rows) != len(expected):
            return None, (requirement_position, 0)
        revision_ids_by_key: dict[str, set[str]] = {}
        for event_position, row in enumerate(rows):
            event = expected_by_id[row.event_id]
            if row.event_hash != event.event_hash:
                return None, (requirement_position, event_position)
            revision_ids_by_key.setdefault(row.observation_key, set()).add(event.revision_id)
        for event_position, row in enumerate(rows):
            event = expected_by_id[row.event_id]
            parent = event.supersedes_revision_id
            if parent is not None and parent not in revision_ids_by_key[row.observation_key]:
                return None, (requirement_position, event_position)
        records[requirement.requirement_hash] = tuple(
            RevisionedObservationRecord(
                row.observation_key,
                ObservationRecord(requirement.observation_query.purpose, expected_by_id[row.event_id]),
            )
            for row in rows
        )
    return records, None


def _cycle_failure(
    schedule: DecisionSchedule,
    eligibilities: tuple[WarmupEligibility, ...],
    authority: MarketDataCaseAuthority,
    reader: InMemoryMarketBundleReader,
) -> tuple[int | None, int | None] | None:
    entries_by_key: dict[tuple[UtcInstant, TimelineSegment], list[int]] = {}
    for position, entry in enumerate(schedule.entries):
        entries_by_key.setdefault((entry.decision_instant.instant, entry.segment), []).append(position)
    cycles_by_key: dict[tuple[UtcInstant, TimelineSegment], list[ResolvedDecisionCycle]] = {}
    for cycle in authority.decision_cycles:
        cycles_by_key.setdefault((cycle.schedule.decision_time, cycle.schedule.segment), []).append(cycle)
    mapped: list[tuple[int, ResolvedDecisionCycle]] = []
    for position, eligibility in enumerate(eligibilities):
        key = (eligibility.entry.decision_instant.instant, eligibility.entry.segment)
        cycles = cycles_by_key.get(key, [])
        if len(entries_by_key[key]) != 1:
            return position, None
        if eligibility.strategy_invocation_eligible:
            if len(cycles) != 1:
                return position, None
            cycle = cycles[0]
            if eligibility.entry.segment is TimelineSegment.WARMUP:
                if cycle.allocations or cycle.admissions:
                    return position, None
            elif not eligibility.trading_side_effects_authorized:
                return position, None
            mapped.append((position, cycle))
        elif cycles:
            return position, None
    if len(mapped) != len(authority.decision_cycles):
        return None, None
    active_admissions: dict[object, int] = {}
    for _, cycle in mapped:
        if cycle.schedule.segment is TimelineSegment.ACTIVE_TRADING:
            for admission in cycle.admissions:
                order_id = admission.order.order_id
                active_admissions[order_id] = active_admissions.get(order_id, 0) + 1
    for event_position, execution in enumerate(authority.bar_executions):
        if active_admissions.get(execution.order_id, 0) != 1:
            return None, event_position
    expected_target_ids = {
        entry.event_id
        for _, cycle in mapped
        for entry in cycle.schedule.entries
    }
    actual_target_ids = {value.event_id for value in authority.target_stream.events}
    if expected_target_ids != actual_target_ids:
        return None, 0
    retained_by_id = {
        value.event_id: value
        for value in reader.streams[authority.target_stream.stream_key]
    }
    if set(retained_by_id) != actual_target_ids or any(
        retained_by_id[value.event_id].event_hash != value.event_hash
        for value in authority.target_stream.events
    ):
        return None, 0
    adapter = PrecomputedTargetStreamAdapter()
    prior_state = None
    for position, cycle in mapped:
        entry = schedule.entries[position]
        events = tuple(retained_by_id[value.event_id] for value in cycle.schedule.entries)
        next_instant = (
            schedule.entries[position + 1].decision_instant
            if position + 1 < len(schedule.entries)
            else None
        )
        for event_position, event in enumerate(events):
            if (
                event.event_time != cycle.schedule.decision_time
                or event.available_time != cycle.schedule.decision_time
                or event.timeline_instant < entry.decision_instant
                or (next_instant is not None and event.timeline_instant >= next_instant)
            ):
                return position, event_position
        outcome = adapter.inject(
            stream=authority.target_stream,
            timeline_events=tuple(TimelineEvent(cycle.schedule.segment, value) for value in events),
            schedule=cycle.schedule,
            prior_state=prior_state,
        )
        if cycle.schedule.segment is TimelineSegment.WARMUP:
            if outcome.suppression is None:
                return position, 0
        else:
            if outcome.injection is None:
                return position, 0
            prior_state = outcome.injection.state
    return None


def prepare_multi_resolution_market_data_v1(
    *,
    expected_bundle_ref: MarketBundleRef,
    reader: MarketBundleReader,
    schedule: DecisionSchedule,
    signal_binding_candidates: tuple[SignalBarBinding, ...],
    execution_binding_candidates: tuple[ExecutionDataBinding, ...],
    valuation_binding_candidates: tuple[ValuationDataBinding, ...],
    signal_lineages: tuple[SignalObservationLineageBinding, ...],
    case_authority: MarketDataCaseAuthority,
    resolved_request: ResolvedBacktestRequest,
    recorder: BoundedPerformanceRecorder | None = None,
) -> MarketDataPreparationOutcome:
    expected_bundle_ref = _bundle_ref(expected_bundle_ref)
    schedule = _schedule(schedule)
    if not isinstance(reader, MarketBundleReader):
        raise TypeError("reader must satisfy MarketBundleReader")
    for name, values, expected in (
        ("signal_binding_candidates", signal_binding_candidates, SignalBarBinding),
        ("execution_binding_candidates", execution_binding_candidates, ExecutionDataBinding),
        ("valuation_binding_candidates", valuation_binding_candidates, ValuationDataBinding),
    ):
        if type(values) is not tuple or any(type(value) is not expected for value in values):
            raise TypeError(f"{name} must contain exact values")
    signal_binding_candidates = tuple(
        sorted(
            (
                SignalBarBinding(
                    value.requirement_hash,
                    value.stream_key,
                    value.price_purpose,
                    value.aggregation_input_hash,
                )
                for value in signal_binding_candidates
            ),
            key=lambda value: (
                value.requirement_hash,
                value.stream_key,
                value.price_purpose.value,
                value.aggregation_input_hash,
            ),
        )
    )
    execution_binding_candidates = tuple(
        sorted(
            (
                ExecutionDataBinding(value.profile_binding_key, value.stream_key)
                for value in execution_binding_candidates
            ),
            key=lambda value: (value.profile_binding_key, value.stream_key),
        )
    )
    valuation_binding_candidates = tuple(
        sorted(
            (
                ValuationDataBinding(value.instrument_id, value.stream_key)
                for value in valuation_binding_candidates
            ),
            key=lambda value: (canonical_bytes(value.instrument_id), value.stream_key),
        )
    )
    if type(signal_lineages) is not tuple:
        raise TypeError("signal_lineages must be an exact tuple")
    signal_lineages = tuple(
        sorted(
            (_lineage(value) for value in signal_lineages),
            key=lambda value: (
                value.requirement_hash,
                value.event_id,
                value.event_hash,
                value.observation_key,
            ),
        )
    )
    case_authority = _case_authority(case_authority)
    if type(resolved_request) is not ResolvedBacktestRequest:
        raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
    if recorder is not None and type(recorder) is not BoundedPerformanceRecorder:
        raise TypeError("recorder must be exact BoundedPerformanceRecorder or None")

    retained = _capture_reader(expected_bundle_ref, reader, resolved_request, recorder)
    if retained is None:
        return _failure(MarketDataPreparationFailureCode.BUNDLE_READER_MISMATCH)

    replay_start = None if recorder is None else _clock()
    expected_requirements = {value.requirement_hash for value in schedule.requirements}
    actual_requirements = {value.requirement_hash for value in signal_binding_candidates}
    if (
        len(actual_requirements) != len(signal_binding_candidates)
        or actual_requirements != expected_requirements
        or any(
            value.stream_key
            != next(
                item.observation_query.dataset_key
                for item in schedule.requirements
                if item.requirement_hash == value.requirement_hash
            )
            for value in signal_binding_candidates
        )
    ):
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(signal_binding_candidates), 0)
        return _failure(MarketDataPreparationFailureCode.SIGNAL_BINDING_MISMATCH, _ROLE_SIGNAL)
    role_keys = tuple(
        [value.stream_key for value in signal_binding_candidates]
        + [value.stream_key for value in execution_binding_candidates]
        + [value.stream_key for value in valuation_binding_candidates]
        + [case_authority.target_stream.stream_key]
    )
    manifests = _stream_lookup(retained, role_keys, recorder)
    if manifests is None:
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(role_keys), 0)
        return _failure(MarketDataPreparationFailureCode.STREAM_MANIFEST_MISMATCH)
    signal_manifest_position = _signal_manifest_failure(
        schedule, signal_binding_candidates, manifests
    )
    if signal_manifest_position is not None:
        _record(
            recorder,
            PerformanceOperation.VERIFY_REPLAY,
            PerformanceOutcome.FAILED,
            replay_start,
            len(signal_binding_candidates),
            0,
        )
        return _failure(
            MarketDataPreparationFailureCode.STREAM_MANIFEST_MISMATCH,
            _ROLE_SIGNAL,
            None,
            signal_manifest_position,
        )
    if len({value.profile_binding_key for value in execution_binding_candidates}) != len(execution_binding_candidates):
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(execution_binding_candidates), 0)
        return _failure(MarketDataPreparationFailureCode.EXECUTION_PROFILE_BINDING_MISMATCH, _ROLE_EXECUTION)
    if len({value.instrument_id for value in valuation_binding_candidates}) != len(valuation_binding_candidates):
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(valuation_binding_candidates), 0)
        return _failure(MarketDataPreparationFailureCode.VALUATION_PROFILE_BINDING_MISMATCH, _ROLE_VALUATION)
    try:
        bindings = construct_multi_resolution_market_data_bindings(
            signal_bindings=signal_binding_candidates,
            execution_bindings=execution_binding_candidates,
            valuation_bindings=valuation_binding_candidates,
            recorder=None,
        )
        validate_schedule_signal_exact_cover(schedule, bindings, None)
    except (TypeError, ValueError):
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(signal_binding_candidates), 0)
        return _failure(MarketDataPreparationFailureCode.SIGNAL_BINDING_MISMATCH, _ROLE_SIGNAL)

    execution_issue = _execution_failure(bindings, manifests, retained, case_authority, resolved_request)
    if execution_issue is not None:
        binding_position, event_position = execution_issue
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(bindings.execution_bindings), 0)
        return _failure(MarketDataPreparationFailureCode.EXECUTION_PROFILE_BINDING_MISMATCH, _ROLE_EXECUTION, None, binding_position, event_position)
    valuation_issue = _valuation_failure(bindings, manifests, retained, case_authority)
    if valuation_issue is not None:
        mark_position, event_position = valuation_issue
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(bindings.valuation_bindings), 0)
        return _failure(MarketDataPreparationFailureCode.VALUATION_PROFILE_BINDING_MISMATCH, _ROLE_VALUATION, None, mark_position, event_position)
    records, lineage_issue = _lineage_records(schedule, bindings, signal_lineages, retained)
    if lineage_issue is not None or records is None:
        requirement_position, event_position = lineage_issue or (None, None)
        _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.FAILED, replay_start, len(signal_lineages), 0)
        return _failure(MarketDataPreparationFailureCode.SIGNAL_LINEAGE_MISMATCH, _ROLE_SIGNAL, None, requirement_position, event_position)
    replay_count = len(bindings.signal_bindings) + len(bindings.execution_bindings) + len(bindings.valuation_bindings) + len(signal_lineages)
    _record(recorder, PerformanceOperation.VERIFY_REPLAY, PerformanceOutcome.SUCCEEDED, replay_start, replay_count, replay_count)

    point_failures: list[tuple[int, int]] = []
    signal_failures: list[tuple[int, int, int]] = []
    window_failures: list[tuple[int, int]] = []
    windows_by_entry: dict[int, list[NamedBarWindowResult]] = {
        position: [] for position in range(len(schedule.entries))
    }
    binding_by_requirement = {value.requirement_hash: value for value in bindings.signal_bindings}
    for entry_position, entry in enumerate(schedule.entries):
        for requirement_position, requirement in enumerate(schedule.requirements):
            requirement_records = records[requirement.requirement_hash]
            point_start = None if recorder is None else _clock()
            try:
                point_outcome = PointInTimeObservationView(
                    allowed_queries=(requirement.observation_query,),
                    records=requirement_records,
                    decision_instant=entry.decision_instant,
                ).query(requirement.observation_query)
            except (TypeError, ValueError):
                point_outcome = None
            if point_outcome is None or point_outcome.result is None:
                point_failures.append((entry_position, requirement_position))
                _record(recorder, PerformanceOperation.PROJECT_POINT_IN_TIME, PerformanceOutcome.FAILED, point_start, len(requirement_records), 0)
                continue
            visible = point_outcome.result
            _record(recorder, PerformanceOperation.PROJECT_POINT_IN_TIME, PerformanceOutcome.SUCCEEDED, point_start, len(requirement_records), len(visible.events))
            try:
                verification = verify_visible_signal_bars(
                    requirement,
                    binding_by_requirement[requirement.requirement_hash],
                    manifests[binding_by_requirement[requirement.requirement_hash].stream_key],
                    visible,
                    None,
                )
            except (TypeError, ValueError):
                signal_failures.append((entry_position, requirement_position, 0))
                continue
            if verification.failure is not None:
                signal_failures.append((entry_position, requirement_position, verification.failure.event_position))
                continue
            window_start = None if recorder is None else _clock()
            try:
                window = NamedBarWindowView(
                    query=NamedBarWindowQuery(
                        requirement.observation_query,
                        requirement.bar_definition,
                        entry.decision_instant,
                        requirement.minimum_count,
                        entry.decision_instant.instant,
                    ),
                    backing_result=visible,
                ).window()
            except (TypeError, ValueError):
                window_failures.append((entry_position, requirement_position))
                _record(recorder, PerformanceOperation.BUILD_WINDOW, PerformanceOutcome.FAILED, window_start, len(visible.events), 0)
                continue
            windows_by_entry[entry_position].append(window)
            _record(recorder, PerformanceOperation.BUILD_WINDOW, PerformanceOutcome.SUCCEEDED, window_start, len(visible.events), len(window.events))
    if point_failures:
        entry_position, requirement_position = min(point_failures)
        return _failure(MarketDataPreparationFailureCode.POINT_IN_TIME_FAILURE, _ROLE_SIGNAL, entry_position, requirement_position)
    if signal_failures:
        entry_position, requirement_position, event_position = min(signal_failures)
        return _failure(MarketDataPreparationFailureCode.SIGNAL_BAR_FAILURE, _ROLE_SIGNAL, entry_position, requirement_position, event_position)
    if window_failures:
        entry_position, requirement_position = min(window_failures)
        return _failure(MarketDataPreparationFailureCode.WINDOW_CONSTRUCTION_FAILURE, _ROLE_SIGNAL, entry_position, requirement_position)

    eligibilities: list[WarmupEligibility] = []
    for entry_position, entry in enumerate(schedule.entries):
        eligibility_start = None if recorder is None else _clock()
        try:
            eligibility = schedule.eligibility(entry, tuple(windows_by_entry[entry_position]))
        except (TypeError, ValueError):
            _record(recorder, PerformanceOperation.EVALUATE_LOOKBACK, PerformanceOutcome.FAILED, eligibility_start, 0, 0)
            return _failure(MarketDataPreparationFailureCode.WINDOW_CONSTRUCTION_FAILURE, _ROLE_SIGNAL, entry_position)
        eligibilities.append(eligibility)
        available = sum(value.available_count for value in eligibility.coverage)
        _record(
            recorder,
            PerformanceOperation.EVALUATE_LOOKBACK,
            PerformanceOutcome.SUCCEEDED if eligibility.lookback_satisfied else PerformanceOutcome.INELIGIBLE,
            eligibility_start,
            available,
            1 if eligibility.lookback_satisfied else 0,
        )
    eligibility_values = tuple(eligibilities)
    cycle_issue = _cycle_failure(schedule, eligibility_values, case_authority, retained)
    if cycle_issue is not None:
        entry_position, event_position = cycle_issue
        return _failure(
            MarketDataPreparationFailureCode.DECISION_CYCLE_ELIGIBILITY_MISMATCH,
            None,
            entry_position,
            None,
            event_position,
        )

    preparation = MultiResolutionMarketDataPreparation(schedule, bindings, signal_lineages)
    return MarketDataPreparationOutcome(
        PreparedMultiResolutionMarketData(preparation, eligibility_values, retained),
        None,
    )
