from __future__ import annotations

from dataclasses import fields, is_dataclass
from importlib import import_module

import crypto_quant_bundle_builder


_SYMBOLS = (
    "TushareCnAShareDailyNormalizationRequest",
    "TushareCnAShareDailyRawBar",
    "TushareCnAShareDailySourceTrace",
    "TushareCnAShareDailyExecutionReference",
    "TushareCnAShareDailyValuation",
    "TushareCnAShareDailyNormalizationFailureCode",
    "TushareCnAShareDailyNormalizationFailure",
    "TushareCnAShareDailyNormalizationResult",
    "TushareCnAShareDailyNormalizationOutcome",
    "normalize_tushare_cn_a_share_daily_v1",
    "project_execution_reference",
    "project_valuation",
)


def test_tushare_daily_contract_is_internal_and_exact() -> None:
    module = import_module(
        "crypto_quant_bundle_builder.tushare_cn_a_share_daily"
    )

    for name in _SYMBOLS:
        assert hasattr(module, name), f"G12B Tushare RED: missing {name}"
        assert name not in crypto_quant_bundle_builder.__all__

    assert tuple(value.name for value in fields(module.TushareCnAShareDailyNormalizationRequest)) == (
        "schema_version",
        "snapshot_id",
        "provenance_hash",
        "member_key",
        "member_content_hash",
        "instrument_id",
        "provider_trade_date",
        "bucket",
    )
    assert tuple(value.name for value in fields(module.TushareCnAShareDailyRawBar)) == (
        "instrument_id",
        "provider_trade_date",
        "bucket",
        "available_time",
        "open_lexeme",
        "high_lexeme",
        "low_lexeme",
        "close_lexeme",
        "pre_close_lexeme",
        "change_lexeme",
        "pct_change_lexeme",
        "volume_lots_lexeme",
        "amount_thousand_cny_lexeme",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "pre_close_price",
        "change_units",
        "change_scale",
        "pct_change",
        "volume",
        "amount",
        "source_record_hash",
        "limitations",
        "decision_grade_eligible",
        "deployment_authorized",
    )
    assert all(
        is_dataclass(getattr(module, name))
        for name in _SYMBOLS[:9]
        if name != "TushareCnAShareDailyNormalizationFailureCode"
    )
