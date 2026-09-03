from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import json
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
    CnAShareOrderRuleQuery,
    CnAShareOrderRuleResolutionKind,
    CnASharePreviousCloseEvidence,
    CnAShareRiskClass,
    CnAShareRuleSourceRef,
    CnAShareSessionQuery,
    CnAShareTradeStatus,
    CnAShareTradeStatusEvidence,
)
from tools.acquisition.cn_a_share_tushare_000703_month_order_authority_v1 import (
    verify_tushare_000703_month_order_authority_v1,
)
from tools.acquisition.cn_a_share_szse_trading_rules_2023_fixed_source_v1 import (
    verify_szse_trading_rules_2023_fixed_source_v1,
)


ROOT = Path(__file__).resolve().parents[4]
CNY = CurrencyId("CNY")
PRICE_SCALE = Scale(2)
SHANGHAI = ZoneInfo("Asia/Shanghai")
START = date(2024, 1, 2)
END = date(2026, 9, 1)
SZSE_RULES_EVIDENCE = ROOT / "evidence/szse-trading-rules-2023-fixed-source-v1"


def _months() -> tuple[str, ...]:
    value = date(2024, 1, 1)
    result = []
    while value < END:
        result.append(value.strftime("%Y%m"))
        value = date(
            value.year + (value.month == 12),
            1 if value.month == 12 else value.month + 1,
            1,
        )
    return tuple(result)


MONTHS = _months()


def _paths(month: str) -> tuple[Path, Path, Path]:
    version = "v3" if month == "202401" else "v1"
    minute_version = "v2" if month == "202401" else "v1"
    calendar = ROOT / f"evidence/tushare-calendar-szse-development-month-{month}-{version}"
    minutes = ROOT / f"evidence/tushare-minute-000703-development-month-{month}-{minute_version}/sessions"
    authority = ROOT / f"evidence/tushare-000703-month-order-authority-{month}-v1"
    return calendar, minutes, authority


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _response_row(path: Path) -> dict[str, object]:
    source = cast(dict[str, object], json.loads(path.read_bytes()))
    data = cast(dict[str, object], source["data"])
    fields = cast(list[str], data["fields"])
    [row] = cast(list[list[object]], data["items"])
    return dict(zip(fields, row, strict=True))


def _calendar_rows(calendar_roots: tuple[Path, ...]) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for root in calendar_roots:
        source = cast(
            dict[str, object],
            json.loads((root / "response/trade-calendar.json").read_bytes()),
        )
        data = cast(dict[str, object], source["data"])
        fields = cast(list[str], data["fields"])
        for values in cast(list[list[object]], data["items"]):
            row = dict(zip(fields, values, strict=True))
            day = cast(str, row["cal_date"])
            known = rows.setdefault(day, row)
            assert known == row, f"calendar overlap drift at {day}"
    return rows


def test_all_discovery_and_oos_order_authorities_reach_public_evaluator() -> None:
    month_paths = tuple(_paths(month) for month in MONTHS)
    assert all(path.is_dir() for paths in month_paths for path in paths)
    calendar_rows = _calendar_rows(tuple(paths[0] for paths in month_paths))
    calendar_days = tuple(
        CnAShareFrozenCalendarDay(
            datetime.strptime(day, "%Y%m%d").date(),
            CnAShareCalendarDayKind.TRADING
            if row["is_open"] == 1
            else CnAShareCalendarDayKind.WEEKEND
            if datetime.strptime(day, "%Y%m%d").weekday() >= 5
            else CnAShareCalendarDayKind.FROZEN_HOLIDAY,
        )
        for day, row in sorted(calendar_rows.items())
    )
    calendar = CnAShareFrozenCalendar(
        venue_id=VenueId("xshe"),
        calendar_id="CN.XSHE",
        coverage_start=min(day.local_date for day in calendar_days),
        coverage_end_exclusive=max(day.local_date for day in calendar_days)
        + timedelta(days=1),
        days=calendar_days,
    )
    session_model = CnAShareCashSessionModel(calendar)
    rules_receipt = verify_szse_trading_rules_2023_fixed_source_v1(SZSE_RULES_EVIDENCE)
    rule_book = CnAShareOrderRuleBook(
        "szse-main-2023-development-authority-000703-202401-202608-v1",
        1,
        (
            CnAShareOrderRuleBand(
                venue_id=VenueId("xshe"),
                board=CnAShareBoard.MAIN,
                effective_from=START,
                effective_to_exclusive=END,
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
                source_ref=CnAShareRuleSourceRef(
                    "szse-trading-rules-2023",
                    cast(str, rules_receipt["attachment_sha256"]),
                ),
            ),
        ),
    )
    model = CnAShareCashOrderRuleModel(rule_book, notional_scale=PRICE_SCALE)
    instrument = InstrumentDefinition(
        instrument_id=InstrumentId(VenueId("xshe"), "000703"),
        instrument_type=InstrumentType.EQUITY,
        base_currency=None,
        quote_currency=CNY,
        settlement_currency=CNY,
    )

    resolved = 0
    for month, (calendar_root, minute_root, authority_root) in zip(
        MONTHS, month_paths, strict=True
    ):
        receipt = verify_tushare_000703_month_order_authority_v1(
            authority_root,
            calendar_authority_dir=calendar_root,
            minute_authority_root=minute_root,
        )
        declaration_path = authority_root / "declaration.json"
        declaration = cast(dict[str, object], json.loads(declaration_path.read_bytes()))
        sessions = tuple(cast(list[str], receipt["open_sessions"]))
        assert tuple(cast(list[str], declaration["open_sessions"])) == sessions
        assert all(day.startswith(month) for day in sessions)
        assert receipt["source_bounded"] is receipt["development_only"] is True
        assert all(receipt[flag] is False for flag in (
            "decision_grade_eligible", "live_eligible", "deployment_authorized"
        ))
        assert declaration["negative_evidence"]["corporate_action_absence_claimed"] is False
        raw_members = cast(dict[str, dict[str, object]], declaration["raw_members"])
        declaration_hash = _sha256(declaration_path)
        for day in sessions:
            local_day = datetime.strptime(day, "%Y%m%d").date()
            session_outcome = session_model.resolve_session(
                CnAShareSessionQuery(
                    venue_id=VenueId("xshe"),
                    instant=UtcInstant.from_datetime(
                        datetime(local_day.year, local_day.month, local_day.day, 10, tzinfo=SHANGHAI)
                    ),
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
            daily = _response_row(authority_root / daily_key)
            limit = _response_row(authority_root / limit_key)
            assert _sha256(authority_root / daily_key) == raw_members[daily_key]["sha256"]
            assert _sha256(authority_root / limit_key) == raw_members[limit_key]["sha256"]
            pretrade = datetime.strptime(
                cast(str, calendar_rows[day]["pretrade_date"]), "%Y%m%d"
            ).date()
            outcome = model.resolve_order_rules(
                CnAShareOrderRuleQuery(
                    instrument=instrument,
                    evaluated_at=session.instant,
                    session=session,
                    context=CnAShareInstrumentRuleContext(
                        board=CnAShareBoard.MAIN,
                        risk_class=CnAShareRiskClass.STANDARD,
                        listing_phase=CnAShareListingPhase.SEASONED,
                        source_key="tushare-000703-development-order-authority",
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
                        reference_trading_date=TradingDate("CN.XSHE", pretrade),
                        price=Price(
                            int(Decimal(str(daily["pre_close"])) * 100),
                            PRICE_SCALE,
                            str(instrument.instrument_id),
                            "CNY",
                        ),
                        available_at=session.instant,
                        source_hash=raw_members[daily_key]["sha256"],
                    ),
                )
            )
            assert outcome.result is not None
            assert outcome.result.kind is CnAShareOrderRuleResolutionKind.RULES
            snapshot = outcome.result.timeline.intervals[0].snapshot
            assert [snapshot.lower_price_limit.units, snapshot.upper_price_limit.units] == [
                int(Decimal(str(limit["down_limit"])) * 100),
                int(Decimal(str(limit["up_limit"])) * 100),
            ]
            resolved += 1
    assert resolved > 0
