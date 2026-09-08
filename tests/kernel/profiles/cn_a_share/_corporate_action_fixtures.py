from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
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
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCalendarDayKind,
    CnAShareCashSessionModel,
    CnAShareCorporateActionAnnouncementCandidate,
    CnAShareCorporateActionAnnouncementStatus,
    CnAShareCorporateActionEntitlementBand,
    CnAShareCorporateActionEntitlementModel,
    CnAShareCorporateActionEntitlementQuery,
    CnAShareCorporateActionEntitlementRuleBook,
    CnAShareCorporateActionSourceRef,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareRegisteredPositionSnapshot,
)

OFFICIAL_SOURCE_HASHES = {
    "chinaclear.sh-issuer-guide.2026-33": "2e0947b9a19b9962c8a43d603b722e907fbd47d7615be5643be1005661f00ec8",
    "chinaclear.sz-issuer-guide.2025-68": "e8db1f9761b083542d72568a25dcbab02b5d0e86d41309ca108eb362c822e902",
    "sse.announcement-format.2025-36": "b441a51f63ace1c715128324e68dd7c66f00cbc4ad6205924bb5bb516e34b275",
    "sse.distribution-guide.2025-document-5": "2830333711f19875734f6662f506c490429ac2eeba31a74dc52850d556933e40",
    "sse.trading-rules.2026-41.corporate-actions": "fc922c433438b2636cb631eab25cca405209712acbb6aaded768c45456ff8888",
    "szse.announcement-format.2026-7": "704eea0816d091c5502023fafc91b4ca6fe790b34843ee8b8006041d1a731175",
    "szse.trading-rules.2026-551.corporate-actions": "9b66f8b0db70f84a25ef1ccb4ee2351001724e408117552d75f6d8993483c586",
}


def local_instant(local_date: date, hour: int) -> UtcInstant:
    return UtcInstant.from_datetime(
        datetime(
            local_date.year,
            local_date.month,
            local_date.day,
            hour,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
    )


def instrument(venue: str) -> InstrumentDefinition:
    return InstrumentDefinition(
        instrument_id=InstrumentId(VenueId(venue), f"{venue}.corporate-action.stable"),
        instrument_type=InstrumentType.EQUITY,
        base_currency=None,
        quote_currency=CurrencyId("CNY"),
        settlement_currency=CurrencyId("CNY"),
    )


def source(key: str, digest: str) -> CnAShareCorporateActionSourceRef:
    return CnAShareCorporateActionSourceRef(key, "sha256:" + digest)


def frozen_calendar(venue: str) -> CnAShareFrozenCalendar:
    calendar_id = {"xshg": "CN.XSHG", "xshe": "CN.XSHE"}[venue]
    days = tuple(
        CnAShareFrozenCalendarDay(
            value,
            (
                CnAShareCalendarDayKind.WEEKEND
                if value.weekday() >= 5
                else CnAShareCalendarDayKind.TRADING
            ),
        )
        for value in (date(2026, 7, day) for day in range(6, 31))
    )
    return CnAShareFrozenCalendar(
        venue_id=VenueId(venue),
        calendar_id=calendar_id,
        coverage_start=date(2026, 7, 6),
        coverage_end_exclusive=date(2026, 7, 31),
        days=days,
    )


def official_sources(venue: str) -> tuple[CnAShareCorporateActionSourceRef, ...]:
    keys = (
        (
            "chinaclear.sh-issuer-guide.2026-33",
            "sse.announcement-format.2025-36",
            "sse.distribution-guide.2025-document-5",
            "sse.trading-rules.2026-41.corporate-actions",
        )
        if venue == "xshg"
        else (
            "chinaclear.sz-issuer-guide.2025-68",
            "szse.announcement-format.2026-7",
            "szse.trading-rules.2026-551.corporate-actions",
        )
    )
    return tuple(source(key, OFFICIAL_SOURCE_HASHES[key]) for key in keys)


def rule_book(venue: str) -> CnAShareCorporateActionEntitlementRuleBook:
    return CnAShareCorporateActionEntitlementRuleBook(
        (
            CnAShareCorporateActionEntitlementBand(
                venue_id=VenueId(venue),
                effective_start=local_instant(date(2026, 7, 6), 0),
                effective_end=local_instant(date(2026, 7, 31), 0),
                source_refs=official_sources(venue),
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class EntitlementCase:
    model: CnAShareCorporateActionEntitlementModel
    query: CnAShareCorporateActionEntitlementQuery
    event: MarketEvent


def entitlement_case(
    venue: str = "xshe",
    *,
    account_id: str = "account-a",
    registered_units: int = 700,
) -> EntitlementCase:
    subject = instrument(venue)
    calendar_id = {"xshg": "CN.XSHG", "xshe": "CN.XSHE"}[venue]
    if venue == "xshe":
        announcement_day = date(2026, 7, 13)
        record_day = date(2026, 7, 16)
        lifecycle_day = date(2026, 7, 17)
        action_id = "CA-XSHE-001"
        cash = Money(10, Scale(2), "CNY")
        bonus = Rate(1, Scale(1), "shares_per_share")
        capitalization = Rate(2, Scale(1), "shares_per_share")
        listing = TradingDate(calendar_id, lifecycle_day)
    else:
        announcement_day = date(2026, 7, 14)
        record_day = date(2026, 7, 17)
        lifecycle_day = date(2026, 7, 20)
        action_id = "CA-XSHG-001"
        cash = Money(20, Scale(2), "CNY")
        bonus = None
        capitalization = None
        listing = None
    announcement_available = SimulationInstant(
        local_instant(announcement_day, 18),
        TimelinePhase(20, "corporate_action_announcement"),
        SourceSequence(1),
    )
    record = TradingDate(calendar_id, record_day)
    event_source = source(
        f"fixture.{venue}.corporate-action-announcement.v1", "a" * 64
    )
    event_id = f"event-{action_id.lower()}"
    revision_id = f"revision-{action_id.lower()}"
    event = MarketEvent(
        event_id=event_id,
        stream_key="corporate-actions",
        event_type="corporate_action_announced",
        capability=MarketBundleCapability("corporate_actions", 1),
        instrument_id=subject.instrument_id,
        event_time=announcement_available.instant,
        available_time=announcement_available.instant,
        phase=announcement_available.phase,
        source_sequence=announcement_available.source_sequence,
        revision_id=revision_id,
        supersedes_revision_id=None,
        source_key=event_source.source_key,
        source_hash=event_source.source_hash,
        payload={
            "corporate_action_id": action_id,
            "status": "final_implementation",
            "record_date": record.value.isoformat(),
            "ex_date": lifecycle_day.isoformat(),
            "payment_date": lifecycle_day.isoformat(),
            "listing_date": None if listing is None else listing.value.isoformat(),
            "cash_per_share_units": cash.units,
            "cash_per_share_scale": cash.scale.places,
            "bonus_rate_units": None if bonus is None else bonus.units,
            "bonus_rate_scale": None if bonus is None else bonus.scale.places,
            "capitalization_rate_units": (
                None if capitalization is None else capitalization.units
            ),
            "capitalization_rate_scale": (
                None if capitalization is None else capitalization.scale.places
            ),
        },
    )
    announcement = CnAShareCorporateActionAnnouncementCandidate(
        corporate_action_id=action_id,
        instrument=subject,
        status=CnAShareCorporateActionAnnouncementStatus.FINAL_IMPLEMENTATION,
        event_id=event.event_id,
        event_hash=event.event_hash,
        event_time=event.event_time,
        announcement_available_at=event.timeline_instant,
        revision_id=event.revision_id,
        supersedes_revision_id=event.supersedes_revision_id,
        record_date=record,
        ex_date=TradingDate(calendar_id, lifecycle_day),
        payment_date=TradingDate(calendar_id, lifecycle_day),
        listing_date=listing,
        cash_per_share=cash,
        bonus_rate=bonus,
        capitalization_rate=capitalization,
        source_refs=(event_source,),
    )
    eligibility = SimulationInstant(
        local_instant(record_day, 15),
        TimelinePhase(100, "corporate_action_record"),
        SourceSequence(0),
    )
    captured_at = SimulationInstant(
        local_instant(record_day, 18),
        TimelinePhase(100, "corporate_action_register"),
        SourceSequence(1),
    )
    position_key = PositionBalanceKey(
        account_id, VenueId(venue), subject.instrument_id
    )
    snapshot = CnAShareRegisteredPositionSnapshot(
        snapshot_id=f"snapshot-{action_id.lower()}-{account_id}",
        register_series_id=f"register-{action_id.lower()}-{account_id}",
        revision_id="register-revision-1",
        supersedes_revision_id=None,
        account_id=account_id,
        position_key=position_key,
        eligibility_instant=eligibility,
        available_at=captured_at,
        registered_quantity=Quantity(
            registered_units, Scale(0), str(subject.instrument_id)
        ),
        source_ref=source("development.cn-a-share.r-register.v1", "c" * 64),
    )
    return EntitlementCase(
        model=CnAShareCorporateActionEntitlementModel(
            rule_book=rule_book(venue),
            session_model=CnAShareCashSessionModel(frozen_calendar(venue)),
        ),
        query=CnAShareCorporateActionEntitlementQuery(
            instrument=subject,
            account_id=account_id,
            announcement=announcement,
            snapshot=snapshot,
            captured_at=captured_at,
        ),
        event=event,
    )
