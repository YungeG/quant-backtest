from __future__ import annotations

import json

from crypto_quant_domain import SourceSequence, TimelinePhase, canonical_bytes
from crypto_quant_market_data import MarketBundleCapability, MarketEvent

from .tushare_cn_a_share_daily import TushareCnAShareDailyNormalizationResult


_SCHEMA_VERSION = 1
_STREAM_KEY = "tushare_cn_a_share.daily.publication.xshe.000001.v1"
_EVENT_TYPE = "tushare_cn_a_share_daily_publication.v1"
_CAPABILITY = MarketBundleCapability("tushare_cn_a_share.daily-publications", 1)
_PHASE = TimelinePhase(0, "market_data")


def project_tushare_cn_a_share_daily_market_event_v1(
    result: TushareCnAShareDailyNormalizationResult,
) -> MarketEvent:
    if type(result) is not TushareCnAShareDailyNormalizationResult:
        raise TypeError("result must be exact Tushare daily normalization result")
    try:
        rebuilt = TushareCnAShareDailyNormalizationResult(
            result.request,
            result.snapshot,
            result.raw_bar,
            result.trace,
            result.execution_reference,
            result.valuation,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("normalization result authority is invalid") from error
    if rebuilt != result:
        raise ValueError("normalization result authority reconstruction mismatch")
    normalization_hash = rebuilt.normalization_hash

    return MarketEvent(
        event_id=f"tushare-cn-a-share-daily-v1:{normalization_hash}",
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=rebuilt.raw_bar.instrument_id,
        event_time=rebuilt.raw_bar.bucket.interval_start,
        available_time=rebuilt.raw_bar.available_time,
        phase=_PHASE,
        source_sequence=SourceSequence(0),
        revision_id=rebuilt.trace.revision_id,
        supersedes_revision_id=None,
        source_key=rebuilt.trace.source_key,
        source_hash=rebuilt.trace.member_content_hash,
        payload={
            "normalization_hash": normalization_hash,
            "raw_bar": json.loads(canonical_bytes(rebuilt.raw_bar)),
            "source_trace": json.loads(canonical_bytes(rebuilt.trace)),
            "execution_reference": json.loads(
                canonical_bytes(rebuilt.execution_reference)
            ),
            "valuation": json.loads(canonical_bytes(rebuilt.valuation)),
            "qualification": {
                "revision_closure_complete": False,
                "historical_listing_status_qualified": False,
                "corporate_actions_qualified": False,
                "decision_grade_eligible": False,
                "deployment_authorized": False,
            },
        },
    )
