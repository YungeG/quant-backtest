from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, cast

from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _positive_int(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
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


def _utc(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be UtcInstant")
    return value


def _scope(value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("closure_scope_key must be a 3-tuple")
    scope = cast(tuple[object, ...], value)
    if len(scope) != 3:
        raise TypeError("closure_scope_key must be a 3-tuple")
    for item in scope:
        _text("closure_scope_key item", item)


def _development_only(
    decision_grade_eligible: object, deployment_authorized: object
) -> None:
    if decision_grade_eligible is not False:
        raise ValueError("declaration must remain development-only")
    if deployment_authorized is not False:
        raise ValueError("declaration cannot authorize deployment")


@dataclass(frozen=True, slots=True)
class BuilderStaleMarkPolicy:
    """Kernel-independent canonical projection of G03 ``StaleMarkPolicy``."""

    schema_version: ClassVar[int] = 1

    policy_key: str
    policy_version: int
    price_purpose: PricePurpose
    max_age_nanoseconds: int
    allow_forward_fill: bool

    def __post_init__(self) -> None:
        _text("policy_key", self.policy_key)
        _positive_int("policy_version", self.policy_version)
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be PricePurpose")
        if type(self.max_age_nanoseconds) is not int:
            raise TypeError("max_age_nanoseconds must be an integer")
        if self.max_age_nanoseconds < 0:
            raise ValueError("max_age_nanoseconds cannot be negative")
        if type(self.allow_forward_fill) is not bool:
            raise TypeError("allow_forward_fill must be bool")

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "stale_mark_policy",
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "price_purpose": self.price_purpose.value,
            "max_age_nanoseconds": self.max_age_nanoseconds,
            "allow_forward_fill": self.allow_forward_fill,
        }


@dataclass(frozen=True, slots=True)
class PricePurposeRequirement:
    """Passive development-only declaration for one purpose and stream scope."""

    schema_version: ClassVar[int] = 1

    requirement_key: str
    requirement_version: int
    scope_key: str
    instrument_id: InstrumentId
    price_purpose: PricePurpose
    stream_key: str
    event_type: str
    capability: MarketBundleCapability
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    stale_policy: BuilderStaleMarkPolicy
    source_key: str
    source_hash: str
    decision_grade_eligible: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _text("requirement_key", self.requirement_key)
        _positive_int("requirement_version", self.requirement_version)
        _text("scope_key", self.scope_key)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be InstrumentId")
        if type(self.price_purpose) is not PricePurpose:
            raise TypeError("price_purpose must be PricePurpose")
        _text("stream_key", self.stream_key)
        _text("event_type", self.event_type)
        if type(self.capability) is not MarketBundleCapability:
            raise TypeError("capability must be MarketBundleCapability")
        MarketBundleCapability(self.capability.key, self.capability.version)
        start = _utc("coverage_start", self.coverage_start)
        end = _utc("coverage_end_exclusive", self.coverage_end_exclusive)
        if end <= start:
            raise ValueError("coverage must be a non-empty half-open range")
        if type(self.stale_policy) is not BuilderStaleMarkPolicy:
            raise TypeError("stale_policy must be BuilderStaleMarkPolicy")
        if self.stale_policy.price_purpose is not self.price_purpose:
            raise ValueError("stale policy purpose must match requirement purpose")
        if self.stale_policy.allow_forward_fill and self.price_purpose in (
            PricePurpose.EXECUTION_REFERENCE,
            PricePurpose.LIQUIDATION,
        ):
            raise ValueError(
                "execution_reference and liquidation cannot allow forward fill"
            )
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)
        _development_only(
            self.decision_grade_eligible,
            self.deployment_authorized,
        )

    def _canonical_body(self) -> dict[str, Any]:
        return {
            "type": "price_purpose_requirement",
            "schema_version": self.schema_version,
            "requirement_key": self.requirement_key,
            "requirement_version": self.requirement_version,
            "scope_key": self.scope_key,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "price_purpose": self.price_purpose.value,
            "stream_key": self.stream_key,
            "event_type": self.event_type,
            "capability": self.capability.to_canonical_dict(),
            "coverage_start": self.coverage_start.to_canonical_dict(),
            "coverage_end_exclusive": self.coverage_end_exclusive.to_canonical_dict(),
            "stale_policy": self.stale_policy.to_canonical_dict(),
            "stale_policy_hash": self.stale_policy.policy_hash,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def requirement_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, Any]:
        return {**self._canonical_body(), "requirement_hash": self.requirement_hash}


class MarketAvailabilityReason(str, Enum):
    NO_SESSION = "NO_SESSION"
    SUSPENDED = "SUSPENDED"
    NO_TRADES = "NO_TRADES"
    MISSING = "MISSING"
    SOURCE_OUTAGE = "SOURCE_OUTAGE"


@dataclass(frozen=True, slots=True)
class AvailabilitySpan:
    schema_version: ClassVar[int] = 1

    start: UtcInstant
    end_exclusive: UtcInstant
    reason: MarketAvailabilityReason

    def __post_init__(self) -> None:
        start = _utc("start", self.start)
        end = _utc("end_exclusive", self.end_exclusive)
        if end <= start:
            raise ValueError("span must be a non-empty half-open range")
        if type(self.reason) is not MarketAvailabilityReason:
            raise TypeError("reason must be MarketAvailabilityReason")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "availability_span",
            "schema_version": self.schema_version,
            "start": self.start.to_canonical_dict(),
            "end_exclusive": self.end_exclusive.to_canonical_dict(),
            "reason": self.reason.value,
        }


@dataclass(frozen=True, slots=True)
class AvailabilityClosureDeclaration:
    schema_version: ClassVar[int] = 1

    closure_scope_key: tuple[str, str, str]
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    spans: tuple[AvailabilitySpan, ...]
    source_key: str
    source_hash: str
    bar_aggregation_manifest_hash: str
    decision_grade_eligible: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _scope(self.closure_scope_key)
        start = _utc("coverage_start", self.coverage_start)
        end = _utc("coverage_end_exclusive", self.coverage_end_exclusive)
        if end < start:
            raise ValueError("coverage end cannot precede coverage start")
        if type(self.spans) is not tuple or any(
            type(span) is not AvailabilitySpan for span in self.spans
        ):
            raise TypeError("spans must be a tuple of AvailabilitySpan")
        if end == start:
            if self.spans:
                raise ValueError("empty coverage must have no spans")
        else:
            if not self.spans:
                raise ValueError("non-empty coverage requires complete spans")
            if self.spans[0].start != start or self.spans[-1].end_exclusive != end:
                raise ValueError("spans must exactly cover the coverage range")
            for previous, current in zip(self.spans, self.spans[1:], strict=False):
                if current.start < previous.end_exclusive:
                    raise ValueError("spans must be ordered and non-overlapping")
                if current.start > previous.end_exclusive:
                    raise ValueError(
                        "spans must exactly cover the coverage range without gaps"
                    )
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)
        _hash("bar_aggregation_manifest_hash", self.bar_aggregation_manifest_hash)
        _development_only(
            self.decision_grade_eligible,
            self.deployment_authorized,
        )

    def _canonical_body(self) -> dict[str, Any]:
        return {
            "type": "availability_closure_declaration",
            "schema_version": self.schema_version,
            "closure_scope_key": list(self.closure_scope_key),
            "coverage_start": self.coverage_start.to_canonical_dict(),
            "coverage_end_exclusive": self.coverage_end_exclusive.to_canonical_dict(),
            "spans": [span.to_canonical_dict() for span in self.spans],
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "bar_aggregation_manifest_hash": self.bar_aggregation_manifest_hash,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, Any]:
        return {**self._canonical_body(), "declaration_hash": self.declaration_hash}


@dataclass(frozen=True, slots=True)
class RevisionTerminalLineage:
    schema_version: ClassVar[int] = 1

    logical_lineage_key: str
    terminal_event_hash: str

    def __post_init__(self) -> None:
        _text("logical_lineage_key", self.logical_lineage_key)
        _hash("terminal_event_hash", self.terminal_event_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "revision_terminal_lineage",
            "schema_version": self.schema_version,
            "logical_lineage_key": self.logical_lineage_key,
            "terminal_event_hash": self.terminal_event_hash,
        }


@dataclass(frozen=True, slots=True)
class RevisionClosureDeclaration:
    schema_version: ClassVar[int] = 1

    closure_scope_key: tuple[str, str, str]
    causal_visibility_limit: UtcInstant
    terminals: tuple[RevisionTerminalLineage, ...]
    source_key: str
    source_hash: str
    decision_grade_eligible: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _scope(self.closure_scope_key)
        _utc("causal_visibility_limit", self.causal_visibility_limit)
        if type(self.terminals) is not tuple or any(
            type(value) is not RevisionTerminalLineage for value in self.terminals
        ):
            raise TypeError("terminals must be a tuple of RevisionTerminalLineage")
        keys = tuple(value.logical_lineage_key for value in self.terminals)
        if len(set(keys)) != len(keys):
            raise ValueError(
                "duplicate logical lineage keys in RevisionClosureDeclaration"
            )
        if keys != tuple(sorted(keys)):
            raise ValueError("terminal lineage keys must use canonical order")
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)
        _development_only(
            self.decision_grade_eligible,
            self.deployment_authorized,
        )

    def _canonical_body(self) -> dict[str, Any]:
        return {
            "type": "revision_closure_declaration",
            "schema_version": self.schema_version,
            "closure_scope_key": list(self.closure_scope_key),
            "causal_visibility_limit": self.causal_visibility_limit.to_canonical_dict(),
            "terminals": [value.to_canonical_dict() for value in self.terminals],
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, Any]:
        return {**self._canonical_body(), "declaration_hash": self.declaration_hash}
