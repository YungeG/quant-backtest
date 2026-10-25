from dataclasses import fields
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import crypto_quant_domain as d
from crypto_quant_backtest import (
    CnASharePortfolioEconomicDailyNavMetricProfileV1, CnASharePortfolioEconomicDailyNavPointV1,
    CnASharePortfolioEconomicDailyNavAnalysisV1,
)
from crypto_quant_backtest.cn_a_share_portfolio_daily_nav_analysis_v1 import _calculate_close_nav_metrics_v1


def test_economic_nav_exact_shape_and_negative_equity_not_clipped():
    assert len([f for f in fields(CnASharePortfolioEconomicDailyNavAnalysisV1) if f.init]) == 13
    assert len(fields(CnASharePortfolioEconomicDailyNavPointV1)) == 11
    profile = CnASharePortfolioEconomicDailyNavMetricProfileV1().to_canonical_dict()
    assert profile["profile_key"] == "cn.shared-cny.economic-close.return-maxdd.fill-count.v1"
    assert not profile["validation_eligible"] and not profile["deployment_authorized"]
    at = d.SimulationInstant(d.UtcInstant.from_datetime(datetime(2023, 8, 29, 15, tzinfo=ZoneInfo("Asia/Shanghai"))),
        d.TimelinePhase(160, "cn_economic_native"), d.SourceSequence(0))
    h = d.canonical_sha256("point.shape")
    point = CnASharePortfolioEconomicDailyNavPointV1("2023-08-29", at, d.Money(-10, d.Scale(2), "CNY"),
        h, h, h, h, h, h, d.Money(100, d.Scale(2), "CNY"), d.Money(200, d.Scale(2), "CNY"))
    assert point.equity.units == -10
    returned, drawdown = _calculate_close_nav_metrics_v1(d.Money(100, d.Scale(2), "CNY"),
        (d.Money(50, d.Scale(2), "CNY"), point.equity))
    assert returned == "-1.1" and drawdown == "1.1"
