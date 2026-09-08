from __future__ import annotations

import json

from crypto_quant_domain import SourceSequence, TimelinePhase, canonical_bytes
from crypto_quant_market_data import MarketBundleCapability, MarketEvent
from .tushare_cn_a_share_minute import TushareCnAShareMinuteNormalizationResult

# Private development-only publication constants; this module is intentionally not root-exported.
_STREAM_KEY = "tushare_cn_a_share.minute.publication.xshe.000703.v1"
_EVENT_TYPE = "tushare_cn_a_share_minute_publication.v1"
_CAPABILITY = MarketBundleCapability("tushare_cn_a_share.minute-publications", 1)
_PHASE = TimelinePhase(0, "market_data")
_CLOSE_STREAM_KEY = "tushare_cn_a_share.minute.bar-close.xshe.000703.v1"
_CLOSE_EVENT_TYPE = "bar_close"
_CLOSE_CAPABILITY = MarketBundleCapability("bar_close", 1)


def _canonical_payload(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("canonical minute payload is invalid") from error


def project_tushare_cn_a_share_minute_bar_close_events_v1(result: TushareCnAShareMinuteNormalizationResult) -> tuple[MarketEvent, ...]:
    """Private development-only projection; raw minute bars remain its authority."""
    if type(result) is not TushareCnAShareMinuteNormalizationResult:
        raise TypeError("result must be exact Tushare minute normalization result")
    rebuilt = TushareCnAShareMinuteNormalizationResult(result.request, result.snapshot, result.raw_bars, result.traces, result.execution_references, result.valuations)
    if rebuilt != result:
        raise ValueError("normalization result authority reconstruction mismatch")
    return tuple(
        MarketEvent(
            event_id=f"tushare-cn-a-share-minute-close-v1:{rebuilt.normalization_hash}:{index}",
            stream_key=_CLOSE_STREAM_KEY, event_type=_CLOSE_EVENT_TYPE, capability=_CLOSE_CAPABILITY,
            instrument_id=bar.instrument_id, event_time=bar.bucket.interval_end_exclusive,
            available_time=bar.bucket.interval_end_exclusive, phase=_PHASE, source_sequence=SourceSequence(index),
            revision_id=trace.revision_id, supersedes_revision_id=trace.supersedes_revision_id,
            source_key=trace.source_key, source_hash=trace.member_content_hash,
            payload={"schema_version": 1, "bar_kind": "real", "close_price": {
                "units": bar.close_price.units, "scale": bar.close_price.scale.places,
                "quote_currency": bar.close_price.quote_currency},
                "interval_start": bar.bucket.interval_start.to_canonical_dict(),
                "interval_end_exclusive": bar.bucket.interval_end_exclusive.to_canonical_dict()},
        )
        for index, (bar, trace) in enumerate(zip(rebuilt.raw_bars, rebuilt.traces))
    )


def project_tushare_cn_a_share_minute_market_events_v1(result: TushareCnAShareMinuteNormalizationResult) -> tuple[MarketEvent, ...]:
    if type(result) is not TushareCnAShareMinuteNormalizationResult:
        raise TypeError("result must be exact Tushare minute normalization result")
    try:
        rebuilt = TushareCnAShareMinuteNormalizationResult(result.request, result.snapshot, result.raw_bars, result.traces, result.execution_references, result.valuations)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("normalization result authority is invalid") from error
    if rebuilt != result:
        raise ValueError("normalization result authority reconstruction mismatch")
    normalization_hash = rebuilt.normalization_hash
    return tuple(MarketEvent(
        event_id=f"tushare-cn-a-share-minute-v1:{normalization_hash}:{index}", stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE, capability=_CAPABILITY, instrument_id=bar.instrument_id,
        event_time=bar.bucket.interval_start, available_time=bar.available_time, phase=_PHASE,
        source_sequence=SourceSequence(index), revision_id=trace.revision_id,
        supersedes_revision_id=trace.supersedes_revision_id, source_key=trace.source_key,
        source_hash=trace.member_content_hash,
        payload={"normalization_hash": normalization_hash, "raw_bar": _canonical_payload(bar),
                 "source_trace": _canonical_payload(trace),
                 "execution_reference": _canonical_payload(execution),
                 "valuation": _canonical_payload(valuation), "limitations": list(bar.limitations),
                 "qualification": {"development_only": True, "revision_closure_complete": False,
                                   "decision_grade_eligible": False, "live_eligible": False,
                                   "deployment_authorized": False}},
    ) for index, (bar, trace, execution, valuation) in enumerate(zip(rebuilt.raw_bars, rebuilt.traces, rebuilt.execution_references, rebuilt.valuations)))
