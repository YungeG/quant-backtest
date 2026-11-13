"""Pure original-source collection and fixed-clock native mark resolution."""
from __future__ import annotations

from dataclasses import dataclass, replace
import unicodedata

from crypto_quant_domain import (
    PricePurpose, SimulationInstant, SourceSequence, TimelinePhase, canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading import (
    AtomicDecisionBatchResult, MarkObservation, MarkResolutionFailure, MarkResolver,
)
from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2
from .cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioMarkBatchDevelopmentV1


def _require_inputs_v2(inputs) -> None:
    if type(inputs) is not CnASharePortfolioEconomicDevelopmentInputsV2:
        raise TypeError("economic activation requires exact InputsV2")


def _economic_activation_at_v2(inputs) -> SimulationInstant:
    _require_inputs_v2(inputs)
    return SimulationInstant(inputs.initial_marks.at.instant, TimelinePhase(30, "cn_economic_native"), SourceSequence(0))


def _activation_coordinator_at_v2(inputs) -> SimulationInstant:
    return SimulationInstant(_economic_activation_at_v2(inputs).instant,
        TimelinePhase(45, "cn_economic_native"), SourceSequence(0))


class _EconomicMarkResolutionFailureV2(ValueError):
    def __init__(self, failure: MarkResolutionFailure, requested_at: SimulationInstant):
        if type(failure) is not MarkResolutionFailure or type(requested_at) is not SimulationInstant:
            raise TypeError("economic mark rejection requires exact native failure and full clock")
        self.failure, self.requested_at = failure, requested_at
        super().__init__("economic activation mark resolution: " + failure.code.value + " " + canonical_sha256(failure))


def _resolve_retained_economic_marks_v2(inputs, at) -> CnASharePortfolioMarkBatchDevelopmentV1:
    _require_inputs_v2(inputs)
    if type(at) is not SimulationInstant or at not in (
            inputs.initial_marks.at, _economic_activation_at_v2(inputs), _activation_coordinator_at_v2(inputs)):
        raise ValueError("economic retained marks require exact initial0/activation30/coordinator45 clock")
    retained = inputs.retained_signal_marks[0].marks
    observations = tuple(MarkObservation(m.instrument_id, m.quote_currency_id, m.price_purpose,
        m.price, m.observed_at, m.available_at, m.stream_id, m.source_event_id, m.revision_id) for m in retained)
    result = []
    for instrument in inputs.scope.instrument_ids:
        outcome = MarkResolver().resolve(observations, instrument_id=instrument,
            price_purpose=PricePurpose.VALUATION, requested_at=at.instant, stale_policy=inputs.activation_stale_policy)
        if outcome.resolved_mark is None:
            raise _EconomicMarkResolutionFailureV2(outcome.failure, at)
        original = tuple(m for m in retained if m.instrument_id == instrument)
        if len(original) != 1:
            raise ValueError("economic retained marks require unique original instrument cover")
        available = original[0].available_at_instant
        if (type(available) is not SimulationInstant or available.instant != original[0].available_at
                or available > at):
            raise ValueError("economic original mark availability full clock is future or inconsistent")
        result.append(replace(outcome.resolved_mark, available_at_instant=available, resolved_at_instant=at))
    return CnASharePortfolioMarkBatchDevelopmentV1(at, tuple(result))


def _economic_financial_checkpoints_v2(inputs) -> tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]:
    _require_inputs_v2(inputs)
    clocks = tuple(b.at for b in inputs.checkpoint_marks)
    blocked = {inputs.initial_marks.at, _economic_activation_at_v2(inputs), _activation_coordinator_at_v2(inputs),
        *(b.at for b in inputs.retained_signal_marks), *(b.at for b in inputs.daily_marks)}
    for batch in inputs.retained_signal_marks:
        blocked.add(SimulationInstant(batch.at.instant, TimelinePhase(45, "cn_economic_native"), SourceSequence(0)))
    if (clocks != tuple(sorted(set(clocks))) or any(at in blocked or at.instant < inputs.initial_marks.at.instant for at in clocks)):
        raise ValueError("economic V2 caller checkpoint collides with internal/source/daily/prestart clock")
    derived = _resolve_retained_economic_marks_v2(inputs, _activation_coordinator_at_v2(inputs))
    return tuple(sorted((*inputs.checkpoint_marks, derived), key=lambda b: b.at))


def _retained_economic_decision_v2(inputs) -> AtomicDecisionBatchResult:
    _require_inputs_v2(inputs)
    from .cn_a_share_portfolio_economic_native_state_v1 import _collect_economic_decision_v1, _EconomicNativeFailureV1
    event = inputs.source_target_stream.events[0]
    try:
        return _collect_economic_decision_v1(inputs=inputs, event=event, original_claim={"event": event})
    except _EconomicNativeFailureV1 as failure:
        raise ValueError("economic V2 original source rejected by native " + failure.operation) from failure


def _economic_native_failure_inputs_v2(operation, native_inputs):
    """Diagnostic@2 encodes the allocator's noncanonical Scale as its native places."""
    from crypto_quant_domain import Scale
    if operation != "portfolio_allocation":
        return native_inputs
    fields = {"sleeve_state", "portfolio_snapshot", "allocations", "target_notional_scale"}
    if type(native_inputs) is not dict or set(native_inputs) != fields or type(native_inputs["target_notional_scale"]) is not Scale:
        raise TypeError("economic diagnostic2 requires exact native allocator arguments")
    return {**native_inputs, "target_notional_scale": native_inputs["target_notional_scale"].places}


def _economic_activation_signal_v2(*, sources, event):
    from crypto_quant_trading import LatestSleeveDecisionState
    from .cn_a_share_portfolio_economic_native_state_v1 import (
        _EconomicOpenSourcesV1, _require_economic_equity_v1, _economic_signal_from_batch_v1,
    )
    if type(sources) is not _EconomicOpenSourcesV1:
        raise TypeError("economic activation requires exact native sources")
    inputs = sources.inputs
    _require_inputs_v2(inputs)
    at = _economic_activation_at_v2(inputs)
    if sources.at != at or canonical_bytes(event) != canonical_bytes(inputs.source_target_stream.events[0]):
        raise ValueError("economic activation requires original event and fixed active30 clock")
    collected = _retained_economic_decision_v2(inputs)
    _require_economic_equity_v1(sources, event)
    state = LatestSleeveDecisionState(as_of=at.instant, decisions=collected.state.decisions, as_of_instant=at)
    return _economic_signal_from_batch_v1(sources=sources, event=event, collected=collected,
        allocation_state=state, valid_from=at.instant)


@dataclass(frozen=True, slots=True)
class _EconomicActivationV2:
    source_target_stream_digest: str
    source_event_id: str
    source_event_hash: str
    source_at: SimulationInstant
    retained_signal_marks_hash: str
    activation_at: SimulationInstant
    activation_stale_policy_hash: str
    activation_marks_hash: str

    def __post_init__(self) -> None:
        for name in ("source_target_stream_digest", "source_event_hash", "retained_signal_marks_hash",
                "activation_stale_policy_hash", "activation_marks_hash"):
            value = getattr(self, name)
            if (type(value) is not str or len(value) != 71 or not value.startswith("sha256:")
                    or any(c not in "0123456789abcdef" for c in value[7:])):
                raise ValueError("economic activation hash is not canonical: " + name)
        if (type(self.source_event_id) is not str or not self.source_event_id
                or self.source_event_id != self.source_event_id.strip()
                or unicodedata.normalize("NFC", self.source_event_id) != self.source_event_id):
            raise ValueError("economic activation source event ID is not canonical")
        if type(self.source_at) is not SimulationInstant or type(self.activation_at) is not SimulationInstant:
            raise TypeError("economic activation requires exact full clocks")
        if (self.source_at.instant >= self.activation_at.instant or self.source_at.phase.rank >= 30
                or self.activation_at.phase != TimelinePhase(30, "cn_economic_native")
                or self.activation_at.source_sequence != SourceSequence(0)):
            raise ValueError("economic activation source/active clock mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_activation", "schema_version": 1,
            **{name: getattr(self, name) for name in self.__dataclass_fields__}}


def _economic_activation_value_v2(inputs, event) -> _EconomicActivationV2:
    _require_inputs_v2(inputs)
    if type(event) is not MarketEvent or canonical_bytes(event) != canonical_bytes(inputs.source_target_stream.events[0]):
        raise ValueError("economic activation requires the exact original source event")
    at = _economic_activation_at_v2(inputs)
    return _EconomicActivationV2(inputs.source_target_stream.target_stream_digest, event.event_id, event.event_hash,
        SimulationInstant(event.event_time, event.phase, event.source_sequence), canonical_sha256(inputs.retained_signal_marks[0]),
        at, inputs.activation_stale_policy.policy_hash, canonical_sha256(_resolve_retained_economic_marks_v2(inputs, at)))
