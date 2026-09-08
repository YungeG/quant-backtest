from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    InstrumentId,
    SimulationInstant,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)


_SCHEMA_VERSION = 1


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    digest = text.removeprefix("sha256:")
    if (
        len(text) != 71
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{name} must be a sha256 content hash")
    return text


class UniverseKind(str, Enum):
    POINT_IN_TIME = "point_in_time"
    STATIC = "static"


@dataclass(frozen=True, slots=True)
class UniverseMembershipRevision:
    universe_key: str
    membership_key: str
    kind: UniverseKind
    instrument_id: InstrumentId
    listed_at: UtcInstant
    delisted_at: UtcInstant | None
    member_from: UtcInstant
    member_until: UtcInstant | None
    available_at: SimulationInstant
    revision_id: str
    supersedes_revision_id: str | None
    source_hash: str

    def __post_init__(self) -> None:
        _text("universe_key", self.universe_key)
        _text("membership_key", self.membership_key)
        if not isinstance(self.kind, UniverseKind):
            raise TypeError("kind must be UniverseKind")
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be InstrumentId")
        if type(self.listed_at) is not UtcInstant:
            raise TypeError("listed_at must be UtcInstant")
        if self.delisted_at is not None and type(self.delisted_at) is not UtcInstant:
            raise TypeError("delisted_at must be UtcInstant or None")
        if self.delisted_at is not None and self.delisted_at <= self.listed_at:
            raise ValueError("delisted_at must be after listed_at")
        if type(self.member_from) is not UtcInstant:
            raise TypeError("member_from must be UtcInstant")
        if self.member_until is not None and type(self.member_until) is not UtcInstant:
            raise TypeError("member_until must be UtcInstant or None")
        if self.member_until is not None and self.member_until <= self.member_from:
            raise ValueError("member_until must be after member_from")
        if self.member_from < self.listed_at:
            raise ValueError("membership must not start before listing")
        if self.delisted_at is not None and (
            self.member_until is None or self.member_until > self.delisted_at
        ):
            raise ValueError("membership must not extend after delisting")
        if type(self.available_at) is not SimulationInstant:
            raise TypeError("available_at must be SimulationInstant")
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        _hash("source_hash", self.source_hash)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "universe_membership_revision",
            "schema_version": _SCHEMA_VERSION,
            "universe_key": self.universe_key,
            "membership_key": self.membership_key,
            "kind": self.kind.value,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "listed_at": self.listed_at.to_canonical_dict(),
            "delisted_at": (
                None if self.delisted_at is None else self.delisted_at.to_canonical_dict()
            ),
            "member_from": self.member_from.to_canonical_dict(),
            "member_until": (
                None if self.member_until is None else self.member_until.to_canonical_dict()
            ),
            "available_at": self.available_at.to_canonical_dict(),
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "source_hash": self.source_hash,
        }

    @property
    def revision_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "revision_hash": self.revision_hash}


@dataclass(frozen=True, slots=True)
class UniverseQuery:
    universe_key: str
    kind: UniverseKind
    decision_instant: SimulationInstant

    def __post_init__(self) -> None:
        _text("universe_key", self.universe_key)
        if not isinstance(self.kind, UniverseKind):
            raise TypeError("kind must be UniverseKind")
        if type(self.decision_instant) is not SimulationInstant:
            raise TypeError("decision_instant must be SimulationInstant")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "universe_query",
            "schema_version": _SCHEMA_VERSION,
            "universe_key": self.universe_key,
            "kind": self.kind.value,
            "decision_instant": self.decision_instant.to_canonical_dict(),
        }

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "query_hash": self.query_hash}


@dataclass(frozen=True, slots=True)
class UniverseSelection:
    query: UniverseQuery
    instruments: tuple[InstrumentId, ...]
    selected_revision_hashes: tuple[str, ...]
    candidate_revision_hashes: tuple[str, ...]
    max_selected_available_at: SimulationInstant | None
    point_in_time: bool
    static_universe: bool
    survivorship_bias_safe: bool
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.query) is not UniverseQuery:
            raise TypeError("query must be UniverseQuery")
        if type(self.instruments) is not tuple or any(
            type(value) is not InstrumentId for value in self.instruments
        ):
            raise TypeError("instruments must be a tuple of InstrumentId")
        if self.instruments != tuple(sorted(set(self.instruments))):
            raise ValueError("instruments must be sorted and unique")
        for name, values in (
            ("selected_revision_hashes", self.selected_revision_hashes),
            ("candidate_revision_hashes", self.candidate_revision_hashes),
        ):
            if type(values) is not tuple or values != tuple(sorted(set(values))):
                raise ValueError(f"{name} must be sorted and unique")
            for value in values:
                _hash(name, value)
        if not set(self.selected_revision_hashes) <= set(
            self.candidate_revision_hashes
        ):
            raise ValueError("selected revisions must be visible candidates")
        if self.max_selected_available_at is not None and type(
            self.max_selected_available_at
        ) is not SimulationInstant:
            raise TypeError("max_selected_available_at must be SimulationInstant or None")
        if len(self.selected_revision_hashes) != len(self.instruments):
            raise ValueError("selected revisions must align with Instruments")
        if bool(self.selected_revision_hashes) != (
            self.max_selected_available_at is not None
        ):
            raise ValueError("selected revisions and max availability must align")
        if (
            self.max_selected_available_at is not None
            and self.max_selected_available_at > self.query.decision_instant
        ):
            raise ValueError("selected availability cannot be after Decision Instant")
        expected_point = self.query.kind is UniverseKind.POINT_IN_TIME
        expected_static = self.query.kind is UniverseKind.STATIC
        if self.point_in_time is not expected_point or self.static_universe is not expected_static:
            raise ValueError("Universe kind flags do not match query")
        if (
            self.survivorship_bias_safe
            or self.decision_grade_eligible
            or self.deployment_authorized
        ):
            raise ValueError("G11C limitation flags must remain false")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "universe_selection",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query.to_canonical_dict(),
            "instruments": [value.to_canonical_dict() for value in self.instruments],
            "selected_revision_hashes": list(self.selected_revision_hashes),
            "candidate_revision_hashes": list(self.candidate_revision_hashes),
            "max_selected_available_at": (
                None
                if self.max_selected_available_at is None
                else self.max_selected_available_at.to_canonical_dict()
            ),
            "point_in_time": self.point_in_time,
            "static_universe": self.static_universe,
            "survivorship_bias_safe": self.survivorship_bias_safe,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def selection_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "selection_hash": self.selection_hash}


class PointInTimeUniverseView:
    __slots__ = ("_query", "_revisions", "_view_hash")

    def __init__(
        self,
        *,
        query: UniverseQuery,
        revisions: Iterable[UniverseMembershipRevision],
    ) -> None:
        if type(query) is not UniverseQuery:
            raise TypeError("query must be UniverseQuery")
        visible_by_hash: dict[str, UniverseMembershipRevision] = {}
        for revision in revisions:
            if type(revision) is not UniverseMembershipRevision:
                raise TypeError("revisions must contain UniverseMembershipRevision")
            if (
                revision.universe_key != query.universe_key
                or revision.kind is not query.kind
            ):
                continue
            if revision.available_at > query.decision_instant:
                continue
            visible_by_hash[revision.revision_hash] = revision
        visible = tuple(
            sorted(
                visible_by_hash.values(),
                key=lambda value: (value.membership_key, value.revision_hash),
            )
        )
        self._validate(visible)
        body = {
            "type": "point_in_time_universe_view",
            "schema_version": _SCHEMA_VERSION,
            "query": query.to_canonical_dict(),
            "visible_revisions": [value.to_canonical_dict() for value in visible],
        }
        self._query = query
        self._revisions = visible
        self._view_hash = canonical_sha256(body)

    @property
    def view_hash(self) -> str:
        return self._view_hash

    def select(self) -> UniverseSelection:
        terminals = self._terminals(self._revisions)
        instant = self._query.decision_instant.instant
        active = tuple(
            revision
            for revision in terminals
            if revision.listed_at <= instant
            and (revision.delisted_at is None or instant < revision.delisted_at)
            and revision.member_from <= instant
            and (revision.member_until is None or instant < revision.member_until)
        )
        instruments = tuple(sorted(revision.instrument_id for revision in active))
        if len(instruments) != len(set(instruments)):
            raise ValueError("active Universe membership overlaps for one Instrument")
        selected_hashes = tuple(sorted(revision.revision_hash for revision in active))
        return UniverseSelection(
            query=self._query,
            instruments=instruments,
            selected_revision_hashes=selected_hashes,
            candidate_revision_hashes=tuple(
                sorted(revision.revision_hash for revision in self._revisions)
            ),
            max_selected_available_at=max(
                (revision.available_at for revision in active), default=None
            ),
            point_in_time=self._query.kind is UniverseKind.POINT_IN_TIME,
            static_universe=self._query.kind is UniverseKind.STATIC,
            survivorship_bias_safe=False,
            decision_grade_eligible=False,
            deployment_authorized=False,
        )

    @staticmethod
    def _groups(
        revisions: tuple[UniverseMembershipRevision, ...],
    ) -> dict[str, tuple[UniverseMembershipRevision, ...]]:
        groups: dict[str, list[UniverseMembershipRevision]] = {}
        for revision in revisions:
            groups.setdefault(revision.membership_key, []).append(revision)
        return {key: tuple(values) for key, values in groups.items()}

    @staticmethod
    def _validate(revisions: tuple[UniverseMembershipRevision, ...]) -> None:
        identities: dict[tuple[str, str], set[str]] = {}
        for revision in revisions:
            identities.setdefault(
                (revision.membership_key, revision.revision_id), set()
            ).add(revision.revision_hash)
        if any(len(hashes) > 1 for hashes in identities.values()):
            raise ValueError("conflicting visible Universe membership revision identity")

        for values in PointInTimeUniverseView._groups(revisions).values():
            by_revision = {value.revision_id: value for value in values}
            if any(
                value.supersedes_revision_id is not None
                and value.supersedes_revision_id not in by_revision
                for value in values
            ):
                raise ValueError("visible Universe membership parent is missing")
            children: dict[str, list[str]] = {}
            roots: list[str] = []
            for value in values:
                parent = value.supersedes_revision_id
                if parent is None:
                    roots.append(value.revision_id)
                else:
                    children.setdefault(parent, []).append(value.revision_id)
            if len(roots) != 1 or any(len(items) != 1 for items in children.values()):
                raise ValueError("visible Universe membership chain conflicts")
            ordered: list[UniverseMembershipRevision] = []
            current = roots[0]
            while current not in {item.revision_id for item in ordered}:
                ordered.append(by_revision[current])
                next_values = children.get(current, [])
                if not next_values:
                    break
                current = next_values[0]
            if len(ordered) != len(by_revision) or current in children:
                raise ValueError("visible Universe membership chain conflicts")
            first = ordered[0]
            if any(
                value.universe_key != first.universe_key
                or value.membership_key != first.membership_key
                or value.kind is not first.kind
                or value.instrument_id != first.instrument_id
                for value in ordered[1:]
            ):
                raise ValueError("Universe membership lineage context changes")
            if any(
                child.available_at <= parent.available_at
                for parent, child in zip(ordered, ordered[1:], strict=False)
            ):
                raise ValueError("Universe membership availability regresses")

    @staticmethod
    def _terminals(
        revisions: tuple[UniverseMembershipRevision, ...],
    ) -> tuple[UniverseMembershipRevision, ...]:
        terminals = []
        for values in PointInTimeUniverseView._groups(revisions).values():
            parent_ids = {
                value.supersedes_revision_id
                for value in values
                if value.supersedes_revision_id is not None
            }
            terminals.append(
                next(value for value in values if value.revision_id not in parent_ids)
            )
        return tuple(sorted(terminals, key=lambda value: value.membership_key))
