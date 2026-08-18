from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SessionId,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent

from .bar_aggregation import BarBucket
from .source_snapshots import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from .tushare_cn_a_share_daily import (
    TushareCnAShareDailyNormalizationRequest,
    TushareCnAShareDailyNormalizationResult,
    normalize_tushare_cn_a_share_daily_v1,
)
from .tushare_cn_a_share_daily_bundle import (
    project_tushare_cn_a_share_daily_market_event_v1,
)

_SCHEMA_VERSION = 1
_MEMBER_KEY = "response/stock-basic.json"
_MEMBER_CONTENT_HASH = "sha256:d78fc472268deacb5af7c59c113325e2a00c5b4619c53fbbfe6fa23c96d471d2"
_SOURCE_KEY = "tushare.pro.daily_listing.000001.sz.20240102"
_STREAM_KEY = "tushare_cn_a_share.daily.publication.xshe.000001.v2"
_EVENT_TYPE = "tushare_cn_a_share_daily_publication.v2"
_CAPABILITY = MarketBundleCapability("tushare_cn_a_share.daily-publications", 2)
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_CURRENCY = CurrencyId("CNY")
_FIELDS = (
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "market",
    "exchange",
    "list_status",
    "list_date",
    "delist_date",
)
_ROW = (
    "000001.SZ",
    "000001",
    "平安银行",
    "深圳",
    "银行",
    "主板",
    "SZSE",
    "L",
    "19910403",
    None,
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _text(name: str, value: object, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value) or value != value.strip():
        raise ValueError(f"{name} must be canonical text")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be NFC text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8 text") from error
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if _HASH.fullmatch(text) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return text


def _constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _duplicate_free_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
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
            parse_constant=_constant,
            object_pairs_hook=_duplicate_free_object,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("invalid stock_basic JSON") from error


def _canonical_json(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise RuntimeError("trusted canonical serialization failed") from error


def _schema_row(value: object) -> tuple[object, ...] | None:
    if type(value) is not dict or set(value) != {
        "request_id",
        "code",
        "data",
        "msg",
        "detail",
    }:
        return None
    try:
        _text("request_id", value.get("request_id"))
    except (TypeError, ValueError):
        return None
    if type(value.get("detail")) is not str:
        return None
    if type(value.get("code")) is not int or value.get("code") != 0:
        return None
    if type(value.get("msg")) is not str or value.get("msg") != "":
        return None
    data = value.get("data")
    if type(data) is not dict or set(data) != {"fields", "items", "has_more", "count"}:
        return None
    has_more = data.get("has_more")
    if type(has_more) is not bool or has_more:
        return None
    if type(data.get("count")) is not int or data.get("count") != 0:
        return None
    fields = data.get("fields")
    items = data.get("items")
    if type(fields) is not list or tuple(fields) != _FIELDS:
        return None
    if type(items) is not list or len(items) != 1:
        return None
    row = items[0]
    if type(row) is not list or len(row) != len(_FIELDS):
        return None
    if any(type(item) is not str for item in row[:-1]) or (
        row[-1] is not None and type(row[-1]) is not str
    ):
        return None
    try:
        for index, item in enumerate(row):
            if item is not None:
                _text(f"row[{index}]", item, nonempty=False)
    except (TypeError, ValueError):
        return None
    return tuple(row)


def _catalog() -> InstrumentCatalog:
    return InstrumentCatalog(
        currencies=(_CURRENCY,),
        instruments=(
            InstrumentDefinition(
                instrument_id=_INSTRUMENT,
                instrument_type=InstrumentType.EQUITY,
                base_currency=None,
                quote_currency=_CURRENCY,
                settlement_currency=_CURRENCY,
            ),
        ),
        symbol_timelines=(),
    )


def _utc(value: object) -> UtcInstant:
    if type(value) is not UtcInstant or type(value.epoch_nanoseconds) is not int:
        raise TypeError("instant must be exact UtcInstant")
    return UtcInstant(value.epoch_nanoseconds)


def _instrument(value: object) -> InstrumentId:
    if type(value) is not InstrumentId or type(value.venue) is not VenueId:
        raise TypeError("instrument must be exact InstrumentId")
    venue = _text("instrument venue", value.venue.value)
    stable_key = _text("instrument stable key", value.stable_key)
    return InstrumentId(VenueId(venue), stable_key)


def _reconstruct_catalog(value: object) -> InstrumentCatalog | None:
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
            or type(currency.value) is not str
            or currency.value != "CNY"
            or type(definition) is not InstrumentDefinition
            or type(definition.instrument_type) is not InstrumentType
            or definition.instrument_type is not InstrumentType.EQUITY
            or definition.base_currency is not None
            or type(definition.quote_currency) is not CurrencyId
            or type(definition.quote_currency.value) is not str
            or definition.quote_currency.value != "CNY"
            or type(definition.settlement_currency) is not CurrencyId
            or type(definition.settlement_currency.value) is not str
            or definition.settlement_currency.value != "CNY"
        ):
            return None
        instrument = _instrument(definition.instrument_id)
        if instrument.venue.value != "xshe" or instrument.stable_key != "000001":
            return None
    except Exception:  # noqa: BLE001 - reject hostile authority objects atomically
        return None
    return _catalog()


def _source_record_hash(row: tuple[object, ...]) -> str:
    return canonical_sha256(
        {
            "type": "tushare_cn_a_share_acquisition_catalog_source_record",
            "schema_version": _SCHEMA_VERSION,
            "fields": _FIELDS,
            "values": row,
        }
    )


def _catalog_binding_hash(
    normalization_hash: str,
    instrument_catalog_hash: str,
    catalog_source_hash: str,
) -> str:
    return canonical_sha256(
        {
            "type": "tushare_cn_a_share_daily_catalog_binding",
            "schema_version": _SCHEMA_VERSION,
            "normalization_hash": normalization_hash,
            "instrument_catalog_hash": instrument_catalog_hash,
            "catalog_source_hash": catalog_source_hash,
        }
    )


@dataclass(frozen=True, slots=True)
class TushareCnAShareAcquisitionCatalogSource:
    snapshot_id: str
    provenance_hash: str
    source_key: str
    member_key: str
    member_content_hash: str
    record_index: int
    acquired_at: UtcInstant
    provider_ts_code: str
    provider_symbol: str
    provider_name: str
    provider_area: str
    provider_industry: str
    provider_market: str
    provider_exchange: str
    provider_list_status: str
    provider_list_date: str
    provider_delist_date: str | None
    source_record_hash: str
    instrument_catalog_hash: str
    current_metadata_only: bool
    provider_revision_id: str | None
    revision_closure_complete: bool
    historical_listing_status_qualified: bool
    survivorship_bias_safe: bool
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        _hash("snapshot_id", self.snapshot_id)
        _hash("provenance_hash", self.provenance_hash)
        _text("source_key", self.source_key)
        _text("member_key", self.member_key)
        if self.source_key != _SOURCE_KEY or self.member_key != _MEMBER_KEY:
            raise ValueError("catalog source identity mismatch")
        _hash("member_content_hash", self.member_content_hash)
        if self.member_content_hash != _MEMBER_CONTENT_HASH:
            raise ValueError("catalog source member hash mismatch")
        if type(self.record_index) is not int or self.record_index != 0:
            raise ValueError("catalog source record index mismatch")
        try:
            rebuilt_time = _utc(self.acquired_at)
        except Exception as error:
            raise ValueError("catalog source acquisition time is invalid") from error
        object.__setattr__(self, "acquired_at", rebuilt_time)
        row = (
            self.provider_ts_code,
            self.provider_symbol,
            self.provider_name,
            self.provider_area,
            self.provider_industry,
            self.provider_market,
            self.provider_exchange,
            self.provider_list_status,
            self.provider_list_date,
            self.provider_delist_date,
        )
        if any(type(value) is not str for value in row[:-1]) or row[-1] is not None:
            raise TypeError("catalog source row must use exact string primitives")
        for index, value in enumerate(row[:-1]):
            _text(f"catalog source row[{index}]", value, nonempty=False)
        if row != _ROW:
            raise ValueError("catalog source row mismatch")
        _hash("source_record_hash", self.source_record_hash)
        if self.source_record_hash != _source_record_hash(row):
            raise ValueError("catalog source record hash mismatch")
        _hash("instrument_catalog_hash", self.instrument_catalog_hash)
        if self.instrument_catalog_hash != canonical_sha256(_catalog()):
            raise ValueError("catalog source catalog hash mismatch")
        if type(self.current_metadata_only) is not bool or not self.current_metadata_only:
            raise ValueError("catalog source must remain current metadata only")
        if self.provider_revision_id is not None:
            raise ValueError("provider revision id must remain null")
        for name in (
            "revision_closure_complete",
            "historical_listing_status_qualified",
            "survivorship_bias_safe",
            "decision_grade_eligible",
            "deployment_authorized",
        ):
            value = getattr(self, name)
            if type(value) is not bool or value:
                raise ValueError(f"{name} must remain false")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_acquisition_catalog_source",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "provenance_hash": self.provenance_hash,
            "source_key": self.source_key,
            "member_key": self.member_key,
            "member_content_hash": self.member_content_hash,
            "record_index": self.record_index,
            "acquired_at": self.acquired_at.to_canonical_dict(),
            "provider_ts_code": self.provider_ts_code,
            "provider_symbol": self.provider_symbol,
            "provider_name": self.provider_name,
            "provider_area": self.provider_area,
            "provider_industry": self.provider_industry,
            "provider_market": self.provider_market,
            "provider_exchange": self.provider_exchange,
            "provider_list_status": self.provider_list_status,
            "provider_list_date": self.provider_list_date,
            "provider_delist_date": self.provider_delist_date,
            "source_record_hash": self.source_record_hash,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "current_metadata_only": self.current_metadata_only,
            "provider_revision_id": self.provider_revision_id,
            "revision_closure_complete": self.revision_closure_complete,
            "historical_listing_status_qualified": self.historical_listing_status_qualified,
            "survivorship_bias_safe": self.survivorship_bias_safe,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def catalog_source_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "catalog_source_hash": self.catalog_source_hash}


class TushareCnAShareDailyCatalogPublicationFailureCode(str, Enum):
    NORMALIZATION_AUTHORITY_INVALID = "normalization_authority_invalid"
    SNAPSHOT_SCOPE_MISMATCH = "snapshot_scope_mismatch"
    CATALOG_MEMBER_MISSING = "catalog_member_missing"
    CATALOG_JSON_INVALID = "catalog_json_invalid"
    CATALOG_SCHEMA_MISMATCH = "catalog_schema_mismatch"
    CATALOG_MEMBER_BINDING_MISMATCH = "catalog_member_binding_mismatch"


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyCatalogPublicationFailure:
    code: TushareCnAShareDailyCatalogPublicationFailureCode

    def __post_init__(self) -> None:
        if type(self.code) is not TushareCnAShareDailyCatalogPublicationFailureCode:
            raise TypeError("code must be exact catalog publication failure code")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_catalog_publication_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


def _reconstruct_bucket(value: object) -> BarBucket:
    if type(value) is not BarBucket:
        raise TypeError("bucket must be exact BarBucket")
    session = value.session_id
    trading_date = value.trading_date
    if (
        type(session) is not SessionId
        or type(session.calendar_id) is not str
        or type(session.value) is not str
        or type(trading_date) is not TradingDate
        or type(trading_date.calendar_id) is not str
        or type(trading_date.value) is not date
    ):
        raise TypeError("bucket identity values must use exact types")
    if type(value.included_spans) is not tuple:
        raise TypeError("bucket spans must be exact tuple")
    spans: list[tuple[UtcInstant, UtcInstant]] = []
    for span in value.included_spans:
        if type(span) is not tuple or len(span) != 2:
            raise TypeError("bucket span must be exact pair")
        spans.append((_utc(span[0]), _utc(span[1])))
    trusted_date = date(
        trading_date.value.year,
        trading_date.value.month,
        trading_date.value.day,
    )
    return BarBucket(
        SessionId(_text("session calendar", session.calendar_id), _text("session", session.value)),
        TradingDate(_text("trading calendar", trading_date.calendar_id), trusted_date),
        tuple(spans),
        _utc(value.interval_start),
        _utc(value.interval_end_exclusive),
    )


def _reconstruct_snapshot(value: object) -> SourceSnapshot:
    if type(value) is not SourceSnapshot or type(value.archive_bytes) is not bytes:
        raise TypeError("snapshot must be exact SourceSnapshot")
    _hash("snapshot_id", value.snapshot_id)
    _hash("content_tree_hash", value.content_tree_hash)
    _hash("provenance_hash", value.provenance_hash)
    if (
        type(value.decision_grade_eligible) is not bool
        or type(value.deployment_authorized) is not bool
        or value.decision_grade_eligible
        or value.deployment_authorized
        or type(value.members) is not tuple
        or type(value.provenance) is not SourceSnapshotProvenance
    ):
        raise ValueError("snapshot authority values are invalid")
    provenance = SourceSnapshotProvenance(
        _text("vendor_key", value.provenance.vendor_key),
        _text("source_key", value.provenance.source_key),
        _text("license_ref", value.provenance.license_ref),
        _text("retention_policy_ref", value.provenance.retention_policy_ref),
    )
    raw_members: list[RawSourceMember] = []
    supplied_members: list[tuple[object, ...]] = []
    for member in value.members:
        if type(member) is not SourceSnapshotMember:
            raise TypeError("snapshot member must be exact SourceSnapshotMember")
        member_key = _text("member_key", member.member_key)
        content_hash = _hash("member content_hash", member.content_hash)
        if type(member.byte_count) is not int or member.byte_count < 0:
            raise TypeError("member byte_count must be exact integer")
        mode = _text("member mode", member.mode)
        if mode not in {"0644", "0755"}:
            raise ValueError("member mode is invalid")
        if type(member.acquired_at_epoch_nanoseconds) is not int:
            raise TypeError("member acquisition time must be exact integer")
        declared = member.declared_sha256
        if declared is not None:
            declared = _hash("member declared_sha256", declared)
        raw_bytes = value.member_bytes(member_key)
        if type(raw_bytes) is not bytes:
            raise TypeError("member bytes must be exact bytes")
        raw_members.append(
            RawSourceMember(
                member_key,
                bytes(raw_bytes),
                mode,
                member.acquired_at_epoch_nanoseconds,
                declared,
            )
        )
        supplied_members.append(
            (
                member_key,
                content_hash,
                member.byte_count,
                mode,
                member.acquired_at_epoch_nanoseconds,
                declared,
            )
        )
    outcome = freeze_source_snapshot(members=tuple(raw_members), provenance=provenance)
    if outcome.snapshot is None:
        raise ValueError("snapshot reconstruction failed")
    trusted = outcome.snapshot
    trusted_members = tuple(
        (
            member.member_key,
            member.content_hash,
            member.byte_count,
            member.mode,
            member.acquired_at_epoch_nanoseconds,
            member.declared_sha256,
        )
        for member in trusted.members
    )
    if (
        value.snapshot_id != trusted.snapshot_id
        or value.archive_bytes != trusted.archive_bytes
        or value.content_tree_hash != trusted.content_tree_hash
        or value.provenance_hash != trusted.provenance_hash
        or tuple(supplied_members) != trusted_members
    ):
        raise ValueError("snapshot reconstruction mismatch")
    return trusted


def _reconstruct_request(
    value: object,
    snapshot: SourceSnapshot,
) -> TushareCnAShareDailyNormalizationRequest:
    if type(value) is not TushareCnAShareDailyNormalizationRequest:
        raise TypeError("request must be exact normalization request")
    if type(value.schema_version) is not int:
        raise TypeError("request schema must be exact integer")
    request = TushareCnAShareDailyNormalizationRequest(
        value.schema_version,
        _hash("request snapshot_id", value.snapshot_id),
        _hash("request provenance_hash", value.provenance_hash),
        _text("request member_key", value.member_key),
        _hash("request member_content_hash", value.member_content_hash),
        _instrument(value.instrument_id),
        _text("provider_trade_date", value.provider_trade_date),
        _reconstruct_bucket(value.bucket),
    )
    if request.snapshot_id != snapshot.snapshot_id or request.provenance_hash != snapshot.provenance_hash:
        raise ValueError("request snapshot binding mismatch")
    return request


def _reconstruct_normalization(
    value: object,
) -> TushareCnAShareDailyNormalizationResult | None:
    try:
        if type(value) is not TushareCnAShareDailyNormalizationResult:
            return None
        validated = TushareCnAShareDailyNormalizationResult(
            value.request,
            value.snapshot,
            value.raw_bar,
            value.trace,
            value.execution_reference,
            value.valuation,
        )
        snapshot = _reconstruct_snapshot(value.snapshot)
        request = _reconstruct_request(value.request, snapshot)
        outcome = normalize_tushare_cn_a_share_daily_v1(snapshot, request)
        trusted = outcome.result
        if trusted is None or canonical_bytes(validated) != canonical_bytes(trusted):
            return None
        return trusted
    except Exception:  # noqa: BLE001 - caller authority failures are data failures
        return None


def _reconstruct_source(
    value: object,
) -> TushareCnAShareAcquisitionCatalogSource | None:
    try:
        if type(value) is not TushareCnAShareAcquisitionCatalogSource:
            return None
        return TushareCnAShareAcquisitionCatalogSource(
            snapshot_id=value.snapshot_id,
            provenance_hash=value.provenance_hash,
            source_key=value.source_key,
            member_key=value.member_key,
            member_content_hash=value.member_content_hash,
            record_index=value.record_index,
            acquired_at=_utc(value.acquired_at),
            provider_ts_code=value.provider_ts_code,
            provider_symbol=value.provider_symbol,
            provider_name=value.provider_name,
            provider_area=value.provider_area,
            provider_industry=value.provider_industry,
            provider_market=value.provider_market,
            provider_exchange=value.provider_exchange,
            provider_list_status=value.provider_list_status,
            provider_list_date=value.provider_list_date,
            provider_delist_date=value.provider_delist_date,
            source_record_hash=value.source_record_hash,
            instrument_catalog_hash=value.instrument_catalog_hash,
            current_metadata_only=value.current_metadata_only,
            provider_revision_id=value.provider_revision_id,
            revision_closure_complete=value.revision_closure_complete,
            historical_listing_status_qualified=value.historical_listing_status_qualified,
            survivorship_bias_safe=value.survivorship_bias_safe,
            decision_grade_eligible=value.decision_grade_eligible,
            deployment_authorized=value.deployment_authorized,
        )
    except Exception:  # noqa: BLE001 - reject hostile authority objects atomically
        return None


def _catalog_source(
    result: TushareCnAShareDailyNormalizationResult,
    acquired_at: UtcInstant,
    instrument_catalog: InstrumentCatalog,
) -> TushareCnAShareAcquisitionCatalogSource:
    return TushareCnAShareAcquisitionCatalogSource(
        snapshot_id=result.snapshot.snapshot_id,
        provenance_hash=result.snapshot.provenance_hash,
        source_key=result.snapshot.provenance.source_key,
        member_key=_MEMBER_KEY,
        member_content_hash=_MEMBER_CONTENT_HASH,
        record_index=0,
        acquired_at=acquired_at,
        provider_ts_code=_ROW[0],
        provider_symbol=_ROW[1],
        provider_name=_ROW[2],
        provider_area=_ROW[3],
        provider_industry=_ROW[4],
        provider_market=_ROW[5],
        provider_exchange=_ROW[6],
        provider_list_status=_ROW[7],
        provider_list_date=_ROW[8],
        provider_delist_date=None,
        source_record_hash=_source_record_hash(_ROW),
        instrument_catalog_hash=canonical_sha256(instrument_catalog),
        current_metadata_only=True,
        provider_revision_id=None,
        revision_closure_complete=False,
        historical_listing_status_qualified=False,
        survivorship_bias_safe=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
    )


def _market_event(
    result: TushareCnAShareDailyNormalizationResult,
    v1: MarketEvent,
    instrument_catalog: InstrumentCatalog,
    catalog_source: TushareCnAShareAcquisitionCatalogSource,
) -> MarketEvent:
    instrument_catalog_hash = canonical_sha256(instrument_catalog)
    binding_hash = _catalog_binding_hash(
        result.normalization_hash,
        instrument_catalog_hash,
        catalog_source.catalog_source_hash,
    )
    return MarketEvent(
        event_id=f"tushare-cn-a-share-daily-v2:{binding_hash}",
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=v1.instrument_id,
        event_time=v1.event_time,
        available_time=v1.available_time,
        phase=v1.phase,
        source_sequence=v1.source_sequence,
        revision_id=v1.revision_id,
        supersedes_revision_id=v1.supersedes_revision_id,
        source_key=v1.source_key,
        source_hash=v1.source_hash,
        payload={
            "normalization_hash": v1.payload["normalization_hash"],
            "raw_bar": v1.payload["raw_bar"],
            "source_trace": v1.payload["source_trace"],
            "execution_reference": v1.payload["execution_reference"],
            "valuation": v1.payload["valuation"],
            "instrument_catalog": _canonical_json(instrument_catalog),
            "instrument_catalog_hash": instrument_catalog_hash,
            "catalog_source": _canonical_json(catalog_source),
            "catalog_binding_hash": binding_hash,
            "qualification": {
                "current_metadata_only": True,
                "provider_revision_id": None,
                "provider_revision_closure_complete": False,
                "revision_closure_complete": False,
                "historical_listing_status_qualified": False,
                "survivorship_bias_safe": False,
                "corporate_actions_qualified": False,
                "decision_grade_eligible": False,
                "deployment_authorized": False,
            },
        },
    )


def _primitive(value: object) -> object:
    if value is None or type(value) in (bool, int, str):
        if type(value) is str:
            _text("event payload string", value, nonempty=False)
        return value
    if type(value) is tuple:
        return tuple(_primitive(item) for item in value)
    if type(value) is MappingProxyType:
        result: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("event payload key must be exact string")
            _text("event payload key", key, nonempty=False)
            result[key] = _primitive(item)
        return result
    raise TypeError("event payload contains untrusted nested value")


def _reconstruct_event(value: object) -> MarketEvent | None:
    try:
        if type(value) is not MarketEvent:
            return None
        capability = value.capability
        if (
            type(capability) is not MarketBundleCapability
            or type(capability.key) is not str
            or type(capability.version) is not int
        ):
            return None
        instrument = None if value.instrument_id is None else _instrument(value.instrument_id)
        phase = value.phase
        sequence = value.source_sequence
        if (
            type(phase) is not TimelinePhase
            or type(phase.rank) is not int
            or type(phase.code) is not str
            or type(sequence) is not SourceSequence
            or type(sequence.value) is not int
        ):
            return None
        supersedes = value.supersedes_revision_id
        if supersedes is not None:
            supersedes = _text("supersedes_revision_id", supersedes)
        payload = _primitive(value.payload)
        if type(payload) is not dict:
            return None
        return MarketEvent(
            event_id=_text("event_id", value.event_id),
            stream_key=_text("stream_key", value.stream_key),
            event_type=_text("event_type", value.event_type),
            capability=MarketBundleCapability(
                _text("capability key", capability.key),
                capability.version,
            ),
            instrument_id=instrument,
            event_time=_utc(value.event_time),
            available_time=_utc(value.available_time),
            phase=TimelinePhase(phase.rank, _text("phase code", phase.code)),
            source_sequence=SourceSequence(sequence.value),
            revision_id=_text("revision_id", value.revision_id),
            supersedes_revision_id=supersedes,
            source_key=_text("event source_key", value.source_key),
            source_hash=_hash("event source_hash", value.source_hash),
            payload=payload,
        )
    except Exception:  # noqa: BLE001 - reject hostile authority objects atomically
        return None


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyCatalogPublicationResult:
    normalization_result: TushareCnAShareDailyNormalizationResult
    instrument_catalog: InstrumentCatalog
    catalog_source: TushareCnAShareAcquisitionCatalogSource
    market_event: MarketEvent

    def __post_init__(self) -> None:
        rebuilt = _reconstruct_normalization(self.normalization_result)
        if rebuilt is None:
            raise ValueError("normalization authority is invalid")
        instrument_catalog = _reconstruct_catalog(self.instrument_catalog)
        if instrument_catalog is None:
            raise ValueError("instrument catalog is invalid")
        source = _reconstruct_source(self.catalog_source)
        if source is None:
            raise ValueError("catalog source is invalid")
        if source.acquired_at != rebuilt.raw_bar.available_time:
            raise ValueError("catalog source acquisition time mismatch")
        expected_source = _catalog_source(
            rebuilt,
            rebuilt.raw_bar.available_time,
            instrument_catalog,
        )
        if canonical_bytes(source) != canonical_bytes(expected_source):
            raise ValueError("catalog source binding mismatch")
        event = _reconstruct_event(self.market_event)
        if event is None:
            raise ValueError("market event authority is invalid")
        v1 = project_tushare_cn_a_share_daily_market_event_v1(rebuilt)
        expected_event = _market_event(
            rebuilt,
            v1,
            instrument_catalog,
            source,
        )
        if canonical_bytes(event) != canonical_bytes(expected_event):
            raise ValueError("market event binding mismatch")
        object.__setattr__(self, "normalization_result", rebuilt)
        object.__setattr__(self, "instrument_catalog", instrument_catalog)
        object.__setattr__(self, "catalog_source", source)
        object.__setattr__(self, "market_event", event)

    @property
    def instrument_catalog_hash(self) -> str:
        return canonical_sha256(self.instrument_catalog)

    @property
    def catalog_binding_hash(self) -> str:
        return _catalog_binding_hash(
            self.normalization_result.normalization_hash,
            self.instrument_catalog_hash,
            self.catalog_source.catalog_source_hash,
        )

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_catalog_publication_result",
            "schema_version": _SCHEMA_VERSION,
            "normalization_hash": self.normalization_result.normalization_hash,
            "instrument_catalog": _canonical_json(self.instrument_catalog),
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "catalog_source": self.catalog_source.to_canonical_dict(),
            "catalog_binding_hash": self.catalog_binding_hash,
            "market_event": _canonical_json(self.market_event),
        }

    @property
    def publication_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "publication_hash": self.publication_hash}


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailyCatalogPublicationOutcome:
    result: TushareCnAShareDailyCatalogPublicationResult | None = None
    failure: TushareCnAShareDailyCatalogPublicationFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one result or failure")
        if self.result is not None and type(self.result) is not TushareCnAShareDailyCatalogPublicationResult:
            raise TypeError("result must be exact catalog publication result")
        if self.failure is not None and type(self.failure) is not TushareCnAShareDailyCatalogPublicationFailure:
            raise TypeError("failure must be exact catalog publication failure")


def _failed(
    code: TushareCnAShareDailyCatalogPublicationFailureCode,
) -> TushareCnAShareDailyCatalogPublicationOutcome:
    return TushareCnAShareDailyCatalogPublicationOutcome(
        failure=TushareCnAShareDailyCatalogPublicationFailure(code)
    )


def _scope_matches(result: TushareCnAShareDailyNormalizationResult) -> bool:
    provenance = result.snapshot.provenance
    return (
        provenance.vendor_key == "tushare.pro"
        and provenance.source_key == _SOURCE_KEY
        and provenance.license_ref == "tushare.pro.terms"
        and provenance.retention_policy_ref == "backtest.acquisition.candidate"
    )


def project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(
    result: TushareCnAShareDailyNormalizationResult,
) -> TushareCnAShareDailyCatalogPublicationOutcome:
    try:
        rebuilt = _reconstruct_normalization(result)
        if rebuilt is None:
            raise ValueError("normalization reconstruction failed")
        v1 = project_tushare_cn_a_share_daily_market_event_v1(rebuilt)
        candidates = tuple(
            member
            for member in rebuilt.snapshot.members
            if member.member_key != rebuilt.request.member_key
        )
        source_bytes: bytes | None = None
        if len(candidates) == 1:
            source_bytes = rebuilt.snapshot.member_bytes(candidates[0].member_key)
        scope_matches = _scope_matches(rebuilt)
    except Exception:  # noqa: BLE001 - frozen authority failures map to one code
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.NORMALIZATION_AUTHORITY_INVALID
        )

    if not scope_matches:
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.SNAPSHOT_SCOPE_MISMATCH
        )
    if not candidates:
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_MEMBER_MISSING
        )
    if len(candidates) != 1:
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_MEMBER_BINDING_MISMATCH
        )
    if source_bytes is None:
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.NORMALIZATION_AUTHORITY_INVALID
        )
    try:
        parsed = _parse(source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError):
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_JSON_INVALID
        )
    row = _schema_row(parsed)
    if row is None:
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_SCHEMA_MISMATCH
        )

    member = candidates[0]
    if (
        member.member_key != _MEMBER_KEY
        or member.content_hash != _MEMBER_CONTENT_HASH
        or member.acquired_at_epoch_nanoseconds
        != rebuilt.raw_bar.available_time.epoch_nanoseconds
        or row != _ROW
        or rebuilt.raw_bar.instrument_id != _INSTRUMENT
        or rebuilt.raw_bar.provider_ts_code != _ROW[0]
    ):
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_MEMBER_BINDING_MISMATCH
        )

    instrument_catalog = _catalog()
    catalog_source = _catalog_source(
        rebuilt,
        UtcInstant(member.acquired_at_epoch_nanoseconds),
        instrument_catalog,
    )
    market_event = _market_event(
        rebuilt,
        v1,
        instrument_catalog,
        catalog_source,
    )
    return TushareCnAShareDailyCatalogPublicationOutcome(
        result=TushareCnAShareDailyCatalogPublicationResult(
            rebuilt,
            instrument_catalog,
            catalog_source,
            market_event,
        )
    )
