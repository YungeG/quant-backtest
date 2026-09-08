from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import SimulationInstant, canonical_bytes, canonical_sha256

from .observation_windows import BarDefinitionRef, NamedBarWindowResult
from .observations import ObservationQuery
from .timeline import TimelineSegment, TimelineWindow


_SCHEMA_VERSION = 1
_MAX_LOOKBACK = 10_000


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _instant_key(value: SimulationInstant) -> tuple[int, int, str, int]:
    return (
        value.instant.epoch_nanoseconds,
        value.phase.rank,
        value.phase.code,
        value.source_sequence.value,
    )


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    digest = text.removeprefix("sha256:")
    if (
        len(text) != 71
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{name} must be sha256 content hash")
    return text


@dataclass(frozen=True, slots=True)
class LookbackRequirement:
    requirement_key: str
    observation_query: ObservationQuery
    bar_definition: BarDefinitionRef
    minimum_count: int

    def __post_init__(self) -> None:
        _text("requirement_key", self.requirement_key)
        if type(self.observation_query) is not ObservationQuery:
            raise TypeError("observation_query must be ObservationQuery")
        if type(self.bar_definition) is not BarDefinitionRef:
            raise TypeError("bar_definition must be BarDefinitionRef")
        if (
            type(self.minimum_count) is not int
            or not 1 <= self.minimum_count <= _MAX_LOOKBACK
        ):
            raise ValueError(f"minimum_count must be between 1 and {_MAX_LOOKBACK}")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "lookback_requirement",
            "schema_version": _SCHEMA_VERSION,
            "requirement_key": self.requirement_key,
            "observation_query": self.observation_query.to_canonical_dict(),
            "bar_definition": self.bar_definition.to_canonical_dict(),
            "minimum_count": self.minimum_count,
        }

    @property
    def requirement_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "requirement_hash": self.requirement_hash}


@dataclass(frozen=True, slots=True)
class DecisionScheduleEntry:
    decision_instant: SimulationInstant
    segment: TimelineSegment

    def __post_init__(self) -> None:
        if type(self.decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")
        if type(self.segment) is not TimelineSegment:
            raise TypeError("segment must be TimelineSegment")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "decision_schedule_entry",
            "schema_version": _SCHEMA_VERSION,
            "decision_instant": self.decision_instant.to_canonical_dict(),
            "segment": self.segment.value,
        }

    @property
    def entry_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "entry_hash": self.entry_hash}


@dataclass(frozen=True, slots=True)
class LookbackCoverage:
    requirement: LookbackRequirement
    window_result_hash: str
    required_count: int
    available_count: int
    shortfall_count: int
    satisfied: bool

    def __post_init__(self) -> None:
        if type(self.requirement) is not LookbackRequirement:
            raise TypeError("requirement must be LookbackRequirement")
        _hash("window_result_hash", self.window_result_hash)
        if self.required_count != self.requirement.minimum_count:
            raise ValueError("required_count must match requirement")
        if type(self.available_count) is not int or self.available_count < 0:
            raise ValueError("available_count must be nonnegative integer")
        if self.shortfall_count != max(self.required_count - self.available_count, 0):
            raise ValueError("shortfall_count does not match counts")
        if self.satisfied is not (self.available_count >= self.required_count):
            raise ValueError("satisfied does not match counts")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "lookback_coverage",
            "schema_version": _SCHEMA_VERSION,
            "requirement": self.requirement.to_canonical_dict(),
            "window_result_hash": self.window_result_hash,
            "required_count": self.required_count,
            "available_count": self.available_count,
            "shortfall_count": self.shortfall_count,
            "satisfied": self.satisfied,
        }


@dataclass(frozen=True, slots=True)
class WarmupEligibility:
    schedule_hash: str
    entry: DecisionScheduleEntry
    coverage: tuple[LookbackCoverage, ...]
    lookback_satisfied: bool
    strategy_invocation_eligible: bool
    trading_side_effects_authorized: bool
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        _hash("schedule_hash", self.schedule_hash)
        if type(self.entry) is not DecisionScheduleEntry:
            raise TypeError("entry must be DecisionScheduleEntry")
        if type(self.coverage) is not tuple or any(
            type(value) is not LookbackCoverage for value in self.coverage
        ):
            raise TypeError("coverage must be tuple of LookbackCoverage")
        keys = tuple(value.requirement.requirement_key for value in self.coverage)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("coverage must use canonical unique requirement order")
        satisfied = all(value.satisfied for value in self.coverage)
        if self.lookback_satisfied is not satisfied:
            raise ValueError("lookback_satisfied does not match coverage")
        if self.strategy_invocation_eligible is not satisfied:
            raise ValueError("strategy_invocation_eligible does not match lookback")
        expected_trading = satisfied and self.entry.segment is TimelineSegment.ACTIVE_TRADING
        if self.trading_side_effects_authorized is not expected_trading:
            raise ValueError("trading_side_effects_authorized does not match segment")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G11E grade flags must remain false")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "warmup_eligibility",
            "schema_version": _SCHEMA_VERSION,
            "schedule_hash": self.schedule_hash,
            "entry": self.entry.to_canonical_dict(),
            "coverage": [value.to_canonical_dict() for value in self.coverage],
            "lookback_satisfied": self.lookback_satisfied,
            "strategy_invocation_eligible": self.strategy_invocation_eligible,
            "trading_side_effects_authorized": self.trading_side_effects_authorized,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def eligibility_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "eligibility_hash": self.eligibility_hash}


@dataclass(frozen=True, slots=True)
class DecisionSchedule:
    key: str
    version: int
    window: TimelineWindow
    entries: tuple[DecisionScheduleEntry, ...]
    requirements: tuple[LookbackRequirement, ...]

    def __post_init__(self) -> None:
        _text("schedule key", self.key)
        if type(self.version) is not int or self.version <= 0:
            raise ValueError("schedule version must be positive integer")
        if type(self.window) is not TimelineWindow:
            raise TypeError("window must be TimelineWindow")
        if type(self.entries) is not tuple or not self.entries:
            raise ValueError("entries must be nonempty tuple")
        if any(type(entry) is not DecisionScheduleEntry for entry in self.entries):
            raise TypeError("entries must contain DecisionScheduleEntry")
        entry_keys = tuple(_instant_key(entry.decision_instant) for entry in self.entries)
        if entry_keys != tuple(sorted(entry_keys)) or len(entry_keys) != len(set(entry_keys)):
            raise ValueError("entries must be strictly increasing and unique")
        for entry in self.entries:
            instant = entry.decision_instant.instant
            if not self.window.data_start <= instant < self.window.end_exclusive:
                raise ValueError("entry must be inside half-open TimelineWindow")
            segment = (
                TimelineSegment.WARMUP
                if instant < self.window.trading_start
                else TimelineSegment.ACTIVE_TRADING
            )
            if entry.segment is not segment:
                raise ValueError("entry segment does not match TimelineWindow")
        if type(self.requirements) is not tuple or any(
            type(value) is not LookbackRequirement for value in self.requirements
        ):
            raise TypeError("requirements must be tuple of LookbackRequirement")
        ordered = tuple(
            sorted(
                self.requirements,
                key=lambda value: (
                    value.requirement_key,
                    value.observation_query.query_hash,
                    value.bar_definition.bar_definition_ref_hash,
                ),
            )
        )
        requirement_keys = [value.requirement_key for value in ordered]
        identities = [
            (
                value.observation_query.query_hash,
                value.bar_definition.bar_definition_ref_hash,
            )
            for value in ordered
        ]
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("requirement keys must be unique")
        if len(identities) != len(set(identities)):
            raise ValueError("requirement selector/definition identities must be unique")
        object.__setattr__(self, "requirements", ordered)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "decision_schedule",
            "schema_version": _SCHEMA_VERSION,
            "key": self.key,
            "version": self.version,
            "window": self.window.to_canonical_dict(),
            "entries": [entry.to_canonical_dict() for entry in self.entries],
            "requirements": [value.to_canonical_dict() for value in self.requirements],
        }

    @property
    def schedule_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "schedule_hash": self.schedule_hash}

    def eligibility(
        self,
        entry: DecisionScheduleEntry,
        windows: tuple[NamedBarWindowResult, ...],
    ) -> WarmupEligibility:
        if type(entry) is not DecisionScheduleEntry or entry not in self.entries:
            raise ValueError("entry must be exact schedule member")
        if type(windows) is not tuple or any(
            type(value) is not NamedBarWindowResult for value in windows
        ):
            raise TypeError("windows must be tuple of NamedBarWindowResult")
        matches: dict[tuple[str, str], NamedBarWindowResult] = {}
        for value in windows:
            if value.query.decision_instant != entry.decision_instant:
                raise ValueError("window Decision Instant must match entry")
            identity = (
                value.query.observation_query.query_hash,
                value.query.bar_definition.bar_definition_ref_hash,
            )
            if identity in matches:
                raise ValueError("window evidence must be unique")
            matches[identity] = value
        expected = {
            (
                value.observation_query.query_hash,
                value.bar_definition.bar_definition_ref_hash,
            )
            for value in self.requirements
        }
        if set(matches) != expected:
            raise ValueError("window evidence must exact-cover requirements")
        coverage_values: list[LookbackCoverage] = []
        for requirement in self.requirements:
            identity = (
                requirement.observation_query.query_hash,
                requirement.bar_definition.bar_definition_ref_hash,
            )
            result = matches[identity]
            coverage_values.append(
                LookbackCoverage(
                    requirement=requirement,
                    window_result_hash=result.result_hash,
                    required_count=requirement.minimum_count,
                    available_count=result.available_count,
                    shortfall_count=max(
                        requirement.minimum_count - result.available_count, 0
                    ),
                    satisfied=result.available_count >= requirement.minimum_count,
                )
            )
        coverage = tuple(coverage_values)
        satisfied = all(value.satisfied for value in coverage)
        return WarmupEligibility(
            schedule_hash=self.schedule_hash,
            entry=entry,
            coverage=coverage,
            lookback_satisfied=satisfied,
            strategy_invocation_eligible=satisfied,
            trading_side_effects_authorized=(
                satisfied and entry.segment is TimelineSegment.ACTIVE_TRADING
            ),
            decision_grade_eligible=False,
            deployment_authorized=False,
        )
