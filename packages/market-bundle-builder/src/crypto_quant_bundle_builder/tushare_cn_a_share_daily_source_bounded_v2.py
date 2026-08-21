from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    InstrumentId,
    Money,
    Price,
    PricePurpose,
    Quantity,
    Rate,
    Scale,
    SessionId,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .bundle_validation import validate_market_bundle_v1
from .coverage_declarations import BuilderStaleMarkPolicy, PricePurposeRequirement
from .source_snapshots import SourceSnapshot
from .tushare_cn_a_share_daily import (
    _LIMITATIONS as _DAILY_LIMITATIONS,
)
from .tushare_cn_a_share_daily import (
    BarBucket,
    _NumericToken,
    _parse,
    _reconstruct_snapshot,
    _scaled_multiplier,
    _source_record_hash,
    _units,
)

_SCHEMA_VERSION = 2
_PROVIDER_DATES = (
    "20260706",
    "20260707",
    "20260708",
    "20260709",
    "20260710",
    "20260711",
    "20260712",
    "20260713",
    "20260714",
    "20260715",
    "20260716",
    "20260717",
    "20260718",
    "20260719",
    "20260720",
    "20260721",
    "20260722",
    "20260723",
    "20260724",
    "20260725",
    "20260726",
    "20260727",
    "20260728",
    "20260729",
    "20260730",
)
_DAILY_FIELDS = (
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
)
_CALENDAR_FIELDS = ("exchange", "cal_date", "is_open", "pretrade_date")
_SUSPEND_FIELDS = ("ts_code", "trade_date", "suspend_timing", "suspend_type")
_PROVIDER_KEY = "tushare.pro"
_DATASETS = ("daily", "trade_cal", "suspend_d")
_SOURCE_KEY = (
    "tushare.pro.cn_a_share_daily_source_bounded_v2.000001.sz.20260706.20260730"
)
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_VENUE_CALENDAR = "XSHE"
_PROVIDER_EXCHANGE = "SZSE"
_COVERAGE_START = UtcInstant(1_783_267_200_000_000_000)
_COVERAGE_END_EXCLUSIVE = UtcInstant(1_785_427_200_000_000_000)
_STREAM_KEY = "tushare_cn_a_share.daily.publication.xshe.000001.v1"
_EVENT_TYPE = "tushare_cn_a_share_daily_publication.v1"
_CAPABILITY = MarketBundleCapability("tushare_cn_a_share.daily-publications", 1)
_PHASE = TimelinePhase(0, "market_data")
_BUNDLE_KEY = "tushare-cn-a-share-daily-000001-20260706-20260730-source-bounded-v2"
_CATALOG_HASH = "sha256:" + "0" * 64
_LIMITATIONS = (
    "permanent_provider_checksum_unavailable",
    "future_revision_finality_unknown",
    "correction_lineage_unavailable",
    "provider_completeness_unknown",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DATE = re.compile(r"[0-9]{8}\Z")
_RECEIPT_KEYS = {
    "type",
    "schema_version",
    "request",
    "provider_requests",
    "acquired_at_epoch_nanoseconds",
    "snapshot",
    "provider_declared_sha256",
    "provider_revision_id",
    "decision_grade_eligible",
    "deployment_authorized",
}
_PROVIDER_REQUEST_KEYS = {
    "api_name",
    "params",
    "fields",
    "member_key",
    "attempts",
    "response_received_at_epoch_nanoseconds",
    "response_byte_count",
    "response_sha256",
    "observed_envelope",
    "declared_sha256",
    "provider_revision_id",
}
_RESPONSE_KEYS = {"request_id", "code", "data", "msg", "detail"}
_RESPONSE_DATA_KEYS = {"fields", "items", "has_more", "count"}
_FORBIDDEN_CREDENTIAL_MARKERS = (
    b"TUSHARE_TOKEN",
    b"tushare_token",
    b'"token":',
    b'"authorization":',
    b'"api_key":',
)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be canonical text")
    value.encode("utf-8")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if _HASH.fullmatch(text) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return text


def _utc(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be exact UtcInstant")
    rebuilt = UtcInstant(value.epoch_nanoseconds)
    if rebuilt != value:
        raise ValueError(f"{name} must be canonical UtcInstant")
    return rebuilt


def _instrument(value: object) -> InstrumentId:
    if type(value) is not InstrumentId or type(value.venue) is not VenueId:
        raise TypeError("instrument_id must be exact InstrumentId")
    rebuilt = InstrumentId(VenueId(value.venue.value), value.stable_key)
    if rebuilt != value:
        raise ValueError("instrument_id must be canonical")
    return rebuilt


def _string_tuple(name: str, value: object) -> tuple[str, ...]:
    if type(value) is not tuple or any(type(item) is not str for item in value):
        raise TypeError(f"{name} must be tuple[str, ...]")
    return tuple(_text(f"{name} item", item) for item in value)


def _hash_tuple(name: str, value: object) -> tuple[str, ...]:
    values = _string_tuple(name, value)
    return tuple(_hash(f"{name} item", item) for item in values)


def _integer_tuple(name: str, value: object) -> tuple[int, ...]:
    if type(value) is not tuple or any(type(item) is not int for item in value):
        raise TypeError(f"{name} must be tuple[int, ...]")
    if any(item < 0 for item in value):
        raise ValueError(f"{name} must be nonnegative")
    return value


def _member_keys() -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                *(f"response/daily/{value}.json" for value in _PROVIDER_DATES),
                *(f"response/suspend-d/{value}.json" for value in _PROVIDER_DATES),
                "response/trade-cal/20260706-20260730.json",
            )
        )
    )


def _bucket_for_trade_date(trade_date: str) -> BarBucket:
    trading_date = date.fromisoformat(
        f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
    )
    day_start = (trading_date - date(1970, 1, 1)).days * 86_400_000_000_000
    spans = tuple(
        (UtcInstant(day_start + start), UtcInstant(day_start + end))
        for start, end in (
            (4_500_000_000_000, 5_100_000_000_000),
            (5_400_000_000_000, 12_600_000_000_000),
            (18_000_000_000_000, 25_020_000_000_000),
            (25_020_000_000_000, 25_200_000_000_000),
        )
    )
    return BarBucket(
        SessionId("CN.XSHE", f"{trading_date.isoformat()}.regular"),
        TradingDate("CN.XSHE", trading_date),
        spans,
        spans[0][0],
        spans[-1][1],
    )


class _SourceBoundedFailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    EVIDENCE_INVALID = "evidence_invalid"
    REQUEST_SCOPE_MISMATCH = "request_scope_mismatch"
    RESPONSE_SCHEMA_MISMATCH = "response_schema_mismatch"
    RESPONSE_PAGE_INCOMPLETE = "response_page_incomplete"
    SOURCE_OBSERVATION_CONFLICT = "source_observation_conflict"
    MISSING_CLASSIFICATION = "missing_classification"
    NORMALIZATION_FAILED = "normalization_failed"
    PUBLICATION_FAILED = "publication_failed"
    PURPOSE_SCOPE_MISMATCH = "purpose_scope_mismatch"
    LOOKAHEAD_VIOLATION = "lookahead_violation"
    REPORT_BINDING_MISMATCH = "report_binding_mismatch"


@dataclass(frozen=True, slots=True)
class _SourceBoundedFailure:
    code: _SourceBoundedFailureCode
    provider_date: str | None = None
    member_key: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not _SourceBoundedFailureCode:
            raise TypeError("code must be exact source-bounded failure code")
        if self.provider_date is not None and (
            type(self.provider_date) is not str
            or _DATE.fullmatch(self.provider_date) is None
        ):
            raise ValueError("provider_date must be YYYYMMDD")
        if self.member_key is not None:
            _text("member_key", self.member_key)

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_source_bounded_observation_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "provider_date": self.provider_date,
            "member_key": self.member_key,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailySourceBoundedObservationReportV2:
    provider_key: str
    datasets: tuple[str, ...]
    instrument_id: InstrumentId
    venue_calendar: str
    provider_exchange: str
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    acquisition_receipt_sha256: str
    snapshot_id: str
    snapshot_content_tree_hash: str
    provenance_hash: str
    member_keys: tuple[str, ...]
    member_content_hashes: tuple[str, ...]
    member_acquired_at_epoch_nanoseconds: tuple[int, ...]
    bundle_ref: MarketBundleRef
    manifest_content_hash: str
    stream_content_hash: str
    published_event_hashes: tuple[str, ...]
    price_purpose_requirement_hashes: tuple[str, ...]
    published_provider_dates: tuple[str, ...]
    no_session_provider_dates: tuple[str, ...]
    suspended_provider_dates: tuple[str, ...]
    observed_at: UtcInstant
    supersedes_report_hash: str | None
    limitations: tuple[str, ...]
    availability_closure_complete: bool
    revision_closure_complete: bool
    generic_price_bars_capability: bool
    g12i_analyzer_ready: bool
    provider_qualified: bool
    historical_listing_status_qualified: bool
    corporate_actions_qualified: bool
    decision_grade_eligible: bool
    deployment_authorized: bool
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.provider_key != _PROVIDER_KEY or self.datasets != _DATASETS:
            raise ValueError("report provider/dataset scope mismatch")
        if _instrument(self.instrument_id) != _INSTRUMENT:
            raise ValueError("report instrument scope mismatch")
        if (
            self.venue_calendar != _VENUE_CALENDAR
            or self.provider_exchange != _PROVIDER_EXCHANGE
            or _utc("coverage_start", self.coverage_start) != _COVERAGE_START
            or _utc("coverage_end_exclusive", self.coverage_end_exclusive)
            != _COVERAGE_END_EXCLUSIVE
        ):
            raise ValueError("report calendar/time scope mismatch")
        for name in (
            "acquisition_receipt_sha256",
            "snapshot_id",
            "snapshot_content_tree_hash",
            "provenance_hash",
            "manifest_content_hash",
            "stream_content_hash",
        ):
            _hash(name, getattr(self, name))
        member_keys = _string_tuple("member_keys", self.member_keys)
        member_hashes = _hash_tuple("member_content_hashes", self.member_content_hashes)
        member_times = _integer_tuple(
            "member_acquired_at_epoch_nanoseconds",
            self.member_acquired_at_epoch_nanoseconds,
        )
        if (
            member_keys != _member_keys()
            or len(member_keys) != len(member_hashes)
            or len(member_keys) != len(member_times)
        ):
            raise ValueError("report member binding mismatch")
        if type(self.bundle_ref) is not MarketBundleRef:
            raise TypeError("bundle_ref must be exact MarketBundleRef")
        rebuilt_ref = MarketBundleRef(
            self.bundle_ref.bundle_key, self.bundle_ref.manifest_hash
        )
        if rebuilt_ref != self.bundle_ref or rebuilt_ref.bundle_key != _BUNDLE_KEY:
            raise ValueError("report Bundle ref mismatch")
        event_hashes = _hash_tuple(
            "published_event_hashes", self.published_event_hashes
        )
        requirement_hashes = _hash_tuple(
            "price_purpose_requirement_hashes",
            self.price_purpose_requirement_hashes,
        )
        if (
            len(requirement_hashes) != 2
            or requirement_hashes[0] == requirement_hashes[1]
        ):
            raise ValueError("report purpose requirements mismatch")
        published = _string_tuple(
            "published_provider_dates", self.published_provider_dates
        )
        no_session = _string_tuple(
            "no_session_provider_dates", self.no_session_provider_dates
        )
        suspended = _string_tuple(
            "suspended_provider_dates", self.suspended_provider_dates
        )
        for value in (*published, *no_session, *suspended):
            if _DATE.fullmatch(value) is None or value not in _PROVIDER_DATES:
                raise ValueError("report partition date is out of scope")
        if (
            published != tuple(sorted(published))
            or no_session != tuple(sorted(no_session))
            or suspended != tuple(sorted(suspended))
            or len({*published, *no_session, *suspended}) != len(_PROVIDER_DATES)
            or {*published, *no_session, *suspended} != set(_PROVIDER_DATES)
            or len(event_hashes) != len(published)
        ):
            raise ValueError("report date partition mismatch")
        try:
            stream = MarketStreamManifest(
                stream_key=_STREAM_KEY,
                event_type=_EVENT_TYPE,
                capability=_CAPABILITY,
                event_count=len(event_hashes),
                content_hash=self.stream_content_hash,
            )
            manifest = MarketBundleManifest(
                bundle_key=_BUNDLE_KEY,
                schema_version=1,
                coverage_start=_COVERAGE_START,
                coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
                instrument_catalog_hash=_CATALOG_HASH,
                capabilities=(_CAPABILITY,),
                streams=(stream,),
                content_hash=self.manifest_content_hash,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("report manifest binding mismatch") from error
        if MarketBundleRef.from_manifest(manifest) != rebuilt_ref:
            raise ValueError("report Bundle ref mismatch")
        observed_at = _utc("observed_at", self.observed_at)
        if observed_at.epoch_nanoseconds != max(member_times):
            raise ValueError("report observation time mismatch")
        if self.supersedes_report_hash is not None:
            _hash("supersedes_report_hash", self.supersedes_report_hash)
        if self.limitations != _LIMITATIONS:
            raise ValueError("report limitations mismatch")
        flags = (
            self.availability_closure_complete,
            self.revision_closure_complete,
            self.generic_price_bars_capability,
            self.g12i_analyzer_ready,
            self.provider_qualified,
            self.historical_listing_status_qualified,
            self.corporate_actions_qualified,
            self.decision_grade_eligible,
            self.deployment_authorized,
        )
        if any(type(value) is not bool for value in flags) or any(flags):
            raise ValueError("report qualification flags must remain false")
        object.__setattr__(self, "report_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_source_bounded_observation_report",
            "schema_version": _SCHEMA_VERSION,
            "provider_key": self.provider_key,
            "datasets": self.datasets,
            "instrument_id": self.instrument_id,
            "venue_calendar": self.venue_calendar,
            "provider_exchange": self.provider_exchange,
            "coverage_start": self.coverage_start,
            "coverage_end_exclusive": self.coverage_end_exclusive,
            "acquisition_receipt_sha256": self.acquisition_receipt_sha256,
            "snapshot_id": self.snapshot_id,
            "snapshot_content_tree_hash": self.snapshot_content_tree_hash,
            "provenance_hash": self.provenance_hash,
            "member_keys": self.member_keys,
            "member_content_hashes": self.member_content_hashes,
            "member_acquired_at_epoch_nanoseconds": self.member_acquired_at_epoch_nanoseconds,
            "bundle_ref": self.bundle_ref,
            "manifest_content_hash": self.manifest_content_hash,
            "stream_content_hash": self.stream_content_hash,
            "published_event_hashes": self.published_event_hashes,
            "price_purpose_requirement_hashes": self.price_purpose_requirement_hashes,
            "published_provider_dates": self.published_provider_dates,
            "no_session_provider_dates": self.no_session_provider_dates,
            "suspended_provider_dates": self.suspended_provider_dates,
            "observed_at": self.observed_at,
            "supersedes_report_hash": self.supersedes_report_hash,
            "limitations": self.limitations,
            "availability_closure_complete": self.availability_closure_complete,
            "revision_closure_complete": self.revision_closure_complete,
            "generic_price_bars_capability": self.generic_price_bars_capability,
            "g12i_analyzer_ready": self.g12i_analyzer_ready,
            "provider_qualified": self.provider_qualified,
            "historical_listing_status_qualified": self.historical_listing_status_qualified,
            "corporate_actions_qualified": self.corporate_actions_qualified,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "report_hash": self.report_hash}

    @classmethod
    def from_canonical_dict(
        cls, value: Mapping[str, object]
    ) -> TushareCnAShareDailySourceBoundedObservationReportV2:
        if type(value) is not dict:
            raise TypeError("report canonical value must be exact dict")
        body = cast(dict[str, object], value)
        expected_keys = {
            "type",
            "schema_version",
            *cls.__dataclass_fields__.keys(),
        }
        if set(body) != expected_keys:
            raise ValueError("report canonical keys mismatch")
        if (
            body["type"] != "tushare_cn_a_share_daily_source_bounded_observation_report"
            or body["schema_version"] != _SCHEMA_VERSION
        ):
            raise ValueError("report canonical schema mismatch")
        instrument = body["instrument_id"]
        bundle_ref = body["bundle_ref"]
        coverage_start = body["coverage_start"]
        coverage_end = body["coverage_end_exclusive"]
        observed_at = body["observed_at"]
        if (
            type(instrument) is not dict
            or set(instrument) != {"type", "venue", "stable_key"}
            or instrument["type"] != "instrument_id"
            or type(bundle_ref) is not dict
            or set(bundle_ref) != {"type", "bundle_key", "manifest_hash"}
            or bundle_ref["type"] != "market_bundle_ref"
        ):
            raise ValueError("report canonical nested identity mismatch")

        def instant(item: object) -> UtcInstant:
            if (
                type(item) is not dict
                or set(item) != {"type", "epoch_nanoseconds"}
                or item["type"] != "utc_instant"
                or type(item["epoch_nanoseconds"]) is not int
            ):
                raise ValueError("report canonical instant mismatch")
            return UtcInstant(item["epoch_nanoseconds"])

        def strings(name: str) -> tuple[str, ...]:
            return _string_tuple(name, tuple(cast(list[object], body[name])))

        def hashes(name: str) -> tuple[str, ...]:
            return _hash_tuple(name, tuple(cast(list[object], body[name])))

        report = cls(
            provider_key=cast(str, body["provider_key"]),
            datasets=strings("datasets"),
            instrument_id=InstrumentId(
                VenueId(cast(str, instrument["venue"])),
                cast(str, instrument["stable_key"]),
            ),
            venue_calendar=cast(str, body["venue_calendar"]),
            provider_exchange=cast(str, body["provider_exchange"]),
            coverage_start=instant(coverage_start),
            coverage_end_exclusive=instant(coverage_end),
            acquisition_receipt_sha256=cast(str, body["acquisition_receipt_sha256"]),
            snapshot_id=cast(str, body["snapshot_id"]),
            snapshot_content_tree_hash=cast(str, body["snapshot_content_tree_hash"]),
            provenance_hash=cast(str, body["provenance_hash"]),
            member_keys=strings("member_keys"),
            member_content_hashes=hashes("member_content_hashes"),
            member_acquired_at_epoch_nanoseconds=_integer_tuple(
                "member_acquired_at_epoch_nanoseconds",
                tuple(
                    cast(
                        list[object],
                        body["member_acquired_at_epoch_nanoseconds"],
                    )
                ),
            ),
            bundle_ref=MarketBundleRef(
                cast(str, bundle_ref["bundle_key"]),
                cast(str, bundle_ref["manifest_hash"]),
            ),
            manifest_content_hash=cast(str, body["manifest_content_hash"]),
            stream_content_hash=cast(str, body["stream_content_hash"]),
            published_event_hashes=hashes("published_event_hashes"),
            price_purpose_requirement_hashes=hashes("price_purpose_requirement_hashes"),
            published_provider_dates=strings("published_provider_dates"),
            no_session_provider_dates=strings("no_session_provider_dates"),
            suspended_provider_dates=strings("suspended_provider_dates"),
            observed_at=instant(observed_at),
            supersedes_report_hash=cast(str | None, body["supersedes_report_hash"]),
            limitations=strings("limitations"),
            availability_closure_complete=cast(
                bool, body["availability_closure_complete"]
            ),
            revision_closure_complete=cast(bool, body["revision_closure_complete"]),
            generic_price_bars_capability=cast(
                bool, body["generic_price_bars_capability"]
            ),
            g12i_analyzer_ready=cast(bool, body["g12i_analyzer_ready"]),
            provider_qualified=cast(bool, body["provider_qualified"]),
            historical_listing_status_qualified=cast(
                bool, body["historical_listing_status_qualified"]
            ),
            corporate_actions_qualified=cast(bool, body["corporate_actions_qualified"]),
            decision_grade_eligible=cast(bool, body["decision_grade_eligible"]),
            deployment_authorized=cast(bool, body["deployment_authorized"]),
        )
        if body["report_hash"] != report.report_hash:
            raise ValueError("report hash mismatch")
        if canonical_bytes(body) != canonical_bytes(report.to_canonical_dict()):
            raise ValueError("report canonical reconstruction mismatch")
        return report


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailySourceBoundedObservationOutcomeV2:
    report: TushareCnAShareDailySourceBoundedObservationReportV2 | None = None
    failure: _SourceBoundedFailure | None = None

    def __post_init__(self) -> None:
        if (self.report is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one report or failure")
        if self.report is not None:
            trusted = _reconstruct_report(self.report)
            if trusted is None:
                raise ValueError("outcome report authority is invalid")
            object.__setattr__(self, "report", trusted)
        if self.failure is not None and type(self.failure) is not _SourceBoundedFailure:
            raise TypeError("failure must be exact source-bounded failure")


@dataclass(frozen=True, slots=True)
class _Response:
    fields: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    has_more: bool
    count: int


@dataclass(frozen=True, slots=True)
class _BuiltPublication:
    events: tuple[MarketEvent, ...]
    bundle_ref: MarketBundleRef
    manifest_content_hash: str
    stream_content_hash: str


def _failed(
    code: _SourceBoundedFailureCode,
    *,
    provider_date: str | None = None,
    member_key: str | None = None,
) -> TushareCnAShareDailySourceBoundedObservationOutcomeV2:
    return TushareCnAShareDailySourceBoundedObservationOutcomeV2(
        failure=_SourceBoundedFailure(code, provider_date, member_key)
    )


def _reconstruct_report(
    value: object,
) -> TushareCnAShareDailySourceBoundedObservationReportV2 | None:
    if type(value) is not TushareCnAShareDailySourceBoundedObservationReportV2:
        return None
    try:
        return TushareCnAShareDailySourceBoundedObservationReportV2.from_canonical_dict(
            json.loads(canonical_bytes(value.to_canonical_dict()))
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _receipt(receipt_bytes: bytes) -> dict[str, object]:
    try:
        parsed = json.loads(
            receipt_bytes.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("receipt must be valid unique-key JSON") from error
    if type(parsed) is not dict or receipt_bytes != canonical_bytes(parsed) + b"\n":
        raise ValueError("receipt must be canonical unique-key JSON")
    return parsed


def _provider_request_structure(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != _PROVIDER_REQUEST_KEYS:
        raise ValueError("provider request evidence shape mismatch")
    request = cast(dict[str, object], value)
    if (
        type(request["api_name"]) is not str
        or type(request["params"]) is not dict
        or type(request["fields"]) is not str
        or type(request["member_key"]) is not str
        or type(request["attempts"]) is not int
        or request["attempts"] <= 0
        or type(request["response_received_at_epoch_nanoseconds"]) is not int
        or request["response_received_at_epoch_nanoseconds"] < 0
        or type(request["response_byte_count"]) is not int
        or request["response_byte_count"] < 0
        or type(request["observed_envelope"]) is not dict
        or set(cast(dict[str, object], request["observed_envelope"]))
        != {"has_more", "count"}
        or type(cast(dict[str, object], request["observed_envelope"])["has_more"])
        is not bool
        or type(cast(dict[str, object], request["observed_envelope"])["count"])
        is not int
        or request["declared_sha256"] is not None
        or request["provider_revision_id"] is not None
    ):
        raise ValueError("provider request evidence primitive mismatch")
    _text("api_name", request["api_name"])
    _text("fields", request["fields"])
    _text("member_key", request["member_key"])
    _hash("response_sha256", request["response_sha256"])
    return request


def _evidence(
    receipt_bytes: bytes, snapshot: SourceSnapshot
) -> tuple[dict[str, object], SourceSnapshot] | None:
    try:
        receipt = _receipt(receipt_bytes)
        if (
            set(receipt) != _RECEIPT_KEYS
            or receipt["type"]
            != "tushare_cn_a_share_daily_source_bounded_acquisition_receipt"
            or receipt["schema_version"] != _SCHEMA_VERSION
            or type(receipt["request"]) is not dict
            or type(receipt["provider_requests"]) is not list
            or type(receipt["acquired_at_epoch_nanoseconds"]) is not int
            or receipt["provider_declared_sha256"] is not None
            or receipt["provider_revision_id"] is not None
            or type(receipt["decision_grade_eligible"]) is not bool
            or receipt["decision_grade_eligible"]
            or type(receipt["deployment_authorized"]) is not bool
            or receipt["deployment_authorized"]
            or type(receipt["snapshot"]) is not dict
            or any(marker in receipt_bytes for marker in _FORBIDDEN_CREDENTIAL_MARKERS)
        ):
            return None
        requests = tuple(
            _provider_request_structure(value)
            for value in cast(list[object], receipt["provider_requests"])
        )
        if len(requests) != 51:
            return None
        rebuilt = _reconstruct_snapshot(snapshot)
        if rebuilt is None:
            return None
        if receipt["snapshot"] != rebuilt.to_canonical_dict():
            return None
        by_key = {member.member_key: member for member in rebuilt.members}
        if len(by_key) != 51 or tuple(by_key) != _member_keys():
            return None
        request_keys = tuple(cast(str, value["member_key"]) for value in requests)
        if len(set(request_keys)) != 51 or set(request_keys) != set(by_key):
            return None
        if receipt["acquired_at_epoch_nanoseconds"] != max(
            cast(int, value["response_received_at_epoch_nanoseconds"])
            for value in requests
        ):
            return None
        for request in requests:
            key = cast(str, request["member_key"])
            member = by_key[key]
            raw = rebuilt.member_bytes(key)
            if (
                cast(int, request["response_received_at_epoch_nanoseconds"])
                != member.acquired_at_epoch_nanoseconds
                or cast(int, request["response_byte_count"]) != member.byte_count
                or request["response_sha256"] != member.content_hash
                or _digest(raw) != member.content_hash
                or any(marker in raw for marker in _FORBIDDEN_CREDENTIAL_MARKERS)
            ):
                return None
        return receipt, rebuilt
    except Exception:  # noqa: BLE001 -- trust-boundary failures are redacted.
        return None


def _request_coordinates() -> tuple[tuple[str, dict[str, object], str, str], ...]:
    return (
        *(
            (
                "daily",
                {"ts_code": "000001.SZ", "start_date": value, "end_date": value},
                ",".join(_DAILY_FIELDS),
                f"response/daily/{value}.json",
            )
            for value in _PROVIDER_DATES
        ),
        (
            "trade_cal",
            {"exchange": "SZSE", "start_date": "20260706", "end_date": "20260730"},
            ",".join(_CALENDAR_FIELDS),
            "response/trade-cal/20260706-20260730.json",
        ),
        *(
            (
                "suspend_d",
                {
                    "ts_code": "000001.SZ",
                    "trade_date": value,
                    "suspend_type": "S",
                },
                ",".join(_SUSPEND_FIELDS),
                f"response/suspend-d/{value}.json",
            )
            for value in _PROVIDER_DATES
        ),
    )


def _request_scope(receipt: dict[str, object], snapshot: SourceSnapshot) -> bool:
    expected_request = {
        "type": "tushare_cn_a_share_daily_source_bounded_request",
        "schema_version": _SCHEMA_VERSION,
        "ts_code": "000001.SZ",
        "exchange": "SZSE",
        "provider_dates": list(_PROVIDER_DATES),
        "start_date": "20260706",
        "end_date": "20260730",
    }
    if receipt["request"] != expected_request:
        return False
    if snapshot.provenance.to_canonical_dict() != {
        "vendor_key": _PROVIDER_KEY,
        "source_key": _SOURCE_KEY,
        "license_ref": "tushare.pro.terms",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }:
        return False
    requests = cast(list[dict[str, object]], receipt["provider_requests"])
    coordinates = _request_coordinates()
    return len(requests) == len(coordinates) and all(
        (
            request["api_name"],
            request["params"],
            request["fields"],
            request["member_key"],
        )
        == expected
        for request, expected in zip(requests, coordinates, strict=True)
    )


def _response(source: bytes, expected_fields: tuple[str, ...]) -> _Response:
    try:
        parsed = _parse(source)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
        ValueError,
    ) as error:
        raise ValueError("response must be valid unique-key JSON") from error
    if type(parsed) is not dict or set(parsed) != _RESPONSE_KEYS:
        raise ValueError("response envelope mismatch")
    request_id = parsed["request_id"]
    code = parsed["code"]
    data = parsed["data"]
    if (
        _text("request_id", request_id) != request_id
        or type(code) is not _NumericToken
        or code.lexeme != "0"
        or parsed["msg"] != ""
        or type(parsed["detail"]) is not str
        or type(data) is not dict
        or set(data) != _RESPONSE_DATA_KEYS
        or type(data["fields"]) is not list
        or tuple(data["fields"]) != expected_fields
        or type(data["items"]) is not list
        or type(data["has_more"]) is not bool
        or type(data["count"]) is not _NumericToken
        or "." in data["count"].lexeme
        or data["count"].lexeme.startswith("-")
    ):
        raise ValueError("response schema mismatch")
    rows: list[tuple[object, ...]] = []
    for row in data["items"]:
        if type(row) is not list or len(row) != len(expected_fields):
            raise ValueError("response row shape mismatch")
        rows.append(tuple(row))
    try:
        count = int(data["count"].lexeme)
    except ValueError as error:
        raise ValueError("response count mismatch") from error
    return _Response(expected_fields, tuple(rows), data["has_more"], count)


def _primitive_rows(api_name: str, response: _Response) -> bool:
    if api_name == "daily":
        return all(
            type(row[0]) is str
            and type(row[1]) is str
            and all(type(value) is _NumericToken for value in row[2:])
            for row in response.rows
        )
    if api_name == "trade_cal":
        return all(
            type(row[0]) is str
            and type(row[1]) is str
            and type(row[2]) is _NumericToken
            and row[2].lexeme in {"0", "1"}
            and type(row[3]) is str
            for row in response.rows
        )
    return all(
        type(row[0]) is str
        and type(row[1]) is str
        and (
            row[2] is None
            or (type(row[2]) is str and bool(row[2]) and row[2] == row[2].strip())
        )
        and type(row[3]) is str
        for row in response.rows
    )


def _responses(
    receipt: dict[str, object], snapshot: SourceSnapshot
) -> tuple[dict[str, _Response], _SourceBoundedFailure | None]:
    parsed: dict[str, _Response] = {}
    requests = cast(list[dict[str, object]], receipt["provider_requests"])
    for request in requests:
        key = cast(str, request["member_key"])
        api_name = cast(str, request["api_name"])
        fields = {
            "daily": _DAILY_FIELDS,
            "trade_cal": _CALENDAR_FIELDS,
            "suspend_d": _SUSPEND_FIELDS,
        }[api_name]
        try:
            response = _response(snapshot.member_bytes(key), fields)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
            TypeError,
            ValueError,
        ):
            return {}, _SourceBoundedFailure(
                _SourceBoundedFailureCode.RESPONSE_SCHEMA_MISMATCH,
                _date_for_member(key),
                key,
            )
        if not _primitive_rows(api_name, response):
            return {}, _SourceBoundedFailure(
                _SourceBoundedFailureCode.RESPONSE_SCHEMA_MISMATCH,
                _date_for_member(key),
                key,
            )
        observed = cast(dict[str, object], request["observed_envelope"])
        if observed != {"has_more": response.has_more, "count": response.count}:
            return {}, _SourceBoundedFailure(
                _SourceBoundedFailureCode.EVIDENCE_INVALID,
                _date_for_member(key),
                key,
            )
        parsed[key] = response
    return parsed, None


def _date_for_member(member_key: str) -> str | None:
    match = re.search(r"/([0-9]{8})(?:\.json|-)", member_key)
    return None if match is None else match.group(1)


def _page_failure(responses: dict[str, _Response]) -> _SourceBoundedFailure | None:
    for _, _, _, key in _request_coordinates():
        if responses[key].has_more:
            return _SourceBoundedFailure(
                _SourceBoundedFailureCode.RESPONSE_PAGE_INCOMPLETE,
                _date_for_member(key),
                key,
            )
    return None


def _coordinates_valid(responses: dict[str, _Response]) -> _SourceBoundedFailure | None:
    for provider_date in _PROVIDER_DATES:
        key = f"response/daily/{provider_date}.json"
        if any(
            row[0] != "000001.SZ" or row[1] != provider_date
            for row in responses[key].rows
        ):
            return _SourceBoundedFailure(
                _SourceBoundedFailureCode.RESPONSE_SCHEMA_MISMATCH,
                provider_date,
                key,
            )
    calendar_key = "response/trade-cal/20260706-20260730.json"
    for row in responses[calendar_key].rows:
        if (
            row[0] != "SZSE"
            or row[1] not in _PROVIDER_DATES
            or _DATE.fullmatch(cast(str, row[1])) is None
            or _DATE.fullmatch(cast(str, row[3])) is None
            or cast(str, row[3]) >= cast(str, row[1])
        ):
            return _SourceBoundedFailure(
                _SourceBoundedFailureCode.RESPONSE_SCHEMA_MISMATCH,
                cast(str, row[1]) if type(row[1]) is str else None,
                calendar_key,
            )
    for provider_date in _PROVIDER_DATES:
        key = f"response/suspend-d/{provider_date}.json"
        if any(
            row[0] != "000001.SZ" or row[1] != provider_date or row[3] != "S"
            for row in responses[key].rows
        ):
            return _SourceBoundedFailure(
                _SourceBoundedFailureCode.RESPONSE_SCHEMA_MISMATCH,
                provider_date,
                key,
            )
    return None


def _classify(
    responses: dict[str, _Response],
) -> tuple[
    tuple[str, ...], tuple[str, ...], tuple[str, ...], _SourceBoundedFailure | None
]:
    calendar_key = "response/trade-cal/20260706-20260730.json"
    calendar: dict[str, bool] = {}
    for row in responses[calendar_key].rows:
        provider_date = cast(str, row[1])
        if provider_date in calendar:
            return (
                (),
                (),
                (),
                _SourceBoundedFailure(
                    _SourceBoundedFailureCode.SOURCE_OBSERVATION_CONFLICT,
                    provider_date,
                    calendar_key,
                ),
            )
        calendar[provider_date] = cast(_NumericToken, row[2]).lexeme == "1"

    for provider_date in _PROVIDER_DATES:
        daily_key = f"response/daily/{provider_date}.json"
        suspend_key = f"response/suspend-d/{provider_date}.json"
        daily_rows = responses[daily_key].rows
        suspension_rows = responses[suspend_key].rows
        full_day_suspension = any(row[2] is None for row in suspension_rows)
        if len(daily_rows) > 1 or len(set(daily_rows)) != len(daily_rows):
            return (
                (),
                (),
                (),
                _SourceBoundedFailure(
                    _SourceBoundedFailureCode.SOURCE_OBSERVATION_CONFLICT,
                    provider_date,
                    daily_key,
                ),
            )
        if len(set(suspension_rows)) != len(suspension_rows):
            return (
                (),
                (),
                (),
                _SourceBoundedFailure(
                    _SourceBoundedFailureCode.SOURCE_OBSERVATION_CONFLICT,
                    provider_date,
                    suspend_key,
                ),
            )
        if (
            provider_date in calendar
            and not calendar[provider_date]
            and (daily_rows or suspension_rows)
        ):
            return (
                (),
                (),
                (),
                _SourceBoundedFailure(
                    _SourceBoundedFailureCode.SOURCE_OBSERVATION_CONFLICT,
                    provider_date,
                    daily_key if daily_rows else suspend_key,
                ),
            )
        if daily_rows and full_day_suspension:
            return (
                (),
                (),
                (),
                _SourceBoundedFailure(
                    _SourceBoundedFailureCode.SOURCE_OBSERVATION_CONFLICT,
                    provider_date,
                    suspend_key,
                ),
            )

    published: list[str] = []
    no_session: list[str] = []
    suspended: list[str] = []
    for provider_date in _PROVIDER_DATES:
        daily_key = f"response/daily/{provider_date}.json"
        suspend_key = f"response/suspend-d/{provider_date}.json"
        daily_rows = responses[daily_key].rows
        suspension_rows = responses[suspend_key].rows
        if provider_date not in calendar:
            return (
                (),
                (),
                (),
                _SourceBoundedFailure(
                    _SourceBoundedFailureCode.MISSING_CLASSIFICATION,
                    provider_date,
                    calendar_key,
                ),
            )
        if not calendar[provider_date]:
            no_session.append(provider_date)
        elif daily_rows:
            published.append(provider_date)
        elif any(row[2] is None for row in suspension_rows):
            suspended.append(provider_date)
        else:
            return (
                (),
                (),
                (),
                _SourceBoundedFailure(
                    _SourceBoundedFailureCode.MISSING_CLASSIFICATION,
                    provider_date,
                    daily_key,
                ),
            )
    return tuple(published), tuple(no_session), tuple(suspended), None


def _canonical_dict(value: object) -> dict[str, object]:
    try:
        result = json.loads(canonical_bytes(value))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError("canonical value must be valid JSON") from error
    if type(result) is not dict:
        raise ValueError("canonical value must be an object")
    return result


def _daily_market_event(snapshot: SourceSnapshot, provider_date: str) -> MarketEvent:
    key = f"response/daily/{provider_date}.json"
    member = next(value for value in snapshot.members if value.member_key == key)
    response = _response(snapshot.member_bytes(key), _DAILY_FIELDS)
    if response.has_more or len(response.rows) != 1:
        raise ValueError("daily response is not one terminal row")
    row = response.rows[0]
    numeric = cast(tuple[_NumericToken, ...], row[2:])
    lexemes = tuple(value.lexeme for value in numeric)
    open_units, high_units, low_units, close_units, pre_close_units, change_units = (
        _units(value, 2) for value in numeric[:6]
    )
    pct_units = _units(numeric[6], 4)
    volume_units = _scaled_multiplier(numeric[7], 2, 100)
    try:
        amount_units = _scaled_multiplier(numeric[8], 5, 1000)
        amount_scale = Scale(0)
    except ValueError:
        amount_units = _scaled_multiplier(numeric[8], 5, 100_000)
        amount_scale = Scale(2)
    if not (
        0 < low_units <= open_units <= high_units
        and 0 < low_units <= close_units <= high_units
        and pre_close_units > 0
        and close_units - pre_close_units == change_units
        and volume_units >= 0
        and amount_units >= 0
    ):
        raise ValueError("daily economic invariants mismatch")

    bucket = _bucket_for_trade_date(provider_date)
    available_time = UtcInstant(member.acquired_at_epoch_nanoseconds)
    if available_time < bucket.interval_end_exclusive:
        raise ValueError("daily response is available before finality")
    price_scale = Scale(2)
    source_record_hash = _source_record_hash(
        cast(str, row[0]), cast(str, row[1]), lexemes
    )
    request_body = {
        "type": "tushare_cn_a_share_daily_normalization_request",
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "provenance_hash": snapshot.provenance_hash,
        "member_key": key,
        "member_content_hash": member.content_hash,
        "instrument_id": _INSTRUMENT,
        "provider_trade_date": provider_date,
        "bucket": bucket,
    }
    request = {
        **_canonical_dict(request_body),
        "request_hash": canonical_sha256(request_body),
    }
    raw_body = {
        "type": "tushare_cn_a_share_daily_raw_bar",
        "schema_version": 1,
        "instrument_id": _INSTRUMENT,
        "provider_ts_code": "000001.SZ",
        "provider_trade_date": provider_date,
        "bucket": bucket,
        "available_time": available_time,
        "open_lexeme": lexemes[0],
        "high_lexeme": lexemes[1],
        "low_lexeme": lexemes[2],
        "close_lexeme": lexemes[3],
        "pre_close_lexeme": lexemes[4],
        "change_lexeme": lexemes[5],
        "pct_change_lexeme": lexemes[6],
        "volume_lots_lexeme": lexemes[7],
        "amount_thousand_cny_lexeme": lexemes[8],
        "open_price": Price(open_units, price_scale, str(_INSTRUMENT), "CNY"),
        "high_price": Price(high_units, price_scale, str(_INSTRUMENT), "CNY"),
        "low_price": Price(low_units, price_scale, str(_INSTRUMENT), "CNY"),
        "close_price": Price(close_units, price_scale, str(_INSTRUMENT), "CNY"),
        "pre_close_price": Price(pre_close_units, price_scale, str(_INSTRUMENT), "CNY"),
        "change_units": change_units,
        "change_scale": 2,
        "pct_change": Rate(pct_units, Scale(4), "percent"),
        "volume": Quantity(volume_units, Scale(0), str(_INSTRUMENT)),
        "amount": Money(amount_units, amount_scale, "CNY"),
        "source_record_hash": source_record_hash,
        "limitations": _DAILY_LIMITATIONS,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    raw_bar_hash = canonical_sha256(raw_body)
    raw_bar = {**_canonical_dict(raw_body), "raw_bar_hash": raw_bar_hash}
    trace_body = {
        "type": "tushare_cn_a_share_daily_source_trace",
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "provenance_hash": snapshot.provenance_hash,
        "source_key": snapshot.provenance.source_key,
        "member_key": key,
        "member_content_hash": member.content_hash,
        "record_index": 0,
        "source_record_hash": source_record_hash,
        "raw_bar_hash": raw_bar_hash,
        "revision_id": member.content_hash,
        "supersedes_revision_id": None,
        "revision_closure_complete": False,
    }
    trace = {
        **_canonical_dict(trace_body),
        "trace_hash": canonical_sha256(trace_body),
    }
    execution_body = {
        "type": "tushare_cn_a_share_daily_execution_reference",
        "schema_version": 1,
        "raw_bar_hash": raw_bar_hash,
        "price_purpose": PricePurpose.EXECUTION_REFERENCE.value,
        "instrument_id": _INSTRUMENT,
        "bucket": bucket,
        "available_time": available_time,
        "open_price": raw_body["open_price"],
        "high_price": raw_body["high_price"],
        "low_price": raw_body["low_price"],
        "close_price": raw_body["close_price"],
        "volume": raw_body["volume"],
        "amount": raw_body["amount"],
    }
    execution = {
        **_canonical_dict(execution_body),
        "projection_hash": canonical_sha256(execution_body),
    }
    valuation_body = {
        "type": "tushare_cn_a_share_daily_valuation",
        "schema_version": 1,
        "raw_bar_hash": raw_bar_hash,
        "price_purpose": PricePurpose.VALUATION.value,
        "instrument_id": _INSTRUMENT,
        "valuation_at": bucket.interval_end_exclusive,
        "available_time": available_time,
        "close_price": raw_body["close_price"],
    }
    valuation = {
        **_canonical_dict(valuation_body),
        "projection_hash": canonical_sha256(valuation_body),
    }
    normalization_body = {
        "type": "tushare_cn_a_share_daily_normalization_result",
        "schema_version": 1,
        "request": request,
        "snapshot": snapshot.to_canonical_dict(),
        "raw_bar": raw_bar,
        "trace": trace,
        "execution_reference": execution,
        "valuation": valuation,
    }
    normalization_hash = canonical_sha256(normalization_body)
    return MarketEvent(
        event_id=f"tushare-cn-a-share-daily-v1:{normalization_hash}",
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=_INSTRUMENT,
        event_time=bucket.interval_start,
        available_time=available_time,
        phase=_PHASE,
        source_sequence=SourceSequence(0),
        revision_id=member.content_hash,
        supersedes_revision_id=None,
        source_key=snapshot.provenance.source_key,
        source_hash=member.content_hash,
        payload={
            "normalization_hash": normalization_hash,
            "raw_bar": raw_bar,
            "source_trace": trace,
            "execution_reference": execution,
            "valuation": valuation,
            "qualification": {
                "revision_closure_complete": False,
                "historical_listing_status_qualified": False,
                "corporate_actions_qualified": False,
                "decision_grade_eligible": False,
                "deployment_authorized": False,
            },
        },
    )


def _normalize_events(
    snapshot: SourceSnapshot, published_dates: tuple[str, ...]
) -> tuple[MarketEvent, ...] | None:
    try:
        return tuple(
            _daily_market_event(snapshot, provider_date)
            for provider_date in published_dates
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _publication(events: tuple[MarketEvent, ...]) -> _BuiltPublication | None:
    outcome = validate_market_bundle_v1(
        bundle_key=_BUNDLE_KEY,
        schema_version=1,
        coverage_start=_COVERAGE_START,
        coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
        instrument_catalog_hash=_CATALOG_HASH,
        events=events,
    )
    if outcome.failure is not None or outcome.manifest is None:
        return None
    manifest = outcome.manifest
    if len(manifest.streams) != 1 or manifest.streams[0].stream_key != _STREAM_KEY:
        return None
    bundle_ref = MarketBundleRef.from_manifest(manifest)
    replay = validate_market_bundle_v1(
        bundle_key=_BUNDLE_KEY,
        schema_version=1,
        coverage_start=_COVERAGE_START,
        coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
        instrument_catalog_hash=_CATALOG_HASH,
        events=events,
    )
    if (
        replay.failure is not None
        or replay.manifest is None
        or canonical_bytes(replay.manifest) != canonical_bytes(manifest)
        or MarketBundleRef.from_manifest(replay.manifest) != bundle_ref
    ):
        return None
    return _BuiltPublication(
        events,
        bundle_ref,
        manifest.content_hash,
        manifest.streams[0].content_hash,
    )


def _requirement(
    snapshot: SourceSnapshot, purpose: PricePurpose
) -> PricePurposeRequirement:
    purpose_key = purpose.value.replace("_", "-")
    policy_suffix = (
        "exact-bucket" if purpose is PricePurpose.EXECUTION_REFERENCE else "exact-close"
    )
    return PricePurposeRequirement(
        requirement_key=(
            f"tushare_cn_a_share.daily.{purpose_key}.xshe.000001.20260706-20260730.v2"
        ),
        requirement_version=2,
        scope_key=(
            "tushare_cn_a_share.daily.source-bounded-purpose-scope."
            f"xshe.000001.20260706-20260730.{purpose_key}.v2"
        ),
        instrument_id=_INSTRUMENT,
        price_purpose=purpose,
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        coverage_start=_COVERAGE_START,
        coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
        stale_policy=BuilderStaleMarkPolicy(
            policy_key=(f"tushare_cn_a_share.daily.{purpose_key}.{policy_suffix}.v2"),
            policy_version=2,
            price_purpose=purpose,
            max_age_nanoseconds=0,
            allow_forward_fill=False,
        ),
        source_key=_SOURCE_KEY,
        source_hash=snapshot.snapshot_id,
    )


def _requirements(snapshot: SourceSnapshot) -> tuple[PricePurposeRequirement, ...]:
    return (
        _requirement(snapshot, PricePurpose.EXECUTION_REFERENCE),
        _requirement(snapshot, PricePurpose.VALUATION),
    )


def _purpose_valid(requirements: tuple[PricePurposeRequirement, ...]) -> bool:
    return (
        type(requirements) is tuple
        and len(requirements) == 2
        and tuple(value.price_purpose for value in requirements)
        == (PricePurpose.EXECUTION_REFERENCE, PricePurpose.VALUATION)
        and all(
            type(value) is PricePurposeRequirement
            and value.stream_key == _STREAM_KEY
            and value.event_type == _EVENT_TYPE
            and value.capability == _CAPABILITY
            and value.instrument_id == _INSTRUMENT
            and value.coverage_start == _COVERAGE_START
            and value.coverage_end_exclusive == _COVERAGE_END_EXCLUSIVE
            and value.stale_policy.max_age_nanoseconds == 0
            and not value.stale_policy.allow_forward_fill
            and not value.decision_grade_eligible
            and not value.deployment_authorized
            for value in requirements
        )
    )


def _lookahead_valid(
    publication: _BuiltPublication,
    published_dates: tuple[str, ...],
    snapshot: SourceSnapshot,
) -> bool:
    if len(publication.events) != len(published_dates):
        return False
    members = {value.member_key: value for value in snapshot.members}
    for provider_date, event in zip(published_dates, publication.events, strict=True):
        key = f"response/daily/{provider_date}.json"
        bucket = _bucket_for_trade_date(provider_date)
        raw_bar = cast(Mapping[str, object], event.payload["raw_bar"])
        if (
            event.stream_key != _STREAM_KEY
            or event.event_type != _EVENT_TYPE
            or event.capability != _CAPABILITY
            or event.instrument_id != _INSTRUMENT
            or event.event_time != bucket.interval_start
            or event.available_time.epoch_nanoseconds
            != members[key].acquired_at_epoch_nanoseconds
            or event.available_time < bucket.interval_end_exclusive
            or event.source_key != _SOURCE_KEY
            or event.source_hash != members[key].content_hash
            or event.supersedes_revision_id is not None
            or raw_bar["provider_trade_date"] != provider_date
            or raw_bar["available_time"] != event.available_time.to_canonical_dict()
        ):
            return False
    return True


def _report(
    *,
    receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    publication: _BuiltPublication,
    requirements: tuple[PricePurposeRequirement, ...],
    published_dates: tuple[str, ...],
    no_session_dates: tuple[str, ...],
    suspended_dates: tuple[str, ...],
    supersedes_report_hash: str | None,
) -> TushareCnAShareDailySourceBoundedObservationReportV2:
    return TushareCnAShareDailySourceBoundedObservationReportV2(
        provider_key=_PROVIDER_KEY,
        datasets=_DATASETS,
        instrument_id=_INSTRUMENT,
        venue_calendar=_VENUE_CALENDAR,
        provider_exchange=_PROVIDER_EXCHANGE,
        coverage_start=_COVERAGE_START,
        coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
        acquisition_receipt_sha256=_digest(receipt_bytes),
        snapshot_id=snapshot.snapshot_id,
        snapshot_content_tree_hash=snapshot.content_tree_hash,
        provenance_hash=snapshot.provenance_hash,
        member_keys=tuple(value.member_key for value in snapshot.members),
        member_content_hashes=tuple(value.content_hash for value in snapshot.members),
        member_acquired_at_epoch_nanoseconds=tuple(
            value.acquired_at_epoch_nanoseconds for value in snapshot.members
        ),
        bundle_ref=publication.bundle_ref,
        manifest_content_hash=publication.manifest_content_hash,
        stream_content_hash=publication.stream_content_hash,
        published_event_hashes=tuple(value.event_hash for value in publication.events),
        price_purpose_requirement_hashes=tuple(
            value.requirement_hash for value in requirements
        ),
        published_provider_dates=published_dates,
        no_session_provider_dates=no_session_dates,
        suspended_provider_dates=suspended_dates,
        observed_at=UtcInstant(
            max(value.acquired_at_epoch_nanoseconds for value in snapshot.members)
        ),
        supersedes_report_hash=supersedes_report_hash,
        limitations=_LIMITATIONS,
        availability_closure_complete=False,
        revision_closure_complete=False,
        generic_price_bars_capability=False,
        g12i_analyzer_ready=False,
        provider_qualified=False,
        historical_listing_status_qualified=False,
        corporate_actions_qualified=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
    )


def observe_tushare_cn_a_share_daily_source_bounded_v2(
    acquisition_receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    supersedes_report: TushareCnAShareDailySourceBoundedObservationReportV2
    | None = None,
) -> TushareCnAShareDailySourceBoundedObservationOutcomeV2:
    if (
        type(acquisition_receipt_bytes) is not bytes
        or type(snapshot) is not SourceSnapshot
    ):
        return _failed(_SourceBoundedFailureCode.INVALID_INPUT)
    trusted_supersedes = None
    if supersedes_report is not None:
        trusted_supersedes = _reconstruct_report(supersedes_report)
        if trusted_supersedes is None:
            return _failed(_SourceBoundedFailureCode.INVALID_INPUT)

    evidence = _evidence(acquisition_receipt_bytes, snapshot)
    if evidence is None:
        return _failed(_SourceBoundedFailureCode.EVIDENCE_INVALID)
    receipt, snapshot = evidence
    if not _request_scope(receipt, snapshot):
        return _failed(_SourceBoundedFailureCode.REQUEST_SCOPE_MISMATCH)

    responses, response_failure = _responses(receipt, snapshot)
    if response_failure is not None:
        return TushareCnAShareDailySourceBoundedObservationOutcomeV2(
            failure=response_failure
        )
    page_failure = _page_failure(responses)
    if page_failure is not None:
        return TushareCnAShareDailySourceBoundedObservationOutcomeV2(
            failure=page_failure
        )
    coordinate_failure = _coordinates_valid(responses)
    if coordinate_failure is not None:
        return TushareCnAShareDailySourceBoundedObservationOutcomeV2(
            failure=coordinate_failure
        )
    published, no_session, suspended, classification_failure = _classify(responses)
    if classification_failure is not None:
        return TushareCnAShareDailySourceBoundedObservationOutcomeV2(
            failure=classification_failure
        )

    events = _normalize_events(snapshot, published)
    if events is None:
        return _failed(_SourceBoundedFailureCode.NORMALIZATION_FAILED)
    publication = _publication(events)
    if publication is None:
        return _failed(_SourceBoundedFailureCode.PUBLICATION_FAILED)
    requirements = _requirements(snapshot)
    if not _purpose_valid(requirements):
        return _failed(_SourceBoundedFailureCode.PURPOSE_SCOPE_MISMATCH)
    if not _lookahead_valid(publication, published, snapshot):
        return _failed(_SourceBoundedFailureCode.LOOKAHEAD_VIOLATION)

    supersedes_hash = None
    if trusted_supersedes is not None:
        if (
            trusted_supersedes.provider_key != _PROVIDER_KEY
            or trusted_supersedes.datasets != _DATASETS
            or trusted_supersedes.instrument_id != _INSTRUMENT
            or trusted_supersedes.coverage_start != _COVERAGE_START
            or trusted_supersedes.coverage_end_exclusive != _COVERAGE_END_EXCLUSIVE
            or trusted_supersedes.snapshot_id == snapshot.snapshot_id
            or trusted_supersedes.acquisition_receipt_sha256
            == _digest(acquisition_receipt_bytes)
            or trusted_supersedes.observed_at.epoch_nanoseconds
            >= max(value.acquired_at_epoch_nanoseconds for value in snapshot.members)
        ):
            return _failed(_SourceBoundedFailureCode.REPORT_BINDING_MISMATCH)
        supersedes_hash = trusted_supersedes.report_hash
    try:
        report = _report(
            receipt_bytes=acquisition_receipt_bytes,
            snapshot=snapshot,
            publication=publication,
            requirements=requirements,
            published_dates=published,
            no_session_dates=no_session,
            suspended_dates=suspended,
            supersedes_report_hash=supersedes_hash,
        )
        trusted_report = _reconstruct_report(report)
        if trusted_report is None or canonical_bytes(trusted_report) != canonical_bytes(
            report
        ):
            raise ValueError("report replay mismatch")
    except (AttributeError, TypeError, ValueError):
        return _failed(_SourceBoundedFailureCode.REPORT_BINDING_MISMATCH)
    return TushareCnAShareDailySourceBoundedObservationOutcomeV2(report=trusted_report)
