from __future__ import annotations

from dataclasses import replace
import json

from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot
from crypto_quant_domain import InstrumentId, Price, Scale, VenueId
import crypto_quant_bundle_builder.tushare_cn_a_share_minute as minute


def _result(*, volume: object = 100, payload: dict[str, object] | None = None, descending: bool = False):
    rows = [["000703.SZ", label, 10.50, 10.00, 11.00, 9.50, volume, 1000.00] for label in minute._expected_labels("20240102")]
    if descending:
        rows.reverse()
    payload = payload or {"request_id":"synthetic","code":0,"data":{"fields":list(minute._FIELDS),"items":rows,"has_more":False,"count":0},"msg":"","detail":"synthetic"}
    source = json.dumps(payload, separators=(",", ":")).encode()
    snapshot = freeze_source_snapshot(members=(RawSourceMember("response/stk-mins.json", source, "0644", 1, None),), provenance=SourceSnapshotProvenance("tushare.pro", "tushare.pro.stk_mins.000703.sz.20240102.5min", "tushare.pro.terms", "backtest.acquisition.candidate")).snapshot
    assert snapshot is not None
    member = snapshot.members[0]
    request = minute.TushareCnAShareMinuteNormalizationRequest(1, snapshot.snapshot_id, snapshot.provenance_hash, member.member_key, member.content_hash, InstrumentId(VenueId("xshe"), "000703"), "20240102")
    return minute.normalize_tushare_cn_a_share_minute_v1(snapshot, request)


def test_regular_bars_bind_source_bucket_and_exclude_anchor() -> None:
    outcome = _result()
    assert outcome.failure is None and outcome.result is not None
    result = outcome.result; first = result.raw_bars[0]
    assert len(result.raw_bars) == 48
    assert first.provider_trade_time.endswith("09:35:00")
    assert first.provider_ts_code == "000703.SZ" and first.instrument_id == result.request.instrument_id
    assert first.bucket.session_id.value == "2024-01-02.regular"
    assert first.bucket.trading_date.value.isoformat() == "2024-01-02"
    assert first.bucket.included_spans == ((first.bucket.interval_start, first.bucket.interval_end_exclusive),)
    assert first.available_time == first.bucket.interval_end_exclusive
    assert first.close_lexeme == "10.5" and first.volume_lexeme == "100"
    assert first.decision_grade_eligible is first.live_eligible is first.deployment_authorized is False
    assert result.execution_references[0].open_price == first.open_price
    assert result.valuations[0].close_price == first.close_price
    assert result.execution_references[0].projection_hash != result.valuations[0].projection_hash


def test_fractional_quantity_and_session_label_are_rejected() -> None:
    outcome = _result(volume=100.5)
    assert outcome.failure is not None
    assert outcome.failure.code is minute.TushareCnAShareMinuteNormalizationFailureCode.DECIMAL_MAPPING_INVALID


def test_descending_source_rows_normalize_chronologically() -> None:
    outcome = _result(descending=True)
    assert outcome.failure is None and outcome.result is not None
    result = outcome.result
    assert tuple(bar.provider_trade_time for bar in result.raw_bars) == minute._expected_labels("20240102")[1:]
    assert tuple(trace.record_index for trace in result.traces) == tuple(range(1, 49))


def test_source_order_parity_preserves_chronological_bars() -> None:
    ascending = _result().result
    descending = _result(descending=True).result
    assert ascending is not None and descending is not None
    assert descending.raw_bars == ascending.raw_bars


def test_normalizer_distinguishes_schema_and_session_failures() -> None:
    schema = _result(payload={"request_id": "synthetic"})
    assert schema.failure is not None
    assert schema.failure.code is minute.TushareCnAShareMinuteNormalizationFailureCode.SOURCE_SCHEMA_MISMATCH

    rows = [["000703.SZ", label, 10.50, 10.00, 11.00, 9.50, 100, 1000.00] for label in minute._expected_labels("20240102")[1:]]
    session = _result(payload={"request_id":"synthetic","code":0,"data":{"fields":list(minute._FIELDS),"items":rows,"has_more":False,"count":0},"msg":"","detail":"synthetic"})
    assert session.failure is not None
    assert session.failure.code is minute.TushareCnAShareMinuteNormalizationFailureCode.SOURCE_SESSION_MISMATCH

    off_grid_rows = [["000703.SZ", label, 10.50, 10.00, 11.00, 9.50, 100, 1000.00] for label in minute._expected_labels("20240102")]
    off_grid_rows[0][1] = "2024-01-02 09:31:00"
    off_grid = _result(payload={"request_id":"synthetic","code":0,"data":{"fields":list(minute._FIELDS),"items":off_grid_rows,"has_more":False,"count":0},"msg":"","detail":"synthetic"})
    assert off_grid.failure is not None
    assert off_grid.failure.code is minute.TushareCnAShareMinuteNormalizationFailureCode.SOURCE_SESSION_MISMATCH

    duplicate_rows = [["000703.SZ", label, 10.50, 10.00, 11.00, 9.50, 100, 1000.00] for label in minute._expected_labels("20240102")]
    duplicate_rows[-1][1] = duplicate_rows[0][1]
    duplicate = _result(payload={"request_id":"synthetic","code":0,"data":{"fields":list(minute._FIELDS),"items":duplicate_rows,"has_more":False,"count":0},"msg":"","detail":"synthetic"})
    assert duplicate.failure is not None
    assert duplicate.failure.code is minute.TushareCnAShareMinuteNormalizationFailureCode.SOURCE_SESSION_MISMATCH

    malformed_rows = [["000703.SZ", label, 10.50, 10.00, 11.00, 9.50, 100, 1000.00] for label in minute._expected_labels("20240102")]
    malformed_rows[0][2] = "10.50"
    malformed = _result(payload={"request_id":"synthetic","code":0,"data":{"fields":list(minute._FIELDS),"items":malformed_rows,"has_more":False,"count":0},"msg":"","detail":"synthetic"})
    assert malformed.failure is not None
    assert malformed.failure.code is minute.TushareCnAShareMinuteNormalizationFailureCode.SOURCE_SCHEMA_MISMATCH


def test_canonical_dicts_include_type_and_nonself_hashes() -> None:
    result = _result().result
    assert result is not None
    for value, hash_name in ((result.request, "request_hash"), (result.raw_bars[0], "raw_bar_hash"),
                             (result.traces[0], "trace_hash"), (result.execution_references[0], "projection_hash"),
                             (result.valuations[0], "projection_hash"), (result, "normalization_hash")):
        canonical = value.to_canonical_dict()
        assert canonical["schema_version"] == 1
        assert canonical["type"].startswith("tushare_cn_a_share_minute_")
        assert canonical[hash_name] == getattr(value, hash_name)


def test_result_rejects_coherent_forged_source_record() -> None:
    result = _result().result
    assert result is not None
    bar = result.raw_bars[0]
    lexemes = ("10.6", bar.open_lexeme, bar.high_lexeme, bar.low_lexeme, bar.volume_lexeme, bar.amount_lexeme)
    forged_bar = replace(bar, close_lexeme="10.6", close_price=Price(1060, Scale(2), str(bar.instrument_id), "CNY"), source_record_hash=minute._source_record_hash(bar.provider_ts_code, bar.provider_trade_time, lexemes))
    forged_trace = replace(result.traces[0], source_record_hash=forged_bar.source_record_hash, raw_bar_hash=forged_bar.raw_bar_hash)
    forged_execution = replace(result.execution_references[0], raw_bar_hash=forged_bar.raw_bar_hash)
    forged_valuation = replace(result.valuations[0], raw_bar_hash=forged_bar.raw_bar_hash)
    try:
        minute.TushareCnAShareMinuteNormalizationResult(result.request, result.snapshot, (forged_bar, *result.raw_bars[1:]), (forged_trace, *result.traces[1:]), (forged_execution, *result.execution_references[1:]), (forged_valuation, *result.valuations[1:]))
    except ValueError:
        pass
    else:
        raise AssertionError("forged retained source record was accepted")


def test_result_rejects_object_setattr_nested_value_forgery() -> None:
    result = _result().result
    assert result is not None
    bar = result.raw_bars[0]
    object.__setattr__(bar, "bucket", minute._bucket(minute._expected_labels("20240102")[2]))
    object.__setattr__(bar, "available_time", bar.bucket.interval_end_exclusive)
    object.__setattr__(bar, "open_price", Price(10000, Scale(3), str(bar.instrument_id), "CNY"))
    try:
        minute.TushareCnAShareMinuteNormalizationResult(result.request, result.snapshot, result.raw_bars, result.traces, result.execution_references, result.valuations)
    except ValueError:
        pass
    else:
        raise AssertionError("object.__setattr__ nested forgery was accepted")
