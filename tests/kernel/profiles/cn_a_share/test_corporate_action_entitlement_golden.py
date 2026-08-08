from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    InstrumentType,
    Money,
    PositionBalanceKey,
    Quantity,
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_backtest import DeterministicTimeline, TimelineWindow
from crypto_quant_market_data import EventCursor, InMemoryMarketBundleReader
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCorporateActionAnnouncementStatus,
    CnAShareCorporateActionEntitlement,
    CnAShareCorporateActionEntitlementRuleBook,
    CnAShareCorporateActionFailureCode,
)
from tests.kernel.profiles.cn_a_share._corporate_action_fixtures import (
    OFFICIAL_SOURCE_HASHES,
    entitlement_case,
    local_instant,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = (
    ROOT
    / "tests/fixtures/kernel/profiles/cn_a_share/corporate-action-entitlement-v1.json"
)


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(value, dict)
    return value


def _result(
    venue: str, account_id: str, registered_units: int
) -> CnAShareCorporateActionEntitlement:
    case = entitlement_case(
        venue, account_id=account_id, registered_units=registered_units
    )
    outcome = case.model.apply_corporate_action(case.query)
    assert outcome.result is not None
    return outcome.result


def _timeline_control() -> dict[str, object]:
    case = entitlement_case()
    assert case.query.announcement is not None
    announcement = case.query.announcement
    event = case.event
    assert announcement.event_id == event.event_id
    assert announcement.event_hash == event.event_hash
    control = replace(
        event,
        event_id="event-corporate-action-control",
        phase=TimelinePhase(19, "corporate_action_control"),
        source_sequence=SourceSequence(0),
        revision_id="revision-corporate-action-control",
        payload={"control": True},
    )
    start = type(event.event_time)(event.event_time.epoch_nanoseconds - 1)
    end = type(event.event_time)(event.available_time.epoch_nanoseconds + 1)

    def reader(events):
        return InMemoryMarketBundleReader.build(
            bundle_key="g08f-announcement-golden",
            schema_version=1,
            coverage_start=start,
            coverage_end_exclusive=end,
            instrument_catalog_hash="sha256:" + "d" * 64,
            capabilities=(event.capability,),
            streams={"corporate-actions": events},
        )

    def drain(source_reader, batch_size: int) -> tuple[tuple[str, str], ...]:
        timeline = DeterministicTimeline.open(
            reader=source_reader,
            stream_keys=("corporate-actions",),
            window=TimelineWindow(start, event.event_time, end),
        )
        assert isinstance(timeline, DeterministicTimeline)
        cursor = timeline.open_cursor(batch_size=batch_size)
        values: list[tuple[str, str]] = []
        while True:
            outcome = timeline.read_batch(cursor)
            assert outcome.batch is not None
            values.extend(
                (item.event.event_id, item.event.event_hash)
                for item in outcome.batch.events
            )
            if outcome.batch.window_complete:
                return tuple(values)
            cursor = outcome.batch.next_cursor

    def drain_reader(source_reader, batch_size: int) -> tuple[tuple[str, str], ...]:
        cursor = source_reader.open_cursor(
            "corporate-actions", batch_size=batch_size
        )
        assert isinstance(cursor, EventCursor)
        values: list[tuple[str, str]] = []
        while True:
            batch, next_cursor = source_reader.read_batch(cursor)
            values.extend((item.event_id, item.event_hash) for item in batch)
            if not batch:
                return tuple(values)
            cursor = next_cursor

    forward_reader = reader((control, event))
    reverse_reader = reader((event, control))
    reader_forward_1 = drain_reader(forward_reader, 1)
    reader_forward_3 = drain_reader(forward_reader, 3)
    reader_reverse_2 = drain_reader(reverse_reader, 2)
    assert reader_forward_1 == reader_forward_3 == reader_reverse_2

    forward = drain(forward_reader, 1)
    reverse = drain(reverse_reader, 3)
    assert forward == reverse

    prior_capture = SimulationInstant(
        announcement.announcement_available_at.instant,
        announcement.announcement_available_at.phase,
        SourceSequence(
            announcement.announcement_available_at.source_sequence.value - 1
        ),
    )
    hidden = case.model.apply_corporate_action(
        replace(case.query, captured_at=prior_capture)
    )
    assert hidden.failure is not None
    assert (
        hidden.failure.code
        is CnAShareCorporateActionFailureCode.ANNOUNCEMENT_NOT_AVAILABLE
    )

    return {
        "control_event": control,
        "announcement_event": event,
        "event_hash": event.event_hash,
        "candidate_event_hash": announcement.event_hash,
        "candidate_hash": announcement.candidate_hash,
        "available_at": announcement.announcement_available_at,
        "reader_forward_page_1": reader_forward_1,
        "reader_forward_page_3": reader_forward_3,
        "reader_reverse_page_2": reader_reverse_2,
        "forward_batch_1": forward,
        "reverse_batch_3": reverse,
        "pre_availability_capture": prior_capture,
        "pre_availability_failure": hidden.failure,
    }


def _failures() -> dict[str, object]:
    case = entitlement_case()
    assert case.query.announcement is not None
    assert case.query.snapshot is not None
    announcement = case.query.announcement
    snapshot = case.query.snapshot
    assert announcement.record_date is not None

    negative_snapshot = replace(
        snapshot,
        registered_quantity=replace(snapshot.registered_quantity, units=-1),
    )

    def apply(*, query=case.query, model=case.model, later_negative=True):
        if later_negative and query.snapshot is snapshot:
            query = replace(query, snapshot=negative_snapshot)
        return model.apply_corporate_action(query).failure

    unsupported_venue_instrument = replace(
        case.query.instrument,
        instrument_id=InstrumentId(VenueId("other"), "other.corporate-action"),
    )
    unsupported_venue = apply(
        query=replace(case.query, instrument=unsupported_venue_instrument)
    )
    unsupported_instrument = apply(
        query=replace(
            case.query,
            instrument=replace(
                case.query.instrument, instrument_type=InstrumentType.SPOT
            ),
        )
    )
    unsupported_currency = apply(
        query=replace(
            case.query,
            instrument=replace(
                case.query.instrument, quote_currency=CurrencyId("USD")
            ),
        )
    )
    invalid_causality = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement,
                event_time=UtcInstant(
                    announcement.announcement_available_at.instant.epoch_nanoseconds + 1
                ),
            ),
        )
    )
    missing_component = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement,
                cash_per_share=None,
                bonus_rate=None,
                capitalization_rate=None,
            ),
        )
    )
    missing_lifecycle = apply(
        query=replace(
            case.query,
            announcement=replace(announcement, payment_date=None),
        )
    )
    same_day = TradingDate(
        announcement.record_date.calendar_id,
        announcement.record_date.value,
    )
    invalid_lifecycle = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement,
                ex_date=same_day,
                payment_date=same_day,
                listing_date=same_day,
            ),
        )
    )
    wrong_rate_basis = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement,
                bonus_rate=Rate(1, Scale(1), "fee_fraction"),
            ),
        )
    )
    xshg_case = entitlement_case("xshg")
    assert xshg_case.query.announcement is not None
    assert xshg_case.query.announcement.ex_date is not None
    unsupported_venue_action = xshg_case.model.apply_corporate_action(
        replace(
            xshg_case.query,
            announcement=replace(
                xshg_case.query.announcement,
                bonus_rate=Rate(1, Scale(1), "shares_per_share"),
                listing_date=xshg_case.query.announcement.ex_date,
            ),
        )
    ).failure
    non_positive = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement, cash_per_share=Money(0, Scale(2), "CNY")
            ),
        )
    )
    unavailable_at = replace(
        announcement.announcement_available_at,
        phase=TimelinePhase(19, "corporate_action_announcement"),
    )
    unavailable = apply(
        query=replace(case.query, captured_at=unavailable_at)
    )
    late_available = SimulationInstant(
        snapshot.eligibility_instant.instant,
        TimelinePhase(101, "corporate_action_announcement"),
        SourceSequence(1),
    )
    late = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement,
                event_time=late_available.instant,
                announcement_available_at=late_available,
            ),
        )
    )

    band = case.model.rule_book.bands[0]
    record = announcement.record_date.value
    gap_model = replace(
        case.model,
        rule_book=CnAShareCorporateActionEntitlementRuleBook(
            (replace(band, effective_end=local_instant(record, 15)),)
        ),
    )
    overlap_band = replace(
        band,
        effective_start=local_instant(record, 0),
        effective_end=local_instant(record, 23),
    )
    overlap_model = replace(
        case.model,
        rule_book=CnAShareCorporateActionEntitlementRuleBook((band, overlap_band)),
    )
    extended_model = replace(
        case.model,
        rule_book=CnAShareCorporateActionEntitlementRuleBook(
            (
                replace(
                    band,
                    effective_start=local_instant(record - timedelta(days=1), 0),
                ),
            )
        ),
    )
    weekend = TradingDate("CN.XSHE", date(2026, 7, 18))
    monday = TradingDate("CN.XSHE", date(2026, 7, 20))
    invalid_session = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement,
                record_date=weekend,
                ex_date=monday,
                payment_date=monday,
                listing_date=monday,
            ),
        )
    )
    account = apply(
        query=replace(
            case.query,
            snapshot=replace(
                negative_snapshot,
                position_key=PositionBalanceKey(
                    "other-account",
                    snapshot.position_key.venue_id,
                    snapshot.position_key.instrument_id,
                ),
            ),
        )
    )
    other_instrument = replace(
        announcement.instrument,
        instrument_id=InstrumentId(VenueId("xshe"), "xshe.other.stable"),
    )
    instrument_mismatch = apply(
        query=replace(
            case.query,
            announcement=replace(announcement, instrument=other_instrument),
        )
    )
    record_mismatch = apply(
        query=replace(
            case.query,
            snapshot=replace(
                negative_snapshot,
                eligibility_instant=replace(
                    snapshot.eligibility_instant,
                    source_sequence=SourceSequence(1),
                ),
                available_at=SimulationInstant(
                    snapshot.eligibility_instant.instant,
                    TimelinePhase(99, "corporate_action_register"),
                    SourceSequence(1),
                ),
            ),
        )
    )
    invalid_register = apply(
        query=replace(
            case.query,
            snapshot=replace(
                negative_snapshot,
                available_at=SimulationInstant(
                    snapshot.eligibility_instant.instant,
                    TimelinePhase(99, "corporate_action_register"),
                    SourceSequence(1),
                ),
            ),
            captured_at=snapshot.eligibility_instant,
        )
    )
    register_unavailable = apply(
        query=replace(case.query, captured_at=snapshot.eligibility_instant)
    )
    negative = apply(
        query=replace(case.query, snapshot=negative_snapshot),
        later_negative=False,
    )
    sub_cent = apply(
        query=replace(
            case.query,
            announcement=replace(
                announcement, cash_per_share=Money(1, Scale(3), "CNY")
            ),
            snapshot=replace(
                snapshot,
                registered_quantity=replace(snapshot.registered_quantity, units=7),
            ),
        ),
        later_negative=False,
    )
    fractional_case = entitlement_case(registered_units=7)

    values = {
        "missing_announcement": apply(
            query=replace(case.query, announcement=None, snapshot=None),
            later_negative=False,
        ),
        "unsupported_venue": unsupported_venue,
        "unsupported_instrument": unsupported_instrument,
        "unsupported_currency": unsupported_currency,
        "plan_only": apply(
            query=replace(
                case.query,
                announcement=replace(
                    announcement,
                    status=CnAShareCorporateActionAnnouncementStatus.PLAN_ONLY,
                ),
            )
        ),
        "cancelled": apply(
            query=replace(
                case.query,
                announcement=replace(
                    announcement,
                    status=CnAShareCorporateActionAnnouncementStatus.CANCELLED,
                ),
            )
        ),
        "announcement_revision": apply(
            query=replace(
                case.query,
                announcement=replace(
                    announcement, supersedes_revision_id="prior-revision"
                ),
            )
        ),
        "invalid_announcement_causality": invalid_causality,
        "missing_distribution_component": missing_component,
        "missing_lifecycle": missing_lifecycle,
        "invalid_lifecycle": invalid_lifecycle,
        "unsupported_rate_basis": wrong_rate_basis,
        "unsupported_venue_action": unsupported_venue_action,
        "non_positive": non_positive,
        "announcement_not_available": unavailable,
        "late_announcement": late,
        "rule_gap": apply(model=gap_model),
        "rule_overlap": apply(model=overlap_model),
        "extended_rule_window": apply(model=extended_model),
        "invalid_record_session": invalid_session,
        "missing_register": apply(
            query=replace(case.query, snapshot=None), later_negative=False
        ),
        "register_revision": apply(
            query=replace(
                case.query,
                snapshot=replace(
                    negative_snapshot,
                    supersedes_revision_id="prior-register-revision",
                    position_key=PositionBalanceKey(
                        "other-account",
                        snapshot.position_key.venue_id,
                        snapshot.position_key.instrument_id,
                    ),
                ),
            )
        ),
        "account_mismatch": account,
        "instrument_mismatch": instrument_mismatch,
        "record_mismatch": record_mismatch,
        "invalid_register_causality": invalid_register,
        "register_not_available": register_unavailable,
        "negative_quantity": negative,
        "sub_cent_cash": sub_cent,
        "fractional_share": fractional_case.model.apply_corporate_action(
            fractional_case.query
        ).failure,
    }
    expected_codes = {
        "missing_announcement": "missing_announcement",
        "unsupported_venue": "unsupported_venue",
        "unsupported_instrument": "unsupported_instrument",
        "unsupported_currency": "unsupported_currency",
        "plan_only": "unsupported_announcement_status",
        "cancelled": "unsupported_announcement_status",
        "announcement_revision": "unsupported_announcement_revision",
        "invalid_announcement_causality": "invalid_announcement_causality",
        "missing_distribution_component": "missing_distribution_component",
        "missing_lifecycle": "missing_lifecycle_term",
        "invalid_lifecycle": "invalid_lifecycle_order",
        "unsupported_rate_basis": "unsupported_distribution_rate_basis",
        "unsupported_venue_action": "unsupported_venue_action_combination",
        "non_positive": "non_positive_distribution_term",
        "announcement_not_available": "announcement_not_available",
        "late_announcement": "late_announcement",
        "rule_gap": "missing_rule_interval",
        "rule_overlap": "overlapping_rule_intervals",
        "extended_rule_window": "missing_rule_interval",
        "invalid_record_session": "invalid_record_session",
        "missing_register": "missing_registered_position",
        "register_revision": "unsupported_register_revision",
        "account_mismatch": "account_mismatch",
        "instrument_mismatch": "instrument_mismatch",
        "record_mismatch": "record_instant_mismatch",
        "invalid_register_causality": "invalid_register_causality",
        "register_not_available": "register_not_available",
        "negative_quantity": "negative_registered_quantity",
        "sub_cent_cash": "unsupported_cash_precision",
        "fractional_share": "unsupported_fractional_share",
    }
    for key, value in values.items():
        assert value is not None
        assert value.code.value == expected_codes[key]
    return values


def build_actual() -> dict[str, object]:
    xshe = entitlement_case()
    xshg = entitlement_case("xshg", registered_units=1_000)
    assert xshe.query.announcement is not None
    assert xshe.query.snapshot is not None
    assert xshg.query.announcement is not None
    assert xshg.query.snapshot is not None
    zero = _result("xshe", "account-b", 0)
    combined = _result("xshe", "account-a", 700)
    cash_only = _result("xshg", "account-a", 1_000)
    before = {
        "query_hash": canonical_sha256(xshe.query),
        "rule_book_hash": xshe.model.rule_book.rule_book_hash,
        "calendar_hash": xshe.model.session_model.calendar.calendar_hash,
        "component_digest": xshe.model.component_ref.component_digest,
    }
    probe = xshe.model.apply_corporate_action(xshe.query)
    assert probe.result is not None
    after = {
        "query_hash": canonical_sha256(xshe.query),
        "rule_book_hash": xshe.model.rule_book.rule_book_hash,
        "calendar_hash": xshe.model.session_model.calendar.calendar_hash,
        "component_digest": xshe.model.component_ref.component_digest,
    }
    assert after == before

    payload = {
        "fixture_id": "cn-a-share-corporate-action-entitlement-v1",
        "qualification": {
            "allowed_grade": "development",
            "deployment_authorized": False,
            "supported": (
                "caller-qualified-standard-domestic-xshg-cny-a-share",
                "caller-qualified-standard-domestic-xshe-cny-a-share",
                "final-cash-bonus-capitalization-announcement",
            ),
            "limitations": (
                "finite-2026-07-06-through-2026-07-30-coverage",
                "register-snapshot-is-caller-supplied-development-evidence",
                "complete-revision-set-and-account-scope-belong-to-g08h",
                "fractional-share-and-sub-cent-cash-fail-closed",
                "no-journal-ledger-lot-settlement-or-availability-mutation",
            ),
        },
        "source_evidence": {
            "official_source_hashes": OFFICIAL_SOURCE_HASHES,
            "xshe_rule_book": xshe.model.rule_book,
            "xshe_rule_book_hash": xshe.model.rule_book.rule_book_hash,
            "xshg_rule_book": xshg.model.rule_book,
            "xshg_rule_book_hash": xshg.model.rule_book.rule_book_hash,
        },
        "components": {
            "xshe": xshe.model.component_ref,
            "xshg": xshg.model.component_ref,
        },
        "announcement_timeline": _timeline_control(),
        "entitlements": {
            "xshe_combined_700": combined,
            "xshe_zero": zero,
            "xshg_cash_1000": cash_only,
            "later_current_quantity_ignored": Quantity(
                500, Scale(0), str(xshe.query.instrument.instrument_id)
            ),
            "repeated_zero_hash": zero.entitlement_hash,
        },
        "failures": {
            "precedence": tuple(
                value.value for value in CnAShareCorporateActionFailureCode
            ),
            "controls": _failures(),
        },
        "no_mutation": {
            "before": before,
            "after": after,
            "result_fields": tuple(probe.result.to_canonical_dict()),
            "financial_mutation_fields_absent": True,
        },
        "expected_amounts": {
            "xshe_registered": 700,
            "xshe_cash": Money(7_000, Scale(2), "CNY"),
            "xshe_bonus": 70,
            "xshe_capitalization": 140,
            "xshg_registered": 1_000,
            "xshg_cash": Money(20_000, Scale(2), "CNY"),
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except (TypeError, ValueError) as error:
        raise AssertionError("G08F golden payload must be canonical JSON") from error
    assert isinstance(decoded, dict)
    return decoded


def test_corporate_action_entitlement_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
