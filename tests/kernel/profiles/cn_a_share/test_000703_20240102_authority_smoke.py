from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
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
from tools.acquisition.cn_a_share_szse_trading_rules_2023_fixed_source_v1 import (
    verify_szse_trading_rules_2023_fixed_source_v1,
)
from tools.acquisition.cn_a_share_tushare_000703_20240102_smoke_v1 import (
    verify_tushare_000703_development_smoke_v1,
)


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-development-smoke-20240102-v1"
SZSE_RULES_EVIDENCE = ROOT / "evidence/szse-trading-rules-2023-fixed-source-v1"
CNY = CurrencyId("CNY")
PRICE_SCALE = Scale(2)
SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_000703_20240102_verified_development_authority_reaches_order_rule_seam() -> None:
    receipt = verify_tushare_000703_development_smoke_v1(EVIDENCE)
    rules_receipt = verify_szse_trading_rules_2023_fixed_source_v1(
        SZSE_RULES_EVIDENCE
    )
    rules_content_hash = cast(str, rules_receipt["attachment_sha256"])
    declaration = cast(
        dict[str, object], json.loads((EVIDENCE / "declaration.json").read_bytes())
    )
    assert receipt["development_only"] is True
    assert receipt["decision_grade_eligible"] is False
    assert declaration["negative_evidence"] == {
        "stock_st_terminal_zero": True,
        "suspend_d_s_terminal_zero": True,
        "suspend_d_r_terminal_zero": True,
        "classification": "STANDARD + NORMAL",
        "corporate_action_absence_claimed": False,
    }
    raw_members = cast(dict[str, str], declaration["raw_members"])
    declaration_hash = cast(str, receipt["declaration_sha256"])

    daily = cast(
        dict[str, object],
        json.loads((EVIDENCE / "response/daily.json").read_bytes())["data"],
    )
    limits = cast(
        dict[str, object],
        json.loads((EVIDENCE / "response/stk-limit.json").read_bytes())["data"],
    )
    daily_row = dict(
        zip(
            cast(list[str], daily["fields"]),
            cast(list[object], daily["items"])[0],
            strict=True,
        )
    )
    limit_row = dict(
        zip(
            cast(list[str], limits["fields"]),
            cast(list[object], limits["items"])[0],
            strict=True,
        )
    )
    assert daily_row["ts_code"] == limit_row["ts_code"] == "000703.SZ"
    assert daily_row["trade_date"] == limit_row["trade_date"] == "20240102"

    calendar = CnAShareFrozenCalendar(
        venue_id=VenueId("xshe"),
        calendar_id="CN.XSHE",
        coverage_start=date(2024, 1, 2),
        coverage_end_exclusive=date(2024, 1, 4),
        days=(
            CnAShareFrozenCalendarDay(
                date(2024, 1, 2), CnAShareCalendarDayKind.TRADING
            ),
            CnAShareFrozenCalendarDay(
                date(2024, 1, 3), CnAShareCalendarDayKind.TRADING
            ),
        ),
    )
    session_model = CnAShareCashSessionModel(calendar)

    def session_for(day: date):
        outcome = session_model.resolve_session(
            CnAShareSessionQuery(
                venue_id=VenueId("xshe"),
                instant=UtcInstant.from_datetime(
                    datetime(day.year, day.month, day.day, 10, tzinfo=SHANGHAI)
                ),
            )
        )
        assert outcome.result is not None
        assert outcome.result.session_id is not None
        assert outcome.result.trading_date is not None
        assert outcome.result.phase_start is not None
        assert outcome.result.phase_end_exclusive is not None
        return outcome.result

    session = session_for(date(2024, 1, 2))
    instrument = InstrumentDefinition(
        instrument_id=InstrumentId(VenueId("xshe"), "000703"),
        instrument_type=InstrumentType.EQUITY,
        base_currency=None,
        quote_currency=CNY,
        settlement_currency=CNY,
    )
    model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook(
            rule_book_key="szse-main-2023-development-authority-smoke-v1",
            rule_book_version=1,
            bands=(
                CnAShareOrderRuleBand(
                    venue_id=VenueId("xshe"),
                    board=CnAShareBoard.MAIN,
                    effective_from=date(2024, 1, 2),
                    effective_to_exclusive=date(2024, 1, 3),
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
                        source_key="szse-trading-rules-2023",
                        source_hash=rules_content_hash,
                    ),
                ),
            ),
        ),
        notional_scale=PRICE_SCALE,
    )
    # Development-only test authority: stock-basic and terminal-zero responses
    # supply STANDARD/SEASONED/NORMAL inputs only; no profile, corporate-action
    # absence, or decision grade is claimed.
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
            reference_trading_date=TradingDate("CN.XSHE", date(2023, 12, 29)),
            price=Price(
                int(Decimal(str(daily_row["pre_close"])) * 100),
                PRICE_SCALE,
                str(instrument.instrument_id),
                "CNY",
            ),
            available_at=session.instant,
            source_hash=raw_members["response/daily.json"],
        ),
    )

    outcome = model.resolve_order_rules(query)
    assert outcome.result is not None
    assert outcome.result.kind is CnAShareOrderRuleResolutionKind.RULES
    assert outcome.result.timeline is not None
    snapshot = outcome.result.timeline.intervals[0].snapshot
    assert snapshot.lower_price_limit is not None
    assert snapshot.upper_price_limit is not None
    assert [snapshot.lower_price_limit.units, snapshot.upper_price_limit.units] == [
        int(Decimal(str(limit_row["down_limit"])) * 100),
        int(Decimal(str(limit_row["up_limit"])) * 100),
    ]
    assert snapshot.price_tick_units == 1
    assert snapshot.quantity_lattice.buy_lot_units == 100
    assert snapshot.quantity_lattice.sell_lot_units == 100
    assert snapshot.max_limit_order_quantity_units == 1_000_000
    assert snapshot.max_market_order_quantity_units == 1_000_000

    # This counterfactual only enters the fail-closed branch; it makes no Jan. 3
    # availability or status interpretation beyond the finite test authority.
    outside_session = session_for(date(2024, 1, 3))
    outside = model.resolve_order_rules(
        replace(
            query,
            evaluated_at=outside_session.instant,
            session=outside_session,
        )
    )
    missing_status = model.resolve_order_rules(replace(query, trade_status_evidence=None))
    missing_previous_close = model.resolve_order_rules(
        replace(query, previous_close_evidence=None)
    )
    assert outside.failure is not None
    assert outside.failure.code is CnAShareOrderRuleFailureCode.MISSING_RULE_INTERVAL
    assert missing_status.failure is not None
    assert missing_status.failure.code is CnAShareOrderRuleFailureCode.MISSING_TRADE_STATUS_EVIDENCE
    assert missing_previous_close.failure is not None
    assert (
        missing_previous_close.failure.code
        is CnAShareOrderRuleFailureCode.MISSING_PREVIOUS_CLOSE_EVIDENCE
    )
