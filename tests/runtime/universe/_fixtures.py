from __future__ import annotations

from crypto_quant_backtest import (
    PointInTimeUniverseView,
    UniverseKind,
    UniverseMembershipRevision,
    UniverseQuery,
    UniverseSelection,
)
from crypto_quant_domain import (
    InstrumentId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)


UNIVERSE_PHASE = TimelinePhase(60, "universe_availability")
DECISION_BEFORE_CORRECTION = SimulationInstant(
    UtcInstant(200), UNIVERSE_PHASE, SourceSequence(2)
)
DECISION_AT_CORRECTION = SimulationInstant(
    UtcInstant(200), UNIVERSE_PHASE, SourceSequence(3)
)
DECISION_LATE = SimulationInstant(UtcInstant(500), UNIVERSE_PHASE, SourceSequence(9))
UNIVERSE_KEY = "portfolio.primary"
INSTRUMENT_A = InstrumentId(VenueId("test"), "asset-a")
INSTRUMENT_B = InstrumentId(VenueId("test"), "asset-b")


def source_hash(label: str) -> str:
    return "sha256:" + label.encode().hex().ljust(64, "0")[:64]


def revision(
    membership_key: str,
    revision_id: str,
    *,
    instrument_id: InstrumentId,
    listed_at: int,
    delisted_at: int | None,
    member_from: int,
    member_until: int | None,
    available_time: int,
    source_sequence: int,
    supersedes_revision_id: str | None,
    universe_key: str = UNIVERSE_KEY,
    kind: UniverseKind = UniverseKind.POINT_IN_TIME,
    label: str | None = None,
) -> UniverseMembershipRevision:
    return UniverseMembershipRevision(
        universe_key=universe_key,
        membership_key=membership_key,
        kind=kind,
        instrument_id=instrument_id,
        listed_at=UtcInstant(listed_at),
        delisted_at=None if delisted_at is None else UtcInstant(delisted_at),
        member_from=UtcInstant(member_from),
        member_until=None if member_until is None else UtcInstant(member_until),
        available_at=SimulationInstant(
            UtcInstant(available_time),
            UNIVERSE_PHASE,
            SourceSequence(source_sequence),
        ),
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
        source_hash=source_hash(revision_id if label is None else label),
    )


def revisions() -> tuple[UniverseMembershipRevision, ...]:
    return (
        revision(
            "asset-a-membership",
            "v1",
            instrument_id=INSTRUMENT_A,
            listed_at=0,
            delisted_at=None,
            member_from=100,
            member_until=None,
            available_time=100,
            source_sequence=1,
            supersedes_revision_id=None,
        ),
        revision(
            "asset-b-membership",
            "v1",
            instrument_id=INSTRUMENT_B,
            listed_at=0,
            delisted_at=190,
            member_from=50,
            member_until=190,
            available_time=80,
            source_sequence=1,
            supersedes_revision_id=None,
        ),
        revision(
            "asset-a-membership",
            "v2",
            instrument_id=INSTRUMENT_A,
            listed_at=0,
            delisted_at=None,
            member_from=100,
            member_until=180,
            available_time=200,
            source_sequence=3,
            supersedes_revision_id="v1",
        ),
        revision(
            "asset-a-membership",
            "v2",
            instrument_id=INSTRUMENT_A,
            listed_at=0,
            delisted_at=None,
            member_from=100,
            member_until=170,
            available_time=200,
            source_sequence=4,
            supersedes_revision_id="v1",
            label="future-conflict",
        ),
        revision(
            "unrelated",
            "orphan",
            instrument_id=INSTRUMENT_A,
            listed_at=0,
            delisted_at=None,
            member_from=0,
            member_until=None,
            available_time=100,
            source_sequence=1,
            supersedes_revision_id="missing",
            universe_key="portfolio.other",
        ),
    )


def query(
    decision_instant: SimulationInstant,
    *,
    kind: UniverseKind = UniverseKind.POINT_IN_TIME,
) -> UniverseQuery:
    return UniverseQuery(
        universe_key=UNIVERSE_KEY,
        kind=kind,
        decision_instant=decision_instant,
    )


def view(
    decision_instant: SimulationInstant,
    *,
    supplied_revisions: tuple[UniverseMembershipRevision, ...] | None = None,
    kind: UniverseKind = UniverseKind.POINT_IN_TIME,
) -> PointInTimeUniverseView:
    return PointInTimeUniverseView(
        query=query(decision_instant, kind=kind),
        revisions=revisions() if supplied_revisions is None else supplied_revisions,
    )


def select_universe(view_value: PointInTimeUniverseView) -> UniverseSelection:
    selector = getattr(view_value, "select")
    return selector()


def failure_cases() -> tuple[
    tuple[str, tuple[UniverseMembershipRevision, ...], str], ...
]:
    root = revision(
        "membership",
        "v1",
        instrument_id=INSTRUMENT_A,
        listed_at=0,
        delisted_at=None,
        member_from=0,
        member_until=None,
        available_time=100,
        source_sequence=1,
        supersedes_revision_id=None,
    )
    return (
        (
            "revision_identity_conflict",
            (
                root,
                revision(
                    "membership",
                    "v1",
                    instrument_id=INSTRUMENT_A,
                    listed_at=0,
                    delisted_at=None,
                    member_from=0,
                    member_until=400,
                    available_time=101,
                    source_sequence=1,
                    supersedes_revision_id=None,
                    label="conflict",
                ),
            ),
            "conflicting visible Universe membership revision identity",
        ),
        (
            "missing_parent",
            (
                revision(
                    "membership",
                    "v2",
                    instrument_id=INSTRUMENT_A,
                    listed_at=0,
                    delisted_at=None,
                    member_from=0,
                    member_until=None,
                    available_time=100,
                    source_sequence=1,
                    supersedes_revision_id="missing",
                ),
            ),
            "parent is missing",
        ),
        (
            "fork",
            (
                root,
                revision(
                    "membership",
                    "v2a",
                    instrument_id=INSTRUMENT_A,
                    listed_at=0,
                    delisted_at=None,
                    member_from=0,
                    member_until=400,
                    available_time=200,
                    source_sequence=1,
                    supersedes_revision_id="v1",
                ),
                revision(
                    "membership",
                    "v2b",
                    instrument_id=INSTRUMENT_A,
                    listed_at=0,
                    delisted_at=None,
                    member_from=0,
                    member_until=300,
                    available_time=201,
                    source_sequence=1,
                    supersedes_revision_id="v1",
                ),
            ),
            "chain conflicts",
        ),
        (
            "availability_regression",
            (
                revision(
                    "membership",
                    "v1",
                    instrument_id=INSTRUMENT_A,
                    listed_at=0,
                    delisted_at=None,
                    member_from=0,
                    member_until=None,
                    available_time=200,
                    source_sequence=2,
                    supersedes_revision_id=None,
                ),
                revision(
                    "membership",
                    "v2",
                    instrument_id=INSTRUMENT_A,
                    listed_at=0,
                    delisted_at=None,
                    member_from=0,
                    member_until=400,
                    available_time=200,
                    source_sequence=1,
                    supersedes_revision_id="v1",
                ),
            ),
            "availability regresses",
        ),
    )
