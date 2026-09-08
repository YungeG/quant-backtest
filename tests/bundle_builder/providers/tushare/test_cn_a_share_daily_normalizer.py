from __future__ import annotations

import json
from dataclasses import fields, is_dataclass, replace
from datetime import date
from importlib import import_module
from inspect import signature
from pathlib import Path
from typing import Any

import crypto_quant_bundle_builder
import pytest
from crypto_quant_bundle_builder import (
    BarBucket,
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

module = import_module("crypto_quant_bundle_builder.tushare_cn_a_share_daily")
ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1"
EVENT_TIME = (
    ROOT
    / "fixtures/market_data/providers/tushare/cn-a-share-trade-calendar-v1"
    / "daily-event-time.expected.json"
)
DAILY = FIXTURE / "daily.json"
LISTING = FIXTURE / "stock-basic.json"
EVIDENCE = json.loads((FIXTURE / "evidence.expected.json").read_text())
EVENT = json.loads(EVENT_TIME.read_text())
ACQUIRED_AT = 1_786_943_026_685_846_805
INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")

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


def _bucket(*, end: int | None = None) -> BarBucket:
    expected = EVENT["bucket"]
    spans = tuple(
        (
            UtcInstant(value["start"]["epoch_nanoseconds"]),
            UtcInstant(value["end_exclusive"]["epoch_nanoseconds"]),
        )
        for value in expected["included_spans"]
    )
    if end is not None:
        spans = (*spans[:-1], (spans[-1][0], UtcInstant(end)))
    return BarBucket(
        SessionId("CN.XSHE", "2024-01-02.regular"),
        TradingDate("CN.XSHE", date(2024, 1, 2)),
        spans,
        spans[0][0],
        spans[-1][1],
    )


def _snapshot(
    daily_bytes: bytes | None = None,
    *,
    acquired_at: int = ACQUIRED_AT,
    include_daily: bool = True,
) -> SourceSnapshot:
    members = []
    if include_daily:
        members.append(
            RawSourceMember(
                "response/daily.json",
                DAILY.read_bytes() if daily_bytes is None else daily_bytes,
                "0644",
                acquired_at,
                None,
            )
        )
    members.append(
        RawSourceMember(
            "response/stock-basic.json",
            LISTING.read_bytes(),
            "0644",
            acquired_at,
            None,
        )
    )
    outcome = freeze_source_snapshot(
        members=tuple(members),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.daily_listing.000001.sz.20240102",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    )
    assert outcome.failure is None and outcome.snapshot is not None
    return outcome.snapshot


def _request(
    snapshot: SourceSnapshot,
    *,
    bucket: BarBucket | None = None,
    member_hash: str | None = None,
) -> Any:
    member = next(
        (
            value
            for value in snapshot.members
            if value.member_key == "response/daily.json"
        ),
        None,
    )
    return module.TushareCnAShareDailyNormalizationRequest(
        1,
        snapshot.snapshot_id,
        snapshot.provenance_hash,
        "response/daily.json",
        member_hash or (member.content_hash if member is not None else "sha256:" + "0" * 64),
        INSTRUMENT,
        "20240102",
        bucket or _bucket(),
    )


def _normalize(snapshot: SourceSnapshot, request: object | None = None):
    return module.normalize_tushare_cn_a_share_daily_v1(
        snapshot,
        _request(snapshot) if request is None else request,
    )


def _source(
    *,
    code: str = "0",
    msg: str = "",
    has_more: str = "false",
    count: str = "0",
    fields: tuple[str, ...] = (
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "change",
        "pct_chg",
        "vol",
        "amount",
    ),
    row: tuple[str, ...] = (
        '"000001.SZ"',
        '"20240102"',
        "9.39",
        "9.42",
        "9.21",
        "9.21",
        "9.39",
        "-0.18",
        "-1.9169",
        "1158366.45",
        "1075742.252",
    ),
    extra_top: str = "",
    extra_data: str = "",
) -> bytes:
    field_wire = ",".join(json.dumps(value) for value in fields)
    row_wire = ",".join(row)
    return (
        "{"
        '"request_id":"request-1",'
        f'"code":{code},'
        '"data":{'
        f'"fields":[{field_wire}],'
        f'"items":[[{row_wire}]],'
        f'"has_more":{has_more},"count":{count}{extra_data}'
        "},"
        f'"msg":{json.dumps(msg)},"detail":"..."{extra_top}'
        "}"
    ).encode()


def _failure(source: bytes, code: object, *, bucket: BarBucket | None = None):
    snapshot = _snapshot(source)
    outcome = _normalize(snapshot, _request(snapshot, bucket=bucket))
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is code
    return outcome.failure


def test_tushare_daily_contract_is_internal_and_exact() -> None:
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
        "provider_ts_code",
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
    assert tuple(value.name for value in fields(module.TushareCnAShareDailySourceTrace)) == (
        "snapshot_id", "provenance_hash", "source_key", "member_key",
        "member_content_hash", "record_index", "source_record_hash", "raw_bar_hash",
        "revision_id", "supersedes_revision_id", "revision_closure_complete",
    )
    assert tuple(value.name for value in fields(module.TushareCnAShareDailyExecutionReference)) == (
        "raw_bar_hash", "price_purpose", "instrument_id", "bucket", "available_time",
        "open_price", "high_price", "low_price", "close_price", "volume", "amount",
    )
    assert tuple(value.name for value in fields(module.TushareCnAShareDailyValuation)) == (
        "raw_bar_hash", "price_purpose", "instrument_id", "valuation_at",
        "available_time", "close_price",
    )
    assert tuple(value.name for value in fields(module.TushareCnAShareDailyNormalizationResult)) == (
        "request", "snapshot", "raw_bar", "trace", "execution_reference", "valuation",
    )
    assert tuple(value.name for value in fields(module.TushareCnAShareDailyNormalizationOutcome)) == (
        "result", "failure",
    )
    assert tuple(module.TushareCnAShareDailyNormalizationFailureCode) == tuple(
        module.TushareCnAShareDailyNormalizationFailureCode[name]
        for name in (
            "INVALID_REQUEST", "SNAPSHOT_INVALID", "SNAPSHOT_BINDING_MISMATCH",
            "SOURCE_MEMBER_MISSING", "SOURCE_MEMBER_BINDING_MISMATCH",
            "SOURCE_JSON_INVALID", "SOURCE_SCHEMA_MISMATCH", "SOURCE_RECORD_MISMATCH",
            "DECIMAL_MAPPING_INVALID", "BAR_INVARIANT_VIOLATION",
            "BUCKET_BINDING_MISMATCH", "AVAILABILITY_INVALID",
        )
    )
    assert tuple(signature(module.normalize_tushare_cn_a_share_daily_v1).parameters) == (
        "snapshot", "request",
    )
    assert tuple(signature(module.project_execution_reference).parameters) == ("raw_bar",)
    assert tuple(signature(module.project_valuation).parameters) == ("raw_bar",)
    assert all(
        is_dataclass(getattr(module, name))
        for name in _SYMBOLS[:9]
        if name != "TushareCnAShareDailyNormalizationFailureCode"
    )


def test_real_daily_source_normalizes_exact_values_hashes_and_purposes() -> None:
    snapshot = _snapshot()
    assert snapshot.to_canonical_dict() == EVIDENCE["snapshot"]

    outcome = _normalize(snapshot)

    assert outcome.failure is None and outcome.result is not None
    result = outcome.result
    raw = result.raw_bar
    assert raw.provider_ts_code == "000001.SZ"
    assert raw.provider_trade_date == "20240102"
    assert raw.bucket.bucket_hash == EVENT["bucket"]["bucket_hash"]
    assert raw.available_time == UtcInstant(ACQUIRED_AT)
    assert (
        raw.open_lexeme,
        raw.high_lexeme,
        raw.low_lexeme,
        raw.close_lexeme,
        raw.pre_close_lexeme,
        raw.change_lexeme,
        raw.pct_change_lexeme,
        raw.volume_lots_lexeme,
        raw.amount_thousand_cny_lexeme,
    ) == (
        "9.39",
        "9.42",
        "9.21",
        "9.21",
        "9.39",
        "-0.18",
        "-1.9169",
        "1158366.45",
        "1075742.252",
    )
    assert [value.units for value in (raw.open_price, raw.high_price, raw.low_price, raw.close_price, raw.pre_close_price)] == [939, 942, 921, 921, 939]
    assert raw.change_units == -18 and raw.change_scale.places == 2
    assert raw.pct_change.units == -19_169 and raw.pct_change.scale.places == 4
    assert raw.volume.units == 115_836_645 and raw.volume.scale.places == 0
    assert raw.amount.units == 1_075_742_252 and raw.amount.scale.places == 0
    assert raw.limitations == (
        "corporate_actions_unproven",
        "historical_listing_status_unproven",
        "late_historical_availability",
        "provider_revision_closure_unproven",
    )
    assert raw.decision_grade_eligible is False
    assert raw.deployment_authorized is False
    assert not hasattr(raw, "price_purpose")

    trace = result.trace
    assert trace.snapshot_id == snapshot.snapshot_id
    assert trace.provenance_hash == snapshot.provenance_hash
    assert trace.member_content_hash == EVIDENCE["source_hashes"]["daily_response_sha256"]
    assert trace.raw_bar_hash == raw.raw_bar_hash
    assert trace.revision_id == trace.member_content_hash
    assert trace.supersedes_revision_id is None
    assert trace.revision_closure_complete is False

    execution = result.execution_reference
    valuation = result.valuation
    assert execution.price_purpose is PricePurpose.EXECUTION_REFERENCE
    assert valuation.price_purpose is PricePurpose.VALUATION
    assert execution.raw_bar_hash == valuation.raw_bar_hash == raw.raw_bar_hash
    assert execution.available_time == valuation.available_time == raw.available_time
    assert valuation.valuation_at == raw.bucket.interval_end_exclusive
    assert valuation.close_price == raw.close_price
    assert execution.projection_hash != valuation.projection_hash
    assert not hasattr(execution, "settlement_price")
    assert not hasattr(valuation, "adjusted_close")

    # Frozen after the contract formulas are applied to the immutable real source.
    assert raw.source_record_hash == "sha256:9b476b034dc596f296959ac817c7d797814b8e2b75498d5ec4c50da09e3d9f5e"
    assert raw.raw_bar_hash == "sha256:7f0739da15fa80c99ccfdf9a1bdcca617376c20ed7b205c9b1e82b88f2759da0"
    assert trace.trace_hash == "sha256:fc05a2fdc26d734bf6cd526eb22a149d36d5ab4022cfa2c67de0e807a7d6ee96"
    assert execution.projection_hash == "sha256:d283870ccf3042530bdc664aeb4f451b3723300fe3e22a59018b253c67b6bbb4"
    assert valuation.projection_hash == "sha256:2f9cf2a71c0f152e5377be0fdad798ec49cc411814b7cd3a372040286507a630"
    assert result.normalization_hash == "sha256:d01518de64eb48c9b796b83bb72eeb53fe6645d4dbcc00e88311148f23adb16c"

    request = _request(snapshot)
    assert result.request == request
    assert result.snapshot == snapshot
    assert result.request_hash == request.request_hash
    assert b"archive_bytes" not in canonical_bytes(result)
    assert canonical_sha256({key: value for key, value in request.to_canonical_dict().items() if key != "request_hash"}) == request.request_hash
    assert canonical_sha256({key: value for key, value in raw.to_canonical_dict().items() if key != "raw_bar_hash"}) == raw.raw_bar_hash
    assert canonical_sha256({key: value for key, value in trace.to_canonical_dict().items() if key != "trace_hash"}) == trace.trace_hash
    assert canonical_sha256({key: value for key, value in execution.to_canonical_dict().items() if key != "projection_hash"}) == execution.projection_hash
    assert canonical_sha256({key: value for key, value in valuation.to_canonical_dict().items() if key != "projection_hash"}) == valuation.projection_hash
    assert canonical_sha256({key: value for key, value in result.to_canonical_dict().items() if key not in {"normalization_hash", "request_hash"}}) == result.normalization_hash


def test_raw_bar_recomputes_source_hash_and_rejects_forged_domain_values() -> None:
    result = _normalize(_snapshot()).result
    assert result is not None
    raw = result.raw_bar
    with pytest.raises(ValueError, match="source record hash"):
        replace(raw, source_record_hash="sha256:" + "f" * 64)
    with pytest.raises(ValueError, match="prices do not match"):
        replace(raw, open_price=replace(raw.open_price, units=940))

    forged_scale = object.__new__(type(raw.change_scale))
    object.__setattr__(forged_scale, "places", True)
    with pytest.raises(ValueError, match="exact integer units and scale"):
        replace(raw, change_scale=forged_scale)

    forged_price = object.__new__(type(raw.open_price))
    object.__setattr__(forged_price, "units", True)
    object.__setattr__(forged_price, "scale", raw.open_price.scale)
    object.__setattr__(forged_price, "instrument_id", raw.open_price.instrument_id)
    object.__setattr__(forged_price, "quote_currency", raw.open_price.quote_currency)
    with pytest.raises(ValueError, match="prices must bind"):
        replace(raw, open_price=forged_price)


def test_result_revalidates_request_snapshot_trace_availability_and_projections() -> None:
    snapshot = _snapshot()
    result = _normalize(snapshot).result
    assert result is not None

    other_snapshot = _snapshot(acquired_at=ACQUIRED_AT + 1)
    other_request = _request(other_snapshot)
    with pytest.raises(ValueError, match="request does not bind"):
        replace(result, request=other_request)
    with pytest.raises(ValueError, match="request does not bind"):
        replace(result, snapshot=other_snapshot)
    with pytest.raises(ValueError, match="authority reconstruction"):
        replace(result, snapshot=replace(snapshot, archive_bytes=b"broken"))

    with pytest.raises(ValueError, match="trace does not exact-bind"):
        replace(result, trace=replace(result.trace, source_key="other.source"))
    with pytest.raises(ValueError, match="trace member/index"):
        replace(result.trace, record_index=False)

    later_raw = replace(
        result.raw_bar,
        available_time=UtcInstant(result.raw_bar.available_time.epoch_nanoseconds + 1),
    )
    with pytest.raises(ValueError, match="member availability"):
        replace(
            result,
            raw_bar=later_raw,
            execution_reference=module.project_execution_reference(later_raw),
            valuation=module.project_valuation(later_raw),
            trace=replace(result.trace, raw_bar_hash=later_raw.raw_bar_hash),
        )

    forged_execution = replace(
        result.execution_reference,
        close_price=result.raw_bar.open_price,
    )
    with pytest.raises(ValueError, match="exact-match"):
        replace(result, execution_reference=forged_execution)

    forged_raw = object.__new__(type(result.raw_bar))
    for field in fields(result.raw_bar):
        object.__setattr__(forged_raw, field.name, getattr(result.raw_bar, field.name))
    object.__setattr__(forged_raw, "source_record_hash", "sha256:" + "e" * 64)
    with pytest.raises(ValueError, match="authority is invalid"):
        replace(result, raw_bar=forged_raw)


def test_snapshot_qualification_forgery_is_rejected_by_normalizer_and_result() -> None:
    snapshot = _snapshot()
    result = _normalize(snapshot).result
    assert result is not None
    forged = object.__new__(SourceSnapshot)
    for field in fields(snapshot):
        object.__setattr__(forged, field.name, getattr(snapshot, field.name))
    object.__setattr__(forged, "decision_grade_eligible", True)
    object.__setattr__(forged, "deployment_authorized", True)

    outcome = _normalize(forged, _request(snapshot))
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is module.TushareCnAShareDailyNormalizationFailureCode.SNAPSHOT_INVALID
    with pytest.raises(ValueError, match="authority reconstruction"):
        replace(result, snapshot=forged)


def test_projections_require_exact_raw_bar_type() -> None:
    with pytest.raises(TypeError, match="exact"):
        module.project_execution_reference(object())
    with pytest.raises(TypeError, match="exact"):
        module.project_valuation(object())


def test_request_and_snapshot_precedence_and_no_partial_output() -> None:
    snapshot = _snapshot(b"not-json")
    malformed = object()
    outcome = module.normalize_tushare_cn_a_share_daily_v1(snapshot, malformed)
    assert outcome.result is None
    assert outcome.failure.code is module.TushareCnAShareDailyNormalizationFailureCode.INVALID_REQUEST

    valid = _snapshot(b"not-json")
    request = _request(valid)
    corrupted = replace(valid, archive_bytes=b"broken")
    outcome = _normalize(corrupted, request)
    assert outcome.result is None
    assert outcome.failure.code is module.TushareCnAShareDailyNormalizationFailureCode.SNAPSHOT_INVALID


def test_provenance_acquisition_mutation_with_identical_bytes_fails_before_parse() -> None:
    original = _snapshot(b"not-json")
    changed = _snapshot(b"not-json", acquired_at=ACQUIRED_AT + 1)
    assert changed.snapshot_id == original.snapshot_id
    assert changed.provenance_hash != original.provenance_hash

    outcome = _normalize(changed, _request(original))

    assert outcome.result is None
    assert outcome.failure.code is module.TushareCnAShareDailyNormalizationFailureCode.SNAPSHOT_BINDING_MISMATCH


def test_member_missing_and_member_binding_precede_source_parsing() -> None:
    missing = _snapshot(include_daily=False)
    outcome = _normalize(missing, _request(missing))
    assert outcome.failure.code is module.TushareCnAShareDailyNormalizationFailureCode.SOURCE_MEMBER_MISSING

    malformed = _snapshot(b"not-json")
    outcome = _normalize(
        malformed,
        _request(malformed, member_hash="sha256:" + "f" * 64),
    )
    assert outcome.failure.code is module.TushareCnAShareDailyNormalizationFailureCode.SOURCE_MEMBER_BINDING_MISMATCH


@pytest.mark.parametrize(
    "source",
    (
        b"not-json",
        b"\xff",
        b'{"request_id":"x","code":0,"code":0}',
        _source(row=('"000001.SZ"', '"20240102"', "9e0", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "+9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "09.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "9.", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "NaN", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "Infinity", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "-Infinity", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        b"[" * 10_000 + b"0" + b"]" * 10_000,
    ),
)
def test_malformed_numeric_grammar_constants_utf8_and_recursion_are_json_failures(source: bytes) -> None:
    _failure(source, module.TushareCnAShareDailyNormalizationFailureCode.SOURCE_JSON_INVALID)


@pytest.mark.parametrize(
    "source",
    (
        _source(code="1"),
        _source(msg="provider error"),
        _source(has_more="true"),
        _source(count="1"),
        _source(extra_top=',"extra":1'),
        _source(extra_data=',"extra":1'),
        _source(fields=("trade_date", "ts_code")),
        _source(row=('"000001.SZ"', '"20240102"', '"9.39"', "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "true", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source(row=('"000001.SZ"', '"20240102"', "null", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252")),
        _source().replace(b'"request_id":"request-1"', b'"request_id":" request-1"'),
        _source().replace(b'"request_id":"request-1"', b'"request_id":"e\\u0301"'),
        _source().replace(b'"request_id":"request-1"', b'"request_id":"\\ud800"'),
    ),
)
def test_exact_wrapper_schema_and_numeric_token_types_are_enforced(source: bytes) -> None:
    _failure(source, module.TushareCnAShareDailyNormalizationFailureCode.SOURCE_SCHEMA_MISMATCH)


@pytest.mark.parametrize(
    "row",
    (
        ('"000002.SZ"', '"20240102"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252"),
        ('"000001.SZ"', '"20240103"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252"),
    ),
)
def test_source_record_coordinate_mismatch(row: tuple[str, ...]) -> None:
    _failure(_source(row=row), module.TushareCnAShareDailyNormalizationFailureCode.SOURCE_RECORD_MISMATCH)


@pytest.mark.parametrize(
    "row",
    (
        ('"000001.SZ"', '"20240102"', "9.391", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.252"),
        ('"000001.SZ"', '"20240102"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.91691", "1158366.45", "1075742.252"),
        ('"000001.SZ"', '"20240102"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.451", "1075742.252"),
        ('"000001.SZ"', '"20240102"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1158366.45", "1075742.2521"),
    ),
)
def test_decimal_scale_failures(row: tuple[str, ...]) -> None:
    _failure(_source(row=row), module.TushareCnAShareDailyNormalizationFailureCode.DECIMAL_MAPPING_INVALID)


@pytest.mark.parametrize(
    "row",
    (
        ('"000001.SZ"', '"20240102"', "-9.39", "-9.21", "-9.42", "-9.21", "-9.39", "0.18", "1.9169", "1", "1"),
        ('"000001.SZ"', '"20240102"', "9.50", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1", "1"),
        ('"000001.SZ"', '"20240102"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.17", "-1.9169", "1", "1"),
        ('"000001.SZ"', '"20240102"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "-1", "1"),
        ('"000001.SZ"', '"20240102"', "9.39", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1", "-1"),
    ),
)
def test_bar_invariant_failures(row: tuple[str, ...]) -> None:
    _failure(_source(row=row), module.TushareCnAShareDailyNormalizationFailureCode.BAR_INVARIANT_VIOLATION)


def test_bucket_precedes_availability_and_mapping_schema_precede_bucket() -> None:
    wrong_bucket = _bucket(end=EVENT["bucket"]["interval_end_exclusive"]["epoch_nanoseconds"] + 1)
    _failure(b"not-json", module.TushareCnAShareDailyNormalizationFailureCode.SOURCE_JSON_INVALID, bucket=wrong_bucket)
    _failure(_source(row=('"000001.SZ"', '"20240102"', "9.391", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1", "1")), module.TushareCnAShareDailyNormalizationFailureCode.DECIMAL_MAPPING_INVALID, bucket=wrong_bucket)
    _failure(_source(row=('"000001.SZ"', '"20240102"', "9.50", "9.42", "9.21", "9.21", "9.39", "-0.18", "-1.9169", "1", "1")), module.TushareCnAShareDailyNormalizationFailureCode.BAR_INVARIANT_VIOLATION, bucket=wrong_bucket)
    _failure(_source(), module.TushareCnAShareDailyNormalizationFailureCode.BUCKET_BINDING_MISMATCH, bucket=wrong_bucket)


def test_adjacent_mixed_fault_precedence_covers_all_twelve_codes() -> None:
    codes = module.TushareCnAShareDailyNormalizationFailureCode

    corrupted = replace(_snapshot(), archive_bytes=b"broken")
    assert _normalize(corrupted, object()).failure.code is codes.INVALID_REQUEST
    assert _normalize(corrupted, _request(_snapshot())).failure.code is codes.SNAPSHOT_INVALID

    missing = _snapshot(include_daily=False)
    assert _normalize(missing, _request(_snapshot())).failure.code is codes.SNAPSHOT_BINDING_MISMATCH
    assert _normalize(missing, _request(missing)).failure.code is codes.SOURCE_MEMBER_MISSING

    malformed = _snapshot(b"not-json")
    assert _normalize(malformed, _request(malformed, member_hash="sha256:" + "f" * 64)).failure.code is codes.SOURCE_MEMBER_BINDING_MISMATCH
    assert _normalize(malformed).failure.code is codes.SOURCE_JSON_INVALID

    schema_and_record = _snapshot(_source(code="1", row=('"000002.SZ"', '"20240102"', "9.391", "9.42", "9.21", "9.21", "9.39", "-0.17", "-1.9169", "1", "1")))
    assert _normalize(schema_and_record).failure.code is codes.SOURCE_SCHEMA_MISMATCH
    record_and_decimal = _snapshot(_source(row=('"000002.SZ"', '"20240102"', "9.391", "9.42", "9.21", "9.21", "9.39", "-0.17", "-1.9169", "1", "1")))
    assert _normalize(record_and_decimal).failure.code is codes.SOURCE_RECORD_MISMATCH
    decimal_and_bar = _snapshot(_source(row=('"000001.SZ"', '"20240102"', "9.501", "9.42", "9.21", "9.21", "9.39", "-0.17", "-1.9169", "1", "1")))
    assert _normalize(decimal_and_bar).failure.code is codes.DECIMAL_MAPPING_INVALID

    wrong_bucket = _bucket(end=EVENT["bucket"]["interval_end_exclusive"]["epoch_nanoseconds"] + 1)
    bar_and_bucket = _snapshot(_source(row=('"000001.SZ"', '"20240102"', "9.50", "9.42", "9.21", "9.21", "9.39", "-0.17", "-1.9169", "1", "1")))
    assert _normalize(bar_and_bucket, _request(bar_and_bucket, bucket=wrong_bucket)).failure.code is codes.BAR_INVARIANT_VIOLATION
    early = _snapshot(acquired_at=_bucket().interval_end_exclusive.epoch_nanoseconds - 1)
    assert _normalize(early, _request(early, bucket=wrong_bucket)).failure.code is codes.BUCKET_BINDING_MISMATCH
    assert _normalize(early).failure.code is codes.AVAILABILITY_INVALID


def test_availability_must_not_precede_session_finality() -> None:
    snapshot = _snapshot(acquired_at=_bucket().interval_end_exclusive.epoch_nanoseconds - 1)
    outcome = _normalize(snapshot)
    assert outcome.result is None
    assert outcome.failure.code is module.TushareCnAShareDailyNormalizationFailureCode.AVAILABILITY_INVALID


def test_failure_and_result_outcomes_are_xor_and_hashes_are_canonical() -> None:
    failure = _failure(b"not-json", module.TushareCnAShareDailyNormalizationFailureCode.SOURCE_JSON_INVALID)
    assert canonical_sha256({key: value for key, value in failure.to_canonical_dict().items() if key != "failure_hash"}) == failure.failure_hash
    with pytest.raises(ValueError, match="exactly one"):
        module.TushareCnAShareDailyNormalizationOutcome()
    success = _normalize(_snapshot())
    assert success.failure is None and success.result is not None
    with pytest.raises(ValueError, match="exactly one"):
        module.TushareCnAShareDailyNormalizationOutcome(success.result, failure)
