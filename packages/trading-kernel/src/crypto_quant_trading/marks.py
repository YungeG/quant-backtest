"""Deterministic point-in-time mark resolution over supplied observations."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Price,
    PricePurpose,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
)


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be NFC text")


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256 digest")


def _validate_price_identity(
    instrument_id: InstrumentId,
    quote_currency_id: CurrencyId,
    price_purpose: PricePurpose,
    price: Price,
) -> None:
    if not isinstance(instrument_id, InstrumentId):
        raise TypeError("instrument_id must be InstrumentId")
    if not isinstance(quote_currency_id, CurrencyId):
        raise TypeError("quote_currency_id must be CurrencyId")
    if not isinstance(price_purpose, PricePurpose):
        raise TypeError("price_purpose must be PricePurpose")
    if not isinstance(price, Price):
        raise TypeError("price must be Price")
    if price.instrument_id != str(instrument_id):
        raise ValueError("price instrument identity mismatch")
    if price.quote_currency != str(quote_currency_id):
        raise ValueError("price currency identity mismatch")


@dataclass(frozen=True, slots=True)
class MarkObservation:
    """One immutable, purpose-specific price-stream fact supplied to a resolver."""

    instrument_id: InstrumentId
    quote_currency_id: CurrencyId
    price_purpose: PricePurpose
    price: Price
    observed_at: UtcInstant
    available_at: UtcInstant
    stream_id: str
    source_event_id: str
    revision_id: str

    def __post_init__(self) -> None:
        _validate_price_identity(
            self.instrument_id,
            self.quote_currency_id,
            self.price_purpose,
            self.price,
        )
        if not isinstance(self.observed_at, UtcInstant):
            raise TypeError("observed_at must be UtcInstant")
        if not isinstance(self.available_at, UtcInstant):
            raise TypeError("available_at must be UtcInstant")
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        _require_text("stream_id", self.stream_id)
        _require_text("source_event_id", self.source_event_id)
        _require_text("revision_id", self.revision_id)

    @property
    def observation_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "mark_observation",
            "instrument_id": self.instrument_id,
            "quote_currency_id": self.quote_currency_id,
            "price_purpose": self.price_purpose.value,
            "price": self.price,
            "observed_at": self.observed_at,
            "available_at": self.available_at,
            "stream_id": self.stream_id,
            "source_event_id": self.source_event_id,
            "revision_id": self.revision_id,
        }


@dataclass(frozen=True, slots=True)
class StaleMarkPolicy:
    """Versioned freshness policy for one and only one price purpose."""

    policy_key: str
    policy_version: int
    price_purpose: PricePurpose
    max_age_nanoseconds: int
    allow_forward_fill: bool

    def __post_init__(self) -> None:
        _require_text("policy_key", self.policy_key)
        if isinstance(self.policy_version, bool) or not isinstance(
            self.policy_version, int
        ):
            raise TypeError("policy_version must be an integer")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        if not isinstance(self.price_purpose, PricePurpose):
            raise TypeError("price_purpose must be PricePurpose")
        if isinstance(self.max_age_nanoseconds, bool) or not isinstance(
            self.max_age_nanoseconds, int
        ):
            raise TypeError("max_age_nanoseconds must be an integer")
        if self.max_age_nanoseconds < 0:
            raise ValueError("max_age_nanoseconds cannot be negative")
        if not isinstance(self.allow_forward_fill, bool):
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
class ResolvedMark:
    """The unique mark selected for one purpose at one requested instant."""

    instrument_id: InstrumentId
    quote_currency_id: CurrencyId
    price_purpose: PricePurpose
    price: Price
    observed_at: UtcInstant
    available_at: UtcInstant
    resolved_at: UtcInstant
    age_nanoseconds: int
    stream_id: str
    source_event_id: str
    revision_id: str
    stale_policy_key: str
    stale_policy_version: int
    stale_policy_hash: str
    available_at_instant: SimulationInstant | None = field(default=None, kw_only=True)
    resolved_at_instant: SimulationInstant | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        _validate_price_identity(
            self.instrument_id,
            self.quote_currency_id,
            self.price_purpose,
            self.price,
        )
        for name, value in (
            ("observed_at", self.observed_at),
            ("available_at", self.available_at),
            ("resolved_at", self.resolved_at),
        ):
            if not isinstance(value, UtcInstant):
                raise TypeError(f"{name} must be UtcInstant")
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        if self.resolved_at < self.available_at:
            raise ValueError("resolved_at cannot precede available_at")
        if (self.available_at_instant is None) != (self.resolved_at_instant is None):
            raise ValueError("exact mark availability and resolution must share mode")
        if self.available_at_instant is not None:
            if not isinstance(self.available_at_instant, SimulationInstant):
                raise TypeError("available_at_instant must be SimulationInstant or None")
            if not isinstance(self.resolved_at_instant, SimulationInstant):
                raise TypeError("resolved_at_instant must be SimulationInstant or None")
            if self.available_at_instant.instant != self.available_at:
                raise ValueError("available_at_instant instant must equal available_at")
            if self.resolved_at_instant.instant != self.resolved_at:
                raise ValueError("resolved_at_instant instant must equal resolved_at")
            if self.resolved_at_instant < self.available_at_instant:
                raise ValueError("resolved_at_instant cannot precede available_at_instant")
        expected_age = (
            self.resolved_at.epoch_nanoseconds
            - self.observed_at.epoch_nanoseconds
        )
        if self.age_nanoseconds != expected_age or self.age_nanoseconds < 0:
            raise ValueError("age_nanoseconds must match resolved_at - observed_at")
        _require_text("stream_id", self.stream_id)
        _require_text("source_event_id", self.source_event_id)
        _require_text("revision_id", self.revision_id)
        _require_text("stale_policy_key", self.stale_policy_key)
        if isinstance(self.stale_policy_version, bool) or not isinstance(
            self.stale_policy_version, int
        ):
            raise TypeError("stale_policy_version must be an integer")
        if self.stale_policy_version <= 0:
            raise ValueError("stale_policy_version must be positive")
        _require_sha256("stale_policy_hash", self.stale_policy_hash)

    @property
    def mark_id(self) -> str:
        return canonical_sha256(self._canonical_body())

    def _canonical_body(self) -> dict[str, Any]:
        value = {
            "instrument_id": self.instrument_id,
            "quote_currency_id": self.quote_currency_id,
            "price_purpose": self.price_purpose.value,
            "price": self.price,
            "observed_at": self.observed_at,
            "available_at": self.available_at,
            "resolved_at": self.resolved_at,
            "age_nanoseconds": self.age_nanoseconds,
            "stream_id": self.stream_id,
            "source_event_id": self.source_event_id,
            "revision_id": self.revision_id,
            "stale_policy_key": self.stale_policy_key,
            "stale_policy_version": self.stale_policy_version,
            "stale_policy_hash": self.stale_policy_hash,
        }
        if self.available_at_instant is not None:
            value["available_at_instant"] = self.available_at_instant
            value["resolved_at_instant"] = self.resolved_at_instant
        return value

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "resolved_mark", "mark_id": self.mark_id, **self._canonical_body()}


class MarkResolutionFailureCode(str, Enum):
    MISSING_MARK = "missing_mark"
    PRICE_PURPOSE_UNAVAILABLE = "price_purpose_unavailable"
    AMBIGUOUS_MARK = "ambiguous_mark"
    STALE_MARK = "stale_mark"


@dataclass(frozen=True, slots=True)
class MarkResolutionFailure:
    """Stable fail-closed evidence for an unsuccessful mark resolution."""

    code: MarkResolutionFailureCode
    instrument_id: InstrumentId
    price_purpose: PricePurpose
    requested_at: UtcInstant
    candidate_count: int
    candidate_observation_hashes: tuple[str, ...]
    selected_observed_at: UtcInstant | None
    stale_policy_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, MarkResolutionFailureCode):
            raise TypeError("code must be MarkResolutionFailureCode")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.price_purpose, PricePurpose):
            raise TypeError("price_purpose must be PricePurpose")
        if not isinstance(self.requested_at, UtcInstant):
            raise TypeError("requested_at must be UtcInstant")
        if isinstance(self.candidate_count, bool) or not isinstance(
            self.candidate_count, int
        ):
            raise TypeError("candidate_count must be an integer")
        if self.candidate_count < 0:
            raise ValueError("candidate_count cannot be negative")
        if not isinstance(self.candidate_observation_hashes, tuple):
            raise TypeError("candidate_observation_hashes must be a tuple")
        for value in self.candidate_observation_hashes:
            _require_sha256("candidate observation hash", value)
        if self.candidate_observation_hashes != tuple(
            sorted(self.candidate_observation_hashes)
        ):
            raise ValueError("candidate_observation_hashes must use canonical order")
        if self.candidate_count != len(self.candidate_observation_hashes):
            raise ValueError("candidate_count must match candidate_observation_hashes")
        if self.selected_observed_at is not None and not isinstance(
            self.selected_observed_at, UtcInstant
        ):
            raise TypeError("selected_observed_at must be UtcInstant or None")
        _require_sha256("stale_policy_hash", self.stale_policy_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "mark_resolution_failure",
            "code": self.code.value,
            "instrument_id": self.instrument_id,
            "price_purpose": self.price_purpose.value,
            "requested_at": self.requested_at,
            "candidate_count": self.candidate_count,
            "candidate_observation_hashes": self.candidate_observation_hashes,
            "selected_observed_at": self.selected_observed_at,
            "stale_policy_hash": self.stale_policy_hash,
        }


@dataclass(frozen=True, slots=True)
class MarkResolutionOutcome:
    """Exactly one resolved mark or one structured failure."""

    resolved_mark: ResolvedMark | None
    failure: MarkResolutionFailure | None

    def __post_init__(self) -> None:
        if (self.resolved_mark is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one resolved mark or failure")
        if self.resolved_mark is not None and not isinstance(
            self.resolved_mark, ResolvedMark
        ):
            raise TypeError("resolved_mark must be ResolvedMark or None")
        if self.failure is not None and not isinstance(
            self.failure, MarkResolutionFailure
        ):
            raise TypeError("failure must be MarkResolutionFailure or None")

    def to_canonical_dict(self) -> dict[str, Any]:
        if self.resolved_mark is not None:
            return {
                "type": "mark_resolution_outcome",
                "status": "resolved",
                "resolved_mark": self.resolved_mark,
            }
        return {
            "type": "mark_resolution_outcome",
            "status": "failed",
            "failure": self.failure,
        }


class MarkResolver:
    """Resolve one mark without owning or querying a data source."""

    def resolve(
        self,
        observations: tuple[MarkObservation, ...],
        *,
        instrument_id: InstrumentId,
        price_purpose: PricePurpose,
        requested_at: UtcInstant,
        stale_policy: StaleMarkPolicy,
    ) -> MarkResolutionOutcome:
        if not isinstance(observations, tuple) or not all(
            isinstance(value, MarkObservation) for value in observations
        ):
            raise TypeError("observations must be a tuple of MarkObservation")
        if not isinstance(instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(price_purpose, PricePurpose):
            raise TypeError("price_purpose must be PricePurpose")
        if not isinstance(requested_at, UtcInstant):
            raise TypeError("requested_at must be UtcInstant")
        if not isinstance(stale_policy, StaleMarkPolicy):
            raise TypeError("stale_policy must be StaleMarkPolicy")

        if stale_policy.price_purpose is not price_purpose:
            return self._failure(
                MarkResolutionFailureCode.PRICE_PURPOSE_UNAVAILABLE,
                instrument_id,
                price_purpose,
                requested_at,
                stale_policy,
            )

        instrument_observations = tuple(
            value for value in observations if value.instrument_id == instrument_id
        )
        if not instrument_observations:
            return self._failure(
                MarkResolutionFailureCode.MISSING_MARK,
                instrument_id,
                price_purpose,
                requested_at,
                stale_policy,
            )

        purpose_observations = tuple(
            value
            for value in instrument_observations
            if value.price_purpose is price_purpose
        )
        if not purpose_observations:
            return self._failure(
                MarkResolutionFailureCode.PRICE_PURPOSE_UNAVAILABLE,
                instrument_id,
                price_purpose,
                requested_at,
                stale_policy,
            )

        eligible = tuple(
            value
            for value in purpose_observations
            if value.observed_at <= requested_at
            and value.available_at <= requested_at
        )
        if not eligible:
            return self._failure(
                MarkResolutionFailureCode.MISSING_MARK,
                instrument_id,
                price_purpose,
                requested_at,
                stale_policy,
            )

        latest_instant = max(value.observed_at for value in eligible)
        latest = tuple(
            value for value in eligible if value.observed_at == latest_instant
        )
        if len(latest) != 1:
            return self._failure(
                MarkResolutionFailureCode.AMBIGUOUS_MARK,
                instrument_id,
                price_purpose,
                requested_at,
                stale_policy,
                candidate_observations=latest,
                selected_observed_at=latest_instant,
            )

        selected = latest[0]
        age = requested_at.epoch_nanoseconds - selected.observed_at.epoch_nanoseconds
        if age > stale_policy.max_age_nanoseconds or (
            age > 0 and not stale_policy.allow_forward_fill
        ):
            return self._failure(
                MarkResolutionFailureCode.STALE_MARK,
                instrument_id,
                price_purpose,
                requested_at,
                stale_policy,
                candidate_observations=(selected,),
                selected_observed_at=selected.observed_at,
            )

        return MarkResolutionOutcome(
            resolved_mark=ResolvedMark(
                instrument_id=selected.instrument_id,
                quote_currency_id=selected.quote_currency_id,
                price_purpose=selected.price_purpose,
                price=selected.price,
                observed_at=selected.observed_at,
                available_at=selected.available_at,
                resolved_at=requested_at,
                age_nanoseconds=age,
                stream_id=selected.stream_id,
                source_event_id=selected.source_event_id,
                revision_id=selected.revision_id,
                stale_policy_key=stale_policy.policy_key,
                stale_policy_version=stale_policy.policy_version,
                stale_policy_hash=stale_policy.policy_hash,
            ),
            failure=None,
        )

    @staticmethod
    def _failure(
        code: MarkResolutionFailureCode,
        instrument_id: InstrumentId,
        price_purpose: PricePurpose,
        requested_at: UtcInstant,
        stale_policy: StaleMarkPolicy,
        *,
        candidate_observations: tuple[MarkObservation, ...] = (),
        selected_observed_at: UtcInstant | None = None,
    ) -> MarkResolutionOutcome:
        return MarkResolutionOutcome(
            resolved_mark=None,
            failure=MarkResolutionFailure(
                code=code,
                instrument_id=instrument_id,
                price_purpose=price_purpose,
                requested_at=requested_at,
                candidate_count=len(candidate_observations),
                candidate_observation_hashes=tuple(
                    sorted(value.observation_hash for value in candidate_observations)
                ),
                selected_observed_at=selected_observed_at,
                stale_policy_hash=stale_policy.policy_hash,
            ),
        )
