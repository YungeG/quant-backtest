from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from crypto_quant_domain import (InstrumentId, Money, Price, PricePurpose, Quantity,
                                 Scale, SessionId, TradingDate, UtcInstant, VenueId,
                                 canonical_sha256)
from .bar_aggregation import BarBucket
from .source_snapshots import (SourceSnapshot, SourceSnapshotMember,
                               SourceSnapshotProvenance, verify_source_snapshot)

_SCHEMA_VERSION = 1
_MEMBER_KEY = "response/stk-mins.json"
_TS_CODE = "000703.SZ"
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000703")
_FIELDS = ("ts_code", "trade_time", "close", "open", "high", "low", "vol", "amount")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_LIMITATIONS = ("development_only_noncausal_close_availability", "historical_listing_status_unproven", "provider_revision_closure_unproven")
_CST = ZoneInfo("Asia/Shanghai")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class _SourceJsonError(ValueError):
    pass


class _SourceSchemaError(ValueError):
    pass


class _SourceSessionError(ValueError):
    pass


def _hash(value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError("must be canonical sha256")
    return value


@dataclass(frozen=True, slots=True)
class _Numeric:
    lexeme: str


def _number(value: str) -> _Numeric:
    if _NUMBER.fullmatch(value) is None:
        raise ValueError("invalid numeric token")
    return _Numeric(value)


def _constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _parse(source: bytes) -> object:
    try:
        return json.loads(
            source.decode("utf-8"),
            parse_int=_number,
            parse_float=_number,
            parse_constant=_constant,
            object_pairs_hook=_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise _SourceJsonError("source JSON") from error


def _units(value: _Numeric, scale: int) -> int:
    try:
        sign = -1 if value.lexeme.startswith("-") else 1
        whole, dot, fraction = value.lexeme.removeprefix("-").partition(".")
        if len(fraction) > scale:
            raise ValueError("numeric token exceeds frozen scale")
        return sign * (
            int(whole) * 10**scale
            + (int(fraction.ljust(scale, "0")) if dot else 0)
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("numeric token mapping invalid") from error


def _date(value: object) -> datetime:
    if type(value) is not str or re.fullmatch(r"[0-9]{8}", value) is None:
        raise ValueError("provider date must be YYYYMMDD")
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError as error:
        raise ValueError("provider date must be valid") from error


def _expected_labels(provider_date: str) -> tuple[str, ...]:
    day = _date(provider_date).strftime("%Y-%m-%d")
    labels = ["09:30:00"]
    try:
        for start, stop in (("09:35:00", "11:30:00"), ("13:05:00", "15:00:00")):
            current, end = (datetime.strptime(f"{day} {value}", "%Y-%m-%d %H:%M:%S") for value in (start, stop))
            while current <= end:
                labels.append(current.strftime("%H:%M:%S"))
                current += timedelta(minutes=5)
    except ValueError as error:
        raise ValueError("provider session labels invalid") from error
    return tuple(f"{day} {label}" for label in labels)


def _instant(label: str) -> UtcInstant:
    try:
        utc = datetime.strptime(label, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_CST).astimezone(timezone.utc)
    except ValueError as error:
        raise ValueError("provider timestamp invalid") from error
    delta = utc - _EPOCH
    return UtcInstant((delta.days * 86400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1000)


def _bucket(label: str) -> BarBucket:
    end = _instant(label)
    start = UtcInstant(end.epoch_nanoseconds - 300_000_000_000)
    day = label[:10]
    try:
        trading_date = TradingDate("CN.XSHE", date.fromisoformat(day))
    except ValueError as error:
        raise ValueError("provider timestamp date invalid") from error
    return BarBucket(SessionId("CN.XSHE", f"{day}.regular"), trading_date,
                     ((start, end),), start, end)


def _source_record_hash(ts_code: str, trade_time: str, numeric_lexemes: tuple[str, ...]) -> str:
    return canonical_sha256({"type": "tushare_cn_a_share_minute_source_record", "schema_version": 1,
                             "fields": _FIELDS, "text_values": (ts_code, trade_time),
                             "numeric_lexemes": numeric_lexemes})


def _snapshot(value: object) -> SourceSnapshot | None:
    if type(value) is not SourceSnapshot:
        return None
    try:
        rebuilt = SourceSnapshot(value.snapshot_id, value.archive_bytes, value.content_tree_hash,
            tuple(SourceSnapshotMember(m.member_key, m.content_hash, m.byte_count, m.mode,
                  m.acquired_at_epoch_nanoseconds, m.declared_sha256) for m in value.members),
            SourceSnapshotProvenance(value.provenance.vendor_key, value.provenance.source_key,
                  value.provenance.license_ref, value.provenance.retention_policy_ref),
            value.provenance_hash, value.decision_grade_eligible, value.deployment_authorized)
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt if rebuilt == value else None


def _member(snapshot: SourceSnapshot, key: str) -> SourceSnapshotMember | None:
    return next((member for member in snapshot.members if member.member_key == key), None)


def _rows(source: bytes, provider_date: str) -> list[tuple[str, str, tuple[str, ...]]]:
    parsed = _parse(source)
    if type(parsed) is not dict or set(parsed) != {"request_id", "code", "data", "msg", "detail"}:
        raise _SourceSchemaError("source wrapper")
    data = parsed.get("data")
    if not (type(parsed.get("request_id")) is str and parsed.get("code") == _Numeric("0")
            and parsed.get("msg") == "" and type(parsed.get("detail")) is str
            and type(data) is dict and set(data) == {"fields", "items", "has_more", "count"}
            and tuple(data.get("fields", ())) == _FIELDS
            and type(data.get("has_more")) is bool and not data.get("has_more")
            and data.get("count") == _Numeric("0") and type(data.get("items")) is list):
        raise _SourceSchemaError("source fields")
    labels = _expected_labels(provider_date)
    items = data["items"]
    if len(items) != 49:
        raise _SourceSessionError("source session count")
    result: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    expected = set(labels)
    for row in items:
        if type(row) is not list or len(row) != 8:
            raise _SourceSchemaError("source row shape")
        if (
            type(row[0]) is not str
            or type(row[1]) is not str
            or any(type(value) is not _Numeric for value in row[2:])
        ):
            raise _SourceSchemaError("source row types")
        if row[0] != _TS_CODE or row[1] not in expected or row[1] in result:
            raise _SourceSessionError("source session row")
        result[row[1]] = (row[0], row[1], tuple(value.lexeme for value in row[2:]))
    if len(result) != len(labels):
        raise _SourceSessionError("source session row")
    return [result[label] for label in labels]


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteNormalizationRequest:
    schema_version: int; snapshot_id: str; provenance_hash: str; member_key: str; member_content_hash: str; instrument_id: InstrumentId; provider_trade_date: str
    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("request schema_version")
        _hash(self.snapshot_id); _hash(self.provenance_hash); _hash(self.member_content_hash); _date(self.provider_trade_date)
        if self.member_key != _MEMBER_KEY or self.instrument_id != _INSTRUMENT:
            raise ValueError("request scope")
    def _body(self) -> dict[str, object]:
        return {"type": "tushare_cn_a_share_minute_normalization_request", "schema_version": _SCHEMA_VERSION,
                "snapshot_id": self.snapshot_id, "provenance_hash": self.provenance_hash,
                "member_key": self.member_key, "member_content_hash": self.member_content_hash,
                "instrument_id": self.instrument_id, "provider_trade_date": self.provider_trade_date}
    @property
    def request_hash(self) -> str: return canonical_sha256(self._body())
    def to_canonical_dict(self) -> dict[str, object]: return {**self._body(), "request_hash": self.request_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteRawBar:
    instrument_id: InstrumentId; provider_ts_code: str; provider_trade_date: str; provider_trade_time: str; bucket: BarBucket; available_time: UtcInstant
    close_lexeme: str; open_lexeme: str; high_lexeme: str; low_lexeme: str; volume_lexeme: str; amount_lexeme: str
    close_price: Price; open_price: Price; high_price: Price; low_price: Price; volume: Quantity; amount: Money; source_record_hash: str; limitations: tuple[str, ...]; decision_grade_eligible: bool; live_eligible: bool; deployment_authorized: bool
    def __post_init__(self) -> None:
        lexemes = (self.close_lexeme, self.open_lexeme, self.high_lexeme, self.low_lexeme, self.volume_lexeme, self.amount_lexeme)
        if self.instrument_id != _INSTRUMENT or self.provider_ts_code != _TS_CODE or self.provider_trade_time not in _expected_labels(self.provider_trade_date)[1:]: raise ValueError("raw bar coordinate")
        if any(type(value) is not str or _NUMBER.fullmatch(value) is None for value in lexemes): raise ValueError("raw bar lexemes")
        if self.bucket != _bucket(self.provider_trade_time) or self.available_time != self.bucket.interval_end_exclusive: raise ValueError("raw bar bucket")
        prices = (self.close_price, self.open_price, self.high_price, self.low_price)
        if any(type(value) is not Price or value.scale != Scale(2) or value.instrument_id != str(_INSTRUMENT) or value.quote_currency != "CNY" for value in prices) or type(self.volume) is not Quantity or self.volume.scale != Scale(0) or self.volume.instrument_id != str(_INSTRUMENT) or type(self.amount) is not Money or self.amount.scale != Scale(2) or self.amount.currency != "CNY": raise ValueError("raw bar values")
        expected = tuple(_units(_Numeric(value), 2) for value in lexemes[:4])
        if tuple(value.units for value in prices) != expected or self.volume.units != _units(_Numeric(self.volume_lexeme), 0) or self.amount.units != _units(_Numeric(self.amount_lexeme), 2): raise ValueError("raw bar scale")
        if self.source_record_hash != _source_record_hash(self.provider_ts_code, self.provider_trade_time, lexemes): raise ValueError("source record hash")
        if not (0 < self.low_price.units <= self.open_price.units <= self.high_price.units and 0 < self.low_price.units <= self.close_price.units <= self.high_price.units and self.volume.units >= 0 and self.amount.units >= 0): raise ValueError("bar invariant")
        if self.limitations != _LIMITATIONS: raise ValueError("development limitations")
        if any(type(value) is not bool for value in (self.decision_grade_eligible, self.live_eligible, self.deployment_authorized)): raise TypeError("qualification flags must be bool")
        if self.decision_grade_eligible or self.live_eligible or self.deployment_authorized: raise ValueError("development qualification")
    def _body(self) -> dict[str, object]:
        return {"type": "tushare_cn_a_share_minute_raw_bar", "schema_version": _SCHEMA_VERSION, **{name: getattr(self, name) for name in self.__dataclass_fields__}}
    @property
    def raw_bar_hash(self) -> str: return canonical_sha256(self._body())
    def to_canonical_dict(self) -> dict[str, object]: return {**self._body(), "raw_bar_hash": self.raw_bar_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteSourceTrace:
    snapshot_id: str; provenance_hash: str; source_key: str; member_key: str; member_content_hash: str; record_index: int; source_record_hash: str; raw_bar_hash: str; revision_id: str; supersedes_revision_id: str | None; revision_closure_complete: bool
    def __post_init__(self) -> None:
        for value in (self.snapshot_id, self.provenance_hash, self.member_content_hash, self.source_record_hash, self.raw_bar_hash, self.revision_id): _hash(value)
        if self.member_key != _MEMBER_KEY or type(self.record_index) is not int or self.record_index not in range(1, 49) or self.revision_id != self.member_content_hash or self.supersedes_revision_id is not None: raise ValueError("trace binding")
        if type(self.revision_closure_complete) is not bool or self.revision_closure_complete: raise ValueError("trace revision closure")
    def _body(self) -> dict[str, object]:
        return {"type": "tushare_cn_a_share_minute_source_trace", "schema_version": _SCHEMA_VERSION, **{name: getattr(self, name) for name in self.__dataclass_fields__}}
    @property
    def trace_hash(self) -> str: return canonical_sha256(self._body())
    def to_canonical_dict(self) -> dict[str, object]: return {**self._body(), "trace_hash": self.trace_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteExecutionReference:
    raw_bar_hash: str; price_purpose: PricePurpose; instrument_id: InstrumentId; bucket: BarBucket; available_time: UtcInstant; open_price: Price
    def __post_init__(self) -> None:
        _hash(self.raw_bar_hash)
        if self.price_purpose is not PricePurpose.EXECUTION_REFERENCE or self.instrument_id != _INSTRUMENT: raise ValueError("execution binding")
    def _body(self) -> dict[str, object]:
        return {"type": "tushare_cn_a_share_minute_execution_reference", "schema_version": _SCHEMA_VERSION,
                "raw_bar_hash": self.raw_bar_hash, "price_purpose": self.price_purpose.value,
                "instrument_id": self.instrument_id, "bucket": self.bucket,
                "available_time": self.available_time, "open_price": self.open_price}
    @property
    def projection_hash(self) -> str: return canonical_sha256(self._body())
    def to_canonical_dict(self) -> dict[str, object]: return {**self._body(), "projection_hash": self.projection_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteValuation:
    raw_bar_hash: str; price_purpose: PricePurpose; instrument_id: InstrumentId; bucket: BarBucket; valuation_at: UtcInstant; available_time: UtcInstant; close_price: Price
    def __post_init__(self) -> None:
        _hash(self.raw_bar_hash)
        if self.price_purpose is not PricePurpose.VALUATION or self.instrument_id != _INSTRUMENT or self.valuation_at != self.bucket.interval_end_exclusive or self.available_time != self.valuation_at: raise ValueError("valuation binding")
    def _body(self) -> dict[str, object]:
        return {"type": "tushare_cn_a_share_minute_valuation", "schema_version": _SCHEMA_VERSION,
                "raw_bar_hash": self.raw_bar_hash, "price_purpose": self.price_purpose.value,
                "instrument_id": self.instrument_id, "bucket": self.bucket, "valuation_at": self.valuation_at,
                "available_time": self.available_time, "close_price": self.close_price}
    @property
    def projection_hash(self) -> str: return canonical_sha256(self._body())
    def to_canonical_dict(self) -> dict[str, object]: return {**self._body(), "projection_hash": self.projection_hash}


class TushareCnAShareMinuteNormalizationFailureCode(str, Enum):
    INVALID_REQUEST = "invalid_request"; SNAPSHOT_INVALID = "snapshot_invalid"; SNAPSHOT_BINDING_MISMATCH = "snapshot_binding_mismatch"; SOURCE_MEMBER_MISSING = "source_member_missing"; SOURCE_MEMBER_BINDING_MISMATCH = "source_member_binding_mismatch"; SOURCE_JSON_INVALID = "source_json_invalid"; SOURCE_SCHEMA_MISMATCH = "source_schema_mismatch"; SOURCE_SESSION_MISMATCH = "source_session_mismatch"; DECIMAL_MAPPING_INVALID = "decimal_mapping_invalid"; BAR_INVARIANT_VIOLATION = "bar_invariant_violation"


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteNormalizationFailure:
    code: TushareCnAShareMinuteNormalizationFailureCode; member_key: str | None = None


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteNormalizationResult:
    request: TushareCnAShareMinuteNormalizationRequest; snapshot: SourceSnapshot; raw_bars: tuple[TushareCnAShareMinuteRawBar, ...]; traces: tuple[TushareCnAShareMinuteSourceTrace, ...]; execution_references: tuple[TushareCnAShareMinuteExecutionReference, ...]; valuations: tuple[TushareCnAShareMinuteValuation, ...]
    def __post_init__(self) -> None:
        if type(self.request) is not TushareCnAShareMinuteNormalizationRequest or type(self.snapshot) is not SourceSnapshot or any(type(value) is not TushareCnAShareMinuteRawBar for value in self.raw_bars) or any(type(value) is not TushareCnAShareMinuteSourceTrace for value in self.traces) or any(type(value) is not TushareCnAShareMinuteExecutionReference for value in self.execution_references) or any(type(value) is not TushareCnAShareMinuteValuation for value in self.valuations): raise TypeError("result authority")
        try:
            request = TushareCnAShareMinuteNormalizationRequest(**{name: getattr(self.request, name) for name in self.request.__dataclass_fields__})
            raw_bars = tuple(TushareCnAShareMinuteRawBar(**{name: getattr(value, name) for name in value.__dataclass_fields__}) for value in self.raw_bars)
            traces = tuple(TushareCnAShareMinuteSourceTrace(**{name: getattr(value, name) for name in value.__dataclass_fields__}) for value in self.traces)
            executions = tuple(TushareCnAShareMinuteExecutionReference(**{name: getattr(value, name) for name in value.__dataclass_fields__}) for value in self.execution_references)
            valuations = tuple(TushareCnAShareMinuteValuation(**{name: getattr(value, name) for name in value.__dataclass_fields__}) for value in self.valuations)
            snapshot = _snapshot(self.snapshot)
            verified = verify_source_snapshot(snapshot) if snapshot is not None else None
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("result authority invalid") from error
        if request != self.request or raw_bars != self.raw_bars or traces != self.traces or executions != self.execution_references or valuations != self.valuations or snapshot is None or verified.snapshot is None:
            raise ValueError("result authority reconstruction mismatch")
        member = _member(snapshot, request.member_key)
        if member is None or (request.snapshot_id, request.provenance_hash, request.member_content_hash) != (snapshot.snapshot_id, snapshot.provenance_hash, member.content_hash): raise ValueError("result request binding")
        try:
            rows = _rows(snapshot.member_bytes(member.member_key), request.provider_trade_date)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
            raise ValueError("result source authority") from error
        if not (len(raw_bars) == len(traces) == len(executions) == len(valuations) == 48): raise ValueError("result count")
        for index, (row, bar, trace, execution, valuation) in enumerate(zip(rows[1:], raw_bars, traces, executions, valuations), 1):
            ts_code, label, lexemes = row
            if (bar.instrument_id, bar.provider_ts_code, bar.provider_trade_date, bar.provider_trade_time, tuple(getattr(bar, f"{name}_lexeme") for name in ("close", "open", "high", "low", "volume", "amount")), bar.source_record_hash) != (_INSTRUMENT, ts_code, request.provider_trade_date, label, lexemes, _source_record_hash(ts_code, label, lexemes)): raise ValueError("result retained source mismatch")
            if (trace.snapshot_id, trace.provenance_hash, trace.source_key, trace.member_key, trace.member_content_hash, trace.record_index, trace.source_record_hash, trace.raw_bar_hash, trace.revision_id, trace.supersedes_revision_id, trace.revision_closure_complete) != (snapshot.snapshot_id, snapshot.provenance_hash, snapshot.provenance.source_key, member.member_key, member.content_hash, index, bar.source_record_hash, bar.raw_bar_hash, member.content_hash, None, False): raise ValueError("result trace mismatch")
            if execution.raw_bar_hash != bar.raw_bar_hash or execution.instrument_id != bar.instrument_id or execution.bucket != bar.bucket or execution.available_time != bar.available_time or execution.open_price != bar.open_price or valuation.raw_bar_hash != bar.raw_bar_hash or valuation.instrument_id != bar.instrument_id or valuation.bucket != bar.bucket or valuation.valuation_at != bar.bucket.interval_end_exclusive or valuation.available_time != bar.available_time or valuation.close_price != bar.close_price or execution.projection_hash == valuation.projection_hash: raise ValueError("result projection mismatch")
    def _body(self) -> dict[str, object]:
        return {"type": "tushare_cn_a_share_minute_normalization_result", "schema_version": _SCHEMA_VERSION,
                "request": self.request.to_canonical_dict(), "snapshot": self.snapshot.to_canonical_dict(),
                "raw_bars": self.raw_bars, "traces": self.traces,
                "execution_references": self.execution_references, "valuations": self.valuations}
    @property
    def normalization_hash(self) -> str: return canonical_sha256(self._body())
    def to_canonical_dict(self) -> dict[str, object]: return {**self._body(), "request_hash": self.request.request_hash, "normalization_hash": self.normalization_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareMinuteNormalizationOutcome:
    result: TushareCnAShareMinuteNormalizationResult | None = None; failure: TushareCnAShareMinuteNormalizationFailure | None = None
    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None): raise ValueError("outcome requires XOR")


def _fail(code: TushareCnAShareMinuteNormalizationFailureCode, key: str | None = None) -> TushareCnAShareMinuteNormalizationOutcome:
    return TushareCnAShareMinuteNormalizationOutcome(failure=TushareCnAShareMinuteNormalizationFailure(code, key))


def normalize_tushare_cn_a_share_minute_v1(snapshot: SourceSnapshot, request: TushareCnAShareMinuteNormalizationRequest) -> TushareCnAShareMinuteNormalizationOutcome:
    try:
        if type(request) is not TushareCnAShareMinuteNormalizationRequest: raise ValueError()
        request = TushareCnAShareMinuteNormalizationRequest(**{name: getattr(request, name) for name in request.__dataclass_fields__})
    except (AttributeError, TypeError, ValueError): return _fail(TushareCnAShareMinuteNormalizationFailureCode.INVALID_REQUEST)
    snapshot = _snapshot(snapshot)
    try: verified = None if snapshot is None else verify_source_snapshot(snapshot).snapshot
    except (AttributeError, TypeError, ValueError): verified = None
    if verified is None: return _fail(TushareCnAShareMinuteNormalizationFailureCode.SNAPSHOT_INVALID)
    if (snapshot.snapshot_id, snapshot.provenance_hash) != (request.snapshot_id, request.provenance_hash): return _fail(TushareCnAShareMinuteNormalizationFailureCode.SNAPSHOT_BINDING_MISMATCH)
    member = _member(snapshot, request.member_key)
    if member is None: return _fail(TushareCnAShareMinuteNormalizationFailureCode.SOURCE_MEMBER_MISSING, request.member_key)
    if member.content_hash != request.member_content_hash: return _fail(TushareCnAShareMinuteNormalizationFailureCode.SOURCE_MEMBER_BINDING_MISMATCH, request.member_key)
    try: rows = _rows(snapshot.member_bytes(member.member_key), request.provider_trade_date)
    except _SourceJsonError: return _fail(TushareCnAShareMinuteNormalizationFailureCode.SOURCE_JSON_INVALID, request.member_key)
    except _SourceSchemaError: return _fail(TushareCnAShareMinuteNormalizationFailureCode.SOURCE_SCHEMA_MISMATCH, request.member_key)
    except _SourceSessionError: return _fail(TushareCnAShareMinuteNormalizationFailureCode.SOURCE_SESSION_MISMATCH, request.member_key)
    bars=[]; traces=[]; executions=[]; valuations=[]
    for index, (ts_code, label, lexemes) in enumerate(rows[1:], 1):
        try: close, open_, high, low, volume, amount = (_units(_Numeric(value), 2 if position != 4 else 0) for position, value in enumerate(lexemes))
        except ValueError: return _fail(TushareCnAShareMinuteNormalizationFailureCode.DECIMAL_MAPPING_INVALID, request.member_key)
        if not (0 < low <= open_ <= high and 0 < low <= close <= high and volume >= 0 and amount >= 0): return _fail(TushareCnAShareMinuteNormalizationFailureCode.BAR_INVARIANT_VIOLATION, request.member_key)
        bucket = _bucket(label); record_hash = _source_record_hash(ts_code, label, lexemes)
        bar = TushareCnAShareMinuteRawBar(_INSTRUMENT, ts_code, request.provider_trade_date, label, bucket, bucket.interval_end_exclusive, *lexemes, Price(close, Scale(2), str(_INSTRUMENT), "CNY"), Price(open_, Scale(2), str(_INSTRUMENT), "CNY"), Price(high, Scale(2), str(_INSTRUMENT), "CNY"), Price(low, Scale(2), str(_INSTRUMENT), "CNY"), Quantity(volume, Scale(0), str(_INSTRUMENT)), Money(amount, Scale(2), "CNY"), record_hash, _LIMITATIONS, False, False, False)
        trace = TushareCnAShareMinuteSourceTrace(snapshot.snapshot_id, snapshot.provenance_hash, snapshot.provenance.source_key, member.member_key, member.content_hash, index, record_hash, bar.raw_bar_hash, member.content_hash, None, False)
        execution = TushareCnAShareMinuteExecutionReference(bar.raw_bar_hash, PricePurpose.EXECUTION_REFERENCE, bar.instrument_id, bucket, bar.available_time, bar.open_price)
        valuation = TushareCnAShareMinuteValuation(bar.raw_bar_hash, PricePurpose.VALUATION, bar.instrument_id, bucket, bucket.interval_end_exclusive, bar.available_time, bar.close_price)
        bars.append(bar); traces.append(trace); executions.append(execution); valuations.append(valuation)
    return TushareCnAShareMinuteNormalizationOutcome(result=TushareCnAShareMinuteNormalizationResult(request, snapshot, tuple(bars), tuple(traces), tuple(executions), tuple(valuations)))
