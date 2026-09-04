from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import NamedBarWindowView
from crypto_quant_domain import SourceSequence, UtcInstant
from crypto_quant_market_data import MarketEvent

from tests.runtime.observation_windows._fixtures import (
    backing_result,
    named_query,
    window,
)
from tests.runtime.observations._causality_fixtures import DECISION_BEFORE_CORRECTION
from tests.runtime.observations._fixtures import query


def test_named_bar_window_returns_bounded_visible_suffix_with_explicit_coverage() -> None:
    backing = backing_result()
    result = window(NamedBarWindowView(query=named_query(), backing_result=backing))

    assert [event.event_id for event in result.events] == ["bar-b-v1", "bar-a-v2"]
    assert result.available_count == 2
    assert result.requested_count == 3
    assert result.coverage_complete is False
    assert result.shortfall_count == 1
    assert result.decision_grade_eligible is False
    assert result.deployment_authorized is False


def test_end_cutoff_and_bar_definition_identity_are_explicit() -> None:
    backing = backing_result()
    cutoff = named_query(end_at_or_before=UtcInstant(100))
    cutoff_result = window(NamedBarWindowView(query=cutoff, backing_result=backing))
    changed_definition = replace(
        cutoff,
        bar_definition=replace(
            cutoff.bar_definition,
            version=2,
            definition_hash="sha256:" + "c" * 64,
        ),
    )

    assert [event.event_id for event in cutoff_result.events] == ["bar-a-v2"]
    assert cutoff_result.available_count == 1
    assert cutoff_result.shortfall_count == 2
    assert NamedBarWindowView(
        query=cutoff, backing_result=backing
    ).view_hash != NamedBarWindowView(
        query=changed_definition, backing_result=backing
    ).view_hash


def test_full_partial_and_empty_coverage_are_successful() -> None:
    backing = backing_result()
    full = window(
        NamedBarWindowView(query=named_query(lookback_count=1), backing_result=backing)
    )
    empty = window(
        NamedBarWindowView(
            query=named_query(end_at_or_before=UtcInstant(0)),
            backing_result=backing,
        )
    )

    assert full.coverage_complete is True
    assert full.shortfall_count == 0
    assert len(full.events) == 1
    assert empty.coverage_complete is False
    assert empty.available_count == 0
    assert not empty.events
    assert empty.max_event_time is None
    assert empty.max_available_instant is None


@pytest.mark.parametrize("lookback", (True, 0, -1, 10_001))
def test_query_rejects_invalid_or_unbounded_lookback(lookback: object) -> None:
    with pytest.raises(ValueError, match="lookback_count"):
        named_query(lookback_count=lookback)


def test_query_view_and_result_reject_forged_context() -> None:
    backing = backing_result()
    named = named_query()
    result = window(NamedBarWindowView(query=named, backing_result=backing))

    with pytest.raises(ValueError, match="after Decision Instant"):
        named_query(end_at_or_before=UtcInstant(201))
    with pytest.raises(ValueError, match="Decision Instant"):
        NamedBarWindowView(
            query=replace(named, decision_instant=DECISION_BEFORE_CORRECTION),
            backing_result=backing,
        )
    with pytest.raises(ValueError, match="Query"):
        NamedBarWindowView(
            query=replace(
                named,
                observation_query=query(dataset_key="bars.other"),
            ),
            backing_result=backing,
        )
    with pytest.raises(ValueError, match="coverage_complete"):
        replace(result, coverage_complete=True)
    with pytest.raises(ValueError, match="flags"):
        replace(result, decision_grade_eligible=True)
    with pytest.raises(ValueError, match="maxima"):
        replace(result, max_event_time=UtcInstant(999))
    forged_event = MarketEvent(
        event_id="forged-bar",
        stream_key=result.events[0].stream_key,
        event_type="bar",
        capability=result.events[0].capability,
        instrument_id=result.events[0].instrument_id,
        event_time=UtcInstant(199),
        available_time=UtcInstant(200),
        phase=result.events[0].phase,
        source_sequence=SourceSequence(2),
        revision_id="forged-v1",
        supersedes_revision_id=None,
        source_key="fixture.forged",
        source_hash="sha256:" + "f" * 64,
        payload={"close": {"scale": 2, "units": 1}},
    )
    with pytest.raises(ValueError, match="causality trace"):
        replace(result, events=(result.events[0], forged_event))


def test_bar_definition_rejects_invalid_identity() -> None:
    current = named_query().bar_definition
    with pytest.raises(ValueError, match="key"):
        replace(current, key=" ")
    with pytest.raises(ValueError, match="version"):
        replace(current, version=True)
    with pytest.raises(ValueError, match="sha256"):
        replace(current, definition_hash="bad")
