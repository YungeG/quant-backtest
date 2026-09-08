from __future__ import annotations

from dataclasses import fields, replace
from datetime import timedelta
from pathlib import Path

from crypto_quant_domain import (
    Money,
    PositionBalanceKey,
    Quantity,
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    canonical_sha256,
)
import pytest

from crypto_quant_backtest import DeterministicTimeline, TimelineWindow
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading import CorporateActionModel
from crypto_quant_trading.profiles import cn_a_share as cn_a_share_profile
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCorporateActionAnnouncementStatus,
    CnAShareCorporateActionEntitlementRuleBook,
    CnAShareCorporateActionFailureCode,
    CnAShareCorporateActionSourceRef,
)

from tests.kernel.profiles.cn_a_share._corporate_action_fixtures import (
    OFFICIAL_SOURCE_HASHES,
    entitlement_case,
    local_instant,
)


def test_combined_distribution_captures_registered_position_once() -> None:
    case = entitlement_case()
    assert isinstance(case.model, CorporateActionModel)

    outcome = case.model.apply_corporate_action(case.query)

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.registered_quantity.units == 700
    assert outcome.result.gross_cash == Money(7_000, Scale(2), "CNY")
    assert outcome.result.bonus_quantity == Quantity(
        70, Scale(0), str(case.query.instrument.instrument_id)
    )
    assert outcome.result.capitalization_quantity == Quantity(
        140, Scale(0), str(case.query.instrument.instrument_id)
    )


def test_announcement_failures_follow_the_frozen_precedence() -> None:
    case = entitlement_case()
    missing = case.model.apply_corporate_action(
        replace(case.query, announcement=None, snapshot=None)
    )
    assert missing.failure is not None
    assert missing.failure.code is CnAShareCorporateActionFailureCode.MISSING_ANNOUNCEMENT

    assert case.query.announcement is not None
    plan = replace(
        case.query.announcement,
        status=CnAShareCorporateActionAnnouncementStatus.PLAN_ONLY,
        supersedes_revision_id="prior",
        cash_per_share=None,
        bonus_rate=None,
        capitalization_rate=None,
    )
    unsupported = case.model.apply_corporate_action(
        replace(case.query, announcement=plan)
    )
    assert unsupported.failure is not None
    assert (
        unsupported.failure.code
        is CnAShareCorporateActionFailureCode.UNSUPPORTED_ANNOUNCEMENT_STATUS
    )

    revised = replace(
        case.query.announcement,
        supersedes_revision_id="prior",
        cash_per_share=None,
        bonus_rate=None,
        capitalization_rate=None,
    )
    revision = case.model.apply_corporate_action(
        replace(case.query, announcement=revised)
    )
    assert revision.failure is not None
    assert (
        revision.failure.code
        is CnAShareCorporateActionFailureCode.UNSUPPORTED_ANNOUNCEMENT_REVISION
    )


def test_announcement_is_not_emitted_before_its_full_available_boundary() -> None:
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
    before = announcement.announcement_available_at.instant.epoch_nanoseconds - 1
    coverage_start = type(event.event_time)(
        event.event_time.epoch_nanoseconds - 3_600_000_000_000
    )
    coverage_end = type(event.event_time)(
        event.available_time.epoch_nanoseconds + 60_000_000_000
    )

    def reader(events):
        return InMemoryMarketBundleReader.build(
            bundle_key="g08f-announcement-causality",
            schema_version=1,
            coverage_start=coverage_start,
            coverage_end_exclusive=coverage_end,
            instrument_catalog_hash="sha256:" + "d" * 64,
            capabilities=(event.capability,),
            streams={"corporate-actions": events},
        )

    hidden = DeterministicTimeline.open(
        reader=reader((event, control)),
        stream_keys=("corporate-actions",),
        window=TimelineWindow(
            data_start=coverage_start,
            trading_start=type(event.event_time)(before - 1),
            end_exclusive=event.available_time,
        ),
    )
    assert isinstance(hidden, DeterministicTimeline)
    hidden_batch = hidden.read_batch(hidden.open_cursor(batch_size=1))
    assert hidden_batch.batch is not None
    assert not hidden_batch.batch.events

    def drain(source_reader, batch_size: int) -> tuple[tuple[str, str], ...]:
        timeline = DeterministicTimeline.open(
            reader=source_reader,
            stream_keys=("corporate-actions",),
            window=TimelineWindow(
                data_start=coverage_start,
                trading_start=type(event.event_time)(before),
                end_exclusive=type(event.event_time)(
                    event.available_time.epoch_nanoseconds + 1
                ),
            ),
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

    expected = (
        (control.event_id, control.event_hash),
        (event.event_id, event.event_hash),
    )
    forward = drain(reader((control, event)), 1)
    reverse = drain(reader((event, control)), 3)
    assert forward == expected
    assert reverse == expected

    same_utc_before_phase = replace(
        announcement.announcement_available_at,
        phase=TimelinePhase(19, "corporate_action_control"),
        source_sequence=SourceSequence(0),
    )
    unavailable = case.model.apply_corporate_action(
        replace(case.query, captured_at=same_utc_before_phase)
    )
    assert unavailable.failure is not None
    assert (
        unavailable.failure.code
        is CnAShareCorporateActionFailureCode.ANNOUNCEMENT_NOT_AVAILABLE
    )


def test_entitlement_arithmetic_fails_closed_without_local_rounding() -> None:
    case = entitlement_case()
    assert case.query.announcement is not None
    assert case.query.snapshot is not None

    negative = case.model.apply_corporate_action(
        replace(
            case.query,
            snapshot=replace(
                case.query.snapshot,
                registered_quantity=replace(
                    case.query.snapshot.registered_quantity, units=-1
                ),
            ),
        )
    )
    assert negative.failure is not None
    assert (
        negative.failure.code
        is CnAShareCorporateActionFailureCode.NEGATIVE_REGISTERED_QUANTITY
    )

    sub_cent = case.model.apply_corporate_action(
        replace(
            case.query,
            announcement=replace(
                case.query.announcement,
                cash_per_share=Money(1, Scale(3), "CNY"),
            ),
        )
    )
    assert sub_cent.failure is not None
    assert (
        sub_cent.failure.code
        is CnAShareCorporateActionFailureCode.UNSUPPORTED_CASH_PRECISION
    )

    fractional_case = entitlement_case(registered_units=7)
    fractional = fractional_case.model.apply_corporate_action(fractional_case.query)
    assert fractional.failure is not None
    assert (
        fractional.failure.code
        is CnAShareCorporateActionFailureCode.UNSUPPORTED_FRACTIONAL_SHARE
    )

    non_positive = case.model.apply_corporate_action(
        replace(
            case.query,
            announcement=replace(
                case.query.announcement,
                cash_per_share=Money(0, Scale(2), "CNY"),
                bonus_rate=Rate(0, Scale(1), "shares_per_share"),
            ),
        )
    )
    assert non_positive.failure is not None
    assert (
        non_positive.failure.code
        is CnAShareCorporateActionFailureCode.NON_POSITIVE_DISTRIBUTION_TERM
    )


def test_lifecycle_order_and_share_rate_basis_are_explicit() -> None:
    case = entitlement_case()
    assert case.query.announcement is not None
    announcement = case.query.announcement
    assert announcement.record_date is not None

    wrong_basis = case.model.apply_corporate_action(
        replace(
            case.query,
            announcement=replace(
                announcement,
                bonus_rate=Rate(1, Scale(1), "fee_fraction"),
            ),
        )
    )
    assert wrong_basis.failure is not None
    assert (
        wrong_basis.failure.code
        is CnAShareCorporateActionFailureCode.UNSUPPORTED_DISTRIBUTION_RATE_BASIS
    )

    same_day = TradingDate(
        announcement.record_date.calendar_id,
        announcement.record_date.value,
    )
    invalid_order = case.model.apply_corporate_action(
        replace(
            case.query,
            announcement=replace(
                announcement,
                ex_date=same_day,
                payment_date=same_day,
                listing_date=same_day,
            ),
        )
    )
    assert invalid_order.failure is not None
    assert (
        invalid_order.failure.code
        is CnAShareCorporateActionFailureCode.INVALID_LIFECYCLE_ORDER
    )

    share_only = case.model.apply_corporate_action(
        replace(
            case.query,
            announcement=replace(
                announcement,
                cash_per_share=None,
                payment_date=None,
            ),
        )
    )
    assert share_only.result is not None
    assert share_only.result.gross_cash.units == 0

    for changed in (
        replace(announcement, ex_date=None),
        replace(announcement, listing_date=None),
    ):
        missing = case.model.apply_corporate_action(
            replace(case.query, announcement=changed)
        )
        assert missing.failure is not None
        assert (
            missing.failure.code
            is CnAShareCorporateActionFailureCode.MISSING_LIFECYCLE_TERM
        )

    wrong_capitalization_basis = case.model.apply_corporate_action(
        replace(
            case.query,
            announcement=replace(
                announcement,
                capitalization_rate=Rate(2, Scale(1), "fee_fraction"),
            ),
        )
    )
    assert wrong_capitalization_basis.failure is not None
    assert (
        wrong_capitalization_basis.failure.code
        is CnAShareCorporateActionFailureCode.UNSUPPORTED_DISTRIBUTION_RATE_BASIS
    )

    xshg = entitlement_case("xshg")
    assert xshg.query.announcement is not None
    assert xshg.query.announcement.ex_date is not None
    unsupported_xshg_shares = xshg.model.apply_corporate_action(
        replace(
            xshg.query,
            announcement=replace(
                xshg.query.announcement,
                bonus_rate=Rate(1, Scale(1), "shares_per_share"),
                listing_date=xshg.query.announcement.ex_date,
            ),
        )
    )
    assert unsupported_xshg_shares.failure is not None
    assert (
        unsupported_xshg_shares.failure.code
        is CnAShareCorporateActionFailureCode.UNSUPPORTED_VENUE_ACTION_COMBINATION
    )


def test_zero_and_cash_only_entitlements_ignore_later_current_holdings() -> None:
    zero_case = entitlement_case(account_id="account-b", registered_units=0)
    zero = zero_case.model.apply_corporate_action(zero_case.query)
    assert zero.failure is None
    assert zero.result is not None
    assert zero.result.gross_cash.units == 0
    assert zero.result.bonus_quantity.units == 0
    assert zero.result.capitalization_quantity.units == 0

    later_current_holding = Quantity(
        500, Scale(0), str(zero_case.query.instrument.instrument_id)
    )
    repeated = zero_case.model.apply_corporate_action(zero_case.query)
    assert later_current_holding.units == 500
    assert repeated.result == zero.result

    cash_case = entitlement_case("xshg", registered_units=1_000)
    cash = cash_case.model.apply_corporate_action(cash_case.query)
    assert cash.failure is None
    assert cash.result is not None
    assert cash.result.gross_cash == Money(20_000, Scale(2), "CNY")
    assert cash.result.bonus_quantity.units == 0
    assert cash.result.capitalization_quantity.units == 0


def test_account_record_and_availability_evidence_are_exactly_bound() -> None:
    case = entitlement_case()
    assert case.query.announcement is not None
    assert case.query.snapshot is not None
    snapshot = case.query.snapshot

    wrong_account = case.model.apply_corporate_action(
        replace(
            case.query,
            snapshot=replace(
                snapshot,
                position_key=PositionBalanceKey(
                    "other-account",
                    snapshot.position_key.venue_id,
                    snapshot.position_key.instrument_id,
                ),
            ),
        )
    )
    assert wrong_account.failure is not None
    assert wrong_account.failure.code is CnAShareCorporateActionFailureCode.ACCOUNT_MISMATCH

    wrong_record = case.model.apply_corporate_action(
        replace(
            case.query,
            snapshot=replace(
                snapshot,
                eligibility_instant=replace(
                    snapshot.eligibility_instant,
                    source_sequence=SourceSequence(1),
                ),
            ),
        )
    )
    assert wrong_record.failure is not None
    assert (
        wrong_record.failure.code
        is CnAShareCorporateActionFailureCode.RECORD_INSTANT_MISMATCH
    )

    premature_register = case.model.apply_corporate_action(
        replace(
            case.query,
            snapshot=replace(
                snapshot,
                available_at=SimulationInstant(
                    snapshot.eligibility_instant.instant,
                    TimelinePhase(99, "corporate_action_register"),
                    SourceSequence(1),
                ),
            ),
        )
    )
    assert premature_register.failure is not None
    assert (
        premature_register.failure.code
        is CnAShareCorporateActionFailureCode.INVALID_REGISTER_CAUSALITY
    )

    unavailable = case.model.apply_corporate_action(
        replace(case.query, captured_at=snapshot.eligibility_instant)
    )
    assert unavailable.failure is not None
    assert unavailable.failure.code is CnAShareCorporateActionFailureCode.REGISTER_NOT_AVAILABLE

    late_available = SimulationInstant(
        snapshot.eligibility_instant.instant,
        TimelinePhase(101, "corporate_action_announcement"),
        SourceSequence(1),
    )
    late = case.model.apply_corporate_action(
        replace(
            case.query,
            announcement=replace(
                case.query.announcement,
                event_time=late_available.instant,
                announcement_available_at=late_available,
            ),
        )
    )
    assert late.failure is not None
    assert late.failure.code is CnAShareCorporateActionFailureCode.LATE_ANNOUNCEMENT


def test_finite_rule_book_gaps_and_overlaps_fail_closed() -> None:
    case = entitlement_case()
    assert case.query.announcement is not None
    assert case.query.announcement.record_date is not None
    band = case.model.rule_book.bands[0]
    record = case.query.announcement.record_date.value

    gap_book = CnAShareCorporateActionEntitlementRuleBook(
        (replace(band, effective_end=local_instant(record, 15)),)
    )
    gap = replace(case.model, rule_book=gap_book).apply_corporate_action(case.query)
    assert gap.failure is not None
    assert gap.failure.code is CnAShareCorporateActionFailureCode.MISSING_RULE_INTERVAL

    overlapping = replace(
        band,
        effective_start=local_instant(record, 0),
        effective_end=local_instant(record, 23),
    )
    overlap_book = CnAShareCorporateActionEntitlementRuleBook((band, overlapping))
    overlap = replace(case.model, rule_book=overlap_book).apply_corporate_action(
        case.query
    )
    assert overlap.failure is not None
    assert (
        overlap.failure.code
        is CnAShareCorporateActionFailureCode.OVERLAPPING_RULE_INTERVALS
    )

    extended_book = CnAShareCorporateActionEntitlementRuleBook(
        (
            replace(
                band,
                effective_start=local_instant(record - timedelta(days=1), 0),
            ),
        )
    )
    extended = replace(case.model, rule_book=extended_book).apply_corporate_action(
        case.query
    )
    assert extended.failure is not None
    assert extended.failure.code is CnAShareCorporateActionFailureCode.MISSING_RULE_INTERVAL


def test_public_contract_and_source_identities_are_frozen() -> None:
    for name in (
        "CnAShareCorporateActionAnnouncementCandidate",
        "CnAShareCorporateActionAnnouncementStatus",
        "CnAShareCorporateActionEntitlement",
        "CnAShareCorporateActionEntitlementBand",
        "CnAShareCorporateActionEntitlementModel",
        "CnAShareCorporateActionEntitlementQuery",
        "CnAShareCorporateActionEntitlementRuleBook",
        "CnAShareCorporateActionFailure",
        "CnAShareCorporateActionFailureCode",
        "CnAShareCorporateActionSourceRef",
        "CnAShareRegisteredPositionSnapshot",
    ):
        assert name in cn_a_share_profile.__all__

    for venue in ("xshg", "xshe"):
        case = entitlement_case(venue)
        actual = {
            ref.source_key: ref.source_hash.removeprefix("sha256:")
            for ref in case.model.rule_book.bands[0].source_refs
        }
        assert actual == {
            key: OFFICIAL_SOURCE_HASHES[key]
            for key in actual
        }
        with pytest.raises(ValueError, match="frozen Venue source identities"):
            replace(
                case.model.rule_book.bands[0],
                source_refs=(
                    CnAShareCorporateActionSourceRef(
                        "fixture.untrusted-source", "sha256:" + "f" * 64
                    ),
                ),
            )

    case = entitlement_case()
    missing = case.model.apply_corporate_action(
        replace(case.query, announcement=None, snapshot=None)
    )
    assert missing.failure is not None
    expected_subject_ids = (
        "missing_announcement",
        "missing-corporate-action",
        "missing-register-snapshot",
        case.query.account_id,
        str(case.query.instrument.instrument_id),
    )
    assert missing.failure.subject_ids == expected_subject_ids


def test_entitlement_model_does_not_mutate_inputs_or_financial_state() -> None:
    case = entitlement_case()
    before = (
        case.query,
        case.model.rule_book,
        case.model.session_model.calendar,
        case.model.component_ref,
    )
    outcome = case.model.apply_corporate_action(case.query)
    after = (
        case.query,
        case.model.rule_book,
        case.model.session_model.calendar,
        case.model.component_ref,
    )
    assert outcome.result is not None
    assert after == before
    forbidden_fields = {
        "journal_entry",
        "ledger_state",
        "lot_changes",
        "settlement_state",
        "availability_state",
    }
    assert forbidden_fields.isdisjoint(outcome.result.to_canonical_dict())


def test_public_outcomes_reject_internally_inconsistent_values() -> None:
    case = entitlement_case()
    outcome = case.model.apply_corporate_action(case.query)
    assert outcome.result is not None
    result = outcome.result
    assert outcome.component_ref == result.component_ref
    assert outcome.input_hash == result.query_hash

    wrong_component = replace(
        result.component_ref,
        component_key="equity.cn_a_share.other-corporate-action.v1",
    )
    with pytest.raises(ValueError, match="frozen Corporate Action Model"):
        replace(result, component_ref=wrong_component)
    changed_band = replace(
        result.active_band,
        effective_start=type(result.active_band.effective_start)(
            result.active_band.effective_start.epoch_nanoseconds - 1
        ),
    )
    changed_rule_book = replace(result.rule_book, bands=(changed_band,))
    with pytest.raises(ValueError, match="embedded RuleBook and Calendar"):
        replace(result, rule_book=changed_rule_book)
    with pytest.raises(ValueError, match="account"):
        replace(result, account_id="other-account")
    with pytest.raises(ValueError, match="embedded Query"):
        replace(result, query_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="active Band"):
        replace(result, band_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="source identities"):
        replace(result, event_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="gross_cash"):
        replace(result, gross_cash=Money(-1, Scale(2), "CNY"))
    with pytest.raises(ValueError, match="quantity"):
        replace(
            result,
            bonus_quantity=Quantity(
                -1, Scale(0), str(case.query.instrument.instrument_id)
            ),
        )

    assert result.query.snapshot is not None
    mismatched_snapshot = replace(result.query.snapshot, account_id="other-account")
    mismatched_query = replace(result.query, snapshot=mismatched_snapshot)
    with pytest.raises(ValueError, match="registered-position evidence"):
        replace(
            result,
            query=mismatched_query,
            query_hash=canonical_sha256(mismatched_query),
            snapshot_hash=mismatched_snapshot.snapshot_hash,
        )

    extended_band = replace(
        result.active_band,
        effective_start=local_instant(
            result.query.announcement.record_date.value - timedelta(days=11), 0
        )
        if result.query.announcement is not None
        and result.query.announcement.record_date is not None
        else result.active_band.effective_start,
    )
    with pytest.raises(ValueError, match="unique RuleBook match"):
        replace(
            result,
            active_band=extended_band,
            band_hash=extended_band.band_hash,
        )

    assert result.query.announcement is not None
    invalid_cash_announcement = replace(
        result.query.announcement,
        cash_per_share=Money(1, Scale(3), "CNY"),
    )
    invalid_cash_query = replace(
        result.query, announcement=invalid_cash_announcement
    )
    with pytest.raises(ValueError, match="CNY Scale 2 cash"):
        replace(
            result,
            query=invalid_cash_query,
            query_hash=canonical_sha256(invalid_cash_query),
            candidate_hash=invalid_cash_announcement.candidate_hash,
        )

    assert result.query.announcement.ex_date is not None
    later_date = TradingDate(
        result.query.announcement.ex_date.calendar_id,
        result.query.announcement.ex_date.value + timedelta(days=1),
    )
    invalid_lifecycle_announcement = replace(
        result.query.announcement,
        ex_date=later_date,
        payment_date=later_date,
        listing_date=later_date,
    )
    invalid_lifecycle_query = replace(
        result.query, announcement=invalid_lifecycle_announcement
    )
    with pytest.raises(ValueError, match="invalid lifecycle evidence"):
        replace(
            result,
            query=invalid_lifecycle_query,
            query_hash=canonical_sha256(invalid_lifecycle_query),
            candidate_hash=invalid_lifecycle_announcement.candidate_hash,
        )

    xshg = entitlement_case("xshg")
    xshg_outcome = xshg.model.apply_corporate_action(xshg.query)
    assert xshg_outcome.result is not None
    assert xshg.query.announcement is not None
    assert xshg.query.announcement.ex_date is not None
    xshg_share_announcement = replace(
        xshg.query.announcement,
        bonus_rate=Rate(1, Scale(1), "shares_per_share"),
        listing_date=xshg.query.announcement.ex_date,
    )
    xshg_share_query = replace(
        xshg.query, announcement=xshg_share_announcement
    )
    with pytest.raises(ValueError, match="unsupported distribution terms"):
        replace(
            xshg_outcome.result,
            query=xshg_share_query,
            query_hash=canonical_sha256(xshg_share_query),
            candidate_hash=xshg_share_announcement.candidate_hash,
        )

    failure_outcome = case.model.apply_corporate_action(
        replace(case.query, announcement=None)
    )
    assert failure_outcome.failure is not None
    failure = failure_outcome.failure
    assert failure_outcome.component_ref == failure.component_ref
    assert failure_outcome.input_hash == failure.query_hash
    with pytest.raises(ValueError, match="frozen Corporate Action Model"):
        replace(failure, component_ref=wrong_component)
    with pytest.raises(ValueError, match="embedded RuleBook and Calendar"):
        replace(failure, rule_book=changed_rule_book)
    with pytest.raises(ValueError, match="embedded Query"):
        replace(failure, query_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="embedded Query and code"):
        replace(
            failure,
            subject_ids=("wrong-code", *failure.subject_ids[1:]),
        )


def test_g08h_owns_current_position_and_cross_query_identity_history() -> None:
    xshe = entitlement_case(account_id="account-b", registered_units=0)
    first = xshe.model.apply_corporate_action(xshe.query)
    assert first.result is not None
    later_xshe_current = Quantity(
        500, Scale(0), str(xshe.query.instrument.instrument_id)
    )
    assert "current_quantity" not in {
        value.name for value in fields(type(xshe.query))
    }
    assert later_xshe_current.units == 500
    assert xshe.model.apply_corporate_action(xshe.query).result == first.result

    xshg = entitlement_case("xshg", registered_units=1_000)
    original = xshg.model.apply_corporate_action(xshg.query)
    assert original.result is not None
    later_xshg_current = Quantity(
        0, Scale(0), str(xshg.query.instrument.instrument_id)
    )
    assert later_xshg_current.units == 0
    assert xshg.model.apply_corporate_action(xshg.query).result == original.result

    assert xshe.query.snapshot is not None
    conflicting = replace(
        xshe.query,
        snapshot=replace(
            xshe.query.snapshot,
            registered_quantity=replace(
                xshe.query.snapshot.registered_quantity, units=100
            ),
        ),
    )
    second = xshe.model.apply_corporate_action(conflicting)
    assert second.result is not None
    assert second.result.entitlement_hash != first.result.entitlement_hash

    profile_root = (
        Path(__file__).resolve().parents[4]
        / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share"
    )
    assert all(
        '"equity.cn_a_share.v1"' not in path.read_text(encoding="utf-8")
        for path in profile_root.glob("*.py")
    )
