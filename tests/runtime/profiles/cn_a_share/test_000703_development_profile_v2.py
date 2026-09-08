from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime, timedelta
from functools import cache
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import pytest
from crypto_quant_backtest import (
    CnAShareDevelopmentCommissionScenarioV2,
    CnAShareDevelopmentMinuteAuthorityV2,
    CnAShareProfileComposerV2,
    CnAShareProfileCompositionRequestV2,
    build_cn_a_share_development_source_manifest_v2,
)
from crypto_quant_backtest.cn_a_share_dividend_profile_v2 import (
    compose_tushare_000703_dividend_profile_v2,
)
from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareAccountScopeDeclaration,
    CnAShareInstrumentScopeDeclaration,
    CnAShareProfileCompositionFailureCode,
)
from crypto_quant_backtest.timeline import TimelineWindow
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_bundle_builder.tushare_000703_dividend_action_set_v2 import (
    map_tushare_000703_dividend_action_set_v2,
)
from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
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
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    LocalMarketBundleReader,
    MarketBundleManifest,
    MarketBundleRef,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareBoard,
    CnAShareCalendarDayKind,
    CnAShareExecutionAccessRoute,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareInstrumentRuleContext,
    CnAShareListingPhase,
    CnAShareOrderRuleBand,
    CnAShareOrderRuleBook,
    CnAShareRiskClass,
    CnAShareRuleSourceRef,
)
from crypto_quant_trading.profiles.cn_a_share.january_2024_development_fee_authority import (
    january_2024_commission_scenarios,
    january_2024_fee_rule_books,
)
from tools.acquisition.cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v2 import (
    verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2,
)


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-dividend-authority-v1"
CALENDAR = ROOT / "evidence/tushare-calendar-szse-development-month-202401-v3"
MONTH = ROOT / "evidence/tushare-000703-development-month-authority-202401-v1"
INSTRUMENT = InstrumentId(VenueId("xshe"), "000703")
START = UtcInstant(1_704_124_800_000_000_000)
END = UtcInstant(1_706_716_800_000_000_000)
WINDOW = TimelineWindow(START, START, END)
AVAILABLE = SimulationInstant(
    UtcInstant(1_800_000_000_000_000_000),
    TimelinePhase(1, "development_authority"),
    SourceSequence(0),
)


def _dividend_profile():
    action_set = map_tushare_000703_dividend_action_set_v2(
        (EVIDENCE / "acquisition-receipt.json").read_bytes(),
        (EVIDENCE / "response/dividend.json").read_bytes(),
        INSTRUMENT,
    )
    return compose_tushare_000703_dividend_profile_v2(
        json.loads(canonical_bytes(action_set)),
        "account:000703-development",
        source_receipt_bytes=(EVIDENCE / "acquisition-receipt.json").read_bytes(),
    )


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _retained_source(root: Path, member_key: str):
    receipt_bytes = (root / "acquisition-receipt.json").read_bytes()
    retained = json.loads(receipt_bytes)["snapshot"]
    [member] = retained["members"]
    provenance = retained["provenance"]
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember(
            member_key,
            (root / member_key).read_bytes(),
            "0644",
            member["acquired_at_epoch_nanoseconds"],
            None,
        ),),
        provenance=SourceSnapshotProvenance(
            provenance["vendor_key"], provenance["source_key"],
            provenance["license_ref"], provenance["retention_policy_ref"],
        ),
    ).snapshot
    assert snapshot is not None
    assert snapshot.snapshot_id == retained["snapshot_id"]
    return receipt_bytes, snapshot


@cache
def _calendar() -> CnAShareFrozenCalendar:
    raw, snapshot = _retained_source(CALENDAR, "response/trade-calendar.json")
    verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2(
        raw, snapshot, _sha256(raw)
    )
    data = json.loads((CALENDAR / "response/trade-calendar.json").read_bytes())["data"]
    rows = [dict(zip(data["fields"], row, strict=True)) for row in data["items"]]
    days = tuple(sorted((
        CnAShareFrozenCalendarDay(
            datetime.strptime(row["cal_date"], "%Y%m%d").date(),
            CnAShareCalendarDayKind.TRADING if row["is_open"] == 1
            else CnAShareCalendarDayKind.FROZEN_HOLIDAY,
        )
        for row in rows
    ), key=lambda day: day.local_date))
    return CnAShareFrozenCalendar(
        VenueId("xshe"), "CN.XSHE", days[0].local_date,
        days[-1].local_date + timedelta(days=1), days,
    )


@cache
def _minute_data():
    raw = (MONTH / "authority-receipt.json").read_bytes()
    receipt = json.loads(raw)
    assert receipt["calendar_receipt_sha256"] == _sha256(
        (CALENDAR / "acquisition-receipt.json").read_bytes()
    )
    ref = MarketBundleRef(
        receipt["bundle_ref"]["bundle_key"], receipt["bundle_ref"]["manifest_hash"]
    )
    # Git does not retain read-only mode bits; reopen an immutable temporary mirror.
    with TemporaryDirectory() as directory:
        mirror = Path(directory) / "market"
        shutil.copytree(MONTH, mirror)
        for path in mirror.rglob("*"):
            path.chmod(0o555 if path.is_dir() else 0o444)
        reader = LocalMarketBundleReader.open(repository_root=mirror, bundle_ref=ref)
        [stream] = reader.manifest.streams
        cursor = reader.open_cursor(stream.stream_key, batch_size=128)
        assert isinstance(cursor, EventCursor)
        events = []
        while not cursor.exhausted:
            batch, cursor = reader.read_batch(cursor)
            events.extend(batch)
        assert canonical_sha256(reader.manifest) == receipt["manifest_hash"]
        return reader.manifest, tuple(events), _sha256(raw)


def _order_rule_book() -> CnAShareOrderRuleBook:
    return CnAShareOrderRuleBook(
        "000703-development-order-rules-202401-v1",
        1,
        (
            CnAShareOrderRuleBand(
                VenueId("xshe"),
                CnAShareBoard.MAIN,
                date(2024, 1, 2),
                date(2024, 2, 1),
                Rate(1_000, Scale(4), "fraction"),
                1,
                1_000_000,
                1_000_000,
                1,
                100,
                100,
                0,
                True,
                True,
                CnAShareRuleSourceRef("szse-2023-rules", "sha256:" + "3" * 64),
            ),
        ),
    )


def _request(
    *,
    window: TimelineWindow = WINDOW,
    minute_available_at: SimulationInstant = AVAILABLE,
) -> CnAShareProfileCompositionRequestV2:
    profile = _dividend_profile()
    manifest, events, receipt_hash = _minute_data()
    minutes = (
        CnAShareDevelopmentMinuteAuthorityV2(
            INSTRUMENT,
            manifest,
            receipt_hash,
            minute_available_at,
            True,
            False,
            False,
            False,
            events=events,
        ),
    )
    calendar = _calendar()
    order_rules = _order_rule_book()
    market_fees, stamp_duty = january_2024_fee_rule_books()
    kernel_scenario = january_2024_commission_scenarios()[1]
    commission = CnAShareDevelopmentCommissionScenarioV2(
        kernel_scenario.scenario_key,
        kernel_scenario.commission_rate,
        kernel_scenario.account_fee_schedule_ref,
        kernel_scenario.development_only,
    )
    source_manifest = build_cn_a_share_development_source_manifest_v2(
        instrument_source_snapshot_hash="sha256:" + "1" * 64,
        instrument_rule_context_source_hash="sha256:" + "6" * 64,
        account_source_snapshot_hash="sha256:" + "2" * 64,
        calendar=calendar,
        order_rule_book=order_rules,
        market_fee_rule_book=market_fees,
        stamp_duty_rule_book=stamp_duty,
        commission_scenario=commission,
        minute_authorities=minutes,
        dividend_profile=profile,
    )
    definition = InstrumentDefinition(
        INSTRUMENT,
        InstrumentType.EQUITY,
        None,
        CurrencyId("CNY"),
        CurrencyId("CNY"),
    )
    context = CnAShareInstrumentRuleContext(
        CnAShareBoard.MAIN,
        CnAShareRiskClass.STANDARD,
        CnAShareListingPhase.SEASONED,
        "tushare.000703.development",
        "sha256:" + "6" * 64,
    )
    instrument_scope = CnAShareInstrumentScopeDeclaration(
        definition,
        context,
        START,
        END,
        AVAILABLE,
        True,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        "sha256:" + "1" * 64,
        source_manifest.manifest_hash,
    )
    account_scope = CnAShareAccountScopeDeclaration(
        "account:000703-development",
        VenueId("xshe"),
        START,
        END,
        AVAILABLE,
        True,
        True,
        False,
        False,
        False,
        "sha256:" + "2" * 64,
        source_manifest.manifest_hash,
    )
    return CnAShareProfileCompositionRequestV2(
        source_manifest,
        instrument_scope,
        account_scope,
        calendar,
        order_rules,
        market_fees,
        stamp_duty,
        commission,
        minutes,
        profile,
        window,
        AVAILABLE,
    )


def _rebind(request: CnAShareProfileCompositionRequestV2, **changes):
    instrument = changes.get("instrument_scope", request.instrument_scope)
    account = changes.get("account_scope", request.account_scope)
    values = {
        name: changes.get(name, getattr(request, name))
        for name in (
            "calendar", "order_rule_book", "market_fee_rule_book",
            "stamp_duty_rule_book", "commission_scenario", "minute_authorities",
            "dividend_profile",
        )
    }
    manifest = build_cn_a_share_development_source_manifest_v2(
        instrument_source_snapshot_hash=instrument.source_snapshot_hash,
        instrument_rule_context_source_hash=instrument.rule_context.source_hash,
        account_source_snapshot_hash=account.source_snapshot_hash,
        **values,
    )
    return replace(request, **{
        **changes,
        "source_manifest": manifest,
        "instrument_scope": replace(instrument, source_manifest_hash=manifest.manifest_hash),
        "account_scope": replace(account, source_manifest_hash=manifest.manifest_hash),
    })


def test_empty_minute_manifest_cannot_resolve_a_profile() -> None:
    request = _request()
    authority = request.minute_authorities[0]
    empty = MarketBundleManifest.build(
        bundle_key=authority.manifest.bundle_key,
        schema_version=authority.manifest.schema_version,
        coverage_start=START,
        coverage_end_exclusive=END,
        instrument_catalog_hash=authority.manifest.instrument_catalog_hash,
        capabilities=authority.manifest.capabilities,
        streams=(),
    )
    request = _rebind(request, minute_authorities=(replace(authority, manifest=empty, events=()),))
    outcome = CnAShareProfileComposerV2().compose(request)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CnAShareProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH


def _with_events(authority: CnAShareDevelopmentMinuteAuthorityV2, events):
    manifest = authority.manifest
    reader = InMemoryMarketBundleReader.build(
        bundle_key=manifest.bundle_key,
        schema_version=manifest.schema_version,
        coverage_start=manifest.coverage_start,
        coverage_end_exclusive=manifest.coverage_end_exclusive,
        instrument_catalog_hash=manifest.instrument_catalog_hash,
        capabilities=manifest.capabilities,
        streams={manifest.streams[0].stream_key: events},
    )
    return replace(authority, manifest=reader.manifest, events=tuple(events))


@pytest.mark.parametrize("mutation", (
    "missing_bar", "missing_session", "off_grid_same_count", "duplicate_close",
    "forward_filled", "foreign_instrument", "wrong_currency", "wrong_interval",
))
def test_minute_evidence_must_exact_cover_real_session_closes(mutation: str) -> None:
    request = _request()
    authority = request.minute_authorities[0]
    events = authority.events
    last = events[-1]
    if mutation == "missing_bar":
        events = events[:-1]
    elif mutation == "missing_session":
        events = events[:-48]
    elif mutation == "duplicate_close":
        events += (replace(last, event_id="duplicate-close", source_sequence=SourceSequence(999)),)
    else:
        if mutation == "off_grid_same_count":
            instant = UtcInstant(last.event_time.epoch_nanoseconds + 300_000_000_000)
            last = replace(last, event_time=instant, available_time=instant, payload={
                **last.payload,
                "interval_start": last.event_time.to_canonical_dict(),
                "interval_end_exclusive": instant.to_canonical_dict(),
            })
        elif mutation == "forward_filled":
            last = replace(last, payload={**last.payload, "bar_kind": "forward_filled", "close_price": None})
        elif mutation == "foreign_instrument":
            last = replace(last, instrument_id=InstrumentId(INSTRUMENT.venue, "000001"))
        elif mutation == "wrong_currency":
            price = last.payload["close_price"]
            assert isinstance(price, Mapping)
            last = replace(last, payload={
                **last.payload, "close_price": {**price, "quote_currency": "USD"},
            })
        else:
            last = replace(last, payload={**last.payload, "interval_start": last.event_time.to_canonical_dict()})
        events = (*events[:-1], last)
    rebound = _rebind(request, minute_authorities=(_with_events(authority, events),))
    outcome = CnAShareProfileComposerV2().compose(rebound)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CnAShareProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH


def test_minute_manifest_and_retained_content_must_match() -> None:
    authority = _request().minute_authorities[0]
    with pytest.raises(ValueError, match="event count"):
        replace(authority, events=authority.events[:-1])
    assert replace(authority, events=tuple(reversed(authority.events))) == authority


def test_public_v2_composer_binds_one_immutable_january_authority_package() -> None:
    request = _request()
    outcome = CnAShareProfileComposerV2().compose(request)
    assert outcome.result is not None
    assert outcome.failure is None
    assert outcome.result.source_manifest_hash == request.source_manifest.manifest_hash
    [authority] = request.minute_authorities
    assert len(authority.events) == 1_056
    assert len({event.event_time.epoch_nanoseconds // 86_400_000_000_000 for event in authority.events}) == 22
    assert canonical_sha256(authority.manifest) == json.loads(
        (MONTH / "authority-receipt.json").read_bytes()
    )["manifest_hash"]
    assert outcome.result.development_only is True
    assert outcome.result.decision_grade_eligible is False
    assert outcome.result.live_eligible is False
    assert outcome.result.deployment_authorized is False
    assert request.source_manifest.source_hashes == tuple(
        sorted(request.source_manifest.source_hashes)
    )
    assert (
        request.instrument_scope.rule_context.source_hash
        in request.source_manifest.source_hashes
    )


@pytest.mark.parametrize(
    "change", ("coverage", "availability", "coverage_precedes_availability")
)
def test_public_v2_composer_returns_existing_structured_failures(
    change: str,
) -> None:
    if change == "coverage":
        window = TimelineWindow(START, START, UtcInstant(END.epoch_nanoseconds + 1))
        request = _request(window=window)
        expected = CnAShareProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH
    else:
        future = SimulationInstant(
            UtcInstant(1_900_000_000_000_000_000),
            TimelinePhase(1, "development_authority"),
            SourceSequence(0),
        )
        if change == "coverage_precedes_availability":
            request = _request(
                window=TimelineWindow(
                    START, START, UtcInstant(END.epoch_nanoseconds + 1)
                ),
                minute_available_at=future,
            )
            expected = CnAShareProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH
        else:
            request = _request(minute_available_at=future)
            expected = CnAShareProfileCompositionFailureCode.EVIDENCE_NOT_AVAILABLE
    outcome = CnAShareProfileComposerV2().compose(request)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is expected


@pytest.mark.parametrize("offset_ns", (-1, 0, 1))
def test_dividend_source_must_be_acquired_by_composition(offset_ns: int) -> None:
    request = _request()
    acquired = json.loads((EVIDENCE / "acquisition-receipt.json").read_bytes())[
        "acquired_at_epoch_nanoseconds"
    ]
    composed_at = replace(AVAILABLE, instant=UtcInstant(acquired + offset_ns))
    request = _rebind(
        request,
        instrument_scope=replace(request.instrument_scope, available_at=composed_at),
        account_scope=replace(request.account_scope, available_at=composed_at),
        minute_authorities=tuple(
            replace(value, available_at=composed_at) for value in request.minute_authorities
        ),
        composed_at=composed_at,
    )
    outcome = CnAShareProfileComposerV2().compose(request)
    if offset_ns < 0:
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is CnAShareProfileCompositionFailureCode.EVIDENCE_NOT_AVAILABLE
    else:
        assert outcome.result is not None
        assert outcome.failure is None


def test_commission_scenario_rejects_unrelated_schedule_identity() -> None:
    three_bps, five_bps, _ = january_2024_commission_scenarios()
    with pytest.raises(ValueError, match="account_fee_schedule_ref"):
        CnAShareDevelopmentCommissionScenarioV2(
            five_bps.scenario_key,
            five_bps.commission_rate,
            three_bps.account_fee_schedule_ref,
            True,
        )


@pytest.mark.parametrize("name", ("market_fee_rule_book", "stamp_duty_rule_book"))
@pytest.mark.parametrize("mutation", ("rate", "applicability", "source", "outside_authority", "book_identity"))
def test_fee_economics_must_match_the_selected_january_source(
    name: str, mutation: str,
) -> None:
    request = _request()
    book = getattr(request, name)
    [band] = book.bands
    rate_field, applies_field, sources_field = (
        ("handling_rate", "handling_applies", "handling_source_refs")
        if name == "market_fee_rule_book"
        else ("rate", "applies_to_sell", "source_refs")
    )
    if mutation == "rate":
        original = getattr(band, rate_field)
        changes = {rate_field: replace(original, units=original.units + 1)}
    elif mutation == "applicability":
        changes = {applies_field: False, rate_field: Rate(0, Scale(0), "fee_fraction")}
    elif mutation == "source":
        sources = getattr(band, sources_field)
        changes = {sources_field: (
            replace(sources[0], source_hash="sha256:" + "f" * 64), *sources[1:],
        )}
    elif mutation == "outside_authority":
        changes = {"effective_to_exclusive": UtcInstant(END.epoch_nanoseconds + 1)}
    else:
        changes = {}
    changed = replace(
        book,
        bands=(replace(band, **changes),),
        rule_book_key="unapproved-rule-book" if mutation == "book_identity" else book.rule_book_key,
    )
    outcome = CnAShareProfileComposerV2().compose(_rebind(request, **{name: changed}))
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH


def test_foreign_fee_route_returns_authority_context_failure() -> None:
    request = _request()
    foreign_fees = replace(
        request.market_fee_rule_book,
        access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT,
    )
    source_manifest = build_cn_a_share_development_source_manifest_v2(
        instrument_source_snapshot_hash=request.instrument_scope.source_snapshot_hash,
        instrument_rule_context_source_hash=request.instrument_scope.rule_context.source_hash,
        account_source_snapshot_hash=request.account_scope.source_snapshot_hash,
        calendar=request.calendar,
        order_rule_book=request.order_rule_book,
        market_fee_rule_book=foreign_fees,
        stamp_duty_rule_book=request.stamp_duty_rule_book,
        commission_scenario=request.commission_scenario,
        minute_authorities=request.minute_authorities,
        dividend_profile=request.dividend_profile,
    )
    rebound = replace(
        request,
        source_manifest=source_manifest,
        instrument_scope=replace(
            request.instrument_scope,
            source_manifest_hash=source_manifest.manifest_hash,
        ),
        account_scope=replace(
            request.account_scope,
            source_manifest_hash=source_manifest.manifest_hash,
        ),
        market_fee_rule_book=foreign_fees,
    )
    outcome = CnAShareProfileComposerV2().compose(rebound)
    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH
    )


@pytest.mark.parametrize("name", (
    "order_rule_book", "market_fee_rule_book", "stamp_duty_rule_book",
))
def test_rule_bands_must_match_the_profile_venue(name: str) -> None:
    request = _request()
    book = getattr(request, name)
    foreign = replace(book, bands=tuple(
        replace(band, venue_id=VenueId("xshg")) for band in book.bands
    ))
    outcome = CnAShareProfileComposerV2().compose(_rebind(request, **{name: foreign}))
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH


def test_order_bands_must_match_the_profile_board() -> None:
    request = _request()
    book = replace(request.order_rule_book, bands=tuple(
        replace(band, board=CnAShareBoard.CHINEXT) for band in request.order_rule_book.bands
    ))
    outcome = CnAShareProfileComposerV2().compose(_rebind(request, order_rule_book=book))
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH


@pytest.mark.parametrize("name", (
    "order_rule_book", "market_fee_rule_book", "stamp_duty_rule_book",
))
@pytest.mark.parametrize("shape", ("conflict", "nested_overlap", "gap", "adjacent"))
def test_rule_intervals_must_cover_once(name: str, shape: str) -> None:
    request = _request()
    book = getattr(request, name)
    [band] = book.bands
    if name == "order_rule_book":
        split = date(2024, 1, 17)
        after_split = split + timedelta(days=1)
        conflicting = replace(band, daily_price_limit_ratio=Rate(2_000, Scale(4), "fraction"))
    else:
        split = UtcInstant(START.epoch_nanoseconds + 15 * 86_400_000_000_000)
        after_split = UtcInstant(split.epoch_nanoseconds + 1)
        conflicting = (
            replace(band, handling_rate=Rate(999, Scale(7), "fee_fraction"))
            if name == "market_fee_rule_book"
            else replace(band, rate=Rate(6, Scale(4), "fee_fraction"))
        )
    if shape == "conflict":
        bands = (band, conflicting)
    elif shape == "nested_overlap":
        bands = (band, replace(conflicting, effective_from=split, effective_to_exclusive=after_split))
    else:
        bands = (
            replace(band, effective_to_exclusive=split),
            replace(band, effective_from=after_split if shape == "gap" else split),
        )
    book = replace(book, bands=tuple(sorted(bands, key=lambda value: (
        value.venue_id.value, value.effective_from, value.effective_to_exclusive, value.band_hash,
    ))))
    outcome = CnAShareProfileComposerV2().compose(_rebind(request, **{name: book}))
    if shape == "adjacent":
        assert outcome.result is not None
        assert outcome.failure is None
    else:
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is CnAShareProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH


def test_request_rejects_scope_manifest_drift() -> None:
    request = _request()
    with pytest.raises(ValueError, match="scope declarations"):
        replace(
            request,
            account_scope=replace(
                request.account_scope,
                source_manifest_hash="sha256:" + "f" * 64,
            ),
        )
