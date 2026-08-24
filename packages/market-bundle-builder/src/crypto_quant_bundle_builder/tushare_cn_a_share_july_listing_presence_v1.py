from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from crypto_quant_domain import InstrumentCatalog, InstrumentId, UtcInstant, VenueId, canonical_bytes, canonical_sha256

from .source_snapshots import SourceSnapshot, verify_source_snapshot
from .tushare_cn_a_share_listing_source_bounded_v2 import _catalog as _accepted_catalog

_SCHEMA_VERSION = 1
_PROVIDER_KEY = "tushare.pro"
_PROXY_KEY = "xiaodefa.approved-tushare-proxy.v1"
_ENDPOINTS = ("https://fast.xiaodefa.cn", "https://tt.xiaodefa.cn")
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_TS_CODE = "000001.SZ"
_NAME = "平安银行"
_LIST_DATE = "19910403"
_DATES = (
    "20260706", "20260707", "20260708", "20260709", "20260710",
    "20260713", "20260714", "20260715", "20260716", "20260717",
    "20260720", "20260721", "20260722", "20260723", "20260724",
    "20260727", "20260728", "20260729", "20260730",
)
_MEMBER_KEYS = tuple(f"response/bak-basic/{date}.json" for date in _DATES)
_FIELDS = ("trade_date", "ts_code", "name", "list_date")
_REQUEST = {
    "type": "tushare_july_listing_presence_request_v1",
    "schema_version": 1,
    "ts_code": _TS_CODE,
    "trade_dates": list(_DATES),
}
_REQUEST_SCOPE_HASH = canonical_sha256(_REQUEST)
_SOURCE_KEY = "tushare.pro.via.xiaodefa.approved-proxy.bak_basic.000001.sz.20260706.20260730"
_G12I_FILE_HASH = "sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6"
_G12I_REPORT_HASH = "sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029"
_LISTING_FILE_HASH = "sha256:24122b0a68c87f7bdc5723640724733a2d1f25a7c1b62b0f02eb17bdad2d0205"
_LISTING_REPORT_HASH = "sha256:6d120c94b8d08fa00389d91894bc17d18ad4a6e0c1f9c42b859e7f1e26cc41c8"
_CATALOG_HASH = "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
_LIMITATIONS = (
    "authoritative_absence_unavailable",
    "historical_listing_lifecycle_unavailable",
    "listing_between_observed_dates_unavailable",
    "post_run_observation_not_causal_execution_input",
    "provider_completeness_unknown",
    "provider_revision_finality_unknown",
    "single_instrument_exact_date_set",
    "survivorship_safety_unavailable",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RECEIPT_KEYS = {
    "absence_authority", "acquired_at_epoch_nanoseconds",
    "corporate_action_lifecycle_qualified", "decision_grade_eligible",
    "deployment_authorized", "historical_listing_lifecycle_qualified",
    "provider_completeness_qualified", "provider_key", "provider_requests",
    "provider_revision_id", "request", "returned_row_count",
    "revision_closure_complete", "schema_version", "snapshot",
    "transport_endpoint", "transport_proxy_key", "type",
}
_REQUEST_KEYS = {
    "api_name", "attempts", "auth_mode", "declared_sha256", "fields",
    "member_key", "params", "provider_revision_id", "response_byte_count",
    "response_sha256", "returned_row_count",
}
_Row = tuple[str, str, str, str]


def _digest(source: bytes) -> str:
    return "sha256:" + hashlib.sha256(source).hexdigest()


def _hash(value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError("value must be canonical sha256")
    return value


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_number(value: str) -> object:
    raise ValueError(f"unsupported JSON number: {value}")


def _deep_exact(value: object) -> bool:
    if value is None or type(value) in (str, int, bool):
        return True
    if type(value) is list:
        return all(_deep_exact(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _deep_exact(item) for key, item in value.items())
    return False


def _decode(source: bytes, *, trailing_newline: bool) -> dict[str, Any]:
    value = json.loads(
        source,
        object_pairs_hook=_pairs,
        parse_float=_reject_number,
        parse_constant=_reject_number,
    )
    if type(value) is not dict or not _deep_exact(value):
        raise ValueError("canonical JSON must be one exact object")
    if source != canonical_bytes(value) + (b"\n" if trailing_newline else b""):
        raise ValueError("source bytes are not canonical")
    return value


def _semantic_hash(value: dict[str, Any], key: str) -> str:
    body = dict(value)
    claimed = _hash(body.pop(key, None))
    if canonical_sha256(body) != claimed:
        raise ValueError("semantic hash mismatch")
    return claimed


def _source_row_hash(row: _Row) -> str:
    return canonical_sha256({"dataset": "bak_basic", "row": row})


class _FailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    EVIDENCE_INVALID = "evidence_invalid"
    UPSTREAM_IDENTITY_MISMATCH = "upstream_identity_mismatch"
    REQUEST_SCOPE_MISMATCH = "request_scope_mismatch"
    RESPONSE_SCHEMA_MISMATCH = "response_schema_mismatch"
    RESPONSE_PAGE_INCOMPLETE = "response_page_incomplete"
    SOURCE_OBSERVATION_CONFLICT = "source_observation_conflict"
    REPORT_BINDING_MISMATCH = "report_binding_mismatch"


@dataclass(frozen=True, slots=True)
class _Failure:
    code: _FailureCode
    member_key: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not _FailureCode:
            raise TypeError("code must be exact failure code")
        if self.member_key is not None and self.member_key not in _MEMBER_KEYS:
            raise ValueError("member_key must be declared")

    def to_canonical_dict(self) -> dict[str, object]:
        body = {
            "type": "tushare_cn_a_share_july_listing_presence_failure_v1",
            "schema_version": 1,
            "code": self.code.value,
            "member_key": self.member_key,
        }
        return {**body, "failure_hash": canonical_sha256(body)}


@dataclass(frozen=True, slots=True)
class _Response:
    rows: tuple[_Row, ...]
    has_more: bool
    count: int


@dataclass(frozen=True, slots=True)
class TushareCnAShareJulyListingPresenceReportV1:
    provider_key: str
    transport_proxy_key: str
    instrument_id: InstrumentId
    trade_dates: tuple[str, ...]
    request_scope_hash: str
    acquisition_receipt_sha256: str
    snapshot_id: str
    snapshot_content_tree_hash: str
    provenance_hash: str
    member_keys: tuple[str, ...]
    member_content_hashes: tuple[str, ...]
    member_acquired_at_epoch_nanoseconds: tuple[int, ...]
    g12i_canonical_file_hash: str
    g12i_report_hash: str
    listing_canonical_file_hash: str
    listing_report_hash: str
    instrument_catalog_hash: str
    source_rows: tuple[_Row, ...]
    source_record_hashes: tuple[str, ...]
    observed_at: UtcInstant
    supersedes_report_hash: None
    limitations: tuple[str, ...]
    revision_closure_complete: bool
    provider_completeness_qualified: bool
    absence_authority: bool
    historical_listing_lifecycle_qualified: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self) is not TushareCnAShareJulyListingPresenceReportV1:
            raise TypeError("report must be exact July listing report v1")
        if (
            self.provider_key != _PROVIDER_KEY
            or self.transport_proxy_key != _PROXY_KEY
            or type(self.instrument_id) is not InstrumentId
            or self.instrument_id != _INSTRUMENT
            or self.trade_dates != _DATES
            or self.request_scope_hash != _REQUEST_SCOPE_HASH
            or self.member_keys != _MEMBER_KEYS
            or self.g12i_canonical_file_hash != _G12I_FILE_HASH
            or self.g12i_report_hash != _G12I_REPORT_HASH
            or self.listing_canonical_file_hash != _LISTING_FILE_HASH
            or self.listing_report_hash != _LISTING_REPORT_HASH
            or self.instrument_catalog_hash != _CATALOG_HASH
        ):
            raise ValueError("report fixed identity mismatch")
        for value in (
            self.request_scope_hash, self.acquisition_receipt_sha256,
            self.snapshot_id, self.snapshot_content_tree_hash, self.provenance_hash,
            self.g12i_canonical_file_hash, self.g12i_report_hash,
            self.listing_canonical_file_hash, self.listing_report_hash,
            self.instrument_catalog_hash,
        ):
            _hash(value)
        if (
            type(self.member_content_hashes) is not tuple
            or len(self.member_content_hashes) != 19
            or type(self.member_acquired_at_epoch_nanoseconds) is not tuple
            or len(self.member_acquired_at_epoch_nanoseconds) != 19
            or any(type(value) is not int or value < 0 for value in self.member_acquired_at_epoch_nanoseconds)
            or len(set(self.member_acquired_at_epoch_nanoseconds)) != 1
        ):
            raise ValueError("report member binding mismatch")
        tuple(_hash(value) for value in self.member_content_hashes)
        rows = _rows(self.source_rows)
        if rows != tuple((date, _TS_CODE, _NAME, _LIST_DATE) for date in _DATES):
            raise ValueError("report source rows mismatch")
        expected_hashes = tuple(_source_row_hash(row) for row in rows)
        if self.source_record_hashes != expected_hashes:
            raise ValueError("report row hash mismatch")
        if (
            type(self.observed_at) is not UtcInstant
            or self.observed_at.epoch_nanoseconds != self.member_acquired_at_epoch_nanoseconds[0]
            or self.supersedes_report_hash is not None
            or self.limitations != _LIMITATIONS
        ):
            raise ValueError("report time, predecessor, or limitations mismatch")
        flags = (
            self.revision_closure_complete, self.provider_completeness_qualified,
            self.absence_authority, self.historical_listing_lifecycle_qualified,
            self.decision_grade_eligible, self.live_eligible, self.deployment_authorized,
        )
        if any(type(value) is not bool or value for value in flags):
            raise ValueError("report qualification flags must remain false")
        object.__setattr__(self, "report_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_july_listing_presence_report_v1",
            "schema_version": 1,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "report_hash"},
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "report_hash": self.report_hash}

    @classmethod
    def from_canonical_dict(
        cls, value: object
    ) -> TushareCnAShareJulyListingPresenceReportV1:
        if type(value) is not dict:
            raise TypeError("report canonical value must be exact dict")
        body = cast(dict[str, object], value)
        if set(body) != {"type", "schema_version", *cls.__dataclass_fields__.keys()}:
            raise ValueError("report canonical keys mismatch")
        if (
            body["type"] != "tushare_cn_a_share_july_listing_presence_report_v1"
            or type(body["schema_version"]) is not int
            or body["schema_version"] != 1
        ):
            raise ValueError("report canonical schema mismatch")

        def text(name: str) -> str:
            item = body[name]
            if type(item) is not str:
                raise ValueError(f"report canonical {name} mismatch")
            return item

        def boolean(name: str) -> bool:
            item = body[name]
            if type(item) is not bool:
                raise ValueError(f"report canonical {name} mismatch")
            return item

        def strings(name: str) -> tuple[str, ...]:
            item = body[name]
            if type(item) is not list or any(type(child) is not str for child in item):
                raise ValueError(f"report canonical {name} mismatch")
            return tuple(cast(list[str], item))

        def integers(name: str) -> tuple[int, ...]:
            item = body[name]
            if type(item) is not list or any(type(child) is not int for child in item):
                raise ValueError(f"report canonical {name} mismatch")
            return tuple(cast(list[int], item))

        instrument = body["instrument_id"]
        observed = body["observed_at"]
        source_rows = body["source_rows"]
        if (
            type(instrument) is not dict
            or instrument
            != {"type": "instrument_id", "venue": "xshe", "stable_key": "000001"}
            or type(observed) is not dict
            or set(observed) != {"type", "epoch_nanoseconds"}
            or observed["type"] != "utc_instant"
            or type(observed["epoch_nanoseconds"]) is not int
            or type(source_rows) is not list
        ):
            raise ValueError("report canonical nested identity mismatch")
        rows: list[_Row] = []
        for row in source_rows:
            if type(row) is not list or len(row) != 4 or any(type(item) is not str for item in row):
                raise ValueError("report canonical source row mismatch")
            rows.append(cast(_Row, tuple(row)))
        target = body["supersedes_report_hash"]
        if target is not None:
            raise ValueError("report canonical predecessor mismatch")
        report_hash = text("report_hash")
        report = cls(
            provider_key=text("provider_key"),
            transport_proxy_key=text("transport_proxy_key"),
            instrument_id=_INSTRUMENT,
            trade_dates=strings("trade_dates"),
            request_scope_hash=text("request_scope_hash"),
            acquisition_receipt_sha256=text("acquisition_receipt_sha256"),
            snapshot_id=text("snapshot_id"),
            snapshot_content_tree_hash=text("snapshot_content_tree_hash"),
            provenance_hash=text("provenance_hash"),
            member_keys=strings("member_keys"),
            member_content_hashes=strings("member_content_hashes"),
            member_acquired_at_epoch_nanoseconds=integers(
                "member_acquired_at_epoch_nanoseconds"
            ),
            g12i_canonical_file_hash=text("g12i_canonical_file_hash"),
            g12i_report_hash=text("g12i_report_hash"),
            listing_canonical_file_hash=text("listing_canonical_file_hash"),
            listing_report_hash=text("listing_report_hash"),
            instrument_catalog_hash=text("instrument_catalog_hash"),
            source_rows=tuple(rows),
            source_record_hashes=strings("source_record_hashes"),
            observed_at=UtcInstant(cast(int, observed["epoch_nanoseconds"])),
            supersedes_report_hash=None,
            limitations=strings("limitations"),
            revision_closure_complete=boolean("revision_closure_complete"),
            provider_completeness_qualified=boolean("provider_completeness_qualified"),
            absence_authority=boolean("absence_authority"),
            historical_listing_lifecycle_qualified=boolean(
                "historical_listing_lifecycle_qualified"
            ),
            decision_grade_eligible=boolean("decision_grade_eligible"),
            live_eligible=boolean("live_eligible"),
            deployment_authorized=boolean("deployment_authorized"),
        )
        if report_hash != report.report_hash:
            raise ValueError("report hash mismatch")
        if canonical_bytes(body) != canonical_bytes(report.to_canonical_dict()):
            raise ValueError("report canonical reconstruction mismatch")
        return report


def _reconstruct_report(
    value: object,
) -> TushareCnAShareJulyListingPresenceReportV1 | None:
    if type(value) is not TushareCnAShareJulyListingPresenceReportV1:
        return None
    try:
        parsed = json.loads(canonical_bytes(value.to_canonical_dict()))
        return TushareCnAShareJulyListingPresenceReportV1.from_canonical_dict(parsed)
    except (AttributeError, TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class TushareCnAShareJulyListingPresenceOutcomeV1:
    report: TushareCnAShareJulyListingPresenceReportV1 | None
    failure: _Failure | None

    def __post_init__(self) -> None:
        if type(self) is not TushareCnAShareJulyListingPresenceOutcomeV1:
            raise TypeError("outcome must be exact July listing outcome v1")
        if (self.report is None) == (self.failure is None):
            raise ValueError("outcome must carry exactly one value")
        if self.report is not None:
            trusted = _reconstruct_report(self.report)
            if trusted is None:
                raise TypeError("report must be exact and reconstructable")
            object.__setattr__(self, "report", trusted)
        if self.failure is not None and type(self.failure) is not _Failure:
            raise TypeError("failure must be exact")


def _failed(code: _FailureCode, member_key: str | None = None) -> TushareCnAShareJulyListingPresenceOutcomeV1:
    return TushareCnAShareJulyListingPresenceOutcomeV1(None, _Failure(code, member_key))


def _rows(value: object) -> tuple[_Row, ...]:
    if type(value) is not tuple:
        raise TypeError("rows must be tuple")
    result: list[_Row] = []
    for row in value:
        if type(row) is not tuple or len(row) != 4 or any(type(item) is not str for item in row):
            raise ValueError("row must be exact four-string tuple")
        result.append(cast(_Row, row))
    return tuple(result)


def _evidence(receipt_bytes: bytes, snapshot: SourceSnapshot) -> tuple[dict[str, Any], SourceSnapshot] | None:
    try:
        receipt = _decode(receipt_bytes, trailing_newline=True)
        if (
            set(receipt) != _RECEIPT_KEYS
            or receipt["type"] != "tushare_july_listing_presence_acquisition_receipt_v1"
            or type(receipt["schema_version"]) is not int
            or receipt["schema_version"] != 1
            or type(receipt["provider_requests"]) is not list
            or len(receipt["provider_requests"]) != 19
            or type(receipt["snapshot"]) is not dict
            or type(receipt["acquired_at_epoch_nanoseconds"]) is not int
            or type(receipt["returned_row_count"]) is not int
            or receipt["returned_row_count"] != 19
        ):
            return None
        verified = verify_source_snapshot(snapshot)
        if verified.snapshot is None:
            return None
        trusted = verified.snapshot
        if canonical_bytes(receipt["snapshot"]) != canonical_bytes(trusted.to_canonical_dict()):
            return None
        by_key = {member.member_key: member for member in trusted.members}
        if tuple(by_key) != _MEMBER_KEYS:
            return None
        for request_value in receipt["provider_requests"]:
            if type(request_value) is not dict or set(request_value) != _REQUEST_KEYS:
                return None
            request = cast(dict[str, Any], request_value)
            key = request["member_key"]
            if type(key) is not str or key not in by_key:
                return None
            member = by_key[key]
            raw = trusted.member_bytes(key)
            if (
                type(request["response_byte_count"]) is not int
                or request["response_byte_count"] != len(raw)
                or request["response_byte_count"] != member.byte_count
                or request["response_sha256"] != member.content_hash
                or member.content_hash != _digest(raw)
                or member.acquired_at_epoch_nanoseconds != receipt["acquired_at_epoch_nanoseconds"]
                or member.mode != "0644"
                or member.declared_sha256 is not None
                or type(request["returned_row_count"]) is not int
                or request["returned_row_count"] != 1
            ):
                return None
        return receipt, trusted
    except Exception:  # noqa: BLE001 -- trust-boundary failures are redacted.
        return None


def _upstream(g12i_bytes: bytes, listing_bytes: bytes, catalog: InstrumentCatalog) -> bool:
    try:
        g12i = _decode(g12i_bytes, trailing_newline=True)
        listing = _decode(listing_bytes, trailing_newline=False)
        return (
            _digest(g12i_bytes) == _G12I_FILE_HASH
            and _semantic_hash(g12i, "report_hash") == _G12I_REPORT_HASH
            and g12i.get("type") == "tushare_cn_a_share_daily_source_bounded_observation_report"
            and g12i.get("schema_version") == 2
            and tuple(g12i.get("published_provider_dates", ())) == _DATES
            and _digest(listing_bytes) == _LISTING_FILE_HASH
            and _semantic_hash(listing, "report_hash") == _LISTING_REPORT_HASH
            and listing.get("type") == "tushare_cn_a_share_listing_source_bounded_observation_report_v2"
            and listing.get("schema_version") == 2
            and listing.get("instrument_catalog_hash") == _CATALOG_HASH
            and listing.get("stock_basic_rows") == [[_TS_CODE, "000001", _NAME, "主板", "SZSE", "L", _LIST_DATE, None]]
            and listing.get("bak_basic_rows") == [["20240102", _TS_CODE, _NAME, _LIST_DATE]]
            and _accepted_catalog(catalog) is not None
        )
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return False


def _request_scope(receipt: dict[str, Any], snapshot: SourceSnapshot) -> bool:
    try:
        if (
            receipt["provider_key"] != _PROVIDER_KEY
            or receipt["transport_proxy_key"] != _PROXY_KEY
            or receipt["transport_endpoint"] not in _ENDPOINTS
            or receipt["request"] != _REQUEST
            or receipt["provider_revision_id"] is not None
            or any(
                type(receipt[key]) is not bool or receipt[key]
                for key in (
                    "revision_closure_complete", "provider_completeness_qualified",
                    "absence_authority", "historical_listing_lifecycle_qualified",
                    "corporate_action_lifecycle_qualified", "decision_grade_eligible",
                    "deployment_authorized",
                )
            )
            or snapshot.provenance.vendor_key != _PROVIDER_KEY
            or snapshot.provenance.source_key != _SOURCE_KEY
            or snapshot.provenance.license_ref != "tushare.pro.terms"
            or snapshot.provenance.retention_policy_ref != "backtest.acquisition.candidate"
            or snapshot.decision_grade_eligible
            or snapshot.deployment_authorized
        ):
            return False
        for date, key, request in zip(_DATES, _MEMBER_KEYS, receipt["provider_requests"], strict=True):
            if (
                request["api_name"] != "bak_basic"
                or request["params"] != {"trade_date": date, "ts_code": _TS_CODE}
                or request["fields"] != ",".join(_FIELDS)
                or request["member_key"] != key
                or request["auth_mode"] != "x-api-key"
                or type(request["attempts"]) is not int
                or not 1 <= request["attempts"] <= 3
                or request["declared_sha256"] is not None
                or request["provider_revision_id"] is not None
            ):
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _response(source: bytes) -> _Response:
    value = json.loads(source, object_pairs_hook=_pairs, parse_float=_reject_number, parse_constant=_reject_number)
    if type(value) is not dict or set(value) != {"request_id", "code", "data", "msg", "detail"}:
        raise ValueError("response envelope mismatch")
    data = value["data"]
    if (
        type(value["request_id"]) is not str or not value["request_id"]
        or type(value["code"]) is not int or value["code"] != 0
        or type(value["msg"]) is not str or type(value["detail"]) is not str
        or type(data) is not dict or set(data) != {"fields", "items", "has_more", "count"}
        or data["fields"] != list(_FIELDS) or type(data["items"]) is not list
        or type(data["has_more"]) is not bool or type(data["count"]) is not int
    ):
        raise ValueError("response schema mismatch")
    rows: list[_Row] = []
    for row in data["items"]:
        if type(row) is not list or len(row) != 4 or any(type(item) is not str for item in row):
            raise ValueError("response row mismatch")
        rows.append(cast(_Row, tuple(row)))
    return _Response(tuple(rows), data["has_more"], data["count"])


def observe_tushare_cn_a_share_july_listing_presence_v1(
    *,
    acquisition_receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    g12i_report_bytes: bytes,
    listing_report_bytes: bytes,
    instrument_catalog: InstrumentCatalog,
) -> TushareCnAShareJulyListingPresenceOutcomeV1:
    if (
        type(acquisition_receipt_bytes) is not bytes or type(snapshot) is not SourceSnapshot
        or type(g12i_report_bytes) is not bytes or type(listing_report_bytes) is not bytes
        or type(instrument_catalog) is not InstrumentCatalog
    ):
        return _failed(_FailureCode.INVALID_INPUT)
    evidence = _evidence(acquisition_receipt_bytes, snapshot)
    if evidence is None:
        return _failed(_FailureCode.EVIDENCE_INVALID)
    receipt, trusted_snapshot = evidence
    if not _upstream(g12i_report_bytes, listing_report_bytes, instrument_catalog):
        return _failed(_FailureCode.UPSTREAM_IDENTITY_MISMATCH)
    if not _request_scope(receipt, trusted_snapshot):
        return _failed(_FailureCode.REQUEST_SCOPE_MISMATCH)
    rows: list[_Row] = []
    for date, key in zip(_DATES, _MEMBER_KEYS, strict=True):
        try:
            response = _response(trusted_snapshot.member_bytes(key))
        except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            return _failed(_FailureCode.RESPONSE_SCHEMA_MISMATCH, key)
        if response.has_more or response.count != 0:
            return _failed(_FailureCode.RESPONSE_PAGE_INCOMPLETE, key)
        if response.rows != ((date, _TS_CODE, _NAME, _LIST_DATE),):
            return _failed(_FailureCode.SOURCE_OBSERVATION_CONFLICT, key)
        rows.extend(response.rows)
    try:
        report = TushareCnAShareJulyListingPresenceReportV1(
            provider_key=_PROVIDER_KEY,
            transport_proxy_key=_PROXY_KEY,
            instrument_id=_INSTRUMENT,
            trade_dates=_DATES,
            request_scope_hash=_REQUEST_SCOPE_HASH,
            acquisition_receipt_sha256=_digest(acquisition_receipt_bytes),
            snapshot_id=trusted_snapshot.snapshot_id,
            snapshot_content_tree_hash=trusted_snapshot.content_tree_hash,
            provenance_hash=trusted_snapshot.provenance_hash,
            member_keys=tuple(member.member_key for member in trusted_snapshot.members),
            member_content_hashes=tuple(member.content_hash for member in trusted_snapshot.members),
            member_acquired_at_epoch_nanoseconds=tuple(member.acquired_at_epoch_nanoseconds for member in trusted_snapshot.members),
            g12i_canonical_file_hash=_G12I_FILE_HASH,
            g12i_report_hash=_G12I_REPORT_HASH,
            listing_canonical_file_hash=_LISTING_FILE_HASH,
            listing_report_hash=_LISTING_REPORT_HASH,
            instrument_catalog_hash=_CATALOG_HASH,
            source_rows=tuple(rows),
            source_record_hashes=tuple(_source_row_hash(row) for row in rows),
            observed_at=UtcInstant(max(member.acquired_at_epoch_nanoseconds for member in trusted_snapshot.members)),
            supersedes_report_hash=None,
            limitations=_LIMITATIONS,
            revision_closure_complete=False,
            provider_completeness_qualified=False,
            absence_authority=False,
            historical_listing_lifecycle_qualified=False,
            decision_grade_eligible=False,
            live_eligible=False,
            deployment_authorized=False,
        )
        trusted_report = _reconstruct_report(report)
        if trusted_report is None:
            raise ValueError("report canonical replay mismatch")
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failed(_FailureCode.REPORT_BINDING_MISMATCH)
    return TushareCnAShareJulyListingPresenceOutcomeV1(trusted_report, None)
