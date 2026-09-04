from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path

import pytest
from crypto_quant_backtest.cn_a_share_development_profile_v2 import (
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
)
from crypto_quant_market_data import MarketBundleCapability, MarketBundleManifest
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


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-dividend-authority-v1"
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
    )


def _calendar() -> CnAShareFrozenCalendar:
    start = date(2024, 1, 1)
    days = tuple(
        CnAShareFrozenCalendarDay(
            start + timedelta(days=offset),
            CnAShareCalendarDayKind.TRADING
            if (start + timedelta(days=offset)).weekday() < 5
            else CnAShareCalendarDayKind.WEEKEND,
        )
        for offset in range(31)
    )
    return CnAShareFrozenCalendar(
        VenueId("xshe"), "CN.XSHE", start, date(2024, 2, 1), days
    )


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
    manifest = MarketBundleManifest.build(
        bundle_key="tushare.000703.minute.202401.v1",
        schema_version=1,
        coverage_start=START,
        coverage_end_exclusive=END,
        instrument_catalog_hash="sha256:" + "4" * 64,
        capabilities=(MarketBundleCapability("bar_close", 1),),
        streams=(),
    )
    minutes = (
        CnAShareDevelopmentMinuteAuthorityV2(
            INSTRUMENT,
            manifest,
            "sha256:" + "5" * 64,
            minute_available_at,
            True,
            False,
            False,
            False,
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


def test_public_v2_composer_binds_one_immutable_january_authority_package() -> None:
    request = _request()
    outcome = CnAShareProfileComposerV2().compose(request)
    assert outcome.result is not None
    assert outcome.failure is None
    assert outcome.result.source_manifest_hash == request.source_manifest.manifest_hash
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


def test_commission_scenario_rejects_unrelated_schedule_identity() -> None:
    three_bps, five_bps, _ = january_2024_commission_scenarios()
    with pytest.raises(ValueError, match="account_fee_schedule_ref"):
        CnAShareDevelopmentCommissionScenarioV2(
            five_bps.scenario_key,
            five_bps.commission_rate,
            three_bps.account_fee_schedule_ref,
            True,
        )


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
