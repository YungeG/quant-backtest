from __future__ import annotations

from dataclasses import replace
import json

from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot, validate_market_bundle_v1
from crypto_quant_domain import InstrumentId, VenueId
import crypto_quant_bundle_builder.tushare_cn_a_share_minute as minute
from crypto_quant_bundle_builder.tushare_cn_a_share_minute_bundle import (project_tushare_cn_a_share_minute_bar_close_events_v1, project_tushare_cn_a_share_minute_market_events_v1)


def _result():
    rows = [["000703.SZ", label, 10.50, 10.00, 11.00, 9.50, 100, 1000.00] for label in minute._expected_labels("20240102")]
    source = json.dumps({"request_id":"synthetic","code":0,"data":{"fields":list(minute._FIELDS),"items":rows,"has_more":False,"count":0},"msg":"","detail":"synthetic"}, separators=(",", ":")).encode()
    snapshot = freeze_source_snapshot(members=(RawSourceMember("response/stk-mins.json", source, "0644", 1, None),), provenance=SourceSnapshotProvenance("tushare.pro", "tushare.pro.stk_mins.000703.sz.20240102.5min", "tushare.pro.terms", "backtest.acquisition.candidate")).snapshot
    assert snapshot is not None
    member = snapshot.members[0]
    request = minute.TushareCnAShareMinuteNormalizationRequest(1, snapshot.snapshot_id, snapshot.provenance_hash, member.member_key, member.content_hash, InstrumentId(VenueId("xshe"), "000703"), "20240102")
    outcome = minute.normalize_tushare_cn_a_share_minute_v1(snapshot, request)
    assert outcome.result is not None
    return outcome.result


def test_projects_48_chronological_development_only_events() -> None:
    result = _result()
    events = project_tushare_cn_a_share_minute_market_events_v1(result)
    assert len(events) == 48
    assert events[0].event_time == result.raw_bars[0].bucket.interval_start
    assert events[0].available_time == result.raw_bars[0].available_time
    assert events[0].instrument_id == result.raw_bars[0].instrument_id
    assert events[0].revision_id == result.traces[0].member_content_hash
    assert events[0].payload["execution_reference"]["price_purpose"] == "execution_reference"
    assert events[0].payload["valuation"]["price_purpose"] == "valuation"
    assert events[0].payload["qualification"]["live_eligible"] is False
    validation = validate_market_bundle_v1(bundle_key="synthetic-minute", schema_version=1, coverage_start=events[0].event_time, coverage_end_exclusive=result.raw_bars[-1].bucket.interval_end_exclusive, instrument_catalog_hash="sha256:" + "0" * 64, events=events)
    assert validation.failure is None


def test_projects_real_causal_bar_close_events() -> None:
    result = _result()
    events = project_tushare_cn_a_share_minute_bar_close_events_v1(result)
    assert len(events) == 48
    assert events[0].event_time == events[0].available_time == result.raw_bars[0].bucket.interval_end_exclusive
    assert events[0].capability.identity == "bar_close@1"
    assert events[0].payload == {"schema_version": 1, "bar_kind": "real", "close_price": {"units": 1050, "scale": 2, "quote_currency": "CNY"}, "interval_start": result.raw_bars[0].bucket.interval_start.to_canonical_dict(), "interval_end_exclusive": result.raw_bars[0].bucket.interval_end_exclusive.to_canonical_dict()}
    assert events[0].source_hash == result.traces[0].member_content_hash
    assert events[0].revision_id == result.traces[0].revision_id


def test_private_publisher_rejects_forged_trace_attribution() -> None:
    result = _result()
    forged = replace(result.traces[0], source_key="forged.source")
    try:
        project_tushare_cn_a_share_minute_market_events_v1(replace(result, traces=(forged, *result.traces[1:])))
    except ValueError:
        pass
    else:
        raise AssertionError("forged source attribution was published")
