from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from crypto_quant_domain import (
    InstrumentId,
    PositionBalanceKey,
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    FundingSlotId,
    LinearDerivativeLedgerProjector,
    LinearFundingEligibility,
    LinearFundingEligibilityFailureCode,
    LinearFundingEligibilityOutcome,
    LinearFundingEligibilityPositionSnapshot,
    LinearFundingEligibilityRequest,
    LinearFundingEligibilityResolver,
    LinearFundingEligibilityComponentRef,
    LinearFundingPublicationStatus,
    LinearFundingRatePublicationCandidate,
)

from tests.kernel.derivatives._fixtures import contract, position_key
from tests.kernel.derivatives.test_linear_derivative_accounting import (
    _replay_request,
    _translated_entries,
)


def _instant(
    nanoseconds: int,
    rank: int,
    code: str,
    sequence: int = 0,
) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds),
        TimelinePhase(rank, code),
        SourceSequence(sequence),
    )


def _availability_evidence():
    direct, entries = _translated_entries()
    journal = AccountingJournal.from_entries(entries)
    availability = LinearDerivativeLedgerProjector().project(
        _replay_request(journal)
    )
    assert availability.result is not None
    return direct, journal, availability.result


def _publication(
    slot: FundingSlotId,
    *,
    status: LinearFundingPublicationStatus = LinearFundingPublicationStatus.FINAL_RATE,
    rate: Rate | None = Rate(1, Scale(4), "funding_fraction_of_notional"),
    event_id: str = "funding-event-root",
    event_time: UtcInstant = UtcInstant(2),
    available_at: SimulationInstant = _instant(3, 50, "funding_publication"),
    revision_id: str = "funding-revision-root",
    supersedes_revision_id: str | None = None,
) -> LinearFundingRatePublicationCandidate:
    return LinearFundingRatePublicationCandidate(
        slot_id=slot,
        status=status,
        published_rate=rate,
        event_id=event_id,
        event_hash="sha256:" + "1" * 64,
        event_time=event_time,
        publication_available_at=available_at,
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
        source_key="synthetic.funding.publication.v1",
        source_hash="sha256:" + "2" * 64,
    )


def _snapshot(
    slot: FundingSlotId,
    eligibility: SimulationInstant,
    *,
    available_at: SimulationInstant = _instant(8, 20, "position_snapshot"),
    supersedes_revision_id: str | None = None,
    availability_entry_count: int | None = None,
) -> LinearFundingEligibilityPositionSnapshot:
    _, journal, availability = _availability_evidence()
    if availability_entry_count is not None:
        available_journal = AccountingJournal(
            journal.entries[:availability_entry_count]
        )
        availability = LinearDerivativeLedgerProjector().project(
            replace(availability.request, journal=available_journal)
        ).result
        assert availability is not None
        journal = available_journal
    count = sum(entry.recorded_at < eligibility for entry in journal.entries)
    prefix = AccountingJournal(journal.entries[:count])
    cutoff = LinearDerivativeLedgerProjector().project(
        replace(availability.request, journal=prefix)
    )
    assert cutoff.result is not None
    return LinearFundingEligibilityPositionSnapshot(
        snapshot_id="funding-position-snapshot-root",
        eligibility_series_id="funding-position-series",
        revision_id="funding-position-revision-root",
        supersedes_revision_id=supersedes_revision_id,
        slot_id=slot,
        eligibility_instant=eligibility,
        available_at=available_at,
        eligibility_cursor=cutoff.result.cursor,
        availability_projection=availability,
        position_state=cutoff.result.position_state,
    )


def _valid_request() -> LinearFundingEligibilityRequest:
    target = UtcInstant(3)
    eligibility = _instant(3, 100, "funding_eligibility")
    slot = FundingSlotId.derive(contract().instrument.instrument_id, target)
    publication = _publication(slot)
    snapshot = _snapshot(slot, eligibility)
    return LinearFundingEligibilityRequest(
        slot_id=slot,
        position_key=position_key(),
        contract=contract(),
        eligibility_instant=eligibility,
        publications=(publication,),
        position_snapshot=snapshot,
        captured_at=_instant(9, 0, "capture"),
    )


def test_final_publication_resolves_against_historical_cutoff_position() -> None:
    request = _valid_request()

    outcome = LinearFundingEligibilityResolver().resolve(request)

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.slot_id == request.slot_id
    assert result.published_rate == Rate(
        1, Scale(4), "funding_fraction_of_notional"
    )
    assert result.position_state.quantity.units == 2_000
    assert request.position_snapshot is not None
    assert (
        request.position_snapshot.availability_projection.position_state.quantity.units
        == 500
    )
    assert result.position_state == request.position_snapshot.position_state
    assert result.eligibility_instant == _instant(
        3, 100, "funding_eligibility"
    )
    assert result.captured_at == request.captured_at


def test_slot_publication_chain_visibility_and_status_semantics_are_exact() -> None:
    request = _valid_request()
    slot = request.slot_id
    assert slot.value.startswith("funding-slot-v1:")
    assert slot == FundingSlotId.derive(
        contract().instrument.instrument_id, UtcInstant(3)
    )
    assert FundingSlotId.derive(
        contract().instrument.instrument_id, UtcInstant(4)
    ) != slot
    other_instrument = InstrumentId(VenueId("other-perpetual"), "other-linear")
    assert FundingSlotId.derive(other_instrument, UtcInstant(3)) != slot
    with pytest.raises(ValueError, match="semantic key"):
        replace(slot, value="funding-slot-v1:" + "0" * 64)

    for units in (1, 0, -1):
        publication = _publication(
            slot,
            rate=Rate(units, Scale(4), "funding_fraction_of_notional"),
        )
        assert publication.published_rate is not None
        assert publication.published_rate.units == units
    cancelled = _publication(
        slot,
        status=LinearFundingPublicationStatus.CANCELLED,
        rate=None,
    )
    with pytest.raises(ValueError, match="FINAL_RATE"):
        replace(cancelled, status=LinearFundingPublicationStatus.FINAL_RATE)

    root = _publication(
        slot,
        rate=Rate(2, Scale(4), "funding_fraction_of_notional"),
        available_at=_instant(3, 30, "funding_publication"),
    )
    corrected = _publication(
        slot,
        rate=Rate(-1, Scale(4), "funding_fraction_of_notional"),
        event_id="funding-event-corrected",
        available_at=_instant(3, 50, "funding_publication"),
        revision_id="funding-revision-corrected",
        supersedes_revision_id=root.revision_id,
    )
    corrected_request = replace(request, publications=(root, corrected))
    corrected_result = LinearFundingEligibilityResolver().resolve(corrected_request)
    assert corrected_result.result is not None
    assert corrected_result.result.published_rate.units == -1
    assert corrected_result.result.publication_revision_id == corrected.revision_id

    hidden = LinearFundingEligibilityResolver().resolve(
        replace(
            request,
            captured_at=_instant(3, 49, "funding_publication"),
        )
    )
    assert hidden.failure is not None
    assert (
        hidden.failure.code
        is LinearFundingEligibilityFailureCode.INVALID_ELIGIBILITY_INSTANT
    )
    same_utc_later = _publication(
        slot,
        available_at=_instant(3, 101, "funding_publication"),
    )
    not_available = LinearFundingEligibilityResolver().resolve(
        replace(
            request,
            publications=(same_utc_later,),
            captured_at=request.eligibility_instant,
        )
    )
    assert not_available.failure is not None
    assert (
        not_available.failure.code
        is LinearFundingEligibilityFailureCode.PUBLICATION_NOT_AVAILABLE
    )
    visible = LinearFundingEligibilityResolver().resolve(
        replace(
            request,
            publications=(same_utc_later,),
            captured_at=_instant(3, 101, "funding_publication"),
            position_snapshot=_snapshot(
                slot,
                request.eligibility_instant,
                available_at=_instant(3, 100, "funding_eligibility"),
                availability_entry_count=3,
            ),
        )
    )
    assert visible.result is not None


def _failure_cases() -> tuple[
    LinearFundingEligibilityRequest,
    tuple[
        tuple[LinearFundingEligibilityRequest, LinearFundingEligibilityFailureCode],
        ...,
    ],
]:
    valid = _valid_request()
    publication = valid.publications[0]
    assert valid.position_snapshot is not None
    snapshot = valid.position_snapshot
    other_instrument = InstrumentId(valid.position_key.venue_id, "other-linear")
    other_slot = FundingSlotId.derive(
        InstrumentId(VenueId("other-perpetual"), "other-linear"),
        valid.slot_id.target_funding_time,
    )

    cases = (
        (replace(valid, publications=()), LinearFundingEligibilityFailureCode.MISSING_PUBLICATION),
        (replace(valid, slot_id=other_slot), LinearFundingEligibilityFailureCode.SLOT_CONTEXT_MISMATCH),
        (
            replace(
                valid,
                position_key=PositionBalanceKey(
                    valid.position_key.account_id,
                    valid.position_key.venue_id,
                    other_instrument,
                ),
            ),
            LinearFundingEligibilityFailureCode.POSITION_CONTEXT_MISMATCH,
        ),
        (
            replace(valid, eligibility_instant=_instant(3, 99, "funding_eligibility")),
            LinearFundingEligibilityFailureCode.INVALID_ELIGIBILITY_INSTANT,
        ),
        (
            replace(valid, publications=(replace(publication, slot_id=other_slot),)),
            LinearFundingEligibilityFailureCode.PUBLICATION_SLOT_MISMATCH,
        ),
        (
            replace(
                valid,
                publications=(
                    replace(
                        publication,
                        published_rate=Rate(1, Scale(4), "other-basis"),
                    ),
                ),
            ),
            LinearFundingEligibilityFailureCode.UNSUPPORTED_RATE_BASIS,
        ),
        (
            replace(
                valid,
                publications=(
                    publication,
                    _publication(
                        valid.slot_id,
                        event_id="funding-event-gap",
                        available_at=_instant(3, 60, "funding_publication"),
                        revision_id="funding-revision-gap",
                        supersedes_revision_id="missing-revision",
                    ),
                ),
            ),
            LinearFundingEligibilityFailureCode.INVALID_PUBLICATION_REVISION_SET,
        ),
        (
            replace(
                valid,
                publications=(
                    replace(
                        publication,
                        publication_available_at=_instant(1, 0, "funding_publication"),
                    ),
                ),
            ),
            LinearFundingEligibilityFailureCode.INVALID_PUBLICATION_CAUSALITY,
        ),
        (
            replace(
                valid,
                publications=(
                    replace(
                        publication,
                        event_time=UtcInstant(4),
                        publication_available_at=_instant(
                            4, 0, "funding_publication"
                        ),
                    ),
                ),
            ),
            LinearFundingEligibilityFailureCode.LATE_PUBLICATION,
        ),
        (
            replace(
                valid,
                publications=(
                    replace(
                        publication,
                        publication_available_at=_instant(3, 101, "funding_publication"),
                    ),
                ),
                captured_at=valid.eligibility_instant,
            ),
            LinearFundingEligibilityFailureCode.PUBLICATION_NOT_AVAILABLE,
        ),
        (
            replace(
                valid,
                publications=(
                    _publication(
                        valid.slot_id,
                        status=LinearFundingPublicationStatus.CANCELLED,
                        rate=None,
                    ),
                ),
            ),
            LinearFundingEligibilityFailureCode.FUNDING_SLOT_CANCELLED,
        ),
        (replace(valid, position_snapshot=None), LinearFundingEligibilityFailureCode.MISSING_ELIGIBILITY_POSITION),
        (
            replace(
                valid,
                position_snapshot=_snapshot(
                    valid.slot_id,
                    valid.eligibility_instant,
                    supersedes_revision_id="prior-position-revision",
                ),
            ),
            LinearFundingEligibilityFailureCode.UNSUPPORTED_POSITION_REVISION,
        ),
        (
            replace(valid, position_snapshot=replace(snapshot, slot_id=other_slot)),
            LinearFundingEligibilityFailureCode.SNAPSHOT_SLOT_MISMATCH,
        ),
        (
            replace(
                valid,
                position_key=PositionBalanceKey(
                    "other-account",
                    valid.position_key.venue_id,
                    valid.position_key.instrument_id,
                ),
            ),
            LinearFundingEligibilityFailureCode.SNAPSHOT_POSITION_CONTEXT_MISMATCH,
        ),
        (
            replace(
                valid,
                position_snapshot=_snapshot(
                    valid.slot_id, _instant(2, 100, "funding_eligibility")
                ),
            ),
            LinearFundingEligibilityFailureCode.ELIGIBILITY_INSTANT_MISMATCH,
        ),
        (
            replace(
                valid,
                position_snapshot=_snapshot(
                    valid.slot_id,
                    valid.eligibility_instant,
                    available_at=_instant(2, 0, "position_snapshot"),
                ),
            ),
            LinearFundingEligibilityFailureCode.INVALID_POSITION_CAPTURE_CAUSALITY,
        ),
        (
            replace(
                valid,
                position_snapshot=_snapshot(
                    valid.slot_id,
                    valid.eligibility_instant,
                    available_at=_instant(10, 0, "position_snapshot"),
                ),
            ),
            LinearFundingEligibilityFailureCode.POSITION_SNAPSHOT_NOT_AVAILABLE,
        ),
    )
    assert len(cases) == 18
    return valid, cases


def test_all_business_failures_follow_frozen_precedence() -> None:
    resolver = LinearFundingEligibilityResolver()
    valid, cases = _failure_cases()
    for request, code in cases:
        outcome = resolver.resolve(request)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is code
        assert outcome.failure.subject_ids[0] == code.value

    combined = resolver.resolve(
        replace(valid, publications=(), position_snapshot=None)
    )
    assert combined.failure is not None
    assert combined.failure.code is LinearFundingEligibilityFailureCode.MISSING_PUBLICATION


def test_public_values_recompute_identity_and_do_not_mutate_authority() -> None:
    request = _valid_request()
    resolver = LinearFundingEligibilityResolver()
    before = canonical_bytes(request)
    outcome = resolver.resolve(request)
    assert outcome.result is not None
    assert canonical_bytes(request) == before
    result = outcome.result
    assert result.request_hash == canonical_sha256(request)
    assert result.eligibility_hash == canonical_sha256(result)
    assert outcome.outcome_hash == canonical_sha256(outcome)
    assert result.component_ref == resolver.component_ref
    assert isinstance(result.component_ref, LinearFundingEligibilityComponentRef)

    assert request.position_snapshot is not None
    with pytest.raises(ValueError, match="eligibility_cursor"):
        replace(
            request.position_snapshot,
            eligibility_cursor=request.position_snapshot.availability_projection.request.journal.cursor_at(0),
        )
    forged_projection = deepcopy(
        request.position_snapshot.availability_projection
    )
    object.__setattr__(
        forged_projection, "ledger_state_hash", "sha256:" + "0" * 64
    )
    with pytest.raises(ValueError, match="availability_projection"):
        replace(
            request.position_snapshot,
            availability_projection=forged_projection,
        )

    mutated_snapshot = deepcopy(request.position_snapshot)
    object.__setattr__(
        mutated_snapshot,
        "position_state",
        request.position_snapshot.availability_projection.position_state,
    )
    mutated = resolver.resolve(
        replace(request, position_snapshot=mutated_snapshot)
    )
    assert mutated.failure is not None
    assert (
        mutated.failure.code
        is LinearFundingEligibilityFailureCode.SNAPSHOT_POSITION_CONTEXT_MISMATCH
    )

    with pytest.raises(ValueError, match="Eligibility fields"):
        replace(result, event_id="forged-event")
    with pytest.raises(ValueError, match="request_hash"):
        replace(result, request_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="Outcome requires exactly one"):
        LinearFundingEligibilityOutcome(
            resolver.component_ref,
            request.request_hash,
            result,
            resolver.resolve(replace(request, publications=())).failure,
        )
    failure = resolver.resolve(replace(request, publications=())).failure
    assert failure is not None
    with pytest.raises(ValueError, match="first Request failure"):
        replace(
            failure,
            code=LinearFundingEligibilityFailureCode.SLOT_CONTEXT_MISMATCH,
        )
    with pytest.raises(ValueError, match="component_digest"):
        LinearFundingEligibilityComponentRef(
            "instrument.linear-perpetual.funding-eligibility.v1",
            1,
            "sha256:" + "0" * 64,
        )

    class ForgedComponentRef(LinearFundingEligibilityComponentRef):
        def __eq__(self, other: object) -> bool:
            return True

    forged_component = ForgedComponentRef(
        resolver.component_ref.component_key,
        resolver.component_ref.component_version,
        resolver.component_ref.component_digest,
    )
    with pytest.raises(TypeError, match="exact funding eligibility ComponentRef"):
        replace(result, component_ref=forged_component)
    with pytest.raises(TypeError, match="exact funding eligibility ComponentRef"):
        replace(failure, component_ref=forged_component)
    with pytest.raises(TypeError, match="exact funding eligibility ComponentRef"):
        replace(outcome, component_ref=forged_component)

    class ForgedText(str):
        pass

    with pytest.raises(TypeError, match="event_id must be exact string"):
        replace(result, event_id=ForgedText(result.event_id))
