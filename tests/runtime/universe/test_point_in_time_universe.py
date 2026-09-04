from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    PointInTimeUniverseView,
    UniverseKind,
    UniverseMembershipRevision,
    UniverseQuery,
    UniverseSelection,
)
from crypto_quant_domain import SimulationInstant, SourceSequence, UtcInstant

from tests.runtime.universe._fixtures import (
    DECISION_AT_CORRECTION,
    DECISION_BEFORE_CORRECTION,
    DECISION_LATE,
    INSTRUMENT_A,
    INSTRUMENT_B,
    UNIVERSE_KEY,
    failure_cases,
    query,
    revision,
    revisions,
    select_universe,
    view,
)


def test_point_in_time_membership_correction_respects_listing_and_hidden_evidence() -> None:
    supplied = revisions()
    baseline = view(
        DECISION_BEFORE_CORRECTION,
        supplied_revisions=supplied[:2],
    )
    with_hidden = view(
        DECISION_BEFORE_CORRECTION,
        supplied_revisions=tuple(reversed(supplied)),
    )

    baseline_selection = select_universe(baseline)
    hidden_selection = select_universe(with_hidden)
    assert baseline.view_hash == with_hidden.view_hash
    assert baseline_selection.to_canonical_dict() == hidden_selection.to_canonical_dict()
    assert baseline_selection.instruments == (INSTRUMENT_A,)

    corrected = select_universe(view(DECISION_AT_CORRECTION))
    assert not corrected.instruments
    assert corrected.point_in_time is True
    assert corrected.static_universe is False
    assert corrected.survivorship_bias_safe is False
    assert corrected.decision_grade_eligible is False
    assert corrected.deployment_authorized is False


@pytest.mark.parametrize(
    ("case_name", "supplied_revisions", "message"),
    failure_cases(),
)
def test_visible_membership_chain_failures_are_deterministic(
    case_name: str,
    supplied_revisions: tuple[UniverseMembershipRevision, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        view(DECISION_LATE, supplied_revisions=supplied_revisions)
    assert case_name


def test_listing_membership_exit_and_reentry_boundaries_are_half_open() -> None:
    supplied = (
        revision(
            "asset-b-first",
            "v1",
            instrument_id=INSTRUMENT_B,
            listed_at=50,
            delisted_at=450,
            member_from=100,
            member_until=200,
            available_time=90,
            source_sequence=1,
            supersedes_revision_id=None,
        ),
        revision(
            "asset-b-second",
            "v1",
            instrument_id=INSTRUMENT_B,
            listed_at=50,
            delisted_at=450,
            member_from=300,
            member_until=400,
            available_time=290,
            source_sequence=1,
            supersedes_revision_id=None,
        ),
    )

    at_first_start = select_universe(
        view(
            SimulationInstant(
                UtcInstant(100), DECISION_LATE.phase, SourceSequence(9)
            ),
            supplied_revisions=supplied,
        )
    )
    at_first_end = select_universe(
        view(
            SimulationInstant(
                UtcInstant(200), DECISION_LATE.phase, SourceSequence(9)
            ),
            supplied_revisions=supplied,
        )
    )
    at_reentry = select_universe(
        view(
            SimulationInstant(
                UtcInstant(300), DECISION_LATE.phase, SourceSequence(9)
            ),
            supplied_revisions=supplied,
        )
    )
    at_delisting = select_universe(
        view(
            SimulationInstant(
                UtcInstant(450), DECISION_LATE.phase, SourceSequence(9)
            ),
            supplied_revisions=supplied,
        )
    )

    assert at_first_start.instruments == (INSTRUMENT_B,)
    assert not at_first_end.instruments
    assert at_reentry.instruments == (INSTRUMENT_B,)
    assert not at_delisting.instruments


def test_static_universe_is_explicitly_labelled_and_never_survivorship_safe() -> None:
    static_revision = revision(
        "static-a",
        "v1",
        kind=UniverseKind.STATIC,
        instrument_id=INSTRUMENT_A,
        listed_at=0,
        delisted_at=None,
        member_from=0,
        member_until=None,
        available_time=0,
        source_sequence=1,
        supersedes_revision_id=None,
    )
    selection = select_universe(
        view(
            DECISION_LATE,
            supplied_revisions=(static_revision,),
            kind=UniverseKind.STATIC,
        )
    )

    assert selection.instruments == (INSTRUMENT_A,)
    assert selection.point_in_time is False
    assert selection.static_universe is True
    assert selection.survivorship_bias_safe is False


def test_empty_duplicates_order_and_active_overlap_are_deterministic() -> None:
    empty = view(DECISION_LATE, supplied_revisions=())
    empty_selection = select_universe(empty)
    assert not empty_selection.instruments
    assert not empty_selection.selected_revision_hashes
    assert empty_selection.max_selected_available_at is None

    one = revisions()[0]
    once = view(DECISION_LATE, supplied_revisions=(one,))
    repeated = view(DECISION_LATE, supplied_revisions=(one, one))
    assert once.view_hash == repeated.view_hash
    assert select_universe(once).selection_hash == select_universe(repeated).selection_hash

    overlap = (
        one,
        revision(
            "asset-a-other",
            "v1",
            instrument_id=INSTRUMENT_A,
            listed_at=0,
            delisted_at=None,
            member_from=150,
            member_until=None,
            available_time=150,
            source_sequence=1,
            supersedes_revision_id=None,
        ),
    )
    with pytest.raises(ValueError, match="overlaps"):
        select_universe(view(DECISION_LATE, supplied_revisions=overlap))


def test_revision_and_query_reject_invalid_intervals_and_identity() -> None:
    current = revisions()[0]
    with pytest.raises(ValueError, match="after listed_at"):
        replace(current, delisted_at=current.listed_at)
    with pytest.raises(ValueError, match="after member_from"):
        replace(current, member_until=current.member_from)
    with pytest.raises(ValueError, match="before listing"):
        replace(current, member_from=UtcInstant(-1))
    with pytest.raises(ValueError, match="after delisting"):
        replace(current, delisted_at=UtcInstant(150), member_until=None)
    with pytest.raises(ValueError, match="sha256"):
        replace(current, source_hash="bad")
    with pytest.raises(TypeError, match="SimulationInstant"):
        UniverseQuery(UNIVERSE_KEY, UniverseKind.POINT_IN_TIME, UtcInstant(1))


def test_selection_and_view_revalidate_forged_context() -> None:
    selection = select_universe(view(DECISION_BEFORE_CORRECTION))
    with pytest.raises(ValueError, match="kind flags"):
        replace(selection, static_universe=True)
    with pytest.raises(ValueError, match="limitation flags"):
        replace(selection, decision_grade_eligible=True)
    with pytest.raises(ValueError, match="align with Instruments"):
        replace(selection, selected_revision_hashes=())
    with pytest.raises(TypeError, match="UniverseQuery"):
        PointInTimeUniverseView(query=object(), revisions=())
    with pytest.raises(TypeError, match="UniverseMembershipRevision"):
        PointInTimeUniverseView(query=query(DECISION_LATE), revisions=(object(),))
