"""Deterministic linear-perpetual funding publication eligibility."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    CashBalanceKey,
    InstrumentId,
    PositionBalanceKey,
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_sha256,
)

from .derivative_accounting import (
    LinearDerivativeLedgerProjection,
    LinearDerivativeLedgerProjector,
)
from .derivatives import LinearPerpetualContract, LinearPositionState
from .journal import AccountingJournal, JournalReplayCursor

_SCHEMA_VERSION = 1
_COMPONENT_KEY = "instrument.linear-perpetual.funding-eligibility.v1"
_ALGORITHM_KEY = "linear-funding-publication-eligibility-v1"
_RATE_BASIS = "funding_fraction_of_notional"
_ELIGIBILITY_PHASE = TimelinePhase(100, "funding_eligibility")
_ELIGIBILITY_SEQUENCE = SourceSequence(0)
_HASH_PREFIX = "sha256:"


def _text(name: str, value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be exact string")
    if not value or value.strip() != value or unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be canonical non-empty text")


def _hash(name: str, value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be exact string")
    suffix = value.removeprefix(_HASH_PREFIX)
    if (
        not value.startswith(_HASH_PREFIX)
        or len(suffix) != 64
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise ValueError(f"{name} must be canonical sha256")


def _instrument_id(name: str, value: InstrumentId) -> None:
    if not (
        type(value) is InstrumentId
        and type(value.venue) is VenueId
        and type(value.venue.value) is str
        and type(value.stable_key) is str
    ):
        raise TypeError(f"{name} must be an exact InstrumentId tree")


def _position_key(value: PositionBalanceKey) -> None:
    if type(value) is not PositionBalanceKey or type(value.account_id) is not str:
        raise TypeError("position_key must be exact PositionBalanceKey")
    if type(value.venue_id) is not VenueId or type(value.venue_id.value) is not str:
        raise TypeError("position_key Venue must be exact")
    _instrument_id("position_key instrument", value.instrument_id)


def _instant(name: str, value: SimulationInstant) -> None:
    if type(value) is not SimulationInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")
    if type(value.instant) is not UtcInstant or type(value.instant.epoch_nanoseconds) is not int:
        raise TypeError(f"{name} instant must be exact UtcInstant")
    if (
        type(value.phase) is not TimelinePhase
        or type(value.phase.rank) is not int
        or type(value.phase.code) is not str
    ):
        raise TypeError(f"{name} phase must be exact TimelinePhase")
    if (
        type(value.source_sequence) is not SourceSequence
        or type(value.source_sequence.value) is not int
    ):
        raise TypeError(f"{name} sequence must be exact SourceSequence")


def _rate(value: Rate) -> None:
    if type(value) is not Rate or type(value.units) is not int:
        raise TypeError("published_rate must be exact Rate")
    if type(value.scale) is not Scale or type(value.scale.places) is not int:
        raise TypeError("published_rate scale must be exact Scale")
    if type(value.basis) is not str:
        raise TypeError("published_rate basis must be exact string")


def _component_digest() -> str:
    return canonical_sha256(
        {
            "type": "linear_funding_eligibility_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "algorithm_key": _ALGORITHM_KEY,
            "slot_key": "instrument_id+target_funding_time",
            "rate_basis": _RATE_BASIS,
            "eligibility_phase": _ELIGIBILITY_PHASE,
            "eligibility_sequence": _ELIGIBILITY_SEQUENCE,
            "eligibility_cutoff": "journal.recorded_at<eligibility_instant",
            "publication_revision_policy": "closed_linear_chain",
            "position_revision_policy": "supplied_root_only",
            "allowed_grade": "development",
        }
    )


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityComponentRef:
    component_key: str
    component_version: int
    component_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.component_key) is not str
            or self.component_key != _COMPONENT_KEY
        ):
            raise ValueError("component_key must identify funding eligibility v1")
        if type(self.component_version) is not int or self.component_version != 1:
            raise ValueError("component_version must be 1")
        _hash("component_digest", self.component_digest)
        if self.component_digest != _component_digest():
            raise ValueError("component_digest must match frozen semantics")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_eligibility_component_ref",
            "schema_version": _SCHEMA_VERSION,
            "component_key": self.component_key,
            "component_version": self.component_version,
            "component_digest": self.component_digest,
        }


def _component_ref() -> LinearFundingEligibilityComponentRef:
    return LinearFundingEligibilityComponentRef(
        _COMPONENT_KEY, 1, _component_digest()
    )


@dataclass(frozen=True, slots=True)
class FundingSlotId:
    instrument_id: InstrumentId
    target_funding_time: UtcInstant
    value: str

    def __post_init__(self) -> None:
        _instrument_id("instrument_id", self.instrument_id)
        if type(self.target_funding_time) is not UtcInstant or type(
            self.target_funding_time.epoch_nanoseconds
        ) is not int:
            raise TypeError("target_funding_time must be exact UtcInstant")
        _text("value", self.value)
        if self.value != self._expected_value(
            self.instrument_id, self.target_funding_time
        ):
            raise ValueError("funding Slot value must match semantic key")

    @staticmethod
    def _expected_value(
        instrument_id: InstrumentId, target_funding_time: UtcInstant
    ) -> str:
        digest = canonical_sha256(
            {
                "type": "funding_slot_semantic_key",
                "schema_version": _SCHEMA_VERSION,
                "instrument_id": instrument_id,
                "target_funding_time": target_funding_time,
            }
        )
        return "funding-slot-v1:" + digest.removeprefix("sha256:")

    @classmethod
    def derive(
        cls, instrument_id: InstrumentId, target_funding_time: UtcInstant
    ) -> FundingSlotId:
        _instrument_id("instrument_id", instrument_id)
        if type(target_funding_time) is not UtcInstant:
            raise TypeError("target_funding_time must be exact UtcInstant")
        return cls(
            instrument_id,
            target_funding_time,
            cls._expected_value(instrument_id, target_funding_time),
        )

    @property
    def slot_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "funding_slot_id",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id,
            "target_funding_time": self.target_funding_time,
            "value": self.value,
        }


class LinearFundingPublicationStatus(str, Enum):
    FINAL_RATE = "final_rate"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class LinearFundingRatePublicationCandidate:
    slot_id: FundingSlotId
    status: LinearFundingPublicationStatus
    published_rate: Rate | None
    event_id: str
    event_hash: str
    event_time: UtcInstant
    publication_available_at: SimulationInstant
    revision_id: str
    supersedes_revision_id: str | None
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        if type(self.slot_id) is not FundingSlotId:
            raise TypeError("slot_id must be exact FundingSlotId")
        if type(self.status) is not LinearFundingPublicationStatus:
            raise TypeError("status must be exact LinearFundingPublicationStatus")
        if self.published_rate is not None:
            _rate(self.published_rate)
        if (self.status is LinearFundingPublicationStatus.FINAL_RATE) != (
            self.published_rate is not None
        ):
            raise ValueError("FINAL_RATE requires Rate and CANCELLED requires none")
        _text("event_id", self.event_id)
        _hash("event_hash", self.event_hash)
        if type(self.event_time) is not UtcInstant or type(
            self.event_time.epoch_nanoseconds
        ) is not int:
            raise TypeError("event_time must be exact UtcInstant")
        _instant("publication_available_at", self.publication_available_at)
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    @property
    def publication_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_rate_publication_candidate",
            "schema_version": _SCHEMA_VERSION,
            "slot_id": self.slot_id,
            "status": self.status.value,
            "published_rate": self.published_rate,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "event_time": self.event_time,
            "publication_available_at": self.publication_available_at,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


def _cutoff_replay(
    availability_projection: LinearDerivativeLedgerProjection,
    eligibility_instant: SimulationInstant,
) -> tuple[JournalReplayCursor, LinearPositionState]:
    journal = availability_projection.request.journal
    count = 0
    for entry in journal.entries:
        if entry.recorded_at < eligibility_instant:
            count += 1
        else:
            break
    prefix = AccountingJournal(journal.entries[:count])
    replay_request = replace(availability_projection.request, journal=prefix)
    outcome = LinearDerivativeLedgerProjector().project(replay_request)
    if outcome.result is None:
        raise ValueError("eligibility prefix must be valid G09B replay")
    return outcome.result.cursor, outcome.result.position_state


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityPositionSnapshot:
    snapshot_id: str
    eligibility_series_id: str
    revision_id: str
    supersedes_revision_id: str | None
    slot_id: FundingSlotId
    eligibility_instant: SimulationInstant
    available_at: SimulationInstant
    eligibility_cursor: JournalReplayCursor
    availability_projection: LinearDerivativeLedgerProjection
    position_state: LinearPositionState

    def __post_init__(self) -> None:
        _text("snapshot_id", self.snapshot_id)
        _text("eligibility_series_id", self.eligibility_series_id)
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        if type(self.slot_id) is not FundingSlotId:
            raise TypeError("slot_id must be exact FundingSlotId")
        _instant("eligibility_instant", self.eligibility_instant)
        _instant("available_at", self.available_at)
        if type(self.eligibility_cursor) is not JournalReplayCursor:
            raise TypeError("eligibility_cursor must be exact JournalReplayCursor")
        if type(self.availability_projection) is not LinearDerivativeLedgerProjection:
            raise TypeError("availability_projection must be exact G09B Projection")
        if type(self.position_state) is not LinearPositionState:
            raise TypeError("position_state must be exact LinearPositionState")
        full = LinearDerivativeLedgerProjector().project(
            self.availability_projection.request
        )
        if full.result is None or canonical_sha256(
            full.result
        ) != canonical_sha256(self.availability_projection):
            raise ValueError("availability_projection must match embedded G09B replay")
        cursor, state = _cutoff_replay(
            self.availability_projection, self.eligibility_instant
        )
        if canonical_sha256(self.eligibility_cursor) != canonical_sha256(cursor):
            raise ValueError("eligibility_cursor must match maximal cutoff prefix")
        if canonical_sha256(self.position_state) != canonical_sha256(state):
            raise ValueError("position_state must match cutoff G09B replay")

    @property
    def snapshot_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_eligibility_position_snapshot",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "eligibility_series_id": self.eligibility_series_id,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "slot_id": self.slot_id,
            "eligibility_instant": self.eligibility_instant,
            "available_at": self.available_at,
            "eligibility_cursor": self.eligibility_cursor,
            "availability_projection": self.availability_projection,
            "position_state": self.position_state,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityPositionSnapshotV2:
    """Thin funding eligibility attestation; full ledger replays stay runtime-local."""

    snapshot_id: str
    eligibility_series_id: str
    revision_id: str
    supersedes_revision_id: str | None
    slot_id: FundingSlotId
    eligibility_instant: SimulationInstant
    available_at: SimulationInstant
    eligibility_cursor: JournalReplayCursor
    availability_cursor: JournalReplayCursor
    eligibility_ledger_state_hash: str
    availability_ledger_state_hash: str
    eligibility_replay_hash: str
    availability_replay_hash: str
    eligibility_position_state: LinearPositionState
    availability_position_state: LinearPositionState

    def __post_init__(self) -> None:
        for name in ("snapshot_id", "eligibility_series_id", "revision_id"):
            _text(name, getattr(self, name))
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        if type(self.slot_id) is not FundingSlotId:
            raise TypeError("slot_id must be exact FundingSlotId")
        _instant("eligibility_instant", self.eligibility_instant)
        _instant("available_at", self.available_at)
        if self.available_at < self.eligibility_instant:
            raise ValueError("available_at must not precede eligibility_instant")
        if type(self.eligibility_cursor) is not JournalReplayCursor or type(self.availability_cursor) is not JournalReplayCursor:
            raise TypeError("thin snapshot cursors must be exact JournalReplayCursor")
        for name in (
            "eligibility_ledger_state_hash", "availability_ledger_state_hash",
            "eligibility_replay_hash", "availability_replay_hash",
        ):
            _hash(name, getattr(self, name))
        if type(self.eligibility_position_state) is not LinearPositionState or type(self.availability_position_state) is not LinearPositionState:
            raise TypeError("thin snapshot position states must be exact LinearPositionState")
        if self.eligibility_cursor.position > self.availability_cursor.position:
            raise ValueError("eligibility cursor cannot exceed availability cursor")

    @property
    def snapshot_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_eligibility_position_snapshot",
            "schema_version": 2,
            "snapshot_id": self.snapshot_id,
            "eligibility_series_id": self.eligibility_series_id,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "slot_id": self.slot_id,
            "eligibility_instant": self.eligibility_instant,
            "available_at": self.available_at,
            "eligibility_cursor": self.eligibility_cursor,
            "availability_cursor": self.availability_cursor,
            "eligibility_ledger_state_hash": self.eligibility_ledger_state_hash,
            "availability_ledger_state_hash": self.availability_ledger_state_hash,
            "eligibility_replay_hash": self.eligibility_replay_hash,
            "availability_replay_hash": self.availability_replay_hash,
            "eligibility_position_state": self.eligibility_position_state,
            "availability_position_state": self.availability_position_state,
        }


def derive_linear_funding_eligibility_snapshot_v2(
    *,
    snapshot_id: str,
    eligibility_series_id: str,
    revision_id: str,
    supersedes_revision_id: str | None,
    slot_id: FundingSlotId,
    eligibility_instant: SimulationInstant,
    available_at: SimulationInstant,
    eligibility_projection: LinearDerivativeLedgerProjection,
    availability_projection: LinearDerivativeLedgerProjection,
) -> LinearFundingEligibilityPositionSnapshotV2:
    """Derive a thin attestation from the two verifier-owned full replays."""
    if (
        type(eligibility_projection) is not LinearDerivativeLedgerProjection
        or type(availability_projection) is not LinearDerivativeLedgerProjection
    ):
        raise TypeError("thin snapshot replays must be exact G09B Projections")
    expected_cutoff_request = replace(
        availability_projection.request,
        journal=AccountingJournal(
            tuple(
                entry
                for entry in availability_projection.request.journal.entries
                if entry.recorded_at < eligibility_instant
            )
        ),
    )
    if eligibility_projection.request != expected_cutoff_request:
        raise ValueError("eligibility replay must equal the availability cutoff")
    return LinearFundingEligibilityPositionSnapshotV2(
        snapshot_id, eligibility_series_id, revision_id, supersedes_revision_id,
        slot_id, eligibility_instant, available_at, eligibility_projection.cursor,
        availability_projection.cursor, eligibility_projection.ledger_state_hash,
        availability_projection.ledger_state_hash, canonical_sha256(eligibility_projection),
        canonical_sha256(availability_projection), eligibility_projection.position_state,
        availability_projection.position_state,
    )


def thin_snapshot_v2_matches_replay(
    snapshot: LinearFundingEligibilityPositionSnapshotV2,
    eligibility_projection: LinearDerivativeLedgerProjection,
    availability_projection: LinearDerivativeLedgerProjection,
) -> bool:
    """Fail closed unless every thin attestation matches the supplied full replays."""
    try:
        expected = derive_linear_funding_eligibility_snapshot_v2(
            snapshot_id=snapshot.snapshot_id,
            eligibility_series_id=snapshot.eligibility_series_id,
            revision_id=snapshot.revision_id,
            supersedes_revision_id=snapshot.supersedes_revision_id,
            slot_id=snapshot.slot_id,
            eligibility_instant=snapshot.eligibility_instant,
            available_at=snapshot.available_at,
            eligibility_projection=eligibility_projection,
            availability_projection=availability_projection,
        )
    except (TypeError, ValueError):
        return False
    return canonical_sha256(snapshot) == canonical_sha256(expected)


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityRequestV2:
    slot_id: FundingSlotId
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    eligibility_instant: SimulationInstant
    publications: tuple[LinearFundingRatePublicationCandidate, ...]
    position_snapshot: LinearFundingEligibilityPositionSnapshotV2 | None
    captured_at: SimulationInstant

    def __post_init__(self) -> None:
        if type(self.slot_id) is not FundingSlotId:
            raise TypeError("slot_id must be exact FundingSlotId")
        _position_key(self.position_key)
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        _instant("eligibility_instant", self.eligibility_instant)
        if type(self.publications) is not tuple or not all(type(value) is LinearFundingRatePublicationCandidate for value in self.publications):
            raise TypeError("publications must be an exact tuple of Candidates")
        if self.position_snapshot is not None and type(self.position_snapshot) is not LinearFundingEligibilityPositionSnapshotV2:
            raise TypeError("position_snapshot must be exact V2 Snapshot or None")
        _instant("captured_at", self.captured_at)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "linear_funding_eligibility_request", "schema_version": 2,
                "slot_id": self.slot_id, "position_key": self.position_key,
                "contract": self.contract, "eligibility_instant": self.eligibility_instant,
                "publications": self.publications, "position_snapshot": self.position_snapshot,
                "captured_at": self.captured_at}


def _v2_first_failure(request: LinearFundingEligibilityRequestV2) -> LinearFundingEligibilityFailureCode | None:
    publications = request.publications
    if not publications:
        return LinearFundingEligibilityFailureCode.MISSING_PUBLICATION
    if request.slot_id.instrument_id != request.contract.instrument.instrument_id:
        return LinearFundingEligibilityFailureCode.SLOT_CONTEXT_MISMATCH
    if request.position_key.venue_id != request.contract.instrument.instrument_id.venue or request.position_key.instrument_id != request.contract.instrument.instrument_id:
        return LinearFundingEligibilityFailureCode.POSITION_CONTEXT_MISMATCH
    if request.eligibility_instant.instant != request.slot_id.target_funding_time or request.eligibility_instant.phase != _ELIGIBILITY_PHASE or request.eligibility_instant.source_sequence != _ELIGIBILITY_SEQUENCE or request.captured_at < request.eligibility_instant:
        return LinearFundingEligibilityFailureCode.INVALID_ELIGIBILITY_INSTANT
    if any(value.slot_id != request.slot_id for value in publications):
        return LinearFundingEligibilityFailureCode.PUBLICATION_SLOT_MISMATCH
    if any(value.status is LinearFundingPublicationStatus.FINAL_RATE and value.published_rate is not None and value.published_rate.basis != _RATE_BASIS for value in publications):
        return LinearFundingEligibilityFailureCode.UNSUPPORTED_RATE_BASIS
    if not _revision_set_valid(publications):
        return LinearFundingEligibilityFailureCode.INVALID_PUBLICATION_REVISION_SET
    if any(value.publication_available_at.instant < value.event_time for value in publications):
        return LinearFundingEligibilityFailureCode.INVALID_PUBLICATION_CAUSALITY
    if any(value.event_time > request.slot_id.target_funding_time or value.publication_available_at.instant > request.slot_id.target_funding_time for value in publications):
        return LinearFundingEligibilityFailureCode.LATE_PUBLICATION
    if any(value.publication_available_at > request.captured_at for value in publications):
        return LinearFundingEligibilityFailureCode.PUBLICATION_NOT_AVAILABLE
    if publications[-1].status is LinearFundingPublicationStatus.CANCELLED:
        return LinearFundingEligibilityFailureCode.FUNDING_SLOT_CANCELLED
    snapshot = request.position_snapshot
    if snapshot is None:
        return LinearFundingEligibilityFailureCode.MISSING_ELIGIBILITY_POSITION
    if snapshot.supersedes_revision_id is not None:
        return LinearFundingEligibilityFailureCode.UNSUPPORTED_POSITION_REVISION
    if snapshot.slot_id != request.slot_id:
        return LinearFundingEligibilityFailureCode.SNAPSHOT_SLOT_MISMATCH
    if snapshot.eligibility_position_state.position_key != request.position_key or snapshot.eligibility_position_state.contract != request.contract or snapshot.availability_position_state.position_key != request.position_key or snapshot.availability_position_state.contract != request.contract:
        return LinearFundingEligibilityFailureCode.SNAPSHOT_POSITION_CONTEXT_MISMATCH
    if snapshot.eligibility_instant != request.eligibility_instant:
        return LinearFundingEligibilityFailureCode.ELIGIBILITY_INSTANT_MISMATCH
    if snapshot.available_at > request.captured_at:
        return LinearFundingEligibilityFailureCode.POSITION_SNAPSHOT_NOT_AVAILABLE
    return None


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityV2:
    component_ref: LinearFundingEligibilityComponentRef
    request: LinearFundingEligibilityRequestV2
    request_hash: str
    slot_id: FundingSlotId
    publication_hash: str
    event_id: str
    event_hash: str
    publication_revision_id: str
    snapshot_hash: str
    position_state: LinearPositionState
    state_hash: str
    published_rate: Rate
    eligibility_instant: SimulationInstant
    captured_at: SimulationInstant

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref() or self.request_hash != self.request.request_hash or _v2_first_failure(self.request) is not None:
            raise ValueError("V2 eligibility evidence is invalid")
        selected = self.request.publications[-1]
        snapshot = self.request.position_snapshot
        if snapshot is None or selected.published_rate is None:
            raise ValueError("successful V2 eligibility requires evidence")
        expected = (self.request.slot_id, selected.publication_hash, selected.event_id, selected.event_hash, selected.revision_id, snapshot.snapshot_hash, snapshot.eligibility_position_state, snapshot.eligibility_position_state.state_hash, selected.published_rate, self.request.eligibility_instant, self.request.captured_at)
        if (self.slot_id, self.publication_hash, self.event_id, self.event_hash, self.publication_revision_id, self.snapshot_hash, self.position_state, self.state_hash, self.published_rate, self.eligibility_instant, self.captured_at) != expected:
            raise ValueError("V2 eligibility fields must match request")

    @property
    def eligibility_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "linear_funding_eligibility", "schema_version": 2,
                "component_ref": self.component_ref, "request": self.request,
                "request_hash": self.request_hash, "slot_id": self.slot_id,
                "publication_hash": self.publication_hash, "event_id": self.event_id,
                "event_hash": self.event_hash, "publication_revision_id": self.publication_revision_id,
                "snapshot_hash": self.snapshot_hash, "position_state": self.position_state,
                "state_hash": self.state_hash, "published_rate": self.published_rate,
                "eligibility_instant": self.eligibility_instant, "captured_at": self.captured_at}


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityOutcomeV2:
    component_ref: LinearFundingEligibilityComponentRef
    request_hash: str
    result: LinearFundingEligibilityV2 | None
    failure: LinearFundingEligibilityFailureCode | None

    def __post_init__(self) -> None:
        if self.component_ref != _component_ref() or (self.result is None) == (self.failure is None):
            raise ValueError("V2 eligibility outcome must have one valid branch")


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityResolverV2:
    @property
    def component_ref(self) -> LinearFundingEligibilityComponentRef:
        return _component_ref()

    def resolve(self, request: LinearFundingEligibilityRequestV2, /) -> LinearFundingEligibilityOutcomeV2:
        if type(request) is not LinearFundingEligibilityRequestV2:
            raise TypeError("request must be exact V2 eligibility Request")
        failure = _v2_first_failure(request)
        if failure is not None:
            return LinearFundingEligibilityOutcomeV2(self.component_ref, request.request_hash, None, failure)
        selected, snapshot = request.publications[-1], request.position_snapshot
        if selected.published_rate is None or snapshot is None:
            raise AssertionError("valid V2 request requires funding evidence")
        result = LinearFundingEligibilityV2(self.component_ref, request, request.request_hash, request.slot_id, selected.publication_hash, selected.event_id, selected.event_hash, selected.revision_id, snapshot.snapshot_hash, snapshot.eligibility_position_state, snapshot.eligibility_position_state.state_hash, selected.published_rate, request.eligibility_instant, request.captured_at)
        return LinearFundingEligibilityOutcomeV2(self.component_ref, request.request_hash, result, None)


def _snapshot_replay_valid(
    snapshot: LinearFundingEligibilityPositionSnapshot,
) -> bool:
    try:
        full = LinearDerivativeLedgerProjector().project(
            snapshot.availability_projection.request
        )
        cursor, state = _cutoff_replay(
            snapshot.availability_projection, snapshot.eligibility_instant
        )
    except (TypeError, ValueError):
        return False
    return (
        full.result is not None
        and canonical_sha256(full.result)
        == canonical_sha256(snapshot.availability_projection)
        and canonical_sha256(cursor)
        == canonical_sha256(snapshot.eligibility_cursor)
        and canonical_sha256(state) == canonical_sha256(snapshot.position_state)
    )


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityRequest:
    slot_id: FundingSlotId
    position_key: PositionBalanceKey
    contract: LinearPerpetualContract
    eligibility_instant: SimulationInstant
    publications: tuple[LinearFundingRatePublicationCandidate, ...]
    position_snapshot: LinearFundingEligibilityPositionSnapshot | None
    captured_at: SimulationInstant

    def __post_init__(self) -> None:
        if type(self.slot_id) is not FundingSlotId:
            raise TypeError("slot_id must be exact FundingSlotId")
        _position_key(self.position_key)
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        _instant("eligibility_instant", self.eligibility_instant)
        if type(self.publications) is not tuple or not all(
            type(value) is LinearFundingRatePublicationCandidate
            for value in self.publications
        ):
            raise TypeError("publications must be an exact tuple of Candidates")
        if self.position_snapshot is not None and type(
            self.position_snapshot
        ) is not LinearFundingEligibilityPositionSnapshot:
            raise TypeError("position_snapshot must be exact Snapshot or None")
        _instant("captured_at", self.captured_at)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_eligibility_request",
            "schema_version": _SCHEMA_VERSION,
            "slot_id": self.slot_id,
            "position_key": self.position_key,
            "contract": self.contract,
            "eligibility_instant": self.eligibility_instant,
            "publications": self.publications,
            "position_snapshot": self.position_snapshot,
            "captured_at": self.captured_at,
        }


class LinearFundingEligibilityFailureCode(str, Enum):
    MISSING_PUBLICATION = "missing_publication"
    SLOT_CONTEXT_MISMATCH = "slot_context_mismatch"
    POSITION_CONTEXT_MISMATCH = "position_context_mismatch"
    INVALID_ELIGIBILITY_INSTANT = "invalid_eligibility_instant"
    PUBLICATION_SLOT_MISMATCH = "publication_slot_mismatch"
    UNSUPPORTED_RATE_BASIS = "unsupported_rate_basis"
    INVALID_PUBLICATION_REVISION_SET = "invalid_publication_revision_set"
    INVALID_PUBLICATION_CAUSALITY = "invalid_publication_causality"
    LATE_PUBLICATION = "late_publication"
    PUBLICATION_NOT_AVAILABLE = "publication_not_available"
    FUNDING_SLOT_CANCELLED = "funding_slot_cancelled"
    MISSING_ELIGIBILITY_POSITION = "missing_eligibility_position"
    UNSUPPORTED_POSITION_REVISION = "unsupported_position_revision"
    SNAPSHOT_SLOT_MISMATCH = "snapshot_slot_mismatch"
    SNAPSHOT_POSITION_CONTEXT_MISMATCH = "snapshot_position_context_mismatch"
    ELIGIBILITY_INSTANT_MISMATCH = "eligibility_instant_mismatch"
    INVALID_POSITION_CAPTURE_CAUSALITY = "invalid_position_capture_causality"
    POSITION_SNAPSHOT_NOT_AVAILABLE = "position_snapshot_not_available"


def _revision_set_valid(
    publications: tuple[LinearFundingRatePublicationCandidate, ...],
) -> bool:
    ordered = tuple(
        sorted(
            publications,
            key=lambda value: (
                value.publication_available_at,
                value.event_id,
                value.revision_id,
            ),
        )
    )
    if publications != ordered:
        return False
    if len({value.event_id for value in publications}) != len(publications):
        return False
    if len({value.revision_id for value in publications}) != len(publications):
        return False
    if publications[0].supersedes_revision_id is not None:
        return False
    previous = publications[0]
    for value in publications[1:]:
        if (
            value.supersedes_revision_id != previous.revision_id
            or value.publication_available_at <= previous.publication_available_at
        ):
            return False
        previous = value
    return True


def _expected_cash_key(request: LinearFundingEligibilityRequest) -> CashBalanceKey:
    return CashBalanceKey(
        request.position_key.account_id,
        request.position_key.venue_id,
        request.contract.instrument.settlement_currency,
    )


def _first_failure(
    request: LinearFundingEligibilityRequest,
) -> LinearFundingEligibilityFailureCode | None:
    publications = request.publications
    if not publications:
        return LinearFundingEligibilityFailureCode.MISSING_PUBLICATION
    if request.slot_id.instrument_id != request.contract.instrument.instrument_id:
        return LinearFundingEligibilityFailureCode.SLOT_CONTEXT_MISMATCH
    if (
        request.position_key.venue_id
        != request.contract.instrument.instrument_id.venue
        or request.position_key.instrument_id
        != request.contract.instrument.instrument_id
    ):
        return LinearFundingEligibilityFailureCode.POSITION_CONTEXT_MISMATCH
    if (
        request.eligibility_instant.instant != request.slot_id.target_funding_time
        or request.eligibility_instant.phase != _ELIGIBILITY_PHASE
        or request.eligibility_instant.source_sequence != _ELIGIBILITY_SEQUENCE
        or request.captured_at < request.eligibility_instant
    ):
        return LinearFundingEligibilityFailureCode.INVALID_ELIGIBILITY_INSTANT
    if any(value.slot_id != request.slot_id for value in publications):
        return LinearFundingEligibilityFailureCode.PUBLICATION_SLOT_MISMATCH
    if any(
        value.status is LinearFundingPublicationStatus.FINAL_RATE
        and value.published_rate is not None
        and value.published_rate.basis != _RATE_BASIS
        for value in publications
    ):
        return LinearFundingEligibilityFailureCode.UNSUPPORTED_RATE_BASIS
    if not _revision_set_valid(publications):
        return LinearFundingEligibilityFailureCode.INVALID_PUBLICATION_REVISION_SET
    if any(
        value.publication_available_at.instant < value.event_time
        for value in publications
    ):
        return LinearFundingEligibilityFailureCode.INVALID_PUBLICATION_CAUSALITY
    if any(
        value.event_time > request.slot_id.target_funding_time
        or value.publication_available_at.instant
        > request.slot_id.target_funding_time
        for value in publications
    ):
        return LinearFundingEligibilityFailureCode.LATE_PUBLICATION
    if any(value.publication_available_at > request.captured_at for value in publications):
        return LinearFundingEligibilityFailureCode.PUBLICATION_NOT_AVAILABLE
    selected = publications[-1]
    if selected.status is LinearFundingPublicationStatus.CANCELLED:
        return LinearFundingEligibilityFailureCode.FUNDING_SLOT_CANCELLED
    snapshot = request.position_snapshot
    if snapshot is None:
        return LinearFundingEligibilityFailureCode.MISSING_ELIGIBILITY_POSITION
    if snapshot.supersedes_revision_id is not None:
        return LinearFundingEligibilityFailureCode.UNSUPPORTED_POSITION_REVISION
    if snapshot.slot_id != request.slot_id:
        return LinearFundingEligibilityFailureCode.SNAPSHOT_SLOT_MISMATCH
    projection_request = snapshot.availability_projection.request
    if (
        not _snapshot_replay_valid(snapshot)
        or snapshot.position_state.position_key != request.position_key
        or snapshot.position_state.contract != request.contract
        or projection_request.position_key != request.position_key
        or projection_request.contract != request.contract
        or projection_request.settlement_cash_key != _expected_cash_key(request)
    ):
        return LinearFundingEligibilityFailureCode.SNAPSHOT_POSITION_CONTEXT_MISMATCH
    if snapshot.eligibility_instant != request.eligibility_instant:
        return LinearFundingEligibilityFailureCode.ELIGIBILITY_INSTANT_MISMATCH
    if snapshot.available_at < snapshot.eligibility_instant or any(
        entry.recorded_at > snapshot.available_at
        for entry in projection_request.journal.entries
    ):
        return LinearFundingEligibilityFailureCode.INVALID_POSITION_CAPTURE_CAUSALITY
    if snapshot.available_at > request.captured_at:
        return LinearFundingEligibilityFailureCode.POSITION_SNAPSHOT_NOT_AVAILABLE
    return None


def _failure_subject_ids(
    request: LinearFundingEligibilityRequest,
    code: LinearFundingEligibilityFailureCode,
) -> tuple[str, ...]:
    event_id = (
        "missing-funding-publication"
        if not request.publications
        else request.publications[-1].event_id
    )
    snapshot_id = (
        "missing-eligibility-position"
        if request.position_snapshot is None
        else request.position_snapshot.snapshot_id
    )
    return (
        code.value,
        request.slot_id.value,
        event_id,
        snapshot_id,
        request.position_key.account_id,
        str(request.contract.instrument.instrument_id),
    )


def _validate_result_evidence(
    component_ref: LinearFundingEligibilityComponentRef,
    request: LinearFundingEligibilityRequest,
    request_hash: str,
) -> None:
    if type(component_ref) is not LinearFundingEligibilityComponentRef:
        raise TypeError("component_ref must be exact funding eligibility ComponentRef")
    if component_ref != _component_ref():
        raise ValueError("component_ref must match funding eligibility")
    if type(request) is not LinearFundingEligibilityRequest:
        raise TypeError("request must be exact LinearFundingEligibilityRequest")
    _hash("request_hash", request_hash)
    if request_hash != request.request_hash:
        raise ValueError("request_hash must match embedded Request")


@dataclass(frozen=True, slots=True)
class LinearFundingEligibility:
    component_ref: LinearFundingEligibilityComponentRef
    request: LinearFundingEligibilityRequest
    request_hash: str
    slot_id: FundingSlotId
    publication_hash: str
    event_id: str
    event_hash: str
    publication_revision_id: str
    snapshot_hash: str
    position_state: LinearPositionState
    state_hash: str
    published_rate: Rate
    eligibility_instant: SimulationInstant
    captured_at: SimulationInstant

    def __post_init__(self) -> None:
        _validate_result_evidence(
            self.component_ref, self.request, self.request_hash
        )
        if type(self.slot_id) is not FundingSlotId:
            raise TypeError("slot_id must be exact FundingSlotId")
        _hash("publication_hash", self.publication_hash)
        _text("event_id", self.event_id)
        _hash("event_hash", self.event_hash)
        _text("publication_revision_id", self.publication_revision_id)
        _hash("snapshot_hash", self.snapshot_hash)
        if type(self.position_state) is not LinearPositionState:
            raise TypeError("position_state must be exact LinearPositionState")
        _hash("state_hash", self.state_hash)
        _rate(self.published_rate)
        _instant("eligibility_instant", self.eligibility_instant)
        _instant("captured_at", self.captured_at)
        if _first_failure(self.request) is not None:
            raise ValueError("Eligibility Request must have no business failure")
        selected = self.request.publications[-1]
        snapshot = self.request.position_snapshot
        if snapshot is None or selected.published_rate is None:
            raise AssertionError("successful eligibility requires evidence")
        expected = (
            self.request.slot_id,
            selected.publication_hash,
            selected.event_id,
            selected.event_hash,
            selected.revision_id,
            snapshot.snapshot_hash,
            snapshot.position_state,
            snapshot.position_state.state_hash,
            selected.published_rate,
            self.request.eligibility_instant,
            self.request.captured_at,
        )
        actual = (
            self.slot_id,
            self.publication_hash,
            self.event_id,
            self.event_hash,
            self.publication_revision_id,
            self.snapshot_hash,
            self.position_state,
            self.state_hash,
            self.published_rate,
            self.eligibility_instant,
            self.captured_at,
        )
        if actual != expected:
            raise ValueError("Eligibility fields must match embedded Request")

    @property
    def eligibility_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_eligibility",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "slot_id": self.slot_id,
            "publication_hash": self.publication_hash,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "publication_revision_id": self.publication_revision_id,
            "snapshot_hash": self.snapshot_hash,
            "position_state": self.position_state,
            "state_hash": self.state_hash,
            "published_rate": self.published_rate,
            "eligibility_instant": self.eligibility_instant,
            "captured_at": self.captured_at,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityFailure:
    component_ref: LinearFundingEligibilityComponentRef
    request: LinearFundingEligibilityRequest
    request_hash: str
    code: LinearFundingEligibilityFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_result_evidence(
            self.component_ref, self.request, self.request_hash
        )
        if type(self.code) is not LinearFundingEligibilityFailureCode:
            raise TypeError("code must be exact LinearFundingEligibilityFailureCode")
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be an exact tuple of strings")
        expected_code = _first_failure(self.request)
        if expected_code is None or expected_code != self.code:
            raise ValueError("failure must match first Request failure")
        expected_subjects = _failure_subject_ids(self.request, self.code)
        if self.subject_ids != expected_subjects:
            raise ValueError("subject_ids must match embedded Request")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        value = {
            "type": "linear_funding_eligibility_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request": self.request,
            "request_hash": self.request_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }
        return value


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityOutcome:
    component_ref: LinearFundingEligibilityComponentRef
    request_hash: str
    result: LinearFundingEligibility | None
    failure: LinearFundingEligibilityFailure | None

    def __post_init__(self) -> None:
        if type(self.component_ref) is not LinearFundingEligibilityComponentRef:
            raise TypeError("component_ref must be exact funding eligibility ComponentRef")
        if self.component_ref != _component_ref():
            raise ValueError("component_ref must match funding eligibility")
        _hash("request_hash", self.request_hash)
        if type(self.result) not in (type(None), LinearFundingEligibility):
            raise TypeError("result must be exact LinearFundingEligibility or None")
        if type(self.failure) not in (
            type(None),
            LinearFundingEligibilityFailure,
        ):
            raise TypeError("failure must be exact LinearFundingEligibilityFailure or None")
        has_result = self.result is not None
        has_failure = self.failure is not None
        if has_result == has_failure:
            raise ValueError("Outcome requires exactly one result or failure")
        selected = self.result if has_result else self.failure
        if selected is None:
            raise AssertionError("exactly-one validation must select a value")
        if selected.request_hash != self.request_hash:
            raise ValueError("Outcome request_hash must match its value")
        if selected.component_ref != self.component_ref:
            raise ValueError("Outcome component_ref must match its value")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "linear_funding_eligibility_outcome",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "request_hash": self.request_hash,
            "result": self.result,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class LinearFundingEligibilityResolver:
    @property
    def component_ref(self) -> LinearFundingEligibilityComponentRef:
        return _component_ref()

    def resolve(
        self, request: LinearFundingEligibilityRequest, /
    ) -> LinearFundingEligibilityOutcome:
        if type(request) is not LinearFundingEligibilityRequest:
            raise TypeError("request must be exact LinearFundingEligibilityRequest")
        code = _first_failure(request)
        if code is not None:
            failure = LinearFundingEligibilityFailure(
                self.component_ref,
                request,
                request.request_hash,
                code,
                _failure_subject_ids(request, code),
            )
            return LinearFundingEligibilityOutcome(
                self.component_ref, request.request_hash, None, failure
            )
        selected = request.publications[-1]
        snapshot = request.position_snapshot
        if selected.published_rate is None or snapshot is None:
            raise AssertionError("successful resolution requires evidence")
        result = LinearFundingEligibility(
            self.component_ref,
            request,
            request.request_hash,
            request.slot_id,
            selected.publication_hash,
            selected.event_id,
            selected.event_hash,
            selected.revision_id,
            snapshot.snapshot_hash,
            snapshot.position_state,
            snapshot.position_state.state_hash,
            selected.published_rate,
            request.eligibility_instant,
            request.captured_at,
        )
        return LinearFundingEligibilityOutcome(
            self.component_ref, request.request_hash, result, None
        )
