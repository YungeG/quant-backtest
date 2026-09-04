from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_backtest import DeterministicTimeline, TimelineWindow
from crypto_quant_domain import (
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketEvent,
)
from crypto_quant_trading import (
    AccountingJournal,
    FundingSlotId,
    LinearDerivativeAccounting,
    LinearDerivativeLedgerProjector,
    LinearFundingEligibilityFailureCode,
    LinearFundingEligibilityResolver,
    LinearFundingPublicationStatus,
)

from tests.architecture.test_derivative_boundary import _purity_violations
from tests.kernel.derivatives._fixtures import contract
from tests.kernel.derivatives.test_linear_derivative_accounting import (
    _accounting_request,
    _replay_request,
    _translated_entries,
)
from tests.kernel.derivatives.test_linear_funding_eligibility import (
    _failure_cases,
    _instant,
    _publication,
    _snapshot,
    _valid_request,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/derivatives/linear-funding-eligibility-v1.json"


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(value, dict)
    return value


def _event_and_timeline_control() -> dict[str, object]:
    valid = _valid_request()
    slot = valid.slot_id
    capability = MarketBundleCapability("funding-rate-publications", 1)
    event = MarketEvent(
        event_id="funding-event-market-root",
        stream_key="funding-publications",
        event_type="linear_funding_rate_publication",
        capability=capability,
        instrument_id=slot.instrument_id,
        event_time=UtcInstant(2),
        available_time=UtcInstant(3),
        phase=TimelinePhase(101, "funding_publication"),
        source_sequence=SourceSequence(1),
        revision_id="funding-revision-market-root",
        supersedes_revision_id=None,
        source_key="synthetic.market-event.funding.v1",
        source_hash="sha256:" + "3" * 64,
        payload={
            "slot_id": slot.value,
            "rate_units": 1,
            "rate_scale": 4,
            "rate_basis": "funding_fraction_of_notional",
            "status": "final_rate",
        },
    )
    candidate = _publication(
        slot,
        event_id=event.event_id,
        available_at=event.timeline_instant,
        revision_id=event.revision_id,
    )
    candidate = replace(
        candidate,
        event_hash=event.event_hash,
        event_time=event.event_time,
        source_key=event.source_key,
        source_hash=event.source_hash,
    )
    assert candidate.event_hash == event.event_hash

    control = replace(
        event,
        event_id="funding-event-market-control",
        phase=TimelinePhase(99, "funding_publication_control"),
        source_sequence=SourceSequence(0),
        revision_id="funding-revision-market-control",
        payload={"control": True},
    )
    start = UtcInstant(1)
    end = UtcInstant(4)

    def reader(events):
        return InMemoryMarketBundleReader.build(
            bundle_key="g09c-funding-publication-golden",
            schema_version=1,
            coverage_start=start,
            coverage_end_exclusive=end,
            instrument_catalog_hash="sha256:" + "4" * 64,
            capabilities=(capability,),
            streams={"funding-publications": events},
        )

    def drain_reader(source_reader, page_size: int):
        cursor = source_reader.open_cursor(
            "funding-publications", batch_size=page_size
        )
        assert isinstance(cursor, EventCursor)
        values: list[tuple[str, str]] = []
        while True:
            batch, next_cursor = source_reader.read_batch(cursor)
            values.extend((value.event_id, value.event_hash) for value in batch)
            if not batch:
                return tuple(values)
            cursor = next_cursor

    def drain_timeline(source_reader, batch_size: int):
        timeline = DeterministicTimeline.open(
            reader=source_reader,
            stream_keys=("funding-publications",),
            window=TimelineWindow(start, UtcInstant(2), end),
        )
        assert isinstance(timeline, DeterministicTimeline)
        cursor = timeline.open_cursor(batch_size=batch_size)
        values: list[tuple[str, str]] = []
        while True:
            outcome = timeline.read_batch(cursor)
            assert outcome.batch is not None
            values.extend(
                (value.event.event_id, value.event.event_hash)
                for value in outcome.batch.events
            )
            if outcome.batch.window_complete:
                return tuple(values)
            cursor = outcome.batch.next_cursor

    forward_reader = reader((control, event))
    reverse_reader = reader((event, control))
    reader_before = {
        "manifest_hash": canonical_sha256(forward_reader.manifest),
        "events": tuple(
            value.event_hash
            for value in forward_reader.streams["funding-publications"]
        ),
    }
    reader_1 = drain_reader(forward_reader, 1)
    reader_3 = drain_reader(forward_reader, 3)
    reader_reverse = drain_reader(reverse_reader, 2)
    timeline_1 = drain_timeline(forward_reader, 1)
    timeline_3 = drain_timeline(reverse_reader, 3)
    assert reader_1 == reader_3 == reader_reverse
    assert timeline_1 == timeline_3

    hidden_request = replace(
        valid,
        publications=(candidate,),
        captured_at=valid.eligibility_instant,
        position_snapshot=_snapshot(
            slot,
            valid.eligibility_instant,
            available_at=valid.eligibility_instant,
            availability_entry_count=3,
        ),
    )
    hidden = LinearFundingEligibilityResolver().resolve(hidden_request)
    assert hidden.failure is not None
    assert hidden.failure.code is LinearFundingEligibilityFailureCode.PUBLICATION_NOT_AVAILABLE
    visible_request = replace(
        hidden_request,
        captured_at=event.timeline_instant,
    )
    visible = LinearFundingEligibilityResolver().resolve(visible_request)
    assert visible.result is not None
    reader_after = {
        "manifest_hash": canonical_sha256(forward_reader.manifest),
        "events": tuple(
            value.event_hash
            for value in forward_reader.streams["funding-publications"]
        ),
    }
    assert reader_before == reader_after
    return {
        "market_event": event,
        "candidate": candidate,
        "reader_page_1": reader_1,
        "reader_page_3": reader_3,
        "reader_reverse": reader_reverse,
        "timeline_batch_1": timeline_1,
        "timeline_batch_3": timeline_3,
        "hidden": {
            "code": hidden.failure.code.value,
            "failure_hash": hidden.failure.failure_hash,
            "subject_ids": hidden.failure.subject_ids,
        },
        "visible": {
            "eligibility_hash": visible.result.eligibility_hash,
            "position_state": visible.result.position_state,
            "published_rate": visible.result.published_rate,
        },
        "reader_no_mutation": {"before": reader_before, "after": reader_after},
    }


def _chain_controls() -> dict[str, object]:
    valid = _valid_request()
    slot = valid.slot_id
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
    cancelled = _publication(
        slot,
        status=LinearFundingPublicationStatus.CANCELLED,
        rate=None,
        event_id="funding-event-cancelled",
        available_at=_instant(3, 70, "funding_publication"),
        revision_id="funding-revision-cancelled",
        supersedes_revision_id=corrected.revision_id,
    )
    resolver = LinearFundingEligibilityResolver()
    corrected_outcome = resolver.resolve(
        replace(valid, publications=(root, corrected))
    )
    cancelled_outcome = resolver.resolve(
        replace(valid, publications=(root, corrected, cancelled))
    )
    assert corrected_outcome.result is not None
    assert cancelled_outcome.failure is not None

    invalid = {}
    mutations = {
        "branch": (root, replace(corrected, supersedes_revision_id=None)),
        "gap": (root, replace(corrected, supersedes_revision_id="missing")),
        "reorder": (corrected, root),
        "duplicate_event": (root, replace(corrected, event_id=root.event_id)),
        "duplicate_revision": (
            root,
            replace(corrected, revision_id=root.revision_id),
        ),
        "same_availability": (
            root,
            replace(corrected, publication_available_at=root.publication_available_at),
        ),
    }
    for name, publications in mutations.items():
        outcome = resolver.resolve(replace(valid, publications=publications))
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is LinearFundingEligibilityFailureCode.INVALID_PUBLICATION_REVISION_SET
        )
        invalid[name] = {
            "code": outcome.failure.code.value,
            "failure_hash": outcome.failure.failure_hash,
            "subject_ids": outcome.failure.subject_ids,
        }
    return {
        "root": root,
        "corrected": {
            "eligibility_hash": corrected_outcome.result.eligibility_hash,
            "publication_revision_id": corrected_outcome.result.publication_revision_id,
            "published_rate": corrected_outcome.result.published_rate,
        },
        "cancelled": {
            "code": cancelled_outcome.failure.code.value,
            "failure_hash": cancelled_outcome.failure.failure_hash,
            "subject_ids": cancelled_outcome.failure.subject_ids,
        },
        "invalid": invalid,
    }


def _position_controls() -> dict[str, object]:
    controls = {}
    for name, target in (("long", 3), ("flat", 4), ("short", 7)):
        eligibility = _instant(target, 100, "funding_eligibility")
        slot = FundingSlotId.derive(
            contract().instrument.instrument_id, UtcInstant(target)
        )
        request = replace(
            _valid_request(),
            slot_id=slot,
            eligibility_instant=eligibility,
            publications=(
                _publication(
                    slot,
                    event_time=UtcInstant(target - 1),
                    available_at=_instant(
                        target, 50, "funding_publication"
                    ),
                ),
            ),
            position_snapshot=_snapshot(slot, eligibility),
        )
        outcome = LinearFundingEligibilityResolver().resolve(request)
        assert outcome.result is not None
        controls[name] = {
            "eligibility_hash": outcome.result.eligibility_hash,
            "position_state": outcome.result.position_state,
            "snapshot_hash": outcome.result.snapshot_hash,
            "published_rate": outcome.result.published_rate,
            "terminal_current_state": (
                request.position_snapshot.availability_projection.position_state
                if request.position_snapshot is not None
                else None
            ),
        }

    _, entries = _translated_entries()
    prefixes = []
    for count in range(len(entries) + 1):
        target = count + 20
        eligibility = _instant(target, 100, "funding_eligibility")
        slot = FundingSlotId.derive(
            contract().instrument.instrument_id, UtcInstant(target)
        )
        snapshot = _snapshot(
            slot,
            eligibility,
            available_at=_instant(target, 100, "funding_eligibility"),
            availability_entry_count=count,
        )
        prefixes.append(
            {
                "count": count,
                "cursor": snapshot.eligibility_cursor,
                "snapshot_hash": snapshot.snapshot_hash,
                "position_state": snapshot.position_state,
            }
        )

    direct, entries = _translated_entries()
    journal = AccountingJournal.from_entries(entries)
    availability = LinearDerivativeLedgerProjector().project(
        _replay_request(journal)
    )
    assert availability.result is not None
    accounting = LinearDerivativeAccounting()
    later_third = accounting.translate_position_fact(
        replace(
            _accounting_request(direct.transitions[2], journal_digit="3"),
            recorded_at=_instant(3, 101, "accounting"),
        )
    ).result
    assert later_third is not None
    phase_journal = AccountingJournal.from_entries(
        (entries[0], entries[1], later_third.journal_entry, *entries[3:])
    )
    phase_availability = LinearDerivativeLedgerProjector().project(
        replace(availability.result.request, journal=phase_journal)
    )
    assert phase_availability.result is not None
    eligibility = _instant(3, 100, "funding_eligibility")
    normal = _snapshot(
        _valid_request().slot_id, eligibility
    )
    later = replace(
        normal,
        availability_projection=phase_availability.result,
        eligibility_cursor=phase_journal.cursor_at(2),
        position_state=direct.transitions[1].after,
    )
    assert normal.position_state.quantity.units == 2_000
    assert later.position_state.quantity.units == 3_000
    return {
        "states": controls,
        "prefixes": tuple(prefixes),
        "same_utc_earlier_phase": normal,
        "same_utc_later_phase": later,
        "terminal_current_state": availability.result.position_state,
    }


def build_actual() -> dict[str, object]:
    resolver = LinearFundingEligibilityResolver()
    valid = _valid_request()
    before = {
        "request": canonical_sha256(valid),
        "journal": valid.position_snapshot.availability_projection.request.journal.journal_hash
        if valid.position_snapshot is not None
        else "missing",
        "ledger_state": valid.position_snapshot.availability_projection.ledger_state_hash
        if valid.position_snapshot is not None
        else "missing",
    }
    first = resolver.resolve(valid)
    second = resolver.resolve(valid)
    assert first.result is not None and second.result is not None
    valid_result = first.result
    missing = resolver.resolve(replace(valid, publications=()))
    assert missing.failure is not None
    missing_failure = missing.failure
    assert first == second
    after = {
        "request": canonical_sha256(valid),
        "journal": valid.position_snapshot.availability_projection.request.journal.journal_hash
        if valid.position_snapshot is not None
        else "missing",
        "ledger_state": valid.position_snapshot.availability_projection.ledger_state_hash
        if valid.position_snapshot is not None
        else "missing",
    }
    assert before == after

    _, cases = _failure_cases()
    failures = []
    for request, code in cases:
        outcome = resolver.resolve(request)
        assert outcome.failure is not None
        assert outcome.failure.code is code
        failures.append(
            {
                "code": outcome.failure.code.value,
                "subject_ids": outcome.failure.subject_ids,
                "request_hash": outcome.failure.request_hash,
                "failure_hash": outcome.failure.failure_hash,
            }
        )

    slot = valid.slot_id
    slot_controls = {
        "base": slot,
        "different_time": FundingSlotId.derive(
            slot.instrument_id, UtcInstant(slot.target_funding_time.epoch_nanoseconds + 1)
        ),
        "same_after_rate_change": replace(
            valid,
            publications=(
                replace(
                    valid.publications[0],
                    published_rate=Rate(-9, Scale(4), "funding_fraction_of_notional"),
                ),
            ),
        ).slot_id,
        "same_after_capture_change": replace(
            valid, captured_at=_instant(10, 0, "capture")
        ).slot_id,
        "same_after_account_change": replace(
            valid,
            position_key=replace(
                valid.position_key, account_id="other-funding-account"
            ),
        ).slot_id,
        "same_after_revision_change": replace(
            valid,
            publications=(
                replace(
                    valid.publications[0],
                    revision_id="funding-revision-other",
                ),
            ),
        ).slot_id,
        "same_after_source_change": replace(
            valid,
            publications=(
                replace(
                    valid.publications[0],
                    source_key="synthetic.funding.other-source.v1",
                    source_hash="sha256:" + "9" * 64,
                ),
            ),
        ).slot_id,
    }
    assert slot_controls["base"] == slot_controls["same_after_rate_change"]
    assert slot_controls["base"] == slot_controls["same_after_capture_change"]
    assert slot_controls["base"] == slot_controls["same_after_account_change"]
    assert slot_controls["base"] == slot_controls["same_after_revision_change"]
    assert slot_controls["base"] == slot_controls["same_after_source_change"]

    assert valid.position_snapshot is not None
    forgery_controls = {}
    for name, operation in (
        (
            "slot",
            lambda: replace(slot, value="funding-slot-v1:" + "0" * 64),
        ),
        (
            "cursor",
            lambda: replace(
                valid.position_snapshot,
                eligibility_cursor=valid.position_snapshot.availability_projection.request.journal.cursor_at(2),
            ),
        ),
        ("result", lambda: replace(valid_result, event_id="forged-event")),
        (
            "failure",
            lambda: replace(
                missing_failure,
                code=LinearFundingEligibilityFailureCode.SLOT_CONTEXT_MISMATCH,
            ),
        ),
        (
            "outcome",
            lambda: type(first)(
                resolver.component_ref,
                valid.request_hash,
                valid_result,
                missing_failure,
            ),
        ),
    ):
        try:
            operation()
        except (TypeError, ValueError) as error:
            forgery_controls[name] = {
                "type": type(error).__name__,
                "message": str(error),
            }
        else:
            raise AssertionError(f"{name} forgery must fail")

    funding_path = ROOT / "packages/trading-kernel/src/crypto_quant_trading/funding.py"
    module_purity = tuple(
        sorted(_purity_violations(funding_path.read_text(encoding="utf-8")))
    )
    assert not module_purity

    payload = {
        "fixture_id": "synthetic-linear-funding-eligibility-v1",
        "component_ref": resolver.component_ref,
        "slot_controls": slot_controls,
        "publication_status_values": tuple(
            value.value for value in LinearFundingPublicationStatus
        ),
        "failure_values": tuple(
            value.value for value in LinearFundingEligibilityFailureCode
        ),
        "rate_controls": (
            _publication(slot, rate=Rate(1, Scale(4), "funding_fraction_of_notional")),
            _publication(slot, rate=Rate(0, Scale(4), "funding_fraction_of_notional")),
            _publication(slot, rate=Rate(-1, Scale(4), "funding_fraction_of_notional")),
        ),
        "event_timeline": _event_and_timeline_control(),
        "chains": _chain_controls(),
        "positions": _position_controls(),
        "valid_result": valid_result,
        "all_failures": tuple(failures),
        "forgery_controls": forgery_controls,
        "module_purity_violations": module_purity,
        "canonical_hashes": {
            "component_digest": resolver.component_ref.component_digest,
            "slot_hash": slot.slot_hash,
            "publication_hash": valid.publications[0].publication_hash,
            "snapshot_hash": valid.position_snapshot.snapshot_hash
            if valid.position_snapshot is not None
            else "missing",
            "request_hash": valid.request_hash,
            "eligibility_hash": valid_result.eligibility_hash,
            "outcome_hash": first.outcome_hash,
        },
        "idempotent": first == second,
        "no_mutation": {"before": before, "after": after},
        "limitations": {
            "development_only": True,
            "deployment_authorized": False,
            "obligation_owned": False,
            "journal_owned": False,
            "cash_owned": False,
            "ledger_mutation_owned": False,
            "funding_mark_owned": False,
            "margin_owned": False,
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except (TypeError, ValueError) as error:
        raise AssertionError("G09C golden payload must be canonical JSON") from error
    assert isinstance(decoded, dict)
    return decoded


def test_linear_funding_eligibility_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
