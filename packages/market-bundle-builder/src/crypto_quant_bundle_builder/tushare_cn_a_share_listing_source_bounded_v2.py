from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

from .source_snapshots import SourceSnapshot, verify_source_snapshot

_SCHEMA_VERSION = 2
_PROVIDER_KEY = "tushare.pro"
_TRANSPORT_PROXY_KEY = "xiaodefa.approved-tushare-proxy.v1"
_ENDPOINTS = ("https://fast.xiaodefa.cn", "https://tt.xiaodefa.cn")
_DATASETS = ("stock_basic", "bak_basic", "namechange")
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_TS_CODE = "000001.SZ"
_TRADE_DATE = "20240102"
_MEMBER_KEYS = (
    "response/bak-basic.json",
    "response/namechange.json",
    "response/stock-basic.json",
)
_REQUEST_MEMBER_KEYS = (
    "response/stock-basic.json",
    "response/bak-basic.json",
    "response/namechange.json",
)
_FIELDS = {
    "stock_basic": (
        "ts_code",
        "symbol",
        "name",
        "market",
        "exchange",
        "list_status",
        "list_date",
        "delist_date",
    ),
    "bak_basic": ("trade_date", "ts_code", "name", "list_date"),
    "namechange": (
        "ts_code",
        "name",
        "start_date",
        "end_date",
        "ann_date",
        "change_reason",
    ),
}
_PARAMS = {
    "stock_basic": {"list_status": "L", "ts_code": _TS_CODE},
    "bak_basic": {"trade_date": _TRADE_DATE, "ts_code": _TS_CODE},
    "namechange": {"ts_code": _TS_CODE},
}
_REQUEST = {
    "type": "tushare_listing_source_bounded_request_v2",
    "schema_version": 2,
    "ts_code": _TS_CODE,
    "trade_date": _TRADE_DATE,
}
_REQUEST_SCOPE_HASH = canonical_sha256(_REQUEST)
_SOURCE_KEY = (
    "tushare.pro.via.xiaodefa.approved-proxy.listing_presence.000001.sz.20240102"
)
_CATALOG_HASH = "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
_LIMITATIONS = (
    "permanent_provider_checksum_unavailable",
    "future_revision_finality_unknown",
    "provider_correction_lineage_unavailable",
    "provider_completeness_unknown",
    "historical_listing_lifecycle_unavailable",
    "authoritative_absence_unavailable",
    "survivorship_safety_unavailable",
    "corporate_action_lifecycle_closure_unavailable",
    "single_instrument_single_date_scope",
    "approved_proxy_transport_is_not_provider_completeness",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DATE = re.compile(r"[0-9]{8}\Z")
_RECEIPT_KEYS = {
    "absence_authority",
    "acquired_at_epoch_nanoseconds",
    "corporate_action_lifecycle_qualified",
    "current_listing_row_count",
    "decision_grade_eligible",
    "deployment_authorized",
    "historical_list_row_count",
    "historical_listing_lifecycle_qualified",
    "namechange_row_count",
    "provider_completeness_qualified",
    "provider_key",
    "provider_requests",
    "provider_revision_id",
    "request",
    "revision_closure_complete",
    "schema_version",
    "snapshot",
    "target_name_interval_count",
    "transport_endpoint",
    "transport_proxy_key",
    "type",
}
_PROVIDER_REQUEST_KEYS = {
    "api_name",
    "attempts",
    "auth_mode",
    "declared_sha256",
    "fields",
    "member_key",
    "params",
    "provider_revision_id",
    "response_byte_count",
    "response_sha256",
    "returned_row_count",
}
_RESPONSE_KEYS = {"request_id", "code", "data", "msg", "detail"}
_RESPONSE_DATA_KEYS = {"fields", "items", "has_more", "count"}
_FORBIDDEN_CREDENTIAL_MARKERS = (b'"token"', b'"authorization"')

_StockRow = tuple[str, str, str, str, str, str, str, str | None]
_BakRow = tuple[str, str, str, str]
_NameRow = tuple[str, str, str, str | None, str, str]


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _exact_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an exact integer")
    return value


def _date(name: str, value: object) -> str:
    text = _text(name, value)
    if _DATE.fullmatch(text) is None:
        raise ValueError(f"{name} must be YYYYMMDD")
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"{name} must be a real date") from error
    return text


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _json(source: bytes) -> object:
    return json.loads(
        source.decode("utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _instrument(value: object) -> InstrumentId:
    if type(value) is not InstrumentId:
        raise TypeError("instrument_id must be exact InstrumentId")
    return InstrumentId(VenueId(value.venue.value), value.stable_key)


def _instant(value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError("observed_at must be exact UtcInstant")
    return UtcInstant(value.epoch_nanoseconds)


def _source_record_hash(dataset: str, row: tuple[object, ...]) -> str:
    return canonical_sha256({"dataset": dataset, "row": row})


class _FailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    EVIDENCE_INVALID = "evidence_invalid"
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
            raise ValueError("member_key must be a declared response member")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_listing_source_bounded_observation_failure_v2",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "member_key": self.member_key,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class _Response:
    fields: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    has_more: bool
    count: int


@dataclass(frozen=True, slots=True)
class TushareCnAShareListingSourceBoundedObservationReportV2:
    provider_key: str
    transport_proxy_key: str
    datasets: tuple[str, ...]
    instrument_id: InstrumentId
    trade_date: str
    request_scope_hash: str
    acquisition_receipt_sha256: str
    snapshot_id: str
    snapshot_content_tree_hash: str
    provenance_hash: str
    member_keys: tuple[str, ...]
    member_content_hashes: tuple[str, ...]
    member_acquired_at_epoch_nanoseconds: tuple[int, ...]
    instrument_catalog_hash: str
    stock_basic_rows: tuple[_StockRow, ...]
    bak_basic_rows: tuple[_BakRow, ...]
    namechange_rows: tuple[_NameRow, ...]
    source_record_hashes: tuple[str, ...]
    target_name_interval_index: int
    observed_at: UtcInstant
    supersedes_report_hash: str | None
    limitations: tuple[str, ...]
    revision_closure_complete: bool
    provider_completeness_qualified: bool
    absence_authority: bool
    historical_listing_lifecycle_qualified: bool
    corporate_action_lifecycle_qualified: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            self.provider_key != _PROVIDER_KEY
            or self.transport_proxy_key != _TRANSPORT_PROXY_KEY
            or self.datasets != _DATASETS
            or _instrument(self.instrument_id) != _INSTRUMENT
            or _date("trade_date", self.trade_date) != _TRADE_DATE
        ):
            raise ValueError("report provider scope mismatch")
        if _hash("request_scope_hash", self.request_scope_hash) != _REQUEST_SCOPE_HASH:
            raise ValueError("report request scope mismatch")
        for name in (
            "acquisition_receipt_sha256",
            "snapshot_id",
            "snapshot_content_tree_hash",
            "provenance_hash",
            "instrument_catalog_hash",
        ):
            _hash(name, getattr(self, name))
        if self.instrument_catalog_hash != _CATALOG_HASH:
            raise ValueError("report catalog mismatch")
        if (
            type(self.member_keys) is not tuple
            or self.member_keys != _MEMBER_KEYS
            or type(self.member_content_hashes) is not tuple
            or len(self.member_content_hashes) != 3
            or type(self.member_acquired_at_epoch_nanoseconds) is not tuple
            or len(self.member_acquired_at_epoch_nanoseconds) != 3
        ):
            raise ValueError("report member binding mismatch")
        tuple(_hash("member_content_hash", value) for value in self.member_content_hashes)
        acquired = tuple(
            _exact_int("member acquired time", value)
            for value in self.member_acquired_at_epoch_nanoseconds
        )
        if len(set(acquired)) != 1 or _instant(self.observed_at).epoch_nanoseconds != acquired[0]:
            raise ValueError("report observation time mismatch")
        stock, bak, names, target = _validated_observation(
            self.stock_basic_rows,
            self.bak_basic_rows,
            self.namechange_rows,
        )
        if (
            type(self.target_name_interval_index) is not int
            or self.target_name_interval_index != target
        ):
            raise ValueError("report target name interval mismatch")
        expected_hashes = tuple(
            _source_record_hash(dataset, row)
            for dataset, rows in (
                ("stock_basic", stock),
                ("bak_basic", bak),
                ("namechange", names),
            )
            for row in rows
        )
        if (
            type(self.source_record_hashes) is not tuple
            or tuple(_hash("source_record_hash", value) for value in self.source_record_hashes)
            != expected_hashes
        ):
            raise ValueError("report source row hash mismatch")
        if self.supersedes_report_hash is not None:
            _hash("supersedes_report_hash", self.supersedes_report_hash)
        if self.limitations != _LIMITATIONS:
            raise ValueError("report limitations mismatch")
        flags = (
            self.revision_closure_complete,
            self.provider_completeness_qualified,
            self.absence_authority,
            self.historical_listing_lifecycle_qualified,
            self.corporate_action_lifecycle_qualified,
            self.decision_grade_eligible,
            self.live_eligible,
            self.deployment_authorized,
        )
        if any(type(value) is not bool for value in flags) or any(flags):
            raise ValueError("report qualification flags must remain false")
        object.__setattr__(self, "report_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_listing_source_bounded_observation_report_v2",
            "schema_version": _SCHEMA_VERSION,
            "provider_key": self.provider_key,
            "transport_proxy_key": self.transport_proxy_key,
            "datasets": self.datasets,
            "instrument_id": self.instrument_id,
            "trade_date": self.trade_date,
            "request_scope_hash": self.request_scope_hash,
            "acquisition_receipt_sha256": self.acquisition_receipt_sha256,
            "snapshot_id": self.snapshot_id,
            "snapshot_content_tree_hash": self.snapshot_content_tree_hash,
            "provenance_hash": self.provenance_hash,
            "member_keys": self.member_keys,
            "member_content_hashes": self.member_content_hashes,
            "member_acquired_at_epoch_nanoseconds": self.member_acquired_at_epoch_nanoseconds,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "stock_basic_rows": self.stock_basic_rows,
            "bak_basic_rows": self.bak_basic_rows,
            "namechange_rows": self.namechange_rows,
            "source_record_hashes": self.source_record_hashes,
            "target_name_interval_index": self.target_name_interval_index,
            "observed_at": self.observed_at,
            "supersedes_report_hash": self.supersedes_report_hash,
            "limitations": self.limitations,
            "revision_closure_complete": self.revision_closure_complete,
            "provider_completeness_qualified": self.provider_completeness_qualified,
            "absence_authority": self.absence_authority,
            "historical_listing_lifecycle_qualified": self.historical_listing_lifecycle_qualified,
            "corporate_action_lifecycle_qualified": self.corporate_action_lifecycle_qualified,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "report_hash": self.report_hash}

    @classmethod
    def from_canonical_dict(
        cls, value: Mapping[str, object]
    ) -> TushareCnAShareListingSourceBoundedObservationReportV2:
        if type(value) is not dict:
            raise TypeError("report canonical value must be exact dict")
        body = cast(dict[str, object], value)
        if set(body) != {"type", "schema_version", *cls.__dataclass_fields__.keys()}:
            raise ValueError("report canonical keys mismatch")
        if (
            body["type"]
            != "tushare_cn_a_share_listing_source_bounded_observation_report_v2"
            or body["schema_version"] != _SCHEMA_VERSION
        ):
            raise ValueError("report canonical schema mismatch")

        def string(name: str) -> str:
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
        observed_at = body["observed_at"]
        if (
            type(instrument) is not dict
            or set(instrument) != {"type", "venue", "stable_key"}
            or instrument["type"] != "instrument_id"
            or type(instrument["venue"]) is not str
            or type(instrument["stable_key"]) is not str
            or type(observed_at) is not dict
            or set(observed_at) != {"type", "epoch_nanoseconds"}
            or observed_at["type"] != "utc_instant"
            or type(observed_at["epoch_nanoseconds"]) is not int
        ):
            raise ValueError("report canonical nested identity mismatch")

        def rows(name: str, width: int, nullable_index: int | None = None):
            item = body[name]
            if type(item) is not list:
                raise ValueError(f"report canonical {name} mismatch")
            parsed: list[tuple[object, ...]] = []
            for row in item:
                if type(row) is not list or len(row) != width:
                    raise ValueError(f"report canonical {name} mismatch")
                for index, child in enumerate(row):
                    if index == nullable_index and child is None:
                        continue
                    if type(child) is not str:
                        raise ValueError(f"report canonical {name} mismatch")
                parsed.append(tuple(row))
            return tuple(parsed)

        supersedes = body["supersedes_report_hash"]
        target_index = body["target_name_interval_index"]
        if supersedes is not None and type(supersedes) is not str:
            raise ValueError("report canonical supersedes mismatch")
        if type(target_index) is not int:
            raise ValueError("report canonical target index mismatch")
        report_hash = string("report_hash")
        report = cls(
            provider_key=string("provider_key"),
            transport_proxy_key=string("transport_proxy_key"),
            datasets=strings("datasets"),
            instrument_id=InstrumentId(
                VenueId(cast(str, instrument["venue"])),
                cast(str, instrument["stable_key"]),
            ),
            trade_date=string("trade_date"),
            request_scope_hash=string("request_scope_hash"),
            acquisition_receipt_sha256=string("acquisition_receipt_sha256"),
            snapshot_id=string("snapshot_id"),
            snapshot_content_tree_hash=string("snapshot_content_tree_hash"),
            provenance_hash=string("provenance_hash"),
            member_keys=strings("member_keys"),
            member_content_hashes=strings("member_content_hashes"),
            member_acquired_at_epoch_nanoseconds=integers(
                "member_acquired_at_epoch_nanoseconds"
            ),
            instrument_catalog_hash=string("instrument_catalog_hash"),
            stock_basic_rows=cast(tuple[_StockRow, ...], rows("stock_basic_rows", 8, 7)),
            bak_basic_rows=cast(tuple[_BakRow, ...], rows("bak_basic_rows", 4)),
            namechange_rows=cast(tuple[_NameRow, ...], rows("namechange_rows", 6, 3)),
            source_record_hashes=strings("source_record_hashes"),
            target_name_interval_index=target_index,
            observed_at=UtcInstant(cast(int, observed_at["epoch_nanoseconds"])),
            supersedes_report_hash=cast(str | None, supersedes),
            limitations=strings("limitations"),
            revision_closure_complete=boolean("revision_closure_complete"),
            provider_completeness_qualified=boolean("provider_completeness_qualified"),
            absence_authority=boolean("absence_authority"),
            historical_listing_lifecycle_qualified=boolean(
                "historical_listing_lifecycle_qualified"
            ),
            corporate_action_lifecycle_qualified=boolean(
                "corporate_action_lifecycle_qualified"
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


@dataclass(frozen=True, slots=True)
class TushareCnAShareListingSourceBoundedObservationOutcomeV2:
    report: TushareCnAShareListingSourceBoundedObservationReportV2 | None = None
    failure: _Failure | None = None

    def __post_init__(self) -> None:
        if (self.report is None) == (self.failure is None):
            raise ValueError("outcome must carry exactly one report or failure")
        if self.report is not None:
            trusted = _reconstruct_report(self.report)
            if trusted is None:
                raise TypeError("report must be a reconstructable observation report")
            object.__setattr__(self, "report", trusted)
        if self.failure is not None and type(self.failure) is not _Failure:
            raise TypeError("failure must be exact observation failure")


def _failed(
    code: _FailureCode, member_key: str | None = None
) -> TushareCnAShareListingSourceBoundedObservationOutcomeV2:
    return TushareCnAShareListingSourceBoundedObservationOutcomeV2(
        failure=_Failure(code, member_key)
    )


def _reconstruct_report(
    value: object,
) -> TushareCnAShareListingSourceBoundedObservationReportV2 | None:
    if type(value) is not TushareCnAShareListingSourceBoundedObservationReportV2:
        return None
    try:
        parsed = json.loads(canonical_bytes(value.to_canonical_dict()))
        rebuilt = TushareCnAShareListingSourceBoundedObservationReportV2.from_canonical_dict(
            parsed
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt if canonical_bytes(rebuilt) == canonical_bytes(value) else None


def _catalog(value: InstrumentCatalog) -> InstrumentCatalog | None:
    try:
        if (
            type(value) is not InstrumentCatalog
            or type(value.currencies) is not tuple
            or type(value.instruments) is not tuple
            or type(value.symbol_timelines) is not tuple
            or len(value.currencies) != 1
            or len(value.instruments) != 1
            or value.symbol_timelines
        ):
            return None
        currency = value.currencies[0]
        definition = value.instruments[0]
        if (
            type(currency) is not CurrencyId
            or currency.value != "CNY"
            or type(definition) is not InstrumentDefinition
            or _instrument(definition.instrument_id) != _INSTRUMENT
            or type(definition.instrument_type) is not InstrumentType
            or definition.instrument_type is not InstrumentType.EQUITY
            or definition.base_currency is not None
            or type(definition.quote_currency) is not CurrencyId
            or definition.quote_currency.value != "CNY"
            or type(definition.settlement_currency) is not CurrencyId
            or definition.settlement_currency.value != "CNY"
        ):
            return None
        trusted_currency = CurrencyId("CNY")
        trusted = InstrumentCatalog(
            currencies=(trusted_currency,),
            instruments=(
                InstrumentDefinition(
                    _INSTRUMENT,
                    InstrumentType.EQUITY,
                    None,
                    trusted_currency,
                    trusted_currency,
                ),
            ),
            symbol_timelines=(),
        )
        if canonical_bytes(value) != canonical_bytes(trusted) or canonical_sha256(trusted) != _CATALOG_HASH:
            return None
        return trusted
    except Exception:  # noqa: BLE001 -- hostile catalog objects fail closed.
        return None


def _receipt(source: bytes) -> dict[str, object]:
    value = _json(source)
    if type(value) is not dict:
        raise ValueError("receipt must be an object")
    return cast(dict[str, object], value)


def _evidence(
    receipt_bytes: bytes, snapshot: SourceSnapshot
) -> tuple[dict[str, object], SourceSnapshot] | None:
    try:
        receipt = _receipt(receipt_bytes)
        if (
            receipt_bytes != _canonical_json_bytes(receipt)
            or set(receipt) != _RECEIPT_KEYS
            or type(receipt["type"]) is not str
            or receipt["type"]
            != "tushare_listing_source_bounded_acquisition_receipt_v2"
            or type(receipt["schema_version"]) is not int
            or receipt["schema_version"] != 2
            or type(receipt["provider_key"]) is not str
            or type(receipt["transport_proxy_key"]) is not str
            or type(receipt["transport_endpoint"]) is not str
            or type(receipt["request"]) is not dict
            or set(cast(dict[str, object], receipt["request"])) != set(_REQUEST)
            or any(
                type(cast(dict[str, object], receipt["request"])[key])
                is not type(value)
                for key, value in _REQUEST.items()
            )
            or type(receipt["provider_requests"]) is not list
            or type(receipt["snapshot"]) is not dict
            or type(receipt["acquired_at_epoch_nanoseconds"]) is not int
            or receipt["acquired_at_epoch_nanoseconds"] < 0
            or type(receipt["provider_revision_id"]) is not type(None)
            or any(
                type(receipt[key]) is not int or cast(int, receipt[key]) < 0
                for key in (
                    "current_listing_row_count",
                    "historical_list_row_count",
                    "namechange_row_count",
                    "target_name_interval_count",
                )
            )
            or any(
                type(receipt[key]) is not bool
                for key in (
                    "revision_closure_complete",
                    "provider_completeness_qualified",
                    "absence_authority",
                    "historical_listing_lifecycle_qualified",
                    "corporate_action_lifecycle_qualified",
                    "decision_grade_eligible",
                    "deployment_authorized",
                )
            )
            or any(marker in receipt_bytes.lower() for marker in _FORBIDDEN_CREDENTIAL_MARKERS)
        ):
            return None
        requests = cast(list[object], receipt["provider_requests"])
        if len(requests) != 3 or any(
            type(value) is not dict or set(value) != _PROVIDER_REQUEST_KEYS
            for value in requests
        ):
            return None
        for value in requests:
            request = cast(dict[str, object], value)
            params = request["params"]
            if (
                type(request["api_name"]) is not str
                or type(request["attempts"]) is not int
                or type(request["auth_mode"]) is not str
                or request["declared_sha256"] is not None
                or type(request["fields"]) is not str
                or type(request["member_key"]) is not str
                or type(params) is not dict
                or any(type(key) is not str or type(item) is not str for key, item in params.items())
                or request["provider_revision_id"] is not None
                or type(request["response_byte_count"]) is not int
                or cast(int, request["response_byte_count"]) < 0
                or type(request["response_sha256"]) is not str
                or type(request["returned_row_count"]) is not int
                or cast(int, request["returned_row_count"]) < 0
            ):
                return None
        verified = verify_source_snapshot(snapshot)
        if verified.snapshot is None:
            return None
        trusted = verified.snapshot
        if _canonical_json_bytes(receipt["snapshot"]) != _canonical_json_bytes(
            trusted.to_canonical_dict()
        ):
            return None
        by_key = {member.member_key: member for member in trusted.members}
        if tuple(by_key) != _MEMBER_KEYS or len(by_key) != 3:
            return None
        for request_value in requests:
            request = cast(dict[str, object], request_value)
            key = request["member_key"]
            if type(key) is not str or key not in by_key:
                return None
            member = by_key[key]
            raw = trusted.member_bytes(key)
            if (
                type(request["response_sha256"]) is not str
                or request["response_sha256"] != member.content_hash
                or request["response_byte_count"] != member.byte_count
                or request["response_byte_count"] != len(raw)
                or member.content_hash != _digest(raw)
                or member.acquired_at_epoch_nanoseconds
                != receipt["acquired_at_epoch_nanoseconds"]
                or member.mode != "0644"
                or member.declared_sha256 is not None
                or any(marker in raw.lower() for marker in _FORBIDDEN_CREDENTIAL_MARKERS)
            ):
                return None
            try:
                shallow = _json(raw)
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
                shallow = None
            if type(shallow) is dict:
                data = shallow.get("data")
                if type(data) is dict and type(data.get("items")) is list:
                    if request["returned_row_count"] != len(data["items"]):
                        return None
        counts = tuple(
            cast(dict[str, object], value)["returned_row_count"] for value in requests
        )
        if (
            counts
            != (
                receipt["current_listing_row_count"],
                receipt["historical_list_row_count"],
                receipt["namechange_row_count"],
            )
            or receipt["target_name_interval_count"] != 1
        ):
            return None
        return receipt, trusted
    except Exception:  # noqa: BLE001 -- trust-boundary failures are redacted.
        return None


def _request_scope(
    receipt: dict[str, object], snapshot: SourceSnapshot, catalog: InstrumentCatalog
) -> bool:
    try:
        if (
            receipt["provider_key"] != _PROVIDER_KEY
            or receipt["transport_proxy_key"] != _TRANSPORT_PROXY_KEY
            or receipt["transport_endpoint"] not in _ENDPOINTS
            or receipt["provider_revision_id"] is not None
            or receipt["request"] != _REQUEST
            or any(
                receipt[key] is not False
                for key in (
                    "revision_closure_complete",
                    "provider_completeness_qualified",
                    "absence_authority",
                    "historical_listing_lifecycle_qualified",
                    "corporate_action_lifecycle_qualified",
                    "decision_grade_eligible",
                    "deployment_authorized",
                )
            )
            or snapshot.provenance.vendor_key != _PROVIDER_KEY
            or snapshot.provenance.source_key != _SOURCE_KEY
            or snapshot.provenance.license_ref != "tushare.pro.terms"
            or snapshot.provenance.retention_policy_ref
            != "backtest.acquisition.candidate"
            or snapshot.decision_grade_eligible
            or snapshot.deployment_authorized
            or _catalog(catalog) is None
        ):
            return False
        requests = cast(list[dict[str, object]], receipt["provider_requests"])
        for index, api_name in enumerate(_DATASETS):
            request = requests[index]
            if (
                request["api_name"] != api_name
                or request["params"] != _PARAMS[api_name]
                or request["fields"] != ",".join(_FIELDS[api_name])
                or request["member_key"] != _REQUEST_MEMBER_KEYS[index]
                or request["auth_mode"] != "x-api-key"
                or type(request["attempts"]) is not int
                or not 1 <= cast(int, request["attempts"]) <= 3
                or request["declared_sha256"] is not None
                or request["provider_revision_id"] is not None
                or type(request["returned_row_count"]) is not int
                or cast(int, request["returned_row_count"]) < 0
            ):
                return False
        return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _response(source: bytes, expected_fields: tuple[str, ...]) -> _Response:
    value = _json(source)
    if type(value) is not dict or set(value) != _RESPONSE_KEYS:
        raise ValueError("response object mismatch")
    data = value["data"]
    if (
        type(value["request_id"]) is not str
        or not value["request_id"]
        or type(value["code"]) is not int
        or value["code"] != 0
        or type(value["msg"]) is not str
        or type(value["detail"]) is not str
        or type(data) is not dict
        or set(data) != _RESPONSE_DATA_KEYS
        or type(data["fields"]) is not list
        or tuple(data["fields"]) != expected_fields
        or any(type(field) is not str for field in data["fields"])
        or type(data["items"]) is not list
        or any(type(row) is not list for row in data["items"])
        or type(data["has_more"]) is not bool
        or type(data["count"]) is not int
    ):
        raise ValueError("response schema mismatch")
    return _Response(
        expected_fields,
        tuple(tuple(row) for row in data["items"]),
        cast(bool, data["has_more"]),
        cast(int, data["count"]),
    )


def _responses(
    receipt: dict[str, object], snapshot: SourceSnapshot
) -> tuple[dict[str, _Response], _Failure | None]:
    parsed: dict[str, _Response] = {}
    requests = cast(list[dict[str, object]], receipt["provider_requests"])
    for request in requests:
        api_name = cast(str, request["api_name"])
        key = cast(str, request["member_key"])
        try:
            response = _response(snapshot.member_bytes(key), _FIELDS[api_name])
            {
                "stock_basic": _stock_rows,
                "bak_basic": _bak_rows,
                "namechange": _name_rows,
            }[api_name](response.rows)
            parsed[api_name] = response
        except (
            AttributeError,
            KeyError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
            TypeError,
            ValueError,
        ):
            return {}, _Failure(_FailureCode.RESPONSE_SCHEMA_MISMATCH, key)
    return parsed, None


def _stock_rows(value: tuple[tuple[object, ...], ...]) -> tuple[_StockRow, ...]:
    rows: list[_StockRow] = []
    for row in value:
        if (
            len(row) != 8
            or any(type(row[index]) is not str for index in range(7))
            or (row[7] is not None and type(row[7]) is not str)
        ):
            raise ValueError("stock_basic row mismatch")
        rows.append(cast(_StockRow, row))
    return tuple(rows)


def _bak_rows(value: tuple[tuple[object, ...], ...]) -> tuple[_BakRow, ...]:
    if any(len(row) != 4 or any(type(item) is not str for item in row) for row in value):
        raise ValueError("bak_basic row mismatch")
    return cast(tuple[_BakRow, ...], value)


def _name_rows(value: tuple[tuple[object, ...], ...]) -> tuple[_NameRow, ...]:
    rows: list[_NameRow] = []
    for row in value:
        if (
            len(row) != 6
            or any(type(row[index]) is not str for index in (0, 1, 2, 4, 5))
            or (row[3] is not None and type(row[3]) is not str)
        ):
            raise ValueError("namechange row mismatch")
        rows.append(cast(_NameRow, row))
    return tuple(rows)


def _validated_observation(
    stock_rows: tuple[_StockRow, ...],
    bak_rows: tuple[_BakRow, ...],
    name_rows: tuple[_NameRow, ...],
) -> tuple[tuple[_StockRow, ...], tuple[_BakRow, ...], tuple[_NameRow, ...], int]:
    if type(stock_rows) is not tuple or type(bak_rows) is not tuple or type(name_rows) is not tuple:
        raise TypeError("source rows must be tuples")
    stock = _stock_rows(cast(tuple[tuple[object, ...], ...], stock_rows))
    bak = _bak_rows(cast(tuple[tuple[object, ...], ...], bak_rows))
    names = _name_rows(cast(tuple[tuple[object, ...], ...], name_rows))
    if len(stock) != 1 or len(bak) != 1 or not names:
        raise ValueError("source singleton mismatch")
    current = stock[0]
    history = bak[0]
    if (
        current[0] != _TS_CODE
        or current[1] != "000001"
        or not current[2]
        or not current[3]
        or current[4] != "SZSE"
        or current[5] != "L"
        or current[7] is not None
        or _date("stock list date", current[6]) > _TRADE_DATE
        or history[0] != _TRADE_DATE
        or history[1] != _TS_CODE
        or not history[2]
        or _date("historical list date", history[3]) != current[6]
        or history[2] != current[2]
        or len(set(names)) != len(names)
    ):
        raise ValueError("source identity conflict")
    covering: list[int] = []
    for index, row in enumerate(names):
        start = _date("name start date", row[2])
        end = None if row[3] is None else _date("name end date", row[3])
        _date("name announcement date", row[4])
        if (
            row[0] != _TS_CODE
            or not row[1]
            or (end is not None and end < start)
        ):
            raise ValueError("name interval conflict")
        if start <= _TRADE_DATE and (end is None or _TRADE_DATE <= end):
            covering.append(index)
    if len(covering) != 1 or names[covering[0]][1] != current[2]:
        raise ValueError("target name interval conflict")
    return stock, bak, names, covering[0]


def _observation(
    responses: dict[str, _Response],
) -> tuple[
    tuple[_StockRow, ...],
    tuple[_BakRow, ...],
    tuple[_NameRow, ...],
    int,
] | None:
    try:
        return _validated_observation(
            _stock_rows(responses["stock_basic"].rows),
            _bak_rows(responses["bak_basic"].rows),
            _name_rows(responses["namechange"].rows),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _build_report(
    *,
    receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    catalog: InstrumentCatalog,
    observation: tuple[
        tuple[_StockRow, ...],
        tuple[_BakRow, ...],
        tuple[_NameRow, ...],
        int,
    ],
    supersedes_report_hash: str | None,
) -> TushareCnAShareListingSourceBoundedObservationReportV2:
    stock, bak, names, target = observation
    return TushareCnAShareListingSourceBoundedObservationReportV2(
        provider_key=_PROVIDER_KEY,
        transport_proxy_key=_TRANSPORT_PROXY_KEY,
        datasets=_DATASETS,
        instrument_id=_INSTRUMENT,
        trade_date=_TRADE_DATE,
        request_scope_hash=_REQUEST_SCOPE_HASH,
        acquisition_receipt_sha256=_digest(receipt_bytes),
        snapshot_id=snapshot.snapshot_id,
        snapshot_content_tree_hash=snapshot.content_tree_hash,
        provenance_hash=snapshot.provenance_hash,
        member_keys=tuple(member.member_key for member in snapshot.members),
        member_content_hashes=tuple(member.content_hash for member in snapshot.members),
        member_acquired_at_epoch_nanoseconds=tuple(
            member.acquired_at_epoch_nanoseconds for member in snapshot.members
        ),
        instrument_catalog_hash=canonical_sha256(catalog),
        stock_basic_rows=stock,
        bak_basic_rows=bak,
        namechange_rows=names,
        source_record_hashes=tuple(
            _source_record_hash(dataset, row)
            for dataset, rows in (
                ("stock_basic", stock),
                ("bak_basic", bak),
                ("namechange", names),
            )
            for row in rows
        ),
        target_name_interval_index=target,
        observed_at=UtcInstant(
            max(member.acquired_at_epoch_nanoseconds for member in snapshot.members)
        ),
        supersedes_report_hash=supersedes_report_hash,
        limitations=_LIMITATIONS,
        revision_closure_complete=False,
        provider_completeness_qualified=False,
        absence_authority=False,
        historical_listing_lifecycle_qualified=False,
        corporate_action_lifecycle_qualified=False,
        decision_grade_eligible=False,
        live_eligible=False,
        deployment_authorized=False,
    )


def _replay_predecessor(
    *,
    report: TushareCnAShareListingSourceBoundedObservationReportV2,
    acquisition_receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    instrument_catalog: InstrumentCatalog,
) -> TushareCnAShareListingSourceBoundedObservationReportV2 | None:
    trusted_report = _reconstruct_report(report)
    evidence = _evidence(acquisition_receipt_bytes, snapshot)
    if trusted_report is None or evidence is None:
        return None
    receipt, trusted_snapshot = evidence
    trusted_catalog = _catalog(instrument_catalog)
    if trusted_catalog is None or not _request_scope(receipt, trusted_snapshot, trusted_catalog):
        return None
    responses, response_failure = _responses(receipt, trusted_snapshot)
    if response_failure is not None or any(
        response.has_more or response.count != 0 for response in responses.values()
    ):
        return None
    observation = _observation(responses)
    if observation is None:
        return None
    try:
        replayed = _build_report(
            receipt_bytes=acquisition_receipt_bytes,
            snapshot=trusted_snapshot,
            catalog=trusted_catalog,
            observation=observation,
            supersedes_report_hash=trusted_report.supersedes_report_hash,
        )
        rebuilt = _reconstruct_report(replayed)
    except (AttributeError, TypeError, ValueError):
        return None
    if rebuilt is None or canonical_bytes(rebuilt) != canonical_bytes(trusted_report):
        return None
    return trusted_report


def observe_tushare_cn_a_share_listing_source_bounded_v2(
    *,
    acquisition_receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    instrument_catalog: InstrumentCatalog,
    supersedes_report: TushareCnAShareListingSourceBoundedObservationReportV2
    | None = None,
    supersedes_acquisition_receipt_bytes: bytes | None = None,
    supersedes_snapshot: SourceSnapshot | None = None,
) -> TushareCnAShareListingSourceBoundedObservationOutcomeV2:
    if (
        type(acquisition_receipt_bytes) is not bytes
        or type(snapshot) is not SourceSnapshot
        or type(instrument_catalog) is not InstrumentCatalog
        or (
            supersedes_report is not None
            and type(supersedes_report)
            is not TushareCnAShareListingSourceBoundedObservationReportV2
        )
        or (
            supersedes_acquisition_receipt_bytes is not None
            and type(supersedes_acquisition_receipt_bytes) is not bytes
        )
        or (
            supersedes_snapshot is not None
            and type(supersedes_snapshot) is not SourceSnapshot
        )
    ):
        return _failed(_FailureCode.INVALID_INPUT)
    predecessor_values = (
        supersedes_report,
        supersedes_acquisition_receipt_bytes,
        supersedes_snapshot,
    )
    if any(value is not None for value in predecessor_values) and not all(
        value is not None for value in predecessor_values
    ):
        return _failed(_FailureCode.INVALID_INPUT)

    evidence = _evidence(acquisition_receipt_bytes, snapshot)
    if evidence is None:
        return _failed(_FailureCode.EVIDENCE_INVALID)
    receipt, trusted_snapshot = evidence
    trusted_catalog = _catalog(instrument_catalog)
    if trusted_catalog is None or not _request_scope(
        receipt, trusted_snapshot, trusted_catalog
    ):
        return _failed(_FailureCode.REQUEST_SCOPE_MISMATCH)
    responses, response_failure = _responses(receipt, trusted_snapshot)
    if response_failure is not None:
        return TushareCnAShareListingSourceBoundedObservationOutcomeV2(
            failure=response_failure
        )
    for api_name in _DATASETS:
        response = responses[api_name]
        if response.has_more or response.count != 0:
            return _failed(
                _FailureCode.RESPONSE_PAGE_INCOMPLETE,
                _REQUEST_MEMBER_KEYS[_DATASETS.index(api_name)],
            )
    observation = _observation(responses)
    if observation is None:
        return _failed(_FailureCode.SOURCE_OBSERVATION_CONFLICT)

    predecessor = None
    if supersedes_report is not None:
        predecessor = _replay_predecessor(
            report=supersedes_report,
            acquisition_receipt_bytes=cast(
                bytes, supersedes_acquisition_receipt_bytes
            ),
            snapshot=cast(SourceSnapshot, supersedes_snapshot),
            instrument_catalog=trusted_catalog,
        )
        observed_at = max(
            member.acquired_at_epoch_nanoseconds for member in trusted_snapshot.members
        )
        if (
            predecessor is None
            or predecessor.snapshot_id == trusted_snapshot.snapshot_id
            or predecessor.observed_at.epoch_nanoseconds >= observed_at
        ):
            return _failed(_FailureCode.REPORT_BINDING_MISMATCH)
    try:
        report = _build_report(
            receipt_bytes=acquisition_receipt_bytes,
            snapshot=trusted_snapshot,
            catalog=trusted_catalog,
            observation=observation,
            supersedes_report_hash=(
                None if predecessor is None else predecessor.report_hash
            ),
        )
        trusted_report = _reconstruct_report(report)
        if trusted_report is None or canonical_bytes(trusted_report) != canonical_bytes(
            report
        ):
            raise ValueError("report replay mismatch")
    except (AttributeError, TypeError, ValueError):
        return _failed(_FailureCode.REPORT_BINDING_MISMATCH)
    return TushareCnAShareListingSourceBoundedObservationOutcomeV2(
        report=trusted_report
    )
