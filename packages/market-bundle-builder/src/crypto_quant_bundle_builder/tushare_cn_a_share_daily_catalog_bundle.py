from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

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
from crypto_quant_market_data import MarketBundleCapability, MarketEvent

from .tushare_cn_a_share_daily import TushareCnAShareDailyNormalizationResult
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
    return json.loads(
        source.decode("utf-8"),
        parse_constant=_constant,
        object_pairs_hook=_duplicate_free_object,
    )


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
        _text("detail", value.get("detail"), nonempty=False)
    except (TypeError, ValueError):
        return None
    if type(value.get("code")) is not int or value.get("code") != 0:
        return None
    if type(value.get("msg")) is not str or value.get("msg") != "":
        return None
    data = value.get("data")
    if type(data) is not dict or set(data) != {"fields", "items", "has_more", "count"}:
        return None
    if data.get("has_more") is not False:
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


def _catalog_valid(value: object) -> bool:
    if type(value) is not InstrumentCatalog:
        return False
    try:
        if (
            type(value.currencies) is not tuple
            or type(value.instruments) is not tuple
            or type(value.symbol_timelines) is not tuple
            or len(value.currencies) != 1
            or len(value.instruments) != 1
            or value.symbol_timelines
        ):
            return False
        currency = value.currencies[0]
        definition = value.instruments[0]
        if type(currency) is not CurrencyId or type(definition) is not InstrumentDefinition:
            return False
        instrument = definition.instrument_id
        if type(instrument) is not InstrumentId or type(instrument.venue) is not VenueId:
            return False
        rebuilt = InstrumentCatalog(
            currencies=(CurrencyId(currency.value),),
            instruments=(
                InstrumentDefinition(
                    InstrumentId(VenueId(instrument.venue.value), instrument.stable_key),
                    InstrumentType(definition.instrument_type.value),
                    None if definition.base_currency is None else CurrencyId(definition.base_currency.value),
                    CurrencyId(definition.quote_currency.value),
                    CurrencyId(definition.settlement_currency.value),
                ),
            ),
            symbol_timelines=(),
        )
    except (AttributeError, TypeError, ValueError):
        return False
    expected = _catalog()
    return rebuilt == value == expected and canonical_bytes(value) == canonical_bytes(expected)


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
        if self.source_key != _SOURCE_KEY or self.member_key != _MEMBER_KEY:
            raise ValueError("catalog source identity mismatch")
        if self.member_content_hash != _MEMBER_CONTENT_HASH:
            raise ValueError("catalog source member hash mismatch")
        if type(self.record_index) is not int or self.record_index != 0:
            raise ValueError("catalog source record index mismatch")
        if type(self.acquired_at) is not UtcInstant:
            raise TypeError("catalog source acquisition time must be exact UtcInstant")
        try:
            rebuilt_time = UtcInstant(self.acquired_at.epoch_nanoseconds)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("catalog source acquisition time is invalid") from error
        if rebuilt_time != self.acquired_at:
            raise ValueError("catalog source acquisition time reconstruction mismatch")
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
        if row != _ROW or any(type(value) is not str for value in row[:-1]) or row[-1] is not None:
            raise ValueError("catalog source row mismatch")
        for index, value in enumerate(row[:-1]):
            _text(f"catalog source row[{index}]", value, nonempty=False)
        if self.source_record_hash != _source_record_hash(row):
            raise ValueError("catalog source record hash mismatch")
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


def _reconstruct_normalization(
    value: object,
) -> TushareCnAShareDailyNormalizationResult | None:
    if type(value) is not TushareCnAShareDailyNormalizationResult:
        return None
    try:
        rebuilt = TushareCnAShareDailyNormalizationResult(
            value.request,
            value.snapshot,
            value.raw_bar,
            value.trace,
            value.execution_reference,
            value.valuation,
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt if rebuilt == value else None


def _reconstruct_source(
    value: object,
) -> TushareCnAShareAcquisitionCatalogSource | None:
    if type(value) is not TushareCnAShareAcquisitionCatalogSource:
        return None
    try:
        rebuilt = TushareCnAShareAcquisitionCatalogSource(
            **{field: getattr(value, field) for field in value.__dataclass_fields__}
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt if rebuilt == value else None


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
            "instrument_catalog": json.loads(canonical_bytes(instrument_catalog)),
            "instrument_catalog_hash": instrument_catalog_hash,
            "catalog_source": json.loads(canonical_bytes(catalog_source)),
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
        if not _catalog_valid(self.instrument_catalog):
            raise ValueError("instrument catalog is invalid")
        source = _reconstruct_source(self.catalog_source)
        if source is None:
            raise ValueError("catalog source is invalid")
        if source.acquired_at != rebuilt.raw_bar.available_time:
            raise ValueError("catalog source acquisition time mismatch")
        expected_source = _catalog_source(
            rebuilt,
            rebuilt.raw_bar.available_time,
            self.instrument_catalog,
        )
        if source != expected_source or canonical_bytes(source) != canonical_bytes(expected_source):
            raise ValueError("catalog source binding mismatch")
        try:
            v1 = project_tushare_cn_a_share_daily_market_event_v1(rebuilt)
            expected_event = _market_event(
                rebuilt,
                v1,
                self.instrument_catalog,
                source,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("market event authority is invalid") from error
        if type(self.market_event) is not MarketEvent:
            raise TypeError("market event must be exact MarketEvent")
        if (
            self.market_event != expected_event
            or canonical_bytes(self.market_event) != canonical_bytes(expected_event)
        ):
            raise ValueError("market event binding mismatch")

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
            "instrument_catalog": json.loads(canonical_bytes(self.instrument_catalog)),
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "catalog_source": self.catalog_source.to_canonical_dict(),
            "catalog_binding_hash": self.catalog_binding_hash,
            "market_event": json.loads(canonical_bytes(self.market_event)),
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
    rebuilt = _reconstruct_normalization(result)
    if rebuilt is None:
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.NORMALIZATION_AUTHORITY_INVALID
        )
    try:
        v1 = project_tushare_cn_a_share_daily_market_event_v1(rebuilt)
    except (AttributeError, TypeError, ValueError):
        return _failed(
            TushareCnAShareDailyCatalogPublicationFailureCode.NORMALIZATION_AUTHORITY_INVALID
        )

    candidates = tuple(
        member
        for member in rebuilt.snapshot.members
        if member.member_key != rebuilt.request.member_key
    )
    source_bytes: bytes | None = None
    if len(candidates) == 1:
        try:
            source_bytes = rebuilt.snapshot.member_bytes(candidates[0].member_key)
        except (AttributeError, TypeError, ValueError):
            return _failed(
                TushareCnAShareDailyCatalogPublicationFailureCode.NORMALIZATION_AUTHORITY_INVALID
            )

    if not _scope_matches(rebuilt):
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
