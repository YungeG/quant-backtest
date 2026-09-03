from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Price,
    Rate,
    Scale,
    TradingDate,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareBoard,
    CnAShareCalendarDayKind,
    CnAShareCashOrderRuleModel,
    CnAShareCashSessionModel,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareInstrumentRuleContext,
    CnAShareListingPhase,
    CnAShareOrderRuleBand,
    CnAShareOrderRuleBook,
    CnAShareOrderRuleFailureCode,
    CnAShareOrderRuleQuery,
    CnAShareOrderRuleResolutionKind,
    CnASharePreviousCloseEvidence,
    CnAShareRiskClass,
    CnAShareRuleSourceRef,
    CnAShareSessionQuery,
    CnAShareTradeStatus,
    CnAShareTradeStatusEvidence,
)
from tools.acquisition.cn_a_share_tushare_000703_202401_month_smoke_v2 import (
    verify_tushare_000703_202401_month_smoke_v2,
)
from tools.acquisition.cn_a_share_szse_trading_rules_2023_fixed_source_v1 import (
    verify_szse_trading_rules_2023_fixed_source_v1,
)


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-development-smoke-202401-v4"
CALENDAR_EVIDENCE = ROOT / "evidence/tushare-calendar-szse-development-month-202401-v3"
MINUTE_EVIDENCE = ROOT / "evidence/tushare-minute-000703-development-month-202401-v2/sessions"
SZSE_RULES_EVIDENCE = ROOT / "evidence/szse-trading-rules-2023-fixed-source-v1"
CNY = CurrencyId("CNY")
PRICE_SCALE = Scale(2)
SHANGHAI = ZoneInfo("Asia/Shanghai")
WORKLIST = (
    "20240102", "20240103", "20240104", "20240105", "20240108", "20240109",
    "20240110", "20240111", "20240112", "20240115", "20240116", "20240117",
    "20240118", "20240119", "20240122", "20240123", "20240124", "20240125",
    "20240126", "20240129", "20240130", "20240131",
)


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _row(path: Path) -> dict[str, object]:
    response = cast(dict[str, object], json.loads(path.read_bytes()))
    data = cast(dict[str, object], response["data"])
    fields = cast(list[str], data["fields"])
    items = cast(list[list[object]], data["items"])
    assert len(items) == 1
    return dict(zip(fields, items[0], strict=True))


def test_000703_202401_verified_development_authority_reaches_order_rule_seam() -> None:
    receipt = verify_tushare_000703_202401_month_smoke_v2(
        EVIDENCE, calendar_authority_dir=CALENDAR_EVIDENCE, minute_authority_root=MINUTE_EVIDENCE
    )
    declaration_path = EVIDENCE / "declaration.json"
    declaration = cast(dict[str, object], json.loads(declaration_path.read_bytes()))
    calendar_receipt = cast(
        dict[str, object],
        json.loads((CALENDAR_EVIDENCE / "acquisition-receipt.json").read_bytes()),
    )
    flags = ("decision_grade_eligible", "live_eligible", "deployment_authorized")
    assert all(receipt[flag] is False for flag in flags)
    assert all(declaration[flag] is False for flag in flags)
    assert all(calendar_receipt[flag] is False for flag in flags)
    assert receipt["source_bounded"] is declaration["source_bounded"] is calendar_receipt["source_bounded"] is True
    assert receipt["development_only"] is declaration["development_only"] is calendar_receipt["development_only"] is True
    negative_evidence = {
        "stock_st_terminal_zero": True,
        "suspend_d_s_terminal_zero": True,
        "suspend_d_r_terminal_zero": True,
        "classification": "STANDARD + NORMAL",
        "corporate_action_absence_claimed": False,
    }
    assert declaration["negative_evidence"] == negative_evidence
    assert receipt["declaration_sha256"] == _sha256(declaration_path)

    calendar_source = cast(
        dict[str, object],
        json.loads((CALENDAR_EVIDENCE / "response/trade-calendar.json").read_bytes()),
    )
    calendar_data = cast(dict[str, object], calendar_source["data"])
    calendar_fields = cast(list[str], calendar_data["fields"])
    calendar_items = cast(list[list[object]], calendar_data["items"])
    calendar_rows = [dict(zip(calendar_fields, item, strict=True)) for item in calendar_items]
    assert calendar_fields == ["exchange", "cal_date", "is_open", "pretrade_date"]
    assert all(row["exchange"] == "SZSE" for row in calendar_rows)
    open_rows = {cast(str, row["cal_date"]): row for row in calendar_rows if row["is_open"] == 1}
    assert tuple(sorted(day for day in open_rows if day.startswith("202401"))) == WORKLIST
    assert calendar_receipt["open_sessions"] == list(WORKLIST)
    calendar_days = tuple(
        CnAShareFrozenCalendarDay(
            datetime.strptime(cast(str, row["cal_date"]), "%Y%m%d").date(),
            CnAShareCalendarDayKind.TRADING
            if row["is_open"] == 1
            else CnAShareCalendarDayKind.WEEKEND
            if datetime.strptime(cast(str, row["cal_date"]), "%Y%m%d").weekday() >= 5
            else CnAShareCalendarDayKind.FROZEN_HOLIDAY,
        )
        for row in calendar_rows
    )
    calendar = CnAShareFrozenCalendar(
        venue_id=VenueId("xshe"),
        calendar_id="CN.XSHE",
        coverage_start=min(day.local_date for day in calendar_days),
        coverage_end_exclusive=max(day.local_date for day in calendar_days) + timedelta(days=1),
        days=calendar_days,
    )
    session_model = CnAShareCashSessionModel(calendar)
    rules_receipt = verify_szse_trading_rules_2023_fixed_source_v1(SZSE_RULES_EVIDENCE)
    rules_content_hash = cast(str, rules_receipt["attachment_sha256"])
    band = CnAShareOrderRuleBand(
        venue_id=VenueId("xshe"),
        board=CnAShareBoard.MAIN,
        effective_from=date(2024, 1, 2),
        effective_to_exclusive=date(2024, 2, 1),
        daily_price_limit_ratio=Rate(1_000, Scale(4), "fraction"),
        price_tick_units=1,
        max_limit_order_quantity_units=1_000_000,
        max_market_order_quantity_units=1_000_000,
        quantity_step_units=1,
        buy_lot_units=100,
        sell_lot_units=100,
        min_quantity_units=0,
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=True,
        source_ref=CnAShareRuleSourceRef("szse-trading-rules-2023", rules_content_hash),
    )
    model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook("szse-main-2023-development-authority-smoke-202401-v1", 1, (band,)),
        notional_scale=PRICE_SCALE,
    )
    instrument = InstrumentDefinition(
        instrument_id=InstrumentId(VenueId("xshe"), "000703"),
        instrument_type=InstrumentType.EQUITY,
        base_currency=None,
        quote_currency=CNY,
        settlement_currency=CNY,
    )
    declaration_hash = _sha256(declaration_path)
    raw_members = cast(dict[str, dict[str, object]], declaration["raw_members"])
    queries: dict[str, CnAShareOrderRuleQuery] = {}
    for day in WORKLIST:
        local_day = datetime.strptime(day, "%Y%m%d").date()
        session_outcome = session_model.resolve_session(
            CnAShareSessionQuery(
                venue_id=VenueId("xshe"),
                instant=UtcInstant.from_datetime(datetime(local_day.year, local_day.month, local_day.day, 10, tzinfo=SHANGHAI)),
            )
        )
        assert session_outcome.result is not None
        session = session_outcome.result
        assert session.session_id is not None
        assert session.trading_date is not None
        assert session.phase_start is not None
        assert session.phase_end_exclusive is not None
        daily_key = f"response/{day}/daily.json"
        limit_key = f"response/{day}/stk-limit.json"
        daily = _row(EVIDENCE / daily_key)
        limit = _row(EVIDENCE / limit_key)
        assert _sha256(EVIDENCE / daily_key) == raw_members[daily_key]["sha256"]
        assert _sha256(EVIDENCE / limit_key) == raw_members[limit_key]["sha256"]
        assert daily["ts_code"] == limit["ts_code"] == "000703.SZ"
        assert daily["trade_date"] == limit["trade_date"] == day
        pretrade_date = datetime.strptime(cast(str, open_rows[day]["pretrade_date"]), "%Y%m%d").date()
        query = CnAShareOrderRuleQuery(
            instrument=instrument,
            evaluated_at=session.instant,
            session=session,
            context=CnAShareInstrumentRuleContext(
                board=CnAShareBoard.MAIN,
                risk_class=CnAShareRiskClass.STANDARD,
                listing_phase=CnAShareListingPhase.SEASONED,
                source_key="tushare-000703-development-only-test-authority",
                source_hash=declaration_hash,
            ),
            trade_status_evidence=CnAShareTradeStatusEvidence(
                instrument_id=instrument.instrument_id,
                session_id=session.session_id,
                status=CnAShareTradeStatus.NORMAL,
                effective_from=session.phase_start,
                effective_to_exclusive=session.phase_end_exclusive,
                source_hash=declaration_hash,
            ),
            previous_close_evidence=CnASharePreviousCloseEvidence(
                instrument_id=instrument.instrument_id,
                reference_trading_date=TradingDate("CN.XSHE", pretrade_date),
                price=Price(int(Decimal(str(daily["pre_close"])) * 100), PRICE_SCALE, str(instrument.instrument_id), "CNY"),
                available_at=session.instant,
                source_hash=raw_members[daily_key]["sha256"],
            ),
        )
        queries[day] = query
        outcome = model.resolve_order_rules(query)
        assert outcome.result is not None
        assert outcome.result.kind is CnAShareOrderRuleResolutionKind.RULES
        assert outcome.result.timeline is not None
        snapshot = outcome.result.timeline.intervals[0].snapshot
        assert snapshot.lower_price_limit is not None
        assert snapshot.upper_price_limit is not None
        assert [snapshot.lower_price_limit.units, snapshot.upper_price_limit.units] == [
            int(Decimal(str(limit["down_limit"])) * 100),
            int(Decimal(str(limit["up_limit"])) * 100),
        ]
        assert snapshot.price_tick_units == 1
        assert snapshot.quantity_lattice.buy_lot_units == snapshot.quantity_lattice.sell_lot_units == 100

    missing_status = model.resolve_order_rules(replace(queries[WORKLIST[0]], trade_status_evidence=None))
    missing_previous_close = model.resolve_order_rules(replace(queries[WORKLIST[0]], previous_close_evidence=None))
    gap_model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook("szse-main-2023-development-authority-smoke-202401-gap-v1", 1, (replace(band, effective_to_exclusive=date(2024, 1, 31)),)),
        notional_scale=PRICE_SCALE,
    )
    finite_band_gap = gap_model.resolve_order_rules(queries["20240131"])
    assert missing_status.failure is not None
    assert missing_status.failure.code is CnAShareOrderRuleFailureCode.MISSING_TRADE_STATUS_EVIDENCE
    assert missing_previous_close.failure is not None
    assert missing_previous_close.failure.code is CnAShareOrderRuleFailureCode.MISSING_PREVIOUS_CLOSE_EVIDENCE
    assert finite_band_gap.failure is not None
    assert finite_band_gap.failure.code is CnAShareOrderRuleFailureCode.MISSING_RULE_INTERVAL
